"""Chart identity: contact ``url:`` host, not ``aroi_domain``."""

from ..string_utils import URL_FIELD_TOKEN_RE

PEERS = {"Guard": "Guards", "Exit": "Exits", "Exit+Guard": "Exit+Guards", "Middle": "middle relays"}


def operator_from_contact(contact):
    """``url:`` host (lowercase, ``www.`` stripped), or ``""``."""
    match = URL_FIELD_TOKEN_RE.search(contact or "")
    if not match:
        return ""
    host = match.group(1).strip().lower()
    if host.startswith("www."):
        host = host[4:]
    host = host.split("/")[0]
    return host if "." in host and host not in ("none", "localhost") else ""


def chart_identity(nickname, operator=""):
    """``jeangrae · 1aeo.com``, or just the nickname when there is no host."""
    nick, op = (nickname or "").strip(), (operator or "").strip()
    if op and nick and op.lower() != nick.lower():
        return "{}  ·  {}".format(nick, op)
    return nick or op


def role_from_flags(flags):
    flags = flags or ()
    if "Exit" in flags:
        return "Exit+Guard" if "Guard" in flags else "Exit"
    return "Guard" if "Guard" in flags else "Middle"


def peers_word(role):
    return PEERS.get(role, role or "relays")
