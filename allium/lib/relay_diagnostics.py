"""
Relay diagnostics - centralized issue detection for relay health.

This module consolidates all issue detection into a single source of truth:
- Consensus issues (votes, reachability)
- Flag eligibility issues (Guard, Stable, HSDir prerequisites + metrics)
- Bandwidth issues (measurement deviation)
- Version issues (not recommended)
- Overload issues (general, rate limits, FD exhaustion)

Each issue includes severity, category, title, description, and actionable suggestion.

Issue Severities:
- error: Critical issues requiring immediate attention
- warning: Issues that should be addressed
- info: Informational notes (shown in Notes section)

Per Tor spec proposal 328, overload status remains for 72 hours after
the last detected overload event.
"""

import time
from datetime import datetime, timezone
from typing import List, Optional

# Import flag thresholds from centralized module
try:
    from .consensus.flag_thresholds import (
        SECONDS_PER_DAY,
        GUARD_TK_DEFAULT,
        GUARD_WFU_DEFAULT,
        GUARD_BW_GUARANTEE,
        HSDIR_TK_DEFAULT,
        HSDIR_WFU_DEFAULT,
    )
except ImportError:
    SECONDS_PER_DAY = 86400
    GUARD_TK_DEFAULT = 691200  # 8 days
    GUARD_WFU_DEFAULT = 0.98
    GUARD_BW_GUARANTEE = 2_000_000
    HSDIR_TK_DEFAULT = 90000  # 25 hours
    HSDIR_WFU_DEFAULT = 0.98

# Import authority data from collector_fetcher
try:
    from .consensus.collector_fetcher import (
        get_voting_authority_names,
        get_voting_authority_count,
    )
except ImportError:
    def get_voting_authority_names():
        return ['bastet', 'dannenberg', 'dizum', 'faravahar', 'gabelmoo', 
                'longclaw', 'maatuska', 'moria1', 'tor26']
    def get_voting_authority_count():
        return 9

# Import bandwidth formatter
try:
    from .bandwidth_formatter import BandwidthFormatter
    _BandwidthFormatterClass = BandwidthFormatter
except ImportError:
    _BandwidthFormatterClass = None

# Import canonical overload threshold from stability_utils (DRY)
from .stability_utils import OVERLOAD_THRESHOLD_HOURS

# Cache formatters
_bw_formatter_cache = {}


def generate_relay_issues(relay: dict, consensus_data: dict = None, 
                          use_bits: bool = False,
                          now_timestamp: float = None) -> List[dict]:
    """
    Generate ALL issues for a relay (consensus + overload).
    
    This is the main entry point for issue detection. It combines:
    - 16 consensus-related issue types
    - 6 overload issue types
    
    Args:
        relay: Full relay dict with all fields (flags, version, overload_*, etc.)
        consensus_data: Optional raw consensus evaluation data from CollecTor
        use_bits: Whether to format bandwidth in bits (for rate limit display)
        now_timestamp: Current Unix timestamp (for batch processing efficiency).
                      If None, time.time() is called once.
    
    Returns:
        List of issue dicts with: severity, category, title, description, suggestion
    """
    issues = []
    
    # Consensus-related issues (16 types)
    if consensus_data:
        issues.extend(generate_issues_from_consensus(
            consensus_data,
            relay.get('flags', []),
            relay.get('observed_bandwidth', 0),
            relay.get('version'),
            relay.get('recommended_version')
        ))
    
    # Overload issues (6 types) - pass timestamp for efficiency
    issues.extend(_check_overload_issues(relay, use_bits, now_timestamp))
    
    return issues


