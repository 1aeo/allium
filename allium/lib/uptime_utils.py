"""
Uptime calculation utilities for operator reliability analysis.

This module provides shared functions for calculating uptime statistics
to avoid duplication between aroileaders.py and relays.py.
"""

import statistics


def normalize_uptime_value(raw_value):
    """
    Normalize uptime value from Onionoo's 0-999 scale to 0-100 percentage.
    
    Args:
        raw_value (int): Raw uptime value from Onionoo API (0-999)
        
    Returns:
        float: Normalized percentage (0.0-100.0)
    """
    return raw_value / 999 * 100


def calculate_relay_uptime_average(uptime_values):
    """
    Calculate average uptime from a list of raw Onionoo uptime values.
    
    Args:
        uptime_values (list): List of raw uptime values (0-999 scale)
        
    Returns:
        float: Average uptime as percentage (0.0-100.0), or 0.0 if no valid values
    """
    if not uptime_values:
        return 0.0
    
    # Filter out None values and normalize
    valid_values = [v for v in uptime_values if v is not None]
    if not valid_values:
        return 0.0
    
    # Calculate average and normalize to percentage
    avg_raw = sum(valid_values) / len(valid_values)
    return normalize_uptime_value(avg_raw)


def find_relay_uptime_data(fingerprint, uptime_data):
    """
    Find uptime data for a specific relay by fingerprint.
    
    Args:
        fingerprint (str): Relay fingerprint to search for
        uptime_data (dict): Uptime data from Onionoo API
        
    Returns:
        dict or None: Relay uptime data if found, None otherwise
    """
    if not uptime_data or not fingerprint:
        return None
    
    for uptime_relay in uptime_data.get('relays', []):
        if uptime_relay.get('fingerprint') == fingerprint:
            return uptime_relay
    
    return None


def extract_relay_uptime_for_period(operator_relays, uptime_data, time_period):
    """
    Extract uptime data for all relays in an operator for a specific time period.
    
    This is the core shared logic used by both AROI leaderboards and contact page reliability.
    
    Args:
        operator_relays (list): List of relay objects for the operator
        uptime_data (dict): Uptime data from Onionoo API
        time_period (str): Time period key (e.g., '6_months', '1_year')
        
    Returns:
        dict: Contains uptime_values (list), relay_breakdown (dict), and valid_relays (int)
    """
    uptime_values = []
    relay_breakdown = {}
    
    for relay in operator_relays:
        fingerprint = relay.get('fingerprint', '')
        nickname = relay.get('nickname', 'Unknown')
        
        if not fingerprint:
            continue
            
        # Find uptime data for this relay
        relay_uptime = find_relay_uptime_data(fingerprint, uptime_data)
        
        if relay_uptime and relay_uptime.get('uptime'):
            period_data = relay_uptime['uptime'].get(time_period, {})
            if period_data.get('values'):
                # Calculate average uptime using shared utility
                avg_uptime = calculate_relay_uptime_average(period_data['values'])
                if avg_uptime > 0:  # Only include relays with valid uptime data
                    uptime_values.append(avg_uptime)
                    relay_breakdown[fingerprint] = {
                        'nickname': nickname,
                        'fingerprint': fingerprint,
                        'uptime': avg_uptime,
                        'data_points': len([v for v in period_data['values'] if v is not None])
                    }
    
    return {
        'uptime_values': uptime_values,
        'relay_breakdown': relay_breakdown,
        'valid_relays': len(uptime_values)
    }


def calculate_statistical_outliers(uptime_values, relay_breakdown, std_dev_threshold=2.0):
    """
    Calculate statistical outliers from uptime values.
    
    Args:
        uptime_values (list): List of uptime percentages
        relay_breakdown (dict): Mapping of fingerprint to relay data
        std_dev_threshold (float): Number of standard deviations for outlier detection
        
    Returns:
        dict: Contains low_outliers and high_outliers lists
    """
    if len(uptime_values) < 3:  # Need at least 3 data points for meaningful std dev
        return {'low_outliers': [], 'high_outliers': []}
    
    try:
        mean_uptime = statistics.mean(uptime_values)
        std_dev = statistics.stdev(uptime_values)
        
        low_threshold = mean_uptime - (std_dev_threshold * std_dev)
        high_threshold = mean_uptime + (std_dev_threshold * std_dev)
        
        low_outliers = []
        high_outliers = []
        
        for fingerprint, relay_data in relay_breakdown.items():
            uptime = relay_data['uptime']
            
            if uptime < low_threshold:
                low_outliers.append({
                    'nickname': relay_data['nickname'],
                    'fingerprint': fingerprint,
                    'uptime': uptime,
                    'deviation': abs(uptime - mean_uptime) / std_dev
                })
            elif uptime > high_threshold:
                high_outliers.append({
                    'nickname': relay_data['nickname'],
                    'fingerprint': fingerprint,
                    'uptime': uptime,
                    'deviation': abs(uptime - mean_uptime) / std_dev
                })
        
        return {'low_outliers': low_outliers, 'high_outliers': high_outliers}
        
    except statistics.StatisticsError:
        # Handle case where all values are identical (std dev = 0)
        return {'low_outliers': [], 'high_outliers': []} 