#!/usr/bin/env python3

"""
Test suite for directory authorities template rendering
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import shutil

# Add lib to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from jinja2 import Environment, FileSystemLoader

class TestTemplateRendering(unittest.TestCase):
    """Test directory authorities template rendering"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        
        # Create template environment
        template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        
        # Mock authorities data
        self.mock_authorities = [
            {
                'nickname': 'moria1',
                'fingerprint': '9695DFC35FFEB861329B9F1AB04C46397020CE31',
                'running': True,
                'as': 'AS3',
                'as_name': 'MIT',
                'country_name': 'United States',
                'uptime_1month': 99.1,
                'uptime_6months': 98.7,
                'uptime_1year': 97.8,
                'uptime_5years': 96.8,
                'uptime_zscore': 0.1,
                'version': '0.4.8.12',
                'platform': 'Tor 0.4.8.12 on Linux',
                'first_seen': '2015-03-11 20:00:00',
                'last_restarted': '2025-05-29 08:18:56',
                'last_seen': '2025-01-01 00:00:00'
            },
            {
                'nickname': 'dannenberg',
                'fingerprint': '7BE683E65D48141321C5ED92F075C55364AC7123',
                'running': True,
                'as': 'AS39788',
                'as_name': 'Chaos Computer Club e.V.',
                'country_name': 'Germany',
                'uptime_1month': 89.1,
                'uptime_6months': 85.7,
                'uptime_1year': 82.1,
                'uptime_5years': 78.5,
                'uptime_zscore': -1.2,
                'version': '0.4.7.16',
                'platform': 'Tor 0.4.7.16 on Linux',
                'first_seen': '2018-03-22 18:00:00',
                'last_restarted': '2025-04-12 09:15:42',
                'last_seen': '2025-01-01 00:00:00'
            }
        ]
        
        # Mock template variables using new attribute structure
        self.template_vars = {
            'relays': Mock(
                timestamp='Mon, 01 Jan 2025 00:00:00 GMT',
                json={'relays': [{'nickname': 'TestRelay'}]},
                authorities_data=self.mock_authorities,
                authorities_summary={
                    'total_authorities': 2,
                    'above_average_uptime': [self.mock_authorities[0]],
                    'below_average_uptime': [],
                    'problem_uptime': [self.mock_authorities[1]],
                }
            ),
            'path_prefix': '../'
        }

    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.test_dir)

    def test_template_compilation(self):
        """Test that the template compiles without syntax errors"""
        try:
            template = self.env.get_template("misc-authorities.html")
            self.assertIsNotNone(template)
        except Exception as e:
            self.fail(f"Template compilation failed: {e}")

    def test_template_rendering(self):
        """Test that the template renders with mock data"""
        try:
            template = self.env.get_template("misc-authorities.html")
            rendered_html = template.render(**self.template_vars)
            
            # Basic content checks
            self.assertIn("Directory Authorities by Network Health", rendered_html)
            self.assertIn("moria1", rendered_html)
            self.assertIn("dannenberg", rendered_html)
            self.assertIn("Version Compliance:", rendered_html)
            self.assertIn("Uptime (1 month):", rendered_html)
            
            # Check for proper structure
            self.assertIn("<!doctype html>", rendered_html.lower())
            self.assertIn('<html lang="en">', rendered_html.lower())
            self.assertIn("</html>", rendered_html.lower())
            self.assertIn("<table", rendered_html.lower())
            self.assertIn("</table>", rendered_html.lower())
            
        except Exception as e:
            self.fail(f"Template rendering failed: {e}")

    def test_template_empty_data(self):
        """Test template with empty authority data"""
        empty_vars = {
            'relays': Mock(
                timestamp='Mon, 01 Jan 2025 00:00:00 GMT',
                json={'relays': []},
                authorities_data=[],
                authorities_summary={
                    'total_authorities': 0,
                    'above_average_uptime': [],
                    'below_average_uptime': [],
                    'problem_uptime': [],
                }
            ),
            'path_prefix': '../'
        }
        
        try:
            template = self.env.get_template("misc-authorities.html")
            rendered_html = template.render(**empty_vars)
            
            # Should still contain basic structure
            self.assertIn("Directory Authorities by Network Health", rendered_html)
            self.assertIn("0 authorities", rendered_html)
            
        except Exception as e:
            self.fail(f"Template rendering with empty data failed: {e}")

    def test_template_special_cases(self):
        """Test template with special case data (None values, edge cases)"""
        special_authority = {
            'nickname': 'test_auth',
            'fingerprint': 'ABCD1234567890ABCD1234567890ABCD12345678',
            'running': False,  # Offline
            'as': None,
            'as_name': None,
            'country_name': None,
            'uptime_1month': None,
            'uptime_6months': None,
            'uptime_1year': None,
            'uptime_5years': None,
            'uptime_zscore': None,
            'version': None,
            'platform': None,
            'first_seen': None,
            'last_restarted': None,
            'last_seen': '2025-01-01 00:00:00'
        }
        
        special_vars = {
            'relays': Mock(
                timestamp='Mon, 01 Jan 2025 00:00:00 GMT',
                json={'relays': []},
                authorities_data=[special_authority],
                authorities_summary={
                    'total_authorities': 1,
                    'above_average_uptime': [],
                    'below_average_uptime': [],
                    'problem_uptime': [],
                }
            ),
            'path_prefix': '../'
        }
        
        try:
            template = self.env.get_template("misc-authorities.html")
            rendered_html = template.render(**special_vars)
            
            # Should handle None/empty values gracefully
            self.assertIn("test_auth", rendered_html)
            self.assertIn("Offline", rendered_html)
            self.assertIn("N/A", rendered_html)
            self.assertIn("Unknown", rendered_html)
            
        except Exception as e:
            self.fail(f"Template rendering with special cases failed: {e}")


if __name__ == '__main__':
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestTemplateRendering))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1) 