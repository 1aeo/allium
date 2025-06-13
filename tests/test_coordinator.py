"""
Unit tests for allium/lib/coordinator.py - Phase 1 API coordination system
"""
import json
import os
import pytest
import sys
import tempfile
import time
from unittest.mock import patch, MagicMock

# Add the allium directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'allium'))

from lib.coordinator import Coordinator, create_relay_set_with_coordinator


class TestCoordinator:
    """Test the main Coordinator class"""
    
    def test_coordinator_initialization(self):
        """Test coordinator initialization with all parameters"""
        output_dir = "./test_output"
        onionoo_url = "https://test.onionoo.torproject.org/details"
        use_bits = True
        progress = True
        start_time = time.time()
        progress_step = 5
        total_steps = 20
        
        coordinator = Coordinator(
            output_dir=output_dir,
            onionoo_url=onionoo_url,
            use_bits=use_bits,
            progress=progress,
            start_time=start_time,
            progress_step=progress_step,
            total_steps=total_steps
        )
        
        assert coordinator.output_dir == output_dir
        assert coordinator.onionoo_url == onionoo_url
        assert coordinator.use_bits == use_bits
        assert coordinator.progress == progress
        assert coordinator.start_time == start_time
        assert coordinator.progress_step == progress_step
        assert coordinator.total_steps == total_steps
        assert coordinator.workers == {}
        assert coordinator.worker_data == {}
    
    def test_coordinator_default_initialization(self):
        """Test coordinator with default parameters"""
        coordinator = Coordinator("./output", "https://test.url")
        
        assert coordinator.output_dir == "./output"
        assert coordinator.onionoo_url == "https://test.url"
        assert coordinator.use_bits is False
        assert coordinator.progress is False
        assert coordinator.progress_step == 0
        assert coordinator.total_steps == 20
        assert isinstance(coordinator.start_time, float)
    
    def test_log_progress_with_progress_enabled(self):
        """Test progress logging when progress is enabled"""
        coordinator = Coordinator("./output", "https://test.url", progress=True)
        
        with patch('builtins.print') as mock_print:
            coordinator._log_progress("Test message")
            
            mock_print.assert_called_once()
            call_args = mock_print.call_args[0][0]
            assert "Test message" in call_args
            assert "Progress:" in call_args
    
    def test_log_progress_with_progress_disabled(self):
        """Test that progress logging is silent when progress is disabled"""
        coordinator = Coordinator("./output", "https://test.url", progress=False)
        
        with patch('builtins.print') as mock_print:
            coordinator._log_progress("Test message")
            
            mock_print.assert_not_called()
    
    def test_fetch_onionoo_data_success(self):
        """Test successful onionoo data fetching"""
        mock_data = {
            "relays": [
                {"nickname": "test1", "fingerprint": "ABC123"},
                {"nickname": "test2", "fingerprint": "DEF456"}
            ],
            "version": "1.0"
        }
        
        coordinator = Coordinator("./output", "https://test.url", progress=True)
        
        with patch('lib.coordinator.fetch_onionoo_details', return_value=mock_data) as mock_fetch:
            with patch('builtins.print') as mock_print:
                result = coordinator.fetch_onionoo_data()
                
                assert result == mock_data
                mock_fetch.assert_called_once_with("https://test.url")
                
                # Check progress messages
                assert any("Fetching onionoo data using workers system" in str(call) for call in mock_print.call_args_list)
                assert any("Successfully fetched 2 relays from onionoo" in str(call) for call in mock_print.call_args_list)
    
    def test_fetch_onionoo_data_failure(self):
        """Test onionoo data fetching failure"""
        coordinator = Coordinator("./output", "https://test.url", progress=True)
        
        with patch('lib.coordinator.fetch_onionoo_details', return_value=None) as mock_fetch:
            with patch('builtins.print') as mock_print:
                result = coordinator.fetch_onionoo_data()
                
                assert result is None
                mock_fetch.assert_called_once_with("https://test.url")
                
                # Check error message
                assert any("Failed to fetch onionoo data" in str(call) for call in mock_print.call_args_list)
    
    def test_fetch_onionoo_data_exception(self):
        """Test onionoo data fetching with exception"""
        coordinator = Coordinator("./output", "https://test.url", progress=True)
        
        with patch('lib.coordinator.fetch_onionoo_details', side_effect=Exception("Network error")) as mock_fetch:
            with patch('builtins.print') as mock_print:
                result = coordinator.fetch_onionoo_data()
                
                assert result is None
                mock_fetch.assert_called_once_with("https://test.url")
                
                # Check error message
                assert any("Error fetching onionoo data: Network error" in str(call) for call in mock_print.call_args_list)
    
    def test_create_relay_set_success(self):
        """Test successful relay set creation"""
        mock_data = {
            "relays": [{"nickname": "test1"}],
            "version": "1.0"
        }
        
        coordinator = Coordinator("./output", "https://test.url", progress=True, use_bits=True)
        
        # Mock the Relays class
        mock_relay_set = MagicMock()
        mock_relay_set.json = mock_data
        
        with patch('lib.coordinator.Relays', return_value=mock_relay_set) as mock_relays:
            with patch('builtins.print') as mock_print:
                result = coordinator.create_relay_set(mock_data)
                
                assert result == mock_relay_set
                
                # Check that Relays was called with correct parameters
                mock_relays.assert_called_once_with(
                    output_dir="./output",
                    onionoo_url="https://test.url",
                    use_bits=True,
                    progress=True,
                    start_time=coordinator.start_time,
                    progress_step=0,
                    total_steps=20,
                    relay_data=mock_data
                )
                
                # Check progress messages
                assert any("Creating relay set with fetched data" in str(call) for call in mock_print.call_args_list)
                assert any("Relay set created successfully" in str(call) for call in mock_print.call_args_list)
    
    def test_create_relay_set_failure(self):
        """Test relay set creation failure"""
        mock_data = {"relays": []}
        
        coordinator = Coordinator("./output", "https://test.url", progress=True)
        
        # Mock the Relays class to return None json
        mock_relay_set = MagicMock()
        mock_relay_set.json = None
        
        with patch('lib.coordinator.Relays', return_value=mock_relay_set):
            with patch('builtins.print') as mock_print:
                result = coordinator.create_relay_set(mock_data)
                
                assert result is None
                
                # Check error message
                assert any("Failed to create relay set" in str(call) for call in mock_print.call_args_list)
    
    def test_get_relay_set_full_flow_success(self):
        """Test the complete get_relay_set flow"""
        mock_data = {
            "relays": [{"nickname": "test1"}],
            "version": "1.0"
        }
        
        coordinator = Coordinator("./output", "https://test.url")
        
        mock_relay_set = MagicMock()
        mock_relay_set.json = mock_data
        
        with patch.object(coordinator, 'fetch_onionoo_data', return_value=mock_data) as mock_fetch:
            with patch.object(coordinator, 'create_relay_set', return_value=mock_relay_set) as mock_create:
                result = coordinator.get_relay_set()
                
                assert result == mock_relay_set
                mock_fetch.assert_called_once()
                mock_create.assert_called_once_with(mock_data)
    
    def test_get_relay_set_fetch_failure(self):
        """Test get_relay_set when data fetching fails"""
        coordinator = Coordinator("./output", "https://test.url")
        
        with patch.object(coordinator, 'fetch_onionoo_data', return_value=None) as mock_fetch:
            with patch.object(coordinator, 'create_relay_set') as mock_create:
                result = coordinator.get_relay_set()
                
                assert result is None
                mock_fetch.assert_called_once()
                mock_create.assert_not_called()
    
    def test_get_worker_status_summary(self):
        """Test getting worker status summary"""
        mock_status = {
            "worker1": {"status": "ready", "timestamp": time.time(), "error": None},
            "worker2": {"status": "stale", "timestamp": time.time(), "error": "Test error"},
            "worker3": {"status": "ready", "timestamp": time.time(), "error": None}
        }
        
        coordinator = Coordinator("./output", "https://test.url")
        
        with patch('lib.coordinator.get_all_worker_status', return_value=mock_status):
            summary = coordinator.get_worker_status_summary()
            
            assert summary["worker_count"] == 3
            assert summary["ready_count"] == 2
            assert summary["stale_count"] == 1
            assert summary["workers"] == mock_status
    
    def test_get_worker_status_summary_empty(self):
        """Test worker status summary with no workers"""
        coordinator = Coordinator("./output", "https://test.url")
        
        with patch('lib.coordinator.get_all_worker_status', return_value={}):
            summary = coordinator.get_worker_status_summary()
            
            assert summary["worker_count"] == 0
            assert summary["ready_count"] == 0
            assert summary["stale_count"] == 0
            assert summary["workers"] == {}


