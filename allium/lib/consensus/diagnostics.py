"""
File: diagnostics.py

Format diagnostic data for templates.
Provides display-ready formatting of consensus troubleshooting data.

OPTIMIZATION: Leverages existing utilities from the codebase:
- BandwidthFormatter from bandwidth_formatter.py for bandwidth display
- format_percentage_from_fraction from string_utils.py for WFU percentages
"""

from typing import Dict, List, Optional, Any

# Import authority country codes and shared constants from collector_fetcher
# Centralizes constants to avoid duplication and ensure consistency
try:
    from .collector_fetcher import (
        AUTHORITY_COUNTRIES,
        GUARD_TK_DEFAULT,
        HSDIR_TK_DEFAULT, 
        SECONDS_PER_DAY,
    )
except ImportError:
    AUTHORITY_COUNTRIES = {}
    GUARD_TK_DEFAULT = 691200
    HSDIR_TK_DEFAULT = 864000
    SECONDS_PER_DAY = 86400

# Reuse existing bandwidth formatter instead of duplicating logic
try:
    from ..bandwidth_formatter import BandwidthFormatter
    _bw_formatter = BandwidthFormatter(use_bits=False)
except ImportError:
    _bw_formatter = None

# Reuse existing percentage formatter from string_utils
try:
    from ..string_utils import format_percentage_from_fraction
except ImportError:
    # Fallback if import fails
    def format_percentage_from_fraction(value, decimals=1, fallback='N/A'):
        if value is None:
            return fallback
        try:
            return f"{float(value) * 100:.{decimals}f}%"
        except (ValueError, TypeError):
            return fallback


# ============================================================================
# MODULE-SPECIFIC CONSTANTS - Not shared with collector_fetcher
# ============================================================================
# Bandwidth thresholds (bytes/second)
GUARD_BW_GUARANTEE = 2_000_000   # AuthDirGuardBWGuarantee: 2 MB/s minimum for Guard
FAST_BW_MINIMUM = 100_000       # 100 KB/s minimum for Fast flag

# WFU thresholds (fractions)
DEFAULT_WFU_THRESHOLD = 0.98    # 98% uptime for Guard/HSDir


# ============================================================================
# LOCAL HELPER FUNCTIONS - Reduce code duplication within this module
# ============================================================================
def _format_days(seconds, decimals=1, suffix='d', fallback='N/A'):
    """Format seconds as days. Consolidates repeated SECONDS_PER_DAY division."""
    if seconds is None:
        return fallback
    days = seconds / SECONDS_PER_DAY
    return f"{days:.{decimals}f}{suffix}"


def _format_wfu_display(wfu, decimals=1, fallback='N/A'):
    """Format WFU (weighted fractional uptime) as percentage using existing formatter."""
    if wfu is None:
        return fallback
    return format_percentage_from_fraction(wfu, decimals, fallback)


# Canonical flag ordering for consistent display across all relay pages
# Order: Authority-first, then alphabetical for common flags
FLAG_ORDER = [
    'Authority',  # Special: directory authority
    'BadExit',    # Flagged as misbehaving exit
    'Exit',       # Can be used as exit node
    'Fast',       # Bandwidth in top 7/8ths or ≥100 KB/s
    'Guard',      # Can be used as entry guard
    'HSDir',      # Hidden service directory
    'NoEdConsensus',  # Doesn't support ed25519
    'Running',    # Relay is reachable
    'Stable',     # Sufficient uptime/MTBF
    'StaleDesc',  # Descriptor is old
    'V2Dir',      # Supports directory protocol v2+
    'Valid',      # Verified, allowed in network
]

# Pre-computed map for O(1) flag ordering lookup (instead of O(n) list.index())
FLAG_ORDER_MAP = {flag: idx for idx, flag in enumerate(FLAG_ORDER)}


def _sort_flags(flags: list) -> list:
    """Sort flags in canonical order for consistent display. O(n log n) with O(1) key lookup."""
    if not flags:
        return []
    
    # Use pre-computed map for O(1) lookup instead of FLAG_ORDER.index() which is O(n)
    max_order = len(FLAG_ORDER)
    return sorted(flags, key=lambda f: FLAG_ORDER_MAP.get(f, max_order + ord(f[0].lower()) if f else 999))


def _parse_wfu_threshold(value) -> Optional[float]:
    """Parse WFU threshold value (can be string like '98%' or float like 0.98)."""
    if value is None:
        return None
    if isinstance(value, str):
        return float(value.replace('%', '')) / 100
    return float(value)


