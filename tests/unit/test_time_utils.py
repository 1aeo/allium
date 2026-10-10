"""Onionoo timestamp helpers shared by charts and bandwidth callers."""

from datetime import datetime, timezone

from allium.lib.time_utils import parse_onionoo_timestamp, published_clock


def test_parse_onionoo_timestamp_string_and_datetime():
    expected = datetime(2026, 8, 15, 6, 0, tzinfo=timezone.utc)
    assert parse_onionoo_timestamp("2026-08-15 06:00:00") == expected
    naive = datetime(2026, 8, 15, 6, 0)
    assert parse_onionoo_timestamp(naive) == expected
    assert parse_onionoo_timestamp(expected) is expected
    assert parse_onionoo_timestamp("") is None
    assert parse_onionoo_timestamp("not-a-date") is None
    assert parse_onionoo_timestamp(None) is None


def test_published_clock_parses_onionoo_and_numbers():
    assert published_clock("") is None
    assert published_clock("not-a-date") is None
    assert published_clock(True) is None
    ts = published_clock("2026-08-15 06:00:00")
    assert ts == datetime(2026, 8, 15, 6, 0, tzinfo=timezone.utc).timestamp()
    assert published_clock(ts) == ts
