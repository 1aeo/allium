"""SVG history charts: drawing helpers and the relay / operator chart writer."""

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from allium.lib.charts.bands import bands_for_role
from allium.lib.charts.render import LEFT, PLOT_WIDTH, bandwidth_chart, uptime_chart
from allium.lib.charts.svg import BLUE, CALLOUT_BG, GREEN, RED, TEXT, Panel, Svg, date_ticks, nice_ticks, text_width

from .fixtures import DAY, OVERLOADED, SPIKE, T0, decode, history, needs_png, relay, writer


def texts(path):
    """The chart's text lines (double spaces are written as no-break spaces)."""
    return [t.text.replace("\xa0", " ") for t in ET.parse(path).iter("{http://www.w3.org/2000/svg}text")]


def height(path):
    return int(ET.parse(path).getroot().get("height"))


def test_relay_charts_carry_identity_title_legend_and_footnote(tmp_path):
    charts = writer([relay("A")], {"A": history([100 + i for i in range(30)])}, {"A": [999] * 180})
    # Each drawn period comes with its chart's height, so the page can reserve the image's box.
    assert charts.relay(relay("A"), str(tmp_path)) == ({"1m": height(tmp_path / "bandwidth-1m.svg")},
                                                       {"1m": height(tmp_path / "uptime-1m.svg")})
    assert sorted(os.listdir(tmp_path)) == ["bandwidth-1m.svg", "uptime-1m.svg"]
    lines = texts(tmp_path / "bandwidth-1m.svg")
    for line in ("relayA  ·  example.com", "Throughput · last 30 days  ·  Guard", "Write (outbound)",
                 "Advertised  2 Mbit/s", "Last restarted  Sep 10", "Write / read · last 30 days  ·  Guard",
                 "This relay", "Typical  1.01–1.17  ·  p10–p90", "Sep 8", "4,444 Guards · baseline 15 Aug 2026"):
        assert line in lines
    assert "Outside p2–p98" not in lines  # nothing red to explain
    assert "Average 100.0%  ·  Onionoo Running flag" in texts(tmp_path / "uptime-1m.svg")


def test_an_unnamed_relays_charts_name_its_fingerprint(tmp_path):
    """An Unnamed relay's bandwidth and uptime charts give its fingerprint's first 8 digits before its url host, and
    the line fits the plot."""
    fp = "0123ABCD" + "F" * 32
    unnamed = relay(fp, nickname="Unnamed", contact="url:https://tor-relays.example-operator-collective.org")
    writer([unnamed], {fp: history([100] * 30)}, {fp: [999] * 180}).relay(unnamed, str(tmp_path))
    for name in ("bandwidth-1m.svg", "uptime-1m.svg"):
        line = texts(tmp_path / name)[0]
        assert line == "Unnamed · 0123ABCD…  ·  tor-relays.example-operator-collective.org"
        assert text_width(line, 15, bold=True) <= PLOT_WIDTH


def test_uptime_chart_of_a_stopped_history_shows_the_pages_average(tmp_path):
    # 150 slots from the window's start, then the relay went offline: Onionoo counts the last 36 slots as down
    charts = writer([relay("A")], {"A": history([100 + i for i in range(30)])}, {"A": [999] * 150},
                    uptime_first="2026-08-30 14:00:00")
    charts.relay(relay("A"), str(tmp_path))
    assert "Average 80.6%  ·  Onionoo Running flag" in texts(tmp_path / "uptime-1m.svg")  # 150 of 186 slots


