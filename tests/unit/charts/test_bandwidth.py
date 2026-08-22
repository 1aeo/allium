"""Renderer contract: callable, lazy matplotlib, tiny synthetic PNG."""

import os
import sys

import pytest

from allium.lib.charts.registry import RELAY_BANDWIDTH_1M
from allium.lib.charts.pipeline import renderer_is_ready


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


def _synthetic_job():
    values_w = [80, 90, 85, 88, 92, 400, 350, 90, 91, 89]
    values_r = [76, 86, 82, 84, 88, 80, 80, 86, 87, 85]
    return {
        "nickname": "jeangrae",
        "operator": "1aeo.com",
        "fingerprint": "02B1C5DFBCBEC735435652050DE1AF0BB0B108CF",
        "advertised_bandwidth": 82000000,
        "flags": ["Fast", "Guard", "HSDir", "Running", "Stable", "V2Dir"],
        "role": "Guard",
        "last_restarted": "2025-10-01 00:00:00",
        "relays_published": "2026-08-15 06:00:00",
        "overload_general_timestamp": None,
        "overload_ratelimits": None,
        "overload_fd_exhausted": None,
        "write_1m": {
            "first": "2026-07-16 12:00:00",
            "last": "2026-07-25 12:00:00",
            "interval": 86400,
            "factor": 100000.0,
            "values": values_w,
        },
        "read_1m": {
            "first": "2026-07-16 12:00:00",
            "last": "2026-07-25 12:00:00",
            "interval": 86400,
            "factor": 100000.0,
            "values": values_r,
        },
        "family_overlay": None,
        "role_overlay": {
            "n": 10,
            "values": [1.04] * 10,
        },
        "bands_frozen_from": "2026-08-15 19:00:00",
    }


def test_renderer_writes_png_from_synthetic_series(temp_dir):
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg", force=True)
    from allium.lib.charts.bandwidth import render_relay_bandwidth_1m

    dest = os.path.join(temp_dir, "bandwidth-1m.png")
    out = render_relay_bandwidth_1m(_synthetic_job(), dest)
    assert out == dest
    assert os.path.isfile(dest)
    with open(dest, "rb") as handle:
        magic = handle.read(8)
    assert magic == b"\x89PNG\r\n\x1a\n"
    assert os.path.getsize(dest) > 2000


def test_renderer_rejects_thin_history(temp_dir):
    pytest.importorskip("matplotlib")
    from allium.lib.charts.bandwidth import render_relay_bandwidth_1m

    job = _synthetic_job()
    job["write_1m"] = None
    dest = os.path.join(temp_dir, "missing.png")
    with pytest.raises(ValueError):
        render_relay_bandwidth_1m(job, dest)
