#!/usr/bin/env python3
"""Design mockup: network bandwidth and uptime history on the health dashboard.

Regenerate from the repo root:

    python3 docs/features/planned/network-history/build_mockup.py

The chart images are drawn by the relay/operator chart renderer so the mockup
is the real height, the real thumbnail switcher, and the real 1m/6m/1y/5y
periods. The series are illustrative, not an Onionoo fetch.
"""

import html
import math
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))

from allium.lib.charts.bands import bands_for_role, census_footnote
from allium.lib.charts.render import bandwidth_chart, uptime_chart

HERE = os.path.dirname(os.path.abspath(__file__))
CHARTS = os.path.join(HERE, "charts")
END = datetime(2026, 10, 16, tzinfo=timezone.utc)
PERIODS = ("1m", "6m", "1y", "5y")
# (points, step in days). 1m is daily and hides the axis caption; the others
# label themselves 1-day, 2-day, and 1-week, as the relay charts do.
SPECS = {"1m": (31, 1), "6m": (183, 1), "1y": (183, 2), "5y": (261, 7)}
SPAN = {"1m": "last 30 days", "6m": "last 6 months", "1y": "last year", "5y": "last 5 years"}
ADVERTISED = 980.0  # illustrative sum of advertised bandwidth, Gbit/s


def _series(period):
    """``(timestamps, write Gbit/s, read Gbit/s, interval seconds)``."""
    count, step = SPECS[period]
    ts, write, read = [], [], []
    for i in range(count):
        ts.append(END - timedelta(days=step * (count - 1 - i)))
        x = i / (count - 1)
        if period == "5y":
            base = 260 + 490 * (x ** 1.2)
        elif period == "1y":
            base = 560 + 160 * x
        elif period == "6m":
            base = 650 + 60 * x
        else:
            base = 700
        weekly = 16 * math.sin(2 * math.pi * i / (7.0 / step if step < 7 else 4.0))
        dip = 0.0
        if period == "1m" and 18 <= i <= 21:
            dip = -48
        elif period == "6m" and 120 <= i <= 128:
            dip = -70
        elif period == "1y" and 80 <= i <= 86:
            dip = -90
        elif period == "5y" and 150 <= i <= 160:
            dip = -110
        noise = 7 * math.sin(i * 1.7) + 4 * math.sin(i * 0.31)
        outbound = max(40.0, base + weekly + dip + noise)
        ratio = 1.05 + 0.05 * math.sin(i / 6.0)
        write.append(outbound)
        read.append(outbound / ratio)
    return ts, write, read, step * 86400


def _uptime(period):
    """``(timestamps, running-flag percent, interval seconds)``."""
    count, step = SPECS[period]
    ts, values = [], []
    for i in range(count):
        ts.append(END - timedelta(days=step * (count - 1 - i)))
        x = i / (count - 1)
        base = 97.8 + 0.7 * math.sin(i / 8.0)
        if period == "5y":
            base += -1.4 + 1.5 * x
        dip = 0.0
        if period == "1m" and i in (12, 13, 14):
            dip = -3.2
        elif period == "6m" and 70 <= i <= 76:
            dip = -4.5
        elif period == "1y" and 40 <= i <= 48:
            dip = -7.0
        elif period == "5y" and 168 <= i <= 180:
            dip = -9.0
        values.append(min(99.7, max(88.0, base + dip)))
    return ts, values, step * 86400


def _retitle_bandwidth(document):
    """Network wording on a chart the renderer built for one operator."""
    footnote = census_footnote(bands_for_role("Guard"))
    document = document.replace(footnote, "Illustrative network sum")
    document = document.replace("&#160;&#160;·&#160;&#160;vs Guard band", "")
    document = document.replace("This operator", "Network sum")
    return document.replace("Mbit/s", "Gbit/s")


def _retitle_uptime(document):
    return document.replace("Average ", "Mean ")


