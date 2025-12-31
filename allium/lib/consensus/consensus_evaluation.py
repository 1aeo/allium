"""
File: consensus_evaluation.py

Format consensus evaluation data for templates.
Provides display-ready formatting of directory authority consensus evaluation data.

OPTIMIZATION: Leverages existing utilities from the codebase:
- BandwidthFormatter from bandwidth_formatter.py for bandwidth display
- format_percentage_from_fraction from string_utils.py for WFU percentages
"""

from typing import Dict, List, Optional, Any

# Import flag thresholds from centralized module (DRY - single source of truth)
try:
    from .flag_thresholds import (
        SECONDS_PER_DAY,
        GUARD_TK_DEFAULT,
        GUARD_WFU_DEFAULT,
        GUARD_BW_GUARANTEE,
        HSDIR_TK_DEFAULT,
        HSDIR_WFU_DEFAULT,
        FAST_BW_GUARANTEE,
        parse_wfu_threshold as _parse_wfu_threshold_impl,
        format_time_as_days,
        format_wfu_as_percent,
        sort_flags as _sort_flags_impl,
        FLAG_ORDER_MAP,
    )
except ImportError:
    # Fallback values if import fails
    SECONDS_PER_DAY = 86400
    GUARD_TK_DEFAULT = 691200
    GUARD_WFU_DEFAULT = 0.98
    GUARD_BW_GUARANTEE = 2_000_000
    HSDIR_TK_DEFAULT = 864000
    HSDIR_WFU_DEFAULT = 0.98
    FAST_BW_GUARANTEE = 100_000
    _parse_wfu_threshold_impl = None
    format_time_as_days = None
    format_wfu_as_percent = None
    _sort_flags_impl = None
    FLAG_ORDER_MAP = {}

# Import authority data from collector_fetcher
try:
    from .collector_fetcher import (
        AUTHORITY_COUNTRIES,
        get_authority_names,           # All authorities (10) - for display
        get_authority_count,           # All authorities count (10)
        get_voting_authority_names,    # Voting authorities (9) - for consensus
        get_voting_authority_count,    # Voting authorities count (9)
    )
except ImportError:
    AUTHORITY_COUNTRIES = {}
    def get_authority_names():
        return ['bastet', 'dannenberg', 'dizum', 'faravahar', 'gabelmoo', 
                'longclaw', 'maatuska', 'moria1', 'Serge', 'tor26']
    def get_authority_count():
        return 10
    def get_voting_authority_names():
        return ['bastet', 'dannenberg', 'dizum', 'faravahar', 'gabelmoo', 
                'longclaw', 'maatuska', 'moria1', 'tor26']
    def get_voting_authority_count():
        return 9

# Note: For consensus-related calculations (majority, reachability), use get_voting_authority_count() (9).
# For display of all authorities, use get_authority_count() (10).
# Serge has Authority flag but doesn't vote.

# Reuse existing bandwidth formatter instead of duplicating logic
try:
    from ..bandwidth_formatter import BandwidthFormatter
    _BandwidthFormatterClass = BandwidthFormatter
except ImportError:
    _BandwidthFormatterClass = None

# Cache formatters to avoid recreating them repeatedly
_bw_formatter_cache = {}

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
# BACKWARD COMPATIBILITY ALIASES - Constants now imported from flag_thresholds.py
# ============================================================================
# These are aliases for the imported constants to maintain backward compatibility
FAST_BW_MINIMUM = FAST_BW_GUARANTEE  # 100 KB/s minimum for Fast flag
DEFAULT_WFU_THRESHOLD = GUARD_WFU_DEFAULT  # 98% uptime for Guard/HSDir


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
    # Use centralized implementation from flag_thresholds if available
    if _parse_wfu_threshold_impl is not None:
        return _parse_wfu_threshold_impl(value)
    # Fallback implementation
    if value is None:
        return None
    if isinstance(value, str):
        return float(value.replace('%', '')) / 100
    return float(value)


