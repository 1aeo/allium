"""Tests for chart CLI flags and the after-HTML chart pass."""

import argparse
import os
import sys
from types import SimpleNamespace

import pytest

from allium.lib.charts.pipeline import (
    CHARTS_AUTO,
    CHARTS_OFF,
    CHARTS_ON,
    MAX_CHART_WORKERS,
    _INSTALL_HINT,
    _NO_BANDWIDTH_HINT,
    _skip_reason,
    add_chart_arguments,
    apply_chart_html_flags,
    charts_will_run,
    default_chart_workers,
    matplotlib_is_available,
    maybe_run_charts,
    renderer_is_ready,
    resolve_charts_mode,
    run_chart_pass,
)
from allium.lib.charts.registry import RELAY_BANDWIDTH_1M
from tests.unit.charts.conftest import (
    FP_A,
    FP_B,
    FP_JEANGRAE,
    fake_render,
    make_bw,
    make_relay,
    make_relay_set,
    on_args,
    stub_chart_pool,
)


def _parser():
    parser = argparse.ArgumentParser()
    add_chart_arguments(parser)
    return parser


def test_cli_default_is_on():
    args = _parser().parse_args([])
    assert args.charts == CHARTS_ON
    assert args.chart_workers == 0
    assert args.charts_limit == 0
    assert args.chart_fingerprints is None
    assert resolve_charts_mode(args) == CHARTS_ON
    help_text = _parser().format_help()
    assert "default: on" in help_text
    assert "--charts-limit" in help_text
    assert "--fingerprint" in help_text


def test_cli_charts_bare_means_on():
    args = _parser().parse_args(["--charts"])
    assert args.charts == CHARTS_ON


def test_cli_charts_auto_and_no_charts():
    assert _parser().parse_args(["--charts", "auto"]).charts == CHARTS_AUTO
    assert _parser().parse_args(["--no-charts"]).charts == CHARTS_OFF
    assert _parser().parse_args(["--charts", "on", "--no-charts"]).charts == (
        CHARTS_OFF
    )


def test_cli_ramp_flags():
    args = _parser().parse_args([
        "--charts", "on",
        "--charts-limit", "3",
        "--fingerprint", "AA",
        "--fingerprint", "$bb",
    ])
    assert args.charts == CHARTS_ON
    assert args.charts_limit == 3
    assert args.chart_fingerprints == ["AA", "$bb"]


def test_default_chart_workers_hard_caps_at_eight():
    auto = max(1, min(4, os.cpu_count() or 1))
    assert default_chart_workers(0) == auto
    assert default_chart_workers(2) == 2
    assert default_chart_workers(8) == 8
    assert default_chart_workers(16) == MAX_CHART_WORKERS
    assert default_chart_workers(-1) == auto
    assert MAX_CHART_WORKERS == 8


def test_renderer_is_ready():
    assert renderer_is_ready(RELAY_BANDWIDTH_1M) is True


def test_maybe_run_charts_off_is_silent(capsys):
    result = maybe_run_charts(
        SimpleNamespace(bandwidth_data={"relays": [1]}),
        SimpleNamespace(charts="off"),
    )
    captured = capsys.readouterr()
    assert result.status == "skipped"
    assert result.reason == "off"
    assert captured.out == ""


def test_maybe_run_charts_on_without_matplotlib(capsys, monkeypatch):
    stub_chart_pool(monkeypatch, render=None, mpl=False)
    result = maybe_run_charts(None, SimpleNamespace(charts="on"))
    captured = capsys.readouterr()
    assert result.reason == "matplotlib_missing"
    assert _INSTALL_HINT in captured.out


def test_maybe_run_charts_auto_without_extra_is_silent(capsys, monkeypatch):
    stub_chart_pool(monkeypatch, render=None, mpl=False)
    result = maybe_run_charts(None, SimpleNamespace(charts="auto"))
    captured = capsys.readouterr()
    assert result.reason == "auto_unavailable"
    assert captured.out == ""


def test_maybe_run_charts_on_without_bandwidth(capsys, monkeypatch):
    stub_chart_pool(monkeypatch, render=None)
    result = maybe_run_charts(
        SimpleNamespace(bandwidth_data=None),
        SimpleNamespace(charts="on"),
    )
    captured = capsys.readouterr()
    assert result.reason == "no_bandwidth_data"
    assert _NO_BANDWIDTH_HINT in captured.out


def test_resolve_unknown_mode_is_off():
    assert resolve_charts_mode(SimpleNamespace(charts="maybe")) == CHARTS_OFF
    assert resolve_charts_mode(SimpleNamespace()) == CHARTS_OFF


