"""
Phase 1 API Unit Tests Summary - All Core Functionality
Tests covering workers, coordinator, and integration for Phase 1 API implementation
"""
import json
import os
import pytest
import sys
import tempfile
import time
import urllib.error
from unittest.mock import patch, MagicMock

# Add the allium directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'allium'))

from lib.workers import (
    fetch_onionoo_details,
    fetch_onionoo_uptime, 
    fetch_collector_data,
    fetch_consensus_health,
    get_worker_status,
    get_all_worker_status,
    _save_cache,
    _load_cache,
    _mark_ready,
    _mark_stale,
    _write_timestamp,
    _read_timestamp
)

from lib.coordinator import Coordinator, create_relay_set_with_coordinator


class TestPhase1APICoreFeatures:
    """Test all Phase 1 API core features"""
    
    def setup_method(self):
        """Clear worker status before each test"""
        import lib.workers
        lib.workers._worker_status = {}
    
    def test_cache_operations(self):
        """Test cache save and load operations"""
        test_data = {"relays": [{"nickname": "TestRelay"}], "version": "test"}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('lib.workers.CACHE_DIR', temp_dir):
                # Test save and load
                _save_cache("test_api", test_data)
                loaded_data = _load_cache("test_api")
                assert loaded_data == test_data
                
                # Test loading non-existent cache
                result = _load_cache("nonexistent")
                assert result is None
    
    def test_worker_state_management(self):
        """Test worker state tracking"""
        # Test marking ready
        _mark_ready("api1")
        status = get_worker_status("api1")
        assert status["status"] == "ready"
        assert status["error"] is None
        assert isinstance(status["timestamp"], float)
        
        # Test marking stale
        _mark_stale("api2", "Test error")
        status = get_worker_status("api2")
        assert status["status"] == "stale"
        assert status["error"] == "Test error"
        
        # Test getting all statuses
        all_status = get_all_worker_status()
        assert len(all_status) == 2
        assert "api1" in all_status
        assert "api2" in all_status
    
    def test_timestamp_operations(self):
        """Test timestamp read/write for conditional requests"""
        test_timestamp = "Mon, 01 Jan 2024 12:00:00 GMT"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('lib.workers.CACHE_DIR', temp_dir):
                _write_timestamp("test_api", test_timestamp)
                read_timestamp = _read_timestamp("test_api")
                assert read_timestamp == test_timestamp
    
    def test_onionoo_details_worker_success(self):
        """Test successful onionoo details fetch"""
        mock_response_data = {
            "relays": [{"nickname": "TestRelay", "fingerprint": "ABC123"}],
            "version": "test"
        }
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_response_data).encode()
        mock_response.info.return_value.get.return_value = "Mon, 01 Jan 2024 12:00:00 GMT"
        
        with patch('urllib.request.urlopen', return_value=mock_response):
            with tempfile.TemporaryDirectory() as temp_dir:
                with patch('lib.workers.CACHE_DIR', temp_dir):
                    result = fetch_onionoo_details()
                    assert result == mock_response_data
                    
                    # Verify caching worked
                    cached = _load_cache("onionoo_details")
                    assert cached == mock_response_data
    
    def test_onionoo_details_worker_cache_fallback(self):
        """Test onionoo details worker with cache fallback"""
        cached_data = {"relays": [{"nickname": "CachedRelay"}], "version": "cached"}
        
        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError("Network error")):
            with tempfile.TemporaryDirectory() as temp_dir:
                with patch('lib.workers.CACHE_DIR', temp_dir):
                    # Pre-populate cache
                    _save_cache("onionoo_details", cached_data)
                    
                    result = fetch_onionoo_details()
                    assert result == cached_data
    
    def test_placeholder_workers(self):
        """Test placeholder worker implementations"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('lib.workers.CACHE_DIR', temp_dir):
                # Test onionoo uptime placeholder
                result = fetch_onionoo_uptime()
                assert result is not None
                assert result["version"] == "placeholder"
                assert "relays" in result
                
                # Test collector placeholder
                result = fetch_collector_data()
                assert result is not None
                assert result["version"] == "placeholder" 
                assert "authorities" in result
                
                # Test consensus health placeholder
                result = fetch_consensus_health()
                assert result is not None
                assert result["version"] == "placeholder"
                assert "health_status" in result
    
    def test_coordinator_initialization(self):
        """Test coordinator initialization"""
        coordinator = Coordinator(
            output_dir="./test_output", 
            onionoo_url="https://onionoo.torproject.org/details",
            use_bits=True, 
            progress=True
        )
        
        assert coordinator.output_dir == "./test_output"
        assert coordinator.onionoo_url == "https://onionoo.torproject.org/details"
        assert coordinator.use_bits == True
        assert coordinator.progress == True
        assert coordinator.start_time is not None
        assert isinstance(coordinator.start_time, float)
    
    def test_coordinator_fetch_onionoo_data(self):
        """Test coordinator onionoo data fetching"""
        coordinator = Coordinator("./test", "https://onionoo.torproject.org/details")
        result = coordinator.fetch_onionoo_data()
        
        # Test that we get a dictionary with expected structure
        assert isinstance(result, dict)
        assert 'relays' in result or 'bridges' in result
        print(f"✓ Coordinator fetch test passed - got {type(result)} with keys: {list(result.keys())}")
    
    def test_coordinator_create_relay_set(self):
        """Test coordinator relay set creation"""
        coordinator = Coordinator("./test", "https://onionoo.torproject.org/details")
        
        # Create proper test data with all required fields
        test_data = {
            "relays": [{
                "nickname": "TestRelay",
                "fingerprint": "A1B2C3D4E5F6789012345678901234567890ABCD",
                "or_addresses": ["1.2.3.4:9001"],
                "last_seen": "2023-01-01 12:00:00",
                "first_seen": "2023-01-01 00:00:00",
                "running": True,
                "flags": ["Fast", "Running", "Valid"]
            }]
        }
        
        relay_set = coordinator.create_relay_set(test_data)
        
        # Verify relay set was created successfully
        assert relay_set is not None
        # The relay_set should have the json structure
        assert hasattr(relay_set, 'json')
        print(f"✓ Coordinator relay set creation test passed - created relay set with {len(test_data['relays'])} relay(s)")
    
    def test_backwards_compatibility_function(self):
        """Test backwards compatibility helper function"""
        test_data = {
            "relays": [
                {
                    "nickname": "TestRelay",
                    "fingerprint": "ABC123", 
                    "flags": ["Running", "Valid"],
                    "consensus_weight": 1000,
                    "observed_bandwidth": 500000,
                    "country": "us"
                }
            ]
        }
        
        with patch('lib.workers.fetch_onionoo_details', return_value=test_data):
            with tempfile.TemporaryDirectory() as temp_dir:
                relay_set = create_relay_set_with_coordinator(
                    output_dir=temp_dir,
                    onionoo_url="https://onionoo.torproject.org/details",
                    use_bits=False,
                    progress=False
                )
                assert relay_set is not None
    
    def test_error_handling(self):
        """Test error handling throughout the system"""
        # Test cache error handling
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            with patch('builtins.print') as mock_print:
                _save_cache("test", {"data": "test"})
                mock_print.assert_called_once()
                assert "Warning: Failed to save cache" in mock_print.call_args[0][0]
        
        # Test worker error states
        _mark_stale("error_api", "Test error")
        status = get_worker_status("error_api")
        assert status["status"] == "stale"
        assert status["error"] == "Test error"
    
    def test_cache_performance(self):
        """Test cache performance with larger datasets"""
        large_data = {
            "relays": [
                {
                    "nickname": f"Relay{i}",
                    "fingerprint": f"FP{i:010d}",
                    "observed_bandwidth": i * 1000,
                    "flags": ["Running", "Valid"]
                }
                for i in range(100)
            ],
            "version": "performance_test"
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('lib.workers.CACHE_DIR', temp_dir):
                # Test save performance
                start_time = time.time()
                _save_cache("performance_test", large_data)
                save_time = time.time() - start_time
                assert save_time < 1.0  # Should complete quickly
                
                # Test load performance  
                start_time = time.time()
                loaded_data = _load_cache("performance_test")
                load_time = time.time() - start_time
                assert load_time < 0.5  # Should load quickly
                assert len(loaded_data["relays"]) == 100


class TestPhase1APIIntegration:
    """Test full integration flow for Phase 1 API"""
    
    def setup_method(self):
        """Clear worker status before each test"""
        import lib.workers
        lib.workers._worker_status = {}
    
    def test_full_integration_flow(self):
        """Test complete flow from coordinator to workers to relays"""
        # Test the actual integration without mocking
        coordinator = Coordinator("./test", "https://onionoo.torproject.org/details")
        data = coordinator.fetch_onionoo_data()
        
        # Verify we get real data structure
        assert isinstance(data, dict)
        assert 'relays' in data
        assert isinstance(data['relays'], list)
        
        if len(data['relays']) > 0:
            # Check that relays have expected structure
            sample_relay = data['relays'][0]
            assert 'fingerprint' in sample_relay
            assert 'nickname' in sample_relay
            
        # Test that coordinator can create relay set from this data
        if len(data['relays']) > 0:
            # Take a small sample to avoid performance issues
            sample_data = {
                'relays': data['relays'][:1],  # Just one relay for testing
                'version': data.get('version', ''),
                'build_revision': data.get('build_revision', ''),
                'relays_published': data.get('relays_published', '')
            }
            relay_set = coordinator.create_relay_set(sample_data)
            assert relay_set is not None
            
        print(f"✓ Full integration test passed - processed {len(data['relays'])} relays")
    
    def test_multi_worker_coordination(self):
        """Test coordination of multiple workers"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('lib.workers.CACHE_DIR', temp_dir):
                # Test all placeholder workers
                uptime_result = fetch_onionoo_uptime()
                collector_result = fetch_collector_data() 
                health_result = fetch_consensus_health()
                
                # All should return placeholder data
                assert uptime_result["version"] == "placeholder"
                assert collector_result["version"] == "placeholder"
                assert health_result["version"] == "placeholder"
                
                # Check that all workers are tracked
                all_status = get_all_worker_status()
                assert "onionoo_uptime" in all_status
                assert "collector" in all_status
                assert "consensus_health" in all_status
                
                # All should be ready
                for worker_name in ["onionoo_uptime", "collector", "consensus_health"]:
                    assert all_status[worker_name]["status"] == "ready"


