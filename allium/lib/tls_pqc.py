"""
Tor TLS post-quantum readiness from the Margot ``tls-ciphers`` scan.

The command writes ``cipher_suites.csv`` (semicolon-separated; the weight
column itself contains a semicolon). ahf.me publishes HTML tables only, at
``/tor-tls-pqc/<date>/``. This module parses whichever of those a URL returns.
The date in the URL is the scan time. A missing fingerprint is "not in this
scan". A Tor version string is not evidence of X25519MLKEM768.
"""

import csv
import io
import re
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

PQC_GROUP = "X25519MLKEM768"
SCHEMA_VERSION = 1

STATUS_SAW = "saw"
STATUS_OTHER = "other"
STATUS_NO_GROUP = "no_group"
STATUS_NOT_IN_SCAN = "not_in_scan"
ANSWERS = {
    STATUS_SAW: "Saw X25519MLKEM768",
    STATUS_OTHER: "Did not see X25519MLKEM768",
    STATUS_NO_GROUP: "No negotiated group",
    STATUS_NOT_IN_SCAN: "not in this scan",
}

DEFAULT_INDEX_URL = "https://ahf.me/tor-tls-pqc/"
LIBRESSL_ISSUE_URL = "https://gitlab.torproject.org/tpo/core/tor/-/issues/41300"
GUIDANCE_TEXT = (
    "Tor 0.4.8.17 and later can negotiate X25519MLKEM768 when that build uses "
    "OpenSSL 3.5.0 or later. LibreSSL 4.3.0 implements ML-KEM-768; current Tor "
    "does not use the LibreSSL group."
)

_FP_RE = re.compile(r"^[A-F0-9]{40}$")
_DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")
_HREF_RE = re.compile(r"""href\s*=\s*(["'])?(?P<href>[^"'>\s]+)""", re.I)
_HEAD_DATE_RE = re.compile(
    r"<(?:title|h1)[^>]*>\s*(20\d{2}-\d{2}-\d{2})", re.I)
_EMPTY_TOKENS = frozenset(("", "N/A"))
_HEADER_ALIASES = {
    "nickname": "nickname",
    "fingerprint": "fingerprint",
    "rsaid": "fingerprint",
    "ciphersuite": "cipher",
    "group": "group",
    "keyexchangegroup": "group",
    "connected": "connected",
}


def normalize_fingerprint(value):
    """Uppercase 40-hex relay identity, or "" when the cell is not one."""
    if not isinstance(value, str):
        return ""
    text = value.strip().upper()
    if text.startswith("$"):
        text = text[1:]
    if _FP_RE.match(text):
        return text
    return ""


def _clean_token(value):
    text = (value or "").strip()
    if text.upper() in _EMPTY_TOKENS:
        return ""
    return text


def _header_key(cell):
    return re.sub(r"[^a-z]", "", (cell or "").lower())


def _real_date(candidate):
    if not candidate or _DATE_RE.fullmatch(candidate) is None:
        return ""
    try:
        datetime.strptime(candidate, "%Y-%m-%d")
    except ValueError:
        return ""
    return candidate


def _scan_time_from_url(url):
    for part in reversed(urlsplit(url or "").path.split("/")):
        found = _real_date(part)
        if found:
            return found
    return ""


def _scan_time_from_html(text):
    match = _HEAD_DATE_RE.search(text[:4000])
    return _real_date(match.group(1) if match else "")


class _TableCollector(HTMLParser):
    """Collect every HTML table as a list of stripped cell rows."""

    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.tables = []
        self._stack = []
        self._raw = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._raw += 1
            return
        if self._raw:
            return
        attributes = {}
        for key, value in attrs:
            attributes[key] = value or ""
        if tag == "table":
            self._stack.append({
                "id": attributes.get("id", ""),
                "rows": [],
                "row": None,
                "cell": None,
            })
        elif self._stack and tag == "tr":
            self._stack[-1]["row"] = []
        elif self._stack and tag in ("td", "th"):
            self._stack[-1]["cell"] = []

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._raw:
            self._raw -= 1
            return
        if self._raw or not self._stack:
            return
        frame = self._stack[-1]
        if tag in ("td", "th") and frame["cell"] is not None:
            if frame["row"] is not None:
                frame["row"].append("".join(frame["cell"]).strip())
            frame["cell"] = None
        elif tag == "tr" and frame["row"] is not None:
            if any(frame["row"]):
                frame["rows"].append(frame["row"])
            frame["row"] = None
        elif tag == "table":
            self.tables.append(self._stack.pop())

    def handle_data(self, data):
        if self._raw:
            return
        if self._stack and self._stack[-1]["cell"] is not None:
            self._stack[-1]["cell"].append(data)

    def close(self):
        HTMLParser.close(self)
        while self._stack:
            self.tables.append(self._stack.pop())


