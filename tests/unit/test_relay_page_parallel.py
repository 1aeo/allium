"""Tests for parallel relay info page generation."""

import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from allium.lib import page_writer


class _FakeRenderer:
    """Writes one marker file per relay; a worker dies on the poisoned relay."""

    parent_pid = None
    poisoned = None

    def __init__(self, relay_set, output_path):
        self.relay_set = relay_set
        self.output_path = output_path

    def write(self, relay):
        if os.getpid() != self.parent_pid and relay["fingerprint"] == self.poisoned:
            os._exit(1)  # simulate a worker killed by the OOM killer
        with open(os.path.join(self.output_path, relay["fingerprint"]), "w") as f:
            f.write(str(os.getpid()))


@pytest.mark.skipif(not hasattr(os, "fork"), reason="needs fork()")
@pytest.mark.parametrize("poisoned", [None, f"{7:040X}"], ids=["parallel", "worker_dies"])
def test_relay_pages_render_in_parallel_or_fall_back(tmp_path, monkeypatch, poisoned):
    monkeypatch.setattr(page_writer, "_RelayPageRenderer", _FakeRenderer)
    monkeypatch.setattr(_FakeRenderer, "parent_pid", os.getpid())
    monkeypatch.setattr(_FakeRenderer, "poisoned", poisoned)
    relay_set = SimpleNamespace(
        json={"relays": [{"fingerprint": f"{i:040X}"} for i in range(120)]},
        output_dir=str(tmp_path), mp_workers=2, progress_logger=Mock())

    page_writer.write_relay_info(relay_set)

    written = os.listdir(tmp_path / "relay")
    assert len(written) == 120
    writers = {(tmp_path / "relay" / name).read_text() for name in written}
    if poisoned is None:  # every page rendered by a worker
        assert str(os.getpid()) not in writers
        assert relay_set.mp_workers == 2
    else:  # a worker died: the parent re-rendered every page
        assert writers == {str(os.getpid())}
        assert relay_set.mp_workers == 0
