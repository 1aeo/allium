"""
File: flag_analysis.py

Statistical coloring, flag uptime/bandwidth display processing, and related
relay display formatting utilities.
Extracted from relays.py for better modularity.
"""

from .operator_analysis import calculate_uptime_display
from .time_utils import format_time_ago


def calculate_network_bandwidth_percentiles(bandwidth_data, relay_set):
    """
    Calculate network-wide bandwidth percentiles for operator comparison.
    Mirrors the uptime percentile calculation but for bandwidth data.
    
    Args:
        bandwidth_data: Bandwidth data from Onionoo API
        
    Returns:
        dict: Network bandwidth percentiles or None if insufficient data
    """
    if not bandwidth_data or 'contact' not in relay_set.json.get('sorted', {}):
        return None
        
    try:
        from .bandwidth_utils import extract_operator_daily_bandwidth_totals
        import statistics
        
        contacts = relay_set.json['sorted']['contact']
        operator_bandwidth_values = []
        
        # Calculate 6-month average bandwidth for each operator
        for contact_hash, contact_data in contacts.items():
            if not contact_data.get('relays'):
                continue
                
            operator_relays = [relay_set.json['relays'][i] for i in contact_data['relays']]
            
            # Use daily totals calculation (matches AROI leaderboard logic)
            daily_totals_result = extract_operator_daily_bandwidth_totals(
                operator_relays, bandwidth_data, '6_months'
            )
            
            if daily_totals_result['daily_totals']:
                avg_bandwidth = daily_totals_result['average_daily_total']
                if avg_bandwidth > 0:  # Only include operators with actual bandwidth
                    operator_bandwidth_values.append(avg_bandwidth)
        
        if len(operator_bandwidth_values) < 10:  # Need minimum operators for percentiles
            return None
            
        # Calculate percentiles
        operator_bandwidth_values.sort()
        
        return {
            'percentile_5': statistics.quantiles(operator_bandwidth_values, n=20)[0],   # 5th percentile
            'percentile_25': statistics.quantiles(operator_bandwidth_values, n=4)[0],   # 25th percentile  
            'percentile_50': statistics.median(operator_bandwidth_values),              # Median
            'percentile_75': statistics.quantiles(operator_bandwidth_values, n=4)[2],   # 75th percentile
            'percentile_95': statistics.quantiles(operator_bandwidth_values, n=20)[18], # 95th percentile
            'total_operators': len(operator_bandwidth_values)
        }
        
    except Exception as e:
        print(f"Warning: Network bandwidth percentiles calculation failed: {e}")
        return None

def apply_statistical_coloring(relays, network_statistics):
    """
    Apply statistical coloring to relay uptime percentages using pre-computed network statistics.
    
    Args:
        network_statistics (dict): Pre-computed network statistics for each time period
    """
    for relay in relays:
        percentages = relay.get("uptime_percentages", {})
        display_parts = []
        
        # Format as "96.7%/98.2%/93.2%/86.1%" with coloring
        for period in ['1_month', '6_months', '1_year', '5_years']:
            percentage = percentages.get(period, 0.0)
            percentage_str = f"{percentage:.1f}%"
            
            # Apply statistical coloring using pre-computed network statistics
            period_stats = network_statistics.get(period)
            if period_stats and percentage > 0:
                # Green for perfect uptime (100.0%)
                if percentage >= 100.0 or abs(percentage - 100.0) < 0.01:
                    percentage_str = f'<span style="color: #28a745;">{percentage_str}</span>'
                # Red for low outliers (>2 std dev below mean)
                elif percentage < period_stats['two_sigma_low']:
                    percentage_str = f'<span style="color: #dc3545;">{percentage_str}</span>'
                # Green for high outliers (>2 std dev above mean)
                elif percentage > period_stats['two_sigma_high']:
                    percentage_str = f'<span style="color: #28a745;">{percentage_str}</span>'
                # Yellow for below-mean values
                elif percentage < period_stats['mean']:
                    percentage_str = f'<span style="color: #cc9900;">{percentage_str}</span>'
                else:
                    # Above mean but within normal range
                    percentage_str = f'<span style="color: #28a745;">{percentage_str}</span>'
            
            display_parts.append(percentage_str)
        
        # Join with forward slashes
        relay["uptime_api_display"] = "/".join(display_parts)