@needs_png
def test_png_charts_are_drawn_at_twice_their_size_and_reused_from_the_cache(tmp_path):
    first, second, third, root = (tmp_path / name for name in ("first", "second", "third", "cache"))
    for directory in (first, second, third):
        directory.mkdir()
    (root / "0123456789abcdef").mkdir(parents=True)  # cached by another drawing version: never hit again
    (root / "notes").mkdir()  # not a drawing version: left alone
    history_a = {"A": history([100 + i for i in range(30)])}
    charts = writer([relay("A")], history_a, {"A": [999] * 180}, "png", str(root))
    assert sorted(os.listdir(root)) == sorted([os.path.basename(charts.cache), "notes"])
    bandwidth, uptime = charts.relay(relay("A"), str(first))
    assert sorted(os.listdir(first)) == ["bandwidth-1m.png", "uptime-1m.png"]
    # Twice the page's size, sharp on HiDPI screens, in the 64-color palette (3 channels once decoded).
    assert decode((first / "bandwidth-1m.png").read_bytes()).shape == (2 * bandwidth["1m"], 2160, 3)
    # The next build links charts that did not change instead of drawing them again, and keeps their
    # modification time so rsync and HTTP caches see them unchanged.
    os.utime(first / "bandwidth-1m.png", (1, 1))
    charts = writer([relay("A")], history_a, {"A": [999] * 180}, "png", str(root))
    charts.raster = SimpleNamespace(png=lambda *args: 1 / 0)
    assert charts.relay(relay("A"), str(second)) == (bandwidth, uptime)
    hit = os.stat(second / "bandwidth-1m.png")
    assert hit.st_ino == os.stat(first / "bandwidth-1m.png").st_ino and hit.st_mtime == 1
    assert hit.st_atime >= charts.started - 60  # marked as used, so sweep() keeps it
    # A page written again in place (the sequential retry after a worker died) replaces its links:
    # a different chart there must not be written through the old link into the cache.
    changed = writer([relay("A")], {"A": history([200 + i for i in range(30)])}, {"A": [500] * 180}, "png", str(root))
    cache = root / os.path.basename(changed.cache)
    before = {path: path.read_bytes() for path in cache.iterdir()}
    assert list(changed.relay(relay("A"), str(second))[0]) == ["1m"]
    assert all(path.read_bytes() == data for path, data in before.items())
    # sweep() keeps what this build used and drops the rest; an SVG build uses none of it.
    stale = cache / "stale.png"
    stale.touch()
    os.utime(stale, (0, 0))
    changed.sweep()
    assert len(os.listdir(cache)) == 4 and not stale.exists()
    # --chart-scale 1.5 draws 1620 px wide and --chart-colors full writes RGBA. Each option is part of each
    # file's key: neither reuses the 2x, 64-color PNG of this drawing cached above.
    for scale, colors, width, channels in ((1.5, "64", 1620, 3), (2, "full", 2160, 4)):
        options = writer([relay("A")], history_a, {"A": [999] * 180}, "png", str(root), scale=scale, colors=colors)
        bandwidth, _uptime = options.relay(relay("A"), str(third))
        assert decode((third / "bandwidth-1m.png").read_bytes()).shape == (
            round(scale * bandwidth["1m"]), width, channels)
    writer([relay("A")], history_a, cache_dir=str(root)).sweep()
    assert os.listdir(root) == ["notes"]


@needs_png
def test_a_png_is_drawn_from_its_own_drawing_not_one_with_the_same_svg_text(tmp_path):
    """The SVG text rounds to 0.1 px and the PNG is drawn at full precision: two charts whose text matches
    (e.g. restarts minutes apart on a 1Y chart) must not share a cached PNG, or builds vary."""
    charts = writer([], {}, image_format="png", cache_dir=str(tmp_path / "cache"))
    for y in (60.01, 60.04):  # both written as y2="60.0"
        svg = Svg(100)
        svg.line(10, 20, 90, y, GREEN, 4)
        charts._save(str(tmp_path), "chart-%g" % y, svg.finish, 100)
        assert (tmp_path / ("chart-%g.png" % y)).read_bytes() == charts.raster.png(svg)


def test_a_failed_png_conversion_is_reported_not_silent(tmp_path, caplog):
    out, cache = tmp_path / "out", tmp_path / "cache"
    out.mkdir()
    cache.mkdir()
    charts = writer([relay("A")], {"A": history([100] * 30)})
    charts.ext, charts.cache = "png", str(cache)
    charts.raster = SimpleNamespace(png=lambda *args: 1 / 0)  # e.g. a broken cairo on the build host
    assert charts.relay(relay("A"), str(out)) == ({}, {})
    assert os.listdir(out) == os.listdir(cache) == [] and "bandwidth-1m.png: division by zero" in caplog.text


def test_each_period_only_shows_its_own_window(tmp_path):
    stale = history([100] * 30, first="2026-06-01 12:00:00")  # 1M stopped updating months ago
    longer = history([100] * 60, key="6_months", first="2026-08-01 12:00:00")
    charts = writer([relay("A")], {"A": {k: dict(stale[k], **longer[k]) for k in stale}})
    assert [list(drawn) for drawn in charts.relay(relay("A"), str(tmp_path))] == [["6m"], []]
    assert os.listdir(tmp_path) == ["bandwidth-6m.svg"]


