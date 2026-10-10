"""
Tests for lazy cache loading in _fetch_with_cache_fallback.

The cache is only parsed when it is needed (fallbacks, 304, fresh-cache
shortcut). A cache presumed readable that turns out not to be must still get
the cache-less retry policy (stale timeout, full retries).
"""

from unittest.mock import patch

from allium.lib.workers import (
    APIConfig,
    TotalTimeoutError,
    _fetch_with_cache_fallback,
)


def _config(**overrides):
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
def test_successful_fetch_never_loads_cache(mock_fetch, mock_cm, mock_save,
                                            mock_stale, mock_ready):
    mock_cm.get_cache_age.return_value = 60  # fresh
    mock_fetch.return_value = b'{"relays": [{"id": "new"}]}'

    with patch('allium.lib.workers._load_cache') as mock_load:
        result = _fetch_with_cache_fallback(
            url="http://test.example.com/api", config=_config())

    assert result == {"relays": [{"id": "new"}]}
    mock_load.assert_not_called()


@patch('allium.lib.workers._mark_ready')
@patch('allium.lib.workers._mark_stale')
@patch('allium.lib.workers._save_cache')
@patch('allium.lib.workers._cache_manager')
@patch('allium.lib.workers._fetch_url_with_total_timeout')
def test_unreadable_fresh_cache_refetches_like_missing_cache(
        mock_fetch, mock_cm, mock_save, mock_stale, mock_ready):
    mock_cm.get_cache_age.return_value = 60  # fresh, but unreadable below
    # Fresh-cache attempt: one try (no retries) with the fresh timeout fails;
    # the cache-less attempt then uses the stale timeout and retries.
    mock_fetch.side_effect = [
        TotalTimeoutError("timeout"),
        TotalTimeoutError("timeout"),
        b'{"relays": [{"id": "recovered"}]}',
    ]

    with patch('allium.lib.workers._load_cache', return_value=None) as mock_load:
        result = _fetch_with_cache_fallback(
            url="http://test.example.com/api", config=_config())

    assert result == {"relays": [{"id": "recovered"}]}
    timeouts = [call.args[1] for call in mock_fetch.call_args_list]
    assert timeouts == [5, 10, 10]
    mock_load.assert_called_once_with('test_api')


@patch('allium.lib.workers._mark_ready')
@patch('allium.lib.workers._mark_stale')
@patch('allium.lib.workers._save_cache')
@patch('allium.lib.workers._cache_manager')
@patch('allium.lib.workers._fetch_url_with_total_timeout')
def test_readable_fresh_cache_is_used_after_failed_fetch(
        mock_fetch, mock_cm, mock_save, mock_stale, mock_ready):
    cached = {"relays": [{"id": "cached"}]}
    mock_cm.get_cache_age.return_value = 60
    mock_fetch.side_effect = TotalTimeoutError("timeout")

    with patch('allium.lib.workers._load_cache', return_value=cached):
        result = _fetch_with_cache_fallback(
            url="http://test.example.com/api", config=_config())

    assert result == cached
    assert mock_fetch.call_count == 1


@patch('allium.lib.workers._mark_ready')
@patch('allium.lib.workers._mark_stale')
@patch('allium.lib.workers._save_cache')
@patch('allium.lib.workers._cache_manager')
@patch('allium.lib.workers._fetch_url_with_total_timeout')
def test_not_modified_loads_cache_once(mock_fetch, mock_cm, mock_save,
                                       mock_stale, mock_ready):
    import urllib.error
    cached = {"relays": [{"id": "cached"}]}
    mock_cm.get_cache_age.return_value = 60
    mock_fetch.side_effect = urllib.error.HTTPError(
        "http://test.example.com/api", 304, "Not Modified", {}, None)

    with patch('allium.lib.workers._load_cache', return_value=cached) as mock_load:
        result = _fetch_with_cache_fallback(
            url="http://test.example.com/api", config=_config())

    assert result == cached
    mock_load.assert_called_once_with('test_api')


@patch('allium.lib.workers._mark_ready')
@patch('allium.lib.workers._mark_stale')
@patch('allium.lib.workers._save_cache')
@patch('allium.lib.workers._cache_manager')
@patch('allium.lib.workers._fetch_url_with_total_timeout')
def test_unreadable_fresh_cache_retries_server_errors(
        mock_fetch, mock_cm, mock_save, mock_stale, mock_ready):
    import urllib.error
    mock_cm.get_cache_age.return_value = 60  # fresh, but unreadable below
    mock_fetch.side_effect = [
        urllib.error.HTTPError("http://test.example.com/api", 503, "Busy", {}, None),
        b'{"relays": [{"id": "recovered"}]}',
    ]

    with patch('allium.lib.workers._load_cache', return_value=None):
        result = _fetch_with_cache_fallback(
            url="http://test.example.com/api", config=_config())

    assert result == {"relays": [{"id": "recovered"}]}
    assert [call.args[1] for call in mock_fetch.call_args_list] == [5, 10]


@patch('allium.lib.workers._mark_ready')
@patch('allium.lib.workers._mark_stale')
@patch('allium.lib.workers._save_cache')
@patch('allium.lib.workers._cache_manager')
@patch('allium.lib.workers._fetch_url_with_total_timeout')
def test_not_modified_with_unreadable_cache_does_not_refetch(
        mock_fetch, mock_cm, mock_save, mock_stale, mock_ready):
    import urllib.error
    mock_cm.get_cache_age.return_value = 60
    mock_fetch.side_effect = urllib.error.HTTPError(
        "http://test.example.com/api", 304, "Not Modified", {}, None)

    with patch('allium.lib.workers._load_cache', return_value=None):
        result = _fetch_with_cache_fallback(
            url="http://test.example.com/api", config=_config())

    assert result is None
    assert mock_fetch.call_count == 1


def test_failed_attempts_leave_no_reference_cycles():
    """allium.py pauses the cyclic GC while fetching, so a failed attempt
    must not leave garbage (e.g. a partial download) that only it frees."""
    import gc
    from allium.lib.workers import _retry_with_backoff

    def fetch():
        partial_download = [bytearray(1024)]  # noqa: F841 - kept by the frame
        raise ConnectionResetError(104, "reset")

    was_enabled = gc.isenabled()
    gc.collect()
    gc.disable()
    try:
        for _ in range(5):
            try:
                _retry_with_backoff(fetch, retry_count=0)
            except ConnectionResetError:
                pass
        assert gc.collect() == 0
    finally:
        if was_enabled:
            gc.enable()
