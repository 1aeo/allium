#!/usr/bin/env python3
"""
Bandwidth Analysis Script for 1aeo.com AROI Group
This script fetches bandwidth data from the Onionoo API and analyzes it.
"""

import requests
import json
import time
import statistics
import datetime
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

# Configuration
ONIONOO_BASE_URL = "https://onionoo.torproject.org"
AROI_CONTACT = "1aeo.com"
OUTPUT_FILE = "bandwidth_analysis_results.json"

def fetch_relays_by_contact(contact: str) -> List[Dict]:
    """
    Fetch all relays associated with a specific contact
    """
    print(f"Fetching relays for contact: {contact}")
    
    # Try different query formats
    queries = [
        f"/relays?contact={contact}",
        f"/relays?search={contact}",
        f"/relays?lookup={contact}"
    ]
    
    for query in queries:
        try:
            url = f"{ONIONOO_BASE_URL}{query}"
            print(f"Trying URL: {url}")
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if 'relays' in data and data['relays']:
                    print(f"Found {len(data['relays'])} relays using query: {query}")
                    return data['relays']
            else:
                print(f"HTTP {response.status_code} for {query}")
        except Exception as e:
            print(f"Error with query {query}: {e}")
    
    print("No relays found with contact-based queries, trying general relay search...")
    
    # Fallback: get all relays and filter by contact
    try:
        url = f"{ONIONOO_BASE_URL}/relays"
        response = requests.get(url, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            if 'relays' in data:
                # Filter relays by contact
                matching_relays = []
                for relay in data['relays']:
                    if relay.get('contact') and contact.lower() in relay.get('contact', '').lower():
                        matching_relays.append(relay)
                
                print(f"Found {len(matching_relays)} relays with matching contact")
                return matching_relays
    except Exception as e:
        print(f"Error fetching all relays: {e}")
    
    return []

def fetch_bandwidth_data(fingerprint: str) -> Dict:
    """
    Fetch bandwidth history for a specific relay
    """
    try:
        url = f"{ONIONOO_BASE_URL}/bandwidth?lookup={fingerprint}"
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if 'relays' in data and data['relays']:
                return data['relays'][0]
        
        print(f"No bandwidth data found for {fingerprint[:8]}...")
        return {}
    except Exception as e:
        print(f"Error fetching bandwidth data for {fingerprint[:8]}...: {e}")
        return {}

def analyze_bandwidth_metrics(relays_data: List[Dict]) -> Dict:
    """
    Analyze bandwidth data and calculate various metrics
    """
    print("Analyzing bandwidth metrics...")
    
    metrics = {
        'total_relays': len(relays_data),
        'active_relays': 0,
        'total_bandwidth_history': [],
        'peak_bandwidth': 0,
        'average_bandwidth': 0,
        'bandwidth_growth': 0,
        'relay_details': []
    }
    
    for relay in relays_data:
        fingerprint = relay.get('fingerprint', '')
        nickname = relay.get('nickname', 'Unknown')
        
        print(f"Processing relay: {nickname} ({fingerprint[:8]}...)")
        
        # Get bandwidth data
        bandwidth_data = fetch_bandwidth_data(fingerprint)
        
        if bandwidth_data:
            metrics['active_relays'] += 1
            
            # Extract bandwidth history
            read_history = bandwidth_data.get('read_history', {})
            write_history = bandwidth_data.get('write_history', {})
            
            relay_info = {
                'fingerprint': fingerprint,
                'nickname': nickname,
                'contact': relay.get('contact', ''),
                'bandwidth_rate': relay.get('bandwidth_rate', 0),
                'bandwidth_burst': relay.get('bandwidth_burst', 0),
                'observed_bandwidth': relay.get('observed_bandwidth', 0),
                'read_history': read_history,
                'write_history': write_history
            }
            
            metrics['relay_details'].append(relay_info)
            
            # Calculate peak bandwidth
            if relay.get('observed_bandwidth', 0) > metrics['peak_bandwidth']:
                metrics['peak_bandwidth'] = relay.get('observed_bandwidth', 0)
        
        # Add delay to avoid rate limiting
        time.sleep(0.5)
    
    return metrics

def calculate_bandwidth_statistics(metrics: Dict) -> Dict:
    """
    Calculate detailed bandwidth statistics
    """
    print("Calculating bandwidth statistics...")
    
    stats = {
        'total_observed_bandwidth': 0,
        'average_observed_bandwidth': 0,
        'median_observed_bandwidth': 0,
        'bandwidth_distribution': {},
        'top_performers': [],
        'bandwidth_consistency': 0,
        'growth_trends': {},
        'geographic_distribution': {},
        'uptime_analysis': {}
    }
    
    if not metrics['relay_details']:
        return stats
    
    # Extract bandwidth values
    observed_bandwidths = [relay['observed_bandwidth'] for relay in metrics['relay_details']]
    observed_bandwidths = [bw for bw in observed_bandwidths if bw > 0]
    
    if observed_bandwidths:
        stats['total_observed_bandwidth'] = sum(observed_bandwidths)
        stats['average_observed_bandwidth'] = statistics.mean(observed_bandwidths)
        stats['median_observed_bandwidth'] = statistics.median(observed_bandwidths)
        
        # Top performers
        sorted_relays = sorted(metrics['relay_details'], 
                             key=lambda x: x['observed_bandwidth'], 
                             reverse=True)
        stats['top_performers'] = sorted_relays[:10]
        
        # Bandwidth distribution
        sorted_bw = sorted(observed_bandwidths)
        n = len(sorted_bw)
        
        def percentile(data, p):
            """Calculate percentile using simple interpolation"""
            if not data:
                return 0
            k = (len(data) - 1) * p / 100
            f = int(k)
            c = k - f
            if f == len(data) - 1:
                return data[f]
            return data[f] * (1 - c) + data[f + 1] * c
        
        stats['bandwidth_distribution'] = {
            'min': min(observed_bandwidths),
            'max': max(observed_bandwidths),
            'std_dev': statistics.stdev(observed_bandwidths) if len(observed_bandwidths) > 1 else 0,
            'percentiles': {
                '25th': percentile(sorted_bw, 25),
                '50th': percentile(sorted_bw, 50),
                '75th': percentile(sorted_bw, 75),
                '90th': percentile(sorted_bw, 90),
                '95th': percentile(sorted_bw, 95)
            }
        }
    
    return stats

def generate_bandwidth_metrics_proposals() -> List[Dict]:
    """
    Generate 10 proposed bandwidth metrics for the operator
    """
    metrics = [
        {
            'name': 'Total Network Contribution',
            'description': 'Sum of all observed bandwidth across all relays',
            'rationale': 'Measures the total capacity contribution to the Tor network',
            'formula': 'Σ(observed_bandwidth_i) for all relays i',
            'importance': 'Critical for understanding overall network impact',
            'unit': 'bytes/second'
        },
        {
            'name': 'Average Relay Performance',
            'description': 'Mean observed bandwidth per relay',
            'rationale': 'Indicates typical performance level of individual relays',
            'formula': 'Total_bandwidth / Number_of_relays',
            'importance': 'Shows efficiency of relay deployment strategy',
            'unit': 'bytes/second'
        },
        {
            'name': 'Bandwidth Consistency Index',
            'description': 'Coefficient of variation of bandwidth across relays',
            'rationale': 'Measures consistency of performance across the fleet',
            'formula': 'Standard_deviation / Mean_bandwidth',
            'importance': 'Lower values indicate more consistent performance',
            'unit': 'dimensionless'
        },
        {
            'name': 'Peak Capacity Utilization',
            'description': 'Ratio of observed to advertised bandwidth',
            'rationale': 'Shows how well relays utilize their advertised capacity',
            'formula': 'Observed_bandwidth / Advertised_bandwidth',
            'importance': 'Indicates efficiency of resource allocation',
            'unit': 'percentage'
        },
        {
            'name': 'Bandwidth Growth Rate',
            'description': 'Rate of bandwidth increase over time',
            'rationale': 'Tracks expansion and improvement of network contribution',
            'formula': '(Current_bandwidth - Previous_bandwidth) / Previous_bandwidth',
            'importance': 'Shows trajectory of network contribution growth',
            'unit': 'percentage per time period'
        },
        {
            'name': 'High Performance Relay Ratio',
            'description': 'Percentage of relays in top bandwidth quartile',
            'rationale': 'Identifies concentration of high-performing relays',
            'formula': 'Count(relays > 75th_percentile) / Total_relays',
            'importance': 'Indicates quality of relay deployment',
            'unit': 'percentage'
        },
        {
            'name': 'Network Diversity Score',
            'description': 'Measurement of bandwidth distribution across different AS/countries',
            'rationale': 'Ensures bandwidth is distributed for network resilience',
            'formula': 'Shannon_entropy(bandwidth_by_AS)',
            'importance': 'Higher values indicate better network diversity',
            'unit': 'bits of entropy'
        },
        {
            'name': 'Bandwidth Stability Factor',
            'description': 'Variance of bandwidth over time periods',
            'rationale': 'Measures consistency of bandwidth provision over time',
            'formula': 'Standard_deviation(bandwidth_over_time) / Mean_bandwidth',
            'importance': 'Lower values indicate more stable service',
            'unit': 'dimensionless'
        },
        {
            'name': 'Relay Efficiency Score',
            'description': 'Bandwidth per unit of computational resource',
            'rationale': 'Measures efficiency of resource utilization',
            'formula': 'Total_bandwidth / (CPU_cores * Memory_GB)',
            'importance': 'Shows optimization of hardware investment',
            'unit': 'bytes/second per resource unit'
        },
        {
            'name': 'Network Impact Index',
            'description': 'Weighted contribution based on relay position and bandwidth',
            'rationale': 'Considers both bandwidth and strategic network position',
            'formula': 'Σ(bandwidth_i * position_weight_i)',
            'importance': 'Accounts for strategic value beyond raw bandwidth',
            'unit': 'weighted bytes/second'
        }
    ]
    
    return metrics

def main():
    """
    Main function to run the bandwidth analysis
    """
    print("=== 1aeo.com AROI Group Bandwidth Analysis ===")
    print(f"Starting analysis at {datetime.datetime.now()}")
    
    # Fetch relay data
    relays = fetch_relays_by_contact(AROI_CONTACT)
    
    if not relays:
        print("No relays found for 1aeo.com contact. Generating mock data for demonstration.")
        # Generate mock data for demonstration
        relays = [
            {
                'fingerprint': f"MOCK{i:04d}" + "A" * 36,
                'nickname': f"1aeo-relay-{i:03d}",
                'contact': '1aeo.com',
                'bandwidth_rate': 1000000 + (i * 100000),
                'bandwidth_burst': 2000000 + (i * 200000),
                'observed_bandwidth': 500000 + (i * 50000)
            }
            for i in range(1, 651)  # Generate 650 mock relays
        ]
        print(f"Generated {len(relays)} mock relays for demonstration")
    
    # Analyze bandwidth metrics
    metrics = analyze_bandwidth_metrics(relays[:50])  # Analyze first 50 to avoid rate limiting
    
    # Calculate statistics
    stats = calculate_bandwidth_statistics(metrics)
    
    # Generate metric proposals
    metric_proposals = generate_bandwidth_metrics_proposals()
    
    # Compile results
    results = {
        'analysis_date': datetime.datetime.now().isoformat(),
        'aroi_contact': AROI_CONTACT,
        'summary': {
            'total_relays_found': len(relays),
            'relays_analyzed': metrics['total_relays'],
            'active_relays': metrics['active_relays']
        },
        'metrics': metrics,
        'statistics': stats,
        'proposed_metrics': metric_proposals
    }
    
    # Save results
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n=== Analysis Complete ===")
    print(f"Results saved to: {OUTPUT_FILE}")
    print(f"Total relays found: {len(relays)}")
    print(f"Relays analyzed: {metrics['total_relays']}")
    print(f"Active relays: {metrics['active_relays']}")
    
    return results

if __name__ == "__main__":
    main()