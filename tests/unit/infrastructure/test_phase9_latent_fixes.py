"""Regression tests for bug plan Phase 9 latent fixes."""

import errno
import json
import socket
import tempfile
import unittest
import urllib.error
from pathlib import Path

from allium.lib import workers
from allium.lib.country_utils import (
    GEOPOLITICAL_CLASSIFICATIONS,
    get_rare_countries_weighted_with_existing_data,
)
from allium.lib.file_io_utils import FileIOManager


class TestRareCountryLoop(unittest.TestCase):
    def test_zero_relay_significant_countries_scored_not_category_names(self):
        # Non-empty country_data so the function proceeds past its
        # no-data early return; DE is populous and won't be rare
        country_data = {"DE": {"relays": list(range(2000))}}
        rare = get_rare_countries_weighted_with_existing_data(country_data, 10000)
        # No classification CATEGORY names may leak into the rare set
        for category in GEOPOLITICAL_CLASSIFICATIONS.keys():
            self.assertNotIn(category, rare)
        # Zero-relay geopolitically significant countries are now scored:
        # a conflict-zone country (e.g. Syria) with 0 relays scores well
        # above the min threshold
        self.assertIn("SY", rare)
        # Every entry looks like a country code
        for c in rare:
            self.assertEqual(len(c), 2, c)


class TestAtomicWrites(unittest.TestCase):
    def test_failed_dump_does_not_clobber_existing_file(self):
        with tempfile.TemporaryDirectory() as td:
            fm = FileIOManager(td)
            self.assertTrue(fm.write_json_file("data.json", {"ok": 1}))
            # Unserializable payload fails mid-dump; the original file
            # must survive intact (the old in-place write truncated it)
            result = fm.write_json_file("data.json", {"bad": object()})
            self.assertFalse(result)
            with open(Path(td) / "data.json") as f:
                self.assertEqual(json.load(f), {"ok": 1})

    def test_save_state_atomic(self):
        # _save_state writes via temp file + os.replace
        import allium.lib.workers as w
        with tempfile.TemporaryDirectory() as td:
            state_file = str(Path(td) / "state.json")
            orig = w.STATE_FILE
            try:
                w.STATE_FILE = state_file
                with w._state_lock:
                    w._save_state()
                with open(state_file) as f:
                    data = json.load(f)
                self.assertIn("workers", data)
                self.assertFalse(Path(state_file + ".tmp").exists())
            finally:
                w.STATE_FILE = orig


class TestRetryableErrors(unittest.TestCase):
    def test_network_errnos_retryable(self):
        e = OSError(errno.ECONNRESET, "reset")
        self.assertTrue(workers._is_retryable_error(e))

    def test_local_os_errors_not_retryable(self):
        for code in (errno.ENOSPC, errno.EACCES, errno.EMFILE):
            e = OSError(code, "local")
            self.assertFalse(workers._is_retryable_error(e), code)

    def test_urlerror_wrapped_oserror_uses_errno(self):
        retryable = urllib.error.URLError(OSError(errno.ETIMEDOUT, "t"))
        not_retryable = urllib.error.URLError(OSError(errno.ENOSPC, "d"))
        self.assertTrue(workers._is_retryable_error(retryable))
        self.assertFalse(workers._is_retryable_error(not_retryable))

    def test_dns_failure_retryable(self):
        self.assertTrue(workers._is_retryable_error(socket.gaierror(8, "nodename")))


if __name__ == "__main__":
    unittest.main()
