"""
File: time_utils.py

Time-related utility functions for parsing, formatting, and calculating
timestamps used throughout the allium codebase.
"""

import time as _time_module

from datetime import datetime, timedelta, timezone

# Shared period name constants (DRY: used across operator_analysis, flag_analysis, network_health)
PERIOD_SHORT_NAMES = {
    '1_month': '1M',
    '3_months': '3M',
    '6_months': '6M',
    '1_year': '1Y',
    '5_years': '5Y',
}

PERIOD_DISPLAY_NAMES = {
    '1_month': '30d',
    '3_months': '90d',
    '6_months': '6mo',
    '1_year': '1y',
    '5_years': '5y',
}


def parse_onionoo_timestamp(timestamp_str):
    """Parse Onionoo timestamp string into datetime object"""
    try:
        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        return timestamp.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def create_time_thresholds():
    """Create common time threshold calculations used across the codebase"""
    now = datetime.utcnow()
    return {
        'now': now,
        'day_ago': now - timedelta(days=1),
        'month_ago': now - timedelta(days=30),
        'six_months_ago': now - timedelta(days=180),
        'year_ago': now - timedelta(days=365)
    }


def format_timestamp_gmt(timestamp=None):
    """Format timestamp as GMT string for HTTP headers and display"""
    import time
    if timestamp is None:
        timestamp = time.time()
    return time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(timestamp))


def format_time_ago(timestamp_str):
    """Format timestamp as multi-unit time ago (e.g., '2y 3m 2w ago')"""
    try:
        # Use centralized parsing
        timestamp = parse_onionoo_timestamp(timestamp_str)
        if timestamp is None:
            return "unknown"

        now = datetime.now(timezone.utc)

        # Calculate time difference
        diff = now - timestamp
        total_seconds = int(diff.total_seconds())

        if total_seconds < 0:
            return "in the future"

        # Time unit calculations
        years = total_seconds // (365 * 24 * 3600)
        remainder = total_seconds % (365 * 24 * 3600)

        months = remainder // (30 * 24 * 3600)
        remainder = remainder % (30 * 24 * 3600)

        weeks = remainder // (7 * 24 * 3600)
        remainder = remainder % (7 * 24 * 3600)

        days = remainder // (24 * 3600)
        remainder = remainder % (24 * 3600)

        hours = remainder // 3600
        remainder = remainder % 3600

        minutes = remainder // 60
        seconds = remainder % 60

        # Build the result with up to 3 largest units
        parts = []
        units = [
            (years, 'y'),
            (months, 'mo'),
            (weeks, 'w'),
            (days, 'd'),
            (hours, 'h'),
            (minutes, 'm'),
            (seconds, 's')
        ]

        # Take the 3 largest non-zero units
        for value, unit in units:
            if value > 0:
                parts.append(f"{value}{unit}")
            if len(parts) == 3:
                break

        if not parts:
            return "just now"

        return " ".join(parts) + " ago"

    except (ValueError, TypeError):
        return "unknown"


def format_timestamp(ts_ms):
    """
    Format Onionoo millisecond timestamp to readable 'YYYY-MM-DD HH:MM' string.

    Used as a Jinja2 filter for overload timestamp display.
    Onionoo overload fields (overload_general_timestamp, overload_ratelimits.timestamp,
    overload_fd_exhausted.timestamp) use millisecond Unix timestamps.

    Args:
        ts_ms: Unix timestamp in milliseconds (int), or None/0

    Returns:
        str: Formatted date string, or "N/A" if input is falsy
    """
    if not ts_ms:
        return "N/A"
    try:
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        return dt.strftime('%Y-%m-%d %H:%M')
    except (ValueError, TypeError, OSError):
        return "N/A"


def format_timestamp_ago(ts_ms):
    """
    Format Onionoo millisecond timestamp to relative 'X hours/days ago' string.

    Used as a Jinja2 filter for overload timestamp display.

    Args:
        ts_ms: Unix timestamp in milliseconds (int), or None/0

    Returns:
        str: Relative time string like "3 hours ago", or "N/A" if input is falsy
    """
    if not ts_ms:
        return "N/A"
    try:
        age_seconds = _time_module.time() - (ts_ms / 1000)
        if age_seconds < 0:
            return "in the future"
        elif age_seconds < 3600:
            return f"{int(age_seconds / 60)} minutes ago"
        elif age_seconds < 86400:
            return f"{int(age_seconds / 3600)} hours ago"
        else:
            return f"{int(age_seconds / 86400)} days ago"
    except (ValueError, TypeError):
        return "N/A"
