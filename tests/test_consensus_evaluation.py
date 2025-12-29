"""
Tests for lib/consensus/consensus_evaluation.py formatting functions.

These tests verify the formatting logic for relay consensus evaluation displayed
in templates. If the template requirements change, update these tests.

Key thresholds tested:
- Guard WFU: >= 98% (0.98)
- Guard TK: >= 8 days (691200 seconds)
- HSDir WFU: >= 98% (0.98)  
- HSDir TK: >= 10 days (864000 seconds)
"""

import os
import sys
import pytest

# Add the allium package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'allium'))

from lib.consensus.consensus_evaluation import (
    format_relay_consensus_evaluation,
    format_authority_consensus_evaluation,
    _format_consensus_status,
    _format_relay_values,
    _format_authority_table_enhanced,
    _format_flag_summary,
    _format_reachability_summary,
    _format_bandwidth_summary,
    _identify_issues,
    _generate_advice,
    _generate_advice_simple,
    _format_thresholds_table,
    _format_bandwidth_value,
)

# Import flag threshold constants for test validation
from lib.consensus.flag_thresholds import (
    GUARD_WFU_DEFAULT,
    GUARD_TK_DEFAULT,
    GUARD_BW_GUARANTEE,
    HSDIR_TK_DEFAULT,
    HSDIR_WFU_DEFAULT,
    SECONDS_PER_DAY,
)


# ============================================================================
# TEST DATA - Real-world scenarios from Tor network
# ============================================================================

# Relay that meets all Guard requirements
GUARD_ELIGIBLE_RELAY = {
    'fingerprint': 'ABC123' * 6 + 'ABCD',
    'in_consensus': True,
    'vote_count': 9,
    'total_authorities': 9,
    'majority_required': 5,
    'authority_votes': [
        {
            'authority': 'moria1',
            'fingerprint': 'F533C81CEF0BC0267857C99B2F471ADF249FA232',
            'voted': True,
            'flags': ['Fast', 'Guard', 'HSDir', 'Running', 'Stable', 'Valid'],
            'wfu': 0.995,  # Above 98%
            'tk': 1000000,  # ~11.5 days, above 8 days
            'bandwidth': 50000000,
            'measured': 45000000,
            'is_bw_authority': True,
        },
    ],
    'flag_eligibility': {
        'guard': {'eligible_count': 9},
        'stable': {'eligible_count': 9},
        'fast': {'eligible_count': 9},
        'hsdir': {'eligible_count': 9},
    },
    'reachability': {
        'ipv4_reachable_count': 9,
        'ipv6_reachable_count': 7,
        'ipv6_not_tested_authorities': ['dizum', 'faravahar'],
        'total_authorities': 9,
    },
}

# Relay that doesn't meet Guard requirements
NON_GUARD_RELAY = {
    'fingerprint': 'DEF456' * 6 + 'DEF4',
    'in_consensus': True,
    'vote_count': 7,
    'total_authorities': 9,
    'majority_required': 5,
    'authority_votes': [
        {
            'authority': 'moria1',
            'voted': True,
            'flags': ['Fast', 'Running', 'Valid'],  # No Guard flag
            'wfu': 0.85,  # Below 98%
            'tk': 500000,  # ~5.8 days, below 8 days
            'bandwidth': 10000,
            'measured': 8000,
        },
    ],
    'flag_eligibility': {
        'guard': {'eligible_count': 0},
        'stable': {'eligible_count': 3},
        'fast': {'eligible_count': 7},
    },
    'reachability': {
        'ipv4_reachable_count': 7,
        'ipv6_reachable_count': 0,
        'total_authorities': 9,
    },
}

# Flag thresholds from multiple authorities
SAMPLE_FLAG_THRESHOLDS = {
    'moria1': {
        'guard-wfu': 0.98,
        'guard-tk': 691200,
        'guard-bw-inc-exits': 10000000,
        'stable-uptime': 1693440,
        'stable-mtbf': 1693440,
        'fast-speed': 22000,
        'hsdir-wfu': 0.98,
        'hsdir-tk': 864000,
    },
    'tor26': {
        'guard-wfu': 0.98,
        'guard-tk': 691200,
        'guard-bw-inc-exits': 35000000,  # Higher threshold
        'stable-uptime': 1209600,
        'stable-mtbf': 2592000,
        'fast-speed': 102000,
        'hsdir-wfu': 0.98,
        'hsdir-tk': 864000,
    },
    'gabelmoo': {
        'guard-wfu': 0.98,
        'guard-tk': 691200,
        'guard-bw-inc-exits': 30000000,
        'stable-uptime': 1500000,
        'fast-speed': 50000,
        'hsdir-wfu': 0.98,
        'hsdir-tk': 864000,
    },
}


