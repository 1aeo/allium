"""
Tests for relay_diagnostics module.

Tests all 22 issue types across 10 categories:
- consensus (1): Not in consensus
- reachability (3): IPv4 issues, IPv6 not reachable, Partial IPv4
- guard (5): BW below, WFU below, TK below, requires Stable, requires Fast
- stable (1): Not eligible
- hsdir (2): WFU below, TK below
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

# Constants for testing
SECONDS_PER_DAY = 86400
GUARD_BW_GUARANTEE = 2_000_000  # 2 MB/s
GUARD_WFU_DEFAULT = 0.98
GUARD_TK_DEFAULT = 691200  # 8 days
HSDIR_TK_DEFAULT = 90000  # 25 hours


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
        """Test Guard WFU below threshold (warning severity)."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.90, 'tk': 10 * SECONDS_PER_DAY}],  # WFU below 98%
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
        }
        
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Stable', 'Fast'],
            observed_bandwidth=3_000_000
        )
        
        wfu_issues = [i for i in issues if 'Guard' in i['title'] and 'WFU' in i['title']]
        assert len(wfu_issues) >= 1
        assert wfu_issues[0]['severity'] == 'warning'
    
    def test_guard_tk_below_is_warning(self):
        """Test Guard Time Known below threshold is WARNING (changed from info)."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.99, 'tk': 3 * SECONDS_PER_DAY}],  # TK below 8 days
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
        }
        
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Stable', 'Fast'],
            observed_bandwidth=3_000_000
        )
        
        tk_issues = [i for i in issues if 'Guard' in i['title'] and 'Time Known' in i['title']]
        assert len(tk_issues) >= 1
        assert tk_issues[0]['severity'] == 'warning'  # Changed from 'info'
    
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
                'stable': {'eligible_count': 2}  # Below majority
            },
        }
        
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Fast'],  # No Stable flag
            observed_bandwidth=3_000_000
        )
        
        stable_issues = [i for i in issues if i['category'] == 'stable']
        assert len(stable_issues) >= 1
        assert stable_issues[0]['severity'] == 'warning'  # Changed from 'info'
    
    def test_hsdir_wfu_below_is_warning(self):
        """Test HSDir WFU below threshold is WARNING (changed from info)."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.90, 'tk': 10 * SECONDS_PER_DAY}],  # WFU below 98%
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
        }
        
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Guard', 'Stable', 'Fast'],  # No HSDir
            observed_bandwidth=3_000_000
        )
        
        hsdir_issues = [i for i in issues if 'HSDir' in i['title'] and 'WFU' in i['title']]
        assert len(hsdir_issues) >= 1
        assert hsdir_issues[0]['severity'] == 'warning'  # Changed from 'info'
    
    def test_hsdir_tk_below_is_warning(self):
        """Test HSDir Time Known below threshold is WARNING (changed from info)."""
        consensus_data = {
            'in_consensus': True,
            'authority_votes': [{'wfu': 0.99, 'tk': 10 * 3600}],  # TK below 25 hours (HSDIR_TK_DEFAULT)
            'reachability': {'ipv4_reachable_count': 9},
            'flag_eligibility': {},
        }
        
        issues = generate_issues_from_consensus(
            consensus_data,
            current_flags=['Guard', 'Stable', 'Fast'],  # No HSDir
            observed_bandwidth=3_000_000
        )
        
        hsdir_tk_issues = [i for i in issues if 'HSDir' in i['title'] and 'Time Known' in i['title']]
        assert len(hsdir_tk_issues) >= 1
        assert hsdir_tk_issues[0]['severity'] == 'warning'  # Changed from 'info'
    
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
            'flags': ['Guard', 'Stable', 'Fast', 'Valid', 'Running', 'HSDir'],
            'observed_bandwidth': 10_000_000,  # 10 MB/s
            'version': '0.4.8.12',
            'recommended_version': True,
        }
        
        issues = generate_relay_issues(relay, consensus_data)
        
        # Filter out info-level notes
        real_issues = [i for i in issues if i['severity'] != 'info']
        assert len(real_issues) == 0


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

