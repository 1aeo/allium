"""
File: flag_thresholds.py

Centralized module for Tor relay flag threshold constants and eligibility logic.
This module consolidates all flag-related thresholds and classification functions
for easy auditing and consistent behavior across the codebase.

Reference: https://spec.torproject.org/dir-spec/

Flag Requirements Summary:
-------------------------
Guard:
  - Must be Fast
  - Must be Stable  
  - WFU >= guard-wfu threshold (typically 98%)
  - TK >= guard-tk threshold (typically 8 days)
  - Bandwidth >= 2 MB/s (AuthDirGuardBWGuarantee) OR in top 25%
  - Must have V2Dir flag

Stable:
  - Uptime >= stable-uptime threshold OR
  - MTBF >= stable-mtbf threshold

Fast:
  - Bandwidth in top 7/8ths of relays OR >= 100 KB/s (AuthDirFastGuarantee)

HSDir:
  - WFU >= hsdir-wfu threshold (typically 98%)
  - TK >= hsdir-tk threshold (typically 25+ hours in practice)
"""

from typing import Dict, Optional, Any

# ============================================================================
# TIME CONSTANTS
# ============================================================================
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400
SECONDS_PER_WEEK = 604800

# ============================================================================
# GUARD FLAG THRESHOLDS
# ============================================================================

# AuthDirGuardBWGuarantee: Minimum bandwidth for Guard flag (2 MB/s)
# If a relay has at least this bandwidth, it meets the BW requirement for Guard
# regardless of network percentile ranking
GUARD_BW_GUARANTEE = 2_000_000  # bytes/second (2 MB/s)

# Default Guard time-known (TK) threshold: 8 days
# Relay must have been known to the authority for at least this long
GUARD_TK_DEFAULT = 8 * SECONDS_PER_DAY  # 691200 seconds

# Default Guard weighted fractional uptime (WFU) threshold: 98%
# Relay must have been running at least this fraction of the time
GUARD_WFU_DEFAULT = 0.98

# ============================================================================
# HSDIR FLAG THRESHOLDS
# ============================================================================

# Default HSDir time-known (TK) threshold: 10 days
# More strict than Guard to ensure HSDir relays are well-established
HSDIR_TK_DEFAULT = 10 * SECONDS_PER_DAY  # 864000 seconds

# Default HSDir weighted fractional uptime (WFU) threshold: 98%
HSDIR_WFU_DEFAULT = 0.98

# ============================================================================
# FAST FLAG THRESHOLDS
# ============================================================================

# AuthDirFastGuarantee: Minimum bandwidth for Fast flag (100 KB/s)
# Relays with at least this bandwidth get Fast even if not in top 7/8ths
FAST_BW_GUARANTEE = 100_000  # bytes/second (100 KB/s)

# ============================================================================
# STABLE FLAG THRESHOLDS
# ============================================================================

