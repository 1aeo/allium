#!/usr/bin/env python3
"""
Line-by-line profiling script for Allium template rendering.
Uses line_profiler for granular analysis of bottlenecks.
"""

import time
import os
import sys
import tempfile
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, '.')

from allium.lib.relays import Relays

def install_line_profiler():
    """Install line_profiler if not available"""
    try:
        import line_profiler
        return True
    except ImportError:
        print("📦 Installing line_profiler...")
        import subprocess
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "line_profiler"])
            import line_profiler
            return True
        except:
            print("❌ Failed to install line_profiler")
            return False

def create_profiled_version():
    """Create a version of the relays.py file with @profile decorators"""
    
    # Read the original relays.py file
    with open('allium/lib/relays.py', 'r') as f:
        content = f.read()
    
    # Add @profile decorators to key methods
    methods_to_profile = [
        'write_pages_by_key',
        '_write_page_by_key', 
        '_write_relay_info',
        '_preprocess_template_data',
        '_calculate_consensus_weight_fractions'
    ]
    
    lines = content.split('\n')
    profiled_lines = []
    
    for i, line in enumerate(lines):
        # Look for method definitions to add @profile decorator
        stripped = line.strip()
        for method in methods_to_profile:
            if f'def {method}(' in stripped:
                # Add @profile decorator on the line before
                indent = len(line) - len(line.lstrip())
                profiled_lines.append(' ' * indent + '@profile')
                break
        profiled_lines.append(line)
    
    # Write the profiled version
    with open('allium/lib/relays_profiled.py', 'w') as f:
        f.write('\n'.join(profiled_lines))
    
    print("✅ Created profiled version: allium/lib/relays_profiled.py")

def run_line_profiler():
    """Run line profiler on the template rendering process"""
    
    # Create a simple script that uses the profiled version
    profiler_script = '''
import sys
import os
sys.path.insert(0, '.')

# Monkey patch to use profiled version
import allium.lib.relays
from allium.lib.relays_profiled import Relays

# Clean output directory
output_dir = "line_profile_output"
if os.path.exists(output_dir):
    import shutil
    shutil.rmtree(output_dir)

# Initialize and run
relay_set = Relays(output_dir, "https://onionoo.torproject.org/details", progress=True)
relay_set._fetch_onionoo_details()
relay_set._trim_platform()
relay_set._fix_missing_observed_bandwidth()
relay_set._process_aroi_contacts()
relay_set._add_hashed_contact()
relay_set._preprocess_template_data()
relay_set._categorize()

# Profile just a few family pages
family_keys = list(relay_set.json["sorted"]["family"].keys())[:3]
relay_set.json["sorted"]["family"] = {k: relay_set.json["sorted"]["family"][k] for k in family_keys}

relay_set.write_pages_by_key("family")
'''
    
    with open('line_profiler_script.py', 'w') as f:
        f.write(profiler_script)
    
    print("🔍 Running line profiler...")
    import subprocess
    
    try:
        # Run kernprof with line profiler
        result = subprocess.run([
            'kernprof', '-l', '-v', 'line_profiler_script.py'
        ], capture_output=True, text=True, timeout=300)
        
        print("📊 Line profiler results:")
        print(result.stdout)
        
        if result.stderr:
            print("⚠️  Line profiler warnings/errors:")
            print(result.stderr)
        
        # Save results to file
        with open('line_profiler_results.txt', 'w') as f:
            f.write("LINE PROFILER RESULTS\n")
            f.write("="*60 + "\n")
            f.write(result.stdout)
            if result.stderr:
                f.write("\nWARNINGS/ERRORS:\n")
                f.write(result.stderr)
        
        return result.stdout
        
    except subprocess.TimeoutExpired:
        print("⏰ Line profiler timed out after 300 seconds")
        return None
    except FileNotFoundError:
        print("❌ kernprof not found. Line profiler analysis skipped.")
        return None
    except Exception as e:
        print(f"❌ Line profiler failed: {e}")
        return None

