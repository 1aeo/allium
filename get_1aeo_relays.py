#!/usr/bin/env python3
"""
Script to fetch all 1aeo.com relays and their bandwidth data
"""

import urllib.request
import json
import time

def fetch_url(url: str, timeout: int = 30) -> dict:
    """Fetch URL and return JSON data"""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = response.read()
            return json.loads(data.decode('utf-8'))
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return {}

def get_all_1aeo_relays():
    """Get all relays with 1aeo.com contact"""
    print("Fetching all relays to find 1aeo.com relays...")
    
    # Get all relay details
    url = "https://onionoo.torproject.org/details"
    data = fetch_url(url, timeout=120)
    
    if 'relays' not in data:
        print("No relay data found")
        return []
    
    print(f"Total relays in network: {len(data['relays'])}")
    
    # Filter for 1aeo.com relays
    aeo_relays = []
    for relay in data['relays']:
        contact = relay.get('contact', '')
        if '1aeo.com' in contact.lower():
            aeo_relays.append(relay)
    
    print(f"Found {len(aeo_relays)} 1aeo.com relays")
    return aeo_relays

def get_bandwidth_data(fingerprint: str) -> dict:
    """Get bandwidth history for a relay"""
    url = f"https://onionoo.torproject.org/bandwidth?lookup={fingerprint}"
    data = fetch_url(url, timeout=30)
    
    if 'relays' in data and data['relays']:
        return data['relays'][0]
    return {}

def main():
    # Get all 1aeo relays
    relays = get_all_1aeo_relays()
    
    if not relays:
        print("No 1aeo.com relays found")
        return
    
    # Print summary
    print(f"\n=== 1aeo.com Relay Summary ===")
    print(f"Total relays: {len(relays)}")
    
    running_relays = [r for r in relays if r.get('running', False)]
    print(f"Running relays: {len(running_relays)}")
    
    total_observed = sum(r.get('observed_bandwidth', 0) for r in relays)
    total_rate = sum(r.get('bandwidth_rate', 0) for r in relays)
    
    print(f"Total observed bandwidth: {total_observed:,} bytes/sec ({total_observed/1024/1024:.1f} MB/s)")
    print(f"Total bandwidth rate: {total_rate:,} bytes/sec ({total_rate/1024/1024:.1f} MB/s)")
    
    # Country distribution
    countries = {}
    for relay in relays:
        country = relay.get('country', 'unknown')
        countries[country] = countries.get(country, 0) + 1
    
    print(f"\nCountry distribution:")
    for country, count in sorted(countries.items()):
        print(f"  {country.upper()}: {count} relays")
    
    # Flag distribution
    flags = {}
    for relay in relays:
        for flag in relay.get('flags', []):
            flags[flag] = flags.get(flag, 0) + 1
    
    print(f"\nFlag distribution:")
    for flag, count in sorted(flags.items()):
        print(f"  {flag}: {count} relays")
    
    # Top performers
    print(f"\nTop 10 performers by observed bandwidth:")
    sorted_relays = sorted(relays, key=lambda x: x.get('observed_bandwidth', 0), reverse=True)
    for i, relay in enumerate(sorted_relays[:10]):
        bw = relay.get('observed_bandwidth', 0)
        print(f"  {i+1:2d}. {relay.get('nickname', 'Unknown'):15s} {bw:>10,} bytes/sec ({bw/1024/1024:6.1f} MB/s)")
    
    # Save detailed data
    output = {
        'analysis_date': time.strftime('%Y-%m-%d %H:%M:%S'),
        'summary': {
            'total_relays': len(relays),
            'running_relays': len(running_relays),
            'total_observed_bandwidth': total_observed,
            'total_bandwidth_rate': total_rate,
            'countries': countries,
            'flags': flags
        },
        'relays': relays
    }
    
    with open('1aeo_relays_data.json', 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\nDetailed data saved to 1aeo_relays_data.json")

if __name__ == "__main__":
    main()