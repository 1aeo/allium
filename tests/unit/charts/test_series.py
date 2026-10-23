"""Onionoo history parsing, operator sums and peer medians for the charts."""

from datetime import datetime, timedelta, timezone

import pytest

from allium.lib.charts.series import (
    MBIT, active_ratio, family_key, network_ratio_bands, network_uptime, operator_throughput, peer_medians, points,
    throughput, uptime_points,
)
from allium.lib.uptime_utils import _block_uptime_percentage_and_datapoints, uptime_windows

from .fixtures import DAY, T0, block, history, relay


def test_points_scale_by_factor_skip_holes_and_clip_to_window():
    assert points(block([1, None, 3]), 2.0) == {T0: 2000.0, T0 + timedelta(days=2): 6000.0}
    assert points(block([1, 2, 3]), since=T0 + timedelta(days=1)) == {
        T0 + timedelta(days=1): 2000.0, T0 + timedelta(days=2): 3000.0}
    assert points(None) == {} and points(block([1], first="bad")) == {}


def test_uptime_points_follow_onionoos_window_and_pad_a_stopped_history():
    # Published 30 Sep 12:00: Onionoo's 1-month window is 186 four-hour slots from 30 Aug 14:00
    windows = uptime_windows({"relays_published": "2026-09-30 12:00:00", "relays": []})
    first = datetime(2026, 8, 30, 14, tzinfo=timezone.utc)
    stopped = block([999] * 150, first="2026-08-30 14:00:00", interval=14400, factor=1 / 999.0)  # ends 24 Sep 12:00
    drawn = uptime_points(stopped, "1_month", windows)
    assert sorted(drawn) == [first + timedelta(hours=4 * i) for i in range(186)]
    assert [drawn[t] for t in sorted(drawn)][148:152] == [pytest.approx(100.0)] * 2 + [0.0] * 2
    # Last seen 24 Sep 11:00, so its consensus hour runs to 12:00, the block's end: no hours missing
    assert uptime_points(stopped, "1_month", windows, {"last_seen": "2026-09-24 11:00:00"}) == drawn
    # Last seen 24 Sep 13:00: the first missing slot holds its last two hours, half the slot
    late = uptime_points(stopped, "1_month", windows, {"last_seen": "2026-09-24 13:00:00"})
    assert [late[t] for t in sorted(late)][149:152] == [pytest.approx(100.0), pytest.approx(50.0), 0.0]
    older = block([999] * 186, first="2026-08-28 14:00:00", interval=14400, factor=1 / 999.0)
    assert min(uptime_points(older, "1_month", windows)) == first  # its first 12 slots predate the window
    assert sum(uptime_points(older, "1_month", windows).values()) == pytest.approx(174 * 100.0)
    assert uptime_points(stopped, "1_month", {}) == points(stopped, 100.0)


def test_an_uptime_block_without_a_factor_is_read_as_the_page_reads_it():
    """Onionoo always sends a factor. A block without one is read with the relay page's default (1/999), not 1: it is
    drawn 0-100%, its mean the page's figure. A factor of 0 stays 0; a bandwidth block without one is unscaled."""
    windows = uptime_windows({"relays_published": "2026-09-30 12:00:00", "relays": []})
    bare = block([999] * 100 + [0] * 36 + [500] * 50, first="2026-08-30 14:00:00", interval=14400)
    del bare["factor"]
    drawn = uptime_points(bare, "1_month", windows)
    assert len(drawn) == 186 and min(drawn.values()) == 0.0 and max(drawn.values()) == pytest.approx(100.0)
    average, _slots = _block_uptime_percentage_and_datapoints(bare, "1_month", windows)
    assert sum(drawn.values()) / len(drawn) == pytest.approx(average)
    assert uptime_points(dict(bare, factor=None), "1_month", windows) == drawn
    assert set(uptime_points(dict(bare, factor=0), "1_month", windows).values()) == {0.0}
    bare = block([1, 2])
    del bare["factor"]
    assert points(bare, 2.0) == {T0: 2.0, T0 + timedelta(days=1): 4.0}


