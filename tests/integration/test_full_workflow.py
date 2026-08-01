"""
Integration tests for Phase 1 API work - testing the full integration flow
"""
import json
import os
import pytest
import tempfile
from types import SimpleNamespace

from allium.lib.file_io_utils import create_cache_manager, create_timestamp_manager
import time
import urllib.error
from unittest.mock import patch, MagicMock

# Import consolidated test utilities
from helpers.fixtures import TestDataFactory, TestPatchingHelpers
from allium.lib.coordinator import Coordinator, create_relay_set_with_coordinator
from allium.lib.workers import fetch_onionoo_details, get_worker_status
from allium.lib.relays import Relays


# Mark all tests in this file as slow integration tests
pytestmark = [pytest.mark.slow, pytest.mark.integration]




def _make_args(**overrides):
    """argparse-like namespace matching allium.py's CLI surface (the
    coordinator entry point has taken an args namespace since the CLI
    refactor; these tests still used the ancient kwargs signature)."""
    defaults = {
        'output_dir': './output',
        'onionoo_details_url': 'https://test.details.url',
        'onionoo_uptime_url': 'https://test.uptime.url',
        'onionoo_bandwidth_url': 'https://test.bandwidth.url',
        'aroi_url': 'https://test.aroi.url/latest.json',
        'exit_dns_health_url': 'https://test.dns.url/latest.json',
        'bandwidth_cache_hours': 12,
        'bandwidth_units': 'bytes',
        'progress': False,
        'enabled_apis': 'all',
        'filter_downtime_days': 7,
        'base_url': '',
        'mp_workers': 4,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)

def _fresh_response_factory(payload_bytes):
    """Return a urlopen side_effect producing a FRESH mock per call:
    payload once, then EOF - the production chunk loop reads until an
    empty read, and each API worker makes its own urlopen call."""
    def _factory(*args, **kwargs):
        resp = MagicMock()
        resp.read.side_effect = [payload_bytes, b'']
        return resp
    return _factory


