"""
File: exit_dns_health.py

Exit DNS Health processing module.
Processes data from exitdnshealth.1aeo.com to track DNS resolution
capability of Tor exit relays.

Only exit relays (those with the Exit flag) are relevant.
Non-exit relays should show nothing for DNS health.
"""

from typing import Dict, Optional, List


def build_exit_dns_health_map(exit_dns_health_data: Optional[Dict]) -> Dict[str, Dict]:
    """
    Build fingerprint -> DNS health result map for O(1) per-relay lookup.
    Called once during enrichment, reused by relay attachment.

    Args:
        exit_dns_health_data: Raw API response from exitdnshealth.1aeo.com

    Returns:
        Dict mapping uppercase fingerprint -> result dict with keys:
        - status: 'success' | 'dns_fail' | 'timeout' | 'relay_unreachable' | etc.
        - error: error string or None
        - consecutive_failures: int
        - timing_ms: total timing in ms or None
    """
    if not exit_dns_health_data or 'results' not in exit_dns_health_data:
        return {}

    health_map = {}
    for result in exit_dns_health_data.get('results', []):
        fp = result.get('exit_fingerprint')
        if fp:
            health_map[fp.upper()] = {
                'status': result.get('status', 'unknown'),
                'error': result.get('error'),
                'consecutive_failures': result.get('consecutive_failures', 0),
                'timing_ms': (result.get('timing') or {}).get('total_ms'),
            }
    return health_map


def attach_exit_dns_health_to_relays(relays: List[Dict], health_map: Dict[str, Dict]):
    """
    Attach DNS health status to each relay dict in-place.

    Exit relays get:
      - exit_dns_health_status: 'success' | 'fail' | 'untested'
      - exit_dns_health_detail: specific status string (e.g. 'dns_fail', 'timeout')
      - exit_dns_health_error: error message or None
      - exit_dns_health_timing_ms: timing in ms or None
      - exit_dns_health_consecutive_failures: int

    Non-exit relays get:
      - exit_dns_health_status: None  (templates check this to hide)

    Args:
        relays: List of relay dicts (modified in-place)
        health_map: From build_exit_dns_health_map()
    """
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
        else:
            relay['exit_dns_health_status'] = 'untested'
            relay['exit_dns_health_detail'] = 'untested'
            relay['exit_dns_health_error'] = None
            relay['exit_dns_health_timing_ms'] = None
            relay['exit_dns_health_consecutive_failures'] = 0


def calculate_exit_dns_health_metrics(exit_dns_health_data: Optional[Dict] = None) -> Dict:
    """
    Calculate network-wide exit DNS health metrics for the health dashboard.
    Reads stats from metadata (where they live in the API response).
    Computes total_failures aggregate for summary display.

    Args:
        exit_dns_health_data: Raw API response

    Returns:
        Dict of metrics for health_metrics integration
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
        'exit_dns_health_success_rate': 0.0,
        'exit_dns_health_reachability_rate': 0.0,
        'exit_dns_health_total_failures': 0,
    }

    if not exit_dns_health_data or not isinstance(exit_dns_health_data, dict):
        return metrics
    if 'metadata' not in exit_dns_health_data:
        return metrics

    metadata = exit_dns_health_data.get('metadata', {})

    # DRY: Reuse _format_timestamp from aroi_validation (same ISO->readable conversion)
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
    metrics['exit_dns_health_success_rate'] = metadata.get('dns_success_rate_percent', 0.0)
    metrics['exit_dns_health_reachability_rate'] = metadata.get('reachability_rate_percent', 0.0)

    # Aggregate total failures for summary display
    metrics['exit_dns_health_total_failures'] = (
        metrics['exit_dns_health_fail'] +
        metrics['exit_dns_health_timeout'] +
        metrics['exit_dns_health_wrong_ip'] +
        metrics['exit_dns_health_socks_error'] +
        metrics['exit_dns_health_network_error']
    )

    return metrics


def get_operator_exit_dns_health_summary(members: List[Dict], exit_count: int = None) -> Optional[Dict]:
    """
    Summarize exit DNS health for a group of relays (operator/AS/country/etc.).
    Reads from pre-attached relay['exit_dns_health_status'] fields.

    OPTIMIZATION: Accepts exit_count from categorization (already computed by sort_relay).
    If exit_count == 0, returns None immediately without iterating members.

    Args:
        members: List of relay dicts for this group (with exit_dns_health_status attached)
        exit_count: Optional pre-computed exit count from categorization for fast bail-out

    Returns:
        None if group has no exit relays, or dict with:
        - exit_count: total exit relays
        - healthy: count with exit_dns_health_status == 'success'
        - failing: count with exit_dns_health_status == 'fail'
        - untested: count with exit_dns_health_status == 'untested'
        - all_healthy: bool
        - any_failing: bool
    """
    # Fast bail-out using pre-computed exit_count from categorization
    if exit_count is not None and exit_count == 0:
        return None

    healthy = 0
    failing = 0
    untested = 0
    total_exits = 0

    for r in members:
        status = r.get('exit_dns_health_status')
        if status is None:  # Non-exit relay
            continue
        total_exits += 1
        if status == 'success':
            healthy += 1
        elif status == 'fail':
            failing += 1
        else:  # 'untested'
            untested += 1

    if total_exits == 0:
        return None

    return {
        'exit_count': total_exits,
        'healthy': healthy,
        'failing': failing,
        'untested': untested,
        'all_healthy': failing == 0 and untested == 0 and healthy > 0,
        'any_failing': failing > 0,
    }
