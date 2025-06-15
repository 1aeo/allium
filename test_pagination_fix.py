#!/usr/bin/env python3

import sys
import os
sys.path.append('allium')
from lib.coordinator import create_relay_set_with_coordinator

# Create a minimal test output directory
test_output_dir = './test_pagination_output'
os.makedirs(test_output_dir, exist_ok=True)

def test_pagination_fix():
    print("=== Testing Pagination Fix ===")
    print("1. Creating relay set with live data...")
    
    try:
        relay_set = create_relay_set_with_coordinator(
            test_output_dir, 
            'https://onionoo.torproject.org/details',
            'https://onionoo.torproject.org/uptime',
            True,  # use_bits
            False,  # progress (silent for test)
            0,     # start_time
            0,     # progress_step
            35,    # total_steps
            'all'  # enabled_apis
        )
        
        if not relay_set or not relay_set.json or 'aroi_leaderboards' not in relay_set.json:
            print("❌ Failed to create relay set with leaderboards")
            return False
            
        leaderboards = relay_set.json['aroi_leaderboards']['leaderboards']
        
        print("\n2. Checking leaderboard data sizes...")
        all_categories = [
            'bandwidth', 'consensus_weight', 'exit_authority', 'guard_authority',
            'exit_operators', 'guard_operators', 'most_diverse', 'platform_diversity',
            'non_eu_leaders', 'frontier_builders', 'network_veterans', 
            'reliability_masters', 'legacy_titans'
        ]
        
        pagination_status = {}
        for category in all_categories:
            data = leaderboards.get(category, [])
            count = len(data)
            
            # Determine which pagination sections should be available
            should_show_11_20 = count > 10
            should_show_21_25 = count > 20
            
            pagination_status[category] = {
                'count': count,
                'show_11_20': should_show_11_20,
                'show_21_25': should_show_21_25
            }
            
            print(f"  {category}: {count} entries - Pages: 1-10✓, 11-20{'✓' if should_show_11_20 else '✗'}, 21-25{'✓' if should_show_21_25 else '✗'}")
        
        # Generate the leaderboards page to test the template logic
        print("\n3. Generating leaderboards page with pagination fix...")
        
        from jinja2 import Environment, FileSystemLoader
        import json
        
        # Setup Jinja2 environment
        template_dir = os.path.join('allium', 'templates')
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template('aroi-leaderboards.html')
        
        # Get page context
        from allium.allium import get_page_context
        page_ctx = get_page_context('index', 'home')
        
        # Render the template
        output = template.render(
            relays=relay_set,
            page_ctx=page_ctx
        )
        
        # Write the output to test file
        output_file = os.path.join(test_output_dir, 'aroi-leaderboards.html')
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output)
            
        print(f"✅ Generated leaderboards page: {output_file}")
        
        # Validate specific cases from our test results
        print("\n4. Validating pagination logic...")
        
        # Check legacy titans specifically (the original issue)
        legacy_titans_count = pagination_status['legacy_titans']['count']
        print(f"  Legacy Titans: {legacy_titans_count} entries")
        
        if legacy_titans_count <= 20:
            print("  ✅ Legacy Titans 21-25 pagination should be hidden (✗)")
        else:
            print("  ⚠️  Legacy Titans has more than 20 entries, 21-25 should be shown")
            
        # Check some categories that should have full pagination
        full_pagination_categories = ['bandwidth', 'consensus_weight', 'most_diverse']
        for category in full_pagination_categories:
            count = pagination_status[category]['count']
            if count > 20:
                print(f"  ✅ {category}: {count} entries - should show all pagination")
            else:
                print(f"  ⚠️  {category}: {count} entries - pagination may be limited")
        
        # Check for any categories with limited entries
        limited_categories = [cat for cat, status in pagination_status.items() 
                            if status['count'] <= 20 and status['count'] > 10]
        if limited_categories:
            print(f"  📊 Categories with 11-20 entries (no 21-25 pagination): {limited_categories}")
            
        very_limited_categories = [cat for cat, status in pagination_status.items() 
                                 if status['count'] <= 10]
        if very_limited_categories:
            print(f"  📊 Categories with ≤10 entries (only 1-10 pagination): {very_limited_categories}")
        
        print("\n5. Testing specific HTML content...")
        
        # Check that the legacy titans 21-25 section is properly conditionally hidden
        if 'id="legacy_titans-21-25"' in output and legacy_titans_count <= 20:
            print("  ❌ Found legacy_titans-21-25 section in HTML but it should be hidden!")
            return False
        elif 'id="legacy_titans-21-25"' not in output and legacy_titans_count <= 20:
            print("  ✅ legacy_titans-21-25 section properly hidden from HTML")
        elif 'id="legacy_titans-21-25"' in output and legacy_titans_count > 20:
            print("  ✅ legacy_titans-21-25 section properly shown in HTML")
            
        # Check navigation links for legacy titans
        legacy_nav_21_25 = 'href="#legacy_titans-21-25"' in output
        if legacy_nav_21_25 and legacy_titans_count <= 20:
            print("  ❌ Found legacy_titans-21-25 navigation link but it should be hidden!")
            return False
        elif not legacy_nav_21_25 and legacy_titans_count <= 20:
            print("  ✅ legacy_titans-21-25 navigation link properly hidden")
            
        print("\n✅ All pagination fixes validated successfully!")
        print(f"📄 Generated HTML file: {output_file}")
        print("🎯 The empty Legacy Titans 21-25 pagination issue has been fixed!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_pagination_fix()
    sys.exit(0 if success else 1)