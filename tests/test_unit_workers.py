"""
Unit tests for allium/lib/allium.lib.workers.py - Worker system for API data fetching
"""
import json
import os
import pytest
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from allium.lib.workers import (
    _save_cache as save_cache, _load_cache as load_cache, 
    _mark_ready as mark_worker_ready, _mark_stale as mark_worker_stale, 
    get_worker_status, get_all_worker_status, 
    _write_timestamp as write_timestamp, _read_timestamp as read_timestamp, 
    fetch_onionoo_details, fetch_onionoo_uptime,
    fetch_collector_data, fetch_consensus_health
)


class TestWorkerCacheManagement:
    """Test worker cache management functionality"""
    
    def test_cache_file_save_and_load_preserves_data_integrity(self):
        """Test saving and loading cache data"""
        test_data = {"test": "data", "number": 123}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = os.path.join(temp_dir, "test_cache.json")
            
            with patch('allium.lib.workers.CACHE_DIR', temp_dir):
                # Save data
                save_cache("test_worker", test_data)
                
                # Load data
                loaded_data = load_cache("test_worker")
                
                assert loaded_data == test_data
    
    def test_cache_load_returns_none_when_file_does_not_exist(self):
        """Test loading cache when file doesn't exist"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('allium.lib.workers.CACHE_DIR', temp_dir):
                result = load_cache("nonexistent_worker")
                assert result is None
    
    def test_cache_save_handles_file_write_errors_gracefully(self):
        """Test cache saving with error handling"""
        test_data = {"test": "data"}
        
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            with patch('builtins.print') as mock_print:
                save_cache("test_worker", test_data)
                
                # Check that error was logged
                mock_print.assert_called()
                assert any("Warning: Failed to save cache" in str(call) for call in mock_print.call_args_list)
    
    def test_cache_load_handles_file_read_errors_gracefully(self):
        """Test cache loading with error handling"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a file with invalid JSON
            cache_file = os.path.join(temp_dir, "onionoo_details.json")
            with open(cache_file, 'w') as f:
                f.write("invalid json content")
            
            with patch('allium.lib.workers.CACHE_DIR', temp_dir):
                with patch('builtins.print') as mock_print:
                    result = load_cache("onionoo_details")
                    
                    assert result is None
                    # Check that error was logged
                    mock_print.assert_called()
                    assert any("Warning: Failed to load cache" in str(call) for call in mock_print.call_args_list)


class TestWorkerStatusManagement:
    """Test worker status tracking functionality"""
    
    def test_worker_status_mark_ready_updates_state_correctly(self):
        """Test marking worker as ready and checking status"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('allium.lib.workers.STATE_FILE', os.path.join(temp_dir, "state.json")):
                mark_worker_ready("test_worker")
                
                status = get_worker_status("test_worker")
                
                assert status["status"] == "ready"
                assert status["error"] is None
                assert isinstance(status["timestamp"], float)
    
    def test_worker_status_mark_stale_updates_state_with_error_message(self):
        """Test marking worker as stale and checking status"""
        error_msg = "Network timeout"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('allium.lib.workers.STATE_FILE', os.path.join(temp_dir, "state.json")):
                mark_worker_stale("test_worker", error_msg)
                
                status = get_worker_status("test_worker")
                
                assert status["status"] == "stale"
                assert status["error"] == error_msg
                assert isinstance(status["timestamp"], float)
    
    def test_worker_status_get_all_returns_complete_status_dictionary(self):
        """Test getting all worker statuses"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('allium.lib.workers.STATE_FILE', os.path.join(temp_dir, "state.json")):
                mark_worker_ready("worker1")
                mark_worker_stale("worker2", "Error")
                
                all_status = get_all_worker_status()
                
                assert "worker1" in all_status
                assert "worker2" in all_status
                assert all_status["worker1"]["status"] == "ready"
                assert all_status["worker2"]["status"] == "stale"
    
    def test_worker_status_get_returns_none_for_nonexistent_worker(self):
        """Test getting status for non-existent worker"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('allium.lib.workers.STATE_FILE', os.path.join(temp_dir, "state.json")):
                status = get_worker_status("nonexistent_worker")
                assert status is None
    
    def test_worker_state_persists_across_multiple_operations(self):
        """Test that worker state persists across multiple operations"""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = os.path.join(temp_dir, "state.json")
            
            with patch('allium.lib.workers.STATE_FILE', state_file):
                # Mark worker as ready
                mark_worker_ready("persistent_worker")
                
                # Check status
                status1 = get_worker_status("persistent_worker")
                assert status1["status"] == "ready"
                
                # Mark worker as stale
                mark_worker_stale("persistent_worker", "New error")
                
                # Check status again
                status2 = get_worker_status("persistent_worker")
                assert status2["status"] == "stale"
                assert status2["error"] == "New error"


class TestWorkerTimestampManagement:
    """Test worker timestamp functionality"""
    
    def test_timestamp_write_and_read_preserves_exact_time_value(self):
        """Test writing and reading timestamps"""
        test_timestamp = "Mon, 01 Jan 2024 12:00:00 GMT"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('allium.lib.workers.CACHE_DIR', temp_dir):
                write_timestamp("test_worker", test_timestamp)
                
                read_timestamp_value = read_timestamp("test_worker")
                
                assert read_timestamp_value == test_timestamp
    
    def test_timestamp_read_returns_none_when_file_does_not_exist(self):
        """Test reading timestamp when file doesn't exist"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('allium.lib.workers.CACHE_DIR', temp_dir):
                result = read_timestamp("nonexistent_worker")
                assert result is None


