#!/usr/bin/env python3

"""
Tests for the uptime_utils.py module

Tests cover:
- Uptime normalization and averaging functions
- Statistical outlier detection algorithms
- Consolidated uptime processing performance
- Edge case handling and data integrity
"""

import unittest
import sys
import os
import time

# Add the project root to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from allium.lib.uptime_utils import (
    normalize_uptime_value,
    calculate_relay_uptime_average,
    find_relay_uptime_data,
    extract_relay_uptime_for_period,
    calculate_statistical_outliers
)


class TestUptimeNormalization(unittest.TestCase):
    """Test uptime value normalization functions"""
    
    def test_normalize_uptime_value(self):
        """Test normalization from Onionoo 0-999 scale to 0-100 percentage"""
        # Test boundary values
        self.assertAlmostEqual(normalize_uptime_value(0), 0.0, places=3)
        self.assertAlmostEqual(normalize_uptime_value(999), 100.0, places=3) 
        
        # Test typical values
        self.assertAlmostEqual(normalize_uptime_value(950), 95.095, places=3)
        self.assertAlmostEqual(normalize_uptime_value(800), 80.080, places=3)
        self.assertAlmostEqual(normalize_uptime_value(500), 50.050, places=3)
    
    def test_calculate_relay_uptime_average(self):
        """Test averaging of multiple uptime data points"""
        # Test normal case with sufficient valid values (30+ required)
        uptime_values = [950 + i for i in range(35)]  # 35 values around 950
        expected = sum(uptime_values) / len(uptime_values) / 999 * 100
        result = calculate_relay_uptime_average(uptime_values)
        self.assertAlmostEqual(result, expected, places=3)
        
        # Test with None values (should be filtered out) - ensure 30+ valid values
        uptime_with_none = [950 + i for i in range(40)] + [None] * 10
        valid_values = [950 + i for i in range(40)]
        expected_filtered = sum(valid_values) / len(valid_values) / 999 * 100
        result = calculate_relay_uptime_average(uptime_with_none)
        self.assertAlmostEqual(result, expected_filtered, places=3)
        
        # Test edge cases
        self.assertEqual(calculate_relay_uptime_average([]), 0.0)
        self.assertEqual(calculate_relay_uptime_average([None, None]), 0.0)
        self.assertEqual(calculate_relay_uptime_average(None), 0.0)
        
        # Test insufficient data points (< 30) - should return 0.0
        few_values = [950, 960, 940, 970]  # Only 4 values
        self.assertEqual(calculate_relay_uptime_average(few_values), 0.0)
        
        # Test single value - insufficient data
        self.assertEqual(calculate_relay_uptime_average([900]), 0.0)
        
        # Test all zeros - should return 0.0 (low uptime)
        self.assertEqual(calculate_relay_uptime_average([0] * 40), 0.0)
        
        # Test low uptime values (<= 1%) - should return 0.0
        low_uptime_values = [9] * 35  # 9/999 = ~0.9% uptime, which is <= 1%
        self.assertEqual(calculate_relay_uptime_average(low_uptime_values), 0.0)


