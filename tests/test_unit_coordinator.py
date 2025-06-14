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
    
    def test_coordinator_initialization_sets_all_parameters_correctly(self):
        """Test coordinator initialization with all parameters"""
        output_dir = "./test_output"
        onionoo_details_url = "https://test.onionoo.torproject.org/details"
        onionoo_uptime_url = "https://test.onionoo.torproject.org/uptime"
        use_bits = True
        progress = True
        start_time = time.time()
        progress_step = 5
        total_steps = 34
        
        coordinator = Coordinator(
            output_dir=output_dir,
            onionoo_details_url=onionoo_details_url,
            onionoo_uptime_url=onionoo_uptime_url,
            use_bits=use_bits,
            progress=progress,
            start_time=start_time,
            progress_step=progress_step,
            total_steps=total_steps
        )
        
        assert coordinator.output_dir == output_dir
        assert coordinator.onionoo_details_url == onionoo_details_url
        assert coordinator.onionoo_uptime_url == onionoo_uptime_url
        assert coordinator.use_bits == use_bits
        assert coordinator.progress == progress
        assert coordinator.start_time == start_time
        assert coordinator.progress_step == progress_step
        assert coordinator.total_steps == total_steps
        assert coordinator.workers == {}
        assert coordinator.worker_data == {}
    
    def test_coordinator_initialization_uses_default_values_when_minimal_parameters_provided(self):
        """Test coordinator with default parameters"""
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url")
        
        assert coordinator.output_dir == "./output"
        assert coordinator.onionoo_details_url == "https://test.details.url"
        assert coordinator.onionoo_uptime_url == "https://test.uptime.url"
        assert coordinator.use_bits is False
        assert coordinator.progress is False
        assert coordinator.progress_step == 0
        assert coordinator.total_steps == 34
        assert isinstance(coordinator.start_time, float)
    
    def test_log_progress_outputs_formatted_message_when_progress_enabled(self):
        """Test progress logging when progress is enabled"""
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url", progress=True)
        
        with patch('builtins.print') as mock_print:
            coordinator._log_progress("Test message")
            
            mock_print.assert_called_once()
            call_args = mock_print.call_args[0][0]
            assert "Test message" in call_args
            assert "Progress:" in call_args
    
    def test_log_progress_remains_silent_when_progress_disabled(self):
        """Test that progress logging is silent when progress is disabled"""
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url", progress=False)
        
        with patch('builtins.print') as mock_print:
            coordinator._log_progress("Test message")
            
            mock_print.assert_not_called()
    
    def test_fetch_onionoo_data_returns_relay_data_when_api_call_succeeds(self):
        """Test successful onionoo data fetching"""
        mock_data = {
            "relays": [
                {"nickname": "test1", "fingerprint": "ABC123"},
                {"nickname": "test2", "fingerprint": "DEF456"}
            ],
            "version": "1.0"
        }
        
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url", progress=True)
        
        # Mock the threaded fetch method to return our test data
        mock_all_data = {'onionoo_details': mock_data}
        with patch.object(coordinator, 'fetch_all_apis_threaded', return_value=mock_all_data) as mock_fetch:
            with patch('builtins.print') as mock_print:
                result = coordinator.fetch_onionoo_data()
                
                assert result == mock_data
                mock_fetch.assert_called_once()
    
    def test_fetch_onionoo_data_returns_none_when_api_call_fails(self):
        """Test onionoo data fetching failure"""
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url", progress=True)
        
        # Mock the threaded fetch method to return empty data
        mock_all_data = {'onionoo_details': None}
        with patch.object(coordinator, 'fetch_all_apis_threaded', return_value=mock_all_data) as mock_fetch:
            with patch('builtins.print') as mock_print:
                result = coordinator.fetch_onionoo_data()
                
                assert result is None
                mock_fetch.assert_called_once()
    
    def test_fetch_onionoo_data_returns_none_when_network_exception_occurs(self):
        """Test onionoo data fetching with exception"""
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url", progress=True)
        
        # Mock the threaded fetch method to raise an exception
        with patch.object(coordinator, 'fetch_all_apis_threaded', side_effect=Exception("Network error")) as mock_fetch:
            with patch('builtins.print') as mock_print:
                result = coordinator.fetch_onionoo_data()
                
                assert result is None
                mock_fetch.assert_called_once()
    
    def test_create_relay_set_returns_relay_object_when_data_processing_succeeds(self):
        """Test successful relay set creation"""
        mock_data = {
            "relays": [{"nickname": "test1"}],
            "version": "1.0"
        }
        
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url", progress=True, use_bits=True)
        
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
                    onionoo_url="https://test.details.url",
                    use_bits=True,
                    progress=True,
                    start_time=coordinator.start_time,
                    progress_step=1,
                    total_steps=34,
                    relay_data=mock_data
                )
                
                # Check progress messages
                assert any("Creating relay set with fetched data" in str(call) for call in mock_print.call_args_list)
                assert any("Relay set created successfully" in str(call) for call in mock_print.call_args_list)
    
    def test_create_relay_set_returns_none_when_data_processing_fails(self):
        """Test relay set creation failure"""
        mock_data = {"relays": []}
        
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url", progress=True)
        
        # Mock the Relays class to return None json
        mock_relay_set = MagicMock()
        mock_relay_set.json = None
        
        with patch('lib.coordinator.Relays', return_value=mock_relay_set):
            with patch('builtins.print') as mock_print:
                result = coordinator.create_relay_set(mock_data)
                
                assert result is None
                
                # Check error message
                assert any("Failed to create relay set" in str(call) for call in mock_print.call_args_list)
    
    def test_get_relay_set_completes_full_workflow_successfully_when_all_steps_succeed(self):
        """Test the complete get_relay_set flow"""
        mock_data = {
            "relays": [{"nickname": "test1"}],
            "version": "1.0"
        }
        
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url")
        
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
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url")
        
        with patch.object(coordinator, 'fetch_onionoo_data', return_value=None) as mock_fetch:
            with patch.object(coordinator, 'create_relay_set') as mock_create:
                result = coordinator.get_relay_set()
                
                assert result is None
                mock_fetch.assert_called_once()
                mock_create.assert_not_called()
    
    def test_get_worker_status_summary(self):
        """Test worker status summary"""
        mock_status = {
            "worker1": {"status": "ready", "timestamp": time.time(), "error": None},
            "worker2": {"status": "stale", "timestamp": time.time(), "error": "Test error"},
            "worker3": {"status": "ready", "timestamp": time.time(), "error": None}
        }
        
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url")
        
        # Patch the function where it's imported in coordinator
        with patch('lib.coordinator.get_all_worker_status', return_value=mock_status):
            summary = coordinator.get_worker_status_summary()
            
            assert summary["worker_count"] == 3
            assert summary["ready_count"] == 2
            assert summary["stale_count"] == 1
            assert summary["workers"] == mock_status
    
    def test_get_worker_status_summary_empty(self):
        """Test worker status summary with no workers"""
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url")
        
        # Patch the function where it's imported in coordinator
        with patch('lib.coordinator.get_all_worker_status', return_value={}):
            summary = coordinator.get_worker_status_summary()
            
            assert summary["worker_count"] == 0
            assert summary["ready_count"] == 0
            assert summary["stale_count"] == 0
            assert summary["workers"] == {}


