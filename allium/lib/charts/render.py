"""Relay and operator history charts, written as SVG next to their HTML pages."""

import os
from collections import Counter
from datetime import datetime, timedelta, timezone

from ..stability_utils import evaluate_overload
from ..time_utils import parse_onionoo_timestamp
from .bands import (
    RATIO_SCALE_HI, RATIO_SCALE_LO, band_legend_labels, bands_for_flags, bands_for_role,
    census_footnote, ratio_strip_data_hi,
)
from .identity import chart_identity, operator_from_contact, role_from_flags
from .outcome import format_day, format_day_span, format_day_time, subtitles
from .series import (
    MBIT, PERIOD_SPAN, PERIODS, WINDOW, family_key, operator_throughput, peer_medians, points, throughput,
)
from .svg import (
    BLUE, CYAN, DASHDOT, DASHED, DOTTED, GREEN, MUTED, ORANGE, PURPLE, RED, TEXT,
    Panel, Svg, legend, nice_ticks, text_width,
)

WIDTH, LEFT = 1080, 138
PLOT_WIDTH = WIDTH - LEFT - 24
SHORT = {"1m": "1M", "6m": "6M", "1y": "1Y", "5y": "5Y"}


def _header(svg, identity, title, subtitle, y=10):
    """Identity, bold title and grey subtitle lines. Returns the y below them."""
    if identity:
        y += 22
        svg.text(LEFT, y, identity, 15, GREEN, bold=True)
    y += 26
    svg.text(LEFT, y, title, 17, bold=True)
    if subtitle:
        y += 20
        svg.text(LEFT, y, subtitle, 12, MUTED)
    return y + 12