def process_flag_bandwidth_display(relays, network_flag_statistics, bandwidth_formatter):
    """
    Process flag bandwidth data into display format with tooltips.
    
    Calculates flag-specific bandwidth display strings using priority system:
    Exit > Guard > Fast > Running flags. Only shows flags the relay actually has.
    
    Args:
        network_flag_statistics (dict): Network-wide flag statistics for comparison
    """
    # Flag priority mapping (Exit > Guard > Fast > Running)
    flag_priority = {'Exit': 1, 'Guard': 2, 'Fast': 3, 'Running': 4}
    flag_display_names = {
        'Exit': 'Exit Node',
        'Guard': 'Entry Guard', 
        'Fast': 'Fast Relay',
        'Running': 'Running Operation'
    }
    
    for relay in relays:
        # Get actual flags this relay has
        relay_flags = set(relay.get('flags', []))
        flag_data = relay.get("_flag_bandwidth_data", {})
        
        if not flag_data or not relay_flags:
            relay["flag_bandwidth_display"] = "N/A"
            relay["flag_bandwidth_tooltip"] = "No flag bandwidth data available"
            continue
        
        # Determine priority flag from flags the relay ACTUALLY HAS
        selected_flag = None
        best_priority = float('inf')
        
        for flag in flag_data.keys():
            # Only consider flags the relay actually has
            if flag in flag_priority and flag in relay_flags and flag_priority[flag] < best_priority:
                selected_flag = flag
                best_priority = flag_priority[flag]
        
        if not selected_flag or selected_flag not in flag_data:
            relay["flag_bandwidth_display"] = "N/A"
            relay["flag_bandwidth_tooltip"] = "No prioritized flag bandwidth data available"
            continue
        
        # Build display string with formatting
        display_parts = []
        tooltip_parts = []
        flag_display = flag_display_names[selected_flag]
        
        for period in ['6_months', '1_year', '5_years']:
            # Map to short period names for tooltip
            period_short = {'6_months': '6M', '1_year': '1Y', '5_years': '5Y'}[period]
            
            if period in flag_data[selected_flag] and flag_data[selected_flag][period] > 0:
                bandwidth_val = flag_data[selected_flag][period]
                data_points = 0  # Not tracked in simplified structure
                
                # Format bandwidth value
                unit = bandwidth_formatter.determine_unit(bandwidth_val)
                formatted_bw = bandwidth_formatter.format_bandwidth_with_unit(bandwidth_val, unit)
                bandwidth_str = f"{formatted_bw} {unit}"
                
                # Apply FLAG BANDWIDTH color coding
                color_class = ''
                if (selected_flag in network_flag_statistics and 
                    period in network_flag_statistics[selected_flag] and
                    network_flag_statistics[selected_flag][period]):
                    
                    net_stats = network_flag_statistics[selected_flag][period]
                    
                    # Color coding based on statistical position
                    if bandwidth_val <= net_stats['two_sigma_low']:
                        color_class = 'statistical-outlier-low'
                    elif bandwidth_val > net_stats['two_sigma_high']:
                        color_class = 'statistical-outlier-high'
                    elif bandwidth_val < net_stats['mean']:
                        color_class = 'below-mean'
                    # High performance threshold (top 10% or above 2x mean)
                    elif bandwidth_val > net_stats['mean'] * 2:
                        color_class = 'high-performance'
                
                # Apply color styling based on class
                if color_class == 'high-performance':
                    styled_bandwidth = f'<span style="color: #28a745; font-weight: bold;">{bandwidth_str}</span>'
                elif color_class == 'statistical-outlier-low':
                    styled_bandwidth = f'<span style="color: #dc3545; font-weight: bold;">{bandwidth_str}</span>'
                elif color_class == 'statistical-outlier-high':
                    styled_bandwidth = f'<span style="color: #28a745; font-weight: bold;">{bandwidth_str}</span>'
                elif color_class == 'below-mean':
                    styled_bandwidth = f'<span style="color: #cc9900; font-weight: bold;">{bandwidth_str}</span>'
                else:
                    styled_bandwidth = bandwidth_str
                
                display_parts.append(styled_bandwidth)
                tooltip_parts.append(f"{period_short}: {bandwidth_str} ({data_points} data points)")
            else:
                # No data for this period
                display_parts.append("—")
                tooltip_parts.append(f"{period_short}: No flag bandwidth data")
        
        # Store results
        relay["flag_bandwidth_display"] = "/".join(display_parts)
        # Generate tooltip in same format as flag reliability
        relay["flag_bandwidth_tooltip"] = f"{flag_display} flag bandwidth over time periods: " + ", ".join(tooltip_parts)