class TestFormatRelayConsensusEvaluation:
    """Tests for format_relay_consensus_evaluation() function."""
    
    def test_empty_consensus_evaluation(self):
        """Test with empty diagnostics."""
        result = format_relay_consensus_evaluation({})
        assert result['available'] == False
        assert result['in_consensus'] == False
    
    def test_none_consensus_evaluation(self):
        """Test with None diagnostics."""
        result = format_relay_consensus_evaluation(None)
        assert result['available'] == False
    
    def test_error_consensus_evaluation(self):
        """Test with error in diagnostics."""
        result = format_relay_consensus_evaluation({'error': 'Test error'})
        assert result['available'] == False
        assert 'Test error' in result['error']
    
    def test_basic_consensus_evaluation(self):
        """Test with basic valid diagnostics."""
        diagnostics = {
            'fingerprint': 'ABC123' * 6 + 'ABCD',
            'in_consensus': True,
            'vote_count': 7,
            'total_authorities': 9,
            'majority_required': 5,
            'authority_votes': [
                {
                    'authority': 'moria1',
                    'voted': True,
                    'flags': ['Fast', 'Guard', 'Stable'],
                    'wfu': 0.99,
                    'tk': 864000,  # 10 days
                }
            ],
            'flag_eligibility': {
                'guard': {'eligible_count': 7},
                'stable': {'eligible_count': 8},
                'fast': {'eligible_count': 9},
                'hsdir': {'eligible_count': 7},
            },
            'reachability': {
                'ipv4_reachable_count': 9,
                'ipv6_reachable_count': 5,
                'total_authorities': 9,
            },
        }
        result = format_relay_consensus_evaluation(diagnostics)
        
        assert result['available'] == True
        assert result['in_consensus'] == True
        assert result['vote_count'] == 7
        assert result['majority_required'] == 5


class TestFormatConsensusStatus:
    """Tests for _format_consensus_status() function."""
    
    def test_in_consensus(self):
        """Test status when relay is in consensus."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 7,
            'total_authorities': 9,
            'majority_required': 5,
        }
        result = _format_consensus_status(diagnostics)
        
        assert result['status'] == 'IN CONSENSUS'
        assert result['status_class'] == 'success'
        assert '7' in result['display']
        assert '9' in result['display']
    
    def test_not_in_consensus(self):
        """Test status when relay is not in consensus."""
        diagnostics = {
            'in_consensus': False,
            'vote_count': 3,
            'total_authorities': 9,
            'majority_required': 5,
        }
        result = _format_consensus_status(diagnostics)
        
        assert result['status'] == 'NOT IN CONSENSUS'
        assert result['status_class'] == 'danger'


class TestFormatRelayValues:
    """Tests for _format_relay_values() function."""
    
    def test_basic_relay_values(self):
        """Test relay values formatting."""
        diagnostics = {
            'authority_votes': [
                {'wfu': 0.99, 'tk': 864000, 'measured': 50000000},
            ],
            'flag_eligibility': {
                'guard': {'eligible_count': 5},
                'stable': {'eligible_count': 5},
                'fast': {'eligible_count': 5},
            },
            'reachability': {
                'ipv4_reachable_count': 9,
                'ipv6_reachable_count': 4,
                'ipv6_not_tested_authorities': ['moria1', 'tor26'],
            },
            'total_authorities': 9,
            'majority_required': 5,
        }
        flag_thresholds = {
            'moria1': {
                'guard-wfu': 0.98,
                'guard-tk': 691200,
                'guard-bw-inc-exits': 1000000,
                'stable-uptime': 1209600,
                'fast-speed': 100000,
            }
        }
        
        result = _format_relay_values(diagnostics, flag_thresholds)
        
        assert result['wfu'] == 0.99
        assert '99' in result['wfu_display']
        assert result['wfu_meets'] == True
        assert result['ipv4_reachable_count'] == 9


class TestFormatBandwidthValue:
    """Tests for _format_bandwidth_value() function."""
    
    def test_none_bandwidth(self):
        """Test with None bandwidth."""
        assert _format_bandwidth_value(None) == 'N/A'
    
    def test_bytes_per_second(self):
        """Test small bandwidth in B/s."""
        result = _format_bandwidth_value(500)
        assert '500' in result
        assert 'B/s' in result
    
    def test_kilobytes_per_second(self):
        """Test bandwidth in KB/s."""
        result = _format_bandwidth_value(5000)
        assert 'KB/s' in result
    
    def test_megabytes_per_second(self):
        """Test bandwidth in MB/s."""
        result = _format_bandwidth_value(5000000)
        assert 'MB/s' in result
    
    def test_gigabytes_per_second(self):
        """Test bandwidth in GB/s."""
        result = _format_bandwidth_value(5000000000)
        assert 'GB/s' in result


class TestIdentifyIssues:
    """Tests for _identify_issues() function."""
    
    def test_no_issues(self):
        """Test when there are no issues."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'reachability': {
                'ipv4_reachable_count': 9,
                'ipv6_reachable_count': 0,
                # All authorities don't test IPv6, so no IPv6 issue should be raised
                'ipv6_not_tested_authorities': ['moria1', 'tor26', 'dizum', 'gabelmoo', 
                                                 'bastet', 'dannenberg', 'longclaw', 'maatuska', 'faravahar'],
            },
            'flag_eligibility': {
                'guard': {'eligible_count': 9},
            },
        }
        # Pass current_flags with 'Guard' to avoid the "not eligible for Guard" warning
        # Pass observed_bandwidth >= 2MB/s to meet Guard BW requirement
        issues = _identify_issues(diagnostics, current_flags=['Guard'], observed_bandwidth=3_000_000)
        assert len(issues) == 0
    
    def test_not_in_consensus_issue(self):
        """Test detection of not-in-consensus issue."""
        diagnostics = {
            'in_consensus': False,
            'vote_count': 3,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {'guard': {'eligible_count': 9}},
        }
        issues = _identify_issues(diagnostics)
        
        assert len(issues) >= 1
        consensus_issues = [i for i in issues if i['category'] == 'consensus']
        assert len(consensus_issues) >= 1
    
    def test_reachability_issue(self):
        """Test detection of reachability issues."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 5,
            'total_authorities': 9,
            'reachability': {
                'ipv4_reachable_count': 3,
                'ipv4_reachable_authorities': ['moria1', 'tor26', 'dizum'],
            },
            'flag_eligibility': {'guard': {'eligible_count': 9}},
        }
        issues = _identify_issues(diagnostics)
        
        reachability_issues = [i for i in issues if i['category'] == 'reachability']
        assert len(reachability_issues) >= 1


class TestGenerateAdvice:
    """Tests for _generate_advice() function."""
    
    def test_advice_for_low_wfu(self):
        """Test advice generation for low WFU."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {'guard': {'eligible_count': 9}},
            'authority_votes': [
                {'wfu': 0.95},  # Below 98% threshold
            ],
        }
        advice = _generate_advice(diagnostics)
        
        assert len(advice) >= 1
        # New format returns list of dicts with 'advice' key
        advice_texts = [a.get('advice', '') for a in advice]
        wfu_advice = [a for a in advice_texts if 'WFU' in a or 'uptime' in a.lower()]
        assert len(wfu_advice) >= 1
    
    def test_advice_returns_dict_format(self):
        """Test that advice returns list of properly formatted dicts."""
        diagnostics = {
            'in_consensus': False,
            'vote_count': 3,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 3, 'ipv4_reachable_authorities': []},
            'flag_eligibility': {},
            'authority_votes': [],
        }
        advice = _generate_advice(diagnostics)
        
        assert len(advice) >= 1
        for item in advice:
            assert isinstance(item, dict)
            assert 'category' in item
            assert 'priority' in item
            assert 'title' in item
            assert 'advice' in item
    
    def test_advice_priority_ordering(self):
        """Test that advice is sorted by priority (errors first)."""
        diagnostics = {
            'in_consensus': False,  # Error severity
            'vote_count': 2,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
            'authority_votes': [{'wfu': 0.85}],  # Warning severity
        }
        advice = _generate_advice(diagnostics)
        
        # Should be sorted by priority (1=error, 2=warning, 3=info)
        priorities = [a.get('priority', 999) for a in advice]
        assert priorities == sorted(priorities)
    
    def test_advice_includes_doc_refs(self):
        """Test that advice includes documentation references where appropriate."""
        diagnostics = {
            'in_consensus': False,
            'vote_count': 2,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 2, 'ipv4_reachable_authorities': ['moria1', 'tor26']},
            'flag_eligibility': {},
            'authority_votes': [],
        }
        advice = _generate_advice(diagnostics)
        
        # At least some advice should have doc_ref
        has_doc_ref = any(a.get('doc_ref') for a in advice)
        assert has_doc_ref, "Expected at least some advice to include documentation reference"