def write_charts():
    """Draw eight SVGs. Returns ``{name: {period: height}}``."""
    os.makedirs(CHARTS, exist_ok=True)
    bands = bands_for_role("Guard")
    footnote = census_footnote(bands)
    heights = {"bandwidth": {}, "uptime": {}}
    for period in PERIODS:
        ts, write, read, interval = _series(period)
        bandwidth = bandwidth_chart(
            period, (ts, write, read, interval), ADVERTISED, bands, "Tor network", operator=True, end=END)
        document = _retitle_bandwidth(bandwidth.document())
        path = os.path.join(CHARTS, "bandwidth-%s.svg" % period)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(document)
        heights["bandwidth"][period] = bandwidth.height
        for banned in ("Mbit/s", "This operator", "vs Guard", footnote):
            if banned in document:
                raise SystemExit("bandwidth %s still contains %r" % (period, banned))

        uts, percent, uinterval = _uptime(period)
        uptime = uptime_chart(period, uts, percent, uinterval, "Tor network", None, sum(percent) / len(percent))
        document = _retitle_uptime(uptime.document())
        path = os.path.join(CHARTS, "uptime-%s.svg" % period)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(document)
        heights["uptime"][period] = uptime.height
        if "Average " in document:
            raise SystemExit("uptime %s still says Average" % period)
    return heights


def esc(text):
    return html.escape(text, quote=True)


def metric(value, label, title, primary=False):
    kind = "metric-item primary" if primary else "metric-item"
    return (
        '<div class="%s" title="%s"><span class="metric-value">%s</span>'
        '<span class="metric-label">%s</span></div>'
    ) % (kind, esc(title), value, esc(label))


def grid(columns, cells):
    inner = "".join(metric(value, label, title) for value, label, title in cells)
    return '<div class="metric-grid" style="grid-template-columns: repeat(%d, 1fr);">%s</div>' % (columns, inner)


def card(anchor, title, primary, grids, history=None):
    """One ribbon card. ``history`` is ``(href, label)`` for a jump to a chart."""
    value, label, title_attr = primary
    jump = ""
    if history:
        jump = '<a class="history-jump" href="%s">%s</a>' % history
    blocks = "".join(grid(columns, cells) for columns, cells in grids)
    return """
        <div class="ribbon-card">
            <div class="card-header" id="%s">
                <h4><a href="#%s" class="al-link-plain">%s</a></h4>
                %s
            </div>
            <div class="card-metrics">
                %s
                %s
            </div>
        </div>""" % (anchor, anchor, title, jump, metric(value, label, title_attr, primary=True), blocks)


def chart_block(name, heading, alt, heights):
    """The relay page's chart_history markup: default period last, sparks first visually."""
    order = list(PERIODS)
    heroes = []
    for period in order[1:] + order[:1]:
        heroes.append(
            '<a id="%s-%s" class="chart-hero chart-on-%s" href="charts/%s-%s.svg">'
            '<img src="charts/%s-%s.svg" width="1080" height="%d" alt="%s, %s"></a>'
            % (name, period, period, name, period, name, period, heights[name][period], esc(alt), SPAN[period])
        )
    sparks = []
    for index, period in enumerate(order):
        default = " chart-spark-default" if index == 0 else ""
        sparks.append(
            '<a class="chart-spark chart-on-%s%s" href="#%s-%s" '
            'aria-label="%s: show the %s"><img src="charts/%s-%s.svg" width="1080" height="%d" alt="">%s</a>'
            % (period, default, name, period, period.upper(), SPAN[period], name, period,
               heights[name][period], period.upper())
        )
    return """
        <div class="history-chart" id="network-%s">
            <h5 class="subsection-header">%s</h5>
            <div class="chart-history">
                %s
                <div class="chart-sparks">%s</div>
            </div>
        </div>""" % (name, esc(heading), "".join(heroes), "".join(sparks))