def format_relay_diagnostics(diagnostics: dict, flag_thresholds: dict = None, current_flags: list = None, observed_bandwidth: int = 0) -> dict:
    """
    Format relay diagnostics for template display.
    
    Args:
        diagnostics: Raw diagnostics from CollectorFetcher.get_relay_diagnostics()
        flag_thresholds: Optional flag threshold data
        current_flags: List of flags the relay currently has (from Onionoo)
        observed_bandwidth: Relay's observed bandwidth in bytes/s (from Onionoo)
                           This is the ACTUAL bandwidth used for Guard eligibility,
                           NOT the scaled consensus weight or vote Measured value.
        
    Returns:
        dict: Formatted diagnostics ready for template rendering
    """
    if not diagnostics:
        return {
            'available': False,
            'error': 'No diagnostic data available',
            'in_consensus': False,
        }
    if diagnostics.get('error'):
        return {
            'available': False,
            'error': diagnostics.get('error', 'No diagnostic data available'),
            'in_consensus': False,
        }
    
    current_flags = current_flags or []
    
    formatted = {
        'available': True,
        'fingerprint': diagnostics.get('fingerprint', ''),
        'in_consensus': diagnostics.get('in_consensus', False),
        'vote_count': diagnostics.get('vote_count', 0),
        'total_authorities': diagnostics.get('total_authorities', 9),
        'majority_required': diagnostics.get('majority_required', 5),
        
        # Consensus status display
        'consensus_status': _format_consensus_status(diagnostics),
        
        # Relay values summary (for Summary table) - pass observed_bandwidth for Guard BW check
        'relay_values': _format_relay_values(diagnostics, flag_thresholds, observed_bandwidth),
        
        # Per-authority voting details - pass observed_bandwidth for Guard BW and Fast checks
        'authority_table': _format_authority_table_enhanced(diagnostics, flag_thresholds, observed_bandwidth),
        
        # Flag eligibility summary - recalculate using observed_bandwidth
        'flag_summary': _format_flag_summary(diagnostics, observed_bandwidth),
        
        # Reachability summary
        'reachability_summary': _format_reachability_summary(diagnostics),
        
        # Bandwidth summary
        'bandwidth_summary': _format_bandwidth_summary(diagnostics),
        
        # Issues and advice
        'issues': _identify_issues(diagnostics, current_flags, observed_bandwidth),
        'advice': _generate_advice(diagnostics),
    }
    
    return formatted


