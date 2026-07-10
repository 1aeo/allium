"""Regression tests for HTTP error-path behavior of the public API fetchers.

Originally added for bug plan Phase 2: cache lookups and worker status on the
304/error fallback paths must use the machine cache key (APIConfig.api_name,
e.g. 'onionoo_details'), never the human-readable display name.

Extended for simplification Phase 2 (folding the HTTP-error decorator into
_fetch_with_cache_fallback): these tests pin the full error-path contract of
the public fetcher functions so it survives refactors of the internals:

- HTTP 304 with cache: return cached data, mark ready under machine key
- HTTP 304 without cache: return None, mark stale under machine key
  (details additionally logs the "dying peacefully" message: allow_exit_on_304)
- HTTP 5xx: log "HTTP error fetching ..." and re-raise (no cache fallback)
- URLError (non-timeout): log network-error messages and re-raise
- Generic error: mark stale, fall back to cache; without cache the log message
  depends on the per-API critical flag (details=True, others=False)

All tests go through the PUBLIC fetchers and mock only the lowest-level
network primitive (_fetch_url_with_total_timeout) or file-level helpers.
"""

import json
import os
import tempfile
import time
import unittest
import urllib.error
from unittest.mock import patch

import pytest

from allium.lib import workers
from allium.lib.file_io_utils import create_cache_manager


def _http_error(code, msg):
    return urllib.error.HTTPError(
        "http://example.test/api", code, msg, {}, None)


def _http_304():
    return _http_error(304, "Not Modified")


