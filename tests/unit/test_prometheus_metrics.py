"""
Unit tests for allium.lib.prometheus_metrics (schema v2).
"""

import os
import re
import sys
import tempfile
import time
import unittest

# Add test utilities to path
sys.path.insert(0, os.path.dirname(__file__))
# Add the allium package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "allium"))

from lib.prometheus_metrics import (  # noqa: E402
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
from prometheus_fixtures import (  # noqa: E402
    make_relay as _make_relay,
    make_relay_set as _make_relay_set,
    sample_aroi_data as _sample_aroi_data,
    sample_dns_metadata as _sample_dns_metadata,
)


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
# Tests: numeric coercion
# ---------------------------------------------------------------------------

class TestSafeNumeric(unittest.TestCase):
    def test_int(self):
        self.assertEqual(_safe_numeric(42), "42")

    def test_zero(self):
        self.assertEqual(_safe_numeric(0), "0")

    def test_float(self):
        self.assertEqual(_safe_numeric(3.14), "3.14")

    def test_string_number(self):
        self.assertEqual(_safe_numeric("99"), "99.0")

    def test_non_numeric_string(self):
        self.assertEqual(_safe_numeric("hello"), "0")

    def test_injection_attempt(self):
        self.assertEqual(_safe_numeric("1\naeo1_injected_metric 42"), "0")

    def test_none(self):
        self.assertEqual(_safe_numeric(None), "0")

    def test_nan(self):
        self.assertEqual(_safe_numeric(float("nan")), "0")

    def test_inf(self):
        self.assertEqual(_safe_numeric(float("inf")), "0")

    def test_negative_inf(self):
        self.assertEqual(_safe_numeric(float("-inf")), "0")

    def test_bool_false(self):
        self.assertEqual(_safe_numeric(False), "0.0")

    def test_bool_true(self):
        self.assertEqual(_safe_numeric(True), "1.0")


# ---------------------------------------------------------------------------
# Tests: helpers
# ---------------------------------------------------------------------------

class TestGetFamilyId(unittest.TestCase):
    def test_found(self):
        rs = _make_relay_set([], fp_to_family_key={"AAAA": "FAMKEY1"})
        self.assertEqual(_get_family_id(rs, "AAAA"), "FAMKEY1")
        self.assertEqual(_get_family_id(rs, "aaaa"), "FAMKEY1")

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


class TestBuildAroiMap(unittest.TestCase):
    def test_map_uses_uppercase_fingerprints(self):
        rs = _make_relay_set([], aroi_validation_data=_sample_aroi_data())
        amap = _build_aroi_map(rs)
        self.assertIn("AAAA", amap)
        self.assertIn("BBBB", amap)
        self.assertTrue(amap["AAAA"]["valid"])
        self.assertFalse(amap["BBBB"]["valid"])


# ---------------------------------------------------------------------------
# Tests: DNS health section
# ---------------------------------------------------------------------------

class TestDnsHealthMetrics(unittest.TestCase):
    def _generate(self, relays, dns_data=None, aroi_data=None, fp_to_family=None, validated_domains=None):
        rs = _make_relay_set(
            relays,
            exit_dns_health_data=dns_data or _sample_dns_metadata(),
            aroi_validation_data=aroi_data,
            fp_to_family_key=fp_to_family or {},
            validated_aroi_domains=validated_domains or set(),
        )
        with tempfile.TemporaryDirectory() as td:
            stats = generate_prometheus_metrics(rs, td)
            with open(os.path.join(td, "metrics"), encoding="utf-8") as f:
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
        self.assertNotIn('aeo1_exit_dns_latency_ms{fingerprint="CCCC"', content)

    def test_untested_relay_not_marked_failed(self):
        relays = [_make_relay("DDDD", dns_status="untested", dns_timing=None)]
        content, _ = self._generate(relays)
        self.assertIn('aeo1_exit_dns_failed{fingerprint="DDDD",familyid="",status="untested"} 0', content)
        self.assertNotIn('aeo1_exit_dns_latency_ms{fingerprint="DDDD"', content)

    def test_non_exit_excluded(self):
        relays = [
            _make_relay("AAAA", flags=["Guard", "Running"]),
            _make_relay("BBBB", flags=["Exit", "Running"]),
        ]
        content, stats = self._generate(relays, aroi_data=_sample_aroi_data())
        self.assertEqual(stats["exit_relays"], 1)
        self.assertNotIn('aeo1_exit_dns_failed{fingerprint="AAAA"', content)

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
        content, _ = self._generate(relays, aroi_data=aroi_data, validated_domains={"example.com"})
        self.assertIn('verifiedaroi="example.com"', content)

    def test_sorted_by_fingerprint(self):
        relays = [_make_relay("CCCC"), _make_relay("AAAA"), _make_relay("BBBB")]
        content, _ = self._generate(relays, aroi_data=_sample_aroi_data())
        fps = re.findall(r'aeo1_exit_dns_failed\{fingerprint="(\w+)"', content)
        self.assertEqual(fps, sorted(fps))


# ---------------------------------------------------------------------------
# Tests: AROI section (schema v2)
# ---------------------------------------------------------------------------

class TestAroiStateMetrics(unittest.TestCase):
    def _generate(self, relays, aroi_data=None, fp_to_family=None):
        rs = _make_relay_set(
            relays,
            exit_dns_health_data=_sample_dns_metadata(),
            aroi_validation_data=aroi_data or _sample_aroi_data(),
            fp_to_family_key=fp_to_family or {},
        )
        with tempfile.TemporaryDirectory() as td:
            stats = generate_prometheus_metrics(rs, td)
            with open(os.path.join(td, "metrics"), encoding="utf-8") as f:
                content = f.read()
        return content, stats

    def test_state_configured_checked_valid(self):
        relay = _make_relay("AAAA", contact="url:https://example.com proof:uri-rsa ciissversion:2", aroi_domain="example.com")
        content, _ = self._generate([relay], aroi_data=_sample_aroi_data())
        self.assertIn('aeo1_aroi_relay_state{fingerprint="AAAA",familyid="",state="configured_checked_valid"} 1', content)

    def test_state_configured_checked_invalid(self):
        relay = _make_relay("BBBB", contact="url:https://broken.org proof:dns-rsa ciissversion:2", aroi_domain="broken.org")
        content, _ = self._generate([relay], aroi_data=_sample_aroi_data())
        self.assertIn('aeo1_aroi_relay_state{fingerprint="BBBB",familyid="",state="configured_checked_invalid"} 1', content)

    def test_state_configured_unchecked(self):
        relay = _make_relay("CCCC", contact="url:https://missing.org proof:dns-rsa ciissversion:2", aroi_domain="missing.org")
        content, _ = self._generate([relay], aroi_data=_sample_aroi_data())
        self.assertIn('aeo1_aroi_relay_state{fingerprint="CCCC",familyid="",state="configured_unchecked"} 1', content)

    def test_state_not_configured(self):
        relay = _make_relay("DDDD", contact="just a contact")
        content, _ = self._generate([relay], aroi_data=_sample_aroi_data())
        self.assertIn('aeo1_aroi_relay_state{fingerprint="DDDD",familyid="",state="not_configured"} 1', content)

    def test_exactly_one_state_series_per_relay(self):
        relays = [
            _make_relay("AAAA", contact="url:https://example.com proof:uri-rsa ciissversion:2", aroi_domain="example.com"),
            _make_relay("BBBB", contact="url:https://broken.org proof:dns-rsa ciissversion:2", aroi_domain="broken.org"),
            _make_relay("CCCC", contact="url:https://missing.org proof:dns-rsa ciissversion:2", aroi_domain="missing.org"),
            _make_relay("DDDD", contact="plain"),
        ]
        content, _ = self._generate(relays, aroi_data=_sample_aroi_data())
        for fp in ("AAAA", "BBBB", "CCCC", "DDDD"):
            matches = re.findall(
                rf'^aeo1_aroi_relay_state\{{fingerprint="{fp}",familyid="",state="[^"]+"\}} 1$',
                content,
                re.MULTILINE,
            )
            self.assertEqual(len(matches), 1, f"expected exactly one state for {fp}")

    def test_aggregate_state_counts(self):
        relays = [
            _make_relay("AAAA", contact="url:https://example.com proof:uri-rsa ciissversion:2", aroi_domain="example.com"),
            _make_relay("BBBB", contact="url:https://broken.org proof:dns-rsa ciissversion:2", aroi_domain="broken.org"),
            _make_relay("CCCC", contact="url:https://missing.org proof:dns-rsa ciissversion:2", aroi_domain="missing.org"),
            _make_relay("DDDD", contact="plain"),
        ]
        content, stats = self._generate(relays, aroi_data=_sample_aroi_data())
        self.assertEqual(stats["aroi_relays"], 3)
        self.assertIn('aeo1_aroi_relays_count{state="not_configured"} 1', content)
        self.assertIn('aeo1_aroi_relays_count{state="configured_unchecked"} 1', content)
        self.assertIn('aeo1_aroi_relays_count{state="configured_checked_invalid"} 1', content)
        self.assertIn('aeo1_aroi_relays_count{state="configured_checked_valid"} 1', content)

    def test_legacy_aroi_valid_removed(self):
        relay = _make_relay("AAAA", contact="url:https://example.com proof:uri-rsa ciissversion:2", aroi_domain="example.com")
        content, _ = self._generate([relay], aroi_data=_sample_aroi_data())
        self.assertNotIn("aeo1_aroi_valid{", content)
        self.assertNotIn("aeo1_aroi_success_ratio", content)

    def test_relay_info_uses_claimed_domain_when_unchecked(self):
        relay = _make_relay("CCCC", nickname="RelayC", contact="url:https://missing.org proof:dns-rsa ciissversion:2", aroi_domain="missing.org")
        content, _ = self._generate([relay], aroi_data=_sample_aroi_data())
        line = next((ln for ln in content.split("\n") if ln.startswith('aeo1_aroi_relay_info{fingerprint="CCCC"')), "")
        self.assertIn('domain="missing.org"', line)


# ---------------------------------------------------------------------------
# Tests: source availability
# ---------------------------------------------------------------------------

class TestSourceAvailability(unittest.TestCase):
    def test_both_sources_up(self):
        rs = _make_relay_set(
            [_make_relay("AAAA", contact="url:https://example.com proof:uri-rsa ciissversion:2", aroi_domain="example.com")],
            exit_dns_health_data=_sample_dns_metadata(),
            aroi_validation_data=_sample_aroi_data(),
        )
        with tempfile.TemporaryDirectory() as td:
            generate_prometheus_metrics(rs, td)
            with open(os.path.join(td, "metrics"), encoding="utf-8") as f:
                content = f.read()
        self.assertIn('aeo1_source_up{source="exitdnshealth"} 1', content)
        self.assertIn('aeo1_source_up{source="aroi"} 1', content)

    def test_dns_source_down(self):
        rs = _make_relay_set(
            [_make_relay("AAAA", contact="url:https://example.com proof:uri-rsa ciissversion:2", aroi_domain="example.com")],
            exit_dns_health_data=None,
            aroi_validation_data=_sample_aroi_data(),
        )
        with tempfile.TemporaryDirectory() as td:
            generate_prometheus_metrics(rs, td)
            with open(os.path.join(td, "metrics"), encoding="utf-8") as f:
                content = f.read()
        self.assertIn('aeo1_source_up{source="exitdnshealth"} 0', content)
        self.assertIn('aeo1_source_up{source="aroi"} 1', content)
        self.assertNotIn("aeo1_exit_dns_failed", content)

    def test_aroi_source_down(self):
        rs = _make_relay_set(
            [_make_relay("AAAA", contact="url:https://example.com proof:uri-rsa ciissversion:2", aroi_domain="example.com")],
            exit_dns_health_data=_sample_dns_metadata(),
            aroi_validation_data=None,
        )
        with tempfile.TemporaryDirectory() as td:
            generate_prometheus_metrics(rs, td)
            with open(os.path.join(td, "metrics"), encoding="utf-8") as f:
                content = f.read()
        self.assertIn('aeo1_source_up{source="exitdnshealth"} 1', content)
        self.assertIn('aeo1_source_up{source="aroi"} 0', content)
        self.assertNotIn("aeo1_aroi_relay_state", content)
        self.assertNotIn("aeo1_aroi_relays_count", content)

    def test_both_sources_down(self):
        rs = _make_relay_set(
            [_make_relay("AAAA")],
            exit_dns_health_data=None,
            aroi_validation_data=None,
        )
        with tempfile.TemporaryDirectory() as td:
            generate_prometheus_metrics(rs, td)
            with open(os.path.join(td, "metrics"), encoding="utf-8") as f:
                content = f.read()
        self.assertIn('aeo1_source_up{source="exitdnshealth"} 0', content)
        self.assertIn('aeo1_source_up{source="aroi"} 0', content)
        self.assertIn("aeo1_build_info", content)
        self.assertIn("aeo1_generation_timestamp_seconds", content)


# ---------------------------------------------------------------------------
# Tests: meta and file integrity
# ---------------------------------------------------------------------------

class TestMetaAndFile(unittest.TestCase):
    def test_build_info_present_schema_v2(self):
        rs = _make_relay_set([], exit_dns_health_data=_sample_dns_metadata())
        with tempfile.TemporaryDirectory() as td:
            generate_prometheus_metrics(rs, td)
            with open(os.path.join(td, "metrics"), encoding="utf-8") as f:
                content = f.read()
        self.assertIn(f'aeo1_build_info{{schema="{SCHEMA_VERSION}",generator="allium"}} 1', content)
        self.assertEqual(SCHEMA_VERSION, "2")

    def test_generation_timestamp_recent(self):
        rs = _make_relay_set([])
        with tempfile.TemporaryDirectory() as td:
            before = int(time.time())
            generate_prometheus_metrics(rs, td)
            after = int(time.time())
            with open(os.path.join(td, "metrics"), encoding="utf-8") as f:
                content = f.read()
        match = re.search(r"aeo1_generation_timestamp_seconds (\d+)", content)
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
        relay = _make_relay("AAAA", contact="url:https://example.com proof:uri-rsa ciissversion:2", aroi_domain="example.com")
        rs = _make_relay_set([relay], exit_dns_health_data=_sample_dns_metadata(), aroi_validation_data=_sample_aroi_data())
        with tempfile.TemporaryDirectory() as td:
            generate_prometheus_metrics(rs, td)
            with open(os.path.join(td, "metrics"), encoding="utf-8") as f:
                content = f.read()

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
            with open(os.path.join(td, "metrics"), encoding="utf-8") as f:
                content = f.read()
        self.assertIn("# EOF", content)


# ---------------------------------------------------------------------------
# Regression tests
# ---------------------------------------------------------------------------

class TestParseTimestampEpoch(unittest.TestCase):
    def test_z_suffix(self):
        from datetime import datetime, timezone

        expected = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc).timestamp()
        self.assertEqual(_parse_timestamp_epoch("2026-03-08T12:00:00Z"), expected)

    def test_offset_suffix(self):
        from datetime import datetime, timezone

        expected = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc).timestamp()
        self.assertEqual(_parse_timestamp_epoch("2026-03-08T12:00:00+00:00"), expected)

    def test_naive_timestamp_assumed_utc(self):
        from datetime import datetime, timezone

        expected = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc).timestamp()
        self.assertEqual(_parse_timestamp_epoch("2026-03-08T12:00:00"), expected)

    def test_empty_returns_zero(self):
        self.assertEqual(_parse_timestamp_epoch(""), 0)
        self.assertEqual(_parse_timestamp_epoch(None), 0)

    def test_numeric_passthrough(self):
        self.assertEqual(_parse_timestamp_epoch("1234567890"), 1234567890.0)


class TestDnsErrorTypesComplete(unittest.TestCase):
    def test_dns_error_and_unknown_emitted(self):
        rs = _make_relay_set(
            [_make_relay("AAAA")],
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
        with tempfile.TemporaryDirectory() as td:
            generate_prometheus_metrics(rs, td)
            with open(os.path.join(td, "metrics"), encoding="utf-8") as f:
                content = f.read()

        self.assertIn('aeo1_exit_dns_errors_count{error_type="error"} 7', content)
        self.assertIn('aeo1_exit_dns_errors_count{error_type="unknown"} 3', content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