def _format_relay_values(diagnostics: dict, flag_thresholds: dict = None, observed_bandwidth: int = 0) -> dict:
    """
    Format relay values summary for the Summary table.
    Shows your relay's values vs consensus thresholds.
    
    Args:
        diagnostics: Raw diagnostics
        flag_thresholds: Flag threshold data  
        observed_bandwidth: Relay's actual observed bandwidth in bytes/s (from Onionoo)
                           This is the bandwidth used for Guard eligibility (>= 2MB/s)
    """
    authority_votes = diagnostics.get('authority_votes', [])
    flag_eligibility = diagnostics.get('flag_eligibility', {})
    reachability = diagnostics.get('reachability', {})
    total_authorities = diagnostics.get('total_authorities', 9)
    majority_required = diagnostics.get('majority_required', 5)
    
    # Extract relay's values from first available authority (single pass)
    relay_wfu = relay_tk = relay_bw = None
    for vote in authority_votes:
        if relay_wfu is None and vote.get('wfu') is not None:
            relay_wfu = vote['wfu']
        if relay_tk is None and vote.get('tk') is not None:
            relay_tk = vote['tk']
        if relay_bw is None:
            relay_bw = vote.get('measured') or vote.get('bandwidth')
        # Early exit if all values found
        if relay_wfu is not None and relay_tk is not None and relay_bw is not None:
            break
    
    # For Guard BW eligibility, use observed_bandwidth (from Onionoo descriptor)
    # NOT the vote's measured value (which is scaled for path selection)
    guard_bw_value = observed_bandwidth if observed_bandwidth else (relay_bw or 0)
    
    # Calculate threshold ranges from flag_thresholds (single pass)
    guard_wfu_threshold = DEFAULT_WFU_THRESHOLD
    guard_tk_threshold = GUARD_TK_DEFAULT
    hsdir_wfu_threshold = DEFAULT_WFU_THRESHOLD
    hsdir_tk_threshold = HSDIR_TK_DEFAULT
    
    guard_bw_values = []
    stable_uptime_values = []
    stable_mtbf_values = []
    fast_speed_values = []
    
    if flag_thresholds:
        for thresholds in flag_thresholds.values():
            # Guard thresholds
            if 'guard-wfu' in thresholds:
                val = _parse_wfu_threshold(thresholds['guard-wfu'])
                if val:
                    guard_wfu_threshold = max(guard_wfu_threshold, val)
            if 'guard-tk' in thresholds:
                guard_tk_threshold = max(guard_tk_threshold, thresholds['guard-tk'] or 0)
            if 'guard-bw-inc-exits' in thresholds:
                guard_bw_values.append(thresholds['guard-bw-inc-exits'])
            # Stable thresholds
            if 'stable-uptime' in thresholds:
                stable_uptime_values.append(thresholds['stable-uptime'])
            if 'stable-mtbf' in thresholds:
                stable_mtbf_values.append(thresholds['stable-mtbf'])
            # Fast thresholds
            if 'fast-speed' in thresholds:
                fast_speed_values.append(thresholds['fast-speed'])
            # HSDir thresholds
            if 'hsdir-wfu' in thresholds:
                val = _parse_wfu_threshold(thresholds['hsdir-wfu'])
                if val:
                    hsdir_wfu_threshold = max(hsdir_wfu_threshold, val)
            if 'hsdir-tk' in thresholds:
                hsdir_tk_threshold = max(hsdir_tk_threshold, thresholds['hsdir-tk'] or 0)
    
    # Calculate Guard BW analysis using observed_bandwidth (actual bandwidth, not scaled consensus value)
    guard_bw_range = _format_range(guard_bw_values, _format_bandwidth_value) if guard_bw_values else 'N/A'
    
    # Check if relay's observed bandwidth meets Guard eligibility
    guard_bw_meets_guarantee = guard_bw_value >= GUARD_BW_GUARANTEE
    # Check against each authority's top 25% threshold
    guard_bw_meets_top25_count = sum(1 for bw in guard_bw_values if guard_bw_value >= bw) if guard_bw_values else 0
    # Relay meets Guard BW if it meets the guarantee OR is in top 25% for any authority
    guard_bw_meets = guard_bw_meets_guarantee or guard_bw_meets_top25_count > 0
    guard_bw_meets_all = guard_bw_meets_guarantee or (guard_bw_meets_top25_count == len(guard_bw_values) if guard_bw_values else False)
    guard_bw_meets_some = guard_bw_meets
    guard_bw_meets_count = total_authorities if guard_bw_meets_guarantee else guard_bw_meets_top25_count
    
    # Calculate Stable analysis
    stable_meets_count = flag_eligibility.get('stable', {}).get('eligible_count', 0)
    stable_meets_all = stable_meets_count == total_authorities
    stable_range = _format_range(stable_uptime_values, _format_days) if stable_uptime_values else 'N/A'
    stable_mtbf_range = _format_range(stable_mtbf_values, _format_days) if stable_mtbf_values else 'N/A'
    
    # Calculate Fast analysis using observed_bandwidth
    fast_range = _format_range(fast_speed_values, _format_bandwidth_value) if fast_speed_values else 'N/A'
    
    # Check if observed_bandwidth meets Fast eligibility
    fast_meets_minimum = guard_bw_value >= FAST_BW_MINIMUM
    fast_meets_threshold_count = sum(1 for fs in fast_speed_values if guard_bw_value >= fs) if fast_speed_values else 0
    fast_meets = fast_meets_minimum or fast_meets_threshold_count > 0
    fast_meets_all = fast_meets_minimum or (fast_meets_threshold_count == len(fast_speed_values) if fast_speed_values else False)
    fast_meets_count = total_authorities if fast_meets_minimum else fast_meets_threshold_count
    
    # IPv4/IPv6 reachability
    ipv4_reachable_count = reachability.get('ipv4_reachable_count', 0)
    ipv6_reachable_count = reachability.get('ipv6_reachable_count', 0)
    ipv6_not_tested = reachability.get('ipv6_not_tested_authorities', [])
    ipv6_tested_count = total_authorities - len(ipv6_not_tested)
    
    return {
        # WFU values
        'wfu': relay_wfu,
        'wfu_display': _format_wfu_display(relay_wfu),
        'wfu_meets': relay_wfu and relay_wfu >= guard_wfu_threshold,
        'guard_wfu_threshold': guard_wfu_threshold,
        
        # Time Known values
        'tk': relay_tk,
        'tk_display': _format_days(relay_tk, suffix=' days'),
        'tk_meets': relay_tk and relay_tk >= guard_tk_threshold,
        'guard_tk_threshold': guard_tk_threshold,
        'tk_days_needed': (guard_tk_threshold - (relay_tk or 0)) / SECONDS_PER_DAY if relay_tk and relay_tk < guard_tk_threshold else 0,
        
        # Guard BW values - use observed_bandwidth for eligibility (actual bandwidth, not scaled)
        # Note: relay_bw is the scaled consensus value, guard_bw_value is observed_bandwidth
        'measured_bw': relay_bw,  # Scaled consensus value (for reference)
        'measured_bw_display': _format_bandwidth_value(relay_bw),  # Scaled consensus value
        'observed_bw': guard_bw_value,  # Actual observed bandwidth (for Guard eligibility)
        'observed_bw_display': _format_bandwidth_value(guard_bw_value),  # Actual bandwidth
        'guard_bw_guarantee': GUARD_BW_GUARANTEE,
        'guard_bw_guarantee_display': _format_bandwidth_value(GUARD_BW_GUARANTEE),
        'guard_bw_range': guard_bw_range,
        'guard_bw_meets_guarantee': guard_bw_meets_guarantee,
        'guard_bw_meets_all': guard_bw_meets_all,
        'guard_bw_meets_some': guard_bw_meets_some,
        'guard_bw_meets_count': guard_bw_meets_count,
        
        # Stable values
        'stable_range': stable_range,
        'stable_meets_all': stable_meets_all,
        'stable_meets_count': stable_meets_count,
        'stable_mtbf_range': stable_mtbf_range,
        'stable_mtbf_meets_all': stable_meets_all,  # Same count for simplicity
        'stable_mtbf_meets_count': stable_meets_count,
        'mtbf_display': _format_days(relay_tk, decimals=0, suffix=' days'),
        
        # Fast values - use observed_bandwidth like Guard
        'fast_speed': guard_bw_value,  # Use observed_bandwidth
        'fast_speed_display': _format_bandwidth_value(guard_bw_value),
        'fast_minimum': FAST_BW_MINIMUM,
        'fast_minimum_display': _format_bandwidth_value(FAST_BW_MINIMUM),
        'fast_range': fast_range,
        'fast_meets_minimum': fast_meets_minimum,
        'fast_meets_all': fast_meets_all,
        'fast_meets_count': fast_meets_count,
        
        # HSDir values
        'hsdir_wfu_threshold': hsdir_wfu_threshold,
        'hsdir_tk_threshold': hsdir_tk_threshold,
        'hsdir_wfu_meets': relay_wfu and relay_wfu >= hsdir_wfu_threshold,
        'hsdir_tk_meets': relay_tk and relay_tk >= hsdir_tk_threshold,
        'hsdir_tk_days_needed': (hsdir_tk_threshold - (relay_tk or 0)) / SECONDS_PER_DAY if relay_tk and relay_tk < hsdir_tk_threshold else 0,
        
        # Reachability values
        'ipv4_reachable_count': ipv4_reachable_count,
        'ipv6_reachable_count': ipv6_reachable_count,
        'ipv6_tested_count': ipv6_tested_count,
        'total_authorities': total_authorities,
        'majority_required': majority_required,
    }


