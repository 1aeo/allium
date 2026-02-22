"""
Unit tests for retry infrastructure in allium/lib/workers.py.

Tests the _retry_with_backoff() function, _is_retryable_error() classifier,
and the integration of retry into _fetch_with_cache_fallback().
"""

import socket
import time
import urllib.error

import pytest
from unittest.mock import patch, MagicMock, call

from allium.lib.workers import (
    _retry_with_backoff,
    _is_retryable_error,
    _fetch_with_cache_fallback,
    TotalTimeoutError,
    APIConfig,
    _cache_manager,
)


# ============================================================================
# Tests for _is_retryable_error()
# ============================================================================

class TestIsRetryableError:
    """Tests for the _is_retryable_error() classifier."""

    def test_total_timeout_is_retryable(self):
        assert _is_retryable_error(TotalTimeoutError("timeout")) is True

    def test_socket_timeout_is_retryable(self):
        assert _is_retryable_error(socket.timeout("timeout")) is True

    def test_timeout_error_is_retryable(self):
        assert _is_retryable_error(TimeoutError("timeout")) is True

    def test_connection_reset_is_retryable(self):
        assert _is_retryable_error(ConnectionResetError("reset")) is True

    def test_connection_refused_is_retryable(self):
        assert _is_retryable_error(ConnectionRefusedError("refused")) is True

    def test_connection_aborted_is_retryable(self):
        assert _is_retryable_error(ConnectionAbortedError("aborted")) is True

    def test_broken_pipe_is_retryable(self):
        assert _is_retryable_error(BrokenPipeError("pipe")) is True

    def test_url_error_with_timeout_reason_is_retryable(self):
        err = urllib.error.URLError(reason=socket.timeout("timeout"))
        assert _is_retryable_error(err) is True

    def test_url_error_with_os_error_reason_is_retryable(self):
        err = urllib.error.URLError(reason=OSError("Network is unreachable"))
        assert _is_retryable_error(err) is True

    def test_http_500_is_retryable(self):
        err = urllib.error.HTTPError(
            url="http://example.com", code=500, msg="Server Error",
            hdrs=MagicMock(), fp=MagicMock()
        )
        assert _is_retryable_error(err) is True

    def test_http_502_is_retryable(self):
        err = urllib.error.HTTPError(
            url="http://example.com", code=502, msg="Bad Gateway",
            hdrs=MagicMock(), fp=MagicMock()
        )
        assert _is_retryable_error(err) is True

    def test_http_503_is_retryable(self):
        err = urllib.error.HTTPError(
            url="http://example.com", code=503, msg="Service Unavailable",
            hdrs=MagicMock(), fp=MagicMock()
        )
        assert _is_retryable_error(err) is True

    def test_http_429_is_retryable(self):
        err = urllib.error.HTTPError(
            url="http://example.com", code=429, msg="Too Many Requests",
            hdrs=MagicMock(), fp=MagicMock()
        )
        assert _is_retryable_error(err) is True

    def test_http_404_is_not_retryable(self):
        err = urllib.error.HTTPError(
            url="http://example.com", code=404, msg="Not Found",
            hdrs=MagicMock(), fp=MagicMock()
        )
        assert _is_retryable_error(err) is False

    def test_http_400_is_not_retryable(self):
        err = urllib.error.HTTPError(
            url="http://example.com", code=400, msg="Bad Request",
            hdrs=MagicMock(), fp=MagicMock()
        )
        assert _is_retryable_error(err) is False

    def test_http_304_is_not_retryable(self):
        err = urllib.error.HTTPError(
            url="http://example.com", code=304, msg="Not Modified",
            hdrs=MagicMock(), fp=MagicMock()
        )
        assert _is_retryable_error(err) is False

    def test_value_error_is_not_retryable(self):
        assert _is_retryable_error(ValueError("bad value")) is False

    def test_key_error_is_not_retryable(self):
        assert _is_retryable_error(KeyError("missing")) is False

    def test_json_decode_error_is_not_retryable(self):
        import json
        try:
            json.loads("{invalid}")
        except json.JSONDecodeError as e:
            assert _is_retryable_error(e) is False

    def test_os_error_is_retryable(self):
        assert _is_retryable_error(OSError("Network unreachable")) is True


