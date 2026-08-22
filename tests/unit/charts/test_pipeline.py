"""Tests for chart CLI flags and the after-HTML chart pass."""

import argparse
import os
import sys
from types import SimpleNamespace

from allium.lib.charts.pipeline import (
    CHARTS_AUTO,
    CHARTS_OFF,
    CHARTS_ON,
    _INSTALL_HINT,
    _NO_BANDWIDTH_HINT,
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


def _parser():
    parser = argparse.ArgumentParser()
    add_chart_arguments(parser)
    return parser


def test_cli_default_is_auto():
    args = _parser().parse_args([])
    assert args.charts == CHARTS_AUTO
    assert args.chart_workers == 0
    assert resolve_charts_mode(args) == CHARTS_AUTO


def test_cli_charts_bare_means_on():
    args = _parser().parse_args(["--charts"])
    assert args.charts == CHARTS_ON


def test_cli_charts_auto_and_no_charts():
    assert _parser().parse_args(["--charts", "auto"]).charts == CHARTS_AUTO
    assert _parser().parse_args(["--no-charts"]).charts == CHARTS_OFF
    assert _parser().parse_args(["--charts", "on", "--no-charts"]).charts == (
        CHARTS_OFF
    )


def test_default_chart_workers_caps_at_four():
    assert default_chart_workers(0) == max(1, min(4, __import__("os").cpu_count() or 1))
    assert default_chart_workers(2) == 2
    assert default_chart_workers(16) == 16
    assert default_chart_workers(-1) == max(1, min(4, __import__("os").cpu_count() or 1))


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
    monkeypatch.setattr(
        "allium.lib.charts.pipeline.matplotlib_is_available",
        lambda: False,
    )
    result = maybe_run_charts(None, SimpleNamespace(charts="on"))
    captured = capsys.readouterr()
    assert result.reason == "matplotlib_missing"
    assert _INSTALL_HINT in captured.out


def test_maybe_run_charts_auto_without_extra_is_silent(capsys, monkeypatch):
    monkeypatch.setattr(
        "allium.lib.charts.pipeline.matplotlib_is_available",
        lambda: False,
    )
    result = maybe_run_charts(None, SimpleNamespace(charts="auto"))
    captured = capsys.readouterr()
    assert result.reason == "auto_unavailable"
    assert captured.out == ""


def test_maybe_run_charts_on_without_bandwidth(capsys, monkeypatch):
    monkeypatch.setattr(
        "allium.lib.charts.pipeline.matplotlib_is_available",
        lambda: True,
    )
    result = maybe_run_charts(
        SimpleNamespace(bandwidth_data=None),
        SimpleNamespace(charts="on"),
    )
    captured = capsys.readouterr()
    assert result.reason == "no_bandwidth_data"
    assert _NO_BANDWIDTH_HINT in captured.out


def test_resolve_unknown_mode_is_off():
    assert resolve_charts_mode(SimpleNamespace(charts="maybe")) == CHARTS_OFF
    # Empty namespace: treat missing as auto, then unknown stays off only
    # when the value is present and invalid.
    assert resolve_charts_mode(SimpleNamespace()) == CHARTS_AUTO


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


_FP = "02B1C5DFBCBEC735435652050DE1AF0BB0B108CF"


def _relay_and_bw():
    relay = {
        "fingerprint": _FP,
        "nickname": "jeangrae",
        "contact": "url:1aeo.com proof:uri-rsa ciissversion:2",
        "contact_md5": "jg",
        "flags": ["Fast", "Guard", "HSDir", "Running", "Stable", "V2Dir"],
        "advertised_bandwidth": 82000000,
        "last_restarted": "2025-10-01 00:00:00",
        "overload_general_timestamp": None,
    }
    bw = {
        "fingerprint": _FP,
        "write_history": {
            "1_month": {
                "first": "2026-07-16 12:00:00",
                "last": "2026-07-19 12:00:00",
                "interval": 86400,
                "factor": 1000.0,
                "values": [100, 110, 120, 115],
            }
        },
        "read_history": {
            "1_month": {
                "first": "2026-07-16 12:00:00",
                "last": "2026-07-19 12:00:00",
                "interval": 86400,
                "factor": 1000.0,
                "values": [95, 105, 112, 110],
            }
        },
    }
    return relay, bw


def _relay_set(temp_dir, extra_relays=None):
    relay, bw = _relay_and_bw()
    relays = [relay] + list(extra_relays or [])
    bws = [bw]
    return SimpleNamespace(
        json={"relays": relays, "relays_published": "2026-08-15 06:00:00"},
        bandwidth_data={
            "relays": bws,
            "relays_published": "2026-08-15 06:00:00",
        },
        output_dir=temp_dir,
        use_bits=True,
    )


class _DummyPool(object):
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def imap_unordered(self, func, jobs, chunksize=1):
        return [func(job) for job in jobs]


class _DummyCtx(object):
    def Pool(self, **kwargs):
        return _DummyPool()


def _fake_render(job, dest):
    parent = os.path.dirname(dest)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(dest, "wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n" + b"fake")
    return dest


def test_apply_chart_html_flags_off_omits_img(temp_dir, monkeypatch):
    monkeypatch.setattr(
        "allium.lib.charts.pipeline.matplotlib_is_available",
        lambda: True,
    )
    relay_set = _relay_set(temp_dir)
    apply_chart_html_flags(relay_set, SimpleNamespace(charts="off"))
    assert relay_set.charts_enabled is False
    assert relay_set.bandwidth_chart_fps == frozenset()


def test_apply_chart_html_flags_auto_without_extra_omits_img(temp_dir, monkeypatch):
    monkeypatch.setattr(
        "allium.lib.charts.pipeline.matplotlib_is_available",
        lambda: False,
    )
    relay_set = _relay_set(temp_dir)
    apply_chart_html_flags(relay_set, SimpleNamespace(charts="auto"))
    assert relay_set.charts_enabled is False
    assert not charts_will_run(SimpleNamespace(charts="auto"), relay_set)


def test_apply_chart_html_flags_marks_chartable(temp_dir, monkeypatch):
    monkeypatch.setattr(
        "allium.lib.charts.pipeline.matplotlib_is_available",
        lambda: True,
    )
    relay_set = _relay_set(temp_dir)
    apply_chart_html_flags(relay_set, SimpleNamespace(charts="auto"))
    assert relay_set.charts_enabled is True
    assert _FP in relay_set.bandwidth_chart_fps


def test_cache_miss_renders_and_publishes(temp_dir, monkeypatch):
    monkeypatch.setattr(
        "allium.lib.charts.pipeline.matplotlib_is_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "allium.lib.charts.bandwidth.render_relay_bandwidth_1m",
        _fake_render,
    )
    monkeypatch.setattr(
        "multiprocessing.get_context",
        lambda name: _DummyCtx(),
    )
    relay_set = _relay_set(temp_dir)
    args = SimpleNamespace(charts="on", chart_workers=1, output_dir=temp_dir)
    result = run_chart_pass(relay_set, args)
    assert result.status == "ok"
    assert result.rendered == 1
    assert result.cache_hits == 0
    published = os.path.join(temp_dir, "relay", _FP, "bandwidth-1m.png")
    cached = os.path.join(
        temp_dir, ".chart-cache", "relay_bandwidth_1m", _FP + ".png",
    )
    assert os.path.isfile(published)
    assert os.path.isfile(cached)
    sidecar = os.path.join(
        temp_dir, ".chart-cache", "relay_bandwidth_1m", _FP + ".json",
    )
    assert os.path.isfile(sidecar)


def test_cache_hit_publishes_without_renderer(temp_dir, monkeypatch):
    calls = []

    def tracking_render(job, dest):
        calls.append(dest)
        return _fake_render(job, dest)

    monkeypatch.setattr(
        "allium.lib.charts.pipeline.matplotlib_is_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "allium.lib.charts.bandwidth.render_relay_bandwidth_1m",
        tracking_render,
    )
    monkeypatch.setattr(
        "multiprocessing.get_context",
        lambda name: _DummyCtx(),
    )
    relay_set = _relay_set(temp_dir)
    args = SimpleNamespace(charts="on", chart_workers=1, output_dir=temp_dir)
    first = run_chart_pass(relay_set, args)
    assert first.rendered == 1
    assert calls
    calls[:] = []
    # Wipe published tree the way write_relay_info rmtree's www/relay/.
    published = os.path.join(temp_dir, "relay", _FP, "bandwidth-1m.png")
    os.remove(published)
    second = run_chart_pass(relay_set, args)
    assert second.rendered == 0
    assert second.cache_hits == 1
    assert calls == []
    assert os.path.isfile(published)