def _format_range(values: list, formatter) -> str:
    """Format a range of values."""
    if not values:
        return 'N/A'
    values = [v for v in values if v is not None and v > 0]
    if not values:
        return 'N/A'
    min_val = min(values)
    max_val = max(values)
    if min_val == max_val:
        return formatter(min_val)
    return f"{formatter(min_val)}-{formatter(max_val)}"


def _format_authority_table_enhanced(diagnostics: dict, flag_thresholds: dict = None, observed_bandwidth: int = 0) -> List[dict]:
    """
    Format authority votes into table rows with threshold comparison.
    
    Args:
        diagnostics: Raw diagnostics dict
        flag_thresholds: Dict of per-authority flag thresholds
        observed_bandwidth: Relay's actual observed bandwidth (for Guard BW and Fast eligibility)
    """
    authority_votes = diagnostics.get('authority_votes', [])
    
    # Compute flag consensus using shared function (avoid duplicate logic)
    consensus = compute_flag_consensus(authority_votes)
    unanimous_flags = consensus['unanimous_flags']
    partial_flags = consensus['partial_flags']
    
    rows = []
    for vote in authority_votes:
        auth_name = vote.get('authority', 'Unknown')
        thresholds = flag_thresholds.get(auth_name, {}) if flag_thresholds else {}
        
        # Get threshold values for this authority using helper function
        guard_wfu_threshold = _parse_wfu_threshold(thresholds.get('guard-wfu')) or DEFAULT_WFU_THRESHOLD
        guard_tk_threshold = thresholds.get('guard-tk', GUARD_TK_DEFAULT)
        guard_bw_top25_threshold = thresholds.get('guard-bw-inc-exits', 0)  # Top 25% cutoff
        stable_threshold = thresholds.get('stable-uptime', 0)
        stable_mtbf_threshold = thresholds.get('stable-mtbf', 0)
        fast_threshold = thresholds.get('fast-speed', 0)
        hsdir_tk_threshold = thresholds.get('hsdir-tk', HSDIR_TK_DEFAULT)
        hsdir_wfu_threshold = _parse_wfu_threshold(thresholds.get('hsdir-wfu')) or DEFAULT_WFU_THRESHOLD
        
        # Relay's measured values from this authority
        relay_wfu = vote.get('wfu')
        relay_tk = vote.get('tk')
        relay_bw = vote.get('measured') or vote.get('bandwidth')
        relay_mtbf = vote.get('mtbf')
        
        # Format flags with consensus highlighting info, in canonical order
        authority_flags = _sort_flags(vote.get('flags', []))
        flags_with_consensus = []
        for flag in authority_flags:
            flags_with_consensus.append({
                'name': flag,
                'unanimous': flag in unanimous_flags,
                'partial': flag in partial_flags,
            })
        
        # Get country code for this authority
        country_code = AUTHORITY_COUNTRIES.get(auth_name.lower(), '')
        authority_display = f"{auth_name} ({country_code})" if country_code else auth_name
        
        row = {
            'authority': auth_name,
            'authority_display': authority_display,
            'country_code': country_code,
            'fingerprint': vote.get('fingerprint', ''),
            'voted': vote.get('voted', False),
            'voted_display': 'Yes' if vote.get('voted') else 'No',
            'voted_class': 'success' if vote.get('voted') else 'danger',
            
            # Flags with consensus info
            'flags': authority_flags,
            'flags_with_consensus': flags_with_consensus,
            'flags_display': ', '.join(authority_flags) or 'None',
            
            # BW authority indicator
            'is_bw_authority': vote.get('is_bw_authority', False),
            
            # Measured BW value and display
            'measured': relay_bw,
            'measured_display': _format_bandwidth_value(relay_bw),
            
            # WFU: measured value | threshold
            'wfu': relay_wfu,
            'wfu_display': _format_wfu_display(relay_wfu),
            'wfu_threshold_display': _format_wfu_display(guard_wfu_threshold, decimals=0),
            'wfu_meets': relay_wfu and relay_wfu >= guard_wfu_threshold,
            'guard_wfu_threshold': guard_wfu_threshold,
            
            # TK: measured value | threshold
            'tk': relay_tk,
            'tk_display': _format_days(relay_tk),
            'tk_threshold_display': _format_days(guard_tk_threshold, decimals=0),
            'tk_meets': relay_tk and relay_tk >= guard_tk_threshold,
            'guard_tk_threshold': guard_tk_threshold,
            
            # Guard BW: uses observed_bandwidth (from descriptor), NOT scaled consensus value
            # Per Tor dir-spec: "bandwidth >= AuthDirGuardBWGuarantee (2 MB) OR in top 25%"
            'guard_bw_guarantee': GUARD_BW_GUARANTEE,
            'guard_bw_top25_threshold': guard_bw_top25_threshold,
            'guard_bw_value': observed_bandwidth,
            'guard_bw_value_display': _format_bandwidth_value(observed_bandwidth),
            'guard_bw_guarantee_display': _format_bandwidth_value(GUARD_BW_GUARANTEE),
            'guard_bw_top25_display': _format_bandwidth_value(guard_bw_top25_threshold),
            'guard_bw_meets_guarantee': observed_bandwidth >= GUARD_BW_GUARANTEE,
            'guard_bw_in_top25': observed_bandwidth >= guard_bw_top25_threshold if guard_bw_top25_threshold else False,
            'guard_bw_meets': observed_bandwidth >= GUARD_BW_GUARANTEE or (guard_bw_top25_threshold and observed_bandwidth >= guard_bw_top25_threshold),
            
            # Stable: measured MTBF | threshold  
            'stable_mtbf': relay_mtbf,
            'stable_mtbf_display': _format_days(relay_mtbf),
            'stable_threshold': stable_mtbf_threshold,
            'stable_threshold_display': _format_days(stable_mtbf_threshold),
            'stable_meets': relay_mtbf and relay_mtbf >= stable_mtbf_threshold if stable_mtbf_threshold else True,
            
            # Fast: uses observed_bandwidth (from descriptor), NOT scaled consensus value
            # Fast requires: bandwidth in top 7/8ths (fast_threshold) OR >= 100 KB/s
            'fast_speed': observed_bandwidth,
            'fast_speed_display': _format_bandwidth_value(observed_bandwidth),
            'fast_threshold': fast_threshold,
            'fast_threshold_display': _format_bandwidth_value(fast_threshold),
            'fast_meets': observed_bandwidth >= fast_threshold if fast_threshold else (observed_bandwidth >= FAST_BW_MINIMUM),
            
            # HSDir TK: measured | threshold
            'hsdir_tk_threshold': hsdir_tk_threshold,
            'hsdir_tk_value_display': _format_days(relay_tk),
            'hsdir_tk_threshold_display': _format_days(hsdir_tk_threshold),
            'hsdir_tk_meets': relay_tk and relay_tk >= hsdir_tk_threshold,
            'hsdir_wfu_threshold': hsdir_wfu_threshold,
            
            # Reachability
            'ipv4_reachable': vote.get('ipv4_reachable', False),
            'ipv4_display': 'Yes' if vote.get('ipv4_reachable') else 'No',
            'ipv4_class': 'success' if vote.get('ipv4_reachable') else 'danger',
            
            'ipv6_reachable': vote.get('ipv6_reachable'),
            'ipv6_display': _format_ipv6_status(vote.get('ipv6_reachable'), vote.get('ipv6_address')),
            'ipv6_class': _get_ipv6_class(vote.get('ipv6_reachable')),
            
            # Descriptor freshness (StaleDesc flag detection)
            'descriptor_published': vote.get('descriptor_published', 'N/A'),
            'has_staledesc': 'StaleDesc' in authority_flags,
        }
        rows.append(row)
    
    return rows


