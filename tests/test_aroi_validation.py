#!/usr/bin/env python3
"""
Test AROI validation module functionality.
Tests validation logic, error detection, and display filtering.
"""

import os
import sys
import unittest
from unittest.mock import Mock

# Add allium to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from allium.lib.aroi_validation import (
    calculate_aroi_validation_metrics,
    _format_timestamp
)


class TestAROIValidation(unittest.TestCase):
    """Test AROI validation functions."""
    
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
        top_error, top_count = metrics['relay_error_top5'][0]
        self.assertEqual(top_count, 2)
        self.assertIn('DNS lookup', top_error)
    
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


if __name__ == '__main__':
    unittest.main()

