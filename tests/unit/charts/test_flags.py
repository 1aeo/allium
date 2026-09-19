"""Flag-presence charts from Onionoo /uptime flags graph-history."""

import os
import sys

from allium.lib.charts.cache import build_relay_flags_payload
from allium.lib.charts.pipeline import (
    FLAG_PERIOD_SPEC_BY_SUFFIX,
    get_chart,
    renderer_is_ready,
    run_chart_pass,
)
from allium.lib.charts.series import (
    flag_chartable_fingerprints,
    flag_percent_series,
    flag_series_by_fp,
    history_block,
    priority_flag,
)
from allium.lib.relays import apply_chart_html_flags
from allium.lib.uptime_utils import build_uptime_map
from tests.unit.charts.conftest import (
    FP_A,
    FP_B,
    FP_JEANGRAE,
    make_bw,
    make_relay,
    make_relay_set,
    make_uptime_data,
    make_uptime_history,
    on_args,
    stub_chart_pool,
)


def test_flag_fixture_has_running_1_month_values():
    import json
    from pathlib import Path

    doc = make_uptime_history()
    values = doc["flags"]["Running"]["1_month"]["values"]
    assert values
    assert all(0 <= v <= 999 for v in values)
    payload = json.loads(
        (Path(__file__).resolve().parent / "data" / "uptime_flags_running.json").read_text()
    )
    running = payload["relays"][0]["flags"]["Running"]["1_month"]["values"]
    assert running
    assert all(isinstance(v, int) and 0 <= v <= 999 for v in running)


def test_flag_renderer_is_not_bandwidth():
    for suffix, spec in FLAG_PERIOD_SPEC_BY_SUFFIX.items():
        assert renderer_is_ready(spec) is True, suffix
        assert spec.renderer_name == "render_relay_flags"
        assert get_chart("relay_flags_%s" % suffix) is spec
        assert spec.renderer_module != "allium.lib.charts.bandwidth"


def test_importing_flags_does_not_load_matplotlib():
    already = "matplotlib" in sys.modules or "matplotlib.pyplot" in sys.modules
    import allium.lib.charts.flags as flags

    assert flags.render_relay_flags is not None
    if not already:
        assert "matplotlib" not in sys.modules
        assert "matplotlib.pyplot" not in sys.modules


def test_exit_and_guard_selects_exit():
    details = [make_relay(flags=["Exit", "Guard", "Fast", "Running"])]
    uptime = make_uptime_history(flag_names=("Exit", "Guard", "Fast", "Running"))
    parsed = flag_series_by_fp(details, build_uptime_map({"relays": [uptime]}))
    assert parsed[FP_JEANGRAE]["flag"] == "Exit"
    assert priority_flag(["Exit", "Guard"], uptime["flags"]) == "Exit"


def test_empty_uptime_flags_emits_no_job(temp_dir, monkeypatch):
    jobs = []

    def capture(job, dest):
        jobs.append(job)
        from tests.unit.charts.conftest import fake_render
        return fake_render(job, dest)

    stub_chart_pool(monkeypatch, render=capture)
    relay_set = make_relay_set(
        temp_dir,
        uptime_data=make_uptime_data([make_uptime_history(flags_object=False)]),
    )
    result = run_chart_pass(relay_set, on_args(temp_dir))
    flag_jobs = [job for job in jobs if job.get("history")]
    assert flag_jobs == []
    assert not os.path.isfile(
        os.path.join(temp_dir, "relay", FP_JEANGRAE, "flags-1m.png")
    )
    assert result.rendered >= 1  # bandwidth still draws


def test_empty_flags_object_emits_no_job(temp_dir, monkeypatch):
    jobs = []

    def capture(job, dest):
        jobs.append(job)
        from tests.unit.charts.conftest import fake_render
        return fake_render(job, dest)

    stub_chart_pool(monkeypatch, render=capture)
    empty = make_uptime_history()
    empty["flags"] = {}
    relay_set = make_relay_set(temp_dir, bandwidth_data=None, uptime_data=make_uptime_data([empty]))
    result = run_chart_pass(relay_set, on_args(temp_dir))
    assert jobs == []
    assert result.reason in ("nothing_to_draw", "no_bandwidth_data")


def test_does_not_invent_timeline_from_details_or_aggregates():
    details = [make_relay(
        flags=["Exit", "Guard", "Running"],
        **{"_flag_uptime_data": {"Exit": {"1_month": {"uptime": 99.0}}}},
    )]
    uptime = make_uptime_history(flag_names=())
    parsed = flag_series_by_fp(details, build_uptime_map({"relays": [uptime]}))
    assert parsed == {}


def test_charts_limit_and_invalid_fingerprint(temp_dir, monkeypatch):
    jobs = []

    def capture(job, dest):
        jobs.append(job)
        from tests.unit.charts.conftest import fake_render
        return fake_render(job, dest)

    stub_chart_pool(monkeypatch, render=capture)
    pairs = [
        (make_relay(), make_bw()),
        (make_relay(FP_A, nickname="two"), make_bw(FP_A)),
        (make_relay(FP_B, nickname="three"), make_bw(FP_B)),
    ]
    uptime = make_uptime_data([
        make_uptime_history(FP_JEANGRAE),
        make_uptime_history(FP_A),
        make_uptime_history(FP_B),
    ])
    relay_set = make_relay_set(temp_dir, pairs, uptime_data=uptime)
    args = on_args(temp_dir, charts_limit=1)
    apply_chart_html_flags(relay_set, args)
    assert relay_set.flag_chart_fps == frozenset([FP_JEANGRAE])
    result = run_chart_pass(relay_set, args)
    flag_fps = {job["fingerprint"] for job in jobs if job.get("history")}
    assert flag_fps == {FP_JEANGRAE}
    assert result.rendered >= 1

    series = flag_series_by_fp(
        [{"fingerprint": "not-a-fp", "flags": ["Running"]}, make_relay(FP_A)],
        build_uptime_map(uptime),
    )
    assert "not-a-fp" not in series
    sliced = flag_chartable_fingerprints(
        [make_relay(FP_A), make_relay(FP_B)],
        flag_series_by_fp(
            [make_relay(FP_A), make_relay(FP_B)],
            build_uptime_map(uptime),
        ),
        fingerprints=["zzzz"],
    )
    assert sliced == []


