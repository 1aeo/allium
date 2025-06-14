#!/usr/bin/env python3

import json
import sys
sys.path.append('./lib')
from coordinator import create_relay_set_with_coordinator

print("Debug: Checking uptime data processing...")

# Create relay set to debug uptime data
relay_set = create_relay_set_with_coordinator('./www', 'https://onionoo.torproject.org/details', 'https://onionoo.torproject.org/uptime', False, False, None, 0, 20, 'all')

if relay_set and hasattr(relay_set, 'uptime_data') and relay_set.uptime_data:
    print(f'Uptime data available: {len(relay_set.uptime_data.get("relays", []))} relays')
    
    # Check first few entries
    for i, relay in enumerate(relay_set.uptime_data.get('relays', [])[:5]):
        print(f'Relay {i+1}:')
        print(f'  Fingerprint: {relay.get("fingerprint", "N/A")}')
        print(f'  Uptime data: {"uptime" in relay}')
        if 'uptime' in relay:
            print(f'  Periods: {list(relay["uptime"].keys())}')
            if '6_months' in relay['uptime']:
                period_data = relay['uptime']['6_months']
                print(f'  6-month data: {"values" in period_data}')
                if 'values' in period_data:
                    values = period_data['values']
                    non_null_values = [v for v in values if v is not None]
                    print(f'  6-month values: {len(values)} total, {len(non_null_values)} non-null')
                    if non_null_values:
                        avg = sum(non_null_values) / len(non_null_values) / 999 * 100
                        print(f'  6-month avg uptime: {avg:.1f}%')
                    else:
                        print(f'  6-month values (sample): {values[:10]}')
        print()
else:
    print('No uptime data available')
    if relay_set:
        print(f'Has uptime_data attr: {hasattr(relay_set, "uptime_data")}')
        if hasattr(relay_set, 'uptime_data'):
            print(f'uptime_data value: {relay_set.uptime_data}')

# Check AROI leaderboard calculation
if relay_set and hasattr(relay_set, 'json') and relay_set.json.get('aroi_leaderboards'):
    leaderboards = relay_set.json['aroi_leaderboards']['leaderboards']
    reliability_masters = leaderboards.get('reliability_masters', [])
    
    print(f"\nReliability masters leaderboard: {len(reliability_masters)} entries")
    for i, entry in enumerate(reliability_masters[:3]):
        print(f"Entry {i+1}: {entry.get('operator_key', 'N/A')} - Score: {entry.get('reliability_score', 'N/A')}") 