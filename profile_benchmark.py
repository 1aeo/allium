#!/usr/bin/env python3
"""
Detailed profiling script for Allium template rendering performance analysis.
Uses cProfile and custom timing to identify specific bottlenecks.
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

from allium.lib.relays import Relays

def profile_family_page_generation():
    """Profile family page generation with detailed breakdown"""
    print("🔍 Starting detailed profiling of family page generation...")
    
    # Create profiler
    profiler = cProfile.Profile()
    
    # Clean output directory
    output_dir = "profile_output"
    if os.path.exists(output_dir):
        import shutil
        shutil.rmtree(output_dir)
    
    # Initialize Relays object
    relay_set = Relays(output_dir, "https://onionoo.torproject.org/details", progress=True)
    
    print("📡 Fetching relay data...")
    start_fetch = time.time()
    relay_set._fetch_onionoo_details()
    fetch_time = time.time() - start_fetch
    print(f"   Data fetch: {fetch_time:.2f}s")
    
    print("🔧 Processing relay data...")
    start_process = time.time()
    relay_set._trim_platform()
    relay_set._fix_missing_observed_bandwidth()
    relay_set._process_aroi_contacts()
    relay_set._add_hashed_contact()
    process_time = time.time() - start_process
    print(f"   Data processing: {process_time:.2f}s")
    
    print("🎯 Pre-processing template data...")
    start_preprocess = time.time()
    relay_set._preprocess_template_data()
    preprocess_time = time.time() - start_preprocess
    print(f"   Template preprocessing: {preprocess_time:.2f}s")
    
    print("📊 Categorizing relays...")
    start_categorize = time.time()
    relay_set._categorize()
    categorize_time = time.time() - start_categorize
    print(f"   Categorization: {categorize_time:.2f}s")
    
    # Profile the family page generation specifically
    print("🔍 Starting profiled family page generation...")
    profiler.enable()
    
    start_family = time.time()
    relay_set.write_pages_by_key("family")
    family_time = time.time() - start_family
    
    profiler.disable()
    
    print(f"✅ Family page generation completed: {family_time:.2f}s")
    
    # Analyze profiling results
    print("\n" + "="*80)
    print("📈 DETAILED PROFILING RESULTS")
    print("="*80)
    
    # Create string buffer for profile output
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s)
    
    # Sort by cumulative time and show top functions
    ps.sort_stats('cumulative')
    ps.print_stats(30)  # Top 30 functions
    
    profile_output = s.getvalue()
    print(profile_output)
    
    # Save detailed profile to file
    with open("family_page_profile.txt", "w") as f:
        f.write(profile_output)
    
    # Analyze specific bottlenecks
    print("\n" + "="*80)
    print("🎯 BOTTLENECK ANALYSIS")
    print("="*80)
    
    # Look for specific expensive operations
    s2 = io.StringIO()
    ps2 = pstats.Stats(profiler, stream=s2)
    
    print("🔍 Template rendering functions:")
    ps2.sort_stats('cumulative')
    ps2.print_stats(".*render.*", 10)
    template_output = s2.getvalue()
    print(template_output)
    
    print("\n🔍 Jinja2 specific functions:")
    s3 = io.StringIO()
    ps3 = pstats.Stats(profiler, stream=s3)
    ps3.sort_stats('cumulative')
    ps3.print_stats(".*jinja.*", 10)
    jinja_output = s3.getvalue()
    print(jinja_output)
    
    print("\n🔍 String and formatting operations:")
    s4 = io.StringIO()
    ps4 = pstats.Stats(profiler, stream=s4)
    ps4.sort_stats('cumulative')
    ps4.print_stats(".*(format|escape|str).*", 10)
    string_output = s4.getvalue()
    print(string_output)
    
    print("\n🔍 File I/O operations:")
    s5 = io.StringIO()
    ps5 = pstats.Stats(profiler, stream=s5)
    ps5.sort_stats('cumulative')
    ps5.print_stats(".*(write|open|close).*", 10)
    io_output = s5.getvalue()
    print(io_output)
    
    # Save all analysis to file
    with open("detailed_bottleneck_analysis.txt", "w") as f:
        f.write("DETAILED PROFILING RESULTS\n")
        f.write("="*80 + "\n")
        f.write(profile_output)
        f.write("\nTEMPLATE RENDERING FUNCTIONS\n")
        f.write("="*40 + "\n")
        f.write(template_output)
        f.write("\nJINJA2 SPECIFIC FUNCTIONS\n")
        f.write("="*40 + "\n")
        f.write(jinja_output)
        f.write("\nSTRING AND FORMATTING OPERATIONS\n")
        f.write("="*40 + "\n")
        f.write(string_output)
        f.write("\nFILE I/O OPERATIONS\n")
        f.write("="*40 + "\n")
        f.write(io_output)
    
    return {
        'fetch_time': fetch_time,
        'process_time': process_time,
        'preprocess_time': preprocess_time,
        'categorize_time': categorize_time,
        'family_time': family_time,
        'total_time': fetch_time + process_time + preprocess_time + categorize_time + family_time
    }

def analyze_template_bottlenecks():
    """Additional analysis focusing on template-specific bottlenecks"""
    print("\n" + "="*80)
    print("🎨 TEMPLATE-SPECIFIC BOTTLENECK ANALYSIS")
    print("="*80)
    
    # Profile a small subset to understand per-page costs
    output_dir = "profile_subset"
    if os.path.exists(output_dir):
        import shutil
        shutil.rmtree(output_dir)
    
    relay_set = Relays(output_dir, "https://onionoo.torproject.org/details", progress=False)
    relay_set._fetch_onionoo_details()
    relay_set._trim_platform()
    relay_set._fix_missing_observed_bandwidth()
    relay_set._process_aroi_contacts()
    relay_set._add_hashed_contact()
    relay_set._preprocess_template_data()
    relay_set._categorize()
    
    # Get just a few family pages for detailed analysis
    family_keys = list(relay_set.json["sorted"]["family"].keys())[:10]
    
    print(f"🔍 Profiling {len(family_keys)} family pages for detailed per-page analysis...")
    
    profiler = cProfile.Profile()
    profiler.enable()
    
    start_time = time.time()
    for key in family_keys:
        # Profile individual page generation
        relay_set.json["sorted"]["family"] = {key: relay_set.json["sorted"]["family"][key]}
        relay_set.write_pages_by_key("family")
        break  # Just do one for now
    
    subset_time = time.time() - start_time
    profiler.disable()
    
    print(f"✅ Single family page generation: {subset_time:.3f}s")
    
    # Analyze per-page bottlenecks
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s)
    ps.sort_stats('cumulative')
    ps.print_stats(20)
    
    single_page_output = s.getvalue()
    print(single_page_output)
    
    with open("single_page_profile.txt", "w") as f:
        f.write(f"Single family page generation time: {subset_time:.3f}s\n")
        f.write("="*60 + "\n")
        f.write(single_page_output)
    
    return subset_time

if __name__ == "__main__":
    print("🚀 ALLIUM TEMPLATE RENDERING PROFILER")
    print("="*80)
    print("Cross-checking against commit b2894f0 benchmark cleanup")
    print("Targeting identification of remaining 99.01s family page bottleneck")
    print("="*80 + "\n")
    
    # Run comprehensive profiling
    try:
        results = profile_family_page_generation()
        single_page_time = analyze_template_bottlenecks()
        
        print("\n" + "="*80)
        print("📊 PROFILING SUMMARY")
        print("="*80)
        print(f"Data fetch time:      {results['fetch_time']:8.2f}s")
        print(f"Data processing:      {results['process_time']:8.2f}s") 
        print(f"Template preprocessing: {results['preprocess_time']:6.2f}s")
        print(f"Categorization:       {results['categorize_time']:8.2f}s")
        print(f"Family page generation: {results['family_time']:6.2f}s")
        print(f"Total time:           {results['total_time']:8.2f}s")
        print(f"\nSingle page generation: {single_page_time:6.3f}s")
        
        family_count = len([f for f in os.listdir('profile_output/family') if os.path.isdir(os.path.join('profile_output/family', f))])
        if family_count > 0:
            print(f"Estimated pages generated: {family_count}")
            print(f"Average per page:     {results['family_time']/family_count:8.3f}s")
        
        print("\n📁 Profiling files generated:")
        print("  - family_page_profile.txt")
        print("  - detailed_bottleneck_analysis.txt") 
        print("  - single_page_profile.txt")
        
    except Exception as e:
        print(f"❌ Profiling failed: {e}")
        import traceback
        traceback.print_exc() 