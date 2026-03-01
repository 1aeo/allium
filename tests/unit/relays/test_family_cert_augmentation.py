#!/usr/bin/env python3
"""
Test family-cert augmentation: injecting family-cert groups into effective_family
when Onionoo doesn't yet support use-family-ids (consensus method < 34).
"""

import unittest
from allium.lib.relays import Relays


def _make_relay(fp, nickname="test", effective_family=None, platform="Tor 0.4.9.5 on Linux",
                contact="test@example.com", flags=None):
    """Helper to create a minimal relay dict for testing."""
    return {
        'fingerprint': fp,
        'nickname': nickname,
        'observed_bandwidth': 1000000,
        'consensus_weight': 100,
        'advertised_bandwidth': 1200000,
        'flags': flags or ['Fast', 'Stable', 'Running', 'V2Dir'],
        'running': True,
        'country': 'US',
        'as': 'AS12345',
        'as_name': 'Test AS',
        'first_seen': '2023-01-01 00:00:00',
        'last_seen': '2024-01-01 00:00:00',
        'platform': platform,
        'version': '0.4.9.5',
        'version_status': 'recommended',
        'contact': contact,
        'effective_family': effective_family or [fp],
        'or_addresses': ['1.2.3.4:443'],
    }


def _build_relays_obj(relays_list):
    """Build a Relays object from a list of relay dicts."""
    relay_data = {'relays': relays_list}
    return Relays(
        output_dir="/tmp/test",
        onionoo_url="http://test.url",
        relay_data=relay_data,
        use_bits=False,
        progress=False,
    )


