"""
Bandwidth calculation utilities for operator performance analysis.

This module provides shared functions for calculating bandwidth statistics
to enable historic bandwidth leaderboard categories similar to uptime leaderboards.
"""

import statistics

def calculate_network_cv_statistics(all_operators_data):
    """Calculate network-wide CV statistics for dynamic threshold setting."""
    if not all_operators_data or len(all_operators_data) < 10:
        return None
        
    try:
        cv_values = sorted([cv for cv in all_operators_data if cv >= 0])
        if len(cv_values) < 10:
            return None
            
        return {
            'p25': statistics.quantiles(cv_values, n=4)[0],
            'p50': statistics.median(cv_values),
            'p75': statistics.quantiles(cv_values, n=4)[2],
            'p90': statistics.quantiles(cv_values, n=10)[8],
            'total_operators': len(cv_values),
            'mean': statistics.mean(cv_values),
            'std_dev': statistics.stdev(cv_values)
        }
    except Exception:
        return None

def calculate_relay_bandwidth_average(bandwidth_values):
    """Calculate average bandwidth from a list of bandwidth values."""
    if not bandwidth_values:
        return 0.0
    
    total = count = 0
    for v in bandwidth_values:
        if v is not None and isinstance(v, (int, float)) and v >= 0:
            total += v
            count += 1
    
    return total / count if count >= 30 else 0.0  # Need at least 30 data points

def _build_bandwidth_map(bandwidth_data):
    """Build shared fingerprint->bandwidth mapping to eliminate redundant mapping creation."""
    bandwidth_map = {}
    if bandwidth_data and bandwidth_data.get('relays'):
        for relay in bandwidth_data['relays']:
            fingerprint = relay.get('fingerprint')
            if fingerprint:
                bandwidth_map[fingerprint] = relay
    return bandwidth_map

def _get_stability_category(cv, network_cv_stats):
    """Determine stability category from CV value and network thresholds."""
    if network_cv_stats and all(k in network_cv_stats for k in ['p25', 'p50', 'p90']):
        if cv < network_cv_stats['p25']: return "Great", "great"
        elif cv < network_cv_stats['p50']: return "Good", "good"
        elif cv < network_cv_stats['p90']: return "Variable", "variable"
        else: return "Extreme", "extreme"
    else:
        # Static fallback thresholds
        if cv < 25: return "Great", "great"
        elif cv < 50: return "Good", "good"
        elif cv < 100: return "Variable", "variable"
        else: return "Extreme", "extreme"

def _calculate_bandwidth_stability(mean_bandwidth, std_dev, network_cv_stats, bandwidth_formatter):
    """Calculate bandwidth stability (coefficient of variation) metrics."""
    if mean_bandwidth <= 0 or std_dev < 0:
        return None
        
    cv = (std_dev / mean_bandwidth) * 100
    category, color = _get_stability_category(cv, network_cv_stats)
    
    # Format units
    std_dev_formatted = mean_formatted = std_dev
    std_dev_unit = mean_unit = "bytes/s"
    
    if bandwidth_formatter:
        std_dev_unit = bandwidth_formatter.determine_unit(std_dev)
        mean_unit = bandwidth_formatter.determine_unit(mean_bandwidth)
        std_dev_formatted = bandwidth_formatter.format_bandwidth_with_unit(std_dev, std_dev_unit)
        mean_formatted = bandwidth_formatter.format_bandwidth_with_unit(mean_bandwidth, mean_unit)
    
    return {
        'coefficient_of_variation': cv,
        'category': category,
        'color': color,
        'std_dev_formatted': std_dev_formatted,
        'std_dev_unit': std_dev_unit,
        'mean_formatted': mean_formatted,
        'mean_unit': mean_unit
    }

