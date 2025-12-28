"""
Unit tests for lib/consensus/authority_monitor.py

Tests the AuthorityMonitor class which monitors
directory authority health and responsiveness.
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock
from datetime import datetime

# Add allium to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'allium'))

from lib.consensus.authority_monitor import (
    AuthorityMonitor,
    DEFAULT_AUTHORITY_ENDPOINTS,
)


class TestAuthorityMonitor:
    """Tests for AuthorityMonitor class."""
    
    def test_init_default_values(self):
        """Test AuthorityMonitor initializes with correct default values."""
        monitor = AuthorityMonitor()
        
        assert monitor.timeout == 10
        assert monitor.authorities == []
        assert monitor._last_check is None
        assert monitor._cached_status is None
    
    def test_init_with_custom_timeout(self):
        """Test AuthorityMonitor accepts custom timeout."""
        monitor = AuthorityMonitor(timeout=30)
        assert monitor.timeout == 30
    
    def test_init_with_authorities(self):
        """Test AuthorityMonitor accepts discovered authorities."""
        authorities = [
            {'nickname': 'TestAuth', 'address': '192.168.1.1', 'dir_port': '80'}
        ]
        monitor = AuthorityMonitor(authorities=authorities)
        assert monitor.authorities == authorities
    
    def test_get_authority_endpoints_default(self):
        """Test _get_authority_endpoints returns defaults when no authorities set."""
        monitor = AuthorityMonitor()
        endpoints = monitor._get_authority_endpoints()
        
        assert endpoints == DEFAULT_AUTHORITY_ENDPOINTS
        assert 'moria1' in endpoints
        assert 'tor26' in endpoints
    
    def test_get_authority_endpoints_from_discovered(self):
        """Test _get_authority_endpoints uses discovered authorities."""
        authorities = [
            {'nickname': 'CustomAuth', 'address': '10.0.0.1', 'dir_port': '9030'}
        ]
        monitor = AuthorityMonitor(authorities=authorities)
        endpoints = monitor._get_authority_endpoints()
        
        assert 'CustomAuth' in endpoints
        assert endpoints['CustomAuth'] == 'http://10.0.0.1:9030'
    
    def test_get_summary_empty(self):
        """Test get_summary with no data."""
        monitor = AuthorityMonitor()
        
        # Mock check_all_authorities to return empty result
        with patch.object(monitor, 'check_all_authorities', return_value={}):
            summary = monitor.get_summary()
        
        assert summary['total_authorities'] == 0
        assert summary['online_count'] == 0
        assert summary['offline_count'] == 0
    
    def test_get_summary_with_data(self):
        """Test get_summary with sample data."""
        monitor = AuthorityMonitor()
        
        status = {
            'moria1': {'online': True, 'latency_ms': 50.0},
            'tor26': {'online': True, 'latency_ms': 100.0},
            'dizum': {'online': False, 'latency_ms': None, 'error': 'Timeout'},
        }
        
        summary = monitor.get_summary(status)
        
        assert summary['total_authorities'] == 3
        assert summary['online_count'] == 2
        assert summary['offline_count'] == 1
        assert summary['average_latency_ms'] == 75.0  # (50 + 100) / 2
        assert summary['min_latency_ms'] == 50.0
        assert summary['max_latency_ms'] == 100.0
        assert 'dizum' in summary['offline_authorities']
    
    def test_get_summary_slow_authorities(self):
        """Test get_summary identifies slow authorities."""
        monitor = AuthorityMonitor()
        
        status = {
            'moria1': {'online': True, 'latency_ms': 50.0},
            'tor26': {'online': True, 'latency_ms': 750.0},  # Slow
        }
        
        summary = monitor.get_summary(status)
        
        assert 'tor26' in summary['slow_authorities']
        assert 'moria1' not in summary['slow_authorities']
    
    def test_get_alerts_no_issues(self):
        """Test get_alerts with all authorities online."""
        monitor = AuthorityMonitor()
        
        status = {
            'moria1': {'online': True, 'latency_ms': 50.0},
            'tor26': {'online': True, 'latency_ms': 100.0},
        }
        
        alerts = monitor.get_alerts(status)
        
        assert len(alerts) == 0
    
    def test_get_alerts_offline_authority(self):
        """Test get_alerts detects offline authority."""
        monitor = AuthorityMonitor()
        
        status = {
            'moria1': {'online': True, 'latency_ms': 50.0},
            'dizum': {'online': False, 'error': 'Connection refused'},
        }
        
        alerts = monitor.get_alerts(status)
        
        assert len(alerts) == 1
        assert alerts[0]['severity'] == 'error'
        assert alerts[0]['authority'] == 'dizum'
        assert 'offline' in alerts[0]['message']
    
    def test_get_alerts_slow_authority(self):
        """Test get_alerts detects slow authority."""
        monitor = AuthorityMonitor()
        
        status = {
            'moria1': {'online': True, 'latency_ms': 50.0},
            'tor26': {'online': True, 'latency_ms': 1500.0},  # Very slow
        }
        
        alerts = monitor.get_alerts(status)
        
        assert len(alerts) == 1
        assert alerts[0]['severity'] == 'warning'
        assert alerts[0]['authority'] == 'tor26'
        assert 'slowly' in alerts[0]['message']
    
    def test_get_alerts_multiple_offline(self):
        """Test get_alerts with multiple authorities offline."""
        monitor = AuthorityMonitor()
        
        status = {
            'moria1': {'online': False, 'error': 'Timeout'},
            'tor26': {'online': False, 'error': 'Connection refused'},
            'dizum': {'online': False, 'error': 'Unreachable'},
            'gabelmoo': {'online': True, 'latency_ms': 50.0},
        }
        
        alerts = monitor.get_alerts(status)
        
        # Should have critical alert first
        critical_alerts = [a for a in alerts if a['severity'] == 'critical']
        assert len(critical_alerts) == 1
        assert '3/4' in critical_alerts[0]['message']
    
    @patch('lib.consensus.authority_monitor.urllib.request.urlopen')
    def test_check_authority_success(self, mock_urlopen):
        """Test _check_authority with successful response."""
        monitor = AuthorityMonitor()
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        result = monitor._check_authority('moria1', 'http://128.31.0.39:9131')
        
        assert result['online'] is True
        assert result['status_code'] == 200
        assert result['latency_ms'] is not None
        assert result['error'] is None
    
    @patch('lib.consensus.authority_monitor.urllib.request.urlopen')
    def test_check_authority_http_error(self, mock_urlopen):
        """Test _check_authority with HTTP error."""
        import urllib.error
        
        monitor = AuthorityMonitor()
        
        # Mock HTTP 503 error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url='http://test', code=503, msg='Service Unavailable',
            hdrs={}, fp=None
        )
        
        result = monitor._check_authority('moria1', 'http://128.31.0.39:9131')
        
        assert result['online'] is False
        assert result['status_code'] == 503
        assert 'HTTP 503' in result['error']
    
    @patch('lib.consensus.authority_monitor.urllib.request.urlopen')
    def test_check_authority_timeout(self, mock_urlopen):
        """Test _check_authority with timeout."""
        import socket
        
        monitor = AuthorityMonitor()
        
        # Mock timeout
        mock_urlopen.side_effect = socket.timeout()
        
        result = monitor._check_authority('moria1', 'http://128.31.0.39:9131')
        
        assert result['online'] is False
        assert result['latency_ms'] is None


class TestDefaultAuthorityEndpoints:
    """Tests for DEFAULT_AUTHORITY_ENDPOINTS constant."""
    
    def test_endpoints_count(self):
        """Test that we have expected number of default endpoints."""
        assert len(DEFAULT_AUTHORITY_ENDPOINTS) == 9
    
    def test_endpoints_format(self):
        """Test that endpoint URLs have correct format."""
        for name, url in DEFAULT_AUTHORITY_ENDPOINTS.items():
            assert url.startswith('http://')
            assert ':' in url.split('//')[-1]  # Has port
    
    def test_known_authorities_present(self):
        """Test that known authorities are present."""
        expected = {'moria1', 'tor26', 'dizum', 'gabelmoo', 'bastet',
                   'dannenberg', 'maatuska', 'longclaw', 'faravahar'}
        assert set(DEFAULT_AUTHORITY_ENDPOINTS.keys()) == expected
