#!/usr/bin/env python3
"""
Test per-relay IPv6 preprocessing in Relays._preprocess_template_data.

Covers the fix for the contact/family page IPv6 column that always rendered
"N/A" due to a Jinja2 for-loop scoping bug: {% set %} inside {% for %} does
not survive past {% endfor %}. The fix precomputes relay['ipv6_display_address']
(and guarantees relay['ipv6_support']) in Python during preprocessing.

NOTE: These tests construct Relays() directly (full unpatched __init__) so the
real _preprocess_template_data runs. Do NOT use
TestSetupHelpers.create_test_relays_instance here — it patches
_preprocess_template_data out.
"""

import unittest

from allium.lib.relays import Relays


def _make_relay(fingerprint, or_addresses):
    """Minimal onionoo-shaped relay dict accepted by the full Relays pipeline."""
    relay = {
        'fingerprint': fingerprint,
        'nickname': f'relay{fingerprint[0]}',
        'contact': 'operator@example.com',
        'observed_bandwidth': 1000000,
        'consensus_weight': 100,
        'flags': ['Running', 'Valid'],
        'running': True,
        'country': 'us',
        'country_name': 'United States',
        'as': 'AS1',
        'as_name': 'Test AS',
        'first_seen': '2023-01-01 00:00:00',
        'last_seen': '2024-01-01 00:00:00',
        'last_restarted': '2024-01-01 00:00:00',
        'platform': 'Tor 0.4.8.10 on Linux',
        'effective_family': [],
    }
    if or_addresses is not None:
        relay['or_addresses'] = or_addresses
    return relay


def _preprocess(or_addresses):
    """Run the full Relays init pipeline on one relay, return the processed dict."""
    relay_data = {'relays': [_make_relay('A' * 40, or_addresses)]}
    relays_obj = Relays(
        output_dir='/tmp/test-ipv6-preprocessing',
        onionoo_url='https://test.example.com',
        relay_data=relay_data,
        use_bits=False,
        progress=False,
    )
    return relays_obj.json['relays'][0]


class TestIPv6DisplayAddressPreprocessing(unittest.TestCase):
    """relay['ipv6_display_address'] extraction from or_addresses."""

    def test_dual_stack_relay(self):
        relay = _preprocess(['1.2.3.4:9001', '[2001:db8::1]:9001'])
        self.assertEqual(relay['ipv6_display_address'], '2001:db8::1')
        self.assertEqual(relay['ipv6_support'], 'both')

    def test_ipv4_only_relay(self):
        relay = _preprocess(['1.2.3.4:9001'])
        self.assertEqual(relay['ipv6_display_address'], '')
        self.assertEqual(relay['ipv6_support'], 'ipv4_only')

    def test_ipv6_only_relay(self):
        relay = _preprocess(['[2001:db8::1]:9001'])
        self.assertEqual(relay['ipv6_display_address'], '2001:db8::1')
        self.assertEqual(relay['ipv6_support'], 'ipv6_only')

    def test_empty_or_addresses(self):
        relay = _preprocess([])
        self.assertEqual(relay['ipv6_display_address'], '')
        self.assertEqual(relay['ipv6_support'], 'none')

    def test_missing_or_addresses(self):
        relay = _preprocess(None)
        self.assertEqual(relay['ipv6_display_address'], '')
        self.assertEqual(relay['ipv6_support'], 'none')

    def test_malformed_address_skipped(self):
        relay = _preprocess(['garbage', '[2001:db8::2]:443'])
        self.assertEqual(relay['ipv6_display_address'], '2001:db8::2')
        self.assertEqual(relay['ipv6_support'], 'ipv6_only')

    def test_first_ipv6_wins(self):
        relay = _preprocess(['[2001:db8::1]:9001', '[2001:db8::2]:9001'])
        self.assertEqual(relay['ipv6_display_address'], '2001:db8::1')
        self.assertEqual(relay['ipv6_support'], 'ipv6_only')

    def test_ipv6_address_normalized(self):
        """Uncompressed/zero-padded input is normalized to canonical form."""
        relay = _preprocess(['[2001:0db8:0000:0000:0000:0000:0000:0001]:9001'])
        self.assertEqual(relay['ipv6_display_address'], '2001:db8::1')

    def test_ipv6_after_ipv4(self):
        """Real-world onionoo ordering: IPv4 first, IPv6 second (reporter's relay)."""
        relay = _preprocess(['195.133.23.252:443', '[2001:470:1f15:16b::1337:c0de]:443'])
        self.assertEqual(relay['ipv6_display_address'], '2001:470:1f15:16b::1337:c0de')
        self.assertEqual(relay['ipv6_support'], 'both')


class TestIPv6SupportSetDuringPreprocessing(unittest.TestCase):
    """ipv6_support must be a guaranteed preprocessing output (not a
    network_health side effect), so header gating and contact_sorting see it
    even if network health metrics were never calculated."""

    def test_ipv6_support_present_without_network_health(self):
        relay_data = {'relays': [
            _make_relay('A' * 40, ['1.2.3.4:9001', '[2001:db8::1]:9001']),
            _make_relay('B' * 40, ['5.6.7.8:9001']),
        ]}
        relays_obj = Relays(
            output_dir='/tmp/test-ipv6-preprocessing',
            onionoo_url='https://test.example.com',
            relay_data=relay_data,
            use_bits=False,
            progress=False,
        )
        # No _calculate_network_health_metrics() call — preprocessing alone
        # must have set the attribute on every relay.
        self.assertNotIn('network_health', relays_obj.json)
        supports = {r['fingerprint']: r['ipv6_support'] for r in relays_obj.json['relays']}
        self.assertEqual(supports['A' * 40], 'both')
        self.assertEqual(supports['B' * 40], 'ipv4_only')


if __name__ == '__main__':
    unittest.main()
