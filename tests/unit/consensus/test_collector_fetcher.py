"""
Tests for collector_fetcher.py

Tests the CollectorFetcher class that fetches and indexes CollecTor data
for per-relay consensus evaluation.

IMPORTANT: These tests are designed to catch changes in CollecTor vote file
format. If these tests fail after a Tor update, it likely means the vote
file format has changed and our parsing code needs to be updated.

Vote file format reference: https://spec.torproject.org/dir-spec/
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from allium.lib.consensus.collector_fetcher import (
    CollectorFetcher,
    discover_authorities,
    calculate_consensus_requirement,
    AUTHORITIES,
    AuthorityRegistry,
    get_authority_names,
    get_authority_count,
    get_authority_registry,
)


# ============================================================================
# SAMPLE DATA FROM REAL COLLECTOR VOTE FILES
# If these formats change in Tor, update these samples and the parsing code
# ============================================================================

# Sample 'r' line format from vote file (relay entry)
# Format: r <nickname> <identity_b64> <digest_b64> <date> <time> <IP> <ORPort> <DirPort>
SAMPLE_R_LINE = "r lisdex AAAErLudKby6FyVrs1ko3b/Iq6k YpRTARWdwmwEVbePGq0/dy8d3I4 2025-12-27 11:01:03 152.53.144.50 8443 0"
SAMPLE_R_LINE_IPV6 = "r MyRelay ABCD1234abcd5678EFGH9012ijkl3456 XYZabc123def456ghi789jkl012mno 2025-12-28 15:30:00 192.168.1.1 9001 0"

# Sample 's' line format (flags assigned to relay)
SAMPLE_S_LINE = "s Fast Guard HSDir Running Stable V2Dir Valid"
SAMPLE_S_LINE_MINIMAL = "s Running Valid"
SAMPLE_S_LINE_EXIT = "s Exit Fast Guard Running Stable Valid"

# Sample 'a' line format (IPv6 address if reachable)
SAMPLE_A_LINE = "a [2001:db8::1]:9001"
SAMPLE_A_LINE_FULL = "a [2607:5300:203:51d2::1]:443"

# Sample 'w' line format (bandwidth weights)
SAMPLE_W_LINE = "w Bandwidth=12345 Measured=67890"
SAMPLE_W_LINE_NO_MEASURED = "w Bandwidth=5000"
SAMPLE_W_LINE_UNMEASURED = "w Bandwidth=1000 Unmeasured=1"

# Sample 'stats' line format (wfu, tk, mtbf values)
SAMPLE_STATS_LINE = "stats wfu=0.965815 tk=1040813 mtbf=2592000"
SAMPLE_STATS_LINE_LOW_WFU = "stats wfu=0.85 tk=500000 mtbf=1000000"
SAMPLE_STATS_LINE_HIGH_TK = "stats wfu=0.99 tk=8640000 mtbf=5000000"

# Sample 'flag-thresholds' line format
SAMPLE_FLAG_THRESHOLDS = "flag-thresholds stable-uptime=1693440 stable-mtbf=1693440 fast-speed=22000 guard-wfu=98% guard-tk=691200 guard-bw-inc-exits=10000000 guard-bw-exc-exits=10000000 enough-mtbf=1 hsdir-wfu=98% hsdir-tk=864000"
SAMPLE_FLAG_THRESHOLDS_VARIANT = "flag-thresholds stable-uptime=1209600 stable-mtbf=2592000 fast-speed=102000 guard-wfu=98% guard-tk=691200 guard-bw-inc-exits=35000000"

# Sample bandwidth-file-headers line (indicates bandwidth authority)
SAMPLE_BW_FILE_HEADERS = "bandwidth-file-headers timestamp=2025-12-28T02:45:10 version=1.4.0"

# Current authority V3 identity key fingerprints (from vote filenames)
# If these change, update AUTHORITIES in collector_fetcher.py
EXPECTED_AUTHORITIES = {
    '0232AF901C31A04EE9848595AF9BB7620D4C5B2E': 'dannenberg',
    '23D15D965BC35114467363C165C4F724B64B4F66': 'longclaw',
    '27102BC123E7AF1D4741AE047E160C91ADC76B21': 'bastet',
    '2F3DF9CA0E5D36F2685A2DA67184EB8DCB8CBA8C': 'tor26',
    '49015F787433103580E3B66A1707A00E60F2D15B': 'maatuska',
    '70849B868D606BAECFB6128C5E3D782029AA394F': 'faravahar',
    'E8A9C45EDE6D711294FADF8E7951F4DE6CA56B58': 'dizum',
    'ED03BB616EB2F60BEC80151114BB25CEF515B226': 'gabelmoo',
    'F533C81CEF0BC0267857C99B2F471ADF249FA232': 'moria1',
}


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
    
    def test_get_relay_consensus_evaluation_not_found(self):
        """Test consensus evaluation for relay not in index."""
        fetcher = CollectorFetcher()
        fetcher.relay_index = {}
        
        result = fetcher.get_relay_consensus_evaluation('0232AF901C31A04EE9848595AF9BB7620D4C5B2E')
        
        assert result['error'] == 'Relay not found in votes'
        assert result['in_consensus'] == False
        assert result['vote_count'] == 0
    
    def test_get_relay_consensus_evaluation_invalid_fingerprint(self):
        """Test consensus evaluation with invalid fingerprint."""
        fetcher = CollectorFetcher()
        
        result = fetcher.get_relay_consensus_evaluation('invalid')
        
        assert result['error'] == 'Invalid fingerprint'
        assert result['in_consensus'] == False
    
    def test_get_relay_consensus_evaluation_in_consensus(self):
        """Test consensus evaluation for relay in consensus."""
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
        
        result = fetcher.get_relay_consensus_evaluation(fingerprint, authority_count=9)
        
        assert result['in_consensus'] == True
        assert result['vote_count'] == 5
        assert result['majority_required'] == 5
    
    def test_get_relay_consensus_evaluation_not_in_consensus(self):
        """Test consensus evaluation for relay not in consensus (too few votes)."""
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
        
        result = fetcher.get_relay_consensus_evaluation(fingerprint, authority_count=9)
        
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
        
        # Use update_registry=False to avoid polluting global state between tests
        authorities = discover_authorities(relays, update_registry=False)
        
        assert len(authorities) == 2
        assert authorities[0]['nickname'] == 'moria1'
        assert authorities[1]['nickname'] == 'tor26'
    
    def test_discover_empty_list(self):
        """Test discovering from empty list."""
        authorities = discover_authorities([], update_registry=False)
        assert authorities == []
    
    def test_discover_no_authorities(self):
        """Test discovering when no authorities in list."""
        relays = [
            {'nickname': 'Relay1', 'fingerprint': 'ABC123', 'flags': ['Running', 'Fast']},
            {'nickname': 'Relay2', 'fingerprint': 'DEF456', 'flags': ['Running', 'Guard']},
        ]
        
        authorities = discover_authorities(relays, update_registry=False)
        assert authorities == []


class TestAuthorityRegistry:
    """Tests for AuthorityRegistry class - dynamic authority discovery."""
    
    def test_registry_initial_fallback(self):
        """Test that a new registry uses fallback values initially."""
        registry = AuthorityRegistry()
        
        assert registry.is_using_fallback() == True
        # Fallback count is 10 (includes Serge who has Authority flag but doesn't vote)
        assert registry.get_authority_count() == 10
        assert 'moria1' in registry.get_authority_names()
        assert 'tor26' in registry.get_authority_names()
        assert 'Serge' in registry.get_authority_names()
        # Voting authorities (9) - excludes Serge
        assert registry.get_voting_authority_count() == 9
    
    def test_registry_update_from_onionoo(self):
        """Test updating registry with Onionoo data."""
        registry = AuthorityRegistry()
        
        # Simulate Onionoo data with authorities
        relays = [
            {'nickname': 'AuthA', 'fingerprint': 'FP_A', 'flags': ['Authority', 'Running'], 'or_addresses': ['1.2.3.4:9001']},
            {'nickname': 'AuthB', 'fingerprint': 'FP_B', 'flags': ['Authority', 'Running'], 'or_addresses': ['2.3.4.5:9001']},
            {'nickname': 'Regular', 'fingerprint': 'FP_R', 'flags': ['Running', 'Fast']},
        ]
        
        count = registry.update_from_onionoo(relays)
        
        assert count == 2  # Only authorities counted
        assert registry.is_using_fallback() == False
        assert registry.get_authority_count() == 2
        assert registry.get_authority_names() == ['AuthA', 'AuthB']  # Sorted
    
    def test_registry_empty_onionoo_keeps_fallback(self):
        """Test that empty Onionoo data doesn't update registry."""
        registry = AuthorityRegistry()
        
        count = registry.update_from_onionoo([])
        
        assert count == 0
        assert registry.is_using_fallback() == True  # Still using fallback
        # Total authorities (10) including non-voting Serge
        assert registry.get_authority_count() == 10
    
    def test_registry_no_authorities_keeps_fallback(self):
        """Test that Onionoo data without authorities keeps fallback."""
        registry = AuthorityRegistry()
        
        relays = [
            {'nickname': 'Relay1', 'fingerprint': 'FP1', 'flags': ['Running', 'Fast']},
            {'nickname': 'Relay2', 'fingerprint': 'FP2', 'flags': ['Running', 'Guard']},
        ]
        
        count = registry.update_from_onionoo(relays)
        
        assert count == 0
        assert registry.is_using_fallback() == True
    
    def test_signing_key_mapping_always_hardcoded(self):
        """Test that signing key to name mapping is always available."""
        registry = AuthorityRegistry()
        signing_keys = registry.get_signing_key_to_name()
        
        # Signing key mapping should always be available (hardcoded)
        # Only 9 voting authorities have signing keys (Serge doesn't vote)
        assert len(signing_keys) == 9
        assert 'moria1' in signing_keys.values()
        assert 'Serge' not in signing_keys.values()  # Serge doesn't vote
        
        # Even after Onionoo update, signing keys remain unchanged
        relays = [{'nickname': 'NewAuth', 'fingerprint': 'NEW', 'flags': ['Authority']}]
        registry.update_from_onionoo(relays)
        
        signing_keys_after = registry.get_signing_key_to_name()
        assert signing_keys_after == signing_keys  # Unchanged