def test_charts_package_import_does_not_load_matplotlib():
    already = "matplotlib" in sys.modules or "matplotlib.pyplot" in sys.modules
    import allium.lib.charts  # noqa: F401
    import allium.lib.charts.cache  # noqa: F401
    import allium.lib.charts.pipeline  # noqa: F401
    if not already:
        assert "matplotlib" not in sys.modules
        assert "matplotlib.pyplot" not in sys.modules
    matplotlib_is_available()
    if not already:
        assert "matplotlib.pyplot" not in sys.modules


@pytest.mark.parametrize("args,mpl", [
    (lambda: _parser().parse_args([]), False),
    (lambda: SimpleNamespace(charts="off"), True),
    (lambda: SimpleNamespace(charts="auto"), False),
])
def test_html_flags_omit_img_when_charts_will_not_run(
    temp_dir, monkeypatch, args, mpl,
):
    stub_chart_pool(monkeypatch, render=None, mpl=mpl)
    parsed = args()
    relay_set = make_relay_set(temp_dir)
    apply_chart_html_flags(relay_set, parsed)
    assert relay_set.charts_enabled is False
    assert relay_set.bandwidth_chart_fps == frozenset()
    assert not charts_will_run(parsed, relay_set)
    assert _skip_reason(parsed, relay_set)
    assert maybe_run_charts(relay_set, parsed).reason == _skip_reason(
        parsed, relay_set,
    )


@pytest.mark.parametrize("charts", [None, "auto"])
def test_html_flags_mark_chartable_when_pass_will_run(
    temp_dir, monkeypatch, charts,
):
    stub_chart_pool(monkeypatch, render=None)
    args = _parser().parse_args([]) if charts is None else SimpleNamespace(
        charts=charts,
    )
    relay_set = make_relay_set(temp_dir)
    apply_chart_html_flags(relay_set, args)
    assert relay_set.charts_enabled is True
    assert FP_JEANGRAE in relay_set.bandwidth_chart_fps
    assert not _skip_reason(args, relay_set)


def test_cache_miss_renders_and_publishes(temp_dir, monkeypatch):
    stub_chart_pool(monkeypatch)
    relay_set = make_relay_set(temp_dir)
    result = run_chart_pass(relay_set, on_args(temp_dir))
    assert result.status == "ok"
    assert result.rendered == 1
    assert result.cache_hits == 0
    published = os.path.join(temp_dir, "relay", FP_JEANGRAE, "bandwidth-1m.png")
    cached = os.path.join(
        temp_dir, ".chart-cache", "relay_bandwidth_1m", FP_JEANGRAE + ".png",
    )
    assert os.path.isfile(published)
    assert os.path.isfile(cached)
    sidecar = os.path.join(
        temp_dir, ".chart-cache", "relay_bandwidth_1m", FP_JEANGRAE + ".json",
    )
    assert os.path.isfile(sidecar)


def test_real_spawn_pool_renders_synthetic(temp_dir):
    """Exercise spawn (not the DummyCtx). Requires matplotlib extra."""
    if not matplotlib_is_available():
        pytest.skip("matplotlib extra not installed")
    relay_set = make_relay_set(temp_dir)
    result = run_chart_pass(relay_set, on_args(temp_dir))
    assert result.status == "ok"
    assert result.rendered == 1
    published = os.path.join(temp_dir, "relay", FP_JEANGRAE, "bandwidth-1m.png")
    assert os.path.isfile(published)
    with open(published, "rb") as handle:
        assert handle.read(8) == b"\x89PNG\r\n\x1a\n"


def test_cache_hit_publishes_without_renderer(temp_dir, monkeypatch):
    calls = []

    def tracking_render(job, dest):
        calls.append(dest)
        return fake_render(job, dest)

    stub_chart_pool(monkeypatch, render=tracking_render)
    relay_set = make_relay_set(temp_dir)
    args = on_args(temp_dir)
    first = run_chart_pass(relay_set, args)
    assert first.rendered == 1
    assert calls
    calls[:] = []
    published = os.path.join(temp_dir, "relay", FP_JEANGRAE, "bandwidth-1m.png")
    os.remove(published)
    second = run_chart_pass(relay_set, args)
    assert second.rendered == 0
    assert second.cache_hits == 1
    assert calls == []
    assert os.path.isfile(published)