class TestBackwardsCompatibility:
    """Test backwards compatibility functions"""
    
    def test_create_relay_set_with_coordinator_success(self):
        """Test backwards compatibility function with successful execution"""
        mock_data = {
            "relays": [{"nickname": "test1"}],
            "version": "1.0"
        }
        
        mock_relay_set = MagicMock()
        mock_relay_set.json = mock_data
        
        # Mock the entire coordinator chain
        mock_coordinator = MagicMock()
        mock_coordinator.get_relay_set.return_value = mock_relay_set
        
        with patch('lib.coordinator.Coordinator', return_value=mock_coordinator) as mock_coordinator_class:
            result = create_relay_set_with_coordinator(
                output_dir="./test_output",
                onionoo_url="https://test.url",
                use_bits=True,
                progress=True,
                start_time=123456,
                progress_step=5,
                total_steps=25
            )
            
            assert result == mock_relay_set
            
            # Check that coordinator was created with correct parameters
            mock_coordinator_class.assert_called_once_with(
                output_dir="./test_output",
                onionoo_url="https://test.url",
                use_bits=True,
                progress=True,
                start_time=123456,
                progress_step=5,
                total_steps=25
            )
            
            # Check that get_relay_set was called
            mock_coordinator.get_relay_set.assert_called_once()
    
    def test_create_relay_set_with_coordinator_failure(self):
        """Test backwards compatibility function with failure"""
        mock_coordinator = MagicMock()
        mock_coordinator.get_relay_set.return_value = None
        
        with patch('lib.coordinator.Coordinator', return_value=mock_coordinator):
            result = create_relay_set_with_coordinator("./output", "https://test.url")
            
            assert result is None
    
    def test_create_relay_set_with_coordinator_default_params(self):
        """Test backwards compatibility function with default parameters"""
        mock_relay_set = MagicMock()
        mock_coordinator = MagicMock()
        mock_coordinator.get_relay_set.return_value = mock_relay_set
        
        with patch('lib.coordinator.Coordinator', return_value=mock_coordinator) as mock_coordinator_class:
            result = create_relay_set_with_coordinator("./output", "https://test.url")
            
            assert result == mock_relay_set
            
            # Check default parameters
            call_args = mock_coordinator_class.call_args
            kwargs = call_args[1]
            assert kwargs['use_bits'] is False
            assert kwargs['progress'] is False
            assert kwargs['progress_step'] == 0
            assert kwargs['total_steps'] == 20
            assert isinstance(kwargs['start_time'], float)