def history_section(heights):
    anchors = "".join('<span id="%s" class="chart-period"></span>' % period for period in PERIODS)
    periods = "".join('<a href="#%s">%s</a>' % (period, period.upper()) for period in PERIODS)
    bandwidth = chart_block( "bandwidth", "Bandwidth", "Network throughput and write/read", heights)
    uptime = chart_block("uptime", "Uptime", "Network mean uptime", heights)
    return """
    <section class="ribbon-card network-history" id="network-history">
        %s
        <div class="card-header">
            <h4><a href="#network-history" class="al-link-plain">Network History</a></h4>
        </div>
        <p class="history-lead">Sum of relay throughput, and the mean running-flag uptime, for the same
            1 month, 6 months, 1 year, and 5 years as a relay page. A thumbnail changes that chart.
            A period link changes both.</p>
        <p class="history-periods">%s</p>
        <div class="history-grid">
            %s
            %s
        </div>
        <p class="history-note">Sample series for the mockup, drawn with the relay chart renderer.
            Throughput is Gbit/s: green write, blue read, dashed orange advertised capacity.
            Uptime is the mean of relays' Running flags, the same kind of figure as Overall Uptime above.
            The lower write/read panel is that relay chart at its real height. A network sum would not be
            graded against one role's percentile bands.</p>
    </section>""" % (anchors, periods, bandwidth, uptime)


# Sample figures, so the ribbon has the real page's weight. Not a live fetch.
T = "Sample figure for the layout mockup"


