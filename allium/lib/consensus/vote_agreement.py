"""Current-hour agreement of directory-authority votes for one relay.

This does not store votes. The counts use the votes already in the collector
relay index.
"""

import logging

from .consensus_evaluation import compute_flag_consensus

logger = logging.getLogger(__name__)

# MiddleOnly and BadExit are authority penalties, not ordinary disagreement.
AGREEMENT_FLAGS = ('Running', 'Valid', 'Fast', 'Stable', 'Guard', 'Exit', 'HSDir')


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
    for name, vote in folded.items():
        ballots.append({'voted': True, 'flags': _flag_list(vote.get('flags'))})
        has_measured = _vote_kb(vote.get('measured')) is not None
        if has_measured:
            measured += 1
        if measuring is None or name in measuring:
            measurable_votes += 1
            if has_measured:
                measurable_measured += 1
    if not ballots:
        return None
    consensus = compute_flag_consensus(ballots)
    split = [flag for flag in AGREEMENT_FLAGS if flag in consensus['partial_flags']]
    return {
        'voted': consensus['total_voting'],
        'agreed': not split,
        'split_flags': split,
        'measured_count': measured,
        'measurement_split': 0 < measurable_measured < measurable_votes,
        'unmeasured': measured < 3,
    }


def summarize_operator_votes(members, limit=6):
    """Agreement counts for one operator, or None when none of the relays were voted."""
    summary, by_flag, examples = _empty_agreement(), {flag: 0 for flag in AGREEMENT_FLAGS}, []
    for relay in members or ():
        info = relay.get('vote_agreement') if isinstance(relay, dict) else None
        if not info:
            continue
        flags = _note_agreement(summary, by_flag, info)
        if flags is not None:
            examples.append((0 if 'Guard' in flags else 1, relay, flags))
    if summary['compared'] == 0:
        return None
    examples.sort(key=lambda item: (item[0], (item[1].get('nickname') or '').lower()))
    summary['split_flags'] = _split_flag_rows(by_flag)
    summary['examples'] = [
        {
            'nickname': relay.get('nickname') or (relay.get('fingerprint') or '')[:12],
            'fingerprint': relay.get('fingerprint') or '',
            'flags_display': ', '.join(flags),
        }
        for _rank, relay, flags in examples[:limit]
    ]
    return summary


def attach_vote_agreement(relays, relay_index, bw_authorities=None):
    """Attach ``vote_agreement`` from the current collector index.

    Returns the network summary. A lowercase fingerprint key in an older cache
    still matches.
    """
    summary, by_flag = _empty_agreement(), {flag: 0 for flag in AGREEMENT_FLAGS}
    index = relay_index if isinstance(relay_index, dict) else {}
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
                _note_agreement(summary, by_flag, agreement)
            else:
                relay.pop('vote_agreement', None)
        except Exception as exc:  # noqa: BLE001 -- one corrupt relay must not blank the rest
            logger.warning("vote agreement skipped for %s (%s)", fp, exc)
    summary['split_flags'] = _split_flag_rows(by_flag)
    return summary


def _empty_agreement():
    return {
        'compared': 0, 'agreed': 0, 'split': 0,
        'measurement_split': 0, 'unmeasured': 0,
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