# No fixed defaults - determined dynamically by authorities based on network
# These are set per-authority in their flag-thresholds vote lines:
#   stable-uptime=<seconds>
#   stable-mtbf=<seconds>

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def parse_wfu_threshold(value: Any) -> Optional[float]:
    """
    Parse WFU (Weighted Fractional Uptime) threshold value.
    
    Can handle:
    - Float fraction (0.98)
    - String percentage ('98%')
    - String fraction ('0.98')
    
    Args:
        value: WFU value to parse
        
    Returns:
        Float between 0 and 1, or None if invalid
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        value = value.strip()
        if value.endswith('%'):
            try:
                return float(value[:-1]) / 100.0
            except ValueError:
                return None
        try:
            return float(value)
        except ValueError:
            return None
    return None


def format_time_as_days(seconds: Optional[float], decimals: int = 1) -> str:
    """
    Format seconds as days for display.
    
    Args:
        seconds: Time in seconds
        decimals: Number of decimal places
        
    Returns:
        Formatted string like "8.0d" or "N/A"
    """
    if seconds is None:
        return 'N/A'
    days = seconds / SECONDS_PER_DAY
    return f"{days:.{decimals}f}d"


def format_wfu_as_percent(wfu: Optional[float], decimals: int = 1) -> str:
    """
    Format WFU fraction as percentage for display.
    
    Args:
        wfu: WFU value between 0 and 1
        decimals: Number of decimal places
        
    Returns:
        Formatted string like "98.0%" or "N/A"
    """
    if wfu is None:
        return 'N/A'
    return f"{wfu * 100:.{decimals}f}%"


def check_guard_eligibility(
    wfu: Optional[float],
    tk: Optional[float],
    bandwidth: Optional[int],
    wfu_threshold: float = GUARD_WFU_DEFAULT,
    tk_threshold: float = GUARD_TK_DEFAULT,
    bw_top25_threshold: int = 0
) -> Dict[str, Any]:
    """
    Check if a relay meets Guard flag eligibility requirements.
    
    Per Tor dir-spec, Guard requires:
    - WFU >= guard-wfu threshold (typically 98%)
    - TK >= guard-tk threshold (typically 8 days)
    - Bandwidth >= 2 MB/s OR in top 25% of relays
    
    Args:
        wfu: Relay's weighted fractional uptime
        tk: Relay's time-known in seconds
        bandwidth: Relay's observed bandwidth in bytes/second
        wfu_threshold: WFU threshold from authority
        tk_threshold: TK threshold from authority
        bw_top25_threshold: Top 25% bandwidth cutoff from authority
        
    Returns:
        Dict with eligibility details
    """
    wfu = wfu or 0
    tk = tk or 0
    bandwidth = bandwidth or 0
    
    wfu_met = wfu >= wfu_threshold
    tk_met = tk >= tk_threshold
    bw_meets_guarantee = bandwidth >= GUARD_BW_GUARANTEE
    bw_in_top25 = bandwidth >= bw_top25_threshold if bw_top25_threshold > 0 else False
    bw_eligible = bw_meets_guarantee or bw_in_top25
    
    eligible = wfu_met and tk_met and bw_eligible
    
    return {
        'eligible': eligible,
        'wfu_value': wfu,
        'wfu_threshold': wfu_threshold,
        'wfu_met': wfu_met,
        'tk_value': tk,
        'tk_threshold': tk_threshold,
        'tk_met': tk_met,
        'bw_value': bandwidth,
        'bw_guarantee': GUARD_BW_GUARANTEE,
        'bw_top25_threshold': bw_top25_threshold,
        'bw_meets_guarantee': bw_meets_guarantee,
        'bw_in_top25': bw_in_top25,
        'bw_eligible': bw_eligible,
    }


def check_hsdir_eligibility(
    wfu: Optional[float],
    tk: Optional[float],
    wfu_threshold: float = HSDIR_WFU_DEFAULT,
    tk_threshold: float = HSDIR_TK_DEFAULT
) -> Dict[str, Any]:
    """
    Check if a relay meets HSDir flag eligibility requirements.
    
    HSDir requires:
    - WFU >= hsdir-wfu threshold
    - TK >= hsdir-tk threshold
    
    Args:
        wfu: Relay's weighted fractional uptime
        tk: Relay's time-known in seconds
        wfu_threshold: WFU threshold from authority
        tk_threshold: TK threshold from authority
        
    Returns:
        Dict with eligibility details
    """
    wfu = wfu or 0
    tk = tk or 0
    
    wfu_met = wfu >= wfu_threshold
    tk_met = tk >= tk_threshold
    eligible = wfu_met and tk_met
    
    return {
        'eligible': eligible,
        'wfu_value': wfu,
        'wfu_threshold': wfu_threshold,
        'wfu_met': wfu_met,
        'tk_value': tk,
        'tk_threshold': tk_threshold,
        'tk_met': tk_met,
    }


def check_fast_eligibility(
    bandwidth: Optional[int],
    fast_threshold: int = 0
) -> Dict[str, Any]:
    """
    Check if a relay meets Fast flag eligibility requirements.
    
    Fast requires:
    - Bandwidth in top 7/8ths of relays OR >= 100 KB/s (AuthDirFastGuarantee)
    
    Args:
        bandwidth: Relay's measured bandwidth in bytes/second
        fast_threshold: Top 7/8ths bandwidth cutoff from authority
        
    Returns:
        Dict with eligibility details
    """
    bandwidth = bandwidth or 0
    
    meets_guarantee = bandwidth >= FAST_BW_GUARANTEE
    meets_threshold = bandwidth >= fast_threshold if fast_threshold > 0 else False
    eligible = meets_guarantee or meets_threshold
    
    return {
        'eligible': eligible,
        'bw_value': bandwidth,
        'bw_guarantee': FAST_BW_GUARANTEE,
        'fast_threshold': fast_threshold,
        'meets_guarantee': meets_guarantee,
        'meets_threshold': meets_threshold,
    }


def check_stable_eligibility(
    uptime: Optional[float],
    mtbf: Optional[float],
    uptime_threshold: float = 0,
    mtbf_threshold: float = 0
) -> Dict[str, Any]:
    """
    Check if a relay meets Stable flag eligibility requirements.
    
    Stable requires:
    - Uptime >= stable-uptime threshold OR
    - MTBF >= stable-mtbf threshold
    
    Args:
        uptime: Relay's uptime in seconds
        mtbf: Relay's mean time between failures in seconds
        uptime_threshold: Uptime threshold from authority
        mtbf_threshold: MTBF threshold from authority
        
    Returns:
        Dict with eligibility details
    """
    uptime = uptime or 0
    mtbf = mtbf or 0
    
    uptime_met = uptime >= uptime_threshold if uptime_threshold > 0 else False
    mtbf_met = mtbf >= mtbf_threshold if mtbf_threshold > 0 else False
    eligible = uptime_met or mtbf_met
    
    return {
        'eligible': eligible,
        'uptime_value': uptime,
        'uptime_threshold': uptime_threshold,
        'uptime_met': uptime_met,
        'mtbf_value': mtbf,
        'mtbf_threshold': mtbf_threshold,
        'mtbf_met': mtbf_met,
    }


def get_flag_thresholds_summary(thresholds: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and normalize flag thresholds from an authority's vote.
    
    Args:
        thresholds: Raw flag-thresholds dict from authority vote
        
    Returns:
        Normalized dict with all threshold values
    """
    return {
        # Guard thresholds
        'guard_wfu': parse_wfu_threshold(thresholds.get('guard-wfu')) or GUARD_WFU_DEFAULT,
        'guard_tk': thresholds.get('guard-tk', GUARD_TK_DEFAULT),
        'guard_bw_inc_exits': thresholds.get('guard-bw-inc-exits', 0),  # Top 25% cutoff
        
        # HSDir thresholds
        'hsdir_wfu': parse_wfu_threshold(thresholds.get('hsdir-wfu')) or HSDIR_WFU_DEFAULT,
        'hsdir_tk': thresholds.get('hsdir-tk', HSDIR_TK_DEFAULT),
        
        # Stable thresholds
        'stable_uptime': thresholds.get('stable-uptime', 0),
        'stable_mtbf': thresholds.get('stable-mtbf', 0),
        
        # Fast threshold
        'fast_speed': thresholds.get('fast-speed', 0),
        
        # Additional thresholds
        'enough_mtbf': thresholds.get('enough-mtbf', 0),
        'min_bw_fr': thresholds.get('min-bw-for-running', 0),
    }


# ============================================================================
# CANONICAL FLAG ORDERING
# ============================================================================

# Canonical flag order for consistent display across all relay pages
# Authority flag first, then alphabetical order for common flags
FLAG_ORDER = [
    'Authority',  # Special: directory authority
    'BadExit',    # Flagged as misbehaving exit
    'Exit',       # Can be used as exit node
    'Fast',       # Bandwidth in top 7/8ths or >= 100 KB/s
    'Guard',      # Can be used as guard node
    'HSDir',      # Hidden service directory
    'Running',    # Relay is reachable
    'Stable',     # Sufficient uptime/MTBF
    'StaleDesc',  # Descriptor is old
    'V2Dir',      # Supports directory protocol v2+
    'Valid',      # Verified, allowed in network
]

# O(1) lookup for flag ordering
FLAG_ORDER_MAP = {flag: idx for idx, flag in enumerate(FLAG_ORDER)}


def sort_flags(flags: list) -> list:
    """
    Sort flags in canonical order for consistent display.
    
    Args:
        flags: List of flag names
        
    Returns:
        Sorted list of flags
    """
    if not flags:
        return []
    return sorted(flags, key=lambda f: (FLAG_ORDER_MAP.get(f, 999), f))