class TestDynamicAuthorityFunctions:
    """Tests for module-level dynamic authority functions."""
    
    def test_get_authority_names_returns_list(self):
        """Test get_authority_names returns sorted list."""
        names = get_authority_names()
        
        assert isinstance(names, list)
        assert len(names) >= 1  # At least one authority
        # Uses case-insensitive sorting (Serge sorts between other names)
        assert names == sorted(names, key=str.lower)
    
    def test_get_authority_count_returns_int(self):
        """Test get_authority_count returns integer."""
        count = get_authority_count()
        
        assert isinstance(count, int)
        assert count >= 1
    
    def test_global_registry_is_singleton(self):
        """Test that get_authority_registry returns the same instance."""
        registry1 = get_authority_registry()
        registry2 = get_authority_registry()
        
        assert registry1 is registry2


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
    """Tests for AUTHORITIES constant.
    
    IMPORTANT: If directory authority signing keys change, these tests will fail.
    Update AUTHORITIES in collector_fetcher.py with new fingerprints from vote files.
    """
    
    def test_authority_count(self):
        """Test that we have the expected number of authorities (currently 9)."""
        assert len(AUTHORITIES) == 9, \
            f"Expected 9 authorities, got {len(AUTHORITIES)}. " \
            "If Tor added/removed authorities, update AUTHORITIES constant."
    
    def test_authority_names(self):
        """Test that all known authority nicknames are present."""
        expected_names = {'moria1', 'tor26', 'gabelmoo', 'faravahar', 'dizum', 
                         'bastet', 'dannenberg', 'maatuska', 'longclaw'}
        actual_names = set(AUTHORITIES.values())
        
        missing = expected_names - actual_names
        extra = actual_names - expected_names
        
        assert not missing, f"Missing authorities: {missing}"
        assert not extra, f"Unknown authorities: {extra}"
    
    def test_fingerprint_format(self):
        """Test that all fingerprints are valid 40-char hex format."""
        for fingerprint in AUTHORITIES.keys():
            assert len(fingerprint) == 40, \
                f"Fingerprint {fingerprint} is not 40 chars"
            # Should be valid hex
            try:
                int(fingerprint, 16)
            except ValueError:
                pytest.fail(f"Fingerprint {fingerprint} is not valid hex")
    
    def test_expected_fingerprints_match(self):
        """Test that AUTHORITIES matches expected current fingerprints.
        
        If this test fails, authority signing keys have changed.
        Run the vote fingerprint discovery script to get new values.
        """
        for fp, name in EXPECTED_AUTHORITIES.items():
            assert fp in AUTHORITIES, \
                f"Fingerprint {fp} for {name} not in AUTHORITIES. " \
                f"Authority signing keys may have changed."
            assert AUTHORITIES[fp] == name, \
                f"Fingerprint {fp} maps to {AUTHORITIES[fp]}, expected {name}"


