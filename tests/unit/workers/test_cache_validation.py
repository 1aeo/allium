"""Cached Onionoo documents are used only when they look like Onionoo responses.

A truncated or hand-edited cache file must be treated as missing. Freshly
downloaded responses are not passed through the same check.
"""

import json
import urllib.error
from unittest.mock import patch

from allium.lib import workers

JUNK = {
    "relays": [{"fingerprint": "ABC123", "nickname": "TestRelay"}],
    "version": "test_version",
}
VALID = {"relays_published": "2026-10-12 14:00:00", "relays": []}
URL = "http://example.test/details"
INVALID_DOCUMENT_LOG = (
    "cache file exists but is not a valid onionoo details document, treating as no cache..."
)


def test_validate_onionoo_document_accepts_published_string_and_relays_list():
    assert workers._validate_onionoo_document(
        {"relays_published": "2026-10-12 14:00:00", "relays": []}) is True


def test_validate_onionoo_document_rejects_non_documents():
    assert workers._validate_onionoo_document(JUNK) is False
    assert workers._validate_onionoo_document([]) is False
    assert workers._validate_onionoo_document(None) is False
    assert workers._validate_onionoo_document({
        "relays_published": "2026-10-12 14:00:00",
        "relays": {"fingerprint": "ABC123"},
    }) is False
    assert workers._validate_onionoo_document(
        {"relays_published": "", "relays": []}) is False


def test_onionoo_configs_check_cached_documents():
    validator = workers._validate_onionoo_document
    assert workers.DETAILS_CONFIG.cache_validator is validator
    assert workers.UPTIME_CONFIG.cache_validator is validator
    assert workers.BANDWIDTH_CONFIG.cache_validator is validator
    assert workers.AROI_CONFIG.cache_validator is None


def test_timeout_with_invalid_details_cache_does_not_return_junk():
    workers._save_cache("onionoo_details", JUNK)
    logs = []
    with patch.object(workers, "_fetch_url_with_total_timeout",
                      side_effect=workers.TotalTimeoutError("timeout")), \
         patch.object(workers.time, "sleep"):
        result = workers._fetch_with_cache_fallback(
            URL, workers.DETAILS_CONFIG, progress_logger=logs.append)

    assert result is None
    assert result != JUNK
    assert INVALID_DOCUMENT_LOG in logs


def test_timeout_with_valid_details_cache_returns_document():
    workers._save_cache("onionoo_details", VALID)
    with patch.object(workers, "_fetch_url_with_total_timeout",
                      side_effect=workers.TotalTimeoutError("timeout")):
        result = workers._fetch_with_cache_fallback(
            URL, workers.DETAILS_CONFIG, progress_logger=lambda message: None)

    assert result == VALID


def test_304_with_invalid_details_cache_does_not_return_junk():
    workers._save_cache("onionoo_details", JUNK)
    logs = []
    with patch.object(
            workers, "_fetch_url_with_total_timeout",
            side_effect=urllib.error.HTTPError(URL, 304, "", {}, None)):
        result = workers._fetch_with_cache_fallback(
            URL, workers.DETAILS_CONFIG, progress_logger=logs.append)

    assert result is None
    assert result != JUNK
    assert INVALID_DOCUMENT_LOG in logs


def test_unexpected_error_does_not_return_invalid_cache():
    """The generic error path used to read the cache without load_cached()."""
    workers._save_cache("onionoo_details", JUNK)
    with patch.object(workers, "_fetch_url_with_total_timeout",
                      return_value=json.dumps(VALID).encode("utf-8")), \
         patch.object(workers, "_save_cache", side_effect=RuntimeError("boom")):
        result = workers._fetch_with_cache_fallback(
            URL, workers.DETAILS_CONFIG, progress_logger=lambda message: None)

    assert result is None


def test_unexpected_error_returns_valid_cache():
    workers._save_cache("onionoo_details", VALID)
    with patch.object(workers, "_fetch_url_with_total_timeout",
                      return_value=json.dumps(VALID).encode("utf-8")), \
         patch.object(workers, "_save_cache", side_effect=RuntimeError("boom")):
        result = workers._fetch_with_cache_fallback(
            URL, workers.DETAILS_CONFIG, progress_logger=lambda message: None)

    assert result == VALID


def test_fresh_download_is_not_cache_validated():
    with patch.object(workers, "_fetch_url_with_total_timeout",
                      return_value=json.dumps(JUNK).encode("utf-8")):
        result = workers._fetch_with_cache_fallback(
            URL, workers.DETAILS_CONFIG, progress_logger=lambda message: None)

    assert result == JUNK
