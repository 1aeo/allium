"""
Tests for collector_fetcher.py

Tests the CollectorFetcher class that fetches and indexes CollecTor data
for per-relay diagnostics.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'allium', 'lib'))

from consensus.collector_fetcher import (
    CollectorFetcher,
    discover_authorities,
    calculate_consensus_requirement,
    AUTHORITIES,
)


class TestCollectorFetcher:
    """Tests for CollectorFetcher class."""
    
    def test_init_default(self):
        """Test default initialization."""
        fetcher = CollectorFetcher()
        assert fetcher.timeout == 30
        assert fetcher.authorities == []
        assert fetcher.votes == {}
        assert fetcher.bandwidth_files == {}
        assert fetcher.relay_index == {}
        assert fetcher.flag_thresholds == {}
    
    def test_init_with_timeout(self):
        """Test initialization with custom timeout."""
        fetcher = CollectorFetcher(timeout=60)
        assert fetcher.timeout == 60
    
    def test_init_with_authorities(self):
        """Test initialization with authorities list."""
        authorities = [{'nickname': 'test', 'fingerprint': 'ABC123'}]
        fetcher = CollectorFetcher(authorities=authorities)
        assert fetcher.authorities == authorities
    
    def test_validate_fingerprint_valid(self):
        """Test validation of valid fingerprint."""
        fetcher = CollectorFetcher()
        # Valid 40-character hex fingerprint
        assert fetcher._validate_fingerprint('0232AF901C31A04EE9848595AF9BB7620D4C5B2E')
        assert fetcher._validate_fingerprint('ABCDEF0123456789ABCDEF0123456789ABCDEF01')
    
    def test_validate_fingerprint_invalid(self):
        """Test validation of invalid fingerprints."""
        fetcher = CollectorFetcher()
        # Too short
        assert not fetcher._validate_fingerprint('0232AF901C31A04EE9848595AF9BB762')
        # Too long
        assert not fetcher._validate_fingerprint('0232AF901C31A04EE9848595AF9BB7620D4C5B2E00')
        # Invalid characters
        assert not fetcher._validate_fingerprint('ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ')
        # Empty
        assert not fetcher._validate_fingerprint('')
        # None
        assert not fetcher._validate_fingerprint(None)
    
    def test_format_time_known(self):
        """Test time formatting for Time Known values."""
        fetcher = CollectorFetcher()
        
        # Days
        assert fetcher._format_time_known(86400) == '1.0 days'
        assert fetcher._format_time_known(691200) == '8.0 days'  # Guard requirement
        
        # Hours
        assert fetcher._format_time_known(3600) == '1.0 hours'
        assert fetcher._format_time_known(7200) == '2.0 hours'
        
        # Seconds
        assert fetcher._format_time_known(60) == '60 seconds'
        
        # None
        assert fetcher._format_time_known(None) == 'N/A'
    
    def test_get_relay_diagnostics_not_found(self):
        """Test diagnostics for relay not in index."""
        fetcher = CollectorFetcher()
        fetcher.relay_index = {}
        
        result = fetcher.get_relay_diagnostics('0232AF901C31A04EE9848595AF9BB7620D4C5B2E')
        
        assert result['error'] == 'Relay not found in votes'
        assert result['in_consensus'] == False
        assert result['vote_count'] == 0
    
    def test_get_relay_diagnostics_invalid_fingerprint(self):
        """Test diagnostics with invalid fingerprint."""
        fetcher = CollectorFetcher()
        
        result = fetcher.get_relay_diagnostics('invalid')
        
        assert result['error'] == 'Invalid fingerprint'
        assert result['in_consensus'] == False
    
    def test_get_relay_diagnostics_in_consensus(self):
        """Test diagnostics for relay in consensus."""
        fetcher = CollectorFetcher()
        fingerprint = '0232AF901C31A04EE9848595AF9BB7620D4C5B2E'
        
        # Set up relay in index with votes from 5+ authorities
        fetcher.relay_index = {
            fingerprint: {
                'fingerprint': fingerprint,
                'nickname': 'TestRelay',
                'votes': {
                    'moria1': {'flags': ['Fast', 'Guard'], 'bandwidth': 10000},
                    'tor26': {'flags': ['Fast'], 'bandwidth': 10000},
                    'dizum': {'flags': ['Fast'], 'bandwidth': 10000},
                    'gabelmoo': {'flags': ['Fast'], 'bandwidth': 10000},
                    'bastet': {'flags': ['Fast'], 'bandwidth': 10000},
                },
                'bandwidth_measurements': {},
            }
        }
        fetcher.flag_thresholds = {}
        
        result = fetcher.get_relay_diagnostics(fingerprint, authority_count=9)
        
        assert result['in_consensus'] == True
        assert result['vote_count'] == 5
        assert result['majority_required'] == 5
    
    def test_get_relay_diagnostics_not_in_consensus(self):
        """Test diagnostics for relay not in consensus (too few votes)."""
        fetcher = CollectorFetcher()
        fingerprint = '0232AF901C31A04EE9848595AF9BB7620D4C5B2E'
        
        # Set up relay with only 3 votes (need 5 for majority)
        fetcher.relay_index = {
            fingerprint: {
                'fingerprint': fingerprint,
                'nickname': 'TestRelay',
                'votes': {
                    'moria1': {'flags': ['Fast'], 'bandwidth': 10000},
                    'tor26': {'flags': ['Fast'], 'bandwidth': 10000},
                    'dizum': {'flags': ['Fast'], 'bandwidth': 10000},
                },
                'bandwidth_measurements': {},
            }
        }
        fetcher.flag_thresholds = {}
        
        result = fetcher.get_relay_diagnostics(fingerprint, authority_count=9)
        
        assert result['in_consensus'] == False
        assert result['vote_count'] == 3
    
    def test_parse_flag_thresholds(self):
        """Test parsing of flag-thresholds line."""
        fetcher = CollectorFetcher()
        
        line = 'flag-thresholds stable-uptime=1693440 stable-mtbf=1693440 fast-speed=22000 guard-wfu=98% guard-tk=691200 guard-bw-inc-exits=10000000 hsdir-wfu=98% hsdir-tk=864000'
        
        thresholds = fetcher._parse_flag_thresholds(line)
        
        assert thresholds['stable-uptime'] == 1693440.0
        assert thresholds['stable-mtbf'] == 1693440.0
        assert thresholds['fast-speed'] == 22000.0
        assert thresholds['guard-wfu'] == 0.98  # Percentage converted to decimal
        assert thresholds['guard-tk'] == 691200.0
        assert thresholds['hsdir-wfu'] == 0.98
    
    def test_parse_w_line(self):
        """Test parsing of bandwidth weight line."""
        fetcher = CollectorFetcher()
        
        line = 'w Bandwidth=12345 Measured=67890'
        
        result = fetcher._parse_w_line(line)
        
        assert result['bandwidth'] == 12345
        assert result['measured'] == 67890
    
    def test_format_bandwidth(self):
        """Test bandwidth formatting."""
        fetcher = CollectorFetcher()
        
        relay = {
            'votes': {
                'moria1': {'bandwidth': 10000, 'measured': 15000},
                'tor26': {'bandwidth': 12000, 'measured': None},
            },
            'bandwidth_measurements': {'bw': 14000},
        }
        
        result = fetcher._format_bandwidth(relay)
        
        assert result['measurement_count'] >= 1
        assert result['average'] is not None


class TestDiscoverAuthorities:
    """Tests for discover_authorities function."""
    
    def test_discover_from_relay_list(self):
        """Test discovering authorities from relay list."""
        relays = [
            {'nickname': 'moria1', 'fingerprint': 'ABC123', 'flags': ['Authority', 'Running']},
            {'nickname': 'tor26', 'fingerprint': 'DEF456', 'flags': ['Authority', 'Running']},
            {'nickname': 'RegularRelay', 'fingerprint': 'GHI789', 'flags': ['Running', 'Fast']},
        ]
        
        authorities = discover_authorities(relays)
        
        assert len(authorities) == 2
        assert authorities[0]['nickname'] == 'moria1'
        assert authorities[1]['nickname'] == 'tor26'
    
    def test_discover_empty_list(self):
        """Test discovering from empty list."""
        authorities = discover_authorities([])
        assert authorities == []
    
    def test_discover_no_authorities(self):
        """Test discovering when no authorities in list."""
        relays = [
            {'nickname': 'Relay1', 'fingerprint': 'ABC123', 'flags': ['Running', 'Fast']},
            {'nickname': 'Relay2', 'fingerprint': 'DEF456', 'flags': ['Running', 'Guard']},
        ]
        
        authorities = discover_authorities(relays)
        assert authorities == []


class TestCalculateConsensusRequirement:
    """Tests for calculate_consensus_requirement function."""
    
    def test_nine_authorities(self):
        """Test with 9 authorities (current Tor network)."""
        result = calculate_consensus_requirement(9)
        
        assert result['authority_count'] == 9
        assert result['majority_required'] == 5  # floor(9/2) + 1 = 5
        assert '5/9' in result['tooltip']
    
    def test_ten_authorities(self):
        """Test with 10 authorities."""
        result = calculate_consensus_requirement(10)
        
        assert result['authority_count'] == 10
        assert result['majority_required'] == 6  # floor(10/2) + 1 = 6
    
    def test_eight_authorities(self):
        """Test with 8 authorities."""
        result = calculate_consensus_requirement(8)
        
        assert result['authority_count'] == 8
        assert result['majority_required'] == 5  # floor(8/2) + 1 = 5
    
    def test_one_authority(self):
        """Test with 1 authority (edge case)."""
        result = calculate_consensus_requirement(1)
        
        assert result['authority_count'] == 1
        assert result['majority_required'] == 1  # floor(1/2) + 1 = 1


class TestAuthoritiesConstant:
    """Tests for AUTHORITIES constant."""
    
    def test_authority_count(self):
        """Test that we have the expected number of authorities."""
        assert len(AUTHORITIES) == 9
    
    def test_authority_names(self):
        """Test that known authorities are present."""
        names = list(AUTHORITIES.values())
        assert 'moria1' in names
        assert 'tor26' in names
        assert 'gabelmoo' in names
        assert 'faravahar' in names
    
    def test_fingerprint_format(self):
        """Test that all fingerprints are valid format."""
        for fingerprint in AUTHORITIES.keys():
            assert len(fingerprint) == 40
            # Should be valid hex
            int(fingerprint, 16)
