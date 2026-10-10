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


def _die_in_worker(monkeypatch, name, poisoned):
    """Make a pool worker exit abruptly when page_writer.<name> is called for a poisoned item.

    Workers look the function up in their forked copy of page_writer; the
    parent's sequential fallback never dies.
    """
    original = getattr(page_writer, name)
    parent_pid = os.getpid()

    def dying(*args, **kwargs):
        if os.getpid() != parent_pid and poisoned(*args):
            os._exit(1)  # simulate a worker killed by the OOM killer
        return original(*args, **kwargs)

    monkeypatch.setattr(page_writer, name, dying)


# multiprocessing.Pool replaces a dead worker without failing its task, so
# these hang (pytest-timeout fails them) unless the pool reports the death.
@pytest.mark.skipif(not hasattr(os, "fork"), reason="parallel generation needs fork()")
@pytest.mark.parametrize("key", ["family", "contact"])
def test_page_pools_fall_back_when_a_worker_dies(tmp_path, monkeypatch, key):
    sequential = _build(tmp_path / "sequential", mp_workers=0)
    page_writer.write_pages_by_key(sequential, key)

    relay_set = _build(tmp_path / "parallel", mp_workers=2)
    relay_set.timestamp = sequential.timestamp  # rendered into every page
    poisoned_dir = page_writer._sanitize_path_component(list(relay_set.json["sorted"][key])[7])
    _die_in_worker(monkeypatch, "_write_html",
                   lambda path, _html: os.path.basename(os.path.dirname(path)) == poisoned_dir)

    page_writer.write_pages_by_key(relay_set, key)

    assert relay_set.mp_workers == 0  # the pool broke and the pages were rendered sequentially
    files = _tree(tmp_path / "parallel")
    assert files == _tree(tmp_path / "sequential")
    assert any(name.startswith(os.path.join(key, poisoned_dir) + os.sep) for name in files)
    _match, mismatch, errors = filecmp.cmpfiles(
        tmp_path / "parallel", tmp_path / "sequential", files, shallow=False)
    assert mismatch == [] and errors == []


@pytest.mark.skipif(not hasattr(os, "fork"), reason="parallel generation needs fork()")
@pytest.mark.parametrize("group, compute, sequential_step", [
    ("contact", "_compute_contact_predata", "_precompute_single_contact"),
    ("family", "_compute_family_predata", "_precompute_single_family"),
])
def test_precompute_pools_fall_back_when_a_worker_dies(tmp_path, monkeypatch, group, compute, sequential_step):
    sequential = _build(tmp_path / "sequential", mp_workers=0)
    poisoned = list(sequential.json["sorted"][group])[7]
    _die_in_worker(monkeypatch, compute, lambda _relay_set, group_hash, *_args: group_hash == poisoned)

    recomputed = []
    original_step = getattr(Relays, sequential_step)

    def recording_step(self, group_hash, *args):
        recomputed.append(group_hash)
        return original_step(self, group_hash, *args)

    monkeypatch.setattr(Relays, sequential_step, recording_step)

    relay_set = _build(tmp_path / "parallel", mp_workers=2)

    # The pool broke and every group was precomputed again sequentially,
    # ending up exactly as the sequential path leaves it.
    assert sorted(recomputed) == sorted(sequential.json["sorted"][group])
    assert relay_set.json["sorted"][group] == sequential.json["sorted"][group]
