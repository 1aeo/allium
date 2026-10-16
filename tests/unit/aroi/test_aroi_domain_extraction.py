#!/usr/bin/env python3
"""
Test AROI domain extraction follows the CIISS spec for both v2 and v3.

Recognised contact formats:
  - CIISS v2: ciissversion:2 + proof:(dns-rsa|uri-rsa) + url:<domain>
  - CIISS v3: ciissversion:3 + proof:(dns-familyid-ed25519|uri-familyid-ed25519) + url:<domain>
"""

import unittest
from unittest.mock import patch

from allium.lib.relays import Relays


class TestAROIDomainExtraction(unittest.TestCase):
    """Test AROI domain extraction for both v2 and v3 specs.

    `_simple_aroi_parsing` returns a 3-tuple:
      (domain_or_'none', version_or_None, proof_type_or_None)
    """

    def setUp(self):
        """Set up test instance with minimal mocking."""
        with patch.object(Relays, '__init__', lambda x, **kwargs: None):
            self.relays = Relays()

    # -------------------------------------------------------------------------
    # CIISS v2 (existing semantics — preserved)
    # -------------------------------------------------------------------------

    def test_v2_dns_rsa_full(self):
        contact = "email:test@example.com ciissversion:2 proof:dns-rsa url:example.com"
        domain, version, proof = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(domain, "example.com")
        self.assertEqual(version, "2")
        self.assertEqual(proof, "dns-rsa")

    def test_v2_uri_rsa_full(self):
        contact = "email:test@example.com ciissversion:2 proof:uri-rsa url:example.com"
        domain, version, proof = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(domain, "example.com")
        self.assertEqual(version, "2")
        self.assertEqual(proof, "uri-rsa")

    def test_v2_missing_proof(self):
        contact = "email:test@example.com ciissversion:2 url:example.com"
        domain, version, proof = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(domain, "none")
        self.assertEqual(version, "2")
        self.assertIsNone(proof)

    def test_v2_missing_ciissversion(self):
        contact = "email:test@example.com proof:dns-rsa url:example.com"
        domain, version, proof = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(domain, "none")
        self.assertIsNone(version)
        self.assertEqual(proof, "dns-rsa")

    def test_v2_missing_url(self):
        contact = "email:test@example.com ciissversion:2 proof:dns-rsa"
        domain, version, proof = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(domain, "none")
        self.assertEqual(version, "2")
        self.assertEqual(proof, "dns-rsa")

    def test_donationurl_is_not_url(self):
        contact = ("email:test@example.com ciissversion:2 proof:dns-rsa "
                   "donationurl:https://donate.example.com")
        domain, _, _ = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(domain, "none")

    def test_case_insensitive_keys(self):
        contact = ("email:test@example.com CIISSVersion:2 Proof:DNS-RSA "
                   "URL:example.com")
        domain, version, proof = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(domain, "example.com")
        self.assertEqual(version, "2")
        # proof_type stored lowercase regardless of input casing
        self.assertEqual(proof, "dns-rsa")

    def test_url_with_protocol_strips_scheme(self):
        contact = "ciissversion:2 proof:dns-rsa url:https://example.com/path"
        domain, _, _ = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(domain, "example.com")

    def test_url_strips_www_prefix(self):
        contact = "ciissversion:2 proof:dns-rsa url:www.example.com"
        domain, _, _ = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(domain, "example.com")

    def test_empty_contact(self):
        self.assertEqual(
            self.relays._simple_aroi_parsing(""),
            ("none", None, None),
        )

    def test_none_contact(self):
        self.assertEqual(
            self.relays._simple_aroi_parsing(None),
            ("none", None, None),
        )

    # -------------------------------------------------------------------------
    # CIISS v3 (new)
    # -------------------------------------------------------------------------

    def test_v3_dns_familyid_full(self):
        contact = "ciissversion:3 url:example.com proof:dns-familyid-ed25519"
        domain, version, proof = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(domain, "example.com")
        self.assertEqual(version, "3")
        self.assertEqual(proof, "dns-familyid-ed25519")

    def test_v3_uri_familyid_full(self):
        contact = "ciissversion:3 url:example.com proof:uri-familyid-ed25519"
        domain, version, proof = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(domain, "example.com")
        self.assertEqual(version, "3")
        self.assertEqual(proof, "uri-familyid-ed25519")

    def test_v3_url_less_is_not_aroi_domain(self):
        """v3 informational-only ContactInfo (no url:) is spec-legal but
        does not have a verifiable domain — domain MUST be 'none'.

        is_v3_no_proof_compliant flag in _check_aroi_fields lets the
        contact-page surface distinguish this from "incomplete".
        """
        contact = ("ciissversion:3 email:tor@example.com "
                   "donationurl:https://donate.example.com")
        domain, version, proof = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(domain, "none")
        self.assertEqual(version, "3")
        self.assertIsNone(proof)

    def test_v3_url_with_protocol(self):
        contact = ("ciissversion:3 url:https://example.com "
                   "proof:dns-familyid-ed25519")
        domain, _, _ = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(domain, "example.com")

    # -------------------------------------------------------------------------
    # Defensive parsing edge cases (A.0.1)
    # -------------------------------------------------------------------------

    def test_legacy_ciissversion_1_rejected(self):
        """ciissversion:1 (legacy) is silently ignored, not crashed on."""
        contact = "ciissversion:1 url:example.com proof:dns-rsa"
        domain, version, _ = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(domain, "none")
        # version is None because the supported-version regex didn't match
        self.assertIsNone(version)

    def test_unknown_future_ciissversion_rejected(self):
        contact = "ciissversion:99 url:example.com proof:dns-rsa"
        domain, version, _ = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(domain, "none")
        self.assertIsNone(version)

    def test_v2_with_v3_proof_type_rejected(self):
        """Operator copy-paste error: ciissversion:2 + v3 proof type.

        Should be rejected as "incomplete AROI" rather than silently
        accepted (which would falsely claim domain ownership).
        """
        contact = ("ciissversion:2 url:example.com "
                   "proof:uri-familyid-ed25519")
        domain, version, proof = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(domain, "none")
        # version + proof are still reported (for diagnostic UI), but
        # mismatch means no aroi_domain was extracted.
        self.assertEqual(version, "2")
        self.assertEqual(proof, "uri-familyid-ed25519")

    def test_v3_with_v2_proof_type_rejected(self):
        contact = "ciissversion:3 url:example.com proof:dns-rsa"
        domain, version, proof = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(domain, "none")
        self.assertEqual(version, "3")
        self.assertEqual(proof, "dns-rsa")

    def test_unknown_proof_type_rejected(self):
        """Future or typoed proof type silently rejected (logged once)."""
        contact = ("ciissversion:3 url:example.com "
                   "proof:dns-familyid-x25519")  # made-up future type
        domain, version, proof = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(domain, "none")
        self.assertEqual(version, "3")
        # proof is None because the SUPPORTED-proof regex didn't match
        self.assertIsNone(proof)

    def test_multiple_proof_declarations_first_wins(self):
        """Per CIISS spec: keys MUST appear once; if they don't, the
        first occurrence wins. re.search returns the first match by
        construction; this test pins the contract.
        """
        contact = ("ciissversion:3 url:example.com "
                   "proof:uri-familyid-ed25519 proof:dns-familyid-ed25519")
        domain, version, proof = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(domain, "example.com")
        self.assertEqual(version, "3")
        self.assertEqual(proof, "uri-familyid-ed25519")

    def test_whitespace_in_value_rejected(self):
        """CIISS spec: keys/values MUST NOT contain whitespace.

        'ciissversion: 2' is malformed and silently ignored.
        """
        contact = "ciissversion: 2 url:example.com proof:dns-rsa"
        domain, version, _ = self.relays._simple_aroi_parsing(contact)
        self.assertEqual(domain, "none")
        self.assertIsNone(version)


if __name__ == '__main__':
    unittest.main()