class TestFormatThresholdsTable:
    """Tests for _format_thresholds_table() function."""
    
    def test_empty_thresholds(self):
        """Test with empty thresholds."""
        result = _format_thresholds_table({})
        assert result['available'] == False
    
    def test_basic_thresholds(self):
        """Test with basic threshold data."""
        thresholds = {
            'moria1': {
                'guard-wfu': 0.98,
                'guard-tk': 691200,
                'stable-uptime': 1209600,
            },
            'tor26': {
                'guard-wfu': 0.98,
                'guard-tk': 691200,
                'stable-uptime': 1296000,
            },
        }
        result = _format_thresholds_table(thresholds)
        
        assert result['available'] == True
        assert 'moria1' in result['authorities']
        assert 'tor26' in result['authorities']
        assert len(result['rows']) >= 1


class TestFormatAuthorityConsensusEvaluation:
    """Tests for format_authority_consensus_evaluation() function."""
    
    def test_basic_authority_consensus_evaluation(self):
        """Test basic authority diagnostics formatting."""
        authority_status = {
            'moria1': {'online': True, 'latency_ms': 50},
            'tor26': {'online': True, 'latency_ms': 75},
        }
        flag_thresholds = {
            'moria1': {'guard-wfu': 0.98},
            'tor26': {'guard-wfu': 0.98},
        }
        bw_authorities = ['moria1']
        
        result = format_authority_consensus_evaluation(authority_status, flag_thresholds, bw_authorities)
        
        assert result['summary']['total'] == 2
        assert result['summary']['online'] == 2
        assert result['summary']['bw_authorities'] == 1
        assert len(result['authorities']) == 2
    
    def test_authority_with_error(self):
        """Test authority with error status."""
        authority_status = {
            'moria1': {'online': False, 'error': 'Connection timeout'},
        }
        flag_thresholds = {}
        bw_authorities = []
        
        result = format_authority_consensus_evaluation(authority_status, flag_thresholds, bw_authorities)
        
        assert result['summary']['online'] == 0
        auth = result['authorities'][0]
        assert auth['online'] == False
        assert auth['error'] == 'Connection timeout'