def test_write_read_counts_on_days_averaging_50_kb_s_both_ways():
    # The mean of write and read decides, not each direction: 90 and 20 KB/s average 55.
    kbytes = 1000 * MBIT
    assert active_ratio(90 * kbytes, 20 * kbytes) == pytest.approx(4.5)
    assert active_ratio(70 * kbytes, 20 * kbytes) is None and active_ratio(100 * kbytes, 0) is None


def test_throughput_keeps_timestamps_with_both_directions():
    ts, write, read, interval = throughput(history([1, 2, None, 4], [1, None, 3, 4]), "1_month")
    assert ts == [T0, T0 + timedelta(days=3)]
    assert write == [1000 * MBIT, 4000 * MBIT] and read == [1000 * MBIT, 4000 * MBIT]
    assert interval == DAY


def test_throughput_needs_two_points_inside_the_window():
    row = history([1, 2, 3])
    assert throughput(row, "6_months") is None
    assert throughput(row, "1_month", since=T0 + timedelta(days=2)) is None


def test_operator_throughput_sums_members_on_the_common_interval():
    bandwidth_map = {
        "A": history([1, 2]),
        "B": history([10, 20], [10, None]),
        "C": history([5, 5], interval=2 * DAY),  # outvoted interval
    }
    bandwidth_map["Z"] = {"write_history": {"1_month": {"values": [1, 2], "interval": "nope", "factor": 1000,
                                                       "first": "2026-09-01 12:00:00"}},
                          "read_history": {"1_month": {"values": [1, 2], "interval": "nope", "factor": 1000,
                                                      "first": "2026-09-01 12:00:00"}}}
    bandwidth_map["shape"] = {"write_history": "not-a-history", "read_history": {"1_month": [1, 2]}}
    members = [{"fingerprint": fp} for fp in ("A", "B", "C", "D", "Z", "shape")]
    (ts, write, read, interval), summed = operator_throughput(members, bandwidth_map, "1_month")
    # Each with the traffic it carried on the days summed (write plus read): B only on day 1.
    assert [(r["fingerprint"], round(traffic / MBIT)) for r, traffic in summed] == [("A", 6000), ("B", 20000)]
    assert ts == [T0, T0 + timedelta(days=1)] and interval == DAY
    assert [round(v / MBIT) for v in write] == [11000, 2000]  # B has no read on day 2, so it sits that day out
    assert [round(v / MBIT) for v in read] == [11000, 2000]
    assert operator_throughput(members[3:], bandwidth_map, "1_month") == (None, [])


def test_operator_throughput_fills_in_members_without_the_period_and_stops_where_all_have_reported():
    year = dict(key="1_year", interval=2 * DAY)  # 2-day slots, centred on Sep 3, 5, 7 ... 00:00 UTC
    bandwidth_map = {
        "A": history([100] * 3, first="2026-09-03 00:00:00", **year),
        # Younger than 6 months: Onionoo gives no 1-year history, its 6-month one holds it whole. Its days are
        # averaged in pairs into the 1-year slots; Sep 8 alone is not a whole slot.
        "B": history([10, 30, 10, 10, 10, 10, 99], key="6_months", first="2026-09-02 12:00:00"),
        "L": history([50] * 2, first="2026-09-03 00:00:00", **year),  # still reporting, not yet at Sep 7
        "O": history([5] * 2, first="2026-08-26 00:00:00", **year),  # stopped long before
    }
    members = [{"fingerprint": fp} for fp in "ABLO"]
    (ts, write, _read, interval), summed = operator_throughput(members, bandwidth_map, "1_year")
    assert [r["fingerprint"] for r, _traffic in summed] == list("ABLO") and interval == 2 * DAY
    # Sep 7 would sum A and B without L: the sum stops at Sep 5 instead of ending on a false drop.
    assert [(t.day, round(v / MBIT / 1000)) for t, v in zip(ts, write)] == [(26, 5), (28, 5), (3, 170), (5, 160)]
    # The network chart keeps that slot: one member a step behind must not hide the other members.
    (open_ts, open_write, _read, _interval), _summed = operator_throughput(
        members, bandwidth_map, "1_year", until_slowest=False)
    assert [(t.day, round(v / MBIT / 1000)) for t, v in zip(open_ts, open_write)][-1] == (7, 110)
    # If L is no longer running, it will not catch up: the drop on Sep 7 is real.
    members[2]["running"] = False
    (ts, write, _read, interval), summed = operator_throughput(members, bandwidth_map, "1_year")
    assert [(t.day, round(v / MBIT / 1000)) for t, v in zip(ts, write)][-2:] == [(5, 160), (7, 110)]


