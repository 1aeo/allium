"""Pytest tests for allium.lib.prometheus_metrics (schema v2)."""

from __future__ import annotations

import re
import time
from pathlib import Path

import pytest

from allium.lib.prometheus_metrics import (
    SCHEMA_VERSION,
    _build_aroi_map,
    _format_labels,
    _get_family_id,
    _is_aroi_configured,
    _parse_timestamp_epoch,
    _safe_numeric,
    _sanitize_prom_label,
    generate_prometheus_metrics,
)
_USE_DEFAULT = object()

def _generate(
    tmp_path: Path,
    make_relay_set,
    sample_dns_metadata,
    sample_aroi_metadata,
    relays,
    dns_data=_USE_DEFAULT,
    aroi_data=_USE_DEFAULT,
    fp_to_family=None,
    validated_domains=None,
) -> tuple[str, dict]:
    selected_dns = sample_dns_metadata() if dns_data is _USE_DEFAULT else dns_data
    selected_aroi = sample_aroi_metadata() if aroi_data is _USE_DEFAULT else aroi_data
    rs = make_relay_set(
        relays,
        exit_dns_health_data=selected_dns,
        aroi_validation_data=selected_aroi,
        fp_to_family_key=fp_to_family or {},
        validated_aroi_domains=validated_domains or set(),
    )
    stats = generate_prometheus_metrics(rs, str(tmp_path))
    content = (tmp_path / "metrics").read_text(encoding="utf-8")
    return content, stats


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("hello", "hello"),
        ('say "hi"', 'say \\"hi\\"'),
        ("a\\b", "a\\\\b"),
        ("line1\nline2", "line1\\nline2"),
        (None, ""),
        ("", ""),
    ],
)
def test_sanitize_prom_label(value, expected):
    assert _sanitize_prom_label(value) == expected


def test_format_labels_empty():
    assert _format_labels({}) == ""


def test_format_labels_single():
    assert _format_labels({"k": "v"}) == '{k="v"}'


def test_format_labels_multiple_preserves_order():
    assert _format_labels({"a": "1", "b": "2", "c": "3"}) == '{a="1",b="2",c="3"}'


def test_format_labels_escaping():
    assert _format_labels({"nick": 'say "hi"'}) == '{nick="say \\"hi\\""}'


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (42, "42"),
        (0, "0"),
        (3.14, "3.14"),
        ("99", "99.0"),
        ("hello", "0"),
        ("1\naeo1_injected_metric 42", "0"),
        (None, "0"),
        (float("nan"), "0"),
        (float("inf"), "0"),
        (float("-inf"), "0"),
        (False, "0.0"),
        (True, "1.0"),
    ],
)
def test_safe_numeric(value, expected):
    assert _safe_numeric(value) == expected


def test_get_family_id_found(make_relay_set):
    rs = make_relay_set([], fp_to_family_key={"AAAA": "FAMKEY1"})
    assert _get_family_id(rs, "AAAA") == "FAMKEY1"
    assert _get_family_id(rs, "aaaa") == "FAMKEY1"


def test_get_family_id_not_found(make_relay_set):
    rs = make_relay_set([], fp_to_family_key={"AAAA": "FAMKEY1"})
    assert _get_family_id(rs, "BBBB") == ""


def test_get_family_id_no_map(make_relay_set):
    rs = make_relay_set([])
    rs._fp_to_family_key = None
    assert _get_family_id(rs, "AAAA") == ""


def test_is_aroi_configured_uses_cached_true():
    assert _is_aroi_configured({"contact": "invalid", "aroi_configured": True}) is True


def test_is_aroi_configured_uses_cached_false():
    relay = {"contact": "url:https://x proof:uri-rsa ciissversion:2", "aroi_configured": False}
    assert _is_aroi_configured(relay) is False


@pytest.mark.parametrize(
    ("relay", "expected"),
    [
        ({"contact": "email:a@b.com url:https://b.com proof:uri-rsa ciissversion:2"}, True),
        ({"contact": "email:a@b.com url:https://b.com ciissversion:2"}, False),
        ({"contact": ""}, False),
        ({}, False),
    ],
)
def test_is_aroi_configured_variants(relay, expected):
    assert _is_aroi_configured(relay) is expected


