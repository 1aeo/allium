"""
File: operator_analysis.py

Contact/operator page data computation: reliability statistics, display data,
flag analysis, downtime alerts, and leaderboard rankings.
Extracted from relays.py for better modularity.
"""

import statistics

from .time_utils import format_time_ago, PERIOD_SHORT_NAMES, PERIOD_DISPLAY_NAMES
from .uptime_utils import (
    extract_relay_uptime_for_period,
    calculate_statistical_outliers,
    find_operator_percentile_position,
    format_network_percentiles_display,
)
from .bandwidth_utils import (
    extract_relay_bandwidth_for_period,
    extract_operator_daily_bandwidth_totals,
    calculate_bandwidth_reliability_metrics,
)


def generate_contact_rankings(contact_hash, relay_set):
    """
    Generate AROI leaderboard rankings for a specific contact hash.
    Returns list of ranking achievements for display on contact pages.
    """
    if not hasattr(relay_set, 'json') or not relay_set.json.get('aroi_leaderboards'):
        return []
    
    leaderboards = relay_set.json['aroi_leaderboards'].get('leaderboards', {})
    rankings = []
    
    # Check each leaderboard category for this contact
    for category, leaders in leaderboards.items():
        for rank, entry in enumerate(leaders, 1):
            # Handle both formatted entries (dict) and raw tuples
            if isinstance(entry, dict):
                leader_contact = entry.get('contact_hash')
            else:
                # Handle tuple format (leader_contact, data)
                leader_contact, data = entry
            
            if leader_contact == contact_hash:
                # Only show top 25 rankings
                if rank <= 25:
                    category_info = get_leaderboard_category_info(category)
                    rankings.append({
                        'category': category,
                        'category_name': category_info['name'],
                        'rank': rank,
                        'emoji': category_info['emoji'],
                        'title': category_info['title'],
                        'statement': f"#{rank} {category_info['name']}",
                        'link': f"aroi-leaderboards.html#{category}"
                    })
                break
    
    # Sort rankings by rank (1st place first, 25th place last)
    rankings.sort(key=lambda x: x['rank'])
    
    return rankings

def get_leaderboard_category_info(category):
    """
    Get display information for a leaderboard category.
    
    Args:
        category (str): Category key
        
    Returns:
        dict: Category display information
    """
    # DRY helper function: when name and title are identical
    def _info(name, emoji):
        return {'name': name, 'emoji': emoji, 'title': name}
    
    category_info = {
        'bandwidth': _info('Bandwidth Capacity Champion', '🚀'),
        'consensus_weight': _info('Network Heavyweight', '⚖️'),
        'exit_authority': _info('Exit Heavyweight Master', '🚪'),
        'guard_authority': _info('Guard Heavyweight Master', '🛡️'),
        'exit_operators': _info('Exit Champion', '🚪'),
        'guard_operators': _info('Guard Gatekeepers', '🛡️'),
        'most_diverse': _info('Diversity Master', '🌈'),
        'platform_diversity': _info('Platform Hero', '💻'),
        'non_eu_leaders': _info('Non-EU Leader', '🌍'),
        'frontier_builders': _info('Frontier Builder', '🏴‍☠️'),
        'network_veterans': _info('Network Veteran', '🏆'),
        'reliability_masters': _info('Reliability Master', '⏰'),
        'legacy_titans': _info('Legacy Titan', '👑'),
        'ipv4_leaders': _info('IPv4 Address Leaders', '🌐'),
        'ipv6_leaders': _info('IPv6 Address Leaders', '🔮')
    }
    
    # Default for unknown categories
    default_name = category.replace('_', ' ').title()
    return category_info.get(category, _info(default_name, '🏅'))

