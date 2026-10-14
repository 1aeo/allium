"""
File: exit_dns_health.py

Exit DNS Health processing module.
Processes data from exitdnshealth.1aeo.com to track DNS resolution
capability of Tor exit relays.

Only exit relays (those with the Exit flag) are relevant.
Non-exit relays should show nothing for DNS health.
"""

import math
from bisect import bisect_left
from typing import Dict, Optional, List

# Upstream resolver categories in results[i].resolver.queries and metadata.resolvers
# (exitmap-dns-health-deploy scripts/resolver_stats.py).
# Version 1 used one "local" bucket (the exit's own address or origin AS). Version 2 splits
# that into local_24 (same IPv4 /24 or IPv6 /64, including the exit's own address), local_22
# (same IPv4 /22 or IPv6 /48), local_as (same origin AS outside those prefixes) and
# local_operator (same operator, other network). "local" stays accepted so version-1 reports
# still parse. Anything this version does not know still folds into "other".
RESOLVER_PROVIDERS = ('google', 'cloudflare', 'quad9', 'opendns', 'ffmuc')
RESOLVER_TIERS = ('local_24', 'local_22', 'local_as', 'local_operator')
RESOLVER_CATEGORIES = RESOLVER_PROVIDERS + ('local',) + RESOLVER_TIERS + ('other', 'unknown')
_RESOLVER_COUNT_FIELDS = ('exits_total', 'exits_covered', 'exits_labelled', 'exits_using_public')

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
    'exit_dns_health_resolver_primary', 'exit_dns_health_resolver_public',
    'exit_dns_health_resolver_queries',
)

_UNTESTED_DEFAULTS = {k: None for k in _RELAY_FIELDS}
_UNTESTED_DEFAULTS.update({
    'exit_dns_health_status': 'untested',
    'exit_dns_health_detail': 'untested',
    'exit_dns_health_consecutive_failures': 0,
    # NOTE: exit_dns_health_cv_per_instance is set to a fresh {} per relay
    # in _make_untested_defaults() to avoid shared mutable state.
})


def _make_untested_defaults():
    """Return a fresh copy of untested defaults with a new dict for cv_per_instance."""
    d = _UNTESTED_DEFAULTS.copy()
    d['exit_dns_health_cv_per_instance'] = {}
    return d

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


