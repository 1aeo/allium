"""
Bandwidth calculation utilities for operator performance analysis.

This module provides shared functions for calculating bandwidth statistics
to enable historic bandwidth leaderboard categories similar to uptime leaderboards.
"""

import statistics
import math
from .error_handlers import handle_calculation_errors
from .statistical_utils import StatisticalUtils


def calculate_relay_bandwidth_average(bandwidth_values):
    """
    Calculate average bandwidth from a list of bandwidth values.
    
    OPTIMIZATION: Single-pass calculation eliminates redundant iterations
    through bandwidth data (filter + sum + len → single loop).
    
    Args:
        bandwidth_values (list): List of bandwidth values in bytes/second
        
    Returns:
        float: Average bandwidth in bytes/second, or 0.0 if no valid values
    """
    if not bandwidth_values:
        return 0.0
    
    # OPTIMIZATION: Single pass - filter, count, and sum simultaneously
    # Eliminates 3 separate iterations (list comprehension, sum(), len())
    total = 0
    count = 0
    for v in bandwidth_values:
        if v is not None and isinstance(v, (int, float)) and v >= 0:
            total += v
            count += 1
    
    # Early exit for insufficient data (need at least 30 data points)
    if count < 30:  # Need at least 30 data points (1 month of daily data)
        return 0.0
    
    # Calculate average bandwidth
    avg_bandwidth = total / count
    
    return avg_bandwidth


def find_relay_bandwidth_data(fingerprint, bandwidth_data):
    """
    Find bandwidth data for a specific relay by fingerprint.
    
    Args:
        fingerprint (str): Relay fingerprint to search for
        bandwidth_data (dict): Bandwidth data from Onionoo API
        
    Returns:
        dict or None: Relay bandwidth data if found, None otherwise
    """
    if not bandwidth_data or not fingerprint:
        return None
    
    for bandwidth_relay in bandwidth_data.get('relays', []):
        if bandwidth_relay.get('fingerprint') == fingerprint:
            return bandwidth_relay
    
    return None


def extract_relay_bandwidth_for_period(operator_relays, bandwidth_data, time_period):
    """
    Extract bandwidth data for all relays in an operator for a specific time period.
    
    This is the core shared logic used by bandwidth-based leaderboards.
    
    OPTIMIZATION: Creates fingerprint-to-bandwidth mapping once (O(m)) instead of 
    repeated linear searches (O(n*m)) for massive performance improvement.
    
    Args:
        operator_relays (list): List of relay objects for the operator
        bandwidth_data (dict): Bandwidth data from Onionoo API
        time_period (str): Time period key (e.g., '6_months', '5_years')
        
    Returns:
        dict: Contains bandwidth_values (list), relay_breakdown (dict), and valid_relays (int)
    """
    bandwidth_values = []
    relay_breakdown = {}
    
    # OPTIMIZATION: Build fingerprint-to-bandwidth mapping ONCE (O(m) instead of O(n*m))
    # This eliminates the repeated linear searches through bandwidth_data for each operator relay
    bandwidth_map = {}
    if bandwidth_data and bandwidth_data.get('relays'):
        for bandwidth_relay in bandwidth_data['relays']:
            fingerprint = bandwidth_relay.get('fingerprint')
            if fingerprint:
                bandwidth_map[fingerprint] = bandwidth_relay
    
    # Process operator relays with O(1) lookups instead of O(m) searches
    for relay in operator_relays:
        fingerprint = relay.get('fingerprint', '')
        nickname = relay.get('nickname', 'Unknown')
        
        if not fingerprint:
            continue
            
        # OPTIMIZATION: O(1) dictionary lookup instead of O(m) linear search
        relay_bandwidth = bandwidth_map.get(fingerprint)
        
        if relay_bandwidth and relay_bandwidth.get('read_history'):
            period_data = relay_bandwidth['read_history'].get(time_period, {})
            if period_data.get('values'):
                # Calculate average bandwidth using optimized shared utility
                avg_bandwidth = calculate_relay_bandwidth_average(period_data['values'])
                if avg_bandwidth > 0:  # Only include relays with valid bandwidth data
                    bandwidth_values.append(avg_bandwidth)
                    
                    # OPTIMIZATION: Avoid redundant list comprehension - count non-None values efficiently
                    data_points = sum(1 for v in period_data['values'] if v is not None)
                    
                    relay_breakdown[fingerprint] = {
                        'nickname': nickname,
                        'fingerprint': fingerprint,
                        'bandwidth': avg_bandwidth,
                        'data_points': data_points
                    }
    
    return {
        'bandwidth_values': bandwidth_values,
        'relay_breakdown': relay_breakdown,
        'valid_relays': len(bandwidth_values)
    }