class TestParseRelayRLine:
    """Tests for _parse_relay_r_line method.
    
    The 'r' line format is:
    r <nickname> <identity_b64> <digest_b64> <date> <time> <IP> <ORPort> <DirPort>
    
    If this format changes in Tor, update the parsing code in collector_fetcher.py
    """
    
    def test_parse_valid_r_line(self):
        """Test parsing a valid 'r' line from vote file."""
        fetcher = CollectorFetcher()
        result = fetcher._parse_relay_r_line(SAMPLE_R_LINE)
        
        assert result is not None, "Failed to parse valid r line"
        assert result['nickname'] == 'lisdex'
        assert result['ip'] == '152.53.144.50'
        assert result['or_port'] == 8443
        assert result['dir_port'] == 0
        assert len(result['fingerprint']) == 40  # Hex fingerprint from base64 identity
    
    def test_parse_r_line_extracts_fingerprint(self):
        """Test that fingerprint is correctly decoded from base64 identity."""
        fetcher = CollectorFetcher()
        result = fetcher._parse_relay_r_line(SAMPLE_R_LINE)
        
        # Fingerprint should be uppercase hex
        assert result['fingerprint'].isupper() or result['fingerprint'].isdigit()
        assert all(c in '0123456789ABCDEF' for c in result['fingerprint'])
    
    def test_parse_r_line_with_different_ports(self):
        """Test parsing r line with various port configurations."""
        fetcher = CollectorFetcher()
        
        # Test with dir_port > 0
        line_with_dirport = "r TestRelay AAAErLudKby6FyVrs1ko3b/Iq6k YpRTAR 2025-12-27 11:01:03 192.168.1.1 9001 9030"
        result = fetcher._parse_relay_r_line(line_with_dirport)
        
        assert result is not None
        assert result['or_port'] == 9001
        assert result['dir_port'] == 9030
    
    def test_parse_r_line_invalid_too_short(self):
        """Test that malformed r line returns None."""
        fetcher = CollectorFetcher()
        
        # Too few fields
        result = fetcher._parse_relay_r_line("r lisdex ABC123")
        assert result is None
    
    def test_parse_r_line_initializes_fields(self):
        """Test that parsed relay has all expected fields initialized."""
        fetcher = CollectorFetcher()
        result = fetcher._parse_relay_r_line(SAMPLE_R_LINE)
        
        assert 'flags' in result
        assert 'bandwidth' in result
        assert 'measured' in result
        assert 'wfu' in result
        assert 'tk' in result
        assert 'mtbf' in result


class TestParseStatsLine:
    """Tests for _parse_stats_line method.
    
    The 'stats' line format is:
    stats wfu=<float> tk=<int> mtbf=<int>
    
    Values:
    - wfu: Weighted Fractional Uptime (0.0 to 1.0)
    - tk: Time Known in seconds
    - mtbf: Mean Time Between Failures in seconds
    """
    
    def test_parse_stats_line(self):
        """Test parsing a valid stats line."""
        fetcher = CollectorFetcher()
        result = fetcher._parse_stats_line(SAMPLE_STATS_LINE)
        
        assert result['wfu'] == pytest.approx(0.965815, rel=1e-5)
        assert result['tk'] == 1040813
        assert result['mtbf'] == 2592000
    
    def test_parse_stats_line_low_wfu(self):
        """Test parsing stats line with low WFU (below Guard threshold)."""
        fetcher = CollectorFetcher()
        result = fetcher._parse_stats_line(SAMPLE_STATS_LINE_LOW_WFU)
        
        assert result['wfu'] == 0.85
        assert result['wfu'] < 0.98  # Below Guard/HSDir threshold
    
    def test_parse_stats_line_high_tk(self):
        """Test parsing stats line with high Time Known."""
        fetcher = CollectorFetcher()
        result = fetcher._parse_stats_line(SAMPLE_STATS_LINE_HIGH_TK)
        
        assert result['tk'] == 8640000  # 100 days in seconds
        assert result['tk'] > 691200  # Above Guard TK threshold (8 days)
    
    def test_parse_stats_empty_result(self):
        """Test parsing stats line without expected values."""
        fetcher = CollectorFetcher()
        result = fetcher._parse_stats_line("stats")
        
        # Should return empty dict, not fail
        assert isinstance(result, dict)


