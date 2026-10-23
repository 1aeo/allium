"""
Tests for relay_diagnostics module.

Tests all 25 issue types across 11 categories:
- consensus (1): Not in consensus
- reachability (3): IPv4 issues, IPv6 not reachable, Partial IPv4
- fast (1): Not getting the Fast flag
- guard: BW below, WFU below, TK below, requires Stable, requires Fast,
  plus info notes when a relay that has Guard is near an authority's own bar
- stable (1): Not eligible
- hsdir (4): requires V2Dir, requires Stable, requires Fast, uptime below 96 hours
- bandwidth (1): High deviation
- descriptor (1): StaleDesc
- flags (1): BadExit
- version (1): Not recommended
- overload (6): General Active, Recent Reported, FD Exhaustion, Write Limit, Read Limit, Rate Config
"""

import pytest
import time
from datetime import datetime, timezone

from allium.lib.relay_diagnostics import (
    generate_relay_issues,
    generate_issues_from_consensus,
    _check_overload_issues,
    OVERLOAD_THRESHOLD_HOURS,
)
from allium.lib.consensus.flag_thresholds import (
    GUARD_BW_NEAR_FRACTION,
    GUARD_TK_NEAR_MARGIN,
    GUARD_WFU_NEAR_MARGIN,
)
from tests.conftest import ACTIVE_VOTING_AUTHORITIES_8, FOREST44_FINGERPRINT

# Constants for testing
SECONDS_PER_DAY = 86400
GUARD_BW_GUARANTEE = 2_097_000  # AuthDirGuardBWGuarantee "2 MB", compared as 2097 KB/s
GUARD_WFU_DEFAULT = 0.98
GUARD_TK_DEFAULT = 691200  # 8 days

# Alphabetical voting authorities. The old warning read the first of these.
_VOTING_AUTHORITIES = [
    'bastet', 'dannenberg', 'dizum', 'faravahar', 'gabelmoo',
    'longclaw', 'maatuska', 'moria1', 'tor26',
]


def _guard_details(wfu_met, tk_met, bw_met=True):
    """Per-authority Guard details. wfu_met and tk_met are nine booleans."""
    return [
        {'authority': name, 'wfu_met': wfu, 'tk_met': tk, 'bw_met': bw_met}
        for name, wfu, tk in zip(_VOTING_AUTHORITIES, wfu_met, tk_met)
    ]


class TestGenerateRelayIssues:
    """Tests for generate_relay_issues() main entry point."""
    
    def test_empty_relay_no_consensus(self):
        """Test with empty relay and no consensus data."""
        issues = generate_relay_issues({})
        # Should only have overload issues (which will be empty for empty relay)
        assert isinstance(issues, list)
        assert len(issues) == 0
    
    def test_combines_consensus_and_overload(self):
        """Test that both consensus and overload issues are combined."""
        relay = {
            'flags': [],
            'observed_bandwidth': 1_000_000,  # Below Guard threshold
            'overload_general_timestamp': int(time.time() * 1000) - 3600000,  # 1 hour ago
        }
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.90, 'tk': 10 * SECONDS_PER_DAY}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
        }
        
        issues = generate_relay_issues(relay, consensus_data)
        
        # Should have at least Guard bandwidth issue + General Overload
        categories = {i['category'] for i in issues}
        assert 'guard' in categories
        assert 'overload' in categories


