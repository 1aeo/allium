"""Relay pages for a wrong DNS answer that another probe also got right.

The report status is wrong_ip. The page must say DNS Returned Wrong IP,
list every wrong address, and keep that answer when some probes succeeded.
"""

import pytest

from allium.lib import page_writer
from allium.lib.relays import Relays

PUBLISHED = "2026-11-03 00:25:58"
MIXED = "42F8E7CE864478CA292E9EA05DC11481C293F8ED"
HEALTHY = "A" * 40
FAILED = "B" * 40
LEGACY = "C" * 40
RECOVERED = "D" * 40
EXIT_FLAGS = ["Exit", "Fast", "Running", "Valid"]


def _relay(fingerprint, nickname):
    return {
        "nickname": nickname, "fingerprint": fingerprint, "running": True, "flags": EXIT_FLAGS,
        "observed_bandwidth": 1_000_000, "consensus_weight": 100, "exit_probability": 0.1,
        "first_seen": "2024-01-01 00:00:00", "last_seen": PUBLISHED, "last_restarted": "2026-10-01 00:00:00",
        "platform": "Tor 0.4.8.10 on Linux", "country": "de", "country_name": "Germany",
        "as": "AS100", "as_name": "Example Networks", "or_addresses": ["192.0.2.1:9001"],
        "contact": f"{nickname} <{nickname}@example.org>",
    }


def _instance(status, resolved_ip=None, total_ms=None):
    detail = {"status": status}
    if resolved_ip:
        detail["resolved_ip"] = resolved_ip
        detail["expected_ip"] = "64.65.4.1"
    if total_ms is not None:
        detail["timing"] = {"total_ms": total_ms}
    return detail


def _result(fingerprint, status, per_instance, resolved_ip=None, improved=False, success=0, total=4):
    result = {
        "exit_fingerprint": fingerprint,
        "status": status,
        "expected_ip": "64.65.4.1",
        "cv": {
            "instances_success": success,
            "instances_total": total,
            "improved": improved,
            "per_instance": per_instance,
        },
    }
    if resolved_ip:
        result["resolved_ip"] = resolved_ip
    if status == "success":
        result["timing"] = {"total_ms": 1000}
    return result


def _pages(tmp_path):
    details = {
        "version": "8.0",
        "relays_published": PUBLISHED,
        "relays": [
            _relay(MIXED, "ibibUNC2"),
            _relay(HEALTHY, "healthy"),
            _relay(FAILED, "lookupfail"),
            _relay(LEGACY, "legacywrong"),
            _relay(RECOVERED, "recovered"),
        ],
    }
    report = {
        "metadata": {"timestamp": "2026-11-03T08:25:58Z", "tested_relays": 5, "dns_success": 2},
        "results": [
            _result(MIXED, "wrong_ip", {
                "cv1_w1": _instance("wrong_ip", "23.202.88.27", 21911),
                "cv2_w1": _instance("success", "64.65.4.1", 19101),
                "cv3_w1": _instance("wrong_ip", "2.18.188.209", 8894),
                "cv4_w1": _instance("success", "64.65.4.1", 12562),
            }, resolved_ip="23.202.88.27", improved=True, success=2, total=4),
            _result(HEALTHY, "success", {
                "cv1_w1": _instance("success", "64.65.4.1", 900),
                "cv2_w1": _instance("success", "64.65.4.1", 900),
                "cv3_w1": _instance("success", "64.65.4.1", 900),
                "cv4_w1": _instance("success", "64.65.4.1", 900),
            }, resolved_ip="64.65.4.1", success=4, total=4),
            _result(FAILED, "dns_fail", {
                "cv1_w1": _instance("dns_fail"),
                "cv2_w1": _instance("timeout"),
            }, success=0, total=2),
            _result(LEGACY, "dns_wrong_ip", {
                "cv1_w1": _instance("wrong_ip", "198.51.100.8", 1000),
            }, resolved_ip="198.51.100.8", success=0, total=1),
            _result(RECOVERED, "success", {
                "cv1_w1": _instance("timeout"),
                "cv2_w1": _instance("success", "64.65.4.1", 800),
            }, resolved_ip="64.65.4.1", improved=True, success=1, total=2),
        ],
    }
    relay_set = Relays(
        output_dir=str(tmp_path), onionoo_url="https://onionoo.example.invalid/details",
        relay_data=details, filter_downtime_days=7, mp_workers=0,
    )
    relay_set.enrich_with_api_data(exit_dns_health_data=report)
    page_writer.write_relay_info(relay_set)
    return {fp: open(f"{relay_set.output_dir}/relay/{fp}/index.html").read()
            for fp in (MIXED, HEALTHY, FAILED, LEGACY, RECOVERED)}


@pytest.fixture(scope="module")
def pages(tmp_path_factory):
    return _pages(tmp_path_factory.mktemp("wrong_ip_pages"))


def test_mixed_wrong_ip_keeps_both_addresses(pages):
    """A mixed wrong_ip result names both addresses and does not call the relay healthy."""
    html = pages[MIXED]
    assert html.count("DNS Returned Wrong IP") >= 2
    assert "23.202.88.27" in html
    assert "2.18.188.209" in html
    assert "2/4" in html
    assert "(a wrong IP was also returned; that answer is kept)" in html
    assert "Wrong IP" in html
    assert "Wrong_Ip" not in html
    assert "improved by cross-validation" not in html
    assert "only marked as failing if all instances agree" not in html
    assert "A wrong IP is kept even when another instance returns the right address." in html


def test_success_relay_renders_healthy(pages):
    html = pages[HEALTHY]
    assert "Healthy" in html
    assert "DNS Returned Wrong IP" not in html
    assert "improved by cross-validation" not in html
    assert "only marked as failing if all instances agree" not in html


def test_dns_fail_row_keeps_fail_and_timeout_labels(pages):
    html = pages[FAILED]
    assert "DNS Lookup Failed" in html
    assert ">DNS Fail</span>" in html
    assert ">Timeout</span>" in html
    assert "Wrong_Ip" not in html
    assert "only marked as failing if all instances agree" not in html


def test_legacy_dns_wrong_ip_detail_uses_the_same_label(pages):
    """Older detail value dns_wrong_ip still matches, in the summary and the section."""
    html = pages[LEGACY]
    assert html.count("DNS Returned Wrong IP") >= 2
    assert "(a wrong IP was also returned; that answer is kept)" not in html
    assert "improved by cross-validation" not in html


def test_recovered_timeout_still_says_improved(pages):
    """A real recovery still shows the improved note. A wrong IP does not."""
    html = pages[RECOVERED]
    assert "Healthy" in html
    assert "(improved by cross-validation)" in html
    assert "(a wrong IP was also returned; that answer is kept)" not in html
    assert ">Timeout</span>" in html
