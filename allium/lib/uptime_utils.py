"""
Uptime calculation utilities for operator reliability analysis.

This module provides shared functions for calculating uptime statistics
to avoid duplication between aroileaders.py and relays.py.
"""

import statistics
import math
from .error_handlers import handle_calculation_errors
from .statistical_utils import StatisticalUtils


def normalize_uptime_value(raw_value):
    """
    Normalize uptime value from Onionoo's 0-999 scale to 0-100 percentage.
    
    Args:
        raw_value (int): Raw uptime value from Onionoo API (0-999)
        
    Returns:
        float: Normalized percentage (0.0-100.0)
    """
    return raw_value / 999 * 100


def _compute_uptime_percentage_and_datapoints(uptime_values):
    """
    Compute uptime percentage and valid datapoint count in a single pass.
    
    This is the core calculation used by both relay processing and network statistics.
    Returns both values to avoid redundant iteration through the data.
    
    Args:
        uptime_values (list): List of raw uptime values (0-999 scale)
        
    Returns:
        tuple: (percentage: float, datapoints: int)
            - percentage: Average uptime as percentage (0.0-100.0), or 0.0 if invalid
            - datapoints: Count of valid data points processed
    """
    if not uptime_values:
        return 0.0, 0
    
    # OPTIMIZATION: Single pass - filter, count, and sum simultaneously
    total = 0
    count = 0
    for v in uptime_values:
        if v is None:
            continue
        if isinstance(v, (int, float)) and 0 <= v <= 999:
            total += v
            count += 1
    
    # Early exit for insufficient data
    if count < 30:  # Need at least 30 data points (1 month of daily data)
        return 0.0, count
    
    # Calculate percentage in single step (inline normalize_uptime_value)
    percentage = (total / count) * (100.0 / 999.0)
    
    # Exclude essentially offline relays (≤1% uptime)
    if percentage <= 1.0:
        return 0.0, count
    
    return percentage, count


def calculate_relay_uptime_average(uptime_values):
    """
    Calculate average uptime from a list of raw Onionoo uptime values.
    
    OPTIMIZATION: Single-pass calculation eliminates redundant iterations
    through uptime data (filter + sum + len → single loop).
    
    Args:
        uptime_values (list): List of raw uptime values (0-999 scale)
        
    Returns:
        float: Average uptime as percentage (0.0-100.0), or 0.0 if no valid values or uptime <= 1%
    """
    percentage, _ = _compute_uptime_percentage_and_datapoints(uptime_values)
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


def build_uptime_map(uptime_data):
    """
    Build fingerprint-to-uptime mapping once for reuse across multiple operators.
    
    PERFORMANCE: This should be called ONCE at the start of batch processing
    (e.g., AROI leaderboard calculation) rather than per-operator to eliminate
    redundant O(n) iterations through uptime_data.
    
    Args:
        uptime_data (dict): Uptime data from Onionoo API
        
    Returns:
        dict: Mapping of fingerprint -> uptime relay data
    """
    uptime_map = {}
    if uptime_data and uptime_data.get('relays'):
        for uptime_relay in uptime_data['relays']:
            fingerprint = uptime_relay.get('fingerprint')
            if fingerprint:
                uptime_map[fingerprint] = uptime_relay
    return uptime_map


