"""
Stability calculation utilities for relay overload analysis.

This module provides shared functions for computing relay stability status
from Onionoo API overload indicators.

Per Tor spec proposal 328, overload status remains for 72 hours after
the last detected overload event.

Onionoo API overload fields:
- overload_general_timestamp (from /details): int (ms) - OOM, onionskins, TCP port
- overload_ratelimits (from /bandwidth): dict with rate-limit, burst-limit, write-count, read-count, timestamp
- overload_fd_exhausted (from /bandwidth): dict with timestamp
"""

import time
from datetime import datetime, timezone

# Tor spec proposal 328: overload flag remains for 72 hours (canonical source)
OVERLOAD_THRESHOLD_HOURS = 72


def evaluate_overload(relay, now_timestamp=None):
    """
    Evaluate a relay's raw Onionoo overload indicators into shared facts.

    Single source of truth for parsing the THREE independent overload fields
    (overload_general_timestamp, overload_ratelimits, overload_fd_exhausted)
    and for the 72-hour general-overload window (Tor spec proposal 328).

    Presentation POLICY intentionally stays with the callers, whose semantics
    differ and must be preserved:
    - compute_relay_stability (relay listing "Stability" cell):
      * ANY truthy overload_fd_exhausted marks the relay overloaded
      * stale general overloads are reported no matter how old
    - relay_diagnostics._check_overload_issues (diagnostics page):
      * overload_fd_exhausted must be a dict to produce an issue
      * stale general overloads are only reported within 7 days (168h)
      * additionally emits separate write/read and rate-config issues

    Args:
        relay: Dict with potential overload fields from Onionoo
        now_timestamp: Current Unix timestamp (seconds). Defaults to time.time().
                      For batch processing, pass once to avoid repeated calls.

    Returns:
        Dict of facts:
        - has_any (bool): any overload field present (PERF: False for ~98% of relays)
        - general_ts: raw overload_general_timestamp (ms) or None
        - general_age_hours (float|None): age of general overload event
        - general_active (bool): age < OVERLOAD_THRESHOLD_HOURS
        - general_date (str|None): 'YYYY-MM-DD HH:MM' UTC when active
        - general_days_ago (int|None): whole days since event when stale
        - ratelimits: raw overload_ratelimits dict or None
        - rate_limit, burst_limit, write_count, read_count (int)
        - ratelimit_hit (bool): write_count > 0 or read_count > 0
        - fd_exhausted: raw overload_fd_exhausted value or None
        - fd_timestamp: fd_exhausted['timestamp'] (ms) when dict, else None
    """
    general_ts = relay.get('overload_general_timestamp')
    ratelimits = relay.get('overload_ratelimits')
    fd_exhausted = relay.get('overload_fd_exhausted')

    facts = {
        'has_any': bool(general_ts or ratelimits or fd_exhausted),
        'general_ts': general_ts,
        'general_age_hours': None,
        'general_active': False,
        'general_date': None,
        'general_days_ago': None,
        'ratelimits': ratelimits,
        'rate_limit': 0,
        'burst_limit': 0,
        'write_count': 0,
        'read_count': 0,
        'ratelimit_hit': False,
        'fd_exhausted': fd_exhausted,
        'fd_timestamp': None,
    }

    # PERF: Early return for relays with no overload data (~98% of relays)
    if not facts['has_any']:
        return facts

    # Only compute timestamp once if needed (for the ~2% with overload data)
    if now_timestamp is None:
        now_timestamp = time.time()

    # overload_general_timestamp with 72-hour threshold (Tor spec proposal 328)
    if general_ts:
        # Onionoo timestamps are in milliseconds
        age_hours = (now_timestamp - general_ts / 1000) / 3600
        facts['general_age_hours'] = age_hours
        if age_hours < OVERLOAD_THRESHOLD_HOURS:
            facts['general_active'] = True
            facts['general_date'] = datetime.fromtimestamp(
                general_ts / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')
        else:
            facts['general_days_ago'] = int(age_hours / 24)

    # overload_ratelimits (from bandwidth endpoint)
    if ratelimits:
        facts['rate_limit'] = ratelimits.get('rate-limit', 0)
        facts['burst_limit'] = ratelimits.get('burst-limit', 0)
        facts['write_count'] = ratelimits.get('write-count', 0)
        facts['read_count'] = ratelimits.get('read-count', 0)
        facts['ratelimit_hit'] = facts['write_count'] > 0 or facts['read_count'] > 0

    # overload_fd_exhausted (from bandwidth endpoint)
    if isinstance(fd_exhausted, dict):
        facts['fd_timestamp'] = fd_exhausted.get('timestamp', 0)

    return facts


def compute_relay_stability(relay, now_timestamp=None, bandwidth_formatter=None):
    """
    Compute stability status from a relay's overload indicators.

    Checks THREE independent Onionoo API overload fields:
    - overload_general_timestamp (from /details) - OOM, onionskins, TCP port (72h threshold per spec)
    - overload_ratelimits (from /bandwidth) - rate/burst limits exceeded
    - overload_fd_exhausted (from /bandwidth) - file descriptor exhaustion

    Args:
        relay: Dict with potential overload fields from Onionoo
        now_timestamp: Current Unix timestamp (seconds). Defaults to time.time().
                      For batch processing, pass once to avoid repeated time.time() calls.
        bandwidth_formatter: BandwidthFormatter instance for rate/burst formatting.
                            If None, raw bytes values are shown.

    Returns:
        Dict with:
        - stability_is_overloaded (bool)
        - stability_text (str): "Overloaded" or "Not Overloaded"
        - stability_color (str): hex color code
        - stability_tooltip (str): description of active conditions
    """
    facts = evaluate_overload(relay, now_timestamp)

    if not facts['has_any']:
        return {
            'stability_is_overloaded': False,
            'stability_tooltip': 'No overload reported',
            'stability_text': 'Not Overloaded',
            'stability_color': '#28a745'
        }

    is_overloaded = False
    reasons = []
    stale_reasons = []  # For "last overload X days ago" info

    # General overload: this caller reports stale events no matter how old
    # (the diagnostics page caps stale reporting at 7 days instead)
    if facts['general_ts']:
        if facts['general_active']:
            is_overloaded = True
            reasons.append(f"General overload at {facts['general_date']} UTC")
        else:
            # Not currently overloaded, but note when it last was
            stale_reasons.append(f"Last general overload: {facts['general_days_ago']} days ago")

    # Rate limits: only overloaded when a limit was actually hit
    if facts['ratelimit_hit']:
        is_overloaded = True

        # Format rate limit using bandwidth_formatter if available
        rate_limit = facts['rate_limit']
        if bandwidth_formatter and rate_limit:
            unit = bandwidth_formatter.determine_unit(rate_limit)
            rate_str = bandwidth_formatter.format_bandwidth_with_suffix(rate_limit, unit, decimal_places=0)
        else:
            rate_str = f"{rate_limit} B/s"

        reasons.append(f"Rate limits hit W:{facts['write_count']} R:{facts['read_count']} (limit: {rate_str})")

    # FD exhaustion: this caller treats ANY truthy overload_fd_exhausted as
    # overloaded (the diagnostics page requires a dict instead)
    if facts['fd_exhausted']:
        is_overloaded = True
        fd_ts = facts['fd_timestamp']
        if fd_ts:
            fd_date = datetime.fromtimestamp(fd_ts / 1000, tz=timezone.utc).strftime('%Y-%m-%d')
            reasons.append(f"FD exhaustion (last: {fd_date})")
        else:
            reasons.append("FD exhaustion reported")
    
    # Build result
    if is_overloaded:
        return {
            'stability_is_overloaded': True,
            'stability_tooltip': "; ".join(reasons),
            'stability_text': 'Overloaded',
            'stability_color': '#dc3545'
        }
    
    # Not overloaded - include stale info in tooltip if available
    tooltip = "No overload reported"
    if stale_reasons:
        tooltip = "; ".join(stale_reasons)
    
    return {
        'stability_is_overloaded': False,
        'stability_tooltip': tooltip,
        'stability_text': 'Not Overloaded',
        'stability_color': '#28a745'
    }


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
    overloaded.sort(key=lambda r: -(r.get('observed_bandwidth') or 0))
    pct = 100.0 * len(overloaded) / total
    return {
        'overloaded': len(overloaded),
        'total': total,
        'pct_formatted': f"{pct:.1f}%" if pct >= 0.05 else "<0.1%",
        'relays': overloaded,
    }

