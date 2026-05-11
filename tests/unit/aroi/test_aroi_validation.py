#!/usr/bin/env python3
"""
Test AROI validation module functionality.
Tests validation logic, error detection, and display filtering.

Updated for new categorization system:
- Operator statuses: validated | unauthorized | misconfigured | not_configured
- Relay categories: validated | unauthorized | misconfigured | incomplete_* | not_configured_*
"""

import unittest
from unittest.mock import Mock

from allium.lib.aroi_validation import (
    calculate_aroi_validation_metrics,
    get_contact_validation_status,
    _format_timestamp,
    _simplify_error_message,
    _simplify_and_categorize_errors
)


class TestAROIValidation(unittest.TestCase):
    """Test AROI validation functions."""
    
    def test_get_contact_validation_status_no_aroi(self):
        """Test contacts with no AROI return correct status."""
        relays = [{'fingerprint': 'ABC123', 'nickname': 'test1'}]
        result = get_contact_validation_status(relays, None)
        
        self.assertFalse(result['has_aroi'])
        self.assertEqual(result['validation_status'], 'not_configured')
        # New structure uses separate lists for each category
        self.assertEqual(len(result['validated_relays']), 0)
        self.assertEqual(len(result['unauthorized_relays']), 0)
        self.assertEqual(len(result['misconfigured_relays']), 0)
    
    def test_get_contact_validation_status_all_validated(self):
        """Test fully validated contact."""
        relays = [
            {'fingerprint': 'ABC123', 'nickname': 'test1', 'aroi_domain': 'example.com'}
        ]
        validation_data = {
            'results': [
                {'fingerprint': 'ABC123', 'valid': True, 'proof_type': 'uri-rsa'}
            ]
        }
        result = get_contact_validation_status(relays, validation_data)
        
        self.assertTrue(result['has_aroi'])
        self.assertEqual(result['validation_status'], 'validated')
        self.assertEqual(result['validation_summary']['validated_count'], 1)
        # New structure uses separate lists
        self.assertEqual(len(result['validated_relays']), 1)
        self.assertEqual(len(result['unauthorized_relays']), 0)
        self.assertEqual(len(result['misconfigured_relays']), 0)
    
    def test_get_contact_validation_status_mixed_validated_and_unauthorized(self):
        """Test contact with validated and unauthorized relays (formerly partially_validated)."""
        relays = [
            {'fingerprint': 'ABC123', 'nickname': 'test1', 'aroi_domain': 'example.com'},
            {'fingerprint': 'DEF456', 'nickname': 'test2', 'aroi_domain': 'example.com'}
        ]
        validation_data = {
            'results': [
                {'fingerprint': 'ABC123', 'valid': True, 'proof_type': 'uri-rsa'},
                {'fingerprint': 'DEF456', 'valid': False, 'error': 'Fingerprint not found', 'proof_type': 'uri-rsa'}
            ]
        }
        result = get_contact_validation_status(relays, validation_data)
        
        self.assertTrue(result['has_aroi'])
        # With at least 1 validated, status should be 'validated' (cascade logic)
        self.assertEqual(result['validation_status'], 'validated')
        self.assertEqual(result['validation_summary']['validated_count'], 1)
        # Unauthorized relays should be in their own list
        self.assertEqual(len(result['validated_relays']), 1)
        self.assertEqual(len(result['unauthorized_relays']), 1)
        self.assertEqual(result['validation_summary']['unauthorized_count'], 1)
    
    def test_show_detailed_errors_false_for_all_missing_aroi(self):
        """Test that contacts with 'Missing AROI fields' are not flagged as having AROI."""
        # These relays don't have all 3 required AROI fields (ciissversion:2, proof, url)
        # so aroi_domain should be 'none'
        relays = [
            {'fingerprint': 'ABC123', 'nickname': 'test1', 'aroi_domain': 'none'},
            {'fingerprint': 'DEF456', 'nickname': 'test2', 'aroi_domain': 'none'}
        ]
        validation_data = {
            'results': [
                {'fingerprint': 'ABC123', 'valid': False, 'error': 'Missing AROI fields'},
                {'fingerprint': 'DEF456', 'valid': False, 'error': 'Missing AROI fields'}
            ]
        }
        result = get_contact_validation_status(relays, validation_data)
        
        # Should not be considered as having AROI since they're missing required fields
        self.assertFalse(result['has_aroi'])
        self.assertEqual(result['validation_status'], 'not_configured')
        # All relays should be in not_configured_relays
        self.assertEqual(len(result['not_configured_relays']), 2)
    
    def test_calculate_aroi_validation_metrics_basic(self):
        """Test basic metrics calculation."""
        relays = [
            {'fingerprint': 'ABC123', 'aroi_domain': 'example.com'},
            {'fingerprint': 'DEF456', 'aroi_domain': 'none'}
        ]
        validation_data = {
            'metadata': {'timestamp': '2025-11-26T00:00:00Z'},
            'statistics': {
                'proof_types': {
                    'dns_rsa': {'total': 0, 'valid': 0, 'success_rate': 0.0},
                    'uri_rsa': {'total': 1, 'valid': 1, 'success_rate': 100.0}
                }
            },
            'results': [
                {'fingerprint': 'ABC123', 'valid': True, 'proof_type': 'uri-rsa'}
            ]
        }
        
        metrics = calculate_aroi_validation_metrics(relays, validation_data)
        
        self.assertTrue(metrics['validation_data_available'])
        self.assertGreater(metrics['aroi_validated_count'], 0)
    
    def test_format_timestamp(self):
        """Test timestamp formatting."""
        timestamp = '2025-11-26T12:00:00Z'
        formatted = _format_timestamp(timestamp)
        self.assertIn('2025-11-26', formatted)
        self.assertIn('UTC', formatted)
    
    def test_contact_without_aroi_fields_not_flagged(self):
        """Test that contacts without all 3 AROI fields are not flagged for validation."""
        # Relay has contact info but not all 3 required AROI fields
        relays = [
            {'fingerprint': 'ABC123', 'nickname': 'test1', 'aroi_domain': 'none', 'contact': 'email:test@example.com'}
        ]
        validation_data = {
            'results': [
                {'fingerprint': 'ABC123', 'valid': False, 'error': 'Missing AROI fields'}
            ]
        }
        result = get_contact_validation_status(relays, validation_data)
        
        # Should NOT be considered as having AROI
        self.assertFalse(result['has_aroi'])
        self.assertEqual(result['validation_status'], 'not_configured')
    
    def test_contact_with_aroi_fields_but_validation_failed_misconfigured(self):
        """Test that contacts with all 3 AROI fields but DNS/SSL errors are misconfigured."""
        # Relay has all 3 required fields so aroi_domain is extracted
        relays = [
            {'fingerprint': 'ABC123', 'nickname': 'test1', 'aroi_domain': 'example.com'}
        ]
        validation_data = {
            'results': [
                {'fingerprint': 'ABC123', 'valid': False, 'error': 'DNS lookup failed', 'proof_type': 'dns-rsa'}
            ]
        }
        result = get_contact_validation_status(relays, validation_data)
        
        # Should be considered as having AROI (all 3 fields present)
        self.assertTrue(result['has_aroi'])
        # DNS errors = misconfigured (not unauthorized)
        self.assertEqual(result['validation_status'], 'misconfigured')
        self.assertEqual(len(result['misconfigured_relays']), 1)
        self.assertTrue(result['show_detailed_errors'])
    
    def test_contact_with_aroi_fields_but_fingerprint_not_found_unauthorized(self):
        """Test that contacts with 'fingerprint not found' error are unauthorized."""
        relays = [
            {'fingerprint': 'ABC123', 'nickname': 'test1', 'aroi_domain': 'example.com'}
        ]
        validation_data = {
            'results': [
                {'fingerprint': 'ABC123', 'valid': False, 'error': 'Fingerprint not found in proof file', 'proof_type': 'uri-rsa'}
            ]
        }
        result = get_contact_validation_status(relays, validation_data)
        
        self.assertTrue(result['has_aroi'])
        # Fingerprint not found = unauthorized
        self.assertEqual(result['validation_status'], 'unauthorized')
        self.assertEqual(len(result['unauthorized_relays']), 1)
        self.assertEqual(result['validation_summary']['unauthorized_count'], 1)

    def test_contact_validation_status_handles_null_error(self):
        """Malformed validator entries should not crash contact page rendering."""
        relays = [
            {'fingerprint': 'ABC123', 'nickname': 'test1', 'aroi_domain': 'example.com'}
        ]
        validation_data = {
            'results': [
                {'fingerprint': 'ABC123', 'valid': False, 'error': None, 'proof_type': 'uri-rsa'}
            ]
        }

        result = get_contact_validation_status(relays, validation_data)

        self.assertTrue(result['has_aroi'])
        self.assertEqual(result['validation_status'], 'misconfigured')
        self.assertEqual(result['misconfigured_relays'][0]['error'], 'Unknown error')
    
    def test_relay_with_aroi_not_in_validation_map(self):
        """Test that relays with AROI not in validation_map are added to misconfigured_relays.
        
        This is a regression test for the bug where partially validated operators
        would not show the validation issues section because relays not in the
        validation_map were silently skipped.
        """
        relays = [
            {'fingerprint': 'ABC123', 'nickname': 'validated1', 'aroi_domain': 'example.com'},
            {'fingerprint': 'DEF456', 'nickname': 'missing_from_map', 'aroi_domain': 'example.com'}
        ]
        validation_data = {
            'results': [
                # Only ABC123 is in validation data, DEF456 is missing
                {'fingerprint': 'ABC123', 'valid': True, 'proof_type': 'uri-rsa'}
            ]
        }
        result = get_contact_validation_status(relays, validation_data)
        
        # Should be validated (1 validated relay means operator is validated)
        self.assertTrue(result['has_aroi'])
        self.assertEqual(result['validation_status'], 'validated')
        self.assertEqual(result['validation_summary']['validated_count'], 1)
        
        # The relay not in validation map should be in misconfigured_relays
        self.assertEqual(len(result['validated_relays']), 1)
        self.assertEqual(len(result['misconfigured_relays']), 1)
        self.assertEqual(result['misconfigured_relays'][0]['fingerprint'], 'DEF456')
        self.assertIn('validator', result['misconfigured_relays'][0]['error'].lower())
    
    def test_operator_status_cascade_validated_wins(self):
        """Test that validated status wins over all other statuses."""
        relays = [
            {'fingerprint': 'ABC123', 'nickname': 'validated', 'aroi_domain': 'example.com'},
            {'fingerprint': 'DEF456', 'nickname': 'unauthorized', 'aroi_domain': 'example.com'},
            {'fingerprint': 'GHI789', 'nickname': 'misconfigured', 'aroi_domain': 'example.com'},
        ]
        validation_data = {
            'results': [
                {'fingerprint': 'ABC123', 'valid': True, 'proof_type': 'uri-rsa'},
                {'fingerprint': 'DEF456', 'valid': False, 'error': 'Fingerprint not found', 'proof_type': 'uri-rsa'},
                {'fingerprint': 'GHI789', 'valid': False, 'error': 'DNS lookup failed', 'proof_type': 'dns-rsa'},
            ]
        }
        result = get_contact_validation_status(relays, validation_data)
        
        # Cascade: validated > unauthorized > misconfigured > not_configured
        self.assertEqual(result['validation_status'], 'validated')
        self.assertEqual(result['validation_summary']['validated_count'], 1)
        self.assertEqual(result['validation_summary']['unauthorized_count'], 1)
        self.assertEqual(result['validation_summary']['misconfigured_count'], 1)
    
    def test_operator_status_cascade_unauthorized_second(self):
        """Test that unauthorized status wins over misconfigured when no validated."""
        relays = [
            {'fingerprint': 'DEF456', 'nickname': 'unauthorized', 'aroi_domain': 'example.com'},
            {'fingerprint': 'GHI789', 'nickname': 'misconfigured', 'aroi_domain': 'example.com'},
        ]
        validation_data = {
            'results': [
                {'fingerprint': 'DEF456', 'valid': False, 'error': 'Fingerprint not found', 'proof_type': 'uri-rsa'},
                {'fingerprint': 'GHI789', 'valid': False, 'error': 'DNS lookup failed', 'proof_type': 'dns-rsa'},
            ]
        }
        result = get_contact_validation_status(relays, validation_data)
        
        # No validated, so unauthorized wins
        self.assertEqual(result['validation_status'], 'unauthorized')
    
    def test_operator_metrics_exclude_missing_aroi_fields(self):
        """Test that operator-level metrics don't count relays with Missing AROI fields."""
        relays = [
            # Relay 1: Has all 3 AROI fields, valid
            {'fingerprint': 'ABC123', 'aroi_domain': 'example.com', 'country': 'us'},
            # Relay 2: Missing AROI fields (no aroi_domain extracted)
            {'fingerprint': 'DEF456', 'aroi_domain': 'none', 'contact': 'email:test@example.com'},
            # Relay 3: Has all 3 AROI fields, invalid
            {'fingerprint': 'GHI789', 'aroi_domain': 'test.com', 'country': 'de'}
        ]
        validation_data = {
            'metadata': {'timestamp': '2025-11-30T00:00:00Z'},
            'statistics': {
                'proof_types': {
                    'dns_rsa': {'total': 0, 'valid': 0, 'success_rate': 0.0},
                    'uri_rsa': {'total': 2, 'valid': 1, 'success_rate': 50.0}
                }
            },
            'results': [
                {'fingerprint': 'ABC123', 'valid': True, 'proof_type': 'uri-rsa'},
                {'fingerprint': 'DEF456', 'valid': False, 'error': 'Missing AROI fields'},
                {'fingerprint': 'GHI789', 'valid': False, 'error': '404 Not Found', 'proof_type': 'uri-rsa'}
            ]
        }
        
        metrics = calculate_aroi_validation_metrics(relays, validation_data, calculate_operator_metrics=True)
        
        # Should only count 2 operators (example.com and test.com), not the one with missing AROI fields
        self.assertEqual(metrics['unique_aroi_domains_count'], 2)
        self.assertEqual(metrics['validated_aroi_domains_count'], 1)
        self.assertEqual(metrics['invalid_aroi_domains_count'], 1)

    def test_operator_metrics_handle_null_error(self):
        """Malformed validator entries should not crash network-health metrics."""
        relays = [
            {'fingerprint': 'ABC123', 'aroi_domain': 'example.com', 'country': 'us'}
        ]
        validation_data = {
            'metadata': {'timestamp': '2025-11-30T00:00:00Z'},
            'statistics': {
                'proof_types': {
                    'dns_rsa': {'total': 0, 'valid': 0, 'success_rate': 0.0},
                    'uri_rsa': {'total': 1, 'valid': 0, 'success_rate': 0.0}
                }
            },
            'results': [
                {'fingerprint': 'ABC123', 'valid': False, 'error': None, 'proof_type': 'uri-rsa'}
            ]
        }

        metrics = calculate_aroi_validation_metrics(relays, validation_data, calculate_operator_metrics=True)

        self.assertEqual(metrics['invalid_aroi_domains_count'], 1)
        self.assertIn(('Unknown error', 1), metrics['relay_error_top5'])
        self.assertIn(('Unknown error', 1), metrics['operator_error_top5'])
    
    def test_relay_error_top5_calculation(self):
        """Test that relay_error_top5 is calculated correctly."""
        relays = [
            {'fingerprint': 'FP1', 'aroi_domain': 'op1.org', 'contact': 'c@op1.org'},
            {'fingerprint': 'FP2', 'aroi_domain': 'op2.org', 'contact': 'c@op2.org'},
            {'fingerprint': 'FP3', 'aroi_domain': 'op2.org', 'contact': 'c@op2.org'},
            {'fingerprint': 'FP4', 'aroi_domain': 'op3.org', 'contact': 'c@op3.org'},
            {'fingerprint': 'FP5', 'aroi_domain': 'op3.org', 'contact': 'c@op3.org'},
            {'fingerprint': 'FP6', 'aroi_domain': 'op3.org', 'contact': 'c@op3.org'},
        ]
        validation_data = {
            'metadata': {'timestamp': '2025-11-30T00:00:00Z'},
            'statistics': {
                'proof_types': {
                    'dns_rsa': {'total': 3, 'valid': 0, 'success_rate': 0.0},
                    'uri_rsa': {'total': 3, 'valid': 0, 'success_rate': 0.0}
                }
            },
            'results': [
                {'fingerprint': 'FP1', 'valid': True},
                {'fingerprint': 'FP2', 'valid': False, 'error': 'DNS lookup failed: NXDOMAIN'},
                {'fingerprint': 'FP3', 'valid': False, 'error': 'DNS lookup failed: NXDOMAIN'},
                {'fingerprint': 'FP4', 'valid': False, 'error': 'SSL certificate error'},
                {'fingerprint': 'FP5', 'valid': False, 'error': 'SSL certificate error'},
                {'fingerprint': 'FP6', 'valid': False, 'error': '404 Not Found'},
            ]
        }
        
        metrics = calculate_aroi_validation_metrics(relays, validation_data, calculate_operator_metrics=True)
        
        # Check relay_error_top5 exists and is a list
        self.assertIn('relay_error_top5', metrics)
        self.assertIsInstance(metrics['relay_error_top5'], list)
        
        # Check it has the right structure (list of tuples)
        if len(metrics['relay_error_top5']) > 0:
            error, count = metrics['relay_error_top5'][0]
            self.assertIsInstance(error, str)
            self.assertIsInstance(count, int)
        
        # Check the top error is the DNS error (appears twice)
        # Note: Error messages are now simplified, "DNS lookup failed: NXDOMAIN" -> "DNS domain not found (NXDOMAIN)"
        top_error, top_count = metrics['relay_error_top5'][0]
        self.assertEqual(top_count, 2)
        self.assertIn('DNS', top_error)  # Simplified error still contains DNS
    
    def test_operator_error_top5_calculation(self):
        """Test that operator_error_top5 counts operators not relays."""
        relays = [
            {'fingerprint': 'FP1', 'aroi_domain': 'op1.org', 'contact': 'c@op1.org'},
            {'fingerprint': 'FP2', 'aroi_domain': 'op2.org', 'contact': 'c@op2.org'},
            {'fingerprint': 'FP3', 'aroi_domain': 'op2.org', 'contact': 'c@op2.org'},
            {'fingerprint': 'FP4', 'aroi_domain': 'op3.org', 'contact': 'c@op3.org'},
        ]
        validation_data = {
            'metadata': {'timestamp': '2025-11-30T00:00:00Z'},
            'statistics': {
                'proof_types': {
                    'dns_rsa': {'total': 3, 'valid': 0, 'success_rate': 0.0},
                    'uri_rsa': {'total': 3, 'valid': 0, 'success_rate': 0.0}
                }
            },
            'results': [
                {'fingerprint': 'FP1', 'valid': True},
                # op2 has 2 relays with same error
                {'fingerprint': 'FP2', 'valid': False, 'error': 'DNS lookup failed: NXDOMAIN'},
                {'fingerprint': 'FP3', 'valid': False, 'error': 'DNS lookup failed: NXDOMAIN'},
                # op3 has different error
                {'fingerprint': 'FP4', 'valid': False, 'error': 'SSL certificate error'},
            ]
        }
        
        metrics = calculate_aroi_validation_metrics(relays, validation_data, calculate_operator_metrics=True)
        
        # Check operator_error_top5 exists
        self.assertIn('operator_error_top5', metrics)
        self.assertIsInstance(metrics['operator_error_top5'], list)
        
        # Each unique error should count 1 operator, not multiple relays
        # DNS error affects 1 operator (op2), SSL error affects 1 operator (op3)
        error_counts = {error: count for error, count in metrics['operator_error_top5']}
        
        # Find DNS and SSL errors
        dns_count = next((count for error, count in metrics['operator_error_top5'] if 'DNS' in error), 0)
        ssl_count = next((count for error, count in metrics['operator_error_top5'] if 'SSL' in error), 0)
        
        # Both should be 1 (one operator each), not 2 for DNS
        self.assertEqual(dns_count, 1, "DNS error should count 1 operator not 2 relays")
        self.assertEqual(ssl_count, 1, "SSL error should count 1 operator")

    def test_operator_error_top5_deduplicates_simplified_reasons(self):
        """Operators should be counted once per simplified reason even with varied raw errors."""
        relays = [
            {'fingerprint': 'FP1', 'aroi_domain': 'multi.org', 'contact': 'c@multi.org'},
            {'fingerprint': 'FP2', 'aroi_domain': 'multi.org', 'contact': 'c@multi.org'},
        ]
        validation_data = {
            'metadata': {'timestamp': '2025-11-30T00:00:00Z'},
            'statistics': {
                'proof_types': {
                    'dns_rsa': {'total': 0, 'valid': 0, 'success_rate': 0.0},
                    'uri_rsa': {'total': 2, 'valid': 0, 'success_rate': 0.0}
                }
            },
            'results': [
                {'fingerprint': 'FP1', 'valid': False, 'error': 'SSL: SSLV3_ALERT_HANDSHAKE_FAILURE'},
                # Same operator, same error type (both v3) but slightly different wording
                {'fingerprint': 'FP2', 'valid': False, 'error': 'sslv3_alert_handshake_failure on uri proof'},
            ]
        }
        
        metrics = calculate_aroi_validation_metrics(relays, validation_data, calculate_operator_metrics=True)
        
        # Relay-level counts should reflect both relays
        handshake_relay_count = next((count for error, count in metrics['relay_error_top5'] if 'SSL/TLS v3 handshake' in error), 0)
        self.assertEqual(handshake_relay_count, 2, "Relay counts should reflect total failing relays")
        
        # Operator-level counts should only count the operator once
        handshake_operator_count = next((count for error, count in metrics['operator_error_top5'] if 'SSL/TLS v3 handshake' in error), 0)
        self.assertEqual(handshake_operator_count, 1, "Operator counts should deduplicate simplified reasons")
    
    def test_top5_lists_empty_when_no_failures(self):
        """Test that top5 lists are empty when all relays validate successfully."""
        relays = [
            {'fingerprint': 'FP1', 'aroi_domain': 'op1.org', 'contact': 'c@op1.org'},
            {'fingerprint': 'FP2', 'aroi_domain': 'op2.org', 'contact': 'c@op2.org'},
        ]
        validation_data = {
            'metadata': {'timestamp': '2025-11-30T00:00:00Z'},
            'statistics': {
                'proof_types': {
                    'dns_rsa': {'total': 2, 'valid': 2, 'success_rate': 100.0},
                    'uri_rsa': {'total': 0, 'valid': 0, 'success_rate': 0.0}
                }
            },
            'results': [
                {'fingerprint': 'FP1', 'valid': True},
                {'fingerprint': 'FP2', 'valid': True},
            ]
        }
        
        metrics = calculate_aroi_validation_metrics(relays, validation_data, calculate_operator_metrics=True)
        
        # When all validate successfully, error lists should be empty
        self.assertEqual(len(metrics['relay_error_top5']), 0)
        self.assertEqual(len(metrics['operator_error_top5']), 0)
    
    def test_top5_lists_not_present_when_operator_metrics_disabled(self):
        """Test that top5 lists are not calculated when calculate_operator_metrics=False."""
        relays = [
            {'fingerprint': 'FP1', 'aroi_domain': 'op1.org', 'contact': 'c@op1.org'},
        ]
        validation_data = {
            'metadata': {'timestamp': '2025-11-30T00:00:00Z'},
            'statistics': {
                'proof_types': {
                    'dns_rsa': {'total': 1, 'valid': 0, 'success_rate': 0.0},
                    'uri_rsa': {'total': 0, 'valid': 0, 'success_rate': 0.0}
                }
            },
            'results': [
                {'fingerprint': 'FP1', 'valid': False, 'error': 'DNS error'},
            ]
        }
        
        metrics = calculate_aroi_validation_metrics(relays, validation_data, calculate_operator_metrics=False)
        
        # Top5 lists should have default empty values
        self.assertEqual(metrics['relay_error_top5'], [])
        self.assertEqual(metrics['operator_error_top5'], [])

    def test_error_simplification(self):
        """Test that verbose error messages are simplified with protocol prefix."""
        # Test SSL/TLS handshake errors - should include v3
        msg, proof = _simplify_error_message("SSL: SSLV3_ALERT_HANDSHAKE_FAILURE")
        self.assertEqual(msg, "URI: SSL/TLS v3 handshake failed")
        self.assertEqual(proof, 'uri')
        
        # Test 404 errors with fingerprint URL
        msg, proof = _simplify_error_message("404 Not Found for https://example.com/.well-known/tor-relay/rsa-fingerprint.txt")
        self.assertEqual(msg, "URI: Fingerprint file not found (404)")
        self.assertEqual(proof, 'uri')
        
        # Test 404 errors without fingerprint URL
        msg, proof = _simplify_error_message("404 Not Found")
        self.assertEqual(msg, "URI: Proof file not found (404)")
        self.assertEqual(proof, 'uri')
        
        # Test NXDOMAIN errors
        msg, proof = _simplify_error_message("DNS lookup failed: NXDOMAIN")
        self.assertEqual(msg, "DNS: Domain not found (NXDOMAIN)")
        self.assertEqual(proof, 'dns')
        
        # Test connection timeout
        msg, proof = _simplify_error_message("Connection timeout after 30 seconds")
        self.assertEqual(msg, "URI: Connection timeout")
        self.assertEqual(proof, 'uri')

    def test_error_categorization(self):
        """Test that errors are categorized into DNS and URI correctly."""
        errors = {
            "DNS lookup failed: NXDOMAIN": 10,
            "SSL certificate error": 5,
            "404 Not Found": 3,
            "DNS TXT record not found": 2,
        }
        
        result = _simplify_and_categorize_errors(errors)
        
        # Check all errors are in 'all' category
        self.assertGreater(len(result['all']), 0)
        
        # Check DNS errors contain DNS-prefixed errors
        self.assertIn("DNS: Domain not found (NXDOMAIN)", result['dns'])
        self.assertIn("DNS: TXT record not found", result['dns'])
        
        # Check URI errors contain URI-prefixed errors
        self.assertIn("URI: SSL certificate error", result['uri'])
        self.assertIn("URI: Proof file not found (404)", result['uri'])
    
    def test_incomplete_relays_categorization(self):
        """Test that relays with partial AROI fields are categorized as incomplete."""
        relays = [
            # Has contact with ciissversion and url but no proof
            {'fingerprint': 'ABC123', 'nickname': 'test1', 'aroi_domain': 'none', 
             'contact': 'ciissversion:2 url:example.com'},
        ]
        result = get_contact_validation_status(relays, None)
        
        # Should be considered as having some AROI info
        self.assertTrue(result['has_aroi'])
        # When only incomplete relays exist (no misconfigured), status is 'incomplete'
        self.assertEqual(result['validation_status'], 'incomplete')
        self.assertEqual(len(result['incomplete_relays']), 1)
        self.assertEqual(result['validation_summary']['incomplete_count'], 1)
        self.assertEqual(result['validation_summary']['incomplete_no_proof_count'], 1)
    
    def test_fingerprint_sets_populated(self):
        """Test that fingerprint sets are populated for O(1) lookups in templates."""
        relays = [
            {'fingerprint': 'ABC123', 'nickname': 'validated', 'aroi_domain': 'example.com'},
            {'fingerprint': 'DEF456', 'nickname': 'unauthorized', 'aroi_domain': 'example.com'},
            {'fingerprint': 'GHI789', 'nickname': 'misconfigured', 'aroi_domain': 'example.com'},
        ]
        validation_data = {
            'results': [
                {'fingerprint': 'ABC123', 'valid': True, 'proof_type': 'uri-rsa'},
                {'fingerprint': 'DEF456', 'valid': False, 'error': 'Fingerprint not found', 'proof_type': 'uri-rsa'},
                {'fingerprint': 'GHI789', 'valid': False, 'error': 'DNS lookup failed', 'proof_type': 'dns-rsa'},
            ]
        }
        result = get_contact_validation_status(relays, validation_data)
        
        # Check fingerprint sets
        self.assertIn('ABC123', result['validated_fingerprints'])
        self.assertIn('DEF456', result['unauthorized_fingerprints'])
        self.assertIn('GHI789', result['misconfigured_fingerprints'])
        
        # Verify they're proper sets
        self.assertIsInstance(result['validated_fingerprints'], set)
        self.assertIsInstance(result['unauthorized_fingerprints'], set)
        self.assertIsInstance(result['misconfigured_fingerprints'], set)


