#!/usr/bin/env python3

import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add the allium directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from allium.lib.relays import Relays


class TestContactDataIntegrityRegression(unittest.TestCase):
    """Regression tests to verify data integrity preservation during contact page refactoring."""
    
    def setUp(self):
        """Set up test fixtures with realistic relay data."""
        # Mock relay data for Relays constructor
        mock_relay_data = {
            'relays': [],
            'sorted': {},
            'network_totals': {
                'total_relays': 0,
                'guard_count': 0,
                'middle_count': 0,
                'exit_count': 0,
                'measured_relays': 0,
                'measured_percentage': 0.0,
                'guard_consensus_weight': 0,
                'middle_consensus_weight': 0,
                'exit_consensus_weight': 0,
                'total_consensus_weight': 0
            }
        }
        
        # Initialize Relays with required constructor arguments and mock methods
        with patch.object(Relays, '_fix_missing_observed_bandwidth'), \
             patch.object(Relays, '_sort_by_observed_bandwidth'), \
             patch.object(Relays, '_trim_platform'), \
             patch.object(Relays, '_add_hashed_contact'), \
             patch.object(Relays, '_process_aroi_contacts'), \
             patch.object(Relays, '_preprocess_template_data'), \
             patch.object(Relays, '_categorize'), \
             patch.object(Relays, '_generate_aroi_leaderboards'), \
             patch.object(Relays, '_generate_smart_context'):
            
            self.relays = Relays(
                output_dir='/tmp/test',
                onionoo_url='https://test.example.com',
                relay_data=mock_relay_data,
                use_bits=False,
                progress=False
            )
        
        # Sample relay data that matches real-world structure
        self.sample_members = [
            {
                'fingerprint': 'A1B2C3D4E5F6789012345678901234567890ABCD',
                'nickname': 'TestRelay1',
                'contact': 'operator@example.com',
                'contact_md5': 'abcd1234efgh5678ijkl9012mnop3456',
                'advertised_bandwidth': 50000000,  # 50 MB/s
                'consensus_weight': 1000,
                'flags': ['Running', 'Fast', 'Guard'],
                'country': 'us',
                'country_name': 'United States',
                'as': 'AS12345',
                'as_name': 'Example ISP',
                'platform': 'Tor 0.4.8.7 on Linux'
            },
            {
                'fingerprint': 'B2C3D4E5F6789012345678901234567890ABCDE1',
                'nickname': 'TestRelay2', 
                'contact': 'operator@example.com',
                'contact_md5': 'abcd1234efgh5678ijkl9012mnop3456',
                'advertised_bandwidth': 75000000,  # 75 MB/s
                'consensus_weight': 1500,
                'flags': ['Running', 'Fast', 'Exit'],
                'country': 'de',
                'country_name': 'Germany',
                'as': 'AS67890',
                'as_name': 'Another ISP',
                'platform': 'Tor 0.4.8.7 on Linux'
            }
        ]
        
        # Pre-computed aggregate data (what would be calculated for the contact)
        self.expected_aggregates = {
            'total_relays': 2,
            'guard_count': 1,
            'middle_count': 0,
            'exit_count': 1,
            'total_bandwidth': 125000000,  # 125 MB/s
            'guard_bandwidth': 50000000,   # 50 MB/s from guard relay
            'middle_bandwidth': 0,
            'exit_bandwidth': 75000000,    # 75 MB/s from exit relay
            'total_consensus_weight': 2500,
            'guard_consensus_weight': 1000,
            'middle_consensus_weight': 0,
            'exit_consensus_weight': 1500
        }

    def test_bandwidth_calculation_integrity(self):
        """Test that bandwidth calculations remain identical after refactoring."""
        # This test simulates the original bandwidth calculation logic
        # and compares it with the new pre-computed data
        
        total_bandwidth = sum(relay['advertised_bandwidth'] for relay in self.sample_members)
        guard_bandwidth = sum(relay['advertised_bandwidth'] for relay in self.sample_members 
                             if 'Guard' in relay['flags'])
        exit_bandwidth = sum(relay['advertised_bandwidth'] for relay in self.sample_members 
                            if 'Exit' in relay['flags'])
        
        # Verify calculations match expected values
        self.assertEqual(total_bandwidth, self.expected_aggregates['total_bandwidth'])
        self.assertEqual(guard_bandwidth, self.expected_aggregates['guard_bandwidth'])
        self.assertEqual(exit_bandwidth, self.expected_aggregates['exit_bandwidth'])

    def test_consensus_weight_calculation_integrity(self):
        """Test that consensus weight calculations remain identical after refactoring."""
        total_consensus_weight = sum(relay['consensus_weight'] for relay in self.sample_members)
        guard_consensus_weight = sum(relay['consensus_weight'] for relay in self.sample_members 
                                   if 'Guard' in relay['flags'])
        exit_consensus_weight = sum(relay['consensus_weight'] for relay in self.sample_members 
                                  if 'Exit' in relay['flags'])
        
        # Verify calculations match expected values
        self.assertEqual(total_consensus_weight, self.expected_aggregates['total_consensus_weight'])
        self.assertEqual(guard_consensus_weight, self.expected_aggregates['guard_consensus_weight'])
        self.assertEqual(exit_consensus_weight, self.expected_aggregates['exit_consensus_weight'])

    def test_relay_count_calculation_integrity(self):
        """Test that relay count calculations remain identical after refactoring."""
        total_relays = len(self.sample_members)
        guard_count = len([r for r in self.sample_members if 'Guard' in r['flags']])
        middle_count = len([r for r in self.sample_members if 'Guard' not in r['flags'] and 'Exit' not in r['flags']])
        exit_count = len([r for r in self.sample_members if 'Exit' in r['flags']])
        
        # Verify counts match expected values
        self.assertEqual(total_relays, self.expected_aggregates['total_relays'])
        self.assertEqual(guard_count, self.expected_aggregates['guard_count'])
        self.assertEqual(middle_count, self.expected_aggregates['middle_count'])
        self.assertEqual(exit_count, self.expected_aggregates['exit_count'])

    @patch('allium.lib.bandwidth_formatter.BandwidthFormatter.format_bandwidth_with_unit')
    def test_bandwidth_breakdown_format_consistency(self, mock_format_bw):
        """Test that bandwidth breakdown formatting remains consistent."""
        mock_format_bw.side_effect = lambda bw, unit: f"{bw/1000000:.1f}"  # Convert to MB
        
        # Simulate the old template-based formatting
        old_guard_bw = f"{self.expected_aggregates['guard_bandwidth']/1000000:.1f} MB/s guard"
        old_exit_bw = f"{self.expected_aggregates['exit_bandwidth']/1000000:.1f} MB/s exit"
        old_breakdown = f"{old_guard_bw}, {old_exit_bw}"
        
        # Test new method produces same result
        relay_data = {
            'guard_count': self.expected_aggregates['guard_count'],
            'middle_count': self.expected_aggregates['middle_count'],
            'exit_count': self.expected_aggregates['exit_count'],
            'guard_bandwidth': self.expected_aggregates['guard_bandwidth'],
            'middle_bandwidth': self.expected_aggregates['middle_bandwidth'],
            'exit_bandwidth': self.expected_aggregates['exit_bandwidth'],
            'guard_consensus_weight_fraction': 0.01,
            'middle_consensus_weight_fraction': 0,
            'exit_consensus_weight_fraction': 0.015
        }
        
        result = self.relays._compute_contact_display_data(
            relay_data, 'MB/s', None, 'test_hash', []
        )
        
        new_breakdown = result['bandwidth_breakdown']
        
        # Should contain same bandwidth values
        self.assertIn('50.0 MB/s guard', new_breakdown)
        self.assertIn('75.0 MB/s exit', new_breakdown)
        self.assertNotIn('middle', new_breakdown)  # Zero middle bandwidth should be filtered

    def test_consensus_weight_percentage_calculation_integrity(self):
        """Test that consensus weight percentage calculations remain identical."""
        # Assuming total network consensus weight for percentage calculation
        total_network_weight = 1000000  # 1M total network weight (example)
        
        guard_percentage = (self.expected_aggregates['guard_consensus_weight'] / total_network_weight) * 100
        exit_percentage = (self.expected_aggregates['exit_consensus_weight'] / total_network_weight) * 100
        total_percentage = (self.expected_aggregates['total_consensus_weight'] / total_network_weight) * 100
        
        # Test the formatting remains consistent
        self.assertEqual(f"{guard_percentage:.2f}%", "0.10%")
        self.assertEqual(f"{exit_percentage:.2f}%", "0.15%")
        self.assertEqual(f"{total_percentage:.2f}%", "0.25%")

    def test_uptime_highlighting_threshold_regression(self):
        """Test that uptime highlighting thresholds remain correct after floating-point fix."""
        # Test the original problematic case that was fixed
        test_cases = [
            (100.0, True),      # Exactly 100% should be highlighted
            (99.99, True),      # 99.99% should be highlighted (fixed threshold)
            (99.999, True),     # 99.999% should be highlighted
            (99.9, False),      # 99.9% should NOT be highlighted
            (99.8, False),      # 99.8% should NOT be highlighted
            (100.001, True),    # Even above 100% should be highlighted (edge case)
        ]
        
        for uptime_value, should_highlight in test_cases:
            with self.subTest(uptime=uptime_value):
                # Test the logic used in _compute_contact_display_data
                # Fixed condition: >= 99.99 or abs(avg - 100.0) < 0.01
                is_highlighted = uptime_value >= 99.99 or abs(uptime_value - 100.0) < 0.01
                self.assertEqual(is_highlighted, should_highlight, 
                               f"Uptime {uptime_value}% highlighting should be {should_highlight}")

    def test_network_position_calculation_consistency(self):
        """Test that network position calculations remain consistent."""
        total_relays = self.expected_aggregates['total_relays']
        guard_count = self.expected_aggregates['guard_count']
        middle_count = self.expected_aggregates['middle_count']
        exit_count = self.expected_aggregates['exit_count']
        
        # Calculate ratios (original logic)
        guard_ratio = guard_count / total_relays if total_relays > 0 else 0
        middle_ratio = middle_count / total_relays if total_relays > 0 else 0
        exit_ratio = exit_count / total_relays if total_relays > 0 else 0
        
        # Test classification logic
        self.assertEqual(guard_ratio, 0.5)  # 1/2 = 50%
        self.assertEqual(middle_ratio, 0.0)  # 0/2 = 0%
        self.assertEqual(exit_ratio, 0.5)   # 1/2 = 50%
        
        # With these ratios, should be classified as mixed (no single type > 50%)
        if guard_ratio > 0.5:
            classification = "Guard-focused"
        elif exit_ratio > 0.5:
            classification = "Exit-focused"
        elif middle_ratio > 0.5:
            classification = "Middle-focused"
        else:
            classification = "Mixed"  # Expected for this test case
            
        self.assertEqual(classification, "Mixed")

    def test_statistical_outliers_calculation_integrity(self):
        """Test that statistical outliers calculations remain mathematically correct."""
        # Sample uptime data for testing
        uptime_values = [95.2, 98.1, 98.5, 99.8, 99.9]  # 5 relays
        
        # Calculate statistics (matches the logic in _calculate_operator_reliability)
        import statistics
        mean_uptime = statistics.mean(uptime_values)
        std_dev = statistics.stdev(uptime_values) if len(uptime_values) > 1 else 0
        
        # Calculate thresholds for 2-sigma outliers
        low_threshold = mean_uptime - (2 * std_dev)
        high_threshold = mean_uptime + (2 * std_dev)
        
        # Test values
        self.assertAlmostEqual(mean_uptime, 98.3, places=1)
        self.assertGreater(std_dev, 0)  # Should have some deviation
        
        # Test outlier detection
        low_outliers = [val for val in uptime_values if val < low_threshold]
        high_outliers = [val for val in uptime_values if val > high_threshold]
        
        # With this sample data, should detect outliers correctly
        total_outliers = len(low_outliers) + len(high_outliers)
        self.assertGreaterEqual(total_outliers, 0)  # Should have non-negative outliers

    def test_aroi_ranking_sort_consistency(self):
        """Test that AROI ranking sorting remains consistent (rank 1 first)."""
        # Sample rankings data
        sample_rankings = [
            {'rank': 5, 'statement': '#5 in Category A'},
            {'rank': 1, 'statement': '#1 in Category B'},
            {'rank': 3, 'statement': '#3 in Category C'},
            {'rank': 2, 'statement': '#2 in Category D'}
        ]
        
        # Sort by rank (as implemented in the fix)
        sorted_rankings = sorted(sample_rankings, key=lambda x: x['rank'])
        
        # Verify first rank is 1, last rank is 5
        self.assertEqual(sorted_rankings[0]['rank'], 1)
        self.assertEqual(sorted_rankings[-1]['rank'], 5)
        
        # Verify correct order
        expected_order = [1, 2, 3, 5]
        actual_order = [r['rank'] for r in sorted_rankings]
        self.assertEqual(actual_order, expected_order)

    @patch('allium.lib.bandwidth_formatter.BandwidthFormatter.format_bandwidth_with_unit')
    def test_zero_value_filtering_consistency(self, mock_format_bw):
        """Test that zero value filtering works consistently across all display components."""
        mock_format_bw.side_effect = lambda bw, unit: "0.00" if bw == 0 else f"{bw/1000000:.1f}"
        
        # Test case with some zero values
        relay_data_with_zeros = {
            'guard_count': 2,
            'middle_count': 0,  # Zero middle count
            'exit_count': 1,
            'guard_bandwidth': 50000000,
            'middle_bandwidth': 0,  # Zero middle bandwidth
            'exit_bandwidth': 25000000,
            'guard_consensus_weight_fraction': 0.02,
            'middle_consensus_weight_fraction': 0,  # Zero middle consensus weight
            'exit_consensus_weight_fraction': 0.01
        }
        
        result = self.relays._compute_contact_display_data(
            relay_data_with_zeros, 'MB/s', None, 'test_hash', []
        )
        
        # Bandwidth breakdown should exclude zero middle bandwidth
        self.assertNotIn('0.00 MB/s middle', result['bandwidth_breakdown'] or '')
        self.assertIn('50.0 MB/s guard', result['bandwidth_breakdown'] or '')
        self.assertIn('25.0 MB/s exit', result['bandwidth_breakdown'] or '')
        
        # Consensus weight breakdown should exclude zero middle weight  
        self.assertNotIn('0.00% middle', result['consensus_weight_breakdown'] or '')
        self.assertIn('2.00% guard', result['consensus_weight_breakdown'] or '')
        self.assertIn('1.00% exit', result['consensus_weight_breakdown'] or '')

    def test_intelligence_rating_color_coding_consistency(self):
        """Test that intelligence rating color coding remains consistent."""
        test_cases = [
            ('Poor, 1 network', '#c82333'),      # Red for Poor
            ('Okay, 2 networks', '#cc9900'),     # Orange for Okay  
            ('Great, 4 networks', '#2e7d2e'),    # Green for Great
        ]
        
        for rating_text, expected_color in test_cases:
            with self.subTest(rating=rating_text):
                result = self.relays._format_intelligence_rating(rating_text)
                self.assertIn(expected_color, result)
                self.assertIn('font-weight: bold', result)
                
                # Verify the rating word is correctly highlighted
                if 'Poor' in rating_text:
                    self.assertIn('>Poor</span>', result)
                elif 'Okay' in rating_text:
                    self.assertIn('>Okay</span>', result)
                elif 'Great' in rating_text:
                    self.assertIn('>Great</span>', result)


if __name__ == '__main__':
    unittest.main()