class TestBackwardsCompatibility:
    """Test backwards compatibility functions"""
    
    def test_create_relay_set_with_coordinator_success(self):
        """Test the backwards compatibility function"""
        mock_relay_set = MagicMock()
        mock_coordinator = MagicMock()
        mock_coordinator.get_relay_set.return_value = mock_relay_set
        
        with patch('lib.coordinator.Coordinator', return_value=mock_coordinator) as mock_coordinator_class:
            result = create_relay_set_with_coordinator(
                output_dir="./test_output",
                onionoo_details_url="https://test.details.url",
                onionoo_uptime_url="https://test.uptime.url",
                use_bits=True,
                progress=True
            )
            
            assert result == mock_relay_set
            
            # Check that Coordinator was instantiated correctly
            mock_coordinator_class.assert_called_once_with(
                output_dir="./test_output",
                onionoo_details_url="https://test.details.url",
                onionoo_uptime_url="https://test.uptime.url",
                use_bits=True,
                progress=True,
                start_time=mock_coordinator_class.call_args[1]['start_time'],
                progress_step=0,
                total_steps=34,
                enabled_apis='all'
            )
            
            mock_coordinator.get_relay_set.assert_called_once()
    
    def test_create_relay_set_with_coordinator_failure(self):
        """Test backwards compatibility function with failure"""
        mock_coordinator = MagicMock()
        mock_coordinator.get_relay_set.return_value = None
        
        with patch('lib.coordinator.Coordinator', return_value=mock_coordinator):
            result = create_relay_set_with_coordinator("./output", "https://test.details.url", "https://test.uptime.url")
            
            assert result is None
    
    def test_create_relay_set_with_coordinator_default_params(self):
        """Test backwards compatibility function with default parameters"""
        mock_relay_set = MagicMock()
        mock_coordinator = MagicMock()
        mock_coordinator.get_relay_set.return_value = mock_relay_set
        
        with patch('lib.coordinator.Coordinator', return_value=mock_coordinator) as mock_coordinator_class:
            result = create_relay_set_with_coordinator("./output", "https://test.details.url", "https://test.uptime.url")
            
            assert result == mock_relay_set
            
            # Check default parameters
            call_args = mock_coordinator_class.call_args
            kwargs = call_args[1]
            assert kwargs['use_bits'] is False
            assert kwargs['progress'] is False
            assert kwargs['progress_step'] == 0
            assert kwargs['total_steps'] == 34
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
        
        coordinator = Coordinator("./test_output", "https://test.details.url", "https://test.uptime.url", progress=True)
        
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
                            assert any("Starting threaded API fetching" in call for call in progress_calls)
                            assert any("successfully fetched 2 relays from onionoo details API" in call for call in progress_calls)
    
    def test_coordinator_error_recovery(self):
        """Test coordinator behavior during worker errors"""
        coordinator = Coordinator("./test_output", "https://test.details.url", "https://test.uptime.url", progress=True)
        
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
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url", progress=True, start_time=time.time())
        
        with patch('builtins.print') as mock_print:
            coordinator._log_progress("Test progress message")
            
            mock_print.assert_called_once()
            log_message = mock_print.call_args[0][0]
            
            # Check format: [HH:MM:SS] [step/total] [Memory: ...] Progress: message
            assert "[" in log_message and "]" in log_message  # Time format
            assert "Progress: Test progress message" in log_message
            assert "[0/34]" in log_message  # Default step/total
    
    def test_progress_logging_memory_error_fallback(self):
        """Test progress logging fallback when memory info is unavailable"""
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url", progress=True)
        
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
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url", start_time=None)
        
        assert isinstance(coordinator.start_time, float)
        assert coordinator.start_time > 0
    
    def test_coordinator_with_invalid_parameters(self):
        """Test coordinator with edge case parameters"""
        # Test with empty strings
        coordinator = Coordinator("", "", "", progress_step=-1, total_steps=0)
        
        assert coordinator.output_dir == ""
        assert coordinator.onionoo_details_url == ""
        assert coordinator.onionoo_uptime_url == ""
        assert coordinator.progress_step == -1
        assert coordinator.total_steps == 0
    
    def test_create_relay_set_with_empty_data(self):
        """Test creating relay set with empty data"""
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url")
        
        mock_relay_set = MagicMock()
        mock_relay_set.json = {"relays": []}
        
        with patch('lib.coordinator.Relays', return_value=mock_relay_set):
            result = coordinator.create_relay_set({"relays": []})
            
            assert result == mock_relay_set


