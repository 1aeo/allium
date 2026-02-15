"""
File: time_utils.py

Time-related utility functions for parsing, formatting, and calculating
timestamps used throughout the allium codebase.
"""

from datetime import datetime, timedelta, timezone


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
