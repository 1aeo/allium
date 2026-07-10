#!/usr/bin/env python3
"""
Test per-relay IPv6 preprocessing in Relays._preprocess_template_data.

Covers the fix for the contact/family page IPv6 column that always rendered
"N/A" due to a Jinja2 for-loop scoping bug: {% set %} inside {% for %} does
not survive past {% endfor %}. The fix precomputes relay['ipv6_display_address']
(and guarantees relay['ipv6_support']) in Python during preprocessing.

NOTE: These tests use the process_relays fixture (tests/conftest.py), which
runs the full unpatched Relays init pipeline so the real
_preprocess_template_data executes. Do NOT use
TestSetupHelpers.create_test_relays_instance here — it patches
_preprocess_template_data out.
"""

import pytest


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


@pytest.mark.parametrize(
    ('or_addresses', 'expected_address', 'expected_support'),
    [
        # dual-stack: IPv4 first, IPv6 second
        (['1.2.3.4:9001', '[2001:db8::1]:9001'], '2001:db8::1', 'both'),
        # IPv4 only
        (['1.2.3.4:9001'], '', 'ipv4_only'),
        # IPv6 only
        (['[2001:db8::1]:9001'], '2001:db8::1', 'ipv6_only'),
        # empty or_addresses
        ([], '', 'none'),
        # missing or_addresses key entirely
        (None, '', 'none'),
        # malformed entry is skipped, valid IPv6 still found
        (['garbage', '[2001:db8::2]:443'], '2001:db8::2', 'ipv6_only'),
        # first IPv6 wins when several are present
        (['[2001:db8::1]:9001', '[2001:db8::2]:9001'], '2001:db8::1', 'ipv6_only'),
        # uncompressed/zero-padded input is normalized to canonical form
        (['[2001:0db8:0000:0000:0000:0000:0000:0001]:9001'], '2001:db8::1', 'ipv6_only'),
        # real-world onionoo ordering from the bug report (reporter's relay)
        (['195.133.23.252:443', '[2001:470:1f15:16b::1337:c0de]:443'],
         '2001:470:1f15:16b::1337:c0de', 'both'),
    ],
    ids=[
        'dual_stack', 'ipv4_only', 'ipv6_only', 'empty', 'missing',
        'malformed_skipped', 'first_ipv6_wins', 'normalized', 'reporter_relay',
    ],
)
def test_ipv6_display_address_preprocessing(process_relays, or_addresses,
                                            expected_address, expected_support):
    """relay['ipv6_display_address'] / ['ipv6_support'] from or_addresses."""
    relays_obj = process_relays([_make_relay('A' * 40, or_addresses)])
    relay = relays_obj.json['relays'][0]
    assert relay['ipv6_display_address'] == expected_address
    assert relay['ipv6_support'] == expected_support


def test_ipv6_support_present_without_network_health(process_relays):
    """ipv6_support must be a guaranteed preprocessing output (not a
    network_health side effect), so header gating and contact_sorting see it
    even if network health metrics were never calculated."""
    relays_obj = process_relays([
        _make_relay('A' * 40, ['1.2.3.4:9001', '[2001:db8::1]:9001']),
        _make_relay('B' * 40, ['5.6.7.8:9001']),
    ])
    # No _calculate_network_health_metrics() call — preprocessing alone
    # must have set the attribute on every relay.
    assert 'network_health' not in relays_obj.json
    supports = {r['fingerprint']: r['ipv6_support'] for r in relays_obj.json['relays']}
    assert supports['A' * 40] == 'both'
    assert supports['B' * 40] == 'ipv4_only'
