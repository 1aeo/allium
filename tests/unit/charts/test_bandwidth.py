"""Renderer contract: callable, lazy matplotlib, tiny synthetic PNG."""

import os
import sys

import pytest

from allium.lib.charts.registry import RELAY_BANDWIDTH_1M, SPARK_SPEC_BY_SUFFIX
from allium.lib.charts.pipeline import renderer_is_ready
from tests.unit.charts.conftest import make_job


def test_render_relay_bandwidth_1m_is_callable():
    assert renderer_is_ready(RELAY_BANDWIDTH_1M) is True
    from allium.lib.charts.bandwidth import render_relay_bandwidth_1m

    assert callable(render_relay_bandwidth_1m)


def test_importing_bandwidth_does_not_load_matplotlib():
    already = "matplotlib" in sys.modules or "matplotlib.pyplot" in sys.modules
    # Fresh attribute access after a prior import still must not force pyplot
    # in a clean interpreter; here we only assert the module itself is lazy
    # when matplotlib was not already imported by this process.
    import allium.lib.charts.bandwidth as bandwidth

    assert bandwidth.render_relay_bandwidth_1m is not None
    if not already:
        assert "matplotlib.pyplot" not in sys.modules


def test_renderer_writes_png_from_synthetic_series(temp_dir):
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg", force=True)
    from allium.lib.charts.bandwidth import render_relay_bandwidth_1m

    dest = os.path.join(temp_dir, "bandwidth-1m.png")
    out = render_relay_bandwidth_1m(make_job(), dest)
    assert out == dest
    assert os.path.isfile(dest)
    with open(dest, "rb") as handle:
        magic = handle.read(8)
    assert magic == b"\x89PNG\r\n\x1a\n"
    assert os.path.getsize(dest) > 2000


def test_renderer_rejects_thin_history(temp_dir):
    pytest.importorskip("matplotlib")
    from allium.lib.charts.bandwidth import render_relay_bandwidth_1m

    job = make_job()
    job["write_1m"] = None
    dest = os.path.join(temp_dir, "missing.png")
    with pytest.raises(ValueError):
        render_relay_bandwidth_1m(job, dest)


def test_spark_renderer_is_ready():
    spec = SPARK_SPEC_BY_SUFFIX["6m"]
    assert renderer_is_ready(spec) is True
    from allium.lib.charts.bandwidth import render_relay_bandwidth_spark

    assert callable(render_relay_bandwidth_spark)


def test_spark_renderer_writes_png(temp_dir):
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg", force=True)
    from allium.lib.charts.bandwidth import render_relay_bandwidth_spark

    hero = make_job()
    dest = os.path.join(temp_dir, "bandwidth-6m.png")
    out = render_relay_bandwidth_spark({
        "write": hero["write_1m"],
        "read": hero["read_1m"],
        "advertised_bandwidth": hero["advertised_bandwidth"],
        "last_restarted": hero["last_restarted"],
        "period": "6m",
        "ylim": 400.0,
    }, dest)
    assert out == dest
    with open(dest, "rb") as handle:
        assert handle.read(8) == b"\x89PNG\r\n\x1a\n"
    assert os.path.getsize(dest) > 800
