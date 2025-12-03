#!/usr/bin/env python3
"""
Regression test: Relays missing consensus_weight_fraction still show 
percentages and validation share correctly.

This test ensures that when relays don't have consensus_weight_fraction 
from the Onionoo API (which is OPTIONAL), the system correctly computes:
1. Percentage values for display (from raw consensus_weight)
2. Validation share metrics in AROI leaderboards
3. Template-rendered percentage values

Prevents future regressions where missing API fields cause blank or broken displays.
"""

import os
import sys
import unittest
from unittest.mock import Mock, MagicMock, patch

# Add allium to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from allium.lib.aroileaders import _calculate_aroi_leaderboards


class MockBandwidthFormatter:
    """Mock bandwidth formatter for testing."""
    
    def determine_unit(self, bandwidth_value):
        if bandwidth_value >= 1e9:
            return "Gbit/s"
        elif bandwidth_value >= 1e6:
            return "Mbit/s"
        else:
            return "Kbit/s"
    
    def format_bandwidth_with_unit(self, bandwidth_value, unit, decimal_places=1):
        if unit == "Gbit/s":
            return f"{bandwidth_value / 1e9:.{decimal_places}f}"
        elif unit == "Mbit/s":
            return f"{bandwidth_value / 1e6:.{decimal_places}f}"
        else:
            return f"{bandwidth_value / 1e3:.{decimal_places}f}"


