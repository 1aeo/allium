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
    assert restart_labels[0] == "Last restarted  Jul 20"

    out_of_span = _events_in_span(restart_events("2025-10-01 00:00:00"), ts)
    omitted = _ratio_labels({}, bands_for_flags(["Guard"]), out_of_span)
    assert not any(label.startswith("Last restarted") for label in omitted)


def test_trim_rgba_matches_strided_min_mask():
    """Channel-or trim must match rgb.min(axis=2) < white on a strided RGBA view."""
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg", force=True)
    import numpy as np

    from allium.lib.charts.bandwidth import _ensure_mpl, _trim_rgba

    _ensure_mpl()
    rgba = np.full((40, 50, 4), 255, dtype=np.uint8)
    rgba[8:30, 6:44, :3] = 10
    rgba[12, 3, :3] = (200, 200, 200)
    got = _trim_rgba(rgba, pad_px=2, white=250)
    ink = rgba[:, :, :3].min(axis=2) < 250
    rows = np.where(ink.any(axis=1))[0]
    cols = np.where(ink.any(axis=0))[0]
    expect = rgba[
        max(0, int(rows[0]) - 2):min(40, int(rows[-1]) + 3),
        max(0, int(cols[0]) - 2):min(50, int(cols[-1]) + 3),
    ]
    assert got.shape == expect.shape
    assert np.array_equal(got, expect)
    blank = np.full((8, 8, 4), 255, dtype=np.uint8)
    assert _trim_rgba(blank, pad_px=2, white=250) is blank


def test_date_axis_year_when_series_crosses_dec_jan():
    from datetime import datetime, timezone

    from allium.lib.charts.bandwidth import (
        date_axis_strftime,
        series_crosses_calendar_year,
    )

    cross = [
        datetime(2025, 8, 29, tzinfo=timezone.utc),
        datetime(2026, 8, 28, tzinfo=timezone.utc),
    ]
    same = [
        datetime(2026, 7, 16, tzinfo=timezone.utc),
        datetime(2026, 8, 15, tzinfo=timezone.utc),
    ]
    assert series_crosses_calendar_year(cross) is True
    assert series_crosses_calendar_year(same) is False
    assert date_axis_strftime("1y", cross) == "%b '%y"
    assert date_axis_strftime("6m", cross) == "%b '%y"
    assert date_axis_strftime("1y", same) == "%b"
    assert date_axis_strftime("6m", same) == "%b"
    assert date_axis_strftime("1m", same) == "%b %d"
    assert date_axis_strftime("1m", cross) == "%b %d"
    assert date_axis_strftime("5y", cross) == "%Y"
    assert date_axis_strftime("5y", same) == "%Y"


def test_date_axis_tick_labels_include_year_across_dec_jan():
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg", force=True)
    from datetime import datetime, timezone

    from allium.lib.charts.bandwidth import _date_axis, _ensure_mpl

    plt = _ensure_mpl()
    cross = [
        datetime(2025, 8, 29, tzinfo=timezone.utc),
        datetime(2026, 8, 28, tzinfo=timezone.utc),
    ]
    fig, ax = plt.subplots()
    ax.plot(cross, [1.0, 2.0])
    ax.set_xlim(cross[0], cross[-1])
    _date_axis(ax, "1y", cross)
    fig.canvas.draw()
    labels = [tick.get_text() for tick in ax.get_xticklabels() if tick.get_text()]
    plt.close(fig)
    assert any("'25" in label for label in labels)
    assert any("'26" in label for label in labels)
    assert all(label[:3].isalpha() for label in labels)

    fig, ax = plt.subplots()
    ax.plot(cross, [1.0, 2.0])
    ax.set_xlim(cross[0], cross[-1])
    _date_axis(ax, "5y", cross)
    fig.canvas.draw()
    year_labels = [tick.get_text() for tick in ax.get_xticklabels() if tick.get_text()]
    plt.close(fig)
    assert year_labels
    assert all(label.isdigit() and len(label) == 4 for label in year_labels)

    same = [
        datetime(2026, 7, 1, tzinfo=timezone.utc),
        datetime(2026, 7, 31, tzinfo=timezone.utc),
    ]
    fig, ax = plt.subplots()
    ax.plot(same, [1.0, 2.0])
    ax.set_xlim(same[0], same[-1])
    _date_axis(ax, "1y", same)
    fig.canvas.draw()
    month_labels = [tick.get_text() for tick in ax.get_xticklabels() if tick.get_text()]
    plt.close(fig)
    assert month_labels
    assert all("'" not in label for label in month_labels)