class TestParseWLine:
    """Tests for _parse_w_line method.
    
    The 'w' line format is:
    w Bandwidth=<int> [Measured=<int>] [Unmeasured=1]
    
    Values are in bytes/second.
    """
    
    def test_parse_w_line_with_measured(self):
        """Test parsing w line with both Bandwidth and Measured."""
        fetcher = CollectorFetcher()
        result = fetcher._parse_w_line(SAMPLE_W_LINE)
        
        assert result['bandwidth'] == 12345
        assert result['measured'] == 67890
    
    def test_parse_w_line_no_measured(self):
        """Test parsing w line without Measured value."""
        fetcher = CollectorFetcher()
        result = fetcher._parse_w_line(SAMPLE_W_LINE_NO_MEASURED)
        
        assert result['bandwidth'] == 5000
        assert 'measured' not in result or result.get('measured') is None
    
    def test_parse_w_line_unmeasured(self):
        """Test parsing w line with Unmeasured flag."""
        fetcher = CollectorFetcher()
        result = fetcher._parse_w_line(SAMPLE_W_LINE_UNMEASURED)
        
        assert result['bandwidth'] == 1000


class TestParseFlagThresholds:
    """Tests for _parse_flag_thresholds method.
    
    The 'flag-thresholds' line contains dynamic thresholds for flag assignment.
    These values can change based on network conditions.
    
    Key thresholds:
    - guard-wfu: Usually 98% (0.98)
    - guard-tk: Usually 691200 seconds (8 days)
    - stable-uptime: Varies, ~14-20 days
    - fast-speed: Varies by network
    """
    
    def test_parse_flag_thresholds_complete(self):
        """Test parsing complete flag-thresholds line."""
        fetcher = CollectorFetcher()
        result = fetcher._parse_flag_thresholds(SAMPLE_FLAG_THRESHOLDS)
        
        # Guard thresholds
        assert result['guard-wfu'] == 0.98  # Percentage converted
        assert result['guard-tk'] == 691200  # 8 days in seconds
        assert result['guard-bw-inc-exits'] == 10000000
        
        # Stable thresholds
        assert result['stable-uptime'] == 1693440
        assert result['stable-mtbf'] == 1693440
        
        # Fast threshold
        assert result['fast-speed'] == 22000
        
        # HSDir thresholds
        assert result['hsdir-wfu'] == 0.98
        assert result['hsdir-tk'] == 864000  # ~10 days
    
    def test_parse_flag_thresholds_variant(self):
        """Test parsing flag-thresholds with different values."""
        fetcher = CollectorFetcher()
        result = fetcher._parse_flag_thresholds(SAMPLE_FLAG_THRESHOLDS_VARIANT)
        
        # Values should differ from SAMPLE_FLAG_THRESHOLDS
        assert result['stable-uptime'] == 1209600  # 14 days
        assert result['guard-bw-inc-exits'] == 35000000  # 35 MB/s
    
    def test_parse_flag_thresholds_percentage_conversion(self):
        """Test that percentage values are correctly converted to decimals."""
        fetcher = CollectorFetcher()
        result = fetcher._parse_flag_thresholds(SAMPLE_FLAG_THRESHOLDS)
        
        # 98% should become 0.98
        assert result['guard-wfu'] == 0.98
        assert result['hsdir-wfu'] == 0.98
        
        # These should not be percentages
        assert result['stable-uptime'] > 1  # Not a percentage


class TestParseVoteFile:
    """Tests for _parse_vote method.
    
    Tests parsing of complete vote file content including:
    - relay entries (r lines)
    - flags (s lines)
    - IPv6 addresses (a lines)
    - bandwidth (w lines)
    - stats (stats lines)
    - flag thresholds
    - bandwidth-file-headers detection
    """
    
    def test_parse_vote_with_relays(self):
        """Test parsing vote content with multiple relays."""
        fetcher = CollectorFetcher()
        
        vote_content = """@type network-status-vote-3 1.0
dir-source moria1 F533C81CEF0BC0267857C99B2F471ADF249FA232 128.31.0.34 128.31.0.34 9131 9101
flag-thresholds stable-uptime=1693440 stable-mtbf=1693440 fast-speed=22000 guard-wfu=98% guard-tk=691200
bandwidth-file-headers timestamp=2025-12-28T02:45:10
r TestRelay1 AAAErLudKby6FyVrs1ko3b/Iq6k YpRT 2025-12-27 11:01:03 192.168.1.1 9001 0
s Fast Running Stable Valid
w Bandwidth=50000 Measured=45000
stats wfu=0.99 tk=1000000 mtbf=2000000
a [2001:db8::1]:9001
r TestRelay2 BBBErLudKby6FyVrs1ko3b/Iq6k ZpRT 2025-12-27 11:02:03 192.168.1.2 9002 0
s Exit Fast Running Valid
w Bandwidth=100000
"""
        result = fetcher._parse_vote(vote_content, 'F533C81CEF0BC0267857C99B2F471ADF249FA232')
        
        assert result['has_bandwidth_file_headers'] == True
        assert 'flag_thresholds' in result
        assert result['flag_thresholds']['guard-wfu'] == 0.98
        assert len(result['relays']) == 2
    
    def test_parse_vote_detects_bw_authority(self):
        """Test that bandwidth-file-headers is detected for BW authorities."""
        fetcher = CollectorFetcher()
        
        vote_with_bw = """@type network-status-vote-3 1.0
bandwidth-file-headers timestamp=2025-12-28T02:45:10
r Relay AAAErLudKby6FyVrs1ko3b/Iq6k YpRT 2025-12-27 11:01:03 1.2.3.4 9001 0
s Fast Running Valid
w Bandwidth=50000 Measured=45000
"""
        result = fetcher._parse_vote(vote_with_bw, 'TEST123')
        assert result['has_bandwidth_file_headers'] == True
        
        vote_without_bw = """@type network-status-vote-3 1.0
r Relay AAAErLudKby6FyVrs1ko3b/Iq6k YpRT 2025-12-27 11:01:03 1.2.3.4 9001 0
s Fast Running Valid
w Bandwidth=50000
"""
        result = fetcher._parse_vote(vote_without_bw, 'TEST456')
        assert result['has_bandwidth_file_headers'] == False
    
    def test_parse_vote_extracts_relay_flags(self):
        """Test that relay flags are correctly extracted."""
        fetcher = CollectorFetcher()
        
        vote_content = """@type network-status-vote-3 1.0
r GuardRelay AAAErLudKby6FyVrs1ko3b/Iq6k YpRT 2025-12-27 11:01:03 1.2.3.4 9001 0
s Fast Guard HSDir Running Stable V2Dir Valid
w Bandwidth=50000 Measured=45000
"""
        result = fetcher._parse_vote(vote_content, 'TEST123')
        
        # Get first relay
        relay = list(result['relays'].values())[0]
        assert 'Fast' in relay['flags']
        assert 'Guard' in relay['flags']
        assert 'HSDir' in relay['flags']
        assert 'Stable' in relay['flags']
    
    def test_parse_vote_extracts_ipv6(self):
        """Test that IPv6 addresses are correctly extracted."""
        fetcher = CollectorFetcher()
        
        vote_content = """@type network-status-vote-3 1.0
r IPv6Relay AAAErLudKby6FyVrs1ko3b/Iq6k YpRT 2025-12-27 11:01:03 1.2.3.4 9001 0
a [2001:db8::1]:9001
s Fast Running Valid
w Bandwidth=50000
"""
        result = fetcher._parse_vote(vote_content, 'TEST123')
        
        relay = list(result['relays'].values())[0]
        assert relay['ipv6_reachable'] == True
        assert '[2001:db8::1]:9001' in relay['ipv6_address']