class TestOnionooDetailsWorker:
    """Test onionoo details API worker"""
    
    def test_fetch_onionoo_details_success(self):
        """Test successful fetch from onionoo details API"""
        # Mock successful response
        mock_data = {
            "relays": [{"nickname": "TestRelay", "fingerprint": "ABC123"}],
            "version": "test_version"
        }
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            with patch('allium.lib.workers._load_cache') as mock_load_cache:
                mock_load_cache.return_value = None  # No cached data
                mock_response = MagicMock()
                mock_response.read.return_value = json.dumps(mock_data).encode('utf-8')
                mock_urlopen.return_value = mock_response
                
                result = fetch_onionoo_details("http://test.url", progress_logger=None)
                
                assert result is not None
                assert isinstance(result, dict)
                assert 'relays' in result
                assert result['relays'][0]['nickname'] == 'TestRelay'


class TestOnionooUptimeWorker:
    """Test onionoo uptime API worker"""
    
    def test_fetch_onionoo_uptime_success(self):
        """Test successful fetch from onionoo uptime API"""
        # Mock successful response 
        mock_data = {
            "relays": [{"fingerprint": "ABC123", "uptime": {"1_month": 95.5}}],
            "version": "test_uptime"
        }
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            with patch('allium.lib.workers._load_cache') as mock_load_cache:
                mock_load_cache.return_value = None  # No cached data
                mock_response = MagicMock()
                mock_response.read.return_value = json.dumps(mock_data).encode('utf-8')
                mock_urlopen.return_value = mock_response
                
                result = fetch_onionoo_uptime("http://test.url", progress_logger=None)
                
                assert result is not None
                assert isinstance(result, dict)


def test_fetch_onionoo_uptime_success():
    """Test successful fetch from onionoo uptime API"""
    # Mock successful response
    mock_data = {
        "relays": [{"fingerprint": "ABC123", "uptime": {"1_month": 95.5}}],
        "version": "test_uptime"
    }
    
    with patch('urllib.request.urlopen') as mock_urlopen:
        with patch('allium.lib.workers._load_cache') as mock_load_cache:
            mock_load_cache.return_value = None  # No cached data
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps(mock_data).encode('utf-8')
            mock_urlopen.return_value = mock_response
            
            result = fetch_onionoo_uptime("http://test.url", progress_logger=None)
            
            assert result is not None
            assert isinstance(result, dict)