def test_operator_throughput_falls_through_a_non_positive_interval():
    # A zero or negative block is not a slot size. It must not hide this relay's shorter history.
    short = {"1_month": block([10, 10])}
    bandwidth_map = {
        "A": history([100, 100], key="6_months"),
        "Z": {"write_history": {"6_months": block([1, 2], interval=0), **short},
              "read_history": {"6_months": block([1, 2], interval=0), **short}},
        "N": {"write_history": {"6_months": block([1, 2], interval=-DAY), "1_month": block([5, 5])},
              "read_history": {"6_months": block([1, 2], interval=-DAY), "1_month": block([5, 5])}},
    }
    (ts, write, _read, interval), summed = operator_throughput(
        [{"fingerprint": fp} for fp in "AZN"], bandwidth_map, "6_months")
    assert [relay["fingerprint"] for relay, _traffic in summed] == list("AZN")
    assert ts == [T0, T0 + timedelta(days=1)] and interval == DAY
    assert [round(v / MBIT) for v in write] == [115000, 115000]


def test_operator_throughput_sums_only_whole_slots_of_a_shorter_history():
    # B's first day (Sep 3 noon) is half of the 2-day slot centred on Sep 3: that slot sums A alone.
    bandwidth_map = {"A": history([100] * 3, key="1_year", interval=2 * DAY, first="2026-09-03 00:00:00"),
                     "B": history([30, 10, 10, 10, 10], key="6_months", first="2026-09-03 12:00:00")}
    (ts, write, _read, _interval), _summed = operator_throughput([{"fingerprint": "A"}, {"fingerprint": "B"}],
                                                                 bandwidth_map, "1_year")
    assert [(t.day, round(v / MBIT / 1000)) for t, v in zip(ts, write)] == [(3, 100), (5, 110), (7, 110)]


