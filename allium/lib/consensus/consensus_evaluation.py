"""
File: consensus_evaluation.py

Format consensus evaluation data for templates.
Provides display-ready formatting of directory authority consensus evaluation data.

OPTIMIZATION: Leverages existing utilities from the codebase:
- BandwidthFormatter from bandwidth_formatter.py for bandwidth display
- format_percentage_from_fraction from string_utils.py for WFU percentages
"""

from typing import Dict, List, Optional, Any
from collections import Counter

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

# Import relay_diagnostics at module level (PERF: avoid in-function import on ~10k calls)
try:
    from ..relay_diagnostics import generate_issues_from_consensus as _generate_issues_impl
except ImportError:
    _generate_issues_impl = None  # Fallback handled in _identify_issues


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


def _port_in_rules(rules: list, port: int) -> bool:
    """Check if a port is covered by a list of exit policy rules.

    Onionoo exit_policy_summary rules are strings like:
    '80', '443', '80-443', '1-65535'
    """
    for rule in rules:
        if '-' in str(rule):
            try:
                start, end = str(rule).split('-')
                if int(start) <= port <= int(end):
                    return True
            except (ValueError, IndexError):
                continue
        else:
            try:
                if int(rule) == port:
                    return True
            except ValueError:
                continue
    return False


def _format_valid_version_display(version: str, recommended_version: bool) -> str:
    """Format Valid flag version display string."""
    if not version:
        return 'Unknown'
    if recommended_version is True:
        return f'{version} (Recommended)'
    elif recommended_version is False:
        return f'{version} (Not Recommended)'
    return version


def _format_v2dir_display(dir_address: str, has_v2dir_flag: bool) -> str:
    """Format V2Dir flag display string.
    
    V2Dir requires DirPort OR tunnelled-dir-server.
    If relay has V2Dir flag but no DirPort, it must have tunnelled-dir-server.
    """
    if dir_address:
        port = dir_address.split(':')[-1] if ':' in dir_address else dir_address
        return f'DirPort: {port}'
    elif has_v2dir_flag:
        return 'Tunnelled: Yes (no DirPort)'
    else:
        return 'No DirPort, no tunnelled-dir-server'


def _analyze_exit_policy(exit_policy_summary: dict) -> dict:
    """Analyze exit policy for Exit flag eligibility.

    Per Tor dir-spec Section 3.4.2: Exit flag requires allowing exits to at least
    one /8 address space on BOTH port 80 AND port 443.

    Args:
        exit_policy_summary: From Onionoo relay['exit_policy_summary']
            Format: {'accept': ['80', '443', '6667'], 'reject': [...]}
            or: {'reject': ['25', '119', ...]}  (implicit accept-all minus rejects)

    Returns:
        dict with: allows_80, allows_443, eligible, display
    """
    if not exit_policy_summary:
        return {'allows_80': False, 'allows_443': False,
                'eligible': False, 'display': 'No exit policy'}

    accept_rules = exit_policy_summary.get('accept', [])
    reject_rules = exit_policy_summary.get('reject', [])

    # Onionoo exit_policy_summary format:
    # - If 'accept' key exists: only listed ports are allowed
    # - If only 'reject' key exists: all ports allowed EXCEPT listed ones
    if accept_rules:
        allows_80 = _port_in_rules(accept_rules, 80)
        allows_443 = _port_in_rules(accept_rules, 443)
    elif reject_rules:
        allows_80 = not _port_in_rules(reject_rules, 80)
        allows_443 = not _port_in_rules(reject_rules, 443)
    else:
        allows_80 = False
        allows_443 = False

    eligible = allows_80 and allows_443

    p80 = 'Yes' if allows_80 else 'No'
    p443 = 'Yes' if allows_443 else 'No'
    display = f"Port 80: {p80} | Port 443: {p443}"

    return {
        'allows_80': allows_80,
        'allows_443': allows_443,
        'eligible': eligible,
        'display': display,
    }


# Empty stats result - reused constant to avoid dict recreation
_EMPTY_DA_STATS = {
    'primary_value': None, 'primary_count': 0, 'has_majority': False,
    'min_value': None, 'median_value': None, 'max_value': None,
    'primary_display': 'N/A', 'min_display': 'N/A',
    'median_display': 'N/A', 'max_display': 'N/A',
    'has_variation': False,
    'voting_count': 0,      # Number of authorities that provided this value
    'total_possible': 0,    # Total authorities that could vote
}

# Tor spec: majority = more than half = ≥5/9 authorities
MAJORITY_THRESHOLD = 5


def _compute_da_value_stats(values: list, format_func, total_possible: int = 9, threshold: float = None) -> dict:
    """
    Compute majority/median, min, max statistics for DA-measured values.
    
    Per Tor dir-spec: majority = ≥5/9 authorities agreeing on same value.
    If no majority exists, fall back to median.
    
    Args:
        values: List of raw values (one per authority that reported)
        format_func: Function to format the value for display (e.g., _format_wfu_display)
        total_possible: Total number of authorities that could vote (9 for most metrics)
        threshold: Optional threshold value - if provided, computes how many values meet it
                   (used for time metrics where exact value agreement is rare)
    
    Returns:
        dict with: primary_value (majority or median), primary_count, has_majority,
                   voting_count, total_possible, min_value, median_value, max_value,
                   meets_threshold_count (if threshold provided)
    """
    # Filter out None values in single pass
    values = [v for v in values if v is not None]
    if not values:
        return {**_EMPTY_DA_STATS, 'total_possible': total_possible}
    
    # Sort once - reuse for min, max, median
    sorted_values = sorted(values)
    voting_count = len(sorted_values)  # How many authorities actually provided values
    min_value = sorted_values[0]
    max_value = sorted_values[-1]
    
    # Median from sorted list
    mid = voting_count // 2
    median_value = (sorted_values[mid - 1] + sorted_values[mid]) / 2 if voting_count % 2 == 0 else sorted_values[mid]
    
    # Check for majority (≥5 per Tor spec)
    value_counts = Counter(values)
    most_common_value, most_common_count = value_counts.most_common(1)[0]
    
    # Tor majority = ≥5 authorities agreeing on same value
    has_majority = most_common_count >= MAJORITY_THRESHOLD
    
    # Primary value: majority if exists, else median
    if has_majority:
        primary_value = most_common_value
        primary_count = most_common_count
    else:
        primary_value = median_value
        # Count how many authorities have exactly the median value
        # (median may be calculated, so could be 0, 1, or more)
        primary_count = value_counts.get(median_value, 0)
    
    # If threshold provided, count how many values meet it
    # (useful for time metrics where exact agreement is rare but threshold comparison matters)
    meets_threshold_count = None
    if threshold is not None:
        meets_threshold_count = sum(1 for v in values if v >= threshold)
    
    return {
        'primary_value': primary_value,
        'primary_count': primary_count,
        'has_majority': has_majority,
        'min_value': min_value,
        'median_value': median_value,
        'max_value': max_value,
        'primary_display': format_func(primary_value),
        'min_display': format_func(min_value),
        'median_display': format_func(median_value),
        'max_display': format_func(max_value),
        'has_variation': min_value != max_value,
        'voting_count': voting_count,       # Total authorities that provided values
        'total_possible': total_possible,   # Total authorities that could vote
        'meets_threshold_count': meets_threshold_count,  # How many meet threshold (if provided)
    }


