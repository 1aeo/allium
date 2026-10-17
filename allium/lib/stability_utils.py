"""
Stability calculation utilities for relay overload analysis.

Allium applies one eligibility window per Onionoo overload signal, using a
single evaluation time for a generation:

- General overload (``overload_general_timestamp`` from /details): a valid
  timestamp with ``0 <= age < 72`` hours. The 72-hour window is the one
  documented for the server-descriptor overload line.
- File-descriptor exhaustion (``overload_fd_exhausted`` from /bandwidth): a
  valid timestamp with ``0 <= age < 72`` hours. The 72-hour window is the
  one documented for the extra-info descriptor line.
- Rate limits (``overload_ratelimits`` from /bandwidth): a valid timestamp
  with ``0 <= age < 24`` hours, plus a valid positive read or write count.
  C Tor publishes this block for relays that hit a limit in the last 24
  hours (``rep_hist_get_overload_stats_lines()``).

A report at exactly 24 or 72 hours is historical, not an active overload.
These windows describe how Allium classifies the reported timestamp. They
do not prove that the relay recovered at the cutoff. Onionoo and Allium's
cache can still carry an older report.

Timestamps must be finite numeric Unix milliseconds. Booleans, strings,
NaN, infinities, nonpositive values, future values, and values that cannot
be formatted are invalid. An invalid signal does not hide another valid one.
"""

import math
import time
from datetime import datetime, timezone

# Kept for callers that imported the general/FD window from this module.
OVERLOAD_THRESHOLD_HOURS = 72
GENERAL_WINDOW_HOURS = 72
FD_WINDOW_HOURS = 72
RATE_WINDOW_HOURS = 24
# Diagnostics still mention a historical general report for a week.
STALE_NOTE_HOURS = 168

_MS_PER_HOUR = 3_600_000
_MS_PER_DAY = 24 * _MS_PER_HOUR
GENERAL_WINDOW_MS = GENERAL_WINDOW_HOURS * _MS_PER_HOUR
FD_WINDOW_MS = FD_WINDOW_HOURS * _MS_PER_HOUR
RATE_WINDOW_MS = RATE_WINDOW_HOURS * _MS_PER_HOUR
STALE_NOTE_MS = STALE_NOTE_HOURS * _MS_PER_HOUR

# Set by bandwidth_utils.apply_bandwidth_overload_fields. Missing means the
# relay dict itself is the record under test (unit tests and direct calls).
BANDWIDTH_AVAILABILITY_KEY = '_bandwidth_overload_availability'

OVERLOAD_GUIDE_URL = 'https://support.torproject.org/relays/performance/overloaded/'

_STATE_CLASS = {
    'eligible': 'al-status-danger-bold',
    'historical': 'al-status-note',
    'absent': 'al-status-muted',
    'zero': 'al-status-success',
    'invalid': 'al-status-warning',
    'unavailable': 'al-status-warning',
    'no_record': 'al-status-warning',
}

_ABSENT_LABEL = {
    'general': 'No general overload report in available data',
    'fd': 'No file-descriptor exhaustion report in available data',
    'rate': 'No rate-limit report in available data',
}

_HISTORICAL_LABEL = {
    'general': 'Historical report — outside the 72-hour window',
    'fd': 'Historical report — outside the 72-hour window',
    'rate': 'Historical report — outside the 24-hour window',
}

_UNAVAILABLE_LABEL = 'Bandwidth data unavailable'
_NO_RECORD_LABEL = 'No bandwidth record available for this relay'
_INVALID_LABEL = 'Invalid overload data'
_REPORTED_LABEL = 'Reported'
_ZERO_LABEL = 'No rate-limit hits reported'

