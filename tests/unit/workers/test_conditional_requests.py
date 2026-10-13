"""Onionoo conditional requests reuse the server's Last-Modified value.

Onionoo answers 304 only when If-Modified-Since is exactly the Last-Modified
header from the previous response. The timestamp file stores that header
after a download whose cache save succeeded. A 304 leaves the timestamp
file alone and refreshes the cache file's modification time.
"""

import json
import os
import time
import urllib.error
from unittest.mock import patch

from allium.lib import workers

URL = "https://onionoo.torproject.org/details"
LAST_MODIFIED = "Mon, 12 Oct 2026 14:07:30 GMT"
DOCUMENT = {
    "relays_published": "2026-10-12 14:07:30",
    "relays": [{"fingerprint": "ABC123"}],
}
BODY = json.dumps(DOCUMENT).encode("utf-8")


def _fetch(steps):
    """Downloader stand-in. `steps` is a list of {body, last_modified, error}."""
    calls = []
    index = {"n": 0}

    def fetch(url, timeout, headers=None, response_headers=None):
        calls.append({"url": url, "timeout": timeout, "headers": headers,
                      "response_headers": response_headers})
        step = steps[index["n"]]
        index["n"] += 1
        last_modified = step.get("last_modified")
        if response_headers is not None and last_modified:
            response_headers["Last-Modified"] = last_modified
        if step.get("error") is not None:
            raise step["error"]
        return step.get("body", BODY)

    fetch.calls = calls
    return fetch


def _http_304():
    return urllib.error.HTTPError(URL, 304, "Not Modified", {}, None)


def test_200_stores_last_modified_timestamp():
    fetch = _fetch([{"body": BODY, "last_modified": LAST_MODIFIED}])
    with patch.object(workers, "_fetch_url_with_total_timeout", fetch):
        result = workers._fetch_with_cache_fallback(
            URL, workers.DETAILS_CONFIG, progress_logger=lambda message: None)

    assert result == DOCUMENT
    assert workers._read_timestamp("onionoo_details") == LAST_MODIFIED


def test_next_call_sends_stored_last_modified():
    fetch = _fetch([
        {"body": BODY, "last_modified": LAST_MODIFIED},
        {"body": BODY, "last_modified": LAST_MODIFIED},
    ])
    with patch.object(workers, "_fetch_url_with_total_timeout", fetch):
        workers._fetch_with_cache_fallback(
            URL, workers.DETAILS_CONFIG, progress_logger=lambda message: None)
        workers._fetch_with_cache_fallback(
            URL, workers.DETAILS_CONFIG, progress_logger=lambda message: None)

    assert fetch.calls[0]["headers"] is None
    assert fetch.calls[1]["headers"]["If-Modified-Since"] == LAST_MODIFIED


def test_200_without_last_modified_still_writes_timestamp():
    fetch = _fetch([{"body": BODY}])
    local_stamp = "Tue, 13 Oct 2026 05:00:00 GMT"

    def fake_strftime(fmt, when):
        return local_stamp

    with patch.object(workers, "_fetch_url_with_total_timeout", fetch), \
         patch.object(workers.time, "strftime", fake_strftime):
        workers._fetch_with_cache_fallback(
            URL, workers.DETAILS_CONFIG, progress_logger=lambda message: None)

    assert workers._read_timestamp("onionoo_details") == local_stamp


def test_304_refreshes_cache_mtime_and_leaves_timestamp():
    workers._save_cache("onionoo_details", DOCUMENT)
    workers._write_timestamp("onionoo_details", LAST_MODIFIED)
    cache_path = workers._cache_manager.get_file_path("onionoo_details.json")
    old = time.time() - 7200
    os.utime(cache_path, (old, old))
    assert workers.get_cache_age("onionoo_details") > 7000

    fetch = _fetch([{"error": _http_304()}])
    with patch.object(workers, "_fetch_url_with_total_timeout", fetch):
        result = workers._fetch_with_cache_fallback(
            URL, workers.DETAILS_CONFIG, progress_logger=lambda message: None)

    assert result == DOCUMENT
    assert workers.get_cache_age("onionoo_details") < 5
    assert workers._read_timestamp("onionoo_details") == LAST_MODIFIED
    assert fetch.calls[0]["headers"]["If-Modified-Since"] == LAST_MODIFIED


def test_failed_cache_save_writes_no_timestamp():
    fetch = _fetch([{"body": BODY, "last_modified": LAST_MODIFIED}])
    with patch.object(workers, "_fetch_url_with_total_timeout", fetch), \
         patch.object(workers, "_save_cache", return_value=None):
        result = workers._fetch_with_cache_fallback(
            URL, workers.DETAILS_CONFIG, progress_logger=lambda message: None)

    assert result == DOCUMENT
    assert workers._read_timestamp("onionoo_details") is None


def test_non_conditional_api_is_called_without_response_headers():
    fetch = _fetch([{"body": b'{"results": []}'}])
    with patch.object(workers, "_fetch_url_with_total_timeout", fetch):
        workers._fetch_with_cache_fallback(
            "http://example.test/aroi", workers.AROI_CONFIG,
            progress_logger=lambda message: None)

    assert fetch.calls[0]["response_headers"] is None
    assert fetch.calls[0]["headers"] == {"User-Agent": "Allium/1.0"}
    assert workers._read_timestamp("aroi_validation") is None
