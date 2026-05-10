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
    """Test short name mapping in API_METADATA."""

    def test_known_apis(self):
        assert API_METADATA["onionoo_details"]["short_name"] == "Details"
        assert API_METADATA["onionoo_uptime"]["short_name"] == "Uptime"
        assert API_METADATA["onionoo_bandwidth"]["short_name"] == "Bandwidth"
        assert API_METADATA["aroi_validation"]["short_name"] == "AROI Validation"
        assert API_METADATA["collector_consensus"]["short_name"] == "Consensus"
        assert API_METADATA["collector_descriptors"]["short_name"] == "Descriptors"

    def test_all_apis_have_short_name(self):
        for api_name, metadata in API_METADATA.items():
            assert "short_name" in metadata, f"{api_name} missing short_name"
            assert len(metadata["short_name"]) > 0, f"{api_name} has empty short_name"


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
            "display_name", "short_name", "owner", "default_url", "expected_frequency",
            "cache_max_age_hours", "cache_max_age_display", "relay_set_attr",
            "count_field", "count_label", "affected_sections",
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
    @patch("allium.lib.api_diagnostics.get_cache_age")
    def test_returns_correct_structure(self, mock_cache_age, mock_status):
        """Verify the returned dict has all expected top-level keys."""
        mock_status.return_value = {}
        mock_cache_age.return_value = 60  # 1 minute old

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
    @patch("allium.lib.api_diagnostics.get_cache_age")
    def test_six_apis_returned(self, mock_cache_age, mock_status):
        """Should return diagnostics for all 6 APIs."""
        mock_status.return_value = {}
        mock_cache_age.return_value = 60

        result = collect_api_diagnostics(self._make_mock_relay_set(), self._make_mock_args())
        assert len(result["apis"]) == 6

    @patch("allium.lib.api_diagnostics.get_all_worker_status")
    @patch("allium.lib.api_diagnostics.get_cache_age")
    def test_all_fresh_when_cache_young(self, mock_cache_age, mock_status):
        """All APIs fresh when cache is very young."""
        mock_status.return_value = {
            name: {"status": "ready", "timestamp": time.time(), "error": None}
            for name in API_METADATA
        }
        mock_cache_age.return_value = 60  # 1 minute

        result = collect_api_diagnostics(self._make_mock_relay_set(), self._make_mock_args())
        assert result["overall_status"] == "fresh"
        assert "ALL SYSTEMS FRESH" in result["overall_status_label"]

    @patch("allium.lib.api_diagnostics.get_all_worker_status")
    @patch("allium.lib.api_diagnostics.get_cache_age")
    def test_stale_when_worker_stale(self, mock_cache_age, mock_status):
        """Overall should be stale if any worker is stale."""
        statuses = {
            name: {"status": "ready", "timestamp": time.time(), "error": None}
            for name in API_METADATA
        }
        statuses["aroi_validation"] = {
            "status": "stale", "timestamp": time.time(), "error": "timeout"
        }
        mock_status.return_value = statuses
        mock_cache_age.return_value = 60

        result = collect_api_diagnostics(self._make_mock_relay_set(), self._make_mock_args())
        assert result["overall_status"] == "stale"
        assert "STALE" in result["overall_status_label"]

    @patch("allium.lib.api_diagnostics.get_all_worker_status")
    @patch("allium.lib.api_diagnostics.get_cache_age")
    def test_per_api_fields(self, mock_cache_age, mock_status):
        """Each API diagnostic should have all required display fields."""
        mock_status.return_value = {}
        mock_cache_age.return_value = 120

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
    @patch("allium.lib.api_diagnostics.get_cache_age")
    def test_section_dependencies_populated(self, mock_cache_age, mock_status):
        """Section dependencies should be populated with freshness data."""
        mock_status.return_value = {}
        mock_cache_age.return_value = 60

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
    @patch("allium.lib.api_diagnostics.get_cache_age")
    def test_disabled_apis_marked_unavailable(self, mock_cache_age, mock_status):
        """APIs not enabled by --apis mode should be marked unavailable."""
        mock_status.return_value = {}
        mock_cache_age.return_value = 60

        args = self._make_mock_args()
        args.enabled_apis = "details"  # Only details mode

        result = collect_api_diagnostics(self._make_mock_relay_set(), args)

        details_api = next(a for a in result["apis"] if a["name"] == "onionoo_details")
        assert details_api["enabled"] is True
        assert details_api["freshness"] == "fresh"

        uptime_api = next(a for a in result["apis"] if a["name"] == "onionoo_uptime")
        assert uptime_api["enabled"] is False
        assert uptime_api["freshness"] == "unavailable"


