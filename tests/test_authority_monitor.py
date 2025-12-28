"""
Tests for authority_monitor.py

Tests the AuthorityMonitor class that monitors directory authority health.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'allium', 'lib'))

from consensus.authority_monitor import (
    AuthorityMonitor,
    DEFAULT_AUTHORITY_ENDPOINTS,
)


class TestAuthorityMonitor:
    """Tests for AuthorityMonitor class."""
    
    def test_init_default(self):
        """Test default initialization."""
        monitor = AuthorityMonitor()
        assert monitor.timeout == 10
        assert monitor.authorities == []
        assert monitor._last_check is None
        assert monitor._cached_status is None
    
    def test_init_with_timeout(self):
        """Test initialization with custom timeout."""
        monitor = AuthorityMonitor(timeout=30)
        assert monitor.timeout == 30
    
    def test_init_with_authorities(self):
        """Test initialization with authorities list."""
        authorities = [
            {'nickname': 'test1', 'address': '127.0.0.1', 'dir_port': '80'},
            {'nickname': 'test2', 'address': '127.0.0.2', 'dir_port': '443'},
        ]
        monitor = AuthorityMonitor(authorities=authorities)
        assert monitor.authorities == authorities
    
    def test_get_authority_endpoints_default(self):
        """Test getting default authority endpoints."""
        monitor = AuthorityMonitor()
        endpoints = monitor._get_authority_endpoints()
        
        assert endpoints == DEFAULT_AUTHORITY_ENDPOINTS
        assert 'moria1' in endpoints
        assert 'tor26' in endpoints
    
    def test_get_authority_endpoints_custom(self):
        """Test getting custom authority endpoints."""
        authorities = [
            {'nickname': 'custom1', 'address': '192.168.1.1', 'dir_port': '8080'},
        ]
        monitor = AuthorityMonitor(authorities=authorities)
        endpoints = monitor._get_authority_endpoints()
        
        assert 'custom1' in endpoints
        assert endpoints['custom1'] == 'http://192.168.1.1:8080'
    
    def test_get_summary_empty(self):
        """Test getting summary with no status data."""
        monitor = AuthorityMonitor()
        monitor._cached_status = {}
        
        summary = monitor.get_summary({})
        
        assert summary['total_authorities'] == 0
        assert summary['online_count'] == 0
        assert summary['offline_count'] == 0
    
    def test_get_summary_with_data(self):
        """Test getting summary with status data."""
        monitor = AuthorityMonitor()
        
        status = {
            'moria1': {'online': True, 'latency_ms': 100},
            'tor26': {'online': True, 'latency_ms': 150},
            'dizum': {'online': False, 'latency_ms': None},
            'gabelmoo': {'online': True, 'latency_ms': 600},  # Slow
        }
        
        summary = monitor.get_summary(status)
        
        assert summary['total_authorities'] == 4
        assert summary['online_count'] == 3
        assert summary['offline_count'] == 1
        assert summary['average_latency_ms'] is not None
        assert 'dizum' in summary['offline_authorities']
        assert 'gabelmoo' in summary['slow_authorities']
    
    def test_get_alerts_none(self):
        """Test getting alerts when all authorities are healthy."""
        monitor = AuthorityMonitor()
        
        status = {
            'moria1': {'online': True, 'latency_ms': 100},
            'tor26': {'online': True, 'latency_ms': 150},
        }
        
        alerts = monitor.get_alerts(status)
        
        assert len(alerts) == 0
    
    def test_get_alerts_offline(self):
        """Test getting alerts for offline authority."""
        monitor = AuthorityMonitor()
        
        status = {
            'moria1': {'online': False, 'latency_ms': None, 'error': 'Connection refused'},
            'tor26': {'online': True, 'latency_ms': 150},
        }
        
        alerts = monitor.get_alerts(status)
        
        assert len(alerts) == 1
        assert alerts[0]['severity'] == 'error'
        assert alerts[0]['authority'] == 'moria1'
        assert 'offline' in alerts[0]['message']
    
    def test_get_alerts_slow(self):
        """Test getting alerts for slow authority."""
        monitor = AuthorityMonitor()
        
        status = {
            'moria1': {'online': True, 'latency_ms': 1500},  # Very slow
            'tor26': {'online': True, 'latency_ms': 150},
        }
        
        alerts = monitor.get_alerts(status)
        
        assert len(alerts) == 1
        assert alerts[0]['severity'] == 'warning'
        assert alerts[0]['authority'] == 'moria1'
        assert 'slowly' in alerts[0]['message']
    
    def test_get_alerts_critical(self):
        """Test getting critical alert when many authorities offline."""
        monitor = AuthorityMonitor()
        
        status = {
            'moria1': {'online': False, 'latency_ms': None, 'error': 'Timeout'},
            'tor26': {'online': False, 'latency_ms': None, 'error': 'Timeout'},
            'dizum': {'online': False, 'latency_ms': None, 'error': 'Timeout'},
            'gabelmoo': {'online': True, 'latency_ms': 150},
        }
        
        alerts = monitor.get_alerts(status)
        
        # Should have critical alert first, then individual offline alerts
        assert len(alerts) >= 1
        assert alerts[0]['severity'] == 'critical'
        assert '3/4' in alerts[0]['message']
    
    @patch('consensus.authority_monitor.urllib.request.urlopen')
    def test_check_authority_success(self, mock_urlopen):
        """Test successful authority check."""
        monitor = AuthorityMonitor()
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        result = monitor._check_authority('test', 'http://example.com')
        
        assert result['online'] == True
        assert result['status_code'] == 200
        assert result['error'] is None
        assert result['latency_ms'] is not None
    
    @patch('consensus.authority_monitor.urllib.request.urlopen')
    def test_check_authority_http_error(self, mock_urlopen):
        """Test authority check with HTTP error."""
        import urllib.error
        
        monitor = AuthorityMonitor()
        
        # Mock HTTP error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            'http://example.com', 503, 'Service Unavailable', {}, None
        )
        
        result = monitor._check_authority('test', 'http://example.com')
        
        assert result['online'] == False
        assert result['status_code'] == 503
        assert 'HTTP 503' in result['error']
    
    @patch('consensus.authority_monitor.urllib.request.urlopen')
    def test_check_authority_timeout(self, mock_urlopen):
        """Test authority check with timeout."""
        import socket
        
        monitor = AuthorityMonitor()
        
        # Mock timeout
        mock_urlopen.side_effect = socket.timeout('Connection timed out')
        
        result = monitor._check_authority('test', 'http://example.com')
        
        assert result['online'] == False
        assert result['latency_ms'] is None
    
    def test_caching(self):
        """Test that results are cached."""
        monitor = AuthorityMonitor()
        
        # Set cached status
        cached_status = {
            'moria1': {'online': True, 'latency_ms': 100},
        }
        monitor._cached_status = cached_status
        monitor._last_check = datetime.utcnow()
        
        # Should return cached data without making requests
        result = monitor.check_all_authorities(force=False)
        
        assert result == cached_status
    
    def test_force_refresh(self):
        """Test that force=True bypasses cache."""
        monitor = AuthorityMonitor()
        
        # Set cached status
        cached_status = {
            'moria1': {'online': True, 'latency_ms': 100},
        }
        monitor._cached_status = cached_status
        monitor._last_check = datetime.utcnow()
        
        # With force=True, should make new requests (will fail without network)
        # We just verify it doesn't immediately return the cached data
        with patch.object(monitor, '_check_authority') as mock_check:
            mock_check.return_value = {
                'online': True,
                'latency_ms': 200,
                'status_code': 200,
                'error': None,
                'checked_at': datetime.utcnow().isoformat(),
            }
            
            result = monitor.check_all_authorities(force=True)
            
            # Verify check_authority was called
            assert mock_check.called


class TestDefaultAuthorityEndpoints:
    """Tests for DEFAULT_AUTHORITY_ENDPOINTS constant."""
    
    def test_endpoint_count(self):
        """Test that we have endpoints for all known authorities."""
        assert len(DEFAULT_AUTHORITY_ENDPOINTS) == 9
    
    def test_endpoint_format(self):
        """Test that all endpoints are valid URLs."""
        for name, endpoint in DEFAULT_AUTHORITY_ENDPOINTS.items():
            assert endpoint.startswith('http://')
            assert ':' in endpoint.split('//')[1]  # Has port
    
    def test_known_authorities(self):
        """Test that known authorities are present."""
        assert 'moria1' in DEFAULT_AUTHORITY_ENDPOINTS
        assert 'tor26' in DEFAULT_AUTHORITY_ENDPOINTS
        assert 'gabelmoo' in DEFAULT_AUTHORITY_ENDPOINTS
        assert 'faravahar' in DEFAULT_AUTHORITY_ENDPOINTS