class TestAROIValidationV3(unittest.TestCase):
    """v3 (CIISS spec version 3) integration tests covering Part A.

    Verifies:
      - all 4 proof types read into metrics (A.3)
      - ciissversion adoption + v3_failure_categories passthrough (A.3)
      - error_category-driven cascade (A.4)
      - upstream hint passthrough (A.4)
      - peer issue categories: security_incident, pending_onionoo (A.5)
      - operator-level v2/v3 counts + tier classification (A.5)
      - is_mixed_migration / is_v3_adopter flags (A.5)
      - schema-version handshake (A.1)
      - error rollup buckets (A.6)
      - V3_CATEGORY_LABELS coverage of all upstream categories (A.7)
    """

    def test_all_four_proof_types_populated(self):
        """A.3: dns_familyid_ed25519 + uri_familyid_ed25519 must be read."""
        relays = [
            {'fingerprint': 'V2A', 'aroi_domain': 'v2.org', 'aroi_version': '2',
             'aroi_proof_type': 'dns-rsa', 'contact': 'ciissversion:2 proof:dns-rsa url:v2.org'},
            {'fingerprint': 'V3A', 'aroi_domain': 'v3.org', 'aroi_version': '3',
             'aroi_proof_type': 'uri-familyid-ed25519',
             'contact': 'ciissversion:3 proof:uri-familyid-ed25519 url:v3.org'},
        ]
        validation_data = {
            'metadata': {'timestamp': '2026-05-05T00:00:00Z',
                         'aroivalidator_schema_version': 2},
            'statistics': {
                'proof_types': {
                    'dns_rsa':              {'total': 100, 'valid': 80, 'success_rate': 80.0},
                    'uri_rsa':              {'total': 200, 'valid': 180, 'success_rate': 90.0},
                    'dns_familyid_ed25519': {'total': 50, 'valid': 50, 'success_rate': 100.0},
                    'uri_familyid_ed25519': {'total': 30, 'valid': 28, 'success_rate': 93.3},
                },
                'ciissversion_declared':  {'2': 300, '3': 80, 'none': 100},
                'ciissversion_validated': {'2': 300, '3': 80, 'filtered_out': 0},
                'v3_failure_categories':  {'missing_family_ids': 2,
                                            'uri_content_mismatch': 1},
            },
            'results': [
                {'fingerprint': 'V2A', 'valid': True, 'proof_type': 'dns-rsa',
                 'ciissversion': '2'},
                {'fingerprint': 'V3A', 'valid': True,
                 'proof_type': 'uri-familyid-ed25519', 'ciissversion': '3'},
            ]
        }
        m = calculate_aroi_validation_metrics(relays, validation_data)

        # Per-proof-type keys (12 total: 4 types * 3 stats each).
        self.assertEqual(m['dns_rsa_total'], 100)
        self.assertEqual(m['uri_rsa_total'], 200)
        self.assertEqual(m['dns_familyid_ed25519_total'], 50)
        self.assertEqual(m['dns_familyid_ed25519_valid'], 50)
        self.assertEqual(m['dns_familyid_ed25519_success_rate'], 100.0)
        self.assertEqual(m['uri_familyid_ed25519_total'], 30)
        self.assertEqual(m['uri_familyid_ed25519_valid'], 28)

        # v2 / v3 aggregates.
        self.assertEqual(m['v2_total'], 300)   # 100 + 200
        self.assertEqual(m['v2_valid'], 260)   # 80 + 180
        self.assertEqual(m['v3_total'], 80)    # 50 + 30
        self.assertEqual(m['v3_valid'], 78)    # 50 + 28
        self.assertAlmostEqual(m['v2_success_rate'], 260/300*100, places=1)
        self.assertAlmostEqual(m['v3_success_rate'], 78/80*100, places=1)

        # Upstream stats passthrough.
        self.assertEqual(m['ciissversion_declared'],
                         {'2': 300, '3': 80, 'none': 100})
        self.assertEqual(m['v3_failure_categories'],
                         {'missing_family_ids': 2, 'uri_content_mismatch': 1})

    def test_security_incident_peer_bucket(self):
        """A.5: secret_key_leaked relays go into security_incident_relays."""
        relays = [{
            'fingerprint': 'BAD', 'aroi_domain': 'leak.org',
            'aroi_version': '3', 'aroi_proof_type': 'uri-familyid-ed25519',
            'nickname': 'leakedrelay',
            'contact': 'ciissversion:3 proof:uri-familyid-ed25519 url:leak.org',
        }]
        validation_data = {
            'metadata': {'aroivalidator_schema_version': 2},
            'statistics': {'proof_types': {}},
            'results': [{
                'fingerprint': 'BAD', 'valid': False, 'ciissversion': '3',
                'proof_type': 'uri-familyid-ed25519',
                'error': ('SECURITY: URI-FamilyID: published content '
                          'appears to contain .secret_family_key. '
                          'Rotate immediately.'),
                'error_category': 'secret_key_leaked',
                'hint': 'tor --keygen-family <newfile>',
            }],
        }
        s = get_contact_validation_status(relays, validation_data)

        # Peer bucket populated.
        self.assertEqual(s['validation_summary']['security_incident_count'], 1)
        self.assertEqual(len(s['security_incident_relays']), 1)
        self.assertIn('BAD', s['security_incident_fingerprints'])

        # Hint passes through verbatim from upstream.
        self.assertEqual(s['security_incident_relays'][0]['hint'],
                         'tor --keygen-family <newfile>')

        # Top-level cascade still reports "misconfigured" (cascade DOES
        # NOT change for peer alerts; templates render the security
        # banner alongside whatever cascade picks).
        self.assertEqual(s['validation_status'], 'misconfigured')

    def test_pending_onionoo_peer_bucket(self):
        """A.5: missing_family_ids -> pending_onionoo_relays bucket."""
        relays = [{
            'fingerprint': 'NEW', 'aroi_domain': 'fresh.org',
            'aroi_version': '3', 'aroi_proof_type': 'uri-familyid-ed25519',
            'contact': 'ciissversion:3 proof:uri-familyid-ed25519 url:fresh.org',
        }]
        validation_data = {
            'metadata': {'aroivalidator_schema_version': 2},
            'statistics': {'proof_types': {}},
            'results': [{
                'fingerprint': 'NEW', 'valid': False, 'ciissversion': '3',
                'error_category': 'missing_family_ids',
                'hint': "Run 'tor --keygen-family ...'",
            }],
        }
        s = get_contact_validation_status(relays, validation_data)
        self.assertEqual(s['validation_summary']['pending_onionoo_count'], 1)
        self.assertEqual(len(s['pending_onionoo_relays']), 1)
        self.assertIn('NEW', s['pending_onionoo_fingerprints'])

    def test_dns_content_mismatch_unauthorized_via_error_category(self):
        """A.4: error_category='dns_content_mismatch' -> unauthorized cascade.

        Today's substring heuristic would not catch this (the v3 error
        message says 'TXT record content does not match...' which
        doesn't include 'fingerprint not found'). With error_category
        plumbed through, classification is correct.
        """
        relays = [{
            'fingerprint': 'X', 'aroi_domain': 'x.org', 'aroi_version': '3',
            'contact': 'ciissversion:3 proof:dns-familyid-ed25519 url:x.org',
        }]
        validation_data = {
            'metadata': {},
            'statistics': {'proof_types': {}},
            'results': [{
                'fingerprint': 'X', 'valid': False, 'ciissversion': '3',
                'error': 'DNS-FamilyID: TXT record content does not match relay family_ids',
                'error_category': 'dns_content_mismatch',
            }],
        }
        s = get_contact_validation_status(relays, validation_data)
        self.assertEqual(s['validation_status'], 'unauthorized')
        self.assertEqual(s['validation_summary']['unauthorized_count'], 1)

    def test_v3_tier_classification_explorer(self):
        """A.5: 1 v3 relay out of 50 -> 'explorer' tier."""
        from allium.lib.aroi_validation import classify_v3_tier
        self.assertEqual(classify_v3_tier(0, 50), 'none')
        self.assertEqual(classify_v3_tier(1, 50), 'explorer')   # 2%
        self.assertEqual(classify_v3_tier(12, 50), 'explorer')  # 24%
        self.assertEqual(classify_v3_tier(13, 50), 'migrating') # 26%
        self.assertEqual(classify_v3_tier(37, 50), 'migrating') # 74%
        self.assertEqual(classify_v3_tier(38, 50), 'mostly')    # 76%
        self.assertEqual(classify_v3_tier(49, 50), 'mostly')    # 98%
        self.assertEqual(classify_v3_tier(50, 50), 'complete')  # 100%
        self.assertEqual(classify_v3_tier(0, 0), 'none')
        self.assertEqual(classify_v3_tier(5, 0), 'none')

    def test_mixed_migration_operator_metadata(self):
        """A.5: operator with both v2 and v3 -> is_mixed_migration=True."""
        relays = [
            {'fingerprint': 'V2', 'aroi_domain': 'mix.org',
             'aroi_version': '2', 'aroi_proof_type': 'uri-rsa',
             'contact': 'ciissversion:2 proof:uri-rsa url:mix.org'},
            {'fingerprint': 'V3A', 'aroi_domain': 'mix.org',
             'aroi_version': '3', 'aroi_proof_type': 'uri-familyid-ed25519',
             'contact': 'ciissversion:3 proof:uri-familyid-ed25519 url:mix.org'},
            {'fingerprint': 'V3B', 'aroi_domain': 'mix.org',
             'aroi_version': '3', 'aroi_proof_type': 'uri-familyid-ed25519',
             'contact': 'ciissversion:3 proof:uri-familyid-ed25519 url:mix.org'},
        ]
        s = get_contact_validation_status(relays, {'results': []})
        self.assertEqual(s['validation_summary']['v2_relay_count'], 1)
        self.assertEqual(s['validation_summary']['v3_relay_count'], 2)
        self.assertAlmostEqual(s['validation_summary']['v3_relay_percentage'],
                                66.66666, places=2)
        self.assertTrue(s['validation_summary']['is_mixed_migration'])
        self.assertTrue(s['validation_summary']['is_v3_adopter'])
        # 2 of 3 = 66% -> 'migrating' tier (>=25%, <75%)
        self.assertEqual(s['validation_summary']['v3_tier'], 'migrating')

    def test_aroi_warnings_log_records_unknown_proof_type(self):
        """B6 (final): _record_warning surfaces unknown_proof_type for the
        api-diagnostics page. Each kind+value pair recorded once with
        timestamp + count of occurrences."""
        from allium.lib.aroi_validation import (
            _check_aroi_fields, get_aroi_warnings_log, reset_aroi_warnings_log,
        )
        reset_aroi_warnings_log()

        # First occurrence: a relay declaring an unknown proof type
        _check_aroi_fields(
            'ciissversion:3 url:foo.bar proof:dns-future-cipher-2030'
        )
        # Same unknown proof type again should NOT add a duplicate entry
        _check_aroi_fields(
            'ciissversion:3 url:bar.baz proof:dns-future-cipher-2030'
        )
        # Different unknown proof type should add a new entry
        _check_aroi_fields(
            'ciissversion:3 url:foo.bar proof:another-unknown-thing'
        )

        warnings = get_aroi_warnings_log()
        kinds_values = {(w['kind'], w['value']) for w in warnings}
        # Both unknown proof types tracked; one warning each (first-occurrence dedup)
        self.assertIn(('unsupported_proof_type', 'dns-future-cipher-2030'), kinds_values)
        self.assertIn(('unsupported_proof_type', 'another-unknown-thing'), kinds_values)

        # Each entry must have a timestamp_iso (Z-suffixed)
        for w in warnings:
            self.assertIn('timestamp_iso', w)
            self.assertTrue(w['timestamp_iso'].endswith('Z'))
            self.assertGreaterEqual(w['count'], 1)

    def test_aroi_warnings_log_records_schema_mismatch(self):
        """B6 (final): schema-version mismatch logged in the warning feed."""
        from allium.lib.aroi_validation import (
            check_schema_version, get_aroi_warnings_log,
            reset_aroi_warnings_log,
        )
        reset_aroi_warnings_log()
        check_schema_version(
            {'metadata': {'aroivalidator_schema_version': 99}},
            lambda m: None,
        )
        warnings = get_aroi_warnings_log()
        kinds_values = {(w['kind'], w['value']) for w in warnings}
        self.assertIn(('schema_mismatch', '99'), kinds_values)

    def test_aroi_warnings_log_timestamp_format(self):
        """B6 (final): timestamp_iso uses Python 3.12-safe APIs.

        Pins the contract that timestamps are ISO format with Z suffix
        and represent UTC. Catches accidental introduction of deprecated
        datetime.utcnow() (deprecated in Python 3.12+, scheduled removal
        in a future release)."""
        import re
        from allium.lib.aroi_validation import (
            _check_aroi_fields, get_aroi_warnings_log, reset_aroi_warnings_log,
        )
        reset_aroi_warnings_log()
        _check_aroi_fields(
            'ciissversion:3 url:foo.bar proof:future-cipher-x'
        )
        warnings = get_aroi_warnings_log()
        self.assertTrue(warnings)
        ts = warnings[0]['timestamp_iso']
        # ISO 8601 second-precision UTC: YYYY-MM-DDTHH:MM:SSZ
        self.assertRegex(
            ts,
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$',
            f'timestamp_iso has invalid format: {ts!r}'
        )

    def test_aroi_warnings_propagates_through_api_diagnostics(self):
        """B6 (final): collect_api_diagnostics surfaces warnings as
        aroi_extras['warnings'] so the template can render them.

        End-to-end test exercising the
        aroi_validation._record_warning → get_aroi_warnings_log
        → api_diagnostics.collect_api_diagnostics path."""
        from allium.lib.aroi_validation import (
            _check_aroi_fields, reset_aroi_warnings_log,
        )

        # Trigger an unsupported_proof_type warning during this test.
        reset_aroi_warnings_log()
        _check_aroi_fields(
            'ciissversion:3 url:foo.bar proof:future-cipher-2030'
        )

        # Stub a relay_set + args minimally so collect_api_diagnostics
        # can produce its dict for the AROI entry.
        from allium.lib.api_diagnostics import collect_api_diagnostics

        class _StubArgs:
            enabled_apis = 'all'
            aroi_url = 'https://aroivalidator.1aeo.com/latest.json'

        class _StubRelaySet:
            aroi_validation_data = {
                'metadata': {'aroivalidator_schema_version': 2},
                'statistics': {'proof_types': {}, 'v3_failure_categories': {}},
                'results': [],
            }
            # Other APIs read .json or other attributes; stub them as empty
            # dicts so collect_api_diagnostics doesn't crash on the non-AROI
            # entries.
            json = {'relays': []}
            exit_dns_health_data = None
            collector_consensus_data = None
            collector_descriptors_data = None
            uptime_data = None
            bandwidth_data = None

        diag = collect_api_diagnostics(_StubRelaySet(), _StubArgs())
        aroi_entry = next(a for a in diag['apis'] if a['name'] == 'aroi_validation')
        warnings = aroi_entry.get('aroi_extras', {}).get('warnings') or []
        kinds_values = {(w['kind'], w['value']) for w in warnings}
        self.assertIn(('unsupported_proof_type', 'future-cipher-2030'), kinds_values)

    def test_per_version_success_rate_pills(self):
        """B1.1 (final): per-version validated counts + success rates
        populated for the v3_migration_summary section's success-rate pills.
        Plan called for 'v2 relay count and v3 relay count side-by-side
        with success-rate pills'."""
        relays = [
            # v2 relays: 2 declared, both valid
            {'fingerprint': 'V2A', 'aroi_domain': 'mix.org',
             'aroi_version': '2', 'aroi_proof_type': 'uri-rsa',
             'contact': 'ciissversion:2 proof:uri-rsa url:mix.org'},
            {'fingerprint': 'V2B', 'aroi_domain': 'mix.org',
             'aroi_version': '2', 'aroi_proof_type': 'uri-rsa',
             'contact': 'ciissversion:2 proof:uri-rsa url:mix.org'},
            # v3 relays: 4 declared, only 1 valid (3 pending)
            {'fingerprint': 'V3A', 'aroi_domain': 'mix.org',
             'aroi_version': '3', 'aroi_proof_type': 'uri-familyid-ed25519',
             'contact': 'ciissversion:3 proof:uri-familyid-ed25519 url:mix.org'},
            {'fingerprint': 'V3B', 'aroi_domain': 'mix.org',
             'aroi_version': '3', 'aroi_proof_type': 'uri-familyid-ed25519',
             'contact': 'ciissversion:3 proof:uri-familyid-ed25519 url:mix.org'},
            {'fingerprint': 'V3C', 'aroi_domain': 'mix.org',
             'aroi_version': '3', 'aroi_proof_type': 'uri-familyid-ed25519',
             'contact': 'ciissversion:3 proof:uri-familyid-ed25519 url:mix.org'},
            {'fingerprint': 'V3D', 'aroi_domain': 'mix.org',
             'aroi_version': '3', 'aroi_proof_type': 'uri-familyid-ed25519',
             'contact': 'ciissversion:3 proof:uri-familyid-ed25519 url:mix.org'},
        ]
        validation_data = {
            'metadata': {'aroivalidator_schema_version': 2},
            'statistics': {'proof_types': {}},
            'results': [
                {'fingerprint': 'V2A', 'valid': True, 'ciissversion': '2',
                 'proof_type': 'uri-rsa'},
                {'fingerprint': 'V2B', 'valid': True, 'ciissversion': '2',
                 'proof_type': 'uri-rsa'},
                {'fingerprint': 'V3A', 'valid': True, 'ciissversion': '3',
                 'proof_type': 'uri-familyid-ed25519'},
                {'fingerprint': 'V3B', 'valid': False, 'ciissversion': '3',
                 'error_category': 'missing_family_ids',
                 'error': 'no family_ids in Onionoo'},
                {'fingerprint': 'V3C', 'valid': False, 'ciissversion': '3',
                 'error_category': 'missing_family_ids',
                 'error': 'no family_ids in Onionoo'},
                {'fingerprint': 'V3D', 'valid': False, 'ciissversion': '3',
                 'error_category': 'missing_family_ids',
                 'error': 'no family_ids in Onionoo'},
            ],
        }
        s = get_contact_validation_status(relays, validation_data)
        summary = s['validation_summary']
        # v2 declarations + validations
        self.assertEqual(summary['v2_relay_count'], 2)
        self.assertEqual(summary['v2_validated_count'], 2)
        self.assertEqual(summary['v2_success_rate'], 100.0)
        # v3 declarations + validations
        self.assertEqual(summary['v3_relay_count'], 4)
        self.assertEqual(summary['v3_validated_count'], 1)
        self.assertEqual(summary['v3_success_rate'], 25.0)

    def test_pure_v3_operator_complete_tier(self):
        """A.5: 100% v3 operator -> v3_tier='complete'."""
        relays = [
            {'fingerprint': 'A', 'aroi_domain': 'pure.org',
             'aroi_version': '3', 'aroi_proof_type': 'dns-familyid-ed25519',
             'contact': 'ciissversion:3 proof:dns-familyid-ed25519 url:pure.org'},
            {'fingerprint': 'B', 'aroi_domain': 'pure.org',
             'aroi_version': '3', 'aroi_proof_type': 'dns-familyid-ed25519',
             'contact': 'ciissversion:3 proof:dns-familyid-ed25519 url:pure.org'},
        ]
        s = get_contact_validation_status(relays, {'results': []})
        self.assertEqual(s['validation_summary']['v3_tier'], 'complete')
        self.assertFalse(s['validation_summary']['is_mixed_migration'])
        self.assertTrue(s['validation_summary']['is_v3_adopter'])

    def test_v2_only_operator_no_tier(self):
        """A.5: v2-only operator -> v3_tier='none', is_v3_adopter=False."""
        relays = [
            {'fingerprint': 'A', 'aroi_domain': 'old.org',
             'aroi_version': '2', 'aroi_proof_type': 'uri-rsa',
             'contact': 'ciissversion:2 proof:uri-rsa url:old.org'},
        ]
        s = get_contact_validation_status(relays, {'results': []})
        self.assertEqual(s['validation_summary']['v3_tier'], 'none')
        self.assertFalse(s['validation_summary']['is_v3_adopter'])

    def test_schema_version_handshake_unknown(self):
        """A.1: schema version outside tested set logs a warning, doesn't crash."""
        # Use the existing public reset helper instead of poking at
        # the private _warned_schema_versions set directly.
        # reset_aroi_warnings_log() already clears every per-warning
        # dedupe set including _warned_schema_versions.
        from allium.lib.aroi_validation import (
            check_schema_version, reset_aroi_warnings_log,
        )
        reset_aroi_warnings_log()  # Test isolation
        warnings = []

        def capture(msg):
            warnings.append(msg)

        # Schema 99 is far in the future of tested schemas.
        result = check_schema_version(
            {'metadata': {'aroivalidator_schema_version': 99}}, capture
        )
        self.assertEqual(result, 99)
        self.assertEqual(len(warnings), 1)
        self.assertIn('schema version 99', warnings[0])
        self.assertIn('newer than tested', warnings[0])

        # Second call with same version: no duplicate warning.
        result2 = check_schema_version(
            {'metadata': {'aroivalidator_schema_version': 99}}, capture
        )
        self.assertEqual(result2, 99)
        self.assertEqual(len(warnings), 1, "duplicate warning emitted")

    def test_schema_version_handshake_known(self):
        """A.1: schema version in tested set -> no warning."""
        from allium.lib.aroi_validation import check_schema_version
        warnings = []
        result = check_schema_version(
            {'metadata': {'aroivalidator_schema_version': 2}},
            lambda m: warnings.append(m)
        )
        self.assertEqual(result, 2)
        self.assertEqual(warnings, [])

    def test_schema_version_handshake_missing(self):
        """A.1: no schema version -> returns None, no warning."""
        from allium.lib.aroi_validation import check_schema_version
        warnings = []
        result = check_schema_version(
            {'metadata': {}}, lambda m: warnings.append(m)
        )
        self.assertIsNone(result)
        self.assertEqual(warnings, [])

    def test_error_rollup_shared_v2_v3_split(self):
        """A.6: _build_error_rollup splits errors into shared / v2-only / v3-only."""
        from allium.lib.aroi_validation import _build_error_rollup
        results = [
            # Shared category: both v2 and v3 hit transport errors
            {'fingerprint': 'A', 'valid': False, 'ciissversion': '2',
             'error_category': 'transport_error'},
            {'fingerprint': 'B', 'valid': False, 'ciissversion': '3',
             'error_category': 'transport_error'},
            # v3-only: missing_family_ids
            {'fingerprint': 'C', 'valid': False, 'ciissversion': '3',
             'error_category': 'missing_family_ids'},
            {'fingerprint': 'D', 'valid': False, 'ciissversion': '3',
             'error_category': 'missing_family_ids'},
            # v2-only: imagine a future v2-specific category
            {'fingerprint': 'E', 'valid': False, 'ciissversion': '2',
             'error_category': 'some_v2_only_thing'},
            # Valid relay should not appear in any rollup
            {'fingerprint': 'F', 'valid': True, 'ciissversion': '3'},
        ]
        shared, v2_only, v3_only = _build_error_rollup(results)
        # Shared: transport_error counted across both versions = 2
        self.assertEqual(len(shared), 1)
        self.assertEqual(shared[0][0], 'transport_error')
        self.assertEqual(shared[0][2], 2)
        # v3-only: missing_family_ids count 2
        v3_categories = {row[0]: row[2] for row in v3_only}
        self.assertEqual(v3_categories.get('missing_family_ids'), 2)
        # v2-only: some_v2_only_thing
        v2_categories = {row[0]: row[2] for row in v2_only}
        self.assertEqual(v2_categories.get('some_v2_only_thing'), 1)

    def test_v3_category_labels_cover_upstream_categories(self):
        """A.7: every upstream error_category we expect must have a label."""
        from allium.lib.aroi_validation import V3_CATEGORY_LABELS
        # The 13 categories from upstream's CATEGORY_INFO.
        upstream_cats = {
            'missing_family_ids', 'dns_txt_missing', 'dns_content_mismatch',
            'uri_file_missing', 'uri_content_mismatch',
            'wrong_proof_type_rsa', 'missing_proof_field', 'invalid_url',
            'unsafe_target', 'redirect_disallowed', 'secret_key_leaked',
            'ciissversion_unsupported', 'transport_error',
        }
        for cat in upstream_cats:
            self.assertIn(cat, V3_CATEGORY_LABELS, f"missing label for {cat}")
            entry = V3_CATEGORY_LABELS[cat]
            self.assertTrue(entry.get('title'), f"{cat} missing title")
            self.assertTrue(entry.get('example'),
                            f"{cat} missing pasteable example")

    def test_version_proof_mismatch_routes_to_incomplete(self):
        """A.5: ciissversion:2 + proof:uri-familyid-ed25519 -> incomplete bucket
        with version_proof_mismatch sub-category and pasteable hint."""
        # _simple_aroi_parsing returns aroi_domain="none" for mismatches, so
        # the relay reaches get_contact_validation_status with aroi_domain="none"
        # but contact has all 3 fields detected by _check_aroi_fields.
        relays = [{
            'fingerprint': 'MIX', 'aroi_domain': 'none',
            'aroi_version': '2', 'aroi_proof_type': 'uri-familyid-ed25519',
            'contact': 'ciissversion:2 url:foo.bar proof:uri-familyid-ed25519',
        }]
        s = get_contact_validation_status(relays, {'results': []})
        # Should be in incomplete bucket with version_proof_mismatch flag.
        self.assertEqual(s['validation_summary']['incomplete_count'], 1)
        self.assertEqual(
            s['validation_summary']['incomplete_version_proof_mismatch_count'], 1
        )
        relay_info = s['incomplete_relays'][0]
        self.assertEqual(relay_info['error_category'], 'version_proof_mismatch')
        # Pasteable example hint surfaced.
        self.assertIn('ciissversion:3', relay_info['hint'])
        self.assertIn('proof:uri-familyid-ed25519', relay_info['hint'])


