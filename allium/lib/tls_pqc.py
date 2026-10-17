"""
Tor TLS post-quantum readiness from the Network Health Margot scanner.

Margot's ``tls-ciphers`` command (branch ``ahf/tls-ciphers-scanner``) probes
each relay and writes ``cipher_suites.csv``:

    nickname;rsa_id;ed25519_id;weight_status;weight;connected;address;cipher_suite;key_exchange_group

The ``weight`` value already contains a semicolon (``measured;100``), which is
why the header has nine columns and the success format string has eight
placeholders. A relay whose handshake did not complete is still a row, with
``connected`` false and empty cipher and group fields.

Alexander Færøy publishes the runs at https://ahf.me/tor-tls-pqc/<date>/.
Those pages are HTML tables (nickname, fingerprint, cipher suite, group).
Checked copies (2026-02-26, 2026-03-01, 2026-06-18) have no JSON or CSV
sibling. This module parses the CSV when a URL serves one, and otherwise
parses that HTML table. The published date in the page URL is the scan time;
the HTML does not include a clock time.

A fingerprint that is absent from the scan is "not in this scan". That is a
different state from a row whose group is empty, and from a row that
negotiated a group other than X25519MLKEM768. Onionoo does not publish the
negotiated group, and a Tor version of 0.4.8.17 or later is not evidence:
that version negotiates X25519MLKEM768 only when it is built against OpenSSL
3.5.0 or later. LibreSSL 4.3.0 implements the group, and current Tor does
not use it (tpo/core/tor#41300).
"""

import csv
import io
import re
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

PQC_GROUP = "X25519MLKEM768"
SCHEMA_VERSION = 1

ANSWER_SAW = "Saw X25519MLKEM768"
ANSWER_OTHER = "Did not see X25519MLKEM768"
ANSWER_NO_GROUP = "No negotiated group"
ANSWER_NOT_IN_SCAN = "not in this scan"

STATUS_SAW = "saw"
STATUS_OTHER = "other"
STATUS_NO_GROUP = "no_group"
STATUS_NOT_IN_SCAN = "not_in_scan"

DEFAULT_INDEX_URL = "https://ahf.me/tor-tls-pqc/"
FORUM_URL = (
    "https://forum.torproject.org/t/"
    "tor-relays-post-quantum-cryptography-in-tors-tls-layer-help-needed/21288"
)
MARGOT_URL = "https://gitlab.torproject.org/tpo/network-health/margot"
MARGOT_BRANCH_URL = (
    "https://gitlab.torproject.org/ahf/margot/-/tree/ahf/tls-ciphers-scanner"
)
LIBRESSL_ISSUE_URL = "https://gitlab.torproject.org/tpo/core/tor/-/issues/41300"

GUIDANCE_TEXT = (
    "Tor 0.4.8.17 and later can negotiate X25519MLKEM768 when that build uses "
    "OpenSSL 3.5.0 or later. LibreSSL 4.3.0 implements ML-KEM-768; current Tor "
    "does not use the LibreSSL group."
)

HTML_ARTIFACT_NOTE = (
    "Margot's tls-ciphers command writes cipher_suites.csv "
    "(nickname;rsa_id;ed25519_id;weight_status;weight;connected;address;"
    "cipher_suite;key_exchange_group). The scans published at ahf.me are HTML "
    "tables of nickname, fingerprint, cipher suite, and key-exchange group, "
    "with no JSON or CSV sibling."
)
CSV_ARTIFACT_NOTE = (
    "Parsed from the semicolon-separated cipher_suites.csv written by "
    "Margot's tls-ciphers command."
)

_CSV_HEADER_MARKERS = ("rsa_id", "key_exchange_group")
_FP_RE = re.compile(r"^[A-F0-9]{40}$")
_DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")
_HREF_RE = re.compile(r"""href\s*=\s*(["'])?(?P<href>[^"'>\s]+)""", re.I)
_TITLE_DATE_RE = re.compile(
    r"<title[^>]*>\s*(20\d{2}-\d{2}-\d{2})", re.I)
_H1_DATE_RE = re.compile(r"<h1[^>]*>\s*(20\d{2}-\d{2}-\d{2})", re.I)
_EMPTY_TOKENS = frozenset(("", "N/A"))
_OPERATOR_LIST_LIMIT = 12

_ROLE_FLAGS = (
    ("guard", "Guard"),
    ("exit", "Exit"),
    ("authority", "Authority"),
)


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


def _scan_time_from_url(url):
    path = urlsplit(url or "").path
    match = _DATE_RE.search(path)
    return match.group(1) if match else ""


def _scan_time_from_html(text):
    head = text[:4000]
    for pattern in (_TITLE_DATE_RE, _H1_DATE_RE):
        match = pattern.search(head)
        if match:
            return match.group(1)
    return ""


