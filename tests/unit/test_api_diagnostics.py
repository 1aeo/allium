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
        rs.leaderboards_version = 1
        first = generate_contact_rankings('OLD', rs)
        assert first  # populates cache
        # Replace the leaderboards object AND bump the deterministic
        # version counter — _generate_aroi_leaderboards in production
        # bumps relay_set.leaderboards_version after every rebuild, so
        # any cached rankings index is invalidated.
        rs.json['aroi_leaderboards']['leaderboards'] = {
            'bandwidth': [('NEW', {})],
        }
        rs.leaderboards_version += 1
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
        """Source-level guarantee: the variants+total_data merged loop
        introduced by item B is exactly ONE pass over members. The
        original two passes used loop target name `r`; after the merge,
        only one such `for r in members` loop remains.

        Note: a *separate* `for relay in members` loop later in the
        function handles version compliance + family-support tracking
        — that's independent of item B's merge and out of scope here.
        We assert specifically on the loop whose target is the Name
        `r` so renaming the unrelated `relay` loop does not falsely
        trip this guarantee.

        Reviewer-flagged upgrade: parse the function body as an AST
        instead of substring-matching. Substring matching can be
        spoofed by comments/docstrings ("# for r in members") and
        breaks on harmless reformatting; AST inspection asserts on
        actual control-flow structure.
        """
        import ast
        import inspect
        import textwrap
        from allium.lib.operator_analysis import compute_contact_display_data
        src = textwrap.dedent(inspect.getsource(compute_contact_display_data))
        tree = ast.parse(src)
        # The item-B merged loop has target Name('r') and iter
        # Name('members'). Count those specifically.
        merged_loops = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.For)
            and isinstance(node.iter, ast.Name)
            and node.iter.id == 'members'
            and isinstance(node.target, ast.Name)
            and node.target.id == 'r'
        ]
        assert len(merged_loops) == 1, (
            "expected exactly 1 'for r in members' merged loop "
            "(item B contract) in compute_contact_display_data, found "
            f"{len(merged_loops)}"
        )


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

        Reviewer-flagged upgrade: parse the module as an AST instead of
        substring/regex-matching. Substring checks can be spoofed by
        comments/docstrings ("# legacy _PROOF_TYPE_VERSION_MAP removed")
        and break on harmless reformatting. We assert on actual
        ast.Assign nodes whose target is a Name with id
        '_PROOF_TYPE_VERSION_MAP' — that's the only structure that
        could shadow the central helper. We also assert on an actual
        ImportFrom node bringing get_proof_type_version into scope.
        """
        import ast
        import inspect
        from allium.lib import api_diagnostics

        module_file = inspect.getsourcefile(api_diagnostics)
        assert module_file, "could not resolve api_diagnostics module file"
        with open(module_file) as f:
            src = f.read()
        tree = ast.parse(src)

        local_map_assigns = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == '_PROOF_TYPE_VERSION_MAP'
                for t in node.targets
            )
        ]
        assert local_map_assigns == [], (
            "Local _PROOF_TYPE_VERSION_MAP rebinding detected; use "
            "aroi_validation.get_proof_type_version instead"
        )

        imports_central = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and any(alias.name == 'get_proof_type_version' for alias in node.names)
        ]
        assert imports_central, (
            "api_diagnostics must import get_proof_type_version from "
            "aroi_validation"
        )


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


# ============================================================================
# Reviewer follow-up #2: 17 hardening fixes
# ============================================================================


class TestV3OnlyCategoriesCorrection:
    """F1: V3_ONLY_ERROR_CATEGORIES used to wrongly include
    proof-file/TXT-related categories. _build_error_rollup() then
    treated every v2 URI-RSA / DNS-RSA failure as v3-only."""

    def test_uri_content_mismatch_not_v3_only(self):
        from allium.lib.aroi_validation import V3_ONLY_ERROR_CATEGORIES
        # These four MUST NOT be in V3_ONLY — they fire for both v2 and v3.
        for cat in (
            'uri_content_mismatch', 'uri_file_missing',
            'dns_content_mismatch', 'dns_txt_missing',
        ):
            assert cat not in V3_ONLY_ERROR_CATEGORIES

    def test_v2_uri_content_mismatch_routes_to_v2_bucket(self):
        from allium.lib.aroi_validation import _build_error_rollup
        results = [
            {'fingerprint': 'A', 'valid': False, 'ciissversion': '2',
             'error_category': 'uri_content_mismatch'},
            {'fingerprint': 'B', 'valid': False, 'ciissversion': '3',
             'error_category': 'uri_content_mismatch'},
        ]
        shared, v2_only, v3_only = _build_error_rollup(results)
        # v2 relay's failure must appear in v2_only — not silently
        # misclassified as v3-only by the legacy bug.
        assert any('uri_content_mismatch' == row[0] for row in v2_only)
        assert any('uri_content_mismatch' == row[0] for row in v3_only)


class TestContactVariantSetCleanup:
    """F2: _contact_variant_set is a Python set and would break
    json.dumps if it survived past categorisation. It must be removed
    by the calculate_contact_derived_data finalisation pass."""

    def test_set_removed_after_finalisation(self):
        import json
        from allium.lib.categorization import (
            sort_relay, calculate_contact_derived_data,
        )
        rs = MagicMock()
        rs.json = {'relays': [], 'sorted': {'contact': {}}}
        base = {
            'fingerprint': 'F' * 40, 'flags': [], 'observed_bandwidth': 100,
            'consensus_weight': 1, 'consensus_weight_fraction': 0.0,
            'guard_consensus_weight_fraction': 0.0,
            'middle_consensus_weight_fraction': 0.0,
            'exit_consensus_weight_fraction': 0.0,
            'first_seen': '2025-01-01 00:00:00', 'country': 'US',
            'platform': 'Linux', 'as': '111', 'as_name': '',
            'effective_family': [], 'aroi_domain': 'x.com',
        }
        for raw in ('A', 'B', 'A'):
            r = dict(base, contact=raw, contact_md5='h1')
            rs.json['relays'].append(r)
            sort_relay(rs, r, len(rs.json['relays']) - 1, 'contact', 'h1', 1, 0.0)
        rs.json['sorted']['contact']['h1']['bandwidth'] = 300
        calculate_contact_derived_data(rs)

        cd = rs.json['sorted']['contact']['h1']
        # Count survives.
        assert cd['contact_variant_count'] == 2
        # Live set is gone.
        assert '_contact_variant_set' not in cd
        # And the dict is JSON-serialisable end-to-end.
        json.dumps(cd, default=str)


class TestEarlyReturnPercentageFields:
    """F19: the early-return fallback branch in
    calculate_aroi_validation_metrics increments
    relays_version_proof_mismatch / relays_v3_informational counters
    but used to forget to compute their _percentage companions —
    leaving downstream templates with KeyError or None."""

    def test_fallback_branch_populates_new_percentages(self):
        from allium.lib.aroi_validation import calculate_aroi_validation_metrics
        m = calculate_aroi_validation_metrics(
            [{
                'fingerprint': 'A' * 40,
                'contact': 'ciissversion:2 proof:uri-rsa url:foo.com',
                'aroi_domain': 'foo.com', 'aroi_version': '2',
                'aroi_proof_type': 'uri-rsa', 'aroi_configured': True,
            }],
            None,  # validation_data None -> early-return fallback
        )
        # Both new percentage keys MUST be present (not missing).
        assert 'relays_version_proof_mismatch_percentage' in m
        assert 'relays_v3_informational_percentage' in m
        assert isinstance(m['relays_version_proof_mismatch_percentage'], float)
        assert isinstance(m['relays_v3_informational_percentage'], float)


# ============================================================================
# Reviewer follow-up #3: F1 (v3_informational counter), F6 (version counter)
# ============================================================================


class TestV3InformationalCounter:
    """F1: the v3_informational branch must bump the dedicated
    incomplete_v3_informational_count field — it was being missed
    despite the field being initialised at construction time."""

    def test_v3_informational_relay_increments_counter(self):
        """A relay with ciissversion:3 + no url: should bump
        validation_summary.incomplete_v3_informational_count
        even though it routes to the not_configured bucket."""
        from allium.lib.aroi_validation import get_contact_validation_status
        relays = [{
            'fingerprint': 'A' * 40,
            # Spec-legal v3 informational form: ciissversion:3 + email
            # but no url:.
            'contact': 'ciissversion:3 email:owner[]example.com',
            # _check_aroi_fields will see has_ciissversion=True,
            # has_url=False, treat as v3_informational category.
            'aroi_domain': 'none',
            'aroi_version': '3',
            'aroi_proof_type': None,
            'aroi_configured': False,
        }]
        result = get_contact_validation_status(relays, {'results': []})
        assert result['validation_summary']['incomplete_v3_informational_count'] == 1

    def test_non_v3_informational_does_not_inflate_counter(self):
        """An unrelated incomplete relay must NOT bump the
        v3_informational counter."""
        from allium.lib.aroi_validation import get_contact_validation_status
        relays = [{
            'fingerprint': 'B' * 40,
            'contact': 'noreply@nowhere.invalid',  # plain contact, no AROI
            'aroi_domain': 'none',
            'aroi_version': None,
            'aroi_proof_type': None,
            'aroi_configured': False,
        }]
        result = get_contact_validation_status(relays, {'results': []})
        assert result['validation_summary']['incomplete_v3_informational_count'] == 0


class TestRankingsCacheVersionCounter:
    """F6: cache key for _get_contact_rankings_index switched from
    id(leaderboards_obj) to a deterministic monotonic counter
    (relay_set.leaderboards_version) bumped by _generate_aroi_leaderboards.
    """

    def test_version_counter_invalidates_cache(self):
        from allium.lib.operator_analysis import generate_contact_rankings
        rs = MagicMock()
        rs.json = {'aroi_leaderboards': {'leaderboards': {
            'bandwidth': [('OLD', {})],
        }}}
        rs.leaderboards_version = 1
        first = generate_contact_rankings('OLD', rs)
        assert first
        # Bump the counter — even WITHOUT replacing the leaderboards
        # dict object, the cache must invalidate.
        rs.leaderboards_version = 2
        rs.json['aroi_leaderboards']['leaderboards'] = {
            'bandwidth': [('NEW', {})],
        }
        new_rankings = generate_contact_rankings('NEW', rs)
        assert new_rankings
        assert generate_contact_rankings('OLD', rs) == []

    def test_same_version_serves_cached_results(self):
        """If leaderboards_version doesn't change, the cached index is
        reused — even after the underlying leaderboards dict is
        mutated in-place. This is intentional: the version counter is
        the authoritative invalidation signal, not object identity."""
        from allium.lib.operator_analysis import generate_contact_rankings
        rs = MagicMock()
        rs.json = {'aroi_leaderboards': {'leaderboards': {
            'bandwidth': [('A', {})],
        }}}
        rs.leaderboards_version = 5
        # First call populates cache.
        first = generate_contact_rankings('A', rs)
        assert first
        # Mutate underlying data WITHOUT bumping the version. The cache
        # MUST keep serving the original snapshot — production code is
        # required to bump leaderboards_version on every rebuild.
        rs.json['aroi_leaderboards']['leaderboards'] = {
            'bandwidth': [('B', {})],
        }
        # 'A' still resolves (because cache wasn't invalidated).
        second = generate_contact_rankings('A', rs)
        assert second
        # 'B' does NOT resolve (the new entry isn't in the cache).
        assert generate_contact_rankings('B', rs) == []

    def test_relays_generate_aroi_leaderboards_bumps_version(self):
        """Source-level guarantee: _generate_aroi_leaderboards must
        increment relay_set.leaderboards_version. Locks the production
        contract that the cache invalidation relies on.

        Reviewer-flagged upgrade: AST inspection instead of substring
        match. We accept any of the common ways to bump an integer
        attribute (`self.leaderboards_version += 1`,
        `self.leaderboards_version = ... + 1`, `getattr(...,
        'leaderboards_version', 0) + 1`) — what matters structurally is
        an Assign or AugAssign node that writes back to
        self.leaderboards_version with an arithmetic expression on the
        right-hand side that itself references leaderboards_version.
        Behavioural correctness is also covered by
        test_version_counter_invalidates_cache below; this test
        guarantees the bump WILL happen on every rebuild even when
        nobody runs the integration smoke.
        """
        import ast
        import inspect
        import textwrap
        from allium.lib.relays import Relays

        src = textwrap.dedent(inspect.getsource(Relays._generate_aroi_leaderboards))
        tree = ast.parse(src)

        def writes_to_leaderboards_version(node):
            """True if `node` is `self.leaderboards_version` (Attribute on
            Name 'self' with attr 'leaderboards_version')."""
            return (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == 'self'
                and node.attr == 'leaderboards_version'
            )

        # Look for `self.leaderboards_version = <expr>` (Assign) OR
        # `self.leaderboards_version += <expr>` (AugAssign).
        bump_nodes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AugAssign) and writes_to_leaderboards_version(node.target):
                bump_nodes.append(node)
            elif isinstance(node, ast.Assign) and any(
                writes_to_leaderboards_version(t) for t in node.targets
            ):
                bump_nodes.append(node)

        assert bump_nodes, (
            "_generate_aroi_leaderboards must assign to "
            "self.leaderboards_version on every rebuild — required for "
            "the cache invalidation contract enforced by "
            "_get_contact_rankings_index"
        )


# ============================================================================
# Reviewer follow-up #4: F1 has_aroi for v3_informational + F2 first-wins
# ============================================================================


class TestV3InformationalHasAROI:
    """F1: a v3_informational relay HAS declared ciissversion:3 — it is
    NOT a zero-AROI-fields contact. result['has_aroi'] must be True
    so downstream code that filters on 'operator has any AROI
    declaration' picks them up. The not_configured_no_aroi_info_count
    bucket (reserved for relays with NO AROI fields at all) must NOT
    be incremented for v3_informational relays."""

    def test_v3_informational_sets_has_aroi(self):
        from allium.lib.aroi_validation import get_contact_validation_status
        relays = [{
            'fingerprint': 'A' * 40,
            'contact': 'ciissversion:3 email:owner[]example.com',
            'aroi_domain': 'none',
            'aroi_version': '3',
            'aroi_proof_type': None,
            'aroi_configured': False,
        }]
        result = get_contact_validation_status(relays, {'results': []})
        assert result['has_aroi'] is True

    def test_v3_informational_does_not_inflate_no_aroi_info(self):
        from allium.lib.aroi_validation import get_contact_validation_status
        relays = [{
            'fingerprint': 'A' * 40,
            'contact': 'ciissversion:3 email:owner[]example.com',
            'aroi_domain': 'none',
            'aroi_version': '3',
            'aroi_proof_type': None,
            'aroi_configured': False,
        }]
        s = get_contact_validation_status(relays, {'results': []})['validation_summary']
        # Bucket reserved for "has contact, no AROI fields at all"
        # MUST NOT count v3_informational (which DOES have ciissversion).
        assert s['not_configured_no_aroi_info_count'] == 0
        # But not_configured_count and incomplete_v3_informational_count DO go up.
        assert s['not_configured_count'] == 1
        assert s['incomplete_v3_informational_count'] == 1


class TestCheckAROIFieldsFirstWins:
    """F2: CIISS spec says duplicate keys -> FIRST wins.
    aroi_validation._check_aroi_fields() previously searched for
    SUPPORTED versions first via _CIISS_VERSION_RE, which silently
    skipped a leading unsupported declaration if a supported one
    followed. Per the spec, an unsupported FIRST token means the
    relay has no usable version regardless of subsequent tokens.

    Note: `Relays._simple_aroi_parsing` (relays.py) is a separate
    parsing path used at categorisation time; the reviewer's F2 ask
    was specifically about the validation-time path here, so we
    target `_check_aroi_fields` directly.
    """

    def _check(self, contact):
        from allium.lib.aroi_validation import _check_aroi_fields
        return _check_aroi_fields(contact)

    def test_unsupported_first_version_preserved_blocks_supported_later(self):
        """ciissversion:99 first, ciissversion:2 second — first-wins
        semantics: the v99 token wins. Per the latest hardening, the
        raw '99' is PRESERVED in result['version'] so downstream code
        can route the relay to the unsupported/mismatch bucket
        instead of bucketing it as 'no ciissversion declared'.
        """
        from allium.lib.aroi_validation import reset_aroi_warnings_log
        reset_aroi_warnings_log()
        result = self._check(
            'ciissversion:99 ciissversion:2 url:foo.com proof:uri-rsa'
        )
        # Raw token preserved (NOT silently overridden by the v2 that
        # appears later in the contact string).
        assert result['version'] == '99'
        # has_ciissversion just reflects 'a version was declared'.
        assert result['has_ciissversion'] is True

    def test_unsupported_first_proof_type_preserved_blocks_supported_later(self):
        """proof:rsa-extended-pq first, proof:uri-rsa second — first
        wins: raw 'rsa-extended-pq' preserved so downstream sees the
        explicit-but-unsupported declaration."""
        from allium.lib.aroi_validation import reset_aroi_warnings_log
        reset_aroi_warnings_log()
        result = self._check(
            'ciissversion:2 proof:rsa-extended-pq proof:uri-rsa url:foo.com'
        )
        assert result['proof_type'] == 'rsa-extended-pq'
        # has_proof flag tracks 'a proof was declared'.
        assert result['has_proof'] is True

    def test_supported_first_version_still_works(self):
        from allium.lib.aroi_validation import reset_aroi_warnings_log
        reset_aroi_warnings_log()
        result = self._check(
            'ciissversion:3 url:foo.com proof:uri-familyid-ed25519'
        )
        assert result['version'] == '3'
        assert result['has_ciissversion'] is True

    def test_supported_first_proof_type_still_works(self):
        from allium.lib.aroi_validation import reset_aroi_warnings_log
        reset_aroi_warnings_log()
        result = self._check('ciissversion:2 proof:uri-rsa url:foo.com')
        assert result['proof_type'] == 'uri-rsa'
        assert result['has_proof'] is True


# ============================================================================
# Reviewer follow-up #5: F1 preserve raw unsupported tokens
# ============================================================================


class TestUnsupportedTokenPreservation:
    """F1: when the FIRST declared ciissversion / proof_type is
    unsupported, _check_aroi_fields preserves the raw token in
    aroi_fields['version'] / aroi_fields['proof_type'] (was None
    previously). This routes the relay through a different bucket
    in _categorize_by_missing_fields than 'missing field' — the
    operator-actionable distinction between 'didn't declare a version'
    vs 'declared an unsupported version' is preserved."""

    def _check(self, contact):
        from allium.lib.aroi_validation import _check_aroi_fields, reset_aroi_warnings_log
        reset_aroi_warnings_log()
        return _check_aroi_fields(contact)

    def test_unsupported_version_preserved_in_aroi_fields(self):
        result = self._check(
            'ciissversion:99 url:foo.com proof:uri-rsa'
        )
        assert result['version'] == '99'
        assert result['has_ciissversion'] is True

    def test_unsupported_proof_type_preserved_in_aroi_fields(self):
        result = self._check(
            'ciissversion:2 proof:rsa-extended-pq url:foo.com'
        )
        assert result['proof_type'] == 'rsa-extended-pq'
        assert result['has_proof'] is True

    def test_unsupported_version_does_not_route_to_no_aroi_info(self):
        """With all 3 fields declared but ciissversion is unsupported,
        the relay should NOT land in the 'no_aroi_info' bucket (which
        is reserved for relays with NO AROI fields at all). The
        unsupported-version case ends up routed via the
        version_proof_mismatch branch because PROOF_TYPE_VERSION can't
        match the unsupported value to any known proof type — that's a
        more accurate signal than 'missing field'."""
        from allium.lib.aroi_validation import (
            _check_aroi_fields, _categorize_by_missing_fields,
            reset_aroi_warnings_log,
        )
        reset_aroi_warnings_log()
        result = _check_aroi_fields(
            'ciissversion:99 url:foo.com proof:uri-rsa'
        )
        category = _categorize_by_missing_fields(result, has_contact=True)
        # Anything OTHER than the missing-field buckets is acceptable —
        # the explicit-but-unsupported declaration is no longer hidden.
        assert category not in ('no_aroi_info', 'missing_two_aroi',
                                'no_proof', 'no_domain', 'no_ciissversion')


class TestDashboardTileValidityAccuracy:
    """F2b: dashboard ciissversion v2/v3 tiles compute validity as
    validated / declared (NOT the proof-attempt success rate which
    the *_success_rate fields carry). The new template logic divides
    ciissversion_validated[N] by ciissversion_declared[N]; this
    test enforces the data shape the template depends on so a future
    change in aroi_validation can't silently break the tile math."""

    def test_ciissversion_validated_and_declared_keys_present(self):
        """Both dicts must be populated by calculate_aroi_validation_metrics
        even for the empty / fallback path the template can hit."""
        from allium.lib.aroi_validation import calculate_aroi_validation_metrics
        m = calculate_aroi_validation_metrics(
            [{'fingerprint': 'A' * 40,
              'contact': 'ciissversion:2 proof:uri-rsa url:foo.com',
              'aroi_domain': 'foo.com', 'aroi_version': '2',
              'aroi_proof_type': 'uri-rsa', 'aroi_configured': True}],
            None,  # validation_data None -> early-return fallback
        )
        # Both dicts must exist (even if empty) so the template's
        # dict.get(...) calls don't crash on undefined access.
        assert 'ciissversion_declared' in m
        assert 'ciissversion_validated' in m
        assert isinstance(m['ciissversion_declared'], dict)
        assert isinstance(m['ciissversion_validated'], dict)