def calculate_operator_reliability(contact_hash, operator_relays, relay_set):
    """
    Calculate comprehensive reliability statistics for an operator.
    
    Uses shared uptime utilities to avoid code duplication with aroileaders.py.
    Uses cached network percentiles for efficiency (calculated once in _reprocess_uptime_data).
    
    NEW: Also calculates bandwidth reliability metrics using shared bandwidth utilities.
    
    Args:
        contact_hash (str): Contact hash for the operator
        operator_relays (list): List of relay objects for this operator
        
    Returns:
        dict: Reliability statistics including overall uptime, time periods, outliers, network percentiles,
              and bandwidth performance metrics
    """
    uptime_data = getattr(relay_set, 'uptime_data', None)
    bandwidth_data = getattr(relay_set, 'bandwidth_data', None)
    if (not uptime_data and not bandwidth_data) or not operator_relays:
        return None
        
    from .uptime_utils import (
        extract_relay_uptime_for_period, 
        calculate_statistical_outliers,
        find_operator_percentile_position
    )
    from .bandwidth_utils import extract_relay_bandwidth_for_period, extract_operator_daily_bandwidth_totals
    
    # Available time periods from Onionoo APIs
    uptime_periods = ['1_month', '3_months', '6_months', '1_year', '5_years']
    bandwidth_periods = ['6_months', '1_year', '5_years']  # Bandwidth has different available periods
    
    reliability_stats = {
        # === UPTIME METRICS (existing) ===
        'overall_uptime': {},  # Unweighted average uptime per time period
        'relay_uptimes': [],   # Individual relay uptime data
        'outliers': {          # Statistical outliers (2+ std dev from mean)
            'low_outliers': [],
            'high_outliers': []
        },
        'network_uptime_percentiles': None,  # Network-wide percentiles for 6-month period
        
        # === BANDWIDTH METRICS (new) ===
        'overall_bandwidth': {},  # Average bandwidth per time period
        'relay_bandwidths': [],   # Individual relay bandwidth data
        'bandwidth_outliers': {   # Bandwidth statistical outliers
            'low_outliers': [],
            'high_outliers': []
        },
        'network_bandwidth_percentiles': None,  # Network-wide bandwidth percentiles for 6-month period
        'operator_daily_bandwidth': {},  # Daily total bandwidth averages per period
        
        # === COMMON METRICS ===
        'valid_relays': 0,
        'total_relays': len(operator_relays)
    }
    
    # PERFORMANCE OPTIMIZATION: Use cached network percentiles instead of recalculating
    # Network percentiles are calculated once in _reprocess_uptime_data for all contacts
    if hasattr(relay_set, 'network_uptime_percentiles') and relay_set.network_uptime_percentiles:
        reliability_stats['network_uptime_percentiles'] = relay_set.network_uptime_percentiles
        
    # BANDWIDTH PERCENTILES: Use cached bandwidth percentiles if available
    if hasattr(relay_set, 'network_bandwidth_percentiles') and relay_set.network_bandwidth_percentiles:
        reliability_stats['network_bandwidth_percentiles'] = relay_set.network_bandwidth_percentiles
    
    # Process uptime data for each time period using shared utilities
    all_relay_data = {}
    
    if uptime_data:
        for period in uptime_periods:
            # Extract uptime data for this period using shared utility
            period_result = extract_relay_uptime_for_period(operator_relays, uptime_data, period)
        
            if period_result['uptime_values']:
                mean_uptime = statistics.mean(period_result['uptime_values'])
                std_dev = statistics.stdev(period_result['uptime_values']) if len(period_result['uptime_values']) > 1 else 0
                
                reliability_stats['overall_uptime'][period] = {
                    'average': mean_uptime,
                    'std_dev': std_dev,
                    'display_name': PERIOD_DISPLAY_NAMES[period],
                    'relay_count': len(period_result['uptime_values'])
                }
                
                # For 6-month period, add network percentile comparison using cached data
                if period == '6_months' and reliability_stats['network_uptime_percentiles']:
                    operator_position_info = find_operator_percentile_position(mean_uptime, reliability_stats['network_uptime_percentiles'])
                    reliability_stats['overall_uptime'][period]['network_position'] = operator_position_info['description']
                    reliability_stats['overall_uptime'][period]['percentile_range'] = operator_position_info['percentile_range']
                
                # Calculate statistical outliers using shared utility
                outliers = calculate_statistical_outliers(
                    period_result['uptime_values'], 
                    period_result['relay_breakdown']
                )
                
                # Add period information to outliers
                for outlier in outliers['low_outliers']:
                    outlier['period'] = period
                for outlier in outliers['high_outliers']:
                    outlier['period'] = period
                
                # Collect outliers from all periods
                reliability_stats['outliers']['low_outliers'].extend(outliers['low_outliers'])
                reliability_stats['outliers']['high_outliers'].extend(outliers['high_outliers'])
                
                # Collect relay data for relay_uptimes
                for fingerprint, relay_data in period_result['relay_breakdown'].items():
                    if fingerprint not in all_relay_data:
                        all_relay_data[fingerprint] = {
                            'fingerprint': fingerprint,
                            'nickname': relay_data['nickname'],
                            'uptime_periods': {},
                            'bandwidth_periods': {}  # Add bandwidth support
                        }
                    all_relay_data[fingerprint]['uptime_periods'][period] = relay_data['uptime']
    
    # Process bandwidth data for each time period using shared utilities
    all_bandwidth_relay_data = {}
    
    if bandwidth_data:
        # BANDWIDTH OUTLIERS: Only calculate for 6mo (actionable timeframe)
        # Historical outliers (1y, 5y) are not actionable for current operations
        bandwidth_outlier_periods = ['6_months']  # Only current/recent outliers are actionable
        
        for period in bandwidth_periods:
            # Extract individual relay bandwidth data for this period
            period_result = extract_relay_bandwidth_for_period(operator_relays, bandwidth_data, period)
            
            if period_result['bandwidth_values']:
                mean_bandwidth = statistics.mean(period_result['bandwidth_values'])
                std_dev = statistics.stdev(period_result['bandwidth_values']) if len(period_result['bandwidth_values']) > 1 else 0
                
                # Format bandwidth with appropriate units for display
                unit = relay_set.bandwidth_formatter.determine_unit(mean_bandwidth)
                formatted_bandwidth = relay_set.bandwidth_formatter.format_bandwidth_with_unit(mean_bandwidth, unit)
                
                reliability_stats['overall_bandwidth'][period] = {
                    'average': mean_bandwidth,
                    'average_formatted': f"{formatted_bandwidth} {unit}",
                    'std_dev': std_dev,
                    'display_name': PERIOD_DISPLAY_NAMES[period],
                    'relay_count': len(period_result['bandwidth_values'])
                }
                
                # PROPOSAL METRICS: Calculate advanced bandwidth reliability metrics
                from .bandwidth_utils import calculate_bandwidth_reliability_metrics
                advanced_metrics = calculate_bandwidth_reliability_metrics(
                    operator_relays, bandwidth_data, period, mean_bandwidth, std_dev, 
                    bandwidth_formatter=relay_set.bandwidth_formatter
                )
                
                # Add advanced metrics to the period data
                reliability_stats['overall_bandwidth'][period].update({
                    'bandwidth_stability': advanced_metrics['bandwidth_stability'],
                    'peak_performance': advanced_metrics['peak_performance'],
                    'growth_trend': advanced_metrics['growth_trend'],
                    'capacity_utilization': advanced_metrics['capacity_utilization']
                })
                
                # For 6-month period, add network percentile comparison using cached data
                if period == '6_months' and reliability_stats['network_bandwidth_percentiles']:
                    # Create a simple position finder for bandwidth (simpler than uptime version)
                    percentiles = reliability_stats['network_bandwidth_percentiles']
                    if mean_bandwidth >= percentiles['percentile_95']:
                        position_desc = "Top 5%"
                        percentile_range = "95th-100th percentile"
                    elif mean_bandwidth >= percentiles['percentile_75']:
                        position_desc = "Top 25%"
                        percentile_range = "75th-95th percentile"
                    elif mean_bandwidth >= percentiles['percentile_50']:
                        position_desc = "Top 50%"
                        percentile_range = "50th-75th percentile"
                    elif mean_bandwidth >= percentiles['percentile_25']:
                        position_desc = "Top 75%"
                        percentile_range = "25th-50th percentile"
                    else:
                        position_desc = "Bottom 25%"
                        percentile_range = "0-25th percentile"
                        
                    reliability_stats['overall_bandwidth'][period]['network_position'] = position_desc
                    reliability_stats['overall_bandwidth'][period]['percentile_range'] = percentile_range
                
                # Calculate bandwidth outliers ONLY for actionable periods (6mo)
                if period in bandwidth_outlier_periods:
                    # Fix: Convert bandwidth relay_breakdown to use 'value' key expected by statistical utilities
                    bandwidth_relay_breakdown_fixed = {}
                    for fingerprint, relay_data in period_result['relay_breakdown'].items():
                        bandwidth_relay_breakdown_fixed[fingerprint] = relay_data.copy()
                        bandwidth_relay_breakdown_fixed[fingerprint]['value'] = relay_data['bandwidth']
                    
                    bandwidth_outliers = calculate_statistical_outliers(
                        period_result['bandwidth_values'], 
                        bandwidth_relay_breakdown_fixed
                    )
                    
                    # Add period information to bandwidth outliers
                    for outlier in bandwidth_outliers['low_outliers']:
                        outlier['period'] = period
                        # Add formatted bandwidth for display (outlier now has 'value' key)
                        bw_value = outlier.get('value', outlier.get('bandwidth', 0))
                        bw_unit = relay_set.bandwidth_formatter.determine_unit(bw_value)
                        bw_formatted = relay_set.bandwidth_formatter.format_bandwidth_with_unit(bw_value, bw_unit)
                        outlier['value_formatted'] = f"{bw_formatted} {bw_unit}"
                    for outlier in bandwidth_outliers['high_outliers']:
                        outlier['period'] = period
                        # Add formatted bandwidth for display (outlier now has 'value' key)
                        bw_value = outlier.get('value', outlier.get('bandwidth', 0))
                        bw_unit = relay_set.bandwidth_formatter.determine_unit(bw_value)
                        bw_formatted = relay_set.bandwidth_formatter.format_bandwidth_with_unit(bw_value, bw_unit)
                        outlier['value_formatted'] = f"{bw_formatted} {bw_unit}"
                    
                    # Collect bandwidth outliers from actionable periods only
                    reliability_stats['bandwidth_outliers']['low_outliers'].extend(bandwidth_outliers['low_outliers'])
                    reliability_stats['bandwidth_outliers']['high_outliers'].extend(bandwidth_outliers['high_outliers'])
                
                # Collect relay bandwidth data for relay_bandwidths
                for fingerprint, relay_data in period_result['relay_breakdown'].items():
                    if fingerprint not in all_bandwidth_relay_data:
                        all_bandwidth_relay_data[fingerprint] = {
                            'fingerprint': fingerprint,
                            'nickname': relay_data['nickname'],
                            'bandwidth_periods': {}
                        }
                    all_bandwidth_relay_data[fingerprint]['bandwidth_periods'][period] = {
                        'bandwidth': relay_data['bandwidth'],
                        'bandwidth_formatted': relay_set.bandwidth_formatter.format_bandwidth_with_unit(
                            relay_data['bandwidth'],
                            relay_set.bandwidth_formatter.determine_unit(relay_data['bandwidth'])
                        ) + " " + relay_set.bandwidth_formatter.determine_unit(relay_data['bandwidth'])
                    }
                    
                    # Also add to the main relay data if it exists
                    if fingerprint in all_relay_data:
                        all_relay_data[fingerprint]['bandwidth_periods'][period] = relay_data['bandwidth']
        
        # Calculate daily total bandwidth averages for this operator using existing logic
        for period in bandwidth_periods:
            daily_totals_result = extract_operator_daily_bandwidth_totals(operator_relays, bandwidth_data, period)
            if daily_totals_result['daily_totals']:
                avg_daily_total = daily_totals_result['average_daily_total']
                
                # Format for display
                unit = relay_set.bandwidth_formatter.determine_unit(avg_daily_total)
                formatted_total = relay_set.bandwidth_formatter.format_bandwidth_with_unit(avg_daily_total, unit)
                
                reliability_stats['operator_daily_bandwidth'][period] = {
                    'average_daily_total': avg_daily_total,
                    'average_daily_total_formatted': f"{formatted_total} {unit}",
                    'valid_days': daily_totals_result['valid_days'],
                    'display_name': PERIOD_DISPLAY_NAMES[period]
                }
    
    # Set relay uptimes and valid relays count
    reliability_stats['relay_uptimes'] = list(all_relay_data.values())
    reliability_stats['valid_relays'] = len(all_relay_data)
    
    # Set relay bandwidth data
    reliability_stats['relay_bandwidths'] = list(all_bandwidth_relay_data.values())
    
    # Remove duplicate outliers (same relay appearing in multiple periods)
    # Keep the one with highest deviation
    def deduplicate_outliers(outliers):
        relay_outliers = {}
        for outlier in outliers:
            fp = outlier['fingerprint']
            if fp not in relay_outliers or outlier['deviation'] > relay_outliers[fp]['deviation']:
                relay_outliers[fp] = outlier
        return list(relay_outliers.values())
    
    # Deduplicate uptime outliers
    reliability_stats['outliers']['low_outliers'] = deduplicate_outliers(reliability_stats['outliers']['low_outliers'])
    reliability_stats['outliers']['high_outliers'] = deduplicate_outliers(reliability_stats['outliers']['high_outliers'])
    
    # Deduplicate bandwidth outliers
    reliability_stats['bandwidth_outliers']['low_outliers'] = deduplicate_outliers(reliability_stats['bandwidth_outliers']['low_outliers'])
    reliability_stats['bandwidth_outliers']['high_outliers'] = deduplicate_outliers(reliability_stats['bandwidth_outliers']['high_outliers'])
    
    return reliability_stats

