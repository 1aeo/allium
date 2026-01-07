#!/usr/bin/env python3
"""
Test AROI validation module functionality.
Tests validation logic, error detection, and display filtering.

Updated for new categorization system:
- Operator statuses: validated | unauthorized | misconfigured | not_configured
- Relay categories: validated | unauthorized | misconfigured | incomplete_* | not_configured_*
"""

import os
import sys
import unittest
from unittest.mock import Mock

# Add allium to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

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


if __name__ == '__main__':
    unittest.main()