def test_build_aroi_map_uppercase(make_relay_set, sample_aroi_data):
    aroi_payload = sample_aroi_data()
    aroi_payload["results"] = [
        {"fingerprint": "aaaa", "valid": True, "domain": "example.com", "proof_type": "uri-rsa"},
        {"fingerprint": "BbBb", "valid": False, "domain": "broken.org", "proof_type": "dns-rsa"},
    ]
    rs = make_relay_set([], aroi_validation_data=aroi_payload)
    amap = _build_aroi_map(rs)
    assert "AAAA" in amap
    assert "BBBB" in amap
    assert amap["AAAA"]["valid"] is True
    assert amap["BBBB"]["valid"] is False


def test_dns_metrics_healthy(tmp_path, make_relay, make_relay_set, sample_dns_metadata, sample_aroi_metadata):
    content, _ = _generate(
        tmp_path, make_relay_set, sample_dns_metadata, sample_aroi_metadata, [make_relay("AAAA", dns_status="success")]
    )
    assert 'aeo1_exit_dns_failed{fingerprint="AAAA",familyid="",status="success"} 0' in content


def test_dns_metrics_failure(tmp_path, make_relay, make_relay_set, sample_dns_metadata, sample_aroi_metadata):
    relays = [make_relay("BBBB", dns_status="dns_fail", dns_timing=5000, dns_consecutive=3)]
    content, _ = _generate(tmp_path, make_relay_set, sample_dns_metadata, sample_aroi_metadata, relays)
    assert 'aeo1_exit_dns_failed{fingerprint="BBBB",familyid="",status="dns_fail"} 1' in content
    assert 'aeo1_exit_dns_latency_ms{fingerprint="BBBB",familyid=""} 5000' in content
    assert 'aeo1_exit_dns_consecutive_failures{fingerprint="BBBB",familyid=""} 3' in content


def test_dns_unreachable_no_latency(tmp_path, make_relay, make_relay_set, sample_dns_metadata, sample_aroi_metadata):
    relays = [make_relay("CCCC", dns_status="relay_unreachable", dns_timing=None)]
    content, _ = _generate(tmp_path, make_relay_set, sample_dns_metadata, sample_aroi_metadata, relays)
    assert 'aeo1_exit_dns_failed{fingerprint="CCCC",familyid="",status="relay_unreachable"} 1' in content
    assert 'aeo1_exit_dns_latency_ms{fingerprint="CCCC"' not in content


def test_dns_untested_not_failed(tmp_path, make_relay, make_relay_set, sample_dns_metadata, sample_aroi_metadata):
    relays = [make_relay("DDDD", dns_status="untested", dns_timing=None)]
    content, _ = _generate(tmp_path, make_relay_set, sample_dns_metadata, sample_aroi_metadata, relays)
    assert 'aeo1_exit_dns_failed{fingerprint="DDDD",familyid="",status="untested"} 0' in content
    assert 'aeo1_exit_dns_latency_ms{fingerprint="DDDD"' not in content


def test_dns_non_exit_excluded(tmp_path, make_relay, make_relay_set, sample_dns_metadata, sample_aroi_data,
                               sample_aroi_metadata):
    relays = [make_relay("AAAA", flags=["Guard", "Running"]), make_relay("BBBB", flags=["Exit", "Running"])]
    content, stats = _generate(
        tmp_path, make_relay_set, sample_dns_metadata, sample_aroi_metadata, relays, aroi_data=sample_aroi_data()
    )
    assert stats["exit_relays"] == 1
    assert 'aeo1_exit_dns_failed{fingerprint="AAAA"' not in content


def test_dns_familyid_populated(tmp_path, make_relay, make_relay_set, sample_dns_metadata, sample_aroi_metadata):
    content, _ = _generate(
        tmp_path,
        make_relay_set,
        sample_dns_metadata,
        sample_aroi_metadata,
        [make_relay("AAAA")],
        fp_to_family={"AAAA": "MYFAMKEY"},
    )
    assert 'familyid="MYFAMKEY"' in content


def test_dns_verifiedaroi_info(tmp_path, make_relay, make_relay_set, sample_dns_metadata, sample_aroi_data,
                               sample_aroi_metadata):
    relays = [make_relay("AAAA", aroi_domain="example.com", contact="url:https://example.com proof:uri-rsa ciissversion:2")]
    aroi_data = sample_aroi_data()
    aroi_data["results"] = [{"fingerprint": "AAAA", "valid": True, "domain": "example.com", "proof_type": "uri-rsa"}]
    content, _ = _generate(
        tmp_path,
        make_relay_set,
        sample_dns_metadata,
        sample_aroi_metadata,
        relays,
        aroi_data=aroi_data,
        validated_domains={"example.com"},
    )
    assert 'verifiedaroi="example.com"' in content


