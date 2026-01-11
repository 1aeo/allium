#!/usr/bin/env python3
"""
Test AROI domain extraction to ensure it follows the AROI spec requirements.
Tests validation that contact strings must have ciissversion:2, proof:(dns-rsa|uri-rsa), and url:<domain>.
"""

import unittest
from unittest.mock import patch

from allium.lib.relays import Relays


class TestAROIDomainExtraction(unittest.TestCase):
    """Test AROI domain extraction matches AROIValidator specification."""
    
    def setUp(self):
        """Set up test instance with minimal mocking."""
        # Create a minimal Relays instance just to test _simple_aroi_parsing
        with patch.object(Relays, '__init__', lambda x, **kwargs: None):
            self.relays = Relays()
    
    def test_valid_aroi_contact_with_all_required_fields(self):
        """Test that valid AROI contacts with all required fields are extracted correctly."""
        # Valid contact with ciissversion:2, proof:dns-rsa, and url:
        contact = "email:test@example.com ciissversion:2 proof:dns-rsa url:example.com"
        result = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(result, "example.com")
    
    def test_valid_aroi_contact_with_uri_rsa_proof(self):
        """Test that proof:uri-rsa is also accepted as valid."""
        contact = "email:test@example.com ciissversion:2 proof:uri-rsa url:example.com"
        result = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(result, "example.com")
    
    def test_invalid_aroi_contact_missing_proof(self):
        """Test that contacts missing proof field are rejected."""
        # Missing proof field
        contact = "email:test@example.com ciissversion:2 url:example.com"
        result = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(result, "none")
    
    def test_invalid_aroi_contact_missing_ciissversion(self):
        """Test that contacts missing ciissversion are rejected."""
        # Missing ciissversion field
        contact = "email:test@example.com proof:dns-rsa url:example.com"
        result = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(result, "none")
    
    def test_invalid_aroi_contact_missing_url(self):
        """Test that contacts missing url field are rejected."""
        # Missing url field
        contact = "email:test@example.com ciissversion:2 proof:dns-rsa"
        result = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(result, "none")
    
    def test_aroi_contact_with_donationurl_not_confused_with_url(self):
        """Test that donationurl: is not confused with url: field."""
        # This should be rejected because it has donationurl: but not url:
        contact = "email:test@example.com ciissversion:2 proof:dns-rsa donationurl:https://donate.example.com"
        result = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(result, "none")
    
    def test_aroi_contact_case_insensitive_matching(self):
        """Test that AROI field matching is case-insensitive."""
        # Case variations should still be accepted
        contact = "email:test@example.com CIISSVersion:2 Proof:DNS-RSA URL:example.com"
        result = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(result, "example.com")
    
    def test_aroi_domain_extraction_with_protocol(self):
        """Test that domains with protocols are extracted correctly."""
        contact = "ciissversion:2 proof:dns-rsa url:https://example.com/path"
        result = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(result, "example.com")
    
    def test_aroi_domain_extraction_removes_www_prefix(self):
        """Test that www. prefix is removed from domains."""
        contact = "ciissversion:2 proof:dns-rsa url:www.example.com"
        result = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(result, "example.com")
    
    def test_empty_contact_returns_none(self):
        """Test that empty contact returns 'none'."""
        result = self.relays._simple_aroi_parsing("")
        self.assertEqual(result, "none")
    
    def test_none_contact_returns_none(self):
        """Test that None contact returns 'none'."""
        result = self.relays._simple_aroi_parsing(None)
        self.assertEqual(result, "none")


if __name__ == '__main__':
    unittest.main()