@handle_calculation_errors("calculate network bandwidth percentiles", default_return=None)
def calculate_network_bandwidth_percentiles(bandwidth_data, time_period='6_months'):
    """
    Calculate network-wide bandwidth percentiles for all active relays.
    
    Used to show where an operator fits within the overall network distribution.
    Only excludes relays with insufficient data points.
    
    Args:
        bandwidth_data (dict): Bandwidth data from Onionoo API containing all network relays
        time_period (str): Time period key (default: '6_months')
        
    Returns:
        dict: Contains percentile values and statistics for network-wide bandwidth distribution
    """
    if not bandwidth_data or not bandwidth_data.get('relays'):
        return None
        
    network_bandwidth_values = []
    total_relays_processed = 0
    excluded_relays = {
        'no_bandwidth_data': 0,
        'insufficient_data': 0,
        'invalid_data': 0
    }
    
    # Collect bandwidth data from all active relays in the network
    for relay_bandwidth in bandwidth_data.get('relays', []):
        total_relays_processed += 1
        
        if not relay_bandwidth.get('read_history'):
            excluded_relays['no_bandwidth_data'] += 1
            continue
            
        period_data = relay_bandwidth['read_history'].get(time_period, {})
        if not period_data.get('values'):
            excluded_relays['no_bandwidth_data'] += 1
            continue
        
        # Calculate average bandwidth
        avg_bandwidth = calculate_relay_bandwidth_average(period_data['values'])
        
        if avg_bandwidth == 0.0:
            # Could be insufficient data or invalid data
            values = period_data.get('values', [])
            valid_values = [v for v in values if v is not None and isinstance(v, (int, float)) and v >= 0]
            
            if not valid_values:
                excluded_relays['invalid_data'] += 1
            elif len(valid_values) < 30:
                excluded_relays['insufficient_data'] += 1
        else:
            # Valid relay with bandwidth data
            network_bandwidth_values.append(avg_bandwidth)
    
    if len(network_bandwidth_values) < 10:  # Need sufficient data for meaningful percentiles
        return None
        
    # Sort for percentile calculations
    network_bandwidth_values.sort()
    
    # Use unified statistical utilities for percentile calculations
    percentiles = StatisticalUtils.calculate_percentiles(network_bandwidth_values, [5, 25, 50, 75, 90, 95, 99])
    
    # Use median as the "average" - robust to outliers
    network_average = percentiles['50th']  # median
    
    # Also calculate arithmetic mean for comparison
    arithmetic_mean = statistics.mean(network_bandwidth_values)
    
    result = {
        'percentiles': percentiles,
        'average': network_average,  # This is actually the median for robustness
        'median': percentiles['50th'],
        'arithmetic_mean': arithmetic_mean,
        'total_relays': len(network_bandwidth_values),
        'time_period': time_period,
        'filtering_stats': {
            'total_processed': total_relays_processed,
            'included': len(network_bandwidth_values),
            'excluded': excluded_relays
        }
    }
    
    return result