# ============================================================================
# Item D: pre-formatted diagnostics rows (template-side simplification)
# ============================================================================


class TestProofTypeRowFormatter:
    """_format_proof_type_rows pre-builds template-ready rows so the
    api-diagnostics.html template doesn't need to do dictsort + 'familyid
    in pt' string-substring classification + zero-bucket filtering in
    Jinja. This locks the contract."""

    def test_v3_proof_types_get_blue_v3_badge(self):
        from allium.lib.api_diagnostics import _format_proof_type_rows
        rows = _format_proof_type_rows({
            'dns_familyid_ed25519': {'valid': 269, 'total': 269},
            'uri_familyid_ed25519': {'valid': 969, 'total': 978},
        })
        assert len(rows) == 2
        for r in rows:
            assert r['version'] == '3'
            assert r['badge_color'] == '#007bff'

    def test_v2_proof_types_get_grey_v2_badge(self):
        from allium.lib.api_diagnostics import _format_proof_type_rows
        rows = _format_proof_type_rows({
            'dns_rsa': {'valid': 211, 'total': 247},
            'uri_rsa': {'valid': 2571, 'total': 2971},
        })
        for r in rows:
            assert r['version'] == '2'
            assert r['badge_color'] == '#6c757d'

    def test_no_proof_bucket_excluded(self):
        from allium.lib.api_diagnostics import _format_proof_type_rows
        rows = _format_proof_type_rows({
            'dns_rsa': {'valid': 1, 'total': 1},
            'no_proof': {'valid': 0, 'total': 6248},
        })
        assert len(rows) == 1
        assert rows[0]['proof_type'] == 'dns_rsa'

    def test_zero_total_buckets_excluded(self):
        from allium.lib.api_diagnostics import _format_proof_type_rows
        rows = _format_proof_type_rows({
            'dns_rsa': {'valid': 0, 'total': 0},
            'uri_rsa': {'valid': 5, 'total': 10},
        })
        assert len(rows) == 1
        assert rows[0]['proof_type'] == 'uri_rsa'

    def test_alphabetical_sort_order(self):
        from allium.lib.api_diagnostics import _format_proof_type_rows
        rows = _format_proof_type_rows({
            'uri_rsa': {'valid': 1, 'total': 1},
            'dns_familyid_ed25519': {'valid': 1, 'total': 1},
            'dns_rsa': {'valid': 1, 'total': 1},
            'uri_familyid_ed25519': {'valid': 1, 'total': 1},
        })
        types = [r['proof_type'] for r in rows]
        assert types == sorted(types)

    def test_unknown_proof_type_falls_back_to_neutral_color(self):
        from allium.lib.api_diagnostics import _format_proof_type_rows
        rows = _format_proof_type_rows({
            'mystery_proof': {'valid': 1, 'total': 5},
        })
        assert rows[0]['version'] == 'unknown'
        assert rows[0]['badge_color'] == '#adb5bd'

    def test_non_dict_input_returns_empty(self):
        from allium.lib.api_diagnostics import _format_proof_type_rows
        assert _format_proof_type_rows(None) == []
        assert _format_proof_type_rows([]) == []


class TestCiissversionRowFormatter:
    """_format_ciissversion_rows pre-builds the version-declared row list
    with consistent ordering (numeric versions ascending, 'none' last)
    and is_none flag the template uses directly."""

    def test_numeric_versions_ascending(self):
        from allium.lib.api_diagnostics import _format_ciissversion_rows
        rows = _format_ciissversion_rows({'3': 1247, '1': 1, '2': 3376})
        keys = [r['key'] for r in rows]
        assert keys == ['1', '2', '3']

    def test_none_bucket_appears_last(self):
        from allium.lib.api_diagnostics import _format_ciissversion_rows
        rows = _format_ciissversion_rows({'2': 100, 'none': 50, '3': 200})
        assert rows[-1]['key'] == 'none'
        assert rows[-1]['is_none'] is True

    def test_v3_gets_blue_badge_v2_gets_grey(self):
        from allium.lib.api_diagnostics import _format_ciissversion_rows
        rows = _format_ciissversion_rows({'2': 1, '3': 1})
        v2 = next(r for r in rows if r['key'] == '2')
        v3 = next(r for r in rows if r['key'] == '3')
        assert v2['badge_color'] == '#6c757d'
        assert v3['badge_color'] == '#007bff'


