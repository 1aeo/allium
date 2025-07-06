#!/usr/bin/env python3
"""
Comprehensive Historical Bandwidth Analysis for 1aeo.com AROI Group
Fetches historical bandwidth data for all 653 relays from Onionoo API
"""

import urllib.request
import json
import time
import statistics
import datetime
from collections import defaultdict
from typing import Dict, List, Optional

def fetch_url(url: str, timeout: int = 30) -> dict:
    """Fetch URL and return JSON data with error handling"""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = response.read()
            return json.loads(data.decode('utf-8'))
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return {}

def load_relay_data():
    """Load the relay data we already collected"""
    try:
        with open('1aeo_relays_data.json', 'r') as f:
            data = json.load(f)
            return data['relays']
    except Exception as e:
        print(f"Error loading relay data: {e}")
        return []

def fetch_bandwidth_history(fingerprint: str) -> dict:
    """Fetch comprehensive bandwidth history for a relay"""
    url = f"https://onionoo.torproject.org/bandwidth?lookup={fingerprint}"
    return fetch_url(url, timeout=30)

def parse_bandwidth_history(bandwidth_data: dict) -> dict:
    """Parse bandwidth history data into useful metrics"""
    if not bandwidth_data or 'relays' not in bandwidth_data or not bandwidth_data['relays']:
        return {}
    
    relay_data = bandwidth_data['relays'][0]
    
    parsed = {
        'fingerprint': relay_data.get('fingerprint', ''),
        'read_history': relay_data.get('read_history', {}),
        'write_history': relay_data.get('write_history', {}),
        'parsed_metrics': {}
    }
    
    # Parse different time periods
    time_periods = ['1_week', '1_month', '3_months', '1_year', '5_years']
    
    for period in time_periods:
        metrics = {
            'read': {},
            'write': {},
            'total': {}
        }
        
        # Parse read history
        if period in parsed['read_history']:
            read_data = parsed['read_history'][period]
            if 'values' in read_data and read_data['values']:
                values = [v for v in read_data['values'] if v is not None]
                if values:
                    metrics['read'] = {
                        'count': len(values),
                        'first': read_data.get('first', ''),
                        'last': read_data.get('last', ''),
                        'interval': read_data.get('interval', 0),
                        'min': min(values),
                        'max': max(values),
                        'mean': statistics.mean(values),
                        'median': statistics.median(values),
                        'std_dev': statistics.stdev(values) if len(values) > 1 else 0,
                        'total_bytes': sum(values) * read_data.get('interval', 0) if read_data.get('interval') else 0
                    }
        
        # Parse write history
        if period in parsed['write_history']:
            write_data = parsed['write_history'][period]
            if 'values' in write_data and write_data['values']:
                values = [v for v in write_data['values'] if v is not None]
                if values:
                    metrics['write'] = {
                        'count': len(values),
                        'first': write_data.get('first', ''),
                        'last': write_data.get('last', ''),
                        'interval': write_data.get('interval', 0),
                        'min': min(values),
                        'max': max(values),
                        'mean': statistics.mean(values),
                        'median': statistics.median(values),
                        'std_dev': statistics.stdev(values) if len(values) > 1 else 0,
                        'total_bytes': sum(values) * write_data.get('interval', 0) if write_data.get('interval') else 0
                    }
        
        # Calculate combined metrics
        if metrics['read'] and metrics['write']:
            read_mean = metrics['read']['mean']
            write_mean = metrics['write']['mean']
            metrics['total'] = {
                'mean_combined': read_mean + write_mean,
                'peak_combined': metrics['read']['max'] + metrics['write']['max'],
                'total_bytes': metrics['read']['total_bytes'] + metrics['write']['total_bytes']
            }
        
        parsed['parsed_metrics'][period] = metrics
    
    return parsed

