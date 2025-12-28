"""
Tests for lib/consensus/diagnostics.py formatting functions.
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
