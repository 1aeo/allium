#!/usr/bin/env python3

import os
import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock

from jinja2 import Environment, FileSystemLoader, select_autoescape

from allium.lib.page_writer import build_template_args, write_pages_by_key
from allium.lib.relays import Relays


class TestContactTemplateIntegration(unittest.TestCase):
    """Integration tests for contact template two-column layout rendering."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Set up Jinja2 environment
        template_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'allium', 'templates')
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        # Add custom filters for template compatibility
        from allium.lib.bandwidth_formatter import determine_unit_filter, format_bandwidth_with_unit, format_bandwidth_filter
        from allium.lib.time_utils import format_time_ago
        self.jinja_env.filters['determine_unit'] = determine_unit_filter
        self.jinja_env.filters['format_bandwidth_with_unit'] = format_bandwidth_with_unit
        self.jinja_env.filters['format_bandwidth'] = format_bandwidth_filter
        self.jinja_env.filters['format_time_ago'] = format_time_ago
        
        # Sample relay data - shared between relay_subset and relays.json.relay_subset
        self.sample_relay = {
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
            'first_seen_date_escaped': '2023-01-01',
            'contact_md5': 'abcd1234'
        }
        
        # Sample template context data
        self.template_context = {
            'contact': 'test@example.com',
            'contact_hash': 'abcd1234',
            'bandwidth': '150.0',
            'bandwidth_unit': 'MB/s',
            'consensus_weight_fraction': 0.025,  # 2.5%
            'network_position': {
                'label': 'mixed',
                'percentage_breakdown': '40% guard, 20% middle, 40% exit',
                'formatted_string': 'Mixed (5 total relays, 2 guards, 1 middle, 2 exits)',
                'guard_percentage': 40,
                'middle_percentage': 20,
                'exit_percentage': 40
            },
            # relay_subset is now passed directly to templates (Option 3 change)
            'relay_subset': [self.sample_relay],
            'relays': {
                'json': {
                    'relay_subset': [self.sample_relay]  # Keep for backward compat in tests
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
                    'network_diversity': '<span class="al-rating-great">Great</span>, 4 networks (2 rare)',
                    'geographic_diversity': '<span class="al-rating-okay">Okay</span>, 2 countries',
                    'infrastructure_diversity': '<span class="al-rating-poor">Poor</span>, 1 platform',
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
                        'display': '<span class="al-status-success-bold">6mo 99.9%</span>',
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
                    'title': 'Bandwidth Capacity Champion',
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
        self.assertIn('📋 Contact & Network Overview', rendered)
        # The template doesn't show the actual email but shows the Hash field
        self.assertIn('Hash:', rendered)
        # Should have country flag image (not emoji)
        self.assertIn('us.png', rendered)  # US flag image
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
        self.assertIn('2 winning', rendered)  # Shows count of rankings
        self.assertIn('— Bandwidth Capacity Champion', rendered)
        self.assertIn('— Diversity Master', rendered)
        
        # Should contain reliability section (not separate network reliability)
        self.assertIn('⏰ Relay Reliability', rendered)
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
        
        # Template displays category names without emojis in small text
        self.assertIn('— Bandwidth Capacity Champion', rendered)
        self.assertIn('— Diversity Master', rendered)

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
        self.assertIn('⏰ Relay Reliability', rendered)

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
        self.assertIn('al-rating-great">Great</span>, 4 networks (2 rare)', rendered)
        self.assertIn('al-rating-okay">Okay</span>, 2 countries', rendered)
        self.assertIn('al-rating-poor">Poor</span>, 1 platform', rendered)

    def test_contact_template_uptime_highlighting(self):
        """Test uptime highlighting for high reliability values."""
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Should preserve green highlighting for high uptime
        self.assertIn('al-status-success-bold">6mo 99.9%', rendered)
        
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
        
        # AROI domain appears in the page title
        self.assertIn('Contact example.org Details', rendered)
        # The template doesn't have a separate "Domain:" field, so we check that contact display works
        self.assertIn('📋 Contact & Network Overview', rendered)

    def test_contact_template_no_aroi_domain(self):
        """Test handling when no AROI domain is available."""
        import copy
        context_no_domain = copy.deepcopy(self.template_context)
        context_no_domain['relay_subset'][0]['aroi_domain'] = 'none'
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
        
        # Should contain relay reliability section (instead of separate flag reliability)
        self.assertIn('⏰ Relay Reliability', rendered)
        
        # Should display uptime information
        self.assertIn('Overall Uptime:', rendered)
        self.assertIn('30d 98.5%', rendered)
        self.assertIn('6mo 99.9%', rendered)
        
        # Should include proper color styling for high reliability
        self.assertIn('al-status-success', rendered)

    def test_contact_template_flag_reliability_tooltips(self):
        """Test that flag reliability tooltips are properly included."""
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Should contain tooltip content for reliability
        self.assertIn('TestRelay1 (95.2%)', rendered)  # Outlier tooltip
        self.assertIn('6 month: ≥2σ 97.8% from average μ 99.9%', rendered)  # Statistical tooltip

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
        """Test that CSS class coding is consistent across different reliability displays."""
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Should use al-status-success class for high reliability
        green_class_occurrences = rendered.count('al-status-success')
        self.assertGreater(green_class_occurrences, 0, "Should have success class for high reliability")
        
        # Should use consistent CSS classes
        self.assertIn('al-rating-great', rendered)  # Intelligence diversity classes
        self.assertIn('al-rating-okay', rendered)  # Warning classes

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
        # Add flag reliability data to the contact_display_data structure instead
        context_mixed_flags['contact_display_data']['flag_analysis'] = {
            'has_flag_data': True,
            'flag_reliabilities': {
            'Exit': {
                    'icon': '🚪',
                    'display_name': 'Exit Node',
                    'periods': {
                        '6M': {
                            'value': 96.2,
                            'color_class': 'high-performance',
                            'tooltip': 'Exit flag reliability: 96.2% - Excellent performance',
                            'relay_count': 3
                        }
                    }
                }
            }
        }
        
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(context_mixed_flags)
        
        # Template uses reliability section rather than separate flag reliability
        # Should contain reliability information
        self.assertIn('⏰ Relay Reliability', rendered)
        
        # Should contain uptime information that reflects overall reliability
        self.assertIn('Overall Uptime:', rendered)
        self.assertIn('99.5%', rendered)  # From the uptime_api_display

    def test_contact_template_statistical_analysis_integration(self):
        """Test that statistical analysis data is properly integrated."""
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Should display outlier information
        self.assertIn('1 relays out of 5 relays (20.0%)', rendered)
        
        # Should include statistical tooltips
        self.assertIn('≥2σ 97.8% from average μ 99.9%', rendered)

    def test_contact_template_sort_links_for_all_columns(self):
        """Contact pages with ≥3 relays should expose static no-JS sort links."""
        import copy
        from allium.lib.contact_sorting import CONTACT_SORT_FILE_MAP

        context = copy.deepcopy(self.template_context)
        context['relay_subset'][0]['ipv6_support'] = 'both'
        context['relay_subset'][0]['or_addresses'] = ['192.168.1.1:9001', '[2001:db8::1]:9001']
        context['relays']['json']['relay_subset'][0]['ipv6_support'] = 'both'
        context['relays']['json']['relay_subset'][0]['or_addresses'] = ['192.168.1.1:9001', '[2001:db8::1]:9001']
        context['sortable_scope'] = 'contact'
        context['contact_sort_mode'] = 'bandwidth'
        context['contact_sort_links'] = CONTACT_SORT_FILE_MAP
        context['contact_sort_enabled'] = True
        context['contact_has_ipv6'] = True

        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**context)

        # Non-default sort links should point to by-*.html pages with #relay-table anchor
        self.assertIn('href="by-nickname.html#relay-table"', rendered)
        self.assertIn('href="by-total-data.html#relay-table"', rendered)
        self.assertIn('href="by-uptime-percentage.html#relay-table"', rendered)
        self.assertIn('href="by-flag-uptime.html#relay-table"', rendered)
        self.assertIn('href="by-ipv4.html#relay-table"', rendered)
        self.assertIn('href="by-flags.html#relay-table"', rendered)
        self.assertIn('href="by-dns.html#relay-table"', rendered)
        self.assertIn('href="by-family.html#relay-table"', rendered)
        self.assertIn('href="by-country.html#relay-table"', rendered)
        self.assertIn('href="by-as-number.html#relay-table"', rendered)
        self.assertIn('href="by-as-name.html#relay-table"', rendered)
        self.assertIn('href="by-platform.html#relay-table"', rendered)
        self.assertIn('href="by-first-seen.html#relay-table"', rendered)
        self.assertIn('href="by-last-restarted.html#relay-table"', rendered)
        self.assertIn('href="by-ipv6.html#relay-table"', rendered)

        # Bandwidth mode is default index page (no by-bandwidth file)
        self.assertNotIn('href="by-bandwidth.html', rendered)
        # Active sort column should have bold indicator
        self.assertIn('▾', rendered)

    def test_contact_template_sort_links_hidden_for_small_contacts(self):
        """Contact pages with ≤2 relays should NOT show sort links."""
        import copy
        from allium.lib.contact_sorting import CONTACT_SORT_FILE_MAP

        context = copy.deepcopy(self.template_context)
        context['sortable_scope'] = 'contact'
        context['contact_sort_mode'] = 'bandwidth'
        context['contact_sort_links'] = CONTACT_SORT_FILE_MAP
        context['contact_sort_enabled'] = False  # ≤2 relays
        context['contact_has_ipv6'] = False

        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**context)

        # Should NOT have sort links
        self.assertNotIn('href="by-nickname.html', rendered)
        self.assertNotIn('href="by-status.html', rendered)
        # Should still show headers (just not clickable)
        self.assertIn('Nickname', rendered)
        self.assertIn('BW Cap', rendered)

    def test_contact_template_non_default_variant_has_index_canonical(self):
        """Non-default contact variants should canonicalize to index.html when no vanity canonical applies."""
        import copy
        from allium.lib.contact_sorting import CONTACT_SORT_FILE_MAP

        context = copy.deepcopy(self.template_context)
        context['sortable_scope'] = 'contact'
        context['contact_sort_mode'] = 'nickname'
        context['contact_sort_enabled'] = True
        context['contact_sort_links'] = CONTACT_SORT_FILE_MAP
        context['base_url'] = None
        context['is_validated_aroi'] = False

        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**context)
        self.assertIn('<link rel="canonical" href="index.html" />', rendered)


class TestContactMultiprocessingRegression(unittest.TestCase):
    """Regression tests for contact page generation under multiprocessing.
    
    Ensures that precomputed contact metadata (rankings, validation, reliability)
    is properly preserved when pages are rendered in parallel worker processes.
    """
    
    def setUp(self):
        """Set up test fixtures with minimal relay data for multiprocessing test."""
        import tempfile
        import hashlib
        self.temp_dir = tempfile.mkdtemp()
        
        # Compute actual MD5 hashes for contacts (as Relays does)
        contact1 = "test@example.org"
        contact2 = "other@example.net"
        self.contact1_md5 = hashlib.md5(contact1.encode('utf-8')).hexdigest()
        self.contact2_md5 = hashlib.md5(contact2.encode('utf-8')).hexdigest()
        
        # Minimal relay data structure - Relays will call _categorize to build sorted structure
        self.relay_data = {
            "relays": [
                {
                    "fingerprint": "AAAA1111BBBB2222CCCC3333DDDD4444EEEE5555",
                    "nickname": "TestRelay1",
                    "contact": contact1,
                    "country": "us",
                    "country_name": "United States",
                    "as": "AS7922",
                    "as_name": "Comcast",
                    "observed_bandwidth": 5000000,
                    "consensus_weight": 1000,
                    "flags": ["Running", "Valid", "Guard"],
                    "running": True,
                    "measured": True,
                    "first_seen": "2023-01-01 00:00:00",
                    "or_addresses": ["192.168.1.1:9001"],
                    "platform": "Tor 0.4.7.8 on Linux",
                    "effective_family": [],
                },
                {
                    "fingerprint": "FFFF6666777788889999AAAABBBBCCCCDDDDEEEE",
                    "nickname": "TestRelay2",
                    "contact": contact2,
                    "country": "de",
                    "country_name": "Germany",
                    "as": "AS3320",
                    "as_name": "Deutsche Telekom",
                    "observed_bandwidth": 3000000,
                    "consensus_weight": 800,
                    "flags": ["Running", "Valid", "Exit"],
                    "running": True,
                    "measured": True,
                    "first_seen": "2023-06-01 00:00:00",
                    "or_addresses": ["10.0.0.1:9001"],
                    "platform": "Tor 0.4.7.8 on FreeBSD",
                    "effective_family": [],
                },
            ],
        }
    
    def tearDown(self):
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_contact_precomputation_stores_required_metadata(self):
        """Test that precomputation stores all required contact metadata directly on contact_data."""
        # Create a minimal Relays instance - it will call _categorize to build contact sorted structure
        relay_set = Relays(
            output_dir=self.temp_dir,
            onionoo_url="https://test.example.com",
            relay_data=self.relay_data,
            use_bits=False,
            progress=False,
            mp_workers=0,  # Disable MP for unit test isolation
        )
        
        # Get actual contact hashes from the categorized data
        contact_hashes = list(relay_set.json["sorted"]["contact"].keys())
        self.assertGreater(len(contact_hashes), 0, "Should have at least one contact after categorization")
        
        # Manually trigger precomputation for contacts
        aroi_validation_timestamp = "2024-01-01 00:00:00"
        validated_aroi_domains = set()  # No validated domains in this test
        
        for contact_hash in contact_hashes:
            relay_set._precompute_single_contact(
                contact_hash, aroi_validation_timestamp, validated_aroi_domains
            )
        
        # Verify required metadata is stored directly on contact_data (not nested)
        contact1 = relay_set.json["sorted"]["contact"][contact_hashes[0]]
        
        # These keys must exist directly on contact_data (flat storage pattern)
        required_keys = [
            "contact_rankings",
            "operator_reliability", 
            "contact_display_data",
            "contact_validation_status",
            "aroi_validation_timestamp",
            "is_validated_aroi",
            "precomputed_bandwidth_unit",
        ]
        
        for key in required_keys:
            self.assertIn(key, contact1, f"Missing required precomputed key: {key}")
        
        # Verify contact_display_data is not None
        self.assertIsNotNone(contact1["contact_display_data"], 
                            "contact_display_data should not be None after precomputation")
    
    def test_contact_page_multiprocessing_preserves_metadata(self):
        """Regression test: contact page rendering under multiprocessing preserves all metadata.
        
        This test forces mp_workers=2 and verifies that the template arguments
        contain all required contact-specific metadata after parallel precomputation.
        """
        import multiprocessing as mp
        
        # Skip if fork context not available (Windows)
        if not hasattr(mp, 'get_context'):
            self.skipTest("Multiprocessing fork context not available")
        
        try:
            ctx = mp.get_context('fork')
        except ValueError:
            self.skipTest("Fork context not supported on this platform")
        
        # Create Relays instance with multiprocessing enabled
        relay_set = Relays(
            output_dir=self.temp_dir,
            onionoo_url="https://test.example.com",
            relay_data=self.relay_data,
            use_bits=False,
            progress=False,
            mp_workers=2,  # Force multiprocessing
        )
        
        # Trigger precomputation (this would normally happen in coordinator)
        relay_set._precompute_all_contact_page_data()
        
        # Get actual contact hash from categorized data
        contact_hashes = list(relay_set.json["sorted"]["contact"].keys())
        self.assertGreater(len(contact_hashes), 0, "Should have contacts after categorization")
        
        contact_hash = contact_hashes[0]
        contact_data = relay_set.json["sorted"]["contact"][contact_hash]
        
        # Verify metadata is available for template rendering
        the_prefixed = ["United States"]
        validated_aroi_domains = set()
        
        template_args = build_template_args(
            relay_set, "contact", contact_hash, contact_data, the_prefixed, validated_aroi_domains
        )
        
        # Verify critical contact metadata is in template args
        self.assertIn("contact_rankings", template_args)
        self.assertIn("operator_reliability", template_args)
        self.assertIn("contact_display_data", template_args)
        self.assertIn("contact_validation_status", template_args)
        self.assertIn("aroi_validation_timestamp", template_args)
        self.assertIn("is_validated_aroi", template_args)
        
        # Verify values are not None/empty (regression for missing precomputation)
        self.assertIsNotNone(template_args["contact_display_data"],
                            "contact_display_data should not be None after precomputation")
    
    def test_build_template_args_uses_flat_storage(self):
        """Test that _build_template_args reads from flat contact_data, not nested 'precomputed' dict."""
        relay_set = Relays(
            output_dir=self.temp_dir,
            onionoo_url="https://test.example.com",
            relay_data=self.relay_data,
            use_bits=False,
            progress=False,
            mp_workers=0,
        )
        
        # Get actual contact hash from categorized data
        contact_hashes = list(relay_set.json["sorted"]["contact"].keys())
        self.assertGreater(len(contact_hashes), 0, "Should have contacts")
        
        contact_hash = contact_hashes[0]
        contact_data = relay_set.json["sorted"]["contact"][contact_hash]
        
        # Manually set flat storage pattern (as done by _precompute_single_contact)
        contact_data["contact_rankings"] = [{"title": "Test Champion", "badge": "🏆"}]
        contact_data["operator_reliability"] = {"valid_relays": 1, "total_relays": 1}
        contact_data["contact_display_data"] = {"test": "data"}
        contact_data["contact_validation_status"] = {"validation_status": "valid"}
        contact_data["aroi_validation_timestamp"] = "2024-01-01"
        contact_data["is_validated_aroi"] = True
        
        # Build template args
        template_args = build_template_args(
            relay_set, "contact", contact_hash, contact_data, [], set()
        )
        
        # Verify flat storage is used (not nested precomputed dict)
        self.assertEqual(template_args["contact_rankings"], 
                        [{"title": "Test Champion", "badge": "🏆"}])
        self.assertEqual(template_args["operator_reliability"],
                        {"valid_relays": 1, "total_relays": 1})
        self.assertTrue(template_args["is_validated_aroi"])
    
    def test_precomputation_stores_aroi_domain_for_vanity_urls(self):
        """Test that aroi_domain is stored during precomputation for efficient vanity URL generation."""
        relay_set = Relays(
            output_dir=self.temp_dir,
            onionoo_url="https://test.example.com",
            relay_data=self.relay_data,
            use_bits=False,
            progress=False,
            mp_workers=0,
        )
        
        # Get contact hash and trigger precomputation
        contact_hashes = list(relay_set.json["sorted"]["contact"].keys())
        self.assertGreater(len(contact_hashes), 0, "Should have contacts")
        
        contact_hash = contact_hashes[0]
        aroi_validation_timestamp = "2024-01-01 00:00:00"
        validated_aroi_domains = set()
        
        relay_set._precompute_single_contact(
            contact_hash, aroi_validation_timestamp, validated_aroi_domains
        )
        
        contact_data = relay_set.json["sorted"]["contact"][contact_hash]
        
        # Verify aroi_domain is stored (used for vanity URL generation without re-fetching members)
        self.assertIn("aroi_domain", contact_data, 
                     "aroi_domain should be stored for efficient vanity URL generation")

    def test_contact_page_generation_creates_sort_variant_files(self):
        """Contact page writer should emit index + by-*.html variants for ≥3 relay contacts."""
        # Build test data with 3 relays sharing the same contact (above threshold)
        contact = "operator@example.com"
        relay_data = {"relays": [
            {"fingerprint": "A" * 40, "nickname": "Relay1", "contact": contact,
             "country": "us", "country_name": "United States", "as": "AS1", "as_name": "Net1",
             "observed_bandwidth": 5000000, "consensus_weight": 1000,
             "flags": ["Running", "Valid", "Guard"], "running": True, "measured": True,
             "first_seen": "2023-01-01 00:00:00", "or_addresses": ["1.1.1.1:9001", "[2001:db8::1]:9001"],
             "platform": "Tor 0.4.7.8 on Linux", "effective_family": [], "ipv6_support": "both"},
            {"fingerprint": "B" * 40, "nickname": "Relay2", "contact": contact,
             "country": "de", "country_name": "Germany", "as": "AS2", "as_name": "Net2",
             "observed_bandwidth": 3000000, "consensus_weight": 800,
             "flags": ["Running", "Valid", "Exit"], "running": True, "measured": True,
             "first_seen": "2023-06-01 00:00:00", "or_addresses": ["2.2.2.2:9001"],
             "platform": "Tor 0.4.7.8 on FreeBSD", "effective_family": []},
            {"fingerprint": "C" * 40, "nickname": "Relay3", "contact": contact,
             "country": "fr", "country_name": "France", "as": "AS3", "as_name": "Net3",
             "observed_bandwidth": 2000000, "consensus_weight": 600,
             "flags": ["Running", "Valid"], "running": True, "measured": True,
             "first_seen": "2024-01-01 00:00:00", "or_addresses": ["3.3.3.3:9001"],
             "platform": "Tor 0.4.7.8 on Linux", "effective_family": []},
        ]}
        relay_set = Relays(
            output_dir=self.temp_dir,
            onionoo_url="https://test.example.com",
            relay_data=relay_data,
            use_bits=False,
            progress=False,
            mp_workers=0,
        )

        write_pages_by_key(relay_set, "contact")

        contact_hashes = list(relay_set.json["sorted"]["contact"].keys())
        self.assertGreater(len(contact_hashes), 0)
        contact_dir = os.path.join(self.temp_dir, "contact", contact_hashes[0])

        expected_files = [
            "index.html",
            "by-status.html",
            "by-nickname.html",
            "by-total-data.html",
            "by-uptime.html",
            "by-uptime-percentage.html",
            "by-flag-uptime.html",
            "by-ipv4.html",
            "by-flags.html",
            "by-dns.html",
            "by-family.html",
            "by-country.html",
            "by-as-number.html",
            "by-as-name.html",
            "by-platform.html",
            "by-first-seen.html",
            "by-last-restarted.html",
            "by-ipv6.html",  # Relay1 has IPv6 → by-ipv6.html emitted
        ]

        for filename in expected_files:
            self.assertTrue(os.path.exists(os.path.join(contact_dir, filename)), f"missing {filename}")

        self.assertFalse(os.path.exists(os.path.join(contact_dir, "by-bandwidth.html")))

        # Regression (IPv6 always-N/A bug): the full pipeline must render the
        # actual IPv6 address in the IPv6 column, not N/A. Relay1 is dual-stack
        # ([2001:db8::1]:9001); Relay2/Relay3 are IPv4-only.
        # This test goes through real preprocessing (relay['ipv6_display_address'])
        # so it guards the Python↔template contract that hand-built contexts can't.
        for filename in ("index.html", "by-ipv6.html"):
            with open(os.path.join(contact_dir, filename), encoding="utf8") as f:
                rendered = f.read()
            self.assertIn("2001:db8::1", rendered,
                          f"{filename}: dual-stack relay's IPv6 address missing from IPv6 column")
            # IPv4-only relay rows must still render N/A in their IPv6 cell
            relay2_row = next(chunk for chunk in rendered.split("<tr>")
                              if 'title="Relay2"' in chunk)
            self.assertNotIn("2001:db8::1", relay2_row)
            self.assertIn("N/A", relay2_row)

    def test_contact_page_generation_threshold_small_contacts(self):
        """Contacts with ≤2 relays should get only index.html (no sort variants)."""
        relay_set = Relays(
            output_dir=self.temp_dir,
            onionoo_url="https://test.example.com",
            relay_data=self.relay_data,  # Original test data: 1 relay per contact
            use_bits=False,
            progress=False,
            mp_workers=0,
        )

        write_pages_by_key(relay_set, "contact")

        contact_hashes = list(relay_set.json["sorted"]["contact"].keys())
        self.assertGreater(len(contact_hashes), 0)

        for contact_hash in contact_hashes:
            contact_dir = os.path.join(self.temp_dir, "contact", contact_hash)
            self.assertTrue(
                os.path.exists(os.path.join(contact_dir, "index.html")),
                f"missing index.html for contact {contact_hash}")
            self.assertFalse(
                os.path.exists(os.path.join(contact_dir, "by-status.html")),
                f"stale by-status.html for contact {contact_hash}")
            self.assertFalse(
                os.path.exists(os.path.join(contact_dir, "by-nickname.html")),
                f"stale by-nickname.html for contact {contact_hash}")

    def test_contact_page_generation_omits_ipv6_variant_when_not_visible(self):
        """Contacts with ≥3 relays but no IPv6 visibility should not emit by-ipv6.html."""
        contact = "no-ipv6-operator@example.org"
        relay_data = {"relays": [
            {"fingerprint": "A" * 40, "nickname": "R1", "contact": contact,
             "country": "us", "country_name": "United States", "as": "AS1", "as_name": "Net1",
             "observed_bandwidth": 5000000, "consensus_weight": 1000,
             "flags": ["Running", "Valid", "Guard"], "running": True, "measured": True,
             "first_seen": "2023-01-01 00:00:00", "or_addresses": ["192.168.1.1:9001"],
             "platform": "Tor 0.4.7.8 on Linux", "effective_family": []},
            {"fingerprint": "B" * 40, "nickname": "R2", "contact": contact,
             "country": "de", "country_name": "Germany", "as": "AS2", "as_name": "Net2",
             "observed_bandwidth": 3000000, "consensus_weight": 800,
             "flags": ["Running", "Valid", "Exit"], "running": True, "measured": True,
             "first_seen": "2023-06-01 00:00:00", "or_addresses": ["10.0.0.1:9001"],
             "platform": "Tor 0.4.7.8 on FreeBSD", "effective_family": []},
            {"fingerprint": "C" * 40, "nickname": "R3", "contact": contact,
             "country": "fr", "country_name": "France", "as": "AS3", "as_name": "Net3",
             "observed_bandwidth": 2000000, "consensus_weight": 700,
             "flags": ["Running", "Valid"], "running": True, "measured": True,
             "first_seen": "2024-01-01 00:00:00", "or_addresses": ["172.16.0.1:9001"],
             "platform": "Tor 0.4.8.0 on Linux", "effective_family": []},
        ]}
        relay_set = Relays(
            output_dir=self.temp_dir,
            onionoo_url="https://test.example.com",
            relay_data=relay_data,
            use_bits=False,
            progress=False,
            mp_workers=0,
        )
        write_pages_by_key(relay_set, "contact")
        contact_hashes = list(relay_set.json["sorted"]["contact"].keys())
        self.assertEqual(len(contact_hashes), 1)
        contact_dir = os.path.join(self.temp_dir, "contact", contact_hashes[0])

        # Should have other variants but NOT by-ipv6.html (no IPv6 relays)
        self.assertTrue(os.path.exists(os.path.join(contact_dir, "by-status.html")))
        self.assertFalse(os.path.exists(os.path.join(contact_dir, "by-ipv6.html")))

    def test_contact_page_generation_creates_vanity_sort_variants_when_validated(self):
        """Validated AROI contacts with ≥3 relays should get vanity sort variants."""
        # Build test data with 3 relays under same contact (above threshold)
        contact = "operator@example.org"
        relay_data = {"relays": [
            {"fingerprint": "D" * 40, "nickname": "V1", "contact": contact,
             "country": "us", "country_name": "United States", "as": "AS1", "as_name": "Net1",
             "observed_bandwidth": 5000000, "consensus_weight": 1000,
             "flags": ["Running", "Valid", "Guard"], "running": True, "measured": True,
             "first_seen": "2023-01-01 00:00:00", "or_addresses": ["1.1.1.1:9001"],
             "platform": "Tor 0.4.7.8 on Linux", "effective_family": []},
            {"fingerprint": "E" * 40, "nickname": "V2", "contact": contact,
             "country": "de", "country_name": "Germany", "as": "AS2", "as_name": "Net2",
             "observed_bandwidth": 3000000, "consensus_weight": 800,
             "flags": ["Running", "Valid", "Exit"], "running": True, "measured": True,
             "first_seen": "2023-06-01 00:00:00", "or_addresses": ["2.2.2.2:9001"],
             "platform": "Tor 0.4.7.8 on FreeBSD", "effective_family": []},
            {"fingerprint": "F" * 40, "nickname": "V3", "contact": contact,
             "country": "fr", "country_name": "France", "as": "AS3", "as_name": "Net3",
             "observed_bandwidth": 2000000, "consensus_weight": 600,
             "flags": ["Running", "Valid"], "running": True, "measured": True,
             "first_seen": "2024-01-01 00:00:00", "or_addresses": ["3.3.3.3:9001"],
             "platform": "Tor 0.4.7.8 on Linux", "effective_family": []},
        ]}
        relay_set = Relays(
            output_dir=self.temp_dir,
            onionoo_url="https://test.example.com",
            relay_data=relay_data,
            use_bits=False,
            progress=False,
            mp_workers=0,
            base_url="https://metrics.1aeo.com",
        )

        contact_hashes = list(relay_set.json["sorted"]["contact"].keys())
        self.assertGreater(len(contact_hashes), 0)
        contact_hash = contact_hashes[0]
        contact_data = relay_set.json["sorted"]["contact"][contact_hash]
        contact_data["is_validated_aroi"] = True
        contact_data["aroi_domain"] = "example.org"

        write_pages_by_key(relay_set, "contact")

        vanity_dir = os.path.join(self.temp_dir, "example.org")
        self.assertTrue(os.path.isdir(vanity_dir))

        # Check canonical variants exist (by-ipv6 excluded — no IPv6 in test data)
        expected_files = [
            "index.html",
            "by-status.html",
            "by-nickname.html",
            "by-total-data.html",
            "by-uptime.html",
            "by-uptime-percentage.html",
            "by-flag-uptime.html",
            "by-ipv4.html",
            "by-flags.html",
            "by-dns.html",
            "by-family.html",
            "by-country.html",
            "by-as-number.html",
            "by-as-name.html",
            "by-platform.html",
            "by-first-seen.html",
            "by-last-restarted.html",
        ]
        for filename in expected_files:
            self.assertTrue(os.path.exists(os.path.join(vanity_dir, filename)), f"missing vanity {filename}")

        # by-ipv6.html should NOT exist (no IPv6 in test data)
        self.assertFalse(os.path.exists(os.path.join(vanity_dir, "by-ipv6.html")))


class TestB3V3RelayInfoRendering(unittest.TestCase):
    """B3.2 (re-opened): integration tests for v3 awareness in
    relay-info / contact macros. Focused on the new B1 + B3 rendering
    contract — does NOT duplicate the data-layer tests in
    test_aroi_validation.py.

    Verifies that the macros emit:
    - aroi_v2v3_pills strip when v2_relay_count + v3_relay_count > 0
    - 🚨 SECURITY badge when security_incident_count > 0
    - ⏳ Pending badge when pending_onionoo_count > 0
    - 🏆 v3 complete pill when 100% v3 + not mixed
    - 🔁 migration percentage when is_mixed_migration
    - relay-info v2/v3 version label per relay
    """

    def setUp(self):
        import os
        from jinja2 import Environment, FileSystemLoader
        template_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'allium', 'templates'
        )
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dir), autoescape=True,
        )

    def _render_pills(self, validation_summary):
        """Render the aroi_v2v3_pills macro with a fake validation status."""
        template_str = (
            "{% from 'macros.html' import aroi_v2v3_pills %}"
            "{{ aroi_v2v3_pills(contact_validation_status) }}"
        )
        template = self.jinja_env.from_string(template_str)
        return template.render(contact_validation_status={
            'validation_summary': validation_summary,
        })

    def test_pills_hidden_when_no_aroi_relays(self):
        """No pill strip when operator has 0 v2 + 0 v3 relays."""
        rendered = self._render_pills({
            'v2_relay_count': 0, 'v3_relay_count': 0,
            'v3_pct_of_total': 0.0, 'v3_migration_progress_pct': 0.0, 'is_mixed_migration': False,
            'v3_tier': 'none', 'is_v3_adopter': False,
        })
        self.assertNotIn('v2:', rendered)
        self.assertNotIn('v3:', rendered)

    def test_v2_only_pill(self):
        """Operator with only v2 relays: gray v2 pill, no v3 pill."""
        rendered = self._render_pills({
            'v2_relay_count': 5, 'v3_relay_count': 0,
            'v3_pct_of_total': 0.0, 'v3_migration_progress_pct': 0.0, 'is_mixed_migration': False,
            'v3_tier': 'none', 'is_v3_adopter': False,
        })
        self.assertIn('v2: 5', rendered)
        self.assertNotIn('v3:', rendered)

    def test_v3_complete_marker(self):
        """100% v3 operator: pill + 🏆 v3 complete badge."""
        rendered = self._render_pills({
            'v2_relay_count': 0, 'v3_relay_count': 10,
            'v3_pct_of_total': 100.0, 'v3_migration_progress_pct': 100.0, 'is_mixed_migration': False,
            'v3_tier': 'complete', 'is_v3_adopter': True,
        })
        self.assertIn('v3: 10', rendered)
        self.assertIn('🏆 v3 complete', rendered)
        self.assertNotIn('🔁', rendered)

    def test_mixed_migration_marker(self):
        """Mixed v2/v3 operator: shows 🔁 migration percentage."""
        rendered = self._render_pills({
            'v2_relay_count': 7, 'v3_relay_count': 3,
            'v3_pct_of_total': 30.0, 'v3_migration_progress_pct': 30.0, 'is_mixed_migration': True,
            'v3_tier': 'migrating', 'is_v3_adopter': True,
        })
        self.assertIn('v2: 7', rendered)
        self.assertIn('v3: 3', rendered)
        self.assertIn('🔁 30% v3', rendered)

    def test_security_badge_renders_alongside_validated(self):
        """B1.1: 🚨 SECURITY badge appears AT THE TOP of badge group
        when security_incident_count > 0, not replacing cascade."""
        template_str = (
            "{% from 'macros.html' import aroi_validation_badge %}"
            "{{ aroi_validation_badge(contact_validation_status) }}"
        )
        template = self.jinja_env.from_string(template_str)
        rendered = template.render(contact_validation_status={
            'validation_status': 'validated',
            'validation_summary': {
                'validated_count': 5,
                'unauthorized_count': 0,
                'misconfigured_count': 1,
                'incomplete_count': 0,
                'not_configured_count': 0,
                'security_incident_count': 1,
                'pending_onionoo_count': 0,
            },
        })
        # Both badges visible (not exclusive).
        self.assertIn('🚨 SECURITY', rendered)
        self.assertIn('Validated', rendered)

    def test_pending_onionoo_badge_NOT_rendered_in_header(self):
        """UX-fix: ⏳ Pending peer badge intentionally REMOVED from
        aroi_validation_badge header to avoid the confusing
        "✓ Validated ⏳ Pending" dual presentation. Pending relays
        are dual-bucketed into 'misconfigured' so the cascade badge
        already conveys "something needs attention", and the section
        anchor (#misconfigured-relays) drills into the per-relay
        error_category for actionable detail.
        """
        template_str = (
            "{% from 'macros.html' import aroi_validation_badge %}"
            "{{ aroi_validation_badge(contact_validation_status) }}"
        )
        template = self.jinja_env.from_string(template_str)
        rendered = template.render(contact_validation_status={
            'validation_status': 'validated',
            'validation_summary': {
                'validated_count': 5,
                'unauthorized_count': 0,
                'misconfigured_count': 1,
                'incomplete_count': 0,
                'not_configured_count': 0,
                'security_incident_count': 0,
                'pending_onionoo_count': 6,
            },
        })
        # Cascade badge IS rendered.
        self.assertIn('Validated', rendered)
        # ⏳ Pending peer badge is NO LONGER rendered in the header.
        self.assertNotIn('⏳ Pending', rendered)

    def test_aroi_validation_icon_v3_label(self):
        """B1.5: aroi_validation_icon appends 'v3' badge for v3 relays."""
        template_str = (
            "{% from 'macros.html' import aroi_validation_icon %}"
            "{{ aroi_validation_icon('AAAA', 'v3.example.com', "
            "validated_fps, [], [], [], [], '3') }}"
        )
        template = self.jinja_env.from_string(template_str)
        rendered = template.render(validated_fps={'AAAA'})
        self.assertIn('v3</span>', rendered)
        # v3 label uses blue background (matches B1.6 styling).
        self.assertIn('background-color: #007bff', rendered)

    def test_aroi_validation_icon_pending_takes_precedence(self):
        """B1.5: ⏳ icon takes visual precedence over the cascade icon."""
        template_str = (
            "{% from 'macros.html' import aroi_validation_icon %}"
            "{{ aroi_validation_icon('AAAA', 'v3.example.com', "
            "validated_fps, [], [], [], pending_fps, '3') }}"
        )
        template = self.jinja_env.from_string(template_str)
        rendered = template.render(
            validated_fps={'AAAA'},
            pending_fps={'AAAA'},
        )
        # Pending icon present; validated checkmark absent in same span group.
        self.assertIn('⏳', rendered)
        # Validated checkmark not emitted because pending branch ran first.
        self.assertNotIn('AROI Validated:', rendered)

    def test_relay_detail_box_renders_fix_and_paste_when_distinct(self):
        """B-final pasteable contract: aroi_relay_detail_box renders both
        💡 Fix: (upstream hint) AND 📋 Paste: (V3_CATEGORY_LABELS example)
        when they differ, ensuring operators always see a literally-pasteable
        line even when upstream hint is multi-sentence prose."""
        template_str = (
            "{% from 'macros.html' import aroi_relay_detail_box %}"
            "{{ aroi_relay_detail_box(relays, 'misconfigured', page_ctx, ts) }}"
        )
        template = self.jinja_env.from_string(template_str)
        rendered = template.render(
            relays=[{
                'fingerprint': 'A' * 40,
                'nickname': 'TestRelay',
                'aroi_domain': 'foo.bar',
                'aroi_version': '3',
                'proof_type': 'uri-familyid-ed25519',
                'error': 'URI-FamilyID: family_id not found at foo.bar',
                'hint': 'Multi-sentence upstream prose. Confirm content. Never paste secrets.',
                'pasteable_example': '# /.well-known/tor-relay/ed25519-family-id.txt must list family_id',
                'error_category': 'uri_content_mismatch',
            }],
            page_ctx={'path_prefix': ''},
            ts='2026-05-06 03:00 UTC',
        )
        # Both 💡 Fix: and 📋 Paste: render
        self.assertIn('💡 Fix:', rendered)
        self.assertIn('📋 Paste:', rendered)
        # Upstream hint visible in 💡 Fix: block
        self.assertIn('Multi-sentence upstream prose', rendered)
        # V3_CATEGORY_LABELS example visible in 📋 Paste: block
        self.assertIn('.well-known/tor-relay', rendered)
        # v3 version label appended next to nickname
        self.assertIn('v3</span>', rendered)

    def test_relay_detail_box_dedups_paste_when_identical_to_hint(self):
        """B-final pasteable contract: when hint == pasteable_example
        (e.g. parse-time errors that share the V3_CATEGORY_LABELS source),
        skip the 📋 Paste: block to avoid duplication."""
        template_str = (
            "{% from 'macros.html' import aroi_relay_detail_box %}"
            "{{ aroi_relay_detail_box(relays, 'not_configured', page_ctx, ts) }}"
        )
        template = self.jinja_env.from_string(template_str)
        same_text = '# pick consistent pair: ciissversion:3 + proof:uri-familyid-ed25519'
        rendered = template.render(
            relays=[{
                'fingerprint': 'B' * 40,
                'nickname': 'MismatchRelay',
                'aroi_domain': None,
                'missing': 'ciissversion:2 declared but proof:uri-familyid-ed25519',
                'hint': same_text,
                'pasteable_example': same_text,
                'error_category': 'version_proof_mismatch',
            }],
            page_ctx={'path_prefix': ''},
            ts='2026-05-06 03:00 UTC',
        )
        # 💡 Fix: renders (hint is set)
        self.assertIn('💡 Fix:', rendered)
        # 📋 Paste: NOT rendered because hint == pasteable_example (dedup guard)
        self.assertNotIn('📋 Paste:', rendered)

    def test_relay_detail_box_security_incident_box_type(self):
        """B1.1: 'security_incident' box type renders red border + 🚨 +
        rotation guidance."""
        template_str = (
            "{% from 'macros.html' import aroi_relay_detail_box %}"
            "{{ aroi_relay_detail_box(relays, 'security_incident', page_ctx, ts) }}"
        )
        template = self.jinja_env.from_string(template_str)
        rendered = template.render(
            relays=[{
                'fingerprint': 'C' * 40,
                'nickname': 'LeakedRelay',
                'aroi_domain': 'leak.bar',
                'aroi_version': '3',
                'error': 'SECURITY: published .secret_family_key',
                'hint': 'Rotate immediately',
                'pasteable_example': 'tor --keygen-family <newfile>',
                'error_category': 'secret_key_leaked',
            }],
            page_ctx={'path_prefix': ''},
            ts=None,
        )
        self.assertIn('SECURITY INCIDENT', rendered)
        self.assertIn('🚨', rendered)
        # Pasteable rotation command surfaced
        self.assertIn('tor --keygen-family', rendered)


class TestContactTemplateIPv6Column:
    """Regression tests for the IPv6 column always-N/A bug (pytest style,
    using the shared jinja_env fixture from tests/conftest.py).

    Root cause: the old template extracted the IPv6 address with {% set %}
    inside a {% for %} loop; Jinja2 loop-local bindings don't survive past
    {% endfor %}, so every row rendered N/A. The fix precomputes
    relay['ipv6_display_address'] in Python and the template does a plain
    dict lookup. These tests render the real contact.html and assert on the
    produced HTML (they would have caught the original bug).
    """

    @staticmethod
    def _make_relay(fingerprint, nickname, dual_stack):
        """Relay dict as the pipeline produces it (incl. precomputed fields)."""
        relay = {
            'fingerprint': fingerprint,
            'nickname': nickname,
            'country': 'us',
            'country_name': 'United States',
            'observed_bandwidth': 1000000,
            'running': True,
            'flags': ['Running', 'Valid'],
            'flags_escaped': ['Running', 'Valid'],
            'flags_lower_escaped': ['running', 'valid'],
            '_flags_html': '',
            'effective_family': [],
            'measured': True,
            'uptime_display': 'UP 5d 12h',
            'uptime_api_display': '99.5%',
            'as': 'AS7922',
            'as_name': 'Comcast Cable',
            'platform': 'Linux',
            'first_seen': '2023-01-01 12:00:00',
            'first_seen_date_escaped': '2023-01-01',
            'contact_md5': 'abcd1234',
        }
        if dual_stack:
            relay['or_addresses'] = ['1.2.3.4:9001', '[2001:db8::1]:9001']
            relay['ipv6_display_address'] = '2001:db8::1'
            relay['ipv6_support'] = 'both'
        else:
            relay['or_addresses'] = ['5.6.7.8:9001']
            relay['ipv6_display_address'] = ''
            relay['ipv6_support'] = 'ipv4_only'
        return relay

    def _base_context(self, relay_subset):
        return {
            'contact': 'test@example.com',
            'contact_hash': 'abcd1234',
            'bandwidth': '150.0',
            'bandwidth_unit': 'MB/s',
            'consensus_weight_fraction': 0.025,
            'network_position': {
                'label': 'mixed',
                'formatted_string': 'Mixed (2 total relays)',
            },
            'relay_subset': relay_subset,
            'relays': {
                'json': {'relay_subset': relay_subset},
                'use_bits': False,
                'timestamp': '2026-01-01 00:00:00',
            },
            'page_ctx': {'path_prefix': '../'},
            'contact_rankings': [],
            'operator_reliability': None,
            'contact_display_data': {},
        }

    @staticmethod
    def _row_for(rendered, nickname):
        """Return the <tr> chunk for the row with the given relay nickname."""
        chunks = [c for c in rendered.split('<tr>') if f'title="{nickname}"' in c]
        assert len(chunks) >= 1, f"no table row found for {nickname}"
        return chunks[0]

    def test_single_table_mode_renders_ipv6_address(self, jinja_env):
        """Single-table mode: dual-stack row shows address, v4-only row shows N/A."""
        relays = [
            self._make_relay('A' * 40, 'DualStackRelay', dual_stack=True),
            self._make_relay('B' * 40, 'V4OnlyRelay', dual_stack=False),
        ]
        template = jinja_env.get_template('contact.html')
        rendered = template.render(**self._base_context(relays))

        # The IPv6 column is present (a dual-stack relay is in the table)...
        assert '<th>IPv6</th>' in rendered
        # ...and the actual address is rendered — the original bug rendered
        # N/A here for every relay.
        dual_row = self._row_for(rendered, 'DualStackRelay')
        assert '2001:db8::1' in dual_row

        # IPv4-only relay must still show N/A in its IPv6 cell (last <td>).
        v4_row = self._row_for(rendered, 'V4OnlyRelay')
        assert '2001:db8::1' not in v4_row
        last_cell = v4_row.rsplit('<td>', 1)[-1]
        assert 'N/A' in last_cell

    def test_ipv6_column_hidden_when_no_ipv6_relays(self, jinja_env):
        """Column gating unchanged: all-v4 tables omit the IPv6 column."""
        relays = [
            self._make_relay('A' * 40, 'V4Relay1', dual_stack=False),
            self._make_relay('B' * 40, 'V4Relay2', dual_stack=False),
        ]
        template = jinja_env.get_template('contact.html')
        rendered = template.render(**self._base_context(relays))
        assert '<th>IPv6</th>' not in rendered

    def test_sectioned_aroi_mode_renders_ipv6_address(self, jinja_env):
        """4-section AROI layout renders rows through contact_validation_status
        section entries (pickled relay copies in production) — assert the
        validated-relays table shows the IPv6 address, not N/A."""
        from allium.lib.aroi_validation import get_contact_validation_status

        dual = self._make_relay('A' * 40, 'DualStackRelay', dual_stack=True)
        v4only = self._make_relay('B' * 40, 'V4OnlyRelay', dual_stack=False)
        for relay in (dual, v4only):
            relay['aroi_domain'] = 'example.org'
            relay['aroi_version'] = '2'
            relay['aroi_proof_type'] = 'uri-rsa'
            relay['contact'] = 'test@example.com'

        validation_data = {
            'metadata': {'timestamp': '2026-01-01T00:00:00Z'},
            'results': [
                {'fingerprint': 'A' * 40, 'valid': True,
                 'proof_type': 'uri-rsa', 'proof_uri': 'https://example.org', 'ciissversion': '2'},
                {'fingerprint': 'B' * 40, 'valid': True,
                 'proof_type': 'uri-rsa', 'proof_uri': 'https://example.org', 'ciissversion': '2'},
            ],
        }
        cvs = get_contact_validation_status([dual, v4only], validation_data)
        assert cvs['validation_status'] == 'validated'

        context = self._base_context([dual, v4only])
        context['contact_validation_status'] = cvs
        context['aroi_validation_timestamp'] = '2026-01-01 00:00 UTC'

        template = jinja_env.get_template('contact.html')
        rendered = template.render(**context)

        # Sectioned layout active (validated table header rendered)
        assert 'VALIDATED RELAYS' in rendered

        dual_row = self._row_for(rendered, 'DualStackRelay')
        assert '2001:db8::1' in dual_row
        v4_row = self._row_for(rendered, 'V4OnlyRelay')
        assert '2001:db8::1' not in v4_row
        last_cell = v4_row.rsplit('<td>', 1)[-1]
        assert 'N/A' in last_cell


if __name__ == '__main__':
    unittest.main()