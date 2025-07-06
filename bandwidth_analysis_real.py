#!/usr/bin/env python3
"""
Real Bandwidth Analysis Script for 1aeo.com AROI Group
This script fetches real bandwidth data from the Onionoo API and analyzes it.
"""

import urllib.request
import urllib.parse
import json
import time
import statistics
import datetime
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

# Configuration
ONIONOO_BASE_URL = "https://onionoo.torproject.org"
AROI_CONTACT = "1aeo.com"
OUTPUT_FILE = "real_bandwidth_analysis_results.json"

def fetch_url(url: str, timeout: int = 30) -> Dict:
    """
    Fetch URL and return JSON data
    """
    try:
        print(f"Fetching: {url}")
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = response.read()
            return json.loads(data.decode('utf-8'))
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return {}

def fetch_all_relays() -> List[Dict]:
    """
    Fetch all relays from Onionoo API
    """
    print("Fetching all relays from Onionoo API...")
    url = f"{ONIONOO_BASE_URL}/relays"
    data = fetch_url(url, timeout=60)
    
    if 'relays' in data:
        print(f"Found {len(data['relays'])} total relays")
        return data['relays']
    
    return []

def filter_relays_by_contact(relays: List[Dict], contact: str) -> List[Dict]:
    """
    Filter relays by contact information
    """
    print(f"Filtering relays by contact: {contact}")
    
    matching_relays = []
    
    for relay in relays:
        relay_contact = relay.get('contact', '')
        if contact.lower() in relay_contact.lower():
            matching_relays.append(relay)
    
    print(f"Found {len(matching_relays)} relays matching contact '{contact}'")
    return matching_relays

def fetch_bandwidth_data(fingerprint: str) -> Dict:
    """
    Fetch bandwidth history for a specific relay
    """
    try:
        url = f"{ONIONOO_BASE_URL}/bandwidth?lookup={fingerprint}"
        data = fetch_url(url, timeout=30)
        
        if 'relays' in data and data['relays']:
            return data['relays'][0]
        
        return {}
    except Exception as e:
        print(f"Error fetching bandwidth data for {fingerprint[:8]}...: {e}")
        return {}

def analyze_relay_bandwidth(relay: Dict) -> Dict:
    """
    Analyze bandwidth data for a single relay
    """
    fingerprint = relay.get('fingerprint', '')
    nickname = relay.get('nickname', 'Unknown')
    
    print(f"Analyzing relay: {nickname} ({fingerprint[:8]}...)")
    
    # Get detailed bandwidth data
    bandwidth_data = fetch_bandwidth_data(fingerprint)
    
    analysis = {
        'fingerprint': fingerprint,
        'nickname': nickname,
        'contact': relay.get('contact', ''),
        'bandwidth_rate': relay.get('bandwidth_rate', 0),
        'bandwidth_burst': relay.get('bandwidth_burst', 0),
        'observed_bandwidth': relay.get('observed_bandwidth', 0),
        'advertised_bandwidth': relay.get('advertised_bandwidth', 0),
        'country': relay.get('country', ''),
        'as_number': relay.get('as_number', 0),
        'as_name': relay.get('as_name', ''),
        'running': relay.get('running', False),
        'flags': relay.get('flags', []),
        'first_seen': relay.get('first_seen', ''),
        'last_seen': relay.get('last_seen', ''),
        'platform': relay.get('platform', ''),
        'bandwidth_history': {}
    }
    
    if bandwidth_data:
        # Extract bandwidth history
        read_history = bandwidth_data.get('read_history', {})
        write_history = bandwidth_data.get('write_history', {})
        
        analysis['bandwidth_history'] = {
            'read_history': read_history,
            'write_history': write_history
        }
        
        # Process historical data
        if '1_month' in read_history and read_history['1_month']['values']:
            recent_read = read_history['1_month']['values']
            recent_read = [v for v in recent_read if v is not None]
            if recent_read:
                analysis['avg_read_1month'] = statistics.mean(recent_read)
                analysis['max_read_1month'] = max(recent_read)
                analysis['min_read_1month'] = min(recent_read)
        
        if '1_month' in write_history and write_history['1_month']['values']:
            recent_write = write_history['1_month']['values']
            recent_write = [v for v in recent_write if v is not None]
            if recent_write:
                analysis['avg_write_1month'] = statistics.mean(recent_write)
                analysis['max_write_1month'] = max(recent_write)
                analysis['min_write_1month'] = min(recent_write)
    
    return analysis

