"""Chart identity line: the relay nickname (with its fingerprint's start when ``Unnamed``) and its contact's ``url:``
host (not ``aroi_domain``), or for an operator its name (AROI domain, host or contact text) and relay count."""

from ..string_utils import URL_FIELD_TOKEN_RE


def operator_from_contact(contact):
    """``url:`` host (lowercase, ``www.`` stripped), or ``""``."""
    match = URL_FIELD_TOKEN_RE.search(contact or "")  # the token holds no whitespace
    host = match.group(1).lower().split("/")[0] if match else ""
    host = host[4:] if host.startswith("www.") else host
    return host if "." in host else ""  # also rules out "none" and "localhost"


def operator_identity(members):
    """``tor@kllx.eu  ·  64 relays`` for an operator's member relays: their AROI domain, else the first ``url:``
    host, else the first contact text with its whitespace collapsed, cut at a word when longer than 50
    characters."""
    contacts = [relay.get("contact") for relay in members]
    name = next((relay["aroi_domain"] for relay in members if relay.get("aroi_domain") not in (None, "", "none")),
                "") or next(filter(None, map(operator_from_contact, contacts)), "")
    if not name:
        name = " ".join(next((c for c in contacts if c and c.strip()), "").split())
        name = name if len(name) <= 50 else name[:49].rsplit(" ", 1)[0] + "…"
    return "{}  ·  {:,} relay{}".format(name, len(members), "" if len(members) == 1 else "s")


def chart_identity(nickname, operator="", fingerprint=""):
    """``jeangrae · 1aeo.com``, or just the nickname when there is no host. A relay named ``Unnamed`` (Tor's
    default, which many share) or not at all gets its fingerprint's first 8 digits: ``Unnamed · 0123ABCD…``."""
    nick, op = (nickname or "").strip(), (operator or "").strip()
    if nick.lower() in ("", "unnamed") and fingerprint:
        nick = "{}{}…".format(nick + " · " if nick else "", fingerprint[:8])
    if op and nick and op.lower() != nick.lower():
        return "{}  ·  {}".format(nick, op)
    return nick or op
