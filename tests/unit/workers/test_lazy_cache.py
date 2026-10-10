"""
Tests for lazy cache loading in _fetch_with_cache_fallback.

The cache is only parsed when it is needed (fallbacks, 304, fresh-cache
shortcut). A cache presumed readable that turns out not to be must still get
the cache-less retry policy (stale timeout, full retries).
"""

import urllib.error
from unittest.mock import DEFAULT, patch

from allium.lib.workers import (
    APIConfig,
    TotalTimeoutError,
    _fetch_with_cache_fallback,
)

NEW = b'{"relays": [{"id": "new"}]}'
CACHED = {"relays": [{"id": "cached"}]}


def _fetch(responses, cached=None):
    """Fetch with a fresh (60s old) cache whose load returns `cached`.
    Returns (result, timeout of each attempt, the _load_cache mock)."""
    config = APIConfig(api_name='test_api', display_name='test API', cache_max_age_hours=1,
                       timeout_fresh_cache=5, timeout_stale_cache=10,
                       use_conditional_requests=False, retry_count=2, retry_delay_base=0.01)
    with patch.multiple('allium.lib.workers', _mark_ready=DEFAULT, _mark_stale=DEFAULT,
                        _save_cache=DEFAULT, _cache_manager=DEFAULT,
                        _fetch_url_with_total_timeout=DEFAULT, _load_cache=DEFAULT) as mocks:
        mocks['_cache_manager'].get_cache_age.return_value = 60
        mocks['_fetch_url_with_total_timeout'].side_effect = responses
        mocks['_load_cache'].return_value = cached
        result = _fetch_with_cache_fallback(url="http://test.example.com/api", config=config)
    timeouts = [call.args[1] for call in mocks['_fetch_url_with_total_timeout'].call_args_list]
    return result, timeouts, mocks['_load_cache']


def _http_error(code):
    return urllib.error.HTTPError("http://test.example.com/api", code, "", {}, None)


def test_successful_fetch_never_loads_cache():
    result, _, load = _fetch([NEW])
    assert result == {"relays": [{"id": "new"}]}
    load.assert_not_called()


def test_unreadable_fresh_cache_refetches_like_missing_cache():
    # Fresh-cache attempt: one try (no retries) with the fresh timeout fails;
    # the cache-less attempt then uses the stale timeout and retries.
    result, timeouts, load = _fetch([TotalTimeoutError("timeout"), TotalTimeoutError("timeout"), NEW])
    assert result == {"relays": [{"id": "new"}]}
    assert timeouts == [5, 10, 10]
    load.assert_called_once_with('test_api')


def test_unreadable_fresh_cache_retries_server_errors():
    result, timeouts, _ = _fetch([_http_error(503), NEW])
    assert result == {"relays": [{"id": "new"}]}
    assert timeouts == [5, 10]


def test_not_modified_loads_cache_once():
    result, _, load = _fetch([_http_error(304)], cached=CACHED)
    assert result == CACHED
    load.assert_called_once_with('test_api')


def test_not_modified_with_unreadable_cache_does_not_refetch():
    result, timeouts, _ = _fetch([_http_error(304)])
    assert result is None
    assert timeouts == [5]


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
