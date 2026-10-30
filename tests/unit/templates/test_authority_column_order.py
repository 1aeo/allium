"""Per-authority columns run from most important on the left to least on the right.

Authority and BW Scan are context for the row. Valid comes before Running.
Cons Wt sits after v4 and v6 and before Flags. Exit and MiddleOnly are names
in Flags, not their own columns.
"""

import re

from allium.lib import page_writer
from allium.lib.consensus.collector_fetcher import AUTHORITIES_BY_NAME
from allium.lib.consensus.consensus_evaluation import format_relay_consensus_evaluation
from allium.lib.consensus.flag_thresholds import BW_SOURCE_MEASURED, SECONDS_PER_DAY
from allium.lib.relays import Relays

PUBLISHED = "2026-10-11 12:00:00"
RELAY_V6 = "A" * 40
RELAY_V4 = "B" * 40

# Visible header text. Authority and BW Scan are context; the rest run from
# most important to least. v6 is omitted when the relay has no IPv6 ORPort.
HEADER_ORDER = [
    "Authority",
    "BW Scan (Authority)",
    "Valid",
    "Running",
    "v4",
    "v6",
    "Cons Wt (Authority)",
    "Flags",
    "Stable MTBF (M|T)",
    "Stable Uptime (Relay|T)",
    "Guard WFU (M|T)",
    "Guard TK (M|T)",
    "Guard BW (BW|Threshold)",
    "Fast (BW|T)",
    "Desc Published",
]

# One marker per body cell, in the same order as HEADER_ORDER. Each marker
# occurs once in the template row, so a header/body mismatch fails this list.
ROW_MARKERS = [
    "authority_page_fps",
    "vote.is_bw_authority",
    "'Valid' in vote.flags",
    'headers="col-running"',
    "vote.ipv4_reachable",
    "vote.ipv6_cell",
    'headers="col-cons-wt"',
    'headers="col-flags"',
    "vote.stable_mtbf_display",
    "vote.stable_uptime_threshold",
    "vote.wfu is not none",
    "vote.tk is not none",
    "vote.guard_bw_guarantee_display",
    'headers="col-fast"',
    'headers="col-desc-published"',
]


def _template_table():
    """The per-authority table source, comments removed."""
    source = (page_writer.ENV.loader.get_source(page_writer.ENV, "relay-info.html")[0])
    start = source.index('id="authority-votes"')
    table = source[source.index("<table", start):source.index("</table>", start)]
    return re.sub(r"\{#.*?#\}", "", table, flags=re.S)


def _header_labels(table):
    """Visible header text, in source or rendered order."""
    thead = table[table.index("<thead"):table.index("</thead>")]
    labels = []
    for body in re.findall(r"<th\b[^>]*>(.*?)</th>", thead, flags=re.S):
        text = re.sub(r"<[^>]+>", " ", body)
        text = re.sub(r"\{%.*?%\}", " ", text, flags=re.S)
        labels.append(" ".join(text.split()))
    return labels


def _section(fragment, tag):
    return fragment[fragment.index(f"<{tag}"):fragment.index(f"</{tag}>")]


def test_template_orders_headers_and_cells_together():
    """Header labels and the matching body cells share one left-to-right order."""
    table = _template_table()
    assert _header_labels(table) == HEADER_ORDER

    row = _section(table, "tbody")
    positions = [row.index(marker) for marker in ROW_MARKERS]
    assert positions == sorted(positions)
    assert len(positions) == len(set(positions))

    # v4, v6, Cons Wt, Flags stay in that order, including when v6 is conditional.
    labels = _header_labels(table)
    assert labels.index("v6") == labels.index("v4") + 1
    assert labels.index("Cons Wt (Authority)") == labels.index("v6") + 1
    assert labels.index("Flags") == labels.index("Cons Wt (Authority)") + 1
    assert labels[:4] == ["Authority", "BW Scan (Authority)", "Valid", "Running"]
    assert labels[-1] == "Desc Published"
    assert "Exit" not in labels
    assert "MiddleOnly" not in labels