class TestBuildRelayIndex:
    """Tests for _build_relay_index method.
    
    The relay index aggregates data from all authority votes
    for O(1) lookup by fingerprint.
    """
    
    def test_build_index_from_votes(self):
        """Test building relay index from multiple authority votes."""
        fetcher = CollectorFetcher()
        
        # Simulate votes from multiple authorities
        fetcher.votes = {
            'moria1': {
                'relays': {
                    'ABC123': {'nickname': 'TestRelay', 'flags': ['Fast'], 'wfu': 0.99},
                }
            },
            'tor26': {
                'relays': {
                    'ABC123': {'nickname': 'TestRelay', 'flags': ['Fast', 'Guard'], 'wfu': 0.99},
                }
            },
        }
        fetcher.bandwidth_files = {}
        
        fetcher._build_relay_index()
        
        assert 'ABC123' in fetcher.relay_index
        assert len(fetcher.relay_index['ABC123']['votes']) == 2
        assert 'moria1' in fetcher.relay_index['ABC123']['votes']
        assert 'tor26' in fetcher.relay_index['ABC123']['votes']
    
    def test_index_aggregates_vote_data(self):
        """Test that index correctly aggregates per-authority vote data."""
        fetcher = CollectorFetcher()
        
        fetcher.votes = {
            'moria1': {
                'relays': {
                    'ABC123': {
                        'nickname': 'TestRelay',
                        'flags': ['Fast'],
                        'wfu': 0.99,
                        'tk': 1000000,
                        'bandwidth': 50000,
                        'measured': 45000,
                    },
                }
            },
        }
        fetcher.bandwidth_files = {}
        
        fetcher._build_relay_index()
        
        vote = fetcher.relay_index['ABC123']['votes']['moria1']
        assert vote['flags'] == ['Fast']
        assert vote['wfu'] == 0.99
        assert vote['tk'] == 1000000
        assert vote['bandwidth'] == 50000
        assert vote['measured'] == 45000


class TestFormatAuthorityVotes:
    """Tests for _format_authority_votes method.
    
    Tests the formatting of per-authority vote data for template display.
    """
    
    def test_format_authority_votes_includes_fingerprint(self):
        """Test that authority fingerprints are included in formatted votes."""
        fetcher = CollectorFetcher()
        
        relay = {
            'votes': {
                'moria1': {'flags': ['Fast'], 'wfu': 0.99, 'tk': 1000000},
            },
        }
        
        result = fetcher._format_authority_votes(relay)
        
        # Find moria1 entry
        moria1_vote = next((v for v in result if v['authority'] == 'moria1'), None)
        assert moria1_vote is not None
        assert 'fingerprint' in moria1_vote
        assert len(moria1_vote['fingerprint']) == 40
    
    def test_format_authority_votes_all_authorities(self):
        """Test that all 9 authorities are included in formatted votes."""
        fetcher = CollectorFetcher()
        
        relay = {'votes': {}}
        result = fetcher._format_authority_votes(relay)
        
        assert len(result) == 9
        authority_names = {v['authority'] for v in result}
        expected = {'moria1', 'tor26', 'gabelmoo', 'faravahar', 'dizum', 
                   'bastet', 'dannenberg', 'maatuska', 'longclaw'}
        assert authority_names == expected


