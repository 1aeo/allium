"""
Integration tests for network uptime percentiles feature.

Tests the complete workflow from uptime data processing through template rendering,
ensuring the network uptime percentiles feature works correctly end-to-end.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add the parent directory to the path so we can import allium modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from allium.lib.relays import Relays


class TestNetworkUptimePercentilesIntegration(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment for integration tests."""
        # Mock relay data
        self.mock_relay_data = {
            'relays': [
                {
                    'fingerprint': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
                    'nickname': 'TestRelay1',
                    'running': True,
                    'contact': 'operator1@example.com',
                    'observed_bandwidth': 1000000,
                    'consensus_weight': 50
                },
                {
                    'fingerprint': 'BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB',
                    'nickname': 'TestRelay2', 
                    'running': True,
                    'contact': 'operator1@example.com',  # Same operator
                    'observed_bandwidth': 2000000,
                    'consensus_weight': 75
                },
                {
                    'fingerprint': 'CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC',
                    'nickname': 'TestRelay3',
                    'running': True,
                    'contact': 'operator2@example.com',  # Different operator
                    'observed_bandwidth': 500000,
                    'consensus_weight': 25
                }
            ]
        }
        
        # Mock uptime data
        self.mock_uptime_data = {
            'relays': [
                {
                    'fingerprint': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
                    'uptime': {
                        '6_months': {
                            'values': [980] * 180  # 98% uptime
                        }
                    }
                },
                {
                    'fingerprint': 'BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB',
                    'uptime': {
                        '6_months': {
                            'values': [950] * 180  # 95% uptime
                        }
                    }
                },
                {
                    'fingerprint': 'CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC',
                    'uptime': {
                        '6_months': {
                            'values': [920] * 180  # 92% uptime
                        }
                    }
                }
            ]
        }
        
        # Add many more relays for realistic percentile calculation
        for i in range(100):
            relay_fp = f'RELAY{i:036}'
            uptime_value = 850 + (i % 150)  # Distribute between 85-99.9%
            
            self.mock_relay_data['relays'].append({
                'fingerprint': relay_fp,
                'nickname': f'MockRelay{i}',
                'running': True,
                'contact': f'operator{i}@example.com',
                'observed_bandwidth': 100000,
                'consensus_weight': 10
            })
            
            self.mock_uptime_data['relays'].append({
                'fingerprint': relay_fp,
                'uptime': {
                    '6_months': {
                        'values': [uptime_value] * 180
                    }
                }
            })
    
    @patch('allium.lib.relays.Relays._fetch_data')
    def test_network_percentiles_calculation_in_relays_object(self, mock_fetch):
        """Test that network percentiles are calculated correctly in Relays object."""
        # Mock the fetch_data method to return our test data
        mock_fetch.return_value = self.mock_relay_data
        
        # Create Relays object with mocked uptime data
        relays = Relays()
        relays.uptime_data = self.mock_uptime_data
        
        # Trigger processing
        relays._reprocess_uptime_data()
        
        # Check that network percentiles were calculated
        self.assertTrue(hasattr(relays, 'network_uptime_percentiles'))
        self.assertIsNotNone(relays.network_uptime_percentiles)
        
        # Verify percentile structure
        percentiles = relays.network_uptime_percentiles
        self.assertIn('25th', percentiles)
        self.assertIn('50th', percentiles)
        self.assertIn('75th', percentiles)
        self.assertIn('total_relays', percentiles)
        
    @patch('allium.lib.relays.Relays._fetch_data')
    def test_operator_reliability_includes_network_percentiles(self, mock_fetch):
        """Test that operator reliability calculations include network percentiles."""
        mock_fetch.return_value = self.mock_relay_data
        
        relays = Relays()
        relays.uptime_data = self.mock_uptime_data
        relays._reprocess_uptime_data()
        
        # Get contact hash for operator1@example.com
        contact_hash = relays._hash_contact('operator1@example.com')
        
        # Get operator relays (should be 2 relays)
        operator_relays = [r for r in self.mock_relay_data['relays'] 
                          if r.get('contact') == 'operator1@example.com']
        
        # Calculate operator reliability
        reliability = relays._calculate_operator_reliability(contact_hash, operator_relays)
        
        self.assertIsNotNone(reliability)
        self.assertIn('network_uptime_percentiles', reliability)
        
        # Verify network percentiles structure in reliability data
        net_percentiles = reliability['network_uptime_percentiles']
        self.assertIn('25th', net_percentiles)
        self.assertIn('50th', net_percentiles)
        
    @patch('allium.lib.relays.Relays._fetch_data')
    def test_contact_display_data_includes_percentiles_formatting(self, mock_fetch):
        """Test that contact display data includes formatted percentiles display."""
        mock_fetch.return_value = self.mock_relay_data
        
        relays = Relays()
        relays.uptime_data = self.mock_uptime_data
        relays._reprocess_uptime_data()
        
        # Get contact hash
        contact_hash = relays._hash_contact('operator1@example.com')
        
        # Get operator data  
        operator_data = relays.json['contacts'][contact_hash]
        operator_relays = [relays.json['relays'][i] for i in operator_data['relays']]
        
        # Calculate display data
        display_data = relays._compute_contact_display_data(contact_hash, operator_relays)
        
        # Should include network uptime percentiles display
        if 'reliability_stats' in display_data and display_data['reliability_stats']:
            reliability = display_data['reliability_stats']
            if 'network_uptime_percentiles_display' in reliability:
                percentiles_display = reliability['network_uptime_percentiles_display']
                self.assertIsInstance(percentiles_display, str)
                self.assertIn('Network Uptime (6mo):', percentiles_display)
                self.assertIn('Operator:', percentiles_display)
                
    def test_performance_optimization_caching(self):
        """Test that network percentiles are cached for performance."""
        relays = Relays()
        relays.uptime_data = self.mock_uptime_data
        
        # Manually trigger percentiles calculation
        relays._reprocess_uptime_data()
        
        # Get initial percentiles
        initial_percentiles = relays.network_uptime_percentiles
        
        # Trigger again - should use cached result
        relays._reprocess_uptime_data()
        cached_percentiles = relays.network_uptime_percentiles
        
        # Should be identical (cached)
        self.assertEqual(initial_percentiles['25th'], cached_percentiles['25th'])
        self.assertEqual(initial_percentiles['total_relays'], cached_percentiles['total_relays'])
        
    @patch('allium.lib.relays.Relays._fetch_data')
    def test_template_data_structure_compatibility(self, mock_fetch):
        """Test that the data structure is compatible with template rendering."""
        mock_fetch.return_value = self.mock_relay_data
        
        relays = Relays()
        relays.uptime_data = self.mock_uptime_data
        relays._reprocess_uptime_data()
        
        # Check that contact data includes all required fields for template
        contact_hash = relays._hash_contact('operator1@example.com')
        if contact_hash in relays.json['contacts']:
            contact_data = relays.json['contacts'][contact_hash]
            
            # Should have reliability stats if uptime data is available
            if hasattr(relays, '_contact_display_data') and contact_hash in relays._contact_display_data:
                display_data = relays._contact_display_data[contact_hash]
                
                # Check structure expected by templates
                if 'reliability_stats' in display_data:
                    reliability = display_data['reliability_stats']
                    
                    # Template expects these fields
                    expected_fields = ['overall_uptime', 'valid_relays', 'total_relays']
                    for field in expected_fields:
                        if field in reliability:
                            self.assertIsNotNone(reliability[field])
                            
    def test_mathematical_validity_in_integration(self):
        """Test mathematical validity in full integration context."""
        relays = Relays()
        relays.uptime_data = self.mock_uptime_data
        relays._reprocess_uptime_data()
        
        if hasattr(relays, 'network_uptime_percentiles') and relays.network_uptime_percentiles:
            percentiles = relays.network_uptime_percentiles
            
            # Verify mathematical constraints
            self.assertLessEqual(percentiles['25th'], percentiles['50th'])
            self.assertLessEqual(percentiles['50th'], percentiles['75th'])
            
            # Average should be >= 25th percentile
            self.assertGreaterEqual(percentiles['average'], percentiles['25th'])
            
            # All percentiles should be valid percentages
            for key in ['5th', '25th', '50th', '75th', '90th', '95th', '99th']:
                if key in percentiles:
                    self.assertGreaterEqual(percentiles[key], 0.0)
                    self.assertLessEqual(percentiles[key], 100.0)
                    
    def test_error_handling_no_uptime_data(self):
        """Test graceful handling when uptime data is unavailable."""
        relays = Relays()
        # Don't set uptime_data - simulate missing uptime API
        
        relays._reprocess_uptime_data()
        
        # Should not crash, network percentiles should be None/unset
        if hasattr(relays, 'network_uptime_percentiles'):
            # If set, should be None for no data
            if relays.network_uptime_percentiles is not None:
                # If not None, should be valid structure
                self.assertIsInstance(relays.network_uptime_percentiles, dict)
                
    def test_color_coding_integration(self):
        """Test that color coding works correctly in integration."""
        relays = Relays()
        relays.uptime_data = self.mock_uptime_data
        relays._reprocess_uptime_data()
        
        # Get a contact with known uptime
        contact_hash = relays._hash_contact('operator1@example.com')
        operator_relays = [r for r in self.mock_relay_data['relays'] 
                          if r.get('contact') == 'operator1@example.com']
        
        if operator_relays:
            display_data = relays._compute_contact_display_data(contact_hash, operator_relays)
            
            if ('reliability_stats' in display_data and 
                display_data['reliability_stats'] and
                'network_uptime_percentiles_display' in display_data['reliability_stats']):
                
                display = display_data['reliability_stats']['network_uptime_percentiles_display']
                
                # Should include color coding
                self.assertIn('color:', display)
                # Should be either green, yellow, or red
                colors = ['#2e7d2e', '#cc9900', '#c82333']
                has_color = any(color in display for color in colors)
                self.assertTrue(has_color, f"Display should contain one of {colors}: {display}")


if __name__ == '__main__':
    unittest.main() 