def _calculate_peak_performance(operator_relays, bandwidth_map, period, mean_bandwidth):
    """Calculate peak performance and capacity utilization metrics."""
    all_values = []
    historical_max_values = []
    historical_max_by_period = {}
    
    for relay in operator_relays:
        fingerprint = relay.get('fingerprint', '')
        if not fingerprint:
            continue
            
        relay_bandwidth = bandwidth_map.get(fingerprint)
        if not relay_bandwidth or not relay_bandwidth.get('read_history'):
            continue
            
        # Current period values
        period_data = relay_bandwidth['read_history'].get(period, {})
        if period_data.get('values') and period_data.get('factor'):
            factor = period_data['factor']
            values = [v * factor for v in period_data['values'] if v is not None and v >= 0]
            all_values.extend(values)
        
        # Historical values for peak detection
        for hist_period in ['1_year', '5_years']:
            hist_data = relay_bandwidth['read_history'].get(hist_period, {})
            if hist_data.get('values') and hist_data.get('factor'):
                hist_factor = hist_data['factor']
                hist_values = [v * hist_factor for v in hist_data['values'] if v is not None and v >= 0]
                if hist_values:
                    period_max = max(hist_values)
                    if hist_period not in historical_max_by_period or period_max > historical_max_by_period[hist_period]:
                        historical_max_by_period[hist_period] = period_max
                    historical_max_values.extend(hist_values)
    
    if not historical_max_values or mean_bandwidth <= 0:
        return None, None
    
    historical_max = max(historical_max_values)
    
    # Determine peak source for dynamic display
    peak_source_period = None
    for period_name, period_max in historical_max_by_period.items():
        if period_max == historical_max:
            peak_source_period = period_name
            break
    
    period_display = {
        '5_years': 'all-time 5yr peak',
        '1_year': 'all-time 1yr peak'
    }.get(peak_source_period, 'historical peak')
    
    ratio = mean_bandwidth / historical_max
    utilization = ratio * 100
    
    peak_performance = {
        'ratio': ratio,
        'percentage': ratio * 100,
        'historical_peak': historical_max,
        'time_periods': '1Y/5Y data',
        'display': f"{ratio * 100:.0f}% of historical peak (1Y/5Y data)"
    }
    
    capacity_utilization = {
        'utilization_percentage': utilization,
        'historical_maximum': historical_max,
        'peak_source_period': peak_source_period,
        'time_periods': f'current 6mo avg vs {period_display}',
        'display': f"{utilization:.0f}% of all-time peak capacity (current 6mo avg vs {period_display})"
    }
    
    return peak_performance, capacity_utilization

def _calculate_growth_trend(operator_relays, bandwidth_map, period):
    """Calculate simplified growth trend metrics."""
    if period != '6_months':
        return None
        
    # Build relay bandwidth arrays
    relay_arrays = []
    for relay in operator_relays:
        fingerprint = relay.get('fingerprint', '')
        relay_bandwidth = bandwidth_map.get(fingerprint)
        if relay_bandwidth and relay_bandwidth.get('read_history'):
            period_data = relay_bandwidth['read_history'].get(period, {})
            if period_data.get('values') and period_data.get('factor'):
                relay_arrays.append({
                    'values': period_data['values'],
                    'factor': period_data['factor']
                })
    
    if not relay_arrays:
        return None
    
    # Calculate daily totals
    max_length = max(len(r['values']) for r in relay_arrays)
    daily_totals = []
    
    for day_index in range(max_length):
        day_total = valid_count = 0
        for relay_data in relay_arrays:
            if day_index < len(relay_data['values']):
                value = relay_data['values'][day_index]
                if value is not None and isinstance(value, (int, float)) and value >= 0:
                    day_total += value * relay_data['factor']
                    valid_count += 1
        
        if valid_count > 0:
            daily_totals.append(day_total)
    
    if len(daily_totals) < 60:  # Need at least ~2 months
        return None
    
    # Compare first vs last third
    third = len(daily_totals) // 3
    older_avg = statistics.mean(daily_totals[:third])
    recent_avg = statistics.mean(daily_totals[-third:])
    
    if older_avg <= 0:
        return None
    
    growth_rate = ((recent_avg - older_avg) / older_avg) * 100
    
    # Simplified trend description
    if growth_rate > 5:
        trend_desc = "Growth"
    elif growth_rate < -5:
        trend_desc = "Decline" 
    else:
        trend_desc = "Stable"
    
    # Try to get actual data collection date
    data_end = None
    for relay in operator_relays:
        fingerprint = relay.get('fingerprint', '')
        relay_bandwidth = bandwidth_map.get(fingerprint)
        if relay_bandwidth and relay_bandwidth.get('read_history'):
            period_data = relay_bandwidth['read_history'].get(period, {})
            if period_data.get('last'):
                try:
                    from .relays import parse_onionoo_timestamp
                    data_end = parse_onionoo_timestamp(period_data['last'])
                    break
                except:
                    pass
    
    # Create display with actual dates if available
    if data_end:
        import datetime
        days_per_third = len(daily_totals) // 3
        recent_start = data_end - datetime.timedelta(days=days_per_third)
        older_start = data_end - datetime.timedelta(days=len(daily_totals))
        older_end = data_end - datetime.timedelta(days=len(daily_totals) - days_per_third)
        
        recent_display = f"most recent ({recent_start.strftime('%b %d')} - {data_end.strftime('%b %d, %Y')})"
        older_display = f"least recent ({older_start.strftime('%b %d')} - {older_end.strftime('%b %d, %Y')})"
        
        display = f"{trend_desc} ({growth_rate:+.1f}%) for {recent_display} vs {older_display}"
    else:
        display = f"{trend_desc} ({growth_rate:+.1f}%)"
    
    return {
        'growth_rate': growth_rate,
        'trend_description': trend_desc,
        'display': display
    }

