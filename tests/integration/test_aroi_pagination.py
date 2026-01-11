#!/usr/bin/env python3

import os
import re
import types
import unittest
from unittest.mock import Mock, patch

from jinja2 import Environment, FileSystemLoader, select_autoescape

from allium.lib.relays import Relays


class TestAROIPaginationSystem(unittest.TestCase):
    """Comprehensive tests for AROI leaderboard pagination system."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Set up Jinja2 environment
        template_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'allium', 'templates')
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        # Add custom filters for template compatibility
        from allium.lib.relays import determine_unit_filter, format_bandwidth_with_unit, format_bandwidth_filter, format_time_ago
        self.jinja_env.filters['determine_unit'] = determine_unit_filter
        self.jinja_env.filters['format_bandwidth_with_unit'] = format_bandwidth_with_unit
        self.jinja_env.filters['format_bandwidth'] = format_bandwidth_filter
        self.jinja_env.filters['format_time_ago'] = format_time_ago
        
        # Create mock AROI leaderboard data for all 12 categories
        self.mock_leaderboards = {}
        categories = [
            'bandwidth', 'consensus_weight', 'exit_authority', 'exit_operators',
            'guard_operators', 'most_diverse', 'platform_diversity', 'non_eu_leaders',
            'frontier_builders', 'network_veterans', 'reliability_masters', 'legacy_titans'
        ]
        
        for category in categories:
            # Create 25 mock entries per category to test pagination
            self.mock_leaderboards[category] = []
            for i in range(25):
                # Create a mock object with attributes that templates expect
                entry = types.SimpleNamespace()
                entry.contact_hash = f'hash{i+1}'
                entry.contact_info_escaped = f'operator{i+1}@example.com'
                entry.display_name = f'Operator{i+1}'
                entry.rank = i + 1
                entry.total_relays = 10 + i
                entry.measured_count = 5 + (i // 2)  # Actual integer, not Mock
                entry.total_bandwidth = f'{1.0 + (i * 0.1):.1f}'
                entry.bandwidth_unit = 'MB/s'
                entry.total_consensus_weight_pct = f'{1.0 + (i * 0.1):.1f}%'
                entry.exit_consensus_weight_pct = f'{0.5 + (i * 0.05):.1f}%'
                entry.guard_consensus_weight_pct = f'{0.5 + (i * 0.05):.1f}%'
                entry.exit_count = 5 + i
                entry.guard_count = 3 + i
                entry.middle_count = 2 + i
                entry.diversity_score = 50 + i
                entry.country_count = 2 + (i // 5)
                entry.platform_count = 1 + (i // 3)
                entry.unique_as_count = 1 + (i // 2)
                entry.non_linux_count = 1 + (i // 3)
                entry.non_eu_count = 1 + (i // 2)
                entry.non_eu_count_with_percentage = f'{1 + (i // 2)} ({50 + i}%)'
                entry.rare_country_count = 1 + (i // 10)
                entry.relays_in_rare_countries = 1 + (i // 8)
                entry.veteran_days = 100 + (i * 10)
                entry.veteran_score = (100 + (i * 10)) * (10 + i)
                entry.reliability_score = f'{90.0 + i:.1f}%'
                entry.reliability_average = f'{90.0 + i:.1f}%'
                entry.unique_ipv4_count = 10 + i
                entry.unique_ipv6_count = 5 + i
                # Add missing tooltip attributes
                entry.diversity_breakdown_tooltip = None
                entry.platform_breakdown_tooltip = None
                entry.geographic_breakdown_tooltip = 'Geographic expansion tooltip'
                entry.rare_country_tooltip = 'Rare country tooltip'
                entry.veteran_tooltip = 'Veteran tooltip'
                entry.reliability_tooltip = 'Reliability tooltip'
                entry.ip_address_tooltip = 'IP address tooltip'
                self.mock_leaderboards[category].append(entry)
        
        # Mock template context
        self.template_context = {
            'relays': {
                'json': {
                    'aroi_leaderboards': {
                        'leaderboards': self.mock_leaderboards,
                        'summary': {
                            'categories': {
                                'bandwidth': 'Bandwidth Contributed',
                                'consensus_weight': 'Network Heavyweight Rankings',
                                'exit_authority': 'Exit Authorities', 
                                'exit_operators': 'Exit Champions',
                                'guard_operators': 'Guard Gatekeepers',
                                'most_diverse': 'Most Diverse Operators',
                                'platform_diversity': 'Platform Diversity Heroes',
                                'non_eu_leaders': 'Non-EU Leaders',
                                'frontier_builders': 'Frontier Builders',
                                'network_veterans': 'Network Veterans',
                                'reliability_masters': 'Reliability Masters',
                                'legacy_titans': 'Legacy Titans'
                            },
                            'total_operators': 150,
                            'total_bandwidth_formatted': '1.5 GB/s',
                            'total_consensus_weight_pct': '25.5%',
                            'live_categories_count': 12,
                            'update_timestamp': '2025-06-15 01:00:00 UTC'
                        }
                    }
                },
                'use_bits': False
            },
            'page_ctx': {
                'path_prefix': './'
            }
        }

    def test_pagination_structure_all_categories(self):
        """Test that all 12 categories have proper pagination structure."""
        template = self.jinja_env.get_template('aroi-leaderboards.html')
        rendered = template.render(**self.template_context)
        
        categories = [
            'bandwidth', 'consensus_weight', 'exit_authority', 'exit_operators',
            'guard_operators', 'most_diverse', 'platform_diversity', 'non_eu_leaders', 
            'frontier_builders', 'network_veterans', 'reliability_masters', 'legacy_titans'
        ]
        
        for category in categories:
            with self.subTest(category=category):
                # Test pagination sections exist
                self.assertIn(f'id="{category}-1-10"', rendered)
                self.assertIn(f'id="{category}-11-20"', rendered)
                self.assertIn(f'id="{category}-21-25"', rendered)
                
                # Test pagination navigation links
                self.assertIn(f'href="#{category}-1-10"', rendered)
                self.assertIn(f'href="#{category}-11-20"', rendered)
                self.assertIn(f'href="#{category}-21-25"', rendered)

    def test_pagination_css_classes(self):
        """Test that pagination sections have correct CSS classes."""
        template = self.jinja_env.get_template('aroi-leaderboards.html')
        rendered = template.render(**self.template_context)
        
        # Test pagination-section class exists for all pages
        pagination_sections = re.findall(r'class="pagination-section"', rendered)
        # Should have 3 sections × 12 categories = 36 pagination sections
        self.assertEqual(len(pagination_sections), 36)
        
        # Test pagination navigation class exists
        navigation_sections = re.findall(r'class="pagination-nav-bottom"', rendered)
        # Should have 12 navigation sections (one per category)
        self.assertEqual(len(navigation_sections), 12)

    def test_data_distribution_across_pages(self):
        """Test that data is properly distributed across pagination pages."""
        template = self.jinja_env.get_template('aroi-leaderboards.html')
        rendered = template.render(**self.template_context)
        
        # Test bandwidth category data distribution (example)
        # Page 1 should have entries 1-10
        self.assertIn('operator1@example.com', rendered)
        self.assertIn('operator10@example.com', rendered)
        
        # All 25 operators should be present somewhere in the rendered output
        for i in range(1, 26):
            self.assertIn(f'operator{i}@example.com', rendered)

    def test_independent_category_pagination_urls(self):
        """Test that each category has independent pagination URLs."""
        template = self.jinja_env.get_template('aroi-leaderboards.html')
        rendered = template.render(**self.template_context)
        
        # Test that each category has unique URL fragments
        test_cases = [
            ('bandwidth', '#bandwidth-1-10'),
            ('consensus_weight', '#consensus_weight-11-20'),
            ('most_diverse', '#most_diverse-21-25'),
            ('reliability_masters', '#reliability_masters-1-10')
        ]
        
        for category, expected_url in test_cases:
            with self.subTest(category=category):
                self.assertIn(expected_url, rendered)

    def test_pagination_accessibility_and_titles(self):
        """Test pagination accessibility features and descriptive titles."""
        template = self.jinja_env.get_template('aroi-leaderboards.html')
        rendered = template.render(**self.template_context)
        
        # Test that pagination navigation has accessible text
        self.assertIn('1-10', rendered)
        self.assertIn('11-20', rendered) 
        self.assertIn('21-25', rendered)
        
        # Test section headings include rank information (emojis may vary)
        # Look for rank headers that actually exist in the output
        rank_pattern = r'Ranks \d+-\d+'
        rank_matches = re.findall(rank_pattern, rendered)
        self.assertGreater(len(rank_matches), 0, "Expected to find rank headers in pagination")
        
        # Test that some pagination sections are properly formed
        self.assertIn('pagination-section', rendered)
        self.assertIn('pagination-nav-bottom', rendered)

    def test_fallback_no_data_handling(self):
        """Test pagination behavior when category has no data."""
        # Create context with empty leaderboard data
        empty_context = self.template_context.copy()
        empty_context['relays']['json']['aroi_leaderboards']['leaderboards']['bandwidth'] = []
        
        template = self.jinja_env.get_template('aroi-leaderboards.html')
        rendered = template.render(**empty_context)
        
        # Should display fallback message when category has no data
        # The template macro shows "No data available for this category."
        self.assertIn('No data available for this category', rendered)
        
        # Should not display pagination navigation for empty category
        bandwidth_section = re.search(r'<section id="bandwidth".*?</section>', rendered, re.DOTALL)
        if bandwidth_section:
            self.assertNotIn('pagination-nav-bottom', bandwidth_section.group())

    def test_emoji_integration_with_pagination(self):
        """Test that emojis are properly integrated in pagination headers."""
        template = self.jinja_env.get_template('aroi-leaderboards.html')
        rendered = template.render(**self.template_context)
        
        # Test emoji integration in category headers and pagination headers
        # Only test for emojis that are actually present in the categories we have data for
        categories_with_data = self.mock_leaderboards.keys()
        expected_emojis = {
            'bandwidth': '🚀',  # This is a category we have data for
            'consensus_weight': '⚖️',  # This is a category we have data for
            'most_diverse': '🌈',
        }
        
        for category, emoji in expected_emojis.items():
            if category in categories_with_data:
                with self.subTest(category=category):
                    # Should find emoji somewhere in the rendered output (headers, tables, etc.)
                    # Use more flexible pattern that matches emoji in any context
                    self.assertIn(emoji, rendered, 
                                  f"Expected emoji '{emoji}' not found for {category}")
        
        # Test that at least some pagination headers with emojis exist
        rank_pattern = r'Ranks \d+-\d+'
        self.assertTrue(re.search(rank_pattern, rendered), 
                      "Expected at least some pagination rank headers")

    def test_template_macro_integration(self):
        """Test that pagination integrates correctly with template macros."""
        template = self.jinja_env.get_template('aroi-leaderboards.html')
        rendered = template.render(**self.template_context)
        
        # Test that template macros are being called within pagination sections
        # Look for table structures that indicate macro execution
        self.assertIn('table-responsive', rendered)
        self.assertIn('aroi-rankings-table', rendered)
        
        # Test that generic_ranking_table_paginated macro is used
        # This should generate table headers and rows
        self.assertIn('<th title=', rendered)  # Table headers from macros
        self.assertIn('Operator (AROI)', rendered)  # Standard header from macro

    def test_skeleton_css_integration(self):
        """Test that pagination system integrates with skeleton.html CSS."""
        # Read skeleton.html to verify CSS classes are defined
        skeleton_path = os.path.join(os.path.dirname(__file__), '..', '..', 'allium', 'templates', 'skeleton.html')
        with open(skeleton_path, 'r') as f:
            skeleton_content = f.read()
        
        # Verify key CSS classes for pagination are defined
        self.assertIn('.pagination-section', skeleton_content)
        self.assertIn('.pagination-nav-bottom', skeleton_content)
        self.assertIn(':target', skeleton_content)
        
        # Verify CSS uses dynamic patterns for category-specific targeting
        # The template generates IDs like #bandwidth-1-10, but CSS targets them
        # using attribute selectors like [id$="-1-10"]
        self.assertIn('[id$="-1-10"]', skeleton_content)

    def test_pagination_performance_structure(self):
        """Test that pagination structure is optimized for performance."""
        template = self.jinja_env.get_template('aroi-leaderboards.html')
        rendered = template.render(**self.template_context)
        
        # Test that data is split correctly (not rendering all data at once)
        # Each category should have exactly 3 pagination sections
        categories = ['bandwidth', 'consensus_weight', 'most_diverse']
        
        for category in categories:
            with self.subTest(category=category):
                # Count pagination sections for this category
                pattern = f'id="{category}-\\d+-\\d+"'
                matches = re.findall(pattern, rendered)
                self.assertEqual(len(matches), 3, 
                               f"Expected 3 pagination sections for {category}, found {len(matches)}")

    def test_url_fragment_consistency(self):
        """Test that URL fragments follow consistent naming convention."""
        template = self.jinja_env.get_template('aroi-leaderboards.html')
        rendered = template.render(**self.template_context)
        
        # Test URL fragment pattern: #{category}-{start}-{end}
        expected_patterns = [
            r'#\w+-1-10',   # First page pattern
            r'#\w+-11-20',  # Second page pattern 
            r'#\w+-21-25'   # Third page pattern
        ]
        
        for pattern in expected_patterns:
            with self.subTest(pattern=pattern):
                matches = re.findall(pattern, rendered)
                # Should find pattern for all 12 categories
                self.assertGreaterEqual(len(matches), 12,
                                       f"Expected at least 12 matches for pattern {pattern}")


class TestPaginationIntegration(unittest.TestCase):
    """Integration tests for pagination with the complete system."""
    
    @patch('allium.lib.relays.Relays._generate_aroi_leaderboards')
    def test_pagination_with_real_template_context(self, mock_aroi):
        """Test pagination with realistic template context structure."""
        # Mock AROI leaderboards generation
        mock_aroi.return_value = None
        
        # Create a mock Relays instance
        relays = Mock()
        # Create mock entry with all required attributes
        mock_entry = types.SimpleNamespace()
        mock_entry.contact_hash = 'test_hash'
        mock_entry.contact_info_escaped = 'test@example.com'
        mock_entry.display_name = 'TestOperator'
        mock_entry.rank = 1
        mock_entry.total_relays = 10
        mock_entry.measured_count = 5
        mock_entry.total_bandwidth = '1.5'
        mock_entry.bandwidth_unit = 'MB/s'
        mock_entry.total_consensus_weight_pct = '1.2%'
        mock_entry.exit_count = 2
        mock_entry.guard_count = 3
        mock_entry.middle_count = 5
        mock_entry.country_count = 2
        mock_entry.platform_count = 1
        mock_entry.non_linux_count = 1
        mock_entry.countries = ['US', 'DE']
        mock_entry.platforms = ['Linux']
        mock_entry.diversity_score = 15
        mock_entry.unique_as_count = 3
        mock_entry.veteran_days = 365
        mock_entry.veteran_score = 3650
        mock_entry.reliability_score = '98.5%'
        mock_entry.reliability_average = '98.5%'
        # Add missing tooltip attributes
        mock_entry.diversity_breakdown_tooltip = 'Diversity breakdown tooltip'
        mock_entry.platform_breakdown_tooltip = 'Platform breakdown tooltip'
        mock_entry.geographic_breakdown_tooltip = 'Geographic breakdown tooltip'
        mock_entry.rare_country_tooltip = 'Rare country tooltip'
        mock_entry.veteran_tooltip = 'Veteran tooltip'
        mock_entry.reliability_tooltip = 'Reliability tooltip'
        mock_entry.ip_address_tooltip = 'IP address tooltip'
        
        relays.json = {
            'aroi_leaderboards': {
                'leaderboards': {'bandwidth': [mock_entry]},
                'summary': {'categories': {'bandwidth': 'Bandwidth Contributed'}}
            }
        }
        relays.use_bits = False
        
        # Test that the pagination system works with real-world data structures
        template_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'allium', 'templates')
        jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        # Add custom filters for template compatibility
        from allium.lib.relays import determine_unit_filter, format_bandwidth_with_unit, format_bandwidth_filter, format_time_ago
        jinja_env.filters['determine_unit'] = determine_unit_filter
        jinja_env.filters['format_bandwidth_with_unit'] = format_bandwidth_with_unit
        jinja_env.filters['format_bandwidth'] = format_bandwidth_filter
        jinja_env.filters['format_time_ago'] = format_time_ago
        
        template = jinja_env.get_template('aroi-leaderboards.html')
        context = {
            'relays': relays,
            'page_ctx': {'path_prefix': './'}
        }
        
        # Should render without errors
        rendered = template.render(**context)
        self.assertIsInstance(rendered, str)
        self.assertGreater(len(rendered), 0)


if __name__ == '__main__':
    unittest.main()