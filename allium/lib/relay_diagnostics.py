"""
Relay diagnostics - centralized issue detection for relay health.

This module consolidates all issue detection into a single source of truth:
- Consensus issues (votes, reachability)
- Flag eligibility issues (Guard, Stable, HSDir prerequisites + metrics)
- Bandwidth issues (measurement deviation)
- Version issues (not recommended)
- Overload issues (general, rate limits, FD exhaustion)

Each issue includes severity, category, title, description, actionable suggestion,
and a `section` fragment for the relay-info row or column that shows the details.

Issue Severities:
- error: Critical issues requiring immediate attention
- warning: Issues that should be addressed
- info: Informational notes (shown in Notes section)

Overload diagnostics use the same signal states as the stability cell.
General overload and file-descriptor exhaustion stay eligible for 72 hours,
and a rate-limit hit stays eligible for 24 hours. A report at the cutoff is
historical. See stability_utils for the window rules.
"""

import html as _html
from typing import List, Optional

# Import flag thresholds from centralized module
from .consensus.flag_thresholds import (
    SECONDS_PER_HOUR,
    GUARD_BW_GUARANTEE,
    FAST_BW_GUARANTEE,
    BW_SOURCE_MEASURED,
    BW_SOURCE_REPORTED,
    BW_SOURCE_UNMEASURED,
    resolve_voting_total,
)
from .string_utils import (
    format_known_duration,
    format_wfu_display,
    _format_tk_requirement,
    _format_wfu_requirement,
    _threshold_summary,
)

# Import authority data from collector_fetcher
try:
    from .consensus.collector_fetcher import get_voting_authority_names
except ImportError:
    def get_voting_authority_names():
        return ['bastet', 'dannenberg', 'dizum', 'faravahar', 'gabelmoo', 
                'longclaw', 'maatuska', 'moria1', 'tor26']

# Import bandwidth formatter (shared cached instances, keyed by use_bits)
try:
    from .bandwidth_formatter import _get_formatter as _get_bw_formatter
except ImportError:
    _get_bw_formatter = None

# Shared overload fact evaluation from stability_utils (DRY).
# OVERLOAD_THRESHOLD_HOURS is re-exported: tests import it from this module.
from .stability_utils import (  # noqa: F401
    HOUR_PRECISION_NOTE,
    OVERLOAD_GUIDE_URL,
    OVERLOAD_THRESHOLD_HOURS,
    RATE_COUNTER_NOTE,
    compute_relay_stability,
    ensure_overload_display,
    guidance_text,
)


def generate_relay_issues(relay: dict, consensus_data: dict = None, 
                          use_bits: bool = False,
                          now_timestamp: float = None) -> List[dict]:
    """
    Generate ALL issues for a relay (consensus + overload).
    
    This is the main entry point for issue detection. It combines:
    - 22 consensus-related issue types
    - 6 overload issue types
    
    Args:
        relay: Full relay dict with all fields (flags, version, overload_*, etc.)
        consensus_data: Optional raw consensus evaluation data from CollecTor
        use_bits: Whether to format bandwidth in bits (for rate limit display)
        now_timestamp: Current Unix timestamp (for batch processing efficiency).
                      If None, time.time() is called once.
    
    Returns:
        List of issue dicts with: severity, category, title, description,
        suggestion, section (page anchor for detailed view)
    """
    issues = []

    # Consensus-related issues (22 types)
    if consensus_data:
        issues.extend(generate_issues_from_consensus(
            consensus_data,
            relay.get('flags', []),
            relay.get('observed_bandwidth', 0),
            relay.get('version'),
            relay.get('recommended_version'),
            use_bits
        ))
    
    # Overload issues (6 types) - pass timestamp for efficiency
    issues.extend(_check_overload_issues(relay, use_bits, now_timestamp))
    
    return issues