def analyze_historical_trends(all_bandwidth_data: List[dict]) -> dict:
    """Analyze trends across all relays' historical data"""
    analysis = {
        'summary': {
            'total_relays_analyzed': len(all_bandwidth_data),
            'relays_with_1week_data': 0,
            'relays_with_1month_data': 0,
            'relays_with_1year_data': 0,
        },
        'aggregate_metrics': {},
        'trends': {},
        'performance_distribution': {},
        'temporal_analysis': {}
    }
    
    time_periods = ['1_week', '1_month', '3_months', '1_year', '5_years']
    
    for period in time_periods:
        period_data = {
            'read_means': [],
            'write_means': [],
            'combined_means': [],
            'total_bytes': [],
            'stability_scores': []
        }
        
        relays_with_data = 0
        
        for relay_data in all_bandwidth_data:
            if period in relay_data.get('parsed_metrics', {}):
                metrics = relay_data['parsed_metrics'][period]
                relays_with_data += 1
                
                if metrics['read']:
                    period_data['read_means'].append(metrics['read']['mean'])
                if metrics['write']:
                    period_data['write_means'].append(metrics['write']['mean'])
                if metrics['total']:
                    period_data['combined_means'].append(metrics['total']['mean_combined'])
                    period_data['total_bytes'].append(metrics['total']['total_bytes'])
                
                # Calculate stability score (lower coefficient of variation = more stable)
                if metrics['read'] and metrics['read']['std_dev'] > 0:
                    stability = 1 - (metrics['read']['std_dev'] / metrics['read']['mean'])
                    period_data['stability_scores'].append(max(0, stability))
        
        if relays_with_data > 0:
            analysis['summary'][f'relays_with_{period}_data'] = relays_with_data
            
            # Aggregate statistics
            agg_stats = {}
            for metric_type, values in period_data.items():
                if values:
                    agg_stats[metric_type] = {
                        'count': len(values),
                        'min': min(values),
                        'max': max(values),
                        'mean': statistics.mean(values),
                        'median': statistics.median(values),
                        'std_dev': statistics.stdev(values) if len(values) > 1 else 0,
                        'total': sum(values) if metric_type == 'total_bytes' else None
                    }
            
            analysis['aggregate_metrics'][period] = agg_stats
    
    return analysis

def calculate_advanced_metrics(relays: List[dict], historical_analysis: dict) -> dict:
    """Calculate advanced bandwidth metrics based on historical data"""
    
    current_time = datetime.datetime.now()
    
    metrics = {
        'total_network_contribution': {
            'current_observed_bandwidth': sum(r.get('observed_bandwidth', 0) for r in relays),
            'current_advertised_bandwidth': sum(r.get('bandwidth_rate', 0) for r in relays),
            'historical_peak_combined': 0,
            'utilization_efficiency': 0
        },
        'bandwidth_distribution_analysis': {
            'geographic_entropy': 0,
            'performance_concentration': {},
            'role_effectiveness': {}
        },
        'temporal_performance': {
            'stability_index': 0,
            'growth_trends': {},
            'consistency_scores': {}
        },
        'network_impact_assessment': {
            'diversity_scores': {},
            'strategic_value': {},
            'reliability_metrics': {}
        }
    }
    
    # Calculate utilization efficiency
    current_obs = metrics['total_network_contribution']['current_observed_bandwidth']
    current_adv = metrics['total_network_contribution']['current_advertised_bandwidth']
    if current_adv > 0:
        metrics['total_network_contribution']['utilization_efficiency'] = current_obs / current_adv
    
    # Geographic analysis
    countries = defaultdict(lambda: {'count': 0, 'bandwidth': 0})
    for relay in relays:
        country = relay.get('country', 'unknown')
        countries[country]['count'] += 1
        countries[country]['bandwidth'] += relay.get('observed_bandwidth', 0)
    
    # Calculate Shannon entropy for geographic distribution
    total_bandwidth = sum(data['bandwidth'] for data in countries.values())
    if total_bandwidth > 0:
        import math
        entropy = 0
        for data in countries.values():
            if data['bandwidth'] > 0:
                p = data['bandwidth'] / total_bandwidth
                entropy -= p * math.log2(p)
        metrics['bandwidth_distribution_analysis']['geographic_entropy'] = entropy
    
    # Performance concentration analysis
    bandwidths = [r.get('observed_bandwidth', 0) for r in relays]
    bandwidths.sort(reverse=True)
    
    total_bw = sum(bandwidths)
    if total_bw > 0:
        # Top 10% concentration
        top_10_percent = int(len(bandwidths) * 0.1)
        top_10_bw = sum(bandwidths[:top_10_percent])
        
        # Top 20% concentration  
        top_20_percent = int(len(bandwidths) * 0.2)
        top_20_bw = sum(bandwidths[:top_20_percent])
        
        metrics['bandwidth_distribution_analysis']['performance_concentration'] = {
            'top_10_percent_share': top_10_bw / total_bw,
            'top_20_percent_share': top_20_bw / total_bw,
            'gini_coefficient': calculate_gini_coefficient(bandwidths)
        }
    
    # Role effectiveness analysis
    flags_analysis = defaultdict(lambda: {'count': 0, 'bandwidth': 0})
    for relay in relays:
        for flag in relay.get('flags', []):
            flags_analysis[flag]['count'] += 1
            flags_analysis[flag]['bandwidth'] += relay.get('observed_bandwidth', 0)
    
    metrics['bandwidth_distribution_analysis']['role_effectiveness'] = dict(flags_analysis)
    
    return metrics