# ============================================================================
# Item A: contact rankings index (precomputed once, reused per contact)
# ============================================================================


class TestContactRankingsIndex:
    """The legacy generate_contact_rankings(contact, relay_set) walked
    every leaderboard category × top-25 entries per contact, costing
    O(N_contacts × N_categories × 25). _build_contact_rankings_index
    builds the full {contact_hash: [rankings]} map in ONE pass; per-
    contact lookups are then O(1) dict access. This locks both the
    output equivalence and the cache behaviour."""

    def _mock_relay_set(self, leaderboards):
        rs = MagicMock()
        rs.json = {'aroi_leaderboards': {'leaderboards': leaderboards}}
        return rs

    def test_index_matches_legacy_output_for_each_contact(self):
        from allium.lib.operator_analysis import (
            generate_contact_rankings, _build_contact_rankings_index,
        )
        rs = self._mock_relay_set({
            'bandwidth': [('A', {}), ('B', {}), ('C', {})],
            'consensus_weight': [{'contact_hash': 'C'}, {'contact_hash': 'A'}],
            'exit_authority': [{'contact_hash': 'X'}],
        })
        index = _build_contact_rankings_index(rs)
        for contact in ('A', 'B', 'C', 'X', 'NONE'):
            fresh = generate_contact_rankings(contact, rs)
            cached = list(index.get(contact, []))
            assert [r['rank'] for r in fresh] == [r['rank'] for r in cached]
            assert [r['category'] for r in fresh] == [r['category'] for r in cached]

    def test_rankings_sorted_by_rank_ascending(self):
        from allium.lib.operator_analysis import generate_contact_rankings
        rs = self._mock_relay_set({
            # 'A' is rank-1 in bandwidth but rank-3 in consensus_weight
            'bandwidth': [('A', {}), ('B', {})],
            'consensus_weight': [('X', {}), ('Y', {}), ('A', {})],
        })
        rankings = generate_contact_rankings('A', rs)
        assert [r['rank'] for r in rankings] == [1, 3]

    def test_rank_capped_at_25(self):
        from allium.lib.operator_analysis import generate_contact_rankings
        # Place 'A' at rank 26 — should NOT appear in the rankings.
        rs = self._mock_relay_set({
            'bandwidth': [('OTHER', {})] * 25 + [('A', {})],
        })
        assert generate_contact_rankings('A', rs) == []

    def test_returns_copy_not_reference(self):
        """Mutating the returned list MUST NOT affect the cached index."""
        from allium.lib.operator_analysis import generate_contact_rankings
        rs = self._mock_relay_set({
            'bandwidth': [('A', {})],
        })
        first = generate_contact_rankings('A', rs)
        first.clear()
        second = generate_contact_rankings('A', rs)
        assert len(second) == 1, "cache was clobbered by external mutation"

    def test_cache_invalidated_on_leaderboards_replacement(self):
        from allium.lib.operator_analysis import generate_contact_rankings
        rs = self._mock_relay_set({
            'bandwidth': [('OLD', {})],
        })
        first = generate_contact_rankings('OLD', rs)
        assert first  # populates cache
        # Replace the leaderboards object — cache key (id of leaderboards
        # dict) should differ, so a fresh build kicks in.
        rs.json['aroi_leaderboards']['leaderboards'] = {
            'bandwidth': [('NEW', {})],
        }
        assert generate_contact_rankings('NEW', rs)
        assert generate_contact_rankings('OLD', rs) == []


# ============================================================================
# Item B: merged variants/total_data loop in compute_contact_display_data
# ============================================================================