def calculate_bandwidth_reliability_metrics(operator_relays, bandwidth_data, period, mean_bandwidth, std_dev, network_cv_stats=None, bandwidth_formatter=None):
    """Calculate comprehensive bandwidth reliability metrics for an operator."""
    metrics = {
        'bandwidth_stability': None,
        'peak_performance': None,
        'growth_trend': None,
        'capacity_utilization': None
    }
    
    if not operator_relays or not bandwidth_data or mean_bandwidth <= 0:
        return metrics
    
    # Build shared bandwidth mapping once
    bandwidth_map = _build_bandwidth_map(bandwidth_data)
    
    # Calculate individual metrics
    metrics['bandwidth_stability'] = _calculate_bandwidth_stability(
        mean_bandwidth, std_dev, network_cv_stats, bandwidth_formatter)
    
    peak_perf, capacity_util = _calculate_peak_performance(
        operator_relays, bandwidth_map, period, mean_bandwidth)
    metrics['peak_performance'] = peak_perf
    metrics['capacity_utilization'] = capacity_util
    
    metrics['growth_trend'] = _calculate_growth_trend(
        operator_relays, bandwidth_map, period)
    
    return metrics

def extract_operator_daily_bandwidth_totals(operator_relays, bandwidth_data, time_period):
    """Calculate daily total bandwidth for an operator."""
    if not operator_relays or not bandwidth_data:
        return {'daily_totals': [], 'average_daily_total': 0.0, 'valid_days': 0}
    
    bandwidth_map = _build_bandwidth_map(bandwidth_data)
    
    # Collect relay bandwidth arrays
    relay_arrays = []
    for relay in operator_relays:
        fingerprint = relay.get('fingerprint', '')
        relay_bandwidth = bandwidth_map.get(fingerprint)
        if relay_bandwidth and relay_bandwidth.get('read_history'):
            period_data = relay_bandwidth['read_history'].get(time_period, {})
            if period_data.get('values') and period_data.get('factor'):
                relay_arrays.append({
                    'values': period_data['values'],
                    'factor': period_data['factor']
                })
    
    if not relay_arrays:
        return {'daily_totals': [], 'average_daily_total': 0.0, 'valid_days': 0}
    
    # Calculate daily totals
    max_length = max(len(r['values']) for r in relay_arrays)
    daily_totals = []
    
    for day_index in range(max_length):
        day_total = valid_count = 0
        for relay_data in relay_arrays:
            if day_index < len(relay_data['values']):
                value = relay_data['values'][day_index]
                if value is not None and isinstance(value, (int, float)) and value >= 0:
                    day_total += value * relay_data['factor']
                    valid_count += 1
        
        if valid_count > 0:
            daily_totals.append(day_total)
    
    avg_daily = statistics.mean(daily_totals) if daily_totals else 0.0
    return {
        'daily_totals': daily_totals,
        'average_daily_total': avg_daily,
        'valid_days': len(daily_totals)
    }

