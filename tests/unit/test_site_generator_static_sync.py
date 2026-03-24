"""Regression tests for static file sync in site_generator."""

import os
import shutil

from allium.lib.site_generator import _sync_static_files


def test_same_size_same_mtime_different_content_is_copied(temp_dir):
    """mtime+size alone are not enough; content must match to skip."""
    src = os.path.join(temp_dir, "src")
    dst = os.path.join(temp_dir, "dst")
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
    assert copied == 1
    assert skipped == 0
    with open(dst_f) as f:
        assert f.read() == "BBBBB"


def test_identical_files_are_skipped(temp_dir):
    """Ensure identical files in src and dst are skipped by _sync_static_files."""
    src = os.path.join(temp_dir, "src")
    dst = os.path.join(temp_dir, "dst")
    os.makedirs(src)
    os.makedirs(dst, exist_ok=True)
    src_f = os.path.join(src, "x.css")
    dst_f = os.path.join(dst, "x.css")
    with open(src_f, "w") as f:
        f.write("unchanged")
    shutil.copy2(src_f, dst_f)

    copied, skipped = _sync_static_files(src, dst)
    assert copied == 0
    assert skipped == 1
