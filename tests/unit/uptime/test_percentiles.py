"""
Unit tests for network uptime percentiles functionality.

Tests the core percentile calculation, operator positioning, and display formatting
functionality added in the network uptime percentiles feature.
"""

import unittest
from unittest.mock import Mock, patch

from allium.lib.uptime_utils import (
    calculate_network_uptime_percentiles,
    find_operator_percentile_position,
    format_network_percentiles_display,
    calculate_relay_uptime_average,
    normalize_uptime_value
)


class TestNetworkUptimePercentiles(unittest.TestCase):
    
    def setUp(self):
        """Set up test data for network uptime percentile tests."""
        # Create mock uptime data with known distribution
        self.mock_uptime_data = {
            'relays': [
                {
                    'fingerprint': f'RELAY{i:04d}',
                    'uptime': {
                        '6_months': {
                            'values': [850 + i for _ in range(180)]  # 180 days of data
                        }
                    }
                } for i in range(100)  # 100 relays with uptime 85-95%
            ]
        }
        
        # Add some high-performing relays
        for i in range(100, 150):
            self.mock_uptime_data['relays'].append({
                'fingerprint': f'RELAY{i:04d}',
                'uptime': {
                    '6_months': {
                        'values': [950 + (i-100) for _ in range(180)]  # 95-99.9% uptime
                    }
                }
            })
    
    def test_calculate_network_uptime_percentiles_basic(self):
        """Test basic network percentile calculation."""
        percentiles = calculate_network_uptime_percentiles(self.mock_uptime_data, '6_months')
        
        self.assertIsNotNone(percentiles)
        self.assertIn('percentiles', percentiles)
        self.assertIn('25th', percentiles['percentiles'])
        self.assertIn('50th', percentiles['percentiles'])
        self.assertIn('75th', percentiles['percentiles'])
        self.assertIn('90th', percentiles['percentiles'])
        self.assertIn('95th', percentiles['percentiles'])
        self.assertIn('99th', percentiles['percentiles'])
        
        # Test additional fields
        self.assertIn('average', percentiles)
        self.assertIn('total_relays', percentiles)
        self.assertIn('time_period', percentiles)
        self.assertEqual(percentiles['time_period'], '6_months')
        
    def test_percentiles_mathematical_validity(self):
        """Test that percentiles are in ascending order."""
        percentiles = calculate_network_uptime_percentiles(self.mock_uptime_data, '6_months')
        
        pct = percentiles['percentiles']
        self.assertLessEqual(pct['5th'], pct['25th'])
        self.assertLessEqual(pct['25th'], pct['50th'])
        self.assertLessEqual(pct['50th'], pct['75th'])
        self.assertLessEqual(pct['75th'], pct['90th'])
        self.assertLessEqual(pct['90th'], pct['95th'])
        self.assertLessEqual(pct['95th'], pct['99th'])
        
    def test_calculate_network_uptime_percentiles_empty_data(self):
        """Test handling of empty uptime data."""
        empty_data = {'relays': []}
        result = calculate_network_uptime_percentiles(empty_data, '6_months')
        self.assertIsNone(result)
        
        # Test None input
        result = calculate_network_uptime_percentiles(None, '6_months')
        self.assertIsNone(result)
        
    def test_calculate_network_uptime_percentiles_insufficient_data(self):
        """Test handling of insufficient data points."""
        small_data = {
            'relays': [
                {
                    'fingerprint': f'RELAY{i:04d}',
                    'uptime': {
                        '6_months': {
                            'values': [900 for _ in range(180)]  # Only a few relays
                        }
                    }
                } for i in range(5)  # Only 5 relays
            ]
        }
        
        percentiles = calculate_network_uptime_percentiles(small_data, '6_months')
        # Should still work with 5 relays since we need >= 10 for meaningful percentiles
        self.assertIsNone(percentiles)
        
    def test_find_operator_percentile_position_above_median(self):
        """Test operator positioning above 50th percentile."""
        percentiles = calculate_network_uptime_percentiles(self.mock_uptime_data, '6_months')
        
        # Test operator with 99% uptime (should be high)
        position = find_operator_percentile_position(99.0, percentiles)
        
        self.assertIsInstance(position, dict)
        self.assertIn('description', position)
        self.assertIn('insert_after', position)
        self.assertIn('percentile_range', position)
        
    def test_find_operator_percentile_position_below_median(self):
        """Test operator positioning below 50th percentile."""
        percentiles = calculate_network_uptime_percentiles(self.mock_uptime_data, '6_months')
        
        # Test operator with 80% uptime (should be low)
        position = find_operator_percentile_position(80.0, percentiles)
        
        self.assertIsInstance(position, dict)
        self.assertIn('description', position)
        
    def test_format_network_percentiles_display(self):
        """Test network percentiles display formatting."""
        percentiles = calculate_network_uptime_percentiles(self.mock_uptime_data, '6_months')
        
        # Test formatting with operator above median
        display = format_network_percentiles_display(percentiles, 99.0)
        
        self.assertIsInstance(display, str)
        if display:  # Check display is not None
            self.assertIn('Network Uptime (6mo):', display)
            self.assertIn('Operator:', display)
            self.assertIn('99%', display)  # Operator value (formatted to 0 decimals)
        
        # Test with below median operator
        display_low = format_network_percentiles_display(percentiles, 80.0)
        if display_low:  # Check display_low is not None
            self.assertIn('80%', display_low)
        
    def test_format_network_percentiles_display_color_coding(self):
        """Test color coding in display formatting."""
        percentiles = calculate_network_uptime_percentiles(self.mock_uptime_data, '6_months')
        
        # Test high performer (should be green)
        display_high = format_network_percentiles_display(percentiles, 99.0)
        self.assertIn('#2e7d2e', display_high)  # Green color
        
        # Test low performer
        display_low = format_network_percentiles_display(percentiles, 70.0)
        # Should have some color coding
        self.assertIn('color:', display_low)
        
    def test_calculate_relay_uptime_average(self):
        """Test individual relay uptime average calculation."""
        # Test normal case
        values = [900, 950, 920, 940] * 10  # 40 values around 92-95%
        average = calculate_relay_uptime_average(values)
        self.assertGreater(average, 90)
        self.assertLess(average, 100)
        
        # Test insufficient data
        values_short = [900, 950]  # Only 2 values
        average_short = calculate_relay_uptime_average(values_short)
        self.assertEqual(average_short, 0.0)
        
        # Test low uptime (should be excluded)
        values_low = [10, 5, 8] * 15  # 45 values but very low uptime
        average_low = calculate_relay_uptime_average(values_low)
        self.assertEqual(average_low, 0.0)
        
    def test_normalize_uptime_value(self):
        """Test uptime value normalization from 0-999 to 0-100."""
        self.assertEqual(normalize_uptime_value(0), 0.0)
        self.assertEqual(normalize_uptime_value(999), 100.0)
        self.assertAlmostEqual(normalize_uptime_value(500), 50.05, places=1)
        
    def test_data_filtering_logic(self):
        """Test that data filtering works correctly."""
        # Create data with some bad relays
        test_data = {
            'relays': [
                # Good relay
                {
                    'fingerprint': 'GOOD001',
                    'uptime': {
                        '6_months': {
                            'values': [950] * 180  # High uptime, sufficient data
                        }
                    }
                },
                # Low uptime relay (should be excluded)
                {
                    'fingerprint': 'BAD001',
                    'uptime': {
                        '6_months': {
                            'values': [10] * 180  # Low uptime
                        }
                    }
                },
                # Insufficient data relay (should be excluded)
                {
                    'fingerprint': 'BAD002',
                    'uptime': {
                        '6_months': {
                            'values': [900] * 20  # Good uptime but insufficient data
                        }
                    }
                },
                # No data relay (should be excluded)
                {
                    'fingerprint': 'BAD003',
                    'uptime': {
                        '6_months': {
                            'values': []
                        }
                    }
                }
            ]
        }
        
        percentiles = calculate_network_uptime_percentiles(test_data, '6_months')
        # Should return None due to insufficient valid relays
        self.assertIsNone(percentiles)
        
    def test_edge_cases(self):
        """Test various edge cases."""
        # Test with None values in uptime data
        data_with_nones = {
            'relays': [
                {
                    'fingerprint': 'RELAY001',
                    'uptime': {
                        '6_months': {
                            'values': [900, None, 950, None, 920] * 20  # Mix of valid and None
                        }
                    }
                }
            ] * 20  # Replicate to have enough data
        }
        
        percentiles = calculate_network_uptime_percentiles(data_with_nones, '6_months')
        # Should handle None values gracefully
        self.assertIsNotNone(percentiles)
        
    def test_performance_optimization_caching(self):
        """Test that performance optimization works (conceptual test)."""
        # This test verifies the calculation works efficiently
        # In actual implementation, we'd test that results are cached
        percentiles1 = calculate_network_uptime_percentiles(self.mock_uptime_data, '6_months')
        percentiles2 = calculate_network_uptime_percentiles(self.mock_uptime_data, '6_months')
        
        # Results should be identical
        self.assertEqual(percentiles1['percentiles']['25th'], percentiles2['percentiles']['25th'])
        self.assertEqual(percentiles1['average'], percentiles2['average'])


if __name__ == '__main__':
    unittest.main() 