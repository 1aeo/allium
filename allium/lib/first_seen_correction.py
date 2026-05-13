"""
Short-term workaround for onionoo's mass `first_seen` reset bug.

Background
==========

Onionoo's `/details` endpoint periodically resets `first_seen` for large
swathes of relays. The root cause is in `NodeDetailsStatusUpdater.java` in
the upstream onionoo source: whenever the persisted `NodeStatus` is dropped
or arrives empty (collector-sync delay, backend desync, fresh deployment),
`firstSeenMillis` is re-initialised from the next consensus's `valid-after`
instead of from older data. Issues filed upstream:

    https://gitlab.torproject.org/tpo/network-health/metrics/onionoo/-/issues/40018
    https://gitlab.torproject.org/tpo/network-health/metrics/onionoo/-/issues/40028
    https://gitlab.torproject.org/tpo/network-health/metrics/onionoo/-/issues/40033
    https://gitlab.torproject.org/tpo/network-health/metrics/onionoo/-/issues/40042

A 2022 upstream hack (commit 4dec094) addressed this via `UptimeStatus`
cross-check but was reverted in commit 85af138 without fixing the underlying
state-loss. As of 2026-05-13, 87.9% of all running relays share the reset
timestamp `2026-04-06 23:00:00`.

Crucially, onionoo's `/uptime` endpoint stores history independently of
`NodeStatus.firstSeenMillis` and survives the reset. Allium already fetches
`/uptime` in parallel with `/details`, so we can cross-check `first_seen`
against the earliest non-null entry in uptime history *before* downstream
processing sees the value.

This module is a self-contained workaround. When upstream fixes the bug, this
module's call site in coordinator.create_relay_set() can be deleted and the
file removed with no other changes.

Design rules
============

- Only ever move `first_seen` *earlier*, never later. The original onionoo
  value is always a lower bound on "earliest possible first_seen".
- Treat `None` in uptime `values` as "no data"; treat `0` as a valid
  observation ("tracked but down").
- Defensive floor: reject any uptime-derived timestamp before 2004-01-01
  (Tor's first public relays appeared in 2003-2004; anything earlier is
  garbage like the epoch-zero bug from issue #40028).
- Catastrophic restore where both `NodeStatus` and `UptimeStatus` are lost
  simultaneously cannot be recovered; in that case we degrade silently to
  current (buggy) behaviour. Acceptable because that's the existing baseline.
- Precision is bucket-aligned: corrected timestamps come from
  `period.first + index * interval`, which is interval-aligned. The largest
  bucket (`5_years`) has 10-day intervals, so corrected `first_seen` may
  be up to 10 days *earlier* than truth, never later. Trading <=10 days
  backwards uncertainty for the >=365 day backwards error in the raw data
  is a clear improvement.
- Relays older than 5 years: the `5_years` bucket saturates at "5 years ago",
  so corrected `first_seen` for very old relays is a lower bound capped at
  5 years ago. The "only move earlier" rule prevents regression for relays
  whose existing `first_seen` is already correctly older than 5 years.

Python 3.8 compatible: uses Optional[...]/Dict[...] (not `X | None`) and
PEP 484 comment-style annotations for the public API.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from .time_utils import parse_onionoo_timestamp


# Defensive floor: earlier than the first public Tor relays existed.
# Any uptime-derived timestamp before this is rejected as garbage
# (cf. onionoo issue #40028, the 1970-01-01 bridge bug).
FIRST_SEEN_FLOOR = datetime(2004, 1, 1, tzinfo=timezone.utc)

# Onionoo's wire format for timestamp strings (naive UTC, no timezone suffix).
_ONIONOO_TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'



def correct_first_seen(relay_data,             # type: Dict[str, Any]
                       uptime_data,            # type: Optional[Dict[str, Any]]
                       progress_logger=None,   # type: Any
                       ):
    # type: (...) -> Dict[str, Any]
    """Mutate ``relay_data`` in place, repairing ``first_seen`` from uptime history.

    For each relay in ``relay_data['relays']``, look up the corresponding entry
    in ``uptime_data['relays']`` by fingerprint. Compute the earliest timestamp
    at which onionoo's uptime endpoint observed the relay (the first non-null
    value across all uptime periods; treats ``0`` as a legitimate observation
    of "tracked but down"). If that timestamp is strictly earlier than
    ``relay['first_seen']`` AND >= ``FIRST_SEEN_FLOOR``, the function:

    * replaces ``first_seen`` with the onionoo-formatted string;
    * stamps ``first_seen_onionoo_raw`` with the original value;
    * stamps ``_first_seen_corrected`` = True and
      ``_first_seen_correction_source`` = "onionoo_uptime".

    These three fields are only added when a correction is applied, so JSON
    for unaffected relays is byte-identical to the input.

    A diagnostic summary is stamped under
    ``relay_data['_first_seen_correction_summary']``::

        {
            'total':              <N total relays>,
            'corrected':          <N where first_seen was moved earlier>,
            'unchanged':          <N where uptime existed but was not earlier>,
            'missing_uptime':     <N with no entry in uptime_data>,
            'no_signal':          <N where uptime entry existed but had no
                                   non-null values>,
            'rejected_floor':     <N where uptime timestamp was < FIRST_SEEN_FLOOR>,
            'invalid_first_seen': <N where relay['first_seen'] was unparseable>,
        }

    The function is a safe no-op when:

    * ``uptime_data`` is ``None`` or missing the ``relays`` key
    * ``uptime_data['relays']`` is empty
    * ``relay_data`` is ``None`` / missing ``relays`` / has an empty list

    Returns the same ``relay_data`` dict (for chaining).
    """
    if not isinstance(relay_data, dict):
        return relay_data
    relays = relay_data.get('relays')
    if not relays:
        # Nothing to correct; still stamp an empty summary so callers that
        # surface .first_seen_repair_stats don't have to special-case None.
        relay_data['_first_seen_correction_summary'] = _empty_summary(0)
        return relay_data

    uptime_index = _build_uptime_index(uptime_data)

    summary = _empty_summary(len(relays))

    for relay in relays:
        fingerprint = relay.get('fingerprint')
        raw_first_seen = relay.get('first_seen')
        current_dt = parse_onionoo_timestamp(raw_first_seen) if raw_first_seen else None

        if current_dt is None:
            summary['invalid_first_seen'] += 1
            continue

        if not fingerprint or fingerprint not in uptime_index:
            summary['missing_uptime'] += 1
            continue

        uptime_relay = uptime_index[fingerprint]
        earliest = _earliest_uptime_timestamp(uptime_relay)
        if earliest is None:
            summary['no_signal'] += 1
            continue

        if earliest < FIRST_SEEN_FLOOR:
            summary['rejected_floor'] += 1
            continue

        if earliest >= current_dt:
            # Uptime says relay was first observed at the same time as, or
            # later than, /details claims. Nothing to correct.
            summary['unchanged'] += 1
            continue

        # Apply the correction.
        relay['first_seen_onionoo_raw'] = raw_first_seen
        relay['first_seen'] = earliest.strftime(_ONIONOO_TIMESTAMP_FORMAT)
        relay['_first_seen_corrected'] = True
        relay['_first_seen_correction_source'] = 'onionoo_uptime'
        summary['corrected'] += 1

    relay_data['_first_seen_correction_summary'] = summary

    message = _format_summary_message(summary)
    _log(progress_logger, message)

    return relay_data


def _earliest_uptime_timestamp(uptime_relay):
    # type: (Dict[str, Any]) -> Optional[datetime]
    """Return UTC datetime of the earliest non-null observation in uptime
    history across all available periods, or ``None`` if no period yields a
    valid signal.

    For each period in ``uptime_relay['uptime']``, find the first index ``i``
    where ``values[i] is not None`` (note: ``0`` is a valid observation
    meaning "tracked but down"). Compute::

        ts = parse(period['first']) + i * period['interval'] seconds

    Return the minimum ``ts`` across all valid periods. Periods missing
    ``first``, ``interval``, or with an empty/all-null ``values`` array are
    skipped silently.
    """
    if not isinstance(uptime_relay, dict):
        return None
    uptime_section = uptime_relay.get('uptime')
    if not isinstance(uptime_section, dict):
        return None

    earliest = None  # type: Optional[datetime]

    # We intentionally iterate over uptime_section.items() rather than the
    # _UPTIME_PERIODS whitelist, so that any new period names onionoo
    # introduces are picked up automatically without a code change.
    for period_name, period_data in uptime_section.items():
        ts = _earliest_in_period(period_data)
        if ts is None:
            continue
        if earliest is None or ts < earliest:
            earliest = ts

    return earliest


def _earliest_in_period(period_data):
    # type: (Any) -> Optional[datetime]
    """Find the earliest non-null timestamp in a single uptime period dict.

    Returns None for malformed/empty periods. Tolerant of:

    * non-dict input
    * missing ``first``
    * unparseable ``first``
    * missing/non-numeric ``interval``
    * missing/empty/non-list ``values``
    * all-None ``values``
    """
    if not isinstance(period_data, dict):
        return None

    first_str = period_data.get('first')
    if not first_str:
        return None
    first_dt = parse_onionoo_timestamp(first_str)
    if first_dt is None:
        return None

    interval = period_data.get('interval')
    if not isinstance(interval, (int, float)) or interval <= 0:
        return None

    values = period_data.get('values')
    if not isinstance(values, list) or not values:
        return None

    for idx, value in enumerate(values):
        if value is not None:
            # 0 is a valid observation (tracked but down); only None means
            # "no data for this interval".
            try:
                return first_dt + timedelta(seconds=int(interval) * idx)
            except (OverflowError, ValueError):
                return None

    # All values were None.
    return None


def _build_uptime_index(uptime_data):
    # type: (Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]
    """Index uptime_data['relays'] by fingerprint for O(1) lookup.

    Tolerates missing/malformed input by returning an empty dict.
    """
    if not isinstance(uptime_data, dict):
        return {}
    relays = uptime_data.get('relays')
    if not isinstance(relays, list):
        return {}
    index = {}  # type: Dict[str, Dict[str, Any]]
    for entry in relays:
        if not isinstance(entry, dict):
            continue
        fp = entry.get('fingerprint')
        if isinstance(fp, str) and fp:
            index[fp] = entry
    return index


def _empty_summary(total):
    # type: (int) -> Dict[str, int]
    return {
        'total': total,
        'corrected': 0,
        'unchanged': 0,
        'missing_uptime': 0,
        'no_signal': 0,
        'rejected_floor': 0,
        'invalid_first_seen': 0,
    }


def _format_summary_message(summary):
    # type: (Dict[str, int]) -> str
    return (
        "First-seen correction: repaired {corrected}/{total} relays from "
        "onionoo uptime history (missing_uptime={missing_uptime}, "
        "no_signal={no_signal}, rejected_floor={rejected_floor}, "
        "invalid_first_seen={invalid_first_seen})"
    ).format(**summary)


def _log(progress_logger, message):
    # type: (Any, str) -> None
    """Logger-shape-agnostic emit. Accepts:

    * ``ProgressLogger``-like objects (calls ``.log_without_increment(msg)``)
    * ``logging.Logger``-like objects (calls ``.info(msg)``)
    * bare callables (calls ``progress_logger(msg)``)
    * ``None`` (no-op)

    Any exception from the logger is swallowed -- we never break correction
    because of a noisy logger.
    """
    if progress_logger is None:
        return
    try:
        log_method = getattr(progress_logger, 'log_without_increment', None)
        if callable(log_method):
            log_method(message)
            return
        info_method = getattr(progress_logger, 'info', None)
        if callable(info_method):
            info_method(message)
            return
        if callable(progress_logger):
            progress_logger(message)
    except Exception:  # noqa: BLE001 -- logging must never break the caller.
        pass
