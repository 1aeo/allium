"""Regression tests for static file sync in site_generator."""

import os
import shutil
import tempfile
import unittest

from allium.lib.site_generator import _sync_static_files


class TestSyncStaticFiles(unittest.TestCase):
    def test_same_size_same_mtime_different_content_is_copied(self):
        """mtime+size alone are not enough; content must match to skip."""
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "src")
            dst = os.path.join(tmp, "dst")
            os.makedirs(src)
            os.makedirs(dst, exist_ok=True)
            src_f = os.path.join(src, "a.css")
            dst_f = os.path.join(dst, "a.css")
            with open(src_f, "w") as f:
                f.write("AAAAA")
            shutil.copy2(src_f, dst_f)
            st = os.stat(dst_f)
            with open(src_f, "w") as f:
                f.write("BBBBB")
            os.utime(src_f, (st.st_atime, st.st_mtime))

            copied, skipped = _sync_static_files(src, dst)
            self.assertEqual(copied, 1)
            self.assertEqual(skipped, 0)
            with open(dst_f) as f:
                self.assertEqual(f.read(), "BBBBB")

    def test_identical_files_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "src")
            dst = os.path.join(tmp, "dst")
            os.makedirs(src)
            os.makedirs(dst, exist_ok=True)
            src_f = os.path.join(src, "x.css")
            dst_f = os.path.join(dst, "x.css")
            with open(src_f, "w") as f:
                f.write("unchanged")
            shutil.copy2(src_f, dst_f)

            copied, skipped = _sync_static_files(src, dst)
            self.assertEqual(copied, 0)
            self.assertEqual(skipped, 1)


if __name__ == "__main__":
    unittest.main()