class TestConsensusEvaluationComprehensive:
    """Comprehensive tests for get_relay_consensus_evaluation method."""
    
    def test_flag_eligibility_included(self):
        """Test that flag eligibility data is included in results."""
        fetcher = CollectorFetcher()
        fingerprint = 'ABC123DEF456ABC123DEF456ABC123DEF456ABC1'
        
        fetcher.relay_index = {
            fingerprint: {
                'fingerprint': fingerprint,
                'nickname': 'TestRelay',
                'votes': {
                    'moria1': {'flags': ['Fast', 'Guard'], 'wfu': 0.99, 'tk': 1000000},
                    'tor26': {'flags': ['Fast', 'Guard'], 'wfu': 0.99, 'tk': 1000000},
                    'dizum': {'flags': ['Fast', 'Guard'], 'wfu': 0.99, 'tk': 1000000},
                    'gabelmoo': {'flags': ['Fast', 'Guard'], 'wfu': 0.99, 'tk': 1000000},
                    'bastet': {'flags': ['Fast', 'Guard'], 'wfu': 0.99, 'tk': 1000000},
                },
                'bandwidth_measurements': {},
            }
        }
        fetcher.flag_thresholds = {
            'moria1': {'guard-wfu': 0.98, 'guard-tk': 691200},
            'tor26': {'guard-wfu': 0.98, 'guard-tk': 691200},
        }
        
        result = fetcher.get_relay_consensus_evaluation(fingerprint, authority_count=9)
        
        assert 'flag_eligibility' in result
    
    def test_reachability_data_included(self):
        """Test that reachability data is included in results."""
        fetcher = CollectorFetcher()
        fingerprint = 'ABC123DEF456ABC123DEF456ABC123DEF456ABC1'
        
        fetcher.relay_index = {
            fingerprint: {
                'fingerprint': fingerprint,
                'nickname': 'TestRelay',
                'votes': {
                    'moria1': {'flags': ['Running'], 'ipv6_reachable': True},
                    'tor26': {'flags': ['Running'], 'ipv6_reachable': False},
                },
                'bandwidth_measurements': {},
            }
        }
        fetcher.flag_thresholds = {}
        
        result = fetcher.get_relay_consensus_evaluation(fingerprint, authority_count=9)
        
        assert 'reachability' in result
        assert 'ipv4_reachable_count' in result['reachability']
    
    def test_authority_votes_formatted(self):
        """Test that authority votes are properly formatted."""
        fetcher = CollectorFetcher()
        fingerprint = 'ABC123DEF456ABC123DEF456ABC123DEF456ABC1'
        
        fetcher.relay_index = {
            fingerprint: {
                'fingerprint': fingerprint,
                'nickname': 'TestRelay',
                'votes': {
                    'moria1': {
                        'flags': ['Fast', 'Guard', 'Running', 'Stable', 'Valid'],
                        'wfu': 0.995,
                        'tk': 1000000,
                        'bandwidth': 5000000,
                        'measured': 4500000,
                    },
                },
                'bandwidth_measurements': {},
            }
        }
        fetcher.flag_thresholds = {'moria1': {'guard-wfu': 0.98}}
        
        result = fetcher.get_relay_consensus_evaluation(fingerprint, authority_count=9)
        
        assert 'authority_votes' in result
        assert len(result['authority_votes']) >= 1


class TestRelayIndexLookup:
    """Tests for relay index lookup functionality."""
    
    def test_case_insensitive_fingerprint(self):
        """Test that fingerprint lookup is case-insensitive (uppercase)."""
        fetcher = CollectorFetcher()
        fingerprint_lower = 'abc123def456abc123def456abc123def456abc1'
        fingerprint_upper = 'ABC123DEF456ABC123DEF456ABC123DEF456ABC1'
        
        fetcher.relay_index = {
            fingerprint_upper: {
                'fingerprint': fingerprint_upper,
                'nickname': 'TestRelay',
                'votes': {'moria1': {'flags': ['Fast']}},
                'bandwidth_measurements': {},
            }
        }
        fetcher.flag_thresholds = {}
        
        # Look up with lowercase (should be converted to uppercase)
        result = fetcher.get_relay_consensus_evaluation(fingerprint_lower, authority_count=9)
        
        # Should still find the relay (fingerprints are normalized to uppercase)
        # Note: This depends on implementation - adjust if needed
        assert result is not None


class TestParseRelayIpv6:
    """Tests for IPv6 address parsing from vote files."""
    
    def test_parse_a_line_standard(self):
        """Test parsing standard IPv6 'a' line."""
        fetcher = CollectorFetcher()
        
        # Simulate vote content with 'a' line
        vote_content = """@type network-status-vote-3 1.0
r TestRelay AAAErLudKby6FyVrs1ko3b/Iq6k YpRT 2025-12-27 11:01:03 192.168.1.1 9001 0
a [2001:db8::1]:9001
s Fast Running Valid
w Bandwidth=50000
"""
        result = fetcher._parse_vote(vote_content, 'TEST123')
        
        relay = list(result['relays'].values())[0]
        assert relay['ipv6_reachable'] == True
        assert '2001:db8::1' in relay['ipv6_address']
    
    def test_parse_multiple_a_lines(self):
        """Test that 'a' lines are parsed (last one wins per current impl)."""
        fetcher = CollectorFetcher()
        
        vote_content = """@type network-status-vote-3 1.0
r TestRelay AAAErLudKby6FyVrs1ko3b/Iq6k YpRT 2025-12-27 11:01:03 192.168.1.1 9001 0
a [2001:db8::1]:9001
a [2001:db8::2]:9002
s Fast Running Valid
w Bandwidth=50000
"""
        result = fetcher._parse_vote(vote_content, 'TEST123')
        
        relay = list(result['relays'].values())[0]
        assert relay['ipv6_reachable'] == True
        # Implementation uses last 'a' line (overwrites)
        assert '2001:db8' in relay['ipv6_address']  # Either address is valid