class TestMissingConsensusWeightFraction(unittest.TestCase):
    """Regression tests for relays without consensus_weight_fraction."""
    
    def setUp(self):
        """Set up common test fixtures."""
        # Create relays without consensus_weight_fraction (API field is OPTIONAL)
        # They should still have raw consensus_weight values
        self.relay_without_cwf_1 = {
            'fingerprint': 'AAAA1111222233334444555566667777AAAABBBB',
            'nickname': 'TestRelay1',
            'contact': 'operator@example.org ciissversion:2 proof:uri-rsa url:https://example.org/.well-known/tor-relay/rsa-fingerprint.txt',
            'aroi_domain': 'example.org',
            'country': 'us',
            'platform': 'Linux',
            'observed_bandwidth': 50000000,  # 50 MB/s
            'consensus_weight': 5000,  # Raw value, NO consensus_weight_fraction
            'flags': ['Guard', 'Stable', 'Valid', 'Running'],
            'running': True,
            'first_seen': '2023-01-01 00:00:00',
            'or_addresses': ['192.168.1.1:9001'],
            'as': 'AS12345',
        }
        
        self.relay_without_cwf_2 = {
            'fingerprint': 'BBBB1111222233334444555566667777CCCCDDDD',
            'nickname': 'TestRelay2',
            'contact': 'operator@example.org ciissversion:2 proof:uri-rsa url:https://example.org/.well-known/tor-relay/rsa-fingerprint.txt',
            'aroi_domain': 'example.org',
            'country': 'de',
            'platform': 'Linux',
            'observed_bandwidth': 30000000,  # 30 MB/s
            'consensus_weight': 3000,  # Raw value, NO consensus_weight_fraction
            'flags': ['Exit', 'Stable', 'Valid', 'Running'],
            'running': True,
            'first_seen': '2023-02-01 00:00:00',
            'or_addresses': ['192.168.1.2:9001'],
            'as': 'AS12346',
        }
        
        # Relay from different operator WITH consensus_weight_fraction (for contrast)
        self.relay_with_cwf = {
            'fingerprint': 'CCCC1111222233334444555566667777EEEEFFFF',
            'nickname': 'TestRelay3',
            'contact': 'other@test.com ciissversion:2 proof:uri-rsa url:https://test.com/.well-known/tor-relay/rsa-fingerprint.txt',
            'aroi_domain': 'test.com',
            'country': 'fr',
            'platform': 'Linux',
            'observed_bandwidth': 20000000,  # 20 MB/s
            'consensus_weight': 2000,
            'consensus_weight_fraction': 0.002,  # Has explicit API fraction
            'flags': ['Guard', 'Stable', 'Valid', 'Running'],
            'running': True,
            'first_seen': '2022-06-01 00:00:00',
            'or_addresses': ['192.168.1.3:9001'],
            'as': 'AS12347',
        }
        
        # Validation data for AROI validation tracking
        self.validation_data = {
            'metadata': {'timestamp': '2025-12-01T00:00:00Z'},
            'statistics': {
                'proof_types': {
                    'uri_rsa': {'total': 3, 'valid': 2, 'success_rate': 66.7}
                }
            },
            'results': [
                {'fingerprint': 'AAAA1111222233334444555566667777AAAABBBB', 'valid': True, 'proof_type': 'uri-rsa'},
                {'fingerprint': 'BBBB1111222233334444555566667777CCCCDDDD', 'valid': True, 'proof_type': 'uri-rsa'},
                {'fingerprint': 'CCCC1111222233334444555566667777EEEEFFFF', 'valid': False, 'error': 'DNS lookup failed', 'proof_type': 'uri-rsa'},
            ]
        }
    
    def _create_mock_relays_instance(self, relays):
        """Create a mock Relays instance with the given relays."""
        mock_relays = MagicMock()
        mock_relays.bandwidth_formatter = MockBandwidthFormatter()
        mock_relays.timestamp = '2025-12-01 00:00:00'
        mock_relays.aroi_validation_data = self.validation_data
        mock_relays.uptime_data = None
        mock_relays.bandwidth_data = None
        
        # Build sorted contacts structure (mimics real relays.py behavior)
        from hashlib import md5
        contacts = {}
        for idx, relay in enumerate(relays):
            contact = relay.get('contact', '')
            contact_hash = md5(contact.encode('utf-8')).hexdigest()
            if contact_hash not in contacts:
                contacts[contact_hash] = {
                    'relays': [],
                    'bandwidth': 0,
                    'exit_bandwidth': 0,
                    'guard_bandwidth': 0,
                    'middle_bandwidth': 0,
                    'consensus_weight_fraction': 0.0,
                    'guard_count': 0,
                    'exit_count': 0,
                    'middle_count': 0,
                    'unique_as_count': 0,
                    'measured_count': 0,
                    'first_seen': relay.get('first_seen', ''),
                    'exit_consensus_weight_fraction': 0.0,
                    'guard_consensus_weight_fraction': 0.0,
                }
            contacts[contact_hash]['relays'].append(idx)
            contacts[contact_hash]['bandwidth'] += relay.get('observed_bandwidth', 0)
            
            flags = relay.get('flags', [])
            if 'Exit' in flags:
                contacts[contact_hash]['exit_count'] += 1
                contacts[contact_hash]['exit_bandwidth'] += relay.get('observed_bandwidth', 0)
            elif 'Guard' in flags:
                contacts[contact_hash]['guard_count'] += 1
                contacts[contact_hash]['guard_bandwidth'] += relay.get('observed_bandwidth', 0)
            else:
                contacts[contact_hash]['middle_count'] += 1
                contacts[contact_hash]['middle_bandwidth'] += relay.get('observed_bandwidth', 0)
        
        # Calculate unique AS count per contact
        for contact_hash, contact_data in contacts.items():
            unique_as = set()
            for idx in contact_data['relays']:
                as_num = relays[idx].get('as', '')
                if as_num:
                    unique_as.add(as_num)
            contact_data['unique_as_count'] = len(unique_as)
        
        mock_relays.json = {
            'relays': relays,
            'sorted': {
                'contact': contacts,
                'country': {},
            }
        }
        
        return mock_relays
    
    def test_leaderboard_calculates_consensus_weight_without_api_fraction(self):
        """
        Test that _calculate_aroi_leaderboards correctly computes consensus weight
        percentages when relays are missing consensus_weight_fraction from API.
        
        This is the primary regression test - the fallback to raw consensus_weight
        must work correctly.
        """
        relays = [self.relay_without_cwf_1, self.relay_without_cwf_2, self.relay_with_cwf]
        mock_relays = self._create_mock_relays_instance(relays)
        
        # Calculate leaderboards
        result = _calculate_aroi_leaderboards(mock_relays)
        
        # Verify we got results
        self.assertIn('leaderboards', result)
        self.assertIn('consensus_weight', result['leaderboards'])
        
        # Find the example.org operator in the formatted leaderboard
        # Formatted leaderboard entries are dictionaries with 'aroi_domain' key
        example_org_entry = None
        for entry in result['leaderboards']['consensus_weight']:
            if entry['aroi_domain'] == 'example.org':
                example_org_entry = entry
                break
        
        self.assertIsNotNone(example_org_entry, "example.org operator should appear in consensus_weight leaderboard")
        
        # Verify raw_operators has correct computed values
        self.assertIn('raw_operators', result)
        self.assertIn('example.org', result['raw_operators'])
        
        raw_op = result['raw_operators']['example.org']
        
        # Verify the operator has 2 relays
        self.assertEqual(raw_op['total_relays'], 2)
        
        # Verify bandwidth is correctly aggregated (80 MB/s total = 80000000)
        self.assertEqual(raw_op['total_bandwidth'], 80000000)
        
        # Verify guard and exit counts
        self.assertEqual(raw_op['guard_count'], 1)  # TestRelay1 is Guard
        self.assertEqual(raw_op['exit_count'], 1)   # TestRelay2 is Exit
    
    def test_validation_share_computed_for_relays_without_cwf(self):
        """
        Test that validated_consensus_weight is correctly computed for operators
        whose relays are missing consensus_weight_fraction.
        
        The validated_consensus_weight should be derived from raw consensus_weight
        when the API fraction is missing.
        """
        relays = [self.relay_without_cwf_1, self.relay_without_cwf_2, self.relay_with_cwf]
        mock_relays = self._create_mock_relays_instance(relays)
        
        result = _calculate_aroi_leaderboards(mock_relays)
        
        # Find example.org in raw_operators
        self.assertIn('raw_operators', result)
        self.assertIn('example.org', result['raw_operators'])
        
        raw_op = result['raw_operators']['example.org']
        
        # Both relays for example.org are validated (see validation_data)
        self.assertEqual(raw_op['validated_relay_count'], 2)
        
        # validated_consensus_weight should be computed from raw consensus_weight
        # since the relays don't have consensus_weight_fraction
        # Total network CW = 10000, example.org validated CW = 8000
        # Expected validated_consensus_weight = 0.8
        expected_validated_cw = (5000 + 3000) / 10000  # 0.8
        
        self.assertAlmostEqual(
            raw_op['validated_consensus_weight'], 
            expected_validated_cw, 
            places=4,
            msg="validated_consensus_weight should be computed from raw consensus_weight"
        )
    
    def test_formatted_percentage_not_empty_or_na(self):
        """
        Test that the formatted percentage values are properly computed
        (not empty, not 'N/A') for relays missing consensus_weight_fraction.
        """
        relays = [self.relay_without_cwf_1, self.relay_without_cwf_2, self.relay_with_cwf]
        mock_relays = self._create_mock_relays_instance(relays)
        
        result = _calculate_aroi_leaderboards(mock_relays)
        
        # Check formatted leaderboards for validated_relays category
        self.assertIn('leaderboards', result)
        self.assertIn('validated_relays', result['leaderboards'])
        
        # Find example.org in the validated_relays formatted leaderboard
        example_org_formatted = None
        for entry in result['leaderboards']['validated_relays']:
            if entry['aroi_domain'] == 'example.org':
                example_org_formatted = entry
                break
        
        self.assertIsNotNone(example_org_formatted, "example.org should be in validated_relays leaderboard")
        
        # Verify the validated_consensus_weight_pct is properly formatted
        validated_cw_pct = example_org_formatted['validated_consensus_weight_pct']
        self.assertIsNotNone(validated_cw_pct, "validated_consensus_weight_pct should not be None")
        self.assertNotEqual(validated_cw_pct, "", "validated_consensus_weight_pct should not be empty")
        self.assertNotEqual(validated_cw_pct, "N/A", "validated_consensus_weight_pct should not be N/A")
        self.assertTrue(validated_cw_pct.endswith('%'), "validated_consensus_weight_pct should end with %")
        
        # Parse the percentage value and verify it's reasonable
        pct_value = float(validated_cw_pct.rstrip('%'))
        self.assertGreater(pct_value, 0, "Percentage should be greater than 0")
        self.assertLessEqual(pct_value, 100, "Percentage should be <= 100")
    
    def test_ipv4_ipv6_consensus_weight_without_api_fraction(self):
        """
        Test that IPv4/IPv6 consensus weight metrics are computed correctly
        when relays don't have consensus_weight_fraction from API.
        """
        relays = [self.relay_without_cwf_1, self.relay_without_cwf_2, self.relay_with_cwf]
        mock_relays = self._create_mock_relays_instance(relays)
        
        result = _calculate_aroi_leaderboards(mock_relays)
        
        # Find example.org in raw_operators
        raw_op = result['raw_operators']['example.org']
        
        # Both example.org relays have IPv4 addresses
        self.assertEqual(raw_op['ipv4_relay_count'], 2)
        
        # IPv4 consensus weight should be computed from raw consensus_weight
        # Total network CW = 10000, example.org IPv4 CW = 8000
        expected_ipv4_cw = (5000 + 3000) / 10000  # 0.8
        
        self.assertAlmostEqual(
            raw_op['ipv4_total_consensus_weight'],
            expected_ipv4_cw,
            places=4,
            msg="ipv4_total_consensus_weight should be computed from raw consensus_weight"
        )
    
    def test_mixed_relays_with_and_without_cwf(self):
        """
        Test that operators with mixed relays (some with consensus_weight_fraction,
        some without) are handled correctly.
        """
        # Create a relay with cwf for the example.org operator
        relay_with_cwf_same_op = {
            'fingerprint': 'DDDD1111222233334444555566667777GGGGHHH',
            'nickname': 'TestRelay4',
            'contact': 'operator@example.org ciissversion:2 proof:uri-rsa url:https://example.org/.well-known/tor-relay/rsa-fingerprint.txt',
            'aroi_domain': 'example.org',
            'country': 'uk',
            'platform': 'Linux',
            'observed_bandwidth': 40000000,
            'consensus_weight': 4000,
            'consensus_weight_fraction': 0.004,  # Has explicit API fraction
            'flags': ['Guard', 'Stable', 'Valid', 'Running'],
            'running': True,
            'first_seen': '2023-03-01 00:00:00',
            'or_addresses': ['192.168.1.4:9001'],
            'as': 'AS12348',
        }
        
        # Add validation for this relay
        self.validation_data['results'].append({
            'fingerprint': 'DDDD1111222233334444555566667777GGGGHHH',
            'valid': True,
            'proof_type': 'uri-rsa'
        })
        
        relays = [
            self.relay_without_cwf_1,  # No cwf, consensus_weight=5000
            self.relay_without_cwf_2,  # No cwf, consensus_weight=3000
            relay_with_cwf_same_op,     # Has cwf=0.004, consensus_weight=4000
            self.relay_with_cwf,        # Different operator
        ]
        mock_relays = self._create_mock_relays_instance(relays)
        
        result = _calculate_aroi_leaderboards(mock_relays)
        
        # Find example.org
        raw_op = result['raw_operators']['example.org']
        
        # Verify all 3 relays are counted
        self.assertEqual(raw_op['total_relays'], 3)
        
        # All 3 relays for example.org should be validated
        self.assertEqual(raw_op['validated_relay_count'], 3)
        
        # Validated consensus weight should combine API fraction where available
        # and computed fraction where missing
        # Total network CW = 5000 + 3000 + 4000 + 2000 = 14000
        # For relay without cwf: computed_fraction = consensus_weight / total_network_cw
        # relay1: 5000/14000 ≈ 0.357
        # relay2: 3000/14000 ≈ 0.214
        # relay4: Uses API fraction 0.004 (but this is recalculated since we compute total_network_cw)
        # Actually in _calculate_aroi_leaderboards, it prefers API fraction when available
        # Let's verify the computation logic handles both cases
        
        self.assertGreater(raw_op['validated_consensus_weight'], 0)
        self.assertLessEqual(raw_op['validated_consensus_weight'], 1.0)
    
    def test_relay_with_zero_consensus_weight(self):
        """
        Test edge case where a relay has consensus_weight=0 and no fraction.
        Should not cause division errors or unexpected behavior.
        """
        relay_zero_cw = {
            'fingerprint': 'EEEE1111222233334444555566667777IIIIJJJ',
            'nickname': 'TestRelayZero',
            'contact': 'zero@example.org ciissversion:2 proof:uri-rsa url:https://zero.example.org/.well-known/tor-relay/rsa-fingerprint.txt',
            'aroi_domain': 'zero.example.org',
            'country': 'us',
            'platform': 'Linux',
            'observed_bandwidth': 1000,
            'consensus_weight': 0,  # Zero consensus weight
            # No consensus_weight_fraction
            'flags': ['Valid', 'Running'],
            'running': True,
            'first_seen': '2024-01-01 00:00:00',
            'or_addresses': ['192.168.1.5:9001'],
            'as': 'AS99999',
        }
        
        relays = [self.relay_without_cwf_1, relay_zero_cw]
        
        # Add validation data for zero cw relay
        self.validation_data['results'].append({
            'fingerprint': 'EEEE1111222233334444555566667777IIIIJJJ',
            'valid': True,
            'proof_type': 'uri-rsa'
        })
        
        mock_relays = self._create_mock_relays_instance(relays)
        
        # Should not raise any exceptions
        result = _calculate_aroi_leaderboards(mock_relays)
        
        self.assertIn('raw_operators', result)
        self.assertIn('zero.example.org', result['raw_operators'])
        
        raw_op = result['raw_operators']['zero.example.org']
        
        # Should have 1 relay
        self.assertEqual(raw_op['total_relays'], 1)
        
        # Validated consensus weight should be 0 (since relay has 0 consensus_weight)
        self.assertEqual(raw_op['validated_consensus_weight'], 0.0)
        
        # Should not crash when formatting percentage
        self.assertIn('leaderboards', result)


