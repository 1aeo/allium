"""Parallel page generation must write the same files as the sequential path."""

import filecmp
import os

import pytest

from allium.lib import page_writer
from allium.lib.relays import Relays

RELAY_COUNT = 150  # above the 100-item thresholds for parallel precompute/rendering


def _onionoo_details():
    relays = []
    for i in range(RELAY_COUNT):
        fingerprint = f"{i:040X}"
        relays.append({
            "nickname": f"relay{i}",
            "fingerprint": fingerprint,
            "running": i % 7 != 0,
            "observed_bandwidth": 1_000_000 + i * 1_000,
            "consensus_weight": 100 + i,
            "flags": (["Running", "Valid", "Fast"]
                      + (["Guard", "Stable"] if i % 3 == 0 else [])
                      + (["Exit"] if i % 5 == 0 else [])),
            "first_seen": "2023-01-01 00:00:00",
            "last_seen": "2024-01-01 00:00:00",
            "last_restarted": "2023-12-01 00:00:00",
            "platform": "Tor 0.4.8.10 on Linux",
            "country": ["us", "de", "nl"][i % 3],
            "country_name": ["United States", "Germany", "Netherlands"][i % 3],
            "as": f"AS{100 + i % 9}",
            "as_name": "Example Networks",
            "or_addresses": [f"192.0.2.{i % 250}:9001"]
                            + ([f"[2001:db8::{i:x}]:9001"] if i % 2 else []),
            # Mostly one operator per relay, plus one AROI operator with many
            "contact": (f"operator{i} <op{i}@example.org>" if i % 4 else
                        "email:ops@example.org url:example.org proof:uri-rsa ciissversion:2"),
            "effective_family": sorted({fingerprint, f"{i ^ 1:040X}"}),
        })
    return {"version": "10.0", "relays_published": "2024-01-01 00:00:00", "relays": relays}


def _build(output_dir, mp_workers):
    relay_set = Relays(
        output_dir=str(output_dir),
        onionoo_url="https://onionoo.example.invalid/details",
        relay_data=_onionoo_details(),
        filter_downtime_days=0,
        mp_workers=mp_workers,
    )
    relay_set.enrich_with_api_data()
    return relay_set


def _tree(root):
    return sorted(
        os.path.relpath(os.path.join(dirpath, name), root)
        for dirpath, _dirs, files in os.walk(root) for name in files
    )


@pytest.mark.skipif(not hasattr(os, "fork"), reason="parallel generation needs fork()")
def test_parallel_and_sequential_generation_write_identical_pages(tmp_path, monkeypatch):
    def no_sequential_fallback(*_args, **_kwargs):
        raise AssertionError("parallel precompute fell back to the sequential path")

    with monkeypatch.context() as patched:
        patched.setattr(Relays, "_precompute_single_contact", no_sequential_fallback)
        patched.setattr(Relays, "_precompute_single_family", no_sequential_fallback)
        parallel = _build(tmp_path / "parallel", mp_workers=2)
    sequential = _build(tmp_path / "sequential", mp_workers=0)
    sequential.timestamp = parallel.timestamp  # rendered into every page

    # Workers send relay dicts back as indexes: statuses reference the
    # parent's own relay dicts, exactly as the sequential path stores them.
    relay_ids = {id(relay) for relay in parallel.json["relays"]}
    linked = [
        entry["relay"]
        for group in ("contact", "family")
        for data in parallel.json["sorted"][group].values()
        for entries in (data.get("contact_validation_status") or {}).values()
        if isinstance(entries, list)
        for entry in entries
        if isinstance(entry, dict) and "relay" in entry
    ]
    assert linked and all(id(relay) in relay_ids for relay in linked)

    for relay_set in (parallel, sequential):
        for key in ("family", "contact", "as", "flag"):
            page_writer.write_pages_by_key(relay_set, key)
        page_writer.write_relay_info(relay_set)
    assert parallel.mp_workers == 2  # no pool fell back to sequential rendering

    parallel_files = _tree(tmp_path / "parallel")
    assert parallel_files == _tree(tmp_path / "sequential")
    assert sum(name.startswith("relay" + os.sep) for name in parallel_files) == RELAY_COUNT
    _match, mismatch, errors = filecmp.cmpfiles(
        tmp_path / "parallel", tmp_path / "sequential", parallel_files, shallow=False)
    assert mismatch == [] and errors == []
