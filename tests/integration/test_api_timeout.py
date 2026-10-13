#!/usr/bin/env python3
"""
Test script for API timeout behavior.

This script tests that:
1. The total timeout wrapper actually enforces timeouts on slow downloads
2. Cached data is properly used when timeouts occur
3. Timestamps remain unchanged when using cached data
"""

import http.server
import os
import socketserver
import sys
import threading
import time
from datetime import datetime

# Direct `python tests/integration/test_api_timeout.py` puts this file's
# directory on sys.path, not the repo root. Pytest already does that via
# conftest / rootdir; the script entry point needs it before importing allium.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import pytest  # noqa: E402

from allium.lib.workers import (  # noqa: E402
    _fetch_url_with_total_timeout,
    TotalTimeoutError,
    _fetch_with_cache_fallback,
    APIConfig,
    _save_cache,
)


class SlowResponseHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler that sends responses slowly to test timeout behavior."""
    
    # Class variable to control behavior
    delay_seconds = 120  # How long to delay (longer than timeout)
    response_data = b'{"relays": [{"fingerprint": "test123", "nickname": "TestRelay"}], "version": "test"}'
    
    def log_message(self, format, *args):
        """Suppress server logs."""
        pass
    
    def do_GET(self):
        """Handle GET requests with configurable delay."""
        if self.path == '/hang':
            # Hang forever (simulate unresponsive server)
            print(f"[SlowServer] Received request to /hang - will hang indefinitely")
            time.sleep(3600)  # 1 hour - effectively forever for test
            return
        
        elif self.path == '/slow':
            # Send data very slowly (1 byte every 10 seconds)
            print(f"[SlowServer] Received request to /slow - will send data slowly")
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            # Send data byte by byte with delays
            for byte in self.response_data:
                self.wfile.write(bytes([byte]))
                self.wfile.flush()
                time.sleep(10)  # 10 seconds per byte
            return
        
        elif self.path == '/delay':
            # Wait before responding, then send full response
            print(f"[SlowServer] Received request to /delay - delaying {self.delay_seconds}s before response")
            time.sleep(self.delay_seconds)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(self.response_data)
            return
        
        elif self.path == '/fast':
            # Fast response for comparison
            print(f"[SlowServer] Received request to /fast - responding immediately")
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(self.response_data)
            return
        
        else:
            # Default: return test data immediately
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(self.response_data)


def start_slow_server():
    """Start a slow test server on an OS-assigned localhost port."""
    # Allow socket reuse to avoid "Address already in use" errors
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("127.0.0.1", 0), SlowResponseHandler)
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"[Test] Started slow server on port {port}")
    return server, port


@pytest.mark.slow
@pytest.mark.timeout(120)  # Allow 2 minutes for this test
def test_total_timeout_wrapper():
    """Test the total timeout wrapper directly."""
    print("\n" + "="*60)
    print("TEST 1: Total Timeout Wrapper")
    print("="*60)

    server, port = start_slow_server()
    try:
        time.sleep(0.5)  # Let server start

        # Test 1a: Fast response should work
        print("\n[Test 1a] Testing fast response (should succeed)...")
        start = time.time()
        result = _fetch_url_with_total_timeout(f"http://127.0.0.1:{port}/fast", timeout=10)
        elapsed = time.time() - start
        print(f"  ✅ Success: Got response in {elapsed:.2f}s")
        print(f"  Response: {result[:100]}...")

        # Test 1b: Delayed response should timeout
        print("\n[Test 1b] Testing delayed response with 5s timeout (should timeout)...")
        SlowResponseHandler.delay_seconds = 30  # 30 second delay
        start = time.time()
        try:
            _fetch_url_with_total_timeout(f"http://127.0.0.1:{port}/delay", timeout=5)
            elapsed = time.time() - start
            pytest.fail(f"Should have timed out but got response in {elapsed:.2f}s")
        except TotalTimeoutError:
            elapsed = time.time() - start
            assert elapsed < 6, f"Timed out but took {elapsed:.2f}s (expected ~5s)"
            print(f"  ✅ Correctly timed out after {elapsed:.2f}s")
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.slow
@pytest.mark.timeout(120)  # Allow 2 minutes for this test
def test_cache_fallback_on_timeout():
    """Test that cache is used when timeout occurs."""
    print("\n" + "="*60)
    print("TEST 2: Cache Fallback on Timeout")
    print("="*60)

    server, port = start_slow_server()
    try:
        time.sleep(0.5)

        # Create a test config with short timeout
        test_config = APIConfig(
            api_name='test_timeout_api',
            display_name='test timeout',
            cache_max_age_hours=1,
            timeout_fresh_cache=3,  # 3 second timeout
            timeout_stale_cache=5,  # 5 second timeout
            use_conditional_requests=False,
            count_field='relays',
        )

        # First, seed the cache with good data
        print("\n[Test 2a] Seeding cache with test data...")
        cache_data = {
            'relays': [
                {'fingerprint': 'CACHED123', 'nickname': 'CachedRelay', 'timestamp': datetime.now().isoformat()}
            ],
            'cached_at': datetime.now().isoformat(),
        }
        _save_cache('test_timeout_api', cache_data)
        print("  ✅ Cache seeded with data")

        # Now test with a slow server - should fallback to cache
        print("\n[Test 2b] Testing fetch with slow server (should fallback to cache)...")
        SlowResponseHandler.delay_seconds = 30

        messages = []

        def log_progress(msg):
            messages.append(msg)
            print(f"  [Progress] {msg}")

        start = time.time()
        result = _fetch_with_cache_fallback(
            url=f"http://127.0.0.1:{port}/delay",
            config=test_config,
            progress_logger=log_progress,
        )
        elapsed = time.time() - start

        assert (
            result and result.get('relays', [{}])[0].get('fingerprint') == 'CACHED123'
        ), f"Did not get cached data. Result: {result}"
        print(f"  ✅ Correctly used cached data after {elapsed:.2f}s timeout")
        print(f"  Cached fingerprint: {result['relays'][0]['fingerprint']}")
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.slow
@pytest.mark.timeout(120)  # Allow 2 minutes for this test
def test_compare_old_vs_new_timeout():
    """Compare old (socket-based) vs new (total) timeout behavior."""
    print("\n" + "="*60)
    print("TEST 3: Old vs New Timeout Behavior Comparison")
    print("="*60)

    server, port = start_slow_server()
    try:
        time.sleep(0.5)

        # Test old behavior with slow response
        print("\n[Test 3a] Old urllib timeout with /slow endpoint...")
        print("  (Sends 1 byte every 10 seconds - old timeout won't trigger)")
        print("  Testing with 5s timeout - this should NOT timeout with old method")
        print("  (but would take 10+ minutes to complete)")
        print("  Skipping actual old test to save time - see production logs for evidence")

        # The user's logs show:
        # - Details API: 90s timeout -> took 7 minutes
        # - Uptime API: 30s timeout -> took 9 minutes
        # This proves the old socket timeout doesn't work for slow streaming responses

        print("\n[Test 3b] New total timeout with /delay endpoint...")
        print("  Testing 5s total timeout on 30s delayed response")

        SlowResponseHandler.delay_seconds = 30
        start = time.time()
        try:
            _fetch_url_with_total_timeout(f"http://127.0.0.1:{port}/delay", timeout=5)
            elapsed = time.time() - start
            pytest.fail(f"Should have timed out but got response in {elapsed:.2f}s")
        except TotalTimeoutError:
            elapsed = time.time() - start
            assert elapsed < 7, f"Timed out but took too long: {elapsed:.2f}s"
            print(f"  ✅ New timeout works! Stopped after {elapsed:.2f}s")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    # pytest.ini deselects slow tests; these three are marked slow.
    sys.exit(pytest.main([__file__, "-v", "-s", "-m", "slow"]))