def test_a_history_that_stopped_leaves_a_gap_up_to_the_window_end(tmp_path):
    # An offline relay: 20 days of history, then nothing until relays_published (Sep 30), and a restart in the gap.
    offline = relay("A", last_restarted="2026-09-25 08:00:00", running=False, last_seen="2026-09-21 11:00:00")
    charts = writer([offline], {"A": history([100] * 20)}, {"A": [999] * 120}, uptime_first="2026-09-01 14:00:00")
    charts.relay(offline, str(tmp_path))
    for name in ("bandwidth-1m.svg", "uptime-1m.svg"):
        lines = texts(tmp_path / name)
        assert "Sep 29" in lines and "Last restarted  Sep 25" in lines
    # Its uptime chart draws the 54 slots of Onionoo's window after its last one at 0%, as Onionoo counts them,
    # and the page's figure for them: 120 of 174 slots up.
    assert "Average 69.0%  ·  Onionoo Running flag" in texts(tmp_path / "uptime-1m.svg")
    # A running relay's history only lags behind Onionoo by a day or two: its axis ends just past it, no gap. One
    # that ended over two slots and a day before relays_published (4 days, not 3) is a stale block: the gap shows,
    # as for a relay no longer running.
    for days, gap in ((27, False), (26, True)):
        charts = writer([relay("A")], {"A": history([100] * days)})
        charts.relay(relay("A"), str(tmp_path))
        write = [p.get("d") for p in ET.parse(tmp_path / "bandwidth-1m.svg").iter("{http://www.w3.org/2000/svg}path")
                 if p.get("stroke") == GREEN]
        last = max(float(x) for d in write for x in re.findall(r"[ML]([\d.]+) ", d))
        assert (last < LEFT + PLOT_WIDTH * 0.95) is gap
    # The bandwidth window and a stopped relay's axis follow the bandwidth document, not the uptime one's publish time.
    offline = relay("A", running=False)
    charts = writer([offline], {"A": history([100] * 20)}, uptime_published="2026-09-26 12:00:00")
    charts.relay(offline, str(tmp_path))
    assert "Sep 29" in texts(tmp_path / "bandwidth-1m.svg")
    # An operator's axis runs on only when every member stopped.
    for running, gap in ((False, True), (None, False)):
        members = [relay("A", running=False), relay("B", running=running)]
        charts = writer(members, {"A": history([100] * 28), "B": history([100] * 28)})
        charts.contact([0, 1], str(tmp_path))
        write = [p.get("d") for p in ET.parse(tmp_path / "bandwidth-1m.svg").iter("{http://www.w3.org/2000/svg}path")
                 if p.get("stroke") == GREEN]
        assert (max(float(x) for d in write for x in re.findall(r"[ML]([\d.]+) ", d)) < LEFT + PLOT_WIDTH * 0.95) is gap


def test_uptime_charts_use_the_uptime_documents_own_window(tmp_path):
    # Uptime from Aug 25: down until Aug 29 12:00, then up. Its document was published Sep 26 (bandwidth: Sep 30),
    # so Onionoo's 1-month window starts Aug 26 12:00: the chart draws its 186 slots, 18 of them down.
    charts = writer([relay("A")], {"A": history([100] * 30)}, {"A": [0] * 24 + [999] * 168},
                    uptime_published="2026-09-26 12:00:00", uptime_first="2026-08-25 14:00:00")
    charts.relay(relay("A"), str(tmp_path))
    assert "Average 90.3%  ·  Onionoo Running flag" in texts(tmp_path / "uptime-1m.svg")
    line = [path.get("d") for path in ET.parse(tmp_path / "uptime-1m.svg").iter("{http://www.w3.org/2000/svg}path")
            if path.get("stroke") == GREEN and path.get("stroke-width") == "2.2"]
    assert len(line) == 1 and len(re.findall(r"[ML]", line[0])) == 186


def test_a_short_uptime_history_is_drawn_without_the_pages_figure(tmp_path):
    # Under 30 slots the page shows no uptime figure, so the chart has no "Average"; one slot is no history.
    for slots, drawn in ((10, True), (1, False)):
        a = relay("A")
        charts = writer([a], {"A": history([100] * 30)}, {"A": [999] * slots}, uptime_first="2026-09-29 14:00:00")
        assert ("1m" in charts.relay(a, str(tmp_path))[1]) is drawn
        if drawn:
            assert not any(text.startswith("Average") for text in texts(tmp_path / "uptime-1m.svg"))


def test_days_under_50_kb_s_leave_the_write_read_strip(tmp_path):
    # Days 10-19 carry 5 KB/s each way: a write/read of 3 there is noise, not out of band.
    write, read = [110] * 30, [100] * 30
    write[10:20], read[10:20] = [15] * 10, [5] * 10
    charts = writer([relay("A"), relay("B")], {"A": history(write, read), "B": history([5] * 30)})
    charts.relay(relay("A"), str(tmp_path))
    lines = texts(tmp_path / "bandwidth-1m.svg")
    assert "Write/read 1.10 overall (typical) · inside p2–p98 throughout" in lines
    strip = [p.get("d") for p in ET.parse(tmp_path / "bandwidth-1m.svg").iter("{http://www.w3.org/2000/svg}path")
             if (p.get("stroke"), p.get("stroke-width")) == (TEXT, "2.2")]
    assert len(strip) == 1 and strip[0].count("M") == 2  # the relay's line breaks over them
    charts.relay(relay("B"), str(tmp_path))
    lines = texts(tmp_path / "bandwidth-1m.svg")
    assert "Under 50 KB/s throughout: too little traffic to compare" in lines
    assert not {"This relay", "Peers (network median)"} & set(lines)  # nothing of its own to set them against