def generate_issues_from_consensus(
    consensus_data: dict,
    current_flags: list = None,
    observed_bandwidth: int = 0,
    version: str = None,
    recommended_version: bool = None
) -> List[dict]:
    """
    Consensus-related issue detection.
    
    This function was moved from consensus_evaluation._identify_issues() to
    consolidate all issue detection in one module.
    
    Changes from original:
    - Guard: Time Known below threshold: info → warning
    - Guard: requires Stable flag: info → warning
    - Guard: requires Fast flag: info → warning
    - Not eligible for Stable flag: info → warning
    - HSDir: WFU below threshold: info → warning
    - HSDir: Time Known below threshold: info → warning
    
    Args:
        consensus_data: Raw consensus evaluation data
        current_flags: Relay's current flags (from Onionoo)
        observed_bandwidth: Relay's observed bandwidth for Guard eligibility
        version: Tor version string running on the relay
        recommended_version: Whether the version is recommended
    
    Returns:
        List of issue dicts
    """
    issues = []
    current_flags = current_flags or []
    
    if not consensus_data:
        return issues
    
    # Skip issue generation if there's an error in the consensus data
    # (e.g., "Relay not found in votes" - CollecTor data might be stale/incomplete)
    # We should only generate issues when we have reliable consensus data
    if consensus_data.get('error'):
        return issues
    
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
    # CONSENSUS STATUS ISSUES (1 issue type)
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
    # REACHABILITY ISSUES (3 issue types)
    # =========================================================================
    ipv4_count = reachability.get('ipv4_reachable_count', 0)
    ipv4_reachable = reachability.get('ipv4_reachable_authorities', [])
    
    # DRY: Compute unreachable list once, reuse for both error and info cases
    unreachable_ipv4 = [name for name in get_voting_authority_names() if name not in ipv4_reachable]
    
    if ipv4_count < majority_threshold:
        issues.append({
            'severity': 'error',
            'category': 'reachability',
            'title': 'IPv4 reachability issues',
            'description': f"Only {ipv4_count}/{auth_count} authorities can reach this relay",
            'suggestion': f"Authorities that cannot reach you: {', '.join(unreachable_ipv4)}. Check: 1) Firewall allows incoming TCP on ORPort, 2) No ISP-level blocking, 3) Tor is running and listening. Use 'nc -zv your-ip your-orport' from external hosts to test.",
            'doc_ref': 'https://community.torproject.org/relay/setup/',
        })
    elif ipv4_count < auth_count and unreachable_ipv4:
        # Partial reachability - informational
        issues.append({
            'severity': 'info',
            'category': 'reachability',
            'title': 'Partial IPv4 reachability',
            'description': f"{ipv4_count}/{auth_count} authorities can reach this relay",
            'suggestion': f"Some authorities cannot reach you: {', '.join(unreachable_ipv4)}. This may be temporary or due to geographic routing issues.",
        })
    
    # IPv6 reachability issues
    # Note: ipv6_not_tested_authorities may not be reliably populated.
    # Use ipv6_tested_count if explicitly provided, otherwise use the count of
    # authorities that successfully tested IPv6 as minimum bound.
    ipv6_count = reachability.get('ipv6_reachable_count', 0)
    ipv6_tested = reachability.get('ipv6_tested_count')  # Explicit count if available
    if ipv6_tested is None:
        # Fallback: calculate from not-tested list, but cap at reasonable value
        # Most authorities (7-8 out of 9) test IPv6 in practice
        not_tested = reachability.get('ipv6_not_tested_authorities', [])
        # Only trust this calculation if not_tested list is small (<=2 authorities)
        # Otherwise the data is likely incomplete and we shouldn't generate this issue
        if len(not_tested) <= 2:
            ipv6_tested = auth_count - len(not_tested)
        else:
            ipv6_tested = 0  # Don't generate issue if data is unreliable
    
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
    # GUARD FLAG ELIGIBILITY (5 issue types) - 3 changed from info to warning
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
        
        # CHANGED: info → warning
        if not tk_eligible and relay_tk is not None:
            tk_days = relay_tk / SECONDS_PER_DAY
            days_needed = (GUARD_TK_DEFAULT - relay_tk) / SECONDS_PER_DAY
            issues.append({
                'severity': 'warning',  # Changed from 'info'
                'category': 'guard',
                'title': 'Guard: Time Known below threshold',
                'description': f"Time Known {tk_days:.1f} days is below 8 days requirement ({days_needed:.1f} more days needed)",
                'suggestion': 'Time Known tracks how long authorities have observed your relay. This resets if: 1) Identity key changes, 2) Long downtime makes authorities forget you. Just keep running stably.',
                'doc_ref': 'https://spec.torproject.org/dir-spec/assigning-flags-vote.html',
            })
        
        # CHANGED: info → warning
        if not has_stable:
            issues.append({
                'severity': 'warning',  # Changed from 'info'
                'category': 'guard',
                'title': 'Guard: requires Stable flag',
                'description': 'Guard flag requires having the Stable flag first',
                'suggestion': 'Get Stable flag by maintaining consistent uptime. Stable requires uptime and MTBF at or above network median (typically 2-3 weeks of stable running).',
            })
        
        # CHANGED: info → warning
        if not has_fast:
            issues.append({
                'severity': 'warning',  # Changed from 'info'
                'category': 'guard',
                'title': 'Guard: requires Fast flag',
                'description': 'Guard flag requires having the Fast flag first',
                'suggestion': 'Get Fast flag by having bandwidth ≥100 KB/s OR in top 7/8ths of network. Most relays get this easily.',
            })
    
    # =========================================================================
    # STABLE FLAG ISSUES (1 issue type) - changed from info to warning
    # =========================================================================
    if not has_stable and relay_tk is not None:
        stable_eligibility = flag_eligibility.get('stable', {})
        if stable_eligibility.get('eligible_count', 0) < majority_threshold:
            issues.append({
                'severity': 'warning',  # Changed from 'info'
                'category': 'stable',
                'title': 'Not eligible for Stable flag',
                'description': 'Uptime or MTBF below network median for most authorities',
                'suggestion': 'Stable flag requires uptime/MTBF at or above network median. Keep your relay running continuously for 2-3 weeks. Avoid restarts. Use reliable hardware and network connection.',
                'doc_ref': 'https://spec.torproject.org/dir-spec/assigning-flags-vote.html',
            })
    
    # =========================================================================
    # HSDIR FLAG ISSUES (4 issue types) - all warning severity
    # =========================================================================
    has_hsdir = 'HSDir' in current_flags
    if not has_hsdir:
        # Prerequisite checks (most common reason for missing HSDir)
        if not has_stable:
            issues.append({
                'severity': 'warning',
                'category': 'hsdir',
                'title': 'HSDir: requires Stable flag',
                'description': 'HSDir flag requires having the Stable flag first',
                'suggestion': 'Get Stable flag by maintaining consistent uptime. Stable requires uptime and MTBF at or above network median (typically 2-3 weeks of stable running). Avoid restarts.',
            })
        
        if not has_fast:
            issues.append({
                'severity': 'warning',
                'category': 'hsdir',
                'title': 'HSDir: requires Fast flag',
                'description': 'HSDir flag requires having the Fast flag first',
                'suggestion': 'Get Fast flag by having bandwidth ≥100 KB/s OR in top 7/8ths of network. Most relays get this easily.',
            })
        
        # WFU check
        if relay_wfu is not None and relay_wfu < HSDIR_WFU_DEFAULT:
            issues.append({
                'severity': 'warning',  # Changed from 'info'
                'category': 'hsdir',
                'title': 'HSDir: WFU below threshold',
                'description': f"WFU {relay_wfu*100:.1f}% below 98% required for HSDir",
                'suggestion': 'HSDir requires ≥98% WFU, Stable flag, and Time Known ≥25 hours (or ~10 days for moria1). Improve uptime consistency.',
            })
        
        # CHANGED: info → warning
        if relay_tk is not None and relay_tk < HSDIR_TK_DEFAULT:
            tk_hours = relay_tk / 3600
            issues.append({
                'severity': 'warning',  # Changed from 'info'
                'category': 'hsdir',
                'title': 'HSDir: Time Known below threshold',
                'description': f"Time Known {tk_hours:.1f} hours below 25 hours (dir-spec default)",
                'suggestion': 'Most authorities use 25 hours for HSDir TK. moria1 uses ~10 days. Keep running stably.',
            })
    
    # =========================================================================
    # BANDWIDTH/MEASUREMENT ISSUES (3 issue types)
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
                'description': "Large variation in Consensus Weight values across authorities (see 'Cons Wt' column in Per-Authority Details below)",
                'suggestion': 'Consensus weight measurements vary significantly between authorities. This can affect traffic distribution. Ensure stable network connection and consistent bandwidth availability.',
            })
        
        # NEW: Bandwidth authority measurement issues
        # Bandwidth authorities (sbws) measure relay capacity for accurate consensus weights
        # Insufficient measurements lead to inaccurate traffic distribution
        bw_auth_measured = bandwidth_data.get('bw_auth_measured_count', 0)
        bw_auth_total = bandwidth_data.get('bw_auth_total', 0)
        
        if bw_auth_total > 0:
            bw_auth_majority = (bw_auth_total // 2) + 1
            
            if bw_auth_measured < 3:
                # Critical: Very few measurements - relay may be "Unmeasured"
                issues.append({
                    'severity': 'warning',
                    'category': 'bandwidth',
                    'title': 'Low bandwidth authority measurements',
                    'description': f"Only {bw_auth_measured}/{bw_auth_total} bandwidth authorities measured this relay. "
                                  "Minimum 3 measurements needed for accurate consensus weight.",
                    'suggestion': 'Low measurement count can indicate connectivity issues. Check: '
                                 '1) Relay is reachable from multiple geographic locations, '
                                 '2) ORPort accepts connections from bandwidth scanners, '
                                 '3) RelayBandwidthRate in torrc matches actual capacity. '
                                 'New relays may take 1-2 days to be measured by all authorities.',
                    'doc_ref': 'https://community.torproject.org/relay/setup/post-install/',
                })
            elif bw_auth_measured < bw_auth_majority:
                # Moderate: Below majority but above minimum
                issues.append({
                    'severity': 'info',
                    'category': 'bandwidth',
                    'title': 'Bandwidth authority measurements below majority',
                    'description': f"{bw_auth_measured}/{bw_auth_total} bandwidth authorities measured this relay "
                                  f"(majority is {bw_auth_majority}).",
                    'suggestion': 'Some bandwidth authorities cannot measure your relay. This may be temporary or '
                                 'due to geographic routing. Monitor over 24-48 hours. If persistent, check firewall '
                                 'rules and ensure ORPort is accessible from various locations.',
                })
    
    # =========================================================================
    # STALEDESC FLAG (1 issue type)
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
    # BADEXIT FLAG (1 issue type)
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
    # MIDDLEONLY FLAG (1 issue type)
    # =========================================================================
    if 'MiddleOnly' in current_flags:
        issues.append({
            'severity': 'error',
            'category': 'flags',
            'title': 'MiddleOnly restriction active',
            'description': 'This relay has been restricted to middle position only by directory authorities. MiddleOnly removes Guard, Exit, HSDir, and V2Dir flags, and adds BadExit. This significantly limits the relay\'s role in the network.',
            'suggestion': 'This may indicate suspicious behavior patterns, Sybil risk indicators, or policy violations. Contact <a href="mailto:bad-relays@lists.torproject.org">bad-relays@lists.torproject.org</a> for more information.',
            'doc_ref': 'https://spec.torproject.org/dir-spec/',
        })
    
    # =========================================================================
    # VERSION ISSUES (1 issue type)
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


def _check_overload_issues(relay: dict, use_bits: bool = False, 
                           now_timestamp: float = None) -> List[dict]:
    """
    Check for overload-related issues from Onionoo overload fields.
    
    Implements 6 issue types from 7 scenarios (guidance doc section 3.2):
    1. General Overload Active (overload_general_timestamp < 72h) - error
    2. Recent Overload Reported (72h-7d ago) - info
    3. File Descriptor Exhaustion (overload_fd_exhausted) - error
    4. Write Bandwidth Limit Hit (overload_ratelimits.write-count > 0) - warning
    5. Read Bandwidth Limit Hit (overload_ratelimits.read-count > 0) - warning
    6. Rate Limit Configuration (context info) - info
    
    Args:
        relay: Relay dict with overload_* fields
        use_bits: Whether to format bandwidth in bits
        now_timestamp: Current Unix timestamp (avoids repeated time.time() calls)
    
    Returns:
        List of overload issue dicts
    """
    issues = []
    now_ts = now_timestamp if now_timestamp is not None else time.time()
    
    # =========================================================================
    # SCENARIO 1 & 2: General Overload (overload_general_timestamp)
    # Per Tor spec proposal 328: 72-hour threshold
    # =========================================================================
    general_ts = relay.get('overload_general_timestamp')
    if general_ts:
        # Onionoo timestamps are in milliseconds
        age_hours = (now_ts - general_ts / 1000) / 3600
        
        if age_hours < OVERLOAD_THRESHOLD_HOURS:
            # Scenario 1: Active overload (within 72 hours)
            ts_str = datetime.fromtimestamp(general_ts / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')
            issues.append({
                'severity': 'error',
                'category': 'overload',
                'title': 'General Overload Active',
                'description': f'Relay reported general overload at {ts_str} UTC. '
                              'This indicates OOM killer invocation, onionskin queue saturation, or TCP port exhaustion.',
                'suggestion': 'Check CPU/memory with htop. Review logs for "out of memory" or "onionskins" warnings. '
                             'Consider increasing MaxMemInQueues in torrc. Verify TCP ports available.',
                'doc_ref': 'https://community.torproject.org/relay/setup/post-install/',
            })
        elif age_hours < 168:  # Within 7 days
            # Scenario 2: Recent overload (stale but notable)
            days_ago = int(age_hours / 24)
            issues.append({
                'severity': 'info',
                'category': 'overload',
                'title': 'Recent Overload Reported',
                'description': f'Relay reported overload {days_ago} days ago (no longer active per 72h threshold).',
                'suggestion': 'Monitor for recurring issues. Check system resources periodically.',
            })
    
    # =========================================================================
    # SCENARIO 3: File Descriptor Exhaustion (overload_fd_exhausted)
    # =========================================================================
    fd_exhausted = relay.get('overload_fd_exhausted')
    if isinstance(fd_exhausted, dict):
        issues.append(_create_fd_exhaustion_issue(fd_exhausted.get('timestamp')))
    
    # =========================================================================
    # SCENARIOS 4, 5, 6: Rate Limit Issues (overload_ratelimits)
    # =========================================================================
    ratelimits = relay.get('overload_ratelimits')
    if ratelimits:
        rate_limit = ratelimits.get('rate-limit', 0)
        burst_limit = ratelimits.get('burst-limit', 0)
        write_count = ratelimits.get('write-count', 0)
        read_count = ratelimits.get('read-count', 0)
        
        # Format rate using BandwidthFormatter
        rate_str = _format_rate(rate_limit, use_bits)
        
        # Scenario 4: Write Bandwidth Limit Hit
        if write_count > 0:
            issues.append({
                'severity': 'warning',
                'category': 'overload',
                'title': 'Write Bandwidth Limit Hit',
                'description': f'Write rate limit ({rate_str}) was hit {write_count:,} times. '
                              'Relay is throttling outbound traffic.',
                'suggestion': 'Increase RelayBandwidthRate and RelayBandwidthBurst in torrc '
                             'if your connection has more upload capacity.',
                'doc_ref': 'https://community.torproject.org/relay/setup/post-install/#bandwidth-limits',
            })
        
        # Scenario 5: Read Bandwidth Limit Hit
        if read_count > 0:
            issues.append({
                'severity': 'warning',
                'category': 'overload',
                'title': 'Read Bandwidth Limit Hit',
                'description': f'Read rate limit ({rate_str}) was hit {read_count:,} times. '
                              'Relay is throttling inbound traffic.',
                'suggestion': 'Increase RelayBandwidthRate and RelayBandwidthBurst in torrc '
                             'if your connection has more download capacity.',
                'doc_ref': 'https://community.torproject.org/relay/setup/post-install/#bandwidth-limits',
            })
        
        # Scenario 6: Rate Limit Configuration (info context)
        if rate_limit > 0 and (write_count > 0 or read_count > 0):
            burst_str = _format_rate(burst_limit, use_bits)
            issues.append({
                'severity': 'info',
                'category': 'overload',
                'title': 'Rate Limit Configuration',
                'description': f'Configured limits: Rate={rate_str}, Burst={burst_str}. '
                              f'Limits hit: Write={write_count:,}, Read={read_count:,}.',
                'suggestion': 'These are your configured torrc limits. Adjust RelayBandwidthRate '
                             'and RelayBandwidthBurst to match your actual network capacity.',
            })
    
    return issues


def _create_fd_exhaustion_issue(timestamp_ms: Optional[int] = None) -> dict:
    """
    Create a File Descriptor Exhaustion issue dict.
    
    DRY helper to avoid duplicate issue creation code.
    
    Args:
        timestamp_ms: Optional timestamp in milliseconds when FD exhaustion occurred
    
    Returns:
        Issue dict with severity, category, title, description, suggestion, doc_ref
    """
    if timestamp_ms:
        ts_str = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')
        description = (f'Relay ran out of file descriptors at {ts_str} UTC. '
                      'This severely impacts connections and performance.')
    else:
        description = ('Relay reported running out of file descriptors. '
                      'This severely impacts connections and performance.')
    
    return {
        'severity': 'error',
        'category': 'overload',
        'title': 'File Descriptor Exhaustion',
        'description': description,
        'suggestion': ('Increase file descriptor limits: '
                      'For systemd: add "LimitNOFILE=65535" to [Service] section. '
                      'For shell: ulimit -n 65535. '
                      'Persistent: edit /etc/security/limits.conf.'),
        'doc_ref': 'https://community.torproject.org/relay/setup/post-install/#file-descriptor-limits',
    }


def _format_rate(rate_bytes: int, use_bits: bool = False) -> str:
    """Format rate limit value for display."""
    if not rate_bytes:
        return "unknown"
    
    # Use BandwidthFormatter if available (preferred)
    if _BandwidthFormatterClass is not None:
        if use_bits not in _bw_formatter_cache:
            _bw_formatter_cache[use_bits] = _BandwidthFormatterClass(use_bits=use_bits)
        try:
            fmt = _bw_formatter_cache[use_bits]
            return fmt.format_bandwidth_with_suffix(rate_bytes, fmt.determine_unit(rate_bytes), decimal_places=0)
        except Exception:
            pass
    
    # Fallback: simple formatting
    value, suffix = (rate_bytes * 8, "bit/s") if use_bits else (rate_bytes, "B/s")
    for threshold, prefix in [(1e9, "G"), (1e6, "M"), (1e3, "K")]:
        if value >= threshold:
            return f"{value / threshold:.0f} {prefix}{suffix}"
    return f"{value:.0f} {suffix}"

