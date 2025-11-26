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
    get_contact_validation_status,
    calculate_aroi_validation_metrics,
    _format_timestamp
)


class TestAROIValidation(unittest.TestCase):
    """Test AROI validation functions."""
    
    def test_get_contact_validation_status_no_aroi(self):
        """Test contacts with no AROI return correct status."""
        relays = [{'fingerprint': 'ABC123', 'nickname': 'test1'}]
        result = get_contact_validation_status(relays, None)
        
        self.assertFalse(result['has_aroi'])
        self.assertEqual(result['validation_status'], 'no_aroi')
        self.assertEqual(len(result['unvalidated_relays']), 0)
    
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
        self.assertEqual(len(result['unvalidated_relays']), 0)
    
    def test_get_contact_validation_status_partially_validated(self):
        """Test partially validated contact."""
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
        self.assertEqual(result['validation_status'], 'partially_validated')
        self.assertEqual(result['validation_summary']['validated_count'], 1)
        self.assertEqual(len(result['unvalidated_relays']), 1)
        self.assertTrue(result['show_detailed_errors'])
    
    def test_show_detailed_errors_false_for_all_missing_aroi(self):
        """Test that detailed errors are hidden when all relays have 'Missing AROI fields'."""
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
        
        self.assertEqual(result['validation_status'], 'unvalidated')
        self.assertFalse(result['show_detailed_errors'])
        self.assertEqual(len(result['unvalidated_relays']), 2)
    
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


if __name__ == '__main__':
    unittest.main()

