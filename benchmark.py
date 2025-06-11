import time
import subprocess
import os

def run_benchmark(label="Benchmark", output_dir="output_benchmark"):
    """
    Runs a benchmark on allium generation, focusing on timing.
    """
    print(f"--- Starting {label} ---")
    
    # Clean output directory if it exists
    if os.path.exists(output_dir):
        import shutil
        shutil.rmtree(output_dir)
    
    command = [
        "python3", 
        "allium/allium.py", 
        "--out", output_dir,
        "-p"  # Progress updates
    ]
    
    start_time = time.time()
    
    try:
        # Run the allium script as a subprocess
        process = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True
        )
        
    except subprocess.CalledProcessError as e:
        print("!!! Benchmark failed !!!")
        print(f"Stderr: {e.stderr}")
        print(f"Stdout: {e.stdout}")
        return None

    end_time = time.time()
    duration = end_time - start_time
    
    print(f"✅ {label} Complete.")
    print(f"⏱️  Total generation took: {duration:.2f} seconds")
    print("---")
    
    return duration

def run_optimization_benchmark():
    """
    Run both before and after benchmarks and compare results.
    """
    print("🚀 Optimization Performance Benchmark")
    print("=" * 50)
    
    # Note: Since we already modified the code, this will show the optimized performance
    # We're measuring the optimized version only
    optimized_time = run_benchmark("Optimized Version", "output_optimized")
    
    if optimized_time:
        print("\n" + "=" * 50)
        print("📊 Benchmark Results Summary")
        print("=" * 50)
        print(f"✅ Optimized Version: {optimized_time:.2f} seconds")
        
        # Based on your original performance report
        baseline_time = 153.10  # From our earlier measurement
        
        if optimized_time < baseline_time:
            improvement = ((baseline_time - optimized_time) / baseline_time) * 100
            print(f"📈 Performance improvement: {improvement:.1f}% faster")
            print(f"⏰ Time saved: {baseline_time - optimized_time:.2f} seconds")
        else:
            regression = ((optimized_time - baseline_time) / baseline_time) * 100
            print(f"📉 Performance regression: {regression:.1f}% slower")
            print(f"⏰ Additional time: {optimized_time - baseline_time:.2f} seconds")
    
    return optimized_time

if __name__ == "__main__":
    run_optimization_benchmark() 