def analyze_jinja_template_performance():
    """Analyze Jinja2 template performance directly"""
    print("\n" + "="*80)
    print("🎨 DIRECT JINJA2 TEMPLATE ANALYSIS")
    print("="*80)
    
    # Create a minimal test case to isolate template rendering
    output_dir = "jinja_analysis"
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
    
    # Get a single family for detailed template analysis
    family_keys = list(relay_set.json["sorted"]["family"].keys())[:1]
    family_key = family_keys[0]
    family_relays = relay_set.json["sorted"]["family"][family_key]
    
    print(f"🔍 Analyzing single family page: {family_key}")
    print(f"   Family contains {len(family_relays)} relays")
    
    # Time different parts of template rendering
    from jinja2 import Environment, FileSystemLoader
    
    template_env = Environment(loader=FileSystemLoader('allium/templates'))
    template = template_env.get_template('family.html')
    
    # Prepare template context
    consensus_weight_fraction = sum(relay.get('consensus_weight', 0) for relay in family_relays) / sum(relay.get('consensus_weight', 0) for relay in relay_set.json.get('relays', []))
    
    context = {
        'path_prefix': '../../',
        'family': family_key,
        'relays': family_relays,
        'family_consensus_weight_fraction': consensus_weight_fraction,
        'consensus_weight_fraction': consensus_weight_fraction,
        'family_consensus_weight_fraction_str': f"{consensus_weight_fraction * 100:.2f}%",
        'last_updated': relay_set.json.get('relays_published', 'Unknown')
    }
    
    # Time template rendering
    print("⏱️  Timing template rendering components...")
    
    # Template loading time
    start_load = time.time()
    template = template_env.get_template('family.html')
    load_time = time.time() - start_load
    print(f"   Template loading: {load_time:.4f}s")
    
    # Context preparation time (already done above)
    start_context = time.time()
    # Context is already prepared
    context_time = time.time() - start_context
    print(f"   Context preparation: {context_time:.4f}s")
    
    # Pure template rendering time
    start_render = time.time()
    rendered_html = template.render(**context)
    render_time = time.time() - start_render
    print(f"   Pure template rendering: {render_time:.4f}s")
    
    # File writing time
    start_write = time.time()
    os.makedirs(f"{output_dir}/family/{family_key}", exist_ok=True)
    with open(f"{output_dir}/family/{family_key}/index.html", 'w') as f:
        f.write(rendered_html)
    write_time = time.time() - start_write
    print(f"   File writing: {write_time:.4f}s")
    
    total_single_page = load_time + context_time + render_time + write_time
    print(f"   Total single page: {total_single_page:.4f}s")
    
    # Analyze template size and complexity
    print(f"\n📊 Template analysis:")
    print(f"   Rendered HTML size: {len(rendered_html):,} bytes")
    print(f"   Number of relays in template: {len(family_relays)}")
    
    if len(family_relays) > 0:
        print(f"   Time per relay: {render_time/len(family_relays):.6f}s")
    
    # Save analysis
    with open('jinja2_direct_analysis.txt', 'w') as f:
        f.write(f"JINJA2 DIRECT TEMPLATE ANALYSIS\n")
        f.write("="*50 + "\n")
        f.write(f"Family: {family_key}\n")
        f.write(f"Relay count: {len(family_relays)}\n")
        f.write(f"Template loading: {load_time:.4f}s\n")
        f.write(f"Context preparation: {context_time:.4f}s\n")
        f.write(f"Pure template rendering: {render_time:.4f}s\n")
        f.write(f"File writing: {write_time:.4f}s\n")
        f.write(f"Total single page: {total_single_page:.4f}s\n")
        f.write(f"Rendered HTML size: {len(rendered_html):,} bytes\n")
        if len(family_relays) > 0:
            f.write(f"Time per relay: {render_time/len(family_relays):.6f}s\n")
    
    return {
        'load_time': load_time,
        'context_time': context_time,
        'render_time': render_time,
        'write_time': write_time,
        'total_time': total_single_page,
        'relay_count': len(family_relays),
        'html_size': len(rendered_html)
    }

if __name__ == "__main__":
    print("🚀 ALLIUM LINE-BY-LINE PROFILER")
    print("="*80)
    print("Detailed line-by-line analysis of template rendering bottlenecks")
    print("Cross-referencing with commit b2894f0 cleanup")
    print("="*80 + "\n")
    
    # Check if line_profiler is available
    if not install_line_profiler():
        print("⚠️  Continuing without line_profiler...")
    else:
        print("✅ Line profiler is available")
        
        # Create profiled version of the code
        create_profiled_version()
        
        # Run line profiler
        line_results = run_line_profiler()
    
    # Run direct Jinja2 analysis
    jinja_results = analyze_jinja_template_performance()
    
    print("\n" + "="*80)
    print("📊 LINE PROFILER SUMMARY")
    print("="*80)
    print(f"Single page Jinja2 analysis:")
    print(f"  Template loading:     {jinja_results['load_time']:8.4f}s")
    print(f"  Context preparation:  {jinja_results['context_time']:8.4f}s")
    print(f"  Pure template render: {jinja_results['render_time']:8.4f}s")
    print(f"  File writing:         {jinja_results['write_time']:8.4f}s")
    print(f"  Total single page:    {jinja_results['total_time']:8.4f}s")
    print(f"  Relays in page:       {jinja_results['relay_count']:8d}")
    print(f"  HTML size:            {jinja_results['html_size']:8,d} bytes")
    
    if jinja_results['relay_count'] > 0:
        print(f"  Time per relay:       {jinja_results['render_time']/jinja_results['relay_count']:8.6f}s")
    
    print("\n📁 Analysis files generated:")
    if 'line_results' in locals() and line_results:
        print("  - line_profiler_results.txt")
    print("  - jinja2_direct_analysis.txt")
    
    # Cleanup
    for temp_file in ['line_profiler_script.py', 'allium/lib/relays_profiled.py']:
        if os.path.exists(temp_file):
            os.remove(temp_file) 