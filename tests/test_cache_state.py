"""
Unit tests for cache and state management in Phase 1 API system
"""
import json
import os
import pytest
import sys
import tempfile
import time
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add the allium directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'allium'))


class TestCacheManagement:
    """Test cache file management functionality"""
    
    def test_cache_directory_creation(self):
        """Test that cache directories are created automatically"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "cache")
            data_dir = temp_dir
            
            # Verify directories don't exist initially
            assert not os.path.exists(cache_dir)
            
            # Import workers module with patched directories
            with patch('lib.workers.CACHE_DIR', cache_dir):
                with patch('lib.workers.DATA_DIR', data_dir):
                    # Re-import the module to trigger directory creation
                    import importlib
                    importlib.reload(sys.modules['lib.workers'])
                    
                    # Verify directories are created
                    assert os.path.exists(cache_dir)
                    assert os.path.exists(data_dir)
    
    def test_cache_file_format_and_structure(self):
        """Test cache file format and JSON structure"""
        from lib.workers import _save_cache, _load_cache
        
        test_data = {
            "relays": [
                {
                    "nickname": "TestRelay1",
                    "fingerprint": "ABC123",
                    "observed_bandwidth": 1000000,
                    "flags": ["Running", "Valid"]
                },
                {
                    "nickname": "TestRelay2", 
                    "fingerprint": "DEF456",
                    "observed_bandwidth": 2000000,
                    "flags": ["Running", "Valid", "Guard"]
                }
            ],
            "version": "test_version",
            "relays_published": "2024-01-01 12:00:00"
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('lib.workers.CACHE_DIR', temp_dir):
                # Save cache
                _save_cache("test_format", test_data)
                
                # Verify file exists and is readable JSON
                cache_file = os.path.join(temp_dir, "test_format.json")
                assert os.path.exists(cache_file)
                
                # Load and verify structure
                with open(cache_file, 'r') as f:
                    cached_json = json.load(f)
                
                assert cached_json == test_data
                assert len(cached_json["relays"]) == 2
                assert cached_json["version"] == "test_version"
                
                # Verify load_cache works correctly
                loaded_data = _load_cache("test_format")
                assert loaded_data == test_data
    
    def test_cache_file_size_and_performance(self):
        """Test cache performance with large datasets"""
        from lib.workers import _save_cache, _load_cache
        
        # Create a larger test dataset
        large_data = {
            "relays": [
                {
                    "nickname": f"TestRelay{i}",
                    "fingerprint": f"FP{i:010d}",
                    "observed_bandwidth": i * 1000,
                    "consensus_weight": i * 10,
                    "flags": ["Running", "Valid"],
                    "country": "us" if i % 2 == 0 else "de",
                    "as": f"AS{i % 100}",
                    "contact": f"operator{i}@example.com"
                }
                for i in range(1000)  # 1000 relays
            ],
            "version": "large_test"
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('lib.workers.CACHE_DIR', temp_dir):
                # Test save performance
                start_time = time.time()
                _save_cache("large_test", large_data)
                save_time = time.time() - start_time
                
                # Should complete reasonably quickly (under 1 second)
                assert save_time < 1.0
                
                # Test load performance
                start_time = time.time()
                loaded_data = _load_cache("large_test")
                load_time = time.time() - start_time
                
                # Should load quickly and correctly
                assert load_time < 0.5
                assert len(loaded_data["relays"]) == 1000
                assert loaded_data["version"] == "large_test"
    
    def test_cache_corruption_handling(self):
        """Test handling of corrupted cache files"""
        from lib.workers import _load_cache
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('lib.workers.CACHE_DIR', temp_dir):
                # Create corrupted JSON file
                cache_file = os.path.join(temp_dir, "corrupted.json")
                with open(cache_file, 'w') as f:
                    f.write('{"invalid": json content}')
                
                # Should handle corruption gracefully
                with patch('builtins.print') as mock_print:
                    result = _load_cache("corrupted")
                    
                    assert result is None
                    mock_print.assert_called_once()
                    assert "Warning: Failed to load cache" in mock_print.call_args[0][0]
    
    def test_cache_concurrent_access(self):
        """Test cache access under concurrent conditions"""
        from lib.workers import _save_cache, _load_cache
        
        test_data = {"relays": [], "version": "concurrent_test"}
        results = []
        
        def cache_worker(worker_id):
            """Worker function for concurrent testing"""
            try:
                _save_cache(f"worker_{worker_id}", test_data)
                loaded = _load_cache(f"worker_{worker_id}")
                results.append(loaded == test_data)
            except Exception as e:
                results.append(False)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('lib.workers.CACHE_DIR', temp_dir):
                # Create multiple threads
                threads = []
                for i in range(5):
                    thread = threading.Thread(target=cache_worker, args=(i,))
                    threads.append(thread)
                    thread.start()
                
                # Wait for all threads
                for thread in threads:
                    thread.join()
                
                # All operations should succeed
                assert len(results) == 5
                assert all(results)


class TestStateManagement:
    """Test worker state management functionality"""
    
    def test_state_file_structure(self):
        """Test state file JSON structure and format"""
        from lib.workers import _mark_ready, _mark_stale, _save_state
        
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = os.path.join(temp_dir, "state.json")
            
            with patch('lib.workers.STATE_FILE', state_file):
                # Mark some workers with different statuses
                _mark_ready("api1")
                _mark_stale("api2", "Test error")
                _mark_ready("api3")
                
                # Verify state file structure
                assert os.path.exists(state_file)
                
                with open(state_file, 'r') as f:
                    state_data = json.load(f)
                
                assert "workers" in state_data
                assert "last_updated" in state_data
                assert isinstance(state_data["last_updated"], float)
                
                workers = state_data["workers"]
                assert len(workers) == 3
                
                # Check api1 (ready)
                assert workers["api1"]["status"] == "ready"
                assert workers["api1"]["error"] is None
                assert isinstance(workers["api1"]["timestamp"], float)
                
                # Check api2 (stale)
                assert workers["api2"]["status"] == "stale"
                assert workers["api2"]["error"] == "Test error"
                assert isinstance(workers["api2"]["timestamp"], float)
    
    def test_state_persistence_across_sessions(self):
        """Test that state persists across different sessions"""
        from lib.workers import _mark_ready, _mark_stale, _load_state, get_worker_status
        
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = os.path.join(temp_dir, "state.json")
            
            with patch('lib.workers.STATE_FILE', state_file):
                # Session 1: Create some worker states
                _mark_ready("persistent_api1")
                _mark_stale("persistent_api2", "Persistent error")
                
                # Verify state exists
                status1 = get_worker_status("persistent_api1")
                status2 = get_worker_status("persistent_api2")
                
                assert status1["status"] == "ready"
                assert status2["status"] == "stale"
                assert status2["error"] == "Persistent error"
                
                # Clear in-memory state
                with patch('lib.workers._worker_status', {}):
                    # Verify in-memory state is cleared
                    assert get_worker_status("persistent_api1") is None
                    
                    # Load state from file
                    _load_state()
                    
                    # Verify state is restored
                    restored_status1 = get_worker_status("persistent_api1")
                    restored_status2 = get_worker_status("persistent_api2")
                    
                    assert restored_status1["status"] == "ready"
                    assert restored_status2["status"] == "stale"
                    assert restored_status2["error"] == "Persistent error"
    
    def test_state_concurrent_updates(self):
        """Test state updates under concurrent conditions"""
        from lib.workers import _mark_ready, _mark_stale, get_worker_status
        
        results = []
        
        def state_worker(worker_id):
            """Worker function for concurrent state testing"""
            try:
                if worker_id % 2 == 0:
                    _mark_ready(f"concurrent_api_{worker_id}")
                else:
                    _mark_stale(f"concurrent_api_{worker_id}", f"Error {worker_id}")
                
                # Verify the status was set correctly
                status = get_worker_status(f"concurrent_api_{worker_id}")
                if worker_id % 2 == 0:
                    results.append(status["status"] == "ready")
                else:
                    results.append(status["status"] == "stale" and status["error"] == f"Error {worker_id}")
            except Exception as e:
                results.append(False)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = os.path.join(temp_dir, "state.json")
            
            with patch('lib.workers.STATE_FILE', state_file):
                # Create multiple threads
                threads = []
                for i in range(10):
                    thread = threading.Thread(target=state_worker, args=(i,))
                    threads.append(thread)
                    thread.start()
                
                # Wait for all threads
                for thread in threads:
                    thread.join()
                
                # All operations should succeed
                assert len(results) == 10
                assert all(results)
    
    def test_state_error_handling(self):
        """Test state management error handling"""
        from lib.workers import _save_state, _load_state, _mark_ready
        
        # Test save error handling
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            with patch('builtins.print') as mock_print:
                _save_state()
                mock_print.assert_called_once()
                assert "Warning: Failed to save state" in mock_print.call_args[0][0]
        
        # Test load error handling
        with patch('builtins.open', side_effect=FileNotFoundError("File not found")):
            with patch('builtins.print') as mock_print:
                _load_state()
                mock_print.assert_called_once()
                assert "Warning: Failed to load state" in mock_print.call_args[0][0]
        
        # Test corrupted state file
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = os.path.join(temp_dir, "corrupted_state.json")
            
            # Create corrupted state file
            with open(state_file, 'w') as f:
                f.write('{"corrupted": json}')
            
            with patch('lib.workers.STATE_FILE', state_file):
                with patch('builtins.print') as mock_print:
                    _load_state()
                    mock_print.assert_called_once()
                    assert "Warning: Failed to load state" in mock_print.call_args[0][0]


class TestTimestampManagement:
    """Test timestamp file management for conditional requests"""
    
    def test_timestamp_file_operations(self):
        """Test timestamp read/write operations"""
        from lib.workers import _write_timestamp, _read_timestamp
        
        test_timestamp = "Mon, 01 Jan 2024 12:00:00 GMT"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('lib.workers.CACHE_DIR', temp_dir):
                # Write timestamp
                _write_timestamp("test_api", test_timestamp)
                
                # Verify file exists
                timestamp_file = os.path.join(temp_dir, "test_api_timestamp.txt")
                assert os.path.exists(timestamp_file)
                
                # Verify content
                with open(timestamp_file, 'r') as f:
                    content = f.read().strip()
                assert content == test_timestamp
                
                # Test read function
                read_timestamp = _read_timestamp("test_api")
                assert read_timestamp == test_timestamp
    
    def test_timestamp_format_validation(self):
        """Test various timestamp formats"""
        from lib.workers import _write_timestamp, _read_timestamp
        
        test_cases = [
            "Mon, 01 Jan 2024 12:00:00 GMT",
            "Tue, 02 Feb 2024 13:30:45 GMT", 
            "Wed, 03 Mar 2024 00:00:00 GMT",
            "Thu, 04 Apr 2024 23:59:59 GMT"
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('lib.workers.CACHE_DIR', temp_dir):
                for i, timestamp in enumerate(test_cases):
                    api_name = f"timestamp_test_{i}"
                    
                    _write_timestamp(api_name, timestamp)
                    read_back = _read_timestamp(api_name)
                    
                    assert read_back == timestamp
    
    def test_timestamp_multiple_apis(self):
        """Test timestamp handling for multiple APIs"""
        from lib.workers import _write_timestamp, _read_timestamp
        
        timestamps = {
            "onionoo_details": "Mon, 01 Jan 2024 12:00:00 GMT",
            "onionoo_uptime": "Mon, 01 Jan 2024 12:05:00 GMT",
            "collector": "Mon, 01 Jan 2024 12:10:00 GMT",
            "consensus_health": "Mon, 01 Jan 2024 12:15:00 GMT"
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('lib.workers.CACHE_DIR', temp_dir):
                # Write all timestamps
                for api_name, timestamp in timestamps.items():
                    _write_timestamp(api_name, timestamp)
                
                # Verify all can be read correctly
                for api_name, expected_timestamp in timestamps.items():
                    actual_timestamp = _read_timestamp(api_name)
                    assert actual_timestamp == expected_timestamp
                
                # Verify separate files exist
                for api_name in timestamps.keys():
                    timestamp_file = os.path.join(temp_dir, f"{api_name}_timestamp.txt")
                    assert os.path.exists(timestamp_file)


class TestDataIntegrity:
    """Test data integrity and consistency"""
    
    def test_cache_data_consistency(self):
        """Test that cached data remains consistent across operations"""
        from lib.workers import _save_cache, _load_cache
        
        original_data = {
            "relays": [
                {
                    "nickname": "ConsistencyTest",
                    "fingerprint": "CONSISTENT123",
                    "observed_bandwidth": 1000000,
                    "consensus_weight": 500,
                    "flags": ["Running", "Valid", "Guard"],
                    "country": "us",
                    "nested_data": {
                        "complex": {"structure": "test"},
                        "array": [1, 2, 3, 4, 5],
                        "unicode": "测试数据"
                    }
                }
            ],
            "version": "consistency_test",
            "special_chars": "Test with special chars: äöü ñ © ® ™"
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('lib.workers.CACHE_DIR', temp_dir):
                # Save and load multiple times
                for i in range(5):
                    _save_cache(f"consistency_{i}", original_data)
                    loaded_data = _load_cache(f"consistency_{i}")
                    
                    # Verify exact match
                    assert loaded_data == original_data
                    
                    # Verify deep structure
                    assert loaded_data["relays"][0]["nested_data"]["complex"]["structure"] == "test"
                    assert loaded_data["relays"][0]["nested_data"]["array"] == [1, 2, 3, 4, 5]
                    assert loaded_data["relays"][0]["nested_data"]["unicode"] == "测试数据"
                    assert loaded_data["special_chars"] == "Test with special chars: äöü ñ © ® ™"
    
    def test_state_data_consistency(self):
        """Test that state data remains consistent"""
        from lib.workers import _mark_ready, _mark_stale, get_worker_status, get_all_worker_status
        
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = os.path.join(temp_dir, "consistency_state.json")
            
            with patch('lib.workers.STATE_FILE', state_file):
                # Create complex state scenario
                _mark_ready("api1")
                time.sleep(0.01)  # Small delay to ensure different timestamps
                _mark_stale("api2", "Complex error with unicode: 错误信息")
                time.sleep(0.01)
                _mark_ready("api3")
                time.sleep(0.01)
                _mark_stale("api1", "Status change")  # Change api1 to stale
                
                # Get individual statuses
                status1 = get_worker_status("api1")
                status2 = get_worker_status("api2")
                status3 = get_worker_status("api3")
                
                # Get all statuses
                all_status = get_all_worker_status()
                
                # Verify consistency
                assert status1 == all_status["api1"]
                assert status2 == all_status["api2"]
                assert status3 == all_status["api3"]
                
                # Verify final states
                assert status1["status"] == "stale"
                assert status1["error"] == "Status change"
                assert status2["status"] == "stale"
                assert status2["error"] == "Complex error with unicode: 错误信息"
                assert status3["status"] == "ready"
                assert status3["error"] is None
    
    def test_edge_case_data_handling(self):
        """Test handling of edge case data"""
        from lib.workers import _save_cache, _load_cache
        
        edge_cases = [
            # Empty data
            {"relays": [], "version": "empty"},
            
            # Very large numbers
            {"relays": [{"bandwidth": 999999999999999}], "version": "large_numbers"},
            
            # None values
            {"relays": [{"optional_field": None}], "version": "none_values"},
            
            # Unicode and special characters
            {"relays": [{"name": "Test™®©αβγ测试🚀"}], "version": "unicode"},
            
            # Complex nested structure
            {
                "relays": [{
                    "complex": {
                        "level1": {
                            "level2": {
                                "level3": ["deep", "nesting", "test"]
                            }
                        }
                    }
                }], 
                "version": "nested"
            }
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('lib.workers.CACHE_DIR', temp_dir):
                for i, data in enumerate(edge_cases):
                    api_name = f"edge_case_{i}"
                    
                    # Should handle all edge cases without errors
                    _save_cache(api_name, data)
                    loaded_data = _load_cache(api_name)
                    
                    assert loaded_data == data


if __name__ == "__main__":
    pytest.main([__file__])