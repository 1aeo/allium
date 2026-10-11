"""Fork-based worker pools that neither hang nor outlive the build."""

from concurrent.futures import ProcessPoolExecutor
import functools
import multiprocessing as mp
import os
import threading
import time

# The items of the pool this worker belongs to (inherited through fork)
_items = None


def _exit_with_parent(parent_pid):
    # multiprocessing.Pool workers exit when their parent dies; executor
    # workers wait forever, each holding its copy of the multi-GB relay set.
    while os.getppid() == parent_pid:
        time.sleep(1)
    os._exit(1)


def _init_worker(parent_pid, items, initializer, initargs):
    global _items
    _items = items
    threading.Thread(target=_exit_with_parent, args=(parent_pid,), daemon=True).start()
    if initializer:
        initializer(*initargs)


def _call_with_item(fn, index):
    return fn(_items[index])


def fork_map(workers, fn, items, chunksize, initializer=None, initargs=()):
    """Yield ``fn(item)`` for each item in order, from workers forked from this
    process that first run ``initializer(*initargs)``.

    Fork hands items and initargs (the relay set) to workers copy-on-write;
    only item indexes cross the call queue. Chunks of the items themselves
    could fill its pipe, and a worker death then hangs Python 3.9/3.10
    (CPython gh-94777) instead of raising BrokenProcessPool, which callers
    use to fall back to sequential work. The pool is shut down before any of
    its errors reach the caller.
    """
    with ProcessPoolExecutor(workers, mp_context=mp.get_context("fork"), initializer=_init_worker,
                             initargs=(os.getpid(), items, initializer, initargs)) as executor:
        yield from executor.map(functools.partial(_call_with_item, fn), range(len(items)),
                                chunksize=chunksize)
