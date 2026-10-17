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

import gzip
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape as xml_escape

from ..bandwidth_formatter import _get_formatter
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

# Stable colors for the directory authorities. Unknown names use _PALETTE.
AUTHORITY_COLORS = {
    'bastet': '#1b9e77',
    'dannenberg': '#d95f02',
    'dizum': '#7570b3',
    'faravahar': '#e7298a',
    'gabelmoo': '#66a61e',
    'longclaw': '#e6ab02',
    'maatuska': '#a6761d',
    'moria1': '#666666',
    'tor26': '#1f78b4',
    'Serge': '#b15928',
}
_PALETTE = (
    '#1b9e77', '#d95f02', '#7570b3', '#e7298a', '#66a61e',
    '#e6ab02', '#a6761d', '#1f78b4', '#666666', '#b15928',
)
MEDIAN_COLOR = '#111111'

_ROW_KEYS = ('m', 'b', 'f', 'median', 'unmeasured', 'cap')


def default_history_path():
    """Gzipped JSON cache beside the other CollecTor caches."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, '..', '..', 'data', 'cache', 'vote_history.json.gz'))


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
    voted = 0
    counts = {flag: 0 for flag in AGREEMENT_FLAGS}
    measured = 0
    measurable_votes = 0
    measurable_measured = 0
    measuring = set(measuring_authorities) if measuring_authorities else None
    for name, vote in votes_by_authority.items():
        if not isinstance(vote, dict):
            continue
        voted += 1
        flags = set(vote.get('flags') or ())
        for flag in AGREEMENT_FLAGS:
            if flag in flags:
                counts[flag] += 1
        has_measured = vote.get('measured') is not None
        if has_measured:
            measured += 1
        if measuring is None or name in measuring:
            measurable_votes += 1
            if has_measured:
                measurable_measured += 1
    if voted == 0:
        return None
    split = [flag for flag in AGREEMENT_FLAGS if 0 < counts[flag] < voted]
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
    compared = agreed = split = measurement_split = unmeasured = 0
    by_flag = {flag: 0 for flag in AGREEMENT_FLAGS}
    examples = []
    for relay in members or ():
        info = relay.get('vote_agreement') if isinstance(relay, dict) else None
        if not info:
            continue
        compared += 1
        if info.get('agreed'):
            agreed += 1
        else:
            split += 1
            flags = list(info.get('split_flags') or ())
            for flag in flags:
                if flag in by_flag:
                    by_flag[flag] += 1
            examples.append((0 if 'Guard' in flags else 1, relay, flags))
        if info.get('measurement_split'):
            measurement_split += 1
        if info.get('unmeasured'):
            unmeasured += 1
    if compared == 0:
        return None
    examples.sort(key=lambda item: (item[0], (item[1].get('nickname') or '').lower()))
    shown = []
    for _rank, relay, flags in examples[:limit]:
        shown.append({
            'nickname': relay.get('nickname') or (relay.get('fingerprint') or '')[:12],
            'fingerprint': relay.get('fingerprint') or '',
            'flags_display': ', '.join(flags),
        })
    return {
        'compared': compared,
        'agreed': agreed,
        'split': split,
        'measurement_split': measurement_split,
        'unmeasured': unmeasured,
        'split_flags': _split_flag_rows(by_flag),
        'examples': shown,
    }


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

    for auth_name in sorted(name for name in votes if isinstance(name, str) and name):
        vote = votes.get(auth_name)
        when = document_time(vote)
        relays = vote.get('relays') if isinstance(vote, dict) else None
        if when is None or not isinstance(relays, dict) or not relays:
            continue
        auth_idx, grew = _ensure_authority(store, auth_name)
        if grew:
            changed = True
        width = len(store['authorities'])
        any_measured = False
        for raw_fp, relay in relays.items():
            fp = _fingerprint(raw_fp)
            if fp is None or not isinstance(relay, dict):
                continue
            measured = _kb(relay.get('measured'))
            bandwidth = _kb(relay.get('bandwidth'))
            if measured is not None:
                any_measured = True
            packed = pack_flags(relay.get('flags') or ())
            entry = _ensure_relay(store, fp)
            idx = _ensure_point(entry, when, width)
            if _assign_cell(entry, idx, auth_idx, measured, bandwidth, packed):
                dirty.add((fp, when))
                changed = True
        if any_measured and _note_measuring_authority(store, when, auth_name):
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


def load_history(path=None):
    """Load the history cache. A missing or unreadable file is an empty store."""
    path = path or default_history_path()
    if not os.path.exists(path):
        return empty_store()
    try:
        with gzip.open(path, 'rt', encoding='utf-8') as handle:
            data = json.load(handle)
    except (OSError, ValueError, gzip.BadGzipFile) as exc:
        logger.warning("vote measurement history could not be read (%s); starting empty", exc)
        return empty_store()
    except Exception as exc:  # noqa: BLE001 -- a corrupt cache must not stop generation
        logger.warning("vote measurement history could not be read (%s); starting empty", exc)
        return empty_store()
    return _normalize_store(data)


def save_history(store, path=None):
    """Atomically write the history cache as gzipped JSON."""
    path = path or default_history_path()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    payload = json.dumps(store, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    tmp_path = path + '.tmp'
    with gzip.open(tmp_path, 'wb', compresslevel=6) as handle:
        handle.write(payload)
    os.replace(tmp_path, path)


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
        store = load_history(path)
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
            cells.append(_cell_at(
                name,
                measured[auth_index] if auth_index < len(measured) else None,
                bandwidth[auth_index] if auth_index < len(bandwidth) else None,
                when,
                use_bits,
                unmeasured,
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
    by_flag = {flag: 0 for flag in AGREEMENT_FLAGS}
    summary = {
        'compared': 0,
        'agreed': 0,
        'split': 0,
        'measurement_split': 0,
        'unmeasured': 0,
    }
    history = history if isinstance(history, dict) else empty_store()
    index = relay_index if isinstance(relay_index, dict) else {}
    for relay in relays or ():
        if not isinstance(relay, dict):
            continue
        fp = _fingerprint(relay.get('fingerprint'))
        raw_votes = {}
        if fp is not None:
            indexed = index.get(fp)
            if isinstance(indexed, dict) and isinstance(indexed.get('votes'), dict):
                raw_votes = indexed['votes']
        agreement = classify_authority_votes(raw_votes, bw_authorities)
        if agreement:
            relay['vote_agreement'] = agreement
            summary['compared'] += 1
            if agreement['agreed']:
                summary['agreed'] += 1
            else:
                summary['split'] += 1
                for flag in agreement['split_flags']:
                    if flag in by_flag:
                        by_flag[flag] += 1
            if agreement['measurement_split']:
                summary['measurement_split'] += 1
            if agreement['unmeasured']:
                summary['unmeasured'] += 1
        else:
            relay.pop('vote_agreement', None)
        view = format_relay_history(history, fp, use_bits=use_bits) if fp is not None else None
        if view:
            relay['vote_history'] = view
        else:
            relay.pop('vote_history', None)
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
    store['relays'] = relays if isinstance(relays, dict) else {}
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
    authorities = store['authorities']
    if name in authorities:
        return authorities.index(name), False
    authorities.append(name)
    width = len(authorities)
    for entry in store['relays'].values():
        for key in ('m', 'b', 'f'):
            for row in entry[key]:
                if len(row) < width:
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
    # Document times are hourly and appended in order on a normal run.
    # bisect keeps an out-of-order late vote in the right period.
    lo, hi = 0, len(times)
    while lo < hi:
        mid = (lo + hi) // 2
        if times[mid] < when:
            lo = mid + 1
        else:
            hi = mid
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


def _note_measuring_authority(store, when, auth_name):
    names = store['periods'].get(when)
    if not isinstance(names, list):
        names = []
        store['periods'][when] = names
    if auth_name in names:
        return False
    names.append(auth_name)
    names.sort()
    return True


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


def _prune(store):
    newest = None
    for entry in store['relays'].values():
        for when in entry.get('t') or ():
            parsed = _parse_time(when)
            if parsed is not None and (newest is None or parsed > newest):
                newest = parsed
    if newest is None:
        return False
    cutoff = newest - timedelta(days=RETENTION_DAYS)
    changed = False
    empty = []
    live = set()
    for fp, entry in store['relays'].items():
        keep = []
        for index, when in enumerate(entry['t']):
            parsed = _parse_time(when)
            if parsed is None or parsed >= cutoff:
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
        if value is None:
            continue
        voted += 1
        if value & bit:
            assigned += 1
            names.append(column['name'])
    return assigned, voted, names


def _cell_at(name, measured, bandwidth, when, use_bits, unmeasured):
    """One authority cell. ``measured`` and ``bandwidth`` are KB/s or None.

    ``counts`` is false for a relay-reported Bandwidth= while the median is
    taken from Measured= values, so the template can gray that cell. A
    scanner measurement stays visible either way: it is the series operators
    compare across documents.
    """
    if measured is None and bandwidth is None:
        return {
            'kind': 'absent',
            'display': '',
            'mark': '',
            'counts': False,
            'title': "%s has no vote document for valid-after %s." % (name, when),
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
    if cap:
        return (
            'Low median of Bandwidth= values: %s KB/s. Fewer than 3 authorities measured the relay, '
            'so the consensus weight uses this median, capped at maxunmeasuredbw (%s KB/s) while '
            '3 or more authorities publish measurements.'
        ) % (median_kb, MAX_UNMEASURED_BW_KB)
    return (
        'Low median of Bandwidth= values: %s KB/s. Fewer than 3 authorities measured the relay. '
        'maxunmeasuredbw applies only while 3 or more authorities publish measurements.'
    ) % median_kb


def _format_kb(kb, use_bits):
    if kb is None:
        return '—'
    value = int(kb) * VOTE_BW_KB_BYTES
    if value < 1000:
        if use_bits:
            return '%d bit/s' % (value * 8)
        return '%d B/s' % value
    return _get_formatter(use_bits=use_bits).format_bandwidth_with_suffix(value, decimal_places=1)


def _color_for(name, index):
    return AUTHORITY_COLORS.get(name) or _PALETTE[index % len(_PALETTE)]


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
        title = xml_escape("Measured= from %s's votes" % name)
        for chunk in chunks:
            coords = ' '.join('%d,%d' % (round(x_pos), round(y_pos)) for x_pos, y_pos in chunk)
            lines.append(
                '<polyline fill="none" stroke="%s" stroke-width="1.4" points="%s"><title>%s</title></polyline>'
                % (color, coords, title)
            )
        for x_pos, y_pos in dots:
            lines.append(
                '<circle cx="%d" cy="%d" r="2.5" fill="%s"><title>%s</title></circle>'
                % (round(x_pos), round(y_pos), color, title)
            )
    chunks, dots = polylines(points_for(medians))
    median_title = xml_escape('Low median the consensus weight uses')
    for chunk in chunks:
        coords = ' '.join('%d,%d' % (round(x_pos), round(y_pos)) for x_pos, y_pos in chunk)
        lines.append(
            '<polyline fill="none" stroke="%s" stroke-width="2.4" points="%s"><title>%s</title></polyline>'
            % (MEDIAN_COLOR, coords, median_title)
        )
    for x_pos, y_pos in dots:
        lines.append(
            '<circle cx="%d" cy="%d" r="3" fill="%s"><title>%s</title></circle>'
            % (round(x_pos), round(y_pos), MEDIAN_COLOR, median_title)
        )

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
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith('Z'):
        text = text[:-1]
    if len(text) >= 19:
        text = text[:19]
    for fmt in _TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _fingerprint(value):
    if not isinstance(value, str) or len(value) != 40:
        return None
    fp = value.upper()
    for char in fp:
        if char not in _HEX:
            return None
    return fp


def _kb(value):
    """A vote bandwidth keyword, in KB/s. Rejects bools (a subclass of int)."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value