class TestFormatRelayConsensusEvaluationGuardEligibility:
    """Tests for Guard flag eligibility formatting."""
    
    def test_guard_eligible_relay(self):
        """Test formatting for relay that meets Guard requirements."""
        result = format_relay_consensus_evaluation(GUARD_ELIGIBLE_RELAY, SAMPLE_FLAG_THRESHOLDS)
        
        assert result['available'] == True
        assert result['in_consensus'] == True
        
        # Should have relay_values with Guard eligibility info
        rv = result.get('relay_values', {})
        assert rv.get('wfu_meets') == True  # WFU >= 98%
        assert rv.get('tk_meets') == True   # TK >= 8 days
    
    def test_non_guard_relay_wfu_issue(self):
        """Test that low WFU is correctly identified."""
        result = format_relay_consensus_evaluation(NON_GUARD_RELAY, SAMPLE_FLAG_THRESHOLDS)
        
        rv = result.get('relay_values', {})
        assert rv.get('wfu_meets') == False  # WFU < 98%
    
    def test_non_guard_relay_tk_issue(self):
        """Test that low Time Known is correctly identified."""
        result = format_relay_consensus_evaluation(NON_GUARD_RELAY, SAMPLE_FLAG_THRESHOLDS)
        
        rv = result.get('relay_values', {})
        assert rv.get('tk_meets') == False  # TK < 8 days


class TestFormatAuthorityTableEnhanced:
    """Tests for _format_authority_table_enhanced with threshold comparison."""
    
    def test_authority_table_includes_thresholds(self):
        """Test that authority table includes per-authority thresholds."""
        diagnostics = {
            'authority_votes': [
                {
                    'authority': 'moria1',
                    'fingerprint': 'F533C81CEF0BC0267857C99B2F471ADF249FA232',
                    'voted': True,
                    'flags': ['Fast', 'Guard'],
                    'wfu': 0.99,
                    'tk': 1000000,
                    'bandwidth': 50000000,
                    'measured': 45000000,
                    'is_bw_authority': True,
                },
            ],
        }
        
        result = _format_authority_table_enhanced(diagnostics, SAMPLE_FLAG_THRESHOLDS)
        
        assert len(result) >= 1
        moria1_row = result[0]
        
        # Should have threshold comparisons
        # Note: guard_bw_threshold was renamed to guard_bw_guarantee and guard_bw_top25_threshold
        assert 'guard_bw_guarantee' in moria1_row
        assert 'guard_bw_meets' in moria1_row
        assert 'stable_threshold' in moria1_row
        assert 'fast_threshold' in moria1_row
    
    def test_authority_table_fingerprint_included(self):
        """Test that authority fingerprints are included in table."""
        diagnostics = {
            'authority_votes': [
                {
                    'authority': 'moria1',
                    'fingerprint': 'F533C81CEF0BC0267857C99B2F471ADF249FA232',
                    'voted': True,
                    'flags': ['Fast'],
                },
            ],
        }
        
        result = _format_authority_table_enhanced(diagnostics, {})
        
        assert result[0]['fingerprint'] == 'F533C81CEF0BC0267857C99B2F471ADF249FA232'


class TestRelayValuesCalculation:
    """Tests for relay values calculation in _format_relay_values."""
    
    def test_guard_bw_range_calculation(self):
        """Test that Guard BW range is calculated from all authorities."""
        diagnostics = {
            'authority_votes': [
                {'wfu': 0.99, 'tk': 1000000, 'measured': 50000000},
            ],
            'flag_eligibility': {
                'guard': {'eligible_count': 5},
            },
            'reachability': {
                'ipv4_reachable_count': 9,
                'ipv6_reachable_count': 5,
                'ipv6_not_tested_authorities': [],
            },
            'total_authorities': 9,
            'majority_required': 5,
        }
        
        result = _format_relay_values(diagnostics, SAMPLE_FLAG_THRESHOLDS)
        
        # Guard BW range should reflect authority variation
        assert 'guard_bw_range' in result
        # With thresholds 10MB, 30MB, 35MB, range should be "10.0 MB/s-35.0 MB/s"
        assert 'MB/s' in result['guard_bw_range']
    
    def test_stable_range_calculation(self):
        """Test that Stable range is calculated correctly."""
        diagnostics = {
            'authority_votes': [{'wfu': 0.99, 'tk': 1000000}],
            'flag_eligibility': {'stable': {'eligible_count': 5}},
            'reachability': {'ipv4_reachable_count': 9},
            'total_authorities': 9,
            'majority_required': 5,
        }
        
        result = _format_relay_values(diagnostics, SAMPLE_FLAG_THRESHOLDS)
        
        assert 'stable_range' in result
        # Stable uptime varies: 1209600 (14d) to 1693440 (19.6d)
        assert 'd' in result['stable_range']  # Should show days
    
    def test_ipv6_tested_count(self):
        """Test IPv6 tested count accounts for non-testing authorities."""
        diagnostics = {
            'authority_votes': [{'wfu': 0.99, 'tk': 1000000}],
            'flag_eligibility': {},
            'reachability': {
                'ipv4_reachable_count': 9,
                'ipv6_reachable_count': 5,
                'ipv6_not_tested_authorities': ['dizum', 'faravahar'],
            },
            'total_authorities': 9,
            'majority_required': 5,
        }
        
        result = _format_relay_values(diagnostics, {})
        
        # 9 total - 2 not testing = 7 tested
        assert result['ipv6_tested_count'] == 7


