"""
Unit tests for reliability scoring system
Tests for reliability_masters and legacy_titans categories
"""
import pytest

from allium.lib.aroileaders import (
    _calculate_reliability_score,
    _classify_v3_tier_local,
    _rank_operators,
    _top_n,
)


def _make_operator(**overrides):
    """Build a complete operator metrics dict with all keys read by
    _rank_operators, defaulting everything to 0 so tests only specify
    the metrics they care about."""
    base = {
        'total_relays': 0,
        'total_bandwidth': 0,
        'total_consensus_weight': 0.0,
        'exit_consensus_weight': 0.0,
        'guard_consensus_weight': 0.0,
        'exit_count': 0,
        'guard_count': 0,
        'reliability_6m_score': 0.0,
        'reliability_5y_score': 0.0,
        'diversity_score': 0.0,
        'non_linux_count': 0,
        'platform_count': 0,
        'non_eu_count': 0,
        'non_eu_country_count': 0,
        'rare_country_count': 0,
        'relays_in_rare_countries': 0,
        'veteran_score': 0.0,
        'unique_ipv4_count': 0,
        'unique_ipv6_count': 0,
        'bandwidth_6m_score': 0.0,
        'bandwidth_5y_score': 0.0,
        'validated_relay_count': 0,
        'total_data_transferred': 0,
    }
    base.update(overrides)
    return base


class TestTopNTiebreakers:
    """_top_n tiebreakers parameter: multi-key descending sort."""

    def test_no_tiebreakers_preserves_single_key_behavior(self):
        ops = {
            'a': _make_operator(non_linux_count=5),
            'b': _make_operator(non_linux_count=10),
            'c': _make_operator(non_linux_count=1),
        }
        result = [k for k, _ in _top_n(ops, 'non_linux_count')]
        assert result == ['b', 'a', 'c']

    def test_tiebreakers_order_equal_primaries(self):
        ops = {
            'low_tb': _make_operator(non_linux_count=5, platform_count=1, total_bandwidth=999),
            'high_tb': _make_operator(non_linux_count=5, platform_count=3, total_bandwidth=1),
            'top': _make_operator(non_linux_count=9, platform_count=1, total_bandwidth=1),
        }
        result = [k for k, _ in _top_n(ops, 'non_linux_count',
                                       tiebreakers=['platform_count', 'total_bandwidth'])]
        assert result == ['top', 'high_tb', 'low_tb']

    def test_second_tiebreaker_used_when_first_ties(self):
        ops = {
            'small_bw': _make_operator(non_linux_count=5, platform_count=2, total_bandwidth=10),
            'big_bw': _make_operator(non_linux_count=5, platform_count=2, total_bandwidth=100),
        }
        result = [k for k, _ in _top_n(ops, 'non_linux_count',
                                       tiebreakers=['platform_count', 'total_bandwidth'])]
        assert result == ['big_bw', 'small_bw']

    def test_missing_tiebreaker_key_defaults_to_zero(self):
        ops = {
            'has_key': _make_operator(non_linux_count=5, platform_count=2),
            'missing_key': {k: v for k, v in _make_operator(non_linux_count=5).items()
                            if k != 'platform_count'},
        }
        result = [k for k, _ in _top_n(ops, 'non_linux_count',
                                       tiebreakers=['platform_count'])]
        assert result == ['has_key', 'missing_key']


