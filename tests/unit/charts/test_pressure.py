"""Pressure charts use the period switcher and the frozen usual-range legend."""

from datetime import datetime, timedelta, timezone

from allium.lib.charts.pressure import directory_chart, guard_chart, overload_chart


def _document():
    document = {"days": {}, "bands": {
        "overload": {"p10": 0.3, "p90": 1.9, "n": 300},
        "guard": {"p10": 5384, "p90": 6336, "n": 300},
        "hsdir": {"p10": 4372, "p90": 5878, "n": 300},
        "directory": {"p10": 2.9, "p90": 11.8, "n": 300},
        "frozen": True,
    }}
    day = datetime(2026, 11, 1, tzinfo=timezone.utc).date()
    for offset in range(10):
        current = day + timedelta(days=offset)
        document["days"][current.isoformat()] = {
            "overload_share": 1.0 if offset < 8 else 15.3,
            "overload_sealed": True,
            "guard": 6000 if offset < 8 else 3000,
            "hsdir": 5000,
            "running": 9000,
            "flags_ok": True,
            "directory": 4.0 if offset < 8 else 50.0,
            "directory_sealed": True,
        }
    return document


def test_overload_chart_names_the_percentile_band_and_has_no_release_mark():
    svg = overload_chart(_document(), "1m")
    text = svg.document()
    assert "Usual range (p10–p90)" in text
    assert "0.3%–1.9%" in text
    assert "onset" not in text
    assert "0.4.9" not in text
    assert "High since" in text


def test_guard_chart_marks_both_sides_of_the_usual_range():
    text = guard_chart(_document(), "1m").document()
    assert "Outside usual range" in text
    assert "#ff6b6b" in text


def test_earlier_series_names_its_last_day():
    document = _document()
    for key, row in document["days"].items():
        row["overload_publishers"] = 9000
    document["days"]["2026-11-10"]["guard"] = None
    text = guard_chart(document, "1m").document()
    assert "through Nov 9" in text


def test_directory_chart_says_bytes_served():
    text = directory_chart(_document(), "1m").document()
    assert "Directory bytes served" in text
    assert "Usual range (p10–p90)" in text
    assert "2.9–11.8" in text
    assert "onset" not in text
