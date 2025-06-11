#!/usr/bin/env python3
"""
Simplified profiling script that uses cProfile on the main allium executable
to identify bottlenecks in template rendering.
"""

import cProfile
import pstats
import io
import time
import os
import sys
import subprocess
import tempfile

def profile_allium_execution():
    """Profile the main allium execution using cProfile"""
    print("🔍 SIMPLIFIED ALLIUM PROFILING")
    print("="*80)
    print("Profiling the full allium execution process")
    print("Cross-checking against commit b2894f0 benchmark cleanup")
    print("="*80 + "\n")
    
    # Create a temporary output directory
    temp_dir = tempfile.mkdtemp(prefix="allium_profile_")
    print(f"📁 Using temporary output directory: {temp_dir}")
    
    try:
        # Profile the execution
        print("🚀 Starting profiled execution...")
        profiler = cProfile.Profile()
        
        # Import and run allium with profiling
        sys.path.insert(0, './allium')
        
        # Set up arguments similar to what allium.py expects
        original_argv = sys.argv
        sys.argv = ['allium.py', '--out', temp_dir, '--progress']
        
        profiler.enable()
        start_time = time.time()
        
        # Import and execute the main allium module
        try:
            import allium.allium
        except Exception as e:
            print(f"❌ Failed to import allium.allium: {e}")
            # Try running as subprocess instead
            return profile_allium_subprocess(temp_dir)
        
        execution_time = time.time() - start_time
        profiler.disable()
        
        # Restore original argv
        sys.argv = original_argv
        
        print(f"✅ Profiled execution completed in {execution_time:.2f}s")
        
        # Analyze results
        analyze_profile_results(profiler, execution_time)
        
    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir)
            print(f"🧹 Cleaned up temporary directory: {temp_dir}")

def profile_allium_subprocess(temp_dir):
    """Profile allium execution using subprocess with time measurement"""
    print("🔄 Falling back to subprocess profiling...")
    
    # Run with time measurement
    start_time = time.time()
    
    try:
        result = subprocess.run([
            sys.executable, 'allium/allium.py', 
            '--out', temp_dir, 
            '--progress'
        ], capture_output=True, text=True, timeout=600)
        
        execution_time = time.time() - start_time
        
        print(f"✅ Subprocess execution completed in {execution_time:.2f}s")
        print(f"📊 Exit code: {result.returncode}")
        
        if result.stdout:
            print("\n📝 Output:")
            print(result.stdout)
        
        if result.stderr:
            print("\n⚠️  Errors:")
            print(result.stderr)
        
        # Parse the output to extract timing information
        analyze_subprocess_output(result.stdout, execution_time)
        
    except subprocess.TimeoutExpired:
        print("⏰ Execution timed out after 600 seconds")
    except Exception as e:
        print(f"❌ Subprocess execution failed: {e}")

def analyze_profile_results(profiler, execution_time):
    """Analyze cProfile results and identify bottlenecks"""
    print("\n" + "="*80)
    print("📈 PROFILING ANALYSIS RESULTS")
    print("="*80)
    
    # Create string buffer for profile output
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s)
    
    # Sort by cumulative time
    ps.sort_stats('cumulative')
    ps.print_stats(30)
    
    profile_output = s.getvalue()
    print(profile_output)
    
    # Save detailed results
    with open("simplified_profile_results.txt", "w") as f:
        f.write(f"SIMPLIFIED ALLIUM PROFILING RESULTS\n")
        f.write("="*60 + "\n")
        f.write(f"Total execution time: {execution_time:.2f}s\n")
        f.write("="*60 + "\n")
        f.write(profile_output)
    
    # Analyze specific patterns
    print("\n🔍 Analyzing specific bottlenecks...")
    
    # Look for template rendering functions
    s2 = io.StringIO()
    ps2 = pstats.Stats(profiler, stream=s2)
    ps2.sort_stats('cumulative')
    ps2.print_stats(".*render.*", 10)
    template_output = s2.getvalue()
    
    if template_output.strip():
        print("🎨 Template rendering functions:")
        print(template_output)
    
    # Look for Jinja2 functions
    s3 = io.StringIO()
    ps3 = pstats.Stats(profiler, stream=s3)
    ps3.sort_stats('cumulative')
    ps3.print_stats(".*jinja.*", 10)
    jinja_output = s3.getvalue()
    
    if jinja_output.strip():
        print("\n🎭 Jinja2 specific functions:")
        print(jinja_output)
    
    # Look for file I/O
    s4 = io.StringIO()
    ps4 = pstats.Stats(profiler, stream=s4)
    ps4.sort_stats('cumulative')
    ps4.print_stats(".*(write|open|close).*", 10)
    io_output = s4.getvalue()
    
    if io_output.strip():
        print("\n💾 File I/O functions:")
        print(io_output)