def _as_number(value) -> Optional[float]:
    """Return value as a finite, non-negative float; None for anything else (bools and strings too)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        value = float(value)
    except OverflowError:
        return None
    return value if math.isfinite(value) and value >= 0 else None


def _as_count(value) -> Optional[int]:
    """Return value as a non-negative integer count, or None."""
    number = _as_number(value)
    return int(number) if number is not None and number.is_integer() else None


def _as_percent(value) -> Optional[float]:
    """Return value as a percentage capped at 100, or None."""
    number = _as_number(value)
    return min(number, 100.0) if number is not None else None


def _parse_resolver(resolver) -> Optional[Dict]:
    """
    Validate one result's resolver block; None when absent or not a dict.
    Query counts keep known categories only (a category this version does not know
    counts as "other"), largest first, so labels and display stay bounded.
    """
    if not isinstance(resolver, dict):
        return None
    queries = {}
    raw_queries = resolver.get('queries')
    for category, count in (raw_queries.items() if isinstance(raw_queries, dict) else ()):
        count = _as_number(count)
        if count is not None:
            category = category if category in RESOLVER_CATEGORIES else 'other'
            queries[category] = round(queries.get(category, 0.0) + count, 2)
    primary = resolver.get('primary')
    if primary not in RESOLVER_CATEGORIES:
        primary = 'other' if isinstance(primary, str) else None
    public = resolver.get('public')
    if not isinstance(public, bool) or primary in (None, 'unknown'):
        public = None
    return {
        'primary': primary,
        'public': public,
        'queries': dict(sorted(queries.items(), key=lambda kv: (-kv[1], RESOLVER_CATEGORIES.index(kv[0])))),
    }


def parse_resolver_summary(metadata) -> Optional[Dict]:
    """
    Validate metadata.resolvers, the network-wide resolver shares; None when absent or unusable.
    Shares are percentages (0-100), weighted by exit probability unless 'weighted' is False.
    Missing or malformed values are None, never 0, so a partial block does not read as real zeros.
    """
    resolvers = metadata.get('resolvers') if isinstance(metadata, dict) else None
    if not isinstance(resolvers, dict):
        return None
    public_share = resolvers.get('public_share_pct')
    public_share = public_share if isinstance(public_share, dict) else {}
    share = resolvers.get('share_pct')
    share = share if isinstance(share, dict) else {}
    summary = {
        'public_share_pct': {p: _as_percent(public_share.get(p)) for p in RESOLVER_PROVIDERS + ('all',)},
        'share_pct': {c: _as_percent(share.get(c)) for c in RESOLVER_CATEGORIES},
        'weighted': resolvers.get('weighted') if isinstance(resolvers.get('weighted'), bool) else None,
    }
    summary.update({k: _as_count(resolvers.get(k)) for k in _RESOLVER_COUNT_FIELDS})
    if summary['exits_covered'] == 0:
        # No exit counted toward the shares (upstream cold start): its 0.0 shares are placeholders
        summary['public_share_pct'] = dict.fromkeys(summary['public_share_pct'])
        summary['share_pct'] = dict.fromkeys(summary['share_pct'])
    values = (list(summary['public_share_pct'].values()) + list(summary['share_pct'].values())
              + [summary[k] for k in _RESOLVER_COUNT_FIELDS])
    return summary if any(v is not None for v in values) else None


def build_exit_dns_health_map(exit_dns_health_data: Optional[Dict]) -> Dict[str, Dict]:
    """
    Build fingerprint -> DNS health result map for O(1) per-relay lookup.
    Preserves full API data per relay for troubleshooting display.
    """
    if not exit_dns_health_data or 'results' not in exit_dns_health_data:
        return {}

    health_map = {}
    for result in exit_dns_health_data.get('results', []):
        if not isinstance(result, dict):
            continue
        fp = result.get('exit_fingerprint')
        if not fp:
            continue
        cv = result.get('cv')
        if not isinstance(cv, dict):
            cv = {}
        health_map[str(fp).upper()] = {
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
            'resolver': _parse_resolver(result.get('resolver')),
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
    # Once any exit in the report has resolver data, exits without it have too few queries yet
    resolver_live = any(e.get('resolver') for e in health_map.values())

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
            relay.update(_make_untested_defaults())
            continue

        status = entry['status']
        is_success = status == 'success'
        fh_info = relay_info_map.get((entry['first_hop'] or '').upper(), ('', ''))
        resolver = entry.get('resolver') or {}

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
            'exit_dns_health_resolver_primary': resolver.get('primary'),
            'exit_dns_health_resolver_public': resolver.get('public'),
            # None: the report has no resolver data; {}: none for this exit yet
            'exit_dns_health_resolver_queries': (
                resolver['queries'] if resolver else ({} if resolver_live else None)),
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
    metrics.update(_resolver_metrics(None))

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

    metrics.update(_resolver_metrics(parse_resolver_summary(metadata)))
    return metrics


def _local_percentage(share: Dict) -> Optional[float]:
    """Version-2 local total, or version-1's local share when no tier is present.

    A version-2 report that includes some tiers and omits others has no total: summing
    the present ones would publish an under-count as if it were complete. Zero is a
    real share; None is a missing one.
    """
    tiers = [share.get(tier) for tier in RESOLVER_TIERS]
    if any(value is not None for value in tiers):
        if any(value is None for value in tiers):
            return None
        return round(sum(tiers), 2)
    return share.get('local')


def _resolver_metrics(summary: Optional[Dict]) -> Dict:
    """Flatten parse_resolver_summary() into dashboard keys. Without a summary every value
    is None and exit_dns_health_resolvers_available is False, so it renders as not available.

    exit_dns_health_resolver_local_percentage stays the single local number: version 1's
    "local", or the sum of the four tiers when a version-2 report includes every tier.
    """
    summary = summary or {}
    public_share = summary.get('public_share_pct', {})
    share = summary.get('share_pct', {})
    metrics = {
        'exit_dns_health_resolvers_available': bool(summary),
        'exit_dns_health_resolver_public_percentage': public_share.get('all'),
        'exit_dns_health_resolver_weighted': summary.get('weighted'),
    }
    metrics.update({f'exit_dns_health_resolver_{p}_percentage': public_share.get(p) for p in RESOLVER_PROVIDERS})
    metrics['exit_dns_health_resolver_local_percentage'] = _local_percentage(share)
    metrics.update({f'exit_dns_health_resolver_{tier}_percentage': share.get(tier) for tier in RESOLVER_TIERS})
    metrics.update({f'exit_dns_health_resolver_{c}_percentage': share.get(c) for c in ('other', 'unknown')})
    metrics.update({f'exit_dns_health_resolver_{k}': summary.get(k) for k in _RESOLVER_COUNT_FIELDS})
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

    return _build_dns_summary_dict(total_exits, healthy, failing, untested)


def _build_dns_summary_dict(total, healthy, failing, untested):
    """Build the standard DNS health summary dict. Single source of truth for dict shape."""
    return {
        'exit_count': total,
        'healthy': healthy,
        'failing': failing,
        'untested': untested,
        'healthy_pct': round(100 * healthy / total) if total > 0 else 0,
        'failing_pct': round(100 * failing / total) if total > 0 else 0,
        'untested_pct': round(100 * untested / total) if total > 0 else 0,
        'all_healthy': failing == 0 and untested == 0 and healthy > 0,
        'any_failing': failing > 0,
    }
