"""Pressure charts use the period switcher and the frozen usual-range legend."""

from datetime import datetime, timedelta, timezone

from allium.lib.charts.pressure import directory_chart, guard_chart, hsdir_chart, overload_chart


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
    assert "Relays Reporting Overload" in text
    assert "Inside usual range" in text and "0.3%–1.9%" in text
    assert "Up to 10% outside usual range" in text
    assert "More than 10% outside usual range" in text
    assert "Pressure, not a cause" not in text
    assert "onset" not in text
    assert "0.4.9" not in text
    assert "High since" in text


def test_guard_chart_marks_both_sides_of_the_usual_range():
    text = guard_chart(_document(), "1m").document()
    assert "Relays with Guard Flag" in text
    assert "Outside usual range" in text
    assert "#ff6b6b" in text


def test_earlier_series_names_its_last_day():
    document = _document()
    for key, row in document["days"].items():
        row["overload_publishers"] = 9000
    document["days"]["2026-11-10"]["guard"] = None
    text = guard_chart(document, "1m").document()
    assert "through Nov 9" in text


def _flat(field, value):
    document = _document()
    for row in document["days"].values():
        row[field] = value
    return document


def test_hsdir_chart_marks_both_sides_of_the_usual_range():
    document = _document()
    document["days"]["2026-11-10"]["hsdir"] = 1000  # below the frozen p10, so the line is redrawn in red
    text = hsdir_chart(document, "1m").document()
    assert "Relays with HSDir Flag" in text
    assert "Outside usual range" in text
    assert 'stroke="#ff6b6b" stroke-width="2.4"' in text
    overload = overload_chart(_document(), "1m").document()
    assert "Relays Reporting Overload" in overload and "Tor network" not in overload
    assert "quiet-year" not in text


def test_hsdir_subtitle_names_the_baseline_in_plain_language():
    document = {"days": {}, "bands": {"hsdir": {"p10": 4372, "p90": 5878, "n": 300}}}
    start = datetime(2025, 6, 1, tzinfo=timezone.utc).date()
    for offset in range(40):
        document["days"][(start + timedelta(days=offset)).isoformat()] = {
            "hsdir": 5000 if offset < 30 else 2000, "flags_ok": True,
        }
    text = hsdir_chart(document, "1m").document()
    assert "quiet-year" not in text
    assert "May 2025–May 2026" in text and "previous 28 readings" in text


def test_the_usual_range_edges_stay_inside_and_zero_is_outside():
    """p10 and p90 are still inside. Zero is under the range, so the lower redraw includes it."""
    red = 'stroke="#ff6b6b" stroke-width="2.4"'
    assert red not in hsdir_chart(_flat("hsdir", 4372), "1m").document()
    assert red not in hsdir_chart(_flat("hsdir", 5878), "1m").document()
    assert red in hsdir_chart(_flat("hsdir", 0), "1m").document()


def test_directory_chart_says_bytes_served():
    text = directory_chart(_document(), "1m").document()
    assert "Directory Bytes Served" in text
    assert "Usual range (p10–p90)" in text
    assert "2.9–11.8" in text
    assert "onset" not in text
