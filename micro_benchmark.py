#!/usr/bin/env python3
"""Micro-benchmark for Jinja2 template operations."""

import time
from jinja2 import Environment

def benchmark_jinja2_operations():
    """Benchmark individual Jinja2 operations that are bottlenecks"""
    print("🔬 JINJA2 MICRO-BENCHMARK")
    print("="*50)
    print("Cross-referencing with commit b2894f0 profiling findings")
    print("="*50)
    
    # Set up Jinja2 environment
    env = Environment()
    
    # Test data representing a typical relay
    test_relay = {
        'fingerprint': 'ABCD1234567890ABCD1234567890ABCD12345678',
        'nickname': 'TestRelayWithALongerNameThanUsual',
        'effective_family': ['ABCD1234567890ABCD1234567890ABCD12345678', 'EFGH1234567890EFGH1234567890EFGH12345678'],
        'contact': 'someone@example.com <tor-relay@example.com>',
        'contact_md5': 'abcd1234567890abcd1234567890abcd12',
        'aroi_domain': 'example.com',
        'running': True,
        'observed_bandwidth': 10485760,  # 10MB
        'as': '1234',
        'as_name': 'Example ISP Network Provider Inc.',
        'country': 'US',
        'country_name': 'United States',
        'platform': 'Tor 0.4.7.10 on Linux',
        'flags': ['Running', 'V2Dir', 'Guard', 'HSDir'],
        'first_seen': '2023-05-15 14:30:25',
        'or_addresses': ['192.168.1.100:9001', '[2001:db8::1]:9001']
    }
    
    iterations = 5000  # Test with 5000 iterations for statistical significance
    print(f"📊 Testing {iterations} iterations of each operation...\n")
    
    # Test 1: String escaping (very common operation)
    print("🧪 Test 1: String Escaping")
    template_escape = env.from_string("{{ relay['nickname']|escape }}")
    
    start = time.time()
    for _ in range(iterations):
        template_escape.render(relay=test_relay)
    escape_time = time.time() - start
    
    print(f"   Time: {escape_time:.3f}s ({escape_time/iterations*1000:.3f}ms per operation)")
    
    # Test 2: String truncation (common in nickname display)
    print("\n🧪 Test 2: String Truncation")
    template_truncate = env.from_string("{{ relay['nickname']|truncate(20) }}")
    
    start = time.time()
    for _ in range(iterations):
        template_truncate.render(relay=test_relay)
    truncate_time = time.time() - start
    
    print(f"   Time: {truncate_time:.3f}s ({truncate_time/iterations*1000:.3f}ms per operation)")
    
    # Test 3: Complex conditional with length check (family link logic)
    print("\n🧪 Test 3: Complex Conditional")
    template_conditional = env.from_string("""{% if relay['effective_family'] is defined and relay['effective_family']|length > 1 -%}
 (<a href="../../family/{{ relay['fingerprint']|escape }}/">{{ relay['effective_family']|length }}</a>)
{% endif -%}""")
    
    start = time.time()
    for _ in range(iterations):
        template_conditional.render(relay=test_relay)
    conditional_time = time.time() - start
    
    print(f"   Time: {conditional_time:.3f}s ({conditional_time/iterations*1000:.3f}ms per operation)")
    
    # Test 4: Combined operation (full nickname cell like in relay-list.html)
    print("\n🧪 Test 4: Combined Complex Operation")
    template_combined = env.from_string("""<a href="../../relay/{{ relay['fingerprint']|escape }}/">{{ relay['nickname']|truncate(20) }}</a>
{% if relay['effective_family'] is defined and relay['effective_family']|length > 1 -%}
 (<a href="../../family/{{ relay['fingerprint']|escape }}/">{{ relay['effective_family']|length }}</a>)
{% endif -%}""")
    
    start = time.time()
    for _ in range(iterations):
        template_combined.render(relay=test_relay)
    combined_time = time.time() - start
    
    print(f"   Time: {combined_time:.3f}s ({combined_time/iterations*1000:.3f}ms per operation)")
    
    # Test 5: Pre-computed equivalent (optimization #2)
    print("\n🧪 Test 5: Pre-computed Value")
    
    # Pre-compute the HTML
    nickname_trunc = test_relay['nickname'][:20] + ('...' if len(test_relay['nickname']) > 20 else '')
    relay_link = f'<a href="../../relay/{test_relay["fingerprint"]}/">{nickname_trunc}</a>'
    family_link = f' (<a href="../../family/{test_relay["fingerprint"]}/">{len(test_relay["effective_family"])}</a>)'
    precomputed_value = relay_link + family_link
    
    test_relay['precomputed_nickname_cell'] = precomputed_value
    
    template_precomputed = env.from_string("{{ relay['precomputed_nickname_cell'] }}")
    
    start = time.time()
    for _ in range(iterations):
        template_precomputed.render(relay=test_relay)
    precomputed_time = time.time() - start
    
    print(f"   Time: {precomputed_time:.3f}s ({precomputed_time/iterations*1000:.3f}ms per operation)")
    
    # Test 6: Large template loop simulation
    print("\n🧪 Test 6: Large Template Loop Simulation")
    
    # Create array of 50 relays (typical family size)
    relay_array = [test_relay.copy() for _ in range(50)]
    for i, relay in enumerate(relay_array):
        relay['nickname'] = f'TestRelay{i}'
        relay['fingerprint'] = f'ABCD{i:016X}{test_relay["fingerprint"][20:]}'
    
    # Template that processes all relays (baseline)
    template_loop_baseline = env.from_string("""{% for relay in relays -%}
<tr>
    <td><a href="../../relay/{{ relay['fingerprint']|escape }}/">{{ relay['nickname']|truncate(20) }}</a>
    {% if relay['effective_family'] is defined and relay['effective_family']|length > 1 -%}
     (<a href="../../family/{{ relay['fingerprint']|escape }}/">{{ relay['effective_family']|length }}</a>)
    {% endif -%}</td>
</tr>
{% endfor -%}""")
    
    start = time.time()
    for _ in range(100):  # 100 iterations of 50-relay processing
        template_loop_baseline.render(relays=relay_array)
    loop_baseline_time = time.time() - start
    
    print(f"   Baseline Loop: {loop_baseline_time:.3f}s (100 iterations × 50 relays)")
    
    # Template that uses pre-computed values (optimized)
    for relay in relay_array:
        nickname_trunc = relay['nickname'][:20] + ('...' if len(relay['nickname']) > 20 else '')
        relay_link = f'<a href="../../relay/{relay["fingerprint"]}/">{nickname_trunc}</a>'
        family_link = f' (<a href="../../family/{relay["fingerprint"]}/">{len(relay["effective_family"])}</a>)'
        relay['precomputed_nickname_cell'] = relay_link + family_link
    
    template_loop_optimized = env.from_string("""{% for relay in relays -%}
<tr>
    <td>{{ relay['precomputed_nickname_cell'] }}</td>
</tr>
{% endfor -%}""")
    
    start = time.time()
    for _ in range(100):  # 100 iterations of 50-relay processing
        template_loop_optimized.render(relays=relay_array)
    loop_optimized_time = time.time() - start
    
    print(f"   Optimized Loop: {loop_optimized_time:.3f}s (100 iterations × 50 relays)")
    
    # Results analysis
    print("\n" + "="*60)
    print("📋 BENCHMARK RESULTS ANALYSIS")
    print("="*60)
    
    print(f"📊 Individual Operation Performance:")
    print(f"   String Escape:       {escape_time:.3f}s")
    print(f"   String Truncate:     {truncate_time:.3f}s")
    print(f"   Complex Conditional: {conditional_time:.3f}s")
    print(f"   Combined Operation:  {combined_time:.3f}s")
    print(f"   Pre-computed:        {precomputed_time:.3f}s")
    
    print(f"\n🚀 Performance Improvement Ratios:")
    print(f"   Combined vs Pre-computed: {combined_time/precomputed_time:.1f}x faster with optimization")
    print(f"   Loop Baseline vs Optimized: {loop_baseline_time/loop_optimized_time:.1f}x faster with optimization")
    
    print(f"\n💡 Template Loop Analysis:")
    print(f"   Baseline processing:  {loop_baseline_time:.3f}s")
    print(f"   Optimized processing: {loop_optimized_time:.3f}s")
    loop_improvement = (loop_baseline_time - loop_optimized_time) / loop_baseline_time * 100
    print(f"   Improvement: {loop_improvement:.1f}%")
    
    print(f"\n🎯 OPTIMIZATION ASSESSMENT:")
    if combined_time/precomputed_time > 2:
        print("   ✅ OPTIMIZATION #2 (HTML Pre-computation) IS HIGHLY BENEFICIAL")
        print(f"   💪 {combined_time/precomputed_time:.1f}x performance gain expected")
    elif combined_time/precomputed_time > 1.5:
        print("   ✅ OPTIMIZATION #2 (HTML Pre-computation) IS BENEFICIAL")
        print(f"   📈 {combined_time/precomputed_time:.1f}x performance gain expected")
    else:
        print("   ❌ OPTIMIZATION #2 (HTML Pre-computation) IS NOT BENEFICIAL")
        print(f"   📉 Only {combined_time/precomputed_time:.1f}x performance difference")
    
    if loop_improvement > 20:
        print("   ✅ TEMPLATE LOOP OPTIMIZATION IS HIGHLY BENEFICIAL")
        print(f"   🔥 {loop_improvement:.1f}% improvement in template processing")
    elif loop_improvement > 10:
        print("   ✅ TEMPLATE LOOP OPTIMIZATION IS BENEFICIAL")
        print(f"   📊 {loop_improvement:.1f}% improvement in template processing")
    else:
        print("   ❌ TEMPLATE LOOP OPTIMIZATION IS NOT BENEFICIAL")
        print(f"   ⚠️  Only {loop_improvement:.1f}% improvement in template processing")
    
    # Cross-reference with profiling data
    print(f"\n🔍 Cross-reference with commit b2894f0 findings:")
    print("   - Template rendering was identified as 98.7% of family page time")
    print("   - 5,326 family pages taking 97.33s (18.3ms per page)")
    
    estimated_per_page_improvement = (combined_time - precomputed_time) * 50 / iterations * 1000  # 50 relays per page average
    print(f"   📊 Estimated per-page improvement: {estimated_per_page_improvement:.2f}ms")
    
    if estimated_per_page_improvement > 2:
        total_estimated_savings = estimated_per_page_improvement * 5326 / 1000
        print(f"   🎯 Estimated total savings for 5,326 pages: {total_estimated_savings:.1f}s")
        if total_estimated_savings > 10:
            print("   ✅ OPTIMIZATION WILL PROVIDE SIGNIFICANT REAL-WORLD BENEFIT")
        else:
            print("   ⚠️  OPTIMIZATION WILL PROVIDE MODEST REAL-WORLD BENEFIT")
    else:
        print("   ❌ OPTIMIZATION UNLIKELY TO PROVIDE SIGNIFICANT REAL-WORLD BENEFIT")

if __name__ == "__main__":
    benchmark_jinja2_operations() 