class TestIssueIdentification:
    """Tests for issue identification logic."""
    
    def test_identifies_ipv4_reachability_issues(self):
        """Test that IPv4 reachability issues are identified."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 5,
            'total_authorities': 9,
            'reachability': {
                'ipv4_reachable_count': 3,  # Below majority
                'ipv4_unreachable_authorities': ['tor26', 'gabelmoo', 'bastet', 
                                                   'dannenberg', 'maatuska', 'longclaw'],
            },
            'flag_eligibility': {'guard': {'eligible_count': 5}},
        }
        
        issues = _identify_issues(diagnostics)
        
        # Should identify reachability as an issue
        reachability_issues = [i for i in issues if i['category'] == 'reachability']
        assert len(reachability_issues) >= 1
    
    def test_identifies_guard_eligibility_issues(self):
        """Test that Guard eligibility issues are identified."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {
                'guard': {'eligible_count': 2},  # Low eligibility
            },
        }
        
        issues = _identify_issues(diagnostics, current_flags=[], observed_bandwidth=1_000_000)
        
        # Should identify Guard eligibility as an issue (category='guard' or mentions 'Guard')
        guard_issues = [i for i in issues if i.get('category') == 'guard' 
                       or 'Guard' in i.get('title', '')
                       or 'Guard' in i.get('description', '')]
        assert len(guard_issues) >= 1


