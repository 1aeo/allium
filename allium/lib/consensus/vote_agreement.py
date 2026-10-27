"""Current-hour agreement of directory-authority votes for one relay.

This does not store votes. The counts use the votes already in the collector
relay index.
"""

import logging
from collections import Counter

from .consensus_evaluation import compute_flag_consensus

logger = logging.getLogger(__name__)

# MiddleOnly and BadExit are authority penalties, not ordinary disagreement.
AGREEMENT_FLAGS = ('Running', 'Valid', 'Fast', 'Stable', 'Guard', 'Exit', 'HSDir')
# Largest exact groups to name. Withheld flags come first, then assigned flags.
_DID_NOT_GROUPS = 2
_ASSIGNED_GROUPS = 1


def classify_authority_votes(votes_by_authority, measuring_authorities=None):
    """Agreement of one relay's latest votes, or None when nobody voted.

    A relay agrees when every voting authority assigned the same Running,
    Valid, Fast, Stable, Guard, Exit, and HSDir state. ``measuring_authorities``
    limits the measurement-split count to authorities whose votes carry
    Measured=. None means every vote can measure. An empty set means none can.
    """
    if not isinstance(votes_by_authority, dict) or not votes_by_authority:
        return None
    from .collector_fetcher import _authority_key, _vote_kb
    if measuring_authorities is None:
        measuring = None
    else:
        measuring = {_authority_key(name) for name in measuring_authorities if _authority_key(name)}
    folded = {}
    for name, vote in votes_by_authority.items():
        key = _authority_key(name)
        if key and isinstance(vote, dict) and vote.get('voted') is not False:
            folded[key] = vote
    ballots = []
    measured = measurable_votes = measurable_measured = 0
    yes_names = {flag: [] for flag in AGREEMENT_FLAGS}
    no_names = {flag: [] for flag in AGREEMENT_FLAGS}
    measured_by = []
    for name, vote in folded.items():
        flags = set(_flag_list(vote.get('flags')))
        ballots.append({'voted': True, 'flags': _flag_list(vote.get('flags'))})
        for flag in AGREEMENT_FLAGS:
            (yes_names if flag in flags else no_names)[flag].append(name)
        has_measured = _vote_kb(vote.get('measured')) is not None
        if has_measured:
            measured += 1
        if measuring is None or name in measuring:
            measurable_votes += 1
            if has_measured:
                measurable_measured += 1
            if measuring is not None and has_measured:
                measured_by.append(name)
    if not ballots:
        return None
    consensus = compute_flag_consensus(ballots)
    split = [flag for flag in AGREEMENT_FLAGS if flag in consensus['partial_flags']]
    sides = {}
    for flag in split:
        sides[flag] = {'yes': sorted(yes_names[flag]), 'no': sorted(no_names[flag])}
    return {
        'voted': consensus['total_voting'],
        'agreed': not split,
        'split_flags': split,
        'measured_count': measured,
        'measurement_split': 0 < measurable_measured < measurable_votes,
        'unmeasured': measured < 3,
        'voters': sorted(folded),
        'assigned_flags': [flag for flag in AGREEMENT_FLAGS if yes_names[flag] and not no_names[flag]],
        'absent_flags': [flag for flag in AGREEMENT_FLAGS if no_names[flag] and not yes_names[flag]],
        'flag_sides': sides,
        'measured_by': sorted(measured_by),
    }


def summarize_operator_votes(members, limit=5, measurement_authorities=None):
    """Agreement counts for one operator, or None when none of the relays were voted."""
    pairs = []
    for relay in members or ():
        info = relay.get('vote_agreement') if isinstance(relay, dict) else None
        if info:
            pairs.append((relay, info))
    if not pairs:
        return None
    return _summarize(pairs, limit, measurement_authorities)


