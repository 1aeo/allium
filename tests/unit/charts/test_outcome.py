"""Locked C outcome subtitles: spiked / dropped / inside / outside / empty."""

from datetime import datetime, timedelta, timezone

from allium.lib.charts.bands import bands_for_flags
from allium.lib.charts.outcome import (
    format_day_span,
    format_outcome_subtitle,
    is_all_clear,
    summarize_bandwidth_outcome,
)


def _days(n=10, start=None):
    start = start or datetime(2026, 7, 16, 12, tzinfo=timezone.utc)
    return [start + timedelta(days=i) for i in range(n)]


def _typical_guard_series(n=10):
    """Write/read near 1.04, well inside Guard typical 1.01–1.17."""
    ts = _days(n)
    write = [100.0] * n
    read = [96.0] * n
    return ts, write, read


def test_format_day_span_consecutive_and_single():
    ts = _days(2, datetime(2026, 7, 22, 12, tzinfo=timezone.utc))
    assert format_day_span([ts[0].date()]) == "22 Jul"
    assert format_day_span([t.date() for t in ts]) == "22–23 Jul"


def test_all_clear_subtitles_are_empty():
    ts, write, read = _typical_guard_series()
    bands = bands_for_flags(["Guard"])
    outcome = summarize_bandwidth_outcome(
        ts, write, read, 200.0, [], {}, bands, None,
    )
    assert is_all_clear(outcome)
    assert format_outcome_subtitle(outcome, "throughput") == ""
    assert format_outcome_subtitle(outcome, "ratio") == ""


def test_write_spiked_includes_dates():
    ts = _days(8)
    write = [80.0] * 8
    read = [76.0] * 8
    # Two investigate days: write/read well above Guard invest_hi 1.58
    write[6] = 400.0
    write[7] = 350.0
    read[6] = 80.0
    read[7] = 80.0
    bands = bands_for_flags(["Guard"])
    outcome = summarize_bandwidth_outcome(
        ts, write, read, 650.0, [], {}, bands, None,
    )
    thru = format_outcome_subtitle(outcome, "throughput")
    ratio = format_outcome_subtitle(outcome, "ratio")
    assert thru.startswith("Write spiked")
    assert "22–23 Jul" in thru
    assert "Mbit/s" in thru
    assert "of advertised" in thru
    assert "Outside the Guard band" in ratio
    assert "22–23 Jul" in ratio
    assert "family and peers stayed" in ratio


def test_both_dropped_includes_dates():
    ts = _days(6)
    write = [5.0] * 6
    read = [5.0] * 6
    bands = bands_for_flags(["Guard"])
    outcome = summarize_bandwidth_outcome(
        ts, write, read, 200.0, [], {}, bands, None,
    )
    thru = format_outcome_subtitle(outcome, "throughput")
    assert thru.startswith("Write and read both dropped")
    assert "Mbit/s" in thru


def test_uncommon_inside_has_no_forced_date():
    """Mean in uncommon, no investigate day — inside-the-band copy, no date."""
    ts = _days(10)
    # Guard typical 1.01–1.17, uncommon up to 1.58. Mean ~1.30.
    write = [130.0] * 10
    read = [100.0] * 10
    bands = bands_for_flags(["Guard"])
    outcome = summarize_bandwidth_outcome(
        ts, write, read, 200.0, [], {}, bands, None,
    )
    assert outcome["zone"] == "uncommon"
    assert not outcome["invest"]
    ratio = format_outcome_subtitle(outcome, "ratio")
    assert "inside the Guard band" in ratio
    assert "Jul" not in ratio


def test_thin_history_is_empty():
    ts, write, read = _typical_guard_series(n=2)
    bands = bands_for_flags(["Guard"])
    outcome = summarize_bandwidth_outcome(
        ts, write, read, 200.0, [], {}, bands, None,
    )
    assert outcome["enough"] is False
    assert format_outcome_subtitle(outcome, "throughput") == ""
    assert format_outcome_subtitle(outcome, "ratio") == ""