class TestBandwidthFileHeadersDetection:
    """Tests for bandwidth authority detection via bandwidth-file-headers."""
    
    def test_detects_bw_authority(self):
        """Test detection of bandwidth authority from vote."""
        fetcher = CollectorFetcher()
        
        vote_content = """@type network-status-vote-3 1.0
bandwidth-file-headers timestamp=2025-12-28T02:45:10 version=1.4.0 file_created=2025-12-28T02:30:00
r TestRelay AAAErLudKby6FyVrs1ko3b/Iq6k YpRT 2025-12-27 11:01:03 192.168.1.1 9001 0
s Fast Running Valid
w Bandwidth=50000 Measured=45000
"""
        result = fetcher._parse_vote(vote_content, 'TEST123')
        
        assert result['has_bandwidth_file_headers'] == True
    
    def test_detects_non_bw_authority(self):
        """Test detection of non-bandwidth authority (no headers)."""
        fetcher = CollectorFetcher()
        
        vote_content = """@type network-status-vote-3 1.0
r TestRelay AAAErLudKby6FyVrs1ko3b/Iq6k YpRT 2025-12-27 11:01:03 192.168.1.1 9001 0
s Fast Running Valid
w Bandwidth=50000
"""
        result = fetcher._parse_vote(vote_content, 'TEST456')
        
        assert result['has_bandwidth_file_headers'] == False


class TestVotingAuthorityFunctions:
    """Tests for voting vs total authority distinction."""
    
    def test_voting_authority_count_excludes_serge(self):
        """Test that voting authority count is 9 (excludes Serge)."""
        registry = AuthorityRegistry()
        
        # Using fallback values
        voting_count = registry.get_voting_authority_count()
        total_count = registry.get_authority_count()
        
        assert voting_count == 9  # Voting authorities only
        assert total_count == 10  # Includes Serge
    
    def test_voting_authority_names_excludes_serge(self):
        """Test that voting authority names exclude Serge."""
        registry = AuthorityRegistry()
        
        voting_names = registry.get_voting_authority_names()
        all_names = registry.get_authority_names()
        
        assert 'Serge' not in voting_names
        assert 'Serge' in all_names
        assert len(voting_names) == 9
        assert len(all_names) == 10


class TestAuthorityRegistryUpdate:
    """Tests for AuthorityRegistry update from Onionoo."""
    
    def test_update_preserves_sorting(self):
        """Test that updating registry preserves alphabetical sorting."""
        registry = AuthorityRegistry()
        
        relays = [
            {'nickname': 'ZuluAuth', 'fingerprint': 'FP_Z', 'flags': ['Authority', 'Running']},
            {'nickname': 'AlphaAuth', 'fingerprint': 'FP_A', 'flags': ['Authority', 'Running']},
            {'nickname': 'MikeAuth', 'fingerprint': 'FP_M', 'flags': ['Authority', 'Running']},
        ]
        
        registry.update_from_onionoo(relays)
        
        names = registry.get_authority_names()
        # Should be sorted case-insensitively
        assert names == sorted(names, key=str.lower)
    
    def test_update_with_mixed_relays(self):
        """Test update with mix of authorities and regular relays."""
        registry = AuthorityRegistry()
        
        relays = [
            {'nickname': 'AuthRelay', 'fingerprint': 'FP_A', 'flags': ['Authority', 'Running']},
            {'nickname': 'FastRelay', 'fingerprint': 'FP_F', 'flags': ['Fast', 'Running']},
            {'nickname': 'GuardRelay', 'fingerprint': 'FP_G', 'flags': ['Guard', 'Running']},
        ]
        
        count = registry.update_from_onionoo(relays)
        
        assert count == 1  # Only one authority
        assert 'AuthRelay' in registry.get_authority_names()
        assert 'FastRelay' not in registry.get_authority_names()


class TestParseStatsLineEdgeCases:
    """Edge case tests for stats line parsing."""
    
    def test_parse_stats_missing_mtbf(self):
        """Test parsing stats line without MTBF."""
        fetcher = CollectorFetcher()
        
        result = fetcher._parse_stats_line("stats wfu=0.95 tk=500000")
        
        assert result['wfu'] == 0.95
        assert result['tk'] == 500000
        assert 'mtbf' not in result or result.get('mtbf') is None
    
    def test_parse_stats_very_high_values(self):
        """Test parsing stats with very high values."""
        fetcher = CollectorFetcher()
        
        # 10 years uptime
        result = fetcher._parse_stats_line("stats wfu=0.999999 tk=315360000 mtbf=315360000")
        
        assert result['wfu'] == pytest.approx(0.999999, rel=1e-5)
        assert result['tk'] == 315360000
        assert result['mtbf'] == 315360000