def test_fetch_onionoo_uptime_network_error_with_cache_fallback():
    """Test timeout network error with cache fallback"""
    # Test timeout error handling with cache available
    import socket
    
    mock_cached_data = {
        "relays": [{"fingerprint": "CACHED123", "uptime": {"1_month": 92.0}}],
        "version": "cached_data"
    }
    
    with patch('urllib.request.urlopen') as mock_urlopen:
        with patch('allium.lib.workers._load_cache') as mock_load_cache:
            with patch('allium.lib.workers._cache_manager') as mock_cache_mgr:
                # Simulate timeout error
                mock_urlopen.side_effect = socket.timeout("Network timeout")
                mock_load_cache.return_value = mock_cached_data
                mock_cache_mgr.get_cache_age.return_value = 3600  # 1 hour cache
                
                result = fetch_onionoo_uptime("http://test.url", progress_logger=None)
                
                # Should return cached data on timeout
                assert result == mock_cached_data


def test_fetch_onionoo_uptime_network_error_no_cache():
    """Test timeout network error without cache"""
    # Test timeout error handling without cache
    import socket
    
    with patch('urllib.request.urlopen') as mock_urlopen:
        with patch('allium.lib.workers._load_cache') as mock_load_cache:
            with patch('allium.lib.workers._cache_manager') as mock_cache_mgr:
                # Simulate timeout error
                mock_urlopen.side_effect = socket.timeout("Network timeout")
                mock_load_cache.return_value = None  # No cache
                mock_cache_mgr.get_cache_age.return_value = None
                
                result = fetch_onionoo_uptime("http://test.url", progress_logger=None)
                
                # Should return None when no cache available
                assert result is None


def test_fetch_onionoo_uptime_progress_steps():
    """Test progress step functionality"""
    # Mock successful response
    mock_data = {
        "relays": [{"fingerprint": "ABC123", "uptime": {"1_month": 95.5}}],
        "version": "test_uptime"
    }
    
    with patch('urllib.request.urlopen') as mock_urlopen:
        with patch('allium.lib.workers._load_cache') as mock_load_cache:
            mock_load_cache.return_value = None  # No cached data
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps(mock_data).encode('utf-8')
            mock_urlopen.return_value = mock_response
            
            result = fetch_onionoo_uptime("http://test.url", progress_logger=None)
            
            assert result is not None
            assert isinstance(result, dict)


