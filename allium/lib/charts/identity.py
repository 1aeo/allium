"""Chart identity: contact ``url:`` host, not ``aroi_domain``."""

from ..string_utils import URL_FIELD_TOKEN_RE

ROLE_EXIT_GUARD = "Exit+Guard"
ROLE_EXIT = "Exit"
ROLE_GUARD = "Guard"
ROLE_MIDDLE = "Middle"

IDENTITY_FONTSIZE = 11
IDENTITY_TITLE_GAP_PT = 10
IDENTITY_EXTRA_FIG_H = 0.48
IDENTITY_TOP_SHIFT = 0.075
IDENTITY_TITLE_PAD_BOOST = 6


def operator_from_contact(contact):
    """``url:`` host (lowercase, ``www.`` stripped), or ``""``."""
    if not contact:
        return ""
    match = URL_FIELD_TOKEN_RE.search(contact)
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


def peers_word(bands_or_role):
    if isinstance(bands_or_role, dict):
        role = bands_or_role.get("role") or ""
    else:
        role = bands_or_role or ""
    return {
        ROLE_GUARD: "Guards",
        ROLE_EXIT: "Exits",
        ROLE_EXIT_GUARD: "Exit+Guards",
        ROLE_MIDDLE: "middle relays",
    }.get(role, role or "relays")