class TestComputeContactDisplayDataMergedLoop:
    """compute_contact_display_data must produce identical contact_variants
    AND td_sums when items are folded into one members loop. The single-
    pass loop is a hot path during ~3,000 contact-page precomputes per
    build."""

    def test_variants_grouped_by_distinct_raw_contact_string(self):
        from allium.lib.operator_analysis import compute_contact_display_data
        members = [
            {'contact': 'STR_A', 'aroi_version': '2', 'aroi_proof_type': 'uri-rsa',
             'aroi_domain': 'mock.com', 'aroi_configured': True,
             'total_data': {'1_month': 10, '6_months': 20, '1_year': 50, '5_years': 100}},
            {'contact': 'STR_A', 'aroi_version': '2', 'aroi_proof_type': 'uri-rsa',
             'aroi_domain': 'mock.com', 'aroi_configured': True,
             'total_data': {'1_month': 5, '6_months': 10, '1_year': 25, '5_years': 50}},
            {'contact': 'STR_B', 'aroi_version': '3', 'aroi_proof_type': 'uri-familyid-ed25519',
             'aroi_domain': 'mock.com', 'aroi_configured': True,
             'total_data': {'1_month': 1, '6_months': 2, '1_year': 5, '5_years': 10}},
        ]
        # Build minimal mock `i` (the contact's sorted data).
        i = {k: 0 for k in (
            'bandwidth', 'guard_bandwidth', 'middle_bandwidth', 'exit_bandwidth',
            'consensus_weight_fraction', 'guard_consensus_weight_fraction',
            'middle_consensus_weight_fraction', 'exit_consensus_weight_fraction',
            'count', 'measured_count',
            'guard_count', 'middle_count', 'exit_count',
            'unique_as_count', 'unique_country_count',
        )}
        i['first_seen'] = '2025-01-01 00:00:00'

        # Mock relay_set with the methods needed by helpers.
        rs = MagicMock()
        rs.bandwidth_formatter.format_bandwidth_with_unit.return_value = '0'
        rs.json = {
            'network_health': {'network_total_data_by_period': {'1_year': 100}},
            'smart_context': {},
        }

        result = compute_contact_display_data(i, 'GB', None, 'mock_v', members, rs)
        # Two distinct ContactInfo strings under this operator.
        assert result['contact_variant_count'] == 2
        # Sorted by count desc — STR_A (2 relays) before STR_B (1 relay).
        assert result['contact_variants'][0]['raw'] == 'STR_A'
        assert result['contact_variants'][0]['count'] == 2
        assert result['contact_variants'][1]['raw'] == 'STR_B'
        assert result['contact_variants'][1]['count'] == 1
        # Total-data summed across all relays in same loop.
        assert result['total_data_formatted']  # non-empty

    def test_single_pass_over_members(self):
        """Source-level guarantee: only ONE 'for r in members' in
        compute_contact_display_data after the item B merge.

        Uses inspect.getsource() on the imported function instead of
        reading a hard-coded repo path, so the test works regardless
        of where the workspace is mounted (/workspace, /home/user,
        cloud-agent VM paths, contributor laptop, etc.).
        """
        import inspect
        from allium.lib.operator_analysis import compute_contact_display_data
        src = inspect.getsource(compute_contact_display_data)
        # Allow at most ONE member-loop in the function body.
        assert src.count('for r in members') == 1


# ============================================================================
# Item 3: contact_variant_count tracked during categorization
# ============================================================================