def test_dns_metrics_sorted_by_fingerprint(tmp_path, make_relay, make_relay_set, sample_dns_metadata, sample_aroi_data,
                                           sample_aroi_metadata):
    relays = [make_relay("CCCC"), make_relay("AAAA"), make_relay("BBBB")]
    content, _ = _generate(
        tmp_path, make_relay_set, sample_dns_metadata, sample_aroi_metadata, relays, aroi_data=sample_aroi_data()
    )
    fps = re.findall(r'aeo1_exit_dns_failed\{fingerprint="(\w+)"', content)
    assert fps == sorted(fps)


def test_aroi_state_and_counts(tmp_path, make_relay, make_relay_set, sample_dns_metadata, sample_aroi_data,
                               sample_aroi_metadata):
    relays = [
        make_relay("AAAA", contact="url:https://example.com proof:uri-rsa ciissversion:2", aroi_domain="example.com"),
        make_relay("BBBB", contact="url:https://broken.org proof:dns-rsa ciissversion:2", aroi_domain="broken.org"),
        make_relay("CCCC", contact="url:https://missing.org proof:dns-rsa ciissversion:2", aroi_domain="missing.org"),
        make_relay("DDDD", contact="plain"),
    ]
    content, stats = _generate(
        tmp_path, make_relay_set, sample_dns_metadata, sample_aroi_metadata, relays, aroi_data=sample_aroi_data()
    )
    assert stats["aroi_relays"] == 3
    # B7.1: aeo1_aroi_relay_state labelset extended with ciissversion +
    # proof_type_family. All test fixture relays declare ciissversion:2
    # with rsa proof types via the contact string.
    assert 'aeo1_aroi_relay_state{fingerprint="AAAA",familyid="",state="configured_checked_valid",ciissversion="2",proof_type_family="rsa"} 1' in content
    assert 'aeo1_aroi_relay_state{fingerprint="BBBB",familyid="",state="configured_checked_invalid",ciissversion="2",proof_type_family="rsa"} 1' in content
    assert 'aeo1_aroi_relay_state{fingerprint="CCCC",familyid="",state="configured_unchecked",ciissversion="2",proof_type_family="rsa"} 1' in content
    # DDDD has plain contact (no ciissversion) — labels: none/none.
    assert 'aeo1_aroi_relay_state{fingerprint="DDDD",familyid="",state="not_configured",ciissversion="none",proof_type_family="none"} 1' in content
    assert 'aeo1_aroi_relays_count{state="not_configured"} 1' in content
    assert 'aeo1_aroi_relays_count{state="configured_unchecked"} 1' in content
    assert 'aeo1_aroi_relays_count{state="configured_checked_invalid"} 1' in content
    assert 'aeo1_aroi_relays_count{state="configured_checked_valid"} 1' in content
    # B7.2: aeo1_aroi_relays_count_by_version emits all 16 (4 state x 4
    # ciissversion) cells with the correct counts.
    assert 'aeo1_aroi_relays_count_by_version{state="configured_checked_valid",ciissversion="2"} 1' in content
    assert 'aeo1_aroi_relays_count_by_version{state="configured_checked_invalid",ciissversion="2"} 1' in content
    assert 'aeo1_aroi_relays_count_by_version{state="configured_unchecked",ciissversion="2"} 1' in content
    assert 'aeo1_aroi_relays_count_by_version{state="not_configured",ciissversion="none"} 1' in content
    # Zero-cell present (no v3 in this fixture).
    assert 'aeo1_aroi_relays_count_by_version{state="configured_checked_valid",ciissversion="3"} 0' in content


