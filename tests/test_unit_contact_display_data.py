#!/usr/bin/env python3

import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add the allium directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'allium'))

from lib.relays import Relays


class TestContactDisplayData(unittest.TestCase):
    """Test suite for contact display data computation functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock relay data for Relays constructor
        mock_relay_data = {
            'relays': [],
            'sorted': {},
            'network_totals': {
                'total_relays': 0,
                'guard_count': 0,
                'middle_count': 0,
                'exit_count': 0,
                'measured_relays': 0
            }
        }
        
        # Initialize Relays with required constructor arguments
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
        
        # Set up test intelligence data
        self.relays.json = {
            'smart_context': {
                'contact_intelligence': {
                    'template_optimized': {
                        'test_contact_hash': {
                            'portfolio_diversity': 'Great, 4 networks',
                            'geographic_risk': 'Okay, 2 countries', 
                            'infrastructure_risk': 'Poor, 1 platform, 1 version',
                            'measurement_status': '5/5 relays measured by authorities',
                            'performance_status': 'optimal efficiency',
                            'performance_underutilized': 0,
                            'performance_underutilized_fps': [],
                            'maturity': 'Operating since 2020-01-01 (all deployed together)'
                        }
                    }
                }
            }
        }
        
        # Sample relay data for testing
        self.sample_relay_data = {
            'guard_count': 2,
            'middle_count': 1, 
            'exit_count': 2,
            'guard_bandwidth': 50000000,  # 50 MB/s
            'middle_bandwidth': 25000000,  # 25 MB/s
            'exit_bandwidth': 75000000,   # 75 MB/s
            'guard_consensus_weight_fraction': 0.02,  # 2%
            'middle_consensus_weight_fraction': 0.01,  # 1% 
            'exit_consensus_weight_fraction': 0.03    # 3%
        }
        
        # Sample operator reliability data
        self.sample_reliability = {
            'valid_relays': 5,
            'total_relays': 5,
            'overall_uptime': {
                '1_month': {
                    'average': 98.5,
                    'std_dev': 2.1,
                    'display_name': '30d',
                    'relay_count': 5
                },
                '6_months': {
                    'average': 99.8,
                    'std_dev': 0.5,
                    'display_name': '6mo', 
                    'relay_count': 5
                }
            },
            'outliers': {
                'low_outliers': [
                    {'nickname': 'TestRelay1', 'uptime': 95.2}
                ],
                'high_outliers': [
                    {'nickname': 'TestRelay2', 'uptime': 99.9}
                ]
            }
        }

    def test_format_intelligence_rating_poor(self):
        """Test color-coded formatting for Poor intelligence ratings."""
        result = self.relays._format_intelligence_rating('Poor, 1 network')
        expected = '<span style="color: #c82333; font-weight: bold;">Poor</span>, 1 network'
        self.assertEqual(result, expected)

    def test_format_intelligence_rating_okay(self):
        """Test color-coded formatting for Okay intelligence ratings.""" 
        result = self.relays._format_intelligence_rating('Okay, 2 countries')
        expected = '<span style="color: #cc9900; font-weight: bold;">Okay</span>, 2 countries'
        self.assertEqual(result, expected)

    def test_format_intelligence_rating_great(self):
        """Test color-coded formatting for Great intelligence ratings."""
        result = self.relays._format_intelligence_rating('Great, 4 networks')
        expected = '<span style="color: #2e7d2e; font-weight: bold;">Great</span>, 4 networks'
        self.assertEqual(result, expected)

    def test_format_intelligence_rating_invalid_format(self):
        """Test handling of invalid rating format."""
        result = self.relays._format_intelligence_rating('Invalid format')
        self.assertEqual(result, 'Invalid format')

    def test_format_intelligence_rating_empty_string(self):
        """Test handling of empty string."""
        result = self.relays._format_intelligence_rating('')
        self.assertEqual(result, '')

    def test_format_intelligence_rating_none(self):
        """Test handling of None input."""
        result = self.relays._format_intelligence_rating(None)
        self.assertEqual(result, None)

    @patch.object(Relays, '_format_bandwidth_with_unit')
    def test_compute_contact_display_data_bandwidth_breakdown(self, mock_format_bw):
        """Test bandwidth breakdown formatting with mixed relay types."""
        mock_format_bw.side_effect = lambda bw, unit: f"{bw/1000000:.1f}"  # Convert to MB
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', []
        )
        
        # Should include all three bandwidth types
        self.assertIn('bandwidth_breakdown', result)
        breakdown = result['bandwidth_breakdown']
        self.assertIn('guard', breakdown)
        self.assertIn('middle', breakdown) 
        self.assertIn('exit', breakdown)

    @patch.object(Relays, '_format_bandwidth_with_unit')
    def test_compute_contact_display_data_bandwidth_breakdown_zero_values(self, mock_format_bw):
        """Test bandwidth breakdown filtering of zero values."""
        mock_format_bw.side_effect = lambda bw, unit: "0.00" if bw == 0 else f"{bw/1000000:.1f}"
        
        relay_data = self.sample_relay_data.copy()
        relay_data['middle_bandwidth'] = 0  # Zero middle bandwidth
        
        result = self.relays._compute_contact_display_data(
            relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', []
        )
        
        breakdown = result['bandwidth_breakdown']
        self.assertNotIn('0.00 MB/s middle', breakdown)  # Should be filtered out
        self.assertIn('guard', breakdown)  # Should still include non-zero values
        self.assertIn('exit', breakdown)

    def test_compute_contact_display_data_consensus_weight_breakdown(self):
        """Test consensus weight breakdown with filtering of zero values."""
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', []
        )
        
        self.assertIn('consensus_weight_breakdown', result)
        breakdown = result['consensus_weight_breakdown']
        
        # Should include all three types (all non-zero in sample data)
        self.assertIn('2.00% guard', breakdown)
        self.assertIn('1.00% middle', breakdown)
        self.assertIn('3.00% exit', breakdown)

    def test_compute_contact_display_data_consensus_weight_breakdown_zero_values(self):
        """Test consensus weight breakdown filtering of zero values."""
        relay_data = self.sample_relay_data.copy()
        relay_data['middle_consensus_weight_fraction'] = 0  # Zero middle consensus weight
        
        result = self.relays._compute_contact_display_data(
            relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', []
        )
        
        breakdown = result['consensus_weight_breakdown']
        self.assertNotIn('0.00% middle', breakdown)  # Should be filtered out
        self.assertIn('2.00% guard', breakdown)  # Should include non-zero values
        self.assertIn('3.00% exit', breakdown)

    def test_compute_contact_display_data_uptime_highlighting_exactly_100(self):
        """Test uptime highlighting for exactly 100% values."""
        reliability_data = self.sample_reliability.copy()
        reliability_data['overall_uptime']['6_months']['average'] = 100.0
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', reliability_data, 'test_contact_hash', []
        )
        
        uptime_formatted = result['uptime_formatted']['6_months']['display']
        self.assertIn('color: #28a745', uptime_formatted)  # Should be green highlighted
        self.assertIn('font-weight: bold', uptime_formatted)

    def test_compute_contact_display_data_uptime_highlighting_near_100(self):
        """Test uptime highlighting for near-100% values (99.99%)."""
        reliability_data = self.sample_reliability.copy()
        reliability_data['overall_uptime']['6_months']['average'] = 99.99
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', reliability_data, 'test_contact_hash', []
        )
        
        uptime_formatted = result['uptime_formatted']['6_months']['display']
        self.assertIn('color: #28a745', uptime_formatted)  # Should be green highlighted

    def test_compute_contact_display_data_uptime_highlighting_below_threshold(self):
        """Test uptime highlighting for values below highlighting threshold."""
        reliability_data = self.sample_reliability.copy()
        reliability_data['overall_uptime']['6_months']['average'] = 99.9  # Below 99.99 threshold
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', reliability_data, 'test_contact_hash', []
        )
        
        uptime_formatted = result['uptime_formatted']['6_months']['display']
        self.assertNotIn('color: #28a745', uptime_formatted)  # Should not be highlighted

    def test_compute_contact_display_data_outliers_calculation(self):
        """Test statistical outliers calculation and tooltip generation."""
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', []
        )
        
        outliers = result['outliers']
        
        # Should calculate total outliers correctly
        self.assertEqual(outliers['total_count'], 2)  # 1 low + 1 high
        self.assertEqual(outliers['total_relays'], 5)
        self.assertEqual(outliers['percentage'], '40.0')  # 2/5 * 100
        
        # Should include tooltip with statistical information
        self.assertIn('tooltip', outliers)
        self.assertIn('6 month:', outliers['tooltip'])
        self.assertIn('≥2σ', outliers['tooltip'])
        
        # Should format low and high outliers correctly
        self.assertEqual(outliers['low_count'], 1)
        self.assertIn('TestRelay1 (95.2%)', outliers['low_tooltip'])
        
        self.assertEqual(outliers['high_count'], 1)
        self.assertIn('TestRelay2 (99.9%)', outliers['high_tooltip'])

    def test_compute_contact_display_data_no_outliers(self):
        """Test outliers handling when no outliers are detected."""
        reliability_data = self.sample_reliability.copy()
        reliability_data['outliers'] = {'low_outliers': [], 'high_outliers': []}
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', reliability_data, 'test_contact_hash', []
        )
        
        outliers = result['outliers']
        self.assertTrue(outliers['none_detected'])

    def test_compute_contact_display_data_operator_intelligence_formatting(self):
        """Test operator intelligence data formatting with color coding."""
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', []
        )
        
        intelligence = result['operator_intelligence']
        
        # Should format network diversity with color coding
        self.assertIn('network_diversity', intelligence)
        self.assertIn('<span style="color: #2e7d2e', intelligence['network_diversity'])  # Great = green
        
        # Should format geographic diversity with color coding
        self.assertIn('geographic_diversity', intelligence)
        self.assertIn('<span style="color: #cc9900', intelligence['geographic_diversity'])  # Okay = orange
        
        # Should format infrastructure diversity with color coding
        self.assertIn('infrastructure_diversity', intelligence)
        self.assertIn('<span style="color: #c82333', intelligence['infrastructure_diversity'])  # Poor = red

    def test_compute_contact_display_data_no_intelligence_data(self):
        """Test handling when no intelligence data is available."""
        relays_no_intel = Relays(
            output_dir='/tmp/test',
            onionoo_url='https://test.example.com',
            relay_data={'relays': [], 'sorted': {}},
            use_bits=False,
            progress=False
        )
        
        # Mock the initialization methods to avoid actual processing
        with patch.object(Relays, '_fix_missing_observed_bandwidth'), \
             patch.object(Relays, '_sort_by_observed_bandwidth'), \
             patch.object(Relays, '_trim_platform'), \
             patch.object(Relays, '_add_hashed_contact'), \
             patch.object(Relays, '_process_aroi_contacts'), \
             patch.object(Relays, '_preprocess_template_data'), \
             patch.object(Relays, '_categorize'), \
             patch.object(Relays, '_generate_aroi_leaderboards'), \
             patch.object(Relays, '_generate_smart_context'):
            
            relays_no_intel.json = {}  # No intelligence data
            
            result = relays_no_intel._compute_contact_display_data(
                self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', []
            )
            
            # Should handle gracefully when no intelligence data exists
            intelligence = result['operator_intelligence']
            self.assertEqual(len(intelligence), 0)

    def test_compute_contact_display_data_no_reliability_data(self):
        """Test handling when no reliability data is available."""
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', None, 'test_contact_hash', []
        )
        
        # Should handle gracefully when no reliability data exists
        self.assertEqual(result['uptime_formatted'], {})
        self.assertEqual(result['outliers'], {})

    @patch.object(Relays, '_format_bandwidth_with_unit')
    def test_compute_contact_display_data_edge_case_single_relay(self, mock_format_bw):
        """Test display data computation for single relay contact."""
        mock_format_bw.return_value = '10.0'
        
        single_relay_data = {
            'guard_count': 1,
            'middle_count': 0,
            'exit_count': 0,
            'guard_bandwidth': 10000000,
            'middle_bandwidth': 0,
            'exit_bandwidth': 0,
            'guard_consensus_weight_fraction': 0.01,
            'middle_consensus_weight_fraction': 0,
            'exit_consensus_weight_fraction': 0
        }
        
        result = self.relays._compute_contact_display_data(
            single_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', []
        )
        
        # Should only include guard information (no middle/exit)
        self.assertIn('10.0 MB/s guard', result['bandwidth_breakdown'])
        self.assertNotIn('middle', result['bandwidth_breakdown'])
        self.assertNotIn('exit', result['bandwidth_breakdown'])
        
        self.assertIn('1.00% guard', result['consensus_weight_breakdown'])
        self.assertNotIn('middle', result['consensus_weight_breakdown'])
        self.assertNotIn('exit', result['consensus_weight_breakdown'])

    def test_compute_contact_display_data_version_compliance_counting(self):
        """Test version compliance counting (compliant/non-compliant/unknown)."""
        # Sample relay data with various version compliance states
        test_members = [
            {'recommended_version': True, 'version_status': 'recommended'},
            {'recommended_version': False, 'version_status': 'obsolete'},
            {'recommended_version': None, 'version_status': 'experimental'},
            {'recommended_version': True, 'version_status': 'recommended'},
            {'recommended_version': False, 'version_status': 'unrecommended'},
        ]
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', test_members
        )
        
        intelligence = result['operator_intelligence']
        
        # Should count version compliance correctly
        self.assertIn('version_compliance', intelligence)
        self.assertEqual(intelligence['version_compliance'], '2 compliant, 2 not compliant, 1 unknown')

    def test_compute_contact_display_data_version_status_counting(self):
        """Test version status counting (recommended/experimental/obsolete/new in series/unrecommended)."""
        # Sample relay data with various version statuses
        test_members = [
            {'recommended_version': True, 'version_status': 'recommended'},
            {'recommended_version': True, 'version_status': 'recommended'},
            {'recommended_version': False, 'version_status': 'obsolete'},
            {'recommended_version': None, 'version_status': 'experimental'},
            {'recommended_version': False, 'version_status': 'unrecommended'},
            {'recommended_version': True, 'version_status': 'new in series'},
        ]
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', test_members
        )
        
        intelligence = result['operator_intelligence']
        
        # Should count version status correctly and only show non-zero counts
        self.assertIn('version_status', intelligence)
        version_status = intelligence['version_status']
        
        # Check that all non-zero counts are included
        self.assertIn('2 recommended', version_status)
        self.assertIn('1 experimental', version_status)
        self.assertIn('1 obsolete', version_status)
        self.assertIn('1 new in series', version_status)  # Test underscore replacement
        self.assertIn('1 unrecommended', version_status)

    def test_compute_contact_display_data_version_status_zero_filtering(self):
        """Test that version status with zero counts are filtered out."""
        # Sample relay data with only some version statuses
        test_members = [
            {'recommended_version': True, 'version_status': 'recommended'},
            {'recommended_version': True, 'version_status': 'recommended'},
            # No obsolete, experimental, new in series, or unrecommended
        ]
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', test_members
        )
        
        intelligence = result['operator_intelligence']
        version_status = intelligence['version_status']
        
        # Should only show recommended (non-zero count)
        self.assertEqual(version_status, '2 recommended')
        self.assertNotIn('experimental', version_status)
        self.assertNotIn('obsolete', version_status)
        self.assertNotIn('unrecommended', version_status)

    def test_compute_contact_display_data_version_empty_members(self):
        """Test version compliance/status handling with empty member list."""
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', []
        )
        
        intelligence = result['operator_intelligence']
        
        # Should handle empty member list gracefully (zero values for not compliant and unknown are filtered out)
        self.assertEqual(intelligence['version_compliance'], '0 compliant')
        self.assertEqual(intelligence['version_status'], 'none')

    def test_compute_contact_display_data_version_missing_fields(self):
        """Test version compliance/status handling with missing version fields."""
        # Sample relay data with missing version fields
        test_members = [
            {},  # No version fields at all
            {'recommended_version': True},  # Missing version_status
            {'version_status': 'recommended'},  # Missing recommended_version
        ]
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', test_members
        )
        
        intelligence = result['operator_intelligence']
        
        # Should handle missing fields gracefully (zero values for not compliant are filtered out)
        # recommended_version: None=2 (missing fields treated as None), True=1, False=0 
        # version_status: None=2 (missing fields), recommended=1
        self.assertEqual(intelligence['version_compliance'], '1 compliant, 2 unknown')
        self.assertEqual(intelligence['version_status'], '1 recommended')

    def test_compute_contact_display_data_version_compliance_zero_filtering(self):
        """Test that zero values for not compliant and unknown are filtered out."""
        # Sample relay data with only compliant relays (no not compliant or unknown)
        test_members = [
            {'recommended_version': True, 'version_status': 'recommended'},
            {'recommended_version': True, 'version_status': 'recommended'},
            {'recommended_version': True, 'version_status': 'experimental'},
        ]
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', test_members
        )
        
        intelligence = result['operator_intelligence']
        
        # Should only show compliant (non-zero count), filter out zero values
        self.assertEqual(intelligence['version_compliance'], '3 compliant')
        self.assertNotIn('not compliant', intelligence['version_compliance'])
        self.assertNotIn('unknown', intelligence['version_compliance'])


if __name__ == '__main__':
    unittest.main()