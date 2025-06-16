"""
Flag Reliability Analysis Utilities for Tor Relay Operators

This module provides flag reliability metrics using the Onionoo uptime API
flag-specific data to help relay operators understand their flag performance
and stability over different time periods.

Key Metrics:
1. Flag-specific uptime percentages per time period
2. Network-wide statistical analysis (mean and 2σ) 
3. Color coding based on statistical significance and performance thresholds
4. Relay-specific outlier identification for tooltips
"""

import statistics
from datetime import datetime
from collections import defaultdict


class FlagReliabilityAnalyzer:
    """Analyze flag reliability and performance for Tor relays"""
    
    # Time period mappings for Onionoo data
    TIME_PERIODS = {
        '1_month': '1M',
        '6_months': '6M', 
        '1_year': '1Y',
        '5_years': '5Y'
    }
    
    # Flag display names and icons
    FLAG_INFO = {
        'Running': {'name': 'Basic Operation', 'icon': '⚡'},
        'Guard': {'name': 'Entry Guard', 'icon': '🛡️'},
        'Exit': {'name': 'Exit Node', 'icon': '🚪'},
        'Fast': {'name': 'Fast Relay', 'icon': '🚀'},
        'Stable': {'name': 'Stable Relay', 'icon': '📌'},
        'HSDir': {'name': 'Directory Services', 'icon': '📁'},
        'V2Dir': {'name': 'Directory Cache', 'icon': '🗃️'},
        'Authority': {'name': 'Directory Authority', 'icon': '👑'},
        'BadExit': {'name': 'Restricted Exit', 'icon': '⚠️'}
    }
    
    def __init__(self, all_relays_data, uptime_data):
        """
        Initialize with all relay data and uptime data
        
        Args:
            all_relays_data: List of all relay objects for the operator
            uptime_data: Onionoo uptime data containing flag-specific information
        """
        self.all_relays_data = all_relays_data
        self.uptime_data = uptime_data
        
    def calculate_operator_flag_reliability(self):
        """
        Calculate flag reliability metrics for the operator
        
        Returns:
            dict: Flag reliability analysis with stats and network comparisons
        """
        if not self.uptime_data or not self.all_relays_data:
            return {'has_flag_data': False}
            
        # Extract flag reliability data for operator's relays
        operator_flag_data = self._extract_operator_flag_data()
        
        if not operator_flag_data:
            return {'has_flag_data': False}
            
        # Calculate network-wide statistics for comparison
        network_stats = self._calculate_network_flag_statistics()
        
        # Process operator flag reliability
        operator_metrics = self._process_operator_flag_metrics(
            operator_flag_data, network_stats
        )
        
        return {
            'has_flag_data': True,
            'flag_reliabilities': operator_metrics,
            'network_stats': network_stats
        }
        
    def _extract_operator_flag_data(self):
        """Extract flag-specific uptime data for operator's relays"""
        operator_data = {}
        
        for relay in self.all_relays_data:
            fingerprint = relay.get('fingerprint', '')
            if not fingerprint:
                continue
                
            # Find uptime data for this relay
            relay_uptime = self._find_relay_uptime_data(fingerprint)
            
            if relay_uptime and relay_uptime.get('flags'):
                for flag, periods in relay_uptime['flags'].items():
                    if flag not in operator_data:
                        operator_data[flag] = {}
                        
                    for period, data in periods.items():
                        if period in self.TIME_PERIODS and data.get('values'):
                            # Convert fractional uptime values (0-1) to percentages
                            uptime_values = [
                                v * 100 for v in data['values'] 
                                if v is not None
                            ]
                            if uptime_values:
                                avg_uptime = statistics.mean(uptime_values)
                                
                                if period not in operator_data[flag]:
                                    operator_data[flag][period] = []
                                    
                                operator_data[flag][period].append({
                                    'fingerprint': fingerprint,
                                    'nickname': relay.get('nickname', 'Unknown'),
                                    'uptime': avg_uptime,
                                    'data_points': len(uptime_values)
                                })
        
        return operator_data
        
    def _find_relay_uptime_data(self, fingerprint):
        """Find uptime data for a specific relay by fingerprint"""
        if not self.uptime_data:
            return None
            
        for uptime_relay in self.uptime_data.get('relays', []):
            if uptime_relay.get('fingerprint') == fingerprint:
                return uptime_relay
                
        return None
        
    def _calculate_network_flag_statistics(self):
        """Calculate network-wide flag statistics for all relays in uptime data"""
        network_data = defaultdict(lambda: defaultdict(list))
        
        if not self.uptime_data:
            return {}
            
        for uptime_relay in self.uptime_data.get('relays', []):
            flags_data = uptime_relay.get('flags', {})
            
            for flag, periods in flags_data.items():
                for period, data in periods.items():
                    if period in self.TIME_PERIODS and data.get('values'):
                        uptime_values = [
                            v * 100 for v in data['values'] 
                            if v is not None
                        ]
                        if uptime_values:
                            avg_uptime = statistics.mean(uptime_values)
                            network_data[flag][period].append(avg_uptime)
        
        # Calculate statistics for each flag/period combination
        stats = {}
        for flag, periods in network_data.items():
            stats[flag] = {}
            for period, values in periods.items():
                if len(values) >= 3:  # Need minimum data for std dev
                    try:
                        mean_val = statistics.mean(values)
                        std_dev = statistics.stdev(values)
                        
                        stats[flag][period] = {
                            'mean': mean_val,
                            'std_dev': std_dev,
                            'count': len(values),
                            'two_sigma_low': mean_val - (2 * std_dev),
                            'two_sigma_high': mean_val + (2 * std_dev)
                        }
                    except statistics.StatisticsError:
                        pass
                        
        return stats
        
    def _process_operator_flag_metrics(self, operator_flag_data, network_stats):
        """Process operator flag metrics with network comparison"""
        processed_metrics = {}
        
        for flag, periods in operator_flag_data.items():
            flag_info = self.FLAG_INFO.get(flag, {'name': flag, 'icon': '🏷️'})
            
            processed_metrics[flag] = {
                'display_name': flag_info['name'],
                'icon': flag_info['icon'],
                'periods': {}
            }
            
            for period, relay_data in periods.items():
                display_period = self.TIME_PERIODS.get(period, period)
                
                # Calculate operator average for this flag/period
                uptimes = [relay['uptime'] for relay in relay_data]
                operator_avg = statistics.mean(uptimes) if uptimes else 0
                
                # Find outlier relays (>=2σ from network mean)
                outlier_relays = self._find_outlier_relays(
                    relay_data, flag, period, network_stats
                )
                
                # Determine color coding
                color_class = self._determine_color_class(
                    operator_avg, flag, period, network_stats
                )
                
                # Generate tooltip info
                tooltip_info = self._generate_tooltip_info(
                    operator_avg, flag, period, network_stats, outlier_relays
                )
                
                processed_metrics[flag]['periods'][display_period] = {
                    'value': operator_avg,
                    'color_class': color_class,
                    'tooltip': tooltip_info,
                    'relay_count': len(relay_data),
                    'outlier_relays': outlier_relays
                }
        
        return processed_metrics
        
    def _find_outlier_relays(self, relay_data, flag, period, network_stats):
        """Find relays that are >=2σ from network mean"""
        outliers = {'high': [], 'low': []}
        
        network_stat = network_stats.get(flag, {}).get(period)
        if not network_stat:
            return outliers
            
        two_sigma_low = network_stat['two_sigma_low'] 
        two_sigma_high = network_stat['two_sigma_high']
        
        for relay in relay_data:
            uptime = relay['uptime']
            if uptime >= two_sigma_high:
                outliers['high'].append({
                    'nickname': relay['nickname'],
                    'uptime': uptime,
                    'deviation': abs(uptime - network_stat['mean']) / network_stat['std_dev']
                })
            elif uptime <= two_sigma_low:
                outliers['low'].append({
                    'nickname': relay['nickname'], 
                    'uptime': uptime,
                    'deviation': abs(uptime - network_stat['mean']) / network_stat['std_dev']
                })
                
        return outliers
        
    def _determine_color_class(self, operator_avg, flag, period, network_stats):
        """Determine color class based on performance and statistical significance"""
        # Green if >99%
        if operator_avg > 99.0:
            return 'high-performance'
            
        # Check if >=2σ from network mean (red)
        network_stat = network_stats.get(flag, {}).get(period)
        if network_stat:
            if operator_avg <= network_stat['two_sigma_low']:
                return 'statistical-outlier-low'
            elif operator_avg >= network_stat['two_sigma_high']:
                return 'statistical-outlier-high'
                
        # Default color for normal performance
        return 'normal-performance'
        
    def _generate_tooltip_info(self, operator_avg, flag, period, network_stats, outlier_relays):
        """Generate tooltip information for flag/period combination"""
        network_stat = network_stats.get(flag, {}).get(period)
        
        if not network_stat:
            return f"Operator average: {operator_avg:.1f}% (no network data available)"
            
        tooltip_parts = [
            f"Operator avg: {operator_avg:.1f}%",
            f"Network μ: {network_stat['mean']:.1f}%",
            f"Network 2σ: {network_stat['two_sigma_low']:.1f}%-{network_stat['two_sigma_high']:.1f}%"
        ]
        
        # Add outlier relay information
        if outlier_relays['high']:
            high_nicknames = [r['nickname'] for r in outlier_relays['high'][:3]]
            tooltip_parts.append(f"High performers: {', '.join(high_nicknames)}")
            
        if outlier_relays['low']:
            low_nicknames = [r['nickname'] for r in outlier_relays['low'][:3]]
            tooltip_parts.append(f"Low performers: {', '.join(low_nicknames)}")
            
        return ' | '.join(tooltip_parts)


def normalize_uptime_value(raw_value):
    """
    Normalize uptime value from Onionoo's 0-1 fractional scale to 0-100 percentage.
    
    Args:
        raw_value (float): Raw uptime value from Onionoo API (0-1 fractional)
        
    Returns:
        float: Normalized percentage (0.0-100.0)
    """
    return raw_value * 100


def calculate_flag_uptime_average(uptime_values):
    """
    Calculate average flag uptime from a list of fractional Onionoo uptime values.
    
    Args:
        uptime_values (list): List of fractional uptime values (0-1 scale)
        
    Returns:
        float: Average uptime as percentage (0.0-100.0), or 0.0 if no valid values
    """
    if not uptime_values:
        return 0.0
    
    # Filter out None values and normalize to percentages
    valid_values = [normalize_uptime_value(v) for v in uptime_values if v is not None]
    if not valid_values:
        return 0.0
    
    return statistics.mean(valid_values)