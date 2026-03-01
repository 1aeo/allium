"""
File: exit_dns_health.py

Exit DNS Health processing module.
Processes data from exitdnshealth.1aeo.com to track DNS resolution
capability of Tor exit relays.
"""

from .aroi_validation import _format_timestamp  # Reuse existing timestamp formatter


def build_exit_dns_health_map(exit_dns_health_data):
    """
    Build fingerprint -> DNS health result map for O(1) per-relay lookup.
    Called once, reused by multiple existing loops.

    Returns:
        Dict mapping uppercase fingerprint -> dict with keys:
        - status: 'success' | 'dns_fail' | 'timeout' | 'relay_unreachable' | etc.
        - error: error string or None
        - consecutive_failures: int
        - timing_ms: total timing in ms or None
        - is_healthy: bool (True only for 'success')
    """
    if not exit_dns_health_data or 'results' not in exit_dns_health_data:
        return {}

    health_map = {}
    for result in exit_dns_health_data.get('results', []):
        fp = result.get('exit_fingerprint')
        if fp:
            status = result.get('status', 'unknown')
            health_map[fp.upper()] = {
                'status': status,
                'error': result.get('error'),
                'consecutive_failures': result.get('consecutive_failures', 0),
                'timing_ms': result.get('timing', {}).get('total_ms') if result.get('timing') else None,
                'is_healthy': status == 'success',
            }
    return health_map


def calculate_exit_dns_health_metrics(exit_dns_health_data=None):
    """
    Calculate network-wide exit DNS health metrics for the health dashboard.
    Reads summary stats from top-level API fields (no relay iteration needed).
    """
    metrics = {
        'exit_dns_health_available': False,
        'exit_dns_health_timestamp': 'Unknown',
        'exit_dns_tested_count': 0,
        'exit_dns_success_count': 0,
        'exit_dns_fail_count': 0,
        'exit_dns_timeout_count': 0,
        'exit_dns_wrong_ip_count': 0,
        'exit_dns_socks_error_count': 0,
        'exit_dns_network_error_count': 0,
        'exit_dns_unreachable_count': 0,
        'exit_dns_success_rate': 0.0,
        'exit_dns_reachability_rate': 0.0,
        'exit_dns_consensus_relays': 0,
        'exit_dns_total_failures': 0,
    }

    if not exit_dns_health_data or 'metadata' not in exit_dns_health_data:
        return metrics

    metrics['exit_dns_health_available'] = True

    # Top-level summary stats (no relay loop — API provides these pre-computed)
    metrics['exit_dns_tested_count'] = exit_dns_health_data.get('tested_relays', 0)
    metrics['exit_dns_success_count'] = exit_dns_health_data.get('dns_success', 0)
    metrics['exit_dns_fail_count'] = exit_dns_health_data.get('dns_fail', 0)
    metrics['exit_dns_timeout_count'] = exit_dns_health_data.get('dns_timeout', 0)
    metrics['exit_dns_wrong_ip_count'] = exit_dns_health_data.get('dns_wrong_ip', 0)
    metrics['exit_dns_socks_error_count'] = exit_dns_health_data.get('dns_socks_error', 0)
    metrics['exit_dns_network_error_count'] = exit_dns_health_data.get('dns_network_error', 0)
    metrics['exit_dns_unreachable_count'] = exit_dns_health_data.get('unreachable_relays', 0)
    metrics['exit_dns_success_rate'] = exit_dns_health_data.get('dns_success_rate_percent', 0.0)
    metrics['exit_dns_reachability_rate'] = exit_dns_health_data.get('reachability_rate_percent', 0.0)
    metrics['exit_dns_consensus_relays'] = exit_dns_health_data.get('consensus_relays', 0)

    # Metadata
    metadata = exit_dns_health_data.get('metadata', {})
    metrics['exit_dns_health_timestamp'] = _format_timestamp(metadata.get('timestamp', ''))

    # Total failures
    metrics['exit_dns_total_failures'] = (
        metrics['exit_dns_fail_count'] +
        metrics['exit_dns_timeout_count'] +
        metrics['exit_dns_wrong_ip_count'] +
        metrics['exit_dns_socks_error_count'] +
        metrics['exit_dns_network_error_count']
    )

    return metrics
