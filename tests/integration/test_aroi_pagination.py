#!/usr/bin/env python3
"""Tests for the AROI leaderboard pagination system.

All fixtures live in tests/conftest.py (backed by helpers.fixtures) so the
mock entry schema and the category matrix cannot drift between test suites:

- ``mock_aroi_leaderboard_entry`` — shared mock entry factory
- ``mock_aroi_leaderboards`` — 25 entries per paginated category
- ``aroi_template_context`` / ``rendered_aroi_leaderboards`` — rendered page
- ``jinja_env`` — template environment with custom filters
"""

import os
import re
from unittest.mock import Mock, patch

from helpers.fixtures import AROI_PAGINATED_CATEGORIES


class TestAROIPaginationSystem:
    """Comprehensive tests for AROI leaderboard pagination system."""

    def test_pagination_structure_all_categories(self, rendered_aroi_leaderboards):
        """All paginated categories have proper pagination structure."""
        rendered = rendered_aroi_leaderboards
        for category in AROI_PAGINATED_CATEGORIES:
            # Pagination sections exist
            assert f'id="{category}-1-10"' in rendered, category
            assert f'id="{category}-11-20"' in rendered, category
            assert f'id="{category}-21-25"' in rendered, category

            # Pagination navigation links exist
            assert f'href="#{category}-1-10"' in rendered, category
            assert f'href="#{category}-11-20"' in rendered, category
            assert f'href="#{category}-21-25"' in rendered, category

    def test_pagination_css_classes(self, rendered_aroi_leaderboards):
        """Pagination sections have correct CSS classes."""
        # 3 sections x N categories pagination sections
        pagination_sections = re.findall(r'class="pagination-section"', rendered_aroi_leaderboards)
        assert len(pagination_sections) == 3 * len(AROI_PAGINATED_CATEGORIES)

        # One navigation section per category
        navigation_sections = re.findall(r'class="pagination-nav-bottom"', rendered_aroi_leaderboards)
        assert len(navigation_sections) == len(AROI_PAGINATED_CATEGORIES)

    def test_data_distribution_across_pages(self, rendered_aroi_leaderboards):
        """Data is properly distributed across pagination pages."""
        # Page 1 should have entries 1-10
        assert 'operator1@example.com' in rendered_aroi_leaderboards
        assert 'operator10@example.com' in rendered_aroi_leaderboards

        # All 25 operators should be present somewhere in the rendered output
        for i in range(1, 26):
            assert f'operator{i}@example.com' in rendered_aroi_leaderboards

    def test_independent_category_pagination_urls(self, rendered_aroi_leaderboards):
        """Each category has independent pagination URLs."""
        test_cases = [
            ('bandwidth', '#bandwidth-1-10'),
            ('consensus_weight', '#consensus_weight-11-20'),
            ('most_diverse', '#most_diverse-21-25'),
            ('reliability_masters', '#reliability_masters-1-10')
        ]

        for category, expected_url in test_cases:
            assert expected_url in rendered_aroi_leaderboards, category

    def test_pagination_accessibility_and_titles(self, rendered_aroi_leaderboards):
        """Pagination accessibility features and descriptive titles."""
        # Pagination navigation has accessible text
        assert '1-10' in rendered_aroi_leaderboards
        assert '11-20' in rendered_aroi_leaderboards
        assert '21-25' in rendered_aroi_leaderboards

        # Section headings include rank information (emojis may vary)
        rank_matches = re.findall(r'Ranks \d+-\d+', rendered_aroi_leaderboards)
        assert len(rank_matches) > 0, "Expected to find rank headers in pagination"

        # Some pagination sections are properly formed
        assert 'pagination-section' in rendered_aroi_leaderboards
        assert 'pagination-nav-bottom' in rendered_aroi_leaderboards

    def test_fallback_no_data_handling(self, jinja_env, aroi_template_context):
        """Pagination behavior when category has no data."""
        aroi_template_context['relays']['json']['aroi_leaderboards']['leaderboards']['bandwidth'] = []

        template = jinja_env.get_template('aroi-leaderboards.html')
        rendered = template.render(**aroi_template_context)

        # Should display fallback message when category has no data
        assert 'No data available for this category' in rendered

        # Should not display pagination navigation for empty category
        bandwidth_section = re.search(r'<section id="bandwidth".*?</section>', rendered, re.DOTALL)
        if bandwidth_section:
            assert 'pagination-nav-bottom' not in bandwidth_section.group()

    def test_emoji_integration_with_pagination(self, rendered_aroi_leaderboards, mock_aroi_leaderboards):
        """Emojis are properly integrated in pagination headers."""
        expected_emojis = {
            'bandwidth': '🚀',
            'consensus_weight': '⚖️',
            'most_diverse': '🌈',
        }

        for category, emoji in expected_emojis.items():
            if category in mock_aroi_leaderboards:
                assert emoji in rendered_aroi_leaderboards, \
                    f"Expected emoji '{emoji}' not found for {category}"

        # At least some pagination headers with rank info exist
        assert re.search(r'Ranks \d+-\d+', rendered_aroi_leaderboards), \
            "Expected at least some pagination rank headers"

    def test_template_macro_integration(self, rendered_aroi_leaderboards):
        """Pagination integrates correctly with template macros."""
        # Table structures that indicate macro execution
        assert 'table-responsive' in rendered_aroi_leaderboards
        assert 'aroi-rankings-table' in rendered_aroi_leaderboards

        # generic_ranking_table_paginated macro generates table headers and rows
        assert '<th title=' in rendered_aroi_leaderboards
        assert 'Operator (AROI)' in rendered_aroi_leaderboards

    def test_skeleton_css_integration(self):
        """Pagination CSS is defined in AROI page CSS.

        Note: Pagination CSS was extracted from aroi-leaderboards.html template
        to external aroi-leaderboards.css file in Phase 5 CSS extraction.
        """
        css_path = os.path.join(os.path.dirname(__file__), '..', '..', 'allium', 'static', 'css', 'aroi-leaderboards.css')
        with open(css_path, 'r') as f:
            css_content = f.read()

        # Key CSS classes for pagination are defined in AROI CSS
        assert '.pagination-section' in css_content
        assert '.pagination-nav-bottom' in css_content
        assert ':target' in css_content

        # CSS uses dynamic patterns for category-specific targeting
        # (template generates IDs like #bandwidth-1-10, CSS targets them
        # using attribute selectors like [id$="-1-10"])
        assert '[id$="-1-10"]' in css_content

        # Backward-compatible pagination approach:
        # - Flex container for visual reordering (DOM order != visual order)
        assert '.pagination-container' in css_content
        # - Sibling combinator hides default page when another is :target
        #   (no :has() needed — works on all Tor Browser versions)
        assert '.pagination-section:target ~ .pagination-section:not(:target)' in css_content

        # All champion badge classes have CSS definitions
        assert '.aroi-champion-total-data' in css_content
        assert '.aroi-champion-validation' in css_content

        # skeleton.html has the page_css block mechanism
        skeleton_path = os.path.join(os.path.dirname(__file__), '..', '..', 'allium', 'templates', 'skeleton.html')
        with open(skeleton_path, 'r') as f:
            skeleton_content = f.read()
        assert '{% block page_css_link %}' in skeleton_content

    def test_pagination_performance_structure(self, rendered_aroi_leaderboards):
        """Pagination structure is optimized for performance."""
        # Each category should have exactly 3 pagination sections
        for category in ['bandwidth', 'consensus_weight', 'most_diverse']:
            pattern = f'id="{category}-\\d+-\\d+"'
            matches = re.findall(pattern, rendered_aroi_leaderboards)
            assert len(matches) == 3, \
                f"Expected 3 pagination sections for {category}, found {len(matches)}"

    def test_url_fragment_consistency(self, rendered_aroi_leaderboards):
        """URL fragments follow consistent naming convention."""
        # URL fragment pattern: #{category}-{start}-{end}
        expected_patterns = [
            r'#\w+-1-10',   # First page pattern
            r'#\w+-11-20',  # Second page pattern
            r'#\w+-21-25'   # Third page pattern
        ]

        for pattern in expected_patterns:
            matches = re.findall(pattern, rendered_aroi_leaderboards)
            # Should find pattern for every paginated category
            assert len(matches) >= len(AROI_PAGINATED_CATEGORIES), \
                f"Expected at least {len(AROI_PAGINATED_CATEGORIES)} matches for pattern {pattern}"


class TestPaginationIntegration:
    """Integration tests for pagination with the complete system."""

    @patch('allium.lib.relays.Relays._generate_aroi_leaderboards')
    def test_pagination_with_real_template_context(self, mock_aroi, jinja_env, mock_aroi_leaderboard_entry):
        """Pagination works with realistic template context structure."""
        mock_aroi.return_value = None

        # Create a mock Relays instance with a single shared-schema entry
        relays = Mock()
        mock_entry = mock_aroi_leaderboard_entry(rank=1, contact_hash='test_hash')
        mock_entry.countries = ['US', 'DE']
        mock_entry.platforms = ['Linux']

        relays.json = {
            'aroi_leaderboards': {
                'leaderboards': {'bandwidth': [mock_entry]},
                'summary': {'categories': {'bandwidth': 'Bandwidth Contributed'}}
            }
        }
        relays.use_bits = False

        template = jinja_env.get_template('aroi-leaderboards.html')
        context = {
            'relays': relays,
            'page_ctx': {'path_prefix': './'}
        }

        # Should render without errors
        rendered = template.render(**context)
        assert isinstance(rendered, str)
        assert len(rendered) > 0
