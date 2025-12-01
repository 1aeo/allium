#!/usr/bin/env python3
"""
Test network health dashboard calculations and metrics
"""

import unittest
from unittest.mock import Mock, patch
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from allium.lib.relays import Relays, determine_ipv6_support

class TestNetworkHealthDashboard(unittest.TestCase):
    
    def setUp(self):
        """Set up test data"""
        self.sample_relay_data = {
            'relays': [
                {
                    'fingerprint': 'AAAA1111BBBB2222CCCC3333DDDD4444EEEE5555',
                    'contact': 'operator1@example.com',
                    'or_addresses': ['192.168.1.1:9001', '[2001:db8::1]:9001'],
                    'observed_bandwidth': 1000000,
                    'consensus_weight': 100,
                    'advertised_bandwidth': 1200000,
                    'flags': ['Fast', 'Stable', 'Running', 'V2Dir'],
                    'running': True,
                    'country': 'US',
                    'as': '12345',
                    'as_name': 'Test AS',
                    'first_seen': '2023-01-01 00:00:00',
                    'last_seen': '2024-01-01 00:00:00',
                    'platform': 'Tor 0.4.8.10 on Linux',
                    'version': '0.4.8.10',
                    'version_status': 'recommended',
                    'exit_policy': ['accept *:80', 'accept *:443', 'reject *:*'],
                    'uptime': 85.5
                }
            ]
        }

    def test_ipv6_support_detection(self):
        """Test IPv6 support determination"""
        # Both IPv4 and IPv6
        addresses_both = ['192.168.1.1:9001', '[2001:db8::1]:9001']
        self.assertEqual(determine_ipv6_support(addresses_both), 'both')
        
        # IPv4 only
        addresses_ipv4 = ['192.168.1.1:9001']
        self.assertEqual(determine_ipv6_support(addresses_ipv4), 'ipv4_only')
        
        # Empty addresses - updated expectation
        self.assertEqual(determine_ipv6_support([]), 'none')
        
        # IPv6 only
        addresses_ipv6 = ['[2001:db8::1]:9001']
        self.assertEqual(determine_ipv6_support(addresses_ipv6), 'ipv6_only')

    def test_network_health_calculation_basic(self):
        """Test basic network health metrics calculation"""
        relays_obj = Relays(
            output_dir="/tmp/test", 
            onionoo_url="http://test.url", 
            relay_data=self.sample_relay_data,
            use_bits=False,
            progress=False
        )
        relays_obj._calculate_network_health_metrics()
        
        # Should have network health data
        self.assertIn('network_health', relays_obj.json)
        health_data = relays_obj.json['network_health']
        
        # Check basic counts
        self.assertIn('relays_total', health_data)
        self.assertIn('exit_count', health_data)
        self.assertIn('guard_count', health_data)

    def test_ipv6_operator_tracking_fix(self):
        """Test that IPv6 operator tracking uses correct field name"""
        relays_obj = Relays(
            output_dir="/tmp/test", 
            onionoo_url="http://test.url", 
            relay_data=self.sample_relay_data,
            use_bits=False,
            progress=False
        )
        relays_obj._calculate_network_health_metrics()
        
        # Should have IPv6 metrics
        health_data = relays_obj.json['network_health']
        self.assertIn('ipv4_only_operators', health_data)
        self.assertIn('both_ipv4_ipv6_operators', health_data)
        
    def test_consensus_weight_calculations(self):
        """Test consensus weight percentage calculations"""
        relays_obj = Relays(
            output_dir="/tmp/test", 
            onionoo_url="http://test.url", 
            relay_data=self.sample_relay_data,
            use_bits=False,
            progress=False
        )
        relays_obj._calculate_network_health_metrics()
        
        health_data = relays_obj.json['network_health']
        
        # Test percentage calculations exist
        if isinstance(health_data, dict):
            total_percentage = (
                health_data.get('guard_percentage', 0) +
                health_data.get('middle_percentage', 0) +
                health_data.get('exit_percentage', 0)
            )
            self.assertLessEqual(total_percentage, 100.0)  # Should not exceed 100%
        
    def test_exit_policy_analysis(self):
        """Test exit policy restriction analysis"""
        # Test with unrestricted exit
        unrestricted_relay = self.sample_relay_data['relays'][0].copy()
        unrestricted_relay['exit_policy'] = ['accept *:*']
        
        relays_obj = Relays(
            output_dir="/tmp/test", 
            onionoo_url="http://test.url", 
            relay_data=self.sample_relay_data,
            use_bits=False,
            progress=False
        )
        relays_obj._calculate_network_health_metrics()
        
        # Should have exit policy metrics
        health_data = relays_obj.json['network_health']
        self.assertIn('unrestricted_exits', health_data)
        self.assertIn('restricted_exits', health_data)
        self.assertIn('web_traffic_exits', health_data)

    def test_cw_bw_ratio_calculations(self):
        """Test CW/BW ratio calculations"""
        relays_obj = Relays(
            output_dir="/tmp/test", 
            onionoo_url="http://test.url", 
            relay_data=self.sample_relay_data,
            use_bits=False,
            progress=False
        )
        relays_obj._calculate_network_health_metrics()
        
        health_data = relays_obj.json['network_health']
        
        # Should have CW/BW ratios
        self.assertIn('exit_cw_bw_overall', health_data)
        self.assertIn('guard_cw_bw_overall', health_data)
        self.assertIn('middle_cw_bw_overall', health_data)

    def test_unique_families_count_fix(self):
        """Test that families_count correctly counts unique families, not family member entries"""
        # Create test data with 2 families:
        # Family 1: 3 relays (fingerprints A, B, C) 
        # Family 2: 2 relays (fingerprints D, E)
        # This should result in families_count = 2, not 5
        family_test_data = {
            'relays': [
                {
                    'fingerprint': 'AAAA1111BBBB2222CCCC3333DDDD4444EEEE5555',
                    'contact': 'operator1@example.com',
                    'effective_family': ['AAAA1111BBBB2222CCCC3333DDDD4444EEEE5555', 'BBBB2222CCCC3333DDDD4444EEEE5555AAAA1111', 'CCCC3333DDDD4444EEEE5555AAAA1111BBBB2222'],
                    'or_addresses': ['192.168.1.1:9001'],
                    'observed_bandwidth': 1000000,
                    'consensus_weight': 100,
                    'flags': ['Fast', 'Running'],
                    'running': True,
                    'country': 'US',
                    'first_seen': '2023-01-01 00:00:00',
                    'platform': 'Tor 0.4.8.10 on Linux',
                    'contact_md5': 'hash1'
                },
                {
                    'fingerprint': 'BBBB2222CCCC3333DDDD4444EEEE5555AAAA1111', 
                    'contact': 'operator1@example.com',
                    'effective_family': ['AAAA1111BBBB2222CCCC3333DDDD4444EEEE5555', 'BBBB2222CCCC3333DDDD4444EEEE5555AAAA1111', 'CCCC3333DDDD4444EEEE5555AAAA1111BBBB2222'],
                    'or_addresses': ['192.168.1.2:9001'],
                    'observed_bandwidth': 1000000,
                    'consensus_weight': 100,
                    'flags': ['Fast', 'Running'],
                    'running': True,
                    'country': 'US',
                    'first_seen': '2023-01-01 00:00:00',
                    'platform': 'Tor 0.4.8.10 on Linux',
                    'contact_md5': 'hash1'
                },
                {
                    'fingerprint': 'CCCC3333DDDD4444EEEE5555AAAA1111BBBB2222',
                    'contact': 'operator1@example.com',
                    'effective_family': ['AAAA1111BBBB2222CCCC3333DDDD4444EEEE5555', 'BBBB2222CCCC3333DDDD4444EEEE5555AAAA1111', 'CCCC3333DDDD4444EEEE5555AAAA1111BBBB2222'],
                    'or_addresses': ['192.168.1.3:9001'],
                    'observed_bandwidth': 1000000,
                    'consensus_weight': 100,
                    'flags': ['Fast', 'Running'],
                    'running': True,
                    'country': 'US',
                    'first_seen': '2023-01-01 00:00:00',
                    'platform': 'Tor 0.4.8.10 on Linux',
                    'contact_md5': 'hash1'
                },
                {
                    'fingerprint': 'DDDD4444EEEE5555AAAA1111BBBB2222CCCC3333',
                    'contact': 'operator2@example.com',
                    'effective_family': ['DDDD4444EEEE5555AAAA1111BBBB2222CCCC3333', 'EEEE5555AAAA1111BBBB2222CCCC3333DDDD4444'],
                    'or_addresses': ['192.168.1.4:9001'],
                    'observed_bandwidth': 1000000,
                    'consensus_weight': 100,
                    'flags': ['Fast', 'Running'],
                    'running': True,
                    'country': 'DE',
                    'first_seen': '2023-01-01 00:00:00',
                    'platform': 'Tor 0.4.8.10 on Linux',
                    'contact_md5': 'hash2'
                },
                {
                    'fingerprint': 'EEEE5555AAAA1111BBBB2222CCCC3333DDDD4444',
                    'contact': 'operator2@example.com',
                    'effective_family': ['DDDD4444EEEE5555AAAA1111BBBB2222CCCC3333', 'EEEE5555AAAA1111BBBB2222CCCC3333DDDD4444'],
                    'or_addresses': ['192.168.1.5:9001'],
                    'observed_bandwidth': 1000000,
                    'consensus_weight': 100,
                    'flags': ['Fast', 'Running'],
                    'running': True,
                    'country': 'DE',
                    'first_seen': '2023-01-01 00:00:00',
                    'platform': 'Tor 0.4.8.10 on Linux',
                    'contact_md5': 'hash2'
                }
            ]
        }
        
        relays_obj = Relays(
            output_dir="/tmp/test", 
            onionoo_url="http://test.url", 
            relay_data=family_test_data,
            use_bits=False,
            progress=False
        )
        
        # Process data to create family sorted data structure
        relays_obj._categorize()
        relays_obj._calculate_network_health_metrics()
        
        # Verify the fix: should count 2 unique families, not 5 family member entries
        health_data = relays_obj.json['network_health']
        self.assertEqual(health_data['families_count'], 2, 
                         "families_count should count unique families (2), not family member entries (5)")
        
        # Verify that the old incorrect calculation would have returned 5
        # by checking the length of the sorted family data structure
        raw_family_count = len(relays_obj.json["sorted"].get('family', {}))
        self.assertEqual(raw_family_count, 5, 
                         "The raw family data structure should have 5 entries (one per family member)")
        
        # Verify families_count is different from raw count (proves the fix works)
        self.assertNotEqual(health_data['families_count'], raw_family_count,
                           "families_count should be different from raw family member count")

    def test_intelligence_engine_families_count_fix(self):
        """Test that intelligence engine also correctly counts unique families, not family member entries"""
        # Use the same test data as the previous test
        family_test_data = {
            'relays': [
                {
                    'fingerprint': 'AAAA1111BBBB2222CCCC3333DDDD4444EEEE5555',
                    'contact': 'operator1@example.com',
                    'effective_family': ['AAAA1111BBBB2222CCCC3333DDDD4444EEEE5555', 'BBBB2222CCCC3333DDDD4444EEEE5555AAAA1111', 'CCCC3333DDDD4444EEEE5555AAAA1111BBBB2222'],
                    'or_addresses': ['192.168.1.1:9001'],
                    'observed_bandwidth': 1000000,
                    'consensus_weight': 100,
                    'flags': ['Fast', 'Running'],
                    'running': True,
                    'country': 'US',
                    'first_seen': '2023-01-01 00:00:00',
                    'platform': 'Tor 0.4.8.10 on Linux',
                    'contact_md5': 'hash1'
                },
                {
                    'fingerprint': 'BBBB2222CCCC3333DDDD4444EEEE5555AAAA1111', 
                    'contact': 'operator1@example.com',
                    'effective_family': ['AAAA1111BBBB2222CCCC3333DDDD4444EEEE5555', 'BBBB2222CCCC3333DDDD4444EEEE5555AAAA1111', 'CCCC3333DDDD4444EEEE5555AAAA1111BBBB2222'],
                    'or_addresses': ['192.168.1.2:9001'],
                    'observed_bandwidth': 1000000,
                    'consensus_weight': 100,
                    'flags': ['Fast', 'Running'],
                    'running': True,
                    'country': 'US',
                    'first_seen': '2023-01-01 00:00:00',
                    'platform': 'Tor 0.4.8.10 on Linux',
                    'contact_md5': 'hash1'
                },
                {
                    'fingerprint': 'CCCC3333DDDD4444EEEE5555AAAA1111BBBB2222',
                    'contact': 'operator1@example.com',
                    'effective_family': ['AAAA1111BBBB2222CCCC3333DDDD4444EEEE5555', 'BBBB2222CCCC3333DDDD4444EEEE5555AAAA1111', 'CCCC3333DDDD4444EEEE5555AAAA1111BBBB2222'],
                    'or_addresses': ['192.168.1.3:9001'],
                    'observed_bandwidth': 1000000,
                    'consensus_weight': 100,
                    'flags': ['Fast', 'Running'],
                    'running': True,
                    'country': 'US',
                    'first_seen': '2023-01-01 00:00:00',
                    'platform': 'Tor 0.4.8.10 on Linux',
                    'contact_md5': 'hash1'
                },
                {
                    'fingerprint': 'DDDD4444EEEE5555AAAA1111BBBB2222CCCC3333',
                    'contact': 'operator2@example.com',
                    'effective_family': ['DDDD4444EEEE5555AAAA1111BBBB2222CCCC3333', 'EEEE5555AAAA1111BBBB2222CCCC3333DDDD4444'],
                    'or_addresses': ['192.168.1.4:9001'],
                    'observed_bandwidth': 1000000,
                    'consensus_weight': 100,
                    'flags': ['Fast', 'Running'],
                    'running': True,
                    'country': 'DE',
                    'first_seen': '2023-01-01 00:00:00',
                    'platform': 'Tor 0.4.8.10 on Linux',
                    'contact_md5': 'hash2'
                },
                {
                    'fingerprint': 'EEEE5555AAAA1111BBBB2222CCCC3333DDDD4444',
                    'contact': 'operator2@example.com',
                    'effective_family': ['DDDD4444EEEE5555AAAA1111BBBB2222CCCC3333', 'EEEE5555AAAA1111BBBB2222CCCC3333DDDD4444'],
                    'or_addresses': ['192.168.1.5:9001'],
                    'observed_bandwidth': 1000000,
                    'consensus_weight': 100,
                    'flags': ['Fast', 'Running'],
                    'running': True,
                    'country': 'DE',
                    'first_seen': '2023-01-01 00:00:00',
                    'platform': 'Tor 0.4.8.10 on Linux',
                    'contact_md5': 'hash2'
                }
            ]
        }
        
        relays_obj = Relays(
            output_dir="/tmp/test", 
            onionoo_url="http://test.url", 
            relay_data=family_test_data,
            use_bits=False,
            progress=False
        )
        
        # Process data to create sorted data structure and generate smart context
        relays_obj._categorize()
        relays_obj._generate_smart_context()
        
        # Verify intelligence engine uses correct unique family count
        smart_context = relays_obj.json.get('smart_context', {})
        basic_relationships = smart_context.get('basic_relationships', {})
        template_optimized = basic_relationships.get('template_optimized', {})
        
        intelligence_families_count = template_optimized.get('total_families', -1)
        self.assertEqual(intelligence_families_count, 2, 
                         "Intelligence engine total_families should count unique families (2), not family member entries (5)")
        
        # Verify this matches the network health dashboard calculation
        relays_obj._calculate_network_health_metrics()
        health_data = relays_obj.json['network_health']
        self.assertEqual(intelligence_families_count, health_data['families_count'],
                        "Intelligence engine total_families should match network health families_count")
 
if __name__ == '__main__':
    unittest.main() 