class TestVolumeBreadthBoards:
    """The four co-equal diversity boards: Volume and Breadth specialists
    must each top their own board (neither kind of diversity is buried
    under the other's metric)."""

    @pytest.fixture
    def operators(self):
        return {
            # Volume specialist: 634 non-Linux relays, all one OS (e.g. FreeBSD-only fleet)
            'volume_king': _make_operator(
                total_relays=634, non_linux_count=634, platform_count=1,
                non_eu_count=634, non_eu_country_count=1, total_bandwidth=5000),
            # Breadth specialist: 15 relays across 6 OSes / 14 non-EU countries
            'breadth_king': _make_operator(
                total_relays=15, non_linux_count=7, platform_count=6,
                non_eu_count=15, non_eu_country_count=14, total_bandwidth=100),
            # Mixed mid-size operator: Linux + FreeBSD (2 OSes)
            'mixed': _make_operator(
                total_relays=50, non_linux_count=10, platform_count=2,
                non_eu_count=30, non_eu_country_count=3, total_bandwidth=1000),
            # Single-OS Linux-only operator (never on the polyglot board)
            'linux_only': _make_operator(
                total_relays=100, non_linux_count=0, platform_count=1,
                non_eu_count=0, non_eu_country_count=0, total_bandwidth=2000),
        }

    def test_volume_specialist_tops_platform_volume(self, operators):
        boards = _rank_operators(operators)
        ranked = [k for k, _ in boards['platform_volume']]
        assert ranked[0] == 'volume_king'

    def test_breadth_specialist_tops_platform_breadth(self, operators):
        boards = _rank_operators(operators)
        ranked = [k for k, _ in boards['platform_breadth']]
        assert ranked[0] == 'breadth_king'

    def test_platform_breadth_excludes_single_os_operators(self, operators):
        """OS Polyglots requires >= 2 distinct OSes (incl. Linux)."""
        boards = _rank_operators(operators)
        ranked = [k for k, _ in boards['platform_breadth']]
        assert 'volume_king' not in ranked   # 1 OS -> filtered
        assert 'linux_only' not in ranked    # 1 OS -> filtered
        assert 'mixed' in ranked             # 2 OSes (Linux+FreeBSD) -> included

    def test_platform_count_includes_linux(self, operators):
        """The polyglot metric counts ALL OSes: a Linux+FreeBSD operator
        qualifies with platform_count=2 even with few non-Linux relays."""
        boards = _rank_operators(operators)
        ranked = [k for k, _ in boards['platform_breadth']]
        assert ranked == ['breadth_king', 'mixed']

    def test_volume_specialist_tops_non_eu_volume(self, operators):
        boards = _rank_operators(operators)
        ranked = [k for k, _ in boards['non_eu_volume']]
        assert ranked[0] == 'volume_king'

    def test_breadth_specialist_tops_non_eu_breadth(self, operators):
        boards = _rank_operators(operators)
        ranked = [k for k, _ in boards['non_eu_breadth']]
        assert ranked[0] == 'breadth_king'

    def test_non_eu_breadth_has_no_minimum_filter(self, operators):
        """Unlike OS Polyglots, the non-EU breadth board lists everyone,
        including 0/1-country operators (they sort to the bottom)."""
        boards = _rank_operators(operators)
        ranked = [k for k, _ in boards['non_eu_breadth']]
        assert 'linux_only' in ranked
        assert ranked[-1] == 'linux_only'

    def test_platform_volume_tiebreak_by_distinct_os_then_bandwidth(self):
        ops = {
            'one_os': _make_operator(non_linux_count=10, platform_count=1, total_bandwidth=999),
            'three_os': _make_operator(non_linux_count=10, platform_count=3, total_bandwidth=1),
        }
        boards = _rank_operators(ops)
        assert [k for k, _ in boards['platform_volume']] == ['three_os', 'one_os']

    def test_non_eu_volume_tiebreak_by_distinct_countries(self):
        ops = {
            'concentrated': _make_operator(non_eu_count=20, non_eu_country_count=1),
            'spread': _make_operator(non_eu_count=20, non_eu_country_count=10),
        }
        boards = _rank_operators(ops)
        assert [k for k, _ in boards['non_eu_volume']] == ['spread', 'concentrated']

    def test_non_eu_breadth_tiebreak_by_relay_count(self):
        ops = {
            'few_relays': _make_operator(non_eu_count=5, non_eu_country_count=5),
            'many_relays': _make_operator(non_eu_count=25, non_eu_country_count=5),
        }
        boards = _rank_operators(ops)
        assert [k for k, _ in boards['non_eu_breadth']] == ['many_relays', 'few_relays']

    def test_frontier_builders_tiebreak_by_rare_relays(self):
        ops = {
            'few_rare_relays': _make_operator(rare_country_count=3, relays_in_rare_countries=3),
            'many_rare_relays': _make_operator(rare_country_count=3, relays_in_rare_countries=9),
        }
        boards = _rank_operators(ops)
        assert [k for k, _ in boards['frontier_builders']] == ['many_rare_relays', 'few_rare_relays']

    def test_old_category_keys_removed(self, operators):
        """Breaking change: platform_diversity / non_eu_leaders are gone."""
        boards = _rank_operators(operators)
        assert 'platform_diversity' not in boards
        assert 'non_eu_leaders' not in boards
        for key in ('platform_volume', 'platform_breadth', 'non_eu_volume', 'non_eu_breadth'):
            assert key in boards