def compute_flag_consensus(authority_votes: List[dict]) -> dict:
    """
    Compute flag consensus across all authorities.
    
    Returns dict with:
        - unanimous_flags: set of flags all voting authorities agree on
        - partial_flags: set of flags only some authorities assign
        - flag_counts: dict of flag_name -> count of authorities
    """
    flag_counts = {}
    for vote in authority_votes:
        if vote.get('voted'):
            for flag in vote.get('flags', []):
                flag_counts[flag] = flag_counts.get(flag, 0) + 1
    
    total_voting = sum(1 for v in authority_votes if v.get('voted'))
    
    unanimous_flags = {f for f, c in flag_counts.items() if c == total_voting}
    partial_flags = {f for f, c in flag_counts.items() if 0 < c < total_voting}
    
    return {
        'unanimous_flags': unanimous_flags,
        'partial_flags': partial_flags,
        'flag_counts': flag_counts,
        'total_voting': total_voting,
    }


def format_authority_diagnostics(
    authority_status: Dict[str, dict],
    flag_thresholds: Dict[str, dict],
    bw_authorities: List[str]
) -> dict:
    """
    Format authority diagnostics for misc-authorities.html dashboard.
    
    Args:
        authority_status: Health status from AuthorityMonitor
        flag_thresholds: Flag thresholds from CollectorFetcher
        bw_authorities: List of authorities running bandwidth scanners
        
    Returns:
        dict: Formatted authority data for template
    """
    formatted = {
        'authorities': [],
        'thresholds_table': _format_thresholds_table(flag_thresholds),
        'summary': {
            'total': len(authority_status),
            'online': sum(1 for s in authority_status.values() if s.get('online')),
            'bw_authorities': len(bw_authorities),
        },
    }
    
    for name, status in sorted(authority_status.items()):
        auth_data = {
            'name': name,
            'online': status.get('online', False),
            'latency_ms': status.get('latency_ms'),
            'latency_class': _get_latency_class(status.get('latency_ms')),
            'error': status.get('error'),
            'is_bw_authority': name in bw_authorities,
            'thresholds': flag_thresholds.get(name, {}),
        }
        formatted['authorities'].append(auth_data)
    
    return formatted