def analyze_subprocess_output(output, execution_time):
    """Analyze the subprocess output to extract timing and bottleneck information"""
    print("\n" + "="*80)
    print("📊 SUBPROCESS OUTPUT ANALYSIS")
    print("="*80)
    
    lines = output.split('\n')
    timing_info = {}
    
    # Parse progress output for timing information
    for line in lines:
        if 'page generation complete' in line and 'Generated' in line:
            # Extract page generation info
            # Format: "✅ family page generation complete!"
            # Followed by: "📊 Generated X pages in Y.ZZs"
            page_type = line.split()[1] if len(line.split()) > 1 else "unknown"
            timing_info[page_type] = {'line': line}
        elif line.strip().startswith('📊 Generated') and 'pages in' in line:
            # Extract timing: "📊 Generated 5335 pages in 99.01s"
            parts = line.split()
            try:
                pages = int(parts[2])
                time_str = parts[5].rstrip('s')
                time_val = float(time_str)
                last_page_type = list(timing_info.keys())[-1] if timing_info else "unknown"
                if last_page_type in timing_info:
                    timing_info[last_page_type]['pages'] = pages
                    timing_info[last_page_type]['time'] = time_val
            except (IndexError, ValueError):
                pass
        elif '🎨 Template render time:' in line:
            # Extract render time: "🎨 Template render time: 97.74s (98.7%)"
            try:
                parts = line.split(':')[1].strip().split()
                render_time_str = parts[0].rstrip('s')
                render_time = float(render_time_str)
                percentage_str = parts[1].strip('()')
                percentage = float(percentage_str.rstrip('%'))
                last_page_type = list(timing_info.keys())[-1] if timing_info else "unknown"
                if last_page_type in timing_info:
                    timing_info[last_page_type]['render_time'] = render_time
                    timing_info[last_page_type]['render_percentage'] = percentage
            except (IndexError, ValueError, KeyError):
                pass
    
    # Display timing analysis
    print(f"Total execution time: {execution_time:.2f}s\n")
    
    total_page_time = 0
    total_render_time = 0
    
    for page_type, info in timing_info.items():
        if 'time' in info and 'pages' in info:
            print(f"📄 {page_type.upper()} PAGES:")
            print(f"  Generated: {info['pages']:,} pages")
            print(f"  Total time: {info['time']:.2f}s")
            print(f"  Avg per page: {info['time']/info['pages']*1000:.1f}ms")
            
            if 'render_time' in info:
                print(f"  Template render: {info['render_time']:.2f}s ({info.get('render_percentage', 0):.1f}%)")
                print(f"  Non-render time: {info['time'] - info['render_time']:.2f}s")
                total_render_time += info['render_time']
            
            total_page_time += info['time']
            print()
    
    if total_page_time > 0:
        print(f"📊 SUMMARY:")
        print(f"  Total page generation: {total_page_time:.2f}s ({total_page_time/execution_time*100:.1f}% of total)")
        if total_render_time > 0:
            print(f"  Total template rendering: {total_render_time:.2f}s ({total_render_time/execution_time*100:.1f}% of total)")
            print(f"  Template rendering efficiency: {total_render_time/total_page_time*100:.1f}% of page generation time")
        print(f"  Other processing: {execution_time - total_page_time:.2f}s")
    
    # Save analysis
    with open("subprocess_timing_analysis.txt", "w") as f:
        f.write(f"ALLIUM SUBPROCESS TIMING ANALYSIS\n")
        f.write("="*50 + "\n")
        f.write(f"Total execution time: {execution_time:.2f}s\n\n")
        
        for page_type, info in timing_info.items():
            if 'time' in info and 'pages' in info:
                f.write(f"{page_type.upper()} PAGES:\n")
                f.write(f"  Generated: {info['pages']:,} pages\n")
                f.write(f"  Total time: {info['time']:.2f}s\n")
                f.write(f"  Avg per page: {info['time']/info['pages']*1000:.1f}ms\n")
                
                if 'render_time' in info:
                    f.write(f"  Template render: {info['render_time']:.2f}s ({info.get('render_percentage', 0):.1f}%)\n")
                    f.write(f"  Non-render time: {info['time'] - info['render_time']:.2f}s\n")
                f.write("\n")

if __name__ == "__main__":
    profile_allium_execution() 