class TestFullIntegrationFlow:
    """Test the complete integration flow from coordinator to workers to relays"""
    
    def test_end_to_end_flow_success(self):
        """Test complete successful flow from coordinator through workers to relay processing"""
        # Mock onionoo data
        mock_onionoo_data = {
            "relays": [
                {
                    "nickname": "TestRelay1",
                    "fingerprint": "ABC123DEF456",
                    # Relays._filter_and_fix_relays drops relays that are not
                    # running unless last_seen is within filter_downtime_days
                    "running": True,
                    "observed_bandwidth": 1000000,
                    "consensus_weight": 500,
                    "consensus_weight_fraction": 0.001,
                    "flags": ["Running", "Valid", "Guard"],
                    "country": "us",
                    "as": "AS7922",
                    "as_name": "Comcast Cable",
                    "contact": "test@example.com",
                    "platform": "Tor 0.4.5.7 on Linux",
                    "first_seen": "2023-01-01 12:00:00",
                    "last_seen": "2024-01-01 12:00:00",
                    "or_addresses": ["192.168.1.1:9001"],
                    # Real onionoo /uptime document shape ({first, interval,
                    # values}) - the mocked urlopen serves this same payload
                    # to EVERY API endpoint, so the uptime worker/pipeline
                    # parses it too; flat strings crash uptime processing
                    "uptime": {
                        "1_month": {"first": "2023-12-01 00:00:00",
                                    "interval": 3600,
                                    "values": [995] * 60},
                        "1_year": {"first": "2023-01-01 00:00:00",
                                   "interval": 43200,
                                   "values": [980] * 60}
                    }
                },
                {
                    "nickname": "TestRelay2",
                    "fingerprint": "DEF456ABC123",
                    "running": True,
                    "observed_bandwidth": 2000000,
                    "consensus_weight": 1000,
                    "consensus_weight_fraction": 0.002,
                    "flags": ["Running", "Valid", "Exit"],
                    "country": "de",
                    "as": "AS8560",
                    "as_name": "1&1 Internet",
                    "contact": "test2@example.com",
                    "platform": "Tor 0.4.5.7 on FreeBSD",
                    "first_seen": "2023-01-01 12:00:00",
                    "last_seen": "2024-01-01 12:00:00",
                    "or_addresses": ["192.168.1.2:9001"]
                }
            ],
            "version": "1.0"
        }
        
        mock_urlopen_factory = _fresh_response_factory(
            json.dumps(mock_onionoo_data).encode('utf-8'))
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = os.path.join(temp_dir, "output")
            cache_dir = os.path.join(temp_dir, "cache")
            state_file = os.path.join(temp_dir, "state.json")
            
            with patch('allium.lib.workers.CACHE_DIR', cache_dir), \
                 patch('allium.lib.workers._cache_manager',
                       create_cache_manager(cache_dir)), \
                 patch('allium.lib.workers._timestamp_manager',
                       create_timestamp_manager(cache_dir)):
                with patch('allium.lib.workers.STATE_FILE', state_file):
                    with patch('urllib.request.urlopen', side_effect=mock_urlopen_factory):
                        with patch('builtins.print'):  # Suppress progress output
                            
                            # Create cache directory since workers expect it to exist
                            os.makedirs(cache_dir, exist_ok=True)
                            
                            # Create coordinator
                            coordinator = Coordinator(
                                output_dir=output_dir,
                                onionoo_details_url="https://test.details.url",
                                onionoo_uptime_url="https://test.uptime.url",
                                progress=True
                            )
                            
                            # Test the full flow
                            relay_set = coordinator.get_relay_set()
                            
                            # Verify the result
                            assert relay_set is not None
                            assert relay_set.json is not None
                            assert len(relay_set.json["relays"]) == 2
                            
                            # Check that relays were processed correctly
                            relay1 = relay_set.json["relays"][0]
                            relay2 = relay_set.json["relays"][1]
                            
                            # Check that preprocessing was applied
                            assert "contact_md5" in relay1
                            assert "aroi_domain" in relay1
                            assert "platform_raw" in relay1
                            assert "nickname_escaped" in relay1
                            
                            # Check that data was cached
                            assert os.path.exists(cache_dir)
                            cache_file = os.path.join(cache_dir, "onionoo_details.json")
                            assert os.path.exists(cache_file)
                            
                            # Check worker status
                            status = get_worker_status("onionoo_details")
                            assert status["status"] == "ready"
                            assert status["error"] is None
    
    def test_end_to_end_flow_with_cache_fallback(self):
        """Test flow when network fails but cache is available"""
        # Pre-populate cache
        cached_data = {
            "relays": [
                {
                    "nickname": "CachedRelay",
                    "fingerprint": "CACHED123",
                    "running": True,  # keeps relay past the downtime filter
                    "observed_bandwidth": 500000,
                    "consensus_weight": 250,
                    "flags": ["Running", "Valid"],
                    "country": "us",
                    "as": "AS1234",
                    "contact": "cached@example.com",
                    "platform": "Tor 0.4.5.7 on Linux",
                    "first_seen": "2023-01-01 12:00:00",
                    "or_addresses": ["192.168.1.100:9001"]
                }
            ],
            "version": "cached"
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = os.path.join(temp_dir, "output")
            cache_dir = os.path.join(temp_dir, "cache")
            state_file = os.path.join(temp_dir, "state.json")
            
            # Pre-create cache
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, "onionoo_details.json")
            with open(cache_file, 'w') as f:
                json.dump(cached_data, f)
            
            with patch('allium.lib.workers.CACHE_DIR', cache_dir), \
                 patch('allium.lib.workers._cache_manager',
                       create_cache_manager(cache_dir)), \
                 patch('allium.lib.workers._timestamp_manager',
                       create_timestamp_manager(cache_dir)):
                with patch('allium.lib.workers.STATE_FILE', state_file):
                    # Simulate network error
                    with patch('urllib.request.urlopen', side_effect=ConnectionError("Network error")):
                        with patch('builtins.print'):  # Suppress output
                            
                            coordinator = Coordinator(output_dir=output_dir, onionoo_details_url="https://test.details.url", onionoo_uptime_url="https://test.uptime.url")
                            relay_set = coordinator.get_relay_set()
                            
                            # Should succeed with cached data
                            assert relay_set is not None
                            assert len(relay_set.json["relays"]) == 1
                            assert relay_set.json["relays"][0]["nickname"] == "CachedRelay"
                            
                            # Current design (_fetch_with_cache_fallback):
                            # a successful cache fallback marks the worker
                            # "ready" - "stale" is reserved for failures with
                            # NO usable data (see test_end_to_end_flow_complete_failure)
                            status = get_worker_status("onionoo_details")
                            assert status["status"] == "ready"
                            assert status["error"] is None
    
    def test_end_to_end_flow_complete_failure(self):
        """Test flow when both network and cache fail"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = os.path.join(temp_dir, "output")
            cache_dir = os.path.join(temp_dir, "cache")
            state_file = os.path.join(temp_dir, "state.json")
            
            with patch('allium.lib.workers.CACHE_DIR', cache_dir), \
                 patch('allium.lib.workers._cache_manager',
                       create_cache_manager(cache_dir)), \
                 patch('allium.lib.workers._timestamp_manager',
                       create_timestamp_manager(cache_dir)):
                with patch('allium.lib.workers.STATE_FILE', state_file):
                    # Simulate network error with no cache
                    with patch('urllib.request.urlopen', side_effect=ConnectionError("Network error")):
                        with patch('builtins.print'):  # Suppress output
                            
                            coordinator = Coordinator(output_dir=output_dir, onionoo_details_url="https://test.details.url", onionoo_uptime_url="https://test.uptime.url")
                            relay_set = coordinator.get_relay_set()
                            
                            # Should fail completely
                            assert relay_set is None


class TestBackwardsCompatibilityIntegration:
    """Test that the new system maintains backwards compatibility"""
    
    def test_backwards_compatibility_function(self):
        """Test that create_relay_set_with_coordinator works like original Relays constructor"""
        mock_onionoo_data = {
            "relays": [
                {
                    "nickname": "CompatRelay",
                    "fingerprint": "COMPAT123",
                    "running": True,  # keeps relay past the downtime filter
                    "observed_bandwidth": 1000000,
                    "consensus_weight": 500,
                    "flags": ["Running", "Valid"],
                    "country": "us",
                    "as": "AS1234",
                    "contact": "compat@example.com",
                    "platform": "Tor 0.4.5.7 on Linux",
                    "first_seen": "2023-01-01 12:00:00",
                    "or_addresses": ["192.168.1.10:9001"]
                }
            ],
            "version": "1.0"
        }
        
        mock_urlopen_factory = _fresh_response_factory(json.dumps(mock_onionoo_data).encode('utf-8'))
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = os.path.join(temp_dir, "output")
            cache_dir = os.path.join(temp_dir, "cache")
            state_file = os.path.join(temp_dir, "state.json")
            
            with patch('allium.lib.workers.CACHE_DIR', cache_dir), \
                 patch('allium.lib.workers._cache_manager',
                       create_cache_manager(cache_dir)), \
                 patch('allium.lib.workers._timestamp_manager',
                       create_timestamp_manager(cache_dir)):
                with patch('allium.lib.workers.STATE_FILE', state_file):
                    with patch('urllib.request.urlopen', side_effect=mock_urlopen_factory):
                        with patch('builtins.print'):  # Suppress output
                            
                            # Use backwards compatibility function
                            relay_set = create_relay_set_with_coordinator(
                                _make_args(output_dir=output_dir,
                                           bandwidth_units='bits'))
                            
                            # Should work exactly like original
                            assert relay_set is not None
                            assert relay_set.json is not None
                            assert len(relay_set.json["relays"]) == 1
                            assert relay_set.json["relays"][0]["nickname"] == "CompatRelay"
                            
                            # Check that use_bits was passed through
                            assert relay_set.use_bits is True
    
    def test_original_relays_constructor_still_works(self):
        """Test that the original Relays constructor with relay_data=None still works"""
        mock_onionoo_data = {
            "relays": [
                {
                    "nickname": "OriginalRelay",
                    "fingerprint": "ORIGINAL123",
                    "running": True,  # keeps relay past the downtime filter
                    "observed_bandwidth": 1000000,
                    "consensus_weight": 500,
                    "flags": ["Running", "Valid"],
                    "country": "us",
                    "as": "AS1234",
                    "contact": "original@example.com",
                    "platform": "Tor 0.4.5.7 on Linux",
                    "first_seen": "2023-01-01 12:00:00",
                    "or_addresses": ["192.168.1.20:9001"]
                }
            ],
            "version": "1.0"
        }
        
        mock_urlopen_factory = _fresh_response_factory(json.dumps(mock_onionoo_data).encode('utf-8'))
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = os.path.join(temp_dir, "output")
            cache_dir = os.path.join(temp_dir, "cache")
            state_file = os.path.join(temp_dir, "state.json")
            
            with patch('allium.lib.workers.CACHE_DIR', cache_dir), \
                 patch('allium.lib.workers._cache_manager',
                       create_cache_manager(cache_dir)), \
                 patch('allium.lib.workers._timestamp_manager',
                       create_timestamp_manager(cache_dir)):
                with patch('allium.lib.workers.STATE_FILE', state_file):
                    with patch('urllib.request.urlopen', side_effect=mock_urlopen_factory):
                        with patch('builtins.print'):  # Suppress output
                            
                            # Create cache directory
                            os.makedirs(cache_dir, exist_ok=True)
                            
                            # Use coordinator pattern instead of old direct constructor
                            from allium.lib.coordinator import create_relay_set_with_coordinator
                            relay_set = create_relay_set_with_coordinator(
                                _make_args(output_dir=output_dir))
                            
                            # Should work exactly like before
                            assert relay_set is not None
                            assert relay_set.json is not None
                            assert len(relay_set.json["relays"]) == 1
                            assert relay_set.json["relays"][0]["nickname"] == "OriginalRelay"
    
    def test_new_relays_constructor_with_data_injection(self):
        """Test that the new Relays constructor with relay_data parameter works"""
        mock_onionoo_data = {
            "relays": [
                {
                    "nickname": "InjectedRelay",
                    "fingerprint": "INJECTED123",
                    "running": True,  # keeps relay past the downtime filter
                    "observed_bandwidth": 1000000,
                    "consensus_weight": 500,
                    "flags": ["Running", "Valid"],
                    "country": "us",
                    "as": "AS1234",
                    "contact": "injected@example.com",
                    "platform": "Tor 0.4.5.7 on Linux",
                    "first_seen": "2023-01-01 12:00:00",
                    "or_addresses": ["192.168.1.30:9001"]
                }
            ],
            "version": "1.0"
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = os.path.join(temp_dir, "output")
            
            with patch('builtins.print'):  # Suppress output
                
                # Use new constructor pattern with data injection
                relay_set = Relays(
                    output_dir=output_dir,
                    onionoo_url="https://test.details.url",
                    relay_data=mock_onionoo_data,  # Required parameter
                    use_bits=True,
                    progress=False
                )
                
                # Should work with injected data
                assert relay_set is not None
                assert relay_set.json == mock_onionoo_data
                assert len(relay_set.json["relays"]) == 1
                assert relay_set.json["relays"][0]["nickname"] == "InjectedRelay"
                
                # Should not have attempted to fetch data
                assert isinstance(relay_set.timestamp, str)


class TestWorkerStateManagement:
    """Test worker state management during integration"""
    
    def test_worker_state_persistence_across_calls(self):
        """Test that worker state persists across multiple coordinator calls"""
        mock_data = {
            "relays": [{
                "nickname": "TestRelay", 
                "fingerprint": "TEST123",
                "flags": ["Running", "Valid"],
                "consensus_weight": 1000,
                "observed_bandwidth": 500000,
                "country": "us",
                "as": "AS1234",
                "first_seen": "2023-01-01 12:00:00",
                "contact": "test@example.com",
                "platform": "Tor 0.4.5.7 on Linux"
            }],
            "version": "1.0"
        }
        
        mock_urlopen_factory = _fresh_response_factory(json.dumps(mock_data).encode('utf-8'))
        
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "cache")
            state_file = os.path.join(temp_dir, "state.json")
            
            with patch('allium.lib.workers.CACHE_DIR', cache_dir), \
                 patch('allium.lib.workers._cache_manager',
                       create_cache_manager(cache_dir)), \
                 patch('allium.lib.workers._timestamp_manager',
                       create_timestamp_manager(cache_dir)):
                with patch('allium.lib.workers.STATE_FILE', state_file):
                    with patch('urllib.request.urlopen', side_effect=mock_urlopen_factory):
                        with patch('builtins.print'):  # Suppress output
                            
                            # First coordinator call
                            coordinator1 = Coordinator(
                                output_dir=temp_dir,
                                onionoo_details_url="https://test.details.url",
                                onionoo_uptime_url="https://test.uptime.url",
                                progress=True
                            )
                            relay_set1 = coordinator1.get_relay_set()
                            assert relay_set1 is not None
                            
                            # Check initial worker status
                            status1 = get_worker_status("onionoo_details")
                            assert status1["status"] == "ready"
                            
                            # Second coordinator call (should reuse state)
                            coordinator2 = Coordinator(
                                output_dir=temp_dir,
                                onionoo_details_url="https://test.details.url",
                                onionoo_uptime_url="https://test.uptime.url",
                                progress=True
                            )
                            
                            # Get status before second call
                            from allium.lib.workers import get_all_worker_status
                            statuses = get_all_worker_status()
                            assert len(statuses) >= 1
                            assert sum(1 for s in statuses.values()
                                       if s.get("status") == "ready") >= 1
                            
                            relay_set2 = coordinator2.get_relay_set()
                            assert relay_set2 is not None
    
    def test_multiple_worker_status_tracking(self):
        """Test that multiple workers are tracked correctly"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "cache")
            state_file = os.path.join(temp_dir, "state.json")
            
            with patch('allium.lib.workers.CACHE_DIR', cache_dir), \
                 patch('allium.lib.workers._cache_manager',
                       create_cache_manager(cache_dir)), \
                 patch('allium.lib.workers._timestamp_manager',
                       create_timestamp_manager(cache_dir)):
                with patch('allium.lib.workers.STATE_FILE', state_file):
                    with patch('builtins.print'):  # Suppress output
                        
                        # Clear existing worker state for this test
                        with patch('allium.lib.workers._worker_status', {}):
                            # Import and run multiple workers
                            from allium.lib.workers import fetch_onionoo_uptime, fetch_collector_consensus_data, fetch_consensus_health
                            
                            # Run placeholder workers
                            fetch_onionoo_uptime()
                            fetch_collector_consensus_data()
                            fetch_consensus_health()
                            
                            # Check worker status tracked by the module registry
                            from allium.lib.workers import get_all_worker_status
                            statuses = get_all_worker_status()
                            
                            assert len(statuses) >= 3
                            assert sum(1 for s in statuses.values()
                                       if s.get("status") == "ready") >= 3
                            assert sum(1 for s in statuses.values()
                                       if s.get("status") == "stale") == 0