class TestFamilyCertAugmentation(unittest.TestCase):

    def test_no_augmentation_without_family_cert_data(self):
        """Relays with no family-cert data should not be augmented."""
        fp_a = 'AAAA' * 10
        fp_b = 'BBBB' * 10
        relays_obj = _build_relays_obj([
            _make_relay(fp_a, effective_family=[fp_a]),
            _make_relay(fp_b, effective_family=[fp_b]),
        ])
        relays_obj._family_key_to_fps = {}
        relays_obj._fp_to_family_key = {}
        relays_obj._family_cert_fps_cache = set()

        relays_obj._augment_families_from_family_cert()

        for relay in relays_obj.json['relays']:
            self.assertEqual(len(relay['effective_family']), 1)

    def test_augmentation_creates_family_from_cert_group(self):
        """Relays sharing a family-cert key should have their effective_family merged."""
        fp_a = 'A' * 40
        fp_b = 'B' * 40
        fp_c = 'C' * 40
        family_key = 'DEADBEEF' * 8

        relays_obj = _build_relays_obj([
            _make_relay(fp_a, nickname='relay_a', effective_family=[fp_a]),
            _make_relay(fp_b, nickname='relay_b', effective_family=[fp_b]),
            _make_relay(fp_c, nickname='relay_c', effective_family=[fp_c]),
        ])

        relays_obj._family_key_to_fps = {family_key: [fp_a, fp_b, fp_c]}
        relays_obj._fp_to_family_key = {fp_a: family_key, fp_b: family_key, fp_c: family_key}
        relays_obj._family_cert_fps_cache = {fp_a, fp_b, fp_c}

        relays_obj._augment_families_from_family_cert()

        for relay in relays_obj.json['relays']:
            ef = relay['effective_family']
            self.assertEqual(len(ef), 3, f"{relay['nickname']} should have 3 family members")
            self.assertIn(fp_a, ef)
            self.assertIn(fp_b, ef)
            self.assertIn(fp_c, ef)

    def test_augmentation_merges_with_existing_effective_family(self):
        """Family-cert members should be unioned with existing MyFamily members."""
        fp_a = 'A' * 40
        fp_b = 'B' * 40
        fp_c = 'C' * 40
        fp_d = 'D' * 40
        family_key = 'CAFE' * 16

        relays_obj = _build_relays_obj([
            _make_relay(fp_a, effective_family=[fp_a, fp_b]),
            _make_relay(fp_b, effective_family=[fp_a, fp_b]),
            _make_relay(fp_c, effective_family=[fp_c]),
            _make_relay(fp_d, effective_family=[fp_d]),
        ])

        relays_obj._family_key_to_fps = {family_key: [fp_a, fp_c, fp_d]}
        relays_obj._fp_to_family_key = {
            fp_a: family_key, fp_c: family_key, fp_d: family_key
        }
        relays_obj._family_cert_fps_cache = {fp_a, fp_c, fp_d}

        relays_obj._augment_families_from_family_cert()

        relay_a = relays_obj.json['relays'][0]
        self.assertIn(fp_a, relay_a['effective_family'])
        self.assertIn(fp_b, relay_a['effective_family'])
        self.assertIn(fp_c, relay_a['effective_family'])
        self.assertIn(fp_d, relay_a['effective_family'])
        self.assertEqual(len(relay_a['effective_family']), 4)

        relay_b = relays_obj.json['relays'][1]
        self.assertEqual(len(relay_b['effective_family']), 2,
                         "relay_b not in cert group, should be unchanged")

        relay_c = relays_obj.json['relays'][2]
        self.assertIn(fp_a, relay_c['effective_family'])
        self.assertIn(fp_c, relay_c['effective_family'])
        self.assertIn(fp_d, relay_c['effective_family'])

    def test_augmentation_updates_sorted_family(self):
        """New family entries should appear in sorted['family']."""
        fp_a = 'A' * 40
        fp_b = 'B' * 40
        family_key = 'BEEF' * 16

        relays_obj = _build_relays_obj([
            _make_relay(fp_a, effective_family=[fp_a]),
            _make_relay(fp_b, effective_family=[fp_b]),
        ])

        had_family_before = "family" in relays_obj.json.get("sorted", {})

        relays_obj._family_key_to_fps = {family_key: [fp_a, fp_b]}
        relays_obj._fp_to_family_key = {fp_a: family_key, fp_b: family_key}
        relays_obj._family_cert_fps_cache = {fp_a, fp_b}

        relays_obj._augment_families_from_family_cert()

        self.assertIn("family", relays_obj.json["sorted"])
        family_sorted = relays_obj.json["sorted"]["family"]
        self.assertIn(fp_a, family_sorted)
        self.assertIn(fp_b, family_sorted)
        self.assertIn(0, family_sorted[fp_a]["relays"])
        self.assertIn(1, family_sorted[fp_a]["relays"])

    def test_single_member_group_not_augmented(self):
        """Family-cert groups with only 1 member should be skipped."""
        fp_a = 'A' * 40
        family_key = 'SOLO' * 16

        relays_obj = _build_relays_obj([
            _make_relay(fp_a, effective_family=[fp_a]),
        ])

        relays_obj._family_key_to_fps = {family_key: [fp_a]}
        relays_obj._fp_to_family_key = {fp_a: family_key}
        relays_obj._family_cert_fps_cache = {fp_a}

        relays_obj._augment_families_from_family_cert()

        self.assertEqual(len(relays_obj.json['relays'][0]['effective_family']), 1)

    def test_freebsd_linux_mixed_family(self):
        """Simulates the 1aeo.com scenario: Linux relays with MyFamily + FreeBSD with cert only."""
        fp_linux = 'L' * 40
        fp_freebsd = 'F' * 40
        family_key = '1AE0' * 16

        relays_obj = _build_relays_obj([
            _make_relay(fp_linux, nickname='linux_relay',
                        platform='Tor 0.4.9.5 on Linux',
                        effective_family=[fp_linux]),
            _make_relay(fp_freebsd, nickname='freebsd_relay',
                        platform='Tor 0.4.9.5 on FreeBSD',
                        effective_family=[fp_freebsd]),
        ])

        relays_obj._family_key_to_fps = {family_key: [fp_linux, fp_freebsd]}
        relays_obj._fp_to_family_key = {
            fp_linux: family_key, fp_freebsd: family_key
        }
        relays_obj._family_cert_fps_cache = {fp_linux, fp_freebsd}

        relays_obj._augment_families_from_family_cert()

        linux_relay = relays_obj.json['relays'][0]
        freebsd_relay = relays_obj.json['relays'][1]

        self.assertEqual(len(linux_relay['effective_family']), 2)
        self.assertIn(fp_freebsd, linux_relay['effective_family'])

        self.assertEqual(len(freebsd_relay['effective_family']), 2)
        self.assertIn(fp_linux, freebsd_relay['effective_family'])

    def test_idempotent_when_already_in_effective_family(self):
        """If family-cert members are already in effective_family, no changes needed."""
        fp_a = 'A' * 40
        fp_b = 'B' * 40
        family_key = 'IDEM' * 16

        relays_obj = _build_relays_obj([
            _make_relay(fp_a, effective_family=[fp_a, fp_b]),
            _make_relay(fp_b, effective_family=[fp_a, fp_b]),
        ])

        relays_obj._family_key_to_fps = {family_key: [fp_a, fp_b]}
        relays_obj._fp_to_family_key = {fp_a: family_key, fp_b: family_key}
        relays_obj._family_cert_fps_cache = {fp_a, fp_b}

        ef_before_a = list(relays_obj.json['relays'][0]['effective_family'])
        ef_before_b = list(relays_obj.json['relays'][1]['effective_family'])

        relays_obj._augment_families_from_family_cert()

        self.assertEqual(relays_obj.json['relays'][0]['effective_family'], ef_before_a)
        self.assertEqual(relays_obj.json['relays'][1]['effective_family'], ef_before_b)


if __name__ == '__main__':
    unittest.main()
