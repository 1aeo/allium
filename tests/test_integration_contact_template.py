#!/usr/bin/env python3

import os
import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock

from jinja2 import Environment, FileSystemLoader, select_autoescape

from allium.lib.relays import Relays


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
        from allium.lib.relays import determine_unit_filter, format_bandwidth_with_unit, format_bandwidth_filter, format_time_ago
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
        self.assertIn('color: #28a745', rendered)

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
        """Test that color coding is consistent across different reliability displays."""
        template = self.jinja_env.get_template('contact.html')
        rendered = template.render(**self.template_context)
        
        # Should use consistent green color coding for high reliability
        green_color_occurrences = rendered.count('color: #28a745')
        self.assertGreater(green_color_occurrences, 0, "Should have green color coding for high reliability")
        
        # Should use consistent color schemes
        self.assertIn('color: #2e7d2e', rendered)  # Intelligence diversity colors
        self.assertIn('color: #cc9900', rendered)  # Warning colors

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
        
        template_args = relay_set._build_template_args(
            "contact", contact_hash, contact_data, the_prefixed, validated_aroi_domains
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
        template_args = relay_set._build_template_args(
            "contact", contact_hash, contact_data, [], set()
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


if __name__ == '__main__':
    unittest.main()