def _percent(part, whole):
    if not whole:
        return None
    return round((100.0 * part) / float(whole), 1)


def _consensus_weight(relay):
    value = relay.get("consensus_weight")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    if value < 0:
        return 0
    return int(value)


class _TableCollector(HTMLParser):
    """Collect every HTML table as a list of stripped cell rows."""

    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.tables = []
        self._stack = []

    def handle_starttag(self, tag, attrs):
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
        if not self._stack:
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
        if self._stack and self._stack[-1]["cell"] is not None:
            self._stack[-1]["cell"].append(data)

    def close(self):
        HTMLParser.close(self)
        while self._stack:
            self.tables.append(self._stack.pop())


def _header_map(row):
    mapping = {}
    for index, cell in enumerate(row):
        key = _header_key(cell)
        if key in ("nickname", "fingerprint", "ciphersuite", "group", "keyexchangegroup"):
            mapping[key] = index
    if "group" not in mapping and "keyexchangegroup" in mapping:
        mapping["group"] = mapping["keyexchangegroup"]
    return mapping


def _select_scan_table(tables):
    ordered = sorted(tables, key=lambda table: table.get("id") != "tor_pqc_tls_table")
    for table in ordered:
        rows = table.get("rows") or []
        if not rows:
            continue
        mapping = _header_map(rows[0])
        if "fingerprint" in mapping and "group" in mapping:
            return rows, mapping
    return None, None


def _cell(row, index):
    if index is None or index >= len(row):
        return ""
    return row[index].strip()


def _remember_row(relays, fingerprint, nickname, cipher, group, connected):
    """Keep the first observed group when the same fingerprint appears twice."""
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
    if not existing.get("key_exchange_group") and row["key_exchange_group"]:
        relays[fingerprint] = row


