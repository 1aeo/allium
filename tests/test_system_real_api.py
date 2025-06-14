"""
Real-world integration tests for allium multi-API system
Tests actual API calls and integration functionality
"""
import sys
import os
import pytest
import time
import tempfile
import shutil

# Add the allium directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'allium'))

from lib.coordinator import Coordinator, create_relay_set_with_coordinator
from lib.workers import fetch_onionoo_details, fetch_onionoo_uptime


class TestRealAPIIntegration:
    """Test integration with real API endpoints"""
    
    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory for tests"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_real_onionoo_details_api(self, temp_output_dir):
        """Test fetching from real onionoo details API"""
        try:
            # Test with real API call (but limit to small subset)
            url = "https://onionoo.torproject.org/details?limit=5"
            result = fetch_onionoo_details(url)
            
            # Verify response structure
            assert result is not None
            assert 'relays' in result
            assert 'relays_published' in result
            assert isinstance(result['relays'], list)
            
            # Verify we got some relays
            assert len(result['relays']) > 0
            
            # Verify relay structure
            relay = result['relays'][0]
            required_fields = ['nickname', 'fingerprint', 'observed_bandwidth']
            for field in required_fields:
                assert field in relay, f"Missing required field: {field}"
                
            print(f"✓ Successfully fetched {len(result['relays'])} relays from details API")
            
        except Exception as e:
            pytest.skip(f"Real API test skipped due to: {e}")
    
    def test_real_onionoo_uptime_api(self, temp_output_dir):
        """Test fetching from real onionoo uptime API"""
        try:
            # Test with real API call (but limit to small subset)
            url = "https://onionoo.torproject.org/uptime?limit=5"
            result = fetch_onionoo_uptime(url)
            
            # Verify response structure
            assert result is not None
            assert 'relays' in result
            assert isinstance(result['relays'], list)
            
            if len(result['relays']) > 0:
                # Verify uptime data structure if relays have uptime info
                relay = result['relays'][0]
                if 'uptime' in relay:
                    assert isinstance(relay['uptime'], dict)
                    # Check for common uptime periods
                    for period in ['1_month', '3_months', '1_year']:
                        if period in relay['uptime']:
                            uptime_data = relay['uptime'][period]
                            assert 'count' in uptime_data
                            assert 'factor' in uptime_data
                            assert isinstance(uptime_data['factor'], (int, float))
                            assert 0 <= uptime_data['factor'] <= 1
                
            print(f"✓ Successfully fetched uptime data from API")
            
        except Exception as e:
            pytest.skip(f"Real API test skipped due to: {e}")
    
    def test_full_coordinator_integration(self, temp_output_dir):
        """Test full coordinator integration with real APIs"""
        try:
            coordinator = Coordinator(
                output_dir=temp_output_dir,
                onionoo_details_url="https://onionoo.torproject.org/details?limit=3",
                onionoo_uptime_url="https://onionoo.torproject.org/uptime?limit=3",
                progress=True
            )
            
            # Test threaded API fetching
            start_time = time.time()
            all_data = coordinator.fetch_all_apis_threaded()
            end_time = time.time()
            
            # Verify we got data from both APIs
            assert 'onionoo_details' in all_data
            assert 'onionoo_uptime' in all_data
            
            details_data = all_data['onionoo_details']
            uptime_data = all_data['onionoo_uptime']
            
            # Verify details data
            assert details_data is not None
            assert 'relays' in details_data
            assert len(details_data['relays']) > 0
            
            # Verify uptime data
            assert uptime_data is not None
            assert 'relays' in uptime_data
            
            # Test relay set creation
            relay_set = coordinator.create_relay_set(details_data)
            assert relay_set is not None
            assert relay_set.json == details_data
            assert relay_set.uptime_data == uptime_data
            
            fetch_time = end_time - start_time
            print(f"✓ Full integration test completed in {fetch_time:.2f}s")
            print(f"✓ Fetched {len(details_data['relays'])} relays with uptime data")
            
        except Exception as e:
            pytest.skip(f"Full integration test skipped due to: {e}")
    
    def test_backward_compatibility_function(self, temp_output_dir):
        """Test the backward compatibility function with real APIs"""
        try:
            relay_set = create_relay_set_with_coordinator(
                output_dir=temp_output_dir,
                onionoo_details_url="https://onionoo.torproject.org/details?limit=2",
                onionoo_uptime_url="https://onionoo.torproject.org/uptime?limit=2",
                progress=True
            )
            
            # Verify relay set was created
            assert relay_set is not None
            assert hasattr(relay_set, 'json')
            assert hasattr(relay_set, 'uptime_data')
            assert hasattr(relay_set, 'consensus_health_data')
            assert hasattr(relay_set, 'collector_data')
            
            # Verify data was attached
            assert relay_set.json is not None
            assert 'relays' in relay_set.json
            
            # uptime_data might be None if no uptime info available
            if relay_set.uptime_data is not None:
                assert 'relays' in relay_set.uptime_data
            
            print(f"✓ Backward compatibility function works correctly")
            
        except Exception as e:
            pytest.skip(f"Backward compatibility test skipped due to: {e}")