def test_network_uptime_averages_the_relays_that_have_the_period():
    relays = [relay("A"), relay("B"), relay("C")]
    uptime_map = {
        "A": {"uptime": {"1_month": block([999, 999], interval=14400, factor=1 / 999.0)}},
        "B": {"uptime": {"1_month": block([0, 999], interval=14400, factor=1 / 999.0)}},
        # No 1-month block: a relay that does not count, rather than a hole treated as 0%.
    }
    ts, percent, interval, average, counts = network_uptime(relays, uptime_map, "1_month", {})
    assert ts == [T0, T0 + timedelta(hours=4)]
    assert percent == [pytest.approx(50.0), pytest.approx(100.0)]
    # Two slots: a relay chart states no average under 30, so the network chart does not either.
    assert interval == 14400 and average == 0.0 and counts == [2, 2]
    assert network_uptime(relays, uptime_map, "5_years", {}) is None
    # A different sampling interval, and one relay's extra trailing slot, do not move the mean.
    relays = [relay(str(i)) for i in range(20)]
    uptime_map = {relay["fingerprint"]: {"uptime": {"1_month": block([999, 999], interval=14400, factor=1 / 999.0)}}
                  for relay in relays}
    uptime_map["0"]["uptime"]["1_month"] = block([999, 999, 0], interval=14400, factor=1 / 999.0)
    relays.append(relay("odd"))
    uptime_map["odd"] = {"uptime": {"1_month": block([0, 0], interval=DAY, factor=1 / 999.0)}}
    ts, percent, interval, average, counts = network_uptime(relays, uptime_map, "1_month", {})
    assert ts == [T0, T0 + timedelta(hours=4)] and interval == 14400
    assert percent == [pytest.approx(100.0), pytest.approx(100.0)] and average == 0.0 and counts == [20, 20]
    # Early slots of a long period have fewer relays. They stay; only a sparse trailing slot is dropped.
    old = [relay("old1"), relay("old2")]
    young = [relay("y%d" % i) for i in range(20)]
    early = {}
    for item in old:
        early[item["fingerprint"]] = {"uptime": {"1_month": block([999] * 4, interval=14400, factor=1 / 999.0)}}
    for item in young:
        early[item["fingerprint"]] = {"uptime": {"1_month": block(
            [999, 999], interval=14400, factor=1 / 999.0, first="2026-09-01 20:00:00")}}
    ts, _percent, _interval, _average, counts = network_uptime(old + young, early, "1_month", {})
    assert [t.hour for t in ts] == [12, 16, 20, 0] and counts == [2, 2, 22, 22]
    # Thirty slots at 100% and 0%: the mean is shown. One percent or less is not, as on a relay chart.
    long_map = {"A": {"uptime": {"1_month": block([999] * 30, interval=14400, factor=1 / 999.0)}},
                "B": {"uptime": {"1_month": block([0] * 30, interval=14400, factor=1 / 999.0)}}}
    _ts, percent, _interval, average, counts = network_uptime([relay("A"), relay("B")], long_map, "1_month", {})
    assert len(percent) == 30 and percent[0] == pytest.approx(50.0) and average == pytest.approx(50.0)
    assert counts == [2] * 30
    quiet = {"A": {"uptime": {"1_month": block([0] * 30, interval=14400, factor=1 / 999.0)}}}
    _ts, percent, _interval, average, counts = network_uptime([relay("A")], quiet, "1_month", {})
    assert percent == [pytest.approx(0.0)] * 30 and average == 0.0 and counts == [1] * 30
    # A zero interval, or one that is not a number, must not become the period's sampling interval,
    # and must not drop the relays that do have one.
    bad = {"uptime": {"1_month": {"first": "2026-09-01 12:00:00", "interval": "nope", "factor": 1 / 999.0,
                                  "values": [1, 2, 3]}}}
    zero = {"uptime": {"1_month": block([0, 0], interval=0, factor=1 / 999.0)}}
    relays = [relay("good"), relay("bad"), relay("zero")]
    uptime_map = {"good": {"uptime": {"1_month": block([999, 999], interval=14400, factor=1 / 999.0)}},
                  "bad": bad, "zero": zero,
                  "shape": {"uptime": {"1_month": {"values": 5, "interval": 14400}}},
                  "text": {"uptime": "not-an-object"}}
    relays.extend((relay("shape"), relay("text")))
    ts, percent, interval, _average, counts = network_uptime(relays, uptime_map, "1_month", {})
    assert ts == [T0, T0 + timedelta(hours=4)] and interval == 14400
    assert percent == [pytest.approx(100.0), pytest.approx(100.0)] and counts == [1, 1]


def test_network_uptime_rejects_a_fractional_interval():
    relays = [relay("good"), relay("a"), relay("b")]
    uptime_map = {
        "good": {"uptime": {"1_month": block([999, 999], interval=14400, factor=1 / 999.0)}},
        # int(1.5) is 1. Two of these would outvote the 4-hour history and plot one-second samples.
        "a": {"uptime": {"1_month": block([999, 999], interval=1.5, factor=1 / 999.0)}},
        "b": {"uptime": {"1_month": block([0, 0], interval=1.5, factor=1 / 999.0)}},
    }
    ts, percent, interval, _average, counts = network_uptime(relays, uptime_map, "1_month", {})
    assert ts == [T0, T0 + timedelta(hours=4)] and interval == 14400
    assert percent == [pytest.approx(100.0), pytest.approx(100.0)] and counts == [1, 1]
    assert network_uptime([relay("a")], {"a": uptime_map["a"]}, "1_month", {}) is None
    # 14400.0 is the same number of seconds as 14400.
    whole = {"uptime": {"1_month": block([999, 999], interval=14400.0, factor=1 / 999.0)}}
    _ts, _percent, interval, _average, counts = network_uptime(
        [relay("good"), relay("whole")], {"good": uptime_map["good"], "whole": whole}, "1_month", {})
    assert interval == 14400 and counts == [2, 2]