def _format_consensus_status(diagnostics: dict) -> dict:
    """Format consensus status display."""
    in_consensus = diagnostics.get('in_consensus', False)
    vote_count = diagnostics.get('vote_count', 0)
    total = diagnostics.get('total_authorities', 9)
    majority = diagnostics.get('majority_required', 5)
    
    if in_consensus:
        return {
            'status': 'IN CONSENSUS',
            'status_class': 'success',
            'display': f"IN CONSENSUS ({vote_count}/{total} authorities)",
            'tooltip': f"Relay is in consensus. {vote_count} out of {total} authorities voted for this relay (requires {majority}).",
        }
    else:
        return {
            'status': 'NOT IN CONSENSUS',
            'status_class': 'danger',
            'display': f"NOT IN CONSENSUS ({vote_count}/{total} authorities)",
            'tooltip': f"Relay is NOT in consensus. Only {vote_count} out of {total} authorities voted for this relay (requires {majority}).",
        }


def _format_flag_summary(diagnostics: dict, observed_bandwidth: int = 0) -> dict:
    """
    Format flag eligibility summary.
    
    Args:
        diagnostics: Raw diagnostics
        observed_bandwidth: Relay's actual observed bandwidth (for Guard BW eligibility)
    """
    flag_eligibility = diagnostics.get('flag_eligibility', {})
    total_authorities = diagnostics.get('total_authorities', 9)
    
    # Guard and Fast both use observed_bandwidth, not the scaled vote values
    bw_value = observed_bandwidth if observed_bandwidth else 0
    guard_bw_eligible = bw_value >= GUARD_BW_GUARANTEE
    fast_bw_eligible = bw_value >= FAST_BW_MINIMUM
    
    summary = {}
    
    for flag_name in ['guard', 'stable', 'fast', 'hsdir']:
        flag_data = flag_eligibility.get(flag_name, {})
        eligible_count = flag_data.get('eligible_count', 0)
        
        # For Guard flag, recalculate based on observed_bandwidth
        if flag_name == 'guard' and guard_bw_eligible:
            # If BW meets 2MB guarantee, check other requirements (WFU, TK)
            # Count how many authorities the relay meets WFU+TK requirements
            eligible_count = sum(
                1 for detail in flag_data.get('details', [])
                if detail.get('wfu_met') and detail.get('tk_met')
            )
        
        # For Fast flag, recalculate based on observed_bandwidth
        # Fast requires: bandwidth in top 7/8ths OR >= 100 KB/s
        if flag_name == 'fast' and fast_bw_eligible:
            # If BW meets 100 KB/s minimum, relay is Fast eligible from all authorities
            eligible_count = total_authorities
        
        if eligible_count == 0:
            status = 'none'
            status_class = 'danger'
            display = f"Not eligible from any authority"
        elif eligible_count < 5:
            status = 'partial'
            status_class = 'warning'
            display = f"Eligible from {eligible_count}/{total_authorities} authorities"
        else:
            status = 'full'
            status_class = 'success'
            display = f"Eligible from {eligible_count}/{total_authorities} authorities"
        
        summary[flag_name] = {
            'eligible_count': eligible_count,
            'total_authorities': total_authorities,
            'status': status,
            'status_class': status_class,
            'display': display,
            'details': flag_data.get('details', []),
        }
    
    return summary


