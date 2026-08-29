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
    _RENDER_SKIP_KEYS,
    _skip_reason,
    add_chart_arguments,
    allocate_period_workers,
    chart_imap_chunksize,
    default_chart_workers,
    job_period,
    matplotlib_is_available,
    maybe_run_charts,
    partition_jobs_by_period,
    resolve_charts_mode,
    run_chart_pass,
)
from allium.lib.relays import apply_chart_html_flags
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


def test_cli_charts_flags():
    default = _parser().parse_args([])
    assert default.charts == CHARTS_ON
    assert default.chart_workers == 0
    assert default.charts_limit == 0
    assert default.chart_fingerprints is None
    assert resolve_charts_mode(default) == CHARTS_ON
    help_text = _parser().format_help()
    assert "default: on" in help_text
    assert "--charts-limit" in help_text
    assert _parser().parse_args(["--charts"]).charts == CHARTS_ON
    assert _parser().parse_args(["--charts", "auto"]).charts == CHARTS_AUTO
    assert _parser().parse_args(["--no-charts"]).charts == CHARTS_OFF
    assert _parser().parse_args(["--charts", "on", "--no-charts"]).charts == CHARTS_OFF
    ramp = _parser().parse_args([
        "--charts", "on", "--charts-limit", "3",
        "--fingerprint", "AA", "--fingerprint", "$bb",
    ])
    assert ramp.charts_limit == 3
    assert ramp.chart_fingerprints == ["AA", "$bb"]
    auto = max(1, min(MAX_CHART_WORKERS, os.cpu_count() or 1))
    assert MAX_CHART_WORKERS == 16
    assert default_chart_workers(0) == auto
    assert default_chart_workers(2) == 2
    assert default_chart_workers(8) == 8
    assert default_chart_workers(16) == MAX_CHART_WORKERS
    assert default_chart_workers(32) == MAX_CHART_WORKERS
    assert default_chart_workers(-1) == auto
    help_text = _parser().format_help()
    assert "min(CPU, 16)" in help_text
    assert "1M/6M/1Y/5Y" in help_text


@pytest.mark.parametrize("args,mpl,reason,hint", [
    (SimpleNamespace(charts="off"), True, "off", None),
    (SimpleNamespace(charts="on"), False, "matplotlib_missing", _INSTALL_HINT),
    (SimpleNamespace(charts="auto"), False, "auto_unavailable", None),
])
def test_maybe_run_charts_skip_reasons(capsys, monkeypatch, args, mpl, reason, hint):
    stub_chart_pool(monkeypatch, render=None, mpl=mpl)
    result = maybe_run_charts(
        SimpleNamespace(bandwidth_data={"relays": [1]}), args,
    )
    captured = capsys.readouterr()
    assert result.status == "skipped"
    assert result.reason == reason
    if hint:
        assert hint in captured.out
    else:
        assert captured.out == ""


def test_maybe_run_charts_on_without_bandwidth(capsys, monkeypatch):
    stub_chart_pool(monkeypatch, render=None)
    result = maybe_run_charts(
        SimpleNamespace(bandwidth_data=None), SimpleNamespace(charts="on"),
    )
    assert result.reason == "no_bandwidth_data"
    assert _NO_BANDWIDTH_HINT in capsys.readouterr().out


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
    assert relay_set.bandwidth_spark_periods == {}
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
    result = run_chart_pass(make_relay_set(temp_dir), on_args(temp_dir))
    assert result.status == "ok"
    assert result.rendered == 1
    assert result.cache_hits == 0
    base = os.path.join(temp_dir, "relay", FP_JEANGRAE)
    assert os.path.isfile(os.path.join(base, "bandwidth-1m.png"))
    assert os.path.isfile(os.path.join(
        temp_dir, ".chart-cache", "relay_bandwidth_1m", FP_JEANGRAE + ".png",
    ))
    assert not os.path.isfile(os.path.join(base, "bandwidth-6m.png"))


def test_real_spawn_pool_renders_synthetic(temp_dir):
    if not matplotlib_is_available():
        pytest.skip("matplotlib extra not installed")
    result = run_chart_pass(make_relay_set(temp_dir), on_args(temp_dir))
    assert result.status == "ok"
    assert result.rendered == 1
    published = os.path.join(temp_dir, "relay", FP_JEANGRAE, "bandwidth-1m.png")
    with open(published, "rb") as handle:
        assert handle.read(8) == b"\x89PNG\r\n\x1a\n"


