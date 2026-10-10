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


def _relay_set(output_dir, count=120):
    return SimpleNamespace(
        json={"relays": [{"fingerprint": f"{i:040X}"} for i in range(count)]},
        output_dir=str(output_dir),
        mp_workers=2,
        progress_logger=Mock(),
    )


@pytest.mark.skipif(not hasattr(os, "fork"), reason="needs fork()")
def test_relay_pages_render_in_parallel(tmp_path, monkeypatch):
    monkeypatch.setattr(page_writer, "_RelayPageRenderer", _FakeRenderer)
    monkeypatch.setattr(_FakeRenderer, "parent_pid", os.getpid())
    monkeypatch.setattr(_FakeRenderer, "poisoned", None)
    relay_set = _relay_set(tmp_path)

    page_writer.write_relay_info(relay_set)

    written = os.listdir(tmp_path / "relay")
    assert len(written) == 120
    writers = {(tmp_path / "relay" / name).read_text() for name in written}
    assert str(os.getpid()) not in writers
    assert relay_set.mp_workers == 2


@pytest.mark.skipif(not hasattr(os, "fork"), reason="needs fork()")
def test_relay_pages_fall_back_when_a_worker_dies(tmp_path, monkeypatch):
    monkeypatch.setattr(page_writer, "_RelayPageRenderer", _FakeRenderer)
    monkeypatch.setattr(_FakeRenderer, "parent_pid", os.getpid())
    monkeypatch.setattr(_FakeRenderer, "poisoned", f"{7:040X}")
    relay_set = _relay_set(tmp_path)

    page_writer.write_relay_info(relay_set)

    written = os.listdir(tmp_path / "relay")
    assert len(written) == 120
    assert {(tmp_path / "relay" / name).read_text() for name in written} == {str(os.getpid())}
    assert relay_set.mp_workers == 0
