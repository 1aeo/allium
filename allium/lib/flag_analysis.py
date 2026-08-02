"""
File: flag_analysis.py

Statistical coloring, flag uptime/bandwidth display processing, and related
relay display formatting utilities.
Extracted from relays.py for better modularity.
"""

from .operator_analysis import calculate_uptime_display
from .time_utils import format_time_ago, PERIOD_SHORT_NAMES, ONIONOO_HISTORY_PERIODS

# Shared flag constants (DRY: used by both process_flag_bandwidth_display and process_flag_uptime_display)
FLAG_PRIORITY = {'Exit': 1, 'Guard': 2, 'Fast': 3, 'Running': 4}
FLAG_DISPLAY_NAMES = {
    'Exit': 'Exit Node',
    'Guard': 'Entry Guard',
    'Fast': 'Fast Relay',
    'Running': 'Running Operation'
}


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
        for period in ONIONOO_HISTORY_PERIODS:
            percentage = percentages.get(period, 0.0)
            percentage_str = f"{percentage:.1f}%"
            
            # Apply statistical coloring using pre-computed network statistics
            period_stats = network_statistics.get(period)
            if period_stats and percentage > 0:
                # Green for perfect uptime (100.0%)
                if percentage >= 100.0 or abs(percentage - 100.0) < 0.01:
                    percentage_str = f'<span class="al-status-success">{percentage_str}</span>'
                # Red for low outliers (>2 std dev below mean)
                elif percentage < period_stats['two_sigma_low']:
                    percentage_str = f'<span class="al-status-danger">{percentage_str}</span>'
                # Green for high outliers (>2 std dev above mean)
                elif percentage > period_stats['two_sigma_high']:
                    percentage_str = f'<span class="al-status-success">{percentage_str}</span>'
                # Yellow for below-mean values
                elif percentage < period_stats['mean']:
                    percentage_str = f'<span class="al-status-warning">{percentage_str}</span>'
                else:
                    # Above mean but within normal range
                    percentage_str = f'<span class="al-status-success">{percentage_str}</span>'
            
            display_parts.append(percentage_str)
        
        # Join with forward slashes
        relay["uptime_api_display"] = "/".join(display_parts)

def _process_flag_metric_display(relays, metric, no_priority_msg, periods,
                                 build_period_parts, all_dash_display=None):
    """
    Shared skeleton for flag uptime/bandwidth display processing: priority
    flag selection (Exit > Guard > Fast > Running, only flags the relay
    actually has), N/A fallbacks, per-period part collection, and result
    storage. All metric-specific formatting lives in build_period_parts,
    which maps (relay, selected_flag, flag_periods, period, period_short) to
    a (display_part, tooltip_part) pair — keeping each variant's output
    byte-identical. When all_dash_display is set and every period produced a
    dash, it is stored instead (the uptime variant's "Match" case).
    """
    data_key = f"_flag_{metric}_data"
    display_key = f"flag_{metric}_display"
    tooltip_key = f"flag_{metric}_tooltip"

    for relay in relays:
        relay_flags = set(relay.get('flags', []))
        flag_data = relay.get(data_key, {})

        if not flag_data or not relay_flags:
            relay[display_key] = "N/A"
            relay[tooltip_key] = f"No flag {metric} data available"
            continue

        # Determine priority flag from flags the relay ACTUALLY HAS
        selected_flag = None
        best_priority = float('inf')
        for flag in flag_data.keys():
            if flag in FLAG_PRIORITY and flag in relay_flags and FLAG_PRIORITY[flag] < best_priority:
                selected_flag = flag
                best_priority = FLAG_PRIORITY[flag]

        if not selected_flag or selected_flag not in flag_data:
            relay[display_key] = "N/A"
            relay[tooltip_key] = no_priority_msg
            continue

        display_parts = []
        tooltip_parts = []
        flag_display = FLAG_DISPLAY_NAMES[selected_flag]
        for period in periods:
            display_part, tooltip_part = build_period_parts(
                relay, selected_flag, flag_data[selected_flag], period, PERIOD_SHORT_NAMES[period]
            )
            display_parts.append(display_part)
            tooltip_parts.append(tooltip_part)

        # If all periods show dashes (no differences), show the match display instead
        if all_dash_display and all(part == "—" for part in display_parts):
            relay[display_key] = all_dash_display
            relay[tooltip_key] = f"{flag_display} flag {metric} matches overall uptime across all periods"
        else:
            relay[display_key] = "/".join(display_parts)
            relay[tooltip_key] = f"{flag_display} flag {metric} over time periods: " + ", ".join(tooltip_parts)

# Maps flag bandwidth color classes to the bold al-status-* span classes
# (flag uptime uses the non-bold variants inline below — do not unify)
_FLAG_BANDWIDTH_SPAN_CLASSES = {
    'high-performance': 'al-status-success-bold',
    'statistical-outlier-low': 'al-status-danger-bold',
    'statistical-outlier-high': 'al-status-success-bold',
    'below-mean': 'al-status-warning-bold',
}

