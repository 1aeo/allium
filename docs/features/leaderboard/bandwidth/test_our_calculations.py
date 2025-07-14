#!/usr/bin/env python3
"""
Test our bandwidth calculation functions against the Onionoo API data.
"""

import urllib.request
import urllib.error
import json
import sys
import os

# Add the current directory to Python path to import our modules
sys.path.append('/workspace')

from allium.lib.bandwidth_utils import extract_operator_daily_bandwidth_totals, extract_relay_bandwidth_for_period

class MockRelay:
    """Mock relay object to match what our functions expect."""
    def __init__(self, fingerprint, nickname):
        self.fingerprint = fingerprint
        self.nickname = nickname

def fetch_onionoo_data(endpoint, limit=None):
    """Fetch data from Onionoo API."""
    url = f"https://onionoo.torproject.org/{endpoint}"
    if limit:
        url += f"?limit={limit}"
    
    print(f"Fetching data from: {url}")
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data
    except urllib.error.URLError as e:
        print(f"Error fetching data: {e}")
        raise

def find_operator_relays_by_contact(details_data, keywords):
    """Find relays belonging to an operator based on contact info keywords."""
    matching_relays = []
    
    for relay in details_data.get('relays', []):
        contact = relay.get('contact', '').lower()
        if any(keyword.lower() in contact for keyword in keywords):
            # Create mock relay object
            mock_relay = MockRelay(
                fingerprint=relay.get('fingerprint'),
                nickname=relay.get('nickname', 'Unknown')
            )
            matching_relays.append(mock_relay)
    
    return matching_relays

def convert_to_bandwidth_format(bandwidth_data):
    """Convert bandwidth data to the format expected by our functions."""
    # Convert from list format to dict format keyed by fingerprint
    bandwidth_dict = {
        'relays': {}
    }
    
    for relay in bandwidth_data.get('relays', []):
        fingerprint = relay.get('fingerprint')
        if fingerprint:
            bandwidth_dict['relays'][fingerprint] = relay
    
    return bandwidth_dict

def format_bandwidth(bytes_per_second):
    """Format bandwidth in human-readable form."""
    if bytes_per_second >= 1e9:
        return f"{bytes_per_second / 1e9:.2f} GB/s"
    elif bytes_per_second >= 1e6:
        return f"{bytes_per_second / 1e6:.2f} MB/s"
    elif bytes_per_second >= 1e3:
        return f"{bytes_per_second / 1e3:.2f} KB/s"
    else:
        return f"{bytes_per_second:.2f} B/s"

def test_our_bandwidth_functions():
    """Test our bandwidth calculation functions."""
    print("Testing Our Bandwidth Calculation Functions")
    print("=" * 50)
    
    # Fetch data from Onionoo
    try:
        details_data = fetch_onionoo_data("details")
        print(f"Successfully fetched details data for {len(details_data.get('relays', []))} relays")
        
        bandwidth_data = fetch_onionoo_data("bandwidth")
        print(f"Successfully fetched bandwidth data for {len(bandwidth_data.get('relays', []))} relays")
    except Exception as e:
        print(f"Error fetching data: {e}")
        return
    
    # Find 1aeo relays
    operator_relays = find_operator_relays_by_contact(details_data, ['1aeo', 'aroi'])
    
    if not operator_relays:
        print("No 1aeo relays found")
        return
    
    print(f"Found {len(operator_relays)} 1aeo relays")
    
    # Convert bandwidth data to expected format
    bandwidth_dict = convert_to_bandwidth_format(bandwidth_data)
    
    # Test our functions
    for time_period in ['6_months', '5_years']:
        print(f"\n--- Testing {time_period.replace('_', ' ').title()} ---")
        
        # Test extract_operator_daily_bandwidth_totals
        daily_totals_result = extract_operator_daily_bandwidth_totals(operator_relays, bandwidth_dict, time_period)
        
        if daily_totals_result['daily_totals']:
            print(f"Our extract_operator_daily_bandwidth_totals results:")
            print(f"  Number of daily totals: {len(daily_totals_result['daily_totals'])}")
            print(f"  Average daily total: {format_bandwidth(daily_totals_result['average_daily_total'])}")
            print(f"  Average bandwidth: {(daily_totals_result['average_daily_total'] * 8) / 1e9:.2f} Gbps")
            
            # Show recent values
            print(f"  Last 7 days:")
            for i, daily_total in enumerate(daily_totals_result['daily_totals'][-7:]):
                print(f"    Day -{6-i}: {format_bandwidth(daily_total)}")
        else:
            print(f"No data available for {time_period}")
        
        # Test extract_relay_bandwidth_for_period
        relay_result = extract_relay_bandwidth_for_period(operator_relays, bandwidth_dict, time_period)
        
        if relay_result['bandwidth_values']:
            print(f"Our extract_relay_bandwidth_for_period results:")
            print(f"  Number of relays with data: {len(relay_result['bandwidth_values'])}")
            print(f"  Average per-relay bandwidth: {format_bandwidth(sum(relay_result['bandwidth_values']) / len(relay_result['bandwidth_values']))}")
            print(f"  Total bandwidth (sum): {format_bandwidth(sum(relay_result['bandwidth_values']))}")
        else:
            print(f"No relay data available for {time_period}")

if __name__ == "__main__":
    test_our_bandwidth_functions()