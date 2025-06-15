#!/usr/bin/env python3

import unittest
from unittest.mock import Mock, patch
import sys
import os
from jinja2 import Environment, FileSystemLoader, select_autoescape
import re

# Add the allium directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'allium'))

from lib.relays import Relays


class TestAROIPaginationSystem(unittest.TestCase):
    """Comprehensive tests for AROI leaderboard pagination system."""
    
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
                self.mock_leaderboards[category].append((
                    f'operator{i+1}@example.com',
                    {
                        'contact': f'operator{i+1}@example.com',
                        'total_relays': 10 + i,
                        'bandwidth': 1000000 + (i * 100000),
                        'consensus_weight': 0.01 + (i * 0.001),
                        'rank': i + 1
                    }
                ))
        
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
        
        # Test section headings include emoji and rank information
        self.assertIn('🚀 Ranks 1-10', rendered)  # Bandwidth
        self.assertIn('⚖️ Ranks 11-20', rendered)  # Consensus weight
        self.assertIn('🌈 Ranks 21-25', rendered)  # Most diverse

    def test_fallback_no_data_handling(self):
        """Test pagination behavior when category has no data."""
        # Create context with empty leaderboard data
        empty_context = self.template_context.copy()
        empty_context['relays']['json']['aroi_leaderboards']['leaderboards']['bandwidth'] = []
        
        template = self.jinja_env.get_template('aroi-leaderboards.html')
        rendered = template.render(**empty_context)
        
        # Should display "No bandwidth data available" message
        self.assertIn('No bandwidth data available', rendered)
        
        # Should not display pagination navigation for empty category
        bandwidth_section = re.search(r'<section id="bandwidth".*?</section>', rendered, re.DOTALL)
        if bandwidth_section:
            self.assertNotIn('pagination-nav-bottom', bandwidth_section.group())

    def test_emoji_integration_with_pagination(self):
        """Test that emojis are properly integrated in pagination headers."""
        template = self.jinja_env.get_template('aroi-leaderboards.html')
        rendered = template.render(**self.template_context)
        
        # Test emoji integration in category headers and pagination headers
        expected_emojis = {
            'most_diverse': '🌈',
            'platform_diversity': '💻', 
            'non_eu_leaders': '🌍',
            'frontier_builders': '🏴‍☠️',
            'network_veterans': '🏆',
            'reliability_masters': '⏰',
            'legacy_titans': '👑'
        }
        
        for category, emoji in expected_emojis.items():
            with self.subTest(category=category):
                # Should find emoji in pagination headers
                pattern = f'{emoji} Ranks \\d+-\\d+'
                self.assertTrue(re.search(pattern, rendered), 
                              f"Expected emoji pattern '{pattern}' not found for {category}")

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
        skeleton_path = os.path.join(os.path.dirname(__file__), '..', 'allium', 'templates', 'skeleton.html')
        with open(skeleton_path, 'r') as f:
            skeleton_content = f.read()
        
        # Verify key CSS classes for pagination are defined
        self.assertIn('.pagination-section', skeleton_content)
        self.assertIn('.pagination-nav-bottom', skeleton_content)
        self.assertIn(':target', skeleton_content)
        
        # Verify category-specific CSS exists
        self.assertIn('#bandwidth-1-10', skeleton_content)
        self.assertIn('#consensus_weight-1-10', skeleton_content)

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
        relays.json = {
            'aroi_leaderboards': {
                'leaderboards': {'bandwidth': [('test@example.com', {'rank': 1})]},
                'summary': {'categories': {'bandwidth': 'Bandwidth Contributed'}}
            }
        }
        relays.use_bits = False
        
        # Test that the pagination system works with real-world data structures
        template_dir = os.path.join(os.path.dirname(__file__), '..', 'allium', 'templates')
        jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        # Add custom filters for template compatibility
        from lib.relays import determine_unit_filter, format_bandwidth_with_unit, format_bandwidth_filter, format_time_ago
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