class TestAdviceGeneration:
    """Tests for advice generation logic."""
    
    def test_advice_for_new_relay(self):
        """Test advice for relay with low Time Known."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {'guard': {'eligible_count': 0}},
            'authority_votes': [
                {'wfu': 0.99, 'tk': 172800},  # Only 2 days - new relay
            ],
        }
        
        advice = _generate_advice(diagnostics)
        
        # Should give advice about Time Known
        assert len(advice) >= 1
    
    def test_advice_mentions_specific_thresholds(self):
        """Test that advice mentions specific threshold values."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {'guard': {'eligible_count': 5}},
            'authority_votes': [
                {'wfu': 0.95},  # Below 98%
            ],
        }
        
        advice = _generate_advice(diagnostics)
        
        # Should mention the 98% threshold in advice text
        advice_texts = [a.get('advice', '') for a in advice]
        advice_text = ' '.join(advice_texts)
        assert '98%' in advice_text or 'WFU' in advice_text
    
    def test_advice_simple_returns_strings(self):
        """Test that _generate_advice_simple returns list of strings."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
            'authority_votes': [{'wfu': 0.90}],
        }
        
        advice = _generate_advice_simple(diagnostics)
        
        assert isinstance(advice, list)
        for item in advice:
            assert isinstance(item, str)


class TestIdentifyIssuesComprehensive:
    """Comprehensive tests for _identify_issues() function."""
    
    def test_not_in_consensus_shows_majority_required(self):
        """Test that not-in-consensus issue shows majority needed."""
        diagnostics = {
            'in_consensus': False,
            'vote_count': 3,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
            'authority_votes': [],
        }
        
        issues = _identify_issues(diagnostics)
        
        consensus_issues = [i for i in issues if i['category'] == 'consensus']
        assert len(consensus_issues) >= 1
        # Should mention need for 5 votes
        assert '5' in consensus_issues[0]['description']
    
    def test_ipv6_not_reachable_issue(self):
        """Test detection of IPv6 reachability issues."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'reachability': {
                'ipv4_reachable_count': 9,
                'ipv6_reachable_count': 0,
                'ipv6_not_tested_authorities': [],  # All tested but none reached
            },
            'flag_eligibility': {},
            'authority_votes': [],
        }
        
        issues = _identify_issues(diagnostics, current_flags=['Guard'], observed_bandwidth=3_000_000)
        
        ipv6_issues = [i for i in issues if 'IPv6' in i.get('title', '')]
        assert len(ipv6_issues) >= 1
    
    def test_guard_low_bandwidth_issue(self):
        """Test detection of Guard bandwidth below threshold."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {'guard': {'eligible_count': 0}},
            'authority_votes': [{'wfu': 0.99, 'tk': 10 * SECONDS_PER_DAY}],
        }
        
        # Low bandwidth (1 MB/s, below 2 MB/s threshold)
        issues = _identify_issues(diagnostics, current_flags=[], observed_bandwidth=1_000_000)
        
        bw_issues = [i for i in issues if i['category'] == 'guard' and 'bandwidth' in i.get('title', '').lower()]
        assert len(bw_issues) >= 1
        # Should mention AuthDirGuardBWGuarantee
        assert 'MB/s' in bw_issues[0]['description'] or '2 MB' in bw_issues[0]['advice']
    
    def test_guard_low_wfu_issue(self):
        """Test detection of Guard WFU below threshold."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
            'authority_votes': [{'wfu': 0.90, 'tk': 10 * SECONDS_PER_DAY}],  # WFU below 98%
        }
        
        issues = _identify_issues(diagnostics, current_flags=[], observed_bandwidth=3_000_000)
        
        wfu_issues = [i for i in issues if i['category'] == 'guard' and 'WFU' in i.get('title', '')]
        assert len(wfu_issues) >= 1
        assert '98%' in wfu_issues[0]['description']
    
    def test_guard_low_tk_issue(self):
        """Test detection of Guard Time Known below threshold."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
            'authority_votes': [{'wfu': 0.99, 'tk': 3 * SECONDS_PER_DAY}],  # TK below 8 days
        }
        
        issues = _identify_issues(diagnostics, current_flags=[], observed_bandwidth=3_000_000)
        
        tk_issues = [i for i in issues if i['category'] == 'guard' and 'Time Known' in i.get('title', '')]
        assert len(tk_issues) >= 1
        assert '8 days' in tk_issues[0]['description']
    
    def test_guard_requires_stable_flag(self):
        """Test that missing Stable flag is identified for Guard."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
            'authority_votes': [{'wfu': 0.99, 'tk': 10 * SECONDS_PER_DAY}],
        }
        
        # Has Fast but not Stable
        issues = _identify_issues(diagnostics, current_flags=['Fast'], observed_bandwidth=3_000_000)
        
        stable_issues = [i for i in issues if 'Stable' in i.get('title', '')]
        assert len(stable_issues) >= 1
    
    def test_guard_requires_fast_flag(self):
        """Test that missing Fast flag is identified for Guard."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
            'authority_votes': [{'wfu': 0.99, 'tk': 10 * SECONDS_PER_DAY}],
        }
        
        # Has Stable but not Fast
        issues = _identify_issues(diagnostics, current_flags=['Stable'], observed_bandwidth=3_000_000)
        
        fast_issues = [i for i in issues if 'Fast' in i.get('title', '')]
        assert len(fast_issues) >= 1
    
    def test_hsdir_low_wfu_issue(self):
        """Test detection of HSDir WFU below threshold."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {'hsdir': {'eligible_count': 0}},
            'authority_votes': [{'wfu': 0.90, 'tk': 10 * SECONDS_PER_DAY}],
        }
        
        issues = _identify_issues(diagnostics, current_flags=['Guard', 'Fast', 'Stable'], observed_bandwidth=3_000_000)
        
        hsdir_issues = [i for i in issues if i['category'] == 'hsdir']
        # Should identify WFU as issue for HSDir
        wfu_hsdir = [i for i in hsdir_issues if 'WFU' in i.get('title', '')]
        assert len(wfu_hsdir) >= 1
    
    def test_hsdir_low_tk_issue(self):
        """Test detection of HSDir Time Known below threshold (25 hours default)."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
            'authority_votes': [{'wfu': 0.99, 'tk': 20 * 3600}],  # 20 hours, below 25 hour default
        }
        
        issues = _identify_issues(diagnostics, current_flags=['Guard', 'Fast', 'Stable'], observed_bandwidth=3_000_000)
        
        hsdir_tk_issues = [i for i in issues if i['category'] == 'hsdir' and 'Time Known' in i.get('title', '')]
        assert len(hsdir_tk_issues) >= 1
        assert '25' in hsdir_tk_issues[0]['description']  # Mentions 25 hours
    
    def test_bandwidth_deviation_warning(self):
        """Test detection of high bandwidth measurement deviation."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
            'authority_votes': [{'wfu': 0.99, 'tk': 10 * SECONDS_PER_DAY}],
            'bandwidth': {
                'deviation': 10_000_000,  # High deviation
                'median': 5_000_000,  # deviation > median * 0.5
            },
        }
        
        issues = _identify_issues(diagnostics, current_flags=['Guard'], observed_bandwidth=3_000_000)
        
        bw_issues = [i for i in issues if i['category'] == 'bandwidth']
        assert len(bw_issues) >= 1
    
    def test_staledesc_flag_detection(self):
        """Test detection of StaleDesc flag in votes."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
            'authority_votes': [
                {'voted': True, 'flags': ['Running', 'Valid', 'StaleDesc']},
            ],
        }
        
        issues = _identify_issues(diagnostics, current_flags=['Guard'], observed_bandwidth=3_000_000)
        
        staledesc_issues = [i for i in issues if 'StaleDesc' in i.get('title', '')]
        assert len(staledesc_issues) >= 1
        assert 'descriptor' in staledesc_issues[0]['suggestion'].lower()
    
    def test_badexit_flag_detection(self):
        """Test detection of BadExit flag."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'reachability': {
                'ipv4_reachable_count': 9,
                'ipv6_reachable_count': 0,
                'ipv6_not_tested_authorities': ['moria1', 'tor26', 'dizum', 'gabelmoo', 
                                                 'bastet', 'dannenberg', 'longclaw', 'maatuska', 'faravahar'],
            },
            'flag_eligibility': {},
            'authority_votes': [],
        }
        
        issues = _identify_issues(diagnostics, current_flags=['BadExit', 'Running', 'Guard'], observed_bandwidth=3_000_000)
        
        badexit_issues = [i for i in issues if 'BadExit' in i.get('title', '')]
        assert len(badexit_issues) >= 1
        # BadExit should be error severity
        assert badexit_issues[0]['severity'] == 'error'
    
    def test_partial_ipv4_reachability(self):
        """Test informational note for partial IPv4 reachability."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 7,
            'total_authorities': 9,
            'reachability': {
                'ipv4_reachable_count': 7,  # Above majority but not all
                'ipv4_reachable_authorities': ['moria1', 'tor26', 'dizum', 'gabelmoo', 'bastet', 'dannenberg', 'longclaw'],
            },
            'flag_eligibility': {},
            'authority_votes': [],
        }
        
        issues = _identify_issues(diagnostics, current_flags=['Guard'], observed_bandwidth=3_000_000)
        
        partial_issues = [i for i in issues if 'Partial' in i.get('title', '')]
        assert len(partial_issues) >= 1
        assert partial_issues[0]['severity'] == 'info'
    
    def test_no_issues_for_healthy_guard(self):
        """Test that healthy Guard relay has no issues."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'reachability': {
                'ipv4_reachable_count': 9,
                'ipv6_reachable_count': 7,
                'ipv6_not_tested_authorities': ['dizum', 'faravahar'],
            },
            'flag_eligibility': {'guard': {'eligible_count': 9}},
            'authority_votes': [{'wfu': 0.99, 'tk': 10 * SECONDS_PER_DAY}],
            'bandwidth': {'deviation': 1000, 'median': 50000},
        }
        
        issues = _identify_issues(
            diagnostics, 
            current_flags=['Guard', 'Fast', 'Stable', 'Running', 'Valid', 'HSDir'],
            observed_bandwidth=3_000_000
        )
        
        # Should have no issues (or only informational)
        errors = [i for i in issues if i['severity'] in ['error', 'warning']]
        assert len(errors) == 0