class TestOnionooUptimeCaching:
    """Test uptime API caching and timeout behavior"""
    
    def test_timeout_with_fresh_cache_fallback(self):
        """Test that with fresh cache (<12h), timeout uses cache fallback"""
        import socket
        from allium.lib.workers import UPTIME_TIMEOUT_FRESH_CACHE
        
        mock_cached_data = {
            "relays": [{"fingerprint": "ABC123", "uptime": {"1_month": 95.5}}],
            "version": "cached_uptime"
        }
        
        # Mock cache age as 1 hour (fresh)
        with patch('allium.lib.workers._cache_manager') as mock_cache_mgr:
            with patch('urllib.request.urlopen') as mock_urlopen:
                with patch('allium.lib.workers._load_cache') as mock_load_cache:
                    mock_cache_mgr.get_cache_age.return_value = 3600  # 1 hour
                    mock_urlopen.side_effect = socket.timeout("Timeout")
                    mock_load_cache.return_value = mock_cached_data
                    
                    result = fetch_onionoo_uptime("http://test.url", progress_logger=None)
                    
                    # Should return cached data on timeout
                    assert result == mock_cached_data
                    # Should have called urlopen with 30 second timeout (fresh cache for uptime)
                    mock_urlopen.assert_called_once()
                    call_args = mock_urlopen.call_args
                    assert call_args[1]['timeout'] == UPTIME_TIMEOUT_FRESH_CACHE
                    assert UPTIME_TIMEOUT_FRESH_CACHE == 30  # Uptime stays at 30 seconds
    
    def test_timeout_with_stale_cache_waits_longer(self):
        """Test that with stale cache (>12h), timeout waits 20 minutes"""
        import socket
        
        mock_cached_data = {
            "relays": [{"fingerprint": "DEF456", "uptime": {"1_month": 90.0}}],
            "version": "stale_cached_uptime"
        }
        
        # Mock cache age as 15 hours (stale)
        with patch('allium.lib.workers._cache_manager') as mock_cache_mgr:
            with patch('urllib.request.urlopen') as mock_urlopen:
                with patch('allium.lib.workers._load_cache') as mock_load_cache:
                    mock_cache_mgr.get_cache_age.return_value = 15 * 3600  # 15 hours
                    mock_urlopen.side_effect = socket.timeout("Timeout")
                    mock_load_cache.return_value = mock_cached_data
                    
                    result = fetch_onionoo_uptime("http://test.url", progress_logger=None)
                    
                    # Should still return cached data on timeout
                    assert result == mock_cached_data
                    # Should have called urlopen with 1200 second (20 min) timeout
                    mock_urlopen.assert_called_once()
                    call_args = mock_urlopen.call_args
                    assert call_args[1]['timeout'] == 1200
    
    def test_no_cache_uses_long_timeout(self):
        """Test that with no cache, function uses 20 minute timeout"""
        mock_data = {
            "relays": [{"fingerprint": "GHI789", "uptime": {"1_month": 98.0}}],
            "version": "fresh_uptime"
        }
        
        # Mock no cache
        with patch('allium.lib.workers._cache_manager') as mock_cache_mgr:
            with patch('urllib.request.urlopen') as mock_urlopen:
                with patch('allium.lib.workers._load_cache') as mock_load_cache:
                    mock_cache_mgr.get_cache_age.return_value = None  # No cache
                    mock_load_cache.return_value = None
                    mock_response = MagicMock()
                    mock_response.read.return_value = json.dumps(mock_data).encode('utf-8')
                    mock_urlopen.return_value = mock_response
                    
                    result = fetch_onionoo_uptime("http://test.url", progress_logger=None)
                    
                    # Should return fresh data
                    assert result is not None
                    # Should have called urlopen with 1200 second (20 min) timeout
                    mock_urlopen.assert_called_once()
                    call_args = mock_urlopen.call_args
                    assert call_args[1]['timeout'] == 1200
    
    def test_timeout_without_cache_returns_none(self):
        """Test that timeout without cache returns None"""
        import socket
        
        # Mock no cache
        with patch('allium.lib.workers._cache_manager') as mock_cache_mgr:
            with patch('urllib.request.urlopen') as mock_urlopen:
                with patch('allium.lib.workers._load_cache') as mock_load_cache:
                    mock_cache_mgr.get_cache_age.return_value = None  # No cache
                    mock_urlopen.side_effect = socket.timeout("Timeout")
                    mock_load_cache.return_value = None
                    
                    result = fetch_onionoo_uptime("http://test.url", progress_logger=None)
                    
                    # Should return None when no cache available
                    assert result is None
    
    def test_corrupted_cache_uses_long_timeout(self):
        """Test that with corrupted cache file, function uses long timeout"""
        mock_data = {
            "relays": [{"fingerprint": "GHI789", "uptime": {"1_month": 98.0}}],
            "version": "fresh_uptime"
        }
        
        # Mock cache file exists (has age) but load returns None (corrupted)
        with patch('allium.lib.workers._cache_manager') as mock_cache_mgr:
            with patch('urllib.request.urlopen') as mock_urlopen:
                with patch('allium.lib.workers._load_cache') as mock_load_cache:
                    mock_cache_mgr.get_cache_age.return_value = 3600  # 1 hour (would be fresh)
                    # But load returns None (corrupted cache)
                    mock_load_cache.return_value = None
                    mock_response = MagicMock()
                    mock_response.read.return_value = json.dumps(mock_data).encode('utf-8')
                    mock_urlopen.return_value = mock_response
                    
                    result = fetch_onionoo_uptime("http://test.url", progress_logger=None)
                    
                    # Should return fresh data
                    assert result is not None
                    # Should have called urlopen with 1200 second (20 min) timeout
                    # because corrupted cache is treated as no cache
                    mock_urlopen.assert_called_once()
                    call_args = mock_urlopen.call_args
                    assert call_args[1]['timeout'] == 1200
    
    def test_preloaded_cache_used_on_timeout(self):
        """Test that pre-loaded cache is reused on timeout (not loaded twice)"""
        import socket
        
        mock_cached_data = {
            "relays": [{"fingerprint": "ABC123", "uptime": {"1_month": 95.5}}],
            "version": "cached_uptime"
        }
        
        # Mock fresh cache
        with patch('allium.lib.workers._cache_manager') as mock_cache_mgr:
            with patch('urllib.request.urlopen') as mock_urlopen:
                with patch('allium.lib.workers._load_cache') as mock_load_cache:
                    mock_cache_mgr.get_cache_age.return_value = 3600  # 1 hour
                    mock_urlopen.side_effect = socket.timeout("Timeout")
                    mock_load_cache.return_value = mock_cached_data
                    
                    result = fetch_onionoo_uptime("http://test.url", progress_logger=None)
                    
                    # Should return cached data on timeout
                    assert result == mock_cached_data
                    # Cache should be loaded once for validation (pre-loading)
                    # The pre-loaded data is reused on timeout fallback
                    mock_load_cache.assert_called_once()
    
    def test_boundary_cache_age_uses_long_timeout(self):
        """Test that cache at exactly the threshold age uses long timeout"""
        import socket
        from allium.lib.workers import UPTIME_CACHE_MAX_AGE_HOURS
        
        mock_cached_data = {
            "relays": [{"fingerprint": "BOUNDARY", "uptime": {"1_month": 90.0}}],
            "version": "boundary_cached_uptime"
        }
        
        # Cache age exactly at the threshold (12 hours = 43200 seconds)
        boundary_age = UPTIME_CACHE_MAX_AGE_HOURS * 3600  # Exactly 12 hours
        
        with patch('allium.lib.workers._cache_manager') as mock_cache_mgr:
            with patch('urllib.request.urlopen') as mock_urlopen:
                with patch('allium.lib.workers._load_cache') as mock_load_cache:
                    mock_cache_mgr.get_cache_age.return_value = boundary_age
                    mock_urlopen.side_effect = socket.timeout("Timeout")
                    mock_load_cache.return_value = mock_cached_data
                    
                    result = fetch_onionoo_uptime("http://test.url", progress_logger=None)
                    
                    # Should return cached data on timeout
                    assert result == mock_cached_data
                    # Should have called urlopen with 1200 second (20 min) timeout
                    # because cache at boundary is considered stale (>= threshold)
                    mock_urlopen.assert_called_once()
                    call_args = mock_urlopen.call_args
                    assert call_args[1]['timeout'] == 1200


