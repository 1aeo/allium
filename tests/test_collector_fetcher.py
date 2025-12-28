"""
Unit tests for lib/consensus/collector_fetcher.py

Tests the CollectorFetcher class which fetches and parses
CollecTor data for per-relay consensus diagnostics.
"""

import pytest
import sys
import os

# Add allium to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'allium'))

from lib.consensus.collector_fetcher import (
    CollectorFetcher,
    discover_authorities,
    calculate_consensus_requirement,
    AUTHORITIES,
)


class TestCollectorFetcher:
    """Tests for CollectorFetcher class."""
    
    def test_init_default_values(self):
        """Test CollectorFetcher initializes with correct default values."""
        fetcher = CollectorFetcher()
        
        assert fetcher.timeout == 30
        assert fetcher.authorities == []
        assert fetcher.votes == {}
        assert fetcher.bandwidth_files == {}
        assert fetcher.relay_index == {}
        assert fetcher.flag_thresholds == {}
    
    def test_init_with_custom_timeout(self):
        """Test CollectorFetcher accepts custom timeout."""
        fetcher = CollectorFetcher(timeout=60)
        assert fetcher.timeout == 60
    
    def test_init_with_authorities(self):
        """Test CollectorFetcher accepts discovered authorities."""
        authorities = [
            {'fingerprint': 'ABC123', 'nickname': 'TestAuth'}
        ]
        fetcher = CollectorFetcher(authorities=authorities)
        assert fetcher.authorities == authorities
    
    def test_validate_fingerprint_valid(self):
        """Test _validate_fingerprint with valid fingerprints."""
        fetcher = CollectorFetcher()
        
        # Valid 40-char hex fingerprint
        assert fetcher._validate_fingerprint('0232AF901C31A04EE9848595AF9BB7620D4C5B2E') is True
        assert fetcher._validate_fingerprint('abcdef0123456789abcdef0123456789abcdef01') is True
    
    def test_validate_fingerprint_invalid(self):
        """Test _validate_fingerprint with invalid fingerprints."""
        fetcher = CollectorFetcher()
        
        # Empty
        assert fetcher._validate_fingerprint('') is False
        assert fetcher._validate_fingerprint(None) is False
        
        # Wrong length
        assert fetcher._validate_fingerprint('ABC123') is False
        assert fetcher._validate_fingerprint('0232AF901C31A04EE9848595AF9BB7620D4C5B2E0') is False
        
        # Non-hex characters
        assert fetcher._validate_fingerprint('ZZZZZF901C31A04EE9848595AF9BB7620D4C5B2E') is False
    
    def test_format_time_known(self):
        """Test _format_time_known formatting."""
        fetcher = CollectorFetcher()
        
        # None
        assert fetcher._format_time_known(None) == 'N/A'
        
        # Days
        assert fetcher._format_time_known(86400) == '1.0 days'
        assert fetcher._format_time_known(691200) == '8.0 days'  # Guard requirement
        
        # Hours
        assert fetcher._format_time_known(3600) == '1.0 hours'
        assert fetcher._format_time_known(7200) == '2.0 hours'
        
        # Seconds
        assert fetcher._format_time_known(300) == '300 seconds'
    
    def test_parse_flag_thresholds(self):
        """Test _parse_flag_thresholds parsing."""
        fetcher = CollectorFetcher()
        
        # Sample flag-thresholds line
        line = 'flag-thresholds stable-uptime=1693440 stable-mtbf=2073600 fast-speed=24000 guard-wfu=0.980000 guard-tk=691200 guard-bw-inc-exits=5120000'
        
        thresholds = fetcher._parse_flag_thresholds(line)
        
        assert thresholds['stable-uptime'] == 1693440
        assert thresholds['stable-mtbf'] == 2073600
        assert thresholds['fast-speed'] == 24000
        assert thresholds['guard-wfu'] == 0.980000
        assert thresholds['guard-tk'] == 691200
        assert thresholds['guard-bw-inc-exits'] == 5120000
    
    def test_get_relay_diagnostics_not_found(self):
        """Test get_relay_diagnostics with relay not in index."""
        fetcher = CollectorFetcher()
        fetcher.relay_index = {}
        
        result = fetcher.get_relay_diagnostics('0232AF901C31A04EE9848595AF9BB7620D4C5B2E')
        
        assert result['error'] == 'Relay not found in votes'
        assert result['in_consensus'] is False
        assert result['vote_count'] == 0
    
    def test_get_relay_diagnostics_invalid_fingerprint(self):
        """Test get_relay_diagnostics with invalid fingerprint."""
        fetcher = CollectorFetcher()
        
        result = fetcher.get_relay_diagnostics('INVALID')
        
        assert result['error'] == 'Invalid fingerprint'
        assert result['in_consensus'] is False
    
    def test_get_relay_diagnostics_in_consensus(self):
        """Test get_relay_diagnostics for relay with majority votes."""
        fetcher = CollectorFetcher()
        
        # Setup relay with 5 authority votes (majority of 9)
        fingerprint = '0232AF901C31A04EE9848595AF9BB7620D4C5B2E'
        fetcher.relay_index = {
            fingerprint: {
                'fingerprint': fingerprint,
                'nickname': 'TestRelay',
                'votes': {
                    'moria1': {'flags': ['Guard', 'Stable']},
                    'tor26': {'flags': ['Guard', 'Stable']},
                    'dizum': {'flags': ['Guard']},
                    'gabelmoo': {'flags': ['Guard', 'Stable', 'Fast']},
                    'bastet': {'flags': ['Guard', 'Stable']},
                },
                'bandwidth_measurements': {},
            }
        }
        
        result = fetcher.get_relay_diagnostics(fingerprint)
        
        assert result['fingerprint'] == fingerprint
        assert result['in_consensus'] is True
        assert result['vote_count'] == 5
        assert result['total_authorities'] == 9
        assert result['majority_required'] == 5
    
    def test_get_relay_diagnostics_not_in_consensus(self):
        """Test get_relay_diagnostics for relay with minority votes."""
        fetcher = CollectorFetcher()
        
        # Setup relay with only 3 authority votes (not majority)
        fingerprint = '0232AF901C31A04EE9848595AF9BB7620D4C5B2E'
        fetcher.relay_index = {
            fingerprint: {
                'fingerprint': fingerprint,
                'nickname': 'TestRelay',
                'votes': {
                    'moria1': {'flags': ['Stable']},
                    'tor26': {'flags': ['Stable']},
                    'dizum': {'flags': []},
                },
                'bandwidth_measurements': {},
            }
        }
        
        result = fetcher.get_relay_diagnostics(fingerprint)
        
        assert result['in_consensus'] is False
        assert result['vote_count'] == 3
    
    def test_format_bandwidth(self):
        """Test _format_bandwidth aggregation."""
        fetcher = CollectorFetcher()
        
        relay = {
            'votes': {
                'moria1': {'bandwidth': 5000000, 'measured': 4500000},
                'gabelmoo': {'bandwidth': 5200000, 'measured': 4800000},
            },
            'bandwidth_measurements': {
                'sbws': 4700000,
            }
        }
        
        result = fetcher._format_bandwidth(relay)
        
        assert result['measurement_count'] == 3
        assert result['min'] == 4500000
        assert result['max'] == 4800000
        assert result['average'] is not None
    
    def test_format_bandwidth_empty(self):
        """Test _format_bandwidth with no measurements."""
        fetcher = CollectorFetcher()
        
        relay = {
            'votes': {},
            'bandwidth_measurements': {}
        }
        
        result = fetcher._format_bandwidth(relay)
        
        assert result['average'] is None
        assert result['min'] is None
        assert result['max'] is None


