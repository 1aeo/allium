#!/usr/bin/env python3

import unittest
from unittest.mock import Mock, patch, MagicMock

# Import consolidated test utilities
from test_utils import TestDataFactory, TestSetupHelpers, TestPatchingHelpers
from allium.lib.relays import Relays


class TestContactDisplayData(unittest.TestCase):
    """Test suite for contact display data computation functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Use consolidated test utilities
        self.relays = TestSetupHelpers.create_test_relays_instance(
            output_dir='/tmp/test',
            onionoo_url='https://test.example.com',
            relay_data=TestDataFactory.create_minimal_relay_data(),
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

    @patch('allium.lib.bandwidth_formatter.BandwidthFormatter.format_bandwidth_with_unit')
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

    @patch('allium.lib.bandwidth_formatter.BandwidthFormatter.format_bandwidth_with_unit')
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
        self.assertIn('6mo:', outliers['tooltip'])
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
        # Version-related fields are always present even with no intelligence data
        intelligence = result['operator_intelligence']
        self.assertEqual(len(intelligence), 3)
        self.assertIn('version_compliance', intelligence)
        self.assertIn('version_status', intelligence)
        self.assertIn('version_status_tooltips', intelligence)
        self.assertEqual(intelligence['version_compliance'], '0 compliant')
        self.assertEqual(intelligence['version_status'], 'none')

    def test_compute_contact_display_data_no_reliability_data(self):
        """Test handling when no reliability data is available."""
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', None, 'test_contact_hash', []
        )
        
        # Should handle gracefully when no reliability data exists
        self.assertEqual(result['uptime_formatted'], {})
        self.assertEqual(result['outliers'], {})

    @patch('allium.lib.bandwidth_formatter.BandwidthFormatter.format_bandwidth_with_unit')
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
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.7'},
            {'recommended_version': False, 'version_status': 'obsolete', 'version': '0.4.6.10'},
            {'recommended_version': None, 'version_status': 'experimental', 'version': '0.4.9.0-alpha'},
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.7'},
            {'recommended_version': False, 'version_status': 'unrecommended', 'version': '0.4.7.5'},
        ]
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', test_members
        )
        
        intelligence = result['operator_intelligence']
        
        # Should count version compliance correctly (2/5 = 40% compliant, which is ≤50% so "Poor")
        self.assertIn('version_compliance', intelligence)
        expected = '<span style="color: #c82333; font-weight: bold;">Poor</span>, 2 (40%) compliant, 2 (40%) not compliant, 1 (20%) unknown'
        self.assertEqual(intelligence['version_compliance'], expected)
        
        # Should include version status tooltips
        self.assertIn('version_status_tooltips', intelligence)
        self.assertIn('Recommended versions:', intelligence['version_status_tooltips']['recommended'])
        self.assertIn('0.4.8.7', intelligence['version_status_tooltips']['recommended'])

    def test_compute_contact_display_data_version_compliance_all_compliant(self):
        """Test version compliance with green 'All' when all relays are compliant."""
        # Sample relay data with all compliant relays
        test_members = [
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.7'},
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.8'},
            {'recommended_version': True, 'version_status': 'experimental', 'version': '0.4.9.0-alpha'},
        ]
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', test_members
        )
        
        intelligence = result['operator_intelligence']
        
        # Should show green "All" for fully compliant operator
        expected = '<span style="color: #2e7d2e; font-weight: bold;">All</span>, 3 (100%) compliant'
        self.assertEqual(intelligence['version_compliance'], expected)
        self.assertNotIn('not compliant', intelligence['version_compliance'])
        self.assertNotIn('unknown', intelligence['version_compliance'])

    def test_compute_contact_display_data_version_status_counting(self):
        """Test version status counting (recommended/experimental/obsolete/new in series/unrecommended)."""
        # Sample relay data with various version statuses
        test_members = [
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.7'},
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.8'},
            {'recommended_version': False, 'version_status': 'obsolete', 'version': '0.4.6.10'},
            {'recommended_version': None, 'version_status': 'experimental', 'version': '0.4.9.0-alpha'},
            {'recommended_version': False, 'version_status': 'unrecommended', 'version': '0.4.7.5'},
            {'recommended_version': True, 'version_status': 'new in series', 'version': '0.4.8.9'},
        ]
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', test_members
        )
        
        intelligence = result['operator_intelligence']
        
        # Should count version status correctly and only show non-zero counts with status indicator
        self.assertIn('version_status', intelligence)
        version_status = intelligence['version_status']
        
        # Check that it shows "Poor" indicator since only 2/6 = 33% are recommended (≤50%)
        self.assertIn('<span style="color: #c82333; font-weight: bold;">Poor</span>', version_status)
        self.assertIn('2 (33%) recommended', version_status)
        self.assertIn('1 (17%) experimental', version_status)
        self.assertIn('1 (17%) obsolete', version_status)
        self.assertIn('1 (17%) new in series', version_status)  # Test underscore replacement
        self.assertIn('1 (17%) unrecommended', version_status)
        
        # Should include version status tooltips with actual Tor versions
        self.assertIn('version_status_tooltips', intelligence)
        tooltips = intelligence['version_status_tooltips']
        
        # Check that tooltips contain actual version information
        self.assertIn('recommended', tooltips)
        self.assertIn('0.4.8.7', tooltips['recommended'])
        self.assertIn('0.4.8.8', tooltips['recommended'])
        
        self.assertIn('experimental', tooltips)
        self.assertIn('0.4.9.0-alpha', tooltips['experimental'])
        
        self.assertIn('new_in_series', tooltips)
        self.assertIn('0.4.8.9', tooltips['new_in_series'])

    def test_compute_contact_display_data_version_status_zero_filtering(self):
        """Test that version status with zero counts are filtered out."""
        # Sample relay data with only some version statuses
        test_members = [
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.7'},
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.8'},
            # No obsolete, experimental, new in series, or unrecommended
        ]
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', test_members
        )
        
        intelligence = result['operator_intelligence']
        version_status = intelligence['version_status']
        
        # Should only show recommended with "All" status indicator (non-zero count)
        expected_status = '<span style="color: #2e7d2e; font-weight: bold;">All</span>, <span title="Recommended versions: 0.4.8.7, 0.4.8.8" style="cursor: help;">2 (100%) recommended</span>'
        self.assertEqual(version_status, expected_status)
        self.assertNotIn('experimental', version_status)
        self.assertNotIn('obsolete', version_status)
        self.assertNotIn('unrecommended', version_status)
        
        # Should only have tooltip for recommended status
        tooltips = intelligence['version_status_tooltips']
        self.assertIn('recommended', tooltips)
        self.assertNotIn('experimental', tooltips)
        self.assertNotIn('obsolete', tooltips)

    def test_compute_contact_display_data_version_compliance_zero_filtering(self):
        """Test that zero values for not compliant and unknown are filtered out."""
        # Sample relay data with only compliant relays (no not compliant or unknown)
        test_members = [
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.7'},
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.8'},
            {'recommended_version': True, 'version_status': 'experimental', 'version': '0.4.9.0-alpha'},
        ]
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', test_members
        )
        
        intelligence = result['operator_intelligence']
        
        # Should show green "All" for fully compliant operator
        expected = '<span style="color: #2e7d2e; font-weight: bold;">All</span>, 3 (100%) compliant'
        self.assertEqual(intelligence['version_compliance'], expected)
        self.assertNotIn('not compliant', intelligence['version_compliance'])
        self.assertNotIn('unknown', intelligence['version_compliance'])

    def test_compute_contact_display_data_version_tooltips_functionality(self):
        """Test version status tooltips with multiple versions and edge cases."""
        # Sample data with duplicate versions and missing version data
        test_members = [
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.7'},
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.7'},  # Duplicate version
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.8'},
            {'recommended_version': False, 'version_status': 'obsolete'},  # Missing version field
            {'recommended_version': False, 'version_status': 'obsolete', 'version': ''},  # Empty version
            {'recommended_version': False, 'version_status': 'obsolete', 'version': '0.4.6.10'},
        ]
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', test_members
        )
        
        intelligence = result['operator_intelligence']
        tooltips = intelligence['version_status_tooltips']
        
        # Should deduplicate versions in tooltips (set() behavior)
        recommended_tooltip = tooltips['recommended']
        self.assertIn('0.4.8.7', recommended_tooltip)
        self.assertIn('0.4.8.8', recommended_tooltip)
        # Should not contain duplicate 0.4.8.7
        version_count = recommended_tooltip.count('0.4.8.7')
        self.assertEqual(version_count, 1, "Versions should be deduplicated in tooltips")
        
        # Should handle missing version data gracefully
        self.assertIn('obsolete', tooltips)
        obsolete_tooltip = tooltips['obsolete']
        self.assertIn('0.4.6.10', obsolete_tooltip)  # Should include valid version
        # Should not include empty or missing versions

    def test_compute_contact_display_data_version_empty_members(self):
        """Test version compliance/status handling with empty member list."""
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', []
        )
        
        intelligence = result['operator_intelligence']
        
        # Should handle empty member list gracefully (zero values for not compliant and unknown are filtered out)
        self.assertEqual(intelligence['version_compliance'], '0 compliant')
        self.assertEqual(intelligence['version_status'], 'none')
        self.assertEqual(intelligence['version_status_tooltips'], {})

    def test_compute_contact_display_data_version_missing_fields(self):
        """Test version compliance/status handling with missing version fields."""
        # Sample relay data with missing version fields
        test_members = [
            {},  # No version fields at all
            {'recommended_version': True, 'version': '0.4.8.7'},  # Missing version_status
            {'version_status': 'recommended', 'version': '0.4.8.8'},  # Missing recommended_version
        ]
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', test_members
        )
        
        intelligence = result['operator_intelligence']
        
        # Should handle missing fields gracefully (1/3 = 33% compliant, which is ≤50% so "Poor")
        # recommended_version: None=2 (missing fields treated as None), True=1, False=0 
        # version_status: None=2 (missing fields), recommended=1
        expected = '<span style="color: #c82333; font-weight: bold;">Poor</span>, 1 (33%) compliant, 2 (67%) unknown'
        self.assertEqual(intelligence['version_compliance'], expected)
        expected_status = '<span style="color: #c82333; font-weight: bold;">Poor</span>, <span title="Recommended versions: 0.4.8.8" style="cursor: help;">1 (33%) recommended</span>'
        self.assertEqual(intelligence['version_status'], expected_status)
        
        # Should include tooltip for the one valid recommended relay
        self.assertIn('recommended', intelligence['version_status_tooltips'])
        self.assertIn('0.4.8.8', intelligence['version_status_tooltips']['recommended'])

    def test_compute_contact_display_data_version_compliance_partial(self):
        """Test version compliance with orange 'Partial' when >50% but not 100% are compliant."""
        # Sample relay data with partial compliance (3 out of 4 = 75% compliant)
        test_members = [
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.7'},
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.8'},
            {'recommended_version': True, 'version_status': 'experimental', 'version': '0.4.9.0-alpha'},
            {'recommended_version': False, 'version_status': 'obsolete', 'version': '0.4.6.10'},
        ]
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', test_members
        )
        
        intelligence = result['operator_intelligence']
        
        # Should show orange "Partial" when >50% but not 100% are compliant
        self.assertIn('version_compliance', intelligence)
        expected = '<span style="color: #cc9900; font-weight: bold;">Partial</span>, 3 (75%) compliant, 1 (25%) not compliant'
        self.assertEqual(intelligence['version_compliance'], expected)

    def test_compute_contact_display_data_version_compliance_exactly_50_percent(self):
        """Test version compliance boundary case when exactly 50% are compliant."""
        # Sample relay data with exactly 50% compliance (2 out of 4 = 50% compliant)
        test_members = [
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.7'},
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.8'},
            {'recommended_version': False, 'version_status': 'obsolete', 'version': '0.4.6.10'},
            {'recommended_version': False, 'version_status': 'unrecommended', 'version': '0.4.7.5'},
        ]
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', test_members
        )
        
        intelligence = result['operator_intelligence']
        
        # Should show red "Poor" when exactly 50% are compliant (not >50%)
        self.assertIn('version_compliance', intelligence)
        expected = '<span style="color: #c82333; font-weight: bold;">Poor</span>, 2 (50%) compliant, 2 (50%) not compliant'
        self.assertEqual(intelligence['version_compliance'], expected)

    def test_compute_contact_display_data_version_compliance_just_over_50_percent(self):
        """Test version compliance boundary case when just over 50% are compliant."""
        # Sample relay data with just over 50% compliance (3 out of 5 = 60% compliant)
        test_members = [
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.7'},
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.8'},
            {'recommended_version': True, 'version_status': 'experimental', 'version': '0.4.9.0-alpha'},
            {'recommended_version': False, 'version_status': 'obsolete', 'version': '0.4.6.10'},
            {'recommended_version': None, 'version_status': 'experimental', 'version': '0.4.9.1-alpha'},
        ]
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', test_members
        )
        
        intelligence = result['operator_intelligence']
        
        # Should show orange "Partial" when just over 50% are compliant
        self.assertIn('version_compliance', intelligence)
        expected = '<span style="color: #cc9900; font-weight: bold;">Partial</span>, 3 (60%) compliant, 1 (20%) not compliant, 1 (20%) unknown'
        self.assertEqual(intelligence['version_compliance'], expected)

    def test_compute_contact_display_data_version_compliance_zero_compliant(self):
        """Test version compliance when no relays are compliant."""
        # Sample relay data with no compliant relays
        test_members = [
            {'recommended_version': False, 'version_status': 'obsolete', 'version': '0.4.6.10'},
            {'recommended_version': False, 'version_status': 'unrecommended', 'version': '0.4.7.5'},
            {'recommended_version': None, 'version_status': 'experimental', 'version': '0.4.9.0-alpha'},
        ]
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', test_members
        )
        
        intelligence = result['operator_intelligence']
        
        # Should show red "Poor" when 0% are compliant
        self.assertIn('version_compliance', intelligence)
        expected = '<span style="color: #c82333; font-weight: bold;">Poor</span>, 0 (0%) compliant, 2 (67%) not compliant, 1 (33%) unknown'
        self.assertEqual(intelligence['version_compliance'], expected)

    def test_compute_contact_display_data_version_status_all_recommended(self):
        """Test version status with green 'All' when all relays have recommended status."""
        # Sample relay data with all recommended status
        test_members = [
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.7'},
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.8'},
            {'recommended_version': False, 'version_status': 'recommended', 'version': '0.4.8.9'},
        ]
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', test_members
        )
        
        intelligence = result['operator_intelligence']
        
        # Should show green "All" when all relays have recommended status
        self.assertIn('version_status', intelligence)
        expected = '<span style="color: #2e7d2e; font-weight: bold;">All</span>, <span title="Recommended versions: 0.4.8.7, 0.4.8.8, 0.4.8.9" style="cursor: help;">3 (100%) recommended</span>'
        self.assertEqual(intelligence['version_status'], expected)

    def test_compute_contact_display_data_version_status_partial_recommended(self):
        """Test version status with orange 'Partial' when >50% but not 100% have recommended status."""
        # Sample relay data with partial recommended status (3 out of 4 = 75% recommended)
        test_members = [
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.7'},
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.8'},
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.9'},
            {'recommended_version': False, 'version_status': 'obsolete', 'version': '0.4.6.10'},
        ]
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', test_members
        )
        
        intelligence = result['operator_intelligence']
        
        # Should show orange "Partial" when >50% but not 100% have recommended status
        self.assertIn('version_status', intelligence)
        expected = '<span style="color: #cc9900; font-weight: bold;">Partial</span>, <span title="Recommended versions: 0.4.8.7, 0.4.8.8, 0.4.8.9" style="cursor: help;">3 (75%) recommended</span>, <span title="Obsolete versions: 0.4.6.10" style="cursor: help;">1 (25%) obsolete</span>'
        self.assertEqual(intelligence['version_status'], expected)

    def test_compute_contact_display_data_version_status_poor_recommended(self):
        """Test version status with red 'Poor' when ≤50% have recommended status."""
        # Sample relay data with poor recommended status (1 out of 4 = 25% recommended)
        test_members = [
            {'recommended_version': True, 'version_status': 'recommended', 'version': '0.4.8.7'},
            {'recommended_version': False, 'version_status': 'obsolete', 'version': '0.4.6.10'},
            {'recommended_version': False, 'version_status': 'obsolete', 'version': '0.4.6.11'},
            {'recommended_version': None, 'version_status': 'experimental', 'version': '0.4.9.0-alpha'},
        ]
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', test_members
        )
        
        intelligence = result['operator_intelligence']
        
        # Should show red "Poor" when ≤50% have recommended status
        self.assertIn('version_status', intelligence)
        expected = '<span style="color: #c82333; font-weight: bold;">Poor</span>, <span title="Recommended versions: 0.4.8.7" style="cursor: help;">1 (25%) recommended</span>, <span title="Experimental versions: 0.4.9.0-alpha" style="cursor: help;">1 (25%) experimental</span>, <span title="Obsolete versions: 0.4.6.10, 0.4.6.11" style="cursor: help;">2 (50%) obsolete</span>'
        self.assertEqual(intelligence['version_status'], expected)

    def test_compute_contact_display_data_version_status_zero_recommended(self):
        """Test version status when no relays have recommended status."""
        # Sample relay data with no recommended status
        test_members = [
            {'recommended_version': False, 'version_status': 'obsolete', 'version': '0.4.6.10'},
            {'recommended_version': False, 'version_status': 'unrecommended', 'version': '0.4.7.5'},
            {'recommended_version': None, 'version_status': 'experimental', 'version': '0.4.9.0-alpha'},
        ]
        
        result = self.relays._compute_contact_display_data(
            self.sample_relay_data, 'MB/s', self.sample_reliability, 'test_contact_hash', test_members
        )
        
        intelligence = result['operator_intelligence']
        
        # Should show red "Poor" when 0% have recommended status
        self.assertIn('version_status', intelligence)
        expected = '<span style="color: #c82333; font-weight: bold;">Poor</span>, <span title="Recommended versions" style="cursor: help;">0 (0%) recommended</span>, <span title="Experimental versions: 0.4.9.0-alpha" style="cursor: help;">1 (33%) experimental</span>, <span title="Obsolete versions: 0.4.6.10" style="cursor: help;">1 (33%) obsolete</span>, <span title="Unrecommended versions: 0.4.7.5" style="cursor: help;">1 (33%) unrecommended</span>'
        self.assertEqual(intelligence['version_status'], expected)


if __name__ == '__main__':
    unittest.main()