def test_family_and_peer_medians_are_drawn_on_1m_only(tmp_path):
    family = ["A", "B", "C"]
    month, longer = history([100 + i for i in range(30)], [100] * 30), history([100] * 60, key="6_months")
    charts = writer([relay(fp, effective_family=family) for fp in family],
                    {fp: {k: dict(month[k], **longer[k]) for k in month} for fp in family})
    charts.relay(relay("A", effective_family=family), str(tmp_path))
    assert {"Operator Family (median, n=3)", "Peers (network median)"} <= set(texts(tmp_path / "bandwidth-1m.svg"))
    assert not {"Operator Family (median, n=3)", "Peers (network median)"} & set(texts(tmp_path / "bandwidth-6m.svg"))


def test_out_of_band_days_are_red_and_one_alone_gets_a_dot():
    # Guard's p2–p98 is 0.99–1.58: day 10 (1.65) leaves it alone, days 20 and 21 together. Day 26 sits between
    # two days without read, so it has no neighbour to join.
    write, read = [110] * 30, [100] * 30
    write[10] = write[20] = write[21] = 165
    read[25] = read[27] = 0
    drawn = []
    charts = writer([relay("A")], {"A": history(write, read)})
    charts._save = lambda directory, name, draw, *args: drawn.append(draw(*args)) or 0
    charts.relay(relay("A"), None)

    def strip_paths(ops):  # drawn after the strip's clip, so not the legend's swatches
        return [op for op in ops[[op[:2] for op in ops].index(("clip", "r")):] if op[0] == "path"]

    paths = strip_paths(drawn[0].ops)
    line = next(d for _kind, d, color, width, *_rest in paths if (color, width) == (TEXT, 2.2))
    points = re.findall(r"[ML]([\d.]+ [\d.]+)", line)  # days 0-24, 26 (as a dash), 28 and 29
    assert len(points) == 28 and re.search(r"M[\d.]+ [\d.]+h4.4", line)
    # The line's segments at out-of-band days, drawn again in red where they leave the band.
    red = {clip: d for _kind, d, color, _width, _dash, fill, clip in paths if color == RED and fill == "none"}
    assert set(red) == {"ri", "rl"} and all(points[day] in red["ri"] for day in (9, 10, 11, 19, 20, 21, 22))
    # ... clipped to the strip beyond the band: above p98 (1.58) and below p2 (0.99) on its 0.5–1.70 scale.
    clips = {op[1]: op[2:] for op in drawn[0].ops if op[0] == "clip"}
    (left, top, width, height), y = clips["r"], lambda ratio: clips["r"][1] + clips["r"][3] * (1.70 - ratio) / 1.20
    assert clips["ri"] == pytest.approx((left, top, width, y(1.58) - top))
    assert clips["rl"] == pytest.approx((left, y(0.99), width, top + height - y(0.99)))
    # The 1.0 line is the strip's grid line in the axis gray, with no green dashed line.
    assert not [op for op in drawn[0].ops if op[0] == "line" and op[5:8] == (GREEN, 1.0, "7 4")]
    assert not any(points[day] in red["ri"] for day in (5, 15, 25))
    # The legend says what the red means, on charts that draw it only.
    assert "Outside p2–p98" in [op[3] for op in drawn[0].ops if op[0] == "text"]
    # Alone, day 10's red is only a tip: it gets a dot too.
    dots = [d for _kind, d, color, _width, _dash, fill, _clip in paths if fill == RED and d.count("L") == 11]
    assert len(dots) == 1
    xs, ys = zip(*(map(float, point.split()) for point in re.findall(r"[ML]([\d.]+ [\d.]+)", dots[0])))
    assert "%.1f %.1f" % (sum(xs) / 12, sum(ys) / 12) == points[10]
    # Days just past the band edge (0.985 under p2 0.99: 0.6 px) are a sliver of red: each gets a dot.
    write[3:5] = [98.5, 98.5]
    drawn.clear()
    charts = writer([relay("A")], {"A": history(write, read)})
    charts._save = lambda directory, name, draw, *args: drawn.append(draw(*args)) or 0
    charts.relay(relay("A"), None)
    assert len([op for op in strip_paths(drawn[0].ops) if op[5] == RED and op[1].count("L") == 11]) == 3


