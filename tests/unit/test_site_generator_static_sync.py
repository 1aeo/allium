"""Regression tests for static file sync in site_generator."""

import os
import shutil

from allium.lib.site_generator import (
    _deduplicate_family_listing_items,
    _remove_stale_pagination_files,
    _remove_unsupported_misc_sort_variants,
    _sync_static_files,
)


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


def test_stale_pagination_files_are_removed_without_touching_base(temp_dir):
    output_dir = os.path.join(temp_dir, "misc")
    os.makedirs(output_dir)
    for filename in (
        "families-by-bandwidth.html",
        "families-by-bandwidth-page-2.html",
        "families-by-bandwidth-page-32.html",
        "families-by-consensus-weight-page-2.html",
    ):
        with open(os.path.join(output_dir, filename), "w") as handle:
            handle.write(filename)

    removed = _remove_stale_pagination_files(
        output_dir, "families-by-bandwidth.html"
    )

    assert removed == 2
    assert os.path.exists(os.path.join(output_dir, "families-by-bandwidth.html"))
    assert os.path.exists(
        os.path.join(output_dir, "families-by-consensus-weight-page-2.html")
    )


def test_unsupported_misc_variants_are_removed_from_reused_output(temp_dir):
    output_dir = os.path.join(temp_dir, "misc")
    os.makedirs(output_dir)
    obsolete = {
        f"{page_type}-{suffix}{page}.html"
        for page_type in ("contacts", "families")
        for suffix in ("by-unique-contact-count", "by-unique-family-count")
        for page in ("", "-page-2")
    }
    retained = {
        "contacts-by-bandwidth.html",
        "contacts-by-bandwidth-page-2.html",
        "families-by-consensus-weight.html",
    }
    for filename in obsolete | retained:
        with open(os.path.join(output_dir, filename), "w") as handle:
            handle.write(filename)

    removed = _remove_unsupported_misc_sort_variants(temp_dir)

    assert removed == len(obsolete)
    assert all(
        not os.path.exists(os.path.join(output_dir, filename))
        for filename in obsolete
    )
    assert all(
        os.path.exists(os.path.join(output_dir, filename))
        for filename in retained
    )


def test_family_deduplication_is_global_before_pagination():
    relays = [
        {"fingerprint": "A"},
        {"fingerprint": "B"},
        {"fingerprint": "C"},
        {"fingerprint": "D"},
    ]
    listing_items = [
        ("family-a", {"relays": [0, 1]}),
        ("overlap", {"relays": [1, 2]}),
        ("family-d", {"relays": [3]}),
    ]

    assert _deduplicate_family_listing_items(listing_items, relays) == [
        listing_items[0],
        listing_items[2],
    ]
