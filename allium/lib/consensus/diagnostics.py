"""
File: diagnostics.py

Format diagnostic data for templates.
Provides display-ready formatting of consensus troubleshooting data.
"""

from typing import Dict, List, Optional, Any


def format_relay_diagnostics(diagnostics: dict, flag_thresholds: dict = None) -> dict:
    """
    Format relay diagnostics for template display.
    
    Args:
        diagnostics: Raw diagnostics from CollectorFetcher.get_relay_diagnostics()
        flag_thresholds: Optional flag threshold data
        
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
    
    formatted = {
        'available': True,
        'fingerprint': diagnostics.get('fingerprint', ''),
        'in_consensus': diagnostics.get('in_consensus', False),
        'vote_count': diagnostics.get('vote_count', 0),
        'total_authorities': diagnostics.get('total_authorities', 9),
        'majority_required': diagnostics.get('majority_required', 5),
        
        # Consensus status display
        'consensus_status': _format_consensus_status(diagnostics),
        
        # Per-authority voting details
        'authority_table': _format_authority_table(diagnostics),
        
        # Flag eligibility summary
        'flag_summary': _format_flag_summary(diagnostics),
        
        # Reachability summary
        'reachability_summary': _format_reachability_summary(diagnostics),
        
        # Bandwidth summary
        'bandwidth_summary': _format_bandwidth_summary(diagnostics),
        
        # Issues and advice
        'issues': _identify_issues(diagnostics),
        'advice': _generate_advice(diagnostics),
    }
    
    return formatted


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


def _format_authority_table(diagnostics: dict) -> List[dict]:
    """Format authority votes into table rows."""
    authority_votes = diagnostics.get('authority_votes', [])
    
    rows = []
    for vote in authority_votes:
        row = {
            'authority': vote.get('authority', 'Unknown'),
            'voted': vote.get('voted', False),
            'voted_display': 'Yes' if vote.get('voted') else 'No',
            'voted_class': 'success' if vote.get('voted') else 'danger',
            
            # Flags
            'flags': vote.get('flags', []),
            'flags_display': ', '.join(vote.get('flags', [])) or 'None',
            
            # Bandwidth
            'bandwidth': vote.get('bandwidth'),
            'bandwidth_display': _format_bandwidth_value(vote.get('bandwidth')),
            'measured': vote.get('measured'),
            'measured_display': _format_bandwidth_value(vote.get('measured')),
            'is_bw_authority': vote.get('is_bw_authority', False),
            
            # WFU (Weighted Fractional Uptime)
            'wfu': vote.get('wfu'),
            'wfu_display': vote.get('wfu_display', 'N/A'),
            'wfu_class': _get_wfu_class(vote.get('wfu')),
            
            # TK (Time Known)
            'tk': vote.get('tk'),
            'tk_display': vote.get('tk_display', 'N/A'),
            'tk_class': _get_tk_class(vote.get('tk')),
            
            # Reachability
            'ipv4_reachable': vote.get('ipv4_reachable', False),
            'ipv4_display': 'Yes' if vote.get('ipv4_reachable') else 'No',
            'ipv4_class': 'success' if vote.get('ipv4_reachable') else 'danger',
            
            'ipv6_reachable': vote.get('ipv6_reachable'),
            'ipv6_display': _format_ipv6_status(vote.get('ipv6_reachable'), vote.get('ipv6_address')),
            'ipv6_class': _get_ipv6_class(vote.get('ipv6_reachable')),
        }
        rows.append(row)
    
    return rows


def _format_flag_summary(diagnostics: dict) -> dict:
    """Format flag eligibility summary."""
    flag_eligibility = diagnostics.get('flag_eligibility', {})
    total_authorities = diagnostics.get('total_authorities', 9)
    
    summary = {}
    
    for flag_name in ['guard', 'stable', 'fast', 'hsdir']:
        flag_data = flag_eligibility.get(flag_name, {})
        eligible_count = flag_data.get('eligible_count', 0)
        
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
            'total': total,
            'display': f"{ipv6_count}/{total} authorities can reach IPv6",
            'status_class': 'success' if ipv6_count > 0 else 'muted',
            'authorities': reachability.get('ipv6_reachable_authorities', []),
            'not_tested': reachability.get('ipv6_not_tested_authorities', []),
        },
    }


def _format_bandwidth_summary(diagnostics: dict) -> dict:
    """Format bandwidth summary."""
    bandwidth = diagnostics.get('bandwidth', {})
    
    avg = bandwidth.get('average')
    min_bw = bandwidth.get('min')
    max_bw = bandwidth.get('max')
    deviation = bandwidth.get('deviation')
    
    return {
        'average': avg,
        'average_display': _format_bandwidth_value(avg),
        'min': min_bw,
        'min_display': _format_bandwidth_value(min_bw),
        'max': max_bw,
        'max_display': _format_bandwidth_value(max_bw),
        'deviation': deviation,
        'deviation_display': _format_bandwidth_value(deviation),
        'measurement_count': bandwidth.get('measurement_count', 0),
        'deviation_class': 'warning' if deviation and deviation > avg * 0.5 else 'normal',
    }


def _identify_issues(diagnostics: dict) -> List[dict]:
    """Identify issues that may affect relay status."""
    issues = []
    
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
    
    # Check flag eligibility
    flag_eligibility = diagnostics.get('flag_eligibility', {})
    
    guard_eligible = flag_eligibility.get('guard', {}).get('eligible_count', 0)
    if guard_eligible < 5:
        issues.append({
            'severity': 'warning',
            'category': 'flags',
            'title': 'Not eligible for Guard flag',
            'description': f"Only {guard_eligible}/9 authorities consider eligible for Guard",
            'suggestion': 'Improve WFU (≥98%), increase uptime, or increase bandwidth',
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
    """Format threshold value for display."""
    if value is None:
        return 'N/A'
    
    # Format time values (in seconds)
    if 'uptime' in key or 'tk' in key or 'mtbf' in key:
        days = value / 86400
        if days >= 1:
            return f"{days:.1f} days"
        hours = value / 3600
        return f"{hours:.1f} hours"
    
    # Format WFU (fraction to percentage)
    if 'wfu' in key:
        if isinstance(value, float) and value <= 1:
            return f"{value * 100:.1f}%"
        return f"{value}%"
    
    # Format bandwidth values
    if 'bw' in key or 'speed' in key:
        return _format_bandwidth_value(value)
    
    return str(value)


def _format_bandwidth_value(value: Any) -> str:
    """Format bandwidth value for display."""
    if value is None:
        return 'N/A'
    
    if value >= 1000000000:
        return f"{value / 1000000000:.1f} GB/s"
    elif value >= 1000000:
        return f"{value / 1000000:.1f} MB/s"
    elif value >= 1000:
        return f"{value / 1000:.1f} KB/s"
    else:
        return f"{value} B/s"


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
    days = tk / 86400
    if days >= 8:
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