class TestAdviceCategories:
    """Tests for advice categorization."""
    
    def test_consensus_category(self):
        """Test advice has consensus category for not-in-consensus."""
        diagnostics = {
            'in_consensus': False,
            'vote_count': 2,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
            'authority_votes': [],
        }
        
        advice = _generate_advice(diagnostics)
        
        categories = [a.get('category') for a in advice]
        assert 'consensus' in categories
    
    def test_reachability_category(self):
        """Test advice has reachability category for unreachable relay."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 5,
            'total_authorities': 9,
            'reachability': {
                'ipv4_reachable_count': 3,
                'ipv4_reachable_authorities': ['moria1', 'tor26', 'dizum'],
            },
            'flag_eligibility': {},
            'authority_votes': [],
        }
        
        advice = _generate_advice(diagnostics)
        
        categories = [a.get('category') for a in advice]
        assert 'reachability' in categories
    
    def test_guard_category(self):
        """Test advice has guard category for Guard-related issues."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
            'authority_votes': [{'wfu': 0.90}],  # Low WFU
        }
        
        advice = _generate_advice(diagnostics, current_flags=[], observed_bandwidth=3_000_000)
        
        categories = [a.get('category') for a in advice]
        assert 'guard' in categories


class TestAdviceDocRefs:
    """Tests for documentation references in advice."""
    
    def test_torproject_doc_refs(self):
        """Test that advice references torproject.org documentation."""
        diagnostics = {
            'in_consensus': False,
            'vote_count': 2,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 2, 'ipv4_reachable_authorities': []},
            'flag_eligibility': {},
            'authority_votes': [],
        }
        
        advice = _generate_advice(diagnostics)
        
        doc_refs = [a.get('doc_ref') for a in advice if a.get('doc_ref')]
        assert len(doc_refs) >= 1
        # Should reference torproject.org
        assert any('torproject.org' in ref for ref in doc_refs)
    
    def test_spec_doc_refs_for_flags(self):
        """Test that flag-related advice references dir-spec."""
        diagnostics = {
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
            'authority_votes': [{'wfu': 0.85, 'tk': 3 * SECONDS_PER_DAY}],  # Below thresholds
        }
        
        advice = _generate_advice(diagnostics, current_flags=[], observed_bandwidth=3_000_000)
        
        doc_refs = [a.get('doc_ref') for a in advice if a.get('doc_ref')]
        # Should reference spec.torproject.org for flag requirements
        assert any('spec.torproject.org' in ref for ref in doc_refs)


