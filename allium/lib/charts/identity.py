"""Chart identity line: the relay nickname and its contact's ``url:`` host (not ``aroi_domain``)."""

from ..string_utils import URL_FIELD_TOKEN_RE


def operator_from_contact(contact):
    """``url:`` host (lowercase, ``www.`` stripped), or ``""``."""
    match = URL_FIELD_TOKEN_RE.search(contact or "")  # the token holds no whitespace
    host = match.group(1).lower().split("/")[0] if match else ""
    host = host[4:] if host.startswith("www.") else host
    return host if "." in host else ""  # also rules out "none" and "localhost"


def chart_identity(nickname, operator=""):
    """``jeangrae · 1aeo.com``, or just the nickname when there is no host."""
    nick, op = (nickname or "").strip(), (operator or "").strip()
    if op and nick and op.lower() != nick.lower():
        return "{}  ·  {}".format(nick, op)
    return nick or op
