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
    # PERF: Early return for relays with no overload data (~98% of relays)
    # Avoid creating lists and doing datetime operations for the common case
    general_ts = relay.get('overload_general_timestamp')
    ratelimits = relay.get('overload_ratelimits')
    fd_exhausted = relay.get('overload_fd_exhausted')
    
    if not general_ts and not ratelimits and not fd_exhausted:
        return {
            'stability_is_overloaded': False,
            'stability_tooltip': 'No overload reported',
            'stability_text': 'Not Overloaded',
            'stability_color': '#28a745'
        }
    
    # Only compute timestamp once if needed (for the ~2% with overload data)
    if now_timestamp is None:
        now_timestamp = time.time()
    
    is_overloaded = False
    reasons = []
    stale_reasons = []  # For "last overload X days ago" info
    
    # Check overload_general_timestamp with 72-hour threshold (Tor spec proposal 328)
    if general_ts:
        # Onionoo timestamps are in milliseconds
        age_hours = (now_timestamp - general_ts / 1000) / 3600
        if age_hours < OVERLOAD_THRESHOLD_HOURS:
            is_overloaded = True
            gen_date = datetime.fromtimestamp(general_ts / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')
            reasons.append(f"General overload at {gen_date} UTC")
        else:
            # Not currently overloaded, but note when it last was
            days_ago = int(age_hours / 24)
            stale_reasons.append(f"Last general overload: {days_ago} days ago")
    
    # Check overload_ratelimits (from bandwidth)
    if ratelimits:
        write_count = ratelimits.get('write-count', 0)
        read_count = ratelimits.get('read-count', 0)
        if write_count > 0 or read_count > 0:
            is_overloaded = True
            
            # Format rate limit using bandwidth_formatter if available
            rate_limit = ratelimits.get('rate-limit', 0)
            if bandwidth_formatter and rate_limit:
                unit = bandwidth_formatter.determine_unit(rate_limit)
                rate_str = bandwidth_formatter.format_bandwidth_with_suffix(rate_limit, unit, decimal_places=0)
            else:
                rate_str = f"{rate_limit} B/s"
            
            reasons.append(f"Rate limits hit W:{write_count} R:{read_count} (limit: {rate_str})")
    
    # Check overload_fd_exhausted (from bandwidth)
    if fd_exhausted:
        is_overloaded = True
        fd_ts = fd_exhausted.get('timestamp', 0)
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

