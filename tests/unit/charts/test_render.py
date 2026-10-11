"""SVG history charts: drawing helpers and the relay / operator chart writer."""

import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from types import SimpleNamespace

from allium.lib.charts.svg import GREEN, Svg, date_ticks, nice_ticks

from .fixtures import OVERLOADED, SPIKE, T0, decode, history, needs_png, relay, writer


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
    (root / "old-drawing").mkdir(parents=True)  # cached by another drawing version: never hit again
    history_a = {"A": history([100 + i for i in range(30)])}
    charts = writer([relay("A")], history_a, {"A": [999] * 180}, "png", str(root))
    assert os.listdir(root) == [os.path.basename(charts.cache)]
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
    assert os.stat(second / "bandwidth-1m.png").st_ino == os.stat(first / "bandwidth-1m.png").st_ino
    assert os.stat(second / "bandwidth-1m.png").st_mtime == 1
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
    writer([relay("A")], history_a, cache_dir=str(root)).sweep()
    assert not root.exists()
    # --chart-scale 1.5 draws 1620 px wide; --chart-colors full writes RGBA.
    smaller = writer([relay("A")], history_a, {"A": [999] * 180}, "png", str(root), scale=1.5, colors="full")
    bandwidth, _uptime = smaller.relay(relay("A"), str(third))
    assert decode((third / "bandwidth-1m.png").read_bytes()).shape == (round(1.5 * bandwidth["1m"]), 1620, 4)


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


def test_overload_legend_and_spike_callout(tmp_path):
    busy = relay("A", last_restarted="2026-09-21 20:00:00", **OVERLOADED)  # restarted after the last point
    charts = writer([busy], {"A": history(SPIKE, [100] * 21)})
    charts.relay(busy, str(tmp_path))
    lines = texts(tmp_path / "bandwidth-1m.svg")
    assert "currently overloaded · last report Sep 29, 22:00 UTC" in lines
    assert "Sep 11 · write/read 4.00 · off the 1.70 scale" in lines
    assert "Last restarted  Sep 21" in lines  # inside the axis' right margin, so still marked


def test_a_malformed_history_skips_that_chart(tmp_path):
    charts = writer([relay("A")], {"A": history(["x", "y", "z"])})
    assert charts.relay(relay("A"), str(tmp_path)) == ({}, {})
    assert os.listdir(tmp_path) == []


def test_operator_chart_sums_members_and_uses_their_main_role(tmp_path):
    members = [relay("A", flags=["Exit"]), relay("B", flags=["Exit"]), relay("C"),
               relay("N", contact=""), relay("D", flags=["Exit"])]
    charts = writer(members, {"A": history([100] * 30), "B": history([300] * 30), "C": history([50] * 30)})
    assert list(charts.contact([0, 1, 2, 4], str(tmp_path))) == ["1m"]
    lines = texts(tmp_path / "bandwidth-1m.svg")
    assert lines[0] == "example.com" and "This operator" in lines
    # D has no history, so its advertised bandwidth stays out of the sum too.
    assert "Advertised  6 Mbit/s" in lines
    assert "1,678 Exits · baseline 15 Aug 2026" in lines
    # Relays without contact info share one hash, but they are not an operator.
    assert charts.contact([3], str(tmp_path / "none")) == {}


def test_svg_text_is_escaped_and_valid_xml():
    svg = Svg(100)
    svg.text(0, 0, "<b>&  x\x01", 10)  # contact strings are operator-controlled
    doc = svg.finish(50).document()
    assert "&lt;b&gt;&amp;&#160;&#160;x<" in doc
    ET.fromstring(doc)


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
    # Too short to reach two ticks: label the ends instead.
    assert labels("5y", day(2026, 2, 1), day(2026, 9, 20)) == ["Feb 1 '26", "Sep 20 '26"]
    assert nice_ticks(126) == [0, 25, 50, 75, 100, 125]
    assert ["%g" % tick for tick in nice_ticks(1.3)] == ["0", "0.25", "0.5", "0.75", "1", "1.25"]