def test_out_of_band_days_on_either_side_of_the_band_each_get_a_dot():
    # Guard's p2–p98 is 0.99–1.58: day 15 is above it and day 16 below (0.95, 3 px under p2). The line joins them,
    # but each one's red is only a tip on its own side.
    ts = [T0 + timedelta(days=i) for i in range(30)]
    ratios = [1.05] * 15 + [1.65, 0.95] + [1.05] * 13
    svg = bandwidth_chart("1m", (ts, [10 * r for r in ratios], [10.0] * 30, DAY), 100.0, bands_for_role("Guard"), "relay")
    start = [op[:2] for op in svg.ops].index(("clip", "r"))
    assert len([op for op in svg.ops[start:] if op[0] == "path" and op[5] == RED and op[1].count("L") == 11]) == 2
    # The legend explains them, its swatch a red line with a dot; on a chart only below p2 too.
    ratios = [1.05] * 10 + [0.98, 0.97] + [1.05] * 18
    svg = bandwidth_chart("1m", (ts, [10 * r for r in ratios], [10.0] * 30, DAY), 100.0, bands_for_role("Guard"), "relay")
    start = [op[:2] for op in svg.ops].index(("clip", "r"))
    assert "Outside p2–p98" in [op[3] for op in svg.ops if op[0] == "text"]
    assert len([op for op in svg.ops[:start] if op[0] == "path" and op[5] == RED and op[1].count("L") == 11]) == 1
    # Of those two days below p2 (0.99), only the one under 2 px past it is a sliver that gets a dot.
    (_x, top, _w, height), = [op[2:] for op in svg.ops if op[:2] == ("clip", "r")]
    near, far = (height * (0.99 - r) / 1.20 for r in ratios[10:12])
    assert 1 < near < 2 < far < 3
    dots = [op[1] for op in svg.ops[start:] if op[0] == "path" and op[5] == RED and op[1].count("L") == 11]
    ys = [float(y) for y in re.findall(r"[ML][\d.]+ ([\d.]+)", dots[0])] if len(dots) == 1 else []
    assert ys and abs(sum(ys) / len(ys) - (top + height * (1.70 - 0.98) / 1.20)) < 1


def test_a_long_write_read_subtitle_falls_back_to_counts_to_fit():
    # Above and below the Exit+Guard band every third day each, with family and peers out alongside.
    ts = [T0 + timedelta(days=i) for i in range(30)]
    ratios = [(3.0, 0.5, 1.05)[i % 3] for i in range(30)]
    out = dict(zip(ts, ratios))
    svg = bandwidth_chart("1m", (ts, [10 * r for r in ratios], [10.0] * 30, DAY), 100.0, bands_for_role("Exit+Guard"),
                          "relay", overlays={"role": out, "family": out}, family_n=3)
    line = next(op[3] for op in svg.ops if op[0] == "text" and op[3].startswith("Write/read 1"))
    assert line == ("Write/read 1.52 overall (uncommon) · above p98 on 10 of 30 days · below p2 on 10 of 30 days · "
                    "out with the family and other Exit+Guards")
    assert text_width(line, 12) <= PLOT_WIDTH
    # Three runs a side with years do not fit in full, but do as date ranges.
    ts = [T0 + timedelta(days=2 * i) for i in range(30)]
    ratios = [(1.05, 3.0, 3.0, 1.05, 0.5, 0.5)[i % 6] if i < 18 else 1.05 for i in range(30)]
    svg = bandwidth_chart("1y", (ts, [10 * r for r in ratios], [10.0] * 30, 2 * DAY), 100.0, bands_for_role("Guard"),
                          "relay")
    line = next(op[3] for op in svg.ops if op[0] == "text" and op[3].startswith("Write/read 1"))
    assert line.endswith("above p98 Sep 3 '26–Sep 29 '26 (6 of 30 points) · below p2 Sep 9 '26–Oct 5 '26 (6 of 30 points)")


def test_both_panels_break_where_slots_are_missing():
    ts = [T0 + timedelta(days=2 * i) for i in range(6)]  # every other day of a 1-day history
    svg = bandwidth_chart("1m", (ts, [10.0] * 6, [10.0] * 6, DAY), 100.0, bands_for_role("Guard"), "relay")
    lines = [op[1] for op in svg.ops if op[0] == "path" and op[2] in (GREEN, TEXT) and op[5] == "none"]
    assert len(lines) == 2 and all(d.count("M") == 6 for d in lines)


def test_band_names_sit_in_their_own_ranges_beside_plain_grid_labels():
    ts = [T0 + timedelta(days=i) for i in range(5)]

    def labels(role):
        svg = bandwidth_chart("1m", (ts, [10.0] * 5, [10.0] * 5, DAY), 100.0, bands_for_role(role), "relay")
        return {op[3]: op[1:3] for op in svg.ops if op[0] == "text" and op[3] in ("1.0", "p10–p90")}

    # Guard's typical band (1.01–1.17) lies above 1.0: its name goes inside it, clear of the "1.0" grid label.
    guard = labels("Guard")
    assert guard["p10–p90"][0] == guard["1.0"][0] and guard["1.0"][1] - guard["p10–p90"][1] >= 13
    # Exit's (0.96–1.02) and Exit+Guard's (0.97–1.15) are too thin to hold the name clear of it, and hold 1.0: their
    # name goes beside the label.
    for role in ("Exit", "Exit+Guard"):
        exits = labels(role)
        assert abs(exits["p10–p90"][1] - exits["1.0"][1]) < 1 and exits["p10–p90"][0] < exits["1.0"][0] - 20
    # ">p98" goes inside its own range, Guard's 1.58 up to the 1.70 scale top, clear of "1.5".
    svg = bandwidth_chart("1m", (ts, [10.0] * 5, [10.0] * 5, DAY), 100.0, bands_for_role("Guard"), "relay")
    (_x, top, _w, height), = [op[2:] for op in svg.ops if op[:2] == ("clip", "r")]
    spot = next(op[2] for op in svg.ops if op[0] == "text" and op[3] == ">p98") - 12 * 0.35
    assert top <= spot <= top + height * (1.70 - 1.58) / 1.20


