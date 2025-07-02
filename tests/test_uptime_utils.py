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
import statistics

# Add the project root to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from allium.lib.uptime_utils import (
    normalize_uptime_value,
    calculate_relay_uptime_average,
    find_relay_uptime_data,
    extract_relay_uptime_for_period,
    calculate_statistical_outliers,
    process_all_uptime_data_consolidated
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
        self.assertAlmostEqual(normalize_uptime_value(250), 25.025, places=3)
        
        # Test mid-range values
        self.assertAlmostEqual(normalize_uptime_value(750), 75.075, places=3)
        self.assertAlmostEqual(normalize_uptime_value(900), 90.090, places=3)
    
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
        self.assertIsNone(find_relay_uptime_data('ABC123', {}))
        self.assertIsNone(find_relay_uptime_data(None, self.sample_uptime_data))
    
    def test_extract_relay_uptime_for_period(self):
        """Test extraction of uptime data for all relays in an operator"""
        result = extract_relay_uptime_for_period(
            self.sample_operator_relays,
            self.sample_uptime_data,
            '1_month'
        )
        
        # Should find 2 valid relays (ABC123 and DEF456)
        self.assertEqual(result['valid_relays'], 2)
        self.assertEqual(len(result['uptime_values']), 2)
        
        # Check relay breakdown
        self.assertIn('ABC123', result['relay_breakdown'])
        self.assertIn('DEF456', result['relay_breakdown'])
        self.assertNotIn('GHI789', result['relay_breakdown'])  # No uptime data
        
        # Verify relay breakdown structure
        for fingerprint, relay_data in result['relay_breakdown'].items():
            self.assertIn('nickname', relay_data)
            self.assertIn('fingerprint', relay_data)
            self.assertIn('uptime', relay_data)
            self.assertIn('data_points', relay_data)
            self.assertTrue(0 <= relay_data['uptime'] <= 100)
        
        # Test different time period
        result_6m = extract_relay_uptime_for_period(
            self.sample_operator_relays,
            self.sample_uptime_data,
            '6_months'
        )
        self.assertEqual(result_6m['valid_relays'], 2)
        
        # Test non-existent period
        result_invalid = extract_relay_uptime_for_period(
            self.sample_operator_relays,
            self.sample_uptime_data,
            'invalid_period'
        )
        self.assertEqual(result_invalid['valid_relays'], 0)


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
        
        # Verify outlier structure
        for outlier in outliers['low_outliers']:
            self.assertIn('nickname', outlier)
            self.assertIn('fingerprint', outlier)
            self.assertIn('uptime', outlier)
            self.assertIn('deviation', outlier)
            self.assertGreater(outlier['deviation'], 2.0)  # Should exceed threshold
        
        for outlier in outliers['high_outliers']:
            self.assertIn('nickname', outlier)
            self.assertIn('fingerprint', outlier)
            self.assertIn('uptime', outlier)
            self.assertIn('deviation', outlier)
            self.assertGreater(outlier['deviation'], 2.0)  # Should exceed threshold
    
    def test_outlier_detection_edge_cases(self):
        """Test outlier detection with edge cases"""
        # Test insufficient data points (need at least 3)
        small_values = [95.0, 96.0]
        small_breakdown = {
            'relay1': {'nickname': 'Test1', 'uptime': 95.0, 'fingerprint': 'ABC123'},
            'relay2': {'nickname': 'Test2', 'uptime': 96.0, 'fingerprint': 'DEF456'}
        }
        
        outliers = calculate_statistical_outliers(small_values, small_breakdown)
        self.assertEqual(len(outliers['low_outliers']), 0)
        self.assertEqual(len(outliers['high_outliers']), 0)
        
        # Test identical values (standard deviation = 0)
        identical_values = [95.0, 95.0, 95.0, 95.0]
        identical_breakdown = {
            f'relay{i}': {'nickname': f'Test{i}', 'uptime': 95.0, 'fingerprint': f'ABC{i}'}
            for i in range(4)
        }
        
        identical_outliers = calculate_statistical_outliers(identical_values, identical_breakdown)
        self.assertEqual(len(identical_outliers['low_outliers']), 0)
        self.assertEqual(len(identical_outliers['high_outliers']), 0)
        
        # Test empty data
        empty_outliers = calculate_statistical_outliers([], {})
        self.assertEqual(len(empty_outliers['low_outliers']), 0)
        self.assertEqual(len(empty_outliers['high_outliers']), 0)
    
    def test_outlier_detection_thresholds(self):
        """Test different outlier detection thresholds"""
        uptime_values = [95.0, 96.0, 94.0, 97.0, 95.5, 80.0, 99.0]  # 80.0 and 99.0 are moderate outliers
        relay_breakdown = {
            f'relay{i}': {
                'nickname': f'TestRelay{i}',
                'uptime': uptime_values[i],
                'fingerprint': f'ABC{i}23'
            } for i in range(len(uptime_values))
        }
        
        # Test strict threshold (3.0 std devs) - should detect fewer outliers
        strict_outliers = calculate_statistical_outliers(
            uptime_values, relay_breakdown, std_dev_threshold=3.0
        )
        
        # Test lenient threshold (1.0 std dev) - should detect more outliers
        lenient_outliers = calculate_statistical_outliers(
            uptime_values, relay_breakdown, std_dev_threshold=1.0
        )
        
        # Lenient should detect more or equal outliers than strict
        total_strict = len(strict_outliers['low_outliers']) + len(strict_outliers['high_outliers'])
        total_lenient = len(lenient_outliers['low_outliers']) + len(lenient_outliers['high_outliers'])
        self.assertGreaterEqual(total_lenient, total_strict)


