#!/usr/bin/env python3
"""
Investigate raw bandwidth values to understand why average is lower than peaks.
"""

import urllib.request
import urllib.error
import json
import statistics

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
            matching_relays.append(relay)
    
    return matching_relays

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

def investigate_raw_values():
    """Investigate raw bandwidth values to understand the discrepancy."""
    print("Investigating Raw Bandwidth Values")
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
    
    # Get fingerprints
    operator_fingerprints = [relay.get('fingerprint') for relay in operator_relays]
    
    # Find matching relays in bandwidth data
    matching_bandwidth_relays = []
    for relay in bandwidth_data.get('relays', []):
        if relay.get('fingerprint') in operator_fingerprints:
            matching_bandwidth_relays.append(relay)
    
    print(f"Found {len(matching_bandwidth_relays)} matching relays in bandwidth data")
    
    # Analyze 6_months data
    time_period = '6_months'
    
    # Get first relay with data to understand the structure
    first_relay = None
    for relay in matching_bandwidth_relays:
        if 'write_history' in relay and time_period in relay['write_history']:
            first_relay = relay
            break
    
    if not first_relay:
        print("No relay found with write_history data")
        return
    
    first_history = first_relay['write_history'][time_period]
    if 'values' not in first_history:
        print("No values found in write_history")
        return
    
    factor = first_history.get('factor', 1.0)
    values_length = len(first_history['values'])
    
    print(f"\nData structure analysis:")
    print(f"  Factor: {factor}")
    print(f"  Number of days: {values_length}")
    print(f"  First relay: {first_relay.get('nickname', 'Unknown')}")
    
    # Calculate daily totals
    daily_totals = []
    
    for day_idx in range(values_length):
        daily_total = 0.0
        valid_relays_for_day = 0
        
        for relay in matching_bandwidth_relays:
            if 'write_history' in relay and time_period in relay['write_history']:
                history = relay['write_history'][time_period]
                if 'values' in history and day_idx < len(history['values']):
                    value = history['values'][day_idx]
                    if value is not None:
                        # Apply factor to get actual bytes/second
                        actual_value = value * factor
                        daily_total += actual_value
                        valid_relays_for_day += 1
        
        if valid_relays_for_day > 0:
            daily_totals.append(daily_total)
    
    if not daily_totals:
        print("No daily totals calculated")
        return
    
    # Analyze the distribution
    print(f"\nDaily totals analysis:")
    print(f"  Number of days with data: {len(daily_totals)}")
    print(f"  Average daily bandwidth: {format_bandwidth(statistics.mean(daily_totals))}")
    print(f"  Median daily bandwidth: {format_bandwidth(statistics.median(daily_totals))}")
    print(f"  Max daily bandwidth: {format_bandwidth(max(daily_totals))}")
    print(f"  Min daily bandwidth: {format_bandwidth(min(daily_totals))}")
    print(f"  Standard deviation: {format_bandwidth(statistics.stdev(daily_totals))}")
    
    # Convert to Gbps
    average_gbps = (statistics.mean(daily_totals) * 8) / 1e9
    max_gbps = (max(daily_totals) * 8) / 1e9
    min_gbps = (min(daily_totals) * 8) / 1e9
    
    print(f"\nIn Gbps:")
    print(f"  Average: {average_gbps:.2f} Gbps")
    print(f"  Max: {max_gbps:.2f} Gbps")
    print(f"  Min: {min_gbps:.2f} Gbps")
    
    # Show recent 14 days
    print(f"\nLast 14 days (most recent first):")
    for i, daily_total in enumerate(daily_totals[-14:]):
        gbps = (daily_total * 8) / 1e9
        print(f"  Day -{13-i}: {format_bandwidth(daily_total)} ({gbps:.2f} Gbps)")
    
    # Show highest 10 days
    sorted_totals = sorted(daily_totals, reverse=True)
    print(f"\nTop 10 highest bandwidth days:")
    for i, daily_total in enumerate(sorted_totals[:10]):
        gbps = (daily_total * 8) / 1e9
        print(f"  #{i+1}: {format_bandwidth(daily_total)} ({gbps:.2f} Gbps)")
    
    # Show lowest 10 days
    print(f"\nBottom 10 lowest bandwidth days:")
    for i, daily_total in enumerate(sorted_totals[-10:]):
        gbps = (daily_total * 8) / 1e9
        print(f"  #{i+1}: {format_bandwidth(daily_total)} ({gbps:.2f} Gbps)")

if __name__ == "__main__":
    investigate_raw_values()