class TestConsensusIssues:
    """Tests for consensus-related issues (16 types)."""
    
    def test_not_in_consensus(self):
        """Test Not in consensus issue (error severity)."""
        consensus_data = {
            'in_consensus': False,
            'vote_count': 3,
            'total_authorities': 9,
            'authority_votes': [],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
        }
        
        issues = generate_issues_from_consensus(consensus_data)
        
        consensus_issues = [i for i in issues if i['category'] == 'consensus']
        assert len(consensus_issues) >= 1
        assert consensus_issues[0]['severity'] == 'error'
        assert 'Not in consensus' in consensus_issues[0]['title']
    
    def test_ipv4_reachability_error(self):
        """Test IPv4 reachability issues (error severity)."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [],
            'reachability': {
                'ipv4_reachable_count': 3,  # Below majority
                'ipv4_reachable_authorities': ['bastet', 'dannenberg', 'dizum'],
            },
            'flag_eligibility': {},
        }
        
        issues = generate_issues_from_consensus(consensus_data)
        
        reach_issues = [i for i in issues if i['category'] == 'reachability' and 'IPv4' in i['title']]
        assert len(reach_issues) >= 1
        assert reach_issues[0]['severity'] == 'error'
    
    def test_ipv6_not_reachable(self):
        """Test IPv6 not reachable issue (warning severity)."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [],
            'reachability': {
                'ipv4_reachable_count': 9,
                'ipv6_reachable_count': 0,
                'ipv6_not_tested_authorities': ['moria1'],  # Only 1 not testing
            },
            'flag_eligibility': {},
        }
        
        issues = generate_issues_from_consensus(consensus_data)
        
        ipv6_issues = [i for i in issues if 'IPv6' in i['title']]
        assert len(ipv6_issues) >= 1
        assert ipv6_issues[0]['severity'] == 'warning'
    
    def test_partial_ipv4_reachability(self):
        """Test partial IPv4 reachability (info severity)."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [],
            'reachability': {
                'ipv4_reachable_count': 7,  # Above majority but not all
                'ipv4_reachable_authorities': ['a', 'b', 'c', 'd', 'e', 'f', 'g'],
            },
            'flag_eligibility': {},
        }
        
        issues = generate_issues_from_consensus(consensus_data)
        
        partial_issues = [i for i in issues if 'Partial' in i['title']]
        assert len(partial_issues) >= 1
        assert partial_issues[0]['severity'] == 'info'
    
    def test_guard_bandwidth_below(self):
        """Test Guard bandwidth below threshold (warning severity)."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.99, 'tk': 10 * SECONDS_PER_DAY}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
        }
        
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Stable', 'Fast'],  # Has prerequisites
            observed_bandwidth=1_000_000  # Below 2 MB/s
        )
        
        bw_issues = [i for i in issues if 'Guard' in i['title'] and 'bandwidth' in i['title']]
        assert len(bw_issues) >= 1
        assert bw_issues[0]['severity'] == 'warning'
    
    def test_guard_wfu_below(self):
        """Guard WFU warns from the authority count, at warning severity."""
        # Two authorities meet their own guard-wfu; seven do not. Majority is 5.
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'authority': 'bastet', 'wfu': 0.90, 'tk': 10 * SECONDS_PER_DAY}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {
                'guard': {'details': _guard_details([True, True] + [False] * 7, [True] * 9)},
            },
        }
        
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Stable', 'Fast'],
            observed_bandwidth=3_000_000
        )
        
        wfu_issues = [i for i in issues if 'Guard' in i['title'] and 'WFU' in i['title']]
        assert len(wfu_issues) == 1
        assert wfu_issues[0]['severity'] == 'warning'
        assert wfu_issues[0]['section'] == 'flag-guard-wfu'
        assert wfu_issues[0]['description'] == (
            '2/9 authorities meet guard-wfu (5 needed). '
            'dizum, faravahar, gabelmoo, longclaw, maatuska, moria1 and tor26 do not meet it.')
        assert [i for i in issues if 'Time Known' in i['title']] == []
    
    def test_guard_tk_below_is_warning(self):
        """Guard Time Known warns from the authority count, at warning severity."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'authority': 'bastet', 'wfu': 0.99, 'tk': 3 * SECONDS_PER_DAY}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {
                'guard': {'details': _guard_details([True] * 9, [True, True] + [False] * 7)},
            },
        }
        
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Stable', 'Fast'],
            observed_bandwidth=3_000_000
        )
        
        tk_issues = [i for i in issues if 'Guard' in i['title'] and 'Time Known' in i['title']]
        assert len(tk_issues) == 1
        assert tk_issues[0]['severity'] == 'warning'
        assert tk_issues[0]['section'] == 'flag-guard-time-known'
        assert tk_issues[0]['description'] == (
            '2/9 authorities meet guard-tk (5 needed). '
            'dizum, faravahar, gabelmoo, longclaw, maatuska, moria1 and tor26 do not meet it.')
        assert [i for i in issues if 'WFU' in i['title']] == []

    def test_guard_wfu_and_tk_ignore_a_single_failing_vote(self):
        """A first vote of 0.0 does not warn when a majority of authorities meet."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [
                {'authority': 'bastet', 'wfu': 0.0, 'tk': 6},
                {'authority': 'dannenberg', 'wfu': 0.982, 'tk': 14 * SECONDS_PER_DAY},
            ],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {
                'guard': {'details': _guard_details([False] + [True] * 8, [False] + [True] * 8)},
            },
        }
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Stable', 'Fast'],
            observed_bandwidth=3_000_000,
        )
        assert [i['title'] for i in issues if i['category'] == 'guard'] == []

    def test_guard_wfu_warns_when_first_vote_passes_and_majority_fails(self):
        """A passing first vote does not hide a majority that misses guard-wfu."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'authority': 'bastet', 'wfu': 0.997499, 'tk': 30 * SECONDS_PER_DAY}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {
                'guard': {'details': _guard_details([True, False, False, True] + [False] * 5, [True] * 9)},
            },
        }
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Stable', 'Fast'],
            observed_bandwidth=3_000_000,
        )
        wfu_issues = [i for i in issues if 'WFU' in i['title']]
        assert len(wfu_issues) == 1
        assert wfu_issues[0]['description'].startswith('2/9 authorities meet guard-wfu (5 needed).')
        assert '99.7%' not in wfu_issues[0]['description']
        assert '0.0%' not in wfu_issues[0]['description']

    def test_guard_has_flag_skips_wfu_and_tk_warnings(self):
        """A relay that already has Guard gets neither uptime warning."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.0, 'tk': 0}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {
                'guard': {'details': _guard_details([False] * 9, [False] * 9)},
            },
        }
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Guard', 'Stable', 'Fast'],
            observed_bandwidth=3_000_000,
        )
        assert [i for i in issues if 'WFU' in i['title'] or 'Time Known' in i['title']] == []

    def test_guard_wfu_without_details_does_not_use_the_first_vote(self):
        """Missing per-authority details do not fall back to one vote's WFU or time-known."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.0, 'tk': 0}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
        }
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Stable', 'Fast'],
            observed_bandwidth=3_000_000,
        )
        assert [i for i in issues if 'WFU' in i['title'] or 'Time Known' in i['title']] == []

    def test_wfu_zero_is_history_and_missing_is_unpublished(self):
        """0% beside days of time-known is recorded downtime. A missing value is not called 0%."""
        details = []
        for name, wfu, met in (
            ('bastet', 0.0, False),
            ('dannenberg', 0.99, True),
            ('dizum', 0.99, True),
            ('faravahar', 0.90, False),
            ('gabelmoo', 0.91, False),
            ('longclaw', 0.92, False),
            ('maatuska', 0.93, False),
            ('moria1', None, False),
            ('tor26', 0.94, False),
        ):
            details.append({
                'authority': name, 'wfu_met': met, 'tk_met': True, 'bw_met': True,
                'wfu_threshold': 0.98, 'wfu_value': wfu, 'tk_threshold': GUARD_TK_DEFAULT,
                'tk_value': 20 * SECONDS_PER_DAY,
            })
        issues = generate_issues_from_consensus({
            'in_consensus': True,
            'total_authorities': 9,
            'authority_votes': [{'wfu': 0.0, 'tk': 20 * SECONDS_PER_DAY}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {'guard': {'details': details}},
        }, current_flags=['Fast', 'Stable'], observed_bandwidth=3_000_000)
        wfu = next(i for i in issues if 'WFU' in i['title'])
        assert wfu['description'] == (
            '2/9 authorities meet guard-wfu (≥98%; 5 needed). '
            'bastet measured 0% (no uptime credit). '
            'moria1 published no WFU. '
            'faravahar, gabelmoo, longclaw, maatuska and tor26 measured 90.0%–94.0%.')
        assert 'no uptime history' not in wfu['description']
        assert 'Minimize restarts' in wfu['suggestion']
        assert 'moria1 measured 0%' not in wfu['description']
        history_only = [{
            'authority': name, 'wfu_met': False, 'tk_met': True, 'bw_met': True,
            'wfu_value': 0.0, 'wfu_threshold': 0.98,
        } for name in _VOTING_AUTHORITIES]
        history = generate_issues_from_consensus({
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.0, 'tk': 20 * SECONDS_PER_DAY}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {'guard': {'details': history_only}},
        }, current_flags=['Fast', 'Stable'], observed_bandwidth=3_000_000)
        history_issue = next(i for i in history if 'WFU' in i['title'])
        assert 'no uptime history for this relay' in history_issue['description']
        assert 'no uptime credit' in history_issue['suggestion']
        short_track = [{
            'authority': 'bastet', 'wfu_met': False, 'tk_met': False, 'bw_met': True,
            'wfu_value': 0.0, 'wfu_threshold': 0.98, 'tk_value': 6, 'tk_threshold': GUARD_TK_DEFAULT,
        }]
        short = generate_issues_from_consensus({
            'in_consensus': True,
            'total_authorities': 1,
            'authority_votes': [{'wfu': 0.0, 'tk': 6}],
            'reachability': {'ipv4_reachable_count': 1},
            'flag_eligibility': {'guard': {'details': short_track}},
        }, current_flags=['Fast', 'Stable'], observed_bandwidth=3_000_000)
        short_text = next(i for i in short if 'WFU' in i['title'])['description']
        assert 'measured 0% (no uptime history for this relay).' in short_text
        assert 'no uptime credit).' not in short_text

    def test_warning_uses_the_relay_total_not_the_registry(self):
        """Eight voters on the page stay 4/8 in the warning, even if the registry says 9."""
        details = [
            {'authority': f'a{i}', 'wfu_met': i < 4, 'tk_met': True, 'bw_met': True, 'wfu_threshold': 0.98}
            for i in range(8)
        ]
        issues = generate_issues_from_consensus({
            'in_consensus': True,
            'total_authorities': 8,
            'authority_votes': [],
            'reachability': {'ipv4_reachable_count': 8},
            'flag_eligibility': {'guard': {'details': details}},
        }, current_flags=['Fast', 'Stable'], observed_bandwidth=3_000_000)
        wfu = next(i for i in issues if 'WFU' in i['title'])
        assert wfu['description'].startswith('4/8 authorities meet guard-wfu (≥98%; 5 needed).')

    def test_a_miss_does_not_round_up_to_the_threshold(self):
        """97.9995% is not printed as 98.0% beside a ≥98% bar, nor 7.97 days as 8.0."""
        details = [{
            'authority': 'bastet', 'bw_met': True,
            'wfu_met': False, 'wfu_value': 0.979995, 'wfu_threshold': 0.98,
            'tk_met': False, 'tk_value': 688363, 'tk_threshold': GUARD_TK_DEFAULT,
        }]
        issues = generate_issues_from_consensus({
            'in_consensus': True,
            'total_authorities': 1,
            'authority_votes': [{'wfu': 0.979995, 'tk': 688363}],
            'reachability': {'ipv4_reachable_count': 1},
            'flag_eligibility': {'guard': {'details': details}},
        }, current_flags=['Fast', 'Stable'], observed_bandwidth=3_000_000)
        by_title = {i['title']: i['description'] for i in issues}
        assert '98.0%' not in by_title['Guard: WFU below threshold']
        assert '97.999%' in by_title['Guard: WFU below threshold']
        assert '8.0 days' not in by_title['Guard: Time Known below threshold']
        assert '7.97 days' in by_title['Guard: Time Known below threshold']

    def test_hours_of_time_known_are_history(self):
        """Six seconds is no history. Twenty hours is a short measurement."""
        def issue_for(seconds):
            details = [{
                'authority': 'bastet', 'bw_met': True, 'wfu_met': True,
                'tk_met': False, 'tk_value': seconds, 'tk_threshold': GUARD_TK_DEFAULT,
            }]
            issues = generate_issues_from_consensus({
                'in_consensus': True,
                'total_authorities': 1,
                'authority_votes': [{'tk': seconds}],
                'reachability': {'ipv4_reachable_count': 1},
                'flag_eligibility': {'guard': {'details': details}},
            }, current_flags=['Fast', 'Stable'], observed_bandwidth=3_000_000)
            return next(i for i in issues if 'Time Known' in i['title'])
        assert 'no time-known history' in issue_for(6)['description']
        hours = issue_for(20 * 3600)
        assert 'no time-known history' not in hours['description']
        assert 'known this relay for 20.0 hours' in hours['description']
        assert 'keep running stably' in hours['suggestion']

    def test_collector_zero_and_missing_wfu_reach_the_warning(self):
        """Collector keeps published 0 and omits a missing stats line, then the warning says so."""
        from allium.lib.consensus.collector_fetcher import CollectorFetcher
        fetcher = CollectorFetcher()
        fetcher.flag_thresholds = {
            name: {'guard-wfu': 0.98, 'guard-tk': GUARD_TK_DEFAULT,
                   'guard-bw-inc-exits': 1_000_000, 'guard-bw-exc-exits': 1_000_000}
            for name in _VOTING_AUTHORITIES
        }
        votes = {}
        measured_low = {'faravahar', 'gabelmoo', 'longclaw', 'maatuska', 'tor26'}
        for name in _VOTING_AUTHORITIES:
            votes[name] = {
                'flags': ['Fast', 'Stable', 'V2Dir', 'Running', 'Valid'],
                'bandwidth': 5000, 'measured': 5000, 'tk': 20 * SECONDS_PER_DAY,
            }
            if name == 'bastet':
                votes[name]['wfu'] = 0.0
            elif name == 'moria1':
                pass
            elif name in measured_low:
                votes[name]['wfu'] = 0.90
            else:
                votes[name]['wfu'] = 0.99
        eligibility = fetcher._analyze_flag_eligibility({'votes': votes})
        by_auth = {d['authority']: d for d in eligibility['guard']['details']}
        assert by_auth['bastet']['wfu_value'] == 0.0
        assert by_auth['bastet']['wfu_met'] is False
        assert by_auth['moria1']['wfu_value'] is None
        assert by_auth['moria1']['wfu_met'] is False
        assert by_auth['dannenberg']['wfu_met'] is True
        formatted = fetcher._format_authority_votes({'votes': votes})
        assert next(v for v in formatted if v['authority'] == 'bastet')['wfu_display'] == '0.0%'
        assert next(v for v in formatted if v['authority'] == 'moria1')['wfu_display'] == 'N/A'
        issues = generate_issues_from_consensus({
            'in_consensus': True,
            'total_authorities': 9,
            'authority_votes': formatted,
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': eligibility,
        }, current_flags=['Fast', 'Stable', 'V2Dir'], observed_bandwidth=5_000_000)
        wfu = next(i for i in issues if i['title'] == 'Guard: WFU below threshold')
        assert wfu['description'].startswith('2/9 authorities meet guard-wfu (≥98%; 5 needed).')
        assert 'bastet measured 0% (no uptime credit).' in wfu['description']
        assert 'no uptime history' not in wfu['description']
        assert 'moria1 published no WFU.' in wfu['description']
        assert 'moria1 measured 0%' not in wfu['description']

    def test_guard_requires_stable_is_warning(self):
        """Test Guard requires Stable flag is WARNING (changed from info)."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.99, 'tk': 10 * SECONDS_PER_DAY}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
        }
        
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Fast'],  # Has Fast but not Stable
            observed_bandwidth=3_000_000
        )
        
        stable_issues = [i for i in issues if 'Guard' in i['title'] and 'Stable' in i['title']]
        assert len(stable_issues) >= 1
        assert stable_issues[0]['severity'] == 'warning'  # Changed from 'info'
    
    def test_guard_requires_fast_is_warning(self):
        """Test Guard requires Fast flag is WARNING (changed from info)."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.99, 'tk': 10 * SECONDS_PER_DAY}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
        }
        
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Stable'],  # Has Stable but not Fast
            observed_bandwidth=3_000_000
        )
        
        fast_issues = [i for i in issues if 'Guard' in i['title'] and 'Fast' in i['title']]
        assert len(fast_issues) >= 1
        assert fast_issues[0]['severity'] == 'warning'  # Changed from 'info'
    
    def test_stable_not_eligible_is_warning(self):
        """Test Not eligible for Stable flag is WARNING (changed from info)."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.99, 'tk': 5 * SECONDS_PER_DAY}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {
                'stable': {'eligible_count': 2, 'details': [{'authority': 'bastet', 'eligible': False}]},
            },
        }
        
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Fast'],  # No Stable flag
            observed_bandwidth=3_000_000
        )
        
        stable_issues = [i for i in issues if i['category'] == 'stable']
        assert len(stable_issues) == 1
        assert stable_issues[0]['severity'] == 'warning'  # Changed from 'info'
        assert stable_issues[0]['description'].startswith(
            '2/9 authorities meet Stable (uptime or MTBF at or above their own median; 5 needed).')
    
    def test_hsdir_uptime_below_is_warning(self):
        """Fast, Stable and V2Dir without HSDir: the 96-hour uptime check is the one WARNING.

        WFU and Time Known below the old 98% / 25-hour rule are not HSDir issues.
        """
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.90, 'tk': 10 * 3600}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {'hsdir': {'assigned_count': 4}},
        }
        
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Guard', 'Stable', 'Fast', 'V2Dir'],  # No HSDir
            observed_bandwidth=3_000_000
        )
        
        hsdir_issues = [i for i in issues if i['category'] == 'hsdir']
        assert [i['title'] for i in hsdir_issues] == ['HSDir: uptime below 96 hours']
        assert hsdir_issues[0]['severity'] == 'warning'
        assert hsdir_issues[0]['section'] == 'flag-hsdir-uptime'
        assert hsdir_issues[0]['description'].startswith('Only 4/9 authorities voted HSDir')
    
    def test_hsdir_requires_stable_is_warning(self):
        """Test HSDir requires Stable flag is WARNING when Stable missing."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.99, 'tk': 10 * SECONDS_PER_DAY}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
        }
        
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Fast'],  # No HSDir, no Stable
            observed_bandwidth=3_000_000
        )
        
        hsdir_stable_issues = [i for i in issues if i['category'] == 'hsdir' and 'requires Stable' in i['title']]
        assert len(hsdir_stable_issues) == 1
        assert hsdir_stable_issues[0]['severity'] == 'warning'
    
    def test_hsdir_requires_fast_is_warning(self):
        """Test HSDir requires Fast flag is WARNING when Fast missing."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.99, 'tk': 10 * SECONDS_PER_DAY}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
        }
        
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Stable'],  # No HSDir, no Fast
            observed_bandwidth=3_000_000
        )
        
        hsdir_fast_issues = [i for i in issues if i['category'] == 'hsdir' and 'requires Fast' in i['title']]
        assert len(hsdir_fast_issues) == 1
        assert hsdir_fast_issues[0]['severity'] == 'warning'
    
    def test_hsdir_requires_v2dir_is_warning(self):
        """Test HSDir requires V2Dir flag is WARNING when V2Dir missing.
        
        This is the root cause for relays like Doomereu1: has Stable, Fast,
        good WFU/TK, but missing V2Dir because descriptor lacks
        tunnelled-dir-server (DirCache 0 in torrc).
        """
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.99, 'tk': 10 * SECONDS_PER_DAY}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
        }
        
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Stable', 'Fast'],  # No HSDir, no V2Dir, but has Stable+Fast
            observed_bandwidth=3_000_000
        )
        
        hsdir_v2dir_issues = [i for i in issues if i['category'] == 'hsdir' and 'V2Dir' in i['title']]
        assert len(hsdir_v2dir_issues) == 1
        assert hsdir_v2dir_issues[0]['severity'] == 'warning'
        assert 'tunnelled-dir-server' in hsdir_v2dir_issues[0]['description']
    
    def test_hsdir_no_prereq_warning_when_has_all(self):
        """Test no HSDir prerequisite warnings when relay has Stable, Fast, and V2Dir."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.99, 'tk': 10 * SECONDS_PER_DAY}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
        }
        
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Stable', 'Fast', 'V2Dir'],  # No HSDir, but has all prereqs
            observed_bandwidth=3_000_000
        )
        
        hsdir_prereq_issues = [i for i in issues if i['category'] == 'hsdir' and 'requires' in i['title']]
        assert len(hsdir_prereq_issues) == 0
    
    def test_high_consensus_weight_deviation(self):
        """Test high consensus weight deviation (warning severity)."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.99, 'tk': 10 * SECONDS_PER_DAY}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
            'bandwidth': {
                'deviation': 10000,
                'median': 5000,  # deviation > median * 0.5
            },
        }
        
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Guard', 'Stable', 'Fast', 'HSDir'],
            observed_bandwidth=3_000_000
        )
        
        bw_issues = [i for i in issues if i['category'] == 'bandwidth']
        assert len(bw_issues) >= 1
        assert bw_issues[0]['severity'] == 'warning'
    
    def test_low_bandwidth_authority_measurements(self):
        """Test low bandwidth authority measurements (warning severity)."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.99, 'tk': 10 * SECONDS_PER_DAY}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
            'bandwidth': {
                'bw_auth_measured_count': 1,  # Only 1 measurement
                'bw_auth_total': 6,
            },
        }
        
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Guard', 'Stable', 'Fast', 'HSDir'],
            observed_bandwidth=3_000_000
        )
        
        bw_issues = [i for i in issues if 'bandwidth authority' in i['title'].lower()]
        assert len(bw_issues) >= 1
        assert bw_issues[0]['severity'] == 'warning'
        assert '1/6' in bw_issues[0]['description']
    
    def test_bandwidth_authority_below_majority(self):
        """Test bandwidth authority measurements below majority (info severity)."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.99, 'tk': 10 * SECONDS_PER_DAY}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
            'bandwidth': {
                'bw_auth_measured_count': 3,  # 3 measurements, below majority of 4
                'bw_auth_total': 6,
            },
        }
        
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Guard', 'Stable', 'Fast', 'HSDir'],
            observed_bandwidth=3_000_000
        )
        
        bw_issues = [i for i in issues if 'majority' in i['title'].lower()]
        assert len(bw_issues) >= 1
        assert bw_issues[0]['severity'] == 'info'
        assert '3/6' in bw_issues[0]['description']
    
    def test_staledesc_flag(self):
        """Test StaleDesc flag detection (warning severity)."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [
                {'voted': True, 'flags': ['StaleDesc', 'Running'], 'wfu': 0.99, 'tk': 10 * SECONDS_PER_DAY}
            ],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
        }
        
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Guard', 'Stable', 'Fast', 'HSDir'],
            observed_bandwidth=3_000_000
        )
        
        staledesc_issues = [i for i in issues if 'StaleDesc' in i['title']]
        assert len(staledesc_issues) == 1  # Only reported once
        assert staledesc_issues[0]['severity'] == 'warning'
    
    def test_badexit_flag(self):
        """Test BadExit flag detection (error severity)."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.99, 'tk': 10 * SECONDS_PER_DAY}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
        }
        
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['BadExit', 'Guard', 'Stable', 'Fast', 'HSDir'],
            observed_bandwidth=3_000_000
        )
        
        badexit_issues = [i for i in issues if 'BadExit' in i['title']]
        assert len(badexit_issues) >= 1
        assert badexit_issues[0]['severity'] == 'error'
    
    def test_version_not_recommended(self):
        """Test version not recommended (warning severity)."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.99, 'tk': 10 * SECONDS_PER_DAY}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
        }
        
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Guard', 'Stable', 'Fast', 'HSDir'],
            observed_bandwidth=3_000_000,
            version='0.4.8.10',
            recommended_version=False
        )
        
        version_issues = [i for i in issues if i['category'] == 'version']
        assert len(version_issues) >= 1
        assert version_issues[0]['severity'] == 'warning'
        assert '0.4.8.10' in version_issues[0]['description']


class TestOverloadIssues:
    """Tests for overload-related issues (6 types)."""
    
    def test_general_overload_active(self):
        """Test General Overload Active within 72 hours (error severity)."""
        now_ms = int(time.time() * 1000)
        relay = {
            'overload_general_timestamp': now_ms - (1 * 3600 * 1000),  # 1 hour ago
        }
        
        issues = _check_overload_issues(relay)
        
        general_issues = [i for i in issues if 'General Overload Active' in i['title']]
        assert len(general_issues) == 1
        assert general_issues[0]['severity'] == 'error'
        assert 'OOM' in general_issues[0]['description'] or 'onionskin' in general_issues[0]['description']
    
    def test_recent_overload_reported(self):
        """Test Recent Overload Reported 72h-7d ago (info severity)."""
        now_ms = int(time.time() * 1000)
        relay = {
            'overload_general_timestamp': now_ms - (4 * 24 * 3600 * 1000),  # 4 days ago
        }
        
        issues = _check_overload_issues(relay)
        
        recent_issues = [i for i in issues if 'Recent Overload Reported' in i['title']]
        assert len(recent_issues) == 1
        assert recent_issues[0]['severity'] == 'info'
    
    def test_overload_outside_7_days_not_reported(self):
        """Test that overload older than 7 days is not reported."""
        now_ms = int(time.time() * 1000)
        relay = {
            'overload_general_timestamp': now_ms - (10 * 24 * 3600 * 1000),  # 10 days ago
        }
        
        issues = _check_overload_issues(relay)
        
        overload_issues = [i for i in issues if 'overload' in i['category']]
        assert len(overload_issues) == 0
    
    def test_fd_exhaustion_with_timestamp(self):
        """Test File Descriptor Exhaustion with timestamp (error severity)."""
        now_ms = int(time.time() * 1000)
        relay = {
            'overload_fd_exhausted': {
                'timestamp': now_ms - (2 * 3600 * 1000),  # 2 hours ago
            },
        }
        
        issues = _check_overload_issues(relay)
        
        fd_issues = [i for i in issues if 'File Descriptor' in i['title']]
        assert len(fd_issues) == 1
        assert fd_issues[0]['severity'] == 'error'
        assert 'LimitNOFILE' in fd_issues[0]['suggestion']
    
    def test_fd_exhaustion_without_timestamp(self):
        """Test File Descriptor Exhaustion without timestamp (error severity)."""
        relay = {
            'overload_fd_exhausted': {},  # No timestamp
        }
        
        issues = _check_overload_issues(relay)
        
        fd_issues = [i for i in issues if 'File Descriptor' in i['title']]
        assert len(fd_issues) == 1
        assert fd_issues[0]['severity'] == 'error'
    
    def test_write_bandwidth_limit_hit(self):
        """Test Write Bandwidth Limit Hit (warning severity)."""
        relay = {
            'overload_ratelimits': {
                'rate-limit': 1_000_000,  # 1 MB/s
                'burst-limit': 2_000_000,
                'write-count': 500,
                'read-count': 0,
            },
        }
        
        issues = _check_overload_issues(relay)
        
        write_issues = [i for i in issues if 'Write' in i['title']]
        assert len(write_issues) == 1
        assert write_issues[0]['severity'] == 'warning'
        assert '500' in write_issues[0]['description']
    
    def test_read_bandwidth_limit_hit(self):
        """Test Read Bandwidth Limit Hit (warning severity)."""
        relay = {
            'overload_ratelimits': {
                'rate-limit': 1_000_000,
                'burst-limit': 2_000_000,
                'write-count': 0,
                'read-count': 1000,
            },
        }
        
        issues = _check_overload_issues(relay)
        
        read_issues = [i for i in issues if 'Read' in i['title']]
        assert len(read_issues) == 1
        assert read_issues[0]['severity'] == 'warning'
        assert '1,000' in read_issues[0]['description']
    
    def test_rate_limit_configuration(self):
        """Test Rate Limit Configuration info (info severity)."""
        relay = {
            'overload_ratelimits': {
                'rate-limit': 1_000_000,
                'burst-limit': 2_000_000,
                'write-count': 100,
                'read-count': 200,
            },
        }
        
        issues = _check_overload_issues(relay, use_bits=False)
        
        config_issues = [i for i in issues if 'Configuration' in i['title']]
        assert len(config_issues) == 1
        assert config_issues[0]['severity'] == 'info'
        assert 'Rate=' in config_issues[0]['description']
        assert 'Burst=' in config_issues[0]['description']
    
    def test_rate_limit_formatting_bits(self):
        """Test that rate limits are formatted correctly with use_bits=True."""
        relay = {
            'overload_ratelimits': {
                'rate-limit': 1_000_000,  # 1 MB/s = 8 Mbit/s
                'burst-limit': 2_000_000,
                'write-count': 100,
                'read-count': 0,
            },
        }
        
        issues = _check_overload_issues(relay, use_bits=True)
        
        write_issues = [i for i in issues if 'Write' in i['title']]
        assert len(write_issues) == 1
        # Should contain bit notation
        desc = write_issues[0]['description']
        assert 'bit' in desc.lower() or 'Mbit' in desc
    
    def test_multiple_overload_conditions(self):
        """Test that multiple overload conditions create separate issues."""
        now_ms = int(time.time() * 1000)
        relay = {
            'overload_general_timestamp': now_ms - (1 * 3600 * 1000),  # Active
            'overload_fd_exhausted': {'timestamp': now_ms},
            'overload_ratelimits': {
                'rate-limit': 1_000_000,
                'burst-limit': 2_000_000,
                'write-count': 100,
                'read-count': 200,
            },
        }
        
        issues = _check_overload_issues(relay)
        
        # Should have: General Active, FD Exhaustion, Write Limit, Read Limit, Rate Config
        assert len(issues) >= 4
        titles = [i['title'] for i in issues]
        assert any('General Overload' in t for t in titles)
        assert any('File Descriptor' in t for t in titles)
        assert any('Write' in t for t in titles)
        assert any('Read' in t for t in titles)
    
    def test_no_overload_issues_for_clean_relay(self):
        """Test that clean relay has no overload issues."""
        relay = {
            'fingerprint': 'ABC123',
            'nickname': 'CleanRelay',
        }
        
        issues = _check_overload_issues(relay)
        
        assert len(issues) == 0


class TestNoIssuesForHealthyRelay:
    """Test that healthy relays have no issues detected."""
    
    def test_healthy_relay_no_issues(self):
        """Test that a fully healthy relay produces no issues."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.99, 'tk': 30 * SECONDS_PER_DAY}],
            'reachability': {
                'ipv4_reachable_count': 9,
                'ipv6_reachable_count': 8,  # Most authorities can reach IPv6
                'ipv6_not_tested_authorities': [],
            },
            'flag_eligibility': {
                'guard': {'eligible_count': 9},
                'stable': {'eligible_count': 9},
                'hsdir': {'eligible_count': 9},
            },
        }
        
        relay = {
            'flags': ['Guard', 'Stable', 'Fast', 'Valid', 'Running', 'HSDir', 'V2Dir'],
            'observed_bandwidth': 10_000_000,  # 10 MB/s
            'version': '0.4.8.12',
            'recommended_version': True,
        }
        
        issues = generate_relay_issues(relay, consensus_data)
        
        # Filter out info-level notes
        real_issues = [i for i in issues if i['severity'] != 'info']
        assert len(real_issues) == 0