class TestAROIPasteableExamples(unittest.TestCase):
    """Pasteable-example contract enforcement (UX feedback round 2).

    Categories that fire for both CIISS v2 and CIISS v3 must render
    version-appropriate file paths in their pasteable curl/DNS examples.

    The user-reported bug: a v2 relay hitting 'URI-RSA fingerprint not found'
    was rendering the ed25519-family-id.txt path (the v3 file). After the
    fix, V3_CATEGORY_LABELS may declare an alternate 'example_v2' entry,
    and _resolve_example_for_proof picks it when proof_type is RSA-flavored.
    """

    def test_resolve_example_for_proof_picks_v2_for_uri_rsa(self):
        from allium.lib.aroi_validation import (
            V3_CATEGORY_LABELS, _resolve_example_for_proof,
        )
        label = V3_CATEGORY_LABELS['uri_content_mismatch']
        v2_example = _resolve_example_for_proof(label, 'uri-rsa')
        v3_example = _resolve_example_for_proof(label, 'uri-familyid-ed25519')
        # v2 must reference rsa-fingerprint.txt (the v2 spec file).
        self.assertIn('rsa-fingerprint.txt', v2_example)
        self.assertNotIn('ed25519-family-id.txt', v2_example)
        # v3 must reference ed25519-family-id.txt (the v3 spec file).
        self.assertIn('ed25519-family-id.txt', v3_example)

    def test_resolve_example_for_proof_picks_v2_for_dns_rsa(self):
        from allium.lib.aroi_validation import (
            V3_CATEGORY_LABELS, _resolve_example_for_proof,
        )
        label = V3_CATEGORY_LABELS['dns_txt_missing']
        v2_example = _resolve_example_for_proof(label, 'dns-rsa')
        # v2 DNS uses 'we-run-this-tor-relay <fingerprint>' pattern.
        self.assertIn('we-run-this-tor-relay', v2_example)
        self.assertIn('<fingerprint>', v2_example)

    def test_resolve_example_for_proof_falls_back_to_v3_when_no_v2_field(self):
        """v3-only categories (no example_v2 key) still return the v3 example
        even if proof_type is somehow RSA — fail-open, never None."""
        from allium.lib.aroi_validation import (
            V3_CATEGORY_LABELS, _resolve_example_for_proof,
        )
        # 'wrong_proof_type_rsa' is v3-only (it describes "v3 contact declares
        # v2 proof type"). No example_v2 declared.
        label = V3_CATEGORY_LABELS['wrong_proof_type_rsa']
        self.assertIsNone(label.get('example_v2'))
        result = _resolve_example_for_proof(label, 'uri-rsa')
        # Should still return *something* (the default v3 example) — never None.
        self.assertIsNotNone(result)
        self.assertEqual(result, label['example'])

    def test_uri_rsa_misconfigured_relay_renders_full_v2_url(self):
        """User-reported bug: a v2 (URI-RSA) misconfigured relay with category
        'uri_content_mismatch' must render the FULL v2 URL in its pasteable
        example, not just '~/.well-known' nor the ed25519 file path.

        The path must include https:// + domain + /.well-known/tor-relay/ +
        rsa-fingerprint.txt + the actual relay's fingerprint."""
        relay = {
            'fingerprint': '0' * 40,
            'aroi_domain': 'example.org',
            'aroi_version': '2',
            'aroi_proof_type': 'uri-rsa',
            'contact': 'ciissversion:2 proof:uri-rsa url:example.org',
        }
        validation_data = {
            'results': [{
                'fingerprint': '0' * 40,
                'valid': False,
                'proof_type': 'uri-rsa',
                'ciissversion': '2',
                'error_category': 'uri_content_mismatch',
                'error': 'URI-RSA: Fingerprint not found at example.org',
            }],
        }
        s = get_contact_validation_status([relay], validation_data)
        # uri_content_mismatch routes to 'unauthorized' (per A.4 cascade),
        # not misconfigured. The pasteable-example contract is the same
        # regardless of which bucket the relay lands in.
        unauthorized = s['unauthorized_relays']
        self.assertEqual(len(unauthorized), 1)
        info = unauthorized[0]
        ex = info.get('pasteable_example') or ''
        # Must reference v2 (RSA) path, not v3 (ed25519) path.
        self.assertIn('rsa-fingerprint.txt', ex)
        self.assertNotIn('ed25519-family-id.txt', ex)
        # Must include the operator's actual domain.
        self.assertIn('example.org', ex)
        # Must include the actual relay fingerprint (substituted in by
        # _render_pasteable_example).
        self.assertIn('0' * 40, ex)
        # Must be a fully-qualified URL, not '~/.well-known'.
        self.assertIn('https://', ex)
        self.assertIn('/.well-known/tor-relay/', ex)