def test_overload_legend_and_spike_callout(tmp_path):
    busy = relay("A", last_restarted="2026-09-21 20:00:00", **OVERLOADED)  # restarted after the last point
    charts = writer([busy], {"A": history(SPIKE, [100] * 21)})
    charts.relay(busy, str(tmp_path))
    lines = texts(tmp_path / "bandwidth-1m.svg")
    assert "currently overloaded · last report Sep 29, 22:00 UTC" in lines
    # An offline relay's verdict comes from its last descriptor: not "currently".
    gone = relay("A", running=False, **OVERLOADED)
    writer([gone], {"A": history(SPIKE, [100] * 21)}).relay(gone, str(tmp_path))
    assert "overloaded · last report Sep 29, 22:00 UTC" in texts(tmp_path / "bandwidth-1m.svg")
    assert "Sep 11 · write/read 4.00 · off the 1.70 scale" in lines
    assert "Last restarted  Sep 21" in lines  # inside the axis' right margin, so still marked
    # Off the scale, the lone day is marked by the edge triangle, not a dot.
    assert "<path" in (tmp_path / "bandwidth-1m.svg").read_text() and not [
        line for line in (tmp_path / "bandwidth-1m.svg").read_text().split("<path") if line.count("L") == 11]
    # On the scale: "beyond the Guard p98"; on 1Y, the neighbouring 2-day slots above p98 are named with it.
    charts = writer([relay("A")], {"A": history([100] * 10 + [165] + [100] * 10, [100] * 21)})
    charts.relay(relay("A"), str(tmp_path))
    assert "Sep 11 · write/read 1.65 · beyond the Guard p98" in texts(tmp_path / "bandwidth-1m.svg")
    ts = [T0 + timedelta(days=2 * i) for i in range(10)]
    svg = bandwidth_chart("1y", (ts, [10.0] * 4 + [17.0, 18.0] + [10.0] * 4, [10.0] * 10, 2 * DAY), 100.0,
                          bands_for_role("Guard"), "relay")
    assert "Sep 9 '26–Sep 11 '26 · write/read 1.70 / 1.80 · off the 1.70 scale" in [op[3] for op in svg.ops if op[0] == "text"]
    # A label too long for either side of a peak mid-axis sits over it, inside the plot (clear of the y labels).
    ts = [T0 + timedelta(days=2 * i) for i in range(61)]
    svg = bandwidth_chart("1y", (ts, [10.0] * 29 + [18.1, 19.1, 18.1] + [10.0] * 29, [10.0] * 61, 2 * DAY), 100.0,
                          bands_for_role("Guard"), "relay")
    (x, _y, width, _height), = [op[1:5] for op in svg.ops if op[0] == "rect" and op[5] == CALLOUT_BG]
    assert width > PLOT_WIDTH / 2 and LEFT <= x and x + width <= LEFT + PLOT_WIDTH
    # Wherever the peak is, the box stays inside the plot (not just the canvas).
    ts = [T0 + timedelta(days=i) for i in range(180)]
    for peak in range(180):
        svg = bandwidth_chart("6m", (ts, [10.0] * peak + [16.5] + [10.0] * (179 - peak), [10.0] * 180, DAY), 100.0,
                              bands_for_role("Guard"), "relay")
        (x, _y, width, _height), = [op[1:5] for op in svg.ops if op[0] == "rect" and op[5] == CALLOUT_BG]
        assert LEFT <= x and x + width <= LEFT + PLOT_WIDTH
    # A newer rate-limit report where no limit was hit does not count toward the verdict, nor its time.
    quiet = dict(OVERLOADED["overload_ratelimits"], **{"write-count": 0, "timestamp": OVERLOADED[
        "overload_ratelimits"]["timestamp"] + 86400000})
    busy = relay("A", overload_ratelimits=quiet, overload_fd_exhausted={"timestamp": quiet["timestamp"] - 2 * 86400000},
                 stability_is_overloaded=True)
    charts.relay(busy, str(tmp_path))
    assert "currently overloaded · last report Sep 28, 22:00 UTC" in texts(tmp_path / "bandwidth-1m.svg")