class TestIssueSectionAnchors:
    """Issues must hyperlink to the relay-info page section with more details.

    Each issue carries a `section` key naming an anchor that exists on the
    relay page (relay-info.html). Clicking an issue title scrolls to that
    section (highlighted via the :target CSS rule).
    """

    def _issues(self, **kwargs):
        base = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.90, 'tk': 3 * SECONDS_PER_DAY}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
        }
        base.update(kwargs)
        return generate_issues_from_consensus(
            base,
            current_flags=kwargs.pop('current_flags', ['Stable']),
            observed_bandwidth=kwargs.pop('observed_bandwidth', 1_000_000),
        )

    def test_flag_eligibility_issues_link_to_flag_rows(self):
        """Missing Fast and low bandwidth link to the Guard and HSDir requirement rows."""
        issues = self._issues(current_flags=['Stable'])  # no Fast, no Guard, no HSDir
        by_title = {i['title']: i['section'] for i in issues}
        assert by_title['Guard: requires Fast flag'] == 'flag-guard-prereq-fast'
        assert by_title['Guard: bandwidth below threshold'] == 'flag-guard-bandwidth'
        assert by_title['HSDir: requires Fast flag'] == 'flag-hsdir-prereq-fast'

    def test_reachability_issues_link_to_running_rows(self):
        """IPv4 and IPv6 reachability issues link to the Running flag rows."""
        issues = self._issues(reachability={
            'ipv4_reachable_count': 3,
            'ipv4_reachable_authorities': ['bastet', 'dannenberg', 'dizum'],
            'ipv6_reachable_count': 0,
            'ipv6_not_tested_authorities': ['moria1'],
        })
        by_title = {i['title']: i['section'] for i in issues}
        assert by_title['IPv4 reachability issues'] == 'flag-running-ipv4-reachability'
        assert by_title['IPv6 not reachable'] == 'flag-running-ipv6-reachability'

    def test_not_in_consensus_links_to_running_column(self):
        """Not in consensus links to the per-authority Running column."""
        issues = self._issues(in_consensus=False, vote_count=3)
        consensus = [i for i in issues if i['category'] == 'consensus']
        assert len(consensus) == 1
        assert consensus[0]['section'] == 'col-running'

    def test_weight_deviation_links_to_cons_wt_column(self):
        """Consensus weight deviation links to the per-authority Cons Wt column."""
        issues = self._issues(
            current_flags=['Guard', 'Stable', 'Fast', 'HSDir'],
            observed_bandwidth=10_000_000,
            bandwidth={'deviation': 10000, 'median': 5000},
        )
        dev = [i for i in issues if 'deviation' in i['title']]
        assert len(dev) == 1
        assert dev[0]['section'] == 'col-cons-wt'

    def test_bw_measurement_issues_link_to_measured_by(self):
        """Bandwidth-authority measurement issues link to the Measured By line."""
        issues = self._issues(
            current_flags=['Guard', 'Stable', 'Fast', 'HSDir'],
            observed_bandwidth=10_000_000,
            bandwidth={'bw_auth_measured_count': 1, 'bw_auth_total': 6},
        )
        meas = [i for i in issues if 'bandwidth authority' in i['title'].lower()]
        assert len(meas) == 1
        assert meas[0]['section'] == 'bw-measured-by'

    def test_staledesc_links_to_desc_published_column(self):
        """StaleDesc links to the per-authority Desc Published column."""
        issues = self._issues(
            authority_votes=[{'voted': True, 'flags': ['StaleDesc', 'Running'],
                              'wfu': 0.99, 'tk': 30 * SECONDS_PER_DAY}],
            current_flags=['Guard', 'Stable', 'Fast', 'HSDir'],
            observed_bandwidth=10_000_000,
        )
        stale = [i for i in issues if 'StaleDesc' in i['title']]
        assert len(stale) == 1
        assert stale[0]['section'] == 'col-desc-published'

    def test_version_issue_links_to_version_row(self):
        """A non-recommended Tor version links to the Version row."""
        issues = generate_issues_from_consensus({
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.99, 'tk': 30 * SECONDS_PER_DAY}],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
        }, current_flags=['Guard', 'Stable', 'Fast', 'HSDir', 'Valid'],
            observed_bandwidth=10_000_000, version='0.4.8.10',
            recommended_version=False)
        version = [i for i in issues if i['category'] == 'version']
        assert len(version) == 1
        assert version[0]['section'] == 'version'

    def test_overload_issues_link_to_their_detail_lines(self):
        """Each overload issue links to its own line in the overload details."""
        now_ms = int(time.time() * 1000)
        relay = {
            'overload_general_timestamp': now_ms - 3600000,  # active
            'overload_fd_exhausted': {'timestamp': now_ms},
            'overload_ratelimits': {
                'rate-limit': 1_000_000, 'burst-limit': 2_000_000,
                'write-count': 100, 'read-count': 200,
            },
        }
        issues = _check_overload_issues(relay)
        by_title = {i['title']: i['section'] for i in issues}
        assert by_title['General Overload Active'] == 'overload-general'
        assert by_title['File Descriptor Exhaustion'] == 'overload-fd'
        assert by_title['Write Bandwidth Limit Hit'] == 'overload-write'
        assert by_title['Read Bandwidth Limit Hit'] == 'overload-read'
        assert by_title['Rate Limit Configuration'] == 'overload-rate-config'


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""
    
    def test_issue_format_matches_expected(self):
        """Test that issue format matches what templates expect."""
        consensus_data = {
            'in_consensus': False,
            'vote_count': 2,
            'total_authorities': 9,
            'authority_votes': [],
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
        }
        
        issues = generate_issues_from_consensus(consensus_data)
        
        # Every issue should have required fields
        for issue in issues:
            assert 'severity' in issue
            assert 'category' in issue
            assert 'title' in issue
            assert 'description' in issue
            assert 'suggestion' in issue
            assert issue['severity'] in ('error', 'warning', 'info')