def _relay(fingerprint, nickname):
    return {
        "nickname": nickname,
        "fingerprint": fingerprint,
        "running": True,
        "observed_bandwidth": 1_000_000,
        "consensus_weight": 100,
        "flags": ["Running", "Valid", "Fast", "Stable"],
        "first_seen": "2024-01-01 00:00:00",
        "last_seen": PUBLISHED,
        "last_restarted": "2026-10-01 00:00:00",
        "platform": "Tor 0.4.8.10 on Linux",
        "country": "de",
        "country_name": "Germany",
        "as": "AS100",
        "as_name": "Example Networks",
        "or_addresses": ["192.0.2.1:9001", "[2001:db8::1]:9001"],
        "contact": f"{nickname} <{nickname}@example.org>",
        "effective_family": [fingerprint],
    }


def _vote(name, **extra):
    vote = {
        "authority": name,
        "fingerprint": AUTHORITIES_BY_NAME[name],
        "voted": True,
        "flags": ["Running", "Valid", "Fast", "Stable"],
        "is_bw_authority": False,
        "ipv4_reachable": True,
        "bandwidth": 100,
        "measured": 80,
        "wfu": 0.99,
        "tk": 20 * SECONDS_PER_DAY,
        "mtbf": 20 * SECONDS_PER_DAY,
        "descriptor_published": "2026-10-11 11:00:00",
    }
    vote.update(extra)
    return vote


def _evaluation(votes, ipv6=False):
    evaluation = {
        "fingerprint": RELAY_V6 if ipv6 else RELAY_V4,
        "in_consensus": True,
        "vote_count": sum(1 for vote in votes if vote["voted"]),
        "total_authorities": len(votes),
        "authority_votes": votes,
        "reachability": {"ipv4_reachable_count": sum(1 for vote in votes if vote["voted"])},
        "flag_eligibility": {
            "fast": {"details": [{
                "authority": vote["authority"],
                "speed_value": 80_000,
                "speed_source": BW_SOURCE_MEASURED,
                "eligible": True,
            } for vote in votes if vote["voted"]]},
            "guard": {"details": [{
                "authority": vote["authority"],
                "bw_met": False,
            } for vote in votes if vote["voted"]]},
        },
    }
    if ipv6:
        evaluation["reachability"].update({
            "ipv6_state": "ok",
            "ipv6_reachable_count": 1,
            "ipv6_tested_count": 2,
            "ipv6_reachable_authorities": ["moria1"],
        })
    return evaluation


def _thresholds(names):
    return {name: {
        "fast-speed": 102000,
        "guard-wfu": 0.98,
        "guard-tk": 691200,
        "stable-uptime": 500000,
        "stable-mtbf": 500000,
        "guard-bw-inc-exits": 25000000,
        "guard-bw-exc-exits": 26000000,
    } for name in names}


def _render(tmp_path):
    """Two relay pages: one with an IPv6 column, one without."""
    moria = _vote(
        "moria1",
        flags=["Running", "Valid", "Stable", "StaleDesc"],
        is_bw_authority=True,
        ipv6_reachable=True,
        tests_ipv6=True,
        measured=50,
        descriptor_published="2020-01-01 00:00:00",
    )
    bastet = _vote("bastet", voted=False, flags=[], ipv4_reachable=False, measured=None, bandwidth=None)
    longclaw = _vote(
        "longclaw", tests_ipv6=False, ipv6_reachable=None,
        flags=["Running", "Valid", "Exit", "MiddleOnly"],
    )
    names = ["moria1", "bastet", "longclaw"]
    details = {
        "version": "8.0",
        "relays_published": PUBLISHED,
        "relays": [_relay(RELAY_V6, "withv6"), _relay(RELAY_V4, "v4only")],
    }
    relay_set = Relays(
        output_dir=str(tmp_path),
        onionoo_url="https://onionoo.example.invalid/details",
        relay_data=details,
        filter_downtime_days=7,
        mp_workers=0,
    )
    relay_set.enrich_with_api_data()
    by_fp = {relay["fingerprint"]: relay for relay in relay_set.json["relays"]}
    by_fp[RELAY_V6]["consensus_evaluation"] = format_relay_consensus_evaluation(
        _evaluation([moria, bastet, longclaw], ipv6=True),
        _thresholds(names),
        current_flags=["Running", "Valid", "Fast", "Stable"],
        observed_bandwidth=1_000_000,
        relay_uptime=10 * SECONDS_PER_DAY,
    )
    by_fp[RELAY_V4]["consensus_evaluation"] = format_relay_consensus_evaluation(
        _evaluation([_vote("moria1"), _vote("bastet", voted=False, flags=[], ipv4_reachable=False)], ipv6=False),
        _thresholds(["moria1", "bastet"]),
        current_flags=["Running", "Valid", "Fast", "Stable"],
        observed_bandwidth=1_000_000,
        relay_uptime=10 * SECONDS_PER_DAY,
    )
    page_writer.write_relay_info(relay_set)
    return tmp_path / "relay"


