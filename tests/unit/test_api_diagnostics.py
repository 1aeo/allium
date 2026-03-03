"""
Tests for allium.lib.api_diagnostics module.

Tests the freshness classification logic, formatting helpers,
diagnostics collection, and dependency mapping.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from allium.lib.api_diagnostics import (
    _classify_freshness,
    _format_age,
    _format_time_ago,
    _format_timestamp,
    _short_name,
    _worst_freshness,
    _is_api_enabled,
    collect_api_diagnostics,
    API_METADATA,
    SECTION_DEPENDENCIES,
)


# ============================================================================
# Freshness Classification
# ============================================================================


class TestClassifyFreshness:
    """Test freshness classification logic."""

    def test_fresh_when_well_below_half(self):
        """Cache at 10% of max age should be fresh."""
        # 6h max, 36 min old = 10%
        assert _classify_freshness(36 * 60, 6, "ready") == "fresh"

    def test_fresh_at_boundary(self):
        """Cache at just under 50% of max age should be fresh."""
        max_hours = 6
        just_under_half = (max_hours * 3600 * 0.5) - 1
        assert _classify_freshness(just_under_half, max_hours, "ready") == "fresh"

    def test_fresh_at_exactly_half(self):
        """Cache at exactly 50% of max age is fresh (boundary: > 50% = aging)."""
        max_hours = 6
        exactly_half = max_hours * 3600 * 0.5
        assert _classify_freshness(exactly_half, max_hours, "ready") == "fresh"

    def test_aging_just_over_half(self):
        """Cache just over 50% of max age should be aging."""
        max_hours = 6
        just_over_half = max_hours * 3600 * 0.5 + 1
        assert _classify_freshness(just_over_half, max_hours, "ready") == "aging"

    def test_aging_at_75_percent(self):
        """Cache at 75% of max age should be aging."""
        max_hours = 12
        at_75 = max_hours * 3600 * 0.75
        assert _classify_freshness(at_75, max_hours, "ready") == "aging"

    def test_aging_just_under_max(self):
        """Cache at just under 100% of max age should be aging."""
        max_hours = 1
        just_under = (max_hours * 3600) - 1
        assert _classify_freshness(just_under, max_hours, "ready") == "aging"

    def test_stale_when_exceeded(self):
        """Cache exceeding max age should be stale."""
        max_hours = 1
        exceeded = max_hours * 3600 + 1
        assert _classify_freshness(exceeded, max_hours, "ready") == "stale"

    def test_stale_when_worker_stale(self):
        """Worker status 'stale' always means stale regardless of cache age."""
        # Even with very fresh cache, stale worker means stale
        assert _classify_freshness(60, 6, "stale") == "stale"

    def test_stale_worker_with_no_cache(self):
        """Stale worker with no cache should be stale."""
        assert _classify_freshness(None, 6, "stale") == "stale"

    def test_unavailable_no_cache_no_worker(self):
        """No cache and no worker status should be unavailable."""
        assert _classify_freshness(None, 6, None) == "unavailable"

    def test_unavailable_no_cache_with_unknown_worker(self):
        """No cache with unknown worker should still check: no cache + no worker = unavailable."""
        # worker_status is not None (it's "unknown"), so it won't hit the unavailable path
        # But cache_age is None, so it goes to the cache check
        assert _classify_freshness(None, 6, "unknown") == "unavailable"


# ============================================================================
# Formatting Helpers
# ============================================================================


class TestFormatAge:
    """Test age formatting."""

    def test_none(self):
        assert _format_age(None) == "N/A"

    def test_seconds(self):
        assert _format_age(45) == "45s"

    def test_minutes(self):
        assert _format_age(180) == "3.0 min"

    def test_hours(self):
        assert _format_age(7200) == "2.0h"

    def test_many_hours(self):
        assert _format_age(90000) == "25.0h"


class TestFormatTimeAgo:
    """Test time-ago formatting."""

    def test_none(self):
        assert _format_time_ago(None) == "N/A"

    def test_seconds(self):
        assert _format_time_ago(30) == "30s ago"

    def test_minutes(self):
        assert _format_time_ago(180) == "3 min ago"

    def test_hours(self):
        assert _format_time_ago(7200) == "2h 0min ago"

    def test_hours_and_minutes(self):
        assert _format_time_ago(7500) == "2h 5min ago"


class TestFormatTimestamp:
    """Test timestamp formatting."""

    def test_none(self):
        assert _format_timestamp(None) == "N/A"

    def test_epoch(self):
        # Known epoch: 2026-01-01 00:00:00 UTC = 1767225600
        result = _format_timestamp(1767225600)
        assert "2026" in result
        assert "GMT" in result


# ============================================================================
# Helper Functions
# ============================================================================


class TestShortName:
    """Test short name mapping."""

    def test_known_apis(self):
        assert _short_name("onionoo_details") == "Details"
        assert _short_name("onionoo_uptime") == "Uptime"
        assert _short_name("onionoo_bandwidth") == "Bandwidth"
        assert _short_name("aroi_validation") == "AROI Validation"
        assert _short_name("collector_consensus") == "Consensus"
        assert _short_name("collector_descriptors") == "Descriptors"

    def test_unknown_api(self):
        assert _short_name("unknown_api") == "unknown_api"


class TestWorstFreshness:
    """Test worst freshness calculation."""

    def test_empty_list(self):
        assert _worst_freshness([]) == "unavailable"

    def test_all_fresh(self):
        assert _worst_freshness(["fresh", "fresh", "fresh"]) == "fresh"

    def test_one_aging(self):
        assert _worst_freshness(["fresh", "aging", "fresh"]) == "aging"

    def test_one_stale(self):
        assert _worst_freshness(["fresh", "aging", "stale"]) == "stale"

    def test_stale_beats_all(self):
        assert _worst_freshness(["stale", "fresh"]) == "stale"

    def test_unavailable_between_aging_and_fresh(self):
        assert _worst_freshness(["fresh", "unavailable"]) == "unavailable"
        assert _worst_freshness(["aging", "unavailable"]) == "aging"


class TestIsApiEnabled:
    """Test API enabled check."""

    def test_details_always_enabled(self):
        assert _is_api_enabled("onionoo_details", "details") is True
        assert _is_api_enabled("onionoo_details", "all") is True

    def test_uptime_only_with_all(self):
        assert _is_api_enabled("onionoo_uptime", "details") is False
        assert _is_api_enabled("onionoo_uptime", "all") is True

    def test_bandwidth_only_with_all(self):
        assert _is_api_enabled("onionoo_bandwidth", "details") is False
        assert _is_api_enabled("onionoo_bandwidth", "all") is True

    def test_aroi_only_with_all(self):
        assert _is_api_enabled("aroi_validation", "details") is False
        assert _is_api_enabled("aroi_validation", "all") is True


# ============================================================================
# Metadata Registry Completeness
# ============================================================================


class TestMetadataRegistry:
    """Test API metadata registry structure."""

    def test_all_six_apis_present(self):
        expected = {
            "onionoo_details", "onionoo_uptime", "onionoo_bandwidth",
            "aroi_validation", "collector_consensus", "collector_descriptors",
        }
        assert set(API_METADATA.keys()) == expected

    def test_required_fields_present(self):
        required_fields = [
            "display_name", "owner", "default_url", "expected_frequency",
            "cache_max_age_hours", "count_field", "count_label", "affected_sections",
        ]
        for api_name, metadata in API_METADATA.items():
            for field in required_fields:
                assert field in metadata, f"{api_name} missing {field}"

    def test_affected_sections_not_empty(self):
        for api_name, metadata in API_METADATA.items():
            assert len(metadata["affected_sections"]) > 0, f"{api_name} has no affected sections"


class TestSectionDependencies:
    """Test section dependency map structure."""

    def test_all_dependencies_reference_known_apis(self):
        known_apis = set(API_METADATA.keys())
        for dep in SECTION_DEPENDENCIES:
            for api in dep["apis"]:
                assert api in known_apis, f"Dependency '{dep['section']}' references unknown API '{api}'"

    def test_all_sections_have_at_least_one_dependency(self):
        for dep in SECTION_DEPENDENCIES:
            assert len(dep["apis"]) > 0, f"Section '{dep['section']}' has no API dependencies"

    def test_required_fields(self):
        for dep in SECTION_DEPENDENCIES:
            assert "section" in dep
            assert "apis" in dep


# ============================================================================
# Full Diagnostics Collection
# ============================================================================


class TestCollectApiDiagnostics:
    """Test the main diagnostics collection function."""

    def _make_mock_relay_set(self):
        """Create a minimal mock relay set."""
        relay_set = MagicMock()
        relay_set.json = {"relays": [{"fingerprint": "AAAA"}, {"fingerprint": "BBBB"}]}
        relay_set.timestamp = "Mon, 02 Mar 2026 15:30:00 GMT"
        relay_set.uptime_data = {"relays": [{"fingerprint": "AAAA"}]}
        relay_set.bandwidth_data = {"relays": [{"fingerprint": "AAAA"}]}
        relay_set.aroi_validation_data = {"results": [{"domain": "test.com"}], "metadata": {}, "statistics": {}}
        relay_set.collector_consensus_data = {"relay_index": {"AAAA": {}}, "votes": {"auth1": {}}}
        relay_set.collector_descriptors_data = {
            "all_seen_fingerprints": ["AAAA", "BBBB"],
            "family_cert_fingerprints": ["AAAA"],
        }
        return relay_set

    def _make_mock_args(self):
        """Create a minimal mock args namespace."""
        args = MagicMock()
        args.enabled_apis = "all"
        args.onionoo_details_url = "https://onionoo.torproject.org/details"
        args.onionoo_uptime_url = "https://onionoo.torproject.org/uptime"
        args.onionoo_bandwidth_url = "https://onionoo.torproject.org/bandwidth"
        args.aroi_url = "https://aroivalidator.1aeo.com/latest.json"
        return args

    @patch("allium.lib.api_diagnostics.get_all_worker_status")
    @patch("allium.lib.api_diagnostics._cache_manager")
    def test_returns_correct_structure(self, mock_cache, mock_status):
        """Verify the returned dict has all expected top-level keys."""
        mock_status.return_value = {}
        mock_cache.get_cache_age.return_value = 60  # 1 minute old

        result = collect_api_diagnostics(self._make_mock_relay_set(), self._make_mock_args())

        assert "apis" in result
        assert "section_dependencies" in result
        assert "overall_status" in result
        assert "overall_status_label" in result
        assert "enabled_count" in result
        assert "total_count" in result
        assert "site_generated" in result
        assert "apis_mode" in result

    @patch("allium.lib.api_diagnostics.get_all_worker_status")
    @patch("allium.lib.api_diagnostics._cache_manager")
    def test_six_apis_returned(self, mock_cache, mock_status):
        """Should return diagnostics for all 6 APIs."""
        mock_status.return_value = {}
        mock_cache.get_cache_age.return_value = 60

        result = collect_api_diagnostics(self._make_mock_relay_set(), self._make_mock_args())
        assert len(result["apis"]) == 6

    @patch("allium.lib.api_diagnostics.get_all_worker_status")
    @patch("allium.lib.api_diagnostics._cache_manager")
    def test_all_fresh_when_cache_young(self, mock_cache, mock_status):
        """All APIs fresh when cache is very young."""
        mock_status.return_value = {
            name: {"status": "ready", "timestamp": time.time(), "error": None}
            for name in API_METADATA
        }
        mock_cache.get_cache_age.return_value = 60  # 1 minute

        result = collect_api_diagnostics(self._make_mock_relay_set(), self._make_mock_args())
        assert result["overall_status"] == "fresh"
        assert "ALL SYSTEMS FRESH" in result["overall_status_label"]

    @patch("allium.lib.api_diagnostics.get_all_worker_status")
    @patch("allium.lib.api_diagnostics._cache_manager")
    def test_stale_when_worker_stale(self, mock_cache, mock_status):
        """Overall should be stale if any worker is stale."""
        statuses = {
            name: {"status": "ready", "timestamp": time.time(), "error": None}
            for name in API_METADATA
        }
        statuses["aroi_validation"] = {
            "status": "stale", "timestamp": time.time(), "error": "timeout"
        }
        mock_status.return_value = statuses
        mock_cache.get_cache_age.return_value = 60

        result = collect_api_diagnostics(self._make_mock_relay_set(), self._make_mock_args())
        assert result["overall_status"] == "stale"
        assert "STALE" in result["overall_status_label"]

    @patch("allium.lib.api_diagnostics.get_all_worker_status")
    @patch("allium.lib.api_diagnostics._cache_manager")
    def test_per_api_fields(self, mock_cache, mock_status):
        """Each API diagnostic should have all required display fields."""
        mock_status.return_value = {}
        mock_cache.get_cache_age.return_value = 120

        result = collect_api_diagnostics(self._make_mock_relay_set(), self._make_mock_args())

        required_fields = [
            "name", "display_name", "url", "owner", "expected_frequency",
            "cache_max_age_hours", "cache_age_display", "freshness",
            "item_count", "enabled", "affected_sections", "cache_pct",
        ]
        for api in result["apis"]:
            for field in required_fields:
                assert field in api, f"API '{api['name']}' missing field '{field}'"

    @patch("allium.lib.api_diagnostics.get_all_worker_status")
    @patch("allium.lib.api_diagnostics._cache_manager")
    def test_section_dependencies_populated(self, mock_cache, mock_status):
        """Section dependencies should be populated with freshness data."""
        mock_status.return_value = {}
        mock_cache.get_cache_age.return_value = 60

        result = collect_api_diagnostics(self._make_mock_relay_set(), self._make_mock_args())

        assert len(result["section_dependencies"]) == len(SECTION_DEPENDENCIES)
        for dep in result["section_dependencies"]:
            assert "section" in dep
            assert "apis" in dep
            assert "worst_freshness" in dep
            for api in dep["apis"]:
                assert "short_name" in api
                assert "freshness" in api

    @patch("allium.lib.api_diagnostics.get_all_worker_status")
    @patch("allium.lib.api_diagnostics._cache_manager")
    def test_disabled_apis_marked_unavailable(self, mock_cache, mock_status):
        """APIs not enabled by --apis mode should be marked unavailable."""
        mock_status.return_value = {}
        mock_cache.get_cache_age.return_value = 60

        args = self._make_mock_args()
        args.enabled_apis = "details"  # Only details mode

        result = collect_api_diagnostics(self._make_mock_relay_set(), args)

        details_api = next(a for a in result["apis"] if a["name"] == "onionoo_details")
        assert details_api["enabled"] is True
        assert details_api["freshness"] == "fresh"

        uptime_api = next(a for a in result["apis"] if a["name"] == "onionoo_uptime")
        assert uptime_api["enabled"] is False
        assert uptime_api["freshness"] == "unavailable"