def extract_relay_uptime_for_period(operator_relays, uptime_data, time_period, uptime_map=None):
    """
    Extract uptime data for all relays in an operator for a specific time period.
    
    This is the core shared logic used by both AROI leaderboards and contact page reliability.
    
    OPTIMIZATION: Accepts pre-built uptime_map for batch processing. When processing
    multiple operators, build the map once with build_uptime_map() and pass it to
    each call to avoid rebuilding the map ~3000+ times.
    
    Args:
        operator_relays (list): List of relay objects for the operator
        uptime_data (dict): Uptime data from Onionoo API
        time_period (str): Time period key (e.g., '6_months', '1_year')
        uptime_map (dict, optional): Pre-built fingerprint->uptime mapping for batch processing
        
    Returns:
        dict: Contains uptime_values (list), relay_breakdown (dict), and valid_relays (int)
    """
    uptime_values = []
    relay_breakdown = {}
    
    # Use pre-built map if provided, otherwise build one (backwards compatibility)
    if uptime_map is None:
        uptime_map = build_uptime_map(uptime_data)
    
    # Process operator relays with O(1) lookups instead of O(m) searches
    for relay in operator_relays:
        fingerprint = relay.get('fingerprint', '')
        nickname = relay.get('nickname', 'Unknown')
        
        if not fingerprint:
            continue
            
        # OPTIMIZATION: O(1) dictionary lookup instead of O(m) linear search
        relay_uptime = uptime_map.get(fingerprint)
        
        if relay_uptime and relay_uptime.get('uptime'):
            period_data = relay_uptime['uptime'].get(time_period, {})
            if period_data.get('values'):
                # Calculate average uptime using optimized shared utility
                avg_uptime = calculate_relay_uptime_average(period_data['values'])
                if avg_uptime > 0:  # Only include relays with valid uptime data
                    uptime_values.append(avg_uptime)
                    
                    # OPTIMIZATION: Avoid redundant list comprehension - count non-None values efficiently
                    data_points = sum(1 for v in period_data['values'] if v is not None)
                    
                    relay_breakdown[fingerprint] = {
                        'nickname': nickname,
                        'fingerprint': fingerprint,
                        'uptime': avg_uptime,
                        'data_points': data_points
                    }
    
    return {
        'uptime_values': uptime_values,
        'relay_breakdown': relay_breakdown,
        'valid_relays': len(uptime_values)
    }


@handle_calculation_errors("calculate network uptime percentiles", default_return=None)
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
    
    if len(network_uptime_values) < 10:  # Need sufficient data for meaningful percentiles
        return None
        
    # Sort for percentile calculations
    network_uptime_values.sort()
    
    # Use unified statistical utilities for percentile calculations
    percentiles = StatisticalUtils.calculate_percentiles(network_uptime_values, [5, 25, 50, 75, 90, 95, 99])
    
    # Use median as the "average" - robust to outliers and mathematically guaranteed valid
    # This represents the typical relay performance better than mean in highly skewed distributions
    # and avoids mathematical impossibilities while showing honest network representation
    network_average = percentiles['50th']  # median
    
    # Also calculate arithmetic mean for comparison/debugging
    arithmetic_mean = statistics.mean(network_uptime_values)
    
    result = {
        'percentiles': percentiles,
        'average': network_average,  # This is actually the median for robustness
        'median': percentiles['50th'],
        'arithmetic_mean': arithmetic_mean,  # Included for debugging
        'total_relays': len(network_uptime_values),
        'time_period': time_period,
        'filtering_stats': {
            'total_processed': total_relays_processed,
            'included': len(network_uptime_values),
            'excluded': excluded_relays
        }
    }
    
    return result


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
    elif operator_uptime >= percentiles['5th']:
        return {
            'description': f"{operator_uptime:.1f}% (5th-25th Pct)",
            'insert_after': '5th',   # Insert after 5th percentile
            'percentile_range': '5th-25th'
        }
    else:
        return {
            'description': f"{operator_uptime:.1f}% (<5th Pct)",
            'insert_after': None,    # Insert at beginning (after label)
            'percentile_range': '<5th'
        }


