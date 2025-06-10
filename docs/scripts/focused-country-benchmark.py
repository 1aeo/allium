#!/usr/bin/env python3
"""
Focused benchmark for rare country calculation optimization
Measures only the specific O(n²) bottleneck that was fixed
"""

import time
import sys
import os

def benchmark_country_processing():
    """Benchmark just the country processing part"""
    print("🎯 Focused Country Processing Benchmark")
    print("=" * 55)
    
    # Add paths
    sys.path.insert(0, 'allium')
    sys.path.insert(0, '.')
    
    from lib.relays import Relays
    from lib.country_utils import get_rare_countries_weighted_with_existing_data
    
    # Load data once
    print("📦 Loading relay data...")
    relays = Relays(
        output_dir="www_benchmark",
        onionoo_url="https://onionoo.torproject.org/details", 
        use_bits=False,
        progress=False
    )
    
    all_relays = relays.json.get('relays', [])
    contacts = relays.json.get('sorted', {}).get('contact', {})
    country_data = relays.json.get('sorted', {}).get('country', {})
    
    print(f"📏 Data loaded: {len(all_relays):,} relays, {len(contacts):,} operators")
    print()
    
    # Benchmark O(n²) approach (old way)
    print("🔴 BEFORE: O(n²) approach (calling for each operator)")
    start_time = time.time()
    
    call_count = 0
    for contact_hash, contact_data in contacts.items():
        # This is what was happening before - calling for EACH operator
        all_rare_countries = get_rare_countries_weighted_with_existing_data(country_data, len(all_relays))
        valid_rare_countries = {country for country in all_rare_countries if len(country) == 2 and country.isalpha()}
        call_count += 1
        
        # Just process first 100 operators for benchmarking (otherwise it takes too long)
        if call_count >= 100:
            break
    
    before_time = time.time() - start_time
    print(f"✅ Processed {call_count} operators in {before_time:.3f} seconds")
    print(f"📊 Average per operator: {(before_time/call_count)*1000:.2f}ms")
    print()
    
    # Benchmark O(n) approach (new way)
    print("🟢 AFTER: O(n) approach (calling once and reusing)")
    start_time = time.time()
    
    # Calculate once and reuse
    all_rare_countries = get_rare_countries_weighted_with_existing_data(country_data, len(all_relays))
    valid_rare_countries = {country for country in all_rare_countries if len(country) == 2 and country.isalpha()}
    
    # Process same number of operators using cached result
    processed = 0
    for contact_hash, contact_data in contacts.items():
        # Just use the pre-calculated result
        _ = valid_rare_countries  # Simulate using the cached data
        processed += 1
        
        if processed >= 100:
            break
    
    after_time = time.time() - start_time
    print(f"✅ Processed {processed} operators in {after_time:.3f} seconds")
    print(f"📊 Average per operator: {(after_time/processed)*1000:.2f}ms")
    print()
    
    # Calculate improvement
    if after_time > 0:
        improvement = before_time / after_time
        time_saved = before_time - after_time
        print("🚀 COUNTRY PROCESSING IMPROVEMENT:")
        print(f"   Speed: {improvement:.1f}x faster")
        print(f"   Time saved: {time_saved:.3f}s for {call_count} operators")
        
        # Extrapolate to all operators
        total_operators = len(contacts)
        extrapolated_savings = (time_saved / call_count) * total_operators
        print(f"   Extrapolated for all {total_operators:,} operators: {extrapolated_savings:.2f}s saved")
    
    return {
        'before_time': before_time,
        'after_time': after_time,
        'operators_tested': call_count,
        'total_operators': len(contacts)
    }

if __name__ == "__main__":
    print("Starting Focused Country Processing Benchmark...")
    print(f"Python version: {sys.version}")
    print(f"PID: {os.getpid()}")
    print()
    
    results = benchmark_country_processing()
    
    print("\n" + "=" * 55)
    print("📊 FOCUSED BENCHMARK SUMMARY:")
    print(f"Country processing improvement: {results['before_time']/results['after_time']:.1f}x faster")
    print(f"Tested on {results['operators_tested']} operators")
    print(f"Total operators in network: {results['total_operators']:,}")
    
    print("\n💡 This shows the specific O(n²) bottleneck improvement!") 