class TestContactVariantCountInCategorization:
    """Item 3: the relays-categorization pass tracks distinct ContactInfo
    strings per contact group via a set, exposing the count as
    sorted.contact[hash].contact_variant_count for variant-aware
    list-view tooltips."""

    def _make_relay(self, raw_contact):
        return {
            'fingerprint': 'F' * 40, 'contact': raw_contact, 'contact_md5': 'h1',
            'aroi_domain': 'x.com', 'flags': [],
            'observed_bandwidth': 100, 'consensus_weight': 1,
            'consensus_weight_fraction': 0.0,
            'guard_consensus_weight_fraction': 0.0,
            'middle_consensus_weight_fraction': 0.0,
            'exit_consensus_weight_fraction': 0.0,
            'first_seen': '2025-01-01 00:00:00',
            'country': 'US', 'platform': 'Linux', 'as': '111', 'as_name': '',
            'effective_family': [],
        }

    def _make_relay_set(self, relays):
        rs = MagicMock()
        rs.json = {
            'relays': relays,
            'sorted': {'contact': {}},
        }
        return rs

    def test_single_variant_count_eq_1(self):
        """Two relays with the SAME raw contact string -> count = 1."""
        from allium.lib.categorization import sort_relay
        relays = [self._make_relay('SAME'), self._make_relay('SAME')]
        rs = self._make_relay_set(relays)
        for idx, relay in enumerate(relays):
            sort_relay(rs, relay, idx, 'contact', 'h1', 1, 0.0)
        sorted_data = rs.json['sorted']['contact']['h1']
        assert sorted_data.get('contact_variant_count') == 1

    def test_two_variants_yields_count_2(self):
        """Two relays with DIFFERENT raw contact strings -> count = 2."""
        from allium.lib.categorization import sort_relay
        relays = [self._make_relay('VAR_A'), self._make_relay('VAR_B')]
        rs = self._make_relay_set(relays)
        for idx, relay in enumerate(relays):
            sort_relay(rs, relay, idx, 'contact', 'h1', 1, 0.0)
        sorted_data = rs.json['sorted']['contact']['h1']
        assert sorted_data.get('contact_variant_count') == 2

    def test_only_tracked_for_contact_groups(self):
        """family/country/etc groups don't get the variant_count field
        — it's specific to the contact listing."""
        from allium.lib.categorization import sort_relay
        relays = [self._make_relay('R1'), self._make_relay('R2')]
        rs = self._make_relay_set(relays)
        # Categorize as 'family' instead of 'contact'.
        for idx, relay in enumerate(relays):
            sort_relay(rs, relay, idx, 'family', 'fam_h', 1, 0.0)
        family_data = rs.json['sorted'].get('family', {}).get('fam_h', {})
        assert 'contact_variant_count' not in family_data


# ============================================================================
# P1-P4 reviewer-priority hardening
# ============================================================================


class TestRankingMutationSafety:
    """P1: generate_contact_rankings must isolate BOTH list-level and
    dict-level mutation — callers receive fresh copies so they cannot
    accidentally clobber the cached index."""

    def _build_rs(self):
        rs = MagicMock()
        rs.json = {'aroi_leaderboards': {'leaderboards': {
            'bandwidth': [('A', {})],
            'consensus_weight': [('A', {})],
        }}}
        return rs

    def test_list_mutation_isolated(self):
        from allium.lib.operator_analysis import generate_contact_rankings
        rs = self._build_rs()
        first = generate_contact_rankings('A', rs)
        first.clear()
        assert len(generate_contact_rankings('A', rs)) == 2

    def test_dict_mutation_isolated(self):
        """Mutating a returned ranking dict must NOT leak back into the
        cached index — locks the P1 contract."""
        from allium.lib.operator_analysis import generate_contact_rankings
        rs = self._build_rs()
        first = generate_contact_rankings('A', rs)
        first[0]['statement'] = 'CLOBBERED'
        first[0]['injected_field'] = True
        # Subsequent call must see pristine cached entries.
        second = generate_contact_rankings('A', rs)
        assert second[0]['statement'] != 'CLOBBERED'
        assert 'injected_field' not in second[0]


class TestRankingsIndexDedupe:
    """P2: legacy generate_contact_rankings broke after first match per
    category, so a malformed leaderboard repeating the same contact
    within one category never produced duplicate rankings. Lock the
    new indexer's parity."""

    def test_duplicate_contact_in_same_category_dedupes(self):
        from allium.lib.operator_analysis import _build_contact_rankings_index
        rs = MagicMock()
        rs.json = {'aroi_leaderboards': {'leaderboards': {
            'bandwidth': [
                ('A', {}),
                ('B', {}),
                ('A', {}),  # duplicate — must be ignored per legacy semantics
                ('A', {}),  # another duplicate
            ],
        }}}
        idx = _build_contact_rankings_index(rs)
        # 'A' appears at rank 1 (first occurrence) only.
        assert len(idx['A']) == 1
        assert idx['A'][0]['rank'] == 1
        assert len(idx['B']) == 1
        assert idx['B'][0]['rank'] == 2

    def test_duplicate_in_different_categories_kept(self):
        """A contact CAN appear in multiple categories — only same-
        category duplicates are deduped."""
        from allium.lib.operator_analysis import _build_contact_rankings_index
        rs = MagicMock()
        rs.json = {'aroi_leaderboards': {'leaderboards': {
            'bandwidth': [('A', {})],
            'consensus_weight': [('A', {})],
            'exit_authority': [('A', {})],
        }}}
        idx = _build_contact_rankings_index(rs)
        assert len(idx['A']) == 3
        cats = {r['category'] for r in idx['A']}
        assert cats == {'bandwidth', 'consensus_weight', 'exit_authority'}