def calculate_aggregate_metrics(relay_analyses: List[Dict]) -> Dict:
    """
    Calculate aggregate metrics across all relays
    """
    print("Calculating aggregate metrics...")
    
    metrics = {
        'total_relays': len(relay_analyses),
        'running_relays': 0,
        'total_observed_bandwidth': 0,
        'total_advertised_bandwidth': 0,
        'total_bandwidth_rate': 0,
        'country_distribution': defaultdict(int),
        'as_distribution': defaultdict(int),
        'flag_distribution': defaultdict(int),
        'platform_distribution': defaultdict(int),
        'bandwidth_stats': {},
        'top_performers': [],
        'bandwidth_history_stats': {}
    }
    
    observed_bandwidths = []
    advertised_bandwidths = []
    bandwidth_rates = []
    
    for relay in relay_analyses:
        if relay.get('running'):
            metrics['running_relays'] += 1
        
        # Bandwidth aggregation
        obs_bw = relay.get('observed_bandwidth', 0)
        adv_bw = relay.get('advertised_bandwidth', 0)
        rate_bw = relay.get('bandwidth_rate', 0)
        
        if obs_bw > 0:
            observed_bandwidths.append(obs_bw)
            metrics['total_observed_bandwidth'] += obs_bw
        
        if adv_bw > 0:
            advertised_bandwidths.append(adv_bw)
            metrics['total_advertised_bandwidth'] += adv_bw
        
        if rate_bw > 0:
            bandwidth_rates.append(rate_bw)
            metrics['total_bandwidth_rate'] += rate_bw
        
        # Distributions
        if relay.get('country'):
            metrics['country_distribution'][relay['country']] += 1
        
        if relay.get('as_name'):
            metrics['as_distribution'][relay['as_name']] += 1
        
        for flag in relay.get('flags', []):
            metrics['flag_distribution'][flag] += 1
        
        if relay.get('platform'):
            metrics['platform_distribution'][relay['platform']] += 1
    
    # Calculate bandwidth statistics
    if observed_bandwidths:
        sorted_obs = sorted(observed_bandwidths)
        metrics['bandwidth_stats'] = {
            'observed': {
                'min': min(observed_bandwidths),
                'max': max(observed_bandwidths),
                'mean': statistics.mean(observed_bandwidths),
                'median': statistics.median(observed_bandwidths),
                'std_dev': statistics.stdev(observed_bandwidths) if len(observed_bandwidths) > 1 else 0,
                'total': sum(observed_bandwidths),
                'count': len(observed_bandwidths)
            }
        }
    
    if advertised_bandwidths:
        metrics['bandwidth_stats']['advertised'] = {
            'min': min(advertised_bandwidths),
            'max': max(advertised_bandwidths),
            'mean': statistics.mean(advertised_bandwidths),
            'median': statistics.median(advertised_bandwidths),
            'std_dev': statistics.stdev(advertised_bandwidths) if len(advertised_bandwidths) > 1 else 0,
            'total': sum(advertised_bandwidths),
            'count': len(advertised_bandwidths)
        }
    
    # Top performers
    metrics['top_performers'] = sorted(
        relay_analyses, 
        key=lambda x: x.get('observed_bandwidth', 0), 
        reverse=True
    )[:20]
    
    return metrics

