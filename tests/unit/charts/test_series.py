"""Onionoo 1M series and overlay alignment — no matplotlib."""

from datetime import datetime, timezone

from allium.lib.charts.series import (
    advertised_mbit,
    aligned_1m_series,
    build_bandwidth_map,
    chartable_fingerprints,
    daily_ratios,
    family_group_key,
    has_1m_graph,
    history_series,
    is_relay_fingerprint,
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


def test_chartable_limit_and_fingerprint_filter():
    fp1 = "A" * 40
    fp2 = "B" * 40
    fp3 = "C" * 40
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


def test_family_group_key_from_effective_family():
    fp1 = "A" * 40
    fp2 = "B" * 40
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
    fp1 = "A" * 40
    fp2 = "B" * 40
    fp3 = "C" * 40
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
