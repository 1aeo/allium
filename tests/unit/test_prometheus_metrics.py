"""
Unit tests for allium.lib.prometheus_metrics

Tests the Prometheus exposition format generator for schema v1.
"""

import os
import re
import sys
import tempfile
import time
import unittest

# Add the allium package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'allium'))

from lib.prometheus_metrics import (
    _sanitize_prom_label,
    _format_labels,
    _get_family_id,
    _is_aroi_configured,
    _build_aroi_map,
    generate_prometheus_metrics,
    SCHEMA_VERSION,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_relay(fingerprint, nickname="TestRelay", flags=None, contact="",
                dns_status="success", dns_timing=1000, dns_consecutive=0,
                aroi_domain="none"):
    """Create a minimal relay dict matching allium's enriched relay structure."""
    return {
        "fingerprint": fingerprint,
        "nickname": nickname,
        "flags": flags or ["Exit", "Fast", "Guard", "Running", "Stable", "Valid"],
        "contact": contact,
        "aroi_domain": aroi_domain,
        "exit_dns_health_status": "success" if dns_status == "success" else "fail",
        "exit_dns_health_detail": dns_status,
        "exit_dns_health_timing_ms": dns_timing,
        "exit_dns_health_consecutive_failures": dns_consecutive,
    }


def _make_relay_set(relays, exit_dns_health_data=None, aroi_validation_data=None,
                    fp_to_family_key=None, validated_aroi_domains=None):
    """Create a mock relay_set object with the attributes prometheus_metrics needs."""

    class MockRelaySet:
        pass

    rs = MockRelaySet()
    rs.json = {"relays": relays}
    rs.exit_dns_health_data = exit_dns_health_data
    rs.aroi_validation_data = aroi_validation_data
    rs._fp_to_family_key = fp_to_family_key or {}
    rs.validated_aroi_domains = validated_aroi_domains or set()
    return rs


def _sample_dns_metadata():
    return {
        "metadata": {
            "timestamp": "2026-03-08T08:00:00Z",
            "consensus_relays": 100,
            "tested_relays": 95,
            "unreachable_relays": 5,
            "dns_success": 90,
            "dns_fail": 3,
            "dns_timeout": 1,
            "dns_wrong_ip": 1,
            "dns_socks_error": 0,
            "dns_network_error": 0,
            "dns_exception": 0,
            "timing": {
                "total": {
                    "avg_ms": 15000,
                    "min_ms": 200,
                    "max_ms": 30000,
                    "p50_ms": 14000,
                    "p95_ms": 25000,
                    "p99_ms": 28000,
                }
            },
        }
    }


def _sample_aroi_data():
    return {
        "metadata": {
            "timestamp": "2026-03-08T10:00:00Z",
            "total_relays": 200,
            "valid_relays": 50,
            "invalid_relays": 150,
        },
        "statistics": {
            "proof_types": {
                "uri_rsa": {"total": 40, "valid": 38},
                "dns_rsa": {"total": 10, "valid": 8},
            }
        },
        "results": [
            {"fingerprint": "AAAA", "valid": True, "domain": "example.com", "proof_type": "uri-rsa"},
            {"fingerprint": "BBBB", "valid": False, "domain": "broken.org", "proof_type": "dns-rsa"},
        ],
    }


# ---------------------------------------------------------------------------
# Tests: label escaping
# ---------------------------------------------------------------------------

class TestSanitizeLabel(unittest.TestCase):

    def test_normal_string(self):
        self.assertEqual(_sanitize_prom_label("hello"), "hello")

    def test_quotes(self):
        self.assertEqual(_sanitize_prom_label('say "hi"'), 'say \\"hi\\"')

    def test_backslash(self):
        self.assertEqual(_sanitize_prom_label("a\\b"), "a\\\\b")

    def test_newline(self):
        self.assertEqual(_sanitize_prom_label("line1\nline2"), "line1\\nline2")

    def test_none(self):
        self.assertEqual(_sanitize_prom_label(None), "")

    def test_empty(self):
        self.assertEqual(_sanitize_prom_label(""), "")

    def test_combined(self):
        self.assertEqual(_sanitize_prom_label('a\\b"c\nd'),
                         'a\\\\b\\"c\\nd')


class TestFormatLabels(unittest.TestCase):

    def test_empty(self):
        self.assertEqual(_format_labels({}), "")

    def test_single(self):
        self.assertEqual(_format_labels({"k": "v"}), '{k="v"}')

    def test_multiple_preserves_order(self):
        result = _format_labels({"a": "1", "b": "2", "c": "3"})
        self.assertEqual(result, '{a="1",b="2",c="3"}')

    def test_escaping_in_values(self):
        result = _format_labels({"nick": 'say "hi"'})
        self.assertEqual(result, '{nick="say \\"hi\\""}')


# ---------------------------------------------------------------------------
# Tests: safe accessors
# ---------------------------------------------------------------------------

class TestGetFamilyId(unittest.TestCase):

    def test_found(self):
        rs = _make_relay_set([], fp_to_family_key={"AAAA": "FAMKEY1"})
        self.assertEqual(_get_family_id(rs, "AAAA"), "FAMKEY1")
        self.assertEqual(_get_family_id(rs, "aaaa"), "FAMKEY1")  # case-insensitive

    def test_not_found(self):
        rs = _make_relay_set([], fp_to_family_key={"AAAA": "FAMKEY1"})
        self.assertEqual(_get_family_id(rs, "BBBB"), "")

    def test_no_map(self):
        rs = _make_relay_set([])
        rs._fp_to_family_key = None
        self.assertEqual(_get_family_id(rs, "AAAA"), "")


class TestIsAroiConfigured(unittest.TestCase):

    def test_all_fields(self):
        relay = {"contact": "email:a@b.com url:https://b.com proof:uri-rsa ciissversion:2"}
        self.assertTrue(_is_aroi_configured(relay))

    def test_missing_proof(self):
        relay = {"contact": "email:a@b.com url:https://b.com ciissversion:2"}
        self.assertFalse(_is_aroi_configured(relay))

    def test_no_contact(self):
        relay = {"contact": ""}
        self.assertFalse(_is_aroi_configured(relay))

    def test_none_contact(self):
        relay = {}
        self.assertFalse(_is_aroi_configured(relay))


# ---------------------------------------------------------------------------
# Tests: DNS health section
# ---------------------------------------------------------------------------

class TestDnsHealthMetrics(unittest.TestCase):

    def _generate(self, relays, dns_data=None, aroi_data=None,
                  fp_to_family=None, validated_domains=None):
        rs = _make_relay_set(
            relays,
            exit_dns_health_data=dns_data or _sample_dns_metadata(),
            aroi_validation_data=aroi_data,
            fp_to_family_key=fp_to_family or {},
            validated_aroi_domains=validated_domains or set(),
        )
        with tempfile.TemporaryDirectory() as td:
            stats = generate_prometheus_metrics(rs, td)
            with open(os.path.join(td, "metrics")) as f:
                content = f.read()
        return content, stats

    def test_healthy_relay(self):
        relays = [_make_relay("AAAA", dns_status="success")]
        content, _ = self._generate(relays)
        self.assertIn('aeo1_exit_dns_failed{fingerprint="AAAA",familyid="",status="success"} 0', content)

    def test_failing_relay(self):
        relays = [_make_relay("BBBB", dns_status="dns_fail", dns_timing=5000, dns_consecutive=3)]
        content, _ = self._generate(relays)
        self.assertIn('aeo1_exit_dns_failed{fingerprint="BBBB",familyid="",status="dns_fail"} 1', content)
        self.assertIn('aeo1_exit_dns_latency_ms{fingerprint="BBBB",familyid=""} 5000', content)
        self.assertIn('aeo1_exit_dns_consecutive_failures{fingerprint="BBBB",familyid=""} 3', content)

    def test_unreachable_relay_no_latency(self):
        relays = [_make_relay("CCCC", dns_status="relay_unreachable", dns_timing=None)]
        content, _ = self._generate(relays)
        self.assertIn('aeo1_exit_dns_failed{fingerprint="CCCC",familyid="",status="relay_unreachable"} 1', content)
        # No latency line for unreachable relays
        self.assertNotIn('aeo1_exit_dns_latency_ms{fingerprint="CCCC"', content)

    def test_non_exit_excluded(self):
        relays = [
            _make_relay("AAAA", flags=["Guard", "Running"]),  # not exit
            _make_relay("BBBB", flags=["Exit", "Running"]),   # exit
        ]
        content, stats = self._generate(relays)
        self.assertEqual(stats["exit_relays"], 1)
        self.assertNotIn('fingerprint="AAAA"', content.split("SECTION 2")[0])  # not in DNS section

    def test_familyid_populated(self):
        relays = [_make_relay("AAAA")]
        content, _ = self._generate(relays, fp_to_family={"AAAA": "MYFAMKEY"})
        self.assertIn('familyid="MYFAMKEY"', content)

    def test_verifiedaroi_in_info(self):
        relays = [_make_relay("AAAA", aroi_domain="example.com",
                              contact="url:https://example.com proof:uri-rsa ciissversion:2")]
        aroi_data = _sample_aroi_data()
        aroi_data["results"] = [
            {"fingerprint": "AAAA", "valid": True, "domain": "example.com", "proof_type": "uri-rsa"}
        ]
        content, _ = self._generate(relays, aroi_data=aroi_data,
                                     validated_domains={"example.com"})
        self.assertIn('verifiedaroi="example.com"', content)

    def test_aggregates_ratio_format(self):
        relays = [_make_relay("AAAA")]
        content, _ = self._generate(relays)
        # Ratios should be 0..1, not percentages
        self.assertIn("aeo1_exit_dns_success_ratio", content)
        # Match the metric line (not HELP/TYPE lines) — must start at line beginning
        match = re.search(r'^aeo1_exit_dns_success_ratio (\S+)', content, re.MULTILINE)
        self.assertIsNotNone(match, "Could not find aeo1_exit_dns_success_ratio metric line")
        ratio = float(match.group(1))
        self.assertLessEqual(ratio, 1.0)

    def test_count_suffix_not_total(self):
        relays = [_make_relay("AAAA")]
        content, _ = self._generate(relays)
        # No _total suffix on any gauge
        for line in content.split("\n"):
            if line.startswith("aeo1_") and "_total" in line.split("{")[0]:
                self.fail(f"Found _total suffix on gauge: {line}")

    def test_sorted_by_fingerprint(self):
        relays = [_make_relay("CCCC"), _make_relay("AAAA"), _make_relay("BBBB")]
        content, _ = self._generate(relays)
        # Extract fingerprints in order from aeo1_exit_dns_failed lines
        fps = re.findall(r'aeo1_exit_dns_failed\{fingerprint="(\w+)"', content)
        self.assertEqual(fps, sorted(fps))


# ---------------------------------------------------------------------------
# Tests: AROI section
# ---------------------------------------------------------------------------

class TestAroiMetrics(unittest.TestCase):

    def _generate(self, relays, aroi_data=None):
        rs = _make_relay_set(
            relays,
            exit_dns_health_data=_sample_dns_metadata(),
            aroi_validation_data=aroi_data or _sample_aroi_data(),
        )
        with tempfile.TemporaryDirectory() as td:
            stats = generate_prometheus_metrics(rs, td)
            with open(os.path.join(td, "metrics")) as f:
                content = f.read()
        return content, stats

    def test_configured_relay_included(self):
        relay = _make_relay("AAAA",
                            contact="url:https://example.com proof:uri-rsa ciissversion:2",
                            aroi_domain="example.com")
        content, stats = self._generate([relay])
        self.assertEqual(stats["aroi_relays"], 1)
        self.assertIn('aeo1_aroi_valid{fingerprint="AAAA"', content)

    def test_unconfigured_relay_excluded(self):
        relay = _make_relay("AAAA", contact="just a name", aroi_domain="none")
        content, stats = self._generate([relay])
        self.assertEqual(stats["aroi_relays"], 0)

    def test_valid_relay(self):
        relay = _make_relay("AAAA",
                            contact="url:https://example.com proof:uri-rsa ciissversion:2")
        content, _ = self._generate([relay])
        self.assertIn('aeo1_aroi_valid{fingerprint="AAAA",familyid=""} 1', content)

    def test_invalid_relay(self):
        relay = _make_relay("BBBB",
                            contact="url:https://broken.org proof:dns-rsa ciissversion:2")
        content, _ = self._generate([relay])
        self.assertIn('aeo1_aroi_valid{fingerprint="BBBB",familyid=""} 0', content)

    def test_info_labels(self):
        relay = _make_relay("AAAA", nickname="MyRelay",
                            contact="url:https://example.com proof:uri-rsa ciissversion:2")
        content, _ = self._generate([relay])
        self.assertIn('nick="MyRelay"', content)
        self.assertIn('domain="example.com"', content)
        self.assertIn('proof_type="uri-rsa"', content)


# ---------------------------------------------------------------------------
# Tests: source availability
# ---------------------------------------------------------------------------

class TestSourceAvailability(unittest.TestCase):

    def test_both_sources_up(self):
        rs = _make_relay_set(
            [_make_relay("AAAA")],
            exit_dns_health_data=_sample_dns_metadata(),
            aroi_validation_data=_sample_aroi_data(),
        )
        with tempfile.TemporaryDirectory() as td:
            generate_prometheus_metrics(rs, td)
            with open(os.path.join(td, "metrics")) as f:
                content = f.read()
        self.assertIn('aeo1_source_up{source="exitdnshealth"} 1', content)
        self.assertIn('aeo1_source_up{source="aroi"} 1', content)

    def test_dns_source_down(self):
        rs = _make_relay_set(
            [_make_relay("AAAA")],
            exit_dns_health_data=None,
            aroi_validation_data=_sample_aroi_data(),
        )
        with tempfile.TemporaryDirectory() as td:
            generate_prometheus_metrics(rs, td)
            with open(os.path.join(td, "metrics")) as f:
                content = f.read()
        self.assertIn('aeo1_source_up{source="exitdnshealth"} 0', content)
        self.assertIn('aeo1_source_up{source="aroi"} 1', content)
        # DNS section should be absent
        self.assertNotIn("aeo1_exit_dns_failed", content)

    def test_both_sources_down(self):
        rs = _make_relay_set(
            [_make_relay("AAAA")],
            exit_dns_health_data=None,
            aroi_validation_data=None,
        )
        with tempfile.TemporaryDirectory() as td:
            generate_prometheus_metrics(rs, td)
            with open(os.path.join(td, "metrics")) as f:
                content = f.read()
        self.assertIn('aeo1_source_up{source="exitdnshealth"} 0', content)
        self.assertIn('aeo1_source_up{source="aroi"} 0', content)
        # Meta always present
        self.assertIn("aeo1_build_info", content)
        self.assertIn("aeo1_generation_timestamp_seconds", content)

    def test_last_success_timestamp_zero_when_none(self):
        rs = _make_relay_set([], exit_dns_health_data=None, aroi_validation_data=None)
        with tempfile.TemporaryDirectory() as td:
            generate_prometheus_metrics(rs, td)
            with open(os.path.join(td, "metrics")) as f:
                content = f.read()
        self.assertIn('aeo1_source_last_success_timestamp_seconds{source="exitdnshealth"} 0', content)
        self.assertIn('aeo1_source_last_success_timestamp_seconds{source="aroi"} 0', content)


# ---------------------------------------------------------------------------
# Tests: meta and file integrity
# ---------------------------------------------------------------------------

class TestMetaAndFile(unittest.TestCase):

    def test_build_info_present(self):
        rs = _make_relay_set([], exit_dns_health_data=_sample_dns_metadata())
        with tempfile.TemporaryDirectory() as td:
            generate_prometheus_metrics(rs, td)
            with open(os.path.join(td, "metrics")) as f:
                content = f.read()
        self.assertIn(f'aeo1_build_info{{schema="{SCHEMA_VERSION}",generator="allium"}} 1', content)

    def test_generation_timestamp_recent(self):
        rs = _make_relay_set([])
        with tempfile.TemporaryDirectory() as td:
            before = int(time.time())
            generate_prometheus_metrics(rs, td)
            after = int(time.time())
            with open(os.path.join(td, "metrics")) as f:
                content = f.read()
        match = re.search(r'aeo1_generation_timestamp_seconds (\d+)', content)
        self.assertIsNotNone(match)
        ts = int(match.group(1))
        self.assertGreaterEqual(ts, before)
        self.assertLessEqual(ts, after)

    def test_file_exists(self):
        rs = _make_relay_set([])
        with tempfile.TemporaryDirectory() as td:
            generate_prometheus_metrics(rs, td)
            self.assertTrue(os.path.exists(os.path.join(td, "metrics")))

    def test_no_tmp_file_left(self):
        rs = _make_relay_set([])
        with tempfile.TemporaryDirectory() as td:
            generate_prometheus_metrics(rs, td)
            self.assertFalse(os.path.exists(os.path.join(td, "metrics.tmp")))

    def test_unique_help_type_per_metric(self):
        rs = _make_relay_set(
            [_make_relay("AAAA",
                         contact="url:https://x.com proof:uri-rsa ciissversion:2")],
            exit_dns_health_data=_sample_dns_metadata(),
            aroi_validation_data=_sample_aroi_data(),
        )
        with tempfile.TemporaryDirectory() as td:
            generate_prometheus_metrics(rs, td)
            with open(os.path.join(td, "metrics")) as f:
                content = f.read()

        # Each metric name should have exactly one HELP and one TYPE
        help_counts = {}
        type_counts = {}
        for line in content.split("\n"):
            if line.startswith("# HELP "):
                name = line.split()[2]
                help_counts[name] = help_counts.get(name, 0) + 1
            elif line.startswith("# TYPE "):
                name = line.split()[2]
                type_counts[name] = type_counts.get(name, 0) + 1

        for name, count in help_counts.items():
            self.assertEqual(count, 1, f"Duplicate HELP for {name}")
        for name, count in type_counts.items():
            self.assertEqual(count, 1, f"Duplicate TYPE for {name}")

    def test_eof_marker(self):
        rs = _make_relay_set([])
        with tempfile.TemporaryDirectory() as td:
            generate_prometheus_metrics(rs, td)
            with open(os.path.join(td, "metrics")) as f:
                content = f.read()
        self.assertIn("# EOF", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
