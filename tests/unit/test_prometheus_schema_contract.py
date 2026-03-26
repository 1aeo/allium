"""
Schema-contract and migration-guard tests for Prometheus schema v2.

These tests are intentionally integration-leaning:
- validate emitted metric families/labels for schema contract stability,
- validate docs + alert examples stay aligned with emitted contract.
"""

import re
from pathlib import Path

import pytest

from allium.lib.prometheus_metrics import generate_prometheus_metrics
from tests.unit.prometheus_fixtures import (
    make_relay as _make_base_relay,
    make_relay_set as _make_base_relay_set,
    sample_aroi_data as _sample_base_aroi_data,
    sample_dns_metadata as _sample_base_dns_metadata,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOCS_DIR = _REPO_ROOT / "docs" / "prometheus"


def _relay(
    fingerprint,
    contact="",
    aroi_domain="none",
    flags=None,
    dns_detail="success",
):
    return _make_base_relay(
        fingerprint=fingerprint,
        nickname=f"n{fingerprint[:4]}",
        flags=flags or ["Exit", "Running", "Valid"],
        contact=contact,
        aroi_domain=aroi_domain,
        dns_status=dns_detail,
        dns_timing=None if dns_detail in ("relay_unreachable", "untested") else 1000,
        dns_consecutive=0,
    )


def _relay_set(relays, dns_data, aroi_data):
    return _make_base_relay_set(
        relays,
        exit_dns_health_data=dns_data,
        aroi_validation_data=aroi_data,
        fp_to_family_key={},
        validated_aroi_domains=set(),
    )


def _dns_data():
    data = _sample_base_dns_metadata()
    data["metadata"].update({
        "consensus_relays": 5,
        "tested_relays": 5,
        "unreachable_relays": 0,
        "dns_success": 1,
        "dns_fail": 1,
        "dns_timeout": 1,
        "dns_wrong_ip": 0,
        "dns_socks_error": 0,
        "dns_network_error": 0,
        "dns_error": 1,
        "dns_exception": 0,
        "dns_unknown": 1,
    })
    data["metadata"]["timing"] = {"total": {"avg_ms": 1, "min_ms": 1, "max_ms": 1, "p50_ms": 1, "p95_ms": 1, "p99_ms": 1}}
    return data


def _aroi_data():
    data = _sample_base_aroi_data()
    data["metadata"] = {"timestamp": "2026-03-08T10:00:00Z"}
    data["statistics"] = {}
    data["results"] = [
        {"fingerprint": "AAAA", "valid": True, "domain": "example.com", "proof_type": "uri-rsa"},
        {"fingerprint": "BBBB", "valid": False, "domain": "broken.org", "proof_type": "dns-rsa"},
    ]
    return data


@pytest.fixture
def render_metrics(tmp_path):
    relays = [
        # configured + checked + valid
        _relay("AAAA", contact="url:https://example.com proof:uri-rsa ciissversion:2", aroi_domain="example.com", dns_detail="success"),
        # configured + checked + invalid
        _relay("BBBB", contact="url:https://broken.org proof:dns-rsa ciissversion:2", aroi_domain="broken.org", dns_detail="dns_fail"),
        # configured + unchecked
        _relay("CCCC", contact="url:https://unchecked.org proof:dns-rsa ciissversion:2", aroi_domain="unchecked.org", dns_detail="timeout"),
        # not configured
        _relay("DDDD", contact="plain contact", aroi_domain="none", dns_detail="relay_unreachable"),
        # untested dns status coverage
        _relay("EEEE", contact="", aroi_domain="none", dns_detail="untested"),
    ]
    rs = _relay_set(relays, _dns_data(), _aroi_data())
    generate_prometheus_metrics(rs, str(tmp_path))
    return (tmp_path / "metrics").read_text(encoding="utf-8")


def _metric_names_from_content(content: str):
    names = set()
    for line in content.split("\n"):
        if not line or line.startswith("#"):
            continue
        names.add(line.split("{", 1)[0].split(" ", 1)[0])
    return names


def _label_key_sets_for_metric(content: str, metric_name: str):
    label_sets = set()
    pattern = re.compile(rf'^{re.escape(metric_name)}(?:\{{([^}}]*)\}})?\s', re.MULTILINE)
    for labels_blob in pattern.findall(content):
        if not labels_blob:
            label_sets.add(frozenset())
            continue
        keys = []
        for token in labels_blob.split(","):
            key = token.split("=", 1)[0].strip()
            if key:
                keys.append(key)
        label_sets.add(frozenset(keys))
    return label_sets


def _extract_non_comment_aeo1_tokens(path: Path):
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    active_lines = [ln for ln in lines if not ln.lstrip().startswith("#")]
    return set(re.findall(r"\baeo1_[a-zA-Z0-9_:]+\b", "".join(active_lines)))


def _extract_record_names(path: Path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return set(re.findall(r"^\s*-\s*record:\s*(aeo1_[a-zA-Z0-9_:]+)\s*$", text, re.MULTILINE))


def _extract_group_names(path: Path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return set(re.findall(r"^\s*-\s*name:\s*(aeo1_[a-zA-Z0-9_:]+)\s*$", text, re.MULTILINE))


def test_metric_family_contract_and_legacy_absence(render_metrics):
    metric_names = _metric_names_from_content(render_metrics)

    required = {
        "aeo1_build_info",
        "aeo1_generation_timestamp_seconds",
        "aeo1_source_up",
        "aeo1_source_last_success_timestamp_seconds",
        "aeo1_exit_dns_failed",
        "aeo1_exit_dns_errors_count",
        "aeo1_aroi_relay_state",
        "aeo1_aroi_relays_count",
        "aeo1_aroi_scan_timestamp_seconds",
        "aeo1_aroi_relay_info",
    }
    removed = {
        "aeo1_aroi_valid",
        "aeo1_aroi_success_ratio",
        "aeo1_aroi_valid_relays_count",
    }

    assert required.issubset(metric_names)
    assert removed.isdisjoint(metric_names)


def test_frozen_aroi_state_enum_values(render_metrics):
    states = set(
        re.findall(
            r'aeo1_aroi_relay_state\{[^}]*state="([^"]+)"\} 1',
            render_metrics,
        )
    )
    assert states == {
        "not_configured",
        "configured_unchecked",
        "configured_checked_invalid",
        "configured_checked_valid",
    }


def test_frozen_label_keys_for_core_metrics(render_metrics):
    expected = {
        "aeo1_build_info": {"schema", "generator"},
        "aeo1_source_up": {"source"},
        "aeo1_source_last_success_timestamp_seconds": {"source"},
        "aeo1_exit_dns_errors_count": {"error_type"},
        "aeo1_exit_dns_latency_ms_stat": {"stat"},
        "aeo1_exit_dns_failed": {"fingerprint", "familyid", "status"},
        "aeo1_exit_dns_latency_ms": {"fingerprint", "familyid"},
        "aeo1_exit_dns_consecutive_failures": {"fingerprint", "familyid"},
        "aeo1_exit_relay_info": {"fingerprint", "familyid", "nick", "verifiedaroi"},
        "aeo1_aroi_relay_state": {"fingerprint", "familyid", "state"},
        "aeo1_aroi_relays_count": {"state"},
        "aeo1_aroi_relay_info": {"fingerprint", "familyid", "nick", "domain", "proof_type"},
    }
    for metric, expected_keys in expected.items():
        found = _label_key_sets_for_metric(render_metrics, metric)
        assert found, f"missing metric lines for {metric}"
        assert found == {frozenset(expected_keys)}, f"unexpected labels for {metric}"


def test_dns_status_enum_includes_untested(render_metrics):
    statuses = set(
        re.findall(
            r'aeo1_exit_dns_failed\{[^}]*status="([^"]+)"\}',
            render_metrics,
        )
    )
    assert {"success", "dns_fail", "timeout", "relay_unreachable", "untested"}.issubset(statuses)


def test_derived_ratios_from_canonical_counts(render_metrics):
    state_counts = {
        state: int(value)
        for state, value in re.findall(
            r'aeo1_aroi_relays_count\{state="([^"]+)"\} ([0-9]+)',
            render_metrics,
        )
    }
    configured_total = (
        state_counts["configured_unchecked"]
        + state_counts["configured_checked_invalid"]
        + state_counts["configured_checked_valid"]
    )
    assert configured_total > 0, f"configured_total must be >0, got {configured_total} from {state_counts}"

    checked_total = (
        state_counts["configured_checked_invalid"]
        + state_counts["configured_checked_valid"]
    )
    success_ratio = state_counts["configured_checked_valid"] / configured_total
    checked_ratio = checked_total / configured_total
    assert 0.0 <= success_ratio <= 1.0, f"success_ratio out of bounds: {success_ratio}"
    assert 0.0 <= checked_ratio <= 1.0, f"checked_ratio out of bounds: {checked_ratio}"


def test_readme_contains_v2_contract_and_dns_note():
    readme = _DOCS_DIR / "README.md"
    text = readme.read_text(encoding="utf-8")

    assert "**Schema:** v2" in text
    assert "aeo1_aroi_relay_state" in text
    assert "configured_unchecked" in text
    assert "configured_checked_invalid" in text
    assert "configured_checked_valid" in text
    assert "`error`" in text
    assert "`unknown`" in text
    assert "`untested`" in text
    assert "Side-by-side query mapping" in text
    assert "Domain unchecked" in text
    assert "Migration checklist" in text
    assert "Operator Runbook" in text
    assert "Aggregate-only dashboard mode" in text
    assert "recording_rules.yml" in text


def test_alert_examples_use_v2_metrics_only():
    alert_path = _DOCS_DIR / "alerts_aroi.yml"
    alerts = alert_path.read_text(encoding="utf-8")

    assert "Schema: v2" in alerts
    assert "aeo1_aroi_relay_state" in alerts
    assert "aeo1_aroi_relays_count" in alerts
    assert "aeo1_aroi_valid" not in alerts


def test_recording_rules_file_exists_and_uses_v2_states():
    rules_path = _DOCS_DIR / "recording_rules.yml"
    assert rules_path.exists()
    text = rules_path.read_text(encoding="utf-8")
    assert 'state="configured_unchecked"' in text
    assert 'state="configured_checked_invalid"' in text
    assert 'state="configured_checked_valid"' in text


def test_alert_and_recording_rule_metric_references_exist(render_metrics):
    emitted = _metric_names_from_content(render_metrics)

    alerts_path = _DOCS_DIR / "alerts_aroi.yml"
    alerts_refs = _extract_non_comment_aeo1_tokens(alerts_path)
    alerts_refs -= _extract_group_names(alerts_path)
    assert alerts_refs.issubset(emitted), f"unknown alert refs: {sorted(alerts_refs - emitted)}"

    rules_path = _DOCS_DIR / "recording_rules.yml"
    rules_refs = _extract_non_comment_aeo1_tokens(rules_path)
    record_names = _extract_record_names(rules_path)
    group_names = _extract_group_names(rules_path)
    expr_refs = rules_refs - record_names - group_names
    assert expr_refs.issubset(emitted), f"unknown recording expr refs: {sorted(expr_refs - emitted)}"
