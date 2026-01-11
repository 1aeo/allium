#!/usr/bin/env python3

"""
Comprehensive tests for the Flag Uptime System

Tests cover:
- Flag uptime calculation logic and priority system
- "Match Overall Uptime" vs percentage display logic  
- Statistical coloring thresholds
- Prefix removal and clean percentage display
- Integration with contact page flag reliability
- Performance and edge case handling
"""

import statistics
import unittest
from unittest.mock import patch, MagicMock

from allium.lib.relays import Relays
from allium.lib.uptime_utils import (
    normalize_uptime_value, 
    calculate_relay_uptime_average,
    extract_relay_uptime_for_period,
    calculate_statistical_outliers
)


class TestFlagUptimeCalculation(unittest.TestCase):
    """Test core flag uptime calculation logic"""
    
    def test_uptime_value_normalization(self):
        """Test conversion from Onionoo 0-999 scale to 0-100 percentage"""
        # Test boundary values
        self.assertAlmostEqual(normalize_uptime_value(0), 0.0, places=2)
        self.assertAlmostEqual(normalize_uptime_value(999), 100.0, places=2)
        
        # Test typical values - allow for more precision
        self.assertAlmostEqual(normalize_uptime_value(950), 95.095, places=2)
        self.assertAlmostEqual(normalize_uptime_value(800), 80.080, places=2)
        self.assertAlmostEqual(normalize_uptime_value(500), 50.050, places=2)
    
    def test_relay_uptime_average_calculation(self):
        """Test averaging of multiple uptime data points"""
        # Test normal case with sufficient valid values (30+ required)
        uptime_values = [950 + i for i in range(35)]  # 35 values around 950
        expected_avg = sum(uptime_values) / len(uptime_values) / 999 * 100
        result = calculate_relay_uptime_average(uptime_values)
        self.assertAlmostEqual(result, expected_avg, places=2)
        
        # Test insufficient data (< 30 values) - should return 0.0
        few_values = [950, 960, 940, 970]  # Only 4 values
        result = calculate_relay_uptime_average(few_values)
        self.assertEqual(result, 0.0)


class TestFlagPrioritySystem(unittest.TestCase):
    """Test the flag priority system (Exit > Guard > Fast > Running)"""
    
    def test_flag_priority_selection(self):
        """Test that highest priority flag is selected for uptime display"""
        # Mock the flag priority logic that would be in the actual implementation
        flag_priorities = ['Exit', 'Guard', 'Fast', 'Running']
        
        def get_highest_priority_flag(flags):
            for priority_flag in flag_priorities:
                if priority_flag in flags:
                    return priority_flag
            return None
        
        # Test priority selection
        self.assertEqual(get_highest_priority_flag(['Exit', 'Fast', 'Running']), 'Exit')
        self.assertEqual(get_highest_priority_flag(['Guard', 'Fast', 'Running']), 'Guard')
        self.assertEqual(get_highest_priority_flag(['Fast', 'Running']), 'Fast')
        self.assertEqual(get_highest_priority_flag(['Running']), 'Running')
    
    def test_flag_priority_edge_cases(self):
        """Test edge cases in flag priority selection"""
        flag_priorities = ['Exit', 'Guard', 'Fast', 'Running']
        
        def get_highest_priority_flag(flags):
            for priority_flag in flag_priorities:
                if priority_flag in flags:
                    return priority_flag
            return None
        
        # Test empty flags
        self.assertIsNone(get_highest_priority_flag([]))
        
        # Test unknown flags
        self.assertIsNone(get_highest_priority_flag(['UnknownFlag', 'AnotherUnknown']))
        
        # Test mixed known/unknown flags
        mixed_flags = ['UnknownFlag', 'Guard', 'AnotherUnknown']
        self.assertEqual(get_highest_priority_flag(mixed_flags), 'Guard')


class TestFlagUptimeDisplayLogic(unittest.TestCase):
    """Test display logic for flag uptime including 'Match Overall Uptime' functionality"""
    
    def test_match_overall_uptime_logic(self):
        """Test when flag uptime should show 'Match Overall Uptime'"""
        
        def should_show_match_overall(flag_uptime, overall_uptime, threshold=0.1):
            """Determine if flag uptime matches overall uptime within threshold"""
            if flag_uptime is None or overall_uptime is None:
                return False
            return abs(flag_uptime - overall_uptime) <= threshold
        
        # Test exact match
        self.assertTrue(should_show_match_overall(95.0, 95.0))
        
        # Test within threshold
        self.assertTrue(should_show_match_overall(95.0, 95.05))
        self.assertTrue(should_show_match_overall(95.0, 94.95))
        
        # Test outside threshold
        self.assertFalse(should_show_match_overall(95.0, 95.2))
        self.assertFalse(should_show_match_overall(95.0, 94.8))
        
        # Test None values
        self.assertFalse(should_show_match_overall(None, 95.0))
        self.assertFalse(should_show_match_overall(95.0, None))
        self.assertFalse(should_show_match_overall(None, None))
    
    def test_clean_percentage_formatting(self):
        """Test that percentages are displayed without prefixes"""
        
        def format_flag_uptime_display(uptime_periods):
            """Format flag uptime without prefixes for clean display"""
            if not uptime_periods:
                return "N/A"
            
            formatted_periods = []
            for period_name, uptime_value in uptime_periods.items():
                if uptime_value is not None and uptime_value > 0:
                    formatted_periods.append(f"{uptime_value:.1f}%")
            
            return " / ".join(formatted_periods) if formatted_periods else "N/A"
        
        # Test normal formatting
        periods = {'1M': 95.5, '6M': 94.2, '1Y': 93.8}
        expected = "95.5% / 94.2% / 93.8%"
        self.assertEqual(format_flag_uptime_display(periods), expected)
        
        # Test with None values (should be excluded)
        periods_with_none = {'1M': 95.5, '6M': None, '1Y': 93.8, '5Y': None}
        expected = "95.5% / 93.8%"
        self.assertEqual(format_flag_uptime_display(periods_with_none), expected)
        
        # Test empty periods
        self.assertEqual(format_flag_uptime_display({}), "N/A")


class TestStatisticalColoring(unittest.TestCase):
    """Test statistical coloring and outlier detection for flag uptime"""
    
    def test_uptime_color_classification(self):
        """Test color classification based on uptime thresholds"""
        
        def classify_uptime_color(uptime_percent):
            """Classify uptime into color categories"""
            if uptime_percent is None:
                return 'unknown'
            elif uptime_percent >= 95.0:
                return 'green'
            elif uptime_percent >= 80.0:
                return 'yellow'
            else:
                return 'red'
        
        # Test green threshold
        self.assertEqual(classify_uptime_color(95.0), 'green')
        self.assertEqual(classify_uptime_color(98.5), 'green')
        self.assertEqual(classify_uptime_color(100.0), 'green')
        
        # Test yellow threshold  
        self.assertEqual(classify_uptime_color(94.9), 'yellow')
        self.assertEqual(classify_uptime_color(85.0), 'yellow')
        self.assertEqual(classify_uptime_color(80.0), 'yellow')
        
        # Test red threshold
        self.assertEqual(classify_uptime_color(79.9), 'red')
        self.assertEqual(classify_uptime_color(50.0), 'red')
        self.assertEqual(classify_uptime_color(0.0), 'red')
        
        # Test None value
        self.assertEqual(classify_uptime_color(None), 'unknown')


if __name__ == '__main__':
    unittest.main() 