def format_intelligence_rating(rating_text):
    """
    Helper function to format intelligence ratings with color coding.
    
    Args:
        rating_text (str): Rating text like "Poor, 1 network" or "Great, 4 networks"
        
    Returns:
        str: HTML formatted string with color-coded rating
    """
    if not rating_text or ', ' not in rating_text:
        return rating_text
    
    rating, details = rating_text.split(', ', 1)
    
    if 'Poor' in rating:
        return f'<span style="color: #c82333; font-weight: bold;">Poor</span>, {details}'
    elif 'Okay' in rating:
        return f'<span style="color: #cc9900; font-weight: bold;">Okay</span>, {details}'
    else:  # Great or other
        return f'<span style="color: #2e7d2e; font-weight: bold;">Great</span>, {details}'

def _format_bandwidth_breakdown(i, bandwidth_unit, relay_set):
    """Format bandwidth breakdown by role (guard/middle/exit) for contact pages."""
    bw_components = []
    for role, count_key, bw_key in [('guard', 'guard_count', 'guard_bandwidth'),
                                     ('middle', 'middle_count', 'middle_bandwidth'),
                                     ('exit', 'exit_count', 'exit_bandwidth')]:
        if i[count_key] > 0 and i[bw_key] > 0:
            formatted = relay_set.bandwidth_formatter.format_bandwidth_with_unit(i[bw_key], bandwidth_unit)
            if formatted != '0.00':
                bw_components.append(f"{formatted} {bandwidth_unit} {role}")
    return ', '.join(bw_components) if bw_components else None


def _format_cw_breakdown(i):
    """Format consensus weight breakdown by role for contact pages."""
    cw_components = []
    for role, count_key, cw_key in [('guard', 'guard_count', 'guard_consensus_weight_fraction'),
                                     ('middle', 'middle_count', 'middle_consensus_weight_fraction'),
                                     ('exit', 'exit_count', 'exit_consensus_weight_fraction')]:
        if i[count_key] > 0 and i[cw_key] > 0:
            cw_components.append(f"{i[cw_key] * 100:.2f}% {role}")
    return ', '.join(cw_components) if cw_components else None


def _format_uptime_periods(operator_reliability):
    """Format overall uptime with green highlighting for 100% periods."""
    uptime_formatted = {}
    if operator_reliability and operator_reliability.get('overall_uptime'):
        for period, data in operator_reliability['overall_uptime'].items():
            avg = data.get('average', 0)
            display_name = data.get('display_name', period)
            relay_count = data.get('relay_count', 0)
            
            if avg >= 99.99 or abs(avg - 100.0) < 0.01:
                uptime_formatted[period] = {
                    'display': f'<span style="color: #28a745; font-weight: bold;">{display_name} {avg:.1f}%</span>',
                    'relay_count': relay_count
                }
            else:
                uptime_formatted[period] = {
                    'display': f'{display_name} {avg:.1f}%',
                    'relay_count': relay_count
                }
    return uptime_formatted


def _format_outliers_data(operator_reliability):
    """Format statistical outlier data for contact pages."""
    outliers_data = {}
    if operator_reliability and operator_reliability.get('outliers'):
        total_outliers = len(operator_reliability['outliers'].get('low_outliers', [])) + len(operator_reliability['outliers'].get('high_outliers', []))
        total_relays = operator_reliability.get('total_relays', 1)
        
        if total_outliers > 0:
            outlier_percentage = (total_outliers / total_relays * 100) if total_relays > 0 else 0
            
            six_month_data = operator_reliability.get('overall_uptime', {}).get('6_months', {})
            mean_uptime = six_month_data.get('average', 0)
            std_dev = six_month_data.get('std_dev', 0)
            two_sigma_threshold = mean_uptime - (2 * std_dev)
            
            outliers_data['total_count'] = total_outliers
            outliers_data['total_relays'] = total_relays
            outliers_data['percentage'] = f"{outlier_percentage:.1f}"
            outliers_data['tooltip'] = f"6mo: ≥2σ {two_sigma_threshold:.1f}% from μ {mean_uptime:.1f}%"
            
            low_outliers = operator_reliability['outliers'].get('low_outliers', [])
            if low_outliers:
                low_names = [f"{o['nickname']} ({o['uptime']:.1f}%)" for o in low_outliers]
                outliers_data['low_count'] = len(low_outliers)
                outliers_data['low_tooltip'] = ', '.join(low_names)
            
            high_outliers = operator_reliability['outliers'].get('high_outliers', [])
            if high_outliers:
                high_names = [f"{o['nickname']} ({o['uptime']:.1f}%)" for o in high_outliers]
                outliers_data['high_count'] = len(high_outliers)
                outliers_data['high_tooltip'] = ', '.join(high_names)
        else:
            outliers_data['none_detected'] = True
    return outliers_data


