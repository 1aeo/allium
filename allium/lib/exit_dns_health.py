"""
File: exit_dns_health.py

Exit DNS Health processing module.
Processes data from exitdnshealth.1aeo.com to track DNS resolution
capability of Tor exit relays.

Only exit relays (those with the Exit flag) are relevant.
Non-exit relays should show nothing for DNS health.
"""

from bisect import bisect_left
from typing import Dict, Optional, List

# Field names set on each exit relay dict during enrichment.
# Defined once here as the single source of truth — used by both the
# tested-relay and untested-relay code paths in attach_exit_dns_health_to_relays().
_RELAY_FIELDS = (
    'exit_dns_health_status', 'exit_dns_health_detail', 'exit_dns_health_error',
    'exit_dns_health_timing_ms', 'exit_dns_health_timing_percentile',
    'exit_dns_health_consecutive_failures',
    'exit_dns_health_query_domain', 'exit_dns_health_first_hop',
    'exit_dns_health_first_hop_nickname', 'exit_dns_health_first_hop_country',
    'exit_dns_health_exit_address', 'exit_dns_health_resolved_ip',
    'exit_dns_health_expected_ip',
    'exit_dns_health_cv_success', 'exit_dns_health_cv_total',
    'exit_dns_health_cv_improved', 'exit_dns_health_cv_per_instance',
    'exit_dns_health_timestamp',
)

_UNTESTED_DEFAULTS = {k: None for k in _RELAY_FIELDS}
_UNTESTED_DEFAULTS.update({
    'exit_dns_health_status': 'untested',
    'exit_dns_health_detail': 'untested',
    'exit_dns_health_consecutive_failures': 0,
    'exit_dns_health_cv_per_instance': {},
})

# Mapping from API metadata keys → metrics dict keys for calculate_exit_dns_health_metrics.
# Simple 1:1 integer fields that just need metadata.get(api_key, 0).
_META_INT_FIELDS = {
    'tested_relays': 'exit_dns_health_tested',
    'consensus_relays': 'exit_dns_health_consensus_exits',
    'unreachable_relays': 'exit_dns_health_unreachable',
    'dns_success': 'exit_dns_health_success',
    'dns_fail': 'exit_dns_health_fail',
    'dns_timeout': 'exit_dns_health_timeout',
    'dns_wrong_ip': 'exit_dns_health_wrong_ip',
    'dns_socks_error': 'exit_dns_health_socks_error',
    'dns_network_error': 'exit_dns_health_network_error',
    'dns_error': 'exit_dns_health_dns_error',
    'dns_exception': 'exit_dns_health_dns_exception',
    'dns_unknown': 'exit_dns_health_dns_unknown',
}

_META_FLOAT_FIELDS = {
    'dns_success_rate_percent': 'exit_dns_health_success_rate',
    'reachability_rate_percent': 'exit_dns_health_reachability_rate',
}

_CIRCUIT_FIELDS = {
    'circuit_timeout': 'exit_dns_health_circuit_timeout',
    'circuit_destroyed': 'exit_dns_health_circuit_destroyed',
    'circuit_channel_closed': 'exit_dns_health_circuit_channel_closed',
    'circuit_connect_failed': 'exit_dns_health_circuit_connect_failed',
}


def build_exit_dns_health_map(exit_dns_health_data: Optional[Dict]) -> Dict[str, Dict]:
    """
    Build fingerprint -> DNS health result map for O(1) per-relay lookup.
    Preserves full API data per relay for troubleshooting display.
    """
    if not exit_dns_health_data or 'results' not in exit_dns_health_data:
        return {}

    health_map = {}
    for result in exit_dns_health_data.get('results', []):
        fp = result.get('exit_fingerprint')
        if fp:
            cv = result.get('cv') or {}
            health_map[fp.upper()] = {
                'status': result.get('status', 'unknown'),
                'error': result.get('error'),
                'consecutive_failures': result.get('consecutive_failures', 0),
                'timing_ms': (result.get('timing') or {}).get('total_ms'),
                'query_domain': result.get('query_domain'),
                'first_hop': result.get('first_hop'),
                'exit_address': result.get('exit_address'),
                'resolved_ip': result.get('resolved_ip'),
                'expected_ip': result.get('expected_ip'),
                'cv_instances_success': cv.get('instances_success'),
                'cv_instances_total': cv.get('instances_total'),
                'cv_improved': cv.get('improved', False),
                'cv_per_instance': cv.get('per_instance', {}),
                'timestamp': result.get('timestamp'),
            }
    return health_map


def _compute_timing_percentiles(health_map: Dict[str, Dict]) -> List[float]:
    """Extract and sort timing values from healthy relays for percentile lookup."""
    timings = [e['timing_ms'] for e in health_map.values()
               if e['status'] == 'success' and e['timing_ms'] is not None]
    timings.sort()
    return timings


def _percentile_rank(sorted_timings: List[float], value: float) -> int:
    """Compute percentile rank (0-100) via bisect. O(log n) per call."""
    if not sorted_timings:
        return 0
    return round(100 * bisect_left(sorted_timings, value) / len(sorted_timings))


