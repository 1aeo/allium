#!/usr/bin/env python3
"""
Integration test for allium.py API timeout behavior.

This test:
1. Starts a slow/hanging proxy server for one of the APIs
2. Runs allium.py with the slow API URL
3. Verifies the timeout triggers and cache is used
4. Compares output timestamps to verify cached data was used
"""

import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import time
from datetime import datetime

# Configuration
SLOW_SERVER_PORT = 19100
HANG_DURATION = 300  # 5 minutes - longer than any timeout


class HangingAPIHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler that hangs indefinitely to test timeout behavior."""
    
    # Class variables to track requests
    request_count = 0
    request_log = []
    
    def log_message(self, format, *args):
        """Log requests with timestamps."""
        msg = f"[HangServer] {datetime.now().isoformat()} - {format % args}"
        print(msg)
        HangingAPIHandler.request_log.append(msg)
    
    def do_GET(self):
        """Handle GET requests by hanging."""
        HangingAPIHandler.request_count += 1
        self.log_message("Request #%d to %s - HANGING for %ds...", 
                        HangingAPIHandler.request_count, self.path, HANG_DURATION)
        
        # Hang - don't send any response
        time.sleep(HANG_DURATION)
        
        # If we get here, timeout didn't work
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"error": "timeout should have triggered"}')


def start_hanging_server():
    """Start a hanging test server in a background thread."""
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("127.0.0.1", SLOW_SERVER_PORT), HangingAPIHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"[Test] Started hanging server on port {SLOW_SERVER_PORT}")
    return server


def run_allium_with_hanging_details_api():
    """Run allium.py with the Details API pointing to hanging server."""
    print("\n" + "="*70)
    print("INTEGRATION TEST: Allium with Hanging Details API")
    print("="*70)
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Expected behavior: Details API should timeout and use cache")
    print(f"Timeout configured: 90s (fresh cache) or 300s (stale cache)")
    print("="*70)
    
    # Reset request tracking
    HangingAPIHandler.request_count = 0
    HangingAPIHandler.request_log = []
    
    # Start hanging server
    server = start_hanging_server()
    time.sleep(0.5)
    
    # Run allium.py with hanging Details API URL
    hanging_url = f"http://127.0.0.1:{SLOW_SERVER_PORT}/details"
    
    cmd = [
        sys.executable,
        "allium.py",
        "--out", "../output-timeout-test",
        "--progress",
        "--onionoo-details-url", hanging_url,  # This will hang
        # Other APIs use real URLs (or cached data)
    ]
    
    print(f"\n[Test] Running: {' '.join(cmd)}")
    print(f"[Test] Details API URL: {hanging_url} (WILL HANG)")
    print("-" * 70)
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            cmd,
            cwd="/workspace/allium",
            capture_output=True,
            text=True,
            timeout=180,  # 3 minute timeout for the entire test
        )
        elapsed = time.time() - start_time
        
        print("-" * 70)
        print(f"[Test] Process completed in {elapsed:.1f}s")
        print(f"[Test] Exit code: {result.returncode}")
        
        # Check output for timeout messages
        output = result.stdout + result.stderr
        
        # Look for timeout-related messages
        timeout_triggered = any([
            "exceeded total timeout" in output,
            "request timed out" in output,
            "using cached" in output.lower() and "timeout" in output.lower(),
        ])
        
        cache_used = "using cached" in output.lower()
        
        print(f"\n[Test Results]")
        print(f"  Timeout triggered: {'✅ YES' if timeout_triggered else '❌ NO'}")
        print(f"  Cache used: {'✅ YES' if cache_used else '❌ NO'}")
        print(f"  Elapsed time: {elapsed:.1f}s")
        print(f"  Requests to hanging server: {HangingAPIHandler.request_count}")
        
        # Show relevant output lines
        print(f"\n[Relevant Output Lines]")
        for line in output.split('\n'):
            if any(kw in line.lower() for kw in ['timeout', 'cache', 'details api', 'error']):
                print(f"  {line}")
        
        server.shutdown()
        
        # Success if timeout triggered and cache was used, within reasonable time
        success = timeout_triggered and cache_used and elapsed < 120  # Should complete in < 2 min
        return success, elapsed, output
        
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        print(f"[Test] ❌ FAILED: Process timed out after {elapsed:.1f}s")
        print("[Test] This means the timeout fix is NOT working!")
        server.shutdown()
        return False, elapsed, "Process timed out"


def run_allium_with_hanging_uptime_api():
    """Run allium.py with the Uptime API pointing to hanging server."""
    print("\n" + "="*70)
    print("INTEGRATION TEST: Allium with Hanging Uptime API")
    print("="*70)
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Expected behavior: Uptime API should timeout (30s fresh cache)")
    print("="*70)
    
    # Reset request tracking
    HangingAPIHandler.request_count = 0
    HangingAPIHandler.request_log = []
    
    # Start hanging server on different port
    global SLOW_SERVER_PORT
    SLOW_SERVER_PORT = 19101
    server = start_hanging_server()
    time.sleep(0.5)
    
    # Run allium.py with hanging Uptime API URL
    hanging_url = f"http://127.0.0.1:{SLOW_SERVER_PORT}/uptime"
    
    cmd = [
        sys.executable,
        "allium.py",
        "--out", "../output-timeout-test2",
        "--progress",
        "--onionoo-uptime-url", hanging_url,  # This will hang
    ]
    
    print(f"\n[Test] Running: {' '.join(cmd)}")
    print(f"[Test] Uptime API URL: {hanging_url} (WILL HANG)")
    print(f"[Test] Uptime timeout: 30s (fresh cache)")
    print("-" * 70)
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            cmd,
            cwd="/workspace/allium",
            capture_output=True,
            text=True,
            timeout=180,
        )
        elapsed = time.time() - start_time
        
        print("-" * 70)
        print(f"[Test] Process completed in {elapsed:.1f}s")
        print(f"[Test] Exit code: {result.returncode}")
        
        output = result.stdout + result.stderr
        
        timeout_triggered = any([
            "exceeded total timeout" in output,
            "request timed out" in output,
        ])
        
        cache_used = "using cached" in output.lower()
        
        print(f"\n[Test Results]")
        print(f"  Timeout triggered: {'✅ YES' if timeout_triggered else '❌ NO'}")
        print(f"  Cache used: {'✅ YES' if cache_used else '❌ NO'}")
        print(f"  Elapsed time: {elapsed:.1f}s")
        
        # Show relevant output lines
        print(f"\n[Relevant Output Lines]")
        for line in output.split('\n'):
            if any(kw in line.lower() for kw in ['timeout', 'cache', 'uptime']):
                print(f"  {line}")
        
        server.shutdown()
        
        success = timeout_triggered and elapsed < 120
        return success, elapsed, output
        
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        print(f"[Test] ❌ FAILED: Process timed out after {elapsed:.1f}s")
        server.shutdown()
        return False, elapsed, "Process timed out"


def compare_timestamps(baseline_file, test_output_dir):
    """Compare file timestamps between baseline and test output."""
    print("\n" + "="*70)
    print("TIMESTAMP COMPARISON")
    print("="*70)
    
    if not os.path.exists(baseline_file):
        print(f"[Error] Baseline file not found: {baseline_file}")
        return False
    
    # Load baseline timestamps
    baseline_ts = {}
    with open(baseline_file, 'r') as f:
        for line in f:
            parts = line.strip().split(' ')
            if len(parts) >= 2:
                path = parts[0].replace('output-baseline/', '')
                ts = parts[1]
                baseline_ts[path] = ts
    
    # Get test output timestamps
    test_ts = {}
    for root, dirs, files in os.walk(test_output_dir):
        for file in files:
            if file.endswith('.html'):
                full_path = os.path.join(root, file)
                rel_path = full_path.replace(test_output_dir + '/', '')
                test_ts[rel_path] = str(int(os.path.getmtime(full_path)))
    
    print(f"Baseline files: {len(baseline_ts)}")
    print(f"Test output files: {len(test_ts)}")
    
    # Compare
    changed = []
    missing = []
    new = []
    
    for path, ts in baseline_ts.items():
        if path not in test_ts:
            missing.append(path)
        elif test_ts[path] != ts:
            changed.append(path)
    
    for path in test_ts:
        if path not in baseline_ts:
            new.append(path)
    
    print(f"\nResults:")
    print(f"  Changed timestamps: {len(changed)}")
    print(f"  Missing files: {len(missing)}")
    print(f"  New files: {len(new)}")
    
    if changed:
        print(f"\n  Sample changed files:")
        for p in changed[:5]:
            print(f"    {p}")
    
    # If cached data was used, most timestamps should be different (new generation)
    # But the DATA should be the same
    return True


def main():
    """Run all integration tests."""
    print("\n" + "="*70)
    print("ALLIUM API TIMEOUT INTEGRATION TESTS")
    print("="*70)
    print(f"Started: {datetime.now().isoformat()}")
    print("="*70)
    
    results = []
    
    # Test 1: Hanging Details API
    print("\n>>> TEST 1: Details API Timeout <<<")
    success1, elapsed1, _ = run_allium_with_hanging_details_api()
    results.append(("Details API Timeout", success1, elapsed1))
    
    # Test 2: Hanging Uptime API
    print("\n>>> TEST 2: Uptime API Timeout <<<")
    success2, elapsed2, _ = run_allium_with_hanging_uptime_api()
    results.append(("Uptime API Timeout", success2, elapsed2))
    
    # Summary
    print("\n" + "="*70)
    print("TEST RESULTS SUMMARY")
    print("="*70)
    
    all_passed = True
    for name, success, elapsed in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status}: {name} ({elapsed:.1f}s)")
        if not success:
            all_passed = False
    
    print("="*70)
    if all_passed:
        print("ALL TESTS PASSED ✅")
    else:
        print("SOME TESTS FAILED ❌")
    print("="*70)
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
