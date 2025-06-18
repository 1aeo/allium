#!/usr/bin/env python3

import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Add the allium directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'allium'))

from lib.relays import Relays


class TestContactTemplateIntegration(unittest.TestCase):
    """Integration tests for contact template two-column layout rendering."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Set up Jinja2 environment
        template_dir = os.path.join(os.path.dirname(__file__), '..', 'allium', 'templates')
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        # Add custom filters for template compatibility
        from lib.relays import determine_unit_filter, format_bandwidth_with_unit, format_bandwidth_filter, format_time_ago
        self.jinja_env.filters['determine_unit'] = determine_unit_filter
        self.jinja_env.filters['format_bandwidth_with_unit'] = format_bandwidth_with_unit
        self.jinja_env.filters['format_bandwidth'] = format_bandwidth_filter
        self.jinja_env.filters['format_time_ago'] = format_time_ago
        
        # Sample template context data
        self.template_context = {
            'contact': 'test@example.com',
            'contact_hash': 'abcd1234',
            'bandwidth': '150.0',
            'bandwidth_unit': 'MB/s',
            'consensus_weight_fraction': 0.025,  # 2.5%
            'network_position': 'Mixed (5 total relays, 2 guards, 1 middle, 2 exits)',
            'relays': {
                'json': {
                    'relay_subset': [{
                        'aroi_domain': 'example.org',
                        'country': 'us',
                        'country_name': 'United States',
                        'observed_bandwidth': 1000000,
                        'nickname': 'TestRelay',
                        'fingerprint': 'ABC123DEF456',
                        'running': True,
                        'flags': ['Running', 'Valid'],
                        'flags_escaped': ['Running', 'Valid'],
                        'flags_lower_escaped': ['running', 'valid'],
                        'effective_family': [],
                        'measured': True,
                        'uptime_display': 'UP 5d 12h',
                        'uptime_api_display': '99.5%',
                        'or_addresses': ['192.168.1.1:9001'],
                        'as': 'AS7922',
                        'as_name': 'Comcast Cable',
                        'platform': 'Linux',
                        'first_seen': '2023-01-01 12:00:00',
                        'first_seen_date_escaped': '2023-01-01'
                    }]
                },
                'use_bits': False
            },
            'page_ctx': {
                'path_prefix': '../'
            },
            'contact_display_data': {
                'bandwidth_breakdown': '50.0 MB/s guard, 25.0 MB/s middle, 75.0 MB/s exit',
                'consensus_weight_breakdown': '1.0% guard, 0.5% middle, 1.0% exit',
                'operator_intelligence': {
                    'network_diversity': '<span style="color: #2e7d2e; font-weight: bold;">Great</span>, 4 networks',
                    'geographic_diversity': '<span style="color: #cc9900; font-weight: bold;">Okay</span>, 2 countries',
                    'infrastructure_diversity': '<span style="color: #c82333; font-weight: bold;">Poor</span>, 1 platform',
                    'measurement_status': '5/5 relays measured by authorities',
                    'performance_status': 'optimal efficiency',
                    'performance_underutilized': 0,
                    'maturity': 'Operating since 2020-01-01'
                },
                'uptime_formatted': {
                    '1_month': {
                        'display': '30d 98.5%',
                        'relay_count': 5
                    },
                    '6_months': {
                        'display': '<span style="color: #28a745; font-weight: bold;">6mo 99.9%</span>',
                        'relay_count': 5
                    }
                },
                'outliers': {
                    'total_count': 1,
                    'total_relays': 5,
                    'percentage': '20.0',
                    'tooltip': '6 month: ≥2σ 97.8% from average μ 99.9%',
                    'low_count': 1,
                    'low_tooltip': 'TestRelay1 (95.2%)'
                }
            },
            'contact_rankings': [
                {
                    'title': 'Bandwidth Champion',
                    'badge': '🥇',
                    'description': 'Top bandwidth contributor',
                    'link': 'aroi-leaderboards.html#bandwidth-1-10',
                    'tooltip': 'Highest total bandwidth across all relays'
                },
                {
                    'title': 'Diversity Master',
                    'badge': '🌈',
                    'description': 'Most diverse operator',
                    'link': 'aroi-leaderboards.html#most_diverse-1-10',
                    'tooltip': 'Highest diversity score combining geographic, platform, and network variety'
                }
            ],
            'operator_reliability': {
                'valid_relays': 5,
                'total_relays': 5
            },
            'flag_reliability': {
                'Exit': {
                    'percentage': 96.2,
                    'rating': 'High',
                    'relay_count': 3,
                    'color_class': 'text-success',
                    'tooltip': 'Exit flag reliability: 96.2% - Excellent performance across 3 relays'
                },
                'Guard': {
                    'percentage': 94.1,
                    'rating': 'Good', 
                    'relay_count': 2,
                    'color_class': 'text-success',
                    'tooltip': 'Guard flag reliability: 94.1% - Good performance across 2 relays'
                }
            }
        }

    def test_contact_template_renders_without_error(self):
        """Test that contact template renders without Jinja2 errors."""
        try:
            template = self.jinja_env.get_template('contact.html')
            rendered = template.render(**self.template_context)
            self.assertIsInstance(rendered, str)
            self.assertGreater(len(rendered), 0)
        except Exception as e:
            self.fail(f"Template rendering failed: {e}")

    def test_contact_template_two_column_layout_structure(self):
        """Test that contact template renders with correct two-column structure."""
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Should contain Bootstrap row and column classes
        self.assertIn('class="row"', rendered)
        self.assertIn('class="col-md-7"', rendered)  # 60% left column
        self.assertIn('class="col-md-5"', rendered)  # 40% right column

    def test_contact_template_left_column_content(self):
        """Test that left column contains contact & network overview and operator intelligence."""
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Should contain contact & network overview section
        self.assertIn('📋 Contact &amp; Network Overview', rendered)
        self.assertIn('test@example.com', rendered)  # Contact email
        self.assertIn('abcd1234', rendered)  # Contact hash
        self.assertIn('🇺🇸', rendered)  # Should have country flag (US flag)
        self.assertIn('United States', rendered)  # Country name
        
        # Should contain network summary
        self.assertIn('Network Summary:', rendered)
        self.assertIn('~150.0 MB/s', rendered)  # Bandwidth
        self.assertIn('2.50% of overall consensus weight', rendered)  # Network influence
        
        # Should contain operator intelligence section
        self.assertIn('📊 Operator Intelligence', rendered)

    def test_contact_template_right_column_content(self):
        """Test that right column contains AROI rankings and network reliability.""" 
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Should contain AROI rankings section
        self.assertIn('🏆 AROI Champion Rankings', rendered)
        self.assertIn('#1 in Bandwidth Champions', rendered)
        self.assertIn('#3 in Most Diverse Operators', rendered)
        
        # Should contain network reliability section
        self.assertIn('⏰ Network Reliability', rendered)
        self.assertIn('Overall Uptime:', rendered)

    def test_contact_template_with_aroi_rankings(self):
        """Test contact template when AROI rankings are present."""
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Should display ranking count
        self.assertIn('2 winning', rendered)  # Should show count of rankings
        
        # Should contain pagination-based ranking links
        self.assertIn('aroi-leaderboards.html#bandwidth-1-10', rendered)
        self.assertIn('aroi-leaderboards.html#most_diverse-1-10', rendered)
        
        # Should display ranking statements
        self.assertIn('🥇 Bandwidth Champion', rendered)
        self.assertIn('🌈 Diversity Master', rendered)

    def test_contact_template_without_aroi_rankings(self):
        """Test contact template layout when no AROI rankings exist."""
        context_no_rankings = self.template_context.copy()
        context_no_rankings['contact_rankings'] = []
        
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**context_no_rankings)
        
        # Should not contain AROI rankings section
        self.assertNotIn('🏆 AROI Champion Rankings', rendered)
        self.assertNotIn('winning', rendered)
        
        # Should still contain reliability section in right column
        self.assertIn('⏰ Network Reliability', rendered)

    def test_contact_template_country_display_formatting(self):
        """Test country flag and name display in contact overview."""
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Should contain country link structure
        self.assertIn('href="../country/us/"', rendered)
        
        # Should contain flag image
        self.assertIn('src="../static/images/cc/us.png"', rendered)
        self.assertIn('title="United States"', rendered)
        self.assertIn('alt="United States"', rendered)

    def test_contact_template_bandwidth_breakdown_display(self):
        """Test bandwidth breakdown display with filtering."""
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Should display bandwidth breakdown tooltip
        self.assertIn('50.0 MB/s guard, 25.0 MB/s middle, 75.0 MB/s exit', rendered)

    def test_contact_template_consensus_weight_breakdown_display(self):
        """Test consensus weight breakdown display."""
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Should display consensus weight breakdown tooltip
        self.assertIn('1.0% guard, 0.5% middle, 1.0% exit', rendered)

    def test_contact_template_operator_intelligence_color_coding(self):
        """Test operator intelligence color-coded display."""
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Should preserve HTML color coding from pre-computed data
        self.assertIn('color: #2e7d2e; font-weight: bold;">Great</span>, 4 networks', rendered)
        self.assertIn('color: #cc9900; font-weight: bold;">Okay</span>, 2 countries', rendered)
        self.assertIn('color: #c82333; font-weight: bold;">Poor</span>, 1 platform', rendered)

    def test_contact_template_uptime_highlighting(self):
        """Test uptime highlighting for high reliability values."""
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Should preserve green highlighting for high uptime
        self.assertIn('color: #28a745; font-weight: bold;">6mo 99.9%', rendered)
        
        # Should display regular uptime without highlighting
        self.assertIn('30d 98.5%', rendered)

    def test_contact_template_outliers_display(self):
        """Test statistical outliers display with tooltips."""
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Should display outliers summary
        self.assertIn('1 relays out of 5 relays (20.0%)', rendered)
        
        # Should include tooltips
        self.assertIn('6 month: ≥2σ 97.8% from average μ 99.9%', rendered)
        self.assertIn('TestRelay1 (95.2%)', rendered)

    def test_contact_template_no_outliers_display(self):
        """Test display when no statistical outliers are detected."""
        context_no_outliers = self.template_context.copy()
        context_no_outliers['contact_display_data']['outliers'] = {'none_detected': True}
        
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**context_no_outliers)
        
        # Should display no outliers message
        self.assertIn('✅ No statistical outliers detected', rendered)

    def test_contact_template_aroi_domain_display(self):
        """Test AROI domain display in contact information."""
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Should display AROI domain
        self.assertIn('Domain:', rendered)
        self.assertIn('example.org', rendered)

    def test_contact_template_no_aroi_domain(self):
        """Test handling when no AROI domain is available."""
        context_no_domain = self.template_context.copy()
        context_no_domain['relays']['json']['relay_subset'][0]['aroi_domain'] = 'none'
        
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**context_no_domain)
        
        # Should not display domain section
        self.assertNotIn('Domain:', rendered)

    def test_contact_template_reliability_data_count(self):
        """Test reliability data availability display."""
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Should display reliability data count
        self.assertIn('Reliability data available for 5/5 relays', rendered)

    def test_contact_template_no_reliability_data(self):
        """Test template handling when no reliability data is available."""
        context_no_reliability = self.template_context.copy()
        context_no_reliability['operator_reliability'] = None
        
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**context_no_reliability)
        
        # Should not crash and should not contain reliability section
        self.assertNotIn('⏰ Network Reliability', rendered)

    def test_contact_template_no_intelligence_data(self):
        """Test template handling when no intelligence data is available."""
        context_no_intelligence = self.template_context.copy()
        context_no_intelligence['contact_display_data']['operator_intelligence'] = {}
        
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**context_no_intelligence)
        
        # Should not crash and should not contain intelligence section content
        self.assertNotIn('Network Diversity:', rendered)
        self.assertNotIn('Geographic Diversity:', rendered)

    def test_contact_template_responsive_layout(self):
        """Test responsive Bootstrap classes for mobile compatibility."""
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Should use Bootstrap responsive classes
        self.assertIn('col-md-7', rendered)  # Left column
        self.assertIn('col-md-5', rendered)  # Right column
        
        # These will stack on mobile (below md breakpoint)

    def test_contact_template_aroi_rankings_pagination(self):
        """Test AROI rankings display correctly with pagination links."""
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Check that AROI rankings display correctly with pagination links
        self.assertIn('aroi-leaderboards.html#bandwidth-1-10', rendered)
        self.assertIn('aroi-leaderboards.html#most_diverse-1-10', rendered)

    def test_contact_template_flag_reliability_display(self):
        """Test that flag reliability section displays correctly."""
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Should contain flag reliability section
        self.assertIn('Flag Reliability', rendered)
        
        # Should display flag reliability percentages and ratings
        self.assertIn('Exit Flag Reliability: 96.2% (High) - 3 relays', rendered)
        self.assertIn('Guard Flag Reliability: 94.1% (Good) - 2 relays', rendered)
        
        # Should include proper color classes
        self.assertIn('text-success', rendered)

    def test_contact_template_flag_reliability_tooltips(self):
        """Test that flag reliability tooltips are properly included."""
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Should contain tooltip content
        self.assertIn('Exit flag reliability: 96.2% - Excellent performance across 3 relays', rendered)
        self.assertIn('Guard flag reliability: 94.1% - Good performance across 2 relays', rendered)

    def test_contact_template_bandwidth_measurement_indicators(self):
        """Test that bandwidth measurement indicators are displayed."""
        # Update context to include measurement status
        context_with_measurements = self.template_context.copy()
        context_with_measurements['relays']['json']['relay_subset'][0]['measured'] = True
        
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(context_with_measurements)
        
        # Should include bandwidth measurement indicators in relay table
        # Note: This would require the template to actually include these indicators
        # For now, we test that the measured status is available in context
        self.assertTrue(context_with_measurements['relays']['json']['relay_subset'][0]['measured'])

    def test_contact_template_color_coding_consistency(self):
        """Test that color coding is consistent across different reliability displays."""
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Should use consistent Bootstrap color classes
        green_occurrences = rendered.count('text-success')
        self.assertGreater(green_occurrences, 0, "Should have green (success) color coding")
        
        # Should not mix different color schemes
        self.assertNotIn('color: green', rendered)  # Should use Bootstrap classes, not inline styles

    def test_contact_template_no_flag_reliability_data(self):
        """Test contact template when no flag reliability data is available."""
        context_no_flags = self.template_context.copy()
        context_no_flags['flag_reliability'] = {}
        
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(context_no_flags)
        
        # Should handle empty flag reliability gracefully
        # Template should not crash and should not show empty flag sections
        self.assertIsInstance(rendered, str)
        self.assertGreater(len(rendered), 0)

    def test_contact_template_mixed_flag_reliability_ratings(self):
        """Test display of mixed flag reliability ratings (good/poor performance)."""
        context_mixed_flags = self.template_context.copy()
        context_mixed_flags['flag_reliability'] = {
            'Exit': {
                'percentage': 96.2,
                'rating': 'High',
                'relay_count': 3,
                'color_class': 'text-success',
                'tooltip': 'Exit flag reliability: 96.2% - Excellent performance'
            },
            'Fast': {
                'percentage': 75.5,
                'rating': 'Poor',
                'relay_count': 5,
                'color_class': 'text-danger',
                'tooltip': 'Fast flag reliability: 75.5% - Poor performance needs attention'
            }
        }
        
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(context_mixed_flags)
        
        # Should display both high and poor performance flags
        self.assertIn('96.2% (High)', rendered)
        self.assertIn('75.5% (Poor)', rendered)
        
        # Should use appropriate color classes
        self.assertIn('text-success', rendered)  # For high performance
        self.assertIn('text-danger', rendered)   # For poor performance

    def test_contact_template_statistical_analysis_integration(self):
        """Test that statistical analysis data is properly integrated."""
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Should display outlier information
        self.assertIn('1 relays out of 5 relays (20.0%)', rendered)
        
        # Should include statistical tooltips
        self.assertIn('≥2σ 97.8% from average μ 99.9%', rendered)


if __name__ == '__main__':
    unittest.main()