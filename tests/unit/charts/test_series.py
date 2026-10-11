"""Onionoo history parsing, operator sums and peer medians for the charts."""

from datetime import timedelta

import pytest

from allium.lib.charts.series import (
    MBIT, family_key, operator_throughput, peer_medians, points, throughput,
)

from .fixtures import DAY, T0, block, history, relay


def test_points_scale_by_factor_skip_holes_and_clip_to_window():
    assert points(block([1, None, 3]), 2.0) == {T0: 2000.0, T0 + timedelta(days=2): 6000.0}
    assert points(block([1, 2, 3]), since=T0 + timedelta(days=1)) == {
        T0 + timedelta(days=1): 2000.0, T0 + timedelta(days=2): 3000.0}
    assert points(None) == {} and points(block([1], first="bad")) == {}


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
    members = [{"fingerprint": fp} for fp in ("A", "B", "C", "D")]
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


def test_family_key_is_the_effective_family_when_it_has_other_members():
    assert family_key({"effective_family": ["A", "B"]}) == ("A", "B")
    assert family_key({"effective_family": ["A"]}) is None


def test_peer_medians_by_role_and_family_skip_quiet_relays():
    relays = [relay("A", effective_family=["A", "B"]), relay("B", effective_family=["A", "B"]), relay("C"), relay("Q")]
    bandwidth_map = {
        "A": history([110, 120, 150], [100, 100, 100]),  # alone on the third day
        "B": history([130, 140], [100, 100]),
        "C": history([100, 100]),
        "Q": history([1, 1], [2, 2]),  # under MIN_OVERLAY_MBIT: not a peer
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
