"""SVG history charts: drawing helpers and the relay / operator chart writer."""

import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from types import SimpleNamespace

from allium.lib.charts.render import ChartWriter
from allium.lib.charts.svg import Svg, date_ticks, nice_ticks

PUBLISHED = "2026-09-30 12:00:00"


def block(values, first="2026-09-01 12:00:00", interval=86400, factor=1000.0):
    return {"first": first, "interval": interval, "factor": factor, "values": list(values)}


def relay(fp, contact="url:example.com", flags=("Guard", "Running"), **extra):
    return dict({"fingerprint": fp, "nickname": "relay" + fp, "contact": contact, "flags": list(flags),
                 "advertised_bandwidth": 250000, "last_restarted": "2026-09-10 08:00:00",
                 "effective_family": [fp], "uptime_percentages": {"1_month": 99.5}}, **extra)


def history(write, read=None, key="1_month", **kwargs):
    return {"write_history": {key: block(write, **kwargs)}, "read_history": {key: block(read or write, **kwargs)}}


def writer(relays, bandwidth, uptime=None):
    return ChartWriter(SimpleNamespace(
        json={"relays": relays},
        bandwidth_data={"relays_published": PUBLISHED, "relays": [dict(row, fingerprint=fp) for fp, row in bandwidth.items()]},
        uptime_data={"relays_published": PUBLISHED, "relays": [
            {"fingerprint": fp, "uptime": {"1_month": block(values, interval=14400, factor=1 / 999.0)}}
            for fp, values in (uptime or {}).items()]},
    ))


def texts(path):
    """The chart's text lines (double spaces are written as no-break spaces)."""
    return [t.text.replace("\xa0", " ") for t in ET.parse(path).iter("{http://www.w3.org/2000/svg}text")]


def test_relay_charts_carry_identity_title_legend_and_footnote(tmp_path):
    charts = writer([relay("A")], {"A": history([100 + i for i in range(30)])}, {"A": [999] * 180})
    assert charts.relay(relay("A"), str(tmp_path)) == (("1m",), ("1m",))
    assert sorted(os.listdir(tmp_path)) == ["bandwidth-1m.svg", "uptime-1m.svg"]
    lines = texts(tmp_path / "bandwidth-1m.svg")
    for line in ("relayA  ·  example.com", "Throughput · last 30 days  ·  Guard", "Write (outbound)",
                 "Advertised  2 Mbit/s", "Last restarted  Sep 10", "Write / read · last 30 days  ·  Guard",
                 "This relay", "Typical  1.01–1.17  ·  p10–p90", "Sep 8", "4,444 Guards · baseline 15 Aug 2026"):
        assert line in lines
    assert "Average 100.0%  ·  Onionoo Running flag" in texts(tmp_path / "uptime-1m.svg")


def test_each_period_only_shows_its_own_window(tmp_path):
    stale = history([100] * 30, first="2026-06-01 12:00:00")  # 1M stopped updating months ago
    longer = history([100] * 60, key="6_months", first="2026-08-01 12:00:00")
    charts = writer([relay("A")], {"A": dict(stale, **{k: dict(stale[k], **longer[k]) for k in stale})})
    assert charts.relay(relay("A"), str(tmp_path)) == (("6m",), ())
    assert os.listdir(tmp_path) == ["bandwidth-6m.svg"]


def test_overload_legend_and_spike_callout(tmp_path):
    write = [100] * 10 + [400] + [100] * 10
    hit = int(datetime(2026, 9, 29, 22, tzinfo=timezone.utc).timestamp() * 1000)
    busy = relay("A", stability_is_overloaded=True, last_restarted="2026-09-21 20:00:00",  # after the last point
                 overload_ratelimits={"timestamp": hit, "write-count": 3, "read-count": 0})
    charts = writer([busy], {"A": history(write, [100] * 21)})
    charts.relay(busy, str(tmp_path))
    lines = texts(tmp_path / "bandwidth-1m.svg")
    assert "currently overloaded · last report Sep 29, 22:00 UTC" in lines
    assert "Sep 11 · write/read 4.00 · off the 1.70 scale" in lines
    assert "Last restarted  Sep 21" in lines  # inside the axis' right margin, so still marked


def test_a_malformed_history_skips_that_chart(tmp_path):
    charts = writer([relay("A")], {"A": history(["x", "y", "z"])})
    assert charts.relay(relay("A"), str(tmp_path)) == ((), ())
    assert os.listdir(tmp_path) == []


def test_operator_chart_sums_members_and_uses_their_main_role(tmp_path):
    members = [relay("A", flags=["Exit"]), relay("B", flags=["Exit"]), relay("C"),
               relay("N", contact=""), relay("D", flags=["Exit"])]
    charts = writer(members, {"A": history([100] * 30), "B": history([300] * 30), "C": history([50] * 30)})
    assert charts.contact([0, 1, 2, 4], str(tmp_path)) == ("1m",)
    lines = texts(tmp_path / "bandwidth-1m.svg")
    assert lines[0] == "example.com" and "This operator" in lines
    # D has no history, so its advertised bandwidth stays out of the sum too.
    assert "Advertised  6 Mbit/s" in lines
    assert "1,678 Exits · baseline 15 Aug 2026" in lines
    # Relays without contact info share one hash, but they are not an operator.
    assert charts.contact([3], str(tmp_path / "none")) == ()


def test_svg_text_is_escaped_and_valid_xml():
    svg = Svg(100)
    svg.text(0, 0, "<b>&  x\x01", 10)  # contact strings are operator-controlled
    doc = svg.document(50)
    assert "&lt;b&gt;&amp;&#160;&#160;x<" in doc
    ET.fromstring(doc)


def test_axis_ticks():
    def labels(period, start, end):
        return [label for _t, label in date_ticks(period, [start, end], end)]

    def day(*ymd):
        return datetime(*ymd, tzinfo=timezone.utc)

    assert labels("1m", day(2026, 9, 1), day(2026, 10, 1)) == ["Sep 1", "Sep 8", "Sep 15", "Sep 22", "Sep 29"]
    assert labels("6m", day(2025, 11, 5), day(2026, 3, 1))[:3] == ["Dec '25", "Jan '26", "Feb '26"]
    assert labels("5y", day(2022, 3, 1), day(2026, 10, 1)) == ["2023", "2024", "2025", "2026"]
    # Too short to reach two ticks: label the ends instead.
    assert labels("5y", day(2026, 2, 1), day(2026, 9, 20)) == ["Feb 1 '26", "Sep 20 '26"]
    assert nice_ticks(126) == [0, 25, 50, 75, 100, 125]
    assert ["%g" % tick for tick in nice_ticks(1.3)] == ["0", "0.25", "0.5", "0.75", "1", "1.25"]