class TestHttpErrorCacheKeys(unittest.TestCase):
    def setUp(self):
        self._saved_status = dict(workers._worker_status)
        # Start from a clean status dict so "not marked" assertions are
        # meaningful regardless of any state loaded at import time.
        workers._worker_status.clear()

    def tearDown(self):
        workers._worker_status.clear()
        workers._worker_status.update(self._saved_status)

    def test_304_with_cache_returns_cached_and_marks_ready_under_machine_key(self):
        cached = {"relays": [{"nickname": "seeded"}], "version": "test"}
        logs = []
        with tempfile.TemporaryDirectory() as td:
            cm = create_cache_manager(td)
            with patch.object(workers, "_cache_manager", cm), \
                 patch.object(workers, "_save_state", lambda: True):
                # Pre-seed the cache under the machine key, as production does
                workers._save_cache("onionoo_details", cached)
                with patch.object(workers, "_fetch_url_with_total_timeout",
                                  side_effect=_http_304()):
                    out = workers.fetch_onionoo_details(
                        "http://example.test/details", logs.append)

        self.assertEqual(out, cached)
        self.assertIn("onionoo_details", workers._worker_status)
        self.assertEqual(
            workers._worker_status["onionoo_details"]["status"], "ready")
        # The display name must never be used as a status key
        self.assertNotIn("onionoo details", workers._worker_status)
        self.assertIn(
            "no onionoo details update since last run, using cached data...",
            logs)

    def test_304_without_cache_marks_stale_under_machine_key(self):
        logs = []
        with tempfile.TemporaryDirectory() as td:
            cm = create_cache_manager(td)
            with patch.object(workers, "_cache_manager", cm), \
                 patch.object(workers, "_save_state", lambda: True), \
                 patch.object(workers, "_fetch_url_with_total_timeout",
                              side_effect=_http_304()):
                out = workers.fetch_onionoo_uptime(
                    "http://example.test/uptime", logs.append)

        self.assertIsNone(out)
        self.assertEqual(
            workers._worker_status["onionoo_uptime"]["status"], "stale")
        self.assertEqual(
            workers._worker_status["onionoo_uptime"]["error"],
            "No cached onionoo uptime data available")
        self.assertNotIn("onionoo uptime", workers._worker_status)
        # Non-critical APIs (allow_exit_on_304=False) log the "skipping" line
        self.assertIn(
            "no onionoo uptime update since last run and no cache, "
            "skipping onionoo uptime data...",
            logs)

    def test_304_without_cache_details_dies_peacefully(self):
        """details has allow_exit_on_304=True: distinct log + stale reason."""
        logs = []
        with tempfile.TemporaryDirectory() as td:
            cm = create_cache_manager(td)
            with patch.object(workers, "_cache_manager", cm), \
                 patch.object(workers, "_save_state", lambda: True), \
                 patch.object(workers, "_fetch_url_with_total_timeout",
                              side_effect=_http_304()):
                out = workers.fetch_onionoo_details(
                    "http://example.test/details", logs.append)

        self.assertIsNone(out)
        self.assertEqual(
            workers._worker_status["onionoo_details"]["status"], "stale")
        self.assertEqual(
            workers._worker_status["onionoo_details"]["error"],
            "No cached onionoo details data available (304 with no cache)")
        self.assertIn(
            "no onionoo details update since last run, dying peacefully...",
            logs)

    def test_http_5xx_logs_and_reraises(self):
        """Non-304 HTTP errors log and re-raise; no cache fallback occurs."""
        cached = {"relays": [{"nickname": "seeded"}], "version": "test"}
        logs = []
        with tempfile.TemporaryDirectory() as td:
            cm = create_cache_manager(td)
            with patch.object(workers, "_cache_manager", cm), \
                 patch.object(workers, "_save_state", lambda: True):
                # Fresh cache => no retries => the 500 surfaces immediately
                workers._save_cache("onionoo_uptime", cached)
                with patch.object(workers, "_fetch_url_with_total_timeout",
                                  side_effect=_http_error(
                                      500, "Internal Server Error")):
                    with pytest.raises(urllib.error.HTTPError) as excinfo:
                        workers.fetch_onionoo_uptime(
                            "http://example.test/uptime", logs.append)

        self.assertEqual(excinfo.value.code, 500)
        self.assertIn("HTTP error fetching onionoo uptime data: 500", logs)
        # The error path neither marks ready nor stale, even with cache present
        self.assertNotIn("onionoo_uptime", workers._worker_status)

    def test_urlerror_logs_and_reraises(self):
        """Non-timeout URLErrors log network-error messages and re-raise."""
        cached = {"relays": [{"nickname": "seeded"}], "version": "test"}
        logs = []
        err = urllib.error.URLError(ConnectionRefusedError(61, "refused"))
        with tempfile.TemporaryDirectory() as td:
            cm = create_cache_manager(td)
            with patch.object(workers, "_cache_manager", cm), \
                 patch.object(workers, "_save_state", lambda: True):
                # Fresh cache => no retries => the URLError surfaces immediately
                workers._save_cache("onionoo_uptime", cached)
                with patch.object(workers, "_fetch_url_with_total_timeout",
                                  side_effect=err):
                    with pytest.raises(urllib.error.URLError):
                        workers.fetch_onionoo_uptime(
                            "http://example.test/uptime", logs.append)

        self.assertIn(f"network error fetching onionoo uptime data: {err}",
                      logs)
        self.assertIn("check your internet connection and try again", logs)
        self.assertIn(
            "in CI environments, this might be a temporary network issue",
            logs)
        self.assertNotIn("onionoo_uptime", workers._worker_status)

    def test_generic_error_fallback_finds_cache_under_machine_key(self):
        cached = {"metadata": {}, "statistics": {}, "results": [{"x": 1}]}
        fetched = {"metadata": {}, "statistics": {}, "results": [{"y": 2}]}
        logs = []
        with tempfile.TemporaryDirectory() as td:
            cm = create_cache_manager(td)
            with patch.object(workers, "_cache_manager", cm), \
                 patch.object(workers, "_save_state", lambda: True):
                workers._save_cache("aroi_validation", cached)
                # Backdate the cache so the fetch is attempted (AROI returns
                # fresh cache immediately otherwise)
                stale = time.time() - 2 * 3600
                os.utime(os.path.join(td, "aroi_validation.json"),
                         (stale, stale))
                with patch.object(workers, "_fetch_url_with_total_timeout",
                                  return_value=json.dumps(
                                      fetched).encode("utf-8")), \
                     patch.object(workers, "_save_cache",
                                  side_effect=RuntimeError("boom")):
                    out = workers.fetch_aroi_validation(
                        "http://example.test/latest.json", logs.append)

        self.assertEqual(out, cached)
        self.assertEqual(
            workers._worker_status["aroi_validation"]["status"], "stale")
        self.assertEqual(
            workers._worker_status["aroi_validation"]["error"],
            "Failed to fetch AROI validation: boom")
        self.assertIn("error: Failed to fetch AROI validation: boom", logs)
        self.assertIn("using cached AROI validation data as fallback", logs)

    def test_generic_error_no_cache_critical_logs_cannot_continue(self):
        """details is critical=True: distinct no-cache message on errors."""
        logs = []
        with tempfile.TemporaryDirectory() as td:
            cm = create_cache_manager(td)
            with patch.object(workers, "_cache_manager", cm), \
                 patch.object(workers, "_save_state", lambda: True), \
                 patch.object(workers, "_fetch_url_with_total_timeout",
                              return_value=b'{"relays": []}'), \
                 patch.object(workers, "_save_cache",
                              side_effect=RuntimeError("boom")):
                out = workers.fetch_onionoo_details(
                    "http://example.test/details", logs.append)

        self.assertIsNone(out)
        self.assertEqual(
            workers._worker_status["onionoo_details"]["status"], "stale")
        self.assertIn("error: Failed to fetch onionoo details: boom", logs)
        self.assertIn("no cached data available, cannot continue", logs)

    def test_generic_error_no_cache_noncritical_logs_continuing_without(self):
        """uptime is critical=False: continues without data on errors."""
        logs = []
        with tempfile.TemporaryDirectory() as td:
            cm = create_cache_manager(td)
            with patch.object(workers, "_cache_manager", cm), \
                 patch.object(workers, "_save_state", lambda: True), \
                 patch.object(workers, "_fetch_url_with_total_timeout",
                              return_value=b'{"relays": []}'), \
                 patch.object(workers, "_save_cache",
                              side_effect=RuntimeError("boom")):
                out = workers.fetch_onionoo_uptime(
                    "http://example.test/uptime", logs.append)

        self.assertIsNone(out)
        self.assertEqual(
            workers._worker_status["onionoo_uptime"]["status"], "stale")
        self.assertIn("error: Failed to fetch onionoo uptime: boom", logs)
        self.assertIn(
            "no cached data available, continuing without onionoo uptime data",
            logs)


if __name__ == "__main__":
    unittest.main()