def dashboard(heights):
    rows = []

    def add(cards):
        rows.append('<div class="ribbon-row">%s</div>' % "".join(cards))

    add([
        card("relay-counts", "📊 Relay Counts", ("8,946", "Total Relays", T), [
            (4, [("2,104 (23.5%)", "Exit", T), ("3,812 (42.6%)", "Guard", T),
                 ("4,221 (47.2%)", "Middle", T), ("891 (10.0%)", "Exit + Guard", T)]),
            (4, [("7,640 (85.4%)", "Fast", T), ("6,102 (68.2%)", "Stable", T),
                 ("7,201 (80.5%)", "Measured", T), ("412 (4.6%)", "Offline", T)]),
            (3, [("9 (0.1%)", "Directory Authorities", T), ("6,440 (72.0%)", "V2Dir", T),
                 ("5,880 (65.7%)", "HSDir", T)]),
            (2, [("5,102 (57.0%)", "Relays with IPv4 &amp; IPv6", T), ("3,844 (43.0%)", "Only IPv4", T)]),
            (4, [("12 (0.1%)", "BadExit", T), ("86 (1.0%)", "StaleDesc", T),
                 ("34 (0.4%)", "Sybil", T), ("219 (2.4%)", "Overloaded", T)]),
            (4, [("18 (0.2%)", "New 1d", T), ("410 (4.6%)", "New 1mo", T),
                 ("1,902 (21.3%)", "New 6mo", T), ("3,240 (36.2%)", "New 1y", T)]),
            (1, [("2y 4mo | 1y 7mo", "Age (Mean | Median)", T)]),
        ]),
        card("bandwidth-capacity", "⚡ Bandwidth Capacity Availability", ("812 Gbit/s", "Total Capacity", T), [
            (1, [("6.8 EiB", "Total Data Transferred (5yr history)", T)]),
            (3, [("1.9 EiB", "Exit Total Data", T), ("3.1 EiB", "Guard Total Data", T),
                 ("1.8 EiB", "Middle Total Data", T)]),
            (3, [("214 Gbit/s", "Exit Capacity", T), ("401 Gbit/s", "Guard Capacity", T),
                 ("197 Gbit/s", "Middle Capacity", T)]),
            (3, [("102 | 41 Mbit/s", "Exit Mean | Median", T), ("105 | 38 Mbit/s", "Guard Mean | Median", T),
                 ("47 | 12 Mbit/s", "Middle Mean | Median", T)]),
            (2, [("11 | 9 Mbit/s", "Obs to Adv Diff (Mean | Median)", T),
                 ("7,201 (80.5%)", "Capacity Measured", T)]),
        ], history=("#network-bandwidth", "Bandwidth history")),
        card("relay-uptime", "⏰ Relay Uptime", ("98.1%", "Overall Uptime (1mo Mean)", T), [
            (3, [("97.4% | 99.1%", "Exit 1mo (Mean | Median)", T),
                 ("98.6% | 99.4%", "Guard 1mo (Mean | Median)", T),
                 ("98.0% | 99.2%", "Middle 1mo (Mean | Median)", T)]),
            (3, [("99.8% | 100%", "Authority 1mo (Mean | Median)", T),
                 ("98.4% | 99.3%", "V2Dir 1mo (Mean | Median)", T),
                 ("98.7% | 99.5%", "HSDir 1mo (Mean | Median)", T)]),
            (1, [("97.4% | 96.8% | 96.1% | 95.2%", "Exit: 1mo | 6mo | 1y | 5y (Mean)", T)]),
            (1, [("98.6% | 98.1% | 97.6% | 96.4%", "Guard: 1mo | 6mo | 1y | 5y (Mean)", T)]),
            (1, [("98.0% | 97.5% | 97.0% | 95.8%", "Middle: 1mo | 6mo | 1y | 5y (Mean)", T)]),
            (1, [("99.8% | 99.6% | 99.4% | 99.1%", "Authority: 1mo | 6mo | 1y | 5y (Mean)", T)]),
        ], history=("#network-uptime", "Uptime history")),
    ])
    add([
        card("operator-participation", "👥 Operator Participation",
             ("1,842 domains | 6,210 relays (69.4%)", "Unique AROI Operators | AROI Relays (% of network)", T), [
                 (2, [("1,204", "Validated AROI Operators", T), ("638", "Failed Validation", T)]),
                 (3, [("4,880", "Validated AROI Relays", T), ("1,330", "Invalid AROI", T), ("2,736", "No AROI", T)]),
             ]),
        card("geographic-participation", "🌍 Geographic Participation",
             ("DE 18.4% · US 14.1% · NL 9.6%", "Top 3 Countries by Consensus Weight", T), [
                 (3, [("41.2%", "EU Consensus Weight", T), ("58.8%", "Non-EU", T), ("6.4%", "Rare Countries", T)]),
                 (2, [("22.8%", "Five Eyes", T), ("61.5%", "Fourteen Eyes", T)]),
             ]),
        card("provider-participation", "🏢 Provider Participation",
             ("Hetzner 11.2% · OVH 8.4% · Frantech 4.1%", "Top 3 Networks by Consensus Weight", T), [
                 (3, [("11.2%", "Top AS", T), ("31.6%", "Top 5 AS", T), ("48.9%", "Top 10 AS", T)]),
             ]),
    ])
    add([
        card("bandwidth-utilization", "📈 Bandwidth Utilization",
             ("46%", "Network Observed / Advertised", T), [
                 (3, [("52%", "Exit Utilization", T), ("49%", "Guard Utilization", T),
                      ("38%", "Middle Utilization", T)]),
             ]),
        card("version-compliance", "🔄 Version Compliance",
             ("94.2%", "Recommended or Newer", T), [
                 (3, [("8,430", "Recommended", T), ("412", "Obsolete", T), ("104", "Experimental", T)]),
             ]),
        card("operating-systems", "💻 Unique Operating Systems",
             ("Linux 96.1%", "Share of Relays", T), [
                 (3, [("8,598", "Linux", T), ("214", "BSD", T), ("134", "Other", T)]),
             ]),
    ])
    add([
        card("happy-families", "🔑 Happy Families Key Migration",
             ("72%", "Family-cert Adoption", T), [
                 (3, [("9 / 9", "DA Readiness", T), ("64%", "AROI Operators", T), ("81%", "Relay Versions", T)]),
             ]),
        card("exit-policies", "🚪 Exit Policies",
             ("1,640", "Default Exit Policy", T), [
                 (3, [("1,640", "Default", T), ("402", "Reduced", T), ("62", "Custom", T)]),
             ]),
        card("exit-dns-health", "🔍 Exit DNS Health",
             ("97.6%", "DNS Success", T), [
                 (3, [("97.6%", "Success", T), ("1.8%", "Timeout", T), ("0.6%", "Wrong Answer", T)]),
             ]),
    ])
    footer = """
    <div class="ribbon-footer">
        <p class="last-updated">Last updated: 2026-10-16 18:30 UTC</p>
    </div>"""
    return "\n".join(rows[:1] + [history_section(heights)] + rows[1:] + [footer])


