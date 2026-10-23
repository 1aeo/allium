"""Margot TLS scan parsing and PQC display. Fixtures only; no live Tor probe."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from allium.lib import workers
from allium.lib.page_context import StandardTemplateContexts
from allium.lib.page_writer import write_misc, write_pages_by_key, write_relay_info
from allium.lib.relays import Relays
from allium.lib.tls_pqc import (
    ANSWER_NOT_IN_SCAN,
    ANSWER_OTHER,
    ANSWER_SAW,
    PQC_GROUP,
    attach_tls_pqc_to_relays,
    latest_scan_url,
    load_tls_pqc_scan,
    network_tls_metrics,
    operator_tls_summary,
    parse_csv_scan,
    parse_html_scan,
    parse_scan_payload,
    validate_tls_pqc_document,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tls_pqc"
REPO = Path(__file__).resolve().parents[3]
PUBLISHED = "2026-10-16 12:00:00"
SAW = "000004ACBB9D29BCBA17256BB35928DDBFC8ABA9"
OTHER = "000C71961332DDA7B6AAB2A88FF07B0C37650F70"
SECP = "00240ECB2B535AA4C1E1874D744DFA6AF2E5E941"
EMPTY = "E25CF3E2BEEB422B7F94CFA29D5B62D5109C5D60"
DUP = "A" * 40
KEEP = "B" * 40
ABSENT = "F" * 40
INDEX = "https://ahf.me/tor-tls-pqc/"
SCAN_URL = "https://ahf.me/tor-tls-pqc/2026-06-18/"


def _read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def _relay(fingerprint, nickname, flags, weight, version="0.4.8.17"):
    return {
        "nickname": nickname,
        "fingerprint": fingerprint,
        "running": True,
        "observed_bandwidth": 1_000_000,
        "consensus_weight": weight,
        "flags": flags,
        "first_seen": "2024-01-01 00:00:00",
        "last_seen": PUBLISHED,
        "last_restarted": "2026-10-01 00:00:00",
        "platform": "Tor %s on Linux" % version,
        "version": version,
        "version_status": "recommended",
        "recommended_version": True,
        "country": "de",
        "country_name": "Germany",
        "as": "AS100",
        "as_name": "Example Networks",
        "or_addresses": ["192.0.2.1:9001"],
        "contact": "ops@example.org",
    }


def test_html_fixture_matches_the_published_table():
    document = parse_html_scan(_read("scan.html"), SCAN_URL)
    assert validate_tls_pqc_document(document)
    assert document["artifact"] == "html"
    assert document["scan_time"] == "2026-06-18"
    assert "HTML tables" in document["artifact_note"]
    assert "cipher_suites.csv" in document["artifact_note"]
    assert document["relays"][SAW]["key_exchange_group"] == PQC_GROUP
    assert document["relays"][SAW]["cipher_suite"] == "TLS13_AES_256_GCM_SHA384"
    assert document["relays"][SAW]["nickname"] == "lisdex"
    assert document["relays"][OTHER]["key_exchange_group"] == "X25519"
    # Lowercase fingerprint and a leading $ still join on the uppercase identity.
    assert document["relays"][SECP]["key_exchange_group"] == "secp256r1"
    assert document["relays"][SECP]["nickname"] == "Amp & Co"
    assert document["relays"][EMPTY]["key_exchange_group"] == ""
    assert document["relays"][EMPTY]["connected"] is False
    # An empty first row is replaced when a later row records a group.
    assert document["relays"][DUP]["key_exchange_group"] == PQC_GROUP
    # The first negotiated group is kept when a later row disagrees.
    assert document["relays"][KEEP]["key_exchange_group"] == "X25519"
    assert "short" not in "".join(document["relays"])
    assert len(document["relays"]) == 6


def test_csv_fixture_is_the_margot_scanner_file():
    document = parse_csv_scan(_read("cipher_suites.csv"), SCAN_URL + "cipher_suites.csv")
    assert document["artifact"] == "csv"
    assert document["scan_time"] == "2026-06-18"
    assert "tls-ciphers" in document["artifact_note"]
    relays = document["relays"]
    assert relays[SAW]["key_exchange_group"] == PQC_GROUP
    assert relays[SAW]["connected"] is True
    assert relays["1" * 40]["key_exchange_group"] == "X25519"
    # connected=false is in the file and has no negotiated group.
    assert relays["2" * 40]["connected"] is False
    assert relays["2" * 40]["key_exchange_group"] == ""
    assert relays["2" * 40]["cipher_suite"] == ""
    assert relays["3" * 40]["key_exchange_group"] == "secp256r1"
    assert "[2001:db8::10]:9001" not in relays["3" * 40]["key_exchange_group"]


def test_index_selects_the_newest_dated_scan_and_skips_other_pages():
    latest = latest_scan_url(_read("index.html"), INDEX)
    assert latest == SCAN_URL


def test_index_then_html_and_a_direct_csv_both_parse():
    pages = {
        INDEX: _read("index.html").encode("utf-8"),
        SCAN_URL: _read("scan.html").encode("utf-8"),
    }
    seen = []

    def fetch_body(url):
        seen.append(url)
        return pages[url]

    document = load_tls_pqc_scan(fetch_body, INDEX)
    assert seen == [INDEX, SCAN_URL]
    assert document["index_url"] == INDEX
    assert document["source_url"] == SCAN_URL
    assert document["relays"][SAW]["key_exchange_group"] == PQC_GROUP

    direct = load_tls_pqc_scan(
        lambda url: _read("cipher_suites.csv").encode("utf-8"),
        "https://example.invalid/cipher_suites.csv",
    )
    assert direct["artifact"] == "csv"
    assert direct["scan_time"] == "unknown"
    assert direct["relays"][SAW]["connected"] is True


def test_unrecognized_payload_is_rejected_and_an_index_without_dates_is_too():
    with pytest.raises(ValueError):
        parse_scan_payload(b'{"relays": []}', INDEX)
    with pytest.raises(ValueError):
        load_tls_pqc_scan(lambda url: b"<html><title>empty</title></html>", INDEX)


def test_missing_fingerprint_is_not_in_this_scan_and_version_is_ignored():
    document = parse_html_scan(_read("scan.html"), SCAN_URL)
    relays = [
        _relay(SAW, "lisdex", ["Guard", "Running"], 100, version="0.4.7.7"),
        _relay(OTHER, "oldtls", ["Exit", "Running"], 50, version="0.4.8.17"),
        _relay(EMPTY, "nogroup", ["Running"], 25, version="0.4.9.1"),
        _relay(ABSENT, "authabsent", ["Authority", "Running"], 10, version="0.4.9.3"),
        _relay(SECP, "authsecp", ["Authority", "Guard", "Running"], 5, version="0.4.8.10"),
        _relay(DUP, "hybridauth", ["Authority", "Fast", "Running"], 40, version="0.4.8.1"),
    ]
    assert attach_tls_pqc_to_relays(relays, document) is True
    by_fp = {relay["fingerprint"]: relay for relay in relays}
    assert by_fp[SAW]["tls_pqc_answer"] == ANSWER_SAW
    assert by_fp[SAW]["tls_pqc_saw_x25519mlkem768"] is True
    # 0.4.8.17 negotiated X25519. The version string does not override the scan.
    assert by_fp[OTHER]["tls_pqc_answer"] == ANSWER_OTHER
    assert by_fp[OTHER]["tls_pqc_group"] == "X25519"
    assert by_fp[OTHER]["tls_pqc_saw_x25519mlkem768"] is False
    assert by_fp[EMPTY]["tls_pqc_status"] == "no_group"
    assert by_fp[EMPTY]["tls_pqc_saw_x25519mlkem768"] is None
    assert by_fp[EMPTY]["tls_pqc_in_scan"] is True
    # A new Tor version that the scan did not list is still absent.
    assert by_fp[ABSENT]["tls_pqc_answer"] == ANSWER_NOT_IN_SCAN
    assert by_fp[ABSENT]["tls_pqc_saw_x25519mlkem768"] is None
    assert by_fp[ABSENT]["tls_pqc_in_scan"] is False
    assert by_fp[ABSENT]["version"] == "0.4.9.3"

    metrics = network_tls_metrics(relays, document)
    assert metrics["tls_pqc_available"] is True
    assert metrics["tls_pqc_saw"] == 2
    assert metrics["tls_pqc_other"] == 2
    assert metrics["tls_pqc_no_group"] == 1
    assert metrics["tls_pqc_not_in_scan"] == 1
    assert metrics["tls_pqc_observed"] == 4
    assert metrics["tls_pqc_observed_percentage"] == 50.0
    # 1 of 3 directory authorities, from the Authority flag joined to the scan.
    assert metrics["tls_pqc_authority_total"] == 3
    assert metrics["tls_pqc_authority_saw"] == 1
    assert metrics["tls_pqc_authority_other"] == 1
    assert metrics["tls_pqc_authority_not_in_scan"] == 1
    assert metrics["tls_pqc_guard_saw"] == 1
    assert metrics["tls_pqc_guard_observed"] == 2
    assert metrics["tls_pqc_exit_saw"] == 0
    assert metrics["tls_pqc_exit_other"] == 1
    # Weights: saw 100+40, other 50+5, no_group 25, absent 10. Total 230.
    assert metrics["tls_pqc_weight_saw_percentage"] == 60.9
    assert metrics["tls_pqc_weight_not_in_scan_percentage"] == 4.3
    names = [group["name"] for group in metrics["tls_pqc_groups"]]
    assert names[0] == PQC_GROUP
    assert "X25519" in names
    assert "secp256r1" in names

    # A different authority set changes the denominator. Nothing is fixed at 9.
    four = [
        _relay("1" * 40, "a1", ["Authority"], 1),
        _relay("2" * 40, "a2", ["Authority"], 1),
        _relay("3" * 40, "a3", ["Authority"], 1),
        _relay("4" * 40, "a4", ["Authority"], 1),
    ]
    scan = parse_csv_scan(_read("cipher_suites.csv"), SCAN_URL + "cipher_suites.csv")
    joined = network_tls_metrics(four, scan)
    assert joined["tls_pqc_authority_total"] == 4
    assert joined["tls_pqc_authority_saw"] == 0
    assert joined["tls_pqc_authority_not_in_scan"] == 1
    assert (joined["tls_pqc_authority_saw"], joined["tls_pqc_authority_total"]) != (5, 9)


def test_operator_summary_separates_other_groups_from_absence():
    document = parse_html_scan(_read("scan.html"), SCAN_URL)
    members = [
        _relay(SAW, "lisdex", ["Guard"], 80),
        _relay(OTHER, "oldtls", ["Exit"], 20),
        _relay(ABSENT, "missing", ["Running"], 20),
    ]
    attach_tls_pqc_to_relays(members, document)
    summary = operator_tls_summary(members)
    assert summary["available"] is True
    assert summary["saw"] == 1
    assert summary["observed"] == 2
    assert summary["not_in_scan"] == 1
    assert summary["absent_relays"][0]["nickname"] == "missing"
    assert summary["other_relays"][0]["group"] == "X25519"
    assert summary["other_relays"][0]["nickname"] == "oldtls"
    assert "OpenSSL 3.5.0" in summary["guidance_text"]
    assert "LibreSSL" in summary["guidance_text"]
    assert summary["guidance_url"].endswith("/issues/41300")
    assert summary["weight_observed_percent"] == 80.0
    assert operator_tls_summary([{"nickname": "untagged"}]) == {"available": False}


def test_dashboard_template_does_not_hardcode_directory_authority_counts():
    text = (REPO / "allium" / "templates" / "network-health-dashboard.html").read_text(encoding="utf-8")
    start = text.index('id="tls-pqc"')
    card = text[start:text.index("FOURTH ROW", start)]
    row = text[text.rindex('<div class="ribbon-row">', 0, start):start]
    assert "grid-template-columns: 1fr" not in row
    assert "5 of 9" not in card
    assert "5/9" not in card
    assert "tls_pqc_authority_saw" in card
    assert "tls_pqc_authority_total" in card
    assert "tls_pqc_weight_saw_percentage_formatted" in card
    assert "not in this scan" in card
    assert "tls_pqc_groups" not in card
    assert "Guards saw" not in card


def test_fresh_cache_skips_the_network_and_a_timeout_uses_the_cache():
    document = parse_html_scan(_read("scan.html"), SCAN_URL)
    workers._save_cache("tls_pqc", document)
    with patch.object(workers, "_fetch_url_with_total_timeout",
                      side_effect=AssertionError("network")) as called:
        loaded = workers.fetch_tls_pqc(INDEX, progress_logger=None)
    assert loaded["relays"][SAW]["key_exchange_group"] == PQC_GROUP
    assert called.call_count == 0

    path = Path(workers.CACHE_DIR) / "tls_pqc.json"
    old = os.path.getmtime(str(path)) - (25 * 3600)
    os.utime(str(path), (old, old))
    with patch.object(workers, "_fetch_url_with_total_timeout",
                      side_effect=workers.TotalTimeoutError("total timeout")) as fetch:
        refreshed = workers.fetch_tls_pqc(INDEX, progress_logger=None)
    assert refreshed["scan_time"] == "2026-06-18"
    assert fetch.call_count == 1
    assert fetch.call_args.args[1] == workers.TLS_PQC_TIMEOUT_FRESH_CACHE


def test_pages_show_the_scan_result_and_absence(tmp_path):
    document = parse_html_scan(_read("scan.html"), SCAN_URL)
    details = {
        "version": "8.0",
        "relays_published": PUBLISHED,
        "relays": [
            _relay(SAW, "lisdex", ["Guard", "Running", "Valid"], 100, version="0.4.7.7"),
            _relay(OTHER, "oldtls", ["Exit", "Running", "Valid"], 50, version="0.4.8.17"),
            _relay(ABSENT, "dirauth", ["Authority", "Running", "Valid"], 10, version="0.4.9.3"),
        ],
    }
    for relay in details["relays"]:
        relay["contact"] = "ops@example.org"
    relay_set = Relays(
        output_dir=str(tmp_path),
        onionoo_url="https://onionoo.example.invalid/details",
        relay_data=details,
        filter_downtime_days=7,
        mp_workers=0,
    )
    relay_set.enrich_with_api_data(tls_pqc_data=document)
    health = relay_set.json["network_health"]
    assert health["tls_pqc_authority_saw"] == 0
    assert health["tls_pqc_authority_total"] == 1
    assert health["tls_pqc_authority_not_in_scan"] == 1
    assert health["tls_pqc_saw"] == 1
    assert health["tls_pqc_other"] == 1

    page_ctx = StandardTemplateContexts(relay_set).get_index_page_context(
        "Network Health Dashboard", relay_set.timestamp)
    write_misc(relay_set, "network-health-dashboard.html", "network-health.html", page_ctx=page_ctx)
    dashboard = (tmp_path / "network-health.html").read_text(encoding="utf-8")
    assert "X25519MLKEM768 consensus weight" in dashboard
    assert "62.5%" in dashboard
    assert "0 of 1" in dashboard
    assert "not in this scan" in dashboard
    assert "5 of 9" not in dashboard
    assert "2026-06-18" in dashboard
    assert ANSWER_SAW in dashboard or "X25519MLKEM768" in dashboard

    write_relay_info(relay_set)
    saw_page = (tmp_path / "relay" / SAW / "index.html").read_text(encoding="utf-8")
    other_page = (tmp_path / "relay" / OTHER / "index.html").read_text(encoding="utf-8")
    absent_page = (tmp_path / "relay" / ABSENT / "index.html").read_text(encoding="utf-8")
    assert ANSWER_SAW in saw_page
    assert "scan 2026-06-18" in saw_page
    assert ANSWER_OTHER in other_page
    assert "X25519" in other_page
    assert "OpenSSL 3.5.0" in other_page
    assert ANSWER_NOT_IN_SCAN in absent_page
    assert "0.4.9.3" in absent_page
    assert ANSWER_SAW not in absent_page

    write_pages_by_key(relay_set, "contact")
    contact_pages = list((tmp_path / "contact").rglob("index.html"))
    assert contact_pages
    operator = ""
    for path in contact_pages:
        text = path.read_text(encoding="utf-8")
        if "oldtls" in text and "lisdex" in text:
            operator = text
            break
    assert operator
    assert "1 of 2 relays with a negotiated group saw X25519MLKEM768" in operator
    assert "not in this scan" in operator
    assert "oldtls" in operator
    assert "X25519" in operator
