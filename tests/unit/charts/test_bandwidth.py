"""Renderer contract: callable, lazy matplotlib, tiny synthetic PNG."""

import os
import sys

import pytest

from allium.lib.charts.pipeline import PERIOD_SPEC_BY_SUFFIX, renderer_is_ready
from tests.unit.charts.conftest import make_job


def test_period_hero_renderers_are_ready():
    for suffix, spec in PERIOD_SPEC_BY_SUFFIX.items():
        assert renderer_is_ready(spec) is True, suffix
        assert spec.renderer_name == "render_relay_bandwidth_1m"


def test_importing_bandwidth_does_not_load_matplotlib():
    already = "matplotlib" in sys.modules or "matplotlib.pyplot" in sys.modules
    import allium.lib.charts.bandwidth as bandwidth

    assert bandwidth.render_relay_bandwidth_1m is not None
    if not already:
        assert "matplotlib.pyplot" not in sys.modules


def test_renderer_writes_png_from_synthetic_series(temp_dir):
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg", force=True)
    from allium.lib.charts.bandwidth import render_relay_bandwidth_1m

    dest = os.path.join(temp_dir, "bandwidth-1m.png")
    assert render_relay_bandwidth_1m(make_job(), dest) == dest
    with open(dest, "rb") as handle:
        assert handle.read(8) == b"\x89PNG\r\n\x1a\n"
    assert os.path.getsize(dest) > 2000


def test_renderer_rejects_thin_history(temp_dir):
    pytest.importorskip("matplotlib")
    from allium.lib.charts.bandwidth import render_relay_bandwidth_1m

    job = make_job()
    job["write_1m"] = None
    with pytest.raises(ValueError):
        render_relay_bandwidth_1m(job, os.path.join(temp_dir, "missing.png"))


def test_period_hero_renderer_writes_png(temp_dir):
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg", force=True)
    from allium.lib.charts.bandwidth import render_relay_bandwidth_1m

    hero = make_job()
    dest = os.path.join(temp_dir, "bandwidth-6m.png")
    out = render_relay_bandwidth_1m({
        "nickname": hero["nickname"],
        "operator": hero["operator"],
        "write": hero["write_1m"],
        "read": hero["read_1m"],
        "advertised_bandwidth": hero["advertised_bandwidth"],
        "last_restarted": hero["last_restarted"],
        "flags": hero["flags"],
        "period": "6m",
        "family_overlay": None,
        "role_overlay": None,
    }, dest)
    assert out == dest
    with open(dest, "rb") as handle:
        assert handle.read(8) == b"\x89PNG\r\n\x1a\n"
    assert os.path.getsize(dest) > 2000


def _ratio_labels(overlays, bands, events):
    from allium.lib.charts.bandwidth import _ensure_mpl, _ratio_legend_handles

    _ensure_mpl()
    return [handle.get_label() for handle in _ratio_legend_handles(overlays, bands, events)]


def test_ratio_legend_includes_restart_handle_when_in_span():
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg", force=True)
    from datetime import datetime, timezone

    from allium.lib.charts.bands import bands_for_flags
    from allium.lib.charts.bandwidth import _events_in_span, restart_events

    ts = [
        datetime(2026, 7, 16, tzinfo=timezone.utc),
        datetime(2026, 7, 25, tzinfo=timezone.utc),
    ]
    in_span = _events_in_span(restart_events("2026-07-20 00:00:00"), ts)
    assert in_span
    labels = _ratio_labels({}, bands_for_flags(["Guard"]), in_span)
    restart_labels = [label for label in labels if label.startswith("Last restarted")]
    assert restart_labels
    assert restart_labels[0] == "Last restarted  20 Jul"

    out_of_span = _events_in_span(restart_events("2025-10-01 00:00:00"), ts)
    omitted = _ratio_labels({}, bands_for_flags(["Guard"]), out_of_span)
    assert not any(label.startswith("Last restarted") for label in omitted)