CSS = """
.mock-bar {
    position: sticky;
    top: 0;
    z-index: 20;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 14px;
    padding: 8px 16px;
    background: #1e1e1e;
    color: #e6e6e6;
    font-size: 13px;
}
.mock-bar a { color: #9a9a9a; text-decoration: none; font-weight: 600; }
.mock-bar a:hover, .mock-bar a:focus { color: #00ff7f; }
.mock-bar a.on { color: #00ff7f; }
.mock-bar .mock-tag {
    color: #ffb454;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    font-size: 11px;
}
.history-jump { display: inline-block; margin-top: 3px; font-size: 1.15rem; font-weight: 600; }
.network-history { margin-bottom: 7px; }
.network-history:hover { transform: none; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08); }
.history-lead { margin: 0 0 8px; color: var(--nh-text-label); font-size: 14px; }
.history-periods { margin: 0 0 4px; }
.history-periods a {
    display: inline-block;
    margin: 0 6px 6px 0;
    padding: 2px 8px;
    border-radius: 3px;
    background: var(--nh-bg-metric);
    color: var(--color-link);
    font-size: 1.2rem;
    font-weight: 600;
    text-decoration: none;
}
.history-periods a[href="#1m"] { color: var(--aeo-green-hover); }
.chart-period:target ~ .history-periods a[href="#1m"] { color: var(--color-link); }
.chart-period[id="1m"]:target ~ .history-periods a[href="#1m"],
.chart-period[id="6m"]:target ~ .history-periods a[href="#6m"],
.chart-period[id="1y"]:target ~ .history-periods a[href="#1y"],
.chart-period[id="5y"]:target ~ .history-periods a[href="#5y"] { color: var(--aeo-green-hover); }
.history-note { margin: 8px 0 0; color: var(--nh-text-label-secondary); font-size: 12px; }
.history-grid { display: block; }
body.layout-c .history-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    align-items: start;
}
.history-grid > * { min-width: 0; }
body.layout-a .network-health-ribbon,
body.layout-c .network-health-ribbon { display: flex; flex-direction: column; }
body.layout-a .network-history,
body.layout-c .network-history { order: 5; }
body.layout-a .ribbon-footer,
body.layout-c .ribbon-footer { order: 6; }
#network-history, #network-bandwidth, #network-uptime { scroll-margin-top: 56px; }
@media (max-width: 1100px) {
    body.layout-c .history-grid { grid-template-columns: 1fr; }
}
.reco { max-width: 1100px; margin: 0 auto 28px; }
.reco h1 { font-size: 28px; margin: 8px 0 10px; color: var(--color-text-heading); }
.reco .verdict { font-size: 18px; margin: 0 0 18px; }
.choices { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.choice {
    border: 1px solid var(--color-border-card);
    border-radius: 6px;
    padding: 10px;
    background: #fff;
}
.choice.preferred { border-top: 3px solid var(--aeo-green-hover); }
.choice h2 { font-size: 16px; margin: 0 0 8px; }
.choice p { font-size: 13px; color: var(--color-text-dark); margin: 8px 0; }
.choice .open-layout { font-weight: 700; }
.wire { display: flex; flex-direction: column; gap: 4px; font-size: 11px; color: var(--nh-text-value); }
.wire-row, .wire-charts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; }
.wire-card, .wire-rest, .wire-chart, .wire-foot {
    background: var(--nh-bg-metric);
    border-radius: 3px;
    padding: 6px;
    text-align: center;
}
.wire-rest { grid-column: 1 / -1; color: var(--nh-text-label); }
.wire-chart {
    background: #1e1e1e;
    color: #e6e6e6;
    min-height: 72px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 4px;
}
.wire-chart span { color: #00cc66; letter-spacing: 0.08em; }
.wire-foot { color: var(--nh-text-footer); }
.layout-a-wire .wire-chart, .layout-b-wire .wire-chart { grid-column: 1 / -1; min-height: 46px; }
.layout-b-wire .wire { display: flex; }
.layout-b-wire .wire-row:first-child { order: 1; }
.layout-b-wire .wire-charts { order: 2; }
.layout-b-wire .wire-row:not(:first-child) { order: 3; }
.layout-b-wire .wire-foot { order: 4; }
.layout-c-wire .wire-charts { grid-template-columns: 1fr 1fr; }
.layout-c-wire .wire-chart.uptime { min-height: 48px; }
.notes { max-width: 1100px; margin: 18px auto 0; font-size: 14px; }
.notes h2 { font-size: 18px; }
@media (max-width: 800px) {
    .choices { grid-template-columns: 1fr; }
}
"""

