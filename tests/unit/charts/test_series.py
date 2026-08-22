"""Onionoo 1M series and overlay alignment — no matplotlib."""

from datetime import datetime, timezone

from allium.lib.charts.series import (
    advertised_mbit,
    aligned_1m_series,
    build_bandwidth_map,
    chartable_fingerprints,
    contact_group_key,
    daily_ratios,
    has_1m_graph,
    history_series,
    month_blocks,
    overlays_for_relay,
    precompute_overlays,
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


def _bw(fp="A" * 40):
    return {
        "fingerprint": fp,
        "write_history": {"1_month": dict(_WRITE)},
        "read_history": {"1_month": dict(_READ)},
    }


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
    fp = "02B1C5DFBCBEC735435652050DE1AF0BB0B108CF"
    doc = {"relays": [_bw(fp)]}
    bw_map = build_bandwidth_map(doc)
    assert fp in bw_map
    relays = [{"fingerprint": fp, "flags": ["Guard"]}]
    assert chartable_fingerprints(relays, bw_map) == [fp]


def test_contact_group_prefers_md5():
    assert contact_group_key({"contact_md5": "abc"}) == "md5:abc"
    assert contact_group_key({"contact": "url:1aeo.com"}) == "host:1aeo.com"
    assert contact_group_key({}) == ""


def test_precompute_omits_singleton_contact_overlay():
    fp1 = "A" * 40
    fp2 = "B" * 40
    relays = [
        {"fingerprint": fp1, "flags": ["Guard"], "contact_md5": "only-me"},
        {"fingerprint": fp2, "flags": ["Guard"], "contact_md5": "us", "contact": "url:x.com"},
    ]
    # Second contact group needs two members for a family overlay.
    relays.append({
        "fingerprint": "C" * 40, "flags": ["Guard"], "contact_md5": "us",
    })
    bw_map = {
        fp1: _bw(fp1),
        fp2: _bw(fp2),
        "C" * 40: _bw("C" * 40),
    }
    pre = precompute_overlays(relays, bw_map)
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
