"""Pressure charts use the period switcher and the frozen usual-range legend."""

from datetime import datetime, timedelta, timezone

from allium.lib.charts.pressure import directory_chart, guard_chart, hsdir_chart, overload_chart
from allium.lib.charts.svg import GREEN, ORANGE, RED
from allium.lib.pressure_history import latest_value, series_latest


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
    assert "Inside usual range (p10–p90)" in text and "0.3%–1.9%" in text
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
    # Inside the usual range, the series and its legend swatch use the same green as the other three charts.
    assert 'stroke="#00ff7f" stroke-width="1.8"' in text
    assert 'stroke="#00ff7f" stroke-width="2.2"' in text
    assert 'stroke="#4da6ff"' not in text
    overload = overload_chart(_document(), "1m").document()
    assert "Relays Reporting Overload" in overload and "Tor network" not in overload
    assert 'stroke="#00ff7f"' in overload
    assert 'stroke="#00ff7f"' in guard_chart(_document(), "1m").document()
    assert 'stroke="#00ff7f"' in directory_chart(_document(), "1m").document()
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
    assert "May 2025–May 2026" in text and "median of up to 28 earlier readings" in text


def test_the_usual_range_edges_stay_inside_and_zero_is_outside():
    """p10 and p90 are still inside. Zero is under the range, so the lower redraw includes it."""
    red = 'stroke="#ff6b6b" stroke-width="2.4"'
    inside = 'stroke="#00ff7f" stroke-width="1.8"'
    for value in (4372, 5878):
        text = hsdir_chart(_flat("hsdir", value), "1m").document()
        assert red not in text
        assert inside in text
        assert 'stroke="#4da6ff"' not in text
    zero = hsdir_chart(_flat("hsdir", 0), "1m").document()
    assert red in zero
    assert inside in zero


def _dot_color(svg):
    for op in reversed(svg.ops):
        if op[0] == "path" and op[5] not in (None, "none"):
            return op[2]
    return None


def _series_colors(svg):
    return {op[2] for op in svg.ops if op[0] == "path" and op[5] in (None, "none")}


def test_overload_marker_matches_the_stroke_it_sits_on():
    """The trailing dot uses the same color as the band redraw, including exactly 10%."""
    orange = overload_chart(_flat("overload_share", 5), "1m")
    ceiling = overload_chart(_flat("overload_share", 10), "1m")
    above = overload_chart(_flat("overload_share", 10.1), "1m")
    assert _dot_color(orange) == ORANGE and ORANGE in _series_colors(orange)
    assert _dot_color(ceiling) == ORANGE and RED not in _series_colors(ceiling)
    assert _dot_color(above) == RED and RED in _series_colors(above)


def test_a_usual_range_past_10_percent_stays_green_inside_it():
    """p90 above 10% is still inside. The orange 'up to 10%' band is not drawn over it."""
    document = _flat("overload_share", 11)
    document["bands"]["overload"] = {"p10": 8.0, "p90": 12.0, "n": 300}
    svg = overload_chart(document, "1m")
    text = svg.document()
    assert _dot_color(svg) == GREEN
    assert RED not in _series_colors(svg) and ORANGE not in _series_colors(svg)
    assert "Inside usual range (p10–p90)" in text and "8.0%–12.0%" in text
    assert "Up to 10% outside usual range" not in text
    assert "More than 10% outside usual range" in text


def test_directory_without_a_band_does_not_invent_an_outside_color():
    document = _document()
    document["bands"].pop("directory")
    svg = directory_chart(document, "1m")
    text = svg.document()
    assert "Above usual range" not in text and "Inside usual range" not in text
    assert "Daily average" in text
    assert RED not in _series_colors(svg) and _dot_color(svg) == GREEN


def test_shared_latest_matches_each_series_and_skips_a_partial_tail():
    document = _document()
    for row in document["days"].values():
        row["overload_publishers"] = 9000
    document["days"]["2026-11-10"]["overload_publishers"] = 100
    document["days"]["2026-11-10"]["overload_share"] = 50
    document["days"]["2026-11-10"]["flags_ok"] = False
    document["days"]["2026-11-10"]["guard"] = 100
    newest, latest, partial = series_latest(document)
    assert datetime(2026, 11, 10).date() in partial
    assert latest["overload_share"] == latest_value(document, "overload_share")
    assert latest["guard"] == latest_value(document, "guard", True)
    assert latest["hsdir"] == latest_value(document, "hsdir", True)
    assert latest["directory"] == latest_value(document, "directory")
    assert newest == latest["directory"][0]
    assert "through Nov 9" in guard_chart(document, "1m").document()
    assert "50.0%" not in overload_chart(document, "1m").document()


def test_latest_dot_stays_series_color_unless_both_band_edges_exist():
    """A value outside one edge is not a hot marker until p10 and p90 both exist."""
    low = _flat("guard", 3000)
    low["bands"]["guard"] = {"p10": 5384}
    one_edge = guard_chart(low, "1m")
    assert "Daily average" in one_edge.document()
    assert "Outside usual range" not in one_edge.document()
    assert RED not in _series_colors(one_edge)
    assert _dot_color(one_edge) == GREEN

    low["bands"]["guard"]["p90"] = 6336
    assert _dot_color(guard_chart(low, "1m")) == RED
    assert _dot_color(guard_chart(_flat("guard", 7000), "1m")) == RED

    high = _flat("directory", 50)
    high["bands"]["directory"] = {"p10": 2.9}
    assert "Daily average" in directory_chart(high, "1m").document()
    assert _dot_color(directory_chart(high, "1m")) == GREEN
    high["bands"]["directory"] = {"p90": 11.8}
    assert _dot_color(directory_chart(high, "1m")) == GREEN
    high["bands"]["directory"] = {"p10": 2.9, "p90": 11.8}
    assert _dot_color(directory_chart(high, "1m")) == RED


def test_directory_chart_says_bytes_served():
    text = directory_chart(_document(), "1m").document()
    assert "Directory Bytes Served" in text
    assert "Inside usual range (p10–p90)" in text and "2.9–11.8" in text
    assert "Above usual range" in text
    assert "2.9–11.8" in text
    assert "onset" not in text