def format_network_percentiles_display(network_percentiles, operator_uptime):
    """
    Format the network percentiles display string with operator position and color coding.
    
    Color coding matches operator intelligence section:
    - Above median: Green (#2e7d2e - same as "All" in version compliance)
    - Below median: Dark yellow (#cc9900 - same as "Okay" in diversity ratings)
    - Below 5th percentile: Red (#c82333 - same as "Poor" in diversity ratings)
    
    Args:
        network_percentiles (dict): Network percentile data
        operator_uptime (float): Operator's average uptime percentage
        
    Returns:
        str: Formatted display string with color-coded operator position
    """
    if not network_percentiles or not network_percentiles.get('percentiles'):
        return None
        
    percentiles = network_percentiles['percentiles']
    network_median = network_percentiles.get('average', 0)  # This is actually the median
    
    # Get operator position information
    position_info = find_operator_percentile_position(operator_uptime, network_percentiles)
    insert_after = position_info['insert_after']
    percentile_range = position_info.get('percentile_range', 'unknown')
    
    # Determine operator color coding based on percentile position
    if percentile_range == '<5th':
        # Below 5th percentile: Red (Poor performance)
        operator_color = '#c82333'
    elif operator_uptime >= percentiles.get('50th', 0):
        # Above median: Green (Good performance)
        operator_color = '#2e7d2e'
    else:
        # Below median but above 5th percentile: Dark yellow (Okay performance)
        operator_color = '#cc9900'
    
    # Format operator entry with color coding
    operator_entry = f'<span style="color: {operator_color}; font-weight: bold;">Operator: {operator_uptime:.0f}%</span>'
    
    # Build the ordered percentile parts
    parts = []
    
    # Always start with 5th percentile
    parts.append(f"5th Pct: {percentiles.get('5th', 0):.0f}%")
    
    # Insert operator after 5th if appropriate
    if insert_after == '5th':
        parts.append(operator_entry)
    
    # Add 25th percentile
    parts.append(f"25th Pct: {percentiles.get('25th', 0):.0f}%")
    
    # Insert operator after 25th if appropriate
    if insert_after == '25th':
        parts.append(operator_entry)
    
    # Add median (renamed from "Avg")
    parts.append(f"50th Pct: {network_median:.0f}%")
    
    # Insert operator after median if appropriate
    if insert_after == 'avg':  # 50th-75th percentile range
        parts.append(operator_entry)
    
    # Add 75th percentile
    parts.append(f"75th Pct: {percentiles.get('75th', 0):.0f}%")
    
    # Insert operator after 75th if appropriate
    if insert_after == '75th':
        parts.append(operator_entry)
    
    # Add 90th percentile
    parts.append(f"90th Pct: {percentiles.get('90th', 0):.0f}%")
    
    # Insert operator after 90th if appropriate
    if insert_after == '90th':
        parts.append(operator_entry)
    
    # Add 95th percentile
    parts.append(f"95th Pct: {percentiles.get('95th', 0):.0f}%")
    
    # Insert operator after 95th if appropriate
    if insert_after == '95th':
        parts.append(operator_entry)
    
    # Add 99th percentile
    parts.append(f"99th Pct: {percentiles.get('99th', 0):.0f}%")
    
    # Insert operator after 99th if appropriate (>99th percentile)
    if insert_after == '99th':
        parts.append(operator_entry)
    
    # Handle special case for operators below 5th percentile
    if insert_after is None:  # <5th percentile
        # Insert at the beginning after the label
        parts.insert(0, operator_entry)  # Insert at beginning of parts list
    
    return "<strong>Network Uptime (6mo):</strong> " + ", ".join(parts)


def calculate_statistical_outliers(uptime_values, relay_breakdown, std_dev_threshold=2.0):
    """
    Calculate statistical outliers from uptime values.
    
    Uses unified StatisticalUtils for consistent outlier detection.
    
    Args:
        uptime_values (list): List of uptime percentages
        relay_breakdown (dict): Mapping of fingerprint to relay data
        std_dev_threshold (float): Number of standard deviations for outlier detection
        
    Returns:
        dict: Contains low_outliers and high_outliers lists
    """
    return StatisticalUtils.calculate_outliers(uptime_values, relay_breakdown, std_dev_threshold)


