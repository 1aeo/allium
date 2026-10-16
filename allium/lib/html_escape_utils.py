#!/usr/bin/env python3
"""
HTML Escaping Utilities.

Collapsed from a former 5-class hierarchy: production needs exactly one
bulk per-relay escaping pass (escape_relay_fields) plus the
safe_html_escape convenience function and a few fallback constants.

All escaping returns markupsafe.Markup so Jinja2 autoescape treats the
values as already-safe and does not escape them a second time (bug plan
Phase 1); fallback constants contain no HTML specials and stay plain str.
"""

import html

from markupsafe import Markup

# Fallback constants for external use
UNKNOWN_ESCAPED = "Unknown"
UNKNOWN_LOWERCASE = "unknown"
NONE_ESCAPED = "none"
NA_FALLBACK = "N/A"


def safe_html_escape(value, fallback=""):
    """
    Safely escape HTML content with consistent fallback handling.

    Args:
        value: The value to escape (can be None, str, or other types)
        fallback: Fallback value if input is None/empty (default: "")

    Returns:
        Markup: HTML-escaped string marked safe for autoescape, or fallback
    """
    if value is None or value == "":
        return fallback
    return Markup(html.escape(str(value)))


def _escape_truncated(value, max_length):
    """Escape a value after truncating it to max_length characters."""
    return Markup(html.escape(str(value)[:max_length]))


def escape_relay_fields(relay):
    """
    Apply comprehensive HTML escaping to a single relay dict, in place.

    Adds the *_escaped / *_truncated fields templates and Python-side HTML
    assembly consume. Called once per relay from
    relays._preprocess_template_data.

    Returns:
        dict: The relay with all escaped fields added
    """
    contact = relay.get("contact")
    relay["contact_escaped"] = safe_html_escape(contact) if contact else ""

    flags = relay.get("flags") or []
    relay["flags_escaped"] = [safe_html_escape(flag) for flag in flags]
    relay["flags_lower_escaped"] = [safe_html_escape(flag.lower()) for flag in flags]

    nickname = relay.get("nickname")
    if nickname:
        relay["nickname_escaped"] = safe_html_escape(nickname)
        relay["nickname_truncated"] = _escape_truncated(nickname, 14)
    else:
        relay["nickname_escaped"] = UNKNOWN_ESCAPED
        relay["nickname_truncated"] = UNKNOWN_ESCAPED

    platform = relay.get("platform")
    if platform:
        relay["platform_escaped"] = safe_html_escape(platform)
        relay["platform_truncated"] = _escape_truncated(platform, 10)
    else:
        relay["platform_escaped"] = UNKNOWN_ESCAPED
        relay["platform_truncated"] = UNKNOWN_ESCAPED

    as_name = relay.get("as_name")
    if as_name:
        relay["as_name_escaped"] = safe_html_escape(as_name)
        relay["as_name_truncated"] = _escape_truncated(as_name, 20)
    else:
        relay["as_name_escaped"] = UNKNOWN_ESCAPED
        relay["as_name_truncated"] = UNKNOWN_ESCAPED

    aroi_domain = relay.get("aroi_domain")
    if aroi_domain and aroi_domain != "none":
        relay["aroi_domain_escaped"] = safe_html_escape(aroi_domain)
    else:
        relay["aroi_domain_escaped"] = NONE_ESCAPED

    first_seen = relay.get("first_seen")
    if first_seen:
        date_only = str(first_seen).split(' ', 1)[0]
        relay["first_seen_date_escaped"] = safe_html_escape(date_only)
    else:
        relay["first_seen_date_escaped"] = ""

    return relay