# Canonical flag ordering for consistent display across all relay pages
# Order: Simple/Common → Complex/Rare
# Running, Valid (basic) → V2Dir (~100% software cap) → Fast, Stable (perf) → HSDir, Guard, Exit (complex)
FLAG_ORDER = [
    'Running',    # Relay is reachable (basic)
    'Valid',      # Verified, allowed in network (basic)
    'V2Dir',      # Supports directory protocol v2+ (~100% of relays)
    'Fast',       # Bandwidth in top 7/8ths or ≥100 KB/s (performance)
    'Stable',     # Sufficient uptime/MTBF (performance)
    'HSDir',      # Hidden service directory (requires Fast+Stable)
    'Guard',      # Can be used as entry guard (requires Fast+Stable+V2Dir)
    'Exit',       # Can be used as exit node (policy-based)
    'Authority',  # Special: directory authority
    'MiddleOnly', # Restricted to middle position only (negative flag)
    'BadExit',    # Flagged as misbehaving exit
    'NoEdConsensus',  # Doesn't support ed25519
    'StaleDesc',  # Descriptor is old
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


def format_relay_consensus_evaluation(evaluation: dict, flag_thresholds: dict = None, current_flags: list = None, observed_bandwidth: int = 0, use_bits: bool = False, relay_uptime: float = None, version: str = None, recommended_version: bool = None, exit_policy_summary: dict = None, dir_address: str = None) -> dict:
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
        exit_policy_summary: Relay's exit policy summary from Onionoo (for Exit flag analysis).
                            Format: {'accept': ['80', '443']} or {'reject': ['25', '119']}.
        dir_address: Relay's directory address from Onionoo (for V2Dir flag analysis).
                    Format: "IP:Port" string or None.
        
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
        
        # Relay values summary (for Summary table) - pass observed_bandwidth, use_bits, relay_uptime, exit_policy_summary
        'relay_values': _format_relay_values(evaluation, flag_thresholds, observed_bandwidth, use_bits, relay_uptime, exit_policy_summary, current_flags=current_flags, version=version, recommended_version=recommended_version, dir_address=dir_address),
        
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
    
    # Add pre-computed flag requirements table (Phase 4 optimization)
    # This moves complex template conditionals to Python for better performance
    formatted['flag_requirements_table'] = _format_flag_requirements_table(
        formatted['relay_values'], 
        formatted
    )
    
    # Pre-compute eligible flags display data (DRY optimization)
    # Moves repeated color mapping and flag display logic from template to Python
    formatted['eligible_flags_display'] = _format_eligible_flags_display(formatted)
    
    # Export tooltip constants for template use
    formatted['tooltips'] = {
        'flags': FLAG_TOOLTIPS,
        'sources': SOURCE_TOOLTIPS,
        'status': STATUS_TOOLTIPS,
    }
    
    # Export color constants for template use
    formatted['status_colors'] = STATUS_COLORS
    
    return formatted


def _format_relay_values(consensus_data: dict, flag_thresholds: dict = None, observed_bandwidth: int = 0, use_bits: bool = False, relay_uptime: float = None, exit_policy_summary: dict = None, current_flags: list = None, version: str = None, recommended_version: bool = None, dir_address: str = None) -> dict:
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
        exit_policy_summary: Relay's exit policy summary from Onionoo (for Exit flag analysis).
        current_flags: Relay's current flags from Onionoo (for V2Dir/Running/Valid display).
        version: Tor version string from Onionoo (for Valid flag display).
        recommended_version: Whether version is recommended from Onionoo (for Valid flag display).
        dir_address: Relay's directory address from Onionoo (for V2Dir flag display).
    """
    current_flags = current_flags or []
    authority_votes = consensus_data.get('authority_votes', [])
    flag_eligibility = consensus_data.get('flag_eligibility', {})
    reachability = consensus_data.get('reachability', {})
    total_authorities = consensus_data.get('total_authorities', get_voting_authority_count())
    majority_required = consensus_data.get('majority_required', 5)
    
    # Collect ALL values from all authorities for DA-measured metrics
    # This enables computing majority, min, median, max statistics
    all_wfu_values = []
    all_tk_values = []
    all_mtbf_values = []
    relay_bw = None
    
    for vote in authority_votes:
        if vote.get('wfu') is not None:
            all_wfu_values.append(vote['wfu'])
        if vote.get('tk') is not None:
            all_tk_values.append(vote['tk'])
        if vote.get('mtbf') is not None:
            all_mtbf_values.append(vote['mtbf'])
        if relay_bw is None:
            relay_bw = vote.get('measured') or vote.get('bandwidth')
    
    # Compute WFU stats (threshold is consistent across authorities)
    wfu_stats = _compute_da_value_stats(all_wfu_values, _format_wfu_display, total_authorities,
                                        threshold=DEFAULT_WFU_THRESHOLD)
    
    # TK and MTBF stats computed after threshold collection (thresholds vary per authority)
    # Placeholder - will be computed after threshold loop
    tk_stats = None
    mtbf_stats = None
    
    # Use WFU majority value as the primary display value
    relay_wfu = wfu_stats['primary_value']
    
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
    
    # Calculate Stable MTBF typical threshold early (needed for stats computation)
    # MTBF thresholds vary per authority; use median as representative threshold
    stable_mtbf_typical = sorted(stable_mtbf_values)[len(stable_mtbf_values)//2] if stable_mtbf_values else 0
    
    # Now compute TK and MTBF stats with threshold comparison
    # TK: Use Guard TK threshold (8 days) - what most authorities require
    tk_stats = _compute_da_value_stats(all_tk_values, _format_days, total_authorities,
                                       threshold=guard_tk_threshold)
    
    # MTBF: Use median authority threshold for comparison
    mtbf_stats = _compute_da_value_stats(all_mtbf_values, _format_days, total_authorities,
                                         threshold=stable_mtbf_typical if stable_mtbf_typical else None)
    
    # Set relay values from stats
    relay_tk = tk_stats['primary_value']
    relay_mtbf = mtbf_stats['primary_value']
    
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
    # stable_mtbf_typical already computed above for threshold stats
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
    
    # Extract Guard prerequisite flag counts from flag_eligibility
    # Per Tor dir-spec Section 3.4.2: Guard requires Fast, Stable, and V2Dir flags
    guard_details = flag_eligibility.get('guard', {}).get('details', [])
    guard_prereq_fast_count = sum(1 for d in guard_details if d.get('has_fast', False))
    guard_prereq_stable_count = sum(1 for d in guard_details if d.get('has_stable', False))
    guard_prereq_v2dir_count = sum(1 for d in guard_details if d.get('has_v2dir', False))
    
    # Extract HSDir prerequisite flag counts from flag_eligibility
    # Per Tor dir-spec: HSDir requires Stable and Fast flags
    # Note: Using guard_details since it contains has_stable/has_fast fields
    # (HSDir and Guard share the same authority flag assignments)
    hsdir_prereq_stable_count = sum(1 for d in guard_details if d.get('has_stable', False))
    hsdir_prereq_fast_count = sum(1 for d in guard_details if d.get('has_fast', False))
    
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
    
    # Exit policy analysis (from Onionoo exit_policy_summary)
    exit_analysis = _analyze_exit_policy(exit_policy_summary)
    
    return {
        # WFU values (DA-measured, with majority/min/median/max stats)
        'wfu': relay_wfu,
        'wfu_display': _format_wfu_display(relay_wfu),
        'wfu_meets': relay_wfu and relay_wfu >= guard_wfu_threshold,
        'guard_wfu_threshold': guard_wfu_threshold,
        # WFU stats for display (full stats dict passed to formatter)
        'wfu_stats': wfu_stats,
        
        # Time Known values (DA-measured, with majority/min/median/max stats)
        'tk': relay_tk,
        'tk_display': _format_days(relay_tk, suffix=' days'),
        'tk_meets': relay_tk and relay_tk >= guard_tk_threshold,
        'guard_tk_threshold': guard_tk_threshold,
        'tk_days_needed': (guard_tk_threshold - (relay_tk or 0)) / SECONDS_PER_DAY if relay_tk and relay_tk < guard_tk_threshold else 0,
        # TK stats for display (full stats dict passed to formatter)
        'tk_stats': tk_stats,
        
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
        
        # Guard prerequisite flag counts (per Tor dir-spec: Guard requires Fast, Stable, V2Dir)
        'guard_prereq_fast_count': guard_prereq_fast_count,
        'guard_prereq_stable_count': guard_prereq_stable_count,
        'guard_prereq_v2dir_count': guard_prereq_v2dir_count,
        'total_authorities': total_authorities,
        'majority_required': majority_required,
        
        # Stable values
        'stable_range': stable_range,
        'stable_meets_all': stable_meets_all,
        'stable_meets_count': stable_meets_count,
        'stable_mtbf_range': stable_mtbf_range,
        'stable_mtbf_meets_all': stable_meets_all,  # Same count for simplicity
        'stable_mtbf_meets_count': stable_meets_count,
        # MTBF stats for display (full stats dict passed to formatter)
        'mtbf': relay_mtbf,
        'mtbf_display': _format_days(relay_mtbf, decimals=0, suffix=' days'),
        'mtbf_stats': mtbf_stats,
        
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
        
        # HSDir prerequisite flag counts (per Tor dir-spec: HSDir requires Stable and Fast)
        'hsdir_prereq_stable_count': hsdir_prereq_stable_count,
        'hsdir_prereq_fast_count': hsdir_prereq_fast_count,
        
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
        
        # Exit policy values (from Onionoo exit_policy_summary)
        # Per Tor dir-spec: Exit requires allowing exits to ≥1 /8 on ports 80 AND 443
        'exit_allows_80': exit_analysis['allows_80'],
        'exit_allows_443': exit_analysis['allows_443'],
        'exit_eligible': exit_analysis['eligible'],
        'exit_policy_display': exit_analysis['display'],
        'exit_assigned_count': flag_eligibility.get('exit', {}).get('assigned_count', 0),
        
        # MiddleOnly detection (from CollecTor vote flags)
        # MiddleOnly is a negative flag — restricts relay to middle position only.
        # Conditional display: only shown when relay is flagged.
        'middleonly_flagged': flag_eligibility.get('middleonly', {}).get('assigned_count', 0) > 0,
        'middleonly_count': flag_eligibility.get('middleonly', {}).get('assigned_count', 0),
        
        # BadExit detection (from CollecTor vote flags)
        # BadExit marks misbehaving exit nodes; also added when MiddleOnly is assigned.
        'badexit_flagged': flag_eligibility.get('badexit', {}).get('assigned_count', 0) > 0,
        'badexit_count': flag_eligibility.get('badexit', {}).get('assigned_count', 0),
        
        # Running flag values (from reachability data, already computed above)
        # Running = authority could reach relay's ORPort within last 45 minutes
        'running_ipv4_count': ipv4_reachable_count,
        'running_ipv6_count': ipv6_reachable_count,
        'running_ipv6_tested': ipv6_tested_count,
        'running_has_ipv6': ipv6_tested_count > 0,
        
        # Valid flag values (version check)
        # Valid = not blacklisted + valid descriptor + non-broken Tor version
        'valid_version': version,
        'valid_recommended': recommended_version,
        'valid_version_display': _format_valid_version_display(version, recommended_version),
        
        # V2Dir flag values (DirPort or tunnelled-dir-server)
        # V2Dir = has DirPort OR tunnelled-dir-server; required for Guard
        'v2dir_has_flag': 'V2Dir' in current_flags,
        'v2dir_dir_address': dir_address or '',
        'v2dir_has_dirport': bool(dir_address),
        'v2dir_display': _format_v2dir_display(dir_address, 'V2Dir' in current_flags),
    }


# ============================================================================
# FLAG REQUIREMENTS TABLE - Pre-computed data for template efficiency
# ============================================================================

# Tooltip constants for DRY - defined once, used in both Python and templates
FLAG_TOOLTIPS = {
    'guard': "Entry Guard: First hop in Tor circuits. Requires high uptime (WFU>=98%), sufficient age (TK>=8d), and bandwidth (>=2MB/s or top 25%).",
    'stable': "Suitable for long-lived connections. Requires sufficient MTBF and uptime to handle persistent streams.",
    'fast': "High bandwidth relay. Requires >=100 KB/s or in top 7/8 of network bandwidth.",
    'hsdir': "Hidden Service Directory: Stores and serves hidden service descriptors. Requires high uptime (WFU>=98%) and sufficient age.",
    'running': "Relay is reachable: Directory Authority successfully connected to relay's OR port.",
    'valid': "Relay is verified: Not blacklisted, has valid descriptor, and properly configured.",
    'v2dir': "Supports directory protocol v2+: Can serve directory information to clients.",
    'exit': "Exit node: Can relay traffic to the regular internet.",
    'authority': "Directory Authority: Votes on network consensus.",
    'middleonly': "MiddleOnly: Relay restricted to middle position only. Removes Exit, Guard, HSDir, V2Dir flags and adds BadExit. Assigned by authorities for suspicious behavior, Sybil risk, or policy violations. (Tor 0.4.7.2+)",
    'badexit': "Flagged as misbehaving exit node.",
}

METRIC_TOOLTIPS = {
    'wfu_guard': "Weighted Fractional Uptime: Measures relay reliability with recent uptime weighted more heavily. Required >=98% for Guard flag. Source: Dir. Auth. vote files.",
    'tk_guard': "How long Directory Authorities have tracked this relay. Required >=8 days for Guard flag to prevent Sybil attacks. Source: Dir. Auth. vote files.",
    'bw_guard': "Relay's observed bandwidth capacity. Required >=2 MB/s (guaranteed) OR in top 25% of network for Guard flag. Source: Relay descriptor.",
    'mtbf_stable': "Mean Time Between Failures: Average uptime between restarts/crashes. Higher = more reliable for long-lived connections. Source: Dir. Auth. vote files.",
    'uptime_stable': "Current session uptime since last restart. Compared against each authority's stable-uptime threshold. Source: Relay descriptor.",
    'speed_fast': "Relay's observed bandwidth. Required >=100 KB/s (guaranteed) OR in top 7/8 of network for Fast flag. Source: Relay descriptor.",
    'wfu_hsdir': "Weighted Fractional Uptime: Required >=98% for HSDir flag to ensure reliable hidden service directory. Source: Dir. Auth. vote files.",
    'tk_hsdir': "How long authorities have tracked this relay. Most require >=25 hours; some (moria1) require ~10 days. Source: Dir. Auth. vote files.",
    'policy_exit': "Exit policy must allow traffic to at least one /8 address space on both port 80 AND port 443 per Tor dir-spec Section 3.4.2. Source: Onionoo exit_policy_summary.",
    'middleonly': "Security restriction assigned by Directory Authorities. MiddleOnly relays cannot serve as Guard, Exit, or HSDir. Removes Exit, Guard, HSDir, V2Dir flags and adds BadExit. Source: CollecTor vote files.",
    'badexit': "Misbehaving exit node flagged by Directory Authorities. Traffic manipulation, SSL stripping, content injection, or DNS manipulation detected. Also assigned automatically with MiddleOnly. Source: CollecTor vote files.",
    'running_ipv4': "IPv4 reachability: Directory Authority must successfully connect to relay's IPv4 ORPort within 45 minutes. Source: CollecTor vote files (presence of relay in vote = reachable).",
    'running_ipv6': "IPv6 reachability: Tested by authorities with AuthDirHasIPv6Connectivity enabled. Not all authorities test IPv6. Source: CollecTor vote files ('a' line).",
    'version_valid': "Tor version must not be known to be broken. Outdated versions may lose Valid flag and be rejected from the network. Source: Onionoo relay descriptor.",
    'v2dir_capability': "Relay needs open DirPort OR tunnelled-dir-server line in descriptor, and DirCache not disabled. Required for Guard flag. Source: Onionoo dir_address / relay descriptor.",
}

SOURCE_TOOLTIPS = {
    'da': "Directory Authority Measured: Value measured by Dir. Authorities from CollecTor vote files.",
    'relay': "Relay Reported: Value self-reported by the relay in its descriptor.",
}

STATUS_TOOLTIPS = {
    'meets': "Relay meets or exceeds threshold for all/majority of Directory Authorities. Flag will be assigned.",
    'partial': "Relay meets threshold for some but not all authorities. May receive flag depending on which authorities agree.",
    'below': "Relay does not meet threshold. Flag will not be assigned until requirements are met.",
}

# Color constants
STATUS_COLORS = {
    'meets': '#28a745',
    'partial': '#856404', 
    'below': '#dc3545',
}

# Map Bootstrap status classes to internal status keys (for get_flag_color lookup)
_STATUS_CLASS_TO_KEY = {'success': 'meets', 'warning': 'partial'}

# Eligible flag order (lowercase version of FLAG_ORDER subset for eligibility display)
# Running, Valid (basic) → V2Dir (~100%) → Fast, Stable (perf) → HSDir, Guard, Exit (complex)
ELIGIBLE_FLAG_ORDER = ['running', 'valid', 'v2dir', 'fast', 'stable', 'hsdir', 'guard', 'exit']


def _get_status_color(status_class: str) -> str:
    """Convert status_class to hex color. DRY helper."""
    if status_class == 'success':
        return STATUS_COLORS['meets']
    elif status_class == 'warning':
        return STATUS_COLORS['partial']
    else:
        return STATUS_COLORS['below']


def _format_eligible_flags_display(diag: dict) -> dict:
    """
    Pre-compute eligible flags display data for template efficiency.
    
    Moves repeated color mapping and flag iteration from template to Python.
    This is a DRY optimization - the same logic was repeated 5+ times in Jinja2.
    
    Flag order: Running → Valid → V2Dir → Fast → Stable → HSDir → Guard → Exit
    (Simple/Common → Complex/Rare: V2Dir is software capability ~100%, before performance metrics)
    
    Returns:
        dict with:
        - flags: list of flag display dicts in correct order (name, count, total, color, tooltip)
        - eligible_count: number of flags with majority (>=5/9)
        - vote_flags: empty list (for backwards compatibility)
    """
    flag_summary = diag.get('flag_summary', {})
    vote_count = diag.get('vote_count', 0)
    total_authorities = diag.get('total_authorities', 9)
    majority_required = diag.get('majority_required', 5)
    
    # Build ordered list of all flags in correct order:
    # Running → Valid → V2Dir → Fast → Stable → HSDir → Guard → Exit
    flags = []
    eligible_count = 0
    
    # Helper to add vote-based flag
    def add_vote_flag(flag_name):
        nonlocal eligible_count
        display_name = 'V2Dir' if flag_name == 'v2dir' else flag_name.capitalize()
        if vote_count >= majority_required:
            eligible_count += 1
        flags.append({
            'name': display_name,
            'key': flag_name,
            'count': vote_count,
            'total': total_authorities,
            'color': STATUS_COLORS['meets'],  # Always green if in consensus
            'tooltip': FLAG_TOOLTIPS.get(flag_name, f'{display_name} flag'),
        })
    
    # Helper to add eligibility-based flag
    def add_eligibility_flag(flag_name):
        nonlocal eligible_count
        flag_data = flag_summary.get(flag_name)
        if flag_data is None:
            return
        display_name = 'HSDir' if flag_name == 'hsdir' else flag_name.capitalize()
        status_color = _get_status_color(flag_data.get('status_class', 'danger'))
        flag_eligible_count = flag_data.get('eligible_count', 0)
        if flag_eligible_count >= majority_required:
            eligible_count += 1
        flags.append({
            'name': display_name,
            'key': flag_name,
            'count': flag_eligible_count,
            'total': flag_data.get('total_authorities', total_authorities),
            'color': status_color,
            'tooltip': FLAG_TOOLTIPS.get(flag_name, f'{display_name} flag'),
        })
    
    # Build flags in order: Running → Valid → V2Dir → Fast → Stable → HSDir → Guard → Exit
    # V2Dir comes before Fast/Stable because it's a software capability (~100%) not performance
    add_vote_flag('running')      # 1. Running (vote-based, basic)
    add_vote_flag('valid')        # 2. Valid (vote-based, basic)
    add_vote_flag('v2dir')        # 3. V2Dir (vote-based, ~100% of relays have it)
    add_eligibility_flag('fast')  # 4. Fast (eligibility-based, performance)
    add_eligibility_flag('stable')# 5. Stable (eligibility-based, performance)
    add_eligibility_flag('hsdir') # 6. HSDir (eligibility-based, requires Fast+Stable)
    add_eligibility_flag('guard') # 7. Guard (eligibility-based, requires Fast+Stable+V2Dir)
    add_eligibility_flag('exit')  # 8. Exit (eligibility-based, policy-based)
    
    return {
        'flags': flags,
        'vote_flags': [],  # Empty for backwards compatibility
        'eligible_count': eligible_count,
        'flag_order': FLAG_ORDER,
    }


def _format_stricter_threshold(strict_auths: list, max_display: str) -> str:
    """Format stricter threshold exception HTML snippet."""
    if not strict_auths:
        return ''
    return f'<br><span style="color: #856404; font-size: 10px;">[Stricter] {", ".join(strict_auths)}: ≥{max_display}</span>'


# Status text lookup (avoid repeated conditionals)
_STATUS_TEXT = {'meets': 'Meets', 'partial': 'Partial', 'below': 'Below'}


def _get_status_text(status: str, extra: str = '', da_count: int = None, da_total: int = None) -> str:
    """Get display text for status with optional DA agreement count and extra info.
    
    Args:
        status: 'meets', 'partial', or 'below'
        extra: Optional suffix (e.g., ' (≥100 KB/s)')
        da_count: Number of authorities that agree relay passes (Option A)
        da_total: Total number of authorities
    """
    base = _STATUS_TEXT.get(status, 'Below')
    if da_count is not None and da_total is not None:
        return f'{base} ({da_count}/{da_total} DA){extra}'
    return f'{base}{extra}'


def _vote_threshold(threshold: str, majority: int, total: int) -> str:
    """Append dynamic vote threshold requirement to a threshold string.
    
    Adds '(≥M/T DA)' showing how many authorities must agree.
    Both majority and total are dynamic from the consensus.
    """
    return f'{threshold} (≥{majority}/{total} DA)'


def _format_da_value_html(stats: dict, source_label: str = 'DA') -> str:
    """Format DA-measured value from stats dict.
    
    Per Tor spec: majority = ≥5/9 authorities agreeing on same value.
    
    First row always shows count of authorities with that EXACT value.
    Second row always shows total voting counts (voting_count/total_possible).
    
    Format when majority exists:
        Majority: **{value}** ({majority_count}/{total_possible} DA)
        Min/Med/Max: {min} / {med} / {max} ({voting_count}/{total_possible})
    
    Format when no majority (fall back to median):
        Median: **{value}** ({median_match_count}/{total_possible} DA, No Majority)
        Min/Max: {min} / {max} ({voting_count}/{total_possible})
    """
    voting_count = stats.get('voting_count', 0)
    total_possible = stats.get('total_possible', 9)
    primary_count = stats.get('primary_count', 0)
    has_majority = stats.get('has_majority', False)
    vote_ratio = f'{voting_count}/{total_possible}'
    
    # Second row clarification text
    vote_clarification = f'({vote_ratio} {source_label}, Voting / Total Eligible)'
    meets_threshold = stats.get('meets_threshold_count')
    
    if has_majority:
        # Majority exists: show value with agreement count (≥5)
        line1 = (f'<span style="color: #666; font-size: 10px;">Majority:</span> '
                 f'<strong>{stats["primary_display"]}</strong> '
                 f'<span style="color: #6c757d; font-size: 10px;">({primary_count}/{total_possible} {source_label})</span>')
        # Second row: Min/Med/Max with total voting ratio and clarification
        if stats.get('has_variation'):
            line2 = (f'<br><span style="color: #666; font-size: 10px;">Min/Med/Max: '
                     f'{stats["min_display"]} / {stats["median_display"]} / {stats["max_display"]} '
                     f'{vote_clarification}</span>')
            return line1 + line2
        return line1
    else:
        # No majority: show median
        # For time metrics with threshold, show "X/9 DA above threshold" instead of "No Majority"
        if meets_threshold is not None:
            threshold_text = f'{meets_threshold}/{total_possible} {source_label} above threshold'
            line1 = (f'<span style="color: #666; font-size: 10px;">Median:</span> '
                     f'<strong>{stats["primary_display"]}</strong> '
                     f'<span style="color: #6c757d; font-size: 10px;">({threshold_text})</span>')
        else:
            line1 = (f'<span style="color: #666; font-size: 10px;">Median:</span> '
                     f'<strong>{stats["primary_display"]}</strong> '
                     f'<span style="color: #6c757d; font-size: 10px;">({primary_count}/{total_possible} {source_label}, No Majority)</span>')
        # Second row: Min/Max with total voting ratio and clarification
        if stats.get('has_variation'):
            line2 = (f'<br><span style="color: #666; font-size: 10px;">Min/Max: '
                     f'{stats["min_display"]} / {stats["max_display"]} '
                     f'{vote_clarification}</span>')
            return line1 + line2
        return line1


def _format_relay_value_html(value_display: str) -> str:
    """Format relay-reported value (single source - the relay itself)."""
    return f'<strong>{value_display}</strong> <span style="color: #6c757d; font-size: 10px;">(R)</span>'


def _majority_status(count: int, required: int) -> str:
    """Get 'meets' or 'below' status based on majority threshold. DRY helper."""
    return 'meets' if count >= required else 'below'


def _make_row(flag: str, flag_tooltip: str, flag_color: str, metric: str, metric_tooltip: str,
              value: str, value_source: str, threshold: str, status: str, 
              status_text: str = None, rowspan: int = 0) -> dict:
    """Build a table row dict with all display values. DRY helper for _format_flag_requirements_table."""
    if status_text is None:
        status_text = _get_status_text(status)
    return {
        'flag': flag,
        'flag_tooltip': flag_tooltip,
        'flag_color': flag_color,
        'metric': metric,
        'metric_tooltip': metric_tooltip,
        'value': value,
        'value_source': value_source,
        'value_source_tooltip': SOURCE_TOOLTIPS.get(value_source, ''),
        'threshold': threshold,
        'status': status,
        'status_text': status_text,
        'status_color': STATUS_COLORS[status],
        'status_tooltip': STATUS_TOOLTIPS[status],
        'rowspan': rowspan,
    }


def _make_prereq_row(parent_flag: str, parent_tooltip: str, parent_color: str,
                     prereq_flag: str, count: int, total: int, majority: int,
                     rowspan: int = 0) -> dict:
    """Build a prerequisite row dict. DRY helper for Guard/HSDir prereq rows."""
    status = _majority_status(count, majority)
    return _make_row(
        flag=parent_flag,
        flag_tooltip=parent_tooltip,
        flag_color=parent_color,
        metric=f'Prereq: {prereq_flag}',
        metric_tooltip=f'{parent_flag} requires the {prereq_flag} flag. Relay must have {prereq_flag} from majority of authorities.',
        value=f'{count}/{total} authorities assigned {prereq_flag} flag',
        value_source='da',
        threshold=_vote_threshold(f'≥{majority}/{total} authorities', majority, total),
        status=status,
        status_text=_get_status_text(status, da_count=count, da_total=total),
        rowspan=rowspan,
    )


def _format_flag_requirements_table(rv: dict, diag: dict) -> list:
    """
    Pre-compute flag requirements table data for template efficiency.
    
    Returns a list of row dictionaries with all display values and colors pre-computed.
    This moves complex Jinja2 conditionals to Python for better performance.
    """
    if not rv or not diag:
        return []
    
    majority_required = diag.get('majority_required', 5)
    total_authorities = diag.get('total_authorities', 9)
    flag_summary = diag.get('flag_summary', {})
    
    def get_flag_color(flag_name: str) -> str:
        """Get color for flag column based on eligibility status."""
        status_class = flag_summary.get(flag_name.lower(), {}).get('status_class', 'danger')
        return STATUS_COLORS.get(_STATUS_CLASS_TO_KEY.get(status_class, 'below'), STATUS_COLORS['below'])
    
    rows = []
    
    # Pre-fetch stats dicts for cleaner code
    wfu_stats = rv.get('wfu_stats', _EMPTY_DA_STATS)
    tk_stats = rv.get('tk_stats', _EMPTY_DA_STATS)
    mtbf_stats = rv.get('mtbf_stats', _EMPTY_DA_STATS)
    
    # ========== FLAG ORDER: Running → Valid → V2Dir → Fast → Stable → HSDir → Guard → Exit ==========
    # Matches Eligible Flags horizontal row order.
    # Most common/basic flags first, then performance, then flags with dependencies.
    
    # ========== Running flag (1-2 rows) ==========
    # Per dir-spec: Running = authority successfully connected within last 45 minutes.
    # Row 1 (always): IPv4 reachability
    # Row 2 (conditional): IPv6 reachability (only if relay has IPv6)
    running_tooltip = FLAG_TOOLTIPS['running']
    running_ipv4 = rv.get('running_ipv4_count', 0)
    running_has_ipv6 = rv.get('running_has_ipv6', False)
    running_ipv6 = rv.get('running_ipv6_count', 0)
    running_ipv6_tested = rv.get('running_ipv6_tested', 0)
    
    running_rowspan = 2 if running_has_ipv6 else 1
    ipv4_status = _majority_status(running_ipv4, majority_required)
    running_color = STATUS_COLORS[ipv4_status]
    
    rows.append(_make_row(
        'Running', running_tooltip, running_color,
        'IPv4 Reachability', METRIC_TOOLTIPS.get('running_ipv4', ''),
        f'{running_ipv4}/{total_authorities} authorities reached relay',
        'da',
        _vote_threshold(f'≥{majority_required}/{total_authorities} (majority)', majority_required, total_authorities),
        ipv4_status,
        _get_status_text(ipv4_status, da_count=running_ipv4, da_total=total_authorities),
        rowspan=running_rowspan,
    ))
    
    if running_has_ipv6:
        ipv6_majority = (running_ipv6_tested // 2) + 1 if running_ipv6_tested > 0 else 1
        ipv6_status = 'meets' if running_ipv6 >= ipv6_majority else ('partial' if running_ipv6 > 0 else 'below')
        ipv6_threshold = f'≥{ipv6_majority}/{running_ipv6_tested} tested (majority)' if running_ipv6_tested > 0 else 'No authorities test IPv6'
        rows.append(_make_row(
            'Running', running_tooltip, running_color,
            'IPv6 Reachability', METRIC_TOOLTIPS.get('running_ipv6', ''),
            f'{running_ipv6}/{running_ipv6_tested} tested authorities reached relay',
            'da',
            _vote_threshold(ipv6_threshold, ipv6_majority if running_ipv6_tested > 0 else 0, running_ipv6_tested),
            ipv6_status,
            _get_status_text(ipv6_status, da_count=running_ipv6, da_total=running_ipv6_tested),
        ))
    
    # ========== Valid flag (1 row) ==========
    # Per dir-spec: Valid = not blacklisted + valid descriptor + non-broken Tor version.
    # We display the version check (the actionable part for operators).
    valid_tooltip = FLAG_TOOLTIPS['valid']
    valid_recommended = rv.get('valid_recommended')
    valid_display = rv.get('valid_version_display', 'Unknown')
    valid_da_count = diag.get('vote_count', 0)
    
    if valid_recommended is True:
        valid_status = 'meets'
        valid_extra = ''
    elif valid_recommended is False:
        valid_status = 'below'
        valid_extra = ' (not recommended)'
    else:
        valid_status = 'partial'
        valid_extra = ' (unknown)'
    valid_color = STATUS_COLORS[valid_status]
    
    rows.append(_make_row(
        'Valid', valid_tooltip, valid_color,
        'Tor Version', METRIC_TOOLTIPS.get('version_valid', ''),
        _format_relay_value_html(valid_display),
        'relay',
        _vote_threshold('Version approved by Directory Authorities', majority_required, total_authorities),
        valid_status,
        _get_status_text(valid_status, valid_extra, da_count=valid_da_count, da_total=total_authorities),
        rowspan=1,
    ))
    
    # ========== V2Dir flag (1 row) ==========
    # Per dir-spec: V2Dir = DirPort OR tunnelled-dir-server.
    # Required for Guard flag. Most modern relays have V2Dir automatically.
    v2dir_tooltip = FLAG_TOOLTIPS['v2dir']
    v2dir_has_flag = rv.get('v2dir_has_flag', False)
    v2dir_display = rv.get('v2dir_display', 'Unknown')
    
    v2dir_status = 'meets' if v2dir_has_flag else 'below'
    v2dir_color = STATUS_COLORS[v2dir_status]
    v2dir_da_count = rv.get('guard_prereq_v2dir_count', 0)
    
    rows.append(_make_row(
        'V2Dir', v2dir_tooltip, v2dir_color,
        'Dir Capability', METRIC_TOOLTIPS.get('v2dir_capability', ''),
        _format_relay_value_html(v2dir_display),
        'relay',
        _vote_threshold('Tunnelled directory via ORPort or DirPort', majority_required, total_authorities),
        v2dir_status,
        _get_status_text(v2dir_status, da_count=v2dir_da_count, da_total=total_authorities),
        rowspan=1,
    ))
    
    # Fast flag (1 row) - using DRY helper
    fast_color = get_flag_color('fast')
    fast_da_count = rv.get('fast_meets_count', 0)
    if rv.get('fast_meets_minimum'):
        fast_status, fast_extra = 'meets', ''
    elif rv.get('fast_meets_all'):
        fast_status, fast_extra = 'meets', ''
    elif fast_da_count > 0:
        fast_status, fast_extra = 'partial', ''
    else:
        fast_status, fast_extra = 'below', ''
    fast_threshold = (_vote_threshold(f"≥{rv.get('fast_minimum_display', '100 KB/s')} (guarantee) OR top 7/8", majority_required, total_authorities)
        + _format_stricter_threshold(rv.get('fast_speed_strict_auths', []), rv.get('fast_speed_max_display', '')))
    rows.append(_make_row('Fast', FLAG_TOOLTIPS['fast'], fast_color, 'Speed', METRIC_TOOLTIPS['speed_fast'],
                          _format_relay_value_html(rv.get('fast_speed_display', 'N/A')), 'relay',
                          fast_threshold, fast_status,
                          _get_status_text(fast_status, fast_extra, da_count=fast_da_count, da_total=total_authorities),
                          rowspan=1))
    
    # Stable flag (2 rows) - using DRY helper
    stable_color = get_flag_color('stable')
    stable_tooltip = FLAG_TOOLTIPS['stable']
    mtbf_meets_count = rv.get('stable_mtbf_meets_count', 0)
    mtbf_status = 'meets' if rv.get('stable_mtbf_meets_all') else ('partial' if mtbf_meets_count >= majority_required else 'below')
    mtbf_threshold = (_vote_threshold(f"≥{rv.get('stable_mtbf_min_display', 'N/A')} - {rv.get('stable_mtbf_typical_display', 'N/A')} (varies)", majority_required, total_authorities)
        + _format_stricter_threshold(rv.get('stable_mtbf_strict_auths', []), rv.get('stable_mtbf_max_display', '')))
    rows.append(_make_row('Stable', stable_tooltip, stable_color, 'MTBF', METRIC_TOOLTIPS['mtbf_stable'],
                          _format_da_value_html(mtbf_stats), 'da', mtbf_threshold, mtbf_status,
                          _get_status_text(mtbf_status, da_count=mtbf_meets_count, da_total=total_authorities),
                          rowspan=2))
    
    # Stable Row 2: Uptime - using DRY helper
    uptime_meets_count = rv.get('stable_uptime_meets_count', 0)
    if rv.get('stable_uptime') is None:
        uptime_status = 'below'
    elif rv.get('stable_uptime_meets_all'):
        uptime_status = 'meets'
    elif uptime_meets_count >= majority_required:
        uptime_status = 'partial'
    else:
        uptime_status = 'below'
    uptime_threshold = (_vote_threshold(f"≥{rv.get('stable_uptime_min_display', 'N/A')} - {rv.get('stable_uptime_typical_display', 'N/A')} (varies)", majority_required, total_authorities)
        + _format_stricter_threshold(rv.get('stable_uptime_strict_auths', []), rv.get('stable_uptime_max_display', '')))
    rows.append(_make_row('Stable', stable_tooltip, stable_color, 'Uptime', METRIC_TOOLTIPS['uptime_stable'],
                          _format_relay_value_html(rv.get('stable_uptime_display', 'N/A')), 'relay',
                          uptime_threshold, uptime_status,
                          _get_status_text(uptime_status, da_count=uptime_meets_count, da_total=total_authorities)))
    
    # HSDir flag (4 rows: 2 prereqs + 2 metrics)
    # Per Tor dir-spec: HSDir requires Stable and Fast flags (2 deps)
    hsdir_color = get_flag_color('hsdir')
    hsdir_tooltip = FLAG_TOOLTIPS['hsdir']
    hsdir_prereq_stable = rv.get('hsdir_prereq_stable_count', 0)
    hsdir_prereq_fast = rv.get('hsdir_prereq_fast_count', 0)
    
    # Row 1-2: Prerequisites (using DRY helper)
    rows.append(_make_prereq_row('HSDir', hsdir_tooltip, hsdir_color, 'Stable', 
                                  hsdir_prereq_stable, total_authorities, majority_required, rowspan=4))
    rows.append(_make_prereq_row('HSDir', hsdir_tooltip, hsdir_color, 'Fast',
                                  hsdir_prereq_fast, total_authorities, majority_required))
    
    # Row 3: WFU (using DRY helper)
    hsdir_wfu_status = 'meets' if rv.get('hsdir_wfu_meets') else 'below'
    hsdir_wfu_da_count = wfu_stats.get('meets_threshold_count', 0) or 0
    rows.append(_make_row('HSDir', hsdir_tooltip, hsdir_color, 'WFU', METRIC_TOOLTIPS['wfu_hsdir'],
                          _format_da_value_html(wfu_stats), 'da',
                          _vote_threshold(f"≥{rv.get('hsdir_wfu_threshold', 0.98) * 100:.1f}%", majority_required, total_authorities),
                          hsdir_wfu_status,
                          _get_status_text(hsdir_wfu_status, da_count=hsdir_wfu_da_count, da_total=total_authorities)))
    
    # Row 4: Time Known (using DRY helper)
    hsdir_tk_status = 'meets' if rv.get('hsdir_tk_meets') else 'below'
    hsdir_tk_da_count = tk_stats.get('meets_threshold_count', 0) or 0
    hsdir_tk_threshold = (_vote_threshold(f"≥{rv.get('hsdir_tk_consensus_display', '25h')} (most)", majority_required, total_authorities)
        + _format_stricter_threshold(rv.get('hsdir_tk_strict_auths', []), rv.get('hsdir_tk_max_display', '10d')))
    rows.append(_make_row('HSDir', hsdir_tooltip, hsdir_color, 'Time Known', METRIC_TOOLTIPS['tk_hsdir'],
                          _format_da_value_html(tk_stats), 'da', hsdir_tk_threshold, hsdir_tk_status,
                          _get_status_text(hsdir_tk_status, da_count=hsdir_tk_da_count, da_total=total_authorities)))
    
    # Guard flag (6 rows: 3 prereqs + 3 metrics)
    # Per Tor dir-spec: Guard requires Fast, Stable, and V2Dir flags (3 deps)
    guard_color = get_flag_color('guard')
    guard_tooltip = FLAG_TOOLTIPS['guard']
    guard_prereq_fast = rv.get('guard_prereq_fast_count', 0)
    guard_prereq_stable = rv.get('guard_prereq_stable_count', 0)
    guard_prereq_v2dir = rv.get('guard_prereq_v2dir_count', 0)
    
    # Row 1-3: Prerequisites (using DRY helper)
    rows.append(_make_prereq_row('Guard', guard_tooltip, guard_color, 'Fast',
                                  guard_prereq_fast, total_authorities, majority_required, rowspan=6))
    rows.append(_make_prereq_row('Guard', guard_tooltip, guard_color, 'Stable',
                                  guard_prereq_stable, total_authorities, majority_required))
    rows.append(_make_prereq_row('Guard', guard_tooltip, guard_color, 'V2Dir',
                                  guard_prereq_v2dir, total_authorities, majority_required))
    
    # Row 4: WFU (using DRY helper)
    wfu_status = 'meets' if rv.get('wfu_meets') else 'below'
    guard_wfu_da_count = wfu_stats.get('meets_threshold_count', 0) or 0
    rows.append(_make_row('Guard', guard_tooltip, guard_color, 'WFU', METRIC_TOOLTIPS['wfu_guard'],
                          _format_da_value_html(wfu_stats), 'da',
                          _vote_threshold('≥98%', majority_required, total_authorities),
                          wfu_status,
                          _get_status_text(wfu_status, da_count=guard_wfu_da_count, da_total=total_authorities)))
    
    # Row 5: Time Known (using DRY helper)
    tk_status = 'meets' if rv.get('tk_meets') else 'below'
    tk_extra = f" (need {rv['tk_days_needed']:.1f} more days)" if not rv.get('tk_meets') and rv.get('tk_days_needed', 0) > 0 else ''
    guard_tk_da_count = tk_stats.get('meets_threshold_count', 0) or 0
    rows.append(_make_row('Guard', guard_tooltip, guard_color, 'Time Known', METRIC_TOOLTIPS['tk_guard'],
                          _format_da_value_html(tk_stats), 'da',
                          _vote_threshold('≥8 days', majority_required, total_authorities),
                          tk_status,
                          _get_status_text(tk_status, tk_extra if tk_status != 'meets' else '',
                                           da_count=guard_tk_da_count, da_total=total_authorities)))
    
    # Row 6: Bandwidth (using DRY helper)
    guard_bw_da_count = rv.get('guard_bw_meets_count', 0)
    if rv.get('guard_bw_meets_guarantee'):
        bw_status, bw_extra = 'meets', ''
    elif rv.get('guard_bw_meets_some'):
        bw_status, bw_extra = 'partial', ''
    else:
        bw_status, bw_extra = 'below', ''
    bw_threshold = _vote_threshold(
        f"≥{rv.get('guard_bw_guarantee_display', '2 MB/s')} OR ≥{rv.get('guard_bw_range', 'top 25%')}",
        majority_required, total_authorities)
    rows.append(_make_row('Guard', guard_tooltip, guard_color, 'Bandwidth', METRIC_TOOLTIPS['bw_guard'],
                          _format_relay_value_html(rv.get('observed_bw_display', 'N/A')), 'relay',
                          bw_threshold, bw_status,
                          _get_status_text(bw_status, bw_extra, da_count=guard_bw_da_count, da_total=total_authorities)))
    
    # ========== Exit flag (1 row) ==========
    # Per Tor dir-spec Section 3.4.2: Exit requires allowing exits to ≥1 /8
    # address space on ports 80 AND 443. Unlike Guard (6 rows with prereqs + metrics),
    # Exit has 1 row (policy-based, no numeric thresholds).
    exit_color = get_flag_color('exit')
    exit_tooltip = FLAG_TOOLTIPS['exit']
    
    exit_allows_80 = rv.get('exit_allows_80', False)
    exit_allows_443 = rv.get('exit_allows_443', False)
    exit_eligible = rv.get('exit_eligible', False)
    
    exit_da_count = rv.get('exit_assigned_count', 0)
    if exit_eligible and exit_da_count >= majority_required:
        exit_status = 'meets'
        exit_extra = ''
    elif exit_eligible and exit_da_count > 0:
        exit_status = 'partial'
        exit_extra = ''
    elif exit_allows_80 or exit_allows_443:
        exit_status = 'partial'
        port = '80' if exit_allows_80 else '443'
        exit_extra = f' (only port {port})'
    else:
        exit_status = 'below'
        exit_extra = ''
    
    rows.append(_make_row(
        'Exit', exit_tooltip, exit_color,
        'Exit Policy', METRIC_TOOLTIPS['policy_exit'],
        _format_relay_value_html(rv.get('exit_policy_display', 'N/A')),
        'relay',
        _vote_threshold('Allows ≥1 /8 on ports 80 AND 443', majority_required, total_authorities),
        exit_status,
        _get_status_text(exit_status, exit_extra, da_count=exit_da_count, da_total=total_authorities),
        rowspan=1,
    ))
    
    # ========== MiddleOnly flag (0-1 rows, conditional) ==========
    # Per dir-spec: MiddleOnly restricts relay to middle position only.
    # Effects: removes Exit, Guard, HSDir, V2Dir; adds BadExit.
    # Only shown when relay is flagged — hidden for 99.9% of relays.
    middleonly_flagged = rv.get('middleonly_flagged', False)
    middleonly_count = rv.get('middleonly_count', 0)
    
    if middleonly_flagged:
        rows.append(_make_row(
            'MiddleOnly', FLAG_TOOLTIPS['middleonly'], STATUS_COLORS['below'],
            'Restriction (by DA)', METRIC_TOOLTIPS['middleonly'],
            f'{middleonly_count}/{total_authorities} authorities assigned MiddleOnly',
            'da',
            'Suspicious behavior, Sybil risk, or policy violation',
            'below',
            f'Flagged ({middleonly_count}/{total_authorities} DA)',
            rowspan=1,
        ))
    
    # ========== BadExit flag (0-1 rows, conditional) ==========
    # Per dir-spec: BadExit marks misbehaving exit nodes.
    # Also assigned automatically when MiddleOnly is set.
    # Only shown when relay is flagged — hidden for most relays.
    badexit_flagged = rv.get('badexit_flagged', False)
    badexit_count = rv.get('badexit_count', 0)
    
    if badexit_flagged:
        rows.append(_make_row(
            'BadExit', FLAG_TOOLTIPS['badexit'], STATUS_COLORS['below'],
            'Exit Blacklist (by DA)', METRIC_TOOLTIPS['badexit'],
            f'{badexit_count}/{total_authorities} authorities assigned BadExit',
            'da',
            'Traffic manipulation, SSL stripping, or policy violation',
            'below',
            f'Flagged ({badexit_count}/{total_authorities} DA)',
            rowspan=1,
        ))
    
    return rows


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
    
    Shows ACTUAL flag assignments from authorities (not calculated potential eligibility).
    This ensures consistency with the Per-Authority Details table.
    
    Args:
        consensus_data: Raw consensus evaluation data
        observed_bandwidth: Relay's actual observed bandwidth (unused, kept for API compatibility)
    """
    flag_eligibility = consensus_data.get('flag_eligibility', {})
    total_authorities = consensus_data.get('total_authorities', get_voting_authority_count())
    
    summary = {}
    
    # Process flags in order: simple/common → complex/rare
    # Exit and MiddleOnly added to match collector_fetcher._analyze_flag_eligibility()
    for flag_name in ['fast', 'stable', 'hsdir', 'guard', 'exit', 'middleonly', 'badexit']:
        flag_data = flag_eligibility.get(flag_name, {})
        
        # Use assigned_count (actual flag assignments) instead of eligible_count (calculated)
        # This ensures "Eligible Flags" matches the Per-Authority Details table
        eligible_count = flag_data.get('assigned_count', flag_data.get('eligible_count', 0))
        
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
    
    # Calculate IPv6 tested total with reliability check
    # The ipv6_not_tested_authorities list may be unreliable (populated incorrectly)
    # Only trust it if it's small (<=2 authorities don't test IPv6 in practice)
    if len(ipv6_not_tested) <= 2:
        ipv6_tested_total = total - len(ipv6_not_tested)
    else:
        # Data is unreliable - don't show misleading counts
        # Set to 0 to hide the IPv6 section in templates
        ipv6_tested_total = 0
    
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
            'total': ipv6_tested_total,  # Only those who test (0 if unreliable)
            'display': f"{ipv6_count}/{ipv6_tested_total} authorities can reach IPv6" if ipv6_tested_total > 0 else "N/A",
            'status_class': 'success' if ipv6_count > 0 else ('muted' if ipv6_tested_total > 0 else 'muted'),
            'authorities': reachability.get('ipv6_reachable_authorities', []),
            'not_tested': ipv6_not_tested if len(ipv6_not_tested) <= 2 else [],  # Hide if unreliable
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
    
    # Pre-compute median display components for template efficiency
    median_display = _format_bandwidth_value(median, use_bits)
    median_int = None
    median_unit = None
    if median_display and median_display != 'N/A':
        parts = median_display.split(' ', 1)
        if len(parts) == 2:
            try:
                median_int = int(float(parts[0]))
                median_unit = parts[1]
            except (ValueError, TypeError):
                pass
    
    # Pre-compute BW authority color coding for template efficiency
    bw_auth_measured = bandwidth.get('bw_auth_measured_count', 0)
    bw_auth_total = bandwidth.get('bw_auth_total', 0)
    bw_auth_majority = (bw_auth_total // 2) + 1 if bw_auth_total > 0 else 0
    
    # Color logic: green for majority, yellow for 3 to <majority, red for 0-2
    if bw_auth_measured >= bw_auth_majority:
        bw_auth_color = '#28a745'  # green
    elif bw_auth_measured >= 3:
        bw_auth_color = '#856404'  # yellow
    else:
        bw_auth_color = '#dc3545'  # red
    
    return {
        'median': median,
        'median_display': median_display,
        'median_int': median_int,      # Pre-computed integer for template
        'median_unit': median_unit,    # Pre-computed unit for template
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
        # BW authority measurement data with pre-computed values
        'bw_auth_measured_count': bw_auth_measured,
        'bw_auth_total': bw_auth_total,
        'bw_auth_majority': bw_auth_majority,  # Pre-computed for template
        'bw_auth_color': bw_auth_color,        # Pre-computed for template
    }


def _identify_issues(consensus_data: dict, current_flags: list = None, observed_bandwidth: int = 0, version: str = None, recommended_version: bool = None) -> List[dict]:
    """
    Identify issues that may affect relay status.
    
    BACKWARD COMPATIBILITY: This function is kept for existing callers and tests.
    Implementation has been moved to relay_diagnostics.generate_issues_from_consensus().
    
    Note: This wrapper maintains the original behavior. The new implementation in
    relay_diagnostics.py has updated severity levels (6 issues changed from 'info' 
    to 'warning'), but this wrapper preserves the original severities for backward
    compatibility with existing tests.
    
    Based on Tor dir-spec (https://spec.torproject.org/dir-spec/) and
    common issues from tor-relays mailing list.
    
    Args:
        consensus_data: Raw consensus evaluation data
        current_flags: Relay's current flags (from Onionoo)
        observed_bandwidth: Relay's observed bandwidth for Guard eligibility
        version: Tor version string running on the relay
        recommended_version: Whether the version is recommended
    
    Returns:
        List of issue dicts with: severity, category, title, description, suggestion
    """
    if _generate_issues_impl is not None:
        return _generate_issues_impl(
            consensus_data, current_flags, observed_bandwidth,
            version, recommended_version
        )
    # Fallback: import here only if module-level import failed
    from ..relay_diagnostics import generate_issues_from_consensus
    return generate_issues_from_consensus(
        consensus_data, current_flags, observed_bandwidth,
        version, recommended_version
    )


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