def test_aroi_exactly_one_state_per_relay(tmp_path, make_relay, make_relay_set, sample_dns_metadata, sample_aroi_data,
                                          sample_aroi_metadata):
    relays = [
        make_relay("AAAA", contact="url:https://example.com proof:uri-rsa ciissversion:2", aroi_domain="example.com"),
        make_relay("BBBB", contact="url:https://broken.org proof:dns-rsa ciissversion:2", aroi_domain="broken.org"),
        make_relay("CCCC", contact="url:https://missing.org proof:dns-rsa ciissversion:2", aroi_domain="missing.org"),
        make_relay("DDDD", contact="plain"),
    ]
    content, _ = _generate(
        tmp_path, make_relay_set, sample_dns_metadata, sample_aroi_metadata, relays, aroi_data=sample_aroi_data()
    )
    expected_states = {
        "AAAA": "configured_checked_valid",
        "BBBB": "configured_checked_invalid",
        "CCCC": "configured_unchecked",
        "DDDD": "not_configured",
    }
    for fp, expected_state in expected_states.items():
        # B7.1: regex updated for new labelset (ciissversion + proof_type_family).
        matches = re.findall(
            rf'^aeo1_aroi_relay_state\{{fingerprint="{fp}",familyid="",state="[^"]+",ciissversion="[^"]+",proof_type_family="[^"]+"\}} 1$',
            content,
            re.MULTILINE,
        )
        assert len(matches) == 1, f"expected exactly one state for {fp}"
        # State assertion — accept any ciissversion/proof_type_family combo.
        state_match = re.search(
            rf'aeo1_aroi_relay_state\{{fingerprint="{fp}",familyid="",state="{expected_state}",ciissversion="[^"]+",proof_type_family="[^"]+"\}} 1',
            content,
        )
        assert state_match is not None, f"expected state {expected_state} for {fp}"


def test_aroi_legacy_metrics_removed(tmp_path, make_relay, make_relay_set, sample_dns_metadata, sample_aroi_data,
                                     sample_aroi_metadata):
    relays = [make_relay("AAAA", contact="url:https://example.com proof:uri-rsa ciissversion:2", aroi_domain="example.com")]
    content, _ = _generate(
        tmp_path, make_relay_set, sample_dns_metadata, sample_aroi_metadata, relays, aroi_data=sample_aroi_data()
    )
    assert "aeo1_aroi_valid{" not in content
    assert "aeo1_aroi_success_ratio" not in content


def test_aroi_unchecked_relay_info_uses_claimed_domain(tmp_path, make_relay, make_relay_set, sample_dns_metadata,
                                                       sample_aroi_data, sample_aroi_metadata):
    relays = [make_relay("CCCC", nickname="RelayC", contact="url:https://missing.org proof:dns-rsa ciissversion:2", aroi_domain="missing.org")]
    content, _ = _generate(
        tmp_path, make_relay_set, sample_dns_metadata, sample_aroi_metadata, relays, aroi_data=sample_aroi_data()
    )
    line = next((ln for ln in content.split("\n") if ln.startswith('aeo1_aroi_relay_info{fingerprint="CCCC"')), "")
    assert 'domain="missing.org"' in line


def test_source_availability_permutations(tmp_path, make_relay, make_relay_set, sample_dns_metadata, sample_aroi_data,
                                          sample_aroi_metadata):
    relay = make_relay("AAAA", contact="url:https://example.com proof:uri-rsa ciissversion:2", aroi_domain="example.com")
    # both up
    content, _ = _generate(
        tmp_path, make_relay_set, sample_dns_metadata, sample_aroi_metadata, [relay], aroi_data=sample_aroi_data()
    )
    assert 'aeo1_source_up{source="exitdnshealth"} 1' in content
    assert 'aeo1_source_up{source="aroi"} 1' in content


def test_source_dns_down(tmp_path, make_relay, make_relay_set, sample_dns_metadata, sample_aroi_data,
                         sample_aroi_metadata):
    relay = make_relay("AAAA", contact="url:https://example.com proof:uri-rsa ciissversion:2", aroi_domain="example.com")
    content, _ = _generate(
        tmp_path, make_relay_set, sample_dns_metadata, sample_aroi_metadata, [relay], dns_data=None,
        aroi_data=sample_aroi_data()
    )
    assert 'aeo1_source_up{source="exitdnshealth"} 0' in content
    assert 'aeo1_source_up{source="aroi"} 1' in content
    assert "aeo1_exit_dns_failed" not in content


def test_source_aroi_down(tmp_path, make_relay, make_relay_set, sample_dns_metadata, sample_aroi_metadata):
    relay = make_relay("AAAA", contact="url:https://example.com proof:uri-rsa ciissversion:2", aroi_domain="example.com")
    content, _ = _generate(tmp_path, make_relay_set, sample_dns_metadata, sample_aroi_metadata, [relay], aroi_data=None)
    assert 'aeo1_source_up{source="exitdnshealth"} 1' in content
    assert 'aeo1_source_up{source="aroi"} 0' in content
    assert "aeo1_aroi_relay_state" not in content
    assert "aeo1_aroi_relays_count" not in content


