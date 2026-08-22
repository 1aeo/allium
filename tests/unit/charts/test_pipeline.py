"""Tests for chart CLI flags and the skip-only chart pass."""

import argparse
import sys
from types import SimpleNamespace

from allium.lib.charts.pipeline import (
    CHARTS_AUTO,
    CHARTS_OFF,
    CHARTS_ON,
    _AUTO_HINT,
    _INSTALL_HINT,
    _RENDERER_HINT,
    add_chart_arguments,
    default_chart_workers,
    matplotlib_is_available,
    maybe_run_charts,
    renderer_is_ready,
    resolve_charts_mode,
)
from allium.lib.charts.registry import RELAY_BANDWIDTH_1M


def _parser():
    parser = argparse.ArgumentParser()
    add_chart_arguments(parser)
    return parser


def test_cli_default_is_off():
    args = _parser().parse_args([])
    assert args.charts == CHARTS_OFF
    assert args.chart_workers == 0
    assert resolve_charts_mode(args) == CHARTS_OFF


def test_cli_charts_bare_means_on():
    args = _parser().parse_args(["--charts"])
    assert args.charts == CHARTS_ON


def test_cli_charts_auto_and_no_charts():
    assert _parser().parse_args(["--charts", "auto"]).charts == CHARTS_AUTO
    assert _parser().parse_args(["--no-charts"]).charts == CHARTS_OFF
    # Last flag wins when both are given.
    assert _parser().parse_args(["--charts", "on", "--no-charts"]).charts == (
        CHARTS_OFF
    )


def test_default_chart_workers_caps_at_four():
    assert default_chart_workers(0) == max(1, min(4, __import__("os").cpu_count() or 1))
    assert default_chart_workers(2) == 2
    assert default_chart_workers(16) == 16
    assert default_chart_workers(-1) == max(1, min(4, __import__("os").cpu_count() or 1))


def test_renderer_is_not_ready_until_module_exists():
    assert renderer_is_ready(RELAY_BANDWIDTH_1M) is False


def test_maybe_run_charts_off_is_silent(capsys):
    result = maybe_run_charts(
        SimpleNamespace(bandwidth_data={"relays": [1]}),
        SimpleNamespace(charts="off"),
    )
    captured = capsys.readouterr()
    assert result.status == "skipped"
    assert result.reason == "off"
    assert captured.out == ""


def test_maybe_run_charts_on_without_renderer_does_not_fail(capsys, monkeypatch):
    monkeypatch.setattr(
        "allium.lib.charts.pipeline.matplotlib_is_available",
        lambda: True,
    )
    result = maybe_run_charts(
        SimpleNamespace(bandwidth_data={"relays": [1]}),
        SimpleNamespace(charts="on"),
    )
    captured = capsys.readouterr()
    assert result.status == "skipped"
    assert result.reason == "renderer_missing"
    assert _RENDERER_HINT in captured.out


def test_maybe_run_charts_on_without_matplotlib(capsys, monkeypatch):
    monkeypatch.setattr(
        "allium.lib.charts.pipeline.matplotlib_is_available",
        lambda: False,
    )
    result = maybe_run_charts(None, SimpleNamespace(charts="on"))
    captured = capsys.readouterr()
    assert result.reason == "matplotlib_missing"
    assert _INSTALL_HINT in captured.out


def test_maybe_run_charts_auto_skips_quietly_enough(capsys, monkeypatch):
    monkeypatch.setattr(
        "allium.lib.charts.pipeline.matplotlib_is_available",
        lambda: False,
    )
    result = maybe_run_charts(None, SimpleNamespace(charts="auto"))
    captured = capsys.readouterr()
    assert result.reason == "auto_unavailable"
    assert _AUTO_HINT in captured.out


def test_resolve_unknown_mode_is_off():
    assert resolve_charts_mode(SimpleNamespace(charts="maybe")) == CHARTS_OFF
    assert resolve_charts_mode(SimpleNamespace()) == CHARTS_OFF


def test_charts_package_import_does_not_load_matplotlib():
    already = "matplotlib" in sys.modules or "matplotlib.pyplot" in sys.modules
    # Importing the public package must stay extra-free.
    import allium.lib.charts  # noqa: F401
    import allium.lib.charts.cache  # noqa: F401
    import allium.lib.charts.pipeline  # noqa: F401
    if not already:
        assert "matplotlib" not in sys.modules
        assert "matplotlib.pyplot" not in sys.modules
    # find_spec does not import the module.
    matplotlib_is_available()
    if not already:
        assert "matplotlib.pyplot" not in sys.modules