def format_relay_consensus_evaluation(evaluation: dict, flag_thresholds: dict = None, current_flags: list = None, observed_bandwidth: int = 0, use_bits: bool = False, relay_uptime: float = None, version: str = None, recommended_version: bool = None) -> dict:
    """
    Format relay consensus evaluation for template display.
    
    Args:
        evaluation: Raw evaluation from CollectorFetcher.get_relay_consensus_evaluation()
        flag_thresholds: Optional flag threshold data
        current_flags: List of flags the relay currently has (from Onionoo)
        observed_bandwidth: Relay's observed bandwidth in bytes/s (from Onionoo)
                           This is the ACTUAL bandwidth used for Guard eligibility,
                           NOT the scaled consensus weight or vote Measured value.
        use_bits: If True, format bandwidth in bits (Mbit/s), otherwise bytes (MB/s).
                  Should match the allium runtime --bits flag.
        relay_uptime: Relay's current uptime in seconds (from Onionoo last_restarted).
                      This is the relay's self-reported uptime, same for all authorities.
                      Used for Stable flag comparison against each authority's stable-uptime threshold.
        version: Tor version string running on the relay (from Onionoo).
        recommended_version: Whether the version is recommended (from Onionoo).
        
    Returns:
        dict: Formatted evaluation ready for template rendering
    """
    if not evaluation:
        return {
            'available': False,
            'error': 'No evaluation data available',
            'in_consensus': False,
        }
    if evaluation.get('error'):
        return {
            'available': False,
            'error': evaluation.get('error', 'No evaluation data available'),
            'in_consensus': False,
        }
    
    current_flags = current_flags or []
    
    formatted = {
        'available': True,
        'fingerprint': evaluation.get('fingerprint', ''),
        'in_consensus': evaluation.get('in_consensus', False),
        'vote_count': evaluation.get('vote_count', 0),
        'total_authorities': evaluation.get('total_authorities', get_voting_authority_count()),
        'majority_required': evaluation.get('majority_required', 5),
        
        # Consensus status display
        'consensus_status': _format_consensus_status(evaluation),
        
        # Relay values summary (for Summary table) - pass observed_bandwidth, use_bits, relay_uptime
        'relay_values': _format_relay_values(evaluation, flag_thresholds, observed_bandwidth, use_bits, relay_uptime),
        
        # Per-authority voting details - pass observed_bandwidth, use_bits, relay_uptime
        'authority_table': _format_authority_table_enhanced(evaluation, flag_thresholds, observed_bandwidth, use_bits, relay_uptime),
        
        # Flag eligibility summary - recalculate using observed_bandwidth
        'flag_summary': _format_flag_summary(evaluation, observed_bandwidth),
        
        # Reachability summary
        'reachability_summary': _format_reachability_summary(evaluation),
        
        # Bandwidth summary - pass use_bits
        'bandwidth_summary': _format_bandwidth_summary(evaluation, use_bits),
        
        # Issues and advice
        'issues': _identify_issues(evaluation, current_flags, observed_bandwidth, version, recommended_version),
        'advice': _generate_advice(evaluation),
    }
    
    return formatted


