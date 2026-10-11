"""SVG history charts: drawing helpers and the relay / operator chart writer."""

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from allium.lib.charts.bands import bands_for_role
from allium.lib.charts.render import PLOT_WIDTH, bandwidth_chart
from allium.lib.charts.svg import GREEN, RED, TEXT, Panel, Svg, date_ticks, nice_ticks, text_width

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
    assert "Average 100.0%  ·  Onionoo Running flag" in texts(tmp_path / "uptime-1m.svg")


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
    offline = relay("A", last_restarted="2026-09-25 08:00:00")
    charts = writer([offline], {"A": history([100] * 20)}, {"A": [999] * 120})
    charts.relay(offline, str(tmp_path))
    for name in ("bandwidth-1m.svg", "uptime-1m.svg"):
        lines = texts(tmp_path / name)
        assert "Sep 29" in lines and "Last restarted  Sep 25" in lines
    # Onionoo has no points while it is out of the consensus: the 54 whole 4-hour slots from its last point
    # (Sep 21 08:00) to relays_published count as down in the average, 120 x 100% / 174.
    assert "Average 69.0%  ·  down since Sep 21  ·  Onionoo Running flag" in texts(tmp_path / "uptime-1m.svg")


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
    assert "Under 50 KB/s throughout: too little traffic to compare" in texts(tmp_path / "bandwidth-1m.svg")


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
    paths = [op for op in drawn[0].ops if op[0] == "path"]
    line = next(d for _kind, d, color, width, *_rest in paths if (color, width) == (TEXT, 2.2))
    points = re.findall(r"[ML]([\d.]+ [\d.]+)", line)  # days 0-24, 26 (as a dash), 28 and 29
    assert len(points) == 28 and re.search(r"M[\d.]+ [\d.]+h4.4", line)
    # The line's segments at out-of-band days, drawn again in red where they leave the band.
    red = {clip: d for _kind, d, color, _width, _dash, fill, clip in paths if color == RED and fill == "none"}
    assert set(red) == {"ri", "rl"} and all(points[day] in red["ri"] for day in (9, 10, 11, 19, 20, 21, 22))
    assert not any(points[day] in red["ri"] for day in (5, 15, 25))
    # Alone, day 10's red is only a tip: it gets a dot too.
    dots = [d for _kind, d, color, _width, _dash, fill, _clip in paths if fill == RED and d.count("L") == 11]
    assert len(dots) == 1
    xs, ys = zip(*(map(float, point.split()) for point in re.findall(r"[ML]([\d.]+ [\d.]+)", dots[0])))
    assert "%.1f %.1f" % (sum(xs) / 12, sum(ys) / 12) == points[10]


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


def test_band_names_sit_in_their_own_ranges_beside_plain_grid_labels():
    ts = [T0 + timedelta(days=i) for i in range(5)]

    def labels(role):
        svg = bandwidth_chart("1m", (ts, [10.0] * 5, [10.0] * 5, DAY), 100.0, bands_for_role(role), "relay")
        return {op[3]: op[1:3] for op in svg.ops if op[0] == "text" and op[3] in ("1.0", "p10–p90")}

    # Guard's typical band (1.01–1.17) lies above 1.0: its name goes inside it, clear of the "1.0" grid label.
    guard = labels("Guard")
    assert guard["p10–p90"][0] == guard["1.0"][0] and guard["1.0"][1] - guard["p10–p90"][1] >= 13
    # Exit's (0.96–1.02) is too thin to clear it, and holds 1.0: its name goes beside the label.
    exits = labels("Exit")
    assert abs(exits["p10–p90"][1] - exits["1.0"][1]) < 1 and exits["p10–p90"][0] < exits["1.0"][0] - 20


def test_overload_legend_and_spike_callout(tmp_path):
    busy = relay("A", last_restarted="2026-09-21 20:00:00", **OVERLOADED)  # restarted after the last point
    charts = writer([busy], {"A": history(SPIKE, [100] * 21)})
    charts.relay(busy, str(tmp_path))
    lines = texts(tmp_path / "bandwidth-1m.svg")
    assert "currently overloaded · last report Sep 29, 22:00 UTC" in lines
    assert "Sep 11 · write/read 4.00 · off the 1.70 scale" in lines
    assert "Last restarted  Sep 21" in lines  # inside the axis' right margin, so still marked
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
    # Relays without contact info share one hash, but they are not an operator.
    assert charts.contact([3], str(tmp_path)) == {}


def test_a_line_breaks_where_a_slot_is_missing():
    svg = Svg(100)
    ts = [T0 + timedelta(days=day) for day in (0, 1, 3, 4)]  # no Sep 3
    Panel(svg, "p", 0, 0, 100, 100, ts, 0, 10).series([1, 2, 3, 4], GREEN, 2)
    assert svg.ops[-1][1].count("M") == 2
    # With the sampling interval known, a history missing every other slot breaks at each gap too.
    ts = [T0 + timedelta(days=day) for day in (0, 2, 4)]
    Panel(svg, "q", 0, 0, 100, 100, ts, 0, 10, interval=86400).series([1, 2, 3], GREEN, 2)
    assert svg.ops[-1][1].count("M") == 3


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
    assert [label for _t, label in date_ticks("1y", [day(2025, 9, 1), day(2025, 12, 1)], day(2026, 2, 1))] == [
        "Sep '25", "Nov '25", "Jan '26"]
    assert nice_ticks(126) == [0, 25, 50, 75, 100, 125]
    assert ["%g" % tick for tick in nice_ticks(1.3)] == ["0", "0.25", "0.5", "0.75", "1", "1.25"]
