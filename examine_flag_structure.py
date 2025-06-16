#!/usr/bin/env python3
"""
Simple script to examine Onionoo flag data structure
"""

import json
import urllib.request

def fetch_sample_data():
    """Fetch small sample of uptime data"""
    url = "https://onionoo.torproject.org/uptime?limit=3"
    
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data
    except Exception as e:
        print(f"Error: {e}")
        return None

def examine_structure():
    """Examine the structure of flag uptime data"""
    data = fetch_sample_data()
    if not data:
        return
    
    print("=== ONIONOO FLAG DATA STRUCTURE ANALYSIS ===\n")
    
    for i, relay in enumerate(data.get('relays', [])[:2]):
        print(f"RELAY #{i+1}: {relay.get('fingerprint', 'Unknown')[:12]}...")
        
        # General uptime data
        if 'uptime' in relay:
            print(f"  📊 General uptime periods: {list(relay['uptime'].keys())}")
            for period, period_data in relay['uptime'].items():
                if 'values' in period_data:
                    values = period_data['values']
                    non_null = [v for v in values if v is not None]
                    print(f"    {period}: {len(non_null)}/{len(values)} non-null values")
        
        # Flag-specific uptime data
        if 'flags' in relay:
            print(f"  🏷️ Available flags: {list(relay['flags'].keys())}")
            
            # Examine a few key flags in detail
            for flag_name in ['Running', 'Guard', 'Fast'][:2]:
                if flag_name in relay['flags']:
                    flag_data = relay['flags'][flag_name]
                    print(f"\n    {flag_name} flag details:")
                    print(f"      Available periods: {list(flag_data.keys())}")
                    
                    for period in ['6_months', '5_years']:
                        if period in flag_data:
                            period_data = flag_data[period]
                            if 'values' in period_data:
                                values = period_data['values']
                                non_null = [v for v in values if v is not None]
                                if non_null:
                                    avg = sum(non_null) / len(non_null) / 999 * 100
                                    print(f"        {period}: {len(non_null)}/{len(values)} values, avg {avg:.1f}%")
                                    print(f"          Sample values: {values[:5]}...")
                                else:
                                    print(f"        {period}: No valid data")
        print("\n" + "-"*60 + "\n")

if __name__ == "__main__":
    examine_structure()