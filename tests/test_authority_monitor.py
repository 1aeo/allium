"""
Tests for authority_monitor.py

Tests the AuthorityMonitor class that monitors directory authority health.

IMPORTANT: These tests verify authority health monitoring functionality.
If directory authority endpoints change (IP addresses, ports), update
DEFAULT_AUTHORITY_ENDPOINTS in authority_monitor.py.

Current directory authorities (as of 2025):
- moria1, tor26, dizum, gabelmoo, bastet, dannenberg, maatuska, longclaw, faravahar
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from allium.lib.consensus.authority_monitor import (
    AuthorityMonitor,
    DEFAULT_AUTHORITY_ENDPOINTS,
)


# ============================================================================
# Expected authority names - update if Tor adds/removes authorities
# ============================================================================
EXPECTED_AUTHORITY_NAMES = {
    'moria1', 'tor26', 'dizum', 'gabelmoo', 'bastet',
    'dannenberg', 'maatuska', 'longclaw', 'faravahar'
}


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
    
    @patch('allium.lib.consensus.authority_monitor.socket.socket')
    def test_check_authority_success(self, mock_socket_class):
        """Test successful authority check."""
        monitor = AuthorityMonitor()
        
        # Mock successful socket connection (connect_ex returns 0 for success)
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        mock_socket_class.return_value = mock_sock
        
        result = monitor._check_authority('test', 'http://127.0.0.1:80')
        
        assert result['online'] == True
        # The implementation uses socket, not HTTP, so status_code is always None
        assert result['status_code'] is None
        assert result['error'] is None
        assert result['latency_ms'] is not None
    
    @patch('allium.lib.consensus.authority_monitor.socket.socket')
    def test_check_authority_http_error(self, mock_socket_class):
        """Test authority check with connection refused."""
        monitor = AuthorityMonitor()
        
        # Mock connection refused (non-zero return from connect_ex)
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 111  # Connection refused error code
        mock_socket_class.return_value = mock_sock
        
        result = monitor._check_authority('test', 'http://127.0.0.1:80')
        
        assert result['online'] == False
        assert 'Connection refused' in result['error']
    
    @patch('allium.lib.consensus.authority_monitor.socket.socket')
    def test_check_authority_timeout(self, mock_socket_class):
        """Test authority check with timeout."""
        import socket as socket_module
        
        monitor = AuthorityMonitor()
        
        # Mock timeout by having socket operations raise socket.timeout
        mock_sock = MagicMock()
        mock_sock.connect_ex.side_effect = socket_module.timeout('Connection timed out')
        mock_socket_class.return_value = mock_sock
        
        result = monitor._check_authority('test', 'http://127.0.0.1:80')
        
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
    """Tests for DEFAULT_AUTHORITY_ENDPOINTS constant.
    
    IMPORTANT: If directory authority endpoints change (new IP, new port),
    update DEFAULT_AUTHORITY_ENDPOINTS in authority_monitor.py.
    """
    
    def test_endpoint_count(self):
        """Test that we have endpoints for all 9 known authorities."""
        assert len(DEFAULT_AUTHORITY_ENDPOINTS) == 9, \
            f"Expected 9 authority endpoints, got {len(DEFAULT_AUTHORITY_ENDPOINTS)}. " \
            "If Tor added/removed authorities, update DEFAULT_AUTHORITY_ENDPOINTS."
    
    def test_endpoint_format(self):
        """Test that all endpoints are valid HTTP URLs with ports."""
        for name, endpoint in DEFAULT_AUTHORITY_ENDPOINTS.items():
            assert endpoint.startswith('http://'), \
                f"Endpoint for {name} should start with http://"
            
            # Should have format http://IP:PORT
            parts = endpoint.replace('http://', '').split(':')
            assert len(parts) == 2, \
                f"Endpoint for {name} should have format http://IP:PORT"
            
            # Port should be a number
            try:
                port = int(parts[1])
                assert 1 <= port <= 65535, \
                    f"Invalid port {port} for {name}"
            except ValueError:
                pytest.fail(f"Port is not a number for {name}: {parts[1]}")
    
    def test_all_expected_authorities_present(self):
        """Test that all expected directory authorities have endpoints."""
        missing = EXPECTED_AUTHORITY_NAMES - set(DEFAULT_AUTHORITY_ENDPOINTS.keys())
        extra = set(DEFAULT_AUTHORITY_ENDPOINTS.keys()) - EXPECTED_AUTHORITY_NAMES
        
        assert not missing, f"Missing authority endpoints: {missing}"
        assert not extra, f"Unknown authority endpoints: {extra}"
    
    def test_endpoints_are_unique(self):
        """Test that no two authorities share the same endpoint."""
        endpoints = list(DEFAULT_AUTHORITY_ENDPOINTS.values())
        assert len(endpoints) == len(set(endpoints)), \
            "Duplicate authority endpoints detected"


class TestAuthorityHealthSummary:
    """Tests for authority health summary calculations."""
    
    def test_summary_counts_online_offline(self):
        """Test that summary correctly counts online/offline authorities."""
        monitor = AuthorityMonitor()
        
        status = {
            'moria1': {'online': True, 'latency_ms': 50},
            'tor26': {'online': True, 'latency_ms': 75},
            'dizum': {'online': False, 'latency_ms': None, 'error': 'Timeout'},
        }
        
        summary = monitor.get_summary(status)
        
        assert summary['online_count'] == 2
        assert summary['offline_count'] == 1
    
    def test_summary_identifies_slow_authorities(self):
        """Test that authorities with high latency are flagged as slow.
        
        Note: The slow threshold is >500ms based on the implementation.
        """
        monitor = AuthorityMonitor()
        
        status = {
            'moria1': {'online': True, 'latency_ms': 50},   # Fast
            'tor26': {'online': True, 'latency_ms': 450},   # Normal (<=500ms)
            'dizum': {'online': True, 'latency_ms': 600},   # Slow (>500ms)
        }
        
        summary = monitor.get_summary(status)
        
        # Only dizum should be in slow_authorities (>500ms)
        assert 'dizum' in summary['slow_authorities']
        assert 'moria1' not in summary['slow_authorities']
        assert 'tor26' not in summary['slow_authorities']
    
    def test_summary_calculates_average_latency(self):
        """Test that average latency is calculated correctly."""
        monitor = AuthorityMonitor()
        
        status = {
            'moria1': {'online': True, 'latency_ms': 100},
            'tor26': {'online': True, 'latency_ms': 200},
            'dizum': {'online': False, 'latency_ms': None},  # Should be excluded
        }
        
        summary = monitor.get_summary(status)
        
        # Average of 100 and 200 = 150
        assert summary['average_latency_ms'] == 150


class TestAlertGeneration:
    """Tests for alert generation logic."""
    
    def test_critical_alert_threshold(self):
        """Test that critical alert is generated when many authorities offline."""
        monitor = AuthorityMonitor()
        
        # 5 out of 9 offline = critical
        status = {
            'moria1': {'online': False, 'error': 'Timeout'},
            'tor26': {'online': False, 'error': 'Timeout'},
            'dizum': {'online': False, 'error': 'Timeout'},
            'gabelmoo': {'online': False, 'error': 'Timeout'},
            'bastet': {'online': False, 'error': 'Timeout'},
            'dannenberg': {'online': True, 'latency_ms': 50},
            'maatuska': {'online': True, 'latency_ms': 50},
            'longclaw': {'online': True, 'latency_ms': 50},
            'faravahar': {'online': True, 'latency_ms': 50},
        }
        
        alerts = monitor.get_alerts(status)
        
        critical_alerts = [a for a in alerts if a['severity'] == 'critical']
        assert len(critical_alerts) >= 1
    
    def test_alert_includes_authority_name(self):
        """Test that alerts include the authority name."""
        monitor = AuthorityMonitor()
        
        status = {
            'moria1': {'online': False, 'error': 'Connection refused'},
            'tor26': {'online': True, 'latency_ms': 50},
        }
        
        alerts = monitor.get_alerts(status)
        
        # Should have alert for moria1
        moria1_alerts = [a for a in alerts if a.get('authority') == 'moria1']
        assert len(moria1_alerts) >= 1
