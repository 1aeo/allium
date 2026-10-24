"""Rolling per-relay history of authority vote measurements.

Each Allium run already downloads the latest vote per directory authority.
This module keeps a small series from those documents: per-authority
Measured= values, the low median the consensus weight uses, and the flag
bits those votes assigned. It does not download the CollecTor vote archive.

Onionoo write_history and read_history are traffic. They are not read here
and are not turned into a second consensus weight.

Document time is the vote's valid-after (published, when valid-after is
absent). Authorities are never mixed across different document times.
The median follows dir-spec "Computing a consensus": the low median of
Measured= when three or more votes have one, otherwise the low median of
Bandwidth=, capped at maxunmeasuredbw while three or more authorities
publish any measurements.

Spec: https://spec.torproject.org/dir-spec/computing-consensus.html
"""

import fcntl
import gzip
import json
import logging
import os
from bisect import bisect_left
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape as xml_escape

from .consensus_evaluation import _format_bandwidth_value, compute_flag_consensus
from .flag_thresholds import (
    MAX_UNMEASURED_BW_KB,
    VOTE_BW_KB_BYTES,
    low_median,
)

logger = logging.getLogger(__name__)

HISTORY_VERSION = 1
RETENTION_DAYS = 14
# Latest documents listed in the relay-page table. The chart draws a longer window.
RECENT_ROWS = 24
CHART_MAX_POINTS = 168

# Bit positions are part of the stored history. Append new flags; do not reorder.
FLAG_BITS = (
    'Running', 'Valid', 'Fast', 'Stable', 'Guard',
    'Exit', 'HSDir', 'V2Dir', 'MiddleOnly', 'BadExit',
)
_FLAG_BIT = {name: 1 << index for index, name in enumerate(FLAG_BITS)}
GUARD_BIT = _FLAG_BIT['Guard']
FAST_BIT = _FLAG_BIT['Fast']
STABLE_BIT = _FLAG_BIT['Stable']

# Flags a split vote is counted on. MiddleOnly and BadExit are authority
# penalties and are not treated as ordinary disagreement.
AGREEMENT_FLAGS = ('Running', 'Valid', 'Fast', 'Stable', 'Guard', 'Exit', 'HSDir')

_TIME_FORMATS = ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S')
_HEX = frozenset('0123456789ABCDEF')

# One color per known authority, in palette order. Any other name uses the palette.
_PALETTE = (
    '#1b9e77', '#d95f02', '#7570b3', '#e7298a', '#66a61e',
    '#e6ab02', '#a6761d', '#1f78b4', '#666666', '#b15928',
)
AUTHORITY_COLORS = dict(zip(
    ('bastet', 'dannenberg', 'dizum', 'faravahar', 'gabelmoo',
     'longclaw', 'maatuska', 'moria1', 'tor26', 'serge'),
    _PALETTE,
))
MEDIAN_COLOR = '#111111'

_ROW_KEYS = ('m', 'b', 'f', 'median', 'unmeasured', 'cap')


def default_history_path():
    """Gzipped JSON cache beside the other CollecTor caches."""
    from ..workers import CACHE_DIR
    return os.path.join(CACHE_DIR, 'vote_history.json.gz')


def empty_store():
    """A history document with no relays yet."""
    return {
        'version': HISTORY_VERSION,
        'authorities': [],
        'periods': {},
        'relays': {},
    }


def consensus_weight_median(measured_kb, bandwidth_kb, measuring_count):
    """Low median the consensus weight uses, in KB/s.

    ``measured_kb`` and ``bandwidth_kb`` are aligned. None means that
    authority did not publish that keyword. A missing vote is None in both.

    Returns ``(median_kb or None, unmeasured, cap_in_force)``. ``unmeasured``
    is true when fewer than three Measured= values are present, matching
    CollectorFetcher._format_bandwidth. ``cap_in_force`` is true when that
    median is capped at maxunmeasuredbw because three or more authorities
    publish measurements for any relay.
    """
    measured_vals = [value for value in measured_kb if value is not None]
    if len(measured_vals) >= 3:
        return low_median(measured_vals), False, False
    bandwidths = [value for value in bandwidth_kb if value is not None]
    median = low_median(bandwidths)
    cap_in_force = measuring_count >= 3
    if median is not None and cap_in_force and median > MAX_UNMEASURED_BW_KB:
        median = MAX_UNMEASURED_BW_KB
    return median, True, cap_in_force