class TestCoordinatorIntegration:
    """Test coordinator integration with real worker functions"""
    
    def test_coordinator_with_real_workers(self):
        """Test coordinator using actual worker functions (with mocking)"""
        mock_data = {
            "relays": [
                {"nickname": "TestRelay1", "fingerprint": "ABC123"},
                {"nickname": "TestRelay2", "fingerprint": "DEF456"}
            ],
            "version": "1.0"
        }
        
        coordinator = Coordinator("./test_output", "https://test.url", progress=True)
        
        # Mock urllib request to return test data
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_data).encode('utf-8')
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('lib.workers.CACHE_DIR', temp_dir):
                with patch('lib.workers.STATE_FILE', os.path.join(temp_dir, 'state.json')):
                    with patch('urllib.request.urlopen', return_value=mock_response):
                        with patch('builtins.print') as mock_print:
                            # Test fetching data
                            data = coordinator.fetch_onionoo_data()
                            
                            assert data == mock_data
                            assert len(data["relays"]) == 2
                            
                            # Check that progress was logged
                            progress_calls = [str(call) for call in mock_print.call_args_list]
                            assert any("Fetching onionoo data using workers system" in call for call in progress_calls)
                            assert any("Successfully fetched 2 relays from onionoo" in call for call in progress_calls)
    
    def test_coordinator_error_recovery(self):
        """Test coordinator behavior during worker errors"""
        coordinator = Coordinator("./test_output", "https://test.url", progress=True)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('lib.workers.CACHE_DIR', temp_dir):
                with patch('lib.workers.STATE_FILE', os.path.join(temp_dir, 'state.json')):
                    # Simulate network error
                    with patch('urllib.request.urlopen', side_effect=ConnectionError("Network error")):
                        with patch('builtins.print'):
                            data = coordinator.fetch_onionoo_data()
                            
                            assert data is None
                            
                            # Check worker status
                            from lib.workers import get_worker_status
                            status = get_worker_status("onionoo_details")
                            assert status["status"] == "stale"
                            assert "Network error" in status["error"]


