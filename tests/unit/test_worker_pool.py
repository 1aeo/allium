"""Tests for the fork-based worker pools in allium.lib.worker_pool."""

import multiprocessing
import os
import signal
import subprocess
import sys
import time
from concurrent.futures.process import BrokenProcessPool

import pytest

from allium.lib.worker_pool import fork_map

pytestmark = pytest.mark.skipif(not hasattr(os, "fork"), reason="fork_map needs fork()")

_offset = 0


def _set_offset(offset):
    """Worker initializer."""
    global _offset
    _offset = offset


def _add_offset(item):
    """Add the offset the initializer set."""
    return item + _offset


def _die_in_worker(item):
    """Exit like a worker killed by the OOM killer."""
    if multiprocessing.parent_process():
        os._exit(1)
    return item


def test_fork_map_runs_the_initializer_and_keeps_order():
    """Results come back in item order, computed after the initializer ran."""
    assert list(fork_map(2, _add_offset, list(range(50)), 3, _set_offset, (100,))) == list(range(100, 150))


def test_dead_worker_raises_even_with_items_larger_than_the_call_queue_pipe():
    """Items reach workers through fork, so chunks never fill the call queue's
    64 KiB pipe, where a worker death hung Python 3.9/3.10 (CPython gh-94777)."""
    with pytest.raises(BrokenProcessPool):
        list(fork_map(2, _die_in_worker, ["x" * 70_000] * 6, 1))


def _live_parent(pid):
    """Parent PID of process ``pid``, or None once it has exited (Linux /proc)."""
    try:
        with open(f"/proc/{pid}/stat") as stat:
            state, ppid = stat.read().rsplit(")", 1)[1].split()[:2]
    except OSError:
        return None
    return None if state == "Z" else int(ppid)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="reads /proc")
def test_workers_exit_when_the_parent_dies():
    """Workers of a killed parent exit instead of waiting forever with their
    copy of the parent's memory, as multiprocessing.Pool workers did."""
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    parent = subprocess.Popen(
        [sys.executable, "-c", "import time\nfrom allium.lib.worker_pool import fork_map\n"
                               "list(fork_map(2, time.sleep, [60] * 4, 1))"],
        env=dict(os.environ, PYTHONPATH=repo_root))
    workers = []
    try:
        deadline = time.time() + 20
        while len(workers) < 2 and time.time() < deadline:
            time.sleep(0.1)
            workers = [pid for pid in map(int, filter(str.isdigit, os.listdir("/proc")))
                       if _live_parent(pid) == parent.pid]
    finally:
        parent.kill()
        parent.wait()
    assert len(workers) == 2

    deadline = time.time() + 10
    while any(_live_parent(pid) is not None for pid in workers) and time.time() < deadline:
        time.sleep(0.1)
    orphans = [pid for pid in workers if _live_parent(pid) is not None]
    for pid in orphans:
        os.kill(pid, signal.SIGKILL)
    assert orphans == []