class TestReachabilityAfterAuthorityRemoval:
    """Regression tests for the stale reachability denominator bug.

    When a directory authority is removed (e.g. gabelmoo went offline), a relay
    reachable by all remaining voters must NOT be flagged 'Partial IPv4 reachability'
    (previously it showed a spurious 8/9). A genuine gap (a voter that couldn't reach
    the relay) must still be flagged, now against the dynamic denominator.
    """

    # 8 active voters (gabelmoo removed) - the voting_registry_8_voters fixture
    # from tests/conftest.py loads this same list into the shared registry
    ACTIVE_VOTERS = ACTIVE_VOTING_AUTHORITIES_8

    def test_no_partial_reachability_when_authority_removed(self, voting_registry_8_voters):
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.99, 'tk': 30 * SECONDS_PER_DAY}],
            'reachability': {
                'ipv4_reachable_count': 8,
                'ipv4_reachable_authorities': self.ACTIVE_VOTERS,
                'ipv6_reachable_count': 8,
                'ipv6_not_tested_authorities': [],
            },
            'flag_eligibility': {},
        }
        issues = generate_issues_from_consensus(consensus_data)
        titles = [i['title'] for i in issues]
        assert 'Partial IPv4 reachability' not in titles
        assert 'IPv4 reachability issues' not in titles

    def test_partial_reachability_still_flagged_for_real_gap(self, voting_registry_8_voters):
        """A voter that genuinely can't reach the relay still warns, using 7/8."""
        reachable = self.ACTIVE_VOTERS[:-1]  # all but 'tor26' can reach (7/8)
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.99, 'tk': 30 * SECONDS_PER_DAY}],
            'reachability': {
                'ipv4_reachable_count': 7,
                'ipv4_reachable_authorities': reachable,
                'ipv6_reachable_count': 7,
                'ipv6_not_tested_authorities': [],
            },
            'flag_eligibility': {},
        }
        issues = generate_issues_from_consensus(consensus_data)
        partial = [i for i in issues if i['title'] == 'Partial IPv4 reachability']
        assert len(partial) == 1
        assert '7/8' in partial[0]['description']
        assert 'tor26' in partial[0]['suggestion']  # the one missing voter