def test_charts_limit_slices_html_and_pass(temp_dir, monkeypatch):
    stub_chart_pool(monkeypatch)
    extra = [
        (make_relay(FP_A, nickname="two"), make_bw(FP_A)),
        (make_relay(FP_B, nickname="three"), make_bw(FP_B)),
    ]
    relay_set = make_relay_set(
        temp_dir, [(make_relay(), make_bw())] + extra,
    )
    args = on_args(temp_dir, charts_limit=1)
    apply_chart_html_flags(relay_set, args)
    assert relay_set.charts_enabled is True
    assert relay_set.bandwidth_chart_fps == frozenset([FP_JEANGRAE])
    result = run_chart_pass(relay_set, args)
    assert result.rendered == 1
    assert os.path.isfile(
        os.path.join(temp_dir, "relay", FP_JEANGRAE, "bandwidth-1m.png")
    )
    assert not os.path.isfile(
        os.path.join(temp_dir, "relay", FP_A, "bandwidth-1m.png")
    )


def test_charts_limit_family_overlay_uses_full_population(temp_dir, monkeypatch):
    jobs = []

    def capture(job, dest):
        jobs.append(job)
        return fake_render(job, dest)

    stub_chart_pool(monkeypatch, render=capture)
    family = [FP_JEANGRAE, FP_A]
    pairs = [
        (make_relay(FP_JEANGRAE, family=family), make_bw(FP_JEANGRAE)),
        (make_relay(FP_A, nickname="two", family=family), make_bw(FP_A)),
    ]
    relay_set = make_relay_set(temp_dir, pairs)
    args = on_args(temp_dir, charts_limit=1)
    apply_chart_html_flags(relay_set, args)
    assert relay_set.bandwidth_chart_fps == frozenset([FP_JEANGRAE])
    result = run_chart_pass(relay_set, args)
    assert result.rendered == 1
    overlay = jobs[0]["family_overlay"]
    assert overlay is not None
    assert overlay["n"] == 2
    assert "series" not in jobs[0]
    assert "ts" not in jobs[0]


def test_apply_then_pass_parses_series_once(temp_dir, monkeypatch):
    import allium.lib.charts.pipeline as pipeline_mod
    import allium.lib.charts.series as series_mod

    calls = []
    real = series_mod.series_by_fp

    def counting(*a, **k):
        calls.append(1)
        return real(*a, **k)

    monkeypatch.setattr(series_mod, "series_by_fp", counting)
    monkeypatch.setattr(pipeline_mod, "series_by_fp", counting)
    stub_chart_pool(monkeypatch)
    relay_set = make_relay_set(temp_dir)
    args = on_args(temp_dir)
    apply_chart_html_flags(relay_set, args)
    run_chart_pass(relay_set, args)
    assert len(calls) == 1


def test_fingerprint_flag_selects_one_relay(temp_dir, monkeypatch):
    stub_chart_pool(monkeypatch)
    pairs = [
        (make_relay(), make_bw()),
        (make_relay(FP_A, nickname="two"), make_bw(FP_A)),
    ]
    relay_set = make_relay_set(temp_dir, pairs)
    args = on_args(temp_dir, chart_fingerprints=["$" + FP_A.lower()])
    apply_chart_html_flags(relay_set, args)
    assert relay_set.bandwidth_chart_fps == frozenset([FP_A])
    result = run_chart_pass(relay_set, args)
    assert result.rendered == 1
    assert os.path.isfile(os.path.join(temp_dir, "relay", FP_A, "bandwidth-1m.png"))
    assert not os.path.isfile(
        os.path.join(temp_dir, "relay", FP_JEANGRAE, "bandwidth-1m.png")
    )


def test_maybe_run_charts_pass_error_leaves_html(monkeypatch, capsys):
    stub_chart_pool(monkeypatch, render=None)
    monkeypatch.setattr(
        "allium.lib.charts.pipeline.run_chart_pass",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("pool dead")),
    )
    result = maybe_run_charts(
        SimpleNamespace(bandwidth_data={"relays": [1]}),
        SimpleNamespace(charts="on"),
    )
    assert result.status == "error"
    assert result.reason == "pass_failed"
    assert "HTML unchanged" in capsys.readouterr().out


def test_one_bad_relay_does_not_kill_the_pass(temp_dir, monkeypatch):
    def flaky_render(job, dest):
        if job.get("fingerprint") == FP_A:
            raise RuntimeError("boom")
        return fake_render(job, dest)

    stub_chart_pool(monkeypatch, render=flaky_render)
    pairs = [
        (make_relay(), make_bw()),
        (make_relay(FP_A, nickname="two"), make_bw(FP_A)),
    ]
    result = run_chart_pass(make_relay_set(temp_dir, pairs), on_args(temp_dir))
    assert result.rendered == 1
    assert result.failed == 1
    assert result.reason == "partial"
    assert os.path.isfile(
        os.path.join(temp_dir, "relay", FP_JEANGRAE, "bandwidth-1m.png")
    )
    assert not os.path.isfile(
        os.path.join(temp_dir, "relay", FP_A, "bandwidth-1m.png")
    )