def compute_contact_display_data(i, bandwidth_unit, operator_reliability, v, members, relay_set):
    """
    Compute contact-specific display data for contact pages.
    
    Composed from helper functions for readability:
    - _format_bandwidth_breakdown: Role-based bandwidth display
    - _format_cw_breakdown: Consensus weight by role
    - _format_uptime_periods: Uptime with green highlighting
    - _format_outliers_data: Statistical outlier display
    
    Args:
        i: The contact's sorted data (bandwidth, counts, fractions)
        bandwidth_unit: The bandwidth unit for this contact
        operator_reliability: Reliability statistics from calculate_operator_reliability
        v: The contact hash
        members: List of relay objects for this contact
        relay_set: The Relays instance
        
    Returns:
        dict: Contact-specific display data for template rendering
    """
    display_data = {}
    
    # 1. Bandwidth breakdown by role
    display_data['bandwidth_breakdown'] = _format_bandwidth_breakdown(i, bandwidth_unit, relay_set)
    
    # 2. Consensus weight breakdown by role
    display_data['consensus_weight_breakdown'] = _format_cw_breakdown(i)
    
    # 3. Operator intelligence formatting (reuse existing contact intelligence data)
    intelligence_formatted = {}
    if hasattr(relay_set, 'json') and relay_set.json.get('smart_context'):
        contact_intel_data = relay_set.json['smart_context'].get('contact_intelligence', {}).get('template_optimized', {})
        contact_intel = contact_intel_data.get(v)
        
        if contact_intel:
            # Format network diversity with color coding
            portfolio_div = contact_intel.get('portfolio_diversity', '')
            intelligence_formatted['network_diversity'] = format_intelligence_rating(portfolio_div)
            
            # Format geographic diversity with color coding
            geo_risk = contact_intel.get('geographic_risk', '')
            intelligence_formatted['geographic_diversity'] = format_intelligence_rating(geo_risk)
            
            # Format infrastructure diversity with color coding
            infra_risk = contact_intel.get('infrastructure_risk', '')
            intelligence_formatted['infrastructure_diversity'] = format_intelligence_rating(infra_risk)
            
            # Copy other intelligence fields
            intelligence_formatted['measurement_status'] = contact_intel.get('measurement_status', '')
            intelligence_formatted['performance_status'] = contact_intel.get('performance_status', '')
            intelligence_formatted['performance_underutilized'] = contact_intel.get('performance_underutilized', 0)
            intelligence_formatted['performance_underutilized_percentage'] = contact_intel.get('performance_underutilized_percentage', 0)
            intelligence_formatted['performance_underutilized_fps'] = contact_intel.get('performance_underutilized_fps', [])
            # Add new CW/BW ratio fields
            intelligence_formatted['performance_operator_overall_ratio'] = contact_intel.get('performance_operator_overall_ratio', '')
            intelligence_formatted['performance_operator_guard_ratio'] = contact_intel.get('performance_operator_guard_ratio', '')
            intelligence_formatted['performance_operator_exit_ratio'] = contact_intel.get('performance_operator_exit_ratio', '')
            intelligence_formatted['performance_network_overall_ratio'] = contact_intel.get('performance_network_overall_ratio', '')
            intelligence_formatted['performance_network_guard_ratio'] = contact_intel.get('performance_network_guard_ratio', '')
            intelligence_formatted['performance_network_exit_ratio'] = contact_intel.get('performance_network_exit_ratio', '')
            intelligence_formatted['performance_network_overall_median'] = contact_intel.get('performance_network_overall_median', '')
            intelligence_formatted['performance_network_guard_median'] = contact_intel.get('performance_network_guard_median', '')
            intelligence_formatted['performance_network_exit_median'] = contact_intel.get('performance_network_exit_median', '')
            intelligence_formatted['performance_operator_overall_pct'] = contact_intel.get('performance_operator_overall_pct', '')
            intelligence_formatted['performance_operator_guard_pct'] = contact_intel.get('performance_operator_guard_pct', '')
            intelligence_formatted['performance_operator_exit_pct'] = contact_intel.get('performance_operator_exit_pct', '')
            intelligence_formatted['performance_relay_count'] = contact_intel.get('performance_relay_count', 0)
            intelligence_formatted['maturity'] = contact_intel.get('maturity', '')
    
    # 4. Version compliance, status counts, version strings, and family support — single pass over members
    version_compliant = 0
    version_not_compliant = 0
    version_unknown = 0
    # Family support counters (merged into version compliance loop — DRY)
    family_support_counts = {'both': 0, 'happy_families': 0, 'my_family': 0, 'none': 0}
    version_status_counts = {
        'recommended': 0, 'experimental': 0, 'obsolete': 0,
        'new_in_series': 0, 'unrecommended': 0
    }
    version_status_versions = {
        'recommended': set(), 'experimental': set(), 'obsolete': set(),
        'new_in_series': set(), 'unrecommended': set()
    }
    # Map version_status strings to dict keys (handles "new in series" → "new_in_series")
    _STATUS_KEY_MAP = {
        'recommended': 'recommended', 'experimental': 'experimental',
        'obsolete': 'obsolete', 'new in series': 'new_in_series',
        'unrecommended': 'unrecommended'
    }
    for relay in members:
        # Version compliance
        rec = relay.get('recommended_version')
        if rec is True:
            version_compliant += 1
        elif rec is False:
            version_not_compliant += 1
        else:
            version_unknown += 1
        # Version status count + version string collection
        status = relay.get('version_status')
        if status:
            status_key = _STATUS_KEY_MAP.get(status)
            if status_key:
                version_status_counts[status_key] += 1
                version = relay.get('version')
                if version:
                    version_status_versions[status_key].add(version)
        # Family support type (pre-computed by _set_family_support_types)
        fst = relay.get('family_support_type', 'none')
        family_support_counts[fst] = family_support_counts.get(fst, 0) + 1
    
    # Format version compliance display (only show non-zero values for not compliant and unknown)
    # Add status indicators based on compliance ratio
    total_relays = len(members)
    
    if total_relays == 0:
        # Edge case: no relays
        intelligence_formatted['version_compliance'] = '0 compliant'
    elif version_compliant == total_relays:
        # All relays are compliant (recommended_version=True)
        intelligence_formatted['version_compliance'] = f'<span style="color: #2e7d2e; font-weight: bold;">All</span>, {version_compliant} (100%) compliant'
    elif version_compliant > 0 and (version_compliant / total_relays) > 0.5:
        # More than 50% are compliant
        compliant_pct = round((version_compliant / total_relays) * 100)
        result = f'<span style="color: #cc9900; font-weight: bold;">Partial</span>, {version_compliant} ({compliant_pct}%) compliant'
        # Add non-zero counts for not compliant and unknown
        parts = []
        if version_not_compliant > 0:
            not_compliant_pct = round((version_not_compliant / total_relays) * 100)
            parts.append(f"{version_not_compliant} ({not_compliant_pct}%) not compliant")
        if version_unknown > 0:
            unknown_pct = round((version_unknown / total_relays) * 100)
            parts.append(f"{version_unknown} ({unknown_pct}%) unknown")
        if parts:
            result += ', ' + ', '.join(parts)
        intelligence_formatted['version_compliance'] = result
    else:
        # 50% or less are compliant (or no compliant relays)
        compliant_pct = round((version_compliant / total_relays) * 100) if total_relays > 0 else 0
        result = f'<span style="color: #c82333; font-weight: bold;">Poor</span>, {version_compliant} ({compliant_pct}%) compliant'
        # Add non-zero counts for not compliant and unknown
        parts = []
        if version_not_compliant > 0:
            not_compliant_pct = round((version_not_compliant / total_relays) * 100)
            parts.append(f"{version_not_compliant} ({not_compliant_pct}%) not compliant")
        if version_unknown > 0:
            unknown_pct = round((version_unknown / total_relays) * 100)
            parts.append(f"{version_unknown} ({unknown_pct}%) unknown")
        if parts:
            result += ', ' + ', '.join(parts)
        intelligence_formatted['version_compliance'] = result
    
    # Format version status display (only show counts > 0) with version tooltips and percentages
    # Add status indicators based on recommended status ratio (similar to version compliance)
    version_status_parts = []
    version_status_tooltips = {}
    
    recommended_count = version_status_counts.get('recommended', 0)
    
    # Create tooltips for all status categories (including recommended)
    for status, count in version_status_counts.items():
        if count > 0:
            status_display = status.replace('_', ' ')  # Convert new_in_series to "new in series"
            
            # Create tooltip with actual Tor versions
            versions = sorted(list(version_status_versions[status]))
            if versions:
                tooltip_status = status_display.capitalize()
                version_status_tooltips[status] = f"{tooltip_status} versions: {', '.join(versions)}"
            else:
                version_status_tooltips[status] = f"{status_display.capitalize()} versions: (no version data)"
    
    # Format with status indicator based on recommended percentage
    if total_relays == 0:
        # Edge case: no relays
        intelligence_formatted['version_status'] = 'none'
    elif recommended_count == total_relays:
        # All relays have recommended status
        recommended_tooltip = version_status_tooltips.get('recommended', 'All relays have recommended versions')
        intelligence_formatted['version_status'] = f'<span style="color: #2e7d2e; font-weight: bold;">All</span>, <span title="{recommended_tooltip}" style="cursor: help;">{recommended_count} (100%) recommended</span>'
    elif recommended_count > 0 and (recommended_count / total_relays) > 0.5:
        # More than 50% have recommended status
        recommended_pct = round((recommended_count / total_relays) * 100)
        recommended_tooltip = version_status_tooltips.get('recommended', 'Recommended versions')
        result = f'<span style="color: #cc9900; font-weight: bold;">Partial</span>, <span title="{recommended_tooltip}" style="cursor: help;">{recommended_count} ({recommended_pct}%) recommended</span>'
        
        # Add other status counts with tooltips
        other_parts = []
        for status, count in version_status_counts.items():
            if status != 'recommended' and count > 0:
                status_display = status.replace('_', ' ')  # Convert new_in_series to "new in series"
                status_pct = round((count / total_relays) * 100)
                tooltip = version_status_tooltips.get(status, f'{status_display.capitalize()} versions')
                other_parts.append(f'<span title="{tooltip}" style="cursor: help;">{count} ({status_pct}%) {status_display}</span>')
        
        if other_parts:
            result += ', ' + ', '.join(other_parts)
        intelligence_formatted['version_status'] = result
    else:
        # 50% or less have recommended status (or no recommended relays)
        recommended_pct = round((recommended_count / total_relays) * 100) if total_relays > 0 else 0
        recommended_tooltip = version_status_tooltips.get('recommended', 'Recommended versions')
        result = f'<span style="color: #c82333; font-weight: bold;">Poor</span>, <span title="{recommended_tooltip}" style="cursor: help;">{recommended_count} ({recommended_pct}%) recommended</span>'
        
        # Add other status counts with tooltips
        other_parts = []
        for status, count in version_status_counts.items():
            if status != 'recommended' and count > 0:
                status_display = status.replace('_', ' ')  # Convert new_in_series to "new in series"
                status_pct = round((count / total_relays) * 100)
                tooltip = version_status_tooltips.get(status, f'{status_display.capitalize()} versions')
                other_parts.append(f'<span title="{tooltip}" style="cursor: help;">{count} ({status_pct}%) {status_display}</span>')
        
        if other_parts:
            result += ', ' + ', '.join(other_parts)
        intelligence_formatted['version_status'] = result
    
    intelligence_formatted['version_status_tooltips'] = version_status_tooltips
    
    # 4b. Family support counts (replaces former Family Certificate Migration section)
    # Counts are computed in the version compliance loop above — no separate loop needed.
    intelligence_formatted['family_support_counts'] = family_support_counts
    
    display_data['operator_intelligence'] = intelligence_formatted
    
    # 5. Overall uptime formatting
    display_data['uptime_formatted'] = _format_uptime_periods(operator_reliability)
    
    # 5.1. Network Uptime Percentiles formatting (6-month period)
    network_percentiles_formatted = {}
    if operator_reliability and operator_reliability.get('network_uptime_percentiles'):
        network_data = operator_reliability['network_uptime_percentiles']
        six_month_data = operator_reliability.get('overall_uptime', {}).get('6_months', {})
        
        if network_data and six_month_data:
            from .uptime_utils import format_network_percentiles_display, find_operator_percentile_position
            
            operator_avg = six_month_data.get('average', 0)
            total_network_relays = network_data.get('total_relays', 0)
            
            # Get operator's percentile range for dynamic tooltip
            position_info = find_operator_percentile_position(operator_avg, network_data)
            percentile_range = position_info.get('percentile_range', 'unknown')
            
            # Use the simplified display formatting function
            percentile_display = format_network_percentiles_display(network_data, operator_avg)
            
            if percentile_display:
                # Create enhanced tooltip with statistical methodology explanation
                if percentile_range != 'unknown':
                    tooltip_text = f"Statistical distribution of 6-month uptime performance across {total_network_relays:,} network relays. Each relay's daily uptime values are averaged over 6 months, then percentile ranks show performance quartiles. This operator falls in the {percentile_range} percentile range of network reliability."
                else:
                    tooltip_text = f"Statistical distribution of 6-month uptime performance across {total_network_relays:,} network relays. Each relay's daily uptime values are averaged over 6 months, then percentile ranks show performance quartiles."
                
                network_percentiles_formatted = {
                    'display': percentile_display,
                    'total_network_relays': total_network_relays,
                    'percentile_range': percentile_range,
                    'tooltip': tooltip_text
                }
    
    display_data['network_percentiles_formatted'] = network_percentiles_formatted
    
    # 6. Outliers calculations and formatting
    display_data['outliers'] = _format_outliers_data(operator_reliability)
    
    # 7. Uptime data timestamp (reuse existing uptime data)
    uptime_timestamp = None
    uptime_data = getattr(relay_set, 'uptime_data', None)
    if uptime_data and uptime_data.get('relays_published'):
        uptime_timestamp = uptime_data['relays_published'] + ' UTC'
    display_data['uptime_timestamp'] = uptime_timestamp
    
    # 8. Real-time downtime alerts (idea #8 from uptime integration proposals)
    downtime_alerts = calculate_operator_downtime_alerts(v, members, i, bandwidth_unit, relay_set)
    display_data['downtime_alerts'] = downtime_alerts
    
    # 9. Flag analysis
    operator_flag_analysis = compute_contact_flag_analysis(v, members, relay_set)
    display_data['flag_analysis'] = operator_flag_analysis
    
    # 10. Flag bandwidth analysis
    operator_flag_bandwidth_analysis = compute_contact_flag_bandwidth_analysis(v, members, relay_set)
    display_data['flag_bandwidth_analysis'] = operator_flag_bandwidth_analysis
    
    return display_data