def test_a_malformed_history_skips_that_chart(tmp_path):
    # Non-numeric slots leave nothing to draw; a malformed interval raises inside the drawing (and, for the
    # 1M history, inside the peer medians too): neither may fail the page, or the build.
    charts = writer([relay("A"), relay("B")], {"A": history(["x", "y", "z"]), "B": history([100] * 30, interval="x")})
    assert charts.relay(relay("A"), str(tmp_path)) == charts.relay(relay("B"), str(tmp_path)) == ({}, {})
    assert os.listdir(tmp_path) == []


def test_operator_chart_sums_members_and_uses_the_role_carrying_most_traffic(tmp_path):
    members = [relay("A", flags=["Exit"]), relay("B", flags=["Exit"]), relay("C"),
               relay("N", contact=""), relay("D", flags=["Exit"]), relay("E")]
    charts = writer(members, {"A": history([100] * 30), "B": history([300] * 30), "C": history([50] * 30),
                              "N": history([50] * 30), "E": history([50] * 30)})
    # Two Guards outnumber the one Exit with history, but the Exit carries three times their traffic.
    assert list(charts.contact([2, 5, 1, 4], str(tmp_path))) == ["1m"]
    lines = texts(tmp_path / "bandwidth-1m.svg")
    assert lines[0] == "example.com  ·  4 relays" and "This operator" in lines
    # D has no history, so its advertised bandwidth stays out of the sum too.
    assert "Advertised  6 Mbit/s" in lines
    assert "Write / read · last 30 days  ·  vs Exit band" in lines and "1,678 Exits · baseline 15 Aug 2026" in lines
    # A tie between roles goes to the first by name, whatever the members' order.
    charts = writer(members, {"A": history([100] * 30), "C": history([100] * 30)})
    for order in ([0, 2], [2, 0]):
        charts.contact(order, str(tmp_path))
        assert "Write / read · last 30 days  ·  vs Exit band" in texts(tmp_path / "bandwidth-1m.svg")
    # Relays without contact info share one hash, but they are not an operator; nor are those whose contact is
    # exactly "none", which the contact page treats alike (" none " is a name there).
    assert charts.contact([3], str(tmp_path)) == {}
    charts = writer([relay("N", contact="none"), relay("O", contact="none")], {"N": history([50] * 30)})
    assert charts.contact([0, 1], str(tmp_path)) == {}
    charts = writer([relay("N", contact=" none ")], {"N": history([50] * 30)})
    assert list(charts.contact([0], str(tmp_path))) == ["1m"]


def test_a_line_breaks_where_a_slot_is_missing():
    svg = Svg(100)
    ts = [T0 + timedelta(days=day) for day in (0, 1, 3, 4)]  # no Sep 3
    Panel(svg, "p", 0, 0, 100, 100, ts, 0, 10).series([1, 2, 3, 4], GREEN, 2)
    assert svg.ops[-1][1].count("M") == 2
    # With the sampling interval known, a history missing every other slot breaks at each gap too.
    ts = [T0 + timedelta(days=day) for day in (0, 2, 4)]
    Panel(svg, "q", 0, 0, 100, 100, ts, 0, 10, interval=86400).series([1, 2, 3], GREEN, 2)
    assert svg.ops[-1][1].count("M") == 3
    # A point with no neighbour is a short dash; at the axis' start, it starts there instead of half outside the plot.
    assert svg.ops[-1][1].startswith("M0.0 90.0h4")  # not M-2.0