def _page_table(relay_dir, fingerprint):
    html = (relay_dir / fingerprint / "index.html").read_text()
    start = html.index('id="authority-votes"')
    return html[html.index("<table", start):html.index("</table>", start)]


def _rows(table):
    tbody = _section(table, "tbody")
    rows = []
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", tbody, flags=re.S):
        cells = []
        for attrs, body in re.findall(r"<td\b([^>]*)>(.*?)</td>", row, flags=re.S):
            text = " ".join(re.sub(r"<[^>]+>", " ", body).split())
            header = re.search(r'headers="([^"]+)"', attrs)
            cells.append((text, header.group(1) if header else None))
        rows.append(cells)
    return rows


def _ids(table):
    thead = _section(table, "thead")
    found = []
    for attrs in re.findall(r"<th\b([^>]*)>", thead):
        match = re.search(r'id="([^"]+)"', attrs)
        found.append(match.group(1) if match else None)
    return found


def test_rendered_pages_keep_header_and_body_aligned(tmp_path):
    """Rendered rows have one cell per header, and deep-link ids land on that column."""
    relay_dir = _render(tmp_path)

    with_v6 = _page_table(relay_dir, RELAY_V6)
    assert _header_labels(with_v6) == HEADER_ORDER
    assert "most important on the left" in (relay_dir / RELAY_V6 / "index.html").read_text()
    rows = _rows(with_v6)
    assert rows
    assert all(len(row) == len(HEADER_ORDER) for row in rows)

    header_ids = _ids(with_v6)
    for row in rows:
        assert [header for _text, header in row] == header_ids

    moria = next(row for row in rows if "moria1" in row[0][0])
    labels = _header_labels(with_v6)
    assert "[Stale]" in moria[labels.index("Desc Published")][0]
    assert "N/T" in next(row for row in rows if "longclaw" in row[0][0])[labels.index("v6")][0]
    assert moria[labels.index("Cons Wt (Authority)")][0].endswith("(M)")
    running = labels.index("Running")
    valid = labels.index("Valid")
    assert valid == running - 1
    assert moria[valid][0] == "Yes"
    assert moria[running][0] == "Yes"
    bastet = next(row for row in rows if row[0][0].startswith("bastet"))
    assert bastet[running][0] == "No"
    assert bastet[valid][0] == "—"
    flags = next(row for row in rows if "longclaw" in row[0][0])[labels.index("Flags")][0]
    assert "Exit" in flags and "MiddleOnly" in flags
    assert "al-status-danger" in next(
        cell for cell in re.findall(r"<td\b[^>]*>(.*?)</td>", 
            _section(with_v6, "tbody"), flags=re.S)
        if "MiddleOnly" in cell)

    v4_only = _page_table(relay_dir, RELAY_V4)
    without_v6 = [label for label in HEADER_ORDER if label != "v6"]
    assert _header_labels(v4_only) == without_v6
    v4_rows = _rows(v4_only)
    assert all(len(row) == len(without_v6) for row in v4_rows)
    assert [header for _text, header in v4_rows[0]] == _ids(v4_only)
    assert _header_labels(v4_only).index("Cons Wt (Authority)") == _header_labels(v4_only).index("v4") + 1
