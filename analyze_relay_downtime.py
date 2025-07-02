#!/usr/bin/env python3
"""
Script to analyze relay downtime data from onionoo API directly
and compare with allium.py results for debugging.
"""

import json
import urllib.request
import sys
from datetime import datetime, timedelta

def fetch_onionoo_data():
    """Fetch relay data from onionoo API"""
    print("🔄 Fetching data from onionoo API...")
    url = "https://onionoo.torproject.org/details"
    
    try:
        response = urllib.request.urlopen(url, timeout=30)
        data = json.loads(response.read().decode('utf-8'))
        print(f"✅ Successfully fetched {len(data.get('relays', []))} relays")
        return data
    except Exception as e:
        print(f"❌ Error fetching onionoo data: {e}")
        return None

def parse_timestamp(timestamp_str):
    """Parse onionoo timestamp string"""
    if not timestamp_str:
        return None
    try:
        return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None

def analyze_downtime(data):
    """Analyze relay downtime patterns"""
    if not data or 'relays' not in data:
        print("❌ No relay data to analyze")
        return
    
    relays = data['relays']
    now = datetime.utcnow()
    
    # Time thresholds
    seven_days_ago = now - timedelta(days=7)
    one_year_ago = now - timedelta(days=365)
    
    print(f"\n📊 RELAY DOWNTIME ANALYSIS")
    print(f"Analysis time: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"Total relays in onionoo response: {len(relays)}")
    print("=" * 60)
    
    # Counters
    running_relays = 0
    offline_relays = 0
    offline_7_days = 0
    offline_1_year = 0
    offline_unknown_time = 0
    
    # Detailed tracking for debugging
    recent_offline = []  # Relays offline < 7 days
    long_offline_7d = []  # Relays offline > 7 days
    long_offline_1y = []  # Relays offline > 1 year
    
    for relay in relays:
        running = relay.get('running', False)
        last_seen = relay.get('last_seen')
        nickname = relay.get('nickname', 'Unknown')
        fingerprint = relay.get('fingerprint', 'Unknown')[:8]
        
        if running:
            running_relays += 1
        else:
            offline_relays += 1
            
            if last_seen:
                last_seen_dt = parse_timestamp(last_seen)
                if last_seen_dt:
                    downtime_duration = now - last_seen_dt
                    days_offline = downtime_duration.days
                    
                    relay_info = {
                        'nickname': nickname,
                        'fingerprint': fingerprint,
                        'last_seen': last_seen,
                        'days_offline': days_offline
                    }
                    
                    if last_seen_dt < one_year_ago:
                        offline_1_year += 1
                        long_offline_1y.append(relay_info)
                    elif last_seen_dt < seven_days_ago:
                        offline_7_days += 1
                        long_offline_7d.append(relay_info)
                    else:
                        recent_offline.append(relay_info)
                else:
                    offline_unknown_time += 1
            else:
                offline_unknown_time += 1
    
    # Print summary results
    print(f"🟢 Running relays: {running_relays}")
    print(f"🔴 Offline relays: {offline_relays}")
    print(f"📊 Offline breakdown:")
    print(f"   • Recent (< 7 days): {len(recent_offline)}")
    print(f"   • Long-term (> 7 days): {offline_7_days}")
    print(f"   • Very long-term (> 1 year): {offline_1_year}")
    print(f"   • Unknown downtime: {offline_unknown_time}")
    
    print(f"\n🎯 ANSWER TO YOUR QUESTION:")
    print(f"Relays with downtime > 7 days: {offline_7_days}")
    print(f"Relays with downtime > 1 year: {offline_1_year}")
    
    # Show some examples for debugging
    if long_offline_7d:
        print(f"\n📋 Sample relays offline > 7 days (showing first 5):")
        for relay in long_offline_7d[:5]:
            print(f"   {relay['nickname']} ({relay['fingerprint']}) - last seen {relay['last_seen']} ({relay['days_offline']} days ago)")
    
    if long_offline_1y:
        print(f"\n📋 Sample relays offline > 1 year (showing first 5):")
        for relay in long_offline_1y[:5]:
            print(f"   {relay['nickname']} ({relay['fingerprint']}) - last seen {relay['last_seen']} ({relay['days_offline']} days ago)")
    
    # Return counts for comparison with allium
    return {
        'total_relays': len(relays),
        'running_relays': running_relays,
        'offline_relays': offline_relays,
        'offline_7_days': offline_7_days,
        'offline_1_year': offline_1_year,
        'offline_unknown': offline_unknown_time
    }

def main():
    """Main function"""
    print("🔍 ONIONOO API RELAY DOWNTIME ANALYZER")
    print("=" * 50)
    
    # Fetch and analyze data
    data = fetch_onionoo_data()
    if data:
        results = analyze_downtime(data)
        
        if results:
            print(f"\n💾 Results for comparison with allium.py:")
            print(f"ONIONOO_TOTAL_RELAYS={results['total_relays']}")
            print(f"ONIONOO_OFFLINE_7_DAYS={results['offline_7_days']}")
            print(f"ONIONOO_OFFLINE_1_YEAR={results['offline_1_year']}")
            
            print(f"\n📝 Note: The onionoo API appears to include relays that have been")
            print(f"offline for extended periods. This suggests the API does NOT")
            print(f"automatically filter out relays with downtime > 7 days.")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main() 