def compute_contact_flag_analysis(contact_hash, members, relay_set):
    """
    Compute flag reliability analysis for contact operator using consolidated uptime data.
    
    This method uses pre-computed results from _reprocess_uptime_data(). If consolidated
    processing isn't available, no flag data is returned (section won't be shown).
    
    Args:
        contact_hash: Contact hash for the operator
        members: List of relay objects for the operator
        
    Returns:
        dict: Flag reliability analysis data or indication that no data is available
    """
    try:
        # Use consolidated uptime results if available (from _reprocess_uptime_data)
        if hasattr(relay_set, '_consolidated_uptime_results'):
            consolidated_results = relay_set._consolidated_uptime_results
            relay_uptime_data = consolidated_results['relay_uptime_data']
            network_flag_statistics = consolidated_results.get('network_flag_statistics', {})
            
            # Extract flag data for operator relays using pre-computed data
            operator_flag_data = {}
            
            for relay in members:
                fingerprint = relay.get('fingerprint', '')
                nickname = relay.get('nickname', 'Unknown')
                
                # Get actual flags this relay currently has (same approach as line 561)
                relay_flags = set(relay.get('flags', []))
                
                if fingerprint in relay_uptime_data:
                    flag_data = relay_uptime_data[fingerprint]['flag_data']
                    
                    for flag, periods in flag_data.items():
                        # Only include flag data for flags the relay currently has
                        if flag in relay_flags:
                            if flag not in operator_flag_data:
                                operator_flag_data[flag] = {}
                            for period, data in periods.items():
                                if period not in operator_flag_data[flag]:
                                    operator_flag_data[flag][period] = []
                                operator_flag_data[flag][period].append({
                                    'relay_nickname': data['relay_info']['nickname'],
                                    'relay_fingerprint': data['relay_info']['fingerprint'],
                                    'uptime': data['uptime'],
                                    'data_points': data['data_points']
                                })
            
            if not operator_flag_data:
                return {'has_flag_data': False, 'error': 'No flag data available for operator relays'}
            
            # Process flag reliability using pre-computed network statistics
            flag_reliability_results = process_operator_flag_reliability(
                operator_flag_data, network_flag_statistics
            )
            
            return {
                'has_flag_data': True,
                'flag_reliabilities': flag_reliability_results['flag_reliabilities'],
                'available_periods': flag_reliability_results['available_periods'],
                'period_display': flag_reliability_results['period_display'],
                'source': 'consolidated_processing'
            }
            
        else:
            # No consolidated results available - don't show flag reliability section
            return {'has_flag_data': False, 'error': 'Consolidated uptime processing not available'}
            
    except Exception as e:
        return {
            'has_flag_data': False, 
            'error': f'Flag analysis processing failed: {str(e)}',
            'source': 'error'
        }

