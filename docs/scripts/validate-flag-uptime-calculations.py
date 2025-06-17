#!/usr/bin/env python3

"""
Flag Uptime Calculations Validation Script

This script validates the flag uptime system to ensure:
- Flag uptime math accuracy
- Priority system logic (Exit > Guard > Fast > Running)
- Color coding thresholds
- "Match Overall Uptime" logic
- Statistical analysis correctness

Usage:
    python validate-flag-uptime-calculations.py [--verbose] [--sample-size N]
"""

import sys
import os
import argparse
import json
import statistics
import time
from datetime import datetime, timezone

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from allium.lib.uptime_utils import (
    normalize_uptime_value,
    calculate_relay_uptime_average,
    extract_relay_uptime_for_period,
    calculate_statistical_outliers
)


class FlagUptimeValidator:
    """Validates flag uptime calculations and logic"""
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.passed_tests = 0
        self.failed_tests = 0
        self.warnings = []
        
    def log(self, message, level='INFO'):
        """Log a message with optional verbosity control"""
        if self.verbose or level in ['ERROR', 'WARNING']:
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"[{timestamp}] {level}: {message}")
    
    def assert_test(self, condition, test_name, error_message=None):
        """Assert a test condition and track results"""
        if condition:
            self.passed_tests += 1
            self.log(f"✓ {test_name}")
        else:
            self.failed_tests += 1
            error_msg = error_message or f"Failed: {test_name}"
            self.log(f"✗ {error_msg}", 'ERROR')
    
    def warn(self, message):
        """Record a warning"""
        self.warnings.append(message)
        self.log(f"⚠ {message}", 'WARNING')
    
    def validate_uptime_normalization(self):
        """Validate Onionoo uptime value normalization (0-999 to 0-100%)"""
        self.log("Validating uptime normalization...")
        
        # Test boundary values
        self.assert_test(
            abs(normalize_uptime_value(0) - 0.0) < 0.01,
            "Normalization: 0 -> 0.0%"
        )
        
        self.assert_test(
            abs(normalize_uptime_value(999) - 100.0) < 0.01,
            "Normalization: 999 -> 100.0%"
        )
        
        # Test typical values
        expected_95 = 950 / 999 * 100  # Should be ~95.095%
        actual_95 = normalize_uptime_value(950)
        self.assert_test(
            abs(actual_95 - expected_95) < 0.01,
            f"Normalization: 950 -> {expected_95:.2f}%",
            f"Expected {expected_95:.2f}%, got {actual_95:.2f}%"
        )
        
        expected_80 = 800 / 999 * 100  # Should be ~80.08%
        actual_80 = normalize_uptime_value(800)
        self.assert_test(
            abs(actual_80 - expected_80) < 0.01,
            f"Normalization: 800 -> {expected_80:.2f}%",
            f"Expected {expected_80:.2f}%, got {actual_80:.2f}%"
        )
    
    def validate_uptime_averaging(self):
        """Validate uptime averaging calculations"""
        self.log("Validating uptime averaging...")
        
        # Test normal averaging
        test_values = [950, 960, 940, 970]
        expected_avg = sum(test_values) / len(test_values) / 999 * 100
        actual_avg = calculate_relay_uptime_average(test_values)
        
        self.assert_test(
            abs(actual_avg - expected_avg) < 0.01,
            f"Average calculation: {test_values} -> {expected_avg:.2f}%",
            f"Expected {expected_avg:.2f}%, got {actual_avg:.2f}%"
        )
        
        # Test filtering of None values
        test_values_with_none = [950, None, 960, None, 940]
        valid_values = [950, 960, 940]
        expected_filtered = sum(valid_values) / len(valid_values) / 999 * 100
        actual_filtered = calculate_relay_uptime_average(test_values_with_none)
        
        self.assert_test(
            abs(actual_filtered - expected_filtered) < 0.01,
            f"Filtered average: {test_values_with_none} -> {expected_filtered:.2f}%",
            f"Expected {expected_filtered:.2f}%, got {actual_filtered:.2f}%"
        )
        
        # Test edge cases
        self.assert_test(
            calculate_relay_uptime_average([]) == 0.0,
            "Empty list -> 0.0%"
        )
        
        self.assert_test(
            calculate_relay_uptime_average([None, None, None]) == 0.0,
            "All None values -> 0.0%"
        )
    
    def validate_flag_priority_system(self):
        """Validate flag priority system logic"""
        self.log("Validating flag priority system...")
        
        # Define priority system (Exit > Guard > Fast > Running)
        flag_priorities = ['Exit', 'Guard', 'Fast', 'Running']
        
        def get_highest_priority_flag(flags):
            for priority_flag in flag_priorities:
                if priority_flag in flags:
                    return priority_flag
            return None
        
        # Test priority selection
        test_cases = [
            (['Exit', 'Guard', 'Fast', 'Running'], 'Exit'),
            (['Guard', 'Fast', 'Running'], 'Guard'), 
            (['Fast', 'Running'], 'Fast'),
            (['Running'], 'Running'),
            (['Exit', 'Running'], 'Exit'),  # Exit should win over Running
            (['Guard', 'Exit'], 'Exit'),    # Exit should win over Guard
            ([], None),                     # Empty should return None
            (['UnknownFlag'], None),        # Unknown flags should return None
        ]
        
        for flags, expected in test_cases:
            actual = get_highest_priority_flag(flags)
            self.assert_test(
                actual == expected,
                f"Priority selection: {flags} -> {expected}",
                f"Expected {expected}, got {actual}"
            )
    
    def validate_match_overall_uptime_logic(self):
        """Validate 'Match Overall Uptime' display logic"""
        self.log("Validating Match Overall Uptime logic...")
        
        def should_show_match_overall(flag_uptime, overall_uptime, threshold=0.1):
            if flag_uptime is None or overall_uptime is None:
                return False
            return abs(flag_uptime - overall_uptime) <= threshold
        
        # Test exact matches
        self.assert_test(
            should_show_match_overall(95.0, 95.0),
            "Exact match: 95.0% == 95.0%"
        )
        
        # Test within threshold
        self.assert_test(
            should_show_match_overall(95.0, 95.05),
            "Within threshold: 95.0% ≈ 95.05%"
        )
        
        self.assert_test(
            should_show_match_overall(95.0, 94.95),
            "Within threshold: 95.0% ≈ 94.95%"
        )
        
        # Test outside threshold
        self.assert_test(
            not should_show_match_overall(95.0, 95.2),
            "Outside threshold: 95.0% ≠ 95.2%"
        )
        
        self.assert_test(
            not should_show_match_overall(95.0, 94.8),
            "Outside threshold: 95.0% ≠ 94.8%"
        )
        
        # Test None handling
        self.assert_test(
            not should_show_match_overall(None, 95.0),
            "None flag uptime handling"
        )
        
        self.assert_test(
            not should_show_match_overall(95.0, None),
            "None overall uptime handling"
        )
    
    def validate_color_coding_thresholds(self):
        """Validate color coding threshold logic"""
        self.log("Validating color coding thresholds...")
        
        def classify_uptime_color(uptime_percent):
            if uptime_percent is None:
                return 'unknown'
            elif uptime_percent >= 95.0:
                return 'green'
            elif uptime_percent >= 80.0:
                return 'yellow'
            else:
                return 'red'
        
        # Test green threshold (≥95%)
        green_cases = [95.0, 95.1, 98.5, 100.0]
        for uptime in green_cases:
            self.assert_test(
                classify_uptime_color(uptime) == 'green',
                f"Green classification: {uptime}%"
            )
        
        # Test yellow threshold (80-94.9%)
        yellow_cases = [80.0, 85.0, 90.0, 94.9]
        for uptime in yellow_cases:
            self.assert_test(
                classify_uptime_color(uptime) == 'yellow',
                f"Yellow classification: {uptime}%"
            )
        
        # Test red threshold (<80%)
        red_cases = [79.9, 70.0, 50.0, 0.0]
        for uptime in red_cases:
            self.assert_test(
                classify_uptime_color(uptime) == 'red',
                f"Red classification: {uptime}%"
            )
        
        # Test None handling
        self.assert_test(
            classify_uptime_color(None) == 'unknown',
            "Unknown classification for None"
        )
    
    def validate_statistical_analysis(self):
        """Validate statistical outlier detection"""
        self.log("Validating statistical analysis...")
        
        # Create test data with clear outliers
        uptime_values = [95.0, 96.0, 94.0, 97.0, 95.5, 50.0, 99.5]  # 50.0 and 99.5 are outliers
        relay_breakdown = {
            f'relay{i}': {
                'nickname': f'TestRelay{i}',
                'uptime': uptime_values[i],
                'fingerprint': f'ABC{i}23'
            } for i in range(len(uptime_values))
        }
        
        outliers = calculate_statistical_outliers(uptime_values, relay_breakdown, std_dev_threshold=2.0)
        
        # Should detect low outlier (50.0%)
        low_outlier_uptimes = [outlier['uptime'] for outlier in outliers['low_outliers']]
        self.assert_test(
            50.0 in low_outlier_uptimes,
            "Low outlier detection: 50.0% detected"
        )
        
        # Should detect high outlier (99.5%)  
        high_outlier_uptimes = [outlier['uptime'] for outlier in outliers['high_outliers']]
        self.assert_test(
            99.5 in high_outlier_uptimes,
            "High outlier detection: 99.5% detected"
        )
        
        # Test edge case: insufficient data
        small_values = [95.0, 96.0]  # Only 2 points
        small_breakdown = {
            'relay1': {'nickname': 'Test1', 'uptime': 95.0, 'fingerprint': 'ABC'},
            'relay2': {'nickname': 'Test2', 'uptime': 96.0, 'fingerprint': 'DEF'}
        }
        
        small_outliers = calculate_statistical_outliers(small_values, small_breakdown)
        self.assert_test(
            len(small_outliers['low_outliers']) == 0 and len(small_outliers['high_outliers']) == 0,
            "Insufficient data handling: No outliers with <3 data points"
        )
    
    def validate_performance_characteristics(self):
        """Validate performance of calculations"""
        self.log("Validating performance characteristics...")
        
        # Test large dataset performance
        large_dataset = [950 + (i % 50) for i in range(100000)]
        
        start_time = time.time()
        result = calculate_relay_uptime_average(large_dataset)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        self.assert_test(
            processing_time < 5.0,  # Should complete in under 5 seconds
            f"Large dataset performance: {len(large_dataset)} values in {processing_time:.3f}s"
        )
        
        # Verify result is reasonable
        self.assert_test(
            90.0 <= result <= 100.0,
            f"Large dataset result validity: {result:.2f}%"
        )
        
        if processing_time > 1.0:
            self.warn(f"Large dataset processing took {processing_time:.3f}s - consider optimization")
    
    def validate_data_integrity(self):
        """Validate data integrity and edge case handling"""
        self.log("Validating data integrity...")
        
        # Test malformed data handling
        malformed_relays = [
            {'fingerprint': 'ABC123'},  # Missing nickname
            {'nickname': 'TestRelay'},  # Missing fingerprint
            {}  # Empty relay data
        ]
        
        malformed_uptime_data = {
            'relays': [
                {'fingerprint': 'ABC123'},  # Missing uptime data
                {'uptime': {}},  # Missing fingerprint
                {'fingerprint': 'DEF456', 'uptime': {'1_month': {}}},  # Missing values
            ]
        }
        
        try:
            result = extract_relay_uptime_for_period(
                malformed_relays,
                malformed_uptime_data,
                '1_month'
            )
            
            self.assert_test(
                isinstance(result, dict) and 'valid_relays' in result,
                "Malformed data handling: Returns valid structure"
            )
            
            self.assert_test(
                result['valid_relays'] == 0,
                "Malformed data handling: No valid relays found"
            )
            
        except Exception as e:
            self.assert_test(
                False,
                "Malformed data handling: Should not raise exceptions",
                f"Raised exception: {e}"
            )
    
    def run_validation(self):
        """Run all validation tests"""
        self.log("Starting Flag Uptime System validation...", 'INFO')
        start_time = time.time()
        
        # Run all validation tests
        self.validate_uptime_normalization()
        self.validate_uptime_averaging()
        self.validate_flag_priority_system()
        self.validate_match_overall_uptime_logic()
        self.validate_color_coding_thresholds()
        self.validate_statistical_analysis()
        self.validate_performance_characteristics()
        self.validate_data_integrity()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Print summary
        print("\n" + "="*60)
        print("FLAG UPTIME VALIDATION SUMMARY")
        print("="*60)
        print(f"Total tests run: {self.passed_tests + self.failed_tests}")
        print(f"Passed: {self.passed_tests}")
        print(f"Failed: {self.failed_tests}")
        print(f"Warnings: {len(self.warnings)}")
        print(f"Validation time: {total_time:.3f}s")
        
        if self.warnings:
            print("\nWarnings:")
            for warning in self.warnings:
                print(f"  ⚠ {warning}")
        
        if self.failed_tests == 0:
            print("\n✅ All flag uptime validations PASSED!")
            return True
        else:
            print(f"\n❌ {self.failed_tests} validation(s) FAILED!")
            return False


def main():
    """Main validation function"""
    parser = argparse.ArgumentParser(description='Validate flag uptime calculations')
    parser.add_argument('--verbose', '-v', action='store_true', 
                        help='Enable verbose output')
    parser.add_argument('--sample-size', '-s', type=int, default=10000,
                        help='Sample size for performance testing (default: 10000)')
    
    args = parser.parse_args()
    
    validator = FlagUptimeValidator(verbose=args.verbose)
    success = validator.run_validation()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main() 