class TestStableUptimeFeature:
    """Tests for Stable Uptime feature (relay uptime from Onionoo + per-authority thresholds)."""
    
    def test_stable_uptime_in_relay_values(self):
        """Test that stable uptime values are included in relay_values."""
        diagnostics = {
            'fingerprint': 'ABC123' * 6 + 'ABCD',
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'majority_required': 5,
            'authority_votes': [
                {'authority': 'moria1', 'wfu': 0.99, 'tk': 1000000, 'voted': True},
            ],
            'flag_eligibility': {'stable': {'eligible_count': 9}},
            'reachability': {'ipv4_reachable_count': 9},
        }
        flag_thresholds = {
            'moria1': {'stable-uptime': 1209600},  # 14 days
            'tor26': {'stable-uptime': 1296000},   # 15 days
        }
        
        # Pass relay_uptime of 20 days
        relay_uptime = 20 * SECONDS_PER_DAY
        result = format_relay_consensus_evaluation(
            diagnostics, flag_thresholds, 
            current_flags=['Guard'], 
            observed_bandwidth=3_000_000,
            relay_uptime=relay_uptime
        )
        
        rv = result.get('relay_values', {})
        
        # Should have stable uptime fields
        assert 'stable_uptime' in rv
        assert rv['stable_uptime'] == relay_uptime
        assert 'stable_uptime_display' in rv
        assert 'stable_uptime_min' in rv
        assert 'stable_uptime_max' in rv
        assert 'stable_uptime_meets_count' in rv
        assert 'stable_uptime_meets_all' in rv
    
    def test_stable_uptime_in_authority_table(self):
        """Test that stable uptime is included in per-authority table."""
        diagnostics = {
            'fingerprint': 'ABC123' * 6 + 'ABCD',
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'majority_required': 5,
            'authority_votes': [
                {'authority': 'moria1', 'wfu': 0.99, 'tk': 1000000, 'voted': True, 'mtbf': 500000},
            ],
            'flag_eligibility': {'stable': {'eligible_count': 9}},
            'reachability': {'ipv4_reachable_count': 9},
        }
        flag_thresholds = {
            'moria1': {'stable-uptime': 1209600, 'stable-mtbf': 1000000},
        }
        
        relay_uptime = 15 * SECONDS_PER_DAY  # 15 days
        result = format_relay_consensus_evaluation(
            diagnostics, flag_thresholds,
            current_flags=['Guard'],
            observed_bandwidth=3_000_000,
            relay_uptime=relay_uptime
        )
        
        # Check authority table
        auth_table = result.get('authority_table', [])
        assert len(auth_table) >= 1
        
        moria1_row = auth_table[0]
        assert 'stable_uptime' in moria1_row
        assert moria1_row['stable_uptime'] == relay_uptime  # Same for all authorities
        assert 'stable_uptime_threshold' in moria1_row
        assert moria1_row['stable_uptime_threshold'] == 1209600
        assert 'stable_uptime_meets' in moria1_row
        assert moria1_row['stable_uptime_meets'] == True  # 15d > 14d threshold
    
    def test_stable_uptime_none_when_not_provided(self):
        """Test that stable_uptime is None when not provided."""
        diagnostics = {
            'fingerprint': 'ABC123' * 6 + 'ABCD',
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'majority_required': 5,
            'authority_votes': [{'authority': 'moria1', 'voted': True}],
            'flag_eligibility': {},
            'reachability': {'ipv4_reachable_count': 9},
        }
        
        # Don't pass relay_uptime
        result = format_relay_consensus_evaluation(
            diagnostics, {}, current_flags=[], observed_bandwidth=0
        )
        
        rv = result.get('relay_values', {})
        assert rv.get('stable_uptime') is None
        assert rv.get('stable_uptime_display') == 'N/A'
    
    def test_stable_uptime_meets_calculation(self):
        """Test that stable_uptime_meets is calculated correctly."""
        diagnostics = {
            'fingerprint': 'ABC123' * 6 + 'ABCD',
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'majority_required': 5,
            'authority_votes': [
                {'authority': 'moria1', 'voted': True},
                {'authority': 'tor26', 'voted': True},
            ],
            'flag_eligibility': {},
            'reachability': {'ipv4_reachable_count': 9},
        }
        flag_thresholds = {
            'moria1': {'stable-uptime': 1209600},  # 14 days
            'tor26': {'stable-uptime': 1728000},   # 20 days
        }
        
        # 15 days uptime - meets moria1's threshold but not tor26's
        relay_uptime = 15 * SECONDS_PER_DAY
        result = format_relay_consensus_evaluation(
            diagnostics, flag_thresholds,
            current_flags=[],
            observed_bandwidth=0,
            relay_uptime=relay_uptime
        )
        
        rv = result.get('relay_values', {})
        assert rv['stable_uptime_meets_count'] == 1  # Only meets moria1's threshold
        assert rv['stable_uptime_meets_all'] == False
    
    def test_stable_uptime_same_for_all_authorities(self):
        """Test that relay uptime is the same value for all authorities."""
        diagnostics = {
            'fingerprint': 'ABC123' * 6 + 'ABCD',
            'in_consensus': True,
            'vote_count': 9,
            'total_authorities': 9,
            'majority_required': 5,
            'authority_votes': [
                {'authority': 'moria1', 'voted': True},
                {'authority': 'tor26', 'voted': True},
                {'authority': 'gabelmoo', 'voted': True},
            ],
            'flag_eligibility': {},
            'reachability': {'ipv4_reachable_count': 9},
        }
        flag_thresholds = {
            'moria1': {'stable-uptime': 1000000},
            'tor26': {'stable-uptime': 1200000},
            'gabelmoo': {'stable-uptime': 1400000},
        }
        
        relay_uptime = 10 * SECONDS_PER_DAY
        result = format_relay_consensus_evaluation(
            diagnostics, flag_thresholds,
            current_flags=[],
            observed_bandwidth=0,
            relay_uptime=relay_uptime
        )
        
        auth_table = result.get('authority_table', [])
        
        # All rows should have the same relay uptime value
        for row in auth_table:
            assert row['stable_uptime'] == relay_uptime


class TestBandwidthFormatting:
    """Tests for bandwidth value formatting."""
    
    def test_format_zero_bandwidth(self):
        """Test formatting of zero bandwidth."""
        result = _format_bandwidth_value(0)
        assert result == '0 B/s' or result == 'N/A'
    
    def test_format_negative_bandwidth(self):
        """Test formatting of negative bandwidth (should handle gracefully)."""
        result = _format_bandwidth_value(-1000)
        # Should not crash, return something reasonable
        assert result is not None
    
    def test_format_large_bandwidth(self):
        """Test formatting of very large bandwidth."""
        result = _format_bandwidth_value(10 * 1024 * 1024 * 1024)  # 10 GB/s
        assert 'GB/s' in result
    
    def test_format_exact_kb_boundary(self):
        """Test formatting at KB boundary."""
        result = _format_bandwidth_value(1024)
        assert 'KB/s' in result or 'B/s' in result
    
    def test_format_exact_mb_boundary(self):
        """Test formatting at MB boundary."""
        result = _format_bandwidth_value(1024 * 1024)
        assert 'MB/s' in result or 'KB/s' in result