def compute_contact_flag_bandwidth_analysis(contact_hash, members, relay_set):
    """
    Compute flag bandwidth analysis for contact operator using consolidated bandwidth data.
    
    This method uses pre-computed results from _reprocess_bandwidth_data(). If consolidated
    processing isn't available, no flag bandwidth data is returned.
    
    Args:
        contact_hash: Contact hash for the operator
        members: List of relay objects for the operator
        
    Returns:
        dict: Flag bandwidth analysis data or indication that no data is available
    """
    try:
        # Use consolidated bandwidth results if available (from _reprocess_bandwidth_data)
        if not hasattr(relay_set, '_consolidated_bandwidth_results'):
            return {'has_flag_data': False, 'error': 'Consolidated bandwidth processing not available'}
        
        consolidated_results = relay_set._consolidated_bandwidth_results
        if not consolidated_results:
            return {'has_flag_data': False, 'error': 'Consolidated bandwidth results are None'}
        
        relay_bandwidth_data = consolidated_results['relay_bandwidth_data']
        network_flag_statistics = consolidated_results.get('network_flag_statistics', {})
        
        # Extract flag bandwidth data for operator relays using pre-computed data
        operator_flag_data = {}
        
        for relay in members:
            fingerprint = relay.get('fingerprint', '')
            nickname = relay.get('nickname', 'Unknown')
            
            # Get actual flags this relay currently has
            relay_flags = set(relay.get('flags', []))
            
            if fingerprint in relay_bandwidth_data:
                flag_data = relay_bandwidth_data[fingerprint]['flag_data']
                
                for flag, bandwidth_averages in flag_data.items():
                    # Only include flag data for flags the relay currently has
                    if flag in relay_flags:
                        if flag not in operator_flag_data:
                            operator_flag_data[flag] = {}
                        for period in ['6_months', '1_year', '5_years']:
                            if period in bandwidth_averages and bandwidth_averages[period] > 0:
                                if period not in operator_flag_data[flag]:
                                    operator_flag_data[flag][period] = []
                                operator_flag_data[flag][period].append({
                                    'relay_nickname': nickname,
                                    'relay_fingerprint': fingerprint,
                                    'bandwidth': bandwidth_averages[period],
                                    'data_points': 0  # Not tracked in simplified structure
                                })
        
        if not operator_flag_data:
            return {'has_flag_data': False, 'error': 'No flag bandwidth data available for operator relays'}
            
        # Process flag bandwidth reliability using pre-computed network statistics
        flag_bandwidth_results = process_operator_flag_bandwidth_reliability(
            operator_flag_data, network_flag_statistics, relay_set
        )
        
        return {
            'has_flag_data': True,
            'flag_reliabilities': flag_bandwidth_results['flag_reliabilities'],
            'available_periods': flag_bandwidth_results['available_periods'],
            'period_display': flag_bandwidth_results['period_display'],
            'source': 'consolidated_processing'
        }
            
    except Exception as e:
        return {
            'has_flag_data': False, 
            'error': f'Flag bandwidth analysis processing failed: {str(e)}',
            'source': 'error'
        }

def process_operator_flag_bandwidth_reliability(operator_flag_data, network_flag_statistics, relay_set):
    """
    Process operator flag bandwidth data into display format with color coding.
    Mirrors the uptime flag processing but for bandwidth metrics.
    
    Args:
        operator_flag_data (dict): Flag bandwidth data for the operator
        network_flag_statistics (dict): Network-wide flag bandwidth statistics
        
    Returns:
        dict: Processed flag bandwidth data for template display
    """
    flag_reliabilities = {}
    periods_with_data = set()
    
    # Flag processing order (Exit > Guard > Fast > Running)
    flag_order = ['Exit', 'Guard', 'Fast', 'Running', 'Authority', 'HSDir', 'Stable', 'V2Dir']
    
    # Flag display configuration
    flag_display_mapping = {
        'Exit': {'icon': '🚪', 'display_name': 'Exit Node'},
        'Guard': {'icon': '🛡️', 'display_name': 'Entry Guard'},
        'Fast': {'icon': '⚡', 'display_name': 'Fast Relay'},
        'Running': {'icon': '🟢', 'display_name': 'Running'},
        'Authority': {'icon': '👑', 'display_name': 'Directory Authority'},
        'HSDir': {'icon': '📁', 'display_name': 'Hidden Service Directory'},
        'Stable': {'icon': '🎯', 'display_name': 'Stable Relay'},
        'V2Dir': {'icon': '📋', 'display_name': 'Version 2 Directory'}
    }
    
    # Process flags in the specified order
    for flag in flag_order:
        if flag not in operator_flag_data:
            continue
            
        periods = operator_flag_data[flag]
        
        if flag not in flag_display_mapping:
            continue
            
        flag_info = {
            'icon': flag_display_mapping[flag]['icon'],
            'display_name': flag_display_mapping[flag]['display_name'],
            'periods': {}
        }
        
        for period in ['6_months', '1_year', '5_years']:
            period_short = PERIOD_SHORT_NAMES.get(period, period)
            
            if period in periods and periods[period]:
                # Calculate average bandwidth for operator relays with this flag
                bandwidth_values = [relay_data['bandwidth'] for relay_data in periods[period]]
                avg_bandwidth = sum(bandwidth_values) / len(bandwidth_values)
                
                # Include all values >= 0 (0 is valid data meaning relay had no bandwidth)
                if avg_bandwidth >= 0:
                    periods_with_data.add(period_short)
                    
                    # Format bandwidth for display
                    unit = relay_set.bandwidth_formatter.determine_unit(avg_bandwidth)
                    formatted_bw = relay_set.bandwidth_formatter.format_bandwidth_with_unit(avg_bandwidth, unit)
                    bandwidth_display = f"{formatted_bw} {unit}"
                    
                    # Determine color coding and tooltip
                    color_class = ''  # Default: no special coloring (black text)
                    tooltip = f'{flag} flag bandwidth over {period_short}: {bandwidth_display}'
                    
                    # Add network comparison if available
                    if (flag in network_flag_statistics and 
                        period in network_flag_statistics[flag] and
                        network_flag_statistics[flag][period]):
                        
                        net_stats = network_flag_statistics[flag][period]
                        net_mean_unit = relay_set.bandwidth_formatter.determine_unit(net_stats["mean"])
                        net_mean_formatted = relay_set.bandwidth_formatter.format_bandwidth_with_unit(net_stats["mean"], net_mean_unit)
                        tooltip += f' (network μ: {net_mean_formatted} {net_mean_unit})'
                        
                        # Enhanced color coding logic for bandwidth - match legend
                        if avg_bandwidth <= net_stats['two_sigma_low']:
                            color_class = 'statistical-outlier-low'  # Red - Poor (≥2σ from network μ)
                        elif avg_bandwidth > net_stats['mean'] * 1.5:  # High performance threshold
                            color_class = 'high-performance'  # Green - High performance (>1.5x μ)
                        elif avg_bandwidth < net_stats['mean']:
                            color_class = 'below-mean'  # Yellow - Below average (<μ of network)
                        # EXPLICIT: Values between mean and 1.5x mean get no color_class (black)
                    
                    else:
                        # Fallback color coding when no network statistics available
                        if avg_bandwidth <= 0:
                            color_class = 'statistical-outlier-low'
                        # Default: no special coloring (black)
                    
                    flag_info['periods'][period_short] = {
                        'value': avg_bandwidth,
                        'value_display': bandwidth_display,
                        'color_class': color_class,
                        'tooltip': tooltip,
                        'relay_count': len(periods[period])
                    }
            
        # Only include flag if it has data for at least one period
        if flag_info['periods']:
            flag_reliabilities[flag] = flag_info
    
    # Generate dynamic period display string
    period_order = ['6M', '1Y', '5Y']
    available_periods = [p for p in period_order if p in periods_with_data]
    period_display = '/'.join(available_periods) if available_periods else 'No Data'
    
    return {
        'flag_reliabilities': flag_reliabilities,
        'available_periods': available_periods,
        'period_display': period_display,
        'has_data': bool(available_periods)
    }

