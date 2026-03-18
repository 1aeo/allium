"""
Schema-contract and migration-guard tests for Prometheus schema v2.

These tests are intentionally integration-leaning:
- validate emitted metric families/labels for schema contract stability,
- validate docs + alert examples stay aligned with emitted contract.
"""

import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "allium"))

from lib.prometheus_metrics import generate_prometheus_metrics  # noqa: E402


def _relay(
    fingerprint,
    contact="",
    aroi_domain="none",
    flags=None,
    dns_detail="success",
):
    return {
        "fingerprint": fingerprint,
        "nickname": f"n{fingerprint[:4]}",
        "contact": contact,
        "aroi_domain": aroi_domain,
        "flags": flags or ["Exit", "Running", "Valid"],
        "exit_dns_health_detail": dns_detail,
        "exit_dns_health_timing_ms": None if dns_detail in ("relay_unreachable", "untested") else 1000,
        "exit_dns_health_consecutive_failures": 0,
    }


def _relay_set(relays, dns_data, aroi_data):
    class RS:
        pass

    rs = RS()
    rs.json = {"relays": relays}
    rs.exit_dns_health_data = dns_data
    rs.aroi_validation_data = aroi_data
    rs._fp_to_family_key = {}
    rs.validated_aroi_domains = set()
    return rs


def _dns_data():
    return {
        "metadata": {
            "timestamp": "2026-03-08T08:00:00Z",
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
            "timing": {"total": {"avg_ms": 1, "min_ms": 1, "max_ms": 1, "p50_ms": 1, "p95_ms": 1, "p99_ms": 1}},
        }
    }


def _aroi_data():
    return {
        "metadata": {"timestamp": "2026-03-08T10:00:00Z"},
        "statistics": {},
        "results": [
            {"fingerprint": "AAAA", "valid": True, "domain": "example.com", "proof_type": "uri-rsa"},
            {"fingerprint": "BBBB", "valid": False, "domain": "broken.org", "proof_type": "dns-rsa"},
        ],
    }


def _render_metrics():
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
    with tempfile.TemporaryDirectory() as td:
        generate_prometheus_metrics(rs, td)
        with open(os.path.join(td, "metrics"), encoding="utf-8") as f:
            return f.read()


class TestPrometheusSchemaV2Contract(unittest.TestCase):
    def test_metric_family_contract_and_legacy_absence(self):
        content = _render_metrics()
        metric_names = set()
        for line in content.split("\n"):
            if not line or line.startswith("#"):
                continue
            metric_names.add(line.split("{", 1)[0].split(" ", 1)[0])

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

        self.assertTrue(required.issubset(metric_names))
        self.assertTrue(removed.isdisjoint(metric_names))

    def test_frozen_aroi_state_enum_values(self):
        content = _render_metrics()
        states = set(
            re.findall(
                r'aeo1_aroi_relay_state\{[^}]*state="([^"]+)"\} 1',
                content,
            )
        )
        self.assertEqual(
            states,
            {
                "not_configured",
                "configured_unchecked",
                "configured_checked_invalid",
                "configured_checked_valid",
            },
        )

    def test_dns_status_enum_includes_untested(self):
        content = _render_metrics()
        statuses = set(
            re.findall(
                r'aeo1_exit_dns_failed\{[^}]*status="([^"]+)"\}',
                content,
            )
        )
        self.assertTrue(
            {"success", "dns_fail", "timeout", "relay_unreachable", "untested"}.issubset(statuses)
        )

    def test_derived_ratios_from_canonical_counts(self):
        content = _render_metrics()
        state_counts = {
            state: int(value)
            for state, value in re.findall(
                r'aeo1_aroi_relays_count\{state="([^"]+)"\} ([0-9]+)',
                content,
            )
        }
        configured_total = (
            state_counts["configured_unchecked"]
            + state_counts["configured_checked_invalid"]
            + state_counts["configured_checked_valid"]
        )
        checked_total = (
            state_counts["configured_checked_invalid"]
            + state_counts["configured_checked_valid"]
        )
        success_ratio = state_counts["configured_checked_valid"] / configured_total
        checked_ratio = checked_total / configured_total
        self.assertGreaterEqual(success_ratio, 0.0)
        self.assertLessEqual(success_ratio, 1.0)
        self.assertGreaterEqual(checked_ratio, 0.0)
        self.assertLessEqual(checked_ratio, 1.0)


class TestPrometheusDocsAndAlertsContract(unittest.TestCase):
    def test_readme_contains_v2_contract_and_dns_note(self):
        readme = "/workspace/docs/prometheus/README.md"
        with open(readme, encoding="utf-8") as f:
            text = f.read()

        # Schema + state model
        self.assertIn("**Schema:** v2", text)
        self.assertIn("aeo1_aroi_relay_state", text)
        self.assertIn("configured_unchecked", text)
        self.assertIn("configured_checked_invalid", text)
        self.assertIn("configured_checked_valid", text)

        # DNS enum completeness in docs
        self.assertIn("`error`", text)
        self.assertIn("`unknown`", text)
        self.assertIn("`untested`", text)

        # Migration/joins presence
        self.assertIn("Side-by-side query mapping", text)
        self.assertIn("Domain unchecked", text)
        self.assertIn("Migration checklist", text)
        self.assertIn("Operator Runbook", text)
        self.assertIn("Aggregate-only dashboard mode", text)
        self.assertIn("recording_rules.yml", text)

    def test_alert_examples_use_v2_metrics_only(self):
        alert_path = "/workspace/docs/prometheus/alerts_aroi.yml"
        with open(alert_path, encoding="utf-8") as f:
            alerts = f.read()

        self.assertIn("Schema: v2", alerts)
        self.assertIn("aeo1_aroi_relay_state", alerts)
        self.assertIn("aeo1_aroi_relays_count", alerts)
        self.assertNotIn("aeo1_aroi_valid", alerts)

    def test_recording_rules_file_exists_and_uses_v2_states(self):
        rules_path = "/workspace/docs/prometheus/recording_rules.yml"
        self.assertTrue(os.path.exists(rules_path))
        with open(rules_path, encoding="utf-8") as f:
            text = f.read()
        self.assertIn('state="configured_unchecked"', text)
        self.assertIn('state="configured_checked_invalid"', text)
        self.assertIn('state="configured_checked_valid"', text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