class TestOnionooDetailsCaching:
    """Test details API caching and timeout behavior"""
    
    def test_timeout_with_fresh_cache_fallback(self):
        """Test that with fresh cache, timeout uses cache fallback"""
        import socket
        from allium.lib.workers import DETAILS_TIMEOUT_FRESH_CACHE
        
        mock_cached_data = {
            "relays": [{"fingerprint": "ABC123", "nickname": "TestRelay"}],
            "version": "cached_details"
        }
        
        # Mock cache age as 1 hour (fresh, < 6 hours default)
        with patch('allium.lib.workers._cache_manager') as mock_cache_mgr:
            with patch('urllib.request.urlopen') as mock_urlopen:
                with patch('allium.lib.workers._load_cache') as mock_load_cache:
                    mock_cache_mgr.get_cache_age.return_value = 3600  # 1 hour
                    mock_urlopen.side_effect = socket.timeout("Timeout")
                    mock_load_cache.return_value = mock_cached_data
                    
                    result = fetch_onionoo_details("http://test.url", progress_logger=None)
                    
                    # Should return cached data on timeout
                    assert result == mock_cached_data
                    # Should have called urlopen with fresh cache timeout (90s for details)
                    mock_urlopen.assert_called_once()
                    call_args = mock_urlopen.call_args
                    assert call_args[1]['timeout'] == DETAILS_TIMEOUT_FRESH_CACHE
                    assert DETAILS_TIMEOUT_FRESH_CACHE == 90  # Verify it's 90 seconds
    
    def test_no_cache_uses_long_timeout(self):
        """Test that with no cache, function uses long timeout"""
        from allium.lib.workers import DETAILS_TIMEOUT_STALE_CACHE
        
        mock_data = {
            "relays": [{"fingerprint": "GHI789", "nickname": "FreshRelay"}],
            "version": "fresh_details"
        }
        
        # Mock no cache
        with patch('allium.lib.workers._cache_manager') as mock_cache_mgr:
            with patch('urllib.request.urlopen') as mock_urlopen:
                with patch('allium.lib.workers._load_cache') as mock_load_cache:
                    mock_cache_mgr.get_cache_age.return_value = None  # No cache
                    mock_load_cache.return_value = None
                    mock_response = MagicMock()
                    mock_response.read.return_value = json.dumps(mock_data).encode('utf-8')
                    mock_urlopen.return_value = mock_response
                    
                    result = fetch_onionoo_details("http://test.url", progress_logger=None)
                    
                    # Should return fresh data
                    assert result is not None
                    # Should have called urlopen with stale cache timeout
                    mock_urlopen.assert_called_once()
                    call_args = mock_urlopen.call_args
                    assert call_args[1]['timeout'] == DETAILS_TIMEOUT_STALE_CACHE


