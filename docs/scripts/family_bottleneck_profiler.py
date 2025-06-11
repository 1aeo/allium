#!/usr/bin/env python3
"""
Focused profiler for family page template rendering bottlenecks.
Isolates the specific operations causing the 97.33s template render time.
"""

import cProfile
import pstats
import io
import time
import os
import sys
import tempfile
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, '.')

def profile_single_family_template():
    """Profile a single family template rendering in detail"""
    print("🎯 FAMILY PAGE TEMPLATE BOTTLENECK PROFILER")
    print("="*80)
    print("Focusing on the 97.33s template render time bottleneck")
    print("Cross-referencing with commit b2894f0 findings")
    print("="*80 + "\n")
    
    # Import at runtime to avoid issues
    try:
        from allium.lib.relays import Relays
        from jinja2 import Environment, FileSystemLoader
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return
    
    # Create a temporary output directory
    temp_dir = tempfile.mkdtemp(prefix="family_profile_")
    print(f"📁 Using temporary directory: {temp_dir}")
    
    try:
        # Initialize minimal relay set
        print("🔧 Initializing relay data...")
        relay_set = Relays(temp_dir, "https://onionoo.torproject.org/details", progress=False)
        relay_set._fetch_onionoo_details()
        relay_set._trim_platform()
        relay_set._fix_missing_observed_bandwidth()
        relay_set._process_aroi_contacts()
        relay_set._add_hashed_contact()
        relay_set._preprocess_template_data()
        relay_set._categorize()
        
        # Get family data
        family_keys = list(relay_set.json["sorted"]["family"].keys())
        print(f"📊 Found {len(family_keys)} family groups")
        
        if not family_keys:
            print("❌ No family data found")
            return
        
        # Profile different family sizes
        family_sizes = []
        for key in family_keys[:10]:  # Sample first 10
            family_size = len(relay_set.json["sorted"]["family"][key]["relays"])
            family_sizes.append((key, family_size))
        
        family_sizes.sort(key=lambda x: x[1], reverse=True)
        print(f"🔍 Family sizes range from {family_sizes[-1][1]} to {family_sizes[0][1]} relays")
        
        # Profile small, medium, and large families
        test_families = [
            ("small", family_sizes[-1][0]),   # Smallest family
            ("medium", family_sizes[len(family_sizes)//2][0]),  # Medium family
            ("large", family_sizes[0][0])     # Largest family
        ]
        
        results = {}
        
        for size_name, family_key in test_families:
            print(f"\n🎯 Profiling {size_name} family: {family_key}")
            family_data = relay_set.json["sorted"]["family"][family_key]
            relay_count = len(family_data["relays"])
            print(f"   Relay count: {relay_count}")
            
            # Get the relays for this family
            family_relays = []
            for relay_id in family_data["relays"]:
                family_relays.append(relay_set.json["relays"][relay_id])
            
            # Profile the template rendering process
            profiler = cProfile.Profile()
            
            # Setup Jinja2 environment
            template_env = Environment(loader=FileSystemLoader('allium/templates'))
            template = template_env.get_template('family.html')
            
            # Prepare context (mimicking write_pages_by_key method)
            consensus_weight_fraction = family_data["consensus_weight_fraction"]
            
            # Create page context like the real code does
            page_ctx = {
                'path_prefix': '../../',
                'breadcrumb_type': 'family_detail', 
                'breadcrumb_data': {'family_hash': family_key}
            }
            
            # Calculate network position using intelligence engine
            from allium.lib.intelligence_engine import IntelligenceEngine
            intelligence = IntelligenceEngine({})  # Empty intelligence engine just for utility method
            total_relays = len(family_relays)
            network_position = intelligence._calculate_network_position(
                family_data["guard_count"], family_data["middle_count"], family_data["exit_count"], total_relays
            )
            
            context = {
                'relays': relay_set,
                'bandwidth': relay_set._format_bandwidth_with_unit(family_data["bandwidth"], relay_set._determine_unit(family_data["bandwidth"])),
                'bandwidth_unit': relay_set._determine_unit(family_data["bandwidth"]),
                'consensus_weight_fraction': consensus_weight_fraction,
                'guard_consensus_weight_fraction': family_data["guard_consensus_weight_fraction"],
                'middle_consensus_weight_fraction': family_data["middle_consensus_weight_fraction"],
                'exit_consensus_weight_fraction': family_data["exit_consensus_weight_fraction"],
                'exit_count': family_data["exit_count"],
                'guard_count': family_data["guard_count"],
                'middle_count': family_data["middle_count"],
                'key': 'family',
                'value': family_key,
                'is_index': False,
                'page_ctx': page_ctx,
                'network_position': network_position,  # Add network position  
                'sp_countries': [],
                # Pre-computed optimizations
                'consensus_weight_percentage': f"{consensus_weight_fraction * 100:.2f}%",
                'guard_consensus_weight_percentage': f"{family_data['guard_consensus_weight_fraction'] * 100:.2f}%",
                'middle_consensus_weight_percentage': f"{family_data['middle_consensus_weight_fraction'] * 100:.2f}%",
                'exit_consensus_weight_percentage': f"{family_data['exit_consensus_weight_fraction'] * 100:.2f}%",
                'guard_relay_text': "guard relay" if family_data["guard_count"] == 1 else "guard relays",
                'middle_relay_text': "middle relay" if family_data["middle_count"] == 1 else "middle relays",
                'exit_relay_text': "exit relay" if family_data["exit_count"] == 1 else "exit relays",
                'has_guard': family_data["guard_count"] > 0,
                'has_middle': family_data["middle_count"] > 0,
                'has_exit': family_data["exit_count"] > 0,
                'has_typed_relays': family_data["guard_count"] > 0 or family_data["middle_count"] > 0 or family_data["exit_count"] > 0
            }
            
            # Update the relay_subset for the template
            relay_set.json["relay_subset"] = family_relays
            
            print(f"   🚀 Starting profiled template rendering...")
            profiler.enable()
            start_time = time.time()
            
            rendered_html = template.render(**context)
            
            render_time = time.time() - start_time
            profiler.disable()
            
            print(f"   ✅ Rendered in {render_time:.4f}s")
            print(f"   📏 HTML size: {len(rendered_html):,} bytes")
            print(f"   ⚡ Time per relay: {render_time/relay_count*1000:.3f}ms")
            
            # Analyze profiling results
            s = io.StringIO()
            ps = pstats.Stats(profiler, stream=s)
            ps.sort_stats('cumulative')
            ps.print_stats(20)
            
            profile_output = s.getvalue()
            
            # Save individual profile
            with open(f"family_profile_{size_name}_{relay_count}_relays.txt", "w") as f:
                f.write(f"FAMILY PAGE PROFILING - {size_name.upper()} ({relay_count} relays)\n")
                f.write("="*60 + "\n")
                f.write(f"Family key: {family_key}\n")
                f.write(f"Relay count: {relay_count}\n")
                f.write(f"Render time: {render_time:.4f}s\n")
                f.write(f"Time per relay: {render_time/relay_count*1000:.3f}ms\n")
                f.write(f"HTML size: {len(rendered_html):,} bytes\n")
                f.write("="*60 + "\n")
                f.write(profile_output)
            
            results[size_name] = {
                'family_key': family_key,
                'relay_count': relay_count,
                'render_time': render_time,
                'html_size': len(rendered_html),
                'time_per_relay': render_time/relay_count,
                'profile_output': profile_output
            }
        
        # Analyze scaling characteristics
        analyze_scaling_bottlenecks(results)
        
    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir)

def analyze_scaling_bottlenecks(results):
    """Analyze how rendering time scales with family size"""
    print("\n" + "="*80)
    print("📈 SCALING ANALYSIS")
    print("="*80)
    
    print(f"{'Size':<8} {'Relays':<8} {'Time':<10} {'Per Relay':<12} {'HTML Size':<12}")
    print("-" * 60)
    
    for size_name, data in results.items():
        print(f"{size_name:<8} {data['relay_count']:<8} {data['render_time']:<10.4f} {data['time_per_relay']*1000:<12.3f} {data['html_size']:<12,d}")
    
    # Calculate scaling efficiency
    if len(results) >= 2:
        small_data = results.get('small', {})
        large_data = results.get('large', {})
        
        if small_data and large_data:
            relay_ratio = large_data['relay_count'] / small_data['relay_count']
            time_ratio = large_data['render_time'] / small_data['render_time']
            
            print(f"\n📊 Scaling Analysis:")
            print(f"  Relay count ratio (large/small): {relay_ratio:.1f}x")
            print(f"  Render time ratio (large/small): {time_ratio:.1f}x")
            print(f"  Scaling efficiency: {relay_ratio/time_ratio:.2f} (1.0 = linear scaling)")
            
            if time_ratio > relay_ratio * 1.2:
                print("  ⚠️  Worse than linear scaling - likely O(n²) or worse complexity")
            elif time_ratio < relay_ratio * 0.8:
                print("  ✅ Better than linear scaling - good optimization")
            else:
                print("  📈 Approximately linear scaling")
    
    # Project total time based on actual family count
    print(f"\n🎯 BOTTLENECK PROJECTION:")
    
    # Use medium family as baseline for projection
    if 'medium' in results:
        medium_time_per_relay = results['medium']['time_per_relay']
        print(f"  Average time per relay: {medium_time_per_relay*1000:.3f}ms")
        
        # Estimate total family page rendering time
        # We know from the profiling that 5326 families took 97.33s of template rendering
        total_estimated_time = 5326 * results['medium']['render_time']
        actual_time = 97.33
        
        print(f"  Estimated total template time: {total_estimated_time:.1f}s")
        print(f"  Actual total template time: {actual_time:.1f}s")
        print(f"  Estimation accuracy: {actual_time/total_estimated_time*100:.1f}%")
        
        # Identify bottleneck areas
        print(f"\n🔍 PRIMARY BOTTLENECKS:")
        print(f"  Template rendering is taking {actual_time:.1f}s for 5,326 family pages")
        print(f"  This equals {actual_time/5326*1000:.2f}ms per family page on average")
        print(f"  At current rate: {5326/actual_time:.0f} pages per second")
        
        # Calculate what improvement would be needed for target
        target_improvement = 0.79  # 79% improvement target
        target_time = actual_time * (1 - target_improvement)
        required_speedup = actual_time / target_time
        
        print(f"\n🎯 TARGET OPTIMIZATION:")
        print(f"  Target template time: {target_time:.1f}s ({target_improvement*100:.0f}% improvement)")
        print(f"  Required speedup: {required_speedup:.1f}x")
        print(f"  Target per-page time: {target_time/5326*1000:.2f}ms")
    
    # Save comprehensive analysis
    with open("family_scaling_analysis.txt", "w") as f:
        f.write("FAMILY PAGE SCALING ANALYSIS\n")
        f.write("="*50 + "\n")
        f.write(f"{'Size':<8} {'Relays':<8} {'Time':<10} {'Per Relay':<12} {'HTML Size':<12}\n")
        f.write("-" * 60 + "\n")
        
        for size_name, data in results.items():
            f.write(f"{size_name:<8} {data['relay_count']:<8} {data['render_time']:<10.4f} {data['time_per_relay']*1000:<12.3f} {data['html_size']:<12,d}\n")
        
        f.write(f"\nACTUAL PERFORMANCE DATA:\n")
        f.write(f"Total families: 5,326\n")
        f.write(f"Total template render time: 97.33s\n")
        f.write(f"Average per family: {97.33/5326*1000:.2f}ms\n")
        f.write(f"Pages per second: {5326/97.33:.0f}\n")

if __name__ == "__main__":
    profile_single_family_template() 