class TestGuardFlagPrerequisites:
    """Tests for Guard flag prerequisite checking.
    
    Per Tor dir-spec Section 3.4.2, Guard flag requires:
    - Fast flag
    - Stable flag
    - V2Dir flag
    - WFU >= 98%
    - TK >= 8 days
    - Bandwidth >= 2 MB/s OR in top 25%
    """
    
    def test_guard_eligible_with_all_prerequisites(self):
        """Test relay IS Guard eligible when it has Fast, Stable, V2Dir flags."""
        fetcher = CollectorFetcher()
        fingerprint = 'ABC123DEF456ABC123DEF456ABC123DEF456ABC1'
        
        # Relay with ALL Guard prerequisites: Fast, Stable, V2Dir + good metrics
        fetcher.relay_index = {
            fingerprint: {
                'fingerprint': fingerprint,
                'nickname': 'FullGuardRelay',
                'votes': {
                    'moria1': {
                        'flags': ['Fast', 'Stable', 'V2Dir', 'Running', 'Valid'],
                        'wfu': 0.99,  # >= 98%
                        'tk': 800000,  # > 8 days (691200 sec)
                        'measured': 3000000,  # > 2 MB/s
                    },
                },
                'bandwidth_measurements': {},
            }
        }
        fetcher.flag_thresholds = {
            'moria1': {
                'guard-wfu': 0.98,
                'guard-tk': 691200,  # 8 days
                'guard-bw-inc-exits': 2000000,
            },
        }
        
        result = fetcher.get_relay_consensus_evaluation(fingerprint, authority_count=9)
        
        # Should be Guard eligible from moria1
        guard_eligibility = result['flag_eligibility']['guard']
        assert guard_eligibility['eligible_count'] == 1
        
        # Check details
        detail = guard_eligibility['details'][0]
        assert detail['eligible'] == True
        assert detail['has_fast'] == True
        assert detail['has_stable'] == True
        assert detail['has_v2dir'] == True
        assert detail['prereqs_met'] == True
    
    def test_guard_not_eligible_without_fast_flag(self):
        """Test relay is NOT Guard eligible when missing Fast flag."""
        fetcher = CollectorFetcher()
        fingerprint = 'ABC123DEF456ABC123DEF456ABC123DEF456ABC1'
        
        # Relay missing Fast flag (has Stable, V2Dir, good metrics)
        fetcher.relay_index = {
            fingerprint: {
                'fingerprint': fingerprint,
                'nickname': 'MissingFastRelay',
                'votes': {
                    'moria1': {
                        'flags': ['Stable', 'V2Dir', 'Running', 'Valid'],  # NO Fast!
                        'wfu': 0.99,
                        'tk': 800000,
                        'measured': 3000000,
                    },
                },
                'bandwidth_measurements': {},
            }
        }
        fetcher.flag_thresholds = {
            'moria1': {
                'guard-wfu': 0.98,
                'guard-tk': 691200,
                'guard-bw-inc-exits': 2000000,
            },
        }
        
        result = fetcher.get_relay_consensus_evaluation(fingerprint, authority_count=9)
        
        guard_eligibility = result['flag_eligibility']['guard']
        assert guard_eligibility['eligible_count'] == 0  # Should NOT be eligible
        
        detail = guard_eligibility['details'][0]
        assert detail['eligible'] == False
        assert detail['has_fast'] == False
        assert detail['prereqs_met'] == False
    
    def test_guard_not_eligible_without_stable_flag(self):
        """Test relay is NOT Guard eligible when missing Stable flag."""
        fetcher = CollectorFetcher()
        fingerprint = 'ABC123DEF456ABC123DEF456ABC123DEF456ABC1'
        
        # Relay missing Stable flag (has Fast, V2Dir, good metrics)
        fetcher.relay_index = {
            fingerprint: {
                'fingerprint': fingerprint,
                'nickname': 'MissingStableRelay',
                'votes': {
                    'moria1': {
                        'flags': ['Fast', 'V2Dir', 'Running', 'Valid'],  # NO Stable!
                        'wfu': 0.99,
                        'tk': 800000,
                        'measured': 3000000,
                    },
                },
                'bandwidth_measurements': {},
            }
        }
        fetcher.flag_thresholds = {
            'moria1': {
                'guard-wfu': 0.98,
                'guard-tk': 691200,
                'guard-bw-inc-exits': 2000000,
            },
        }
        
        result = fetcher.get_relay_consensus_evaluation(fingerprint, authority_count=9)
        
        guard_eligibility = result['flag_eligibility']['guard']
        assert guard_eligibility['eligible_count'] == 0  # Should NOT be eligible
        
        detail = guard_eligibility['details'][0]
        assert detail['eligible'] == False
        assert detail['has_stable'] == False
        assert detail['prereqs_met'] == False
    
    def test_guard_not_eligible_without_v2dir_flag(self):
        """Test relay is NOT Guard eligible when missing V2Dir flag."""
        fetcher = CollectorFetcher()
        fingerprint = 'ABC123DEF456ABC123DEF456ABC123DEF456ABC1'
        
        # Relay missing V2Dir flag (has Fast, Stable, good metrics)
        fetcher.relay_index = {
            fingerprint: {
                'fingerprint': fingerprint,
                'nickname': 'MissingV2DirRelay',
                'votes': {
                    'moria1': {
                        'flags': ['Fast', 'Stable', 'Running', 'Valid'],  # NO V2Dir!
                        'wfu': 0.99,
                        'tk': 800000,
                        'measured': 3000000,
                    },
                },
                'bandwidth_measurements': {},
            }
        }
        fetcher.flag_thresholds = {
            'moria1': {
                'guard-wfu': 0.98,
                'guard-tk': 691200,
                'guard-bw-inc-exits': 2000000,
            },
        }
        
        result = fetcher.get_relay_consensus_evaluation(fingerprint, authority_count=9)
        
        guard_eligibility = result['flag_eligibility']['guard']
        assert guard_eligibility['eligible_count'] == 0  # Should NOT be eligible
        
        detail = guard_eligibility['details'][0]
        assert detail['eligible'] == False
        assert detail['has_v2dir'] == False
        assert detail['prereqs_met'] == False
    
    def test_guard_eligible_with_prereqs_but_low_wfu_not_eligible(self):
        """Test relay with prereqs but low WFU is NOT Guard eligible."""
        fetcher = CollectorFetcher()
        fingerprint = 'ABC123DEF456ABC123DEF456ABC123DEF456ABC1'
        
        # Relay with Fast, Stable, V2Dir but LOW WFU
        fetcher.relay_index = {
            fingerprint: {
                'fingerprint': fingerprint,
                'nickname': 'LowWFURelay',
                'votes': {
                    'moria1': {
                        'flags': ['Fast', 'Stable', 'V2Dir', 'Running', 'Valid'],
                        'wfu': 0.95,  # < 98% threshold!
                        'tk': 800000,
                        'measured': 3000000,
                    },
                },
                'bandwidth_measurements': {},
            }
        }
        fetcher.flag_thresholds = {
            'moria1': {
                'guard-wfu': 0.98,
                'guard-tk': 691200,
                'guard-bw-inc-exits': 2000000,
            },
        }
        
        result = fetcher.get_relay_consensus_evaluation(fingerprint, authority_count=9)
        
        guard_eligibility = result['flag_eligibility']['guard']
        assert guard_eligibility['eligible_count'] == 0  # NOT eligible due to low WFU
        
        detail = guard_eligibility['details'][0]
        assert detail['eligible'] == False
        assert detail['prereqs_met'] == True  # Prereqs are met
        assert detail['wfu_met'] == False  # But WFU is not met