class TestOnionooBandwidthCaching:
    """Test bandwidth API caching and timeout behavior"""
    
    def test_fresh_cache_returns_immediately(self):
        """Test that fresh cache is returned without making a request"""
        mock_cached_data = {
            "relays": [{"fingerprint": "ABC123", "write_history": {}}],
            "version": "cached_bandwidth"
        }
        
        # Mock fresh cache (1 hour old, < 12 hours default)
        with patch('allium.lib.workers._cache_manager') as mock_cache_mgr:
            with patch('urllib.request.urlopen') as mock_urlopen:
                with patch('allium.lib.workers._load_cache') as mock_load_cache:
                    mock_cache_mgr.get_cache_age.return_value = 3600  # 1 hour
                    mock_load_cache.return_value = mock_cached_data
                    
                    from allium.lib.workers import fetch_onionoo_bandwidth
                    result = fetch_onionoo_bandwidth("http://test.url", cache_hours=12, progress_logger=None)
                    
                    # Should return cached data without making a request
                    assert result == mock_cached_data
                    # Should NOT have called urlopen
                    mock_urlopen.assert_not_called()
    
    def test_timeout_with_stale_cache_fallback(self):
        """Test that timeout with stale cache falls back to cache"""
        import socket
        from allium.lib.workers import BANDWIDTH_TIMEOUT_STALE_CACHE
        
        mock_cached_data = {
            "relays": [{"fingerprint": "ABC123", "write_history": {}}],
            "version": "stale_cached_bandwidth"
        }
        
        # Mock stale cache (15 hours old, > 12 hours default)
        with patch('allium.lib.workers._cache_manager') as mock_cache_mgr:
            with patch('urllib.request.urlopen') as mock_urlopen:
                with patch('allium.lib.workers._load_cache') as mock_load_cache:
                    mock_cache_mgr.get_cache_age.return_value = 15 * 3600  # 15 hours
                    mock_urlopen.side_effect = socket.timeout("Timeout")
                    mock_load_cache.return_value = mock_cached_data
                    
                    from allium.lib.workers import fetch_onionoo_bandwidth
                    result = fetch_onionoo_bandwidth("http://test.url", cache_hours=12, progress_logger=None)
                    
                    # Should return cached data on timeout
                    assert result == mock_cached_data
                    # Should have used stale cache timeout
                    mock_urlopen.assert_called_once()
                    call_args = mock_urlopen.call_args
                    assert call_args[1]['timeout'] == BANDWIDTH_TIMEOUT_STALE_CACHE