# ============================================================================
# Tests for _retry_with_backoff()
# ============================================================================

class TestRetryWithBackoff:
    """Tests for the _retry_with_backoff() generic retry wrapper."""

    def test_succeeds_first_try(self):
        """Function succeeds on first attempt - no retries needed."""
        fn = MagicMock(return_value="success")
        result = _retry_with_backoff(fn, retry_count=3, retry_delay_base=0.01)
        assert result == "success"
        assert fn.call_count == 1

    def test_succeeds_after_retries(self):
        """Function fails then succeeds - retries recover."""
        fn = MagicMock(side_effect=[
            socket.timeout("timeout"),
            ConnectionResetError("reset"),
            "success",
        ])
        result = _retry_with_backoff(fn, retry_count=3, retry_delay_base=0.01)
        assert result == "success"
        assert fn.call_count == 3

    def test_exhausts_retries(self):
        """Function keeps failing - exhausts all retries and raises."""
        fn = MagicMock(side_effect=socket.timeout("timeout"))
        with pytest.raises(socket.timeout):
            _retry_with_backoff(fn, retry_count=2, retry_delay_base=0.01)
        assert fn.call_count == 3  # 1 initial + 2 retries

    def test_non_retryable_raises_immediately(self):
        """Non-retryable error is not retried."""
        fn = MagicMock(side_effect=ValueError("bad data"))
        with pytest.raises(ValueError, match="bad data"):
            _retry_with_backoff(fn, retry_count=3, retry_delay_base=0.01)
        assert fn.call_count == 1  # No retries

    def test_http_404_raises_immediately(self):
        """HTTP 404 (client error) is not retried."""
        err = urllib.error.HTTPError(
            url="http://example.com", code=404, msg="Not Found",
            hdrs=MagicMock(), fp=MagicMock()
        )
        fn = MagicMock(side_effect=err)
        with pytest.raises(urllib.error.HTTPError):
            _retry_with_backoff(fn, retry_count=3, retry_delay_base=0.01)
        assert fn.call_count == 1

    def test_http_500_is_retried(self):
        """HTTP 500 (server error) is retried."""
        err = urllib.error.HTTPError(
            url="http://example.com", code=500, msg="Server Error",
            hdrs=MagicMock(), fp=MagicMock()
        )
        fn = MagicMock(side_effect=[err, "success"])
        result = _retry_with_backoff(fn, retry_count=2, retry_delay_base=0.01)
        assert result == "success"
        assert fn.call_count == 2

    def test_zero_retries_means_single_attempt(self):
        """retry_count=0 means only one attempt."""
        fn = MagicMock(side_effect=socket.timeout("timeout"))
        with pytest.raises(socket.timeout):
            _retry_with_backoff(fn, retry_count=0, retry_delay_base=0.01)
        assert fn.call_count == 1

    def test_log_function_called_on_retry(self):
        """Log function receives retry progress messages."""
        messages = []
        fn = MagicMock(side_effect=[
            socket.timeout("timeout"),
            "success",
        ])
        result = _retry_with_backoff(
            fn, retry_count=2, retry_delay_base=0.01,
            log_fn=messages.append, operation_name="test op"
        )
        assert result == "success"
        assert len(messages) == 1
        assert "test op" in messages[0]
        assert "attempt 1/3" in messages[0]
        assert "retrying" in messages[0]

    def test_log_function_called_on_exhaustion(self):
        """Log function receives exhaustion message when all retries fail."""
        messages = []
        fn = MagicMock(side_effect=socket.timeout("timeout"))
        with pytest.raises(socket.timeout):
            _retry_with_backoff(
                fn, retry_count=1, retry_delay_base=0.01,
                log_fn=messages.append, operation_name="test op"
            )
        # Should get retry message + exhaustion message
        assert len(messages) == 2
        assert "giving up" in messages[1]

    def test_passes_args_and_kwargs(self):
        """Arguments and keyword arguments are forwarded correctly."""
        fn = MagicMock(return_value="ok")
        result = _retry_with_backoff(
            fn, args=("a", "b"), kwargs={"key": "val"},
            retry_count=0, retry_delay_base=0.01
        )
        assert result == "ok"
        fn.assert_called_once_with("a", "b", key="val")

    @patch('allium.lib.workers.time.sleep')
    def test_backoff_delay_increases(self, mock_sleep):
        """Verify exponential backoff delays increase between retries."""
        fn = MagicMock(side_effect=[
            socket.timeout("t"),
            socket.timeout("t"),
            "success",
        ])
        _retry_with_backoff(fn, retry_count=3, retry_delay_base=1.0)
        
        # Should have slept twice (before retry 1 and retry 2)
        assert mock_sleep.call_count == 2
        
        # First delay: base * 2^0 + jitter ≈ 1.0-2.0
        first_delay = mock_sleep.call_args_list[0][0][0]
        assert 1.0 <= first_delay < 2.0
        
        # Second delay: base * 2^1 + jitter ≈ 2.0-3.0
        second_delay = mock_sleep.call_args_list[1][0][0]
        assert 2.0 <= second_delay < 3.0

    def test_total_timeout_error_is_retried(self):
        """TotalTimeoutError (custom exception) is retried."""
        fn = MagicMock(side_effect=[
            TotalTimeoutError("total timeout"),
            "success",
        ])
        result = _retry_with_backoff(fn, retry_count=2, retry_delay_base=0.01)
        assert result == "success"
        assert fn.call_count == 2