def find_operator_bandwidth_percentile_position(operator_bandwidth, network_percentiles):
    """
    Find where an operator's bandwidth fits within network percentiles.
    
    Args:
        operator_bandwidth (float): Operator's average bandwidth in bytes/second
        network_percentiles (dict): Network percentile data from calculate_network_bandwidth_percentiles
        
    Returns:
        dict: Contains position description and insertion information for display formatting
    """
    if not network_percentiles or not network_percentiles.get('percentiles'):
        return {
            'description': "Unknown",
            'insert_after': None,
            'percentile_range': 'unknown'
        }
        
    percentiles = network_percentiles['percentiles']
    
    # Determine position and where to insert in display
    if operator_bandwidth >= percentiles['99th']:
        return {
            'description': f"{operator_bandwidth:.1f} bytes/s (>99th Pct)",
            'insert_after': '99th',
            'percentile_range': '>99th'
        }
    elif operator_bandwidth >= percentiles['95th']:
        return {
            'description': f"{operator_bandwidth:.1f} bytes/s (95th-99th Pct)",
            'insert_after': '95th',
            'percentile_range': '95th-99th'
        }
    elif operator_bandwidth >= percentiles['90th']:
        return {
            'description': f"{operator_bandwidth:.1f} bytes/s (90th-95th Pct)",
            'insert_after': '90th',
            'percentile_range': '90th-95th'
        }
    elif operator_bandwidth >= percentiles['75th']:
        return {
            'description': f"{operator_bandwidth:.1f} bytes/s (75th-90th Pct)",
            'insert_after': '75th',
            'percentile_range': '75th-90th'
        }
    elif operator_bandwidth >= percentiles['50th']:
        return {
            'description': f"{operator_bandwidth:.1f} bytes/s (50th-75th Pct)",
            'insert_after': 'avg',
            'percentile_range': '50th-75th'
        }
    elif operator_bandwidth >= percentiles['25th']:
        return {
            'description': f"{operator_bandwidth:.1f} bytes/s (25th-50th Pct)",
            'insert_after': '25th',
            'percentile_range': '25th-50th'
        }
    elif operator_bandwidth >= percentiles['5th']:
        return {
            'description': f"{operator_bandwidth:.1f} bytes/s (5th-25th Pct)",
            'insert_after': '5th',
            'percentile_range': '5th-25th'
        }
    else:
        return {
            'description': f"{operator_bandwidth:.1f} bytes/s (<5th Pct)",
            'insert_after': None,
            'percentile_range': '<5th'
        }


def format_network_bandwidth_percentiles_display(network_percentiles, operator_bandwidth, use_bits=False):
    """
    Format the network bandwidth percentiles display string with operator position and color coding.
    
    Args:
        network_percentiles (dict): Network percentile data
        operator_bandwidth (float): Operator's average bandwidth in bytes/second
        use_bits (bool): Whether to display in bits or bytes
        
    Returns:
        str: Formatted display string with color-coded operator position
    """
    if not network_percentiles or not network_percentiles.get('percentiles'):
        return None
        
    percentiles = network_percentiles['percentiles']
    network_median = network_percentiles.get('average', 0)
    
    # Get operator position information
    position_info = find_operator_bandwidth_percentile_position(operator_bandwidth, network_percentiles)
    insert_after = position_info['insert_after']
    percentile_range = position_info.get('percentile_range', 'unknown')
    
    # Determine operator color coding based on percentile position
    if percentile_range == '<5th':
        # Below 5th percentile: Red (Poor performance)
        operator_color = '#c82333'
    elif operator_bandwidth >= percentiles.get('50th', 0):
        # Above median: Green (Good performance)
        operator_color = '#2e7d2e'
    else:
        # Below median but above 5th percentile: Dark yellow (Okay performance)
        operator_color = '#cc9900'
    
    # Format values based on use_bits flag
    def format_bandwidth(value):
        if use_bits:
            return f"{value * 8:.0f} bits/s"
        else:
            return f"{value:.0f} bytes/s"
    
    # Format operator entry with color coding
    operator_entry = f'<span style="color: {operator_color}; font-weight: bold;">Operator: {format_bandwidth(operator_bandwidth)}</span>'
    
    # Build the ordered percentile parts
    parts = []
    
    # Always start with 5th percentile
    parts.append(f"5th Pct: {format_bandwidth(percentiles.get('5th', 0))}")
    
    # Insert operator after 5th if appropriate
    if insert_after == '5th':
        parts.append(operator_entry)
    
    # Add other percentiles with appropriate operator insertion
    parts.append(f"25th Pct: {format_bandwidth(percentiles.get('25th', 0))}")
    if insert_after == '25th':
        parts.append(operator_entry)
    
    parts.append(f"50th Pct: {format_bandwidth(network_median)}")
    if insert_after == 'avg':
        parts.append(operator_entry)
    
    parts.append(f"75th Pct: {format_bandwidth(percentiles.get('75th', 0))}")
    if insert_after == '75th':
        parts.append(operator_entry)
    
    parts.append(f"90th Pct: {format_bandwidth(percentiles.get('90th', 0))}")
    if insert_after == '90th':
        parts.append(operator_entry)
    
    parts.append(f"95th Pct: {format_bandwidth(percentiles.get('95th', 0))}")
    if insert_after == '95th':
        parts.append(operator_entry)
    
    parts.append(f"99th Pct: {format_bandwidth(percentiles.get('99th', 0))}")
    if insert_after == '99th':
        parts.append(operator_entry)
    
    # Handle special case for operators below 5th percentile
    if insert_after is None:
        parts.insert(0, operator_entry)
    
    return "<strong>Network Bandwidth (6mo):</strong> " + ", ".join(parts)