_GUIDANCE = (
    {
        'id': 'memory',
        'signals': ('general',),
        'title': 'Tor internal memory pressure',
        'checks': (
            'Inspect CPU and memory with htop, Tor service logs, host or container '
            'memory headroom, and the effective MaxMemInQueues. When the process was '
            'killed or restarted, check kernel OOM logs separately. A kernel OOM kill '
            'is a different mechanism from Tor freeing memory itself.'
        ),
        'metric': 'tor_relay_load_oom_bytes_total',
        'metric_meaning': (
            'Broken down by subsys. An increase measures bytes freed by Tor’s internal '
            'OOM handling. It is not an invocation count and it is not proof of a kernel OOM kill.'
        ),
    },
    {
        'id': 'ntor',
        'signals': ('general',),
        'title': 'ntor handshake pressure',
        'checks': (
            'Review Tor’s onionskin and drop messages, and whether the CPU is saturated '
            'or contended. The general-overload flag does not say this trigger fired.'
        ),
        'metric': (
            'tor_relay_load_onionskins_total{type="ntor",action="dropped"} and '
            '{type="ntor_v3",action="dropped"}'
        ),
        'metric_meaning': (
            'Compare each with the matching action="processed" series. Inspect both '
            'supported handshake types.'
        ),
    },
    {
        'id': 'tcp',
        'signals': ('general',),
        'title': 'TCP port exhaustion',
        'checks': (
            'Review Tor logs, socket usage, and the host’s ephemeral-port allocation. '
            'On Linux, ss -s and reading net.ipv4.ip_local_port_range are useful starting checks.'
        ),
        'metric': 'tor_relay_load_tcp_exhaustion_total',
        'metric_meaning': 'An increase records additional exhaustion events.',
    },
    {
        'id': 'bandwidth',
        'signals': ('rate',),
        'title': 'Configured bandwidth limits',
        'checks': (
            'Inspect BandwidthRate and BandwidthBurst (the values reported with this hit), '
            'any relay-specific caps such as RelayBandwidthRate and RelayBandwidthBurst, '
            'the intended bandwidth budget, and actual uplink headroom. A rate-limit report '
            'is not evidence of ISP throttling. After checking that evidence and the capacity '
            'you meant to offer, review whether those limits should change.'
        ),
        'metric': (
            'tor_relay_load_global_rate_limit_reached_total{side="read"} and {side="write"}'
        ),
        'metric_meaning': 'Increases indicate additional global token-bucket limit events.',
    },
    {
        'id': 'fd',
        'signals': ('fd',),
        'title': 'File-descriptor exhaustion',
        'checks': (
            'Review socket-open errors, current file-descriptor and socket usage, and the '
            'running process’s effective descriptor limit. On systemd, inspect the actual Tor '
            'unit’s LimitNOFILE. On Linux, /proc/<pid>/limits shows that process limit. '
            'Running ulimit in a shell does not change an existing systemd service. After '
            'checking headroom, adjust the service limit only if the process is short of descriptors.'
        ),
        'metric': 'tor_relay_load_socket_total{state="opened"}',
        'metric_meaning': (
            'A current socket gauge. In the verified Tor release the unlabeled '
            'tor_relay_load_socket_total sample is Tor’s maximum socket value. '
            'That gauge is context, not an FD-exhaustion event counter.'
        ),
    },
)


def _now_ms(now_timestamp):
    """Unix milliseconds for this evaluation. Integers stay exact."""
    if isinstance(now_timestamp, bool) or not isinstance(now_timestamp, (int, float)):
        now_timestamp = time.time()
    elif isinstance(now_timestamp, float) and not math.isfinite(now_timestamp):
        now_timestamp = time.time()
    if isinstance(now_timestamp, int):
        return now_timestamp * 1000
    return now_timestamp * 1000.0