def _header_map(row):
    mapping = {}
    for index, cell in enumerate(row):
        name = _HEADER_ALIASES.get(_header_key(cell))
        if name and name not in mapping:
            mapping[name] = index
    return mapping


def _select_scan_table(tables):
    ordered = sorted(tables, key=lambda table: table.get("id") != "tor_pqc_tls_table")
    for table in ordered:
        rows = table.get("rows") or []
        for header_at, header in enumerate(rows[:5]):
            mapping = _header_map(header)
            if "fingerprint" in mapping and "group" in mapping:
                return rows[header_at:], mapping
    return None, None


def _cell(row, index):
    if index is None or index >= len(row):
        return ""
    return row[index].strip()


def _remember_row(relays, fingerprint, nickname, cipher, group, connected):
    """One fingerprint can be listed twice. A hybrid handshake wins, then any group."""
    group = _clean_token(group)
    cipher = _clean_token(cipher)
    # HTML rows have no connected column. A recorded group is a completed
    # handshake. An explicit false from the CSV clears the group.
    if connected is False:
        group = ""
        cipher = ""
    if not group:
        connected = False
    elif connected is None:
        connected = True
    row = {
        "nickname": nickname or "",
        "cipher_suite": cipher,
        "key_exchange_group": group,
        "connected": bool(connected),
    }
    existing = relays.get(fingerprint)
    if existing is None:
        relays[fingerprint] = row
        return
    old_group = (existing.get("key_exchange_group") or "").upper()
    new_group = (row.get("key_exchange_group") or "").upper()
    if new_group == PQC_GROUP.upper() and old_group != PQC_GROUP.upper():
        relays[fingerprint] = row
    elif not old_group and new_group:
        relays[fingerprint] = row


def _document(relays, url, artifact, scan_time):
    return {
        "schema": SCHEMA_VERSION,
        "artifact": artifact,
        "source_url": url or "",
        "index_url": "",
        "scan_time": scan_time or "unknown",
        "relays": relays,
    }


def validate_tls_pqc_document(data):
    """True for a parsed scan this module is willing to cache and display."""
    if not isinstance(data, dict):
        return False
    if data.get("schema") != SCHEMA_VERSION:
        return False
    if data.get("artifact") not in ("html", "csv"):
        return False
    if not isinstance(data.get("scan_time"), str) or not data.get("scan_time"):
        return False
    if not isinstance(data.get("source_url"), str) or not data.get("source_url"):
        return False
    relays = data.get("relays")
    if not isinstance(relays, dict):
        return False
    for fingerprint, row in relays.items():
        if not isinstance(fingerprint, str) or not _FP_RE.match(fingerprint):
            return False
        if not isinstance(row, dict):
            return False
        if not isinstance(row.get("key_exchange_group", ""), str):
            return False
        if not isinstance(row.get("cipher_suite", ""), str):
            return False
        if "connected" in row and not isinstance(row.get("connected"), bool):
            return False
    return True


def _looks_like_csv(text):
    for line in text.lstrip("\ufeff").splitlines():
        if line.strip():
            folded = line.lower().replace(" ", "")
            return "rsa_id" in folded and "key_exchange_group" in folded
    return False


def _looks_like_html(text):
    folded = text[:20000].lower()
    return "<html" in folded or "<!doctype" in folded or "<table" in folded


