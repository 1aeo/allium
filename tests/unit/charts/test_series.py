"""Onionoo 1M series and overlay alignment — no matplotlib."""

from datetime import datetime, timezone

from allium.lib.bandwidth_utils import build_bandwidth_map
from allium.lib.charts.series import (
    advertised_mbit,
    aligned_1m_series,
    chartable_fingerprints,
    daily_ratios,
    family_group_key,
    has_1m_graph,
    history_series,
    is_relay_fingerprint,
    month_blocks,
    overlays_for_relay,
    period_blocks,
    precompute_overlays,
    series_by_fp,
    spark_shared_ylim,
    spark_suffixes,
    period_axis_caption,
    period_html_name,
    period_title_span,
    period_views,
)
from allium.lib.time_utils import published_clock
from tests.unit.charts.conftest import (
    FP_A,
    FP_B,
    FP_C,
    FP_JEANGRAE,
    make_bw,
    make_relay,
)


_WRITE = {
    "first": "2026-07-16 12:00:00",
    "last": "2026-07-19 12:00:00",
    "interval": 86400,
    "factor": 1000.0,
    "values": [100, 110, None, 120],
}
_READ = {
    "first": "2026-07-16 12:00:00",
    "last": "2026-07-19 12:00:00",
    "interval": 86400,
    "factor": 1000.0,
    "values": [95, 105, None, 115],
}


def _bw(fp=FP_A):
    return make_bw(
        fp,
        write_values=list(_WRITE["values"]),
        read_values=list(_READ["values"]),
        factor=_WRITE["factor"],
        first=_WRITE["first"],
        last=_WRITE["last"],
        interval=_WRITE["interval"],
    )


def test_history_series_skips_nones():
    ts, vals = history_series(_WRITE)
    assert len(ts) == 3
    assert vals == [100000.0, 110000.0, 120000.0]
    assert ts[0] == datetime(2026, 7, 16, 12, tzinfo=timezone.utc)


def test_has_1m_graph_and_aligned_series():
    assert has_1m_graph(_bw()) is True
    series = aligned_1m_series(*month_blocks(_bw()))
    assert series is not None
    assert len(series["ts"]) == 3
    assert advertised_mbit(125000) == 1.0


def test_thin_or_missing_is_not_chartable():
    assert has_1m_graph({}) is False
    assert has_1m_graph({
        "write_history": {"1_month": {"values": [1], "first": "2026-01-01 00:00:00",
                                      "interval": 86400, "factor": 1}},
        "read_history": {"1_month": {"values": [1], "first": "2026-01-01 00:00:00",
                                     "interval": 86400, "factor": 1}},
    }) is False


def test_build_bandwidth_map_and_chartable():
    fp = FP_JEANGRAE
    doc = {"relays": [_bw(fp)]}
    bw_map = build_bandwidth_map(doc)
    assert fp in bw_map
    relays = [{"fingerprint": fp, "flags": ["Guard"]}]
    assert chartable_fingerprints(relays, bw_map) == [fp]


def test_chartable_limit_and_fingerprint_filter():
    fp1, fp2, fp3 = FP_A, FP_B, FP_C
    relays = [
        {"fingerprint": fp1, "flags": ["Guard"]},
        {"fingerprint": fp2, "flags": ["Guard"]},
        {"fingerprint": fp3, "flags": ["Guard"]},
    ]
    bw_map = {fp1: _bw(fp1), fp2: _bw(fp2), fp3: _bw(fp3)}
    assert chartable_fingerprints(relays, bw_map, limit=2) == [fp1, fp2]
    assert chartable_fingerprints(
        relays, bw_map, fingerprints=["$" + fp2.lower(), fp3],
    ) == [fp2, fp3]
    assert chartable_fingerprints(
        relays, bw_map, fingerprints=[fp2, fp3], limit=1,
    ) == [fp2]


def test_chartable_rejects_path_like_fingerprints():
    assert is_relay_fingerprint("../etc/passwd") is False
    assert is_relay_fingerprint("Α" * 40) is False
    evil = "../" + ("A" * 37)
    relays = [{"fingerprint": evil, "flags": ["Guard"]}]
    bw_map = {evil: _bw(evil)}
    assert chartable_fingerprints(relays, bw_map) == []


def test_published_clock_parses_onionoo_and_numbers():
    assert published_clock("") is None
    assert published_clock("not-a-date") is None
    ts = published_clock("2026-08-15 06:00:00")
    assert ts == datetime(2026, 8, 15, 6, 0, tzinfo=timezone.utc).timestamp()
    assert published_clock(ts) == ts