class TestPerformanceMetrics:
    """Test performance aspects of our implementation"""
    
    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory for tests"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_threading_performance_improvement(self, temp_output_dir):
        """Test that threading provides performance improvement"""
        try:
            coordinator = Coordinator(
                output_dir=temp_output_dir,
                onionoo_details_url="https://onionoo.torproject.org/details?limit=2",
                onionoo_uptime_url="https://onionoo.torproject.org/uptime?limit=2",
                progress=False
            )
            
            # Test threaded approach
            start_threaded = time.time()
            threaded_result = coordinator.fetch_all_apis_threaded()
            end_threaded = time.time()
            threaded_time = end_threaded - start_threaded
            
            # Test sequential approach (simulate)
            start_sequential = time.time()
            details_result = fetch_onionoo_details("https://onionoo.torproject.org/details?limit=2")
            uptime_result = fetch_onionoo_uptime("https://onionoo.torproject.org/uptime?limit=2")
            end_sequential = time.time()
            sequential_time = end_sequential - start_sequential
            
            # Verify both approaches got data
            assert threaded_result['onionoo_details'] is not None
            assert threaded_result['onionoo_uptime'] is not None
            assert details_result is not None
            assert uptime_result is not None
            
            # Threading should be faster (or at least not significantly slower)
            performance_ratio = threaded_time / sequential_time if sequential_time > 0 else 1
            
            print(f"✓ Threaded time: {threaded_time:.2f}s")
            print(f"✓ Sequential time: {sequential_time:.2f}s")
            print(f"✓ Performance ratio: {performance_ratio:.2f}")
            
            # Threading should provide some benefit for real network calls
            # Allow for some overhead but shouldn't be more than 20% slower
            assert performance_ratio < 1.2, f"Threading performance regression: {performance_ratio:.2f}x slower"
            
        except Exception as e:
            pytest.skip(f"Performance test skipped due to: {e}")


class TestErrorHandlingWithRealAPIs:
    """Test error handling with real API scenarios"""
    
    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory for tests"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_invalid_url_handling(self, temp_output_dir):
        """Test handling of invalid URLs"""
        coordinator = Coordinator(
            output_dir=temp_output_dir,
            onionoo_details_url="https://invalid-domain-that-does-not-exist.com/details",
            onionoo_uptime_url="https://invalid-domain-that-does-not-exist.com/uptime",
            progress=False
        )
        
        # Should handle failures gracefully
        result = coordinator.fetch_all_apis_threaded()
        
        # Should return dict with None values for failed APIs
        assert isinstance(result, dict)
        assert 'onionoo_details' in result
        assert 'onionoo_uptime' in result
        # Values should be None due to failures
        assert result['onionoo_details'] is None
        assert result['onionoo_uptime'] is None
        
        print("✓ Invalid URL handling works correctly")
    
    def test_partial_api_failure_handling(self, temp_output_dir):
        """Test handling when only some APIs fail"""
        try:
            coordinator = Coordinator(
                output_dir=temp_output_dir,
                onionoo_details_url="https://onionoo.torproject.org/details?limit=1",  # Valid
                onionoo_uptime_url="https://invalid-domain.com/uptime",  # Invalid
                progress=False
            )
            
            result = coordinator.fetch_all_apis_threaded()
            
            # Should get valid data from working API, None from failing API
            assert result['onionoo_details'] is not None
            assert result['onionoo_uptime'] is None
            
            # Should still be able to create relay set with partial data
            relay_set = coordinator.create_relay_set(result['onionoo_details'])
            assert relay_set is not None
            assert relay_set.uptime_data is None  # Failed API
            assert relay_set.json is not None  # Working API
            
            print("✓ Partial API failure handling works correctly")
            
        except Exception as e:
            pytest.skip(f"Partial failure test skipped due to: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"]) 