"""
Integration tests for lib/consensus module.

Tests the full integration of CollecTor consensus data:
- Worker fetching via coordinator
- Data processing in relays.py
- Template rendering with diagnostics data
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock

# Add allium to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'allium'))

from lib.consensus import is_enabled, COLLECTOR_DIAGNOSTICS_ENABLED
from lib.consensus.collector_fetcher import CollectorFetcher, discover_authorities, calculate_consensus_requirement
from lib.consensus.authority_monitor import AuthorityMonitor
from lib.consensus.diagnostics import format_relay_diagnostics, format_authority_diagnostics


class TestFeatureFlag:
    """Test feature flag functionality."""
    
    def test_feature_flag_default_enabled(self):
        """Test that the feature is enabled by default."""
        assert COLLECTOR_DIAGNOSTICS_ENABLED is True
        assert is_enabled() is True
    
    @patch.dict(os.environ, {'ALLIUM_COLLECTOR_DIAGNOSTICS': 'false'})
    def test_feature_flag_disabled(self):
        """Test feature can be disabled via environment variable."""
        # Need to reimport to pick up new env var
        import importlib
        from lib import consensus
        importlib.reload(consensus)
        
        # After reload, check the new value
        assert consensus.is_enabled() is False
        
        # Restore for other tests
        os.environ['ALLIUM_COLLECTOR_DIAGNOSTICS'] = 'true'
        importlib.reload(consensus)


class TestCoordinatorIntegration:
    """Test coordinator integration with collector consensus workers."""
    
    def test_collector_worker_in_api_workers(self):
        """Test that collector_consensus worker is added when feature is enabled."""
        from lib.coordinator import Coordinator
        
        with patch('lib.consensus.is_enabled', return_value=True):
            coordinator = Coordinator(
                output_dir='/tmp/test',
                onionoo_details_url='https://onionoo.torproject.org/details',
                onionoo_uptime_url='https://onionoo.torproject.org/uptime',
                onionoo_bandwidth_url='https://onionoo.torproject.org/bandwidth',
                aroi_url='https://aroivalidator.1aeo.com/latest.json',
                bandwidth_cache_hours=12,
                enabled_apis='all',
            )
            
            # Check that collector_consensus worker is in the list
            worker_names = [name for name, _, _ in coordinator.api_workers]
            assert 'collector_consensus' in worker_names
    
    def test_consensus_health_worker_in_api_workers(self):
        """Test that consensus_health worker is added when feature is enabled."""
        from lib.coordinator import Coordinator
        
        with patch('lib.consensus.is_enabled', return_value=True):
            coordinator = Coordinator(
                output_dir='/tmp/test',
                onionoo_details_url='https://onionoo.torproject.org/details',
                onionoo_uptime_url='https://onionoo.torproject.org/uptime',
                onionoo_bandwidth_url='https://onionoo.torproject.org/bandwidth',
                aroi_url='https://aroivalidator.1aeo.com/latest.json',
                bandwidth_cache_hours=12,
                enabled_apis='all',
            )
            
            # Check that consensus_health worker is in the list
            worker_names = [name for name, _, _ in coordinator.api_workers]
            assert 'consensus_health' in worker_names
    
    def test_collector_worker_not_added_when_disabled(self):
        """Test that collector workers are not added when feature is disabled."""
        from lib.coordinator import Coordinator
        
        with patch('lib.consensus.is_enabled', return_value=False):
            coordinator = Coordinator(
                output_dir='/tmp/test',
                onionoo_details_url='https://onionoo.torproject.org/details',
                onionoo_uptime_url='https://onionoo.torproject.org/uptime',
                onionoo_bandwidth_url='https://onionoo.torproject.org/bandwidth',
                aroi_url='https://aroivalidator.1aeo.com/latest.json',
                bandwidth_cache_hours=12,
                enabled_apis='all',
            )
            
            # Check that collector workers are NOT in the list
            worker_names = [name for name, _, _ in coordinator.api_workers]
            assert 'collector_consensus' not in worker_names
            assert 'consensus_health' not in worker_names
    
    def test_collector_data_getter(self):
        """Test get_collector_consensus_data getter method."""
        from lib.coordinator import Coordinator
        
        coordinator = Coordinator(
            output_dir='/tmp/test',
            onionoo_details_url='https://onionoo.torproject.org/details',
            onionoo_uptime_url='https://onionoo.torproject.org/uptime',
            onionoo_bandwidth_url='https://onionoo.torproject.org/bandwidth',
            aroi_url='https://aroivalidator.1aeo.com/latest.json',
            bandwidth_cache_hours=12,
        )
        
        # Initially should return None
        assert coordinator.get_collector_consensus_data() is None
        
        # Set mock data
        mock_data = {'relay_index': {}, 'flag_thresholds': {}}
        coordinator.worker_data['collector_consensus'] = mock_data
        
        # Now should return the data
        assert coordinator.get_collector_consensus_data() == mock_data


class TestDiagnosticsFormatting:
    """Test diagnostics formatting for templates."""
    
    def test_format_relay_diagnostics_available(self):
        """Test formatting relay diagnostics when data is available."""
        raw_diagnostics = {
            'fingerprint': '0232AF901C31A04EE9848595AF9BB7620D4C5B2E',
            'in_consensus': True,
            'vote_count': 7,
            'total_authorities': 9,
            'majority_required': 5,
            'authority_votes': [
                {'authority': 'moria1', 'voted': True, 'flags': ['Guard', 'Stable']},
            ],
            'flag_eligibility': {
                'guard': {'eligible_count': 5, 'details': []},
                'stable': {'eligible_count': 7, 'details': []},
                'fast': {'eligible_count': 9, 'details': []},
                'hsdir': {'eligible_count': 6, 'details': []},
            },
            'reachability': {
                'ipv4_reachable_count': 7,
                'ipv6_reachable_count': 3,
                'total_authorities': 9,
            },
            'bandwidth': {
                'average': 5000000,
                'min': 4000000,
                'max': 6000000,
            },
        }
        
        formatted = format_relay_diagnostics(raw_diagnostics)
        
        assert formatted['available'] is True
        assert formatted['in_consensus'] is True
        assert formatted['vote_count'] == 7
        assert 'consensus_status' in formatted
        assert 'authority_table' in formatted
        assert 'flag_summary' in formatted
    
    def test_format_relay_diagnostics_not_available(self):
        """Test formatting relay diagnostics when data is not available."""
        raw_diagnostics = {
            'error': 'Relay not found in votes',
            'in_consensus': False,
        }
        
        formatted = format_relay_diagnostics(raw_diagnostics)
        
        assert formatted['available'] is False
        assert formatted['in_consensus'] is False
        assert 'error' in formatted
    
    def test_format_relay_diagnostics_empty(self):
        """Test formatting relay diagnostics with empty/None input."""
        formatted = format_relay_diagnostics(None)
        assert formatted['available'] is False
        
        formatted = format_relay_diagnostics({})
        assert formatted['available'] is False


class TestAuthorityMonitorIntegration:
    """Test authority monitor integration."""
    
    def test_get_summary_format(self):
        """Test that summary has expected format."""
        monitor = AuthorityMonitor()
        
        # Mock status data
        status = {
            'moria1': {'online': True, 'latency_ms': 50.0},
            'tor26': {'online': True, 'latency_ms': 100.0},
            'dizum': {'online': False, 'latency_ms': None, 'error': 'Timeout'},
        }
        
        summary = monitor.get_summary(status)
        
        assert 'total_authorities' in summary
        assert 'online_count' in summary
        assert 'offline_count' in summary
        assert 'average_latency_ms' in summary
        assert 'slow_authorities' in summary
        assert 'offline_authorities' in summary
    
    def test_get_alerts_format(self):
        """Test that alerts have expected format."""
        monitor = AuthorityMonitor()
        
        # Mock status with issues
        status = {
            'moria1': {'online': True, 'latency_ms': 50.0},
            'dizum': {'online': False, 'error': 'Connection refused'},
        }
        
        alerts = monitor.get_alerts(status)
        
        # Should have at least one alert for dizum being offline
        assert len(alerts) >= 1
        
        # Each alert should have expected fields
        for alert in alerts:
            assert 'severity' in alert
            assert 'message' in alert
            assert alert['severity'] in ['critical', 'error', 'warning']


class TestRelayDiagnosticsIntegration:
    """Test relay diagnostics integration with relays.py."""
    
    def test_collector_diagnostics_attached_to_relay(self):
        """Test that collector diagnostics are attached to relay objects."""
        # Create mock collector data
        collector_data = {
            'relay_index': {
                '0232AF901C31A04EE9848595AF9BB7620D4C5B2E': {
                    'fingerprint': '0232AF901C31A04EE9848595AF9BB7620D4C5B2E',
                    'nickname': 'TestRelay',
                    'votes': {
                        'moria1': {'flags': ['Guard', 'Stable']},
                        'tor26': {'flags': ['Guard', 'Stable']},
                        'dizum': {'flags': ['Guard']},
                        'gabelmoo': {'flags': ['Guard', 'Stable']},
                        'bastet': {'flags': ['Guard', 'Stable']},
                    },
                    'bandwidth_measurements': {},
                },
            },
            'flag_thresholds': {
                'moria1': {'guard-wfu': 0.98, 'guard-tk': 691200},
            },
            'bw_authorities': ['moria1', 'gabelmoo'],
            'ipv6_testing_authorities': ['moria1'],
        }
        
        # Simulate what _reprocess_collector_data does
        fetcher = CollectorFetcher()
        fetcher.relay_index = collector_data['relay_index']
        fetcher.flag_thresholds = collector_data['flag_thresholds']
        fetcher.bw_authorities = set(collector_data['bw_authorities'])
        
        fingerprint = '0232AF901C31A04EE9848595AF9BB7620D4C5B2E'
        diagnostics = fetcher.get_relay_diagnostics(fingerprint)
        formatted = format_relay_diagnostics(diagnostics)
        
        # Verify diagnostics structure
        assert formatted['available'] is True
        assert formatted['in_consensus'] is True
        assert formatted['vote_count'] == 5


class TestTemplateDataStructure:
    """Test that data structures are correctly formatted for templates."""
    
    def test_consensus_status_structure(self):
        """Test consensus_status has correct template structure."""
        raw_diagnostics = {
            'fingerprint': 'TEST',
            'in_consensus': True,
            'vote_count': 7,
            'total_authorities': 9,
            'majority_required': 5,
            'authority_votes': [],
            'flag_eligibility': {},
            'reachability': {},
            'bandwidth': {},
        }
        
        formatted = format_relay_diagnostics(raw_diagnostics)
        
        assert 'consensus_status' in formatted
        status = formatted['consensus_status']
        
        assert 'status' in status
        assert 'status_class' in status
        assert 'display' in status
        assert 'tooltip' in status
        
        # Success case
        assert status['status_class'] == 'success'
        assert 'IN CONSENSUS' in status['display']
    
    def test_authority_table_structure(self):
        """Test authority_table has correct template structure."""
        raw_diagnostics = {
            'fingerprint': 'TEST',
            'in_consensus': True,
            'vote_count': 1,
            'total_authorities': 9,
            'majority_required': 5,
            'authority_votes': [
                {
                    'authority': 'moria1',
                    'voted': True,
                    'flags': ['Guard', 'Stable'],
                    'bandwidth': 5000000,
                    'measured': 4500000,
                    'wfu': 0.99,
                    'wfu_display': '99.0%',
                    'tk': 1000000,
                    'tk_display': '11.6 days',
                    'ipv4_reachable': True,
                    'ipv6_reachable': True,
                    'is_bw_authority': True,
                }
            ],
            'flag_eligibility': {},
            'reachability': {},
            'bandwidth': {},
        }
        
        formatted = format_relay_diagnostics(raw_diagnostics)
        
        assert 'authority_table' in formatted
        assert len(formatted['authority_table']) >= 1
        
        row = formatted['authority_table'][0]
        assert 'authority' in row
        assert 'voted' in row
        assert 'voted_class' in row
        assert 'flags_display' in row
        assert 'wfu_display' in row
        assert 'wfu_class' in row
        assert 'ipv4_class' in row
        assert 'ipv6_class' in row
    
    def test_flag_summary_structure(self):
        """Test flag_summary has correct template structure."""
        raw_diagnostics = {
            'fingerprint': 'TEST',
            'in_consensus': True,
            'vote_count': 5,
            'total_authorities': 9,
            'majority_required': 5,
            'authority_votes': [],
            'flag_eligibility': {
                'guard': {'eligible_count': 5, 'details': []},
                'stable': {'eligible_count': 7, 'details': []},
                'fast': {'eligible_count': 9, 'details': []},
                'hsdir': {'eligible_count': 3, 'details': []},
            },
            'reachability': {},
            'bandwidth': {},
        }
        
        formatted = format_relay_diagnostics(raw_diagnostics)
        
        assert 'flag_summary' in formatted
        summary = formatted['flag_summary']
        
        for flag_name in ['guard', 'stable', 'fast', 'hsdir']:
            assert flag_name in summary
            flag_data = summary[flag_name]
            
            assert 'eligible_count' in flag_data
            assert 'total_authorities' in flag_data
            assert 'status' in flag_data
            assert 'status_class' in flag_data
            assert 'display' in flag_data