def test_series_by_fp_skips_thin_and_evil():
    evil = "../" + ("A" * 37)
    relays = [
        make_relay(FP_A, flags=["Guard"]),
        {"fingerprint": evil, "flags": ["Guard"]},
        {"fingerprint": FP_B, "flags": ["Guard"]},
    ]
    bw_map = {
        FP_A: _bw(FP_A),
        evil: _bw(evil),
        FP_B: {
            "fingerprint": FP_B,
            "write_history": {"1_month": {
                "values": [1], "first": "2026-01-01 00:00:00",
                "interval": 86400, "factor": 1,
            }},
            "read_history": {"1_month": {
                "values": [1], "first": "2026-01-01 00:00:00",
                "interval": 86400, "factor": 1,
            }},
        },
    }
    parsed = series_by_fp(relays, bw_map)
    assert set(parsed) == {FP_A}
    assert parsed[FP_A]["series"] is not None
    assert set(parsed[FP_A]["periods"]) == {"1m"}
    assert spark_suffixes(parsed[FP_A]) == ()


def test_family_group_key_from_effective_family():
    fp1 = FP_A
    fp2 = FP_B
    family = ["$" + fp1, "$" + fp2]
    key_a = family_group_key({
        "fingerprint": fp1, "effective_family": family, "contact_md5": "only-me",
    })
    key_b = family_group_key({
        "fingerprint": fp2, "effective_family": list(reversed(family)),
        "contact": "url:other.example",
    })
    assert key_a == key_b
    assert key_a.startswith("fam:")
    singleton = family_group_key({"fingerprint": fp1, "effective_family": [fp1]})
    assert singleton != key_a


def test_precompute_omits_singleton_family_overlay():
    fp1, fp2, fp3 = FP_A, FP_B, FP_C
    family_bc = [fp2, fp3]
    relays = [
        {
            "fingerprint": fp1, "flags": ["Guard"],
            "effective_family": [fp1], "contact_md5": "shared",
        },
        {
            "fingerprint": fp2, "flags": ["Guard"],
            "effective_family": family_bc, "contact_md5": "shared",
        },
        {
            "fingerprint": fp3, "flags": ["Guard"],
            "effective_family": family_bc, "contact_md5": "other",
        },
    ]
    bw_map = {
        fp1: _bw(fp1),
        fp2: _bw(fp2),
        fp3: _bw(fp3),
    }
    pre = precompute_overlays(relays, bw_map)
    assert "contact_median" not in pre
    assert "family_median" in pre
    write_1m, _read = month_blocks(_bw(fp1))
    family, role = overlays_for_relay(relays[0], write_1m, pre)
    assert family is None
    assert role is not None
    assert role["n"] == 3
    assert len(role["values"]) == 4

    family2, _role2 = overlays_for_relay(relays[1], write_1m, pre)
    assert family2 is not None
    assert family2["n"] == 2


def test_daily_ratios_skip_below_cut():
    tiny = {
        "write_history": {"1_month": {
            "first": "2026-07-16 12:00:00", "interval": 86400,
            "factor": 1.0, "values": [10, 10],
        }},
        "read_history": {"1_month": {
            "first": "2026-07-16 12:00:00", "interval": 86400,
            "factor": 1.0, "values": [10, 10],
        }},
    }
    assert daily_ratios(tiny) == {}
    assert daily_ratios(_bw())


def test_series_by_fp_collects_spark_periods_in_one_walk():
    bw = make_bw(
        FP_A,
        extra_periods=("6_months", "1_year"),
    )
    parsed = series_by_fp([make_relay(FP_A, flags=["Guard"])], {FP_A: bw})
    assert spark_suffixes(parsed[FP_A]) == ("6m", "1y")
    assert "1m" in parsed[FP_A]["periods"]
    assert "5y" not in parsed[FP_A]["periods"]
    write_6m, read_6m = period_blocks(bw, "6_months")
    assert parsed[FP_A]["periods"]["6m"]["write"] == write_6m
    assert parsed[FP_A]["periods"]["6m"]["read"] == read_6m
    ylim = spark_shared_ylim(
        {k: v for k, v in parsed[FP_A]["periods"].items() if k != "1m"}, 0,
    )
    assert ylim == max(parsed[FP_A]["periods"]["6m"]["series"]["write_m"])


def test_period_views_and_captions():
    assert period_html_name("1m") == "index.html"
    assert period_html_name("6m") == "6m.html"
    assert period_title_span("6m") == "last 6 months"
    assert period_axis_caption("6m", {"interval": 86400}) == "6M · 1-day"
    assert period_axis_caption("5y", {"interval": 604800}) == "5Y · 1-week"
    views = period_views(("1m", "6m", "1y"))
    by_hero = {hero: (name, sparks) for name, hero, sparks in views}
    assert by_hero["1m"] == ("index.html", ("6m", "1y"))
    assert by_hero["6m"] == ("6m.html", ("1m", "1y"))
    assert "5y" not in by_hero
    assert period_views(()) == ()
