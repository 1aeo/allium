#!/usr/bin/env python3
"""
Verification script to test bandwidth calculation logic against Onionoo API.
This script will manually verify the math for key operators like 1aeo and nothingtohide.nl.
"""

import urllib.request
import urllib.error
import json
import statistics
from datetime import datetime, timedelta

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

def explore_contact_info(details_data, keywords):
    """Explore available contact information to find operators."""
    print(f"\n{'='*60}")
    print(f"EXPLORING CONTACT INFO FOR: {keywords}")
    print(f"{'='*60}")
    
    matching_contacts = []
    
    for relay in details_data.get('relays', []):
        contact = relay.get('contact', '').lower()
        if any(keyword.lower() in contact for keyword in keywords):
            matching_contacts.append({
                'nickname': relay.get('nickname', 'Unknown'),
                'fingerprint': relay.get('fingerprint', 'Unknown')[:8],
                'full_fingerprint': relay.get('fingerprint', 'Unknown'),
                'contact': contact
            })
    
    print(f"Found {len(matching_contacts)} relays matching keywords: {keywords}")
    for match in matching_contacts[:10]:  # Show first 10
        print(f"  - {match['nickname']} ({match['fingerprint']}...): {match['contact'][:80]}...")
    
    return matching_contacts

def find_operator_relays_by_fingerprints(bandwidth_data, fingerprints):
    """Find relays in bandwidth data by their fingerprints."""
    matching_relays = []
    
    for relay in bandwidth_data.get('relays', []):
        if relay.get('fingerprint') in fingerprints:
            matching_relays.append(relay)
    
    return matching_relays

def calculate_daily_bandwidth_totals(relays, time_period='6_months'):
    """Calculate daily bandwidth totals for an operator's relays."""
    if not relays:
        return []
    
    # Get write_history from all relays
    all_daily_totals = []
    
    # Find the first relay with data to get the timeline
    first_relay_with_data = None
    for relay in relays:
        if 'write_history' in relay and time_period in relay['write_history']:
            first_relay_with_data = relay
            break
    
    if not first_relay_with_data:
        print(f"No relay found with write_history data for {time_period}")
        return []
    
    first_history = first_relay_with_data['write_history'][time_period]
    if 'values' not in first_history:
        print(f"No values found in write_history for {time_period}")
        return []
    
    factor = first_history.get('factor', 1.0)
    values_length = len(first_history['values'])
    
    print(f"Factor: {factor}")
    print(f"Number of days: {values_length}")
    
    # For each day, sum bandwidth across all relays
    for day_idx in range(values_length):
        daily_total = 0.0
        valid_relays_for_day = 0
        
        for relay in relays:
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
            all_daily_totals.append(daily_total)
    
    return all_daily_totals

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

def analyze_operator_bandwidth(bandwidth_data, operator_name, operator_fingerprints):
    """Analyze bandwidth for a specific operator."""
    print(f"\n{'='*60}")
    print(f"ANALYZING OPERATOR: {operator_name}")
    print(f"{'='*60}")
    
    # Find relays for this operator in bandwidth data
    relays = find_operator_relays_by_fingerprints(bandwidth_data, operator_fingerprints)
    
    if not relays:
        print(f"No relays found in bandwidth data for {operator_name}")
        return
    
    print(f"Found {len(relays)} relays for {operator_name} in bandwidth data")
    
    # Show relay details
    for relay in relays:
        print(f"  - {relay.get('nickname', 'Unknown')} ({relay.get('fingerprint', 'Unknown')[:8]}...)")
    
    # Calculate for both 6 months and 5 years
    for time_period in ['6_months', '5_years']:
        print(f"\n--- {time_period.replace('_', ' ').title()} Analysis ---")
        
        daily_totals = calculate_daily_bandwidth_totals(relays, time_period)
        
        if not daily_totals:
            print(f"No data available for {time_period}")
            continue
        
        # Calculate statistics
        average_daily = statistics.mean(daily_totals)
        median_daily = statistics.median(daily_totals)
        max_daily = max(daily_totals)
        min_daily = min(daily_totals)
        
        print(f"Daily totals calculated: {len(daily_totals)} days")
        print(f"Average daily bandwidth: {format_bandwidth(average_daily)}")
        print(f"Median daily bandwidth: {format_bandwidth(median_daily)}")
        print(f"Max daily bandwidth: {format_bandwidth(max_daily)}")
        print(f"Min daily bandwidth: {format_bandwidth(min_daily)}")
        
        # Show recent values (last 7 days)
        print(f"\nLast 7 days:")
        for i, daily_total in enumerate(daily_totals[-7:]):
            print(f"  Day -{6-i}: {format_bandwidth(daily_total)}")
        
        # Convert to Gbps for comparison
        average_gbps = (average_daily * 8) / 1e9
        print(f"\nAverage bandwidth: {average_gbps:.2f} Gbps")

def main():
    """Main verification function."""
    print("Bandwidth Calculation Verification Script")
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
    
    # First, explore contact info to find the right keywords
    explore_keywords = [
        ['1aeo', 'aroi'],
        ['nothingtohide', 'nothing to hide'],
        ['quintex', 'alliance'],
        ['priv8', 'privacy'],
        ['tor', 'relay']
    ]
    
    for keywords in explore_keywords:
        contacts = explore_contact_info(details_data, keywords)
        if contacts:
            # If we found some matches, let's analyze the first operator
            operator_name = keywords[0]
            operator_fingerprints = [contact['full_fingerprint'] for contact in contacts]
            analyze_operator_bandwidth(bandwidth_data, operator_name, operator_fingerprints)
            break
    
    print(f"\n{'='*60}")
    print("VERIFICATION COMPLETE")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()