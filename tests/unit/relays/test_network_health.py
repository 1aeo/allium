#!/usr/bin/env python3
"""
Test network health dashboard calculations and metrics
"""

import unittest
from unittest.mock import Mock, patch

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
        
        # Should have IPv6 AROI operator metrics
        health_data = relays_obj.json['network_health']
        self.assertIn('ipv4_only_aroi_operators', health_data)
        self.assertIn('both_ipv4_ipv6_aroi_operators', health_data)
        
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

    def test_happy_family_migration_metrics(self):
        """Test Happy Family Key Migration metrics with mixed relay versions"""
        relay_data = {
            'relays': [
                {
                    'fingerprint': 'A' * 40,
                    'contact': 'op@example.com',
                    'or_addresses': ['1.2.3.4:9001'],
                    'observed_bandwidth': 1000000,
                    'consensus_weight': 100,
                    'advertised_bandwidth': 1200000,
                    'flags': ['Fast', 'Guard', 'Running', 'V2Dir', 'Authority'],
                    'running': True,
                    'country': 'US',
                    'as': '12345',
                    'as_name': 'Test AS',
                    'first_seen': '2023-01-01 00:00:00',
                    'platform': 'Tor 0.4.9.5 on Linux',
                    'version': '0.4.9.5',
                    'version_status': 'recommended',
                    'recommended_version': True,
                    'aroi_domain': 'example.com',
                },
                {
                    'fingerprint': 'B' * 40,
                    'contact': 'op@example.com',
                    'or_addresses': ['1.2.3.5:9001'],
                    'observed_bandwidth': 500000,
                    'consensus_weight': 50,
                    'advertised_bandwidth': 600000,
                    'flags': ['Fast', 'Stable', 'Running', 'V2Dir'],
                    'running': True,
                    'country': 'DE',
                    'as': '67890',
                    'as_name': 'Test AS 2',
                    'first_seen': '2023-06-01 00:00:00',
                    'platform': 'Tor 0.4.8.12 on Linux',
                    'version': '0.4.8.12',
                    'version_status': 'recommended',
                    'recommended_version': True,
                    'aroi_domain': 'example.com',
                },
                {
                    'fingerprint': 'C' * 40,
                    'contact': 'op2@example2.com',
                    'or_addresses': ['1.2.3.6:9001'],
                    'observed_bandwidth': 800000,
                    'consensus_weight': 80,
                    'advertised_bandwidth': 900000,
                    'flags': ['Fast', 'Exit', 'Running', 'V2Dir'],
                    'running': True,
                    'country': 'FR',
                    'as': '11111',
                    'as_name': 'Test AS 3',
                    'first_seen': '2024-01-01 00:00:00',
                    'platform': 'Tor 0.4.9.3 on Linux',
                    'version': '0.4.9.3',
                    'version_status': 'recommended',
                    'recommended_version': True,
                    'aroi_domain': 'example2.com',
                },
            ]
        }
        
        relays_obj = Relays(
            output_dir="/tmp/test",
            onionoo_url="http://test.url",
            relay_data=relay_data,
            use_bits=False,
            progress=False
        )
        relays_obj._calculate_network_health_metrics()
        
        health = relays_obj.json['network_health']
        
        # 2 of 3 relays run v0.4.9.x+
        self.assertEqual(health['hf_ready_relays'], 2)
        self.assertEqual(health['hf_not_ready_relays'], 1)
        
        # 1 authority relay on v0.4.9.x+
        self.assertEqual(health['hf_ready_authorities'], 1)
        self.assertEqual(health['hf_authorities_remaining'], 6)  # 7 - 1
        
        # 1 exit relay ready, 1 guard relay ready (authority with Guard flag)
        self.assertEqual(health['hf_ready_exit_relays'], 1)
        self.assertEqual(health['hf_ready_guard_relays'], 1)
        
        # Consensus method should be None (no collector data in unit test)
        self.assertIsNone(health['hf_consensus_method'])
        self.assertEqual(health['hf_consensus_method_required'], 35)
        
        # Family-cert count should be 0 (no descriptor data in unit test)
        self.assertEqual(health['hf_family_cert_count'], 0)
        
        # Consensus params should be None (no collector data)
        self.assertIsNone(health['hf_use_family_ids'])
        self.assertIsNone(health['hf_use_family_lists'])
        
        # Bandwidth: relay A (1000000) + relay C (800000) = 1800000
        self.assertEqual(health['hf_ready_bandwidth'], 1800000)
        
        # Ready relay percentage should be correct
        self.assertAlmostEqual(health['hf_ready_relays_percentage'], 2/3 * 100, places=1)

    def test_happy_family_version_edge_cases(self):
        """Test _is_happy_family_ready version parsing edge cases"""
        from allium.lib.network_health import calculate_network_health_metrics
        
        # Access the nested helper by running a minimal calculation
        relay_data = {
            'relays': [
                {
                    'fingerprint': 'A' * 40,
                    'contact': '',
                    'or_addresses': ['1.2.3.4:9001'],
                    'observed_bandwidth': 100,
                    'consensus_weight': 1,
                    'advertised_bandwidth': 100,
                    'flags': ['Running'],
                    'running': True,
                    'country': 'US',
                    'as': '12345',
                    'as_name': 'Test',
                    'first_seen': '2023-01-01 00:00:00',
                    'platform': 'Tor 0.4.9.1-alpha on Linux',
                    'version': '0.4.9.1-alpha',
                    'version_status': 'experimental',
                },
                {
                    'fingerprint': 'B' * 40,
                    'contact': '',
                    'or_addresses': ['1.2.3.5:9001'],
                    'observed_bandwidth': 100,
                    'consensus_weight': 1,
                    'advertised_bandwidth': 100,
                    'flags': ['Running'],
                    'running': True,
                    'country': 'US',
                    'as': '12345',
                    'as_name': 'Test',
                    'first_seen': '2023-01-01 00:00:00',
                    'platform': 'Tor 0.4.9.4-rc-dev on Linux',
                    'version': '0.4.9.4-rc-dev',
                    'version_status': 'experimental',
                },
                {
                    'fingerprint': 'C' * 40,
                    'contact': '',
                    'or_addresses': ['1.2.3.6:9001'],
                    'observed_bandwidth': 100,
                    'consensus_weight': 1,
                    'advertised_bandwidth': 100,
                    'flags': ['Running'],
                    'running': True,
                    'country': 'US',
                    'as': '12345',
                    'as_name': 'Test',
                    'first_seen': '2023-01-01 00:00:00',
                    'platform': 'Tor 0.4.8.22 on Linux',
                    'version': '0.4.8.22',
                    'version_status': 'recommended',
                },
                {
                    'fingerprint': 'D' * 40,
                    'contact': '',
                    'or_addresses': ['1.2.3.7:9001'],
                    'observed_bandwidth': 100,
                    'consensus_weight': 1,
                    'advertised_bandwidth': 100,
                    'flags': ['Running'],
                    'running': True,
                    'country': 'US',
                    'as': '12345',
                    'as_name': 'Test',
                    'first_seen': '2023-01-01 00:00:00',
                    'platform': 'Tor 0.4.9.0 on Linux',
                    'version': '0.4.9.0',
                    'version_status': 'experimental',
                },
            ]
        }
        
        relays_obj = Relays(
            output_dir="/tmp/test",
            onionoo_url="http://test.url",
            relay_data=relay_data,
            use_bits=False,
            progress=False
        )
        relays_obj._calculate_network_health_metrics()
        
        health = relays_obj.json['network_health']
        
        # 0.4.9.1-alpha → ready (>= 0.4.9.1)
        # 0.4.9.4-rc-dev → ready
        # 0.4.8.22 → NOT ready
        # 0.4.9.0 → NOT ready (< 0.4.9.1)
        self.assertEqual(health['hf_ready_relays'], 2, 
                         "0.4.9.1-alpha and 0.4.9.4-rc-dev should be ready, 0.4.8.22 and 0.4.9.0 should not")
 
if __name__ == '__main__':
    unittest.main() 