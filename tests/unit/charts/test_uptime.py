"""Uptime renderer contract: callable, lazy matplotlib, tiny synthetic PNG."""

import os
import sys

import pytest

from allium.lib.charts.pipeline import UPTIME_SPEC_BY_SUFFIX, renderer_is_ready
from allium.lib.charts.series import history_block
from tests.unit.charts.conftest import FP_JEANGRAE, make_uptime


def _uptime_job(**overrides):
    block = history_block(make_uptime()["uptime"]["1_month"])
    job = {
        "nickname": "jeangrae",
        "operator": "1aeo.com",
        "fingerprint": FP_JEANGRAE,
        "last_restarted": "2025-10-01 00:00:00",
        "period": "1m",
        "uptime": block,
    }
    job.update(overrides)
    return job


def test_uptime_renderers_are_ready():
    for suffix, spec in UPTIME_SPEC_BY_SUFFIX.items():
        assert renderer_is_ready(spec) is True, suffix
        assert spec.renderer_name == "render_relay_uptime"


def test_importing_uptime_does_not_load_matplotlib():
    already = "matplotlib" in sys.modules or "matplotlib.pyplot" in sys.modules
    import allium.lib.charts.uptime as uptime

    assert uptime.render_relay_uptime is not None
    if not already:
        assert "matplotlib.pyplot" not in sys.modules


def test_uptime_renderer_writes_png(temp_dir):
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg", force=True)
    from allium.lib.charts.uptime import render_relay_uptime

    dest = os.path.join(temp_dir, "uptime-1m.png")
    assert render_relay_uptime(_uptime_job(), dest) == dest
    with open(dest, "rb") as handle:
        assert handle.read(8) == b"\x89PNG\r\n\x1a\n"
    assert os.path.getsize(dest) > 2000


def test_uptime_renderer_writes_period_png(temp_dir):
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg", force=True)
    from allium.lib.charts.uptime import render_relay_uptime

    dest = os.path.join(temp_dir, "uptime-6m.png")
    out = render_relay_uptime(_uptime_job(period="6m"), dest)
    assert out == dest
    with open(dest, "rb") as handle:
        assert handle.read(8) == b"\x89PNG\r\n\x1a\n"


def test_uptime_renderer_rejects_thin_history(temp_dir):
    pytest.importorskip("matplotlib")
    from allium.lib.charts.uptime import render_relay_uptime

    with pytest.raises(ValueError):
        render_relay_uptime(
            _uptime_job(uptime=None),
            os.path.join(temp_dir, "missing.png"),
        )