# ============================================================================
# Tests for retry integration in _fetch_with_cache_fallback()
# ============================================================================

class TestFetchWithCacheFallbackRetry:
    """Tests for retry behavior integrated into _fetch_with_cache_fallback()."""

    def _make_config(self, **overrides):
        """Create a test APIConfig."""
        defaults = dict(
            api_name='test_api',
            display_name='test API',
            cache_max_age_hours=1,
            timeout_fresh_cache=5,
            timeout_stale_cache=10,
            use_conditional_requests=False,
            retry_count=2,
            retry_delay_base=0.01,
        )
        defaults.update(overrides)
        return APIConfig(**defaults)

    @patch('allium.lib.workers._mark_ready')
    @patch('allium.lib.workers._mark_stale')
    @patch('allium.lib.workers._save_cache')
    @patch('allium.lib.workers._cache_manager')
    @patch('allium.lib.workers._fetch_url_with_total_timeout')
    def test_retries_on_timeout_then_succeeds(self, mock_fetch, mock_cm, mock_save,
                                               mock_stale, mock_ready):
        """Retry recovers from transient timeout."""
        mock_cm.get_cache_age.return_value = None  # No cache
        
        # First call: timeout, second call: success
        mock_fetch.side_effect = [
            TotalTimeoutError("timeout"),
            b'{"relays": [{"id": 1}]}',
        ]
        
        config = self._make_config()
        result = _fetch_with_cache_fallback(
            url="http://test.example.com/api",
            config=config,
        )
        
        assert result is not None
        assert result["relays"] == [{"id": 1}]
        assert mock_fetch.call_count == 2  # Retried once
        mock_ready.assert_called()

    @patch('allium.lib.workers._mark_ready')
    @patch('allium.lib.workers._mark_stale')
    @patch('allium.lib.workers._save_cache')
    @patch('allium.lib.workers._cache_manager')
    @patch('allium.lib.workers._fetch_url_with_total_timeout')
    def test_falls_back_to_cache_after_retries_exhausted(self, mock_fetch, mock_cm,
                                                          mock_save, mock_stale, mock_ready):
        """Falls back to cache when all retries are exhausted."""
        cached = {"relays": [{"id": "cached"}]}
        mock_cm.get_cache_age.return_value = 7200  # 2 hours (stale)
        mock_cm.load_cache.return_value = cached
        
        with patch('allium.lib.workers._load_cache', return_value=cached):
            # All calls timeout
            mock_fetch.side_effect = TotalTimeoutError("timeout")
            
            config = self._make_config(retry_count=2, cache_max_age_hours=1)
            result = _fetch_with_cache_fallback(
                url="http://test.example.com/api",
                config=config,
            )
        
        assert result is not None
        assert result["relays"] == [{"id": "cached"}]
        assert mock_fetch.call_count == 3  # 1 initial + 2 retries

    @patch('allium.lib.workers._mark_ready')
    @patch('allium.lib.workers._mark_stale')
    @patch('allium.lib.workers._save_cache')
    @patch('allium.lib.workers._cache_manager')
    @patch('allium.lib.workers._fetch_url_with_total_timeout')
    def test_skips_retries_with_fresh_cache(self, mock_fetch, mock_cm, mock_save,
                                             mock_stale, mock_ready):
        """When fresh cache exists, retries are skipped (fast fallback)."""
        cached = {"relays": [{"id": "fresh_cached"}]}
        mock_cm.get_cache_age.return_value = 1800  # 30 minutes (fresh, < 1 hour)
        
        with patch('allium.lib.workers._load_cache', return_value=cached):
            # Single timeout - no retry because fresh cache
            mock_fetch.side_effect = TotalTimeoutError("timeout")
            
            config = self._make_config(retry_count=3, cache_max_age_hours=1)
            result = _fetch_with_cache_fallback(
                url="http://test.example.com/api",
                config=config,
            )
        
        assert result is not None
        assert result["relays"] == [{"id": "fresh_cached"}]
        assert mock_fetch.call_count == 1  # No retries with fresh cache

    @patch('allium.lib.workers._mark_ready')
    @patch('allium.lib.workers._mark_stale')
    @patch('allium.lib.workers._save_cache')
    @patch('allium.lib.workers._cache_manager')
    @patch('allium.lib.workers._fetch_url_with_total_timeout')
    def test_json_parse_error_falls_back_to_cache(self, mock_fetch, mock_cm, mock_save,
                                                    mock_stale, mock_ready):
        """Malformed JSON response falls back to cache."""
        cached = {"relays": [{"id": "cached"}]}
        mock_cm.get_cache_age.return_value = 7200  # Stale
        
        with patch('allium.lib.workers._load_cache', return_value=cached):
            # Return invalid JSON
            mock_fetch.return_value = b'{invalid json!!}'
            
            config = self._make_config()
            result = _fetch_with_cache_fallback(
                url="http://test.example.com/api",
                config=config,
            )
        
        assert result is not None
        assert result["relays"] == [{"id": "cached"}]

    @patch('allium.lib.workers._mark_ready')
    @patch('allium.lib.workers._mark_stale')
    @patch('allium.lib.workers._save_cache')
    @patch('allium.lib.workers._cache_manager')
    @patch('allium.lib.workers._fetch_url_with_total_timeout')
    def test_json_parse_error_returns_none_without_cache(self, mock_fetch, mock_cm,
                                                          mock_save, mock_stale, mock_ready):
        """Malformed JSON with no cache returns None."""
        mock_cm.get_cache_age.return_value = None  # No cache
        
        with patch('allium.lib.workers._load_cache', return_value=None):
            mock_fetch.return_value = b'{invalid json}'
            
            config = self._make_config()
            result = _fetch_with_cache_fallback(
                url="http://test.example.com/api",
                config=config,
            )
        
        assert result is None
        mock_stale.assert_called()