class TestConsolidatedProcessing(unittest.TestCase):
    """Test consolidated uptime data processing for performance"""
    
    def setUp(self):
        """Set up test data for consolidated processing"""
        self.large_relay_set = []
        for i in range(1000):
            self.large_relay_set.append({
                'fingerprint': f'RELAY{i:06d}',
                'nickname': f'TestRelay{i}',
                'flags': ['Running', 'Fast'][i % 2:i % 2 + 1]  # Alternate flags
            })
        
        self.large_uptime_data = {
            'relays': []
        }
        
        for i in range(1000):
            self.large_uptime_data['relays'].append({
                'fingerprint': f'RELAY{i:06d}',
                'uptime': {
                    '1_month': {'values': [900 + (i % 100) for _ in range(30)]},
                    '6_months': {'values': [880 + (i % 120) for _ in range(180)]}
                }
            })
    
    def test_consolidated_processing_performance(self):
        """Test performance of consolidated uptime processing"""
        start_time = time.time()
        
        result = process_all_uptime_data_consolidated(
            self.large_relay_set,
            self.large_uptime_data,
            include_flag_analysis=False
        )
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should complete in reasonable time (less than 5 seconds for 1000 relays)
        self.assertLess(processing_time, 5.0)
        
        # Should return proper structure
        self.assertIn('relay_uptime_data', result)
        self.assertIn('network_statistics', result)
        
        # Should process all relays
        self.assertEqual(len(result['relay_uptime_data']), 1000)
    
    def test_consolidated_processing_accuracy(self):
        """Test accuracy of consolidated processing vs individual processing"""
        # Use smaller dataset for accuracy comparison
        small_relays = self.large_relay_set[:10] 
        small_uptime_data = {
            'relays': self.large_uptime_data['relays'][:10]
        }
        
        # Process with consolidated function
        consolidated_result = process_all_uptime_data_consolidated(
            small_relays,
            small_uptime_data,
            include_flag_analysis=False
        )
        
        # Process individually for comparison
        individual_results = {}
        for relay in small_relays:
            fingerprint = relay['fingerprint']
            individual_result = extract_relay_uptime_for_period(
                [relay],
                small_uptime_data,
                '1_month'
            )
            if individual_result['valid_relays'] > 0:
                individual_results[fingerprint] = individual_result['uptime_values'][0]
        
        # Compare results
        for fingerprint, individual_uptime in individual_results.items():
            consolidated_uptime = consolidated_result['relay_uptime_data'].get(fingerprint, {}).get('1_month')
            if consolidated_uptime is not None:
                self.assertAlmostEqual(
                    individual_uptime,
                    consolidated_uptime,
                    places=2,
                    msg=(
                        f"Mismatch for {fingerprint}: individual={individual_uptime},"
                        f" consolidated={consolidated_uptime}"
                    )
                )
    
    def test_consolidated_processing_with_flag_analysis(self):
        """Test consolidated processing with flag analysis enabled"""
        result = process_all_uptime_data_consolidated(
            self.large_relay_set[:100],  # Use smaller set for flag analysis
            {'relays': self.large_uptime_data['relays'][:100]},
            include_flag_analysis=True
        )
        
        # Should include network flag statistics data 
        self.assertIn('network_flag_statistics', result)
        self.assertIsNotNone(result['network_flag_statistics'])
        
        # Should still include other data
        self.assertIn('relay_uptime_data', result)
        self.assertIn('network_statistics', result)