def _format_reachability_summary(diagnostics: dict) -> dict:
    """Format reachability summary."""
    reachability = diagnostics.get('reachability', {})
    
    ipv4_count = reachability.get('ipv4_reachable_count', 0)
    ipv6_count = reachability.get('ipv6_reachable_count', 0)
    total = reachability.get('total_authorities', 9)
    ipv6_not_tested = reachability.get('ipv6_not_tested_authorities', [])
    ipv6_tested_total = total - len(ipv6_not_tested)  # Only count authorities that test IPv6
    
    return {
        'ipv4': {
            'reachable_count': ipv4_count,
            'total': total,
            'display': f"{ipv4_count}/{total} authorities can reach IPv4",
            'status_class': 'success' if ipv4_count >= 5 else 'danger',
            'authorities': reachability.get('ipv4_reachable_authorities', []),
        },
        'ipv6': {
            'reachable_count': ipv6_count,
            'total': ipv6_tested_total,  # Only those who test
            'display': f"{ipv6_count}/{ipv6_tested_total} authorities can reach IPv6",
            'status_class': 'success' if ipv6_count > 0 else 'muted',
            'authorities': reachability.get('ipv6_reachable_authorities', []),
            'not_tested': ipv6_not_tested,
        },
    }


def _format_bandwidth_summary(diagnostics: dict) -> dict:
    """Format bandwidth summary."""
    bandwidth = diagnostics.get('bandwidth', {})
    
    median = bandwidth.get('median')  # Tor consensus uses median
    avg = bandwidth.get('average')
    min_bw = bandwidth.get('min')
    max_bw = bandwidth.get('max')
    deviation = bandwidth.get('deviation')
    
    return {
        'median': median,
        'median_display': _format_bandwidth_value(median),
        'average': avg,
        'average_display': _format_bandwidth_value(avg),
        'min': min_bw,
        'min_display': _format_bandwidth_value(min_bw),
        'max': max_bw,
        'max_display': _format_bandwidth_value(max_bw),
        'deviation': deviation,
        'deviation_display': _format_bandwidth_value(deviation),
        'measurement_count': bandwidth.get('measurement_count', 0),
        'deviation_class': 'warning' if deviation and median and deviation > median * 0.5 else 'normal',
    }


def _identify_issues(diagnostics: dict, current_flags: list = None, observed_bandwidth: int = 0) -> List[dict]:
    """
    Identify issues that may affect relay status.
    
    Args:
        diagnostics: Raw diagnostics
        current_flags: Relay's current flags (from Onionoo)
        observed_bandwidth: Relay's observed bandwidth for Guard eligibility
    """
    issues = []
    current_flags = current_flags or []
    
    # Check consensus status
    if not diagnostics.get('in_consensus'):
        vote_count = diagnostics.get('vote_count', 0)
        total = diagnostics.get('total_authorities', 9)
        issues.append({
            'severity': 'error',
            'category': 'consensus',
            'title': 'Not in consensus',
            'description': f"Only {vote_count}/{total} authorities voted for this relay",
            'suggestion': 'Check reachability from all authority locations',
        })
    
    # Check reachability
    reachability = diagnostics.get('reachability', {})
    ipv4_count = reachability.get('ipv4_reachable_count', 0)
    if ipv4_count < 5:
        unreachable = [
            name for name in ['moria1', 'tor26', 'dizum', 'gabelmoo', 'bastet', 
                             'dannenberg', 'maatuska', 'longclaw', 'faravahar']
            if name not in reachability.get('ipv4_reachable_authorities', [])
        ]
        issues.append({
            'severity': 'error',
            'category': 'reachability',
            'title': 'IPv4 reachability issues',
            'description': f"Only {ipv4_count}/9 authorities can reach this relay",
            'suggestion': f"Check firewall rules for: {', '.join(unreachable)}",
        })
    
    # Check Guard flag eligibility using observed_bandwidth
    # Guard BW requires >= 2MB/s (AuthDirGuardBWGuarantee) OR in top 25%
    has_guard = 'Guard' in current_flags
    guard_bw_eligible = observed_bandwidth >= GUARD_BW_GUARANTEE if observed_bandwidth else False
    
    # If relay doesn't have Guard and doesn't meet BW requirement, show warning
    if not has_guard and not guard_bw_eligible:
        bw_display = f"{observed_bandwidth / 1_000_000:.1f} MB/s" if observed_bandwidth else "unknown"
        issues.append({
            'severity': 'warning',
            'category': 'flags',
            'title': 'Not eligible for Guard flag',
            'description': f"Bandwidth {bw_display} is below 2 MB/s minimum for Guard",
            'suggestion': 'Need: BW ≥2 MB/s, WFU ≥98%, TK ≥8 days, and Fast+Stable flags',
        })
    
    return issues


def _generate_advice(diagnostics: dict) -> List[str]:
    """Generate actionable advice based on diagnostics."""
    advice = []
    
    issues = _identify_issues(diagnostics)
    
    for issue in issues:
        if issue.get('suggestion'):
            advice.append(issue['suggestion'])
    
    # General advice based on metrics
    authority_votes = diagnostics.get('authority_votes', [])
    for vote in authority_votes:
        wfu = vote.get('wfu')
        if wfu and wfu < 0.98:
            advice.append(f"Increase WFU to ≥98% for Guard/HSDir eligibility (current: {wfu*100:.1f}%)")
            break
    
    return list(set(advice))  # Remove duplicates