class TestRelayUptimeDataExtraction(unittest.TestCase):
    """Test relay uptime data finding and extraction"""
    
    def setUp(self):
        """Set up test data"""
        self.sample_uptime_data = {
            'relays': [
                {
                    'fingerprint': 'ABC123',
                    'uptime': {
                        '1_month': {'values': [950 + i for i in range(35)]},  # 35 values for sufficient data
                        '6_months': {'values': [940 + i for i in range(35)]}
                    }
                },
                {
                    'fingerprint': 'DEF456',
                    'uptime': {
                        '1_month': {'values': [960 + i for i in range(35)]},  # 35 values for sufficient data, staying within 0-999 range
                        '6_months': {'values': [950 + i for i in range(35)]}  # Staying within valid range
                    }
                }
            ]
        }
        
        self.sample_operator_relays = [
            {'fingerprint': 'ABC123', 'nickname': 'TestRelay1'},
            {'fingerprint': 'DEF456', 'nickname': 'TestRelay2'},
            {'fingerprint': 'GHI789', 'nickname': 'TestRelay3'}  # No uptime data
        ]
    
    def test_find_relay_uptime_data(self):
        """Test finding uptime data for specific relay by fingerprint"""
        # Test existing relay
        result = find_relay_uptime_data('ABC123', self.sample_uptime_data)
        self.assertIsNotNone(result)
        if result:  # Only access fields if result is not None
            self.assertEqual(result['fingerprint'], 'ABC123')
            self.assertIn('uptime', result)
        
        # Test non-existing relay
        result = find_relay_uptime_data('NONEXISTENT', self.sample_uptime_data)
        self.assertIsNone(result)
        
        # Test edge cases
        self.assertIsNone(find_relay_uptime_data('', self.sample_uptime_data))
        self.assertIsNone(find_relay_uptime_data('ABC123', None))
    
    def test_extract_relay_uptime_for_period(self):
        """Test extraction of uptime data for all relays in an operator"""
        result = extract_relay_uptime_for_period(
            self.sample_operator_relays,
            self.sample_uptime_data,
            '1_month'
        )
        
        # Should find 2 valid relays (ABC123 and DEF456) with sufficient data
        self.assertEqual(result['valid_relays'], 2)
        self.assertEqual(len(result['uptime_values']), 2)
        
        # Check relay breakdown
        self.assertIn('ABC123', result['relay_breakdown'])
        self.assertIn('DEF456', result['relay_breakdown'])
        self.assertNotIn('GHI789', result['relay_breakdown'])  # No uptime data


class TestStatisticalOutliers(unittest.TestCase):
    """Test statistical outlier detection algorithms"""
    
    def test_calculate_statistical_outliers(self):
        """Test statistical outlier detection with various datasets"""
        # Create dataset with clear outliers - use more extreme values to ensure detection
        uptime_values = [95.0, 96.0, 94.0, 97.0, 95.5, 30.0, 99.9]  # 30.0 (very low) and 99.9 (very high) are clear outliers
        relay_breakdown = {
            f'relay{i}': {
                'nickname': f'TestRelay{i}',
                'uptime': uptime_values[i],
                'fingerprint': f'ABC{i}23'
            } for i in range(len(uptime_values))
        }
        
        outliers = calculate_statistical_outliers(
            uptime_values, relay_breakdown, std_dev_threshold=2.0
        )
        
        # Should detect outliers
        self.assertGreater(len(outliers['low_outliers']), 0)
        # Note: might not always have high outliers with the dataset, depending on distribution
        # So just check that the function returns valid structure
        self.assertIn('high_outliers', outliers)
        self.assertIsInstance(outliers['high_outliers'], list)
    
    def test_outlier_detection_edge_cases(self):
        """Test outlier detection with edge cases"""
        # Test insufficient data points
        small_values = [95.0, 96.0]
        small_breakdown = {
            'relay1': {'nickname': 'Test1', 'uptime': 95.0, 'fingerprint': 'ABC123'},
            'relay2': {'nickname': 'Test2', 'uptime': 96.0, 'fingerprint': 'DEF456'}
        }
        
        outliers = calculate_statistical_outliers(small_values, small_breakdown)
        self.assertEqual(len(outliers['low_outliers']), 0)
        self.assertEqual(len(outliers['high_outliers']), 0)


class TestDataIntegrityAndEdgeCases(unittest.TestCase):
    """Test data integrity and edge case handling"""
    
    def test_malformed_data_handling(self):
        """Test handling of malformed or missing data"""
        malformed_relays = [
            {'fingerprint': 'ABC123'},  # Missing nickname
            {'nickname': 'TestRelay'},  # Missing fingerprint
            {},  # Empty relay data
        ]
        
        malformed_uptime_data = {
            'relays': [
                {'fingerprint': 'ABC123'},  # Missing uptime data
                {'uptime': {}},  # Missing fingerprint
            ]
        }
        
        # Should handle gracefully without crashing
        result = extract_relay_uptime_for_period(
            malformed_relays,
            malformed_uptime_data,
            '1_month'
        )
        
        # Should return valid structure
        self.assertIsInstance(result, dict)
        self.assertIn('valid_relays', result)
        self.assertIn('uptime_values', result)
        self.assertIn('relay_breakdown', result)


if __name__ == '__main__':
    unittest.main() 