def _calculate_period_statistics(values):
    """
    OPTIMIZATION: Centralized statistical calculation function to eliminate code duplication.
    
    Uses unified StatisticalUtils for consistent statistical calculations.
    
    Args:
        values (list): List of uptime values for statistical analysis
        
    Returns:
        dict: Statistical metrics including mean, median, std_dev, and outlier thresholds
    """
    if len(values) < 3:
        return None
    
    # Use unified statistical utilities
    stats = StatisticalUtils.calculate_basic_statistics(values)
    if not stats:
        return None
    
    # Add two-sigma bounds for outlier detection (maintain backwards compatibility)
    mean = stats['mean']
    std_dev = stats['std_dev']
    
    return {
        'mean': mean,
        'median': stats['median'],
        'std_dev': std_dev,
        'two_sigma_low': max(0.0, mean - 2 * std_dev),  # Lower bound of 0 since negative uptimes impossible
        'two_sigma_high': mean + 2 * std_dev,
        'count': stats['count']
    }


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
    relay_uptime_data = {}  # fingerprint -> {uptime_percentages, uptime_datapoints, flag_data}
    network_uptime_values = {'1_month': [], '6_months': [], '1_year': [], '5_years': []}
    network_flag_data = {}  # flag -> period -> [values] for network statistics
    network_relays_with_uptime = 0  # Track count during processing (avoid re-counting later)
    
    # SINGLE PASS through uptime data - this replaces multiple separate loops
    for uptime_relay in uptime_data.get('relays', []):
        fingerprint = uptime_relay.get('fingerprint')
        if not fingerprint:
            continue
            
        # Check if this relay is in our relay set
        relay_obj = relay_fingerprint_map.get(fingerprint)
        
        # Process regular uptime data
        uptime_percentages = {'1_month': 0.0, '6_months': 0.0, '1_year': 0.0, '5_years': 0.0}
        uptime_datapoints = {'1_month': 0, '6_months': 0, '1_year': 0, '5_years': 0}
        uptime_section = uptime_relay.get('uptime', {})
        has_any_uptime = False
        
        for period in ['1_month', '6_months', '1_year', '5_years']:
            period_data = uptime_section.get(period, {})
            if period_data.get('values'):
                # Use optimized single-pass calculation that returns both values
                uptime_percentage, datapoints = _compute_uptime_percentage_and_datapoints(period_data['values'])
                uptime_percentages[period] = uptime_percentage
                uptime_datapoints[period] = datapoints
                
                # Collect for network statistics (only relays with valid uptime)
                if uptime_percentage > 0.0:
                    network_uptime_values[period].append(uptime_percentage)
                    has_any_uptime = True
        
        if has_any_uptime:
            network_relays_with_uptime += 1
        
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
                        # Use optimized single-pass calculation for flag data
                        avg_uptime, datapoints = _compute_uptime_percentage_and_datapoints(data['values'])
                        
                        if avg_uptime > 0.0:
                            flag_data[flag][period] = {
                                'uptime': avg_uptime,
                                'data_points': datapoints,
                                'relay_info': {
                                    'nickname': relay_obj.get('nickname', 'Unknown') if relay_obj else 'Unknown',
                                    'fingerprint': fingerprint
                                }
                            }
                            
                            # Collect for network flag statistics
                            network_flag_data[flag][period].append(avg_uptime)
        
        # Store processed data for this relay (including datapoints for AROI leaderboard display)
        relay_uptime_data[fingerprint] = {
            'uptime_percentages': uptime_percentages,
            'uptime_datapoints': uptime_datapoints,
            'flag_data': flag_data,
            'relay_obj': relay_obj  # Store reference for easy access
        }
    
    # Calculate network statistics for outlier detection using centralized function
    network_statistics = {}
    for period in ['1_month', '6_months', '1_year', '5_years']:
        values = network_uptime_values[period]
        # OPTIMIZATION: Use centralized statistical calculation function
        network_statistics[period] = _calculate_period_statistics(values)
    
    # Calculate network flag statistics using centralized function (if flag analysis enabled)
    network_flag_statistics = {}
    if include_flag_analysis:
        for flag, periods_data in network_flag_data.items():
            network_flag_statistics[flag] = {}
            for period, values in periods_data.items():
                # OPTIMIZATION: Use centralized statistical calculation function
                network_flag_statistics[flag][period] = _calculate_period_statistics(values)
    
    # Calculate middle relay statistics (non-Exit, non-Guard relays) for network health dashboard
    # This consolidates all role-specific calculations in one place following DRY principle
    network_middle_statistics = {}
    for period in ['1_month', '6_months', '1_year', '5_years']:
        middle_uptime_values = []
        
        # Collect middle relay uptime values for this period
        for fingerprint, relay_data in relay_uptime_data.items():
            relay_obj = relay_data['relay_obj']
            if relay_obj:  # Only process relays that are in our relay set
                flags = relay_obj.get('flags', [])
                is_exit = 'Exit' in flags
                is_guard = 'Guard' in flags
                
                # Middle relays are those that are neither Exit nor Guard (same logic as contact pages)
                if not is_exit and not is_guard:
                    uptime_value = relay_data['uptime_percentages'].get(period, 0.0)
                    if uptime_value > 0:  # Only include relays with actual uptime data
                        middle_uptime_values.append(uptime_value)
        
        # OPTIMIZATION: Use centralized statistical calculation function
        network_middle_statistics[period] = _calculate_period_statistics(middle_uptime_values)
    
    # Calculate other relay statistics (non-Exit, non-Guard, non-Middle relays) for network health dashboard
    # "Other" category includes: Directory Authorities, Bad Relays, Unflagged relays, Special status relays
    # This follows the same pattern as middle relay calculations for consistency
    network_other_statistics = {}
    for period in ['1_month', '6_months', '1_year', '5_years']:
        other_uptime_values = []
        
        # Collect other relay uptime values for this period
        for fingerprint, relay_data in relay_uptime_data.items():
            relay_obj = relay_data['relay_obj']
            if relay_obj:  # Only process relays that are in our relay set
                flags = relay_obj.get('flags', [])
                is_exit = 'Exit' in flags
                is_guard = 'Guard' in flags
                is_authority = 'Authority' in flags
                is_bad_exit = 'BadExit' in flags
                
                # Determine if this relay belongs to "other" category
                is_other = False
                
                # Directory Authorities - high priority special relays
                if is_authority:
                    is_other = True
                
                # Bad relays - flagged relays with potentially different uptime patterns
                elif is_bad_exit:
                    is_other = True
                
                # Unflagged relays - relays with no major flags (not Exit, Guard, Authority, or BadExit)
                elif not is_exit and not is_guard and not is_authority and not is_bad_exit:
                    # Check if relay has no significant flags at all or only minor flags
                    significant_flags = {'Exit', 'Guard', 'Authority', 'BadExit', 'HSDir', 'Fast', 'Stable', 'Running', 'Valid'}
                    relay_flags = set(flags)
                    has_significant_flags = bool(relay_flags.intersection(significant_flags))
                    if not has_significant_flags:
                        is_other = True
                
                # Special status relays - relays with unique flag combinations not covered by Exit/Guard/Middle
                # This covers edge cases like relays that might have unusual flag combinations
                elif not is_exit and not is_guard and (is_authority or is_bad_exit):
                    is_other = True
                
                # Include relays in "other" category that have uptime data
                if is_other:
                    uptime_value = relay_data['uptime_percentages'].get(period, 0.0)
                    if uptime_value > 0:  # Only include relays with actual uptime data
                        other_uptime_values.append(uptime_value)
        
        # OPTIMIZATION: Use centralized statistical calculation function
        network_other_statistics[period] = _calculate_period_statistics(other_uptime_values)
    
    return {
        'relay_uptime_data': relay_uptime_data,
        'network_statistics': network_statistics,
        'network_flag_statistics': network_flag_statistics if include_flag_analysis else None,
        'network_middle_statistics': network_middle_statistics,
        'network_other_statistics': network_other_statistics,
        'processing_summary': {
            'total_relays_processed': len(relay_uptime_data),
            'network_relays_with_uptime': len([r for r in relay_uptime_data.values() if any(p > 0 for p in r['uptime_percentages'].values())]),
            'flags_found': list(network_flag_data.keys()) if include_flag_analysis else []
        }
    } 