def _footer(svg, panel, period, interval, footnote=""):
    """Date-axis caption (``6M · 1-day``) under longer periods, then the footnote. Returns the height."""
    y = panel.top + panel.height + 38
    if period != "1m":
        unit = next(((s, n) for s, n in ((604800, "week"), (86400, "day"), (3600, "hour")) if interval % s == 0), None)
        caption = "{} · {}-{}".format(SHORT[period], interval // unit[0], unit[1]) if interval and unit else SHORT[period]
        y += 20
        svg.text(LEFT + PLOT_WIDTH / 2, y, caption, 13, MUTED, "middle")
    if footnote:
        y += 24
        svg.text(12, y, footnote, 11, MUTED)
    return y + 12


def _spike_callout(svg, panel, rows, bands, clear_of):
    """Label the highest write/read day above this role's p98 (with its neighbours) on the throughput lines.

    The label sits above the peak, or below it when it would reach the legend (bottom at ``clear_of``).
    """
    high = [row for row in rows if row[3] > bands["invest_hi"]]
    if not high:
        return
    peak = max(high, key=lambda row: row[3])
    by_day = {row[0].date(): row for row in high}
    day = peak[0].date()
    run = sorted([peak] + [by_day[d] for d in (day - timedelta(days=1), day + timedelta(days=1)) if d in by_day])
    label = "{} · write/read {} · {}".format(
        format_day_span([row[0].date() for row in run]),
        " / ".join("{:.2f}".format(row[3]) for row in run),
        "off the {:.2f} scale".format(RATIO_SCALE_HI) if peak[3] > RATIO_SCALE_HI else "beyond this role’s p98",
    )
    x, y = panel.x(peak[0]), panel.y(peak[1])
    width = text_width(label, 11.5, bold=True) + 14
    left = (x - panel.left) * 1.03 > 0.62 * panel.width  # late peaks get the label on their left
    box_x = x - 19 - width if left else x + 19
    box_y = y - 44 if y - 48 > clear_of else y + 20
    svg.line(x, y, box_x + (width if left else 0), box_y + 12, MUTED, 1)
    svg.rect(box_x, box_y, width, 24, "#161a20", stroke=RED, rx=5)
    svg.text(box_x + 7, box_y + 16.5, label, 11.5, RED, bold=True)


def bandwidth_chart(period, series, advertised, bands, identity, title_role, restart=None, overload=None,
                    overlays=None, family_n=0, scope="relay"):
    """Throughput panel over a write/read panel against the role's frozen bands."""
    ts, write, read, interval = series
    rows = [(t, w, r, w / r) for t, w, r in zip(ts, write, read) if r]
    overlays = overlays or {}
    thru_sub, ratio_sub = subtitles(rows, advertised, overlays, bands, period, interval)
    span = PERIOD_SPAN[period] + ("  ·  " + bands["role"] if title_role else "")
    restart = restart if restart and ts[0] <= restart <= ts[-1] else None
    svg = Svg(WIDTH)

    y = _header(svg, identity, "Throughput · " + span, thru_sub)
    ceiling = max(max(write), max(read), advertised) or 1.0
    top = Panel(svg, "t", LEFT, y, PLOT_WIDTH, 290, ts, 0, ceiling * (1.28 if overload else 1.26))
    top.yaxis(nice_ticks(top.yspan), "Throughput (Mbit/s)")
    top.xaxis(period, ts, labels=False)
    if advertised:
        top.hline(advertised, ORANGE, 1.3, DASHED)
    if restart:
        top.vline(restart, PURPLE, 1.4, DASHDOT)
    top.series(ts, write, GREEN, 2.4)
    top.series(ts, read, BLUE, 1.7)
    entries = [("line", GREEN, None, "Write (outbound)"), ("line", BLUE, None, "Read (inbound)")]
    if advertised:
        entries.append(("line", ORANGE, DASHED, "Advertised  {:.0f} Mbit/s".format(advertised)))
    if restart:
        entries.append(("line", PURPLE, DASHDOT, "Last restarted  " + format_day(restart)))
    y += 8 + legend(svg, LEFT + 8, y + 8, [entries] + ([[("marker", RED, None, overload)]] if overload else []))
    _spike_callout(svg, top, rows, bands, y)

    y = _header(svg, "", "Write / read · " + span, ratio_sub, top.top + top.height + 8)
    entries = [("line", TEXT, None, "This operator" if scope == "operator" else "This relay")]
    if overlays.get("family"):
        entries.append(("line", MUTED, DOTTED, "Operator Family (median, n={})".format(family_n)))
    if overlays.get("role"):
        entries.append(("line", CYAN, DASHED, "Peers (network median)"))
    if restart:
        entries.append(("line", PURPLE, DASHDOT, "Last restarted  " + format_day(restart)))
    labels = band_legend_labels(bands)
    y += 6 + legend(svg, LEFT, y, [entries, [("patch", GREEN, 0.25, labels[0]), ("patch", ORANGE, 0.22, labels[1]),
                                             ("patch", RED, 0.22, labels[2])]])
    tlo, thi, ilo, ihi = bands["typical_lo"], bands["typical_hi"], bands["invest_lo"], bands["invest_hi"]
    ylo, yhi = RATIO_SCALE_LO, ratio_strip_data_hi(bands)
    strip = Panel(svg, "r", LEFT, y, PLOT_WIDTH, 150, ts, ylo, yhi)
    for lo, hi, color, opacity in ((0.45, ilo, RED, 0.12), (ilo, tlo, ORANGE, 0.11), (tlo, thi, GREEN, 0.14),
                                   (thi, ihi, ORANGE, 0.11), (ihi, yhi, RED, 0.12)):
        strip.hband(lo, hi, color, opacity)
    # Name the typical band at 1.0 (or its own tick) and the top Investigate shelf (at 1.5 or above it).
    styles = {ylo: ("%.1f" % ylo, MUTED, False), 1.0: ("1.0", MUTED, False), 1.5: ("1.5", MUTED, False)}
    if abs((tlo + thi) / 2 - 1.0) < 0.10:
        styles[1.0] = ("1.0   p10–p90", GREEN, True)
    else:
        styles[(tlo + thi) / 2] = ("p10–p90", GREEN, True)
    p98 = min(yhi - 0.06, max(ihi + 0.05, (ihi + yhi) / 2))
    if ihi <= 1.5 or abs(p98 - 1.5) <= 0.12:
        styles[1.5] = ("1.5   >p98", RED, True)
    elif p98 > 1.5:
        styles[p98] = (">p98", RED, True)
    strip.yaxis(sorted(styles), "Write / read", styles=styles)
    strip.xaxis(period, ts)
    strip.hline(1.0, GREEN, 1.0, DASHED)
    for key, color, dash in (("role", CYAN, DASHED), ("family", MUTED, DOTTED)):
        if key in overlays:
            strip.series(ts, [overlays[key].get(t) for t in ts], color, 1.4, dash)
    ratios = [w / r if r else None for w, r in zip(write, read)]
    clipped = [None if v is None else min(max(v, ylo), yhi) for v in ratios]
    strip.series(ts, clipped, TEXT, 2.2)
    strip.series(ts, [v if r is not None and not ilo <= r <= ihi else None for v, r in zip(clipped, ratios)], RED, 2.4)
    for t, r in zip(ts, ratios):
        if r is not None and not ylo <= r <= yhi:
            x, edge = strip.x(t), strip.y(yhi if r > yhi else ylo)
            svg.path("M%.1f %.1fl5 %gh-10z" % (x, edge, 8 if r > yhi else -8), RED, 1, fill=RED)
    if restart:
        strip.vline(restart, PURPLE, 1.4, DASHDOT)
    return svg.document(_footer(svg, strip, period, interval, census_footnote(bands)))


def uptime_chart(period, ts, percent, interval, identity, restart, average):
    """Running-flag uptime percent over one period."""
    restart = restart if restart and ts[0] <= restart <= ts[-1] else None
    svg = Svg(WIDTH)
    subtitle = "Average {:.1f}%  ·  Onionoo Running flag".format(average) if average else ""
    y = _header(svg, identity, "Uptime · " + PERIOD_SPAN[period], subtitle)
    panel = Panel(svg, "u", LEFT, y, PLOT_WIDTH, 240, ts, 0, 112)
    panel.yaxis(range(0, 101, 20), "Uptime (%)")
    panel.xaxis(period, ts)
    if restart:
        panel.vline(restart, PURPLE, 1.4, DASHDOT)
    panel.series(ts, percent, GREEN, 2.2)
    entries = [("line", GREEN, None, "Running flag")]
    if restart:
        entries.append(("line", PURPLE, DASHDOT, "Last restarted  " + format_day(restart)))
    if average:
        entries.append(("blank", None, None, "Average  {:.1f}%".format(average)))
    legend(svg, LEFT + 8, y + 8, [entries])
    return svg.document(_footer(svg, panel, period, interval))


def _overload_text(relay):
    """Legend text while the relay is overloaded (relays.py's verdict), with the newest report time."""
    if not relay.get("stability_is_overloaded"):
        return None
    facts = evaluate_overload(relay)
    stamps = [facts["general_ts"] if facts["general_active"] else None,
              (facts["ratelimits"] or {}).get("timestamp"), facts["fd_timestamp"]]
    stamps = [stamp for stamp in stamps if stamp]
    if not stamps:
        return "currently overloaded"
    return "currently overloaded · last report " + format_day_time(
        datetime.fromtimestamp(max(stamps) / 1000.0, timezone.utc))


class ChartWriter(object):
    """Writes relay and operator charts next to their pages.

    Built once in the parent process (the peer medians need every relay),
    then shared with the forked page workers.
    """

    def __init__(self, relay_set):
        from ..operator_analysis import history_maps
        self.relays = relay_set.json["relays"]
        self.uptime, self.bandwidth = history_maps(relay_set)
        published = parse_onionoo_timestamp(
            (relay_set.bandwidth_data or relay_set.uptime_data or {}).get("relays_published"))
        self.since = {period: published - WINDOW[period] if published else None for _key, period in PERIODS}
        self.role_medians, self.family_medians = peer_medians(self.relays, self.bandwidth, self.since["1m"])

    @staticmethod
    def _save(directory, name, draw, *args):
        """Write one chart. No drawable history, or a malformed one, skips that chart instead of failing the page."""
        try:
            svg = draw(*args)
        except Exception:  # noqa: BLE001
            svg = None
        if svg:
            with open(os.path.join(directory, name), "w", encoding="utf-8") as handle:
                handle.write(svg)
        return bool(svg)

    def relay(self, relay, directory):
        """Write ``bandwidth-<period>.svg`` and ``uptime-<period>.svg``; return the periods drawn for each."""
        bands = bands_for_flags(relay.get("flags"))
        identity = chart_identity(relay.get("nickname"), operator_from_contact(relay.get("contact")))
        restart = parse_onionoo_timestamp(relay.get("last_restarted"))
        common = dict(advertised=(relay.get("advertised_bandwidth") or 0) * MBIT, bands=bands, identity=identity,
                      title_role=True, restart=restart, overload=_overload_text(relay))
        bandwidth, uptime = [], []
        for key, period in PERIODS:
            # Every period needs the 1M history; peers and family medians are 1M-aligned only.
            if (period == "1m" or bandwidth) and self._save(
                    directory, "bandwidth-%s.svg" % period, self._relay_bandwidth, relay, key, period, common):
                bandwidth.append(period)
            if self._save(directory, "uptime-%s.svg" % period, self._relay_uptime, relay, key, period, identity,
                          restart):
                uptime.append(period)
        return tuple(bandwidth), tuple(uptime)

    def _relay_bandwidth(self, relay, key, period, common):
        series = throughput(self.bandwidth.get(relay["fingerprint"]), key, self.since[period])
        if not series:
            return None
        if period != "1m":
            return bandwidth_chart(period, series, **common)
        role = self.role_medians.get(common["bands"]["role"], {})
        overlays = {"role": {t: role[t] for t in series[0] if t in role}}
        family_n, family = self.family_medians.get(family_key(relay), (0, None))
        if family:
            overlays["family"] = {t: family[t] for t in series[0] if t in family}
        return bandwidth_chart(period, series, overlays=overlays, family_n=family_n, **common)

    def _relay_uptime(self, relay, key, period, identity, restart):
        block = ((self.uptime.get(relay["fingerprint"]) or {}).get("uptime") or {}).get(key) or {}
        percent = points(block, 100.0, self.since[period])
        if len(percent) < 2:
            return None
        ts = sorted(percent)
        return uptime_chart(period, ts, [percent[t] for t in ts], int(block.get("interval") or 0), identity,
                            restart, (relay.get("uptime_percentages") or {}).get(key))

    def contact(self, member_indexes, directory):
        """Write ``bandwidth-<period>.svg`` for an operator's summed members; return the periods drawn."""
        members = [self.relays[i] for i in member_indexes]
        # Relays without contact info share one hash, but they are not an operator.
        if not any((relay.get("contact") or "").strip() for relay in members):
            return ()
        operator = next((host for host in (operator_from_contact(r.get("contact")) for r in members) if host), "")
        # Operators mix roles: judge write/read against the members' most common role.
        bands = bands_for_role(Counter(role_from_flags(r.get("flags")) for r in members).most_common(1)[0][0])
        identity = chart_identity(operator or "Operator", operator)
        return tuple(period for key, period in PERIODS if self._save(
            directory, "bandwidth-%s.svg" % period, self._contact_bandwidth, members, key, period, bands, identity))

    def _contact_bandwidth(self, members, key, period, bands, identity):
        series, summed = operator_throughput(members, self.bandwidth, key, self.since[period])
        if not series:
            return None
        advertised = sum(relay.get("advertised_bandwidth") or 0 for relay in summed) * MBIT
        return bandwidth_chart(period, series, advertised, bands, identity, title_role=False, scope="operator")