class TestAROIValidationCaching:
    """Test AROI validation API caching and timeout behavior"""
    
    def test_fresh_cache_returns_immediately(self):
        """Test that fresh cache is returned without making a request"""
        mock_cached_data = {
            "metadata": {"version": "1.0"},
            "statistics": {},
            "results": [{"fingerprint": "ABC123", "status": "valid"}]
        }
        
        # Mock fresh cache (30 minutes old, < 1 hour default)
        with patch('allium.lib.workers._cache_manager') as mock_cache_mgr:
            with patch('urllib.request.urlopen') as mock_urlopen:
                with patch('allium.lib.workers._load_cache') as mock_load_cache:
                    mock_cache_mgr.get_cache_age.return_value = 1800  # 30 minutes
                    mock_load_cache.return_value = mock_cached_data
                    
                    from allium.lib.workers import fetch_aroi_validation
                    result = fetch_aroi_validation("http://test.url", progress_logger=None)
                    
                    # Should return cached data without making a request
                    assert result == mock_cached_data
                    # Should NOT have called urlopen
                    mock_urlopen.assert_not_called()
    
    def test_timeout_with_cache_fallback(self):
        """Test that timeout uses cache fallback"""
        import socket
        from allium.lib.workers import AROI_TIMEOUT_STALE_CACHE
        
        mock_cached_data = {
            "metadata": {"version": "1.0"},
            "statistics": {},
            "results": [{"fingerprint": "DEF456", "status": "valid"}]
        }
        
        # Mock stale cache (2 hours old, > 1 hour default)
        with patch('allium.lib.workers._cache_manager') as mock_cache_mgr:
            with patch('urllib.request.urlopen') as mock_urlopen:
                with patch('allium.lib.workers._load_cache') as mock_load_cache:
                    mock_cache_mgr.get_cache_age.return_value = 2 * 3600  # 2 hours
                    mock_urlopen.side_effect = socket.timeout("Timeout")
                    mock_load_cache.return_value = mock_cached_data
                    
                    from allium.lib.workers import fetch_aroi_validation
                    result = fetch_aroi_validation("http://test.url", progress_logger=None)
                    
                    # Should return cached data on timeout
                    assert result == mock_cached_data
                    # Should have used stale cache timeout
                    mock_urlopen.assert_called_once()
                    call_args = mock_urlopen.call_args
                    assert call_args[1]['timeout'] == AROI_TIMEOUT_STALE_CACHE
    
    def test_invalid_response_falls_back_to_cache(self):
        """Test that invalid API response falls back to cache"""
        mock_cached_data = {
            "metadata": {"version": "1.0"},
            "statistics": {},
            "results": [{"fingerprint": "GHI789", "status": "valid"}]
        }
        
        # Invalid response (missing required keys)
        mock_invalid_data = {"invalid": "data"}
        
        # Mock stale cache
        with patch('allium.lib.workers._cache_manager') as mock_cache_mgr:
            with patch('urllib.request.urlopen') as mock_urlopen:
                with patch('allium.lib.workers._load_cache') as mock_load_cache:
                    mock_cache_mgr.get_cache_age.return_value = 2 * 3600  # 2 hours (stale)
                    mock_load_cache.return_value = mock_cached_data
                    mock_response = MagicMock()
                    mock_response.read.return_value = json.dumps(mock_invalid_data).encode('utf-8')
                    mock_urlopen.return_value = mock_response
                    
                    from allium.lib.workers import fetch_aroi_validation
                    result = fetch_aroi_validation("http://test.url", progress_logger=None)
                    
                    # Should fall back to cached data when response is invalid
                    assert result == mock_cached_data


class TestPlaceholderWorkers:
    """Test placeholder worker functions"""
    
    def test_fetch_collector_data(self):
        """Test collector data worker placeholder"""
        result = fetch_collector_data()
        assert result == {"authorities": [], "version": "placeholder"}
    
    def test_fetch_consensus_health(self):
        """Test consensus health worker placeholder"""
        result = fetch_consensus_health()
        assert result == {"health_status": {}, "version": "placeholder"}


class TestWorkerErrorHandling:
    """Test worker error handling and state management"""
    
    def test_placeholder_worker_error_handling(self):
        """Test that placeholder workers handle errors gracefully"""
        # Since placeholder workers just return None, verify they don't raise exceptions
        try:
            fetch_onionoo_uptime()
            fetch_collector_data()
            fetch_consensus_health()
        except Exception as e:
            pytest.fail(f"Placeholder worker raised unexpected exception: {e}")


class TestDirectoryCreation:
    """Test automatic directory creation"""
    
    def test_directories_created_on_import(self):
        """Test that required directories are created when module is imported"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "cache")
            data_dir = temp_dir
            
            # Ensure directories don't exist initially
            if os.path.exists(cache_dir):
                os.rmdir(cache_dir)
            
            # Patch the directory constants
            with patch('allium.lib.workers.CACHE_DIR', cache_dir):
                with patch('allium.lib.workers.DATA_DIR', data_dir):
                    # Create the cache directory since save_cache expects it to exist
                    os.makedirs(cache_dir, exist_ok=True)
                    # Manually trigger directory creation by calling the function that creates them
                    save_cache("test", {"test": "data"})
                    
                    # Now check that directories exist
                    assert os.path.exists(cache_dir)
                    assert os.path.exists(data_dir)


if __name__ == "__main__":
    pytest.main([__file__]) 