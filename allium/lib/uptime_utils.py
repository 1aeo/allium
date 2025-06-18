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
        float: Average uptime as percentage (0.0-100.0), or 0.0 if no valid values or uptime <= 1%
    """
    if not uptime_values:
        return 0.0
    
    # Filter out None values and invalid values
    valid_values = [v for v in uptime_values if v is not None and isinstance(v, (int, float)) and 0 <= v <= 999]
    if not valid_values:
        return 0.0
    
    # Require minimum data points for reliable calculation
    if len(valid_values) < 30:  # Need at least 30 data points (1 month of daily data)
        return 0.0
    
    # Calculate average and normalize to percentage
    avg_raw = sum(valid_values) / len(valid_values)
    percentage = normalize_uptime_value(avg_raw)
    
    # Only include relays with minimal uptime (> 1%) to exclude completely offline relays
    # We include all operational relays, including problem ones, as they represent the real
    # network experience. Hiding poorly performing relays would misrepresent network reality.
    if percentage <= 1.0:
        return 0.0  # Will be excluded from percentile calculations
    
    return percentage


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


def calculate_network_uptime_percentiles(uptime_data, time_period='6_months'):
    """
    Calculate network-wide uptime percentiles for all active relays.
    
    Used to show where an operator fits within the overall network distribution.
    Only excludes relays with ≤1% uptime (essentially offline) and insufficient data points.
    
    Includes all operational relays, including those with poor performance, as they represent 
    the real network experience. Hiding poorly performing relays would misrepresent network reality.
    
    Due to the highly skewed nature of relay uptime data (75% of relays achieve >98% uptime),
    we use median instead of mean to represent "average" network performance, as median
    is robust to outliers and mathematically guaranteed to be valid.
    
    Args:
        uptime_data (dict): Uptime data from Onionoo API containing all network relays
        time_period (str): Time period key (default: '6_months')
        
    Returns:
        dict: Contains percentile values and statistics for network-wide uptime distribution
    """
    if not uptime_data or not uptime_data.get('relays'):
        return None
        
    network_uptime_values = []
    total_relays_processed = 0
    excluded_relays = {
        'no_uptime_data': 0,
        'insufficient_data': 0, 
        'low_uptime': 0,
        'invalid_data': 0
    }
    
    # Collect uptime data from all active relays in the network
    for relay_uptime in uptime_data.get('relays', []):
        total_relays_processed += 1
        
        if not relay_uptime.get('uptime'):
            excluded_relays['no_uptime_data'] += 1
            continue
            
        period_data = relay_uptime['uptime'].get(time_period, {})
        if not period_data.get('values'):
            excluded_relays['no_uptime_data'] += 1
            continue
        
        # Calculate average uptime - this includes all relays >1% (includes problem relays)
        avg_uptime = calculate_relay_uptime_average(period_data['values'])
        
        if avg_uptime == 0.0:
            # Could be insufficient data, low uptime, or invalid data
            # The calculate_relay_uptime_average function handles the specific filtering
            values = period_data.get('values', [])
            valid_values = [v for v in values if v is not None and isinstance(v, (int, float)) and 0 <= v <= 999]
            
            if not valid_values:
                excluded_relays['invalid_data'] += 1
            elif len(valid_values) < 30:
                excluded_relays['insufficient_data'] += 1
            else:
                # Must be low uptime (≤1% - essentially offline)
                excluded_relays['low_uptime'] += 1
        else:
            # Valid relay with any operational uptime (> 1%) - includes problem relays
            network_uptime_values.append(avg_uptime)
    
    # Log filtering results for debugging
    included_relays = len(network_uptime_values)
    excluded_total = sum(excluded_relays.values())
    
    print(f"📊 Network Percentile Calculation ({time_period}):")
    print(f"   Total relays processed: {total_relays_processed}")
    print(f"   Included in percentiles: {included_relays} ({(included_relays/total_relays_processed)*100:.1f}%)")
    print(f"   Excluded - No uptime data: {excluded_relays['no_uptime_data']}")
    print(f"   Excluded - Insufficient data (<30 points): {excluded_relays['insufficient_data']}")
    print(f"   Excluded - Offline relays (≤1%): {excluded_relays['low_uptime']}")
    print(f"   Excluded - Invalid data: {excluded_relays['invalid_data']}")
    print(f"   ℹ️  Including all operational relays (even poor performers) for honest network representation")
    
    if len(network_uptime_values) < 10:  # Need sufficient data for meaningful percentiles
        print(f"❌ ERROR: Only {len(network_uptime_values)} valid relays found - insufficient for percentiles")
        return None
        
    # Sort for percentile calculations
    network_uptime_values.sort()
    
    try:
        # Use Python's robust quantiles function if available (Python 3.8+)
        # Otherwise fall back to manual calculation
        try:
            import sys
            if sys.version_info >= (3, 8):
                # Use statistics.quantiles for more accurate results
                quantile_values = statistics.quantiles(network_uptime_values, n=100, method='inclusive')
                percentiles = {
                    '25th': quantile_values[24],  # 25th percentile
                    '50th': quantile_values[49],  # 50th percentile (median)
                    '75th': quantile_values[74],  # 75th percentile
                    '90th': quantile_values[89],  # 90th percentile
                    '95th': quantile_values[94],  # 95th percentile
                    '99th': quantile_values[98]   # 99th percentile
                }
            else:
                raise ImportError("Using fallback calculation")
        except (ImportError, IndexError):
            # Fallback to manual calculation for older Python versions
            def calculate_percentile(data, percentile):
                """Calculate percentile manually using numpy-style interpolation"""
                if not data:
                    return 0.0
                n = len(data)
                if n == 1:
                    return data[0]
                # Use method similar to numpy.percentile with linear interpolation
                k = (n - 1) * (percentile / 100.0)
                f = int(k)
                c = k - f
                if f >= n - 1:
                    return data[-1]
                return data[f] + c * (data[f + 1] - data[f])
            
            percentiles = {
                '25th': calculate_percentile(network_uptime_values, 25),
                '50th': calculate_percentile(network_uptime_values, 50),  # Median
                '75th': calculate_percentile(network_uptime_values, 75),
                '90th': calculate_percentile(network_uptime_values, 90),
                '95th': calculate_percentile(network_uptime_values, 95),
                '99th': calculate_percentile(network_uptime_values, 99)
            }
        
        # Use median as the "average" - robust to outliers and mathematically guaranteed valid
        # This represents the typical relay performance better than mean in highly skewed distributions
        # and avoids mathematical impossibilities while showing honest network representation
        network_average = percentiles['50th']  # median
        
        # Also calculate arithmetic mean for comparison/debugging
        arithmetic_mean = statistics.mean(network_uptime_values)
        
        # Mathematical validation - explains why median is used for honest network representation
        if arithmetic_mean < percentiles['25th']:
            print(f"ℹ️  Network shows typical infrastructure distribution pattern:")
            print(f"   Arithmetic mean ({arithmetic_mean:.1f}%) < 25th percentile ({percentiles['25th']:.1f}%)")
            print(f"   This reflects reality: many excellent relays + scattered problem relays")
            print(f"   Using median ({network_average:.1f}%) as robust 'average' for honest representation")
        else:
            print(f"✅ Network distribution is well-behaved:")
            print(f"   Arithmetic mean ({arithmetic_mean:.1f}%) ≥ 25th percentile ({percentiles['25th']:.1f}%)")
            print(f"   Using median ({network_average:.1f}%) for consistency and robustness")
        
        result = {
            'percentiles': percentiles,
            'average': network_average,  # This is actually the median for robustness
            'median': percentiles['50th'],
            'arithmetic_mean': arithmetic_mean,  # Included for debugging
            'total_relays': len(network_uptime_values),
            'time_period': time_period,
            'filtering_stats': {
                'total_processed': total_relays_processed,
                'included': included_relays,
                'excluded': excluded_relays
            }
        }
        
        return result
        
    except Exception as e:
        # Fallback in case of any calculation errors
        print(f"ERROR in calculate_network_uptime_percentiles: {e}")
        return None


def find_operator_percentile_position(operator_uptime, network_percentiles):
    """
    Find where an operator's uptime fits within network percentiles.
    
    Args:
        operator_uptime (float): Operator's average uptime percentage
        network_percentiles (dict): Network percentile data from calculate_network_uptime_percentiles
        
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
    if operator_uptime >= percentiles['99th']:
        return {
            'description': f"{operator_uptime:.1f}% (>99th Pct)",
            'insert_after': '99th',  # Insert after 99th percentile
            'percentile_range': '>99th'
        }
    elif operator_uptime >= percentiles['95th']:
        return {
            'description': f"{operator_uptime:.1f}% (95th-99th Pct)",
            'insert_after': '95th',  # Insert after 95th percentile  
            'percentile_range': '95th-99th'
        }
    elif operator_uptime >= percentiles['90th']:
        return {
            'description': f"{operator_uptime:.1f}% (90th-95th Pct)",
            'insert_after': '90th',  # Insert after 90th percentile
            'percentile_range': '90th-95th'
        }
    elif operator_uptime >= percentiles['75th']:
        return {
            'description': f"{operator_uptime:.1f}% (75th-90th Pct)",
            'insert_after': '75th',  # Insert after 75th percentile
            'percentile_range': '75th-90th'
        }
    elif operator_uptime >= percentiles['50th']:
        return {
            'description': f"{operator_uptime:.1f}% (50th-75th Pct)",
            'insert_after': 'avg',   # Insert after average
            'percentile_range': '50th-75th'
        }
    elif operator_uptime >= percentiles['25th']:
        return {
            'description': f"{operator_uptime:.1f}% (25th-50th Pct)",
            'insert_after': '25th',  # Insert after 25th percentile
            'percentile_range': '25th-50th'
        }
    else:
        return {
            'description': f"{operator_uptime:.1f}% (<25th Pct)",
            'insert_after': None,    # Insert at beginning (after label)
            'percentile_range': '<25th'
        }


