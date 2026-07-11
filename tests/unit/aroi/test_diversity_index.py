"""
Unit tests for the Diversity Index (Diversity All-Rounders leaderboard).

Covers the reviewer-approved Part 2 design:
- diverse relay counting (Version A: relay differs from the operator's
  dominant OS/country/AS profile in >= 1 dimension)
- network-adaptive yardsticks (structural caps for breadth, top-5 cohort for
  volume, OS cap = the most OSes any single operator runs today)
- 0-100 sub-scores + composite index ordering
- Option-2 tooltips carrying today's yardsticks
"""
import pytest

from allium.lib.diversity_index import (
    OS_CAP_FLOOR,
    VOLUME_CAP_FLOOR,
    annotate_operators,
    compute_network_caps,
    compute_operator_scores,
    count_diverse_relays,
)


def _relay(platform='Linux', country='de', as_number='AS1'):
    return {'platform': platform, 'country': country, 'as': as_number}


def _operator(**overrides):
    base = {
        'country_count': 1, 'non_eu_count': 0,
        'platform_count': 1, 'non_linux_count': 0,
        'unique_as_count': 1, 'as_rarity_sum': 0.0,
        'rare_as_count': 0, 'diverse_relay_count': 0,
    }
    base.update(overrides)
    return base


class TestCountDiverseRelays:
    def test_empty_fleet(self):
        assert count_diverse_relays([]) == 0

    def test_perfect_monoculture_scores_zero(self):
        """quintex-style fleet: same OS, country and AS everywhere -> 0."""
        assert count_diverse_relays([_relay()] * 400) == 0

    def test_relay_differing_in_one_dimension_counts(self):
        relays = [_relay()] * 3 + [_relay(country='us')]
        assert count_diverse_relays(relays) == 1

    def test_relay_differing_in_any_dimension_counts_once(self):
        # differs in ALL three dimensions -> still one diverse relay
        relays = [_relay()] * 3 + [_relay('FreeBSD', 'us', 'AS9')]
        assert count_diverse_relays(relays) == 1

    def test_dominant_profile_is_per_dimension_mode(self):
        # 2x Linux/de/AS1 + 1x FreeBSD/de/AS1: mode profile is Linux/de/AS1,
        # so only the FreeBSD relay is diverse
        relays = [_relay(), _relay(), _relay(platform='FreeBSD')]
        assert count_diverse_relays(relays) == 1

    def test_missing_attributes_treated_as_unknown_bucket(self):
        # Relays without platform/country/as fall into a '?' bucket; a fleet
        # of all-unknown relays is a monoculture of unknowns
        assert count_diverse_relays([{}, {}, {}]) == 0

    def test_brokenbotnet_style_fleet_fully_diverse(self):
        # 15 relays: each differs from the mode country (14 distinct countries)
        relays = [_relay(country=f'c{i}') for i in range(14)] + [_relay(country='c0')]
        # mode country is c0 (2 relays); the other 13 differ
        assert count_diverse_relays(relays) == 13

    def test_count_is_order_independent_under_tied_modes(self):
        """CodeRabbit (PR #222): tied modes must break deterministically
        (lexicographically smallest), so the same relay multiset yields the
        same diverse-relay count regardless of input order."""
        from itertools import permutations
        relays = [
            _relay('A', 'X', '1'),
            _relay('A', 'Y', '2'),
            _relay('B', 'X', '2'),
            _relay('B', 'Y', '1'),
        ]
        counts = {count_diverse_relays(list(p)) for p in permutations(relays)}
        assert len(counts) == 1, f"order-dependent counts: {counts}"
        # Deterministic modes = (A, X, 1) -> only relay (A, X, 1) matches all
        assert counts == {3}

    def test_tied_mode_breaks_to_smallest_key(self):
        # 1x FreeBSD + 1x Linux (tie): mode platform must be 'FreeBSD'
        # (lexicographically smallest), regardless of insertion order
        for order in ([_relay('Linux'), _relay('FreeBSD')],
                      [_relay('FreeBSD'), _relay('Linux')]):
            # mode = FreeBSD -> the Linux relay is the diverse one
            assert count_diverse_relays(order) == 1


