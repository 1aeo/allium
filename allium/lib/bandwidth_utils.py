"""
Bandwidth calculation utilities for operator performance analysis.

This module provides shared functions for calculating bandwidth statistics
to enable historic bandwidth leaderboard categories similar to uptime leaderboards.
"""


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


def extract_operator_daily_bandwidth_totals(operator_relays, bandwidth_data, time_period):
    """
    Calculate daily total bandwidth for an operator (sum across all relays per day).
    
    This matches the Onionoo details API calculation: sum all relay bandwidth for each day,
    then average those daily totals over the time period.
    
    Args:
        operator_relays (list): List of relay objects for the operator
        bandwidth_data (dict): Bandwidth data from Onionoo API
        time_period (str): Time period key (e.g., '6_months', '5_years')
        
    Returns:
        dict: Contains daily_totals (list), average_daily_total (float), and valid_days (int)
    """
    if not operator_relays or not bandwidth_data:
        return {
            'daily_totals': [],
            'average_daily_total': 0.0,
            'valid_days': 0
        }
    
    # OPTIMIZATION: Build fingerprint-to-bandwidth mapping ONCE (O(m) instead of O(n*m))
    bandwidth_map = {}
    if bandwidth_data and bandwidth_data.get('relays'):
        for bandwidth_relay in bandwidth_data['relays']:
            fingerprint = bandwidth_relay.get('fingerprint')
            if fingerprint:
                bandwidth_map[fingerprint] = bandwidth_relay
    
    # Collect all relay bandwidth arrays for this time period
    relay_bandwidth_arrays = []
    for relay in operator_relays:
        fingerprint = relay.get('fingerprint', '')
        if not fingerprint:
            continue
            
        relay_bandwidth = bandwidth_map.get(fingerprint)
        if relay_bandwidth and relay_bandwidth.get('read_history'):
            period_data = relay_bandwidth['read_history'].get(time_period, {})
            if period_data.get('values') and period_data.get('factor'):
                # Each relay needs its values and factor stored together
                relay_bandwidth_arrays.append({
                    'values': period_data['values'],
                    'factor': period_data['factor']
                })
    
    if not relay_bandwidth_arrays:
        return {
            'daily_totals': [],
            'average_daily_total': 0.0,
            'valid_days': 0
        }
    
    # Find the maximum length to handle arrays of different lengths
    max_length = max(len(relay_data['values']) for relay_data in relay_bandwidth_arrays)
    
    # Calculate daily totals by summing across all relays for each day
    daily_totals = []
    for day_index in range(max_length):
        day_total = 0
        valid_relays_for_day = 0
        
        for relay_data in relay_bandwidth_arrays:
            values = relay_data['values']
            factor = relay_data['factor']
            
            if day_index < len(values):
                value = values[day_index]
                if value is not None and isinstance(value, (int, float)) and value >= 0:
                    # Apply the factor to convert normalized value to actual bytes/second
                    actual_bandwidth = value * factor
                    day_total += actual_bandwidth
                    valid_relays_for_day += 1
        
        # Only include days with at least some valid relay data
        if valid_relays_for_day > 0:
            daily_totals.append(day_total)
    
    # Calculate average daily total
    if daily_totals:
        average_daily_total = sum(daily_totals) / len(daily_totals)
    else:
        average_daily_total = 0.0
    
    return {
        'daily_totals': daily_totals,
        'average_daily_total': average_daily_total,
        'valid_days': len(daily_totals)
    }


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
            if period_data.get('values') and period_data.get('factor'):
                # Apply factor to convert normalized values to actual bytes/second
                factor = period_data['factor']
                actual_values = [v * factor for v in period_data['values'] if v is not None]
                
                # Calculate average bandwidth using optimized shared utility
                avg_bandwidth = calculate_relay_bandwidth_average(actual_values)
                if avg_bandwidth > 0:  # Only include relays with valid bandwidth data
                    bandwidth_values.append(avg_bandwidth)
                    
                    # OPTIMIZATION: Avoid redundant list comprehension - count non-None values efficiently
                    data_points = len(actual_values)
                    
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