def format_network_percentiles_display(network_percentiles, operator_uptime):
    """
    Format the network percentiles display string with operator position.
    
    Args:
        network_percentiles (dict): Network percentile data
        operator_uptime (float): Operator's average uptime percentage
        
    Returns:
        str: Formatted display string
    """
    if not network_percentiles or not network_percentiles.get('percentiles'):
        return None
        
    percentiles = network_percentiles['percentiles']
    network_avg = network_percentiles.get('average', 0)
    
    # Get operator position information
    position_info = find_operator_percentile_position(operator_uptime, network_percentiles)
    insert_after = position_info['insert_after']
    
    # Build the ordered percentile parts
    parts = []
    
    # Always start with 25th percentile
    parts.append(f"25th Pct: {percentiles.get('25th', 0):.0f}%")
    
    # Insert operator after 25th if appropriate
    if insert_after is None:  # <25th percentile
        parts.append(f"Operator: {operator_uptime:.0f}%")
    elif insert_after == '25th':
        parts.append(f"Operator: {operator_uptime:.0f}%")
    
    # Add average
    parts.append(f"Avg: {network_avg:.0f}%")
    
    # Insert operator after average if appropriate
    if insert_after == 'avg':  # 50th-75th percentile range
        parts.append(f"Operator: {operator_uptime:.0f}%")
    
    # Add 75th percentile
    parts.append(f"75th Pct: {percentiles.get('75th', 0):.0f}%")
    
    # Insert operator after 75th if appropriate
    if insert_after == '75th':
        parts.append(f"Operator: {operator_uptime:.0f}%")
    
    # Add 90th percentile
    parts.append(f"90th Pct: {percentiles.get('90th', 0):.0f}%")
    
    # Insert operator after 90th if appropriate
    if insert_after == '90th':
        parts.append(f"Operator: {operator_uptime:.0f}%")
    
    # Add 95th percentile
    parts.append(f"95th Pct: {percentiles.get('95th', 0):.0f}%")
    
    # Insert operator after 95th if appropriate
    if insert_after == '95th':
        parts.append(f"Operator: {operator_uptime:.0f}%")
    
    # Add 99th percentile
    parts.append(f"99th Pct: {percentiles.get('99th', 0):.0f}%")
    
    # Insert operator after 99th if appropriate (>99th percentile)
    if insert_after == '99th':
        parts.append(f"Operator: {operator_uptime:.0f}%")
    
    return "Network Uptime (6mo): " + ", ".join(parts)


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