def test_cache_hit_republishes_without_renderer(temp_dir, monkeypatch):
    calls = []

    def tracking_render(job, dest):
        calls.append(dest)
        return fake_render(job, dest)

    stub_chart_pool(monkeypatch, render=tracking_render)
    relay_set = make_relay_set(temp_dir, [(
        make_relay(), make_bw(extra_periods=("6_months",)),
    )])
    args = on_args(temp_dir)
    first = run_chart_pass(relay_set, args)
    assert first.rendered == 2
    assert calls
    calls[:] = []
    spark = os.path.join(temp_dir, "relay", FP_JEANGRAE, "bandwidth-6m.png")
    os.remove(spark)
    second = run_chart_pass(relay_set, args)
    assert second.rendered == 0
    assert second.cache_hits == 2
    assert calls == []
    assert os.path.isfile(spark)


def test_charts_limit_slices_and_keeps_family_overlay(temp_dir, monkeypatch):
    jobs = []

    def capture(job, dest):
        jobs.append(job)
        return fake_render(job, dest)

    stub_chart_pool(monkeypatch, render=capture)
    family = [FP_JEANGRAE, FP_A]
    pairs = [
        (make_relay(FP_JEANGRAE, family=family), make_bw(FP_JEANGRAE)),
        (make_relay(FP_A, nickname="two", family=family), make_bw(FP_A)),
        (make_relay(FP_B, nickname="three"), make_bw(FP_B)),
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
    assert os.path.isfile(
        os.path.join(temp_dir, "relay", FP_JEANGRAE, "bandwidth-1m.png")
    )
    assert not os.path.isfile(
        os.path.join(temp_dir, "relay", FP_A, "bandwidth-1m.png")
    )


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
    args = on_args(temp_dir)
    relay_set = make_relay_set(temp_dir)
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


def test_sparks_publish_and_omit_missing_5y(temp_dir, monkeypatch):
    stub_chart_pool(monkeypatch)
    relay_set = make_relay_set(temp_dir, [(
        make_relay(),
        make_bw(extra_periods=("6_months", "1_year")),
    )])
    args = on_args(temp_dir)
    apply_chart_html_flags(relay_set, args)
    assert relay_set.bandwidth_spark_periods[FP_JEANGRAE] == ("6m", "1y")
    result = run_chart_pass(relay_set, args)
    assert result.rendered == 3
    base = os.path.join(temp_dir, "relay", FP_JEANGRAE)
    assert os.path.isfile(os.path.join(base, "bandwidth-1m.png"))
    assert os.path.isfile(os.path.join(base, "bandwidth-6m.png"))
    assert os.path.isfile(os.path.join(base, "bandwidth-1y.png"))
    assert not os.path.isfile(os.path.join(base, "bandwidth-5y.png"))


def test_cache_hit_is_per_period(temp_dir, monkeypatch):
    stub_chart_pool(monkeypatch)
    relay_set = make_relay_set(temp_dir, [(
        make_relay(),
        make_bw(extra_periods=("6_months",)),
    )])
    args = on_args(temp_dir)
    first = run_chart_pass(relay_set, args)
    assert first.rendered == 2
    os.remove(os.path.join(
        temp_dir, ".chart-cache", "relay_bandwidth_6m", FP_JEANGRAE + ".json",
    ))
    second = run_chart_pass(relay_set, args)
    assert second.cache_hits == 1
    assert second.rendered == 1
    assert os.path.isfile(
        os.path.join(temp_dir, "relay", FP_JEANGRAE, "bandwidth-6m.png")
    )


def test_job_period_reads_wrapper_chart_id_and_render():
    assert job_period({"period": "6m", "chart_id": "relay_bandwidth_1m"}) == "6m"
    assert job_period({"chart_id": "relay_bandwidth_5y"}) == "5y"
    assert job_period({"render": {"period": "1y"}}) == "1y"
    assert job_period({}) == "1m"


def test_partition_jobs_by_period_keeps_known_order():
    jobs = [
        {"period": "1m", "fingerprint": "a"},
        {"period": "6m", "fingerprint": "a"},
        {"period": "1y", "fingerprint": "a"},
        {"period": "5y", "fingerprint": "a"},
        {"period": "1m", "fingerprint": "b"},
        {"chart_id": "relay_bandwidth_6m", "fingerprint": "b"},
    ]
    groups = partition_jobs_by_period(jobs)
    assert [period for period, _group in groups] == ["1m", "6m", "1y", "5y"]
    assert [len(group) for _period, group in groups] == [2, 2, 1, 1]


@pytest.mark.parametrize("workers,n_groups,expected", [
    (16, 4, [4, 4, 4, 4]),
    (8, 4, [2, 2, 2, 2]),
    (5, 4, [2, 1, 1, 1]),
    (4, 4, [1, 1, 1, 1]),
    (7, 3, [3, 2, 2]),
])
def test_allocate_period_workers_splits_one_budget(workers, n_groups, expected):
    alloc = allocate_period_workers(workers, n_groups)
    assert alloc == expected
    assert sum(alloc) == workers
    assert all(count >= 1 for count in alloc)


def test_allocate_period_workers_falls_back_when_fewer_than_periods():
    assert allocate_period_workers(3, 4) is None
    assert allocate_period_workers(0, 4) is None
    assert allocate_period_workers("x", 4) is None


def test_chart_imap_chunksize_batches_without_huge_chunks():
    assert chart_imap_chunksize(1, 4) == 1
    assert chart_imap_chunksize(8000, 4) == 32
    assert chart_imap_chunksize(8000, 1) == 32
    assert chart_imap_chunksize(10, 2) == 1
    assert 1 <= chart_imap_chunksize(100, 4) <= 32


def test_four_periods_use_one_runner_each(temp_dir, monkeypatch):
    pool_calls = []
    imap_periods = []

    class TrackingPool(object):
        def __init__(self, **kwargs):
            pool_calls.append(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def imap_unordered(self, func, jobs, chunksize=1):
            imap_periods.append([job.get("period") for job in jobs])
            return [func(job) for job in jobs]

    class TrackingCtx(object):
        def Pool(self, **kwargs):
            return TrackingPool(**kwargs)

    monkeypatch.setattr(
        "allium.lib.charts.pipeline.matplotlib_is_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "allium.lib.charts.bandwidth.render_relay_bandwidth_1m",
        fake_render,
    )
    monkeypatch.setattr("multiprocessing.get_context", lambda name: TrackingCtx())

    relay_set = make_relay_set(temp_dir, [(
        make_relay(),
        make_bw(extra_periods=("6_months", "1_year", "5_years")),
    )])
    result = run_chart_pass(relay_set, on_args(temp_dir, chart_workers=4))
    assert result.rendered == 4
    assert len(pool_calls) == 4
    assert [call.get("processes") for call in pool_calls] == [1, 1, 1, 1]
    assert [set(group) for group in imap_periods] == [
        {"1m"}, {"6m"}, {"1y"}, {"5y"},
    ]


def test_one_worker_does_not_open_four_pools(temp_dir, monkeypatch):
    pool_calls = []

    class TrackingPool(object):
        def __init__(self, **kwargs):
            pool_calls.append(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def imap_unordered(self, func, jobs, chunksize=1):
            return [func(job) for job in jobs]

    class TrackingCtx(object):
        def Pool(self, **kwargs):
            return TrackingPool(**kwargs)

    monkeypatch.setattr(
        "allium.lib.charts.pipeline.matplotlib_is_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "allium.lib.charts.bandwidth.render_relay_bandwidth_1m",
        fake_render,
    )
    monkeypatch.setattr("multiprocessing.get_context", lambda name: TrackingCtx())

    relay_set = make_relay_set(temp_dir, [(
        make_relay(),
        make_bw(extra_periods=("6_months", "1_year", "5_years")),
    )])
    result = run_chart_pass(relay_set, on_args(temp_dir, chart_workers=1))
    assert result.rendered == 4
    assert len(pool_calls) == 1


def test_queued_render_omits_cache_only_fields(temp_dir, monkeypatch):
    seen = []

    def capture(job, dest):
        seen.append(job)
        return fake_render(job, dest)

    stub_chart_pool(monkeypatch, render=capture)
    run_chart_pass(make_relay_set(temp_dir), on_args(temp_dir))
    assert seen
    for key in _RENDER_SKIP_KEYS:
        assert key not in seen[0]
    assert seen[0].get("period") == "1m"
    assert "write_1m" in seen[0]