NAV = """
<nav class="navbar navbar-default" style="margin-bottom: 20px;">
    <div class="container-fluid">
        <ul class="nav navbar-nav">
            <li class="active"><a href="layout-a.html">Network Health</a></li>
            <li><a href="layout-a.html">Operator Champions</a></li>
            <li><a href="layout-a.html">By Operator / Contact</a></li>
            <li><a href="layout-a.html">By Family</a></li>
            <li><a href="layout-a.html">By Network</a></li>
            <li><a href="layout-a.html">By Country</a></li>
            <li><a href="layout-a.html">By Platform</a></li>
        </ul>
    </div>
</nav>"""

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>@@TITLE@@ | 1AEO Tor Metrics</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="noindex">
    <link rel="stylesheet" href="../../../../allium/static/css/bootstrap.min.css">
    <link rel="stylesheet" href="../../../../allium/static/css/allium-base.css">
    <link rel="stylesheet" href="../../../../allium/static/css/network-health.css">
    <style>@@CSS@@</style>
</head>
<body class="@@BODY@@">
    <div class="mock-bar">@@BAR@@</div>
    <nav class="aeo-cross-nav">
        <div class="aeo-nav-container">
            <a href="https://www.1aeo.com" class="aeo-nav-brand"><span>1AEO</span></a>
            <div class="aeo-nav-links">
                <a href="https://www.1aeo.com">Home</a>
                <a href="https://metrics.1aeo.com" class="active">Metrics</a>
                <a href="https://aroivalidator.1aeo.com">AROI Validator</a>
                <a href="https://routefluxmap.1aeo.com">RouteFluxMap</a>
            </div>
        </div>
    </nav>
    <div class="container">
        @@MAIN@@
    </div>