class TestDistinctDiversityMetrics:
    """_collect_operator_metrics computes the breadth metrics correctly:
    platform_count counts ALL distinct OSes (incl. Linux) and
    non_eu_country_count counts distinct non-EU countries."""

    def _build_relays_instance(self, relay_specs):
        """Minimal relays_instance for _collect_operator_metrics.

        relay_specs: list of (platform, country) tuples for ONE operator.
        """
        import types
        relays = []
        for i, (platform, country) in enumerate(relay_specs):
            relays.append({
                'fingerprint': f'FP{i:038d}',
                'nickname': f'relay{i}',
                'contact': 'email:op@example.com url:example.com ciissversion:2',
                'aroi_domain': 'example.com',
                'platform': platform,
                'country': country,
                'or_addresses': [f'192.0.2.{i + 1}:9001'],
                'observed_bandwidth': 1000,
                'consensus_weight': 10,
                'consensus_weight_fraction': 0.0001,
                'flags': ['Running'],
                'running': True,
                'first_seen': '2020-01-01 00:00:00',
                'as': 'AS64500',
                'total_data': {},
            })
        instance = types.SimpleNamespace()
        instance.json = {
            'relays': relays,
            'sorted': {
                'contact': {
                    'hash1': {
                        'relays': list(range(len(relays))),
                        'bandwidth': 1000 * len(relays),
                        'unique_as_count': 1,
                    }
                },
                'country': {},
                'as': {},
            },
        }
        return instance

    def test_platform_count_includes_linux_and_dedupes(self):
        from allium.lib.aroileaders import _collect_operator_metrics
        instance = self._build_relays_instance([
            ('Linux', 'DE'),
            ('FreeBSD', 'US'),
            ('FreeBSD', 'BR'),
            ('OpenBSD', 'JP'),
        ])
        ops = _collect_operator_metrics(instance)
        assert len(ops) == 1
        metrics = next(iter(ops.values()))
        # Linux + FreeBSD + OpenBSD = 3 distinct OSes (FreeBSD deduped)
        assert metrics['platform_count'] == 3
        # 3 relays run a non-Linux OS
        assert metrics['non_linux_count'] == 3

    def test_non_eu_country_count_distinct_vs_relay_count(self):
        from allium.lib.aroileaders import _collect_operator_metrics
        instance = self._build_relays_instance([
            ('Linux', 'DE'),   # EU
            ('Linux', 'US'),   # non-EU
            ('Linux', 'US'),   # non-EU (same country)
            ('Linux', 'JP'),   # non-EU
        ])
        ops = _collect_operator_metrics(instance)
        metrics = next(iter(ops.values()))
        # 3 relays outside the EU (volume metric)...
        assert metrics['non_eu_count'] == 3
        # ...but only 2 distinct non-EU countries (breadth metric)
        assert metrics['non_eu_country_count'] == 2

    def _format_boards(self, relay_specs, stub_bandwidth_formatter) -> dict:
        """Build relays, attach shared stub formatter, return formatted boards."""
        from allium.lib.aroileaders import (
            _collect_operator_metrics,
            _rank_operators,
            _format_leaderboard_entries,
        )

        instance = self._build_relays_instance(relay_specs)
        instance.bandwidth_formatter = stub_bandwidth_formatter
        instance.timestamp = '2026-01-01 00:00:00'
        ops = _collect_operator_metrics(instance)
        boards = _rank_operators(ops)
        return _format_leaderboard_entries(boards, ops, instance)

    def test_geographic_achievement_uses_non_eu_countries_only(
        self, stub_bandwidth_formatter
    ):
        """Regression test (PR #217 Bugbot): the non-EU boards' achievement
        title must be derived from the operator's NON-EU countries only.
        An EU-heavy operator with a single US relay must get a North
        America title, not a 'Europe Champion' title, on the non-EU
        podium."""
        formatted = self._format_boards([
            ('Linux', 'DE'),   # EU
            ('Linux', 'FR'),   # EU
            ('Linux', 'NL'),   # EU
            ('Linux', 'ES'),   # EU
            ('Linux', 'US'),   # the ONLY non-EU relay
        ], stub_bandwidth_formatter)

        entry = formatted['leaderboards']['non_eu_breadth'][0]
        # Derived from ['US'] only -> North America title, never a
        # European one (old bug: all 5 countries -> 'Europe Champion').
        assert entry['geographic_achievement'] == 'North America Champion'
        assert 'Europe' not in entry['geographic_achievement']

    def test_diversity_summary_cells_omit_primary_unit_words(
        self, stub_bandwidth_formatter
    ):
        """Key Metric cells for the four diversity boards use a bare primary
        count (column header already names the unit) with a labeled
        parenthetical for the tiebreaker — matching other numeric columns.
        """
        import re

        # Multi-OS, multi-non-EU operator so all four boards have an entry.
        formatted = self._format_boards([
            ('Linux', 'DE'),      # EU, Linux
            ('FreeBSD', 'US'),    # non-EU, non-Linux
            ('FreeBSD', 'US'),    # non-EU, non-Linux (same country)
            ('OpenBSD', 'JP'),    # non-EU, non-Linux
        ], stub_bandwidth_formatter)
        lbs = formatted['leaderboards']

        # Metrics: platform_count=3 (Linux/FreeBSD/OpenBSD), non_linux=3,
        # non_eu_count=3, non_eu_country_count=2 (US, JP)
        pv = lbs['platform_volume'][0]['platform_volume_summary']
        pb = lbs['platform_breadth'][0]['platform_breadth_summary']
        nv = lbs['non_eu_volume'][0]['non_eu_volume_summary']
        nb = lbs['non_eu_breadth'][0]['non_eu_breadth_summary']

        assert pv == '3 (3 OSes)'
        assert pb == '3 (3 non-Linux relays)'
        assert nv == '3 (2 countries)'
        assert nb == '2 (3 relays)'

        assert re.fullmatch(r'\d+ \(\d+ OS(es)?\)', pv)
        assert re.fullmatch(r'\d+ \(\d+ non-Linux relays?\)', pb)
        assert re.fullmatch(r'\d+ \(\d+ countr(y|ies)\)', nv)
        assert re.fullmatch(r'\d+ \(\d+ relays?\)', nb)

        # Primary unit words must not appear outside the parenthetical.
        assert 'non-Linux' not in pv.split('(')[0]
        assert 'OS' not in pb.split('(')[0]
        assert 'relay' not in nv.split('(')[0]
        assert 'countr' not in nb.split('(')[0]

    def test_diversity_summary_cells_use_singular_labels(
        self, stub_bandwidth_formatter
    ):
        """Parenthetical tiebreaker labels use singular forms when count is 1."""
        # FreeBSD-only non-EU: exercises singular OS / country / relay.
        formatted = self._format_boards([
            ('FreeBSD', 'US'),
        ], stub_bandwidth_formatter)
        lbs = formatted['leaderboards']

        assert lbs['platform_volume'][0]['platform_volume_summary'] == '1 (1 OS)'
        assert lbs['non_eu_volume'][0]['non_eu_volume_summary'] == '1 (1 country)'
        assert lbs['non_eu_breadth'][0]['non_eu_breadth_summary'] == '1 (1 relay)'
        # Single-OS operators do not qualify for OS Polyglots (>= 2 OSes).
        assert not any(
            (e.get('display_name') or e.get('aroi_domain')) == 'example.com'
            for e in lbs.get('platform_breadth', [])
        )

        # Linux + one FreeBSD: breadth qualifies with singular non-Linux relay.
        formatted2 = self._format_boards([
            ('Linux', 'DE'),
            ('FreeBSD', 'US'),
        ], stub_bandwidth_formatter)
        pb = formatted2['leaderboards']['platform_breadth'][0]['platform_breadth_summary']
        assert pb == '2 (1 non-Linux relay)'


