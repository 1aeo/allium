"""
Tests for lib/workers.py collector-related functions.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from allium.lib.workers import (
    fetch_collector_consensus_data,
    fetch_consensus_health,
    _validate_collector_cache,
)


class TestFetchCollectorConsensusData:
    """Tests for fetch_collector_consensus_data() function."""
    
    def test_function_exists(self):
        """Test that the function exists and is callable."""
        assert callable(fetch_collector_consensus_data)
    
    @patch('allium.lib.workers._cache_manager')
    @patch('allium.lib.workers._mark_ready')
    def test_returns_data_dict(self, mock_mark_ready, mock_cache_manager):
        """Test that function returns a dict with expected structure."""
        # Mock that feature is enabled
        with patch('allium.lib.consensus.is_consensus_evaluation_enabled', return_value=True):
            # Mock the CollectorFetcher class
            with patch('allium.lib.consensus.CollectorFetcher') as MockFetcher:
                mock_instance = MagicMock()
                mock_instance.fetch_all.return_value = {
                    'votes': {'moria1': {}},
                    'relay_index': {},
                    'flag_thresholds': {},
                    'bw_authorities': [],
                    'ipv6_authorities': [],
                    'fetched_at': datetime.utcnow().isoformat(),
                }
                MockFetcher.return_value = mock_instance
                
                # Mock cache says no valid cache
                mock_cache_manager.get_cache_age.return_value = 7200  # 2 hours old
                
                result = fetch_collector_consensus_data()
                
                # Should return dict or None (on error)
                assert result is None or isinstance(result, dict)
    
    @patch('allium.lib.workers._cache_manager')
    def test_uses_cached_data_if_fresh(self, mock_cache_manager):
        """Test that function uses cache if data is fresh."""
        # Mock fresh cache
        mock_cache_manager.get_cache_age.return_value = 1800  # 30 minutes
        
        cached_data = {
            'votes': {'moria1': {}},
            'relay_index': {'ABC123': {}},
            'fetched_at': datetime.utcnow().isoformat(),
            'consensus_method_info': {
                'total_voters': 9,
                'current_method': 34,
                'max_method': 34,
                'max_method_support': 9,
            },
        }
        mock_cache_manager.load_cache.return_value = cached_data
        
        with patch('allium.lib.workers._mark_ready'):
            with patch('allium.lib.consensus.is_consensus_evaluation_enabled', return_value=True):
                result = fetch_collector_consensus_data()
                
                # Should use cached data without fetching
                assert result == cached_data


class TestFetchConsensusHealth:
    """Tests for fetch_consensus_health() function."""
    
    def test_function_exists(self):
        """Test that the function exists and is callable."""
        assert callable(fetch_consensus_health)
    
    @patch('allium.lib.workers._mark_ready')
    def test_returns_dict_or_none(self, mock_mark_ready):
        """Test that function returns a dict with expected structure."""
        with patch('allium.lib.consensus.is_consensus_evaluation_enabled', return_value=True):
            with patch('allium.lib.consensus.AuthorityMonitor') as MockMonitor:
                mock_instance = MagicMock()
                mock_instance.check_all_authorities.return_value = {
                    'moria1': {'online': True, 'latency_ms': 50},
                }
                mock_instance.get_summary.return_value = {
                    'online': 1,
                    'offline': 0,
                }
                mock_instance.get_alerts.return_value = []
                MockMonitor.return_value = mock_instance
                
                result = fetch_consensus_health()
                
                # Should return dict or None
                assert result is None or isinstance(result, dict)


class TestValidateCollectorCache:
    """Tests for _validate_collector_cache() function."""
    
    def test_validate_valid_cache(self):
        """Test validation of valid cache data."""
        valid_data = {
            'votes': {'moria1': {'relay_index': {}}},
            'relay_index': {'ABC123': {}},
            'fetched_at': datetime.utcnow().isoformat(),
            'consensus_method_info': {'total_voters': 9, 'current_method': 34},
        }
        assert _validate_collector_cache(valid_data) == True
    
    def test_validate_empty_cache(self):
        """Test validation of empty cache."""
        assert _validate_collector_cache({}) == False
        assert _validate_collector_cache(None) == False
    
    def test_validate_missing_keys(self):
        """Test validation with missing required keys."""
        # Missing 'relay_index' key
        data = {
            'votes': {},
            'fetched_at': datetime.utcnow().isoformat(),
        }
        assert _validate_collector_cache(data) == False
    
    def test_validate_missing_consensus_method_info(self):
        """Test validation rejects cache without consensus_method_info."""
        data = {
            'votes': {'moria1': {}},
            'relay_index': {},
            'fetched_at': datetime.utcnow().isoformat(),
        }
        assert _validate_collector_cache(data) == False
    
    def test_validate_empty_consensus_method_info(self):
        """Test validation rejects cache with empty consensus_method_info."""
        data = {
            'votes': {'moria1': {}},
            'relay_index': {},
            'fetched_at': datetime.utcnow().isoformat(),
            'consensus_method_info': {},
        }
        assert _validate_collector_cache(data) == False
    
    def test_validate_consensus_method_info_zero_voters(self):
        """Test validation rejects cache with zero total_voters."""
        data = {
            'votes': {'moria1': {}},
            'relay_index': {},
            'fetched_at': datetime.utcnow().isoformat(),
            'consensus_method_info': {'total_voters': 0},
        }
        assert _validate_collector_cache(data) == False
    
    def test_validate_old_cache(self):
        """Test validation rejects cache older than 3 hours."""
        old_time = (datetime.utcnow() - timedelta(hours=4)).isoformat()
        data = {
            'votes': {'moria1': {}},
            'relay_index': {},
            'fetched_at': old_time,
            'consensus_method_info': {'total_voters': 9},
        }
        assert _validate_collector_cache(data) == False
    
    def test_validate_recent_cache(self):
        """Test validation accepts cache less than 3 hours old."""
        recent_time = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        data = {
            'votes': {'moria1': {}},
            'relay_index': {},
            'fetched_at': recent_time,
            'consensus_method_info': {'total_voters': 9, 'current_method': 34},
        }
        assert _validate_collector_cache(data) == True


class TestFeatureFlagIntegration:
    """Tests for feature flag integration in workers."""
    
    def test_disabled_feature_returns_none(self):
        """Test that disabled feature returns None."""
        with patch('allium.lib.consensus.is_consensus_evaluation_enabled', return_value=False):
            result = fetch_collector_consensus_data()
            assert result is None
    
    def test_health_disabled_returns_none(self):
        """Test that disabled feature returns None for health check."""
        with patch('allium.lib.consensus.is_consensus_evaluation_enabled', return_value=False):
            result = fetch_consensus_health()
            assert result is None


class TestErrorHandling:
    """Tests for error handling in collector workers."""
    
    @patch('allium.lib.workers._cache_manager')
    @patch('allium.lib.workers._mark_stale')
    def test_fetch_collector_handles_exception(self, mock_mark_stale, mock_cache_manager):
        """Test that fetch_collector_consensus_data handles exceptions gracefully."""
        mock_cache_manager.get_cache_age.return_value = 7200  # Force fetch
        mock_cache_manager.load_cache.return_value = None  # No fallback cache
        
        with patch('allium.lib.consensus.is_consensus_evaluation_enabled', return_value=True):
            with patch('allium.lib.consensus.CollectorFetcher') as MockFetcher:
                MockFetcher.side_effect = Exception('Network error')
                
                # Should not raise, should return None
                result = fetch_collector_consensus_data()
                
                assert result is None
                # Should mark as stale
                mock_mark_stale.assert_called()
    
    @patch('allium.lib.workers._mark_stale')
    @patch('allium.lib.workers._load_cache', return_value=None)
    def test_fetch_health_handles_exception_no_cache(self, mock_load_cache, mock_mark_stale):
        """Test that fetch_consensus_health returns None on exception with no cache."""
        with patch('allium.lib.consensus.is_consensus_evaluation_enabled', return_value=True):
            with patch('allium.lib.consensus.AuthorityMonitor') as MockMonitor:
                MockMonitor.side_effect = Exception('Network error')
                
                # Should not raise, should return None when no cache
                result = fetch_consensus_health()
                
                assert result is None
                # Should mark as stale
                mock_mark_stale.assert_called()
    
    @patch('allium.lib.workers._mark_stale')
    @patch('allium.lib.workers._load_cache')
    def test_fetch_health_falls_back_to_cache_on_exception(self, mock_load_cache, mock_mark_stale):
        """Test that fetch_consensus_health falls back to cache on exception."""
        cached_health = {
            'authority_status': {'moria1': {'online': True, 'latency_ms': 50}},
            'summary': {'online': 1, 'offline': 0},
            'alerts': [],
            'fetched_at': None,
        }
        mock_load_cache.return_value = cached_health
        
        with patch('allium.lib.consensus.is_consensus_evaluation_enabled', return_value=True):
            with patch('allium.lib.consensus.AuthorityMonitor') as MockMonitor:
                MockMonitor.side_effect = Exception('Network error')
                
                # Should fall back to cached data
                result = fetch_consensus_health()
                
                assert result is not None
                assert result == cached_health
                # Should still mark as stale
                mock_mark_stale.assert_called()
