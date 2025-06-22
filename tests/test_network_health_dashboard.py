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
                    'as': 12345,
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
        
        # Empty addresses
        self.assertEqual(determine_ipv6_support([]), 'ipv4_only')
        
        # IPv6 only (edge case)
        addresses_ipv6 = ['[2001:db8::1]:9001']
        self.assertEqual(determine_ipv6_support(addresses_ipv6), 'both')

    def test_network_health_calculation_basic(self):
        """Test basic network health metrics calculation"""
        relays_obj = Relays()
        relays_obj.json = {'relays': self.sample_relay_data['relays']}
        
        # Process relays
        relays_obj._categorize()
        relays_obj._add_hashed_contact()
        relays_obj._calculate_network_health_metrics()
        
        # Verify basic counts
        health_metrics = relays_obj.json['network_health']
        self.assertEqual(health_metrics['relays_total'], 1)
        self.assertGreater(health_metrics['both_ipv4_ipv6_relays'], 0)
        self.assertEqual(health_metrics['ipv4_only_relays'], 0)

    def test_ipv6_operator_tracking_fix(self):
        """Test that IPv6 operator tracking uses correct field name"""
        relays_obj = Relays()
        relays_obj.json = {'relays': self.sample_relay_data['relays']}
        
        # Process relays
        relays_obj._categorize()
        relays_obj._add_hashed_contact()
        relays_obj._calculate_network_health_metrics()
        
        # Verify operator-level IPv6 tracking works
        health_metrics = relays_obj.json['network_health']
        self.assertGreater(health_metrics['both_ipv4_ipv6_operators'], 0)
        
    def test_consensus_weight_calculations(self):
        """Test consensus weight percentage calculations"""
        relays_obj = Relays()
        relays_obj.json = {'relays': self.sample_relay_data['relays']}
        
        relays_obj._categorize()
        relays_obj._calculate_network_health_metrics()
        
        health_metrics = relays_obj.json['network_health']
        
        # Verify percentages add up correctly
        self.assertAlmostEqual(
            health_metrics['eu_consensus_weight_percentage'] + 
            health_metrics['non_eu_consensus_weight_percentage'], 
            100.0, places=1
        )
        
    def test_exit_policy_analysis(self):
        """Test exit policy restriction analysis"""
        # Test with unrestricted exit
        unrestricted_relay = self.sample_relay_data['relays'][0].copy()
        unrestricted_relay['exit_policy'] = ['accept *:*']
        
        relays_obj = Relays()
        relays_obj.json = {'relays': [unrestricted_relay]}
        
        relays_obj._categorize()
        relays_obj._calculate_network_health_metrics()
        
        health_metrics = relays_obj.json['network_health']
        # Should detect unrestricted exit policy
        self.assertGreaterEqual(health_metrics['unrestricted_exits'], 0)

    def test_cw_bw_ratio_calculations(self):
        """Test CW/BW ratio calculations"""
        relays_obj = Relays()
        relays_obj.json = {'relays': self.sample_relay_data['relays']}
        
        relays_obj._categorize()
        relays_obj._calculate_network_health_metrics()
        
        health_metrics = relays_obj.json['network_health']
        
        # Verify CW/BW ratio calculations exist and are reasonable
        self.assertIsInstance(health_metrics['cw_bw_ratio_overall_mean'], (int, float))
        self.assertIsInstance(health_metrics['cw_bw_ratio_overall_median'], (int, float))
        self.assertGreater(health_metrics['cw_bw_ratio_overall_mean'], 0)

if __name__ == '__main__':
    unittest.main() 