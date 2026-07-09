#!/usr/bin/env python3

"""
Test suite for directory authorities functionality
"""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch, mock_open

from allium.lib.relays import Relays


class TestDirectoryAuthorities(unittest.TestCase):
    """Test directory authorities functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.test_onionoo_url = "https://test.onionoo.url/details"
        
        # Mock authority data
        self.mock_authorities_response = {
            "version": "10.0",
            "build_revision": "unknown",
            "relays_published": "2025-01-01 00:00:00",
            "relays_skipped": 0,
            "relays_truncated": 0,
            "relays": [
                {
                    "nickname": "moria1",
                    "fingerprint": "9695DFC35FFEB861329B9F1AB04C46397020CE31",  
                    "running": True,
                    "flags": ["Authority", "Running", "Stable", "V2Dir", "Valid"],
                    "country": "US",
                    "country_name": "United States",
                    "as": "AS3",
                    "as_name": "MIT",
                    "contact": "tor-ops@mit.edu",
                    "version": "0.4.8.12",
                    "platform": "Tor 0.4.8.12 on Linux",
                    "first_seen": "2015-03-11 20:00:00",
                    "last_restarted": "2025-05-29 08:18:56",
                    "last_seen": "2025-01-01 00:00:00"
                },
                {
                    "nickname": "tor26", 
                    "fingerprint": "847B1F850344D7876491A54892F904934E4EB85D",
                    "running": True,
                    "flags": ["Authority", "Running", "Stable", "V2Dir", "Valid"],
                    "country": "AT",
                    "country_name": "Austria", 
                    "as": "AS5404",
                    "as_name": "conova communications GmbH",
                    "contact": "tor-ops@conova.com",
                    "version": "0.4.8.12",
                    "platform": "Tor 0.4.8.12 on Linux",
                    "first_seen": "2015-07-30 10:15:00",
                    "last_restarted": "2025-05-31 13:28:19",
                    "last_seen": "2025-01-01 00:00:00"
                },
                {
                    "nickname": "dannenberg",
                    "fingerprint": "7BE683E65D48141321C5ED92F075C55364AC7123",
                    "running": True,
                    "flags": ["Authority", "Running", "Stable", "V2Dir", "Valid"],
                    "country": "DE",
                    "country_name": "Germany",
                    "as": "AS39788", 
                    "as_name": "Chaos Computer Club e.V.",
                    "contact": "tor-ops@ccc.de",
                    "version": "0.4.7.16",  # Outdated version
                    "platform": "Tor 0.4.7.16 on Linux",
                    "first_seen": "2018-03-22 18:00:00",
                    "last_restarted": "2025-04-12 09:15:42", 
                    "last_seen": "2025-01-01 00:00:00"
                }
            ]
        }
        
        # Mock uptime data
        self.mock_uptime_response = {
            "version": "10.0",
            "build_revision": "unknown",
            "relays_published": "2025-01-01 00:00:00",
            "relays": [
                {
                    "fingerprint": "9695DFC35FFEB861329B9F1AB04C46397020CE31",
                    "uptime": {
                        "1_month": {
                            "factor": 0.01,
                            "count": 720,
                            "values": [99.2, 98.8, 99.1, 99.0, 98.9]  # Good uptime
                        },
                        "6_months": {
                            "factor": 0.01,
                            "count": 4320,
                            "values": [98.5, 98.8, 99.0, 98.7, 98.6]
                        },
                        "1_year": {
                            "factor": 0.01,
                            "count": 8760,
                            "values": [97.5, 97.8, 98.0, 97.9, 97.6]
                        },
                        "5_years": {
                            "factor": 0.01,
                            "count": 43800,
                            "values": [96.8, 97.0, 97.2, 96.9, 96.7]
                        }
                    }
                },
                {
                    "fingerprint": "847B1F850344D7876491A54892F904934E4EB85D", 
                    "uptime": {
                        "1_month": {
                            "factor": 0.01,
                            "count": 720,
                            "values": [99.8, 99.6, 99.7, 99.5, 99.9]  # Excellent uptime
                        },
                        "6_months": {
                            "factor": 0.01,
                            "count": 4320,
                            "values": [99.6, 99.4, 99.5, 99.3, 99.7]
                        },
                        "1_year": {
                            "factor": 0.01,
                            "count": 8760,
                            "values": [99.1, 99.0, 99.2, 98.9, 99.3]
                        },
                        "5_years": {
                            "factor": 0.01,
                            "count": 43800,
                            "values": [98.7, 98.5, 98.9, 98.6, 98.8]
                        }
                    }
                },
                {
                    "fingerprint": "7BE683E65D48141321C5ED92F075C55364AC7123",
                    "uptime": {
                        "1_month": {
                            "factor": 0.01,
                            "count": 720,
                            "values": [89.2, 88.5, 90.1, 87.8, 89.9]  # Poor uptime
                        },
                        "6_months": {
                            "factor": 0.01,
                            "count": 4320,
                            "values": [85.7, 86.2, 85.0, 86.8, 85.3]
                        },
                        "1_year": {
                            "factor": 0.01,
                            "count": 8760,
                            "values": [82.1, 83.0, 81.5, 82.8, 81.9]
                        },
                        "5_years": {
                            "factor": 0.01,
                            "count": 43800,
                            "values": [78.5, 79.2, 78.0, 79.8, 78.1]
                        }
                    }
                }
            ]
        }

    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.test_dir)

    def test_get_directory_authorities_data(self):
        """Test directory authorities data processing"""
        # Create Relays instance with mock authority data
        mock_relay_data = {
            "relays": [
                {
                    "nickname": "moria1",
                    "fingerprint": "9695DFC35FFEB861329B9F1AB04C46397020CE31",  
                    "running": True,
                    "flags": ["Authority", "Running", "Stable", "V2Dir", "Valid"],
                    "country": "US",
                    "country_name": "United States",
                    "version": "0.4.8.12",
                    "platform": "Tor 0.4.8.12 on Linux",
                    "first_seen": "2015-03-11 20:00:00",
                    "observed_bandwidth": 1000000,
                    "consensus_weight": 5000,
                    "uptime_percentages": {
                        "1_month": 99.2,
                        "6_months": 98.5,
                        "1_year": 97.5,
                        "5_years": 96.8
                    }
                },
                {
                    "nickname": "regular_relay",
                    "fingerprint": "ABCD1234567890ABCD1234567890ABCD12345678",
                    "running": True,
                    "flags": ["Running", "Valid"],  # No Authority flag
                    "observed_bandwidth": 1000000,
                    "consensus_weight": 3000,
                    "first_seen": "2024-01-01 12:00:00",
                    "platform": "Tor 0.4.8.12 on Linux"
                }
            ]
        }
        
        relays = Relays(self.test_dir, self.test_onionoo_url, mock_relay_data)
        
        # Test authorities data extraction
        authorities_info = relays._get_directory_authorities_data()
        
        # Verify structure
        self.assertIn('authorities_data', authorities_info)
        self.assertIn('authorities_summary', authorities_info)
        
        # Verify only authorities are returned (not regular relays).
        # Exclude hardcoded known-offline placeholders (e.g. gabelmoo) that are merged
        # in for historical context; they are not part of the dynamic Onionoo set.
        dynamic_authorities = [a for a in authorities_info['authorities_data']
                               if not a.get('is_known_offline')]
        self.assertEqual(len(dynamic_authorities), 1)
        self.assertEqual(dynamic_authorities[0]['nickname'], 'moria1')
        
        # Verify summary (authority-flag count excludes offline placeholders)
        self.assertEqual(authorities_info['authorities_summary']['total_authorities'], 1)

    @patch('urllib.request.urlopen')
    def test_process_directory_authorities(self, mock_urlopen):
        """Test processing of directory authority data"""
        # Mock the main details response for Relays __init__ with authority data included
        main_response_with_authorities = {
            "relays": [
                {
                    "nickname": "moria1",
                    "fingerprint": "9695DFC35FFEB861329B9F1AB04C46397020CE31",  
                    "running": True,
                    "flags": ["Authority", "Running", "Stable", "V2Dir", "Valid"],
                    "country": "US",
                    "country_name": "United States",
                    "as": "AS3",
                    "as_name": "MIT",
                    "contact": "tor-ops@mit.edu",
                    "version": "0.4.8.12",
                    "platform": "Tor 0.4.8.12 on Linux",
                    "first_seen": "2015-03-11 20:00:00",
                    "last_restarted": "2025-05-29 08:18:56",
                    "last_seen": "2025-01-01 00:00:00",
                    "observed_bandwidth": 1000000
                },
                {
                    "nickname": "tor26", 
                    "fingerprint": "847B1F850344D7876491A54892F904934E4EB85D",
                    "running": True,
                    "flags": ["Authority", "Running", "Stable", "V2Dir", "Valid"],
                    "country": "AT",
                    "country_name": "Austria", 
                    "as": "AS5404",
                    "as_name": "conova communications GmbH",
                    "contact": "tor-ops@conova.com",
                    "version": "0.4.8.12",
                    "platform": "Tor 0.4.8.12 on Linux",
                    "first_seen": "2015-07-30 10:15:00",
                    "last_restarted": "2025-05-31 13:28:19",
                    "last_seen": "2025-01-01 00:00:00",
                    "observed_bandwidth": 1000000
                },
                {
                    "nickname": "dannenberg",
                    "fingerprint": "7BE683E65D48141321C5ED92F075C55364AC7123",
                    "running": True,
                    "flags": ["Authority", "Running", "Stable", "V2Dir", "Valid"],
                    "country": "DE",
                    "country_name": "Germany",
                    "as": "AS39788", 
                    "as_name": "Chaos Computer Club e.V.",
                    "contact": "tor-ops@ccc.de",
                    "version": "0.4.7.16",  # Outdated version
                    "platform": "Tor 0.4.7.16 on Linux",
                    "first_seen": "2018-03-22 18:00:00",
                    "last_restarted": "2025-04-12 09:15:42", 
                    "last_seen": "2025-01-01 00:00:00",
                    "observed_bandwidth": 1000000
                },
                {
                    "nickname": "regular_relay",
                    "fingerprint": "ABCD1234567890ABCD1234567890ABCD12345678",
                    "running": True,
                    "flags": ["Running", "Valid"],  # No Authority flag
                    "observed_bandwidth": 1000000,
                    "first_seen": "2024-01-01 00:00:00"
                }
            ]
        }
        
        # Mock sequential API calls: first details, then uptime
        details_response = Mock(read=Mock(return_value=json.dumps(main_response_with_authorities).encode('utf-8')))
        uptime_response = Mock(read=Mock(return_value=json.dumps(self.mock_uptime_response).encode('utf-8')))
        mock_urlopen.side_effect = [details_response, uptime_response]
        
        relays = Relays(self.test_dir, self.test_onionoo_url, main_response_with_authorities)
        
        authorities_info = relays._get_directory_authorities_data()
        authorities = authorities_info['authorities_data']
        
        # Verify we got expected number of authorities (only relays with Authority flag).
        # Exclude hardcoded known-offline placeholders (e.g. gabelmoo) merged in for context.
        dynamic_authorities = [a for a in authorities if not a.get('is_known_offline')]
        self.assertEqual(len(dynamic_authorities), 3)
        
        # Verify authorities are found (order may vary)
        nicknames = [auth['nickname'] for auth in dynamic_authorities]
        self.assertIn('dannenberg', nicknames)
        self.assertIn('moria1', nicknames)
        self.assertIn('tor26', nicknames)
        
        # Version compliance is now commented out, so we don't test for it
        # Verify z-score attributes are present (may be None if no uptime data)
        for auth in authorities:
            self.assertIn('uptime_zscore', auth)
            self.assertIn('uptime_outlier_status', auth)
            # With the mock data, there's no consolidated uptime results, so these should be None
            self.assertIsNone(auth['uptime_zscore'])
            self.assertEqual(auth['uptime_outlier_status'], 'insufficient_data')

    @patch('urllib.request.urlopen')
    def test_write_directory_authorities(self, mock_urlopen):
        """Test generation of directory authorities HTML page"""
        # Mock the main details response with authority data included
        main_response_with_authorities = {
            "relays": [
                {
                    "nickname": "moria1",
                    "fingerprint": "9695DFC35FFEB861329B9F1AB04C46397020CE31",  
                    "running": True,
                    "flags": ["Authority", "Running", "Stable", "V2Dir", "Valid"],
                    "country": "US",
                    "country_name": "United States",
                    "as": "AS3",
                    "as_name": "MIT",
                    "contact": "tor-ops@mit.edu",
                    "version": "0.4.8.12",
                    "platform": "Tor 0.4.8.12 on Linux",
                    "first_seen": "2015-03-11 20:00:00",
                    "last_restarted": "2025-05-29 08:18:56",
                    "last_seen": "2025-01-01 00:00:00",
                    "observed_bandwidth": 1000000
                }
            ]
        }
        
        # Mock sequential API calls: first details, then uptime
        details_response = Mock(read=Mock(return_value=json.dumps(main_response_with_authorities).encode('utf-8')))
        uptime_response = Mock(read=Mock(return_value=json.dumps(self.mock_uptime_response).encode('utf-8')))
        mock_urlopen.side_effect = [details_response, uptime_response]
        
        relays = Relays(self.test_dir, self.test_onionoo_url, main_response_with_authorities)
        
        # Call write_misc directly since write_directory_authorities no longer exists
        relays.write_misc(
            template="misc-authorities.html",
            path="misc/authorities.html"
        )
        
        # Verify authority data and summary were stored as attributes
        self.assertTrue(hasattr(relays, 'authorities_data'))
        self.assertTrue(hasattr(relays, 'authorities_summary'))
        # Exclude hardcoded known-offline placeholders (e.g. gabelmoo) merged in for context.
        dynamic_authorities = [a for a in relays.authorities_data
                               if not a.get('is_known_offline')]
        self.assertEqual(len(dynamic_authorities), 1)
        self.assertEqual(relays.authorities_summary['total_authorities'], 1)
        
        # Verify output file was created
        output_file = os.path.join(self.test_dir, "misc", "authorities.html")
        self.assertTrue(os.path.exists(output_file))

    @patch('urllib.request.urlopen')
    def test_network_error_handling(self, mock_urlopen):
        """Test handling of network errors when fetching authority data"""
        # Mock successful details response but failed uptime response
        details_response = Mock(read=Mock(return_value=json.dumps({"relays": []}).encode('utf-8')))
        mock_urlopen.side_effect = [details_response, Exception("Network error")]
        
        empty_relay_data = {"relays": []}
        relays = Relays(self.test_dir, self.test_onionoo_url, empty_relay_data)
        
        # Should still work but authorities will have empty uptime data.
        # Exclude hardcoded known-offline placeholders (e.g. gabelmoo) merged in for context.
        authorities_info = relays._get_directory_authorities_data()
        dynamic_authorities = [a for a in authorities_info['authorities_data']
                               if not a.get('is_known_offline')]
        self.assertEqual(len(dynamic_authorities), 0)  # No authorities since no relays with Authority flag

    @patch('urllib.request.urlopen')
    def test_uptime_edge_cases(self, mock_urlopen):
        """Test edge cases in uptime processing"""
        # Mock response with authority but missing uptime data
        main_response_with_authority = {
            "relays": [{
                "nickname": "test_auth",
                "fingerprint": "ABCD1234567890ABCD1234567890ABCD12345678",
                "running": True,
                "flags": ["Authority", "Running"],  # Include Authority flag
                "version": "0.4.8.12",
                "observed_bandwidth": 1000000,
                "first_seen": "2024-01-01 00:00:00"
            }]
        }
        
        uptime_no_data = {"relays": []}
        
        # Mock sequential API calls: details with authority data, uptime with no data
        details_response = Mock(read=Mock(return_value=json.dumps(main_response_with_authority).encode('utf-8')))
        uptime_response = Mock(read=Mock(return_value=json.dumps(uptime_no_data).encode('utf-8')))
        mock_urlopen.side_effect = [details_response, uptime_response]
        
        relays = Relays(self.test_dir, self.test_onionoo_url, main_response_with_authority)
        
        authorities_info = relays._get_directory_authorities_data()
        authorities = authorities_info['authorities_data']
        
        # Should handle missing uptime gracefully.
        # Exclude hardcoded known-offline placeholders (e.g. gabelmoo) merged in for context.
        dynamic_authorities = [a for a in authorities if not a.get('is_known_offline')]
        self.assertEqual(len(dynamic_authorities), 1)
        # Note: The actual implementation may not set these fields if uptime data is missing
        # The test focuses on proper handling without errors

    def test_zscore_calculation(self):
        """Test Z-score calculation for authority uptime analysis"""
        # Create mock data with authorities having different uptimes
        mock_authorities_data = {
            "relays": [
                {
                    "nickname": "good_auth",
                    "fingerprint": "GOOD1234567890ABCD1234567890ABCD12345678",
                    "running": True,
                    "flags": ["Authority", "Running"],
                    "uptime_percentages": {"1_month": 99.5},  # High uptime
                    "observed_bandwidth": 1000000,
                    "first_seen": "2024-01-01 00:00:00",
                    "platform": "Tor 0.4.8.12 on Linux",
                    "consensus_weight": 3000
                },
                {
                    "nickname": "avg_auth", 
                    "fingerprint": "AVG1234567890ABCD1234567890ABCD12345678",
                    "running": True,
                    "flags": ["Authority", "Running"],
                    "uptime_percentages": {"1_month": 98.0},  # Average uptime
                    "observed_bandwidth": 1000000,
                    "first_seen": "2024-01-01 00:00:00",
                    "platform": "Tor 0.4.8.12 on Linux",
                    "consensus_weight": 3000
                },
                {
                    "nickname": "poor_auth",
                    "fingerprint": "POOR1234567890ABCD1234567890ABCD12345678", 
                    "running": True,
                    "flags": ["Authority", "Running"],
                    "uptime_percentages": {"1_month": 95.0},  # Poor uptime
                    "observed_bandwidth": 1000000,
                    "first_seen": "2024-01-01 00:00:00",
                    "platform": "Tor 0.4.8.12 on Linux",
                    "consensus_weight": 3000
                }
            ]
        }
        
        relays = Relays(self.test_dir, self.test_onionoo_url, mock_authorities_data)
        
        # Mock consolidated uptime results to enable Z-score calculation
        relays._consolidated_uptime_results = {
            "network_flag_statistics": {
                "Authority": {
                    "1_month": {
                        "mean": 97.5,
                        "std_dev": 1.5,
                        "two_sigma_low": 94.5,
                        "two_sigma_high": 100.5
                    }
                }
            }
        }
        
        authorities_info = relays._get_directory_authorities_data()
        authorities = authorities_info['authorities_data']
        
        # Test Z-score calculation and classification
        good_auth = next(auth for auth in authorities if auth['nickname'] == 'good_auth')
        avg_auth = next(auth for auth in authorities if auth['nickname'] == 'avg_auth')
        poor_auth = next(auth for auth in authorities if auth['nickname'] == 'poor_auth')
        
        # Z-scores should be calculated
        self.assertIsNotNone(good_auth['uptime_zscore'])
        self.assertIsNotNone(avg_auth['uptime_zscore'])
        self.assertIsNotNone(poor_auth['uptime_zscore'])
        
        # Good authority should have positive Z-score
        self.assertGreater(good_auth['uptime_zscore'], 0)
        
        # Poor authority should have negative Z-score
        self.assertLess(poor_auth['uptime_zscore'], 0)

    def test_version_compliance_check(self):
        """Test version compliance logic - DISABLED: Version compliance commented out until consensus-health data available"""
        # This test is commented out since version compliance is disabled
        # until we have real consensus-health API data
        pass
        
        # # This test doesn't need network mocking since it tests logic
        # with patch('urllib.request.urlopen') as mock_main:
        #     mock_main.return_value.read.return_value = json.dumps({"relays": []}).encode('utf-8')
        #     relays = Relays(self.test_dir, self.test_onionoo_url)
        # 
        # # Test version compliance
        # test_cases = [
        #     ("0.4.8.12", "0.4.8.12", True),   # Exact match
        #     ("0.4.8.11", "0.4.8.12", False),  # Outdated
        #     ("0.4.9.0", "0.4.8.12", False),   # Different version
        #     ("", "0.4.8.12", False),          # Empty version
        #     (None, "0.4.8.12", False),        # None version
        # ]
        # 
        # for current, recommended, expected in test_cases:
        #     # Simulate authority data
        #     auth = {"version": current}
        #     auth["recommended_version"] = recommended
        #     auth["version_compliant"] = auth.get('version', '') == recommended
        #     
        #     self.assertEqual(auth["version_compliant"], expected,
        #                    f"Version compliance check failed for {current} vs {recommended}")

    @patch('urllib.request.urlopen')
    def test_no_authorities_found(self, mock_urlopen):
        """Test handling when no directory authorities are found in relay data"""
        # Mock response with no authorities (no relays with Authority flag)
        main_response_no_authorities = {
            "relays": [
                {
                    "nickname": "regular_relay",
                    "fingerprint": "ABCD1234567890ABCD1234567890ABCD12345678",
                    "running": True,
                    "flags": ["Running", "Valid"],  # No Authority flag
                    "observed_bandwidth": 1000000,
                    "first_seen": "2024-01-01 00:00:00"
                }
            ]
        }
        
        # Mock sequential API calls: details with no authorities, uptime (doesn't matter for this test)
        details_response = Mock(read=Mock(return_value=json.dumps(main_response_no_authorities).encode('utf-8')))
        uptime_response = Mock(read=Mock(return_value=json.dumps({"relays": []}).encode('utf-8')))
        mock_urlopen.side_effect = [details_response, uptime_response]
        
        relays = Relays(self.test_dir, self.test_onionoo_url, main_response_no_authorities)
        
        # Exclude hardcoded known-offline placeholders (e.g. gabelmoo) merged in for context.
        authorities_info = relays._get_directory_authorities_data()
        dynamic_authorities = [a for a in authorities_info['authorities_data']
                               if not a.get('is_known_offline')]
        self.assertEqual(len(dynamic_authorities), 0)


    def test_template_validation(self):
        """Test that authorities template renders with minimal data"""
        # Minimal authority data for template testing
        minimal_authority_data = {
            "relays": [{
                "nickname": "test_auth",
                "fingerprint": "ABCD1234567890ABCD1234567890ABCD12345678",
                "running": True,
                "flags": ["Authority", "Running"],
                "first_seen": "2024-01-01 00:00:00",
                "platform": "Tor 0.4.8.12 on Linux",
                "observed_bandwidth": 1000000,
                "consensus_weight": 3000
            }]
        }
        
        relays = Relays(self.test_dir, self.test_onionoo_url, minimal_authority_data)
        
        # Test template compilation and rendering
        try:
            relays.write_misc(
                template="misc-authorities.html",
                path="misc/authorities.html"
            )
            
            # Verify output file was created and has content
            output_file = os.path.join(self.test_dir, "misc", "authorities.html")
            self.assertTrue(os.path.exists(output_file))
            
            with open(output_file, 'r') as f:
                content = f.read()
                
            # Basic content validation
            self.assertIn("test_auth", content)
            self.assertIn("Directory Authorities", content)
            self.assertIn("authorities discovered", content)
            
        except Exception as e:
            self.fail(f"Template rendering failed: {e}")


class TestAuthorityIntegration(unittest.TestCase):
    """Integration tests for directory authorities in full Allium workflow"""
    
    def setUp(self):
        """Set up integration test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        
        # Mock a minimal but complete onionoo response 
        self.mock_main_response = {
            "version": "10.0",
            "relays_published": "2025-01-01 00:00:00",
            "relays": [
                {
                    "nickname": "TestRelay",
                    "fingerprint": "ABCD1234567890ABCD1234567890ABCD12345678",
                    "running": True,
                    "observed_bandwidth": 1000000,
                    "flags": ["Running", "Valid"],
                    "first_seen": "2024-01-01 00:00:00",
                    "platform": "Tor 0.4.8.12 on Linux",
                    "consensus_weight": 3000
                }
            ]
        }

    def tearDown(self):
        """Clean up integration test fixtures"""
        shutil.rmtree(self.test_dir)

    @patch('urllib.request.urlopen')
    def test_allium_integration(self, mock_urlopen):
        """Test that authorities page integrates properly with Allium workflow"""
        # Mock sequential API calls: details and uptime
        details_response = Mock(read=Mock(return_value=json.dumps(self.mock_main_response).encode('utf-8')))
        uptime_response = Mock(read=Mock(return_value=json.dumps({"relays": []}).encode('utf-8')))
        mock_urlopen.side_effect = [details_response, uptime_response]
        
        # Create Relays instance (this would normally be done in allium.py)
        relays = Relays(self.test_dir, "https://test.onionoo.url/details", self.mock_main_response)
        
        # Verify Relays was created successfully 
        self.assertIsNotNone(relays.json)
        self.assertEqual(len(relays.json['relays']), 1)
        
        # Test that write_misc method can handle misc-authorities.html template
        self.assertTrue(hasattr(relays, 'write_misc'))
        self.assertTrue(callable(getattr(relays, 'write_misc')))
        
        # Test authorities processing integration
        try:
            relays.write_misc(
                template="misc-authorities.html", 
                path="misc/authorities.html"
            )
            # If no exception, integration is working
        except Exception as e:
            self.fail(f"Authorities integration failed: {e}")


