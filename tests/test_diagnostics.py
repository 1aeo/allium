"""
Tests for lib/consensus/diagnostics.py formatting functions.

These tests verify the formatting logic for relay diagnostics displayed
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

from lib.consensus.diagnostics import (
    format_relay_diagnostics,
    format_authority_diagnostics,
    _format_consensus_status,
    _format_relay_values,
    _format_authority_table_enhanced,
    _format_flag_summary,
    _format_reachability_summary,
    _format_bandwidth_summary,
    _identify_issues,
    _generate_advice,
    _format_thresholds_table,
    _format_bandwidth_value,
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


class TestFormatRelayDiagnostics:
    """Tests for format_relay_diagnostics() function."""
    
    def test_empty_diagnostics(self):
        """Test with empty diagnostics."""
        result = format_relay_diagnostics({})
        assert result['available'] == False
        assert result['in_consensus'] == False
    
    def test_none_diagnostics(self):
        """Test with None diagnostics."""
        result = format_relay_diagnostics(None)
        assert result['available'] == False
    
    def test_error_diagnostics(self):
        """Test with error in diagnostics."""
        result = format_relay_diagnostics({'error': 'Test error'})
        assert result['available'] == False
        assert 'Test error' in result['error']
    
    def test_basic_diagnostics(self):
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
        result = format_relay_diagnostics(diagnostics)
        
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
            },
            'flag_eligibility': {
                'guard': {'eligible_count': 9},
            },
        }
        issues = _identify_issues(diagnostics)
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
        wfu_advice = [a for a in advice if 'WFU' in a or 'uptime' in a.lower()]
        assert len(wfu_advice) >= 1


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


class TestFormatAuthorityDiagnostics:
    """Tests for format_authority_diagnostics() function."""
    
    def test_basic_authority_diagnostics(self):
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
        
        result = format_authority_diagnostics(authority_status, flag_thresholds, bw_authorities)
        
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
        
        result = format_authority_diagnostics(authority_status, flag_thresholds, bw_authorities)
        
        assert result['summary']['online'] == 0
        auth = result['authorities'][0]
        assert auth['online'] == False
        assert auth['error'] == 'Connection timeout'


class TestFormatRelayDiagnosticsGuardEligibility:
    """Tests for Guard flag eligibility formatting."""
    
    def test_guard_eligible_relay(self):
        """Test formatting for relay that meets Guard requirements."""
        result = format_relay_diagnostics(GUARD_ELIGIBLE_RELAY, SAMPLE_FLAG_THRESHOLDS)
        
        assert result['available'] == True
        assert result['in_consensus'] == True
        
        # Should have relay_values with Guard eligibility info
        rv = result.get('relay_values', {})
        assert rv.get('wfu_meets') == True  # WFU >= 98%
        assert rv.get('tk_meets') == True   # TK >= 8 days
    
    def test_non_guard_relay_wfu_issue(self):
        """Test that low WFU is correctly identified."""
        result = format_relay_diagnostics(NON_GUARD_RELAY, SAMPLE_FLAG_THRESHOLDS)
        
        rv = result.get('relay_values', {})
        assert rv.get('wfu_meets') == False  # WFU < 98%
    
    def test_non_guard_relay_tk_issue(self):
        """Test that low Time Known is correctly identified."""
        result = format_relay_diagnostics(NON_GUARD_RELAY, SAMPLE_FLAG_THRESHOLDS)
        
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
        assert 'guard_bw_threshold' in moria1_row
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
        
        issues = _identify_issues(diagnostics)
        
        # Should identify Guard eligibility as an issue
        guard_issues = [i for i in issues if 'guard' in i.get('type', '').lower() 
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
        
        # Should mention the 98% threshold
        advice_text = ' '.join(advice)
        assert '98%' in advice_text or 'WFU' in advice_text


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