def test_flag_jobs_use_flags_renderer_and_period(temp_dir, monkeypatch):
    jobs = []

    def capture(job, dest):
        jobs.append(job)
        from tests.unit.charts.conftest import fake_render
        return fake_render(job, dest)

    stub_chart_pool(monkeypatch, render=capture)
    relay_set = make_relay_set(
        temp_dir,
        [(make_relay(flags=["Exit", "Guard", "Running"]), make_bw())],
        uptime_data=make_uptime_data([
            make_uptime_history(
                flag_names=("Exit", "Guard", "Running"),
                extra_periods=("6_months", "1_year", "5_years"),
            ),
        ]),
    )
    result = run_chart_pass(relay_set, on_args(temp_dir))
    flag_jobs = [job for job in jobs if job.get("history")]
    assert {job["period"] for job in flag_jobs} == {"1m", "6m", "1y", "5y"}
    assert {job["flag"] for job in flag_jobs} == {"Exit"}
    assert all(job.get("period") in ("1m", "6m", "1y", "5y") for job in flag_jobs)
    assert "family_overlay" not in flag_jobs[0]
    assert "bands" not in flag_jobs[0]
    import json
    sidecar = os.path.join(
        temp_dir, ".chart-cache", "relay_flags_1m", FP_JEANGRAE + ".json",
    )
    assert json.load(open(sidecar))["chart_id"] == "relay_flags_1m"
    for suffix in ("1m", "6m", "1y", "5y"):
        assert os.path.isfile(
            os.path.join(temp_dir, "relay", FP_JEANGRAE, "flags-%s.png" % suffix)
        )
    assert result.rendered == 5  # 1 bandwidth 1m + 4 flag periods


def test_payload_names_selected_flag():
    payload = build_relay_flags_payload(
        make_relay(),
        flag="Exit",
        period="1m",
        history=history_block(make_uptime_history()["flags"]["Running"]["1_month"]),
    )
    assert payload["flag"] == "Exit"
    assert payload["chart_id"] == "relay_flags_1m"
    assert payload["period"] == "1m"
    assert "family_overlay" not in payload
    assert payload["history"]["values"]


def test_flag_percent_scale_matches_uptime_html():
    block = {
        "first": "2026-07-16 12:00:00",
        "last": "2026-07-19 12:00:00",
        "interval": 14400,
        "values": [999, None, 0],
    }
    ts, perc = flag_percent_series(block)
    assert len(ts) == 2
    assert perc[0] == 100.0
    assert perc[1] == 0.0


def test_flags_only_pass_skips_bandwidth_bands(temp_dir, monkeypatch):
    jobs = []

    def capture(job, dest):
        jobs.append(job)
        from tests.unit.charts.conftest import fake_render
        return fake_render(job, dest)

    stub_chart_pool(monkeypatch, render=capture)

    def boom(*args, **kwargs):
        raise AssertionError("bands_for_flags must not run for flags-only")

    monkeypatch.setattr("allium.lib.charts.bands.bands_for_flags", boom)
    relay_set = make_relay_set(
        temp_dir,
        bandwidth_data=None,
        uptime_data=make_uptime_data([make_uptime_history()]),
    )
    # details still needed
    relay_set.json = {
        "relays": [make_relay()],
        "relays_published": "2026-08-15 06:00:00",
    }
    result = run_chart_pass(relay_set, on_args(temp_dir))
    assert result.status == "ok"
    assert result.rendered == 1
    assert jobs[0]["flag"] == "Guard"
    assert jobs[0]["period"] == "1m"


def test_html_flags_mark_flag_chart(temp_dir, monkeypatch):
    stub_chart_pool(monkeypatch)
    relay_set = make_relay_set(
        temp_dir,
        uptime_data=make_uptime_data([make_uptime_history()]),
    )
    apply_chart_html_flags(relay_set, on_args(temp_dir))
    assert FP_JEANGRAE in relay_set.flag_chart_fps
    assert relay_set.flag_chart_periods[FP_JEANGRAE] == ("1m",)
    assert "Guard" in relay_set.flag_chart_labels[FP_JEANGRAE]


def test_renderer_writes_png_and_title_names_flag(temp_dir):
    import pytest
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg", force=True)
    from allium.lib.charts.flags import render_relay_flags

    dest = os.path.join(temp_dir, "flags-1m.png")
    job = build_relay_flags_payload(
        make_relay(),
        flag="Guard",
        period="1m",
        history=history_block(make_uptime_history()["flags"]["Guard"]["1_month"]),
    )
    assert render_relay_flags(job, dest) == dest
    with open(dest, "rb") as handle:
        assert handle.read(8) == b"\x89PNG\r\n\x1a\n"
    assert os.path.getsize(dest) > 2000


def test_flags_source_does_not_use_ratio_bands():
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[3]
        / "allium" / "lib" / "charts" / "flags.py"
    ).read_text(encoding="utf-8")
    assert "bands_for_flags" not in text
    assert "role_ratio_bands" not in text
    assert "bandwidth.py" not in text