class TestFastFlagIssue:
    """forest44's real votes (tests/conftest.py): why it lacks Fast, and the rows that show it."""

    @staticmethod
    def _issues(fetcher, flags=('Running', 'Valid', 'V2Dir', 'Stable'), **kwargs):
        """Issues for forest44's votes, by title."""
        return {issue['title']: issue for issue in generate_issues_from_consensus(
            fetcher.get_relay_consensus_evaluation(FOREST44_FINGERPRINT, 9), current_flags=list(flags), **kwargs)}

    def test_example_relay_issues_link_to_flag_and_consensus_weight_details(self, forest44_fetcher):
        """forest44's real votes: missing Fast, low Guard bandwidth, uneven Cons Wt."""
        issues = self._issues(forest44_fetcher, observed_bandwidth=854_738, version='0.4.9.13',
                              recommended_version=True)
        assert [(title, issue['section']) for title, issue in issues.items() if issue['severity'] != 'info'] == [
            ('Not getting the Fast flag', 'flag-fast-speed'),
            ('Guard: requires Fast flag', 'flag-guard-prereq-fast'),
            ('Guard: bandwidth below threshold', 'flag-guard-bandwidth'),
            ('HSDir: requires Fast flag', 'flag-hsdir-prereq-fast'),
            ('High consensus weight deviation', 'col-cons-wt'),
        ]

    def test_fast_issue_explains_the_shortfall_like_the_votes(self, forest44_fetcher):
        """The Fast issue reports what the votes show: 4/9 Fast, low bwauth measurements."""
        issues = self._issues(forest44_fetcher)
        fast = issues['Not getting the Fast flag']
        assert fast['description'] == (
            "Only 4/9 authorities vote Fast (5 needed). bastet, dannenberg, gabelmoo, moria1 and tor26 "
            "measured this relay at 32.0 KB/s – 230.0 KB/s, below the Fast threshold "
            "(102.0 KB/s; moria1: 1.0 MB/s). Its consensus weight, the median of the 5 "
            "bandwidth-scanner measurements, is 68.0 KB/s.")
        assert 'underperforming compared with other relays that report a similar speed' in fast['suggestion']
        guard_bw = issues['Guard: bandwidth below threshold']['description']
        assert guard_bw.startswith(
            "0/9 authorities credit this relay with enough bandwidth for Guard (5 needed): "
            "at least 2.1 MB/s (AuthDirGuardBWGuarantee) or a place in their top 25% (10.0 MB/s – 35.0 MB/s).")
        assert 'dizum, longclaw and maatuska used the relay-reported 854.0 KB/s.' in guard_bw

    def test_fast_issue_in_bits(self, forest44_fetcher):
        """The Fast issue's rates follow the bits display."""
        description = self._issues(forest44_fetcher, use_bits=True)['Not getting the Fast flag']['description']
        assert '256.0 Kbit/s – 1.8 Mbit/s' in description
        assert '(816.0 Kbit/s; moria1: 8.4 Mbit/s)' in description
        assert description.endswith('is 544.0 Kbit/s.')

    def test_no_fast_issue_when_relay_has_fast(self, forest44_fetcher):
        """A relay that has the Fast flag gets no Fast issue."""
        assert 'Not getting the Fast flag' not in self._issues(
            forest44_fetcher, flags=('Fast', 'Running', 'Valid', 'V2Dir', 'Stable'))

    def test_fast_issue_names_authorities_that_count_relay_as_zero(self):
        """Each reason an authority withheld Fast gets its own sentence."""
        details = [
            {'authority': 'bastet', 'assigned': False, 'speed_value': 0,
             'speed_threshold': 102_000, 'speed_source': 'unmeasured'},
            {'authority': 'faravahar', 'assigned': False, 'speed_value': None,
             'speed_threshold': 102_000, 'speed_source': 'unpublished'},
            {'authority': 'dizum', 'assigned': True, 'speed_value': 854_000,
             'speed_threshold': 102_000, 'speed_source': 'reported'},
            {'authority': 'gabelmoo', 'assigned': False, 'speed_value': 500_000,
             'speed_threshold': 102_000, 'speed_source': 'measured'},
            {'authority': 'tor26', 'assigned': False, 'speed_value': 600_000,
             'speed_threshold': 102_000, 'speed_source': 'measured', 'sybil': True},
        ]
        issues = generate_issues_from_consensus({
            'in_consensus': True,
            'authority_votes': [],
            'reachability': {},
            'flag_eligibility': {'fast': {'details': details, 'assigned_count': 1}},
        }, current_flags=['Running', 'Valid'])
        fast = next(issue for issue in issues if issue['title'] == 'Not getting the Fast flag')
        assert fast['description'].startswith('Only 1/9 authorities vote Fast (5 needed). ')
        assert 'tor26 listed it as Sybil (more relays on its IP address than allowed), which clears all flags.' \
            in fast['description']
        assert 'bastet counted this relay as 0 (no measurement, relay-reported bandwidth ignored).' \
            in fast['description']
        assert 'gabelmoo did not vote Fast despite enough bandwidth.' in fast['description']
        assert 'faravahar judged it by bandwidth not shown in the votes.' in fast['description']
        assert 'measured this relay' not in fast['description']
        assert 'consensus weight' not in fast['description']


