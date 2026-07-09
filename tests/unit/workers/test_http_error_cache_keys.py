"""Regression tests for bug plan Phase 2: handle_http_errors must use the
machine cache key (APIConfig.api_name) for cache lookups and worker status,
not the human-readable display name.

Before the fix the decorator received only "onionoo details" and looked for
a cache file literally named 'onionoo details.json', which never exists, so
the 304 fallback always failed and worker status was keyed inconsistently.
"""

import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from allium.lib import workers
from allium.lib.file_io_utils import create_cache_manager


def _http_304():
    return urllib.error.HTTPError(
        "http://example.test/details", 304, "Not Modified", {}, None)


class TestHttpErrorCacheKeys(unittest.TestCase):
    def setUp(self):
        self._saved_status = dict(workers._worker_status)

    def tearDown(self):
        workers._worker_status.clear()
        workers._worker_status.update(self._saved_status)

    def test_304_with_cache_returns_cached_and_marks_ready_under_machine_key(self):
        cached = {"relays": [{"nickname": "seeded"}], "version": "test"}
        with tempfile.TemporaryDirectory() as td:
            cm = create_cache_manager(td)
            with patch.object(workers, "_cache_manager", cm), \
                 patch.object(workers, "_save_state", lambda: True), \
                 patch.object(workers, "_fetch_with_cache_fallback",
                              side_effect=_http_304()):
                # Pre-seed the cache under the machine key, as production does
                workers._save_cache("onionoo_details", cached)

                out = workers.fetch_onionoo_details(
                    "http://example.test/details", lambda msg: None)

        self.assertEqual(out, cached)
        self.assertIn("onionoo_details", workers._worker_status)
        self.assertEqual(
            workers._worker_status["onionoo_details"]["status"], "ready")
        # The display name must never be used as a status key
        self.assertNotIn("onionoo details", workers._worker_status)

    def test_304_without_cache_marks_stale_under_machine_key(self):
        with tempfile.TemporaryDirectory() as td:
            cm = create_cache_manager(td)
            with patch.object(workers, "_cache_manager", cm), \
                 patch.object(workers, "_save_state", lambda: True), \
                 patch.object(workers, "_fetch_with_cache_fallback",
                              side_effect=_http_304()):
                out = workers.fetch_onionoo_uptime(
                    "http://example.test/uptime", lambda msg: None)

        self.assertIsNone(out)
        self.assertEqual(
            workers._worker_status["onionoo_uptime"]["status"], "stale")
        self.assertNotIn("onionoo uptime", workers._worker_status)

    def test_generic_error_fallback_finds_cache_under_machine_key(self):
        cached = {"results": {"x": 1}}
        with tempfile.TemporaryDirectory() as td:
            cm = create_cache_manager(td)
            with patch.object(workers, "_cache_manager", cm), \
                 patch.object(workers, "_save_state", lambda: True), \
                 patch.object(workers, "_fetch_with_cache_fallback",
                              side_effect=RuntimeError("boom")):
                workers._save_cache("aroi_validation", cached)
                out = workers.fetch_aroi_validation(
                    "http://example.test/latest.json", lambda msg: None)

        self.assertEqual(out, cached)
        self.assertEqual(
            workers._worker_status["aroi_validation"]["status"], "stale")


if __name__ == "__main__":
    unittest.main()