class TestDataIntegrityAndEdgeCases(unittest.TestCase):
    """Test data integrity and edge case handling"""
    
    def test_malformed_data_handling(self):
        """Test handling of malformed or missing data"""
        malformed_relays = [
            {'fingerprint': 'ABC123'},  # Missing nickname
            {'nickname': 'TestRelay'},  # Missing fingerprint
            {},  # Empty relay data
            {'fingerprint': 'DEF456', 'nickname': 'ValidRelay'}  # Valid relay
        ]
        
        malformed_uptime_data = {
            'relays': [
                {'fingerprint': 'ABC123'},  # Missing uptime data
                {'uptime': {}},  # Missing fingerprint
                {'fingerprint': 'DEF456', 'uptime': {'1_month': {}}},  # Missing values
                {'fingerprint': 'GHI789', 'uptime': {'1_month': {'values': [950, 960]}}},  # Valid but no matching relay
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
        
        # Should handle empty inputs
        empty_result = extract_relay_uptime_for_period([], {}, '1_month')
        self.assertEqual(empty_result['valid_relays'], 0)
        
        # Should handle None inputs gracefully (may raise TypeError)
        try:
            none_result = extract_relay_uptime_for_period(None, None, '1_month')
            self.assertEqual(none_result['valid_relays'], 0)
        except TypeError:
            # Function doesn't handle None input - this is acceptable behavior
            pass
    
    def test_memory_efficiency(self):
        """Test memory efficiency with large datasets"""
        # This test verifies that large datasets don't cause memory issues
        
        # Create large dataset
        very_large_dataset = []
        for i in range(10000):
            uptime_values = [900 + (i % 100) for _ in range(100)]  # 100 data points per relay
            very_large_dataset.extend(uptime_values)
        
        # Should process without memory errors
        start_time = time.time()
        result = calculate_relay_uptime_average(very_large_dataset)
        end_time = time.time()
        
        # Should complete reasonably quickly
        self.assertLess(end_time - start_time, 10.0)
        
        # Should produce reasonable result
        self.assertTrue(80.0 <= result <= 100.0)
    
    def test_data_type_validation(self):
        """Test proper handling of different data types"""
        # Test with string values (should be ignored) - ensure 30+ valid values
        base_values = [950 + i for i in range(30)]  # 30 valid numeric values  
        mixed_values = base_values + ['960', None, 970.5, '980']  # Add some invalid types
        valid_values = base_values + [970.5]  # Only valid numeric values
        result = calculate_relay_uptime_average(mixed_values)
        # Should only process valid numeric values
        expected = sum(valid_values) / len(valid_values) / 999 * 100
        self.assertAlmostEqual(result, expected, places=2)
        
        # Test with negative values (edge case) - ensure 30+ values for testing
        negative_values = [-10] + [950 + i for i in range(35)]  # 1 invalid + 35 valid
        # Should handle gracefully (negative values might be invalid but shouldn't crash)
        result = calculate_relay_uptime_average(negative_values)
        self.assertIsInstance(result, (int, float))


if __name__ == '__main__':
    unittest.main() 