_HOLDING_GUARD = ['Guard', 'Stable', 'Fast', 'V2Dir', 'HSDir', 'Running', 'Valid']
_WFU_CONSEQUENCE = (
    'Recent downtime weighs more than older downtime. Avoid restarts '
    'while it is this close; a short outage can drop the Guard flag.'
)
_WFU_NEAR = (
    'Weighted Fractional Uptime is just above the Guard bar at '
    'bastet and dizum (95.2%, need ≥95%), maatuska (98.2%, need ≥98%) and moria1 (99.2%, need ≥99%). '
    + _WFU_CONSEQUENCE
)
_TK_CONSEQUENCE = (
    'This is weighted time, so the day count is shorter than calendar uptime, '
    'and it falls while the relay is unreachable. Stay reachable so it can move clear of the bar.'
)
_BW_CONSEQUENCE = (
    "The bar is the lower of AuthDirGuardBWGuarantee and that authority's "
    'top 25%. A dip in the bandwidth it counts can drop the Guard flag.'
)


def _guard_detail(authority, wfu, tk, bandwidth, wfu_threshold=GUARD_WFU_DEFAULT,
                  tk_threshold=GUARD_TK_DEFAULT, top25=30_000_000, bw_met=True,
                  publish_wfu=True):
    """One authority's measured-vs-threshold Guard row, as flag_eligibility stores it."""
    detail = {
        'authority': authority,
        'wfu_value': wfu,
        'tk_value': tk,
        'tk_threshold': tk_threshold,
        'bw_value': bandwidth,
        'bw_guarantee': GUARD_BW_GUARANTEE,
        'bw_top25_threshold': top25,
        'bw_met': bw_met,
        'bw_source': 'measured',
    }
    wfu_bar = wfu_threshold if publish_wfu else GUARD_WFU_DEFAULT
    if publish_wfu:
        detail['wfu_threshold'] = wfu_threshold
    detail['wfu_met'] = wfu is not None and wfu >= wfu_bar
    detail['tk_met'] = tk is not None and tk >= tk_threshold
    return detail