def document_time(vote):
    """Normalize a vote's document time to ``YYYY-MM-DD HH:MM:SS`` (UTC).

    valid-after, then published. ``vote_time`` is the same pair already
    chosen by the vote parser. Returns None when neither time is present.
    """
    if not isinstance(vote, dict):
        return None
    for key in ('vote_time', 'valid_after', 'published'):
        parsed = _parse_time(vote.get(key))
        if parsed is not None:
            return parsed.strftime('%Y-%m-%d %H:%M:%S')
    return None


def classify_authority_votes(votes_by_authority, measuring_authorities=None):
    """Agreement of one relay's latest votes.

    ``votes_by_authority`` maps an authority name to the vote fields Allium
    already stores (``flags``, ``measured``). Authorities that did not vote
    are absent. Returns None when nobody voted.

    A relay is in agreement when every voting authority assigned the same
    Running, Valid, Fast, Stable, Guard, Exit, and HSDir state. A flag is
    split when some of those authorities assigned it and some did not.
    ``measurement_split`` is true when some bandwidth authorities measured
    the relay and some did not. Pass ``measuring_authorities`` (the names
    whose votes carry Measured= for any relay). Without that set, every
    vote is treated as able to measure, which counts a non-scanner authority
    as a split. ``unmeasured`` is true when fewer than three votes include
    Measured=, which is when the consensus weight uses Bandwidth=.
    """
    if not isinstance(votes_by_authority, dict) or not votes_by_authority:
        return None
    from .collector_fetcher import _authority_key
    ballots = []
    measured = measurable_votes = measurable_measured = 0
    # None means "no scanner list was supplied". An empty set means none measure.
    if measuring_authorities is None:
        measuring = None
    else:
        measuring = {_authority_key(name) for name in measuring_authorities if _authority_key(name)}
    folded = {}
    for name, vote in votes_by_authority.items():
        key = _authority_key(name)
        if key and isinstance(vote, dict) and vote.get('voted') is not False:
            folded[key] = vote
    for name, vote in folded.items():
        flags = _flag_list(vote.get('flags'))
        ballots.append({'voted': True, 'flags': flags})
        has_measured = _kb(vote.get('measured')) is not None
        if has_measured:
            measured += 1
        if measuring is None or name in measuring:
            measurable_votes += 1
            if has_measured:
                measurable_measured += 1
    if not ballots:
        return None
    # Same partial-flag rule as the relay page: assigned by some voters, not all.
    consensus = compute_flag_consensus(ballots)
    voted = consensus['total_voting']
    split = [flag for flag in AGREEMENT_FLAGS if flag in consensus['partial_flags']]
    measurement_split = 0 < measurable_measured < measurable_votes
    return {
        'voted': voted,
        'agreed': not split,
        'split_flags': split,
        'measured_count': measured,
        'measurement_split': measurement_split,
        'unmeasured': measured < 3,
    }


def summarize_operator_votes(members, limit=6):
    """Agreement counts for one operator's relays, or None when none were voted.

    ``members`` are relay dicts that may carry ``vote_agreement`` from
    ``attach_relay_vote_views``. Split relays that include Guard are listed
    first, then the other split relays, up to ``limit``.
    """
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
    shown = []
    for _rank, relay, flags in examples[:limit]:
        shown.append({
            'nickname': relay.get('nickname') or (relay.get('fingerprint') or '')[:12],
            'fingerprint': relay.get('fingerprint') or '',
            'flags_display': ', '.join(flags),
            'anchor': 'vote-history' if relay.get('vote_history') else 'consensus-evaluation',
        })
    summary['split_flags'] = _split_flag_rows(by_flag)
    summary['examples'] = shown
    return summary


def record_votes(store, votes):
    """Merge already-parsed authority votes into ``store``.

    ``votes`` is ``{authority_name: vote_dict}`` as CollectorFetcher stores
    it (``vote_time`` / ``valid_after`` / ``published`` and ``relays``).
    Returns ``(store, changed)``. The same documents recorded again do not
    count as a change. Does not fetch anything.
    """
    store = _normalize_store(store)
    if not isinstance(votes, dict) or not votes:
        return store, _prune(store)

    changed = False
    dirty = set()
    periods_to_recompute = set()

    from .collector_fetcher import _authority_key
    for auth_name in sorted(name for name in votes if isinstance(name, str) and name):
        vote = votes.get(auth_name)
        when = document_time(vote)
        relays = vote.get('relays') if isinstance(vote, dict) else None
        auth_key = _authority_key(auth_name)
        if when is None or not _stamp_kept(when) or not isinstance(relays, dict) or not auth_key:
            continue
        auth_idx, grew = _ensure_authority(store, auth_key)
        if grew:
            changed = True
        width = len(store['authorities'])
        any_measured = False
        seen = set()
        for raw_fp, relay in relays.items():
            fp = _fingerprint(raw_fp)
            if fp is None or not isinstance(relay, dict):
                continue
            seen.add(fp)
            measured = _kb(relay.get('measured'))
            bandwidth = _kb(relay.get('bandwidth'))
            if measured is not None:
                any_measured = True
            packed = pack_flags(_flag_list(relay.get('flags')))
            entry = _ensure_relay(store, fp)
            idx = _ensure_point(entry, when, width)
            if _assign_cell(entry, idx, auth_idx, measured, bandwidth, packed):
                dirty.add((fp, when))
                changed = True
        # A replacement vote for this document drops relays the authority no longer lists.
        if _clear_absent(store, when, auth_idx, width, seen, dirty):
            changed = True
        if _set_measuring(store, when, auth_key, any_measured):
            changed = True
            periods_to_recompute.add(when)

    for when in periods_to_recompute:
        for fp, entry in store['relays'].items():
            if when in entry['t']:
                dirty.add((fp, when))

    if _recompute(store, dirty):
        changed = True
    if _prune(store):
        changed = True
    return store, changed


