#!/usr/bin/env python3
"""
Tests for B5.1 \u2014 search index v3 schema (version 1.6).

Verifies the search-index.json generator (allium/lib/search_index.py)
emits the v3-related compact fields (`vn` per relay, `v3p` per family,
`v3_thresholds` lookup) and bumps `meta.version` to '1.6'.
"""

import json
import os
import tempfile
import unittest

from allium.lib.search_index import (
    generate_search_index,
    compact_relay_entry,
    compact_family_entry,
)


class TestSearchIndexV3Fields(unittest.TestCase):

    def test_relay_entry_emits_vn_for_v3_relay(self):
        """B5.1: per-relay 'vn' field set to '3' for ciissversion:3 relays."""
        relay = {
            'fingerprint': 'A' * 40,
            'nickname': 'v3relay',
            'aroi_domain': 'v3.example.com',
            'aroi_version': '3',
            'aroi_proof_type': 'uri-familyid-ed25519',
            'or_addresses': ['1.2.3.4:9001'],
            'as': 'AS12345',
            'country': 'DE',
        }
        entry = compact_relay_entry(relay, family_id=None)
        self.assertEqual(entry.get('vn'), '3')

    def test_relay_entry_emits_vn_for_v2_relay(self):
        """B5.1: 'vn' set to '2' for ciissversion:2 relays."""
        relay = {
            'fingerprint': 'B' * 40,
            'nickname': 'v2relay',
            'aroi_domain': 'v2.example.com',
            'aroi_version': '2',
            'aroi_proof_type': 'uri-rsa',
            'or_addresses': [],
        }
        entry = compact_relay_entry(relay, family_id=None)
        self.assertEqual(entry.get('vn'), '2')

    def test_relay_entry_omits_vn_when_no_aroi_version(self):
        """B5.1: sparse \u2014 'vn' absent for relays without aroi_version."""
        relay = {
            'fingerprint': 'C' * 40,
            'nickname': 'no_aroi',
            'or_addresses': [],
        }
        entry = compact_relay_entry(relay, family_id=None)
        self.assertNotIn('vn', entry)

    def test_family_entry_emits_v3p_for_pure_v3_family(self):
        """B5.1: per-family 'v3p' set to 100 for 100% v3 families."""
        members = [
            {'fingerprint': 'A' * 40, 'nickname': 'a', 'aroi_version': '3'},
            {'fingerprint': 'B' * 40, 'nickname': 'b', 'aroi_version': '3'},
        ]
        entry = compact_family_entry('fam_id', {}, members)
        self.assertEqual(entry.get('v3p'), 100)

    def test_family_entry_emits_v3p_for_mixed_family(self):
        """B5.1: 'v3p' = round(v3 / total * 100) for mixed families."""
        members = [
            {'fingerprint': 'A' * 40, 'nickname': 'a', 'aroi_version': '2'},
            {'fingerprint': 'B' * 40, 'nickname': 'b', 'aroi_version': '3'},
            {'fingerprint': 'C' * 40, 'nickname': 'c', 'aroi_version': '3'},
            {'fingerprint': 'D' * 40, 'nickname': 'd', 'aroi_version': '3'},
        ]
        entry = compact_family_entry('fam_id', {}, members)
        # 3/4 = 75%
        self.assertEqual(entry.get('v3p'), 75)

    def test_family_entry_omits_v3p_when_no_v3(self):
        """B5.1: sparse \u2014 'v3p' absent when no v3 relays in family."""
        members = [
            {'fingerprint': 'A' * 40, 'nickname': 'a', 'aroi_version': '2'},
            {'fingerprint': 'B' * 40, 'nickname': 'b', 'aroi_version': '2'},
        ]
        entry = compact_family_entry('fam_id', {}, members)
        self.assertNotIn('v3p', entry)

    def test_meta_version_bumped_to_1_6(self):
        """B5.1: meta.version bumped to '1.6' on schema change."""
        relays_data = {
            'relays': [
                {
                    'fingerprint': 'A' * 40,
                    'nickname': 'a',
                    'aroi_version': '3',
                    'or_addresses': [],
                }
            ],
            'sorted': {'family': {}},
            'relays_published': '2026-05-05 00:00:00',
        }
        with tempfile.NamedTemporaryFile(suffix='.json', mode='w', delete=False) as f:
            output_path = f.name
        try:
            generate_search_index(relays_data, output_path)
            with open(output_path) as f:
                index = json.load(f)
            self.assertEqual(index['meta']['version'], '1.6')
        finally:
            os.unlink(output_path)

    def test_lookups_v3_thresholds_present(self):
        """B5.1: lookups block exposes v3_thresholds map."""
        relays_data = {
            'relays': [],
            'sorted': {'family': {}},
            'relays_published': '2026-05-05 00:00:00',
        }
        with tempfile.NamedTemporaryFile(suffix='.json', mode='w', delete=False) as f:
            output_path = f.name
        try:
            generate_search_index(relays_data, output_path)
            with open(output_path) as f:
                index = json.load(f)
            thresholds = index['lookups'].get('v3_thresholds')
            self.assertIsNotNone(thresholds)
            # Mirror constants in aroi_validation.py for cross-surface
            # consistency.
            self.assertEqual(thresholds, {
                'explorer': 1,
                'migrating': 25,
                'mostly': 75,
                'complete': 100,
            })
        finally:
            os.unlink(output_path)


if __name__ == '__main__':
    unittest.main()