class TestErrorRecoveryIntegration:
    """Test error recovery scenarios in integration"""
    
    def test_coordinator_handles_worker_errors_gracefully(self):
        """Test that coordinator handles worker errors without crashing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "cache")
            state_file = os.path.join(temp_dir, "state.json")
            
            with patch('allium.lib.workers.CACHE_DIR', cache_dir), \
                 patch('allium.lib.workers._cache_manager',
                       create_cache_manager(cache_dir)), \
                 patch('allium.lib.workers._timestamp_manager',
                       create_timestamp_manager(cache_dir)):
                with patch('allium.lib.workers.STATE_FILE', state_file):
                    # Simulate various types of errors
                    with patch('urllib.request.urlopen', side_effect=TimeoutError("Request timeout")):
                        with patch('builtins.print'):  # Suppress output
                            
                            coordinator = Coordinator(
                                output_dir=temp_dir,
                                onionoo_details_url="https://test.details.url",
                                onionoo_uptime_url="https://test.uptime.url",
                                progress=True
                            )
                            relay_set = coordinator.get_relay_set()
                            
                            # Should handle error gracefully
                            assert relay_set is None
                            
                            # Worker should be marked as stale
                            status = get_worker_status("onionoo_details")
                            assert status["status"] == "stale"
                            assert "timeout" in status["error"].lower()
    
    def test_partial_success_scenarios(self):
        """Test scenarios where some operations succeed and others fail"""
        # Test successful fetch but failed relay creation
        mock_data = {"relays": [{"nickname": "TestRelay"}], "version": "1.0"}
        mock_urlopen_factory = _fresh_response_factory(json.dumps(mock_data).encode('utf-8'))
        
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "cache")
            state_file = os.path.join(temp_dir, "state.json")
            
            with patch('allium.lib.workers.CACHE_DIR', cache_dir), \
                 patch('allium.lib.workers._cache_manager',
                       create_cache_manager(cache_dir)), \
                 patch('allium.lib.workers._timestamp_manager',
                       create_timestamp_manager(cache_dir)):
                with patch('allium.lib.workers.STATE_FILE', state_file):
                    with patch('urllib.request.urlopen', side_effect=mock_urlopen_factory):
                        # Make Relays constructor fail
                        with patch('allium.lib.coordinator.Relays', side_effect=Exception("Relay creation failed")):
                            with patch('builtins.print'):  # Suppress output
                                
                                # Create cache directory
                                os.makedirs(cache_dir, exist_ok=True)
                                
                                coordinator = Coordinator(
                                    output_dir=temp_dir,
                                    onionoo_details_url="https://test.details.url",
                                    onionoo_uptime_url="https://test.uptime.url",
                                    progress=True
                                )
                                
                                # Should handle the exception gracefully
                                try:
                                    relay_set = coordinator.get_relay_set()
                                    # If no exception, it should return None
                                    assert relay_set is None
                                except Exception:
                                    # If exception is raised, that's also acceptable for this test
                                    pass
                                
                                # Worker should still be ready (fetch succeeded)
                                status = get_worker_status("onionoo_details")
                                assert status["status"] == "ready"


class TestPerformanceAndCaching:
    """Test performance aspects and caching behavior"""
    
    def test_cache_reduces_network_calls(self):
        """Test that caching reduces network calls on subsequent requests"""
        mock_data = {
            "relays": [{
                "nickname": "CachedTestRelay",
                "fingerprint": "CACHE123",
                "running": True,  # keeps relay past the downtime filter
                "flags": ["Running", "Valid"],
                "consensus_weight": 1000,
                "observed_bandwidth": 500000,
                "country": "us",
                "as": "AS1234",
                "first_seen": "2023-01-01 12:00:00",
                "contact": "cached@example.com",
                "platform": "Tor 0.4.5.7 on Linux"
            }],
            "version": "1.0"
        }
        
        mock_urlopen_factory = _fresh_response_factory(json.dumps(mock_data).encode('utf-8'))
        
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "cache")
            state_file = os.path.join(temp_dir, "state.json")
            
            with patch('allium.lib.workers.CACHE_DIR', cache_dir), \
                 patch('allium.lib.workers._cache_manager',
                       create_cache_manager(cache_dir)), \
                 patch('allium.lib.workers._timestamp_manager',
                       create_timestamp_manager(cache_dir)):
                with patch('allium.lib.workers.STATE_FILE', state_file):
                    with patch('urllib.request.urlopen', side_effect=mock_urlopen_factory) as mock_urlopen:
                        with patch('builtins.print'):  # Suppress output
                            
                            # Create cache directory
                            os.makedirs(cache_dir, exist_ok=True)
                            
                            # First call - should make network request
                            coordinator1 = Coordinator(
                                output_dir=temp_dir,
                                onionoo_details_url="https://test.details.url",
                                onionoo_uptime_url="https://test.uptime.url",
                                progress=True
                            )
                            relay_set1 = coordinator1.get_relay_set()
                            assert relay_set1 is not None
                            
                            initial_call_count = mock_urlopen.call_count
                            assert initial_call_count > 0
                            
                            # Now cache should be populated, so we can test 304 response
                            # Mock 304 Not Modified response for subsequent calls
                            http_304_error = urllib.error.HTTPError(
                                url="test", code=304, msg="Not Modified", hdrs={}, fp=None
                            )
                            mock_urlopen.side_effect = http_304_error
                            
                            # Second call - should use cache (304 response)
                            coordinator2 = Coordinator(
                                output_dir=temp_dir,
                                onionoo_details_url="https://test.details.url",
                                onionoo_uptime_url="https://test.uptime.url",
                                progress=True
                            )
                            relay_set2 = coordinator2.get_relay_set()
                            assert relay_set2 is not None
                            
                            # Should have same data
                            assert relay_set1.json["relays"][0]["nickname"] == relay_set2.json["relays"][0]["nickname"]


if __name__ == "__main__":
    # Import urllib.error for the integration tests
    import urllib.error
    pytest.main([__file__])