def attach_vote_agreement(relays, relay_index, bw_authorities=None, scanner_authorities=None):
    """Attach ``vote_agreement`` from the current collector index.

    ``bw_authorities`` is the set whose votes publish Measured= (the caller's
    measuring authorities). ``scanner_authorities`` is every authority that
    included a bandwidth file. Returns the network summary. A lowercase
    fingerprint key in an older cache still matches.
    """
    from .collector_fetcher import _authority_key
    index = relay_index if isinstance(relay_index, dict) else {}
    publishing = _name_list(bw_authorities, _authority_key)
    scanners = _name_list(scanner_authorities, _authority_key)
    silent = [name for name in scanners if name not in set(publishing)]
    authorities = {'publishing': publishing, 'silent': silent, 'scanners': scanners}
    pairs = []
    from .collector_fetcher import _votes_by_name
    for relay in relays or ():
        if not isinstance(relay, dict):
            continue
        fp = _fingerprint(relay.get('fingerprint'))
        try:
            indexed = index.get(fp) if fp else None
            if not isinstance(indexed, dict) and fp:
                indexed = index.get(fp.lower())
            raw_votes = _votes_by_name(indexed) if isinstance(indexed, dict) else {}
            agreement = classify_authority_votes(raw_votes, bw_authorities)
            if agreement:
                relay['vote_agreement'] = agreement
                pairs.append((relay, agreement))
            else:
                relay.pop('vote_agreement', None)
        except Exception as exc:  # noqa: BLE001 -- one corrupt relay must not blank the rest
            logger.warning("vote agreement skipped for %s (%s)", fp, exc)
    if not pairs:
        empty = _empty_agreement()
        empty['measurement_authorities'] = authorities
        return empty
    summary = _summarize(pairs, 5, authorities)
    summary['measurement_authorities'] = authorities
    return summary


def _summarize(pairs, limit, measurement_authorities):
    summary, by_flag = _empty_agreement(), {flag: 0 for flag in AGREEMENT_FLAGS}
    examples = []
    sides = {flag: [] for flag in AGREEMENT_FLAGS}
    assigned_sets, absent_sets, voter_sets = [], [], []
    for relay, info in pairs:
        flags = _note_agreement(summary, by_flag, info)
        if flags is not None and relay is not None:
            examples.append((relay, flags))
        for flag, side in (info.get('flag_sides') or {}).items():
            if flag in sides and isinstance(side, dict):
                sides[flag].append((tuple(side.get('no') or ()), tuple(side.get('yes') or ())))
        if info.get('agreed'):
            assigned_sets.append(tuple(info.get('assigned_flags') or ()))
            absent_sets.append(tuple(info.get('absent_flags') or ()))
            voter_sets.append(tuple(info.get('voters') or ()))
    examples.sort(key=lambda item: ((item[0].get('nickname') or '').lower(), item[0].get('fingerprint') or ''))
    summary['split_flags'] = _split_flag_rows(by_flag)
    summary['flag_rows'] = [
        {'flag': flag, 'agreed': summary['compared'] - by_flag[flag], 'split': by_flag[flag]}
        for flag in AGREEMENT_FLAGS
    ]
    summary['example_total'] = len(examples)
    summary['examples'] = [
        {
            'nickname': relay.get('nickname') or (relay.get('fingerprint') or '')[:12],
            'fingerprint': relay.get('fingerprint') or '',
            'flags_display': ', '.join(flags),
        }
        for relay, flags in examples[:limit]
    ]
    summary['all_agreed'] = summary['split'] == 0 and summary['compared'] > 0
    same_flags = summary['all_agreed'] and len(set(assigned_sets)) == 1 and len(set(absent_sets)) == 1
    summary['assigned_flags'] = list(assigned_sets[0]) if same_flags else []
    summary['absent_flags'] = list(absent_sets[0]) if same_flags else []
    summary['voters'] = list(voter_sets[0]) if summary['all_agreed'] and len(set(voter_sets)) == 1 else []
    summary['flag_patterns'] = [
        {'flag': row['flag'], 'relays': row['count'], 'lines': _pattern_lines(sides[row['flag']])}
        for row in summary['split_flags']
    ]
    summary['bandwidth'] = _bandwidth_summary(pairs, summary['compared'], measurement_authorities)
    return summary


def _bandwidth_summary(pairs, compared, measurement_authorities):
    authorities = measurement_authorities if isinstance(measurement_authorities, dict) else {}
    publishing = list(authorities.get('publishing') or [])
    scanners = list(authorities.get('scanners') or [])
    silent = list(authorities.get('silent') or [])
    if scanners and not silent:
        known = set(publishing)
        silent = [name for name in scanners if name not in known]
    elif not scanners:
        scanners = list(publishing)
    misses = Counter()
    full = 0
    if publishing:
        for _relay, info in pairs:
            measured = set(info.get('measured_by') or ())
            missing = [name for name in publishing if name not in measured]
            if missing:
                misses.update(missing)
            else:
                full += 1
    return {
        'full_count': full,
        'compared': compared,
        'publishing': publishing,
        'silent': silent,
        'scanners': scanners,
        'misses': [
            {'name': name, 'count': count}
            for name, count in sorted(misses.items(), key=lambda item: (-item[1], item[0]))
        ],
    }