class TestNetworkAdaptiveCaps:
    def test_caps_derive_from_network_structure(self):
        ops = {
            'a': _operator(platform_count=6, non_eu_count=100, non_linux_count=20,
                           as_rarity_sum=52.0, diverse_relay_count=40),
            'b': _operator(platform_count=2, non_eu_count=50, non_linux_count=10,
                           as_rarity_sum=20.0, diverse_relay_count=20),
        }
        caps = compute_network_caps(ops, n_countries=89, n_ases=1100)
        assert caps['countries'] == 9      # 10% of 89, ceil
        assert caps['unique_as'] == 11     # 1% of 1100
        # OS cap = the most OSes any single operator runs (reviewer-approved)
        assert caps['oses'] == 6

    def test_os_cap_is_max_single_operator(self):
        ops = {f'op{i}': _operator(platform_count=1) for i in range(30)}
        ops['polyglot'] = _operator(platform_count=4)
        caps = compute_network_caps(ops, n_countries=50, n_ases=1000)
        assert caps['oses'] == 4

    def test_os_cap_floor(self):
        ops = {'a': _operator(platform_count=1)}
        caps = compute_network_caps(ops, n_countries=50, n_ases=1000)
        assert caps['oses'] == OS_CAP_FLOOR

    def test_volume_caps_use_rank5_not_max(self):
        """The 5th-highest value anchors volume caps, so one outlier can't
        stretch the yardstick."""
        counts = [1000, 90, 80, 70, 60, 5, 4, 3]  # rank-5 value = 60
        ops = {f'op{i}': _operator(non_eu_count=c) for i, c in enumerate(counts)}
        caps = compute_network_caps(ops, n_countries=50, n_ases=1000)
        assert caps['non_eu_relays'] == 60

    def test_volume_cap_floor_on_tiny_networks(self):
        ops = {'a': _operator(), 'b': _operator()}
        caps = compute_network_caps(ops, n_countries=1, n_ases=1)
        assert caps['non_eu_relays'] == VOLUME_CAP_FLOOR
        assert caps['diverse_relays'] == VOLUME_CAP_FLOOR


class TestOperatorScores:
    CAPS = {'countries': 9, 'oses': 6, 'unique_as': 11,
            'non_eu_relays': 100, 'non_linux_relays': 11,
            'as_rarity_sum': 52, 'diverse_relays': 40}

    def test_all_rounder_beats_specialists(self):
        all_rounder = compute_operator_scores(_operator(
            country_count=14, non_eu_count=15, platform_count=6, non_linux_count=7,
            unique_as_count=10, as_rarity_sum=34.0, diverse_relay_count=15), self.CAPS)
        country_collector = compute_operator_scores(_operator(
            country_count=26, non_eu_count=30, platform_count=1, non_linux_count=0,
            unique_as_count=33, as_rarity_sum=121.0, diverse_relay_count=48), self.CAPS)
        assert all_rounder['diversity_index'] > country_collector['diversity_index']

    def test_single_os_operator_platform_breadth_is_zero(self):
        scores = compute_operator_scores(_operator(
            country_count=26, unique_as_count=33, non_linux_count=0,
            platform_count=1), self.CAPS)
        # breadth half = (1-1)/cap = 0 and volume half = 0 non-Linux relays
        assert scores['platform_score'] == 0

    def test_monoculture_scale_is_zero_regardless_of_fleet_size(self):
        scores = compute_operator_scores(_operator(diverse_relay_count=0), self.CAPS)
        assert scores['scale_score'] == 0

    def test_index_is_mean_of_four_components(self):
        scores = compute_operator_scores(_operator(
            country_count=9, non_eu_count=100, platform_count=6, non_linux_count=11,
            unique_as_count=11, as_rarity_sum=52.0, diverse_relay_count=40), self.CAPS)
        assert scores['geo_score'] == scores['platform_score'] == 100
        assert scores['network_score'] == scores['scale_score'] == 100
        assert scores['diversity_index'] == 100

    def test_scores_clamped_to_100(self):
        scores = compute_operator_scores(_operator(
            country_count=999, non_eu_count=9999, platform_count=99,
            non_linux_count=9999, unique_as_count=999, as_rarity_sum=9999.0,
            diverse_relay_count=9999), self.CAPS)
        for key in ('geo_score', 'platform_score', 'network_score',
                    'scale_score', 'diversity_index'):
            assert scores[key] == 100

    def test_index_equals_mean_of_displayed_rounded_scores(self):
        """CodeRabbit (PR #222): the tooltip states the Index is the average
        of the four visible scores, so it must be computed from the ROUNDED
        components, not the raw values."""
        scores = compute_operator_scores(_operator(
            country_count=3, non_eu_count=7, platform_count=2, non_linux_count=3,
            unique_as_count=4, as_rarity_sum=11.0, diverse_relay_count=9), self.CAPS)
        expected = round((scores['geo_score'] + scores['platform_score']
                          + scores['network_score'] + scores['scale_score']) / 4)
        assert scores['diversity_index'] == expected