def parse_csv_scan(text, url):
    """Parse Margot's semicolon CSV. Raises ValueError when the header is wrong."""
    sample = text.lstrip("\ufeff")
    first = ""
    for line in sample.splitlines():
        if line.strip():
            first = line
            break
    delimiter = ";" if ";" in first else ","
    reader = csv.reader(io.StringIO(sample), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration:
        raise ValueError("TLS PQC CSV is empty")
    mapping = _header_map(header)
    if "fingerprint" not in mapping or "group" not in mapping:
        raise ValueError("TLS PQC CSV header has no fingerprint and group columns")
    relays = {}
    connected_index = mapping.get("connected")
    for row in reader:
        if not any(cell.strip() for cell in row):
            continue
        fingerprint = normalize_fingerprint(_cell(row, mapping["fingerprint"]))
        if not fingerprint:
            continue
        connected = None
        flag = _cell(row, connected_index).lower()
        if flag in ("true", "1", "yes"):
            connected = True
        elif flag in ("false", "0", "no"):
            connected = False
        _remember_row(
            relays, fingerprint, _cell(row, mapping.get("nickname")),
            _cell(row, mapping.get("cipher")), _cell(row, mapping["group"]), connected,
        )
    return _document(relays, url, "csv", _scan_time_from_url(url))


def parse_html_scan(text, url):
    """Parse a published ahf.me scan page. Returns None when it has no scan table.

    None means the body is HTML without the scan table (the date index). A
    table whose header row names fingerprint and group is a scan, including a
    scan that recorded no relays.
    """
    parser = _TableCollector()
    parser.feed(text)
    parser.close()
    rows, mapping = _select_scan_table(parser.tables)
    if rows is None:
        return None
    relays = {}
    for row in rows[1:]:
        fingerprint = normalize_fingerprint(_cell(row, mapping.get("fingerprint")))
        if not fingerprint:
            continue
        _remember_row(
            relays, fingerprint, _cell(row, mapping.get("nickname")),
            _cell(row, mapping.get("cipher")), _cell(row, mapping.get("group")), None,
        )
    scan_time = _scan_time_from_url(url) or _scan_time_from_html(text)
    return _document(relays, url, "html", scan_time)


def parse_scan_payload(payload, url):
    """Parse one response body.

    Returns a document dict, None when the body is an HTML index with no scan
    table, or raises ValueError when the body is neither a scan nor an index.
    """
    if isinstance(payload, bytes):
        text = payload.decode("utf-8", errors="replace")
    else:
        text = payload
    if _looks_like_csv(text):
        return parse_csv_scan(text, url)
    if _looks_like_html(text):
        return parse_html_scan(text, url)
    raise ValueError("unrecognized TLS PQC scan payload")


def latest_scan_url(html, index_url):
    """Absolute URL of the newest dated scan linked from an index page.

    Links stay on the index host. An https index does not follow an http URL.
    A date that is not a real calendar day is ignored, so 2026-99-99 cannot
    sort ahead of a real scan.
    """
    found = []
    index = urlsplit(index_url or "")
    index_path = index.path.rstrip("/")
    for match in _HREF_RE.finditer(html or ""):
        absolute = urljoin(index_url or "", match.group("href"))
        link = urlsplit(absolute)
        if link.scheme not in ("http", "https"):
            continue
        if index.scheme == "https" and link.scheme != "https":
            continue
        if index.netloc and link.netloc.lower() != index.netloc.lower():
            continue
        path = link.path.rstrip("/")
        date = _real_date(path.rsplit("/", 1)[-1])
        if not date:
            continue
        direct = index_path + "/" + date
        if not (path.endswith("/tor-tls-pqc/" + date) or path == direct):
            continue
        if not absolute.endswith("/"):
            absolute += "/"
        found.append((date, absolute))
    if not found:
        return ""
    found.sort()
    return found[-1][1]


def load_tls_pqc_scan(fetch_body, start_url):
    """Fetch ``start_url`` and parse a scan, following the index to its latest date.

    ``fetch_body(url)`` returns bytes. A dated scan page or a Margot CSV is
    parsed directly. The ahf.me index has no table; the newest ``/tor-tls-pqc/YYYY-MM-DD/``
    link is fetched next.
    """
    first = fetch_body(start_url)
    parsed = parse_scan_payload(first, start_url)
    if parsed is not None:
        return parsed
    text = first.decode("utf-8", errors="replace") if isinstance(first, bytes) else first
    latest = latest_scan_url(text, start_url)
    if not latest:
        raise ValueError("TLS PQC index has no dated scan link")
    if latest.rstrip("/") == (start_url or "").rstrip("/"):
        raise ValueError("TLS PQC index linked to itself")
    second = fetch_body(latest)
    parsed = parse_scan_payload(second, latest)
    if parsed is None:
        raise ValueError("latest TLS PQC link was not a scan table or CSV")
    parsed["index_url"] = start_url or ""
    return parsed


def classify_scan_row(row):
    """Return (status, group, cipher) for one scan row, or a missing row."""
    if row is None:
        return STATUS_NOT_IN_SCAN, "", ""
    group = _clean_token(row.get("key_exchange_group") or "")
    cipher = _clean_token(row.get("cipher_suite") or "")
    if row.get("connected") is False or not group:
        return STATUS_NO_GROUP, "", cipher if row.get("connected") is not False else ""
    if group.upper() == PQC_GROUP.upper():
        return STATUS_SAW, group, cipher
    return STATUS_OTHER, group, cipher


def _lookup_row(document, fingerprint):
    relays = document.get("relays") or {}
    normalized = normalize_fingerprint(fingerprint or "")
    if not normalized:
        return None
    return relays.get(normalized)


def attach_tls_pqc_to_relays(relays, document):
    """Copy the latest scan onto each relay. Returns False when there is no scan.

    Absent fingerprints get status ``not_in_scan``. An empty group on a row
    that is present gets ``no_group``. Neither state is a failed relay.
    """
    if not validate_tls_pqc_document(document):
        return False
    scan_time = document.get("scan_time") or ""
    scan_url = document.get("source_url") or ""
    for relay in relays:
        status, group, cipher = classify_scan_row(
            _lookup_row(document, relay.get("fingerprint")))
        relay["tls_pqc_status"] = status
        relay["tls_pqc_answer"] = ANSWERS[status]
        relay["tls_pqc_group"] = group
        relay["tls_pqc_cipher"] = cipher
        relay["tls_pqc_scan_time"] = scan_time
        relay["tls_pqc_scan_url"] = scan_url
    return True