def _read_store(path):
    """Return ``(store, readable)``.

    A missing file is an empty store and readable. A file that exists but cannot
    be parsed is not readable: the caller must not replace it with this hour.
    """
    if not os.path.exists(path):
        return empty_store(), True
    try:
        with gzip.open(path, 'rt', encoding='utf-8') as handle:
            data = json.load(handle)
    except (OSError, ValueError, EOFError, gzip.BadGzipFile) as exc:
        logger.warning("vote measurement history could not be read (%s)", exc)
        return empty_store(), False
    except Exception as exc:  # noqa: BLE001 -- a corrupt cache must not stop generation
        logger.warning("vote measurement history could not be read (%s)", exc)
        return empty_store(), False
    return _normalize_store(data), True


def load_history(path=None):
    """Load the history cache. A missing or unreadable file is an empty store."""
    store, _readable = _read_store(path or default_history_path())
    return store


def save_history(store, path=None):
    """Atomically write the history cache as gzipped JSON."""
    path = path or default_history_path()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    payload = json.dumps(store, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    tmp_path = '%s.tmp.%s' % (path, os.getpid())
    lock_path = path + '.lock'
    with open(lock_path, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            with gzip.open(tmp_path, 'wb', compresslevel=6) as handle:
                handle.write(payload)
            os.replace(tmp_path, path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            fcntl.flock(lock, fcntl.LOCK_UN)


def update_history_from_collector(data, path=None):
    """Record ``data['votes']`` and return how many relays the store holds.

    ``data`` is the collector consensus cache. Empty or invalid input leaves
    the file untouched. Failures are logged and reported as zero so a history
    problem does not discard the votes Allium already fetched.
    """
    try:
        votes = data.get('votes') if isinstance(data, dict) else None
        if not isinstance(votes, dict) or not votes:
            return 0
        path = path or default_history_path()
        store, readable = _read_store(path)
        if not readable:
            return 0
        store, changed = record_votes(store, votes)
        if changed:
            save_history(store, path)
        return len(store.get('relays') or {})
    except Exception as exc:  # noqa: BLE001 -- history is additive; votes still render
        logger.warning("vote measurement history was not updated: %s", exc)
        return 0


def format_relay_history(history, fingerprint, use_bits=False):
    """Template view for one relay, or None when it has no stored documents.

    The table lists the latest ``RECENT_ROWS`` documents, newest first.
    The chart covers up to ``CHART_MAX_POINTS`` documents on a time axis, so
    a missing hour stays a gap. Bandwidths are displayed in the page's
    bits/bytes units; the underlying vote values stay KB/s.
    """
    fp = _fingerprint(fingerprint)
    if fp is None or not isinstance(history, dict):
        return None
    relays = history.get('relays')
    entry = relays.get(fp) if isinstance(relays, dict) else None
    if not isinstance(entry, dict):
        return None
    times = entry.get('t') or []
    if not times:
        return None
    authorities = list(history.get('authorities') or ())
    width = len(authorities)
    count = min(len(times), len(entry.get('m') or ()), len(entry.get('b') or ()), len(entry.get('f') or ()))
    if count == 0:
        return None

    shown = []
    for index, name in enumerate(authorities):
        if _authority_voted(entry, index, count):
            shown.append((name, index))
    shown.sort(key=lambda item: item[0].lower())
    if not shown:
        return None

    parsed = [_parse_time(times[index]) for index in range(count)]
    columns = [{'name': name, 'index': index, 'color': _color_for(name, pos)}
               for pos, (name, index) in enumerate(shown)]

    rows = []
    previous_guard = None
    for index in range(count):
        measured = _row(entry, 'm', index, width)
        bandwidth = _row(entry, 'b', index, width)
        flags = _row(entry, 'f', index, width)
        when = times[index]
        guard_assigned, guard_voted, guard_names = _flag_tally(flags, columns, GUARD_BIT)
        fast_assigned, fast_voted, _fast_names = _flag_tally(flags, columns, FAST_BIT)
        stable_assigned, stable_voted, _stable_names = _flag_tally(flags, columns, STABLE_BIT)
        guard_delta = None if previous_guard is None else guard_assigned - previous_guard
        previous_guard = guard_assigned
        unmeasured = bool(_at(entry, 'unmeasured', index, 0))
        cap = bool(_at(entry, 'cap', index, 0))
        median_kb = _at(entry, 'median', index, None)
        cells = []
        for name, auth_index in shown:
            flag_mask = flags[auth_index] if auth_index < len(flags) else None
            cells.append(_cell_at(
                name,
                measured[auth_index] if auth_index < len(measured) else None,
                bandwidth[auth_index] if auth_index < len(bandwidth) else None,
                when,
                use_bits,
                unmeasured,
                isinstance(flag_mask, int) and not isinstance(flag_mask, bool),
            ))
        rows.append({
            'valid_after': when,
            'median_display': _format_kb(median_kb, use_bits),
            'median_title': _median_title(median_kb, unmeasured, cap),
            'unmeasured': unmeasured,
            'guard': _ratio(guard_assigned, guard_voted),
            'guard_delta': guard_delta,
            'guard_title': _flag_title('Guard', guard_names, guard_assigned, guard_voted),
            'fast': _ratio(fast_assigned, fast_voted),
            'stable': _ratio(stable_assigned, stable_voted),
            'cells': cells,
        })

    chart_start = 0 if count <= CHART_MAX_POINTS else count - CHART_MAX_POINTS
    chart_times = [parsed[index] for index in range(chart_start, count)]
    chart_medians = [_at(entry, 'median', index, None) for index in range(chart_start, count)]
    chart_series = []
    for column in columns:
        values = []
        present = False
        for index in range(chart_start, count):
            value = _row(entry, 'm', index, width)[column['index']] if column['index'] < width else None
            values.append(value)
            if value is not None:
                present = True
        if present:
            chart_series.append((column['name'], column['color'], values))
    svg = _svg_chart(chart_times, chart_medians, chart_series, [times[index] for index in range(chart_start, count)])

    recent = list(reversed(rows[-RECENT_ROWS:]))
    return {
        'point_count': count,
        'chart_count': count - chart_start,
        'chart_truncated': chart_start > 0,
        'oldest': times[0],
        'newest': times[count - 1],
        'columns': [{'name': column['name'], 'color': column['color']} for column in columns],
        'rows': recent,
        'svg': svg,
        'retention_days': RETENTION_DAYS,
    }


def attach_relay_vote_views(relays, history, relay_index, use_bits=False, bw_authorities=None):
    """Attach ``vote_history`` and ``vote_agreement`` to each relay.

    ``relay_index`` is the collector fingerprint index. ``bw_authorities``
    limits measurement-split counts to authorities whose votes carry
    Measured=. Returns the network summary of the latest votes (independent
    of how many past documents are stored).
    """
    summary, by_flag = _empty_agreement(), {flag: 0 for flag in AGREEMENT_FLAGS}
    history = history if isinstance(history, dict) else empty_store()
    index = relay_index if isinstance(relay_index, dict) else {}
    for relay in relays or ():
        if not isinstance(relay, dict):
            continue
        fp = _fingerprint(relay.get('fingerprint'))
        try:
            raw_votes = {}
            if fp is not None:
                indexed = index.get(fp)
                if not isinstance(indexed, dict):
                    indexed = index.get(fp.lower())
                if isinstance(indexed, dict):
                    from .collector_fetcher import _votes_by_name
                    raw_votes = _votes_by_name(indexed)
            agreement = classify_authority_votes(raw_votes, bw_authorities)
            if agreement:
                relay['vote_agreement'] = agreement
                _note_agreement(summary, by_flag, agreement)
            else:
                relay.pop('vote_agreement', None)
            view = format_relay_history(history, fp, use_bits=use_bits) if fp is not None else None
            if view:
                relay['vote_history'] = view
            else:
                relay.pop('vote_history', None)
        except Exception as exc:  # noqa: BLE001 -- one corrupt relay must not blank the rest
            logger.warning("vote view skipped for %s (%s)", fp, exc)
            continue
    summary['split_flags'] = _split_flag_rows(by_flag)
    return summary


def pack_flags(flags):
    """Pack flag names into the stored bitmask. Unknown names are ignored."""
    bits = 0
    if isinstance(flags, (list, tuple, set)):
        for name in flags:
            bit = _FLAG_BIT.get(name)
            if bit:
                bits |= bit
    return bits


def _empty_agreement():
    return {
        'compared': 0, 'agreed': 0, 'split': 0,
        'measurement_split': 0, 'unmeasured': 0,
    }


def _note_agreement(summary, by_flag, info):
    """Add one relay to an agreement summary. Returns its split flags, or None."""
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


def _normalize_store(store):
    if not isinstance(store, dict) or store.get('version') != HISTORY_VERSION:
        return empty_store()
    authorities = store.get('authorities')
    if not isinstance(authorities, list):
        authorities = []
    store['authorities'] = [name for name in authorities if isinstance(name, str) and name]
    periods = store.get('periods')
    store['periods'] = periods if isinstance(periods, dict) else {}
    relays = store.get('relays')
    if not isinstance(relays, dict):
        relays = {}
    # A non-dict entry would raise on the next record and block the whole file.
    store['relays'] = {
        fp: entry for fp, entry in relays.items() if isinstance(entry, dict)
    }
    width = len(store['authorities'])
    for entry in store['relays'].values():
        if not isinstance(entry, dict):
            continue
        times = entry.get('t') if isinstance(entry.get('t'), list) else []
        entry['t'] = times
        count = len(times)
        for key in _ROW_KEYS:
            rows = entry.get(key)
            if not isinstance(rows, list):
                rows = []
            if len(rows) < count:
                pad = None if key in ('m', 'b', 'f', 'median') else 0
                rows.extend([pad] * (count - len(rows)))
            elif len(rows) > count:
                del rows[count:]
            if key in ('m', 'b', 'f'):
                for index, row in enumerate(rows):
                    if not isinstance(row, list):
                        rows[index] = [None] * width
                    elif len(row) < width:
                        row.extend([None] * (width - len(row)))
                    elif len(row) > width:
                        del row[width:]
            entry[key] = rows
    return store


def _ensure_authority(store, name):
    from .collector_fetcher import _authority_key
    key = _authority_key(name) or name
    authorities = store['authorities']
    for index, existing in enumerate(authorities):
        if _authority_key(existing) == _authority_key(key):
            renamed = existing != key
            if renamed:
                authorities[index] = key
            return index, renamed
    authorities.append(key)
    width = len(authorities)
    for entry in store['relays'].values():
        if not isinstance(entry, dict):
            continue
        for series in ('m', 'b', 'f'):
            rows = entry.get(series)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if isinstance(row, list) and len(row) < width:
                    row.extend([None] * (width - len(row)))
    return width - 1, True


def _ensure_relay(store, fingerprint):
    entry = store['relays'].get(fingerprint)
    if entry is None:
        entry = {'t': [], 'm': [], 'b': [], 'f': [], 'median': [], 'unmeasured': [], 'cap': []}
        store['relays'][fingerprint] = entry
    return entry


def _ensure_point(entry, when, width):
    times = entry['t']
    # Stored timestamps sort lexicographically. bisect keeps a late vote in its period.
    lo = bisect_left(times, when)
    if lo < len(times) and times[lo] == when:
        _pad_row(entry, lo, width)
        return lo
    times.insert(lo, when)
    entry['m'].insert(lo, [None] * width)
    entry['b'].insert(lo, [None] * width)
    entry['f'].insert(lo, [None] * width)
    entry['median'].insert(lo, None)
    entry['unmeasured'].insert(lo, 1)
    entry['cap'].insert(lo, 0)
    return lo


def _pad_row(entry, index, width):
    for key in ('m', 'b', 'f'):
        row = entry[key][index]
        if len(row) < width:
            row.extend([None] * (width - len(row)))


def _assign_cell(entry, index, auth_idx, measured, bandwidth, packed):
    measured_row = entry['m'][index]
    bandwidth_row = entry['b'][index]
    flag_row = entry['f'][index]
    if (measured_row[auth_idx] == measured and bandwidth_row[auth_idx] == bandwidth
            and flag_row[auth_idx] == packed):
        return False
    measured_row[auth_idx] = measured
    bandwidth_row[auth_idx] = bandwidth
    flag_row[auth_idx] = packed
    return True


def _set_measuring(store, when, auth_name, measuring):
    """Record whether this authority published any Measured= for this document.

    Names are lowercase. An authority that stops publishing measurements is
    removed, so the maxunmeasuredbw cap does not stay on after the scanner stops.
    """
    from .collector_fetcher import _authority_key
    key = _authority_key(auth_name)
    names = store['periods'].get(when)
    folded = []
    seen = set()
    if isinstance(names, list):
        for name in names:
            folded_name = _authority_key(name)
            if folded_name and folded_name not in seen:
                seen.add(folded_name)
                folded.append(folded_name)
    changed = folded != (names or [])
    if measuring and key and key not in seen:
        folded.append(key)
        folded.sort()
        changed = True
    elif key and key in seen and not measuring:
        folded = [name for name in folded if name != key]
        changed = True
    if not changed:
        return False
    if folded:
        store['periods'][when] = folded
    else:
        store['periods'].pop(when, None)
    return True


def _clear_absent(store, when, auth_idx, width, seen, dirty):
    """Clear this authority's cell for relays missing from its replacement vote."""
    changed = False
    for fp, entry in list(store['relays'].items()):
        if not isinstance(entry, dict) or when not in (entry.get('t') or ()):
            continue
        if fp in seen:
            continue
        index = entry['t'].index(when)
        _pad_row(entry, index, width)
        if _assign_cell(entry, index, auth_idx, None, None, None):
            dirty.add((fp, when))
            changed = True
    return changed


def _stamp_kept(when, now=None):
    """False for a document time more than 36 hours ahead of now.

    A far-future valid-after would become the prune anchor and delete the
    real window. Dir-spec stamps are the consensus hour, not an arbitrary date.
    """
    parsed = _parse_time(when)
    if parsed is None:
        return False
    now = now or datetime.now(timezone.utc)
    return parsed <= now + timedelta(hours=36)


def _recompute(store, dirty):
    changed = False
    for fp, when in dirty:
        entry = store['relays'].get(fp)
        if entry is None or when not in entry['t']:
            continue
        index = entry['t'].index(when)
        measuring = len(store['periods'].get(when) or ())
        median, unmeasured, cap = consensus_weight_median(entry['m'][index], entry['b'][index], measuring)
        unmeasured_i = 1 if unmeasured else 0
        cap_i = 1 if cap else 0
        if (entry['median'][index] != median or entry['unmeasured'][index] != unmeasured_i
                or entry['cap'][index] != cap_i):
            entry['median'][index] = median
            entry['unmeasured'][index] = unmeasured_i
            entry['cap'][index] = cap_i
            changed = True
    return changed


def _prune(store, now=None):
    now = now or datetime.now(timezone.utc)
    horizon = now + timedelta(hours=36)
    newest = None
    for entry in store['relays'].values():
        if not isinstance(entry, dict):
            continue
        for when in entry.get('t') or ():
            parsed = _parse_time(when)
            if parsed is None or parsed > horizon:
                continue
            if newest is None or parsed > newest:
                newest = parsed
    if newest is None:
        cutoff = horizon
    else:
        cutoff = newest - timedelta(days=RETENTION_DAYS)
    changed = False
    empty = []
    live = set()
    for fp, entry in store['relays'].items():
        keep = []
        for index, when in enumerate(entry['t']):
            parsed = _parse_time(when)
            if parsed is not None and cutoff <= parsed <= horizon:
                keep.append(index)
        if len(keep) != len(entry['t']):
            changed = True
            entry['t'] = [entry['t'][index] for index in keep]
            for key in _ROW_KEYS:
                entry[key] = [entry[key][index] for index in keep]
        if entry['t']:
            live.update(entry['t'])
        else:
            empty.append(fp)
    for fp in empty:
        del store['relays'][fp]
        changed = True
    for when in list(store['periods']):
        if when not in live:
            del store['periods'][when]
            changed = True
    return changed


def _authority_voted(entry, index, count):
    """True when this authority has a stored vote in any document for the relay."""
    for key in ('m', 'b', 'f'):
        rows = entry.get(key) or ()
        for row_index in range(count):
            row = rows[row_index] if row_index < len(rows) else None
            if isinstance(row, list) and index < len(row) and row[index] is not None:
                return True
    return False


def _row(entry, key, index, width):
    rows = entry.get(key) or ()
    row = rows[index] if index < len(rows) else None
    if not isinstance(row, list):
        return [None] * width
    if len(row) < width:
        return row + [None] * (width - len(row))
    return row


def _at(entry, key, index, default):
    rows = entry.get(key) or ()
    if index >= len(rows):
        return default
    return rows[index]


def _flag_tally(flags, columns, bit):
    assigned = voted = 0
    names = []
    for column in columns:
        value = flags[column['index']] if column['index'] < len(flags) else None
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        voted += 1
        if value & bit:
            assigned += 1
            names.append(column['name'])
    return assigned, voted, names


def _cell_at(name, measured, bandwidth, when, use_bits, unmeasured, voted=False):
    """One authority cell. ``measured`` and ``bandwidth`` are KB/s or None.

    ``counts`` is false for a relay-reported Bandwidth= while the median is
    taken from Measured= values, so the template can gray that cell. A
    scanner measurement stays visible either way: it is the series operators
    compare across documents.
    """
    if measured is None and bandwidth is None:
        if voted:
            title = (
                "%s voted at valid-after %s and published no Measured= or Bandwidth=."
                % (name, when)
            )
        else:
            title = "%s has no vote document for valid-after %s." % (name, when)
        return {
            'kind': 'absent',
            'display': '',
            'mark': '',
            'counts': False,
            'title': title,
        }
    if measured is not None:
        extra = ''
        if unmeasured:
            extra = (
                ' Fewer than 3 authorities measured this relay in this document, so the '
                'consensus-weight median is of Bandwidth= values, not this measurement.'
            )
        return {
            'kind': 'measured',
            'display': _format_kb(measured, use_bits),
            'mark': 'M',
            'counts': True,
            'title': (
                "Measured=%s KB/s in %s's vote. Document time (valid-after) %s. "
                "This is the bandwidth scanner's measurement.%s"
            ) % (measured, name, when, extra),
        }
    counts = bool(unmeasured)
    return {
        'kind': 'reported',
        'display': _format_kb(bandwidth, use_bits),
        'mark': 'R',
        'counts': counts,
        'title': (
            "Bandwidth=%s KB/s in %s's vote (valid-after %s). "
            "This relay-reported value is not a scanner measurement. "
            "%s"
        ) % (
            bandwidth, name, when,
            'It is an input to the consensus-weight median because fewer than 3 authorities measured the relay.'
            if counts else
            'It does not count toward the consensus-weight median while 3 or more authorities measured the relay.',
        ),
    }


def _ratio(assigned, voted):
    if voted == 0:
        return '—'
    return '%d/%d' % (assigned, voted)


def _flag_title(flag, names, assigned, voted):
    if voted == 0:
        return '%s: no authority voted in this document.' % flag
    who = ', '.join(names) if names else 'none'
    return '%s assigned by %s (%d/%d authorities that voted).' % (flag, who, assigned, voted)


def _median_title(median_kb, unmeasured, cap):
    if median_kb is None:
        return 'No Measured= or Bandwidth= values in the votes stored for this document.'
    if not unmeasured:
        return (
            'Low median of Measured= values: %s KB/s. '
            'When 3 or more authorities measured the relay, the consensus weight uses this median.'
        ) % median_kb
    if cap and median_kb >= MAX_UNMEASURED_BW_KB:
        return (
            'Fewer than 3 authorities measured the relay, and 3 or more publish measurements, '
            'so the consensus weight is the maxunmeasuredbw cap (%s KB/s). '
            'The uncapped Bandwidth= median was at least this high.'
        ) % median_kb
    if cap:
        return (
            'Low median of Bandwidth= values: %s KB/s. Fewer than 3 authorities measured the relay. '
            'That median is under the maxunmeasuredbw cap of %s KB/s, which applies while '
            '3 or more authorities publish measurements.'
        ) % (median_kb, MAX_UNMEASURED_BW_KB)
    return (
        'Low median of Bandwidth= values: %s KB/s. Fewer than 3 authorities measured the relay. '
        'maxunmeasuredbw applies only while 3 or more authorities publish measurements.'
    ) % median_kb


def _format_kb(kb, use_bits):
    """Vote KB/s in the same units as the rest of the relay page."""
    if kb is None:
        return '—'
    return _format_bandwidth_value(int(kb) * VOTE_BW_KB_BYTES, use_bits)


def _color_for(name, index):
    return AUTHORITY_COLORS.get(str(name).lower()) or _PALETTE[index % len(_PALETTE)]


def _svg_series(chunks, dots, color, width, radius, title):
    """One chart series: polylines for runs, circles for isolated points."""
    title = xml_escape(title)
    parts = []
    for chunk in chunks:
        coords = ' '.join('%d,%d' % (round(x_pos), round(y_pos)) for x_pos, y_pos in chunk)
        parts.append(
            '<polyline fill="none" stroke="%s" stroke-width="%s" points="%s"><title>%s</title></polyline>'
            % (color, width, coords, title))
    for x_pos, y_pos in dots:
        parts.append(
            '<circle cx="%d" cy="%d" r="%s" fill="%s"><title>%s</title></circle>'
            % (round(x_pos), round(y_pos), radius, color, title))
    return ''.join(parts)


def _svg_chart(times, medians, series, labels):
    """Inline SVG of the median and Measured= lines. None with fewer than two times."""
    parsed = [(index, when) for index, when in enumerate(times) if when is not None]
    if len(parsed) < 2:
        return None
    values = [value for value in medians if isinstance(value, int)]
    for _name, _color, series_values in series:
        values.extend(value for value in series_values if isinstance(value, int))
    if not values:
        return None
    low = min(values)
    high = max(values)
    span = high - low or 1
    width, height = 720, 196
    left, right, top, bottom = 64, 12, 14, 32
    plot_w = width - left - right
    plot_h = height - top - bottom
    start = parsed[0][1]
    end = parsed[-1][1]
    seconds = (end - start).total_seconds() or 1.0

    def x_of(when):
        return left + (when - start).total_seconds() / seconds * plot_w

    def y_of(value):
        return top + (high - value) / float(span) * plot_h

    def polylines(xs_ys):
        chunks = []
        dots = []
        segment = []
        for x_pos, y_pos in xs_ys:
            if y_pos is None:
                if len(segment) >= 2:
                    chunks.append(segment)
                elif len(segment) == 1:
                    dots.append(segment[0])
                segment = []
            else:
                segment.append((x_pos, y_pos))
        if len(segment) >= 2:
            chunks.append(segment)
        elif len(segment) == 1:
            dots.append(segment[0])
        return chunks, dots

    def points_for(series_values):
        drawn = []
        for index, when in parsed:
            value = series_values[index] if index < len(series_values) else None
            if not isinstance(value, int):
                drawn.append((x_of(when), None))
            else:
                drawn.append((x_of(when), y_of(value)))
        return drawn

    lines = []
    for name, color, series_values in series:
        chunks, dots = polylines(points_for(series_values))
        lines.append(_svg_series(chunks, dots, color, '1.4', '2.5', "Measured= from %s's votes" % name))
    chunks, dots = polylines(points_for(medians))
    lines.append(_svg_series(chunks, dots, MEDIAN_COLOR, '2.4', '3', 'Low median the consensus weight uses'))

    first_label = xml_escape(labels[parsed[0][0]] if parsed[0][0] < len(labels) else '')
    last_label = xml_escape(labels[parsed[-1][0]] if parsed[-1][0] < len(labels) else '')
    # Axis labels stay in vote KB/s. The table uses the page's bits/bytes units.
    y_high = xml_escape('%s KB/s' % high)
    y_low = xml_escape('%s KB/s' % low)
    body = ''.join(lines)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="100%%" height="196" '
        'role="img" aria-label="Authority Measured values and the consensus-weight median">'
        '<title>Measured= by authority and the median the consensus weight uses</title>'
        '<desc>Each point is one authority-vote document. The horizontal axis is that document\'s '
        'valid-after. Colored lines are Measured= in KB/s. The black line is the low median the '
        'consensus weight uses. Periods Allium did not fetch are gaps. This is not Onionoo traffic.'
        '</desc>'
        '<text x="%d" y="12" font-size="11" fill="#444">%s</text>'
        '<text x="%d" y="%d" font-size="11" fill="#444">%s</text>'
        '<text x="%d" y="%d" font-size="11" fill="#444">%s</text>'
        '<text x="%d" y="%d" font-size="11" fill="#444" text-anchor="end">%s</text>'
        '%s</svg>'
    ) % (
        width, height,
        left, y_high,
        left, height - 8, first_label,
        left, top + plot_h, y_low,
        width - right, height - 8, last_label,
        body,
    )


def _parse_time(value):
    """UTC time of a vote stamp. Offsets are applied; naive values are UTC."""
    from .collector_fetcher import _parse_utc
    parsed = _parse_utc(value)
    if parsed is None:
        return None
    return parsed.replace(microsecond=0)


def _fingerprint(value):
    if not isinstance(value, str) or len(value) != 40:
        return None
    fp = value.upper()
    for char in fp:
        if char not in _HEX:
            return None
    return fp


def _kb(value):
    """Same KB/s predicate as the live consensus-weight median."""
    from .collector_fetcher import _vote_kb
    return _vote_kb(value)


def _flag_list(flags):
    """Flag names, once each. A string is not a list of one-character flags."""
    if isinstance(flags, str) or not isinstance(flags, (list, tuple, set)):
        return []
    names = []
    for name in flags:
        if isinstance(name, str) and name not in names:
            names.append(name)
    return names