def process_operator_flag_reliability(operator_flag_data, network_flag_statistics):
    """
    Process flag reliability metrics for an operator using pre-computed network statistics.
    
    Args:
        operator_flag_data: Operator's flag-specific uptime data
        network_flag_statistics: Network-wide flag statistics for comparison
        
    Returns:
        dict: Processed flag reliability metrics with available periods info
    """
    flag_display_mapping = {
        'Running': {'icon': '🟢', 'display_name': 'Running Operation'},
        'Fast': {'icon': '⚡', 'display_name': 'Fast Relay'},
        'Stable': {'icon': '🛡️', 'display_name': 'Stable Operation'}, 
        'Guard': {'icon': '🛡️', 'display_name': 'Entry Guard'},
        'Exit': {'icon': '🚪', 'display_name': 'Exit Node'},
        'HSDir': {'icon': '📂', 'display_name': 'Hidden Services'},
        'Authority': {'icon': '⚖️', 'display_name': 'Directory Authority'},
        'V2Dir': {'icon': '📁', 'display_name': 'Directory Services'},
        'BadExit': {'icon': '🚫', 'display_name': 'Bad Exit'}
    }
    
    # Define flag ordering for consistent display - Hidden Services before Directory Services
    flag_order = ['BadExit', 'Stable', 'Fast', 'Running', 'Authority', 'Guard', 'Exit', 'HSDir', 'V2Dir']
    
    flag_reliabilities = {}
    
    # Track which time periods have data across all flags
    periods_with_data = set()
    
    # Process flags in the specified order
    for flag in flag_order:
        if flag not in operator_flag_data:
            continue
            
        periods = operator_flag_data[flag]
        
        if flag not in flag_display_mapping:
            continue
            
        flag_info = {
            'icon': flag_display_mapping[flag]['icon'],
            'display_name': flag_display_mapping[flag]['display_name'],
            'periods': {}
        }
        
        for period in ['1_month', '6_months', '1_year', '5_years']:
            period_short = PERIOD_SHORT_NAMES.get(period, period)
            
            if period in periods and periods[period]:
                # Calculate average uptime for operator relays with this flag
                uptime_values = [relay_data['uptime'] for relay_data in periods[period]]
                avg_uptime = sum(uptime_values) / len(uptime_values)
                
                # Include all values >= 0 (0% is valid data meaning relay never had this flag)
                if avg_uptime >= 0:
                    periods_with_data.add(period_short)
                    
                    # Determine color coding and tooltip
                    color_class = ''
                    tooltip = f'{flag} flag uptime over {period_short}: {avg_uptime:.1f}%'
                    
                    # Add network comparison if available
                    if (flag in network_flag_statistics and 
                        period in network_flag_statistics[flag] and
                        network_flag_statistics[flag][period]):
                        
                        net_stats = network_flag_statistics[flag][period]
                        tooltip += f' (network μ: {net_stats["mean"]:.1f}%, 2σ: {net_stats["two_sigma_low"]:.1f}%)'
                        
                        # Enhanced color coding logic: prioritize statistical outliers over >99%
                        # Special handling for very low values (≤1%) - likely to be statistical outliers
                        if avg_uptime <= 1.0:
                            color_class = 'statistical-outlier-low'
                        elif avg_uptime <= net_stats['two_sigma_low']:
                            color_class = 'statistical-outlier-low'
                        elif avg_uptime >= 99.0:
                            color_class = 'high-performance'
                        elif avg_uptime > net_stats['two_sigma_high']:
                            color_class = 'statistical-outlier-high'
                        elif avg_uptime < net_stats['mean']:
                            color_class = 'below-mean'
                        # Note: Removed default above-mean green coloring per user feedback
                    
                    else:
                        # Fallback color coding when no network statistics available
                        if avg_uptime <= 1.0:
                            color_class = 'statistical-outlier-low'
                        elif avg_uptime >= 99.0:
                            color_class = 'high-performance'
                        # Default: no special coloring
                    
                    flag_info['periods'][period_short] = {
                        'value': avg_uptime,
                        'color_class': color_class,
                        'tooltip': tooltip,
                        'relay_count': len(periods[period])
                    }
            
        # Only include flag if it has data for at least one period
        if flag_info['periods']:
            flag_reliabilities[flag] = flag_info
    
    # Generate dynamic period display string
    period_order = ['1M', '6M', '1Y', '5Y']
    available_periods = [p for p in period_order if p in periods_with_data]
    period_display = '/'.join(available_periods) if available_periods else 'No Data'
    
    return {
        'flag_reliabilities': flag_reliabilities,
        'available_periods': available_periods,
        'period_display': period_display,
        'has_data': bool(available_periods)
    }