class TestKnownOfflineAuthorityMerge(unittest.TestCase):
    """Tests for retaining removed/offline authorities on the DA page (Task 5).

    A directory authority removed from the consensus eventually ages out of all live
    data sources, so it would vanish from the page. A small hardcoded list keeps such
    authorities visible (as offline) - but only when NOT present dynamically, and
    without ever affecting the voting/reachability counts.
    """

    GABELMOO_FP = 'F2044413DAC2E02E3D6BCF4735A19BCA1DE97281'

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_onionoo_url = "https://test.onionoo.url/details"

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _authorities_by_nick(self, authorities_info):
        return {a['nickname']: a for a in authorities_info['authorities_data']}

    def test_offline_authority_merged_when_absent(self):
        """gabelmoo absent from Onionoo -> appears as an offline, context-only row."""
        mock_relay_data = {
            "relays": [
                {
                    "nickname": "moria1",
                    "fingerprint": "9695DFC35FFEB861329B9F1AB04C46397020CE31",
                    "running": True,
                    "flags": ["Authority", "Running", "V2Dir", "Valid"],
                    "country": "US", "country_name": "United States",
                    "first_seen": "2015-03-11 20:00:00",
                    "platform": "Tor 0.4.8.12 on Linux",
                    "observed_bandwidth": 1000000, "consensus_weight": 5000,
                },
            ]
        }
        relays = Relays(self.test_dir, self.test_onionoo_url, mock_relay_data)
        info = relays._get_directory_authorities_data()
        by_nick = self._authorities_by_nick(info)

        # gabelmoo is merged in as offline / context-only
        self.assertIn('gabelmoo', by_nick)
        self.assertFalse(by_nick['gabelmoo']['running'])
        self.assertTrue(by_nick['gabelmoo'].get('is_known_offline'))
        # No broken relay link source: it carries an offline_note for the badge tooltip
        self.assertTrue(by_nick['gabelmoo'].get('offline_note'))

        # The live authority is untouched (not flagged offline)
        self.assertTrue(by_nick['moria1']['running'])
        self.assertFalse(by_nick['moria1'].get('is_known_offline', False))

        # Counts: dynamic authority-flag count EXCLUDES the hardcoded offline row
        self.assertEqual(info['authorities_summary']['total_with_authority_flag'], 1)
        # Offline summary (dynamic) reflects gabelmoo
        self.assertGreaterEqual(info['authorities_summary']['offline_count'], 1)
        self.assertIn('gabelmoo', info['authorities_summary']['offline_names'])
        # Alphabetical ordering preserved after merge
        nicks = [a['nickname'] for a in info['authorities_data']]
        self.assertEqual(nicks, sorted(nicks, key=str.lower))

    def test_offline_authority_not_duplicated_when_present(self):
        """gabelmoo present in Onionoo -> live row wins, no hardcoded duplicate."""
        mock_relay_data = {
            "relays": [
                {
                    "nickname": "moria1",
                    "fingerprint": "9695DFC35FFEB861329B9F1AB04C46397020CE31",
                    "running": True,
                    "flags": ["Authority", "Running", "V2Dir", "Valid"],
                    "country": "US", "country_name": "United States",
                    "first_seen": "2015-03-11 20:00:00",
                    "platform": "Tor 0.4.8.12 on Linux",
                    "observed_bandwidth": 1000000, "consensus_weight": 5000,
                },
                {
                    "nickname": "gabelmoo",
                    "fingerprint": self.GABELMOO_FP,
                    "running": True,
                    "flags": ["Authority", "Running", "V2Dir", "Valid"],
                    "country": "DE", "country_name": "Germany",
                    "first_seen": "2010-03-22 11:00:00",
                    "platform": "Tor 0.4.9.9 on Linux",
                    "observed_bandwidth": 9810000, "consensus_weight": 20,
                },
            ]
        }
        relays = Relays(self.test_dir, self.test_onionoo_url, mock_relay_data)
        info = relays._get_directory_authorities_data()

        gabelmoo_rows = [a for a in info['authorities_data'] if a['nickname'] == 'gabelmoo']
        self.assertEqual(len(gabelmoo_rows), 1)  # no duplicate
        # The live row wins: running True, not flagged as the hardcoded offline entry
        self.assertTrue(gabelmoo_rows[0]['running'])
        self.assertFalse(gabelmoo_rows[0].get('is_known_offline', False))
        # Both authorities online -> offline summary empty, and gabelmoo counted live
        self.assertEqual(info['authorities_summary']['offline_count'], 0)
        self.assertEqual(info['authorities_summary']['total_with_authority_flag'], 2)


if __name__ == '__main__':
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestDirectoryAuthorities))
    suite.addTests(loader.loadTestsFromTestCase(TestAuthorityIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestKnownOfflineAuthorityMerge))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1) 