def calculate_gini_coefficient(values):
    """Calculate Gini coefficient for inequality measurement"""
    if not values or len(values) < 2:
        return 0
    
    values = sorted(values)
    n = len(values)
    cumsum = sum(values)
    
    if cumsum == 0:
        return 0
    
    index = list(range(1, n + 1))
    return (2 * sum(index[i] * values[i] for i in range(n))) / (n * cumsum) - (n + 1) / n

def main():
    print("=== 1aeo.com AROI Group Historical Bandwidth Analysis ===")
    print(f"Starting comprehensive analysis at {datetime.datetime.now()}")
    
    # Load relay data
    relays = load_relay_data()
    if not relays:
        print("No relay data found. Please run get_1aeo_relays.py first.")
        return
    
    print(f"Loaded {len(relays)} relays")
    
    # Fetch historical bandwidth data for all relays
    print("Fetching historical bandwidth data for all relays...")
    all_bandwidth_data = []
    
    for i, relay in enumerate(relays):
        fingerprint = relay.get('fingerprint', '')
        nickname = relay.get('nickname', 'Unknown')
        
        print(f"Processing {i+1}/{len(relays)}: {nickname} ({fingerprint[:8]}...)")
        
        # Fetch bandwidth history
        bandwidth_data = fetch_bandwidth_history(fingerprint)
        
        if bandwidth_data:
            # Parse the data
            parsed_data = parse_bandwidth_history(bandwidth_data)
            parsed_data['relay_info'] = relay  # Include basic relay info
            all_bandwidth_data.append(parsed_data)
        
        # Rate limiting - be respectful to the API
        if i < len(relays) - 1:  # Don't sleep after the last request
            time.sleep(0.5)  # 2 requests per second
    
    print(f"\nSuccessfully collected bandwidth history for {len(all_bandwidth_data)} relays")
    
    # Analyze historical trends
    print("Analyzing historical trends...")
    historical_analysis = analyze_historical_trends(all_bandwidth_data)
    
    # Calculate advanced metrics
    print("Calculating advanced metrics...")
    advanced_metrics = calculate_advanced_metrics(relays, historical_analysis)
    
    # Compile comprehensive results
    results = {
        'analysis_metadata': {
            'timestamp': datetime.datetime.now().isoformat(),
            'total_relays': len(relays),
            'successful_bandwidth_fetches': len(all_bandwidth_data),
            'api_source': 'https://onionoo.torproject.org/bandwidth',
            'analysis_type': 'comprehensive_historical'
        },
        'relay_summary': {
            'total_relays': len(relays),
            'running_relays': sum(1 for r in relays if r.get('running', False)),
            'total_observed_bandwidth': sum(r.get('observed_bandwidth', 0) for r in relays),
            'total_advertised_bandwidth': sum(r.get('bandwidth_rate', 0) for r in relays)
        },
        'historical_analysis': historical_analysis,
        'advanced_metrics': advanced_metrics,
        'bandwidth_histories': all_bandwidth_data
    }
    
    # Save comprehensive results
    output_file = 'comprehensive_1aeo_bandwidth_analysis.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n=== Analysis Complete ===")
    print(f"Comprehensive results saved to: {output_file}")
    print(f"Total data size: {len(json.dumps(results, default=str)):,} characters")
    
    # Print summary statistics
    print(f"\n=== Summary Statistics ===")
    print(f"Total relays analyzed: {len(relays)}")
    print(f"Successful bandwidth history fetches: {len(all_bandwidth_data)}")
    print(f"Success rate: {len(all_bandwidth_data)/len(relays)*100:.1f}%")
    
    if '1_month' in historical_analysis['aggregate_metrics']:
        month_stats = historical_analysis['aggregate_metrics']['1_month']
        if 'combined_means' in month_stats:
            avg_combined = month_stats['combined_means']['mean']
            print(f"Average 1-month combined bandwidth: {avg_combined:,.0f} bytes/sec ({avg_combined/1024/1024:.1f} MB/s)")
    
    print(f"Current total observed bandwidth: {results['relay_summary']['total_observed_bandwidth']:,} bytes/sec")
    print(f"Bandwidth utilization efficiency: {advanced_metrics['total_network_contribution']['utilization_efficiency']*100:.2f}%")
    
    return results

if __name__ == "__main__":
    main()