def calculate_operator_downtime_alerts(contact_hash, operator_relays, contact_data, bandwidth_unit, relay_set):
    """
    Calculate real-time downtime alerts for operator contact pages.
    
    Shows offline relays by type with traffic percentages and impact calculations.
    Implements idea #8 from uptime integration proposals.
    
    Args:
        contact_hash (str): Contact hash for the operator  
        operator_relays (list): List of relay objects for this operator
        contact_data (dict): Pre-computed contact statistics (guard_count, bandwidth, etc.)
        bandwidth_unit (str): Bandwidth unit for display (MB/s, GB/s, etc.)
        
    Returns:
        dict: Downtime alert data with offline counts, impact metrics, and tooltips
    """
    if not operator_relays:
        return None
    
    downtime_alerts = {
        'offline_counts': {
            'guard': 0,
            'middle': 0, 
            'exit': 0
        },
        'offline_bandwidth_impact': {
            'total_offline_bandwidth': 0,  # bytes
            'total_offline_bandwidth_formatted': '0.00',  # formatted with unit
            'offline_bandwidth_percentage': 0.0,  # percentage of operator's total bandwidth
            'total_operator_bandwidth_formatted': '0.00'  # formatted operator total
        },
        'offline_consensus_weight_impact': {
            'total_offline_cw_fraction': 0.0,  # fraction of network consensus weight
            'offline_cw_percentage_of_operator': 0.0,  # percentage of operator's total CW  
            'total_operator_cw_percentage': 0.0  # operator's total network influence
        },
        'offline_relay_details': {
            'guard_relays': [],  # List of offline guard relays with last_seen
            'middle_relays': [],  # List of offline middle relays with last_seen  
            'exit_relays': []   # List of offline exit relays with last_seen
        },
        'has_offline_relays': False
    }
    
    # Calculate network totals for percentage calculations (validation method 1)
    if not hasattr(relay_set, 'json') or not relay_set.json.get('network_totals'):
        return downtime_alerts
        
    network_totals = relay_set.json['network_totals']
    total_network_guard_cw = network_totals.get('guard_consensus_weight', 0)
    total_network_middle_cw = network_totals.get('middle_consensus_weight', 0) 
    total_network_exit_cw = network_totals.get('exit_consensus_weight', 0)
    total_network_cw = total_network_guard_cw + total_network_middle_cw + total_network_exit_cw
    
    # Calculate operator totals for impact percentage calculations (validation method 2)
    operator_total_bandwidth = contact_data.get('bandwidth', 0)  # bytes
    operator_total_cw_fraction = contact_data.get('consensus_weight_fraction', 0.0)
    
    # Track offline totals for impact calculations
    total_offline_bandwidth = 0
    total_offline_cw_fraction = 0.0
    
    # Process each relay to check if offline and categorize by flags
    for relay in operator_relays:
        # Check if relay is offline (not running)
        if not relay.get('running', False):
            downtime_alerts['has_offline_relays'] = True
            
            # Get relay basic info
            nickname = relay.get('nickname', 'Unknown')
            fingerprint = relay.get('fingerprint', '')
            last_seen = relay.get('last_seen', 'Unknown')
            observed_bandwidth = relay.get('observed_bandwidth', 0)
            consensus_weight = relay.get('consensus_weight', 0)
            flags = relay.get('flags', [])
            
            # Format last seen time using existing utility
            if last_seen and last_seen != 'Unknown':
                last_seen_formatted = format_time_ago(last_seen)
            else:
                last_seen_formatted = 'Unknown'
            
            # Add to total offline impact calculations
            total_offline_bandwidth += observed_bandwidth
            
            # Convert consensus weight to fraction for network percentage calculation
            if total_network_cw > 0:
                relay_cw_fraction = consensus_weight / total_network_cw
                total_offline_cw_fraction += relay_cw_fraction
            
            # Create relay info for tooltips
            relay_info = {
                'nickname': nickname,
                'fingerprint': fingerprint[:8],  # Short fingerprint for display
                'last_seen': last_seen_formatted,
                'bandwidth': observed_bandwidth,
                'consensus_weight': consensus_weight,
                'display_text': f"{nickname} ({last_seen_formatted})"
            }
            
            # Categorize by relay type based on flags
            if 'Guard' in flags:
                downtime_alerts['offline_counts']['guard'] += 1
                downtime_alerts['offline_relay_details']['guard_relays'].append(relay_info)
                
            if 'Exit' in flags:
                downtime_alerts['offline_counts']['exit'] += 1  
                downtime_alerts['offline_relay_details']['exit_relays'].append(relay_info)
                
            # Middle relays are all relays that aren't Guard or Exit only, or relays that are both
            # This matches the logic used elsewhere in the codebase for middle relay classification
            if not flags or ('Guard' not in flags and 'Exit' not in flags) or ('Guard' in flags and 'Exit' in flags):
                downtime_alerts['offline_counts']['middle'] += 1
                downtime_alerts['offline_relay_details']['middle_relays'].append(relay_info)
    
    # Calculate bandwidth impact metrics
    if operator_total_bandwidth > 0:
        offline_bandwidth_percentage = (total_offline_bandwidth / operator_total_bandwidth) * 100
    else:
        offline_bandwidth_percentage = 0.0
        
    downtime_alerts['offline_bandwidth_impact'] = {
        'total_offline_bandwidth': total_offline_bandwidth,
        'total_offline_bandwidth_formatted': relay_set.bandwidth_formatter.format_bandwidth_with_unit(total_offline_bandwidth, bandwidth_unit),
        'offline_bandwidth_percentage': offline_bandwidth_percentage,
        'total_operator_bandwidth_formatted': relay_set.bandwidth_formatter.format_bandwidth_with_unit(operator_total_bandwidth, bandwidth_unit)
    }
    
    # Calculate consensus weight impact metrics  
    if operator_total_cw_fraction > 0:
        offline_cw_percentage_of_operator = (total_offline_cw_fraction / operator_total_cw_fraction) * 100
    else:
        offline_cw_percentage_of_operator = 0.0
        
    downtime_alerts['offline_consensus_weight_impact'] = {
        'total_offline_cw_fraction': total_offline_cw_fraction,
        'total_offline_cw_percentage': total_offline_cw_fraction * 100,  # Network percentage
        'offline_cw_percentage_of_operator': offline_cw_percentage_of_operator,
        'total_operator_cw_percentage': operator_total_cw_fraction * 100
    }
    
    # Calculate traffic percentages for each relay type (validation against operator totals)
    # This provides the "X% of observed traffic" metrics requested
    guard_traffic_percentage = 0.0
    middle_traffic_percentage = 0.0
    exit_traffic_percentage = 0.0
    
    if contact_data.get('guard_bandwidth', 0) > 0:
        guard_offline_bandwidth = sum(r['bandwidth'] for r in downtime_alerts['offline_relay_details']['guard_relays'])
        guard_traffic_percentage = (guard_offline_bandwidth / contact_data['guard_bandwidth']) * 100
        
    if contact_data.get('middle_bandwidth', 0) > 0:
        middle_offline_bandwidth = sum(r['bandwidth'] for r in downtime_alerts['offline_relay_details']['middle_relays'])
        middle_traffic_percentage = (middle_offline_bandwidth / contact_data['middle_bandwidth']) * 100
        
    if contact_data.get('exit_bandwidth', 0) > 0:
        exit_offline_bandwidth = sum(r['bandwidth'] for r in downtime_alerts['offline_relay_details']['exit_relays'])
        exit_traffic_percentage = (exit_offline_bandwidth / contact_data['exit_bandwidth']) * 100
    
    # Add traffic percentages to offline counts for display
    downtime_alerts['traffic_percentages'] = {
        'guard': guard_traffic_percentage,
        'middle': middle_traffic_percentage,
        'exit': exit_traffic_percentage
    }
    
    return downtime_alerts

def calculate_uptime_display(relay, _format_time_ago_fn=None):
    """
    Calculate uptime/downtime display for a single relay.
    
    Logic:
    - For running relays: Show uptime from last_restarted
    - For offline relays: Show downtime from last_seen (avoids incorrect long downtimes)
    
    Args:
        relay (dict): Relay data dictionary
        _format_time_ago_fn: Deprecated parameter, ignored. Uses module-level format_time_ago.
        
    Returns:
        str: Formatted uptime display (e.g., "UP 2d 5h ago", "DOWN 3h 45m ago", "Unknown")
    """
    if not relay.get('last_restarted'):
        return "Unknown"
        
    is_running = relay.get('running', False)
    
    if is_running:
        # For running relays, show uptime from last_restarted
        time_since_restart = format_time_ago(relay['last_restarted'])
        if time_since_restart and time_since_restart != "unknown":
            return f"UP {time_since_restart}"
        else:
            return "Unknown"
    else:
        # For offline relays, show downtime from last_seen (when it was last observed online)
        # This avoids showing incorrect long downtimes based on old last_restarted timestamps
        if relay.get('last_seen'):
            time_since_last_seen = format_time_ago(relay['last_seen'])
            if time_since_last_seen and time_since_last_seen != "unknown":
                return f"DOWN {time_since_last_seen}"
            else:
                return "DOWN (unknown)"
        else:
            return "DOWN (unknown)"