def process_flag_uptime_display(relays, network_flag_statistics):
    """
    Process flag uptime data into display format with tooltips.
    
    Calculates flag-specific uptime display strings using priority system:
    Exit > Guard > Fast > Running flags. Only shows flags the relay actually has.
    Only displays flag uptime values when they differ from regular uptime.
    
    Args:
        network_flag_statistics (dict): Network-wide flag statistics for comparison
    """
    # Flag priority mapping (Exit > Guard > Fast > Running)
    flag_priority = {'Exit': 1, 'Guard': 2, 'Fast': 3, 'Running': 4}
    flag_display_names = {
        'Exit': 'Exit Node',
        'Guard': 'Entry Guard', 
        'Fast': 'Fast Relay',
        'Running': 'Running Operation'
    }
    
    for relay in relays:
        # Get actual flags this relay has
        relay_flags = set(relay.get('flags', []))
        flag_data = relay.get("_flag_uptime_data", {})
        
        if not flag_data or not relay_flags:
            relay["flag_uptime_display"] = "N/A"
            relay["flag_uptime_tooltip"] = "No flag uptime data available"
            continue
        
        # Determine priority flag from flags the relay ACTUALLY HAS
        selected_flag = None
        best_priority = float('inf')
        
        for flag in flag_data.keys():
            # Only consider flags the relay actually has
            if flag in flag_priority and flag in relay_flags and flag_priority[flag] < best_priority:
                selected_flag = flag
                best_priority = flag_priority[flag]
        
        if not selected_flag or selected_flag not in flag_data:
            relay["flag_uptime_display"] = "N/A"
            relay["flag_uptime_tooltip"] = "No prioritized flag data available"
            continue
        
        # Build display string with color coding and prefix
        display_parts = []
        tooltip_parts = []
        flag_display = flag_display_names[selected_flag]
        
        # Get regular uptime percentages for comparison
        regular_uptime = relay.get("uptime_percentages", {})
        
        for period in ['1_month', '6_months', '1_year', '5_years']:
            # Map to short period names for tooltip
            period_short = {'1_month': '1M', '6_months': '6M', '1_year': '1Y', '5_years': '5Y'}[period]
            
            if period in flag_data[selected_flag]:
                uptime_val = flag_data[selected_flag][period]['uptime']
                data_points = flag_data[selected_flag][period].get('data_points', 0)
                
                # Compare flag uptime with regular uptime before adding prefix
                regular_uptime_val = regular_uptime.get(period, 0.0)
                
                # Only show flag uptime if it differs from regular uptime (allowing for small floating point differences)
                if abs(uptime_val - regular_uptime_val) < 0.1:
                    # Values are essentially the same, skip showing flag uptime for this period
                    display_parts.append("—")  # Show dash to indicate "same as uptime"
                    tooltip_parts.append(f"{period_short}: Same as uptime ({uptime_val:.1f}%)")
                    continue
                
                # Format without prefix
                percentage_str = f"{uptime_val:.1f}%"
                
                # Apply FLAG RELIABILITY color coding (not uptime color coding)
                color_class = ''
                
                # Add network comparison for color determination
                if (selected_flag in network_flag_statistics and 
                    period in network_flag_statistics[selected_flag] and
                    network_flag_statistics[selected_flag][period]):
                    
                    net_stats = network_flag_statistics[selected_flag][period]
                    net_mean = net_stats.get('mean', 0)
                    two_sigma_low = net_stats.get('two_sigma_low', 0)
                    two_sigma_high = net_stats.get('two_sigma_high', float('inf'))
                    
                    # Enhanced color coding logic matching flag reliability:
                    # Special handling for very low values (≤1%) - likely to be statistical outliers
                    if uptime_val <= 1.0:
                        colored_str = f'<span style="color: #dc3545;">{percentage_str}</span>'  # Red
                    elif uptime_val <= two_sigma_low:
                        colored_str = f'<span style="color: #dc3545;">{percentage_str}</span>'  # Red
                    elif uptime_val >= 99.0:
                        colored_str = f'<span style="color: #28a745;">{percentage_str}</span>'  # Green
                    elif uptime_val > two_sigma_high:
                        colored_str = f'<span style="color: #28a745;">{percentage_str}</span>'  # Green
                    elif uptime_val < net_mean:
                        colored_str = f'<span style="color: #cc9900;">{percentage_str}</span>'  # Yellow
                    else:
                        # Above mean but within normal range - no special coloring
                        colored_str = percentage_str
                else:
                    # Fallback color coding when no network statistics available
                    if uptime_val <= 1.0:
                        colored_str = f'<span style="color: #dc3545;">{percentage_str}</span>'  # Red
                    elif uptime_val >= 99.0:
                        colored_str = f'<span style="color: #28a745;">{percentage_str}</span>'  # Green
                    else:
                        # Default: no special coloring
                        colored_str = percentage_str
                
                display_parts.append(colored_str)
                
                # Add network comparison for tooltip (if available)
                network_comparison = ""
                if (selected_flag in network_flag_statistics and 
                    period in network_flag_statistics[selected_flag] and
                    network_flag_statistics[selected_flag][period]):
                    
                    net_stats = network_flag_statistics[selected_flag][period]
                    net_mean = net_stats.get('mean', 0)
                    if net_mean > 0:
                        if uptime_val >= net_stats.get('two_sigma_high', float('inf')):
                            network_comparison = f" (exceptional vs network μ {net_mean:.1f}%)"
                        elif uptime_val <= net_stats.get('two_sigma_low', 0):
                            network_comparison = f" (low vs network μ {net_mean:.1f}%)"
                        elif uptime_val < net_mean:
                            network_comparison = f" (below network μ {net_mean:.1f}%)"
                        else:
                            network_comparison = f" (above network μ {net_mean:.1f}%)"
                
                tooltip_parts.append(f"{period_short}: {uptime_val:.1f}%{network_comparison}")
            else:
                # No data for this period
                display_parts.append("—")
                tooltip_parts.append(f"{period_short}: No flag data")
        
        # Store results
        # If all periods show dashes (no differences), show "N/A" instead
        if all(part == "—" for part in display_parts):
            relay["flag_uptime_display"] = "Match"
            relay["flag_uptime_tooltip"] = f"{flag_display} flag uptime matches overall uptime across all periods"
        else:
            relay["flag_uptime_display"] = "/".join(display_parts)
            # Generate tooltip in same format as flag reliability
            relay["flag_uptime_tooltip"] = f"{flag_display} flag uptime over time periods: " + ", ".join(tooltip_parts)

def basic_uptime_processing(relays):
    """
    Basic uptime processing fallback if consolidated processing fails.
    This maintains the original logic for compatibility.
    """
    for relay in relays:
        # Basic uptime/downtime display
        relay["uptime_display"] = calculate_uptime_display(relay)
        
        # Basic uptime percentages without statistical analysis
        uptime_percentages = {'1_month': 0.0, '6_months': 0.0, '1_year': 0.0, '5_years': 0.0}
        relay["uptime_percentages"] = uptime_percentages
        relay["_uptime_datapoints"] = {}
        relay["uptime_api_display"] = "0.0%/0.0%/0.0%/0.0%"
        
        # Initialize flag uptime display for fallback processing
        relay["flag_uptime_display"] = "N/A"
        relay["flag_uptime_tooltip"] = "Uptime data processing failed"

def sort_by_observed_bandwidth(relay_json):
    """
    Sort full JSON list by highest observed_bandwidth, retain this order
    during subsequent sorting (country, AS, etc)
    """
    relay_json["relays"].sort(
        key=lambda x: x["observed_bandwidth"], reverse=True
    )