def generate_bandwidth_metrics_proposals() -> List[Dict]:
    """
    Generate 10 proposed bandwidth metrics for the operator
    """
    metrics = [
        {
            'name': 'Total Network Contribution',
            'description': 'Sum of all observed bandwidth across all relays in the AROI group',
            'rationale': 'Measures the total capacity contribution to the Tor network. This is the most fundamental metric showing the overall impact of the operator.',
            'formula': 'Σ(observed_bandwidth_i) for all relays i',
            'importance': 'Critical for understanding overall network impact and capacity contribution',
            'unit': 'bytes/second',
            'calculation_method': 'Sum all observed_bandwidth values from active relays'
        },
        {
            'name': 'Average Relay Efficiency',
            'description': 'Mean ratio of observed to advertised bandwidth per relay',
            'rationale': 'Indicates how well relays utilize their advertised capacity. Higher efficiency means better resource utilization.',
            'formula': 'Mean(observed_bandwidth_i / advertised_bandwidth_i) for all relays i',
            'importance': 'Shows efficiency of relay deployment and network configuration',
            'unit': 'percentage',
            'calculation_method': 'Calculate ratio for each relay, then take the mean'
        },
        {
            'name': 'Bandwidth Distribution Diversity',
            'description': 'Coefficient of variation of bandwidth across relays',
            'rationale': 'Measures consistency of performance across the fleet. Lower values indicate more uniform performance.',
            'formula': 'Standard_deviation(observed_bandwidth) / Mean(observed_bandwidth)',
            'importance': 'Lower values indicate more consistent and predictable performance',
            'unit': 'dimensionless',
            'calculation_method': 'Standard deviation divided by mean of observed bandwidths'
        },
        {
            'name': 'Geographic Bandwidth Distribution',
            'description': 'Entropy of bandwidth distribution across countries',
            'rationale': 'Ensures bandwidth is geographically distributed for network resilience and reduced surveillance risk.',
            'formula': 'Shannon_entropy(bandwidth_by_country)',
            'importance': 'Higher values indicate better geographic diversity',
            'unit': 'bits of entropy',
            'calculation_method': 'Calculate Shannon entropy of bandwidth distribution by country'
        },
        {
            'name': 'High-Performance Relay Concentration',
            'description': 'Percentage of total bandwidth from top 20% of relays',
            'rationale': 'Identifies concentration of bandwidth in high-performing relays vs. distributed across many relays.',
            'formula': 'Sum(top_20%_bandwidth) / Total_bandwidth',
            'importance': 'Shows whether bandwidth is concentrated or distributed',
            'unit': 'percentage',
            'calculation_method': 'Sum bandwidth of top 20% relays divided by total bandwidth'
        },
        {
            'name': 'Bandwidth Growth Velocity',
            'description': 'Rate of bandwidth increase over time periods',
            'rationale': 'Tracks expansion and improvement of network contribution over time.',
            'formula': '(Current_period_bandwidth - Previous_period_bandwidth) / Previous_period_bandwidth',
            'importance': 'Shows trajectory of network contribution growth',
            'unit': 'percentage per time period',
            'calculation_method': 'Compare bandwidth across time periods from historical data'
        },
        {
            'name': 'Relay Uptime Bandwidth Weight',
            'description': 'Bandwidth-weighted uptime across all relays',
            'rationale': 'Accounts for both bandwidth contribution and reliability. High-bandwidth relays with poor uptime hurt this metric more.',
            'formula': 'Σ(bandwidth_i * uptime_i) / Σ(bandwidth_i)',
            'importance': 'Measures reliable bandwidth contribution to the network',
            'unit': 'percentage',
            'calculation_method': 'Weight uptime by bandwidth contribution'
        },
        {
            'name': 'AS Diversity Index',
            'description': 'Number of unique Autonomous Systems weighted by bandwidth',
            'rationale': 'Ensures bandwidth is distributed across different AS providers for network resilience.',
            'formula': 'Shannon_entropy(bandwidth_by_AS)',
            'importance': 'Higher values indicate better AS diversity',
            'unit': 'effective number of AS',
            'calculation_method': 'Calculate effective number of AS using Shannon entropy'
        },
        {
            'name': 'Bandwidth Stability Score',
            'description': 'Variance of bandwidth over recent time periods',
            'rationale': 'Measures consistency of bandwidth provision over time. More stable bandwidth is more valuable to users.',
            'formula': '1 - (Standard_deviation(bandwidth_over_time) / Mean_bandwidth)',
            'importance': 'Higher values indicate more stable and predictable service',
            'unit': 'stability score (0-1)',
            'calculation_method': 'Calculate coefficient of variation from historical bandwidth data'
        },
        {
            'name': 'Exit Relay Bandwidth Contribution',
            'description': 'Percentage of total bandwidth from exit relays',
            'rationale': 'Exit relays are critical for network usability but carry higher operational risk. This tracks their contribution.',
            'formula': 'Sum(exit_relay_bandwidth) / Total_bandwidth',
            'importance': 'Measures contribution to most critical relay type',
            'unit': 'percentage',
            'calculation_method': 'Sum bandwidth from relays with Exit flag divided by total bandwidth'
        }
    ]
    
    return metrics

def main():
    """
    Main function to run the real bandwidth analysis
    """
    print("=== 1aeo.com AROI Group Real Bandwidth Analysis ===")
    print(f"Starting analysis at {datetime.datetime.now()}")
    
    # Fetch all relays
    all_relays = fetch_all_relays()
    
    if not all_relays:
        print("Failed to fetch relay data from Onionoo API")
        return
    
    # Filter for 1aeo.com relays
    aeo_relays = filter_relays_by_contact(all_relays, AROI_CONTACT)
    
    if not aeo_relays:
        print(f"No relays found for contact '{AROI_CONTACT}'")
        return
    
    print(f"Found {len(aeo_relays)} relays for {AROI_CONTACT}")
    
    # Analyze each relay's bandwidth (limit to first 100 to avoid rate limiting)
    relay_analyses = []
    for i, relay in enumerate(aeo_relays[:100]):
        print(f"Processing relay {i+1}/{min(len(aeo_relays), 100)}")
        analysis = analyze_relay_bandwidth(relay)
        relay_analyses.append(analysis)
        
        # Rate limiting
        time.sleep(1)
    
    # Calculate aggregate metrics
    aggregate_metrics = calculate_aggregate_metrics(relay_analyses)
    
    # Generate metric proposals
    metric_proposals = generate_bandwidth_metrics_proposals()
    
    # Compile results
    results = {
        'analysis_date': datetime.datetime.now().isoformat(),
        'aroi_contact': AROI_CONTACT,
        'summary': {
            'total_relays_found': len(aeo_relays),
            'relays_analyzed': len(relay_analyses),
            'running_relays': aggregate_metrics['running_relays']
        },
        'relay_analyses': relay_analyses,
        'aggregate_metrics': aggregate_metrics,
        'proposed_metrics': metric_proposals
    }
    
    # Save results
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n=== Analysis Complete ===")
    print(f"Results saved to: {OUTPUT_FILE}")
    print(f"Total relays found: {len(aeo_relays)}")
    print(f"Relays analyzed: {len(relay_analyses)}")
    print(f"Running relays: {aggregate_metrics['running_relays']}")
    print(f"Total observed bandwidth: {aggregate_metrics['total_observed_bandwidth']:,} bytes/sec")
    
    return results

if __name__ == "__main__":
    main()