class TestCoordinatorProgressLogging:
    """Test coordinator progress logging functionality"""
    
    def test_progress_logging_format(self):
        """Test that progress logging follows the expected format"""
        coordinator = Coordinator("./output", "https://test.url", progress=True, start_time=time.time())
        
        with patch('builtins.print') as mock_print:
            coordinator._log_progress("Test progress message")
            
            mock_print.assert_called_once()
            log_message = mock_print.call_args[0][0]
            
            # Check format: [HH:MM:SS] [step/total] [Memory: ...] Progress: message
            assert "[" in log_message and "]" in log_message  # Time format
            assert "Progress: Test progress message" in log_message
            assert "[0/20]" in log_message  # Default step/total
    
    def test_progress_logging_memory_error_fallback(self):
        """Test progress logging fallback when memory info is unavailable"""
        coordinator = Coordinator("./output", "https://test.url", progress=True)
        
        # Mock resource module to raise an exception
        with patch('resource.getrusage', side_effect=Exception("Memory unavailable")):
            with patch('builtins.print') as mock_print:
                coordinator._log_progress("Test message")
                
                mock_print.assert_called_once()
                log_message = mock_print.call_args[0][0]
                
                assert "Progress: Test message" in log_message
                assert "[Memory: unavailable (Memory unavailable)]" in log_message


class TestCoordinatorEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_coordinator_with_none_start_time(self):
        """Test coordinator when start_time is None"""
        coordinator = Coordinator("./output", "https://test.url", start_time=None)
        
        assert isinstance(coordinator.start_time, float)
        assert coordinator.start_time > 0
    
    def test_coordinator_with_invalid_parameters(self):
        """Test coordinator with edge case parameters"""
        # Test with empty strings
        coordinator = Coordinator("", "", progress_step=-1, total_steps=0)
        
        assert coordinator.output_dir == ""
        assert coordinator.onionoo_url == ""
        assert coordinator.progress_step == -1
        assert coordinator.total_steps == 0
    
    def test_create_relay_set_with_empty_data(self):
        """Test creating relay set with empty data"""
        coordinator = Coordinator("./output", "https://test.url")
        
        mock_relay_set = MagicMock()
        mock_relay_set.json = {"relays": []}
        
        with patch('lib.coordinator.Relays', return_value=mock_relay_set):
            result = coordinator.create_relay_set({"relays": []})
            
            assert result == mock_relay_set


if __name__ == "__main__":
    pytest.main([__file__])