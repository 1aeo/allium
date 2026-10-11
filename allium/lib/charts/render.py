"""Relay and operator history charts, written as PNG (or SVG) next to their HTML pages."""

import errno
import hashlib
import logging
import os
import shutil
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

from ..stability_utils import evaluate_overload
from ..time_utils import SECONDS_PER_DAY, SECONDS_PER_HOUR, SECONDS_PER_WEEK, parse_onionoo_timestamp
from .bands import RATIO_SCALE_LO, band_legend_labels, bands_for_role, census_footnote, ratio_strip_data_hi
from .identity import chart_identity, operator_from_contact, role_from_flags
from .outcome import format_day, format_day_span, mbit, subtitles
from .series import (
    MBIT, PERIOD_SPAN, PERIODS, WINDOW, family_key, operator_throughput, peer_medians, points, throughput,
)
from .svg import (
    BLUE, CYAN, DASHDOT, DASHED, DOTTED, GREEN, MUTED, ORANGE, PURPLE, RED, TEXT,
    Panel, Svg, legend, nice_ticks, text_width, view_end,
)

WIDTH, LEFT = 1080, 138
PLOT_WIDTH = WIDTH - LEFT - 24
logger = logging.getLogger(__name__)


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
        units = ((SECONDS_PER_WEEK, "week"), (SECONDS_PER_DAY, "day"), (SECONDS_PER_HOUR, "hour"))
        unit = next(((s, n) for s, n in units if interval and interval % s == 0), None)
        caption = period.upper() + (" · {}-{}".format(interval // unit[0], unit[1]) if unit else "")
        y += 20
        svg.text(LEFT + PLOT_WIDTH / 2, y, caption, 13, MUTED, "middle")
    if footnote:
        y += 24
        svg.text(12, y, footnote, 11, MUTED)
    return y + 12


def _spike_callout(svg, panel, rows, bands, clear_of, period):
    """Label the highest write/read day above this role's p98 (with its neighbours) on the throughput lines.

    The label sits right of the peak (left when it would not fit) in the band the y range keeps
    free under the legend, whose bottom is ``clear_of``.
    """
    high = [row for row in rows if row[3] > bands["invest_hi"]]
    if not high:
        return
    peak = max(high, key=lambda row: row[3])
    by_day = {row[0].date(): row for row in high}
    day = peak[0].date()
    run = sorted([peak] + [by_day[d] for d in (day - timedelta(days=1), day + timedelta(days=1)) if d in by_day])
    top = ratio_strip_data_hi(bands)
    label = "{} · write/read {} · {}".format(
        format_day_span([row[0].date() for row in run], year=period in ("1y", "5y")),
        " / ".join("{:.2f}".format(row[3]) for row in run),
        "off the {:.2f} scale".format(top) if peak[3] > top else "beyond this role’s p98",
    )
    x, y = panel.x(peak[0]), panel.y(peak[1])
    width = text_width(label, 11.5, bold=True) + 14
    box_x = x + 19 if x + 19 + width <= svg.width - 12 else max(12, x - 19 - width)
    svg.line(x, y, min(max(x, box_x), box_x + width), clear_of + 30, MUTED, 1)
    svg.rect(box_x, clear_of + 6, width, 24, "#161a20", stroke=RED, rx=5)
    svg.text(box_x + 7, clear_of + 22.5, label, 11.5, RED, bold=True)


def _restarted(restart, ts):
    """The restart legend entry when the restart is on the time axis, else nothing."""
    if restart and ts[0] <= restart <= view_end(ts):
        return [("line", PURPLE, DASHDOT, "Last restarted  " + format_day(restart))]
    return []


def bandwidth_chart(period, series, advertised, bands, identity, restart=None, overload=None,
                    overlays=None, family_n=0, operator=False):
    """Throughput panel over a write/read panel against the role's frozen bands."""
    ts, write, read, interval = series
    ratios = [w / r if r else None for w, r in zip(write, read)]
    rows = [row for row in zip(ts, write, read, ratios) if row[3] is not None]
    overlays = overlays or {}
    thru_sub, ratio_sub = subtitles(rows, advertised, overlays, bands, period, interval)
    span = PERIOD_SPAN[period] + ("" if operator else "  ·  " + bands["role"])
    restarted = _restarted(restart, ts)
    svg = Svg(WIDTH)

    y = _header(svg, identity, "Throughput · " + span, thru_sub)
    ceiling = max(max(write), max(read), advertised) or 1.0
    # Headroom for the legend (two rows when overloaded) and, with a spike, its callout below it.
    spike = any(row[3] > bands["invest_hi"] for row in rows)
    headroom = (1.45 if overload else 1.34) if spike else (1.28 if overload else 1.26)
    top = Panel(svg, "t", LEFT, y, PLOT_WIDTH, 290, ts, 0, ceiling * headroom)
    top.yaxis(nice_ticks(top.yspan), "Throughput (Mbit/s)")
    top.xaxis(period, ts, labels=False)
    entries = [("line", GREEN, None, "Write (outbound)"), ("line", BLUE, None, "Read (inbound)")]
    if advertised:
        top.hline(advertised, ORANGE, 1.3, DASHED)
        entries.append(("line", ORANGE, DASHED, "Advertised  {} Mbit/s".format(mbit(advertised))))
    if restarted:
        top.vline(restart, PURPLE, 1.4, DASHDOT)
    top.series(ts, write, GREEN, 2.4)
    top.series(ts, read, BLUE, 1.7)
    y += 8 + legend(svg, LEFT + 8, y + 8, [entries + restarted] + ([[("marker", RED, None, overload)]] if overload else []))
    _spike_callout(svg, top, rows, bands, y, period)

    y = _header(svg, "", "Write / read · " + span, ratio_sub, top.top + top.height + 8)
    entries = [("line", TEXT, None, "This operator" if operator else "This relay")]
    if overlays.get("family"):
        entries.append(("line", MUTED, DOTTED, "Operator Family (median, n={})".format(family_n)))
    if overlays.get("role"):
        entries.append(("line", CYAN, DASHED, "Peers (network median)"))
    labels = band_legend_labels(bands)
    bands_row = [("patch", GREEN, 0.25, labels[0]), ("patch", ORANGE, 0.22, labels[1]), ("patch", RED, 0.22, labels[2])]
    y += 6 + legend(svg, LEFT, y, [entries + restarted, bands_row])
    tlo, thi, ilo, ihi = bands["typical_lo"], bands["typical_hi"], bands["invest_lo"], bands["invest_hi"]
    ylo, yhi = RATIO_SCALE_LO, ratio_strip_data_hi(bands)
    strip = Panel(svg, "r", LEFT, y, PLOT_WIDTH, 150, ts, ylo, yhi)
    for lo, hi, color, opacity in ((0.45, ilo, RED, 0.08), (ilo, tlo, ORANGE, 0.07), (tlo, thi, GREEN, 0.14),
                                   (thi, ihi, ORANGE, 0.07), (ihi, yhi, RED, 0.08)):
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
    clipped = [None if v is None else min(max(v, ylo), yhi) for v in ratios]
    strip.series(ts, clipped, TEXT, 2.2)
    strip.series(ts, [v if r is not None and not ilo <= r <= ihi else None for v, r in zip(clipped, ratios)], RED, 2.4)
    for t, r in zip(ts, ratios):
        if r is not None and not ylo <= r <= yhi:
            x, edge = strip.x(t), strip.y(yhi if r > yhi else ylo)
            svg.path("M%.1f %.1fl5 %gh-10z" % (x, edge, 8 if r > yhi else -8), RED, 1, fill=RED)
    if restarted:
        strip.vline(restart, PURPLE, 1.4, DASHDOT)
    return svg.finish(_footer(svg, strip, period, interval, census_footnote(bands)))


def uptime_chart(period, ts, percent, interval, identity, restart, average):
    """Running-flag uptime percent over one period, its legend above the plot."""
    svg = Svg(WIDTH)
    subtitle = "Average {:.1f}%  ·  Onionoo Running flag".format(average) if average else ""
    y = _header(svg, identity, "Uptime · " + PERIOD_SPAN[period], subtitle)
    restarted = _restarted(restart, ts)
    y += 8 + legend(svg, LEFT, y, [[("line", GREEN, None, "Running flag")] + restarted])
    panel = Panel(svg, "u", LEFT, y, PLOT_WIDTH, 220, ts, 0, 105)
    panel.yaxis(range(0, 101, 20), "Uptime (%)")
    panel.xaxis(period, ts)
    if restarted:
        panel.vline(restart, PURPLE, 1.4, DASHDOT)
    panel.series(ts, percent, GREEN, 2.2)
    return svg.finish(_footer(svg, panel, period, interval))


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
    last = datetime.fromtimestamp(max(stamps) / 1000.0, timezone.utc)
    return "currently overloaded · last report {}, {:%H:%M} UTC".format(format_day(last), last)


class ChartWriter(object):
    """Writes relay and operator charts next to their pages.

    Built once in the parent process (the peer medians need every relay),
    then shared with the forked page workers.

    PNG charts are kept in ``cache_dir`` under a hash of their SVG text, which
    describes the whole drawing: a chart that did not change since the last
    build (most 6M/1Y/5Y charts, and 1M ones between Onionoo's 4-hourly
    points) is hard-linked from there instead of drawn again. A hit marks
    the file's access time and keeps its modification time, so ``rsync -a``
    and HTTP caches see an unchanged chart as unchanged. ``sweep()`` drops
    the ones this build did not use (all of them in an SVG build).
    """

    _copy_warned = False

    def __init__(self, relay_set, image_format="png", cache_dir=None):
        from ..operator_analysis import history_maps
        from ..workers import CACHE_DIR
        self.ext, self.raster, self.started = image_format, None, time.time()
        self.cache_root = self.cache = cache_dir or os.path.join(CACHE_DIR, "charts")
        if image_format == "png":
            from . import raster  # cairocffi, numpy, zlib-ng
            self.raster = raster
            # One directory per drawing (code, cairo and fonts): the others can never be hit again, so they go
            # now, before this build fills its own.
            self.cache = os.path.join(self.cache_root, hashlib.blake2b(raster.VERSION, digest_size=8).hexdigest())
            os.makedirs(self.cache, exist_ok=True)
            for entry in os.scandir(self.cache_root):
                if entry.is_dir():
                    if entry.path != self.cache:
                        shutil.rmtree(entry.path, ignore_errors=True)
                else:
                    os.remove(entry.path)
        self.relays = relay_set.json["relays"]
        self.uptime, self.bandwidth = history_maps(relay_set)
        published = parse_onionoo_timestamp(
            (relay_set.bandwidth_data or relay_set.uptime_data or {}).get("relays_published"))
        self.since = {period: published - WINDOW[period] if published else None for _key, period in PERIODS}
        self.role_medians, self.family_medians = peer_medians(self.relays, self.bandwidth, self.since["1m"])

    def _save(self, directory, name, draw, *args):
        """Write ``name`` plus the format's extension; return its height (0 when skipped, so the page can reserve
        the space). No drawable history, or a malformed one, skips that chart instead of failing the page."""
        path = os.path.join(directory, "%s.%s" % (name, self.ext))
        try:
            svg = draw(*args)
            text = svg.document().encode("utf-8") if svg else b""
        except Exception:  # noqa: BLE001
            return 0
        if not text:
            return 0
        if not self.raster:
            with open(path, "wb") as handle:
                handle.write(text)
            return svg.height
        try:
            self._png(svg, text, path)
        except Exception as error:  # noqa: BLE001 -- unlike odd history, this is the build host's problem
            logger.warning("PNG conversion failed for %s: %s", path, error)
            return 0
        return svg.height

    def _png(self, svg, text, path):
        cached = os.path.join(self.cache, hashlib.blake2b(text + self.raster.VERSION, digest_size=16).hexdigest() + ".png")
        try:  # a hit: mark it used for sweep() in the access time, keep the modification time
            os.utime(cached, ns=(time.time_ns(), os.stat(cached).st_mtime_ns))
        except FileNotFoundError:
            data, partial = self.raster.png(svg), "%s.%d" % (cached, os.getpid())
            with open(partial, "wb") as handle:
                handle.write(data)
            os.replace(partial, cached)
        # A page written again (e.g. by the sequential retry after a worker died) finds its old link here:
        # remove it, never write through it into a cache file.
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        try:
            os.link(cached, path)
        except OSError as error:  # e.g. the output is on another filesystem
            if error.errno == errno.EXDEV and not ChartWriter._copy_warned:
                ChartWriter._copy_warned = True
                logger.warning("--out is not on the filesystem of %s: copying every PNG chart (~10 GB) instead of "
                               "linking it; build next to it to save that", self.cache_root)
            shutil.copy2(cached, path)

    def sweep(self):
        """Delete cached PNGs no chart of this build used (call once every page is written)."""
        if not self.raster:
            shutil.rmtree(self.cache_root, ignore_errors=True)
            return
        for entry in os.scandir(self.cache):
            try:  # another build sharing the cache may remove or rename files meanwhile
                if entry.stat().st_atime < self.started - 60:
                    os.remove(entry.path)
            except FileNotFoundError:
                pass

    def relay(self, relay, directory):
        """Write ``bandwidth-<period>`` and ``uptime-<period>`` charts; return ``{period: height}`` for each."""
        common = dict(advertised=(relay.get("advertised_bandwidth") or 0) * MBIT,
                      bands=bands_for_role(role_from_flags(relay.get("flags"))),
                      identity=chart_identity(relay.get("nickname"), operator_from_contact(relay.get("contact"))),
                      restart=parse_onionoo_timestamp(relay.get("last_restarted")), overload=_overload_text(relay))
        bandwidth, uptime = {}, {}
        for key, period in PERIODS:
            bandwidth[period] = self._save(directory, "bandwidth-" + period, self._relay_bandwidth, relay, key, period,
                                           common)
            uptime[period] = self._save(directory, "uptime-" + period, self._relay_uptime, relay, key, period, common)
        return {p: h for p, h in bandwidth.items() if h}, {p: h for p, h in uptime.items() if h}

    def _relay_bandwidth(self, relay, key, period, common):
        series = throughput(self.bandwidth.get(relay["fingerprint"]), key, self.since[period])
        if not series:
            return None
        if period != "1m":  # peer and family medians are 1M only
            return bandwidth_chart(period, series, **common)
        role = self.role_medians.get(common["bands"]["role"], {})
        overlays = {"role": {t: role[t] for t in series[0] if t in role}}
        family_n, family = self.family_medians.get(family_key(relay), (0, None))
        if family:
            overlays["family"] = {t: family[t] for t in series[0] if t in family}
        return bandwidth_chart(period, series, overlays=overlays, family_n=family_n, **common)

    def _relay_uptime(self, relay, key, period, common):
        block = ((self.uptime.get(relay["fingerprint"]) or {}).get("uptime") or {}).get(key) or {}
        percent = points(block, 100.0, self.since[period])
        if len(percent) < 2:
            return None
        ts = sorted(percent)
        # Average what is drawn (factor applied, window clipped); like the site's uptime figures,
        # only from 30 points and above 1%.
        average = sum(percent.values()) / len(percent)
        return uptime_chart(period, ts, [percent[t] for t in ts], int(block.get("interval") or 0), common["identity"],
                            common["restart"], average if len(percent) >= 30 and average > 1.0 else 0)

    def contact(self, member_indexes, directory):
        """Write ``bandwidth-<period>`` charts for an operator's summed members; return ``{period: height}``."""
        members = [self.relays[i] for i in member_indexes]
        # Relays without contact info share one hash, but they are not an operator.
        if not any((relay.get("contact") or "").strip() for relay in members):
            return {}
        operator = next((host for host in (operator_from_contact(r.get("contact")) for r in members) if host), "")
        # Operators mix roles: judge write/read against the members' most common role.
        bands = bands_for_role(Counter(role_from_flags(r.get("flags")) for r in members).most_common(1)[0][0])
        identity = operator or "Operator"
        heights = {period: self._save(directory, "bandwidth-" + period, self._contact_bandwidth, members, key, period,
                                      bands, identity) for key, period in PERIODS}
        return {period: height for period, height in heights.items() if height}

    def _contact_bandwidth(self, members, key, period, bands, identity):
        series, summed = operator_throughput(members, self.bandwidth, key, self.since[period])
        if not series:
            return None
        advertised = sum(relay.get("advertised_bandwidth") or 0 for relay in summed) * MBIT
        return bandwidth_chart(period, series, advertised, bands, identity, operator=True)
