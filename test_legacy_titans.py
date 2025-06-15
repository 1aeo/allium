#!/usr/bin/env python3

import sys
sys.path.append('allium')
from lib.coordinator import create_relay_set_with_coordinator
import json

# Create a minimal relay set to test
try:
    relay_set = create_relay_set_with_coordinator(
        './test_output', 
        'https://onionoo.torproject.org/details',
        'https://onionoo.torproject.org/uptime',
        True,  # use_bits
        True,  # progress
        0,     # start_time
        0,     # progress_step
        35,    # total_steps
        'all'  # enabled_apis
    )
    
    if relay_set and relay_set.json and 'aroi_leaderboards' in relay_set.json:
        leaderboards = relay_set.json['aroi_leaderboards']['leaderboards']
        
        print('LEGACY TITANS DATA:')
        legacy_titans = leaderboards.get('legacy_titans', [])
        print(f'Total legacy titans entries: {len(legacy_titans)}')
        
        if len(legacy_titans) > 0:
            print(f'First entry: {legacy_titans[0]["display_name"] if isinstance(legacy_titans[0], dict) else legacy_titans[0][0]}')
            print(f'Last entry: {legacy_titans[-1]["display_name"] if isinstance(legacy_titans[-1], dict) else legacy_titans[-1][0]}')
        
        if len(legacy_titans) > 20:
            print(f'Entry at position 21: {legacy_titans[20]["display_name"] if isinstance(legacy_titans[20], dict) else legacy_titans[20][0]}')
        else:
            print('No entry at position 21')
            
        # Check if we have uptime data available
        print(f'Has uptime data: {hasattr(relay_set, "uptime_data") and relay_set.uptime_data is not None}')
        
        if hasattr(relay_set, 'uptime_data') and relay_set.uptime_data:
            uptime_relays = relay_set.uptime_data.get('relays', [])
            print(f'Uptime data relay count: {len(uptime_relays)}')
            
            # Check if any relay has 5_years data
            has_5y_data = False
            for relay in uptime_relays[:10]:  # Check first 10
                if relay.get('uptime', {}).get('5_years'):
                    has_5y_data = True
                    break
            print(f'Has 5-year uptime data: {has_5y_data}')
        
        # Check each leaderboard size
        print('\nLEADERBOARD SIZES:')
        for category, data in leaderboards.items():
            print(f'{category}: {len(data)} entries')
        
    else:
        print('No AROI leaderboards data available')
        
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()