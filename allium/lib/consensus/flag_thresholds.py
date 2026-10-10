"""
File: flag_thresholds.py

Centralized module for Tor relay flag threshold constants and eligibility logic.
This module consolidates all flag-related thresholds and classification functions
for easy auditing and consistent behavior across the codebase.

Authoritative Reference: https://spec.torproject.org/dir-spec/
Section 3.4.2 - "Assigning flags to relays"

Flag Requirements per dir-spec Section 3.4.2:
=============================================

Guard (all must be true):
  - Relay is "Fast" (has bandwidth in top 7/8ths or >= AuthDirFastGuarantee)
  - Relay is "Stable" (uptime/MTBF meets threshold)
  - Relay is "Valid" (not blacklisted)
  - WFU >= guard-wfu threshold
    * Default: 0.98 (98%) per dir-spec "WFU" parameter
  - TK (Time Known) >= guard-tk threshold  
    * Default: 8 days (691200 seconds) per dir-spec "TK" parameter
  - Bandwidth >= AuthDirGuardBWGuarantee OR in fastest 25% of network
    * AuthDirGuardBWGuarantee default: "2 MB" = 2,097,152 bytes, compared
      by tor as 2097 KB/s (voteflags.c: routerbw_kb >= bw_opt / 1000)
  - Has "V2Dir" flag

Bandwidth used for Fast and Guard (tor bwauth.c dirserv_get_credible_bandwidth_kb):
  - The authority's bandwidth-scanner measurement (vote "Measured=") if it has one
  - Otherwise the relay's advertised bandwidth (vote "Bandwidth="), unless the
    authority has measurements for enough relays (ignoring-advertised-bws=1),
    in which case an unmeasured relay counts as 0

Stable:
  - Weighted MTBF >= median network MTBF, OR
  - Uptime >= stable-uptime threshold (dynamically computed per authority)

Fast:
  - Bandwidth in top 7/8ths of network, OR
  - Bandwidth >= AuthDirFastGuarantee
    * Default: "100 KB" = 102,400 bytes; tor caps the Fast threshold at
      102 KB/s, which votes publish as fast-speed=102000

HSDir:
  - Has "Stable" flag
  - Has "Running" flag  
  - WFU >= hsdir-wfu threshold (dir-spec default: same as guard-wfu, 0.98)
  - TK >= hsdir-tk threshold
    * dir-spec default: 25 hours (90,000 seconds)
    * NOTE: In practice, moria1 uses ~10 days; most authorities don't set explicitly

Running:
  - Authority could establish OR connection to relay within last 45 minutes

Valid:
  - Relay is not on the blacklist AND
  - Has valid descriptor with acceptable address

BadExit:
  - Relay is on the "bad exit" list (misbehaving exit node)
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
# BANDWIDTH UNITS
# ============================================================================

# Vote and consensus "w" lines carry Bandwidth= and Measured= in kilobytes per
# second (dir-spec consensus-formats). Multiply by this to get bytes per second.
# flag-thresholds values (fast-speed, guard-bw-*) are already bytes per second.
VOTE_BW_KB_BYTES = 1000

# Consensus weight cap for relays measured by fewer than 3 authorities
# (dirvote.c DEFAULT_MAX_UNMEASURED_BW_KB, consensus param maxunmeasuredbw).
MAX_UNMEASURED_BW_KB = 20

# ============================================================================
# GUARD FLAG THRESHOLDS
# Per dir-spec Section 3.4.2 and Tor source (src/feature/dirauth/voteflags.c,
# dirauth_options.inc)
# ============================================================================

# AuthDirGuardBWGuarantee: Minimum bandwidth for Guard flag.
# Default "2 MB" is a tor MEMUNIT (2 * 1024 * 1024 bytes); voteflags.c compares
# credible bandwidth in KB/s against bw_opt / 1000, i.e. 2097 KB/s.
# If a relay has at least this bandwidth, it meets the BW requirement for Guard
# regardless of whether it's in the top 25% by bandwidth.
GUARD_BW_GUARANTEE_KB = (2 * 1024 * 1024) // 1000
GUARD_BW_GUARANTEE = GUARD_BW_GUARANTEE_KB * VOTE_BW_KB_BYTES  # bytes/second

# Guard time-known (TK) threshold per dir-spec: 8 days
# Per dir-spec: "TK" parameter default is 8 days (691200 seconds)
# Relay must have been known to the authority for at least this long
# to be considered "familiar" and eligible for Guard flag.
# Verified: All 9 voting authorities use 691200 seconds (8 days).
GUARD_TK_DEFAULT = 8 * SECONDS_PER_DAY  # 691200 seconds

# Guard weighted fractional uptime (WFU) threshold per dir-spec: 98%
# Per dir-spec: "WFU" parameter default is 0.98 (98%)
# Relay must have been running at least this fraction of the time.
# Verified: All 9 voting authorities use 0.98 (98%).
GUARD_WFU_DEFAULT = 0.98

# ============================================================================
# HSDIR FLAG THRESHOLDS
# Per dir-spec Section 3.4.2
# ============================================================================

# Default HSDir time-known (TK) threshold per dir-spec: 25 hours
# NOTE: In practice, moria1 authority uses ~10 days (848498 seconds).
# Other authorities don't set hsdir-tk explicitly, relying on the dir-spec default.
# We use 25 hours as per the dir-spec specification.
HSDIR_TK_DEFAULT = 25 * SECONDS_PER_HOUR  # 90000 seconds (25 hours)

# Default HSDir weighted fractional uptime (WFU) threshold: 98%
# Same as Guard WFU per dir-spec
HSDIR_WFU_DEFAULT = 0.98

# ============================================================================
# FAST FLAG THRESHOLDS
# Per dir-spec Section 3.4.2
# ============================================================================

# AuthDirFastGuarantee: Minimum bandwidth for Fast flag.
# Default "100 KB" is a tor MEMUNIT (102,400 bytes); voteflags.c caps the Fast
# threshold at fast_opt / 1000 = 102 KB/s, published as fast-speed=102000.
# Relays with at least this bandwidth get Fast flag even if not in top 7/8ths.
FAST_BW_GUARANTEE_KB = (100 * 1024) // 1000
FAST_BW_GUARANTEE = FAST_BW_GUARANTEE_KB * VOTE_BW_KB_BYTES  # bytes/second

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

# Where the bandwidth an authority judges Fast and Guard by comes from (credible_bandwidth())
BW_SOURCE_MEASURED = 'measured'        # its bandwidth scanner's Measured= value
BW_SOURCE_REPORTED = 'reported'        # the relay's advertised Bandwidth= value
BW_SOURCE_UNMEASURED = 'unmeasured'    # no measurement; the authority counts it as 0
BW_SOURCE_UNPUBLISHED = 'unpublished'  # a measurement the vote doesn't show


def credible_bandwidth(measured_kb: Optional[int], advertised_kb: Optional[int],
                       ignoring_advertised: bool, unpublished: bool = False) -> tuple:
    """
    (bytes/second or None, BW_SOURCE_*) an authority judges Fast and Guard by.

    tor's dirserv_get_credible_bandwidth_kb() (bwauth.c): the vote's Measured=, else its
    Bandwidth=, else 0 if the vote says ignoring-advertised-bws=1, unless tor kept a
    measurement from an earlier bandwidth file. Votes don't show those, so when the
    vote gives one away (unpublished) the value is unknown (None).
    """
    if measured_kb is not None:
        return measured_kb * VOTE_BW_KB_BYTES, BW_SOURCE_MEASURED
    if not ignoring_advertised:
        return (advertised_kb or 0) * VOTE_BW_KB_BYTES, BW_SOURCE_REPORTED
    return (None, BW_SOURCE_UNPUBLISHED) if unpublished else (0, BW_SOURCE_UNMEASURED)


def guard_bw_top_threshold(thresholds: Dict[str, Any]) -> Optional[float]:
    """
    Top-25% Guard bandwidth cutoff an authority applies, in bytes/second.

    voteflags.c accepts MIN(guard_bandwidth_including_exits_kb,
    guard_bandwidth_excluding_exits_kb); votes publish both as
    guard-bw-inc-exits and guard-bw-exc-exits.
    """
    values = [thresholds[key] for key in ('guard-bw-inc-exits', 'guard-bw-exc-exits')
              if isinstance(thresholds.get(key), (int, float))]
    return min(values) if values else None


def low_median(values: list):
    """Lower median, as tor's median_uint32() picks for an even count."""
    ordered = sorted(values)
    return ordered[(len(ordered) - 1) // 2] if ordered else None


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
    - Bandwidth >= AuthDirGuardBWGuarantee OR in top 25% of relays
    
    Args:
        wfu: Relay's weighted fractional uptime
        tk: Relay's time-known in seconds
        bandwidth: Bandwidth the authority credits the relay with, in bytes/second
                   (see credible_bandwidth)
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
    - Bandwidth in top 7/8ths of relays OR >= AuthDirFastGuarantee
    
    Args:
        bandwidth: Bandwidth the authority credits the relay with, in bytes/second
                   (see credible_bandwidth)
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
    'MiddleOnly', # Restricted to middle position only (negative flag)
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