def process_flag_bandwidth_display(relays, network_flag_statistics, bandwidth_formatter):
    """
    Process flag bandwidth data into display format with tooltips.

    Calculates flag-specific bandwidth display strings using priority system:
    Exit > Guard > Fast > Running flags. Only shows flags the relay actually has.

    Args:
        network_flag_statistics (dict): Network-wide flag statistics for comparison
    """
    def build_period_parts(relay, selected_flag, flag_periods, period, period_short):
        if not (period in flag_periods and flag_periods[period] > 0):
            return "—", f"{period_short}: No flag bandwidth data"

        bandwidth_val = flag_periods[period]
        data_points = 0  # Not tracked in simplified structure
        unit = bandwidth_formatter.determine_unit(bandwidth_val)
        formatted_bw = bandwidth_formatter.format_bandwidth_with_unit(bandwidth_val, unit)
        bandwidth_str = f"{formatted_bw} {unit}"

        # Apply FLAG BANDWIDTH color coding based on statistical position
        color_class = ''
        if (selected_flag in network_flag_statistics and
            period in network_flag_statistics[selected_flag] and
            network_flag_statistics[selected_flag][period]):

            net_stats = network_flag_statistics[selected_flag][period]
            if bandwidth_val <= net_stats['two_sigma_low']:
                color_class = 'statistical-outlier-low'
            elif bandwidth_val > net_stats['two_sigma_high']:
                color_class = 'statistical-outlier-high'
            elif bandwidth_val < net_stats['mean']:
                color_class = 'below-mean'
            # High performance threshold (top 10% or above 2x mean)
            elif bandwidth_val > net_stats['mean'] * 2:
                color_class = 'high-performance'

        span_class = _FLAG_BANDWIDTH_SPAN_CLASSES.get(color_class)
        styled_bandwidth = f'<span class="{span_class}">{bandwidth_str}</span>' if span_class else bandwidth_str
        return styled_bandwidth, f"{period_short}: {bandwidth_str} ({data_points} data points)"

    _process_flag_metric_display(
        relays, 'bandwidth', "No prioritized flag bandwidth data available",
        ['6_months', '1_year', '5_years'], build_period_parts
    )

def process_flag_uptime_display(relays, network_flag_statistics):
    """
    Process flag uptime data into display format with tooltips.

    Calculates flag-specific uptime display strings using priority system:
    Exit > Guard > Fast > Running flags. Only shows flags the relay actually has.
    Only displays flag uptime values when they differ from regular uptime.

    Args:
        network_flag_statistics (dict): Network-wide flag statistics for comparison
    """
    def build_period_parts(relay, selected_flag, flag_periods, period, period_short):
        if period not in flag_periods:
            return "—", f"{period_short}: No flag data"

        uptime_val = flag_periods[period]['uptime']

        # Only show flag uptime if it differs from regular uptime (allowing for
        # small floating point differences); a dash indicates "same as uptime"
        regular_uptime_val = relay.get("uptime_percentages", {}).get(period, 0.0)
        if abs(uptime_val - regular_uptime_val) < 0.1:
            return "—", f"{period_short}: Same as uptime ({uptime_val:.1f}%)"

        percentage_str = f"{uptime_val:.1f}%"
        network_comparison = ""

        if (selected_flag in network_flag_statistics and
            period in network_flag_statistics[selected_flag] and
            network_flag_statistics[selected_flag][period]):

            net_stats = network_flag_statistics[selected_flag][period]
            net_mean = net_stats.get('mean', 0)
            two_sigma_low = net_stats.get('two_sigma_low', 0)
            two_sigma_high = net_stats.get('two_sigma_high', float('inf'))

            # FLAG RELIABILITY color coding; very low values (≤1%) are likely
            # statistical outliers, values above mean within normal range stay plain
            if uptime_val <= 1.0:
                colored_str = f'<span class="al-status-danger">{percentage_str}</span>'  # Red
            elif uptime_val <= two_sigma_low:
                colored_str = f'<span class="al-status-danger">{percentage_str}</span>'  # Red
            elif uptime_val >= 99.0:
                colored_str = f'<span class="al-status-success">{percentage_str}</span>'  # Green
            elif uptime_val > two_sigma_high:
                colored_str = f'<span class="al-status-success">{percentage_str}</span>'  # Green
            elif uptime_val < net_mean:
                colored_str = f'<span class="al-status-warning">{percentage_str}</span>'  # Yellow
            else:
                colored_str = percentage_str

            # Add network comparison for tooltip (if available)
            if net_mean > 0:
                if uptime_val >= two_sigma_high:
                    network_comparison = f" (exceptional vs network μ {net_mean:.1f}%)"
                elif uptime_val <= two_sigma_low:
                    network_comparison = f" (low vs network μ {net_mean:.1f}%)"
                elif uptime_val < net_mean:
                    network_comparison = f" (below network μ {net_mean:.1f}%)"
                else:
                    network_comparison = f" (above network μ {net_mean:.1f}%)"
        else:
            # Fallback color coding when no network statistics available
            if uptime_val <= 1.0:
                colored_str = f'<span class="al-status-danger">{percentage_str}</span>'  # Red
            elif uptime_val >= 99.0:
                colored_str = f'<span class="al-status-success">{percentage_str}</span>'  # Green
            else:
                colored_str = percentage_str

        return colored_str, f"{period_short}: {uptime_val:.1f}%{network_comparison}"

    _process_flag_metric_display(
        relays, 'uptime', "No prioritized flag data available",
        ONIONOO_HISTORY_PERIODS, build_period_parts,
        all_dash_display="Match"
    )

def basic_uptime_processing(relays):
    """
    Basic uptime processing fallback if consolidated processing fails.
    This maintains the original logic for compatibility.
    """
    for relay in relays:
        # Basic uptime/downtime display
        relay["uptime_display"] = calculate_uptime_display(relay, format_time_ago)
        
        # Basic uptime percentages without statistical analysis
        uptime_percentages = {p: 0.0 for p in ONIONOO_HISTORY_PERIODS}
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