class TestAnnotateOperators:
    def test_annotation_adds_scores_and_tooltips(self):
        ops = {'a': _operator(country_count=14, non_eu_count=15, platform_count=6,
                              non_linux_count=7, unique_as_count=10,
                              as_rarity_sum=34.0, rare_as_count=10,
                              diverse_relay_count=15)}
        caps = annotate_operators(ops, n_countries=89, n_ases=1100)
        a = ops['a']
        for key in ('diversity_index', 'geo_score', 'platform_score',
                    'network_score', 'scale_score'):
            assert isinstance(a[key], int) and 0 <= a[key] <= 100
        # Option-2 tooltips always state today's yardsticks
        assert 'yardstick' in a['geo_cell_tooltip']
        assert str(caps['countries']) in a['geo_cell_tooltip']
        assert 'diverse relays' in a['scale_cell_tooltip']
        assert 'four co-equal components' in a['index_tooltip']

    def test_small_population_tooltips_say_largest_available(self):
        """CodeRabbit (PR #222): with fewer than 5 operators the volume caps
        fall back to the smallest available value, so tooltips must not claim
        a '5th-largest' cohort."""
        ops = {'only': _operator(non_eu_count=3, diverse_relay_count=3)}
        annotate_operators(ops, n_countries=10, n_ases=100)
        assert 'largest available' in ops['only']['geo_cell_tooltip']
        assert '5th-largest' not in ops['only']['scale_cell_tooltip']

    def test_full_population_tooltips_say_5th_largest(self):
        ops = {f'op{i}': _operator(non_eu_count=i + 1) for i in range(6)}
        annotate_operators(ops, n_countries=10, n_ases=100)
        assert "5th-largest" in ops['op0']['geo_cell_tooltip']


class TestCapacitySpreadRename:
    """Q7: Gini 'diversity_status' renamed + plain-language phrasing."""

    def _engine(self, weights):
        from allium.lib.intelligence_engine import IntelligenceEngine
        relays = [{'consensus_weight': w, 'flags': []} for w in weights]
        return IntelligenceEngine({'relays': relays, 'sorted': {}, 'network_totals': {},
                                   'family_statistics': {}})

    def test_poor_spread_phrase_and_status(self):
        # Extremely concentrated: one relay holds nearly everything
        engine = self._engine([1] * 20 + [100000])
        values = engine._layer13_capacity_distribution()['template_optimized']
        assert values['capacity_spread_status'] == 'POOR'
        assert values['capacity_spread_phrase'] == 'a few relays hold most capacity'
        assert 'diversity_status' not in values

    def test_excellent_spread(self):
        engine = self._engine([100] * 50)
        values = engine._layer13_capacity_distribution()['template_optimized']
        assert values['capacity_spread_status'] == 'EXCELLENT'

    def test_gini_tooltip_explains_direction(self):
        """Reviewer requirement: make it obvious whether high or low Gini is good."""
        engine = self._engine([1] * 20 + [100000])
        values = engine._layer13_capacity_distribution()['template_optimized']
        assert 'Lower is better' in values['gini_tooltip']
        assert '0.0 = perfectly even (best)' in values['gini_tooltip']
        # CodeRabbit (PR #222): finite-sample Gini max is (n-1)/n, so the
        # tooltip must not claim 1.0 means "one relay holds everything";
        # and the POOR band starts AT 0.6 (gini >= 0.6), not above it.
        assert 'approaching' in values['gini_tooltip']
        assert '0.6 and above = POOR' in values['gini_tooltip']


class TestGeoLineRelayCount:
    """Q6: contact-page Geographic Diversity line appends the relay count."""

    def test_geo_risk_includes_relay_count(self):
        from allium.lib.intelligence_engine import IntelligenceEngine
        relays = [
            {'country': c, 'platform': 'Linux', 'as': 'AS1', 'flags': [],
             'observed_bandwidth': 1, 'consensus_weight': 1, 'fingerprint': f'F{i}',
             'first_seen': '2020-01-01 00:00:00'}
            for i, c in enumerate(['de', 'us', 'jp', 'br', 'nz'])
        ]
        data = {
            'relays': relays,
            'sorted': {'contact': {'h1': {'relays': [0, 1, 2, 3, 4],
                                          'unique_as_count': 1, 'measured_count': 0}},
                       'platform': {}},
            'network_totals': {}, 'family_statistics': {},
        }
        engine = IntelligenceEngine(data)
        intel = engine._layer14_contact_intelligence()['template_optimized']
        assert intel['h1']['geographic_risk'] == 'Great, 5 countries (5 relays)'