</body>
</html>
"""


def bar(current):
    links = [
        ("index.html", "index", "Recommendation"),
        ("layout-a.html", "layout-a", "A · Bottom, stacked"),
        ("layout-b.html", "layout-b", "B · Under the first row"),
        ("layout-c.html", "layout-c", "C · Bottom, side by side"),
    ]
    parts = ['<span class="mock-tag">Design mockup</span>']
    for href, key, label in links:
        mark = " on" if key == current else ""
        parts.append('<a class="%s" href="%s">%s</a>' % (mark.strip(), href, label))
    return "".join(parts)


def layout_main():
    return """
        <div class="aroi-center-text aroi-subsection">
            <h1>Tor Network Health Dashboard</h1>
            <p class="lead"><strong>Real-time Overview Metrics</strong></p>
        </div>
        %s
        <div class="network-health-ribbon">
            @@DASH@@
        </div>""" % NAV


def write_page(name, body_class, title, main, dash=""):
    document = (PAGE
                .replace("@@TITLE@@", title)
                .replace("@@CSS@@", CSS)
                .replace("@@BODY@@", body_class)
                .replace("@@BAR@@", bar(name))
                .replace("@@MAIN@@", main)
                .replace("@@DASH@@", dash))
    path = os.path.join(HERE, name + ".html")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(document)
    return path


def index_main():
    def wire(kind, charts):
        rest = """
            <div class="wire-row"><div class="wire-rest">Operators · Geography · Providers</div></div>
            <div class="wire-row"><div class="wire-rest">Utilization · Versions · Operating systems</div></div>
            <div class="wire-row"><div class="wire-rest">Families · Exit policy · Exit DNS</div></div>"""
        first = """
            <div class="wire-row">
                <div class="wire-card">Relay counts</div>
                <div class="wire-card">Bandwidth<br>history link</div>
                <div class="wire-card">Uptime<br>history link</div>
            </div>"""
        foot = '<div class="wire-foot">Last updated</div>'
        if kind == "b":
            body = first + charts + rest + foot
        else:
            body = first + rest + charts + foot
        return '<div class="wire layout-%s-wire">%s</div>' % (kind, body)

    bandwidth = '<div class="wire-chart">Bandwidth<br><span>1M  6M  1Y  5Y</span></div>'
    uptime = '<div class="wire-chart uptime">Uptime<br><span>1M  6M  1Y  5Y</span></div>'
    stacked = '<div class="wire-charts">%s%s</div>' % (bandwidth, uptime)
    paired = '<div class="wire-charts">%s%s</div>' % (bandwidth, uptime)
    return """
    <div class="reco">
        <h1>Network history charts</h1>
        <p class="verdict">Put both charts at the bottom of Network Health, stacked, each at the width of the relay chart.</p>
        <div class="choices">
            <div class="choice preferred">
                <h2>A · Bottom, stacked</h2>
                %s
                <p>After the last row of cards and before Last updated. Bandwidth, then uptime. The history links on the Bandwidth Capacity and Relay Uptime cards jump here.</p>
                <p>This is the preferred placement. The charts stay 1080px wide, which is the width they are drawn at, inside the 1400px ribbon.</p>
                <a class="open-layout" href="layout-a.html">Open layout A</a>
            </div>
            <div class="choice">
                <h2>B · Under the first row</h2>
                %s
                <p>The same stack, moved up to sit directly under Relay Counts, Bandwidth Capacity, and Relay Uptime.</p>
                <p>The charts stay next to the numbers they extend. Operators, geography, versions, families, and DNS then start below two tall chart panels.</p>
                <a class="open-layout" href="layout-b.html">Open layout B</a>
            </div>
            <div class="choice">
                <h2>C · Bottom, side by side</h2>
                %s
                <p>The same bottom position as A, with bandwidth and uptime in one row and one shared period control.</p>
                <p>At the ribbon's 1400px each chart is about 680px wide, so the 11px axis type shrinks to about 7px. The bandwidth chart is also much taller than uptime. Below 1100px the columns stack, so the pair only sits side by side on a wide window.</p>
                <a class="open-layout" href="layout-c.html">Open layout C</a>
            </div>
        </div>
        <div class="notes">
            <h2>How the charts behave</h2>
            <p>Open a layout and use the 1M / 6M / 1Y / 5Y links, or a chart's own thumbnails. The switcher is the relay page's CSS, with no JavaScript. A period link changes both charts. A thumbnail changes one.</p>
            <p>The series are illustrative. Throughput is the sum of relay write and read in Gbit/s, with the sum of advertised capacity as the dashed line. Uptime is the mean Running flag. Periods match a relay page: 1 month, 6 months, 1 year, 5 years.</p>
            <p>The charts are not drawn inside the Bandwidth Capacity or Relay Uptime cards. Those cards are a third of the ribbon, narrower than layout C, and they are already the tallest cards in the first row.</p>
        </div>
    </div>""" % (wire("a", stacked), wire("b", stacked), wire("c", paired))


def main():
    heights = write_charts()
    dash = dashboard(heights)
    write_page("index", "layout-index", "Network history chart layouts", index_main())
    main_html = layout_main()
    for name, title in (
        ("layout-a", "Network Health — history at the bottom"),
        ("layout-b", "Network Health — history under the first row"),
        ("layout-c", "Network Health — history side by side"),
    ):
        write_page(name, name, title, main_html, dash)
    for name, height in sorted(heights["bandwidth"].items()):
        print("bandwidth", name, height, "uptime", heights["uptime"][name])


if __name__ == "__main__":
    main()
