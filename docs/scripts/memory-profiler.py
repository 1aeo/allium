#!/usr/bin/env python3
"""
Memory profiler for AROI leaderboard generation
Measures memory consumption during full allium.py execution
"""

import psutil
import tracemalloc
import traceback
import sys
import time
import gc
import subprocess
import os
from typing import Dict, Any

def get_memory_usage():
    """Get current memory usage in MB"""
    process = psutil.Process()
    memory_info = process.memory_info()
    return {
        'rss_mb': memory_info.rss / 1024 / 1024,  # Resident Set Size
        'vms_mb': memory_info.vms / 1024 / 1024,  # Virtual Memory Size
        'percent': process.memory_percent()
    }

def measure_memory_with_subprocess():
    """Measure memory usage of allium.py subprocess"""
    print("🔍 Subprocess Memory Measurement")
    print("=" * 50)
    
    # Run allium.py and measure its memory usage
    cmd = ['python3', 'allium.py', '--out', 'www_memory_test']
    print(f"📦 Running: {' '.join(cmd)}")
    
    # Change to the allium directory
    os.chdir("../../")
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Track memory usage during execution
    max_memory = 0
    measurements = []
    
    try:
        while process.poll() is None:
            try:
                proc_info = psutil.Process(process.pid)
                memory_info = proc_info.memory_info()
                rss_mb = memory_info.rss / 1024 / 1024
                max_memory = max(max_memory, rss_mb)
                measurements.append({
                    'time': time.time(),
                    'rss_mb': rss_mb,
                    'vms_mb': memory_info.vms / 1024 / 1024
                })
                time.sleep(0.1)  # Sample every 100ms
            except psutil.NoSuchProcess:
                break
        
        # Wait for completion
        stdout, stderr = process.communicate()
        
        print(f"🎯 Process completed with exit code: {process.returncode}")
        print(f"📊 Peak memory usage: {max_memory:.2f} MB")
        print(f"📏 Total measurements: {len(measurements)}")
        
        if measurements:
            avg_memory = sum(m['rss_mb'] for m in measurements) / len(measurements)
            print(f"📈 Average memory usage: {avg_memory:.2f} MB")
        
        return {
            'peak_mb': max_memory,
            'measurements': measurements,
            'exit_code': process.returncode,
            'stdout': stdout.decode('utf-8') if stdout else '',
            'stderr': stderr.decode('utf-8') if stderr else ''
        }
        
    except Exception as e:
        print(f"❌ Error measuring subprocess: {e}")
        return None

def profile_aroi_inline():
    """Profile AROI generation inline within this process"""
    print("🔍 Inline AROI Memory Profiling")
    print("=" * 50)
    
    # Start memory tracking
    tracemalloc.start()
    initial_memory = get_memory_usage()
    
    print(f"📊 Initial Memory Usage:")
    print(f"   RSS: {initial_memory['rss_mb']:.2f} MB")
    print(f"   VMS: {initial_memory['vms_mb']:.2f} MB")
    print(f"   Percent: {initial_memory['percent']:.2f}%")
    print()
    
    try:
        # Import and run the full allium process
        print("📦 Importing allium...")
        import_start = time.time()
        
        # Add paths
        sys.path.insert(0, '../../allium')
        sys.path.insert(0, '.')
        
        # Import the main allium functionality
        from lib.relays import Relays
        
        import_memory = get_memory_usage()
        import_time = time.time() - import_start
        
        print(f"   Time: {import_time:.2f}s")
        print(f"   Memory after import: {import_memory['rss_mb']:.2f} MB (+{import_memory['rss_mb'] - initial_memory['rss_mb']:.2f} MB)")
        print()
        
        # Create full Relays instance (this will trigger AROI generation)
        print("🏗️ Creating full Relays instance...")
        relays_start = time.time()
        
        # Use the same parameters as allium.py
        onionoo_url = "https://onionoo.torproject.org/details"
        output_dir = "www_memory_test"
        
        relays = Relays(
            output_dir=output_dir,
            onionoo_url=onionoo_url,
            use_bits=False,
            progress=False
        )
        
        relays_memory = get_memory_usage()
        relays_time = time.time() - relays_start
        
        print(f"   Time: {relays_time:.2f}s")
        print(f"   Memory after Relays creation: {relays_memory['rss_mb']:.2f} MB (+{relays_memory['rss_mb'] - import_memory['rss_mb']:.2f} MB)")
        print()
        
        # Analyze the data structures
        print("📏 Data structure analysis:")
        if hasattr(relays, 'json') and relays.json:
            total_relays = len(relays.json.get('relays', []))
            print(f"   Total relays: {total_relays}")
            
            if 'sorted' in relays.json:
                contacts = relays.json['sorted'].get('contact', {})
                print(f"   AROI operators: {len(contacts)}")
                
                # Analyze AROI leaderboards if available
                if hasattr(relays, 'aroi_leaderboards'):
                    aroi_data = relays.aroi_leaderboards
                    if aroi_data:
                        print(f"   AROI leaderboards generated: {len(aroi_data)}")
                        
                        # Analyze memory usage of AROI data
                        aroi_size = sys.getsizeof(aroi_data)
                        print(f"   AROI data size: {aroi_size / 1024:.2f} KB")
        
        # Memory snapshot
        current, peak = tracemalloc.get_traced_memory()
        print(f"📈 Tracemalloc Results:")
        print(f"   Current: {current / 1024 / 1024:.2f} MB")
        print(f"   Peak: {peak / 1024 / 1024:.2f} MB")
        print()
        
        # Final results
        final_memory = get_memory_usage()
        total_increase = final_memory['rss_mb'] - initial_memory['rss_mb']
        
        print(f"🎯 Final Results:")
        print(f"   Total memory increase: {total_increase:.2f} MB")
        print(f"   Peak RSS: {final_memory['rss_mb']:.2f} MB")
        print(f"   Process memory %: {final_memory['percent']:.2f}%")
        print(f"   Total time: {relays_time:.2f}s")
        
        return {
            'initial_mb': initial_memory['rss_mb'],
            'final_mb': final_memory['rss_mb'],
            'increase_mb': total_increase,
            'peak_mb': peak / 1024 / 1024,
            'total_time': relays_time
        }
        
    except Exception as e:
        print(f"❌ Error during profiling: {e}")
        traceback.print_exc()
        return None
    finally:
        tracemalloc.stop()

if __name__ == "__main__":
    print("Starting AROI Memory Profiling...")
    print(f"Python version: {sys.version}")
    print(f"PID: {os.getpid()}")
    print()
    
    # Run garbage collection before starting
    gc.collect()
    
    print("🔬 METHOD 1: Subprocess Memory Measurement")
    print("=" * 60)
    subprocess_results = measure_memory_with_subprocess()
    
    print("\n🔬 METHOD 2: Inline Memory Profiling")
    print("=" * 60)
    inline_results = profile_aroi_inline()
    
    print("\n" + "=" * 60)
    print("📊 COMPREHENSIVE RESULTS:")
    
    if subprocess_results:
        print(f"Subprocess peak memory: {subprocess_results['peak_mb']:.2f} MB")
        print(f"Subprocess exit code: {subprocess_results['exit_code']}")
        
    if inline_results:
        print(f"Inline memory increase: {inline_results['increase_mb']:.2f} MB")
        print(f"Inline peak memory: {inline_results['peak_mb']:.2f} MB")
        print(f"Inline total time: {inline_results['total_time']:.2f}s")
        
    print("\n💡 This baseline will be used to measure optimization impact!") 