def _valid_timestamp_ms(value):
    """Finite positive Unix milliseconds that ``datetime`` can format, else None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float):
        if not math.isfinite(value) or value <= 0:
            return None
    elif value <= 0:
        return None
    try:
        seconds = value / 1000.0
        if not math.isfinite(seconds):
            return None
        datetime.fromtimestamp(seconds, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')
    except (OverflowError, OSError, ValueError, TypeError):
        return None
    return value


def _format_when(ms):
    seconds = ms / 1000.0
    return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')


def _age_label(age_ms):
    if age_ms is None or age_ms < 0:
        return None
    seconds = age_ms / 1000.0
    if seconds < 60:
        return 'just now'
    if seconds < 3600:
        minutes = int(seconds // 60)
        unit = 'minute' if minutes == 1 else 'minutes'
        return f'{minutes} {unit} ago'
    if seconds < 86400:
        hours = int(seconds // 3600)
        unit = 'hour' if hours == 1 else 'hours'
        return f'{hours} {unit} ago'
    days = int(seconds // 86400)
    unit = 'day' if days == 1 else 'days'
    return f'{days} {unit} ago'


def _classify_timestamp(value, present, now_ms, window_ms):
    """Return state eligible, historical, absent, or invalid for one timestamp."""
    empty = {'state': 'absent', 'ms': None, 'age_ms': None, 'when': None, 'days_ago': None,
             'note_recent': False}
    if not present:
        return empty
    ms = _valid_timestamp_ms(value)
    if ms is None:
        empty['state'] = 'invalid'
        return empty
    age = now_ms - ms
    if age < 0:
        empty['state'] = 'invalid'
        return empty
    try:
        when = _format_when(ms)
    except (OverflowError, OSError, ValueError, TypeError):
        empty['state'] = 'invalid'
        return empty
    days_ago = int(age // _MS_PER_DAY)
    if age < window_ms:
        state = 'eligible'
        days_ago_out = None
        note_recent = False
    else:
        state = 'historical'
        days_ago_out = days_ago
        note_recent = age < STALE_NOTE_MS
    return {
        'state': state,
        'ms': ms,
        'age_ms': age,
        'when': when,
        'days_ago': days_ago_out,
        'note_recent': note_recent,
    }


def _blank_signal():
    return {
        'state': 'absent',
        'status_label': '',
        'status_class': _STATE_CLASS['absent'],
        'ms': None,
        'age_ms': None,
        'when': None,
        'age_label': None,
        'days_ago': None,
        'note_recent': False,
    }


def _finish_signal(signal, state, label):
    signal['state'] = state
    signal['status_label'] = label
    signal['status_class'] = _STATE_CLASS.get(state, _STATE_CLASS['invalid'])
    signal['age_label'] = _age_label(signal.get('age_ms')) if signal.get('when') else None
    return signal


def _timestamp_signal(classified, state, label):
    signal = _blank_signal()
    signal.update({
        'ms': classified['ms'],
        'age_ms': classified['age_ms'],
        'when': classified['when'],
        'days_ago': classified['days_ago'],
        'note_recent': classified['note_recent'],
    })
    return _finish_signal(signal, state, label)


def _bandwidth_availability(relay):
    value = relay.get(BANDWIDTH_AVAILABILITY_KEY) if isinstance(relay, dict) else None
    if value is None:
        return 'loaded'
    if value in ('loaded', 'no_record', 'unavailable'):
        return value
    return 'unavailable'


def _closed_bandwidth_signal(availability):
    signal = _blank_signal()
    if availability == 'unavailable':
        return _finish_signal(signal, 'unavailable', _UNAVAILABLE_LABEL)
    return _finish_signal(signal, 'no_record', _NO_RECORD_LABEL)


def _classify_general(relay, now_ms):
    present = isinstance(relay, dict) and 'overload_general_timestamp' in relay
    value = relay.get('overload_general_timestamp') if present else None
    classified = _classify_timestamp(value, present, now_ms, GENERAL_WINDOW_MS)
    if classified['state'] == 'eligible':
        return _timestamp_signal(classified, 'eligible', _REPORTED_LABEL)
    if classified['state'] == 'historical':
        return _timestamp_signal(classified, 'historical', _HISTORICAL_LABEL['general'])
    if classified['state'] == 'invalid':
        return _finish_signal(_blank_signal(), 'invalid', _INVALID_LABEL)
    return _finish_signal(_blank_signal(), 'absent', _ABSENT_LABEL['general'])


def _parse_count(record, key):
    """Return ('ok', int), ('missing', None), or ('invalid', None)."""
    if key not in record:
        return 'missing', None
    value = record[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 'invalid', None
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer() or value < 0:
            return 'invalid', None
        return 'ok', int(value)
    if value < 0:
        return 'invalid', None
    return 'ok', value


def _parse_config(record, key):
    """Non-negative finite number, or None when the setting is missing or unusable."""
    if key not in record:
        return None
    value = record[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and (not math.isfinite(value) or value < 0):
        return None
    if isinstance(value, int) and value < 0:
        return None
    return value


def _rate_payload(raw, now_ms):
    ts_present = 'timestamp' in raw
    classified = _classify_timestamp(
        raw.get('timestamp') if ts_present else None, ts_present, now_ms, RATE_WINDOW_MS)
    write_state, write_value = _parse_count(raw, 'write-count')
    read_state, read_value = _parse_count(raw, 'read-count')
    signal = _blank_signal()
    signal.update({
        'write_state': write_state,
        'write_value': write_value,
        'read_state': read_state,
        'read_value': read_value,
        'rate_value': _parse_config(raw, 'rate-limit'),
        'burst_value': _parse_config(raw, 'burst-limit'),
    })
    usable_time = classified['state'] in ('eligible', 'historical')
    if usable_time:
        signal.update({
            'ms': classified['ms'],
            'age_ms': classified['age_ms'],
            'when': classified['when'],
            'days_ago': classified['days_ago'],
            'note_recent': classified['note_recent'],
        })
    return signal, classified, write_state, write_value, read_state, read_value


def _classify_rate(relay, availability, now_ms):
    if availability != 'loaded':
        return _closed_bandwidth_signal(availability)
    if 'overload_ratelimits' not in relay:
        return _finish_signal(_blank_signal(), 'absent', _ABSENT_LABEL['rate'])
    raw = relay.get('overload_ratelimits')
    if not isinstance(raw, dict):
        return _finish_signal(_blank_signal(), 'invalid', _INVALID_LABEL)
    signal, classified, write_state, write_value, read_state, read_value = _rate_payload(raw, now_ms)
    if classified['state'] in ('absent', 'invalid'):
        return _finish_signal(signal, 'invalid', _INVALID_LABEL)
    if classified['state'] == 'historical':
        return _finish_signal(signal, 'historical', _HISTORICAL_LABEL['rate'])
    hit = ((write_state == 'ok' and write_value > 0) or (read_state == 'ok' and read_value > 0))
    if hit:
        return _finish_signal(signal, 'eligible', _REPORTED_LABEL)
    both_zero = (
        write_state == 'ok' and read_state == 'ok' and write_value == 0 and read_value == 0
    )
    if both_zero:
        return _finish_signal(signal, 'zero', _ZERO_LABEL)
    return _finish_signal(signal, 'invalid', _INVALID_LABEL)


def _classify_fd(relay, availability, now_ms):
    if availability != 'loaded':
        return _closed_bandwidth_signal(availability)
    if 'overload_fd_exhausted' not in relay:
        return _finish_signal(_blank_signal(), 'absent', _ABSENT_LABEL['fd'])
    raw = relay.get('overload_fd_exhausted')
    if not isinstance(raw, dict):
        return _finish_signal(_blank_signal(), 'invalid', _INVALID_LABEL)
    present = 'timestamp' in raw
    classified = _classify_timestamp(
        raw.get('timestamp') if present else None, present, now_ms, FD_WINDOW_MS)
    if classified['state'] == 'eligible':
        return _timestamp_signal(classified, 'eligible', _REPORTED_LABEL)
    if classified['state'] == 'historical':
        return _timestamp_signal(classified, 'historical', _HISTORICAL_LABEL['fd'])
    return _finish_signal(_blank_signal(), 'invalid', _INVALID_LABEL)


def _headline(general, rate, fd):
    signals = (general, rate, fd)
    if any(signal['state'] == 'eligible' for signal in signals):
        return 'overloaded'
    incomplete = ('invalid', 'unavailable', 'no_record')
    if any(signal['state'] in incomplete for signal in signals):
        return 'incomplete'
    return 'clear'


def _latest_eligible_ms(general, rate, fd):
    stamps = [
        signal['ms'] for signal in (general, rate, fd)
        if signal['state'] == 'eligible' and signal.get('ms') is not None
    ]
    return max(stamps) if stamps else None


def evaluate_overload(relay, now_timestamp=None):
    """
    Classify one relay's overload signals.

    ``now_timestamp`` is Unix seconds. Pass the generation's captured time so
    every consumer shares one clock. Bandwidth availability comes from
    ``_bandwidth_overload_availability`` when the pipeline has set it.

    The returned dict is the shared fact record. ``compute_relay_stability``
    adds formatted rates, guidance, and the stability-cell fields.
    """
    if now_timestamp is None:
        now_timestamp = time.time()
    now_ms = _now_ms(now_timestamp)
    relay = relay if isinstance(relay, dict) else {}
    availability = _bandwidth_availability(relay)
    try:
        general = _classify_general(relay, now_ms)
        rate = _classify_rate(relay, availability, now_ms)
        fd = _classify_fd(relay, availability, now_ms)
    except (OverflowError, OSError, ValueError, TypeError, ArithmeticError):
        general = _finish_signal(_blank_signal(), 'invalid', _INVALID_LABEL)
        rate = _finish_signal(_blank_signal(), 'invalid', _INVALID_LABEL)
        fd = _finish_signal(_blank_signal(), 'invalid', _INVALID_LABEL)
    headline = _headline(general, rate, fd)
    return {
        'evaluated_at': now_timestamp,
        'bandwidth_availability': availability,
        'headline': headline,
        'is_overloaded': headline == 'overloaded',
        'latest_eligible_ms': _latest_eligible_ms(general, rate, fd),
        'general': general,
        'rate': rate,
        'fd': fd,
        'show_time_note': any(signal.get('when') for signal in (general, rate, fd)),
        'guide_url': OVERLOAD_GUIDE_URL,
    }


def _format_rate_display(value, formatter, decimal_places):
    if value is None:
        return 'unavailable'
    try:
        if formatter is None:
            from .bandwidth_formatter import _get_formatter
            formatter = _get_formatter(use_bits=False)
        unit = formatter.determine_unit(value)
        return formatter.format_bandwidth_with_suffix(
            value, unit, decimal_places=decimal_places)
    except (TypeError, ValueError, OverflowError, ZeroDivisionError, ArithmeticError):
        return 'unavailable'


def _format_burst_display(value):
    if value is None:
        return 'unavailable'
    try:
        from .bandwidth_formatter import format_data_volume_with_unit
        return format_data_volume_with_unit(value)
    except (TypeError, ValueError, OverflowError, ArithmeticError):
        return 'unavailable'


def _count_display(state, value, active, confirmed_zero):
    if state != 'ok' or value is None:
        return 'unknown', 'al-status-note'
    text = f'{value:,}'
    if active and value > 0:
        return text, 'al-status-danger-bold'
    if value == 0 and confirmed_zero:
        return text, 'al-status-success'
    return text, 'al-status-note'


def _attach_rate_display(rate, formatter):
    # A non-dict record is invalid but has no counts to show. A dict with a bad
    # timestamp or a bad count still shows the directions that could be read.
    show = rate['state'] in ('eligible', 'historical', 'zero') or (
        rate['state'] == 'invalid' and 'write_state' in rate
    )
    rate['show_counts'] = show
    if not show:
        rate['rate_display'] = '—'
        rate['burst_display'] = '—'
        rate['write_display'] = '—'
        rate['read_display'] = '—'
        rate['write_class'] = 'al-status-muted'
        rate['read_class'] = 'al-status-muted'
        return
    active = rate['state'] == 'eligible'
    confirmed_zero = rate['state'] == 'zero'
    rate['rate_display'] = _format_rate_display(rate.get('rate_value'), formatter, 2)
    rate['burst_display'] = _format_burst_display(rate.get('burst_value'))
    rate['write_display'], rate['write_class'] = _count_display(
        rate.get('write_state'), rate.get('write_value'), active, confirmed_zero)
    rate['read_display'], rate['read_class'] = _count_display(
        rate.get('read_state'), rate.get('read_value'), active, confirmed_zero)


def _guidance_for(facts):
    items = []
    for item in _GUIDANCE:
        if any(facts[name]['state'] == 'eligible' for name in item['signals']):
            items.append(item)
    return items


def _historical_notes(facts):
    notes = []
    general = facts['general']
    if general['state'] == 'historical' and general.get('days_ago') is not None:
        notes.append(f"Last general overload: {general['days_ago']} days ago")
    if facts['rate']['state'] == 'historical':
        notes.append('Historical rate-limit report outside the 24-hour window')
    if facts['fd']['state'] == 'historical':
        notes.append('Historical file-descriptor report outside the 72-hour window')
    return notes


def _incomplete_notes(facts):
    notes = []
    if facts['general']['state'] == 'invalid':
        notes.append(_INVALID_LABEL)
    bandwidth_states = {facts['rate']['state'], facts['fd']['state']}
    if 'unavailable' in bandwidth_states:
        notes.append(_UNAVAILABLE_LABEL)
    elif 'no_record' in bandwidth_states:
        notes.append(_NO_RECORD_LABEL)
    if facts['rate']['state'] == 'invalid' or facts['fd']['state'] == 'invalid':
        if _INVALID_LABEL not in notes:
            notes.append(_INVALID_LABEL)
    notes.extend(_historical_notes(facts))
    return notes or ['Overload signals could not all be evaluated']


def _direction_text(state, value):
    if state == 'ok' and value is not None:
        return f'{value:,}'
    return 'unknown'


def _overloaded_tooltip(facts, formatter):
    reasons = []
    general = facts['general']
    if general['state'] == 'eligible' and general.get('when'):
        reasons.append(f"General overload at {general['when']} UTC")
    rate = facts['rate']
    if rate['state'] == 'eligible':
        limit = _format_rate_display(rate.get('rate_value'), formatter, 0)
        write = _direction_text(rate.get('write_state'), rate.get('write_value'))
        read = _direction_text(rate.get('read_state'), rate.get('read_value'))
        reasons.append(f'Rate limits hit W:{write} R:{read} (limit: {limit})')
    fd_signal = facts['fd']
    if fd_signal['state'] == 'eligible' and fd_signal.get('when'):
        reasons.append(f"FD exhaustion (last: {fd_signal['when']})")
    return '; '.join(reasons) or 'Overloaded'


def _with_utc(value):
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if 'UTC' in text or text.endswith('Z'):
        return text
    return text + ' UTC'


def sources_line(source_meta):
    """One line separating evaluation time, document snapshots, and cache age."""
    if not source_meta:
        return ''
    parts = []
    evaluated = source_meta.get('evaluated_label')
    if evaluated:
        parts.append(f'Evaluated {evaluated}')
    details = _with_utc(source_meta.get('details_published'))
    if details:
        text = f'/details snapshot {details}'
        if source_meta.get('details_cache_label'):
            text += f" ({source_meta['details_cache_label']})"
        parts.append(text)
    if source_meta.get('bandwidth_loaded'):
        bandwidth = _with_utc(source_meta.get('bandwidth_published'))
        if bandwidth:
            text = f'/bandwidth snapshot {bandwidth}'
            if source_meta.get('bandwidth_cache_label'):
                text += f" ({source_meta['bandwidth_cache_label']})"
            parts.append(text)
        else:
            parts.append('/bandwidth document loaded without a snapshot time')
    else:
        parts.append('/bandwidth not loaded for this generation')
    if not parts:
        return ''
    return '. '.join(parts) + '.'


def _attach_display(facts, formatter, source_meta):
    _attach_rate_display(facts['rate'], formatter)
    facts['guidance'] = _guidance_for(facts)
    facts['sources_line'] = sources_line(source_meta)
    notes = _historical_notes(facts)
    facts['historical_note'] = '; '.join(notes)
    return facts


def _stability_fields(facts, formatter):
    headline = facts['headline']
    if headline == 'overloaded':
        return {
            'stability_is_overloaded': True,
            'stability_text': 'Overloaded',
            'stability_color': '#dc3545',
            'stability_tooltip': _overloaded_tooltip(facts, formatter),
        }
    if headline == 'incomplete':
        return {
            'stability_is_overloaded': False,
            'stability_text': 'Incomplete',
            'stability_color': '#6c757d',
            'stability_tooltip': '; '.join(_incomplete_notes(facts)),
        }
    tooltip = facts.get('historical_note') or 'No overload reported'
    return {
        'stability_is_overloaded': False,
        'stability_text': 'Not Overloaded',
        'stability_color': '#28a745',
        'stability_tooltip': tooltip,
    }


def compute_relay_stability(relay, now_timestamp=None, bandwidth_formatter=None, source_meta=None):
    """
    Stability cell for one relay, derived from ``evaluate_overload``.

    Returns the existing ``stability_*`` fields plus ``overload``, the shared
    fact record used by the detail card, diagnostics, and chart caption.
    ``stability_is_overloaded`` is true only when at least one signal is inside
    its eligibility window. Historical, zero-hit, missing, and invalid records
    do not set it. Incomplete evaluations use ``stability_text`` ``Incomplete``
    rather than ``Not Overloaded``.
    """
    facts = evaluate_overload(relay, now_timestamp)
    _attach_display(facts, bandwidth_formatter, source_meta)
    status = _stability_fields(facts, bandwidth_formatter)
    status['overload'] = facts
    return status


def compute_group_overload_summary(members):
    """Summarize overloaded relays in a group; None if zero (hides the bullet).

    Returns a dict with the count fields plus 'relays': the overloaded member
    dicts themselves (references, not copies) sorted by observed bandwidth
    descending — impact order, matching the by-overload.html table sort — so
    templates can link each relay (nickname/fingerprint/stability_tooltip).
    """
    total = len(members)
    if not total:
        return None
    overloaded = [r for r in members if r.get('stability_is_overloaded')]
    if not overloaded:
        return None
    overloaded.sort(key=lambda r: (
        -int(r.get('observed_bandwidth', 0) or 0),
        r.get('fingerprint', ''),
    ))
    pct = 100.0 * len(overloaded) / total
    return {
        'overloaded': len(overloaded),
        'total': total,
        'pct_formatted': f"{pct:.1f}%" if pct >= 0.05 else "<0.1%",
        'relays': overloaded,
    }