def _format_relay_values(consensus_data: dict, flag_thresholds: dict = None, observed_bandwidth: int = 0, use_bits: bool = False, relay_uptime: float = None) -> dict:
    """
    Format relay values summary for the Summary table.
    Shows your relay's values vs consensus thresholds.
    
    Args:
        consensus_data: Raw consensus evaluation data
        flag_thresholds: Flag threshold data  
        observed_bandwidth: Relay's actual observed bandwidth in bytes/s (from Onionoo)
                           This is the bandwidth used for Guard eligibility (>= 2MB/s)
        use_bits: If True, format bandwidth in bits (Mbit/s), otherwise bytes (MB/s)
        relay_uptime: Relay's current uptime in seconds (from Onionoo last_restarted).
                      Used for Stable uptime comparison.
    """
    authority_votes = consensus_data.get('authority_votes', [])
    flag_eligibility = consensus_data.get('flag_eligibility', {})
    reachability = consensus_data.get('reachability', {})
    total_authorities = consensus_data.get('total_authorities', get_voting_authority_count())
    majority_required = consensus_data.get('majority_required', 5)
    
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
    # Track both actual values set AND defaults for authorities that don't set values
    guard_wfu_threshold = DEFAULT_WFU_THRESHOLD
    guard_tk_threshold = GUARD_TK_DEFAULT
    hsdir_wfu_threshold = DEFAULT_WFU_THRESHOLD
    hsdir_tk_threshold = HSDIR_TK_DEFAULT
    
    guard_bw_values = []
    stable_uptime_values = []
    stable_mtbf_values = []
    fast_speed_values = []
    
    # Track per-threshold statistics for showing min/max and authority counts
    # This helps distinguish dir-spec defaults from actual authority values
    hsdir_tk_values = []  # (auth_name, value) tuples for authorities that SET this
    hsdir_tk_default_count = 0  # Count of authorities using dir-spec default
    fast_speed_by_auth = {}  # auth_name -> value
    stable_mtbf_by_auth = {}  # auth_name -> value for MTBF outlier detection
    stable_uptime_by_auth = {}  # auth_name -> value for uptime threshold tracking
    
    if flag_thresholds:
        for auth_name, thresholds in flag_thresholds.items():
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
                stable_uptime_by_auth[auth_name] = thresholds['stable-uptime']
            if 'stable-mtbf' in thresholds:
                stable_mtbf_values.append(thresholds['stable-mtbf'])
                stable_mtbf_by_auth[auth_name] = thresholds['stable-mtbf']
            # Fast thresholds - track per authority
            if 'fast-speed' in thresholds:
                fast_speed_values.append(thresholds['fast-speed'])
                fast_speed_by_auth[auth_name] = thresholds['fast-speed']
            # HSDir thresholds - track which authorities set vs use default
            if 'hsdir-wfu' in thresholds:
                val = _parse_wfu_threshold(thresholds['hsdir-wfu'])
                if val:
                    hsdir_wfu_threshold = max(hsdir_wfu_threshold, val)
            if 'hsdir-tk' in thresholds and thresholds['hsdir-tk']:
                hsdir_tk_values.append((auth_name, thresholds['hsdir-tk']))
                hsdir_tk_threshold = max(hsdir_tk_threshold, thresholds['hsdir-tk'])
            else:
                hsdir_tk_default_count += 1
    
    # Calculate HSDir TK statistics for display
    # dir-spec default: 25 hours (HSDIR_TK_DEFAULT)
    # Consensus needs majority (5/9), so if 8 authorities use 25h and 1 uses 10d,
    # relay only needs 25h to get HSDir from majority
    hsdir_tk_min = HSDIR_TK_DEFAULT  # dir-spec default (25 hours)
    hsdir_tk_max = hsdir_tk_threshold  # strictest (currently moria1's ~10 days)
    hsdir_tk_consensus = HSDIR_TK_DEFAULT  # what majority requires (dir-spec default)
    hsdir_tk_strict_auths = [name for name, val in hsdir_tk_values if val > HSDIR_TK_DEFAULT * 2]  # significantly stricter
    
    # Calculate Fast speed statistics
    # Most authorities use ~102 KB/s, moria1 uses ~1 MB/s
    fast_speed_min = min(fast_speed_values) if fast_speed_values else FAST_BW_GUARANTEE
    fast_speed_max = max(fast_speed_values) if fast_speed_values else FAST_BW_GUARANTEE
    fast_speed_typical = sorted(fast_speed_values)[len(fast_speed_values)//2] if fast_speed_values else FAST_BW_GUARANTEE
    fast_speed_strict_auths = [name for name, val in fast_speed_by_auth.items() if val > fast_speed_typical * 2]
    
    # Calculate Stable MTBF statistics for outlier detection
    # Most authorities have similar thresholds, but moria1 may differ significantly
    stable_mtbf_min = min(stable_mtbf_values) if stable_mtbf_values else 0
    stable_mtbf_max = max(stable_mtbf_values) if stable_mtbf_values else 0
    stable_mtbf_typical = sorted(stable_mtbf_values)[len(stable_mtbf_values)//2] if stable_mtbf_values else 0
    # Find authorities with significantly stricter MTBF requirements (>5x typical = outlier)
    stable_mtbf_strict_auths = [name for name, val in stable_mtbf_by_auth.items() if stable_mtbf_typical > 0 and val > stable_mtbf_typical * 5]
    
    # Calculate Stable Uptime statistics
    # stable-uptime threshold is compared against relay's self-reported uptime (from descriptor)
    stable_uptime_min = min(stable_uptime_values) if stable_uptime_values else 0
    stable_uptime_max = max(stable_uptime_values) if stable_uptime_values else 0
    stable_uptime_typical = sorted(stable_uptime_values)[len(stable_uptime_values)//2] if stable_uptime_values else 0
    # Find authorities with significantly stricter uptime requirements (>2x typical = outlier)
    stable_uptime_strict_auths = [name for name, val in stable_uptime_by_auth.items() if stable_uptime_typical > 0 and val > stable_uptime_typical * 2]
    
    # Check relay uptime against each authority's stable-uptime threshold
    # relay_uptime comes from Onionoo (relay's self-reported uptime from last_restarted)
    stable_uptime_meets_count = 0
    if relay_uptime is not None and stable_uptime_values:
        stable_uptime_meets_count = sum(1 for ut in stable_uptime_values if relay_uptime >= ut)
    stable_uptime_meets_all = stable_uptime_meets_count == len(stable_uptime_values) if stable_uptime_values else False
    
    # Calculate Guard BW analysis using observed_bandwidth (actual bandwidth, not scaled consensus value)
    bw_formatter = lambda v: _format_bandwidth_value(v, use_bits)
    guard_bw_range = _format_range(guard_bw_values, bw_formatter) if guard_bw_values else 'N/A'
    
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
    fast_range = _format_range(fast_speed_values, bw_formatter) if fast_speed_values else 'N/A'
    
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
        'measured_bw_display': _format_bandwidth_value(relay_bw, use_bits),  # Scaled consensus value
        'observed_bw': guard_bw_value,  # Actual observed bandwidth (for Guard eligibility)
        'observed_bw_display': _format_bandwidth_value(guard_bw_value, use_bits),  # Actual bandwidth
        'guard_bw_guarantee': GUARD_BW_GUARANTEE,
        'guard_bw_guarantee_display': _format_bandwidth_value(GUARD_BW_GUARANTEE, use_bits),
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
        'fast_speed_display': _format_bandwidth_value(guard_bw_value, use_bits),
        'fast_minimum': FAST_BW_MINIMUM,
        'fast_minimum_display': _format_bandwidth_value(FAST_BW_MINIMUM, use_bits),
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
        
        # HSDir TK threshold statistics (showing dir-spec vs actual)
        # dir-spec default: 25 hours; moria1 uses ~10 days; others use default
        'hsdir_tk_min': hsdir_tk_min,  # dir-spec default (25 hours)
        'hsdir_tk_max': hsdir_tk_max,  # strictest authority (moria1's ~10 days)
        'hsdir_tk_consensus': hsdir_tk_consensus,  # what majority requires
        'hsdir_tk_min_display': _format_days(hsdir_tk_min),
        'hsdir_tk_max_display': _format_days(hsdir_tk_max),
        'hsdir_tk_consensus_display': _format_days(hsdir_tk_consensus),
        'hsdir_tk_strict_auths': hsdir_tk_strict_auths,  # authorities with stricter requirements
        'hsdir_tk_default_count': hsdir_tk_default_count,  # count using dir-spec default
        
        # Fast speed threshold statistics
        # Most authorities use ~102 KB/s, moria1 uses ~1 MB/s
        'fast_speed_min': fast_speed_min,
        'fast_speed_max': fast_speed_max,
        'fast_speed_typical': fast_speed_typical,
        'fast_speed_min_display': _format_bandwidth_value(fast_speed_min, use_bits),
        'fast_speed_max_display': _format_bandwidth_value(fast_speed_max, use_bits),
        'fast_speed_typical_display': _format_bandwidth_value(fast_speed_typical, use_bits),
        'fast_speed_strict_auths': fast_speed_strict_auths,  # authorities with stricter requirements
        
        # Stable MTBF threshold statistics
        # Most authorities have similar thresholds, outliers shown separately
        'stable_mtbf_min': stable_mtbf_min,
        'stable_mtbf_max': stable_mtbf_max,
        'stable_mtbf_typical': stable_mtbf_typical,
        'stable_mtbf_min_display': _format_days(stable_mtbf_min),
        'stable_mtbf_max_display': _format_days(stable_mtbf_max),
        'stable_mtbf_typical_display': _format_days(stable_mtbf_typical),
        'stable_mtbf_strict_auths': stable_mtbf_strict_auths,  # authorities with stricter requirements (outliers)
        
        # Stable Uptime values (relay uptime from Onionoo vs per-authority threshold from CollecTor)
        # Note: relay_uptime is the SAME for all authorities (relay's self-reported uptime)
        # Only the threshold varies per authority
        'stable_uptime': relay_uptime,  # From Onionoo (relay's descriptor via last_restarted)
        'stable_uptime_display': _format_days(relay_uptime) if relay_uptime else 'N/A',
        'stable_uptime_min': stable_uptime_min,
        'stable_uptime_max': stable_uptime_max,
        'stable_uptime_typical': stable_uptime_typical,
        'stable_uptime_min_display': _format_days(stable_uptime_min),
        'stable_uptime_max_display': _format_days(stable_uptime_max),
        'stable_uptime_typical_display': _format_days(stable_uptime_typical),
        'stable_uptime_strict_auths': stable_uptime_strict_auths,
        'stable_uptime_meets_count': stable_uptime_meets_count,
        'stable_uptime_meets_all': stable_uptime_meets_all,
        
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


def _format_authority_table_enhanced(consensus_data: dict, flag_thresholds: dict = None, observed_bandwidth: int = 0, use_bits: bool = False, relay_uptime: float = None) -> List[dict]:
    """
    Format authority votes into table rows with threshold comparison.
    
    Args:
        consensus_data: Raw consensus evaluation data
        flag_thresholds: Dict of per-authority flag thresholds
        observed_bandwidth: Relay's actual observed bandwidth (for Guard BW and Fast eligibility)
        use_bits: If True, format bandwidth in bits (Mbit/s), otherwise bytes (MB/s)
        relay_uptime: Relay's current uptime in seconds (from Onionoo last_restarted).
                      Same value for all authorities (relay's self-reported uptime).
    """
    authority_votes = consensus_data.get('authority_votes', [])
    
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
            'measured_display': _format_bandwidth_value(relay_bw, use_bits),
            
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
            'guard_bw_value_display': _format_bandwidth_value(observed_bandwidth, use_bits),
            'guard_bw_guarantee_display': _format_bandwidth_value(GUARD_BW_GUARANTEE, use_bits),
            'guard_bw_top25_display': _format_bandwidth_value(guard_bw_top25_threshold, use_bits),
            'guard_bw_meets_guarantee': observed_bandwidth >= GUARD_BW_GUARANTEE,
            'guard_bw_in_top25': observed_bandwidth >= guard_bw_top25_threshold if guard_bw_top25_threshold else False,
            'guard_bw_meets': observed_bandwidth >= GUARD_BW_GUARANTEE or (guard_bw_top25_threshold and observed_bandwidth >= guard_bw_top25_threshold),
            
            # Stable MTBF: measured MTBF | threshold  
            'stable_mtbf': relay_mtbf,
            'stable_mtbf_display': _format_days(relay_mtbf),
            'stable_threshold': stable_mtbf_threshold,
            'stable_threshold_display': _format_days(stable_mtbf_threshold),
            'stable_meets': relay_mtbf and relay_mtbf >= stable_mtbf_threshold if stable_mtbf_threshold else True,
            
            # Stable Uptime: relay uptime (from Onionoo) | threshold (from CollecTor)
            # Note: relay_uptime is the SAME for all authorities (relay's self-reported uptime from descriptor)
            # Only the stable-uptime threshold varies per authority
            'stable_uptime': relay_uptime,  # From Onionoo (relay descriptor via last_restarted)
            'stable_uptime_display': _format_days(relay_uptime) if relay_uptime else 'N/A',
            'stable_uptime_threshold': stable_threshold,  # From CollecTor (per-authority)
            'stable_uptime_threshold_display': _format_days(stable_threshold) if stable_threshold else 'N/A',
            'stable_uptime_meets': relay_uptime and relay_uptime >= stable_threshold if stable_threshold and relay_uptime else None,
            
            # Fast: uses observed_bandwidth (from descriptor), NOT scaled consensus value
            # Fast requires: bandwidth in top 7/8ths (fast_threshold) OR >= 100 KB/s
            'fast_speed': observed_bandwidth,
            'fast_speed_display': _format_bandwidth_value(observed_bandwidth, use_bits),
            'fast_threshold': fast_threshold,
            'fast_threshold_display': _format_bandwidth_value(fast_threshold, use_bits),
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


def format_authority_consensus_evaluation(
    authority_status: Dict[str, dict],
    flag_thresholds: Dict[str, dict],
    bw_authorities: List[str]
) -> dict:
    """
    Format authority consensus evaluation for misc-authorities.html dashboard.
    
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


def _format_consensus_status(consensus_data: dict) -> dict:
    """Format consensus status display."""
    in_consensus = consensus_data.get('in_consensus', False)
    vote_count = consensus_data.get('vote_count', 0)
    total = consensus_data.get('total_authorities', get_voting_authority_count())
    majority = consensus_data.get('majority_required', 5)
    
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


def _format_flag_summary(consensus_data: dict, observed_bandwidth: int = 0) -> dict:
    """
    Format flag eligibility summary.
    
    Args:
        consensus_data: Raw consensus evaluation data
        observed_bandwidth: Relay's actual observed bandwidth (for Guard BW eligibility)
    """
    flag_eligibility = consensus_data.get('flag_eligibility', {})
    total_authorities = consensus_data.get('total_authorities', get_voting_authority_count())
    
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


def _format_reachability_summary(consensus_data: dict) -> dict:
    """Format reachability summary."""
    reachability = consensus_data.get('reachability', {})
    
    ipv4_count = reachability.get('ipv4_reachable_count', 0)
    ipv6_count = reachability.get('ipv6_reachable_count', 0)
    total = reachability.get('total_authorities', get_voting_authority_count())
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


def _format_bandwidth_summary(consensus_data: dict, use_bits: bool = False) -> dict:
    """Format bandwidth summary."""
    bandwidth = consensus_data.get('bandwidth', {})
    
    median = bandwidth.get('median')  # Tor consensus uses median
    avg = bandwidth.get('average')
    min_bw = bandwidth.get('min')
    max_bw = bandwidth.get('max')
    deviation = bandwidth.get('deviation')
    
    return {
        'median': median,
        'median_display': _format_bandwidth_value(median, use_bits),
        'average': avg,
        'average_display': _format_bandwidth_value(avg, use_bits),
        'min': min_bw,
        'min_display': _format_bandwidth_value(min_bw, use_bits),
        'max': max_bw,
        'max_display': _format_bandwidth_value(max_bw, use_bits),
        'deviation': deviation,
        'deviation_display': _format_bandwidth_value(deviation, use_bits),
        'measurement_count': bandwidth.get('measurement_count', 0),
        'deviation_class': 'warning' if deviation and median and deviation > median * 0.5 else 'normal',
        # Pass through BW authority measurement counts from collector_fetcher
        'bw_auth_measured_count': bandwidth.get('bw_auth_measured_count', 0),
        'bw_auth_total': bandwidth.get('bw_auth_total', 0),
    }


def _identify_issues(consensus_data: dict, current_flags: list = None, observed_bandwidth: int = 0, version: str = None, recommended_version: bool = None) -> List[dict]:
    """
    Identify issues that may affect relay status.
    
    Based on Tor dir-spec (https://spec.torproject.org/dir-spec/) and
    common issues from tor-relays mailing list.
    
    Args:
        consensus_data: Raw consensus evaluation data
        current_flags: Relay's current flags (from Onionoo)
        observed_bandwidth: Relay's observed bandwidth for Guard eligibility
        version: Tor version string running on the relay
        recommended_version: Whether the version is recommended
    """
    issues = []
    current_flags = current_flags or []
    
    # Extract data for analysis
    authority_votes = consensus_data.get('authority_votes', [])
    reachability = consensus_data.get('reachability', {})
    flag_eligibility = consensus_data.get('flag_eligibility', {})
    auth_count = get_voting_authority_count()
    majority_threshold = (auth_count // 2) + 1
    
    # Get relay metrics from first available vote
    relay_wfu = relay_tk = None
    for vote in authority_votes:
        if relay_wfu is None and vote.get('wfu') is not None:
            relay_wfu = vote['wfu']
        if relay_tk is None and vote.get('tk') is not None:
            relay_tk = vote['tk']
        if relay_wfu is not None and relay_tk is not None:
            break
    
    # =========================================================================
    # CONSENSUS STATUS ISSUES
    # =========================================================================
    if not consensus_data.get('in_consensus'):
        vote_count = consensus_data.get('vote_count', 0)
        total = consensus_data.get('total_authorities', auth_count)
        issues.append({
            'severity': 'error',
            'category': 'consensus',
            'title': 'Not in consensus',
            'description': f"Only {vote_count}/{total} authorities voted for this relay (need {majority_threshold})",
            'suggestion': 'Verify your relay is reachable from multiple geographic locations. Check firewall rules allow incoming connections on your ORPort from all directory authority IP addresses.',
            'doc_ref': 'https://community.torproject.org/relay/setup/guard/',
        })
    
    # =========================================================================
    # REACHABILITY ISSUES (per Tor dir-spec: relay must be reachable)
    # =========================================================================
    ipv4_count = reachability.get('ipv4_reachable_count', 0)
    if ipv4_count < majority_threshold:
        unreachable = [
            name for name in get_voting_authority_names()
            if name not in reachability.get('ipv4_reachable_authorities', [])
        ]
        issues.append({
            'severity': 'error',
            'category': 'reachability',
            'title': 'IPv4 reachability issues',
            'description': f"Only {ipv4_count}/{auth_count} authorities can reach this relay",
            'suggestion': f"Authorities that cannot reach you: {', '.join(unreachable)}. Check: 1) Firewall allows incoming TCP on ORPort, 2) No ISP-level blocking, 3) Tor is running and listening. Use 'nc -zv your-ip your-orport' from external hosts to test.",
            'doc_ref': 'https://community.torproject.org/relay/setup/',
        })
    elif ipv4_count < auth_count:
        # Partial reachability - informational
        unreachable = [
            name for name in get_voting_authority_names()
            if name not in reachability.get('ipv4_reachable_authorities', [])
        ]
        if unreachable:
            issues.append({
                'severity': 'info',
                'category': 'reachability',
                'title': 'Partial IPv4 reachability',
                'description': f"{ipv4_count}/{auth_count} authorities can reach this relay",
                'suggestion': f"Some authorities cannot reach you: {', '.join(unreachable)}. This may be temporary or due to geographic routing issues.",
            })
    
    # IPv6 reachability issues
    ipv6_count = reachability.get('ipv6_reachable_count', 0)
    ipv6_tested = auth_count - len(reachability.get('ipv6_not_tested_authorities', []))
    if ipv6_tested > 0 and ipv6_count == 0:
        issues.append({
            'severity': 'warning',
            'category': 'reachability',
            'title': 'IPv6 not reachable',
            'description': f"0/{ipv6_tested} authorities that test IPv6 can reach your IPv6 address",
            'suggestion': 'Verify IPv6 is correctly configured: 1) Check ORPort binding includes IPv6 address, 2) Firewall allows IPv6 traffic, 3) IPv6 address is publicly routable. Test with: curl -6 http://ipv6.icanhazip.com/',
            'doc_ref': 'https://community.torproject.org/relay/setup/',
        })
    
    # =========================================================================
    # GUARD FLAG ELIGIBILITY (per Tor dir-spec section on Guard assignment)
    # =========================================================================
    has_guard = 'Guard' in current_flags
    has_stable = 'Stable' in current_flags
    has_fast = 'Fast' in current_flags
    guard_bw_eligible = observed_bandwidth >= GUARD_BW_GUARANTEE if observed_bandwidth else False
    wfu_eligible = relay_wfu and relay_wfu >= GUARD_WFU_DEFAULT
    tk_eligible = relay_tk and relay_tk >= GUARD_TK_DEFAULT
    
    if not has_guard:
        # Check each Guard requirement and provide specific advice
        if not guard_bw_eligible and observed_bandwidth:
            bw_display = f"{observed_bandwidth / 1_000_000:.1f} MB/s"
            issues.append({
                'severity': 'warning',
                'category': 'guard',
                'title': 'Guard: bandwidth below threshold',
                'description': f"Observed bandwidth {bw_display} is below 2 MB/s minimum (AuthDirGuardBWGuarantee)",
                'suggestion': 'Guard requires ≥2 MB/s bandwidth OR being in top 25% of network. To increase bandwidth: 1) Ensure adequate upstream capacity, 2) Check RelayBandwidthRate/RelayBandwidthBurst in torrc, 3) Monitor with Nyx or ARM.',
                'doc_ref': 'https://community.torproject.org/relay/setup/guard/',
            })
        
        if not wfu_eligible and relay_wfu is not None:
            wfu_pct = relay_wfu * 100
            issues.append({
                'severity': 'warning',
                'category': 'guard',
                'title': 'Guard: WFU below threshold',
                'description': f"Weighted Fractional Uptime {wfu_pct:.1f}% is below 98% requirement",
                'suggestion': 'WFU measures recent uptime (recent downtime weighs more heavily). To improve: 1) Minimize restarts, 2) Use systemd with Restart=always, 3) Monitor for OOM kills, 4) Schedule updates during low-traffic periods.',
                'doc_ref': 'https://spec.torproject.org/dir-spec/assigning-flags-vote.html',
            })
        
        if not tk_eligible and relay_tk is not None:
            tk_days = relay_tk / SECONDS_PER_DAY
            days_needed = (GUARD_TK_DEFAULT - relay_tk) / SECONDS_PER_DAY
            issues.append({
                'severity': 'info',
                'category': 'guard',
                'title': 'Guard: Time Known below threshold',
                'description': f"Time Known {tk_days:.1f} days is below 8 days requirement ({days_needed:.1f} more days needed)",
                'suggestion': 'Time Known tracks how long authorities have observed your relay. This resets if: 1) Identity key changes, 2) Long downtime makes authorities forget you. Just keep running stably.',
                'doc_ref': 'https://spec.torproject.org/dir-spec/assigning-flags-vote.html',
            })
        
        if not has_stable:
            issues.append({
                'severity': 'info',
                'category': 'guard',
                'title': 'Guard: requires Stable flag',
                'description': 'Guard flag requires having the Stable flag first',
                'suggestion': 'Get Stable flag by maintaining consistent uptime. Stable requires uptime and MTBF at or above network median (typically 2-3 weeks of stable running).',
            })
        
        if not has_fast:
            issues.append({
                'severity': 'info',
                'category': 'guard',
                'title': 'Guard: requires Fast flag',
                'description': 'Guard flag requires having the Fast flag first',
                'suggestion': 'Get Fast flag by having bandwidth ≥100 KB/s OR in top 7/8ths of network. Most relays get this easily.',
            })
    
    # =========================================================================
    # STABLE FLAG ISSUES
    # =========================================================================
    if not has_stable and relay_tk is not None:
        stable_eligibility = flag_eligibility.get('stable', {})
        if stable_eligibility.get('eligible_count', 0) < majority_threshold:
            issues.append({
                'severity': 'info',
                'category': 'stable',
                'title': 'Not eligible for Stable flag',
                'description': 'Uptime or MTBF below network median for most authorities',
                'suggestion': 'Stable flag requires uptime/MTBF at or above network median. Keep your relay running continuously for 2-3 weeks. Avoid restarts. Use reliable hardware and network connection.',
                'doc_ref': 'https://spec.torproject.org/dir-spec/assigning-flags-vote.html',
            })
    
    # =========================================================================
    # HSDIR FLAG ISSUES
    # =========================================================================
    has_hsdir = 'HSDir' in current_flags
    if not has_hsdir:
        hsdir_eligibility = flag_eligibility.get('hsdir', {})
        if relay_wfu is not None and relay_wfu < HSDIR_WFU_DEFAULT:
            issues.append({
                'severity': 'info',
                'category': 'hsdir',
                'title': 'HSDir: WFU below threshold',
                'description': f"WFU {relay_wfu*100:.1f}% below 98% required for HSDir",
                'suggestion': 'HSDir requires ≥98% WFU, Stable flag, and Time Known ≥25 hours (or ~10 days for moria1). Improve uptime consistency.',
            })
        if relay_tk is not None and relay_tk < HSDIR_TK_DEFAULT:
            tk_hours = relay_tk / 3600
            issues.append({
                'severity': 'info',
                'category': 'hsdir',
                'title': 'HSDir: Time Known below threshold',
                'description': f"Time Known {tk_hours:.1f} hours below 25 hours (dir-spec default)",
                'suggestion': 'Most authorities use 25 hours for HSDir TK. moria1 uses ~10 days. Keep running stably.',
            })
    
    # =========================================================================
    # BANDWIDTH/MEASUREMENT ISSUES
    # =========================================================================
    bandwidth_data = consensus_data.get('bandwidth', {})
    if bandwidth_data:
        deviation = bandwidth_data.get('deviation')
        median = bandwidth_data.get('median')
        if deviation and median and deviation > median * 0.5:
            issues.append({
                'severity': 'warning',
                'category': 'bandwidth',
                'title': 'High consensus weight deviation',
                'description': f"Large variation in Consensus Weight values across authorities (see 'Cons Wt' column in Per-Authority Details below)",
                'suggestion': 'Consensus weight measurements vary significantly between authorities. This can affect traffic distribution. Ensure stable network connection and consistent bandwidth availability.',
            })
    
    # =========================================================================
    # STALEDESC FLAG (descriptor too old)
    # =========================================================================
    for vote in authority_votes:
        if vote.get('voted') and 'StaleDesc' in vote.get('flags', []):
            issues.append({
                'severity': 'warning',
                'category': 'descriptor',
                'title': 'StaleDesc flag assigned',
                'description': 'Relay descriptor is older than 18 hours',
                'suggestion': 'Your relay is not publishing fresh descriptors. Check: 1) Tor process is running, 2) Network connectivity, 3) Clock is synchronized (NTP). Restart Tor if needed.',
                'doc_ref': 'https://spec.torproject.org/dir-spec/assigning-flags-vote.html',
            })
            break  # Only report once
    
    # =========================================================================
    # BADEXIT FLAG
    # =========================================================================
    if 'BadExit' in current_flags:
        issues.append({
            'severity': 'error',
            'category': 'flags',
            'title': 'BadExit flag assigned',
            'description': 'This relay has been flagged as a bad exit by directory authorities. BadExit means authorities detected malicious behavior (traffic modification, SSL stripping, etc.).',
            'suggestion': 'Contact <a href="mailto:bad-relays@lists.torproject.org">bad-relays@lists.torproject.org</a> to understand and resolve this issue.',
            'doc_ref': 'https://community.torproject.org/relay/',
        })
    
    # =========================================================================
    # VERSION ISSUES
    # =========================================================================
    if recommended_version is False and version:
        issues.append({
            'severity': 'warning',
            'category': 'version',
            'title': 'Tor version not recommended',
            'description': f'Running Tor version {version} which is not on the recommended list.',
            'suggestion': 'Update to the latest stable Tor version. Outdated versions may have security vulnerabilities and could eventually be rejected by the network. See <a href="https://www.torproject.org/download/tor/">torproject.org/download</a> for latest releases.',
            'doc_ref': 'https://www.torproject.org/download/tor/',
        })
    
    return issues


def _generate_advice(consensus_data: dict, current_flags: list = None, observed_bandwidth: int = 0) -> List[dict]:
    """
    Generate detailed actionable advice based on consensus evaluation.
    
    Returns list of advice dicts with 'category', 'priority', 'title', 'advice', and optional 'doc_ref'.
    Based on Tor Project official guidance and common operator issues.
    
    Args:
        consensus_data: Raw consensus evaluation data
        current_flags: Relay's current flags
        observed_bandwidth: Relay's observed bandwidth
    """
    advice_list = []
    current_flags = current_flags or []
    
    # Get all issues first
    issues = _identify_issues(consensus_data, current_flags, observed_bandwidth)
    
    # Convert issues to advice with priorities
    priority_map = {'error': 1, 'warning': 2, 'info': 3}
    
    for issue in issues:
        advice_list.append({
            'category': issue.get('category', 'general'),
            'priority': priority_map.get(issue.get('severity', 'info'), 3),
            'title': issue.get('title', ''),
            'advice': issue.get('suggestion', ''),
            'doc_ref': issue.get('doc_ref'),
        })
    
    # =========================================================================
    # ADDITIONAL PROACTIVE ADVICE (not tied to specific issues)
    # =========================================================================
    
    # Extract metrics
    authority_votes = consensus_data.get('authority_votes', [])
    relay_wfu = relay_tk = None
    for vote in authority_votes:
        if relay_wfu is None and vote.get('wfu') is not None:
            relay_wfu = vote['wfu']
        if relay_tk is None and vote.get('tk') is not None:
            relay_tk = vote['tk']
        if relay_wfu is not None and relay_tk is not None:
            break
    
    has_guard = 'Guard' in current_flags
    has_stable = 'Stable' in current_flags
    has_exit = 'Exit' in current_flags
    
    # Advice for relays close to Guard eligibility
    if not has_guard and has_stable and relay_wfu and relay_wfu >= 0.95:
        if relay_wfu < 0.98:
            advice_list.append({
                'category': 'guard',
                'priority': 2,
                'title': 'Almost Guard eligible (WFU)',
                'advice': f"Your WFU is {relay_wfu*100:.1f}%, close to the 98% threshold. Minimize restarts and downtime to reach Guard eligibility.",
            })
    
    # Advice for new relays
    if relay_tk and relay_tk < GUARD_TK_DEFAULT:
        days_remaining = (GUARD_TK_DEFAULT - relay_tk) / SECONDS_PER_DAY
        if days_remaining > 0 and days_remaining < 3:
            advice_list.append({
                'category': 'guard',
                'priority': 3,
                'title': 'Guard eligibility approaching',
                'advice': f"Your relay will reach 8 days Time Known in {days_remaining:.1f} days. Keep running stably to get Guard flag.",
            })
    
    # General best practices for all relays
    if consensus_data.get('in_consensus'):
        # Relay is in consensus, provide optimization advice
        if not has_exit and observed_bandwidth and observed_bandwidth > 10_000_000:
            advice_list.append({
                'category': 'general',
                'priority': 3,
                'title': 'Consider becoming an exit relay',
                'advice': 'Your relay has good bandwidth. Consider configuring an exit policy to help the network. Exits are in high demand. See: https://community.torproject.org/relay/setup/exit/',
                'doc_ref': 'https://community.torproject.org/relay/setup/exit/',
            })
    
    # Sort by priority (lower = higher priority)
    advice_list.sort(key=lambda x: x.get('priority', 3))
    
    return advice_list


def _generate_advice_simple(consensus_data: dict) -> List[str]:
    """
    Generate simple string advice for backward compatibility.
    Returns list of advice strings.
    """
    detailed_advice = _generate_advice(consensus_data)
    return [item.get('advice', '') for item in detailed_advice if item.get('advice')]


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


def _format_bandwidth_value(value: Any, use_bits: bool = False) -> str:
    """
    Format bandwidth value for display.
    Leverages existing BandwidthFormatter for KB/s and above.
    Handles sub-KB values directly (BandwidthFormatter doesn't support B/s).
    
    Args:
        value: Bandwidth in bytes/second
        use_bits: If True, display in bits (Mbit/s), otherwise bytes (MB/s)
    """
    if value is None:
        return 'N/A'
    
    # Handle sub-KB values directly (BandwidthFormatter starts at KB/s)
    if value < 1000:
        if use_bits:
            return f"{value * 8} bit/s"
        return f"{value} B/s"
    
    # Get or create cached formatter for this use_bits setting
    if _BandwidthFormatterClass is not None:
        if use_bits not in _bw_formatter_cache:
            _bw_formatter_cache[use_bits] = _BandwidthFormatterClass(use_bits=use_bits)
        formatter = _bw_formatter_cache[use_bits]
        try:
            return formatter.format_bandwidth_with_suffix(value, decimal_places=1)
        except (ValueError, TypeError):
            pass
    
    # Manual fallback if BandwidthFormatter not available
    if use_bits:
        value_bits = value * 8
        if value_bits >= 1000000000:
            return f"{value_bits / 1000000000:.1f} Gbit/s"
        elif value_bits >= 1000000:
            return f"{value_bits / 1000000:.1f} Mbit/s"
        else:
            return f"{value_bits / 1000:.1f} Kbit/s"
    else:
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
