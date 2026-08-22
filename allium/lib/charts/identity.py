"""Chart identity helpers.

Operator on the figure is the contact ``url:`` host when present — the
same rule as the locked mockups. This is not ``relay['aroi_domain']``,
which is only set for a complete AROI triple.
"""

import re

# Same token shape as allium.lib.string_utils.URL_FIELD_TOKEN_RE, kept
# local so this module stays import-light on the generate hot path.
_RE_URL_FIELD = re.compile(r"\burl:(?:https?://)?([^,\s/]+)", re.I)

# Flag-set roles used by the write/read strip and the Throughput title.
ROLE_EXIT_GUARD = "Exit+Guard"
ROLE_EXIT = "Exit"
ROLE_GUARD = "Guard"
ROLE_MIDDLE = "Middle"


def operator_from_contact(contact):
    """Short operator label for the chart identity line.

    Returns the ``url:`` host (lowercase, ``www.`` stripped) or ``""``.
    Does not dump the raw contact, an email, or ``as_name``.
    """
    if not contact:
        return ""
    match = _RE_URL_FIELD.search(contact)
    if not match:
        return ""
    host = match.group(1).strip().lower()
    if host.startswith("www."):
        host = host[4:]
    host = host.split("/")[0]
    if "." not in host or host in ("none", "localhost"):
        return ""
    return host


def chart_identity(nickname, operator=None):
    """``jeangrae · 1aeo.com``, or just the nickname when there is no host."""
    nick = (nickname or "").strip()
    op = (operator or "").strip()
    if op and nick and op.lower() != nick.lower():
        return "{}  ·  {}".format(nick, op)
    return nick or op


def role_from_flags(flags):
    """Frozen band role for this relay's current flag set."""
    flags = flags or []
    exit_f = "Exit" in flags
    guard_f = "Guard" in flags
    if exit_f and guard_f:
        return ROLE_EXIT_GUARD
    if exit_f:
        return ROLE_EXIT
    if guard_f:
        return ROLE_GUARD
    return ROLE_MIDDLE