class TestDiscoverAuthorities:
    """Tests for discover_authorities function."""
    
    def test_discover_authorities_found(self):
        """Test discovering authorities from relay list."""
        relays = [
            {
                'fingerprint': 'ABC123DEF456789012345678901234567890ABCD',
                'nickname': 'moria1',
                'flags': ['Authority', 'Fast', 'Guard', 'Running', 'Stable', 'V2Dir', 'Valid'],
                'or_addresses': ['128.31.0.39:9101'],
                'dir_address': '128.31.0.39:9131',
            },
            {
                'fingerprint': 'DEF456789012345678901234567890ABCDEF1234',
                'nickname': 'TestRelay',
                'flags': ['Fast', 'Guard', 'Running', 'Stable', 'Valid'],
                'or_addresses': ['192.168.1.1:9001'],
            },
        ]
        
        authorities = discover_authorities(relays)
        
        assert len(authorities) == 1
        assert authorities[0]['nickname'] == 'moria1'
        assert authorities[0]['fingerprint'] == 'ABC123DEF456789012345678901234567890ABCD'
    
    def test_discover_authorities_empty(self):
        """Test discovering authorities with no authorities in list."""
        relays = [
            {
                'fingerprint': 'DEF456789012345678901234567890ABCDEF1234',
                'nickname': 'TestRelay',
                'flags': ['Fast', 'Guard', 'Running', 'Stable', 'Valid'],
            },
        ]
        
        authorities = discover_authorities(relays)
        
        assert len(authorities) == 0


class TestCalculateConsensusRequirement:
    """Tests for calculate_consensus_requirement function."""
    
    def test_nine_authorities(self):
        """Test consensus requirement with 9 authorities (current network)."""
        result = calculate_consensus_requirement(9)
        
        assert result['authority_count'] == 9
        assert result['majority_required'] == 5  # floor(9/2) + 1 = 5
        assert '5/9' in result['tooltip']
    
    def test_ten_authorities(self):
        """Test consensus requirement with 10 authorities."""
        result = calculate_consensus_requirement(10)
        
        assert result['authority_count'] == 10
        assert result['majority_required'] == 6  # floor(10/2) + 1 = 6
    
    def test_eight_authorities(self):
        """Test consensus requirement with 8 authorities."""
        result = calculate_consensus_requirement(8)
        
        assert result['authority_count'] == 8
        assert result['majority_required'] == 5  # floor(8/2) + 1 = 5
    
    def test_one_authority(self):
        """Test consensus requirement with 1 authority (edge case)."""
        result = calculate_consensus_requirement(1)
        
        assert result['authority_count'] == 1
        assert result['majority_required'] == 1  # floor(1/2) + 1 = 1


class TestAuthoritiesConstant:
    """Tests for AUTHORITIES constant."""
    
    def test_authorities_count(self):
        """Test that we have the expected number of authorities."""
        assert len(AUTHORITIES) == 9
    
    def test_authorities_fingerprint_format(self):
        """Test that authority fingerprints are valid format."""
        for fingerprint in AUTHORITIES.keys():
            assert len(fingerprint) == 40
            # Should be valid hex
            int(fingerprint, 16)
    
    def test_known_authorities_present(self):
        """Test that known authorities are present."""
        names = set(AUTHORITIES.values())
        expected = {'moria1', 'tor26', 'dizum', 'gabelmoo', 'bastet', 
                   'dannenberg', 'maatuska', 'longclaw', 'faravahar'}
        assert names == expected