def _format_thresholds_table(flag_thresholds: Dict[str, dict]) -> dict:
    """Format flag thresholds into comparison table."""
    if not flag_thresholds:
        return {'available': False}
    
    # Collect all threshold keys
    all_keys = set()
    for thresholds in flag_thresholds.values():
        all_keys.update(thresholds.keys())
    
    # Sort keys for consistent display
    sorted_keys = sorted(all_keys)
    
    # Build table rows
    rows = []
    for key in sorted_keys:
        row = {
            'threshold_name': key,
            'display_name': _format_threshold_name(key),
            'values': {},
        }
        for auth_name, thresholds in sorted(flag_thresholds.items()):
            value = thresholds.get(key)
            row['values'][auth_name] = {
                'raw': value,
                'display': _format_threshold_value(key, value),
            }
        rows.append(row)
    
    return {
        'available': True,
        'authorities': sorted(flag_thresholds.keys()),
        'rows': rows,
    }


def _format_threshold_name(key: str) -> str:
    """Format threshold key for display."""
    display_names = {
        'stable-uptime': 'Stable Uptime',
        'stable-mtbf': 'Stable MTBF',
        'fast-speed': 'Fast Speed',
        'guard-wfu': 'Guard WFU',
        'guard-tk': 'Guard Time Known',
        'guard-bw-inc-exits': 'Guard BW (inc. exits)',
        'guard-bw-exc-exits': 'Guard BW (exc. exits)',
        'hsdir-wfu': 'HSDir WFU',
        'hsdir-tk': 'HSDir Time Known',
        'enough-mtbf': 'Enough MTBF',
    }
    return display_names.get(key, key.replace('-', ' ').title())


def _format_threshold_value(key: str, value: Any) -> str:
    """Format threshold value for display. Uses shared helper functions."""
    if value is None:
        return 'N/A'
    
    # Format time values (in seconds) using _format_days helper
    if 'uptime' in key or 'tk' in key or 'mtbf' in key:
        days = value / SECONDS_PER_DAY
        if days >= 1:
            return _format_days(value, suffix=' days')
        hours = value / 3600
        return f"{hours:.1f} hours"
    
    # Format WFU (fraction to percentage) using shared formatter
    if 'wfu' in key:
        if isinstance(value, float) and value <= 1:
            return _format_wfu_display(value)
        return f"{value}%"
    
    # Format bandwidth values using shared formatter
    if 'bw' in key or 'speed' in key:
        return _format_bandwidth_value(value)
    
    return str(value)


def _format_bandwidth_value(value: Any) -> str:
    """
    Format bandwidth value for display.
    Leverages existing BandwidthFormatter for KB/s and above.
    Handles sub-KB values directly (BandwidthFormatter doesn't support B/s).
    """
    if value is None:
        return 'N/A'
    
    # Handle sub-KB values directly (BandwidthFormatter starts at KB/s)
    if value < 1000:
        return f"{value} B/s"
    
    # Use existing BandwidthFormatter for KB/s and above (avoids code duplication)
    if _bw_formatter is not None:
        try:
            return _bw_formatter.format_bandwidth_with_suffix(value, decimal_places=1)
        except (ValueError, TypeError):
            pass
    
    # Manual fallback if BandwidthFormatter not available
    if value >= 1000000000:
        return f"{value / 1000000000:.1f} GB/s"
    elif value >= 1000000:
        return f"{value / 1000000:.1f} MB/s"
    else:
        return f"{value / 1000:.1f} KB/s"


def _format_ipv6_status(reachable: Optional[bool], address: Optional[str]) -> str:
    """Format IPv6 reachability status."""
    if reachable is True:
        return f"Yes ({address})" if address else "Yes"
    elif reachable is False:
        return "No"
    else:
        return "Not tested"


def _get_wfu_class(wfu: Optional[float]) -> str:
    """Get CSS class for WFU value."""
    if wfu is None:
        return 'muted'
    if wfu >= 0.98:
        return 'success'
    elif wfu >= 0.95:
        return 'warning'
    else:
        return 'danger'


def _get_tk_class(tk: Optional[int]) -> str:
    """Get CSS class for Time Known value."""
    if tk is None:
        return 'muted'
    days = tk / SECONDS_PER_DAY
    if days >= 8:  # 8 days = Guard TK requirement
        return 'success'
    elif days >= 4:
        return 'warning'
    else:
        return 'danger'


def _get_ipv6_class(reachable: Optional[bool]) -> str:
    """Get CSS class for IPv6 status."""
    if reachable is True:
        return 'success'
    elif reachable is False:
        return 'danger'
    else:
        return 'muted'


def _get_latency_class(latency_ms: Optional[float]) -> str:
    """Get CSS class for latency value."""
    if latency_ms is None:
        return 'muted'
    if latency_ms < 200:
        return 'success'
    elif latency_ms < 500:
        return 'warning'
    else:
        return 'danger'