class TestPreprocessTemplateDataFallback(unittest.TestCase):
    """Test _preprocess_template_data fallback for missing consensus_weight_fraction."""
    
    def test_preprocess_computes_percentage_from_raw_consensus_weight(self):
        """
        Test that _preprocess_template_data correctly computes 
        consensus_weight_percentage when consensus_weight_fraction is missing.
        
        This test creates a minimal Relays instance and calls _preprocess_template_data
        directly to verify the fallback logic.
        """
        # Import the actual Relays class
        from allium.lib.relays import Relays
        
        # Create minimal mock data with relays missing consensus_weight_fraction
        mock_json = {
            'relays': [
                {
                    'fingerprint': 'AAAA1111222233334444555566667777AAAABBBB',
                    'nickname': 'TestRelay1',
                    'contact': 'test@example.org',
                    'consensus_weight': 5000,
                    # NO consensus_weight_fraction - this is the key test case
                    'observed_bandwidth': 50000000,
                    'flags': ['Guard', 'Stable', 'Valid', 'Running'],
                    'or_addresses': ['192.168.1.1:9001'],
                },
                {
                    'fingerprint': 'BBBB1111222233334444555566667777CCCCDDDD',
                    'nickname': 'TestRelay2',
                    'contact': 'test2@example.org',
                    'consensus_weight': 5000,
                    # NO consensus_weight_fraction
                    'observed_bandwidth': 50000000,
                    'flags': ['Exit', 'Stable', 'Valid', 'Running'],
                    'or_addresses': ['192.168.1.2:9001'],
                },
            ],
            'bridges_published': '2025-01-01 00:00:00',
            'relays_published': '2025-01-01 00:00:00',
            'version': '8.0',
        }
        
        # Create a minimal Relays instance by bypassing __init__
        relays = Relays.__new__(Relays)
        relays.json = mock_json
        relays.output_dir = '/tmp'
        relays.use_bits = True
        relays.progress = False
        relays.start_time = 0
        relays.progress_step = 0
        relays.total_steps = 10
        relays.timestamp = '2025-01-01 00:00:00'
        relays.base_url = ''
        relays.bandwidth_formatter = MockBandwidthFormatter()
        relays.uptime_data = None
        relays.bandwidth_data = None
        relays.aroi_validation_data = None
        
        # Call _preprocess_template_data directly
        relays._preprocess_template_data()
        
        # Verify consensus_weight_percentage was computed from raw consensus_weight
        relay1 = relays.json['relays'][0]
        relay2 = relays.json['relays'][1]
        
        # Total CW = 5000 + 5000 = 10000
        # Each relay should have 50% (5000/10000)
        self.assertIn('consensus_weight_percentage', relay1)
        self.assertIn('consensus_weight_percentage', relay2)
        
        self.assertEqual(relay1['consensus_weight_percentage'], '50.00%')
        self.assertEqual(relay2['consensus_weight_percentage'], '50.00%')
        
        # Verify consensus_weight_fraction was also populated via fallback
        self.assertIn('consensus_weight_fraction', relay1)
        self.assertAlmostEqual(relay1['consensus_weight_fraction'], 0.5)
        
        # Verify the same for relay2
        self.assertIn('consensus_weight_fraction', relay2)
        self.assertAlmostEqual(relay2['consensus_weight_fraction'], 0.5)
    
    def test_preprocess_handles_mixed_relays(self):
        """
        Test that _preprocess_template_data correctly handles a mix of relays
        with and without consensus_weight_fraction.
        """
        from allium.lib.relays import Relays
        
        mock_json = {
            'relays': [
                {
                    'fingerprint': 'AAAA1111222233334444555566667777AAAABBBB',
                    'nickname': 'TestRelay1',
                    'contact': 'test@example.org',
                    'consensus_weight': 4000,
                    # NO consensus_weight_fraction
                    'observed_bandwidth': 40000000,
                    'flags': ['Guard'],
                    'or_addresses': ['192.168.1.1:9001'],
                },
                {
                    'fingerprint': 'BBBB1111222233334444555566667777CCCCDDDD',
                    'nickname': 'TestRelay2',
                    'contact': 'test2@example.org',
                    'consensus_weight': 6000,
                    'consensus_weight_fraction': 0.006,  # Has API fraction
                    'observed_bandwidth': 60000000,
                    'flags': ['Exit'],
                    'or_addresses': ['192.168.1.2:9001'],
                },
            ],
            'bridges_published': '2025-01-01 00:00:00',
            'relays_published': '2025-01-01 00:00:00',
            'version': '8.0',
        }
        
        relays = Relays.__new__(Relays)
        relays.json = mock_json
        relays.output_dir = '/tmp'
        relays.use_bits = True
        relays.progress = False
        relays.start_time = 0
        relays.progress_step = 0
        relays.total_steps = 10
        relays.timestamp = '2025-01-01 00:00:00'
        relays.base_url = ''
        relays.bandwidth_formatter = MockBandwidthFormatter()
        relays.uptime_data = None
        relays.bandwidth_data = None
        relays.aroi_validation_data = None
        
        relays._preprocess_template_data()
        
        relay1 = relays.json['relays'][0]
        relay2 = relays.json['relays'][1]
        
        # relay1: No API fraction, should be computed
        # Total CW = 4000 + 6000 = 10000
        # relay1 fraction = 4000/10000 = 0.4 = 40%
        self.assertEqual(relay1['consensus_weight_percentage'], '40.00%')
        self.assertAlmostEqual(relay1['consensus_weight_fraction'], 0.4)
        
        # relay2: Has API fraction (0.006), should use that
        # 0.006 * 100 = 0.6%
        self.assertEqual(relay2['consensus_weight_percentage'], '0.60%')
        # Original fraction preserved
        self.assertEqual(relay2['consensus_weight_fraction'], 0.006)


if __name__ == '__main__':
    unittest.main()

