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
sys.path.insert(0, '../allium')

# Import using direct lib paths (same approach as working tests)
from lib.coordinator import Coordinator, create_relay_set_with_coordinator
from lib.workers import fetch_onionoo_details, fetch_onionoo_uptime


class TestErrorHandlingWithRealAPIs:
    """Test error handling with real API endpoints"""
    
    def test_invalid_url_handling(self):
        """Test handling of invalid URLs in coordinator"""
        # Test that invalid URLs are handled gracefully
        invalid_details_url = "http://invalid.nonexistent.url/details"
        invalid_uptime_url = "http://invalid.nonexistent.url/uptime"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            coordinator = Coordinator(
                output_dir=temp_dir,
                onionoo_details_url=invalid_details_url,
                onionoo_uptime_url=invalid_uptime_url,
                progress=False
            )
            
            # Should handle invalid URLs gracefully without crashing
            try:
                result = coordinator.get_relay_set()
                # If we get a result, it should either be None or have proper structure
                if result is not None:
                    assert hasattr(result, 'json') or isinstance(result, dict)
            except Exception as e:
                # Should handle network errors gracefully
                assert "Network" in str(e) or "URL" in str(e) or "Connection" in str(e)


if __name__ == "__main__":
    pytest.main([__file__]) 