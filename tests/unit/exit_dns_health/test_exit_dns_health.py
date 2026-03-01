#!/usr/bin/env python3
"""
Test Exit DNS Health processing module.
Tests map building, relay attachment, metrics calculation, and operator summaries.
"""

import unittest

from allium.lib.exit_dns_health import (
    build_exit_dns_health_map,
    attach_exit_dns_health_to_relays,
    calculate_exit_dns_health_metrics,
    get_operator_exit_dns_health_summary,
)


class TestBuildMap(unittest.TestCase):
    """Test build_exit_dns_health_map()."""

    def test_build_map_basic(self):
        """Map is built correctly from API response."""
        data = {
            'metadata': {'timestamp': '2026-01-01T00:00:00Z'},
            'results': [
                {'exit_fingerprint': 'ABC123', 'status': 'success',
                 'error': None, 'consecutive_failures': 0,
                 'timing': {'total_ms': 5000}},
                {'exit_fingerprint': 'DEF456', 'status': 'dns_fail',
                 'error': 'NXDOMAIN', 'consecutive_failures': 3,
                 'timing': None},
            ],
        }
        m = build_exit_dns_health_map(data)
        self.assertEqual(len(m), 2)
        self.assertEqual(m['ABC123']['status'], 'success')
        self.assertEqual(m['ABC123']['timing_ms'], 5000)
        self.assertEqual(m['DEF456']['status'], 'dns_fail')
        self.assertEqual(m['DEF456']['error'], 'NXDOMAIN')
        self.assertEqual(m['DEF456']['consecutive_failures'], 3)
        self.assertIsNone(m['DEF456']['timing_ms'])

    def test_build_map_empty(self):
        """None/empty data returns empty dict."""
        self.assertEqual(build_exit_dns_health_map(None), {})
        self.assertEqual(build_exit_dns_health_map({}), {})
        self.assertEqual(build_exit_dns_health_map({'results': []}), {})

    def test_build_map_uppercase(self):
        """Fingerprints are uppercased."""
        data = {
            'metadata': {},
            'results': [
                {'exit_fingerprint': 'abcdef', 'status': 'success',
                 'error': None, 'consecutive_failures': 0, 'timing': None},
            ],
        }
        m = build_exit_dns_health_map(data)
        self.assertIn('ABCDEF', m)
        self.assertNotIn('abcdef', m)


class TestAttachToRelays(unittest.TestCase):
    """Test attach_exit_dns_health_to_relays()."""

    def _make_relay(self, fp, flags):
        return {'fingerprint': fp, 'flags': flags}

    def test_attach_exit_success(self):
        """Exit relay with success status gets status='success'."""
        relays = [self._make_relay('AAA', ['Exit', 'Fast'])]
        health_map = {'AAA': {'status': 'success', 'error': None,
                              'consecutive_failures': 0, 'timing_ms': 1234}}
        attach_exit_dns_health_to_relays(relays, health_map)
        self.assertEqual(relays[0]['exit_dns_health_status'], 'success')
        self.assertEqual(relays[0]['exit_dns_health_detail'], 'success')
        self.assertEqual(relays[0]['exit_dns_health_timing_ms'], 1234)

    def test_attach_exit_dns_fail(self):
        """Exit relay with dns_fail gets status='fail', detail='dns_fail'."""
        relays = [self._make_relay('BBB', ['Exit'])]
        health_map = {'BBB': {'status': 'dns_fail', 'error': 'NXDOMAIN',
                              'consecutive_failures': 5, 'timing_ms': None}}
        attach_exit_dns_health_to_relays(relays, health_map)
        self.assertEqual(relays[0]['exit_dns_health_status'], 'fail')
        self.assertEqual(relays[0]['exit_dns_health_detail'], 'dns_fail')
        self.assertEqual(relays[0]['exit_dns_health_error'], 'NXDOMAIN')
        self.assertEqual(relays[0]['exit_dns_health_consecutive_failures'], 5)

    def test_attach_exit_timeout(self):
        """Exit relay with timeout gets status='fail', detail='timeout'."""
        relays = [self._make_relay('CCC', ['Exit'])]
        health_map = {'CCC': {'status': 'timeout', 'error': 'timed out',
                              'consecutive_failures': 1, 'timing_ms': None}}
        attach_exit_dns_health_to_relays(relays, health_map)
        self.assertEqual(relays[0]['exit_dns_health_status'], 'fail')
        self.assertEqual(relays[0]['exit_dns_health_detail'], 'timeout')

    def test_attach_exit_not_in_map(self):
        """Exit relay not in map gets status='untested'."""
        relays = [self._make_relay('DDD', ['Exit'])]
        attach_exit_dns_health_to_relays(relays, {})
        self.assertEqual(relays[0]['exit_dns_health_status'], 'untested')
        self.assertIsNone(relays[0]['exit_dns_health_error'])

    def test_attach_non_exit(self):
        """Non-exit relay gets exit_dns_health_status=None."""
        relays = [self._make_relay('EEE', ['Guard', 'Fast'])]
        health_map = {'EEE': {'status': 'success', 'error': None,
                              'consecutive_failures': 0, 'timing_ms': 100}}
        attach_exit_dns_health_to_relays(relays, health_map)
        self.assertIsNone(relays[0]['exit_dns_health_status'])
        # Non-exit relay should NOT have detail fields
        self.assertNotIn('exit_dns_health_detail', relays[0])


class TestCalculateMetrics(unittest.TestCase):
    """Test calculate_exit_dns_health_metrics()."""

    def test_metrics_with_data(self):
        """All metrics populated from API metadata."""
        data = {
            'metadata': {
                'timestamp': '2026-02-28T20:00:00Z',
                'run_id': 'test123',
                'tested_relays': 100,
                'consensus_relays': 110,
                'unreachable_relays': 5,
                'dns_success': 90,
                'dns_fail': 3,
                'dns_timeout': 2,
                'dns_wrong_ip': 1,
                'dns_socks_error': 0,
                'dns_network_error': 0,
                'dns_success_rate_percent': 93.75,
                'reachability_rate_percent': 95.45,
            },
            'results': [],
        }
        m = calculate_exit_dns_health_metrics(data)
        self.assertTrue(m['exit_dns_health_available'])
        self.assertEqual(m['exit_dns_health_tested'], 100)
        self.assertEqual(m['exit_dns_health_success'], 90)
        self.assertEqual(m['exit_dns_health_fail'], 3)
        self.assertEqual(m['exit_dns_health_timeout'], 2)
        self.assertEqual(m['exit_dns_health_wrong_ip'], 1)
        self.assertAlmostEqual(m['exit_dns_health_success_rate'], 93.75)
        self.assertEqual(m['exit_dns_health_run_id'], 'test123')

    def test_metrics_no_data(self):
        """None data returns safe defaults."""
        m = calculate_exit_dns_health_metrics(None)
        self.assertFalse(m['exit_dns_health_available'])
        self.assertEqual(m['exit_dns_health_tested'], 0)
        self.assertAlmostEqual(m['exit_dns_health_success_rate'], 0.0)

    def test_metrics_total_failures(self):
        """Total failures aggregation is correct."""
        data = {
            'metadata': {
                'timestamp': '2026-01-01T00:00:00Z',
                'dns_success_rate_percent': 90.0,
                'dns_fail': 5,
                'dns_timeout': 3,
                'dns_wrong_ip': 1,
                'dns_socks_error': 2,
                'dns_network_error': 1,
            },
            'results': [],
        }
        m = calculate_exit_dns_health_metrics(data)
        self.assertEqual(m['exit_dns_health_total_failures'], 12)  # 5+3+1+2+1


class TestOperatorSummary(unittest.TestCase):
    """Test get_operator_exit_dns_health_summary()."""

    def _make_relay(self, status):
        return {'exit_dns_health_status': status, 'flags': ['Exit']}

    def _make_non_exit(self):
        return {'exit_dns_health_status': None, 'flags': ['Guard']}

    def test_summary_no_exits(self):
        """No exit relays returns None."""
        members = [self._make_non_exit(), self._make_non_exit()]
        self.assertIsNone(get_operator_exit_dns_health_summary(members))

    def test_summary_all_healthy(self):
        """All healthy sets correct flags."""
        members = [self._make_relay('success'), self._make_relay('success')]
        s = get_operator_exit_dns_health_summary(members)
        self.assertEqual(s['exit_count'], 2)
        self.assertEqual(s['healthy'], 2)
        self.assertEqual(s['failing'], 0)
        self.assertTrue(s['all_healthy'])
        self.assertFalse(s['any_failing'])

    def test_summary_mixed(self):
        """Mix of healthy and failing."""
        members = [self._make_relay('success'), self._make_relay('fail'),
                   self._make_non_exit()]
        s = get_operator_exit_dns_health_summary(members)
        self.assertEqual(s['exit_count'], 2)
        self.assertEqual(s['healthy'], 1)
        self.assertEqual(s['failing'], 1)
        self.assertFalse(s['all_healthy'])
        self.assertTrue(s['any_failing'])

    def test_summary_all_untested(self):
        """All untested edge case."""
        members = [self._make_relay('untested'), self._make_relay('untested')]
        s = get_operator_exit_dns_health_summary(members)
        self.assertEqual(s['untested'], 2)
        self.assertFalse(s['all_healthy'])
        self.assertFalse(s['any_failing'])

    def test_summary_exit_count_bailout(self):
        """exit_count=0 returns None without iteration."""
        members = [self._make_relay('success')]  # Would normally return summary
        # But with exit_count=0, should bail out
        self.assertIsNone(get_operator_exit_dns_health_summary(members, exit_count=0))


class TestValidateResponse(unittest.TestCase):
    """Test response validation logic."""

    def test_valid_response(self):
        """Valid response passes."""
        from allium.lib.workers import _validate_exit_dns_health_response
        data = {'metadata': {'timestamp': 'x', 'dns_success_rate_percent': 99.0}, 'results': []}
        self.assertTrue(_validate_exit_dns_health_response(data))

    def test_missing_metadata(self):
        """Missing metadata fails."""
        from allium.lib.workers import _validate_exit_dns_health_response
        self.assertFalse(_validate_exit_dns_health_response({'results': []}))

    def test_missing_results(self):
        """Missing results fails."""
        from allium.lib.workers import _validate_exit_dns_health_response
        self.assertFalse(_validate_exit_dns_health_response({'metadata': {'timestamp': 'x'}}))

    def test_missing_timestamp(self):
        """Missing timestamp in metadata fails."""
        from allium.lib.workers import _validate_exit_dns_health_response
        self.assertFalse(_validate_exit_dns_health_response(
            {'metadata': {'dns_success_rate_percent': 99.0}, 'results': []}))


if __name__ == '__main__':
    unittest.main()