class TestProofTypeVersionSingleSourceOfTruth:
    """P3: only ONE place defines proof_type -> ciissversion mapping —
    aroi_validation.PROOF_TYPE_VERSION (with both dashed and underscore
    keys). api_diagnostics row formatters must reuse it via
    get_proof_type_version() instead of carrying a local copy."""

    def test_get_proof_type_version_handles_dashed_form(self):
        from allium.lib.aroi_validation import get_proof_type_version
        assert get_proof_type_version('dns-rsa') == '2'
        assert get_proof_type_version('uri-rsa') == '2'
        assert get_proof_type_version('dns-familyid-ed25519') == '3'
        assert get_proof_type_version('uri-familyid-ed25519') == '3'

    def test_get_proof_type_version_handles_underscore_form(self):
        from allium.lib.aroi_validation import get_proof_type_version
        # Same proof types via the upstream-stats key form.
        assert get_proof_type_version('dns_rsa') == '2'
        assert get_proof_type_version('uri_rsa') == '2'
        assert get_proof_type_version('dns_familyid_ed25519') == '3'
        assert get_proof_type_version('uri_familyid_ed25519') == '3'

    def test_unknown_proof_type_returns_unknown_not_misclassified(self):
        """Future proof types added upstream MUST classify as 'unknown'
        until PROOF_TYPE_VERSION is updated — never silently misclassified
        as v2 because they happen to contain 'rsa' or as v3 because they
        contain 'family'."""
        from allium.lib.aroi_validation import get_proof_type_version
        # 'rsa-extended' contains 'rsa' but isn't in our dict.
        assert get_proof_type_version('rsa-extended') == 'unknown'
        # 'pq-familyid-mlkem' contains 'familyid' but isn't in our dict.
        assert get_proof_type_version('pq-familyid-mlkem') == 'unknown'
        assert get_proof_type_version('') == 'unknown'
        assert get_proof_type_version(None) == 'unknown'

    def test_api_diagnostics_uses_central_helper(self):
        """Source-level guarantee: api_diagnostics.py MUST NOT carry a
        local proof-type -> version dict definition. The single source
        of truth lives in aroi_validation.PROOF_TYPE_VERSION.

        Uses inspect.getsourcefile() to discover the module's file
        path at test time instead of hard-coding /workspace/..., so
        the test works regardless of where the repo is mounted.
        """
        import inspect, re
        from allium.lib import api_diagnostics
        module_file = inspect.getsourcefile(api_diagnostics)
        assert module_file, "could not resolve api_diagnostics module file"
        with open(module_file) as f:
            src = f.read()
        # No literal dict-definition for the local map. Comments
        # mentioning the old name are fine — they explain the migration.
        assert not re.search(r'^\s*_PROOF_TYPE_VERSION_MAP\s*=\s*\{', src, re.MULTILINE), \
            "Local proof-type map must be removed; use aroi_validation.get_proof_type_version"
        # And the central helper IS imported/used.
        assert 'get_proof_type_version' in src


class TestCiissversionNumericSort:
    """P4: future-proof the ciissversion row sort. String-sorting works
    for v1/v2/v3 today but breaks once a hypothetical v10 ships
    (string-sort puts '10' between '1' and '2')."""

    def test_v10_sorts_after_v3(self):
        from allium.lib.api_diagnostics import _format_ciissversion_rows
        rows = _format_ciissversion_rows({'10': 5, '3': 100, '2': 200, '1': 1})
        keys = [r['key'] for r in rows]
        assert keys == ['1', '2', '3', '10']

    def test_none_still_last_with_high_versions(self):
        from allium.lib.api_diagnostics import _format_ciissversion_rows
        rows = _format_ciissversion_rows({'10': 1, '2': 1, 'none': 1})
        assert rows[-1]['key'] == 'none'

    def test_alphabetical_after_numeric(self):
        """Two non-numeric keys both land at the end, in alpha order."""
        from allium.lib.api_diagnostics import _format_ciissversion_rows
        rows = _format_ciissversion_rows({'2': 1, 'none': 1, 'unknown': 1})
        assert [r['key'] for r in rows] == ['2', 'none', 'unknown']