def _issues_with_guard_details(details, flags, votes=None, observed=10_000_000, use_bits=False):
    if votes is None:
        votes = [{'wfu': 0.99, 'tk': 30 * SECONDS_PER_DAY}]
    return generate_issues_from_consensus({
        'in_consensus': True,
        'total_authorities': 9,
        'authority_votes': votes,
        'reachability': {'ipv4_reachable_count': 9},
        'flag_eligibility': {'guard': {'details': details}},
    }, current_flags=list(flags), observed_bandwidth=observed, use_bits=use_bits)


class TestGuardNearThreshold:
    """Info notes for a relay that has Guard and is close to an authority's own bar.

    Thresholds are the ones that authority published. 98% WFU and 8 days are the
    dirauth defaults used only when a vote omits them. Bandwidth is near the lower
    of AuthDirGuardBWGuarantee and that authority's top-25% cutoff.
    """

    def test_names_each_input_and_the_authorities_close_to_their_own_bar(self):
        """Just above a published bar, including a stricter moria1 and an omitted default."""
        wfu_slack = GUARD_WFU_NEAR_MARGIN * 0.4
        tk_near = GUARD_TK_DEFAULT + GUARD_TK_NEAR_MARGIN * 0.4
        comfortable_tk = 30 * SECONDS_PER_DAY
        comfortable_bw = 20_000_000
        details = [
            _guard_detail('bastet', 0.95 + wfu_slack, comfortable_tk, comfortable_bw, wfu_threshold=0.95),
            _guard_detail('dizum', 0.95 + wfu_slack, comfortable_tk, comfortable_bw, wfu_threshold=0.95),
            # Vote omitted guard-wfu: the 98% dirauth default applies, and this value is inside half a point.
            _guard_detail('maatuska', GUARD_WFU_DEFAULT + wfu_slack, comfortable_tk, comfortable_bw,
                          publish_wfu=False),
            _guard_detail('moria1', 0.99 + wfu_slack, tk_near,
                          1_000_000 + int(1_000_000 * GUARD_BW_NEAR_FRACTION * 0.6),
                          wfu_threshold=0.99, top25=1_000_000),
            _guard_detail('longclaw', 0.995, 40 * SECONDS_PER_DAY, comfortable_bw),
            _guard_detail('faravahar', 0.999, 40 * SECONDS_PER_DAY, None),
        ]
        issues = _issues_with_guard_details(details, _HOLDING_GUARD)
        notes = [issue for issue in issues if issue['severity'] == 'info' and issue['category'] == 'guard']
        by_title = {issue['title']: issue for issue in notes}

        assert [issue['title'] for issue in notes] == [
            'Guard: WFU near threshold',
            'Guard: Time Known near threshold',
            'Guard: bandwidth near threshold',
        ]
        assert not any(issue['category'] == 'guard' and issue['severity'] != 'info' for issue in issues)
        assert by_title['Guard: WFU near threshold']['section'] == 'flag-guard-wfu'
        assert by_title['Guard: WFU near threshold']['description'] == _WFU_NEAR
        assert 'longclaw' not in by_title['Guard: WFU near threshold']['description']
        assert 'faravahar' not in by_title['Guard: WFU near threshold']['description']
        assert by_title['Guard: Time Known near threshold']['section'] == 'flag-guard-time-known'
        assert by_title['Guard: Time Known near threshold']['description'] == (
            'Time Known is just above the Guard bar at moria1 (8.4 days, need ≥8 days). '
            + _TK_CONSEQUENCE
        )
        bandwidth = by_title['Guard: bandwidth near threshold']
        assert bandwidth['section'] == 'flag-guard-bandwidth'
        assert bandwidth['description'] == (
            'Bandwidth counted for Guard is just above the Guard bar at '
            'moria1 (1.1 MB/s, need ≥1.0 MB/s). ' + _BW_CONSEQUENCE
        )
        assert '2.1 MB/s' not in bandwidth['description']

        bits = _issues_with_guard_details(details, _HOLDING_GUARD, use_bits=True)
        bits_bw = next(issue for issue in bits if issue['title'] == 'Guard: bandwidth near threshold')
        assert 'moria1 (8.5 Mbit/s, need ≥8.0 Mbit/s)' in bits_bw['description']

    def test_comfortably_above_every_published_threshold_has_no_note(self):
        """98.4% WFU and 2.2 MB/s stay quiet when the authority published a lower bar."""
        top25 = 1_000_000
        binding_margin = top25 * GUARD_BW_NEAR_FRACTION
        # 2.2 MB/s is inside the guessed 2.0–2.5 MB/s band, and 1.2 MB above this top-25% cutoff.
        guessed_bw_window = 2_200_000
        assert guessed_bw_window - top25 > binding_margin
        details = [
            # 98.4% would be "near 98%" under a fixed band. This authority published 95%.
            _guard_detail('bastet', 0.984, 30 * SECONDS_PER_DAY, guessed_bw_window,
                          wfu_threshold=0.95, top25=top25),
            _guard_detail('moria1', 0.999, 20 * SECONDS_PER_DAY, guessed_bw_window,
                          wfu_threshold=0.97, tk_threshold=12 * SECONDS_PER_DAY, top25=top25),
            # Exactly one WFU percentage point above the published bar is outside the open margin.
            _guard_detail('gabelmoo', 0.95 + GUARD_WFU_NEAR_MARGIN, 30 * SECONDS_PER_DAY, 20_000_000,
                          wfu_threshold=0.95),
            _guard_detail('longclaw', 0.999, 60 * SECONDS_PER_DAY, 50_000_000, top25=40_000_000),
            # A published 0 is a real measurement and is far from a 98% bar.
            _guard_detail('tor26', 0.0, 40 * SECONDS_PER_DAY, 20_000_000),
            _guard_detail('dizum', None, 40 * SECONDS_PER_DAY, 20_000_000),
        ]
        issues = _issues_with_guard_details(details, _HOLDING_GUARD)
        assert [issue['title'] for issue in issues if 'near threshold' in issue['title']] == []
        assert [issue for issue in issues if issue['category'] == 'guard'] == []

    def test_just_under_one_authority_while_the_flag_is_held(self):
        """A consensus Guard can still be just under one authority's published bar."""
        wfu_slack = GUARD_WFU_NEAR_MARGIN * 0.4
        comfortable_tk = 30 * SECONDS_PER_DAY
        comfortable_bw = 20_000_000
        details = [
            _guard_detail('bastet', 0.95 + wfu_slack, comfortable_tk, comfortable_bw, wfu_threshold=0.95),
            _guard_detail('moria1', 0.99 - wfu_slack, comfortable_tk, comfortable_bw, wfu_threshold=0.99),
        ]
        issues = _issues_with_guard_details(details, _HOLDING_GUARD)
        notes = [issue for issue in issues if issue['category'] == 'guard']
        assert [issue['title'] for issue in notes] == ['Guard: WFU near threshold']
        assert notes[0]['severity'] == 'info'
        assert notes[0]['description'] == (
            'Weighted Fractional Uptime is just above the Guard bar at bastet (95.2%, need ≥95%) '
            'and just under the Guard bar at moria1 (98.8%, need ≥99%). ' + _WFU_CONSEQUENCE
        )

    def test_guard_already_lost_keeps_majority_failure_text(self):
        """Without Guard, the per-authority majority warning stays and the near note does not."""
        flags = ['Stable', 'Fast', 'V2Dir', 'HSDir']
        votes = [{'wfu': 0.90, 'tk': 3 * SECONDS_PER_DAY}]
        # No per-authority rows: one vote's 90% WFU is not a warning. Bandwidth still is.
        bare = _issues_with_guard_details([], flags, votes=votes, observed=1_000_000)
        bare_guard = [issue for issue in bare if issue['category'] == 'guard']
        assert [issue['title'] for issue in bare_guard] == ['Guard: bandwidth below threshold']
        assert bare_guard[0]['description'] == (
            'Observed bandwidth 1 MB/s is below the 2.1 MB/s AuthDirGuardBWGuarantee')

        short = []
        for name in _VOTING_AUTHORITIES:
            row = _guard_detail(name, 0.90, 3 * SECONDS_PER_DAY, 20_000_000, bw_met=True)
            short.append(row)
        missed = _issues_with_guard_details(short, flags, votes=votes, observed=3_000_000)
        guard = [issue for issue in missed if issue['category'] == 'guard']
        names = ', '.join(_VOTING_AUTHORITIES[:-1]) + ' and ' + _VOTING_AUTHORITIES[-1]
        assert [issue['title'] for issue in guard] == [
            'Guard: WFU below threshold',
            'Guard: Time Known below threshold',
        ]
        assert all(issue['severity'] == 'warning' for issue in guard)
        assert guard[0]['description'] == (
            '0/9 authorities meet guard-wfu (≥98%; 5 needed). ' + names + ' measured 90.0%.')
        assert guard[1]['description'] == (
            '0/9 authorities meet guard-tk (≥8 days; 5 needed). '
            + names + ' have known this relay for 3.0 days.')
        assert [issue['title'] for issue in missed if 'near threshold' in issue['title']] == []

        # Just above every bar, but the consensus flag is already gone: no info note.
        near = [
            _guard_detail(name, 0.984, 30 * SECONDS_PER_DAY, 20_000_000, bw_met=True)
            for name in _VOTING_AUTHORITIES
        ]
        held_off = _issues_with_guard_details(near, flags, votes=votes, observed=3_000_000)
        assert [issue for issue in held_off if issue['category'] == 'guard'] == []