def _pattern_lines(pairs):
    """Sentences for one flag. Withheld groups come before assigned groups."""
    if not pairs:
        return []
    lack_sets = [set(lack) for lack, _yes in pairs]
    assign_sets = [set(yes) for _lack, yes in pairs]
    count = len(pairs)
    universal_lack = set.intersection(*lack_sets)
    universal_assign = set.intersection(*assign_sets)
    if universal_lack:
        lines = [_line('did_not', count, 'all', sorted(universal_lack), also=False, only=False)]
        extra = Counter()
        for lack in lack_sets:
            extra.update(lack - universal_lack)
        for name, times in sorted(extra.items(), key=lambda item: (-item[1], item[0])):
            lines.append(_line('did_not', times, 'of_those', [name], also=True, only=False))
        if universal_assign:
            lines.append(_line('assigned', count, 'all', sorted(universal_assign), also=False, only=False))
        return lines
    groups = Counter(pairs)
    withheld, assigned = [], []
    for (lack, yes), times in groups.items():
        if len(yes) < len(lack):
            assigned.append((times, list(yes)))
        else:
            withheld.append((times, list(lack)))
    withheld.sort(key=lambda item: (-item[0], item[1]))
    assigned.sort(key=lambda item: (-item[0], item[1]))
    lines = [
        _line('did_not', times, 'on', names, also=False, only=len(names) == 1)
        for times, names in withheld[:_DID_NOT_GROUPS]
    ]
    lines.extend(
        _line('assigned', times, 'on', names, also=False, only=True)
        for times, names in assigned[:_ASSIGNED_GROUPS]
    )
    return lines


def _line(kind, count, scope, names, also, only):
    return {
        'kind': kind, 'count': count, 'scope': scope, 'names': names, 'also': also, 'only': only,
    }


def _empty_agreement():
    return {
        'compared': 0, 'agreed': 0, 'split': 0,
        'measurement_split': 0, 'unmeasured': 0,
        'all_agreed': False, 'assigned_flags': [], 'absent_flags': [], 'voters': [],
        'split_flags': [], 'flag_rows': [], 'flag_patterns': [], 'examples': [],
        'example_total': 0, 'bandwidth': None, 'measurement_authorities': None,
    }


def _note_agreement(summary, by_flag, info):
    """Add one relay. Returns its split flags, or None when the votes agree."""
    summary['compared'] += 1
    flags = list(info.get('split_flags') or ())
    if info.get('agreed'):
        summary['agreed'] += 1
        flags = None
    else:
        summary['split'] += 1
        for flag in flags:
            if flag in by_flag:
                by_flag[flag] += 1
    if info.get('measurement_split'):
        summary['measurement_split'] += 1
    if info.get('unmeasured'):
        summary['unmeasured'] += 1
    return flags


def _split_flag_rows(by_flag):
    rows = [{'flag': flag, 'count': count} for flag, count in by_flag.items() if count]
    rows.sort(key=lambda item: (-item['count'], item['flag']))
    return rows


def _name_list(names, key):
    if isinstance(names, (str, bytes)) or not isinstance(names, (list, tuple, set, frozenset)):
        return []
    found = []
    seen = set()
    for name in names:
        folded = key(name)
        if folded and folded not in seen:
            seen.add(folded)
            found.append(folded)
    found.sort()
    return found


def _flag_list(flags):
    """Flag names, once each. A string is not a list of one-character flags."""
    if isinstance(flags, str) or not isinstance(flags, (list, tuple, set)):
        return []
    names = []
    for name in flags:
        if isinstance(name, str) and name not in names:
            names.append(name)
    return names


def _fingerprint(value):
    if not isinstance(value, str) or len(value) != 40:
        return None
    fp = value.strip().upper()
    return fp if all(char in '0123456789ABCDEF' for char in fp) else None