def test_phase1_summary():
    """Summary test ensuring Phase 1 API implementation works end-to-end"""
    print("\n" + "="*60)
    print("🎯 PHASE 1 API IMPLEMENTATION SUMMARY")
    print("="*60)
    
    # Test core components
    core_tests = TestPhase1APICoreFeatures()
    core_tests.setup_method()
    
    try:
        # Test each core feature
        core_tests.test_cache_operations()
        print("✅ Cache Operations: PASS")
        
        core_tests.test_worker_state_management()
        print("✅ Worker State Management: PASS")
        
        core_tests.test_timestamp_operations()
        print("✅ Timestamp Operations: PASS")
        
        core_tests.test_onionoo_details_worker_success()
        print("✅ Onionoo Details Worker: PASS")
        
        core_tests.test_placeholder_workers()
        print("✅ Placeholder Workers: PASS")
        
        core_tests.test_coordinator_initialization()
        print("✅ Coordinator Initialization: PASS")
        
        core_tests.test_coordinator_fetch_onionoo_data()
        print("✅ Coordinator Data Fetching: PASS")
        
        core_tests.test_coordinator_create_relay_set()
        print("✅ Coordinator Relay Set Creation: PASS")
        
        core_tests.test_backwards_compatibility_function()
        print("✅ Backwards Compatibility: PASS")
        
        core_tests.test_error_handling()
        print("✅ Error Handling: PASS")
        
        core_tests.test_cache_performance()
        print("✅ Cache Performance: PASS")
        
        # Test integration
        integration_tests = TestPhase1APIIntegration()
        integration_tests.setup_method()
        
        integration_tests.test_multi_worker_coordination()
        print("✅ Multi-Worker Coordination: PASS")
        
        integration_tests.test_full_integration_flow()
        print("✅ Full Integration Flow: PASS")
        
        print("\n" + "="*60)
        print("🚀 PHASE 1 API IMPLEMENTATION: ALL TESTS PASS")
        print("="*60)
        print("\n📋 IMPLEMENTATION FEATURES VERIFIED:")
        print("   • Multi-API Worker System")
        print("   • Caching with Conditional Requests")
        print("   • State Management & Error Tracking")
        print("   • Coordinator Layer")
        print("   • Backwards Compatibility")
        print("   • Performance & Reliability")
        print("\n🔧 READY FOR PHASE 2: Additional API Integration")
        
    except Exception as e:
        print(f"❌ PHASE 1 TESTS FAILED: {e}")
        raise


if __name__ == "__main__":
    test_phase1_summary()
    pytest.main([__file__])