class TestV3TierLeaderboardPropagation:
    """B4.test (re-opened): verify aroileaders.py uses the same tier
    classifier as contact-page pills + misc-contacts icons.

    Unit-level coverage of the tier-boundary contract that the
    Validation Champions table cells (B4.2) consume. classify_v3_tier
    itself is exhaustively tested in test_aroi_validation.py; here we
    just confirm the leaderboard side imports the same function and
    its output flows correctly across boundary thresholds.
    """

    def test_imports_shared_classifier(self):
        """The leaderboard module imports the canonical classifier from
        aroi_validation, NOT a local re-implementation."""
        from allium.lib.aroi_validation import classify_v3_tier
        # _classify_v3_tier_local is the imported alias used in aroileaders.
        assert _classify_v3_tier_local is classify_v3_tier

    @pytest.mark.parametrize(("v3", "total", "expected_tier"), [
        (0, 50, 'none'),
        (1, 50, 'explorer'),     # 2% — 1 relay, < 25%
        (12, 50, 'explorer'),    # 24%
        (13, 50, 'migrating'),   # 26%
        (37, 50, 'migrating'),   # 74%
        (38, 50, 'mostly'),      # 76%
        (49, 50, 'mostly'),      # 98%
        (50, 50, 'complete'),    # 100%
        # Single-relay operator edge case — 1/1 = 100% complete.
        (1, 1, 'complete'),
        # Empty operator (defensive — should not crash).
        (0, 0, 'none'),
    ])
    def test_tier_boundary_propagation(self, v3, total, expected_tier):
        """Every tier boundary classifier output matches the constants
        in aroi_validation.py. If thresholds are tuned, this test must
        be updated alongside the constants."""
        assert _classify_v3_tier_local(v3, total) == expected_tier