def extract_relay_bandwidth_for_period(operator_relays, bandwidth_data, time_period):
    """Extract bandwidth data for all relays in an operator for a specific time period."""
    bandwidth_values = []
    relay_breakdown = {}
    
    bandwidth_map = _build_bandwidth_map(bandwidth_data)
    
    for relay in operator_relays:
        fingerprint = relay.get('fingerprint', '')
        nickname = relay.get('nickname', 'Unknown')
        
        if not fingerprint:
            continue
            
        relay_bandwidth = bandwidth_map.get(fingerprint)
        if relay_bandwidth and relay_bandwidth.get('read_history'):
            period_data = relay_bandwidth['read_history'].get(time_period, {})
            if period_data.get('values') and period_data.get('factor'):
                factor = period_data['factor']
                actual_values = [v * factor for v in period_data['values'] if v is not None]
                
                avg_bandwidth = calculate_relay_bandwidth_average(actual_values)
                if avg_bandwidth > 0:
                    bandwidth_values.append(avg_bandwidth)
                    relay_breakdown[fingerprint] = {
                        'nickname': nickname,
                        'fingerprint': fingerprint,
                        'bandwidth': avg_bandwidth,
                        'data_points': len(actual_values)
                    }
    
    return {
        'bandwidth_values': bandwidth_values,
        'relay_breakdown': relay_breakdown,
        'valid_relays': len(bandwidth_values)
    }

def process_all_bandwidth_data_consolidated(all_relays, bandwidth_data, include_flag_analysis=True):
    """Consolidated bandwidth data processing function."""
    if not bandwidth_data or not all_relays:
        return {'relay_bandwidth_data': {}, 'network_flag_statistics': {} if include_flag_analysis else None}
    
    # Create fingerprint mapping
    relay_fingerprint_map = {}
    for relay in all_relays:
        fingerprint = relay.get('fingerprint')
        if fingerprint:
            relay_fingerprint_map[fingerprint] = relay
    
    # Initialize data structures
    relay_bandwidth_data = {}
    network_flag_data = {}
    
    # Process bandwidth data
    for bandwidth_relay in bandwidth_data.get('relays', []):
        fingerprint = bandwidth_relay.get('fingerprint')
        if not fingerprint:
            continue
            
        relay_obj = relay_fingerprint_map.get(fingerprint)
        bandwidth_averages = {'6_months': 0.0, '1_year': 0.0, '5_years': 0.0}
        read_history = bandwidth_relay.get('read_history', {})
        
        for period in ['6_months', '1_year', '5_years']:
            period_data = read_history.get(period, {})
            if period_data.get('values') and period_data.get('factor'):
                factor = period_data['factor']
                actual_values = [v * factor for v in period_data['values'] if v is not None]
                bandwidth_averages[period] = calculate_relay_bandwidth_average(actual_values)
        
        # Flag analysis
        flag_data = {}
        if include_flag_analysis and relay_obj:
            flags = relay_obj.get('flags', [])
            for flag in ['Fast', 'Stable', 'Guard', 'Exit', 'HSDir', 'V2Dir', 'Authority', 'Running']:
                if flag in flags:
                    if flag not in network_flag_data:
                        network_flag_data[flag] = {}
                    
                    for period in ['6_months', '1_year', '5_years']:
                        if bandwidth_averages[period] > 0:
                            if period not in network_flag_data[flag]:
                                network_flag_data[flag][period] = []
                            network_flag_data[flag][period].append(bandwidth_averages[period])
                    
                    flag_data[flag] = bandwidth_averages
        
        relay_bandwidth_data[fingerprint] = {
            'bandwidth_averages': bandwidth_averages,
            'flag_data': flag_data,
            # Overload fields from bandwidth endpoint (for stability computation)
            'overload_ratelimits': bandwidth_relay.get('overload_ratelimits'),
            'overload_fd_exhausted': bandwidth_relay.get('overload_fd_exhausted'),
        }
    
    # Calculate network flag statistics
    network_flag_statistics = {}
    if include_flag_analysis:
        for flag, periods in network_flag_data.items():
            network_flag_statistics[flag] = {}
            for period, values in periods.items():
                if values and len(values) >= 3:
                    mean_bw = statistics.mean(values)
                    std_dev = statistics.stdev(values) if len(values) > 1 else 0
                    
                    network_flag_statistics[flag][period] = {
                        'mean': mean_bw,
                        'std_dev': std_dev,
                        'two_sigma_low': max(0.0, mean_bw - 2 * std_dev),
                        'two_sigma_high': mean_bw + 2 * std_dev,
                        'count': len(values)
                    }
    
    return {
        'relay_bandwidth_data': relay_bandwidth_data,
        'network_flag_statistics': network_flag_statistics if include_flag_analysis else None,
        'processing_summary': {
            'total_relays_processed': len(relay_bandwidth_data),
            'network_relays_with_bandwidth': len([r for r in relay_bandwidth_data.values() if any(p > 0 for p in r['bandwidth_averages'].values())]),
            'flags_found': list(network_flag_data.keys()) if include_flag_analysis else []
        }
    }