def test_source_both_down(tmp_path, make_relay, make_relay_set, sample_dns_metadata, sample_aroi_metadata):
    content, _ = _generate(
        tmp_path, make_relay_set, sample_dns_metadata, sample_aroi_metadata, [make_relay("AAAA")], dns_data=None,
        aroi_data=None
    )
    assert 'aeo1_source_up{source="exitdnshealth"} 0' in content
    assert 'aeo1_source_up{source="aroi"} 0' in content
    assert "aeo1_build_info" in content
    assert "aeo1_generation_timestamp_seconds" in content


def test_meta_build_info(tmp_path, make_relay_set, sample_dns_metadata):
    rs = make_relay_set([], exit_dns_health_data=sample_dns_metadata())
    generate_prometheus_metrics(rs, str(tmp_path))
    content = (tmp_path / "metrics").read_text(encoding="utf-8")
    assert f'aeo1_build_info{{schema="{SCHEMA_VERSION}",generator="allium"}} 1' in content
    assert SCHEMA_VERSION == "2"


def test_generation_timestamp_recent(tmp_path, make_relay_set):
    rs = make_relay_set([])
    before = int(time.time())
    generate_prometheus_metrics(rs, str(tmp_path))
    after = int(time.time())
    content = (tmp_path / "metrics").read_text(encoding="utf-8")
    match = re.search(r"aeo1_generation_timestamp_seconds (\d+)", content)
    assert match is not None
    ts = int(match.group(1))
    assert before <= ts <= after


def test_file_written_and_tmp_removed(tmp_path, make_relay_set):
    rs = make_relay_set([])
    generate_prometheus_metrics(rs, str(tmp_path))
    assert (tmp_path / "metrics").exists()
    assert not (tmp_path / "metrics.tmp").exists()


def test_unique_help_type_per_metric(tmp_path, make_relay, make_relay_set, sample_dns_metadata, sample_aroi_data):
    relay = make_relay("AAAA", contact="url:https://example.com proof:uri-rsa ciissversion:2", aroi_domain="example.com")
    rs = make_relay_set([relay], exit_dns_health_data=sample_dns_metadata(), aroi_validation_data=sample_aroi_data())
    generate_prometheus_metrics(rs, str(tmp_path))
    content = (tmp_path / "metrics").read_text(encoding="utf-8")

    help_counts = {}
    type_counts = {}
    for line in content.split("\n"):
        if line.startswith("# HELP "):
            name = line.split()[2]
            help_counts[name] = help_counts.get(name, 0) + 1
        elif line.startswith("# TYPE "):
            name = line.split()[2]
            type_counts[name] = type_counts.get(name, 0) + 1

    assert all(count == 1 for count in help_counts.values())
    assert all(count == 1 for count in type_counts.values())


def test_eof_marker_present(tmp_path, make_relay_set):
    rs = make_relay_set([])
    generate_prometheus_metrics(rs, str(tmp_path))
    content = (tmp_path / "metrics").read_text(encoding="utf-8")
    assert "# EOF" in content


def test_parse_timestamp_epoch_variants():
    from datetime import datetime, timezone

    expected = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc).timestamp()
    assert _parse_timestamp_epoch("2026-03-08T12:00:00Z") == expected
    assert _parse_timestamp_epoch("2026-03-08T12:00:00+00:00") == expected
    assert _parse_timestamp_epoch("2026-03-08T12:00:00") == expected
    assert _parse_timestamp_epoch("") == 0
    assert _parse_timestamp_epoch(None) == 0
    assert _parse_timestamp_epoch("1234567890") == 1234567890.0


def test_dns_error_and_unknown_emitted(tmp_path, make_relay, make_relay_set):
    rs = make_relay_set(
        [make_relay("AAAA")],
        exit_dns_health_data={
            "metadata": {
                "timestamp": "2026-03-08T08:00:00Z",
                "consensus_relays": 100,
                "tested_relays": 95,
                "unreachable_relays": 5,
                "dns_success": 80,
                "dns_fail": 3,
                "dns_timeout": 1,
                "dns_wrong_ip": 1,
                "dns_socks_error": 0,
                "dns_network_error": 0,
                "dns_error": 7,
                "dns_exception": 0,
                "dns_unknown": 3,
                "timing": {"total": {}},
            }
        },
    )
    generate_prometheus_metrics(rs, str(tmp_path))
    content = (tmp_path / "metrics").read_text(encoding="utf-8")
    assert 'aeo1_exit_dns_errors_count{error_type="error"} 7' in content
    assert 'aeo1_exit_dns_errors_count{error_type="unknown"} 3' in content