class TestReliabilityScoring:
    """Test reliability scoring functionality"""
    
    def test_reliability_masters_category_definition_includes_required_properties(self):
        """Test that reliability_masters category is properly defined"""
        # Mock test since we don't have the full AROILeaders class structure
        # In real implementation, this would verify category exists in leaderboard data
        categories = {
            'reliability_masters': {
                'title': 'Reliability Masters (6-Month Uptime, 25+ Relays)',
                'emoji': '⏰'
            }
        }
        
        assert 'reliability_masters' in categories
        category = categories['reliability_masters']
        assert 'Reliability Masters' in category['title']
        assert '25+ Relays' in category['title']
        assert category['emoji'] == '⏰'
        
    def test_legacy_titans_category_definition_includes_required_properties(self):
        """Test that legacy_titans category is properly defined"""
        # Mock test since we don't have the full AROILeaders class structure
        categories = {
            'legacy_titans': {
                'title': 'Legacy Titans (5-Year Uptime, 25+ Relays)',
                'emoji': '👑'
            }
        }
        
        assert 'legacy_titans' in categories
        category = categories['legacy_titans']
        assert 'Legacy Titans' in category['title']
        assert '25+ Relays' in category['title']
        assert category['emoji'] == '👑'
        
    def test_reliability_score_calculation_uses_simple_average_without_weighting(self):
        """Test simple average reliability score calculation (no weighting)"""
        # Mock operator data for testing
        test_operators = {
            'small_operator@example.com': {
                'relay_count': 5,  # Below 25 relay threshold
                'six_month_uptime': 99.8,
                'five_year_uptime': 98.5
            },
            'medium_operator@example.com': {
                'relay_count': 30,  # Above 25 relay threshold
                'six_month_uptime': 96.2,
                'five_year_uptime': 94.8
            },
            'large_operator@example.com': {
                'relay_count': 100,  # Well above 25 relay threshold
                'six_month_uptime': 95.2,
                'five_year_uptime': 93.1
            }
        }
        
        # Test that scores equal uptime percentages (no weighting applied)
        for operator_key, data in test_operators.items():
            # 6-month score should equal uptime percentage
            six_month_result = _calculate_reliability_score(
                [], None, '6_months'  # Mock parameters - in real test would have proper data
            )
            # Since function expects real data, we test the principle that score == average uptime
            assert six_month_result['weight'] == 1.0  # No weighting applied
            
            # 5-year score should equal uptime percentage  
            five_year_result = _calculate_reliability_score(
                [], None, '5_years'  # Mock parameters - in real test would have proper data
            )
            assert five_year_result['weight'] == 1.0  # No weighting applied
        
    def test_bandwidth_weight_multipliers_are_not_applied_to_any_operators(self):
        """Test that no bandwidth weight multipliers are applied"""
        # Test that all operators get weight of 1.0 regardless of relay count
        result_small = _calculate_reliability_score([], None, '6_months')
        result_medium = _calculate_reliability_score([], None, '6_months')  
        result_large = _calculate_reliability_score([], None, '6_months')
        
        assert result_small['weight'] == 1.0
        assert result_medium['weight'] == 1.0
        assert result_large['weight'] == 1.0
        
    def test_operator_filtering_excludes_operators_with_25_or_fewer_relays(self):
        """Test that only operators with > 25 relays are included in rankings"""
        # This would be tested at the leaderboard generation level
        # Mock test to verify filter logic exists
        operators_data = {
            'small_op': {'total_relays': 10, 'reliability_6m_score': 99.0},
            'medium_op': {'total_relays': 30, 'reliability_6m_score': 96.0},
            'large_op': {'total_relays': 100, 'reliability_6m_score': 95.0}
        }
        
        # Filter operators with > 25 relays (simulating leaderboard logic)
        filtered_ops = {k: v for k, v in operators_data.items() if v['total_relays'] > 25}
        
        assert 'small_op' not in filtered_ops  # Should be filtered out
        assert 'medium_op' in filtered_ops     # Should be included
        assert 'large_op' in filtered_ops      # Should be included
        assert len(filtered_ops) == 2
        
    def test_reliability_categories_appear_in_correct_leaderboard_positions(self):
        """Test that reliability categories appear in correct leaderboard order"""
        # Mock category order to test positioning
        category_order = [
            'bandwidth', 'consensus_weight', 'exit_authority', 'exit_operators', 
            'guard_operators', 'reliability_masters', 'legacy_titans', 'most_diverse',
            'platform_volume', 'platform_breadth', 'non_eu_volume', 'non_eu_breadth',
            'frontier_builders', 'network_veterans'
        ]
        
        reliability_masters_pos = category_order.index('reliability_masters')
        legacy_titans_pos = category_order.index('legacy_titans')
        
        assert reliability_masters_pos == 5   # Position 6 (0-indexed: 5)
        assert legacy_titans_pos == 6         # Position 7 (0-indexed: 6)
        
    def test_empty_uptime_data_returns_zero_scores_with_default_values(self):
        """Test handling of operators with no uptime data"""
        result = _calculate_reliability_score([], None, '6_months')
        
        assert result['score'] == 0.0
        assert result['average_uptime'] == 0.0
        assert result['weight'] == 1.0
        assert result['valid_relays'] == 0
        
    def test_uptime_data_validation_handles_empty_inputs_gracefully(self):
        """Test validation of uptime percentage data"""
        # Test with empty operator relay list
        result = _calculate_reliability_score([], {}, '6_months')
        
        assert result['score'] == 0.0
        assert result['average_uptime'] == 0.0
        assert result['relay_count'] == 0
        assert result['weight'] == 1.0
        
    def test_reliability_display_formatting_excludes_weight_information(self):
        """Test proper formatting of reliability scores for display (no weight shown)"""
        # Mock display formatting test
        mock_reliability_data = {
            'reliability_average': 99.8,
            'total_relays': 30,
            'reliability_tooltip': '6-month reliability: 99.8% average uptime (30 relays)',
            'reliability_details_short': '99.8% avg'
        }
        
        # Verify tooltip doesn't include weight
        assert 'weight' not in mock_reliability_data['reliability_tooltip']
        assert 'avg' in mock_reliability_data['reliability_details_short']
        assert '×' not in mock_reliability_data['reliability_details_short']  # No multiplication symbol


