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


def build_exit_dns_health_map(exit_dns_health_data: Optional[Dict]) -> Dict[str, Dict]:
    """
    Build fingerprint -> DNS health result map for O(1) per-relay lookup.
    Called once during enrichment, reused by relay attachment.

    Preserves full API data per relay (cv, query_domain, first_hop, etc.)
    for troubleshooting display on individual relay pages.

    Also collects timing values for percentile computation.

    Args:
        exit_dns_health_data: Raw API response from exitdnshealth.1aeo.com

    Returns:
        Dict mapping uppercase fingerprint -> result dict
    """
    if not exit_dns_health_data or 'results' not in exit_dns_health_data:
        return {}

    health_map = {}
    for result in exit_dns_health_data.get('results', []):
        fp = result.get('exit_fingerprint')
        if fp:
            timing_ms = (result.get('timing') or {}).get('total_ms')
            cv = result.get('cv', {})
            health_map[fp.upper()] = {
                'status': result.get('status', 'unknown'),
                'error': result.get('error'),
                'consecutive_failures': result.get('consecutive_failures', 0),
                'timing_ms': timing_ms,
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
    """
    Extract and sort timing values from healthy relays for percentile lookup.
    Returns sorted list; empty if no timings available.
    """
    timings = [e['timing_ms'] for e in health_map.values()
               if e['status'] == 'success' and e['timing_ms'] is not None]
    timings.sort()
    return timings


def _percentile_rank(sorted_timings: List[float], value: float) -> int:
    """
    Compute the percentile rank of a value within sorted timings.
    Returns integer 0-100 representing what percentage of relays are slower.
    Uses bisect for O(log n) per lookup.
    """
    if not sorted_timings:
        return 0
    pos = bisect_left(sorted_timings, value)
    return round(100 * pos / len(sorted_timings))


def attach_exit_dns_health_to_relays(relays: List[Dict], health_map: Dict[str, Dict]):
    """
    Attach DNS health status to each relay dict in-place.

    Exit relays get:
      - exit_dns_health_status: 'success' | 'fail' | 'untested'
      - exit_dns_health_detail: specific status string
      - exit_dns_health_error: error message or None
      - exit_dns_health_timing_ms: timing in ms or None
      - exit_dns_health_timing_percentile: int 0-100 or None
      - exit_dns_health_consecutive_failures: int
      - exit_dns_health_query_domain, _first_hop, _exit_address,
        _resolved_ip, _expected_ip: for troubleshooting display
      - exit_dns_health_cv_*: cross-validation details

    Non-exit relays get:
      - exit_dns_health_status: None  (templates check this to hide)
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
        if entry:
            status = entry['status']
            relay['exit_dns_health_status'] = 'success' if status == 'success' else 'fail'
            relay['exit_dns_health_detail'] = status
            relay['exit_dns_health_error'] = entry['error']
            relay['exit_dns_health_timing_ms'] = entry['timing_ms']
            relay['exit_dns_health_consecutive_failures'] = entry['consecutive_failures']
            # Percentile (only meaningful for healthy relays with timing)
            if status == 'success' and entry['timing_ms'] is not None:
                relay['exit_dns_health_timing_percentile'] = _percentile_rank(
                    sorted_timings, entry['timing_ms'])
            else:
                relay['exit_dns_health_timing_percentile'] = None
            # Troubleshooting fields
            relay['exit_dns_health_query_domain'] = entry['query_domain']
            relay['exit_dns_health_first_hop'] = entry['first_hop']
            fh_info = relay_info_map.get((entry['first_hop'] or '').upper(), ('', ''))
            relay['exit_dns_health_first_hop_nickname'] = fh_info[0]
            relay['exit_dns_health_first_hop_country'] = fh_info[1]
            relay['exit_dns_health_exit_address'] = entry['exit_address']
            relay['exit_dns_health_resolved_ip'] = entry['resolved_ip']
            relay['exit_dns_health_expected_ip'] = entry['expected_ip']
            relay['exit_dns_health_cv_success'] = entry['cv_instances_success']
            relay['exit_dns_health_cv_total'] = entry['cv_instances_total']
            relay['exit_dns_health_cv_improved'] = entry['cv_improved']
            relay['exit_dns_health_cv_per_instance'] = entry['cv_per_instance']
            relay['exit_dns_health_timestamp'] = entry['timestamp']
        else:
            relay['exit_dns_health_status'] = 'untested'
            relay['exit_dns_health_detail'] = 'untested'
            relay['exit_dns_health_error'] = None
            relay['exit_dns_health_timing_ms'] = None
            relay['exit_dns_health_timing_percentile'] = None
            relay['exit_dns_health_consecutive_failures'] = 0
            relay['exit_dns_health_query_domain'] = None
            relay['exit_dns_health_first_hop'] = None
            relay['exit_dns_health_first_hop_nickname'] = None
            relay['exit_dns_health_first_hop_country'] = None
            relay['exit_dns_health_exit_address'] = None
            relay['exit_dns_health_resolved_ip'] = None
            relay['exit_dns_health_expected_ip'] = None
            relay['exit_dns_health_cv_success'] = None
            relay['exit_dns_health_cv_total'] = None
            relay['exit_dns_health_cv_improved'] = None
            relay['exit_dns_health_cv_per_instance'] = {}
            relay['exit_dns_health_timestamp'] = None


def calculate_exit_dns_health_metrics(exit_dns_health_data: Optional[Dict] = None) -> Dict:
    """
    Calculate network-wide exit DNS health metrics for the health dashboard.
    Reads stats from metadata (where they live in the API response).
    Computes total_failures aggregate for summary display.
    Includes circuit-level failure breakdown and timing percentiles.
    """
    metrics = {
        'exit_dns_health_available': False,
        'exit_dns_health_timestamp': 'Unknown',
        'exit_dns_health_run_id': '',
        'exit_dns_health_tested': 0,
        'exit_dns_health_consensus_exits': 0,
        'exit_dns_health_unreachable': 0,
        'exit_dns_health_success': 0,
        'exit_dns_health_fail': 0,
        'exit_dns_health_timeout': 0,
        'exit_dns_health_wrong_ip': 0,
        'exit_dns_health_socks_error': 0,
        'exit_dns_health_network_error': 0,
        'exit_dns_health_dns_error': 0,
        'exit_dns_health_dns_exception': 0,
        'exit_dns_health_dns_unknown': 0,
        'exit_dns_health_success_rate': 0.0,
        'exit_dns_health_reachability_rate': 0.0,
        'exit_dns_health_total_failures': 0,
        # Circuit-level failure breakdown
        'exit_dns_health_circuit_timeout': 0,
        'exit_dns_health_circuit_destroyed': 0,
        'exit_dns_health_circuit_channel_closed': 0,
        'exit_dns_health_circuit_connect_failed': 0,
        'exit_dns_health_circuit_other': 0,
        # Timing percentiles from API metadata
        'exit_dns_health_timing_avg_ms': 0,
        'exit_dns_health_timing_p50_ms': 0,
        'exit_dns_health_timing_p95_ms': 0,
        'exit_dns_health_timing_p99_ms': 0,
    }

    if not exit_dns_health_data or not isinstance(exit_dns_health_data, dict):
        return metrics
    if 'metadata' not in exit_dns_health_data:
        return metrics

    metadata = exit_dns_health_data.get('metadata', {})

    from .aroi_validation import _format_timestamp

    metrics['exit_dns_health_available'] = True
    metrics['exit_dns_health_timestamp'] = _format_timestamp(metadata.get('timestamp', ''))
    metrics['exit_dns_health_run_id'] = metadata.get('run_id', '')
    metrics['exit_dns_health_tested'] = metadata.get('tested_relays', 0)
    metrics['exit_dns_health_consensus_exits'] = metadata.get('consensus_relays', 0)
    metrics['exit_dns_health_unreachable'] = metadata.get('unreachable_relays', 0)
    metrics['exit_dns_health_success'] = metadata.get('dns_success', 0)
    metrics['exit_dns_health_fail'] = metadata.get('dns_fail', 0)
    metrics['exit_dns_health_timeout'] = metadata.get('dns_timeout', 0)
    metrics['exit_dns_health_wrong_ip'] = metadata.get('dns_wrong_ip', 0)
    metrics['exit_dns_health_socks_error'] = metadata.get('dns_socks_error', 0)
    metrics['exit_dns_health_network_error'] = metadata.get('dns_network_error', 0)
    metrics['exit_dns_health_dns_error'] = metadata.get('dns_error', 0)
    metrics['exit_dns_health_dns_exception'] = metadata.get('dns_exception', 0)
    metrics['exit_dns_health_dns_unknown'] = metadata.get('dns_unknown', 0)
    metrics['exit_dns_health_success_rate'] = metadata.get('dns_success_rate_percent', 0.0)
    metrics['exit_dns_health_reachability_rate'] = metadata.get('reachability_rate_percent', 0.0)

    metrics['exit_dns_health_total_failures'] = (
        metrics['exit_dns_health_fail'] +
        metrics['exit_dns_health_timeout'] +
        metrics['exit_dns_health_wrong_ip'] +
        metrics['exit_dns_health_socks_error'] +
        metrics['exit_dns_health_network_error']
    )

    # Circuit-level failures (explain "Unreachable" category)
    metrics['exit_dns_health_circuit_timeout'] = metadata.get('circuit_timeout', 0)
    metrics['exit_dns_health_circuit_destroyed'] = metadata.get('circuit_destroyed', 0)
    metrics['exit_dns_health_circuit_channel_closed'] = metadata.get('circuit_channel_closed', 0)
    metrics['exit_dns_health_circuit_connect_failed'] = metadata.get('circuit_connect_failed', 0)
    circuit_known = (metrics['exit_dns_health_circuit_timeout'] +
                     metrics['exit_dns_health_circuit_destroyed'] +
                     metrics['exit_dns_health_circuit_channel_closed'] +
                     metrics['exit_dns_health_circuit_connect_failed'])
    metrics['exit_dns_health_circuit_other'] = max(0, metrics['exit_dns_health_unreachable'] - circuit_known)

    # Timing from API metadata
    timing = metadata.get('timing', {}).get('total', {})
    metrics['exit_dns_health_timing_avg_ms'] = timing.get('avg_ms', 0)
    metrics['exit_dns_health_timing_p50_ms'] = timing.get('p50_ms', 0)
    metrics['exit_dns_health_timing_p95_ms'] = timing.get('p95_ms', 0)
    metrics['exit_dns_health_timing_p99_ms'] = timing.get('p99_ms', 0)

    return metrics


def get_operator_exit_dns_health_summary(members: List[Dict], exit_count: int = None) -> Optional[Dict]:
    """
    Summarize exit DNS health for a group of relays (operator/AS/country/etc.).
    Reads from pre-attached relay['exit_dns_health_status'] fields.

    OPTIMIZATION: Accepts exit_count from categorization (already computed by sort_relay).
    If exit_count == 0, returns None immediately without iterating members.

    Returns:
        None if group has no exit relays, or dict with counts and percentages.
    """
    if exit_count is not None and exit_count == 0:
        return None

    healthy = 0
    failing = 0
    untested = 0
    total_exits = 0

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