def test_network_uptime_ignores_a_block_with_no_numeric_values():
    relays = [relay("good"), relay("words"), relay("holes"), relay("mixed")]
    uptime_map = {
        "good": {"uptime": {"1_month": block([999, 999], interval=14400, factor=1 / 999.0)}},
        # Two lists with no numbers would outvote the real 4-hour history.
        "words": {"uptime": {"1_month": block(["down", "down"], interval=DAY)}},
        "holes": {"uptime": {"1_month": block([None, None], interval=DAY)}},
        # A null beside a sample is still a history: the sample counts.
        "mixed": {"uptime": {"1_month": block([None, 999], interval=14400, factor=1 / 999.0)}},
    }
    ts, percent, interval, _average, counts = network_uptime(relays, uptime_map, "1_month", {})
    assert ts == [T0, T0 + timedelta(hours=4)] and interval == 14400
    assert percent == [pytest.approx(100.0), pytest.approx(100.0)] and counts == [1, 2]


def test_network_ratio_bands_uses_the_relay_census_cut():
    """p10/p90 of per-relay sum(write)/sum(read), dropping quiet relays and histories under three points."""
    relays = [relay(str(i)) for i in range(40)]
    bandwidth = {}
    for i, item in enumerate(relays):
        # write/read = 1 + i/100 exactly (1.00 .. 1.39), so the linear percentiles are known.
        bandwidth[item["fingerprint"]] = history([1000 + 10 * i] * 5, [1000] * 5)
    relays.append(relay("short"))
    bandwidth["short"] = history([5000] * 2, [1000] * 2)  # two points: not a census member
    relays.append(relay("quiet"))
    bandwidth["quiet"] = history([1] * 5, [1] * 5)  # under 50 KB/s
    few = []
    operator_throughput(relays[:10], bandwidth, "1_month", ratios=few)
    assert network_ratio_bands(few) is None
    ratios = []
    operator_throughput(relays, bandwidth, "1_month", ratios=ratios)
    bands = network_ratio_bands(ratios)
    assert bands["n"] == 40 and bands["role"] == "network"
    # rank = 39 * quantile / 100, between value 1 + i*0.01 and the next.
    assert bands["typical_lo"] == pytest.approx(1.039) and bands["typical_hi"] == pytest.approx(1.351)
    assert bands["invest_lo"] == pytest.approx(1.0078) and bands["invest_hi"] == pytest.approx(1.3822)
    # A native history on another interval stays in the census and out of the sum.
    odd = [relay("day"), relay("day2"), relay("wide")]
    odd_bw = {name: history([1000] * 5) for name in ("day", "day2")}
    odd_bw["wide"] = history([2000] * 4, [1000] * 4, interval=2 * DAY)
    odd_ratios = []
    _series, summed = operator_throughput(odd, odd_bw, "1_month", ratios=odd_ratios)
    assert sorted(round(ratio, 3) for ratio in odd_ratios) == [1.0, 1.0, 2.0]
    assert [relay["fingerprint"] for relay, _traffic in summed] == ["day", "day2"]


def test_family_key_is_the_effective_family_when_it_has_other_members():
    assert family_key({"effective_family": ["A", "B"]}) == ("A", "B")
    assert family_key({"effective_family": ["A"]}) is None


def test_peer_medians_by_role_and_family_skip_quiet_relays():
    relays = [relay("A", effective_family=["A", "B"]), relay("B", effective_family=["A", "B"]), relay("C"), relay("Q")]
    bandwidth_map = {
        "A": history([110, 120, 150], [100, 100, 100]),  # alone on the third day
        "B": history([130, 140], [100, 100]),
        "C": history([100, 100]),
        "Q": history([1, 1], [2, 2]),  # under MIN_ACTIVE_MBIT: not a peer
    }
    roles, families = peer_medians(relays, bandwidth_map)
    assert set(roles) == {"Guard"}
    assert roles["Guard"][T0] == pytest.approx(1.1)  # median of 1.1, 1.3, 1.0
    assert families == {}  # a family of two: its median is the mean of A and B, half made of each
    # Effective families are mutual declarations, so they can differ by member: A's family is A, B and C even
    # though C does not list B. Its median is over those members, not over the relays listing the same set.
    relays[:3] = [relay("A", effective_family=["A", "B", "C"]), relay("B", effective_family=["A", "B"]),
                  relay("C", effective_family=["A", "C"])]
    _roles, families = peer_medians(relays, bandwidth_map)  # on days with 3 members, as for the family as a whole
    assert families == {("A", "B", "C"): (3, pytest.approx({T0: 1.1, T0 + timedelta(days=1): 1.2}))}