def attach_exit_dns_health_to_relays(relays: List[Dict], health_map: Dict[str, Dict]):
    """
    Attach DNS health fields to each relay dict in-place.
    Exit relays get full troubleshooting data; non-exit relays get status=None.
    """
    sorted_timings = _compute_timing_percentiles(health_map)

    # Build fp->(nickname, country) map for first_hop display (O(n) once)
    relay_info_map = {}
    for r in relays:
        fp = r.get('fingerprint', '').upper()
        if fp:
            relay_info_map[fp] = (r.get('nickname', ''), r.get('country', ''))

    for relay in relays:
        if 'Exit' not in relay.get('flags', []):
            relay['exit_dns_health_status'] = None
            continue

        fp = relay.get('fingerprint', '').upper()
        entry = health_map.get(fp)
        if not entry:
            relay.update(_UNTESTED_DEFAULTS)
            continue

        status = entry['status']
        is_success = status == 'success'
        fh_info = relay_info_map.get((entry['first_hop'] or '').upper(), ('', ''))

        relay.update({
            'exit_dns_health_status': 'success' if is_success else 'fail',
            'exit_dns_health_detail': status,
            'exit_dns_health_error': entry['error'],
            'exit_dns_health_timing_ms': entry['timing_ms'],
            'exit_dns_health_timing_percentile': (
                _percentile_rank(sorted_timings, entry['timing_ms'])
                if is_success and entry['timing_ms'] is not None else None),
            'exit_dns_health_consecutive_failures': entry['consecutive_failures'],
            'exit_dns_health_query_domain': entry['query_domain'],
            'exit_dns_health_first_hop': entry['first_hop'],
            'exit_dns_health_first_hop_nickname': fh_info[0],
            'exit_dns_health_first_hop_country': fh_info[1],
            'exit_dns_health_exit_address': entry['exit_address'],
            'exit_dns_health_resolved_ip': entry['resolved_ip'],
            'exit_dns_health_expected_ip': entry['expected_ip'],
            'exit_dns_health_cv_success': entry['cv_instances_success'],
            'exit_dns_health_cv_total': entry['cv_instances_total'],
            'exit_dns_health_cv_improved': entry['cv_improved'],
            'exit_dns_health_cv_per_instance': entry['cv_per_instance'],
            'exit_dns_health_timestamp': entry['timestamp'],
        })


def calculate_exit_dns_health_metrics(exit_dns_health_data: Optional[Dict] = None) -> Dict:
    """
    Calculate network-wide exit DNS health metrics for the health dashboard.
    Reads stats from API metadata; computes aggregates for display.
    """
    metrics = {v: 0 for v in _META_INT_FIELDS.values()}
    metrics.update({v: 0.0 for v in _META_FLOAT_FIELDS.values()})
    metrics.update({v: 0 for v in _CIRCUIT_FIELDS.values()})
    metrics.update({
        'exit_dns_health_available': False,
        'exit_dns_health_timestamp': 'Unknown',
        'exit_dns_health_run_id': '',
        'exit_dns_health_total_failures': 0,
        'exit_dns_health_circuit_other': 0,
        'exit_dns_health_timing_avg_ms': 0,
        'exit_dns_health_timing_p50_ms': 0,
        'exit_dns_health_timing_p95_ms': 0,
        'exit_dns_health_timing_p99_ms': 0,
    })

    if not exit_dns_health_data or not isinstance(exit_dns_health_data, dict):
        return metrics
    if 'metadata' not in exit_dns_health_data:
        return metrics

    metadata = exit_dns_health_data['metadata']
    from .aroi_validation import _format_timestamp

    metrics['exit_dns_health_available'] = True
    metrics['exit_dns_health_timestamp'] = _format_timestamp(metadata.get('timestamp', ''))
    metrics['exit_dns_health_run_id'] = metadata.get('run_id', '')

    for api_key, metric_key in _META_INT_FIELDS.items():
        metrics[metric_key] = metadata.get(api_key, 0)
    for api_key, metric_key in _META_FLOAT_FIELDS.items():
        metrics[metric_key] = metadata.get(api_key, 0.0)

    metrics['exit_dns_health_total_failures'] = sum(
        metrics[k] for k in ('exit_dns_health_fail', 'exit_dns_health_timeout',
                              'exit_dns_health_wrong_ip', 'exit_dns_health_socks_error',
                              'exit_dns_health_network_error'))

    for api_key, metric_key in _CIRCUIT_FIELDS.items():
        metrics[metric_key] = metadata.get(api_key, 0)
    circuit_known = sum(metrics[v] for v in _CIRCUIT_FIELDS.values())
    metrics['exit_dns_health_circuit_other'] = max(0, metrics['exit_dns_health_unreachable'] - circuit_known)

    timing = metadata.get('timing', {}).get('total', {})
    for suffix in ('avg', 'p50', 'p95', 'p99'):
        metrics[f'exit_dns_health_timing_{suffix}_ms'] = timing.get(f'{suffix}_ms', 0)

    return metrics


def get_operator_exit_dns_health_summary(members: List[Dict], exit_count: int = None) -> Optional[Dict]:
    """
    Summarize exit DNS health for a group of relays.
    Accepts exit_count for fast bail-out when group has no exits.
    """
    if exit_count is not None and exit_count == 0:
        return None

    healthy = failing = untested = total_exits = 0
    for r in members:
        status = r.get('exit_dns_health_status')
        if status is None:
            continue
        total_exits += 1
        if status == 'success':
            healthy += 1
        elif status == 'fail':
            failing += 1
        else:
            untested += 1

    if total_exits == 0:
        return None

    return {
        'exit_count': total_exits,
        'healthy': healthy,
        'failing': failing,
        'untested': untested,
        'healthy_pct': round(100 * healthy / total_exits),
        'failing_pct': round(100 * failing / total_exits),
        'untested_pct': round(100 * untested / total_exits),
        'all_healthy': failing == 0 and untested == 0 and healthy > 0,
        'any_failing': failing > 0,
    }