def _document(relays, url, artifact, scan_time):
    if artifact == "csv":
        note = CSV_ARTIFACT_NOTE
    else:
        note = HTML_ARTIFACT_NOTE
    if not scan_time:
        scan_time = "unknown"
    return {
        "schema": SCHEMA_VERSION,
        "artifact": artifact,
        "source_url": url or "",
        "index_url": "",
        "scan_time": scan_time,
        "artifact_note": note,
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
    scan_time = data.get("scan_time")
    source_url = data.get("source_url")
    note = data.get("artifact_note")
    if not isinstance(scan_time, str) or not scan_time:
        return False
    if not isinstance(source_url, str) or not source_url:
        return False
    if not isinstance(note, str) or not note:
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
        nickname = row.get("nickname", "")
        if nickname is not None and not isinstance(nickname, str):
            return False
    return True


def _looks_like_csv(text):
    for line in text.lstrip("\ufeff").splitlines():
        if line.strip():
            folded = line.lower().replace(" ", "")
            return all(marker in folded for marker in _CSV_HEADER_MARKERS)
    return False


def _looks_like_html(text):
    folded = text[:2000].lower()
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
    fingerprint_index = mapping.get("fingerprint")
    if fingerprint_index is None:
        for index, cell in enumerate(header):
            if _header_key(cell) in ("rsaid", "rsa_id", "fingerprint"):
                fingerprint_index = index
                break
    group_index = mapping.get("group")
    if fingerprint_index is None or group_index is None:
        raise ValueError("TLS PQC CSV header has no fingerprint and group columns")
    cipher_index = mapping.get("ciphersuite")
    nickname_index = mapping.get("nickname")
    connected_index = None
    for index, cell in enumerate(header):
        if _header_key(cell) == "connected":
            connected_index = index
            break
    relays = {}
    for row in reader:
        if not any(cell.strip() for cell in row):
            continue
        fingerprint = normalize_fingerprint(_cell(row, fingerprint_index))
        if not fingerprint:
            continue
        connected = None
        if connected_index is not None and connected_index < len(row):
            flag = row[connected_index].strip().lower()
            if flag in ("true", "1", "yes"):
                connected = True
            elif flag in ("false", "0", "no"):
                connected = False
        _remember_row(
            relays,
            fingerprint,
            _cell(row, nickname_index),
            _cell(row, cipher_index),
            _cell(row, group_index),
            connected,
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
            relays,
            fingerprint,
            _cell(row, mapping.get("nickname")),
            _cell(row, mapping.get("ciphersuite")),
            _cell(row, mapping.get("group")),
            None,
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
    """Absolute URL of the newest dated scan linked from an index page."""
    found = []
    index_path = urlsplit(index_url or "").path.rstrip("/")
    for match in _HREF_RE.finditer(html or ""):
        href = match.group("href")
        absolute = urljoin(index_url or "", href)
        path = urlsplit(absolute).path.rstrip("/")
        date_match = re.search(r"/(\d{4}-\d{2}-\d{2})$", path)
        if not date_match:
            continue
        date = date_match.group(1)
        direct = index_path + "/" + date
        published = path.endswith("/tor-tls-pqc/" + date) or path == direct
        if not published:
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


def answer_for(status):
    if status == STATUS_SAW:
        return ANSWER_SAW
    if status == STATUS_OTHER:
        return ANSWER_OTHER
    if status == STATUS_NO_GROUP:
        return ANSWER_NO_GROUP
    return ANSWER_NOT_IN_SCAN


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
        if status == STATUS_SAW:
            saw = True
        elif status == STATUS_OTHER:
            saw = False
        else:
            saw = None
        relay["tls_pqc_status"] = status
        relay["tls_pqc_answer"] = answer_for(status)
        relay["tls_pqc_group"] = group
        relay["tls_pqc_cipher"] = cipher
        relay["tls_pqc_saw_x25519mlkem768"] = saw
        relay["tls_pqc_scan_time"] = scan_time
        relay["tls_pqc_scan_url"] = scan_url
        relay["tls_pqc_in_scan"] = status != STATUS_NOT_IN_SCAN
    return True


def _empty_counts():
    return {
        STATUS_SAW: 0,
        STATUS_OTHER: 0,
        STATUS_NO_GROUP: 0,
        STATUS_NOT_IN_SCAN: 0,
    }


def _role_metrics(prefix, counts):
    observed = counts[STATUS_SAW] + counts[STATUS_OTHER]
    total = observed + counts[STATUS_NO_GROUP] + counts[STATUS_NOT_IN_SCAN]
    return {
        "tls_pqc_%s_saw" % prefix: counts[STATUS_SAW],
        "tls_pqc_%s_other" % prefix: counts[STATUS_OTHER],
        "tls_pqc_%s_no_group" % prefix: counts[STATUS_NO_GROUP],
        "tls_pqc_%s_not_in_scan" % prefix: counts[STATUS_NOT_IN_SCAN],
        "tls_pqc_%s_observed" % prefix: observed,
        "tls_pqc_%s_total" % prefix: total,
    }


def empty_network_metrics():
    """Dashboard keys for a run with no usable scan. Counts are zero, not a percentage."""
    metrics = {
        "tls_pqc_available": False,
        "tls_pqc_scan_time": "",
        "tls_pqc_scan_url": "",
        "tls_pqc_index_url": "",
        "tls_pqc_artifact": "",
        "tls_pqc_artifact_note": "",
        "tls_pqc_saw": 0,
        "tls_pqc_other": 0,
        "tls_pqc_no_group": 0,
        "tls_pqc_not_in_scan": 0,
        "tls_pqc_observed": 0,
        "tls_pqc_in_scan": 0,
        "tls_pqc_consensus": 0,
        "tls_pqc_scan_rows": 0,
        "tls_pqc_observed_percentage": None,
        "tls_pqc_weight_saw_percentage": None,
        "tls_pqc_weight_other_percentage": None,
        "tls_pqc_weight_no_group_percentage": None,
        "tls_pqc_weight_not_in_scan_percentage": None,
        "tls_pqc_groups": [],
    }
    for prefix, _flag in _ROLE_FLAGS:
        metrics.update(_role_metrics(prefix, _empty_counts()))
    return metrics


def network_tls_metrics(relays, document):
    """Join the scan to the current consensus. Authority totals come from that join.

    Relays with the Authority flag are the denominator. The numerator is how
    many of those fingerprints the scan recorded as X25519MLKEM768. Authorities
    absent from the scan stay in ``tls_pqc_authority_not_in_scan``.
    """
    metrics = empty_network_metrics()
    if not validate_tls_pqc_document(document):
        return metrics
    counts = _empty_counts()
    weights = _empty_counts()
    roles = {prefix: _empty_counts() for prefix, _flag in _ROLE_FLAGS}
    groups = Counter()
    for relay in relays or []:
        status, group, _cipher = classify_scan_row(
            _lookup_row(document, relay.get("fingerprint")))
        counts[status] += 1
        weights[status] += _consensus_weight(relay)
        flags = relay.get("flags") or []
        for prefix, flag in _ROLE_FLAGS:
            if flag in flags:
                roles[prefix][status] += 1
        if status == STATUS_SAW:
            groups[PQC_GROUP] += 1
        elif status == STATUS_OTHER and group:
            groups[group] += 1
    observed = counts[STATUS_SAW] + counts[STATUS_OTHER]
    in_scan = observed + counts[STATUS_NO_GROUP]
    consensus = in_scan + counts[STATUS_NOT_IN_SCAN]
    total_weight = sum(weights.values())
    metrics.update({
        "tls_pqc_available": True,
        "tls_pqc_scan_time": document.get("scan_time") or "",
        "tls_pqc_scan_url": document.get("source_url") or "",
        "tls_pqc_index_url": document.get("index_url") or "",
        "tls_pqc_artifact": document.get("artifact") or "",
        "tls_pqc_artifact_note": document.get("artifact_note") or "",
        "tls_pqc_saw": counts[STATUS_SAW],
        "tls_pqc_other": counts[STATUS_OTHER],
        "tls_pqc_no_group": counts[STATUS_NO_GROUP],
        "tls_pqc_not_in_scan": counts[STATUS_NOT_IN_SCAN],
        "tls_pqc_observed": observed,
        "tls_pqc_in_scan": in_scan,
        "tls_pqc_consensus": consensus,
        "tls_pqc_scan_rows": len(document.get("relays") or {}),
        "tls_pqc_observed_percentage": _percent(counts[STATUS_SAW], observed),
        "tls_pqc_weight_saw_percentage": _percent(weights[STATUS_SAW], total_weight),
        "tls_pqc_weight_other_percentage": _percent(weights[STATUS_OTHER], total_weight),
        "tls_pqc_weight_no_group_percentage": _percent(weights[STATUS_NO_GROUP], total_weight),
        "tls_pqc_weight_not_in_scan_percentage": _percent(
            weights[STATUS_NOT_IN_SCAN], total_weight),
        "tls_pqc_groups": [
            {"name": name, "count": count} for name, count in groups.most_common()
        ],
    })
    for prefix, _flag in _ROLE_FLAGS:
        metrics.update(_role_metrics(prefix, roles[prefix]))
    return metrics


def _operator_entry(relay):
    return {
        "nickname": relay.get("nickname") or relay.get("fingerprint") or "",
        "fingerprint": relay.get("fingerprint") or "",
        "group": relay.get("tls_pqc_group") or "",
        "cipher": relay.get("tls_pqc_cipher") or "",
    }


def _cap_entries(relays):
    ordered = sorted(
        relays,
        key=lambda relay: (
            (relay.get("nickname") or "").lower(),
            relay.get("fingerprint") or "",
        ),
    )
    shown = [_operator_entry(relay) for relay in ordered[:_OPERATOR_LIST_LIMIT]]
    return shown, max(0, len(ordered) - len(shown))


def operator_tls_summary(members):
    """Per-operator counts from relay fields set by ``attach_tls_pqc_to_relays``.

    Relays with no scan fields are left out of the counts. They are not
    reported as "not in this scan": that phrase is only for a fingerprint the
    loaded scan did not contain.
    """
    tagged = [relay for relay in members or [] if relay.get("tls_pqc_status")]
    if not tagged:
        return {"available": False}
    buckets = {
        STATUS_SAW: [],
        STATUS_OTHER: [],
        STATUS_NO_GROUP: [],
        STATUS_NOT_IN_SCAN: [],
    }
    weights = _empty_counts()
    for relay in tagged:
        status = relay.get("tls_pqc_status")
        if status not in buckets:
            continue
        buckets[status].append(relay)
        weights[status] += _consensus_weight(relay)
    observed_weight = weights[STATUS_SAW] + weights[STATUS_OTHER]
    total_weight = observed_weight + weights[STATUS_NO_GROUP] + weights[STATUS_NOT_IN_SCAN]
    observed = len(buckets[STATUS_SAW]) + len(buckets[STATUS_OTHER])
    other_relays, other_more = _cap_entries(buckets[STATUS_OTHER])
    no_group_relays, no_group_more = _cap_entries(buckets[STATUS_NO_GROUP])
    absent_relays, absent_more = _cap_entries(buckets[STATUS_NOT_IN_SCAN])
    saw = len(buckets[STATUS_SAW])
    other = len(buckets[STATUS_OTHER])
    return {
        "available": True,
        "scan_time": tagged[0].get("tls_pqc_scan_time") or "",
        "scan_url": tagged[0].get("tls_pqc_scan_url") or "",
        "saw": saw,
        "other": other,
        "no_group": len(buckets[STATUS_NO_GROUP]),
        "not_in_scan": len(buckets[STATUS_NOT_IN_SCAN]),
        "observed": observed,
        "total": len(tagged),
        "observed_percent": _percent(saw, observed),
        "weight_observed_percent": _percent(weights[STATUS_SAW], observed_weight),
        "weight_share_percent": _percent(weights[STATUS_SAW], total_weight),
        "other_relays": other_relays,
        "other_more": other_more,
        "no_group_relays": no_group_relays,
        "no_group_more": no_group_more,
        "absent_relays": absent_relays,
        "absent_more": absent_more,
        "guidance_text": GUIDANCE_TEXT if other else "",
        "guidance_url": LIBRESSL_ISSUE_URL if other else "",
    }
