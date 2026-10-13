"""
Tests that the test suite never touches the real API cache in allium/data/.

allium.lib.workers derives its data paths from its own location, so site
builds and tests share allium/data/cache unless the autouse
isolated_worker_data fixture in tests/conftest.py redirects them.
"""
import os
import sys
import types
from pathlib import Path, PurePath

from allium.lib import workers
from allium.lib.file_io_utils import FileIOManager, create_cache_manager


def _real_data_dir():
    """The same derivation workers.py uses for DATA_DIR at import (ABS_PATH is not patched).

    A function rather than a module constant, so this module holds no real path itself.
    """
    return os.path.join(os.path.dirname(workers.ABS_PATH), "data")


def _is_under(path, root):
    # String comparison only: captured names hold the same abspath-derived
    # strings workers.py built, and arbitrary module strings must not hit the filesystem.
    path, root = os.path.normpath(str(path)), os.path.normpath(root)
    return path == root or path.startswith(root + os.sep)


def _real_data_references(modules):
    """Return 'module.name' for module globals that point into the real data dir."""
    real_data_dir = _real_data_dir()
    found = []
    for module_name, module in list(modules.items()):
        namespace = getattr(module, "__dict__", None)
        if not isinstance(namespace, dict):
            continue
        for name, value in list(namespace.items()):
            if isinstance(value, FileIOManager):
                target = value.base_directory
            elif isinstance(value, (str, PurePath)) and os.path.isabs(value):
                target = value
            else:
                continue
            if _is_under(target, real_data_dir):
                found.append(f"{module_name}.{name}")
    return found


class TestWorkerDataIsolation:
    """The autouse fixture points every worker path at a per-test temp dir."""

    def test_worker_paths_are_outside_real_data_dir(self):
        for path in (workers.DATA_DIR, workers.CACHE_DIR, workers.STATE_FILE):
            assert not _is_under(path, _real_data_dir()), path
        assert workers._cache_manager.base_directory == Path(workers.CACHE_DIR)
        assert workers._timestamp_manager.base_directory == Path(workers.CACHE_DIR)

    def test_worker_writes_land_in_temp_dir(self):
        # Never write the probe files into the real cache, even if the fixture is missing.
        assert not _is_under(workers.CACHE_DIR, _real_data_dir())
        assert not _is_under(workers.STATE_FILE, _real_data_dir())

        workers._save_cache("cache_isolation_probe", {"relays": []})
        workers._write_timestamp("cache_isolation_probe", "Thu, 01 Jan 2026 00:00:00 GMT")
        workers._mark_ready("cache_isolation_probe")

        cache_dir = Path(workers.CACHE_DIR)
        assert (cache_dir / "cache_isolation_probe.json").is_file()
        assert (cache_dir / "cache_isolation_probe_timestamp.txt").is_file()
        assert Path(workers.STATE_FILE).is_file()
        real_cache_dir = Path(_real_data_dir()) / "cache"
        assert not (real_cache_dir / "cache_isolation_probe.json").exists()
        assert not (real_cache_dir / "cache_isolation_probe_timestamp.txt").exists()

    def test_worker_status_starts_empty(self):
        assert workers.get_all_worker_status() == {}

    def test_no_loaded_module_holds_real_data_paths(self):
        """A name bound at import (from allium.lib.workers import _cache_manager)
        keeps the real path after the fixture patches the workers module."""
        assert _real_data_references(sys.modules) == []

    def test_real_data_reference_scan_detects_captured_names(self):
        captured = types.ModuleType("captured_real_cache")
        captured._cache_manager = create_cache_manager(workers.CACHE_DIR)
        captured.STATE_FILE = os.path.join(_real_data_dir(), "state.json")
        captured.CACHE_PATH = Path(_real_data_dir()) / "cache"
        captured.real_manager = FileIOManager.__new__(FileIOManager)
        captured.real_manager.base_directory = Path(_real_data_dir()) / "cache"

        assert _real_data_references({"captured_real_cache": captured}) == [
            "captured_real_cache.STATE_FILE",
            "captured_real_cache.CACHE_PATH",
            "captured_real_cache.real_manager",
        ]