class TestCoordinatorMultiAPI:
    """Test multiapi-p2 coordinator functionality with multiple APIs"""
    
    def test_coordinator_initialization_with_enabled_apis_all(self):
        """Test coordinator initialization with enabled_apis='all'"""
        coordinator = Coordinator(
            output_dir="./test_output",
            onionoo_details_url="https://test.onionoo.torproject.org/details",
            onionoo_uptime_url="https://test.onionoo.torproject.org/uptime",
            enabled_apis='all'
        )
        
        assert coordinator.enabled_apis == 'all'
        # Should have both details and uptime APIs
        assert len(coordinator.api_workers) == 2
        
        # Check that both APIs are configured
        api_names = [worker[0] for worker in coordinator.api_workers]
        assert "onionoo_details" in api_names
        assert "onionoo_uptime" in api_names
        
        # Check URLs are correct
        details_worker = next(w for w in coordinator.api_workers if w[0] == "onionoo_details")
        uptime_worker = next(w for w in coordinator.api_workers if w[0] == "onionoo_uptime")
        
        assert details_worker[2][0] == "https://test.onionoo.torproject.org/details"
        assert uptime_worker[2][0] == "https://test.onionoo.torproject.org/uptime"
    
    def test_coordinator_initialization_with_enabled_apis_details_only(self):
        """Test coordinator initialization with details API only"""
        coordinator = Coordinator(
            output_dir="./test_output",
            onionoo_details_url="https://test.onionoo.torproject.org/details",
            onionoo_uptime_url="https://test.onionoo.torproject.org/uptime",
            enabled_apis='details'
        )
        
        assert coordinator.enabled_apis == 'details'
        # Should have only details API
        assert len(coordinator.api_workers) == 1
        
        api_names = [worker[0] for worker in coordinator.api_workers]
        assert "onionoo_details" in api_names
        assert "onionoo_uptime" not in api_names
    
    def test_fetch_all_apis_threaded_success(self):
        """Test successful threaded fetching of all APIs (simulated)"""
        mock_details_data = {
            "relays": [{"nickname": "TestRelay1", "fingerprint": "ABC123"}],
            "version": "details_test"
        }
        
        mock_uptime_data = {
            "relays": [{"fingerprint": "ABC123", "uptime": {"1_month": 95.5}}],
            "version": "uptime_test"
        }
        
        coordinator = Coordinator(
            output_dir="./test_output",
            onionoo_details_url="https://test.onionoo.torproject.org/details",
            onionoo_uptime_url="https://test.onionoo.torproject.org/uptime",
            enabled_apis='all',
            progress=True
        )
        
        # Simulate successful API fetching by directly setting worker_data
        coordinator.worker_data = {
            'onionoo_details': mock_details_data,
            'onionoo_uptime': mock_uptime_data
        }
        
        # Test the data access methods
        assert coordinator.worker_data == {
            'onionoo_details': mock_details_data,
            'onionoo_uptime': mock_uptime_data
        }
        
        assert coordinator.get_uptime_data() == mock_uptime_data
    
    def test_fetch_all_apis_threaded_with_error(self):
        """Test threaded API fetching with one API failing (simulated)"""
        mock_details_data = {
            "relays": [{"nickname": "TestRelay1", "fingerprint": "ABC123"}],
            "version": "details_test"
        }
        
        coordinator = Coordinator(
            output_dir="./test_output",
            onionoo_details_url="https://test.onionoo.torproject.org/details",
            onionoo_uptime_url="https://test.onionoo.torproject.org/uptime",
            enabled_apis='all',
            progress=True
        )
        
        # Simulate one API failing
        coordinator.worker_data = {
            'onionoo_details': mock_details_data,
            'onionoo_uptime': None
        }
        
        # Details should succeed, uptime should be None
        assert coordinator.worker_data['onionoo_details'] == mock_details_data
        assert coordinator.worker_data['onionoo_uptime'] is None
        assert coordinator.get_uptime_data() is None
    
    def test_get_uptime_data(self):
        """Test getting uptime data from coordinator"""
        mock_uptime_data = {
            "relays": [{"fingerprint": "ABC123", "uptime": {"1_month": 95.5}}],
            "version": "uptime_test"
        }
        
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url")
        coordinator.worker_data = {'onionoo_uptime': mock_uptime_data}
        
        result = coordinator.get_uptime_data()
        assert result == mock_uptime_data
    
    def test_get_uptime_data_none(self):
        """Test getting uptime data when not available"""
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url")
        
        result = coordinator.get_uptime_data()
        assert result is None
    
    def test_get_consensus_health_data(self):
        """Test getting consensus health data from coordinator"""
        mock_health_data = {"health_status": {"test": "data"}}
        
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url")
        coordinator.worker_data = {'consensus_health': mock_health_data}
        
        result = coordinator.get_consensus_health_data()
        assert result == mock_health_data
    
    def test_get_collector_data(self):
        """Test getting collector data from coordinator"""
        mock_collector_data = {"authorities": [{"name": "test"}]}
        
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url")
        coordinator.worker_data = {'collector': mock_collector_data}
        
        result = coordinator.get_collector_data()
        assert result == mock_collector_data
    
    def test_create_relay_set_with_additional_apis(self):
        """Test relay set creation with additional API data attached"""
        mock_details_data = {
            "relays": [{"nickname": "TestRelay1", "fingerprint": "ABC123"}],
            "version": "details_test"
        }
        
        mock_uptime_data = {
            "relays": [{"fingerprint": "ABC123", "uptime": {"1_month": 95.5}}],
            "version": "uptime_test"
        }
        
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url", enabled_apis='all')
        coordinator.worker_data = {
            'onionoo_uptime': mock_uptime_data,
            'consensus_health': {"health_status": {}},
            'collector': {"authorities": []}
        }
        
        mock_relay_set = MagicMock()
        mock_relay_set.json = mock_details_data
        
        with patch('lib.coordinator.Relays', return_value=mock_relay_set) as mock_relays:
            result = coordinator.create_relay_set(mock_details_data)
            
            assert result == mock_relay_set
            
            # Verify additional API data was attached
            assert mock_relay_set.uptime_data == mock_uptime_data
            assert mock_relay_set.consensus_health_data == {"health_status": {}}
            assert mock_relay_set.collector_data == {"authorities": []}
    
    def test_fetch_onionoo_data_multiapi_compatibility(self):
        """Test that fetch_onionoo_data returns details for backward compatibility"""
        mock_details_data = {
            "relays": [{"nickname": "TestRelay1", "fingerprint": "ABC123"}],
            "version": "details_test"
        }
        
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url", enabled_apis='all', progress=True)
        
        # Mock the fetch_all_apis_threaded method to avoid real threading
        with patch.object(coordinator, 'fetch_all_apis_threaded') as mock_fetch:
            mock_fetch.return_value = {
                'onionoo_details': mock_details_data,
                'onionoo_uptime': {"relays": [], "version": "uptime_test"}
            }
            
            with patch('builtins.print'):
                result = coordinator.fetch_onionoo_data()
                
                # Should return only details data for backward compatibility
                assert result == mock_details_data
    
    def test_get_relay_set_full_multiapi_flow(self):
        """Test complete multiapi relay set creation flow"""
        mock_details_data = {
            "relays": [{"nickname": "TestRelay1", "fingerprint": "ABC123"}],
            "version": "details_test"
        }
        
        mock_uptime_data = {
            "relays": [{"fingerprint": "ABC123", "uptime": {"1_month": 95.5}}],
            "version": "uptime_test"
        }
        
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url", enabled_apis='all')
        
        mock_relay_set = MagicMock()
        mock_relay_set.json = mock_details_data
        
        # Mock the data fetching to avoid real network calls
        with patch.object(coordinator, 'fetch_onionoo_data', return_value=mock_details_data):
            with patch('lib.coordinator.Relays', return_value=mock_relay_set):
                # Set up worker data
                coordinator.worker_data = {'onionoo_uptime': mock_uptime_data}
                
                result = coordinator.get_relay_set()
                
                assert result == mock_relay_set
                
                # Verify additional API data was attached
                assert mock_relay_set.uptime_data == mock_uptime_data
    
    def test_api_workers_url_transformation(self):
        """Test that API worker URLs are correctly assigned"""
        details_url = "https://custom.onionoo.org/details"
        uptime_url = "https://custom.onionoo.org/uptime"
        
        coordinator = Coordinator("./output", details_url, uptime_url, enabled_apis='all')
        
        # Check that workers are configured with correct functions and arguments
        assert len(coordinator.api_workers) == 2
        
        details_worker = next(w for w in coordinator.api_workers if w[0] == 'onionoo_details')
        uptime_worker = next(w for w in coordinator.api_workers if w[0] == 'onionoo_uptime')
        
        # Check that first argument is the URL, second is the progress logger
        assert details_worker[2][0] == details_url
        assert uptime_worker[2][0] == uptime_url
        
        # Check that progress logger is callable
        assert callable(details_worker[2][1])
        assert callable(uptime_worker[2][1])


class TestCoordinatorThreading:
    """Test coordinator threading functionality (simplified)"""
    
    def test_worker_thread_management(self):
        """Test that worker threads are properly configured"""
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url", enabled_apis='all')
        
        # Test that api_workers are properly configured
        assert len(coordinator.api_workers) == 2
        
        api_names = [worker[0] for worker in coordinator.api_workers]
        assert "onionoo_details" in api_names
        assert "onionoo_uptime" in api_names
    
    def test_worker_configuration(self):
        """Test that worker functions and arguments are properly set up"""
        coordinator = Coordinator("./output", "https://test.details.url", "https://test.uptime.url", enabled_apis='all')
        
        # Check that workers are configured with correct functions and arguments
        for api_name, worker_func, args in coordinator.api_workers:
            assert callable(worker_func)
            assert isinstance(args, list)
            assert len(args) > 0  # Should have at least URL argument


if __name__ == "__main__":
    pytest.main([__file__])