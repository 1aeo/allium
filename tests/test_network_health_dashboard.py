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

if __name__ == '__main__':
    unittest.main() 