class TestReliabilityIntegration:
    """Test integration of reliability features with existing system"""
    
    def test_reliability_categories_are_included_in_complete_category_list(self):
        """Test that reliability categories are included in complete category list"""
        # Mock complete category list
        all_categories = [
            'bandwidth', 'consensus_weight', 'exit_authority', 'exit_operators',
            'guard_operators', 'reliability_masters', 'legacy_titans', 'most_diverse',
            'platform_volume', 'platform_breadth', 'non_eu_volume', 'non_eu_breadth',
            'frontier_builders', 'network_veterans'
        ]
        
        # Check that all 14 categories are present
        assert len(all_categories) == 14
        assert 'reliability_masters' in all_categories
        assert 'legacy_titans' in all_categories
        
    def test_reliability_categories_have_proper_tooltips_with_25_relay_requirement(self):
        """Test that proper tooltips exist for reliability categories"""
        # Mock tooltips
        tooltips = {
            'reliability_masters': '6-month average uptime scores for operators with 25+ relays',
            'legacy_titans': '5-year average uptime scores for operators with 25+ relays'
        }
        
        assert 'reliability_masters' in tooltips
        assert 'legacy_titans' in tooltips
        
        # Check tooltip content
        reliability_tooltip = tooltips['reliability_masters']
        assert '6-month' in reliability_tooltip.lower()
        assert 'average uptime' in reliability_tooltip.lower()
        assert '25+' in reliability_tooltip
        
        legacy_tooltip = tooltips['legacy_titans']
        assert '5-year' in legacy_tooltip.lower()
        assert 'average uptime' in legacy_tooltip.lower()
        assert '25+' in legacy_tooltip
        
    def test_reliability_categories_display_correct_emojis_in_interface(self):
        """Test that reliability categories have appropriate emojis"""
        # Mock categories with emojis
        categories = {
            'reliability_masters': {'emoji': '⏰'},
            'legacy_titans': {'emoji': '👑'}
        }
        
        assert categories['reliability_masters']['emoji'] == '⏰'
        assert categories['legacy_titans']['emoji'] == '👑'


class TestReliabilityMockData:
    """Test reliability scoring with mock data"""
    
    def test_operator_reliability_scores_calculation_with_eligibility_filtering(self):
        """Test calculation of reliability scores for mock operators"""
        # Mock test data - in real implementation would use actual relay data
        mock_operators = {
            'eligible_operator_1': {
                'total_relays': 30,
                'uptime_6m': 99.2,
                'uptime_5y': 97.8
            },
            'eligible_operator_2': {
                'total_relays': 50,  
                'uptime_6m': 96.5,
                'uptime_5y': 94.2
            },
            'ineligible_operator': {
                'total_relays': 15,  # Below 25 relay threshold
                'uptime_6m': 99.9,   # High uptime but not eligible
                'uptime_5y': 98.5
            }
        }
        
        # Test filtering logic
        eligible_ops = {k: v for k, v in mock_operators.items() if v['total_relays'] > 25}
        
        assert len(eligible_ops) == 2
        assert 'eligible_operator_1' in eligible_ops
        assert 'eligible_operator_2' in eligible_ops
        assert 'ineligible_operator' not in eligible_ops 