# ============================================================================
# Tests for APIConfig retry defaults
# ============================================================================

class TestAPIConfigRetryDefaults:
    """Test that APIConfig has proper retry defaults."""

    def test_default_retry_count(self):
        config = APIConfig(
            api_name='test', display_name='test',
            cache_max_age_hours=1, timeout_fresh_cache=30, timeout_stale_cache=60,
        )
        assert config.retry_count == 3
        assert config.retry_delay_base == 1.0
        assert config.retry_on_fresh_cache is False

    def test_custom_retry_count(self):
        config = APIConfig(
            api_name='test', display_name='test',
            cache_max_age_hours=1, timeout_fresh_cache=30, timeout_stale_cache=60,
            retry_count=5, retry_delay_base=2.0, retry_on_fresh_cache=True,
        )
        assert config.retry_count == 5
        assert config.retry_delay_base == 2.0
        assert config.retry_on_fresh_cache is True

    def test_production_configs_have_retries(self):
        """Verify all production API configs have retry enabled."""
        from allium.lib.workers import (
            DETAILS_CONFIG, UPTIME_CONFIG, BANDWIDTH_CONFIG, AROI_CONFIG,
        )
        assert DETAILS_CONFIG.retry_count >= 1
        assert UPTIME_CONFIG.retry_count >= 1
        assert BANDWIDTH_CONFIG.retry_count >= 1
        assert AROI_CONFIG.retry_count >= 1