def generate_issues_from_consensus(
    consensus_data: dict,
    current_flags: list = None,
    observed_bandwidth: int = 0,
    version: str = None,
    recommended_version: bool = None,
    use_bits: bool = False
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
    
    Args:
        consensus_data: Raw consensus evaluation data
        current_flags: Relay's current flags (from Onionoo)
        observed_bandwidth: Relay's observed bandwidth; only used for the Guard bandwidth
                            check when the votes give no per-authority details
        version: Tor version string running on the relay
        recommended_version: Whether the version is recommended
        use_bits: Whether to show bandwidth in bits
    
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
    # Same total and majority as the flag rows. A missing total uses the registry.
    auth_count, majority_threshold = resolve_voting_total(consensus_data.get('total_authorities'))
    
    # =========================================================================
    # CONSENSUS STATUS ISSUES (1 issue type)
    # =========================================================================
    if not consensus_data.get('in_consensus'):
        vote_count = consensus_data.get('vote_count', 0)
        issues.append({
            'severity': 'error',
            'category': 'consensus',
            'title': 'Not in consensus',
            'description': f"Only {vote_count}/{auth_count} authorities voted for this relay (need {majority_threshold})",
            'suggestion': 'Verify your relay is reachable from multiple geographic locations. Check firewall rules allow incoming connections on your ORPort from all directory authority IP addresses.',
            'section': 'col-running',
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
            'section': 'flag-running-ipv4-reachability',
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
            'section': 'flag-running-ipv4-reachability',
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
            'section': 'flag-running-ipv6-reachability',
            'doc_ref': 'https://community.torproject.org/relay/setup/',
        })
    
    # =========================================================================
    # FAST FLAG (1 issue type)
    # Each authority decides Fast from the bandwidth it credits the relay with:
    # its bandwidth scanner's Measured= value when it has one, not the bandwidth
    # the relay reports (tor bwauth.c dirserv_get_credible_bandwidth_kb).
    # =========================================================================
    has_fast = 'Fast' in current_flags
    fast_details = flag_eligibility.get('fast', {}).get('details', [])
    fast_votes = flag_eligibility.get('fast', {}).get('assigned_count', 0)
    fast_suggestion = (f'Fast requires a bandwidth in the top 7/8 of relays or at least AuthDirFastGuarantee '
                       f'({_format_rate(FAST_BW_GUARANTEE, use_bits, decimal_places=1)} by default), judged by '
                       'each authority. Authorities that have a bandwidth-scanner measurement of your relay '
                       'judge by it, not by the bandwidth your relay reports.')
    if not has_fast and fast_details and fast_votes < majority_threshold:
        issues.append({
            'severity': 'warning',
            'category': 'fast',
            'title': 'Not getting the Fast flag',
            'description': _describe_fast_shortfall(
                fast_details, fast_votes, auth_count, majority_threshold,
                consensus_data.get('bandwidth') or {}, use_bits),
            'suggestion': fast_suggestion + (
                ' A low measurement means the scanners see your relay underperforming compared with other '
                'relays that report a similar speed. Clients only build circuits through Fast relays, so a relay '
                'near the threshold can gain and lose most of its traffic from one hourly consensus to the next.'),
            'section': 'flag-fast-speed',
            'doc_ref': 'https://spec.torproject.org/dir-spec/assigning-flags-vote.html',
        })
    
    # =========================================================================
    # GUARD FLAG ELIGIBILITY (5 issue types) - 3 changed from info to warning
    # =========================================================================
    has_guard = 'Guard' in current_flags
    has_stable = 'Stable' in current_flags
    guard_details = flag_eligibility.get('guard', {}).get('details', [])
    guard_bw_votes = sum(1 for d in guard_details if d.get('bw_met'))
    if guard_details:
        guard_bw_eligible = guard_bw_votes >= majority_threshold
    else:
        guard_bw_eligible = observed_bandwidth >= GUARD_BW_GUARANTEE if observed_bandwidth else False
    # Each authority compares its own WFU and time-known with its own guard-wfu
    # and guard-tk (voteflags.c dirauth_set_routerstatus_from_routerinfo).
    # wfu_met / tk_met are those comparisons. A majority of them is what the
    # consensus needs (dirvote.c networkstatus_compute_consensus).
    wfu_met_count = sum(1 for d in guard_details if d.get('wfu_met'))
    tk_met_count = sum(1 for d in guard_details if d.get('tk_met'))
    
    if not has_guard:
        # Check each Guard requirement (order matches flag table: Fast → Stable → V2Dir → BW → WFU → TK)
        
        # Prerequisite flags first
        if not has_fast:
            issues.append({
                'severity': 'warning',
                'category': 'guard',
                'title': 'Guard: requires Fast flag',
                'description': 'Guard flag requires having the Fast flag first',
                'suggestion': fast_suggestion,
                'section': 'flag-guard-prereq-fast',
            })
        
        if not has_stable:
            issues.append({
                'severity': 'warning',
                'category': 'guard',
                'title': 'Guard: requires Stable flag',
                'description': 'Guard flag requires having the Stable flag first',
                'suggestion': 'Get Stable flag by maintaining consistent uptime. Stable requires uptime and MTBF at or above network median (typically 2-3 weeks of stable running).',
                'section': 'flag-guard-prereq-stable',
            })
        
        # Note: V2Dir prereq for Guard is checked via the flag table but not
        # as a separate diagnostic — V2Dir is almost always present (default on)
        
        # Metric thresholds
        if not guard_bw_eligible and (guard_details or observed_bandwidth):
            guarantee = _format_rate(GUARD_BW_GUARANTEE, use_bits, decimal_places=1)
            if guard_details:
                description = _describe_guard_bw_shortfall(
                    guard_details, guard_bw_votes, auth_count, majority_threshold, guarantee, use_bits)
            else:
                description = (f"Observed bandwidth {_format_rate(observed_bandwidth, use_bits)} is below "
                               f"the {guarantee} AuthDirGuardBWGuarantee")
            issues.append({
                'severity': 'warning',
                'category': 'guard',
                'title': 'Guard: bandwidth below threshold',
                'description': description,
                'suggestion': (f'Guard requires a bandwidth of at least AuthDirGuardBWGuarantee ({guarantee} by '
                               'default) or one in the top 25% of relays, judged by each authority the same way '
                               'as for Fast. To increase bandwidth: 1) Ensure adequate upstream capacity, '
                               '2) Check RelayBandwidthRate/RelayBandwidthBurst in torrc, 3) Monitor with Nyx.'),
                'section': 'flag-guard-bandwidth',
                'doc_ref': 'https://community.torproject.org/relay/setup/guard/',
            })
        
        if guard_details and wfu_met_count < majority_threshold:
            wfu_short = [d for d in guard_details if not d.get('wfu_met')]
            issues.append({
                'severity': 'warning',
                'category': 'guard',
                'title': 'Guard: WFU below threshold',
                'description': _describe_measurement_shortfall(
                    guard_details, wfu_met_count, auth_count, majority_threshold,
                    met_key='wfu_met', value_key='wfu_value', threshold_key='wfu_threshold',
                    what='guard-wfu', requirement=_format_wfu_requirement, amount=format_wfu_display,
                    bucket_of=_wfu_shortfall_bucket, bucket_text=_WFU_SHORTFALL),
                'suggestion': _guard_wfu_suggestion(wfu_short),
                'section': 'flag-guard-wfu',
                'doc_ref': 'https://spec.torproject.org/dir-spec/assigning-flags-vote.html',
            })

        if guard_details and tk_met_count < majority_threshold:
            tk_short = [d for d in guard_details if not d.get('tk_met')]
            issues.append({
                'severity': 'warning',
                'category': 'guard',
                'title': 'Guard: Time Known below threshold',
                'description': _describe_measurement_shortfall(
                    guard_details, tk_met_count, auth_count, majority_threshold,
                    met_key='tk_met', value_key='tk_value', threshold_key='tk_threshold',
                    what='guard-tk', requirement=_format_tk_requirement, amount=format_known_duration,
                    bucket_of=_tk_shortfall_bucket, bucket_text=_TK_SHORTFALL),
                'suggestion': _guard_tk_suggestion(tk_short),
                'section': 'flag-guard-time-known',
                'doc_ref': 'https://spec.torproject.org/dir-spec/assigning-flags-vote.html',
            })
    
    # =========================================================================
    # STABLE FLAG ISSUES (1 issue type) - changed from info to warning
    # =========================================================================
    stable_eligibility = flag_eligibility.get('stable') or {}
    stable_details = stable_eligibility.get('details') or []
    stable_met = stable_eligibility.get('eligible_count', 0)
    # Same signal as wfu_met: per-authority details, not "some vote published tk".
    if not has_stable and stable_details and stable_met < majority_threshold:
        issues.append({
            'severity': 'warning',  # Changed from 'info'
            'category': 'stable',
            'title': 'Not eligible for Stable flag',
            'description': _describe_stable_shortfall(
                stable_details, stable_met, auth_count, majority_threshold),
            'suggestion': 'Stable flag requires uptime/MTBF at or above network median. Keep your relay running continuously for 2-3 weeks. Avoid restarts. Use reliable hardware and network connection.',
            'section': 'flag-stable-mtbf',
            'doc_ref': 'https://spec.torproject.org/dir-spec/assigning-flags-vote.html',
        })
    
    # =========================================================================
    # HSDIR FLAG ISSUES (4 issue types) - all warning severity
    # Per Tor source (voteflags.c dirserv_thinks_router_is_hs_dir):
    #   HSDir requires: wants_to_be_hs_dir AND supports_tunnelled_dir_requests
    #   AND is_stable AND is_fast AND uptime >= 96h AND is_active
    # supports_tunnelled_dir_requests maps to the V2Dir flag.
    # =========================================================================
    has_hsdir = 'HSDir' in current_flags
    has_v2dir = 'V2Dir' in current_flags
    if not has_hsdir:
        # Prerequisite checks (order matches Guard & flag table: Fast → Stable → V2Dir)
        if not has_fast:
            issues.append({
                'severity': 'warning',
                'category': 'hsdir',
                'title': 'HSDir: requires Fast flag',
                'description': 'HSDir flag requires having the Fast flag first',
                'suggestion': fast_suggestion,
                'section': 'flag-hsdir-prereq-fast',
            })
        
        if not has_stable:
            issues.append({
                'severity': 'warning',
                'category': 'hsdir',
                'title': 'HSDir: requires Stable flag',
                'description': 'HSDir flag requires having the Stable flag first',
                'suggestion': 'Get Stable flag by maintaining consistent uptime. Stable requires uptime and MTBF at or above network median (typically 2-3 weeks of stable running). Avoid restarts.',
                'section': 'flag-hsdir-prereq-stable',
            })
        
        # V2Dir / tunnelled-dir-server check
        # Tor source requires supports_tunnelled_dir_requests for HSDir.
        # Without it, HSDir is never assigned even if all other metrics pass.
        if not has_v2dir:
            issues.append({
                'severity': 'warning',
                'category': 'hsdir',
                'title': 'HSDir: requires V2Dir (tunnelled-dir-server)',
                'description': 'HSDir requires the relay to support tunnelled directory requests (V2Dir flag). '
                              'This relay is missing V2Dir — the descriptor likely does not include '
                              '<code>tunnelled-dir-server</code>, usually because <code>DirCache 0</code> is set in torrc.',
                'suggestion': 'Remove <code>DirCache 0</code> from torrc (DirCache is enabled by default in Tor ≥0.3.3). '
                              'Restart Tor and verify the descriptor includes <code>tunnelled-dir-server</code>. '
                              'You can check with: <code>grep tunnelled-dir-server /var/lib/tor/cached-descriptors</code>',
                'section': 'flag-hsdir-prereq-v2dir',
            })
        
        # With Fast, Stable and V2Dir, what's left is the 96-hour uptime check
        if has_fast and has_stable and has_v2dir:
            hsdir_votes = flag_eligibility.get('hsdir', {}).get('assigned_count', 0)
            issues.append({
                'severity': 'warning',
                'category': 'hsdir',
                'title': 'HSDir: uptime below 96 hours',
                'description': (f"Only {hsdir_votes}/{auth_count} authorities voted HSDir, "
                                "though this relay has Fast, Stable and V2Dir"),
                'suggestion': 'HSDir needs 96 hours of uptime as each authority sees it (MinUptimeHidServDirectoryV2): '
                              'the time since your relay restarted, or since that authority last failed to reach it '
                              'if that is shorter. Keep the relay running and reachable.',
                'section': 'flag-hsdir-uptime',
                'doc_ref': 'https://spec.torproject.org/dir-spec/assigning-flags-vote.html',
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
                'section': 'col-cons-wt',
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
                    'section': 'bw-measured-by',
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
                    'section': 'bw-measured-by',
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
                'section': 'col-desc-published',
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
            'section': 'flag-badexit-restriction-by-da',
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
            'section': 'flag-middleonly-restriction-by-da',
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
            'description': f'Running Tor version {_html.escape(str(version))} which is not on the recommended list.',
            'suggestion': 'Update to the latest stable Tor version. Outdated versions may have security vulnerabilities and could eventually be rejected by the network. See <a href="https://www.torproject.org/download/tor/">torproject.org/download</a> for latest releases.',
            'section': 'version',
            'doc_ref': 'https://www.torproject.org/download/tor/',
        })
    
    return issues


def _displayed_facts(relay, use_bits, now_timestamp, facts):
    """Attach rate displays without reclassifying a record that already has a clock.

    Recomputing from ``time.time()`` would let a later call expire a signal
    the caller already judged eligible.
    """
    if facts:
        return ensure_overload_display(facts, use_bits)
    from .bandwidth_formatter import BandwidthFormatter
    return compute_relay_stability(
        relay, now_timestamp, BandwidthFormatter(use_bits=use_bits))['overload']


def _issue(severity, title, description, suggestion, section, doc_ref=OVERLOAD_GUIDE_URL):
    return {
        'severity': severity,
        'category': 'overload',
        'title': title,
        'description': description,
        'suggestion': suggestion,
        'section': section,
        'doc_ref': doc_ref,
    }


def _check_overload_issues(relay: dict, use_bits: bool = False,
                           now_timestamp: float = None, facts: dict = None) -> List[dict]:
    """
    Overload issues from the shared signal evaluation.

    Issue types and severities:
    1. General Overload Active (eligible general timestamp) - error
    2. Recent Overload Reported (historical general report within 7 days) - info
    3. File Descriptor Exhaustion (eligible FD timestamp) - error
    4. Write Bandwidth Limit Hit (eligible rate record, positive write count) - warning
    5. Read Bandwidth Limit Hit (eligible rate record, positive read count) - warning
    6. Rate Limit Configuration (context for an eligible hit) - info

    Pass ``facts`` from the generation's ``compute_relay_stability`` call so
    this does not evaluate the signals again. Expired, invalid, empty, and
    zero-hit records do not produce an overload issue.
    """
    facts = _displayed_facts(relay, use_bits, now_timestamp, facts)
    issues = _general_overload_issues(facts)
    fd_issue = _fd_overload_issue(facts)
    if fd_issue:
        issues.append(fd_issue)
    issues.extend(_rate_overload_issues(facts))
    return issues


def _general_overload_issues(facts: dict) -> List[dict]:
    """General-overload diagnostics. The title and severities stay as reviewed."""
    general = facts.get('general') or {}
    when = general.get('when')
    guide = (
        _html.escape(guidance_text(('memory', 'ntor', 'tcp')))
        + f' See <a href="{OVERLOAD_GUIDE_URL}">the Tor overload troubleshooting guide</a>.'
    )
    if general.get('state') == 'eligible' and when:
        return [_issue(
            'error', 'General Overload Active',
            f"Relay reported general overload at {when} UTC. {HOUR_PRECISION_NOTE} "
            'The flag does not identify which trigger fired. Investigation paths are '
            "Tor's internal OOM handling, dropped ntor onionskins, and TCP port exhaustion.",
            guide, 'overload-general')]
    if general.get('note_recent'):
        return [_issue(
            'info', 'Recent Overload Reported',
            f"Relay reported general overload {general.get('days_ago')} days ago, outside the "
            '72-hour eligibility window. The report can remain available after that window; '
            'the cutoff is not proof the relay recovered then.',
            'Monitor for a new report. Check system resources if it recurs.',
            'overload-general')]
    return []


def _fd_overload_issue(facts: dict) -> Optional[dict]:
    """FD exhaustion issue only for a timestamp inside the 72-hour window."""
    fd_signal = facts.get('fd') or {}
    if fd_signal.get('state') != 'eligible' or not fd_signal.get('when'):
        return None
    return _issue(
        'error', 'File Descriptor Exhaustion',
        f"Relay reported file-descriptor exhaustion at {fd_signal['when']} UTC. {HOUR_PRECISION_NOTE}",
        _html.escape(guidance_text(('fd',))), 'overload-fd')


_RATE_DIRECTIONS = (
    ('write', 'Write Bandwidth Limit Hit', 'overload-write'),
    ('read', 'Read Bandwidth Limit Hit', 'overload-read'),
)


def _rate_overload_issues(facts: dict) -> List[dict]:
    """Write, read, and configuration issues for one eligible rate-limit hit."""
    rate = facts.get('rate') or {}
    if rate.get('state') != 'eligible':
        return []
    suggestion = _html.escape(guidance_text(('bandwidth',)))
    rate_str = rate.get('rate_display', 'unavailable')
    issues = []
    for key, title, section in _RATE_DIRECTIONS:
        if rate.get(f'{key}_state') == 'ok' and (rate.get(f'{key}_value') or 0) > 0:
            issues.append(_issue(
                'warning', title,
                f"{title.split()[0]} rate-limit counter is {rate[f'{key}_display']} "
                f'(configured rate {rate_str}). {RATE_COUNTER_NOTE}',
                suggestion, section,
                'https://community.torproject.org/relay/setup/post-install/#bandwidth-limits'))
    issues.append(_issue(
        'info', 'Rate Limit Configuration',
        f"Configured limits: Rate={rate_str}, Burst={rate.get('burst_display', 'unavailable')}. "
        f"Counters: Write={rate.get('write_display', 'unknown')}, "
        f"Read={rate.get('read_display', 'unknown')}. "
        'These values are BandwidthRate and BandwidthBurst from the extra-info descriptor. '
        'RelayBandwidthRate and RelayBandwidthBurst are additional torrc caps, not the names '
        'of these values. Burst is a quantity of bytes.',
        suggestion, 'overload-rate-config'))
    return issues


def _authority_names(details: list) -> str:
    """The details' authority names as 'a', 'a and b' or 'a, b and c'."""
    names = [d.get('authority', '?') for d in details]
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def _rate_range(values: list, use_bits: bool) -> str:
    """'low – high' for the rates, or a single rate when both ends display the same."""
    low, high = (_format_rate(v, use_bits, decimal_places=1) for v in (min(values), max(values)))
    return low if low == high else f"{low} – {high}"


# What each bandwidth source an authority judged the relay by says about it
_BW_SOURCE_SENTENCES = {
    BW_SOURCE_MEASURED: '{names} measured this relay at {rate}{below}.',
    BW_SOURCE_REPORTED: '{names} used the relay-reported {rate}{below}.',
    BW_SOURCE_UNMEASURED: '{names} counted this relay as 0 (no measurement, relay-reported bandwidth ignored).',
}


def _bandwidth_source_sentences(details: list, value_key: str, source_key: str, use_bits: bool,
                                fast_threshold_key: Optional[str] = None) -> List[str]:
    """One sentence per bandwidth source, for the details that have a value."""
    def rate(value):
        return _format_rate(value, use_bits, decimal_places=1)

    sentences = []
    for source, sentence in _BW_SOURCE_SENTENCES.items():
        group = [d for d in details if d.get(source_key) == source and d.get(value_key) is not None]
        if group:
            summary = _threshold_summary(group, fast_threshold_key, rate) if fast_threshold_key else None
            below = f", below the Fast threshold ({summary})" if summary else ''
            sentences.append(sentence.format(names=_authority_names(group), below=below,
                                             rate=_rate_range([d[value_key] for d in group], use_bits)))
    return sentences


def _describe_fast_shortfall(details: list, fast_votes: int, auth_count: int, majority: int,
                             bandwidth: dict, use_bits: bool = False) -> str:
    """Why authorities withheld Fast, from the bandwidth each one judged the relay by."""
    withheld = [d for d in details if not d.get('assigned') and not d.get('sybil')]
    known = [d for d in withheld if d.get('speed_value') is not None and d.get('speed_threshold') is not None]
    below = [d for d in known if d['speed_value'] < d['speed_threshold']]
    sentences = [f"Only {fast_votes}/{auth_count} authorities vote Fast ({majority} needed)."]
    sentences += _bandwidth_source_sentences(below, 'speed_value', 'speed_source', use_bits, 'speed_threshold')
    for group, text in (([d for d in details if d.get('sybil')],
                         'listed it as Sybil (more relays on its IP address than allowed), which clears all flags'),
                        ([d for d in known if d['speed_value'] >= d['speed_threshold']],
                         'did not vote Fast despite enough bandwidth'),
                        ([d for d in withheld if d.get('speed_value') is None],
                         'judged it by bandwidth not shown in the votes')):
        if group:
            sentences.append(f"{_authority_names(group)} {text}.")
    weight = bandwidth.get('median')
    if any(d.get('speed_source') == BW_SOURCE_MEASURED for d in below) and weight and not bandwidth.get('unmeasured'):
        sentences.append(f"Its consensus weight, the median of the {bandwidth.get('measurement_count', 0)} "
                         f"bandwidth-scanner measurements, is {_format_rate(weight, use_bits, decimal_places=1)}.")
    return ' '.join(sentences)


def _requirement_lead(met_count: int, auth_count: int, majority: int, what: str, threshold: Optional[str]) -> str:
    """'2/9 authorities meet guard-wfu (≥98%; 5 needed).'"""
    requirement = f"{threshold}; {majority} needed" if threshold else f"{majority} needed"
    return f"{met_count}/{auth_count} authorities meet {what} ({requirement})."


_WFU_MEASURED_SUGGESTION = (
    'WFU measures recent uptime (recent downtime weighs more heavily). To improve: '
    '1) Minimize restarts, 2) Use systemd with Restart=always, 3) Monitor for OOM kills, '
    '4) Schedule updates during low-traffic periods.'
)
_WFU_HISTORY_SUGGESTION = (
    'A WFU of 0 means that authority has not observed this relay up yet, so it has no uptime '
    'credit. Keep the relay running and reachable from those authorities. This is that '
    "authority's history, not a network-wide measurement of 0%."
)
_TK_MEASURED_SUGGESTION = (
    'Time Known tracks how long authorities have observed your relay. This resets if: '
    '1) Identity key changes, 2) Long downtime makes authorities forget you. Just keep running stably.'
)
_TK_HISTORY_SUGGESTION = (
    'Time Known stays near zero until an authority has observed the relay. Keep it running '
    'with the same identity key so those authorities accumulate history.'
)


def _guard_wfu_suggestion(short: list) -> str:
    """History advice when every shortfall is 0 or unpublished. Otherwise the uptime advice."""
    if short and all('wfu_value' in d and (d.get('wfu_value') is None or d.get('wfu_value') == 0) for d in short):
        return _WFU_HISTORY_SUGGESTION
    return _WFU_MEASURED_SUGGESTION


def _guard_tk_suggestion(short: list) -> str:
    """History advice only when every shortfall is unpublished or under an hour."""
    if short and all('tk_value' in d and (
            d.get('tk_value') is None or d.get('tk_value') < SECONDS_PER_HOUR) for d in short):
        return _TK_HISTORY_SUGGESTION
    return _TK_MEASURED_SUGGESTION


def _span_details(details: list, value_key: str, threshold_key: str, formatter) -> str:
    """Low–high for the group, each end formatted against its own threshold."""
    ordered = sorted(details, key=lambda detail: detail[value_key])
    low, high = ordered[0], ordered[-1]
    start = formatter(low[value_key], low.get(threshold_key))
    end = formatter(high[value_key], high.get(threshold_key))
    return start if start == end else f"{start}–{end}"


def _wfu_shortfall_bucket(detail: dict) -> str:
    """Split a missed WFU into unpublished, untracked zero, recorded-down zero, or a measurement.

    Tor's rep_hist_get_weighted_fractional_uptime returns 0 both when the relay
    has not been observed and when only downtime has been recorded. Days of
    time-known beside that 0 are recorded downtime, not missing history.
    """
    value = detail.get('wfu_value')
    if value is None:
        return 'missing'
    if value != 0:
        return 'measured'
    tracked = detail.get('tk_value')
    if tracked is not None and tracked >= SECONDS_PER_HOUR:
        return 'down'
    return 'history'


def _tk_shortfall_bucket(detail: dict) -> str:
    """Split a missed Time Known into unpublished, under an hour, or a real measurement."""
    value = detail.get('tk_value')
    if value is None:
        return 'missing'
    if value < SECONDS_PER_HOUR:
        return 'untracked'
    return 'measured'


def _measured_sentence(group: list, formatter, value_key: str, threshold_key: str, prefix: str) -> str:
    span = _span_details(group, value_key, threshold_key, formatter)
    return f"{_authority_names(group)} {prefix}{span}."


# Unpublished, empty, and measured are different sentences. A WFU of 0 beside
# days of time-known is recorded downtime; under an hour it is no history.
_WFU_SHORTFALL = (
    ('history', lambda group, _fmt: (
        f"{_authority_names(group)} measured 0% (no uptime history for this relay).")),
    ('down', lambda group, _fmt: f"{_authority_names(group)} measured 0% (no uptime credit)."),
    ('missing', lambda group, _fmt: f"{_authority_names(group)} published no WFU."),
    ('measured', lambda group, fmt: _measured_sentence(group, fmt, 'wfu_value', 'wfu_threshold', 'measured ')),
)
_TK_SHORTFALL = (
    ('untracked', lambda group, fmt: (
        f"{_authority_names(group)} have no time-known history "
        f"({_span_details(group, 'tk_value', 'tk_threshold', fmt)}).")),
    ('missing', lambda group, _fmt: f"{_authority_names(group)} published no Time Known."),
    ('measured', lambda group, fmt: _measured_sentence(
        group, fmt, 'tk_value', 'tk_threshold', 'have known this relay for ')),
)


def _describe_measurement_shortfall(details: list, met_count: int, auth_count: int, majority: int, *,
                                    met_key: str, value_key: str, threshold_key: str, what: str,
                                    requirement, amount, bucket_of, bucket_text) -> str:
    """Count, the authorities' own bar, and one sentence per kind of shortfall."""
    threshold = _threshold_summary(details, threshold_key, requirement)
    sentences = [_requirement_lead(met_count, auth_count, majority, what, threshold)]
    groups = {}
    unnamed = []
    for detail in details:
        if detail.get(met_key):
            continue
        if value_key not in detail:
            unnamed.append(detail)
            continue
        groups.setdefault(bucket_of(detail), []).append(detail)
    for bucket, text in bucket_text:
        group = groups.get(bucket)
        if group:
            sentences.append(text(group, amount))
    named = [detail for detail in unnamed if detail.get('authority')]
    if named:
        sentences.append(f"{_authority_names(named)} do not meet it.")
    return ' '.join(sentences)


def _describe_stable_shortfall(details: list, met_count: int, auth_count: int, majority: int) -> str:
    """How many authorities find the relay Stable, and who does not when the details agree."""
    lead = _requirement_lead(met_count, auth_count, majority, 'Stable',
                             'uptime or MTBF at or above their own median')
    eligible_in_details = sum(1 for detail in details if detail.get('eligible'))
    if eligible_in_details != met_count:
        return lead
    short = [detail for detail in details if not detail.get('eligible') and detail.get('authority')]
    if short:
        lead += f" {_authority_names(short)} do not."
    return lead


def _describe_guard_bw_shortfall(details: list, met_count: int, auth_count: int, majority: int,
                                 guarantee: str, use_bits: bool = False) -> str:
    """How far each authority's bandwidth for this relay is from the Guard requirement."""
    top = [d['bw_top25_threshold'] for d in details if d.get('bw_top25_threshold') is not None]
    top25 = f" or a place in their top 25% ({_rate_range(top, use_bits)})" if top else ''
    return ' '.join([f"{met_count}/{auth_count} authorities credit this relay with enough bandwidth for Guard "
                     f"({majority} needed): at least {guarantee} (AuthDirGuardBWGuarantee){top25}."]
                    + _bandwidth_source_sentences([d for d in details if not d.get('bw_met')],
                                                  'bw_value', 'bw_source', use_bits))


def _format_rate(rate_bytes: int, use_bits: bool = False, decimal_places: int = 0) -> str:
    """Format a bandwidth rate (bytes/second) for display."""
    if not rate_bytes:
        return "unknown"

    # Use shared cached BandwidthFormatter if available (preferred)
    if _get_bw_formatter is not None:
        try:
            fmt = _get_bw_formatter(use_bits=use_bits)
            return fmt.format_bandwidth_with_suffix(rate_bytes, fmt.determine_unit(rate_bytes),
                                                    decimal_places=decimal_places)
        except Exception:
            pass

    # Fallback: simple formatting
    value, suffix = (rate_bytes * 8, "bit/s") if use_bits else (rate_bytes, "B/s")
    for threshold, prefix in [(1e9, "G"), (1e6, "M"), (1e3, "K")]:
        if value >= threshold:
            return f"{value / threshold:.{decimal_places}f} {prefix}{suffix}"
    return f"{value:.0f} {suffix}"

