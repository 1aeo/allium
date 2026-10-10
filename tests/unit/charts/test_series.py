"""Onionoo history parsing, operator sums and peer medians for the charts."""

from datetime import datetime, timedelta, timezone

import pytest

from allium.lib.charts.series import (
    MBIT, family_key, operator_throughput, peer_medians, points, throughput,
)

DAY = 86400
T0 = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)


def block(values, first="2026-09-01 12:00:00", interval=DAY, factor=1000.0):
    return {"first": first, "interval": interval, "factor": factor, "values": list(values)}


def bandwidth_row(write, read, key="1_month", **kwargs):
    return {"write_history": {key: block(write, **kwargs)}, "read_history": {key: block(read, **kwargs)}}


def test_points_scale_by_factor_skip_holes_and_clip_to_window():
    assert points(block([1, None, 3]), 2.0) == {T0: 2000.0, T0 + timedelta(days=2): 6000.0}
    assert points(block([1, 2, 3]), since=T0 + timedelta(days=1)) == {
        T0 + timedelta(days=1): 2000.0, T0 + timedelta(days=2): 3000.0}
    assert points(None) == {} and points(block([1], first="bad")) == {}


def test_throughput_keeps_timestamps_with_both_directions():
    ts, write, read, interval = throughput(bandwidth_row([1, 2, None, 4], [1, None, 3, 4]), "1_month")
    assert ts == [T0, T0 + timedelta(days=3)]
    assert write == [1000 * MBIT, 4000 * MBIT] and read == [1000 * MBIT, 4000 * MBIT]
    assert interval == DAY


def test_throughput_needs_two_points_inside_the_window():
    row = bandwidth_row([1, 2, 3], [1, 2, 3])
    assert throughput(row, "6_months") is None
    assert throughput(row, "1_month", since=T0 + timedelta(days=2)) is None


def test_operator_throughput_sums_members_on_the_common_interval():
    bandwidth_map = {
        "A": bandwidth_row([1, 2], [1, 2]),
        "B": bandwidth_row([10, 20], [10, None]),
        "C": bandwidth_row([5, 5], [5, 5], interval=2 * DAY),  # outvoted interval
    }
    members = [{"fingerprint": fp} for fp in ("A", "B", "C", "D")]
    (ts, write, read, interval), summed = operator_throughput(members, bandwidth_map, "1_month")
    assert [r["fingerprint"] for r in summed] == ["A", "B"]
    assert ts == [T0, T0 + timedelta(days=1)] and interval == DAY
    assert [round(v / MBIT) for v in write] == [11000, 22000]
    assert [round(v / MBIT) for v in read] == [11000, 2000]
    assert operator_throughput(members[3:], bandwidth_map, "1_month") == (None, [])


def test_family_key_is_the_effective_family_when_it_has_other_members():
    assert family_key({"effective_family": ["A", "B"]}) == ("A", "B")
    assert family_key({"effective_family": ["A"]}) is None


def test_peer_medians_by_role_and_family_skip_quiet_relays():
    def relay(fp, flags, family):
        return {"fingerprint": fp, "flags": flags, "effective_family": family}

    relays = [relay("A", ["Guard"], ["A", "B"]), relay("B", ["Guard"], ["A", "B"]),
              relay("C", ["Guard"], ["C"]), relay("Q", ["Guard"], ["Q"])]
    bandwidth_map = {
        "A": bandwidth_row([110, 120], [100, 100]),
        "B": bandwidth_row([130, 140], [100, 100]),
        "C": bandwidth_row([100, 100], [100, 100]),
        "Q": bandwidth_row([1, 1], [2, 2]),  # under MIN_OVERLAY_MBIT: not a peer
    }
    roles, families = peer_medians(relays, bandwidth_map)
    assert set(roles) == {"Guard"}
    assert roles["Guard"][T0] == pytest.approx(1.1)  # median of 1.1, 1.3, 1.0
    assert families == {("A", "B"): (2, pytest.approx({T0: 1.2, T0 + timedelta(days=1): 1.3}))}