class TestAROIValidationMapCacheRegression(unittest.TestCase):
    """Regression test for commit 119687b33e -> d68fcec7ec.

    Phase 2 caching used .pop('_validation_map', {}) to extract the
    validation_map from the metrics dict, then assigned it to
    relay_set.validation_map. The .pop is destructive: on the first call
    it extracted the map correctly, but on subsequent CACHE-HIT calls
    it found no '_validation_map' key (already popped) and overwrote
    relay_set.validation_map with {} (the .pop default).

    Net effect was: every contact page rendered AFTER the first
    _calculate_network_health_metrics call had relay_set.validation_map
    = {} -> every fingerprint lookup missed -> every relay rendered as
    'misconfigured' / 0% valid even when upstream said 100% valid.

    Visible to operators as: 'all operators show misconfigured AROI'.

    The fix: cache the validation_map separately on
    relay_set._aroi_metrics_cache and restore it from the cache on
    every call (not just first compute). This test enforces that
    contract.
    """

    def _build_mock_relay_set(self):
        """Construct a minimal relay_set with one v2-AROI relay that
        upstream marks as valid, and the validation_data needed."""
        validation_data = {
            'results': [{
                'fingerprint': '1' * 40,
                'valid': True,
                'proof_type': 'uri-rsa',
                'ciissversion': '2',
            }],
            'metadata': {'aroivalidator_schema_version': 1},
        }
        relays = [{
            'fingerprint': '1' * 40,
            'nickname': 'TestRelay',
            'contact': 'ciissversion:2 proof:uri-rsa url:test.example',
            'aroi_domain': 'test.example',
            'aroi_version': '2',
            'aroi_proof_type': 'uri-rsa',
            'aroi_configured': True,
        }]

        class MockRelaySet:
            progress = False
            progress_logger = None

            def __init__(self):
                self.aroi_validation_data = validation_data
                self.json = {'relays': relays}

        return MockRelaySet(), validation_data, relays

    def test_validation_map_survives_multiple_cache_hits(self):
        """The cache-hit path must NOT wipe relay_set.validation_map."""
        from allium.lib.network_health import _integrate_aroi_validation
        rs, _, _ = self._build_mock_relay_set()

        # First call (cache miss): map populated.
        hm1 = {}
        _integrate_aroi_validation(hm1, rs, 1)
        size_after_1st = len(getattr(rs, 'validation_map', {}))
        self.assertGreater(
            size_after_1st, 0,
            "validation_map empty after first call - cache miss path broken"
        )

        # Second call (cache hit): map MUST still be populated.
        hm2 = {}
        _integrate_aroi_validation(hm2, rs, 1)
        size_after_2nd = len(getattr(rs, 'validation_map', {}))
        self.assertEqual(
            size_after_2nd, size_after_1st,
            "validation_map was wiped on cache hit "
            "(regression of commit 119687b33e)"
        )

        # Third call (still cache hit) - reinforces the contract.
        hm3 = {}
        _integrate_aroi_validation(hm3, rs, 1)
        size_after_3rd = len(getattr(rs, 'validation_map', {}))
        self.assertEqual(size_after_3rd, size_after_1st)

    def test_contact_validation_correct_after_cache_hits(self):
        """End-to-end: a valid v2 relay must still be reported as
        validated after the cache has been hit multiple times.

        This is the BEHAVIOURAL contract that the cache regression
        violated: contact pages rendered after the first call were
        seeing every relay as misconfigured.
        """
        from allium.lib.network_health import _integrate_aroi_validation
        from allium.lib.aroi_validation import get_contact_validation_status
        rs, validation_data, relays = self._build_mock_relay_set()

        # Drive 4 calls (matches typical _calculate_network_health_metrics
        # call count: uptime + bandwidth + exit_dns + fallback).
        for _ in range(4):
            _integrate_aroi_validation({}, rs, 1)

        # After all those cache hits, validation_map must still let the
        # one valid relay round-trip as 'validated'.
        result = get_contact_validation_status(
            relays, validation_data, rs.validation_map
        )
        s = result['validation_summary']
        self.assertEqual(s['validated_count'], 1)
        self.assertEqual(s['v2_validated_count'], 1)
        self.assertEqual(s['v2_relay_count'], 1)
        self.assertEqual(s['v2_success_rate'], 100.0)
        self.assertEqual(result['validation_status'], 'validated')


if __name__ == '__main__':
    unittest.main()