def test_a_lone_slot_without_traffic_sits_on_the_bottom_edge():
    """A lone dash at or just above 0 on an axis from 0 sits on the bottom edge rather than half under the clip; lines
    along the edge, points below the scale and the write/read strip's floor stay where they are."""
    # Sep 11 has no traffic and no neighbour to join: its write and read dashes would lie on the throughput panel's
    # bottom edge, the lower half of their strokes under its clip. They sit on the edge instead.
    ts = [T0 + timedelta(days=day) for day in [*range(9), 10, *range(12, 20)]]
    traffic = [10.0] * 9 + [0.0] + [10.0] * 8
    svg = bandwidth_chart("1m", (ts, traffic, traffic, DAY), 100.0, bands_for_role("Guard"), "relay")
    (_x, top, _w, height), = [op[2:] for op in svg.ops if op[:2] == ("clip", "t")]
    for color, width in ((GREEN, 2.4), (BLUE, 1.7)):
        line, = [op[1] for op in svg.ops if op[0] == "path" and op[2:4] == (color, width)]
        dash, = re.findall(r"M[\d.]+ ([\d.]+)h", line)
        assert float(dash) == pytest.approx(top + height - width / 2, abs=0.06)
    # As does a lone 0% slot on an uptime chart.
    svg = uptime_chart("1m", ts, [100.0] * 9 + [0.0] + [100.0] * 8, DAY, "relay", None, 0.0)
    (_x, top, _w, height), = [op[2:] for op in svg.ops if op[:2] == ("clip", "u")]
    line, = [op[1] for op in svg.ops if op[0] == "path" and op[2:4] == (GREEN, 2.2)]
    assert [float(y) for y in re.findall(r"M[\d.]+ ([\d.]+)h", line)] == [pytest.approx(top + height - 1.1, abs=0.06)]
    # One just above 0 sits on the edge too; a line along it and a point below the scale stay where they are.
    svg = Svg(100)
    ts = [T0 + timedelta(days=day) for day in (0, 1, 3, 5)]
    Panel(svg, "p", 0, 0, 100, 100, ts, 0, 10).series([0, 0, 0.05, -1], GREEN, 2)
    assert re.findall(r"[ML][\d.]+ ([\d.]+)", svg.ops[-1][1]) == ["100.0", "100.0", "99.0", "110.0"]
    # The write/read strip's bottom edge is a cut of its scale, not 0: a day below it is drawn there, under its marker.
    Panel(svg, "s", 0, 0, 100, 100, ts, 0.5, 1.5).series([1.0, None, 0.5, None], TEXT, 2.2)
    assert re.findall(r"[ML][\d.]+ ([\d.]+)", svg.ops[-1][1]) == ["50.0", "100.0"]


def test_text_width_knows_the_charts_punctuation():
    # DejaVu Sans: a subtitle full of "·" and "–" must not look wider than it is, or it collapses needlessly.
    assert text_width("·–…", 100) == pytest.approx(32 + 50 + 100) and text_width("ab", 100) == 61 + 63


def test_svg_text_is_escaped_and_valid_xml():
    svg = Svg(100)
    svg.text(0, 0, "<b>&  x\x01\ud800\ufffe\U0001f600", 10)  # contact strings are operator-controlled
    doc = svg.finish(50).document()
    assert "&lt;b&gt;&amp;&#160;&#160;x\U0001f600<" in doc
    ET.fromstring(doc.encode("utf-8"))


def test_axis_ticks():
    def labels(period, start, end):
        return [label for _t, label in date_ticks(period, [start, end], end)]

    def day(*ymd):
        return datetime(*ymd, tzinfo=timezone.utc)

    assert labels("1m", day(2026, 9, 1), day(2026, 10, 1)) == ["Sep 1", "Sep 8", "Sep 15", "Sep 22", "Sep 29"]
    # Onionoo's daily points sit at noon: no tick at the Tuesday midnight before the first one.
    assert labels("1m", T0, day(2026, 10, 1))[0] == "Sep 8"
    assert labels("6m", day(2025, 11, 5), day(2026, 3, 1))[:3] == ["Dec '25", "Jan '26", "Feb '26"]
    assert labels("5y", day(2022, 3, 1), day(2026, 10, 1)) == ["2023", "2024", "2025", "2026"]
    # Too short to reach two ticks: 1M ticks daily; otherwise the ends are labelled too, with the hour on one day,
    # and the year on month ticks of an axis that runs into the next year.
    assert labels("5y", day(2026, 2, 1), day(2026, 9, 20)) == ["Feb 1 '26", "Sep 20 '26"]
    assert labels("5y", day(2025, 5, 7), day(2026, 9, 20)) == ["May 7 '25", "2026", "Sep 20 '26"]
    assert [label for _t, label in date_ticks("1m", [day(2026, 10, 4, 22), day(2026, 10, 5, 2)], day(2026, 10, 7))] == [
        "Oct 5", "Oct 6", "Oct 7"]
    assert labels("1m", day(2026, 10, 6, 10), day(2026, 10, 6, 14)) == ["Oct 6 10:00", "Oct 6 14:00"]
    assert [label for _t, label in date_ticks("1m", [day(2026, 10, 10, 22), day(2026, 10, 11, 2)], day(2026, 10, 11, 6))
            ] == ["Oct 10 22:00", "Oct 11", "Oct 11 02:00"]  # an end on the midnight tick's day
    assert labels("5y", day(2025, 12, 20), day(2026, 9, 20)) == ["2026", "Sep 20 '26"]  # Dec 20 '25: too near 2026
    assert labels("5y", day(2025, 11, 12), day(2026, 9, 20)) == ["Nov 12 '25", "2026", "Sep 20 '26"]  # 50 of 312 days
    assert [label for _t, label in date_ticks("1y", [day(2025, 9, 1), day(2025, 12, 1)], day(2026, 2, 1))] == [
        "Sep '25", "Nov '25", "Jan '26"]
    assert nice_ticks(126) == [0, 25, 50, 75, 100, 125]
    assert ["%g" % tick for tick in nice_ticks(1.3)] == ["0", "0.25", "0.5", "0.75", "1", "1.25"]