def calculate_statistical_outliers(bandwidth_values, relay_breakdown, std_dev_threshold=2.0):
    """
    Calculate statistical outliers from bandwidth values.
    
    Uses unified StatisticalUtils for consistent outlier detection.
    
    Args:
        bandwidth_values (list): List of bandwidth values in bytes/second
        relay_breakdown (dict): Mapping of fingerprint to relay data
        std_dev_threshold (float): Number of standard deviations for outlier detection
        
    Returns:
        dict: Contains low_outliers and high_outliers lists
    """
    return StatisticalUtils.calculate_outliers(bandwidth_values, relay_breakdown, std_dev_threshold)


def _calculate_period_statistics(values):
    """
    OPTIMIZATION: Centralized statistical calculation function to eliminate code duplication.
    
    Uses unified StatisticalUtils for consistent statistical calculations.
    
    Args:
        values (list): List of bandwidth values for statistical analysis
        
    Returns:
        dict: Statistical metrics including mean, median, std_dev, and outlier thresholds
    """
    if len(values) < 3:
        return None
    
    # Use unified statistical utilities
    stats = StatisticalUtils.calculate_basic_statistics(values)
    if not stats:
        return None
    
    # Add two-sigma bounds for outlier detection
    mean = stats['mean']
    std_dev = stats['std_dev']
    
    return {
        'mean': mean,
        'median': stats['median'],
        'std_dev': std_dev,
        'two_sigma_low': max(0.0, mean - 2 * std_dev),  # Lower bound of 0 since negative bandwidth impossible
        'two_sigma_high': mean + 2 * std_dev,
        'count': stats['count']
    }


def process_all_bandwidth_data_consolidated(all_relays, bandwidth_data, include_flag_analysis=True):
    """
    Consolidated bandwidth data processing function that extracts all bandwidth-related data
    in a single pass through the bandwidth API data to optimize performance.
    
    Args:
        all_relays (list): List of all relay objects
        bandwidth_data (dict): Onionoo bandwidth API data
        include_flag_analysis (bool): Whether to include flag reliability analysis
        
    Returns:
        dict: Consolidated bandwidth analysis with all computed metrics
    """
    if not bandwidth_data or not all_relays:
        return {
            'relay_bandwidth_data': {},
            'network_percentiles': None,
            'flag_analysis': {}
        }
    
    # Build fingerprint-to-bandwidth mapping for O(1) lookups
    bandwidth_map = {}
    for bandwidth_relay in bandwidth_data.get('relays', []):
        fingerprint = bandwidth_relay.get('fingerprint')
        if fingerprint:
            bandwidth_map[fingerprint] = bandwidth_relay
    
    # Process each relay and extract bandwidth data
    relay_bandwidth_data = {}
    for relay in all_relays:
        fingerprint = relay.get('fingerprint', '')
        if fingerprint and fingerprint in bandwidth_map:
            relay_bandwidth_data[fingerprint] = bandwidth_map[fingerprint]
    
    # Calculate network-wide percentiles
    network_percentiles = calculate_network_bandwidth_percentiles(bandwidth_data, '6_months')
    
    return {
        'relay_bandwidth_data': relay_bandwidth_data,
        'network_percentiles': network_percentiles,
        'flag_analysis': {}  # Placeholder for future flag analysis
    }