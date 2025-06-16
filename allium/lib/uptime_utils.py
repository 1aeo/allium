"""
Uptime calculation utilities for operator reliability analysis.

This module provides shared functions for calculating uptime statistics
to avoid duplication between aroileaders.py and relays.py.
"""

import statistics
import math


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


def process_all_uptime_data_consolidated(all_relays, uptime_data, include_flag_analysis=True):
    """
    Consolidated uptime data processing function that extracts all uptime-related data
    in a single pass through the uptime API data to optimize performance.
    
    This replaces multiple separate loops through uptime data with one optimized pass
    that computes:
    - Regular uptime percentages for individual relays
    - Network-wide statistical analysis for outlier detection  
    - Flag-specific uptime data for flag reliability analysis
    
    Args:
        all_relays (list): List of all relay objects
        uptime_data (dict): Onionoo uptime API data
        include_flag_analysis (bool): Whether to include flag reliability analysis
        
    Returns:
        dict: Consolidated uptime analysis with all computed metrics
    """
    if not uptime_data or not all_relays:
        return {
            'relay_uptime_data': {},
            'network_statistics': {},
            'flag_analysis_data': {} if include_flag_analysis else None
        }
    
    # Create fingerprint to relay mapping for fast lookup
    relay_fingerprint_map = {}
    for relay in all_relays:
        fingerprint = relay.get('fingerprint')
        if fingerprint:
            relay_fingerprint_map[fingerprint] = relay
    
    # Initialize data structures for consolidated processing
    relay_uptime_data = {}  # fingerprint -> {uptime_percentages, flag_data}
    network_uptime_values = {'1_month': [], '6_months': [], '1_year': [], '5_years': []}
    network_flag_data = {}  # flag -> period -> [values] for network statistics
    
    # SINGLE PASS through uptime data - this replaces multiple separate loops
    for uptime_relay in uptime_data.get('relays', []):
        fingerprint = uptime_relay.get('fingerprint')
        if not fingerprint:
            continue
            
        # Check if this relay is in our relay set
        relay_obj = relay_fingerprint_map.get(fingerprint)
        
        # Process regular uptime data
        uptime_percentages = {'1_month': 0.0, '6_months': 0.0, '1_year': 0.0, '5_years': 0.0}
        uptime_section = uptime_relay.get('uptime', {})
        
        for period in ['1_month', '6_months', '1_year', '5_years']:
            period_data = uptime_section.get(period, {})
            if period_data.get('values'):
                uptime_percentage = calculate_relay_uptime_average(period_data['values'])
                uptime_percentages[period] = uptime_percentage
                
                # Collect for network statistics (for all relays, not just operator relays)
                network_uptime_values[period].append(uptime_percentage)
        
        # Process flag-specific uptime data (if enabled)
        flag_data = {}
        if include_flag_analysis:
            flags_section = uptime_relay.get('flags', {})
            
            for flag, periods in flags_section.items():
                flag_data[flag] = {}
                
                # Initialize network flag data structure
                if flag not in network_flag_data:
                    network_flag_data[flag] = {'1_month': [], '6_months': [], '1_year': [], '5_years': []}
                
                for period, data in periods.items():
                    if period in ['1_month', '6_months', '1_year', '5_years'] and data.get('values'):
                        # Flag data uses same scale as regular uptime data (0-999) 
                        # Convert to percentages (0-100) using existing utility
                        valid_values = [v for v in data['values'] if v is not None and 0 <= v <= 999]
                        if valid_values:
                            # Calculate average uptime using shared utility (handles 0-999 to 0-100% conversion)
                            avg_uptime = calculate_relay_uptime_average(valid_values)
                            
                            flag_data[flag][period] = {
                                'uptime': avg_uptime,
                                'data_points': len(valid_values),
                                'relay_info': {
                                    'nickname': relay_obj.get('nickname', 'Unknown') if relay_obj else 'Unknown',
                                    'fingerprint': fingerprint
                                }
                            }
                            
                            # Collect for network flag statistics
                            network_flag_data[flag][period].append(avg_uptime)
        
        # Store processed data for this relay
        relay_uptime_data[fingerprint] = {
            'uptime_percentages': uptime_percentages,
            'flag_data': flag_data,
            'relay_obj': relay_obj  # Store reference for easy access
        }
    
    # Calculate network statistics for outlier detection
    network_statistics = {}
    for period in ['1_month', '6_months', '1_year', '5_years']:
        values = network_uptime_values[period]
        if len(values) >= 3:
            try:
                total_sum = sum(values)
                count = len(values)
                sum_of_squares = sum(x ** 2 for x in values)
                
                # Calculate statistical thresholds for outlier detection
                mean = total_sum / count
                variance = (sum_of_squares / count) - (mean ** 2)
                std_dev = math.sqrt(max(0, variance))  # Ensure non-negative variance
                
                # Set lower bound of 0 for two_sigma_low since negative uptimes are impossible
                two_sigma_low = max(0.0, mean - 2 * std_dev)
                two_sigma_high = mean + 2 * std_dev
                
                period_stats = {
                    'mean': mean,
                    'std_dev': std_dev,
                    'two_sigma_low': two_sigma_low,
                    'two_sigma_high': two_sigma_high,
                    'count': count
                }
                
                network_statistics[period] = period_stats
            except Exception:
                network_statistics[period] = None
        else:
            network_statistics[period] = None
    
    # Calculate network flag statistics (if flag analysis enabled)
    network_flag_statistics = {}
    if include_flag_analysis:
        for flag, periods_data in network_flag_data.items():
            network_flag_statistics[flag] = {}
            for period, values in periods_data.items():
                if len(values) >= 3:
                    try:
                        total_sum = sum(values)
                        count = len(values)
                        sum_of_squares = sum(x ** 2 for x in values)
                        
                        # Calculate statistical thresholds for outlier detection
                        mean = total_sum / count
                        variance = (sum_of_squares / count) - (mean ** 2)
                        std_dev = math.sqrt(max(0, variance))  # Ensure non-negative variance
                        
                        # Set lower bound of 0 for two_sigma_low since negative uptimes are impossible
                        two_sigma_low = max(0.0, mean - 2 * std_dev)
                        two_sigma_high = mean + 2 * std_dev
                        
                        period_stats = {
                            'mean': mean,
                            'std_dev': std_dev,
                            'two_sigma_low': two_sigma_low,
                            'two_sigma_high': two_sigma_high,
                            'count': count
                        }
                        
                        network_flag_statistics[flag][period] = period_stats
                    except Exception:
                        network_flag_statistics[flag][period] = None
                else:
                    network_flag_statistics[flag][period] = None
    
    return {
        'relay_uptime_data': relay_uptime_data,
        'network_statistics': network_statistics,
        'network_flag_statistics': network_flag_statistics if include_flag_analysis else None,
        'processing_summary': {
            'total_relays_processed': len(relay_uptime_data),
            'network_relays_with_uptime': len([r for r in relay_uptime_data.values() if any(p > 0 for p in r['uptime_percentages'].values())]),
            'flags_found': list(network_flag_data.keys()) if include_flag_analysis else []
        }
    } 