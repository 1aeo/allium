#!/usr/bin/env python3
"""
Test Exit DNS Health processing module.
Tests map building, relay attachment, metrics calculation, and operator summaries.

Uses pytest conventions: plain functions, assert statements, module-level helpers.
"""

from allium.lib.exit_dns_health import (
    build_exit_dns_health_map,
    attach_exit_dns_health_to_relays,
    calculate_exit_dns_health_metrics,
    get_operator_exit_dns_health_summary,
    _build_dns_summary_dict,
)
from allium.lib.workers import _validate_exit_dns_health_response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_health_entry(status='success', error=None, consecutive_failures=0,
                       timing_ms=None, first_hop=None, query_domain=None,
                       exit_address=None, resolved_ip=None, expected_ip=None):
    """Build a complete health map entry with all required fields."""
    return {
        'status': status,
        'error': error,
        'consecutive_failures': consecutive_failures,
        'timing_ms': timing_ms,
        'first_hop': first_hop,
        'query_domain': query_domain,
        'exit_address': exit_address,
        'resolved_ip': resolved_ip,
        'expected_ip': expected_ip,
        'cv_instances_success': None,
        'cv_instances_total': None,
        'cv_improved': False,
        'cv_per_instance': {},
        'timestamp': None,
    }


def _make_relay(fp, flags, **extra):
    """Build a minimal relay dict."""
    r = {'fingerprint': fp, 'flags': flags}
    r.update(extra)
    return r


def _make_exit_status(status):
    """Build a relay with pre-attached DNS health status for summary tests."""
    return {'exit_dns_health_status': status, 'flags': ['Exit']}


def _make_non_exit():
    return {'exit_dns_health_status': None, 'flags': ['Guard']}


# ---------------------------------------------------------------------------
# build_exit_dns_health_map
# ---------------------------------------------------------------------------

def test_build_map_basic():
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
    assert len(m) == 2
    assert m['ABC123']['status'] == 'success'
    assert m['ABC123']['timing_ms'] == 5000
    assert m['DEF456']['status'] == 'dns_fail'
    assert m['DEF456']['error'] == 'NXDOMAIN'
    assert m['DEF456']['consecutive_failures'] == 3
    assert m['DEF456']['timing_ms'] is None


def test_build_map_empty():
    assert build_exit_dns_health_map(None) == {}
    assert build_exit_dns_health_map({}) == {}
    assert build_exit_dns_health_map({'results': []}) == {}


def test_build_map_uppercase():
    data = {
        'metadata': {},
        'results': [
            {'exit_fingerprint': 'abcdef', 'status': 'success',
             'error': None, 'consecutive_failures': 0, 'timing': None},
        ],
    }
    m = build_exit_dns_health_map(data)
    assert 'ABCDEF' in m
    assert 'abcdef' not in m


def test_build_map_preserves_cv_data():
    data = {
        'metadata': {},
        'results': [
            {'exit_fingerprint': 'AAA', 'status': 'success',
             'error': None, 'consecutive_failures': 0, 'timing': {'total_ms': 100},
             'cv': {'instances_success': 3, 'instances_total': 4, 'improved': True}},
        ],
    }
    m = build_exit_dns_health_map(data)
    assert m['AAA']['cv_instances_success'] == 3
    assert m['AAA']['cv_instances_total'] == 4
    assert m['AAA']['cv_improved'] is True


# ---------------------------------------------------------------------------
# attach_exit_dns_health_to_relays
# ---------------------------------------------------------------------------

def test_attach_exit_success():
    relays = [_make_relay('AAA', ['Exit', 'Fast'])]
    health_map = {'AAA': _make_health_entry('success', timing_ms=1234)}
    attach_exit_dns_health_to_relays(relays, health_map)
    assert relays[0]['exit_dns_health_status'] == 'success'
    assert relays[0]['exit_dns_health_detail'] == 'success'
    assert relays[0]['exit_dns_health_timing_ms'] == 1234


def test_attach_exit_dns_fail():
    relays = [_make_relay('BBB', ['Exit'])]
    health_map = {'BBB': _make_health_entry('dns_fail', error='NXDOMAIN',
                                             consecutive_failures=5)}
    attach_exit_dns_health_to_relays(relays, health_map)
    assert relays[0]['exit_dns_health_status'] == 'fail'
    assert relays[0]['exit_dns_health_detail'] == 'dns_fail'
    assert relays[0]['exit_dns_health_error'] == 'NXDOMAIN'
    assert relays[0]['exit_dns_health_consecutive_failures'] == 5


def test_attach_exit_timeout():
    relays = [_make_relay('CCC', ['Exit'])]
    health_map = {'CCC': _make_health_entry('timeout', error='timed out',
                                             consecutive_failures=1)}
    attach_exit_dns_health_to_relays(relays, health_map)
    assert relays[0]['exit_dns_health_status'] == 'fail'
    assert relays[0]['exit_dns_health_detail'] == 'timeout'


def test_attach_exit_not_in_map():
    relays = [_make_relay('DDD', ['Exit'])]
    attach_exit_dns_health_to_relays(relays, {})
    assert relays[0]['exit_dns_health_status'] == 'untested'
    assert relays[0]['exit_dns_health_error'] is None


def test_attach_non_exit():
    relays = [_make_relay('EEE', ['Guard', 'Fast'])]
    health_map = {'EEE': _make_health_entry('success', timing_ms=100)}
    attach_exit_dns_health_to_relays(relays, health_map)
    assert relays[0]['exit_dns_health_status'] is None
    assert 'exit_dns_health_detail' not in relays[0]


def test_attach_first_hop_info():
    relays = [
        _make_relay('AAA', ['Exit']),
        _make_relay('GUARD1', ['Guard'], nickname='MyGuard', country='DE'),
    ]
    health_map = {'AAA': _make_health_entry('success', first_hop='GUARD1', timing_ms=500)}
    attach_exit_dns_health_to_relays(relays, health_map)
    assert relays[0]['exit_dns_health_first_hop'] == 'GUARD1'
    assert relays[0]['exit_dns_health_first_hop_nickname'] == 'MyGuard'
    assert relays[0]['exit_dns_health_first_hop_country'] == 'DE'


# ---------------------------------------------------------------------------
# calculate_exit_dns_health_metrics
# ---------------------------------------------------------------------------

def test_metrics_with_data():
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
    assert m['exit_dns_health_available'] is True
    assert m['exit_dns_health_tested'] == 100
    assert m['exit_dns_health_success'] == 90
    assert m['exit_dns_health_fail'] == 3
    assert m['exit_dns_health_timeout'] == 2
    assert m['exit_dns_health_wrong_ip'] == 1
    assert m['exit_dns_health_success_rate'] == 93.75
    assert m['exit_dns_health_run_id'] == 'test123'


def test_metrics_no_data():
    m = calculate_exit_dns_health_metrics(None)
    assert m['exit_dns_health_available'] is False
    assert m['exit_dns_health_tested'] == 0
    assert m['exit_dns_health_success_rate'] == 0.0


def test_metrics_total_failures():
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
    assert m['exit_dns_health_total_failures'] == 12  # 5+3+1+2+1


# ---------------------------------------------------------------------------
# get_operator_exit_dns_health_summary
# ---------------------------------------------------------------------------

def test_summary_no_exits():
    members = [_make_non_exit(), _make_non_exit()]
    assert get_operator_exit_dns_health_summary(members) is None


def test_summary_all_healthy():
    members = [_make_exit_status('success'), _make_exit_status('success')]
    s = get_operator_exit_dns_health_summary(members)
    assert s['exit_count'] == 2
    assert s['healthy'] == 2
    assert s['failing'] == 0
    assert s['all_healthy'] is True
    assert s['any_failing'] is False
    assert s['healthy_pct'] == 100
    assert s['failing_pct'] == 0


def test_summary_mixed():
    members = [_make_exit_status('success'), _make_exit_status('fail'), _make_non_exit()]
    s = get_operator_exit_dns_health_summary(members)
    assert s['exit_count'] == 2
    assert s['healthy'] == 1
    assert s['failing'] == 1
    assert s['all_healthy'] is False
    assert s['any_failing'] is True


def test_summary_all_untested():
    members = [_make_exit_status('untested'), _make_exit_status('untested')]
    s = get_operator_exit_dns_health_summary(members)
    assert s['untested'] == 2
    assert s['all_healthy'] is False
    assert s['any_failing'] is False


def test_summary_exit_count_bailout():
    members = [_make_exit_status('success')]
    assert get_operator_exit_dns_health_summary(members, exit_count=0) is None


# ---------------------------------------------------------------------------
# _build_dns_summary_dict (shared builder)
# ---------------------------------------------------------------------------

def test_build_summary_dict_shape():
    d = _build_dns_summary_dict(10, 8, 1, 1)
    assert d['exit_count'] == 10
    assert d['healthy'] == 8
    assert d['failing'] == 1
    assert d['untested'] == 1
    assert d['healthy_pct'] == 80
    assert d['failing_pct'] == 10
    assert d['untested_pct'] == 10
    assert d['all_healthy'] is False
    assert d['any_failing'] is True


# ---------------------------------------------------------------------------
# _validate_exit_dns_health_response
# ---------------------------------------------------------------------------

def test_valid_response():
    data = {'metadata': {'timestamp': 'x', 'dns_success_rate_percent': 99.0}, 'results': []}
    assert _validate_exit_dns_health_response(data) is True


def test_missing_metadata():
    assert _validate_exit_dns_health_response({'results': []}) is False


def test_missing_results():
    assert _validate_exit_dns_health_response({'metadata': {'timestamp': 'x'}}) is False


def test_missing_timestamp():
    assert _validate_exit_dns_health_response(
        {'metadata': {'dns_success_rate_percent': 99.0}, 'results': []}) is False


def test_non_dict_data():
    assert _validate_exit_dns_health_response("not a dict") is False
    assert _validate_exit_dns_health_response(None) is False


def test_non_list_results():
    assert _validate_exit_dns_health_response(
        {'metadata': {'timestamp': 'x', 'dns_success_rate_percent': 1}, 'results': 'bad'}) is False


def test_non_dict_result_entry():
    assert _validate_exit_dns_health_response(
        {'metadata': {'timestamp': 'x', 'dns_success_rate_percent': 1}, 'results': ['bad']}) is False
