"""Relay and operator history charts, written as PNG (or SVG) next to their HTML pages."""

import errno
import hashlib
import logging
import marshal
import os
import re
import shutil
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

from ..stability_utils import evaluate_overload
from ..time_utils import SECONDS_PER_DAY, SECONDS_PER_HOUR, SECONDS_PER_WEEK, parse_onionoo_timestamp
from .bands import RATIO_SCALE_LO, band_legend_labels, bands_for_role, census_footnote, ratio_strip_data_hi, role_from_flags
from .identity import chart_identity, operator_from_contact, operator_identity
from .outcome import YEAR_PERIODS, format_day, format_day_span, mbit, ratio_subtitle, ratio_text, throughput_subtitle
from .series import (
    MBIT, PERIOD_SPAN, PERIODS, WINDOW, active_ratio, family_key, operator_throughput, peer_medians, points,
    throughput,
)
from .svg import (
    AXIS, BLUE, CALLOUT_BG, CYAN, DASHDOT, DASHED, DOTTED, GREEN, MUTED, ORANGE, PURPLE, RED, TEXT,
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


def _spike_callout(svg, panel, high, yhi, clear_of, period, bands, interval):
    """Label the highest of the ``high`` write/read rows (above the role's p98), with its neighbouring slots
    (``interval`` apart), on the throughput lines; ``yhi`` is the top of the write/read strip's scale.

    The label sits right of the peak (left when it would not fit) in the band the y range keeps
    free under the legend, whose bottom is ``clear_of``.
    """
    peak, step = max(high, key=lambda row: row[3]), timedelta(seconds=interval or SECONDS_PER_DAY)
    by_time = {row[0]: row for row in high}
    run = sorted([peak] + [by_time[t] for t in (peak[0] - step, peak[0] + step) if t in by_time])
    label = "{} · write/read {} · {}".format(
        format_day_span([row[0] for row in run], step, year=period in YEAR_PERIODS),
        " / ".join(ratio_text(row[3], yhi, bands["invest_hi"]) for row in run),
        "off the {:.2f} scale".format(yhi) if peak[3] > yhi else "beyond the {} p98".format(bands["role"]),
    )
    x, y = panel.x(peak[0]), panel.y(peak[1])
    width = text_width(label, 11.5, bold=True) + 14
    box_x = x + 19 if x + 19 + width <= svg.width - 12 else max(12, x - 19 - width)
    svg.line(x, y, min(max(x, box_x), box_x + width), clear_of + 30, MUTED, 1)
    svg.rect(box_x, clear_of + 6, width, 24, CALLOUT_BG, stroke=RED, rx=5)
    svg.text(box_x + 7, clear_of + 22.5, label, 11.5, RED, bold=True)


def _restart_entry(restart, ts, end):
    """``[]``, or the restart's legend entry when the restart is on the time axis."""
    if restart and ts[0] <= restart <= view_end(ts, end):
        return [("line", PURPLE, DASHDOT, "Last restarted  " + format_day(restart))]
    return []


def bandwidth_chart(period, series, advertised, bands, identity, restart=None, overload=None,
                    overlays=None, family_n=0, operator=False, end=None):
    """Throughput panel over a write/read panel against the role's frozen bands.

    ``series`` is ``(ts, write, read, interval)`` in Mbit/s (``series.throughput``); ``overlays`` maps
    ``"role"`` / ``"family"`` to ``{ts: median write/read}`` (1M relay charts only; ``family_n`` relays).
    ``end`` is the period window's end (``relays_published``): the time axis runs to it at least.
    """
    ts, write, read, interval = series
    # Write/read only on days with enough traffic to compare, the band census's cut: below it the ratio is noise.
    ratios = [active_ratio(w, r) for w, r in zip(write, read)]
    rows = [row for row in zip(ts, write, read, ratios) if row[3] is not None]
    overlays = (overlays or {}) if rows else {}  # no day of this relay's to hold the medians against
    for most in (3, 0, -1):  # days, then date ranges with counts, then counts only: whichever fits the plot
        ratio_sub = ratio_subtitle(rows, overlays, bands, period, interval, most)
        if text_width(ratio_sub, 12) <= PLOT_WIDTH:
            break
    span = PERIOD_SPAN[period]
    role = "  ·  vs {} band".format(bands["role"]) if operator else "  ·  " + bands["role"]
    restarted = _restart_entry(restart, ts, end)
    svg = Svg(WIDTH)

    y = _header(svg, identity, "Throughput · " + span + ("" if operator else role),
                throughput_subtitle(ts, write, advertised, period))
    ceiling = max(max(write), max(read), advertised) or 1.0
    # Headroom for the legend (two rows when overloaded) and, with a spike, its callout below it.
    high = [row for row in rows if row[3] > bands["invest_hi"]]
    headroom = (1.45 if overload else 1.34) if high else (1.28 if overload else 1.26)
    top = Panel(svg, "t", LEFT, y, PLOT_WIDTH, 290, ts, 0, ceiling * headroom, end, interval)
    top.yaxis(nice_ticks(top.yspan), "Throughput (Mbit/s)")
    top.xaxis(period, labels=False)
    entries = [("line", GREEN, None, "Write (outbound)"), ("line", BLUE, None, "Read (inbound)")]
    if advertised:
        top.hline(advertised, ORANGE, 1.3, DASHED)
        entries.append(("line", ORANGE, DASHED, "Advertised  {} Mbit/s".format(mbit(advertised))))
    if restarted:
        top.vline(restart, PURPLE, 1.4, DASHDOT)
    top.series(write, GREEN, 2.4)
    top.series(read, BLUE, 1.7)
    y += 8 + legend(svg, LEFT + 8, y + 8, [entries + restarted] + ([[("marker", RED, None, overload)]] if overload else []))
    ylo, yhi = RATIO_SCALE_LO, ratio_strip_data_hi(bands)
    if high:
        _spike_callout(svg, top, high, yhi, y, period, bands, interval)

    y = _header(svg, "", "Write / read · " + span + role, ratio_sub, top.top + top.height + 8)
    entries = [("line", TEXT, None, "This operator" if operator else "This relay")] if rows else []
    if overlays.get("family"):
        entries.append(("line", MUTED, DOTTED, "Operator Family (median, n={})".format(family_n)))
    if overlays.get("role"):
        entries.append(("line", CYAN, DASHED, "Peers (network median)"))
    labels = band_legend_labels(bands)
    bands_row = [("patch", GREEN, 0.25, labels[0]), ("patch", ORANGE, 0.22, labels[1]), ("patch", RED, 0.22, labels[2])]
    y += 6 + legend(svg, LEFT, y, [row for row in (entries + restarted, bands_row) if row])
    tlo, thi, ilo, ihi = bands["typical_lo"], bands["typical_hi"], bands["invest_lo"], bands["invest_hi"]
    strip = Panel(svg, "r", LEFT, y, PLOT_WIDTH, 150, ts, ylo, yhi, end, interval)
    for lo, hi, color, opacity in ((ylo, ilo, RED, 0.08), (ilo, tlo, ORANGE, 0.07), (tlo, thi, GREEN, 0.14),
                                   (thi, ihi, ORANGE, 0.07), (ihi, yhi, RED, 0.08)):
        strip.hband(lo, hi, color, opacity)
    # Plain labels on the fixed grid lines; the typical band and the top Investigate shelf are named in their own
    # ranges (beside a grid label where the range is too narrow to clear it).
    ticks = (ylo, 1.0, 1.5)
    strip.yaxis(ticks, "Write / read", fmt="{:.1f}")
    strip.band_label("p10–p90", tlo, thi, GREEN, ticks)
    strip.band_label(">p98", ihi, yhi, RED, ticks)
    strip.xaxis(period)
    strip.hline(1.0, AXIS, 1.0)  # write = read: its grid line, drawn brighter
    for key, color, dash in (("role", CYAN, DASHED), ("family", MUTED, DOTTED)):
        if overlays.get(key):
            strip.series([overlays[key].get(t) for t in ts], color, 1.4, dash)
    clipped = [None if v is None else min(max(v, ylo), yhi) for v in ratios]
    strip.series(clipped, TEXT, 2.2)
    # Red where the line leaves this role's p2–p98: the line's segments at an out-of-band day, drawn again clipped
    # to the strip above ihi and below ilo; and a dot on a day out of band alone, as its red is only a short tip.
    out = [r is not None and not ilo <= r <= ihi for r in ratios]
    if any(out):
        near = [v if any(out[max(i - 1, 0):i + 2]) else None for i, v in enumerate(clipped)]
        for clip, clip_top, clip_bottom in (("ri", strip.top, strip.y(ihi)), ("rl", strip.y(ilo), strip.top + strip.height)):
            svg.clip(clip, strip.left, clip_top, strip.width, clip_bottom - clip_top)
            strip.series(near, RED, 2.4, clip=clip)
    for run in strip.runs([v if o else None for v, o in zip(ratios, out)]):
        if not run[1:] and ylo <= ratios[run[0]] <= yhi:  # off the scale, the edge marker below shows it
            svg.dot(strip.xs[run[0]], strip.y(ratios[run[0]]), 3.5, RED)
    for x, r in zip(strip.xs, ratios):
        if r is not None and not ylo <= r <= yhi:
            edge = strip.y(yhi if r > yhi else ylo)
            svg.path("M%.1f %.1fl5 %gh-10z" % (x, edge, 8 if r > yhi else -8), RED, 1, fill=RED)
    if restarted:
        strip.vline(restart, PURPLE, 1.4, DASHDOT)
    return svg.finish(_footer(svg, strip, period, interval, census_footnote(bands)))


def uptime_chart(period, ts, percent, interval, identity, restart, end=None, last_seen=None):
    """Running-flag uptime percent over one period, its legend above the plot.

    ``end`` (relays_published) and ``last_seen`` are for a relay no longer running: Onionoo adds no points once it
    is out of the consensus, so its axis runs on to ``end``, and the whole slots from ``last_seen`` (or the last
    slot's end) to there count as down.
    """
    svg = Svg(WIDTH)
    gone = last_seen or ts[-1] + timedelta(seconds=interval / 2)
    down = max(0, int((end - gone).total_seconds() // interval)) if end and interval else 0
    # Average what is drawn (factor applied, window clipped) and the slots down; like the site's uptime
    # figures, only from 30 points and above 1%.
    average = sum(percent) / (len(percent) + down)
    since = "  ·  down since {}".format(format_day(gone, year=period in YEAR_PERIODS)) if down else ""
    subtitle = "Average {:.1f}%{}  ·  Onionoo Running flag".format(average, since) if len(percent) >= 30 and \
        average > 1.0 else ""
    y = _header(svg, identity, "Uptime · " + PERIOD_SPAN[period], subtitle)
    restarted = _restart_entry(restart, ts, end)
    y += 8 + legend(svg, LEFT, y, [[("line", GREEN, None, "Running flag")] + restarted])
    panel = Panel(svg, "u", LEFT, y, PLOT_WIDTH, 220, ts, 0, 105, end, interval)
    panel.yaxis(range(0, 101, 20), "Uptime (%)")
    panel.xaxis(period)
    if restarted:
        panel.vline(restart, PURPLE, 1.4, DASHDOT)
    panel.series(percent, GREEN, 2.2)
    return svg.finish(_footer(svg, panel, period, interval))


def _overload_text(relay):
    """Legend text while the relay is overloaded (relays.py's verdict), with the newest report time among the
    reports that verdict counts (a rate-limit report counts only when a limit was hit)."""
    if not relay.get("stability_is_overloaded"):
        return None
    facts = evaluate_overload(relay)
    stamps = [stamp for stamp in (facts["general_ts"] if facts["general_active"] else None,
                                  facts["ratelimits"].get("timestamp") if facts["ratelimit_hit"] else None,
                                  facts["fd_timestamp"]) if stamp]
    if not stamps:
        return "currently overloaded"
    last = datetime.fromtimestamp(max(stamps) / 1000.0, timezone.utc)
    return "currently overloaded · last report {}, {:%H:%M} UTC".format(format_day(last), last)


class ChartWriter(object):
    """Writes relay and operator charts next to their pages.

    Built once in the parent process (the peer medians need every relay),
    then shared with the forked page workers.

    PNG charts are kept in ``cache_dir`` under a hash of their drawing calls
    (``Svg.ops``, which cairo replays at full precision; the SVG text rounds
    them to 0.1 px): a chart that did not change since the last build (most
    6M/1Y/5Y charts, and 1M ones between Onionoo's 4-hourly points) is
    hard-linked from there instead of drawn again. A hit marks
    the file's access time and keeps its modification time, so ``rsync -a``
    and HTTP caches see an unchanged chart as unchanged. ``sweep()`` drops
    the ones this build did not use (all of them in an SVG build).
    """

    _copy_warned = False

    def __init__(self, relay_set, image_format="png", cache_dir=None, scale=2, colors="64"):
        from ..operator_analysis import history_maps
        from ..workers import CACHE_DIR
        self.ext, self.raster, self.started = image_format, None, time.time()
        self.scale, self.colors = scale, colors
        self.cache_root = self.cache = cache_dir or os.path.join(CACHE_DIR, "charts")
        if image_format == "png":
            from . import raster  # cairocffi and numpy (zlib-ng if installed)
            self.raster = raster
            if colors != "full":
                raster.lookup()  # built once here, then shared with the forked page workers
            # One directory per drawing version (code, background, palette, cairo, fonts): the others can never
            # be hit again, so they go now, before this build fills its own. --chart-scale and --chart-colors
            # are part of each file's key instead, so builds with other options do not delete this folder
            # under each other (sweep() still drops the charts this build did not use).
            self.cache = os.path.join(self.cache_root, hashlib.blake2b(raster.VERSION, digest_size=8).hexdigest())
            os.makedirs(self.cache, exist_ok=True)
            self._drop_versions(keep=self.cache)
        self.relays = relay_set.json["relays"]
        self.uptime, self.bandwidth = history_maps(relay_set)
        # Each period's window ends at its Onionoo document's relays_published (bandwidth is cached for longer
        # than uptime), and so does each chart's time axis.
        self.published = {name: parse_onionoo_timestamp((data or {}).get("relays_published")) for name, data in
                          (("bandwidth", relay_set.bandwidth_data), ("uptime", relay_set.uptime_data))}
        self.role_medians, self.family_medians = peer_medians(self.relays, self.bandwidth, self._since("bandwidth", "1m"))

    def _since(self, document, period):
        """Start of a period's window in an Onionoo document ("bandwidth" or "uptime"), None when undated."""
        end = self.published[document]
        return end - WINDOW[period] if end else None

    def _save(self, directory, name, draw, *args):
        """Write ``name`` plus the format's extension and return its height, which the page reserves for the
        image, or 0 when nothing was written: no drawable history, or a malformed one, skips the chart instead
        of failing the page."""
        path = os.path.join(directory, "%s.%s" % (name, self.ext))
        try:
            svg = draw(*args)
            text = svg.document().encode("utf-8") if svg and not self.raster else b""
        except Exception:  # noqa: BLE001
            return 0
        if not svg:
            return 0
        if not self.raster:
            with open(path, "wb") as handle:
                handle.write(text)
            return svg.height
        try:
            self._png(svg, path)
        except Exception as error:  # noqa: BLE001 -- unlike odd history, this is the build host's problem
            logger.warning("PNG conversion failed for %s: %s", path, error)
            return 0
        return svg.height

    def _png(self, svg, path):
        # Keyed on what cairo replays, by value (marshal format 2 has no identity-based references).
        drawing = marshal.dumps((self.scale, self.colors, svg.width, svg.height, svg.ops), 2)
        cached = os.path.join(self.cache, hashlib.blake2b(drawing, digest_size=16).hexdigest() + ".png")
        try:  # a hit: mark it used for sweep() in the access time, keep the modification time
            os.utime(cached, ns=(time.time_ns(), os.stat(cached).st_mtime_ns))
        except FileNotFoundError:
            data, partial = self.raster.png(svg, self.scale, self.colors), "%s.%d" % (cached, os.getpid())
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
                logger.warning("--out is not on the filesystem of %s: copying every PNG chart (~3.4 GB at the "
                               "defaults) instead of linking it; build next to it to save that", self.cache_root)
            shutil.copy2(cached, path)

    def _drop_versions(self, keep=None):
        """Delete the cache's drawing-version folders but ``keep``; nothing else under ``cache_root``."""
        if os.path.isdir(self.cache_root):
            for entry in os.scandir(self.cache_root):
                if entry.is_dir() and entry.path != keep and re.fullmatch("[0-9a-f]{16}", entry.name):
                    shutil.rmtree(entry.path, ignore_errors=True)

    def sweep(self):
        """Delete cached PNGs no chart of this build used (call once every page is written)."""
        if not self.raster:
            self._drop_versions()
            return
        for entry in os.scandir(self.cache):
            try:  # another build sharing the cache may remove or rename files meanwhile
                if entry.stat().st_atime < self.started - 60:
                    os.remove(entry.path)
            except FileNotFoundError:
                pass

    def relay(self, relay, directory):
        """Write ``bandwidth-<period>`` and ``uptime-<period>`` charts; return their ``{period: height}`` maps
        (drawn periods only), bandwidth first."""
        # A relay no longer running gets no more history: its axes run on to relays_published, showing the gap.
        stopped = relay.get("running") is False
        common = dict(advertised=(relay.get("advertised_bandwidth") or 0) * MBIT,
                      bands=bands_for_role(role_from_flags(relay.get("flags"))),
                      identity=chart_identity(relay.get("nickname"), operator_from_contact(relay.get("contact"))),
                      restart=parse_onionoo_timestamp(relay.get("last_restarted")), overload=_overload_text(relay))
        return (self._charts(directory, "bandwidth", self._relay_bandwidth, relay, common, stopped),
                self._charts(directory, "uptime", self._relay_uptime, relay, common, stopped))

    def _charts(self, directory, name, draw, *args):
        """``{period: height}`` of the ``<name>-<period>`` charts written, drawn by ``draw(*args, key, period)``."""
        heights = ((period, self._save(directory, name + "-" + period, draw, *args, key, period))
                   for key, period in PERIODS)
        return {period: height for period, height in heights if height}

    def _relay_bandwidth(self, relay, common, stopped, key, period):
        series = throughput(self.bandwidth.get(relay["fingerprint"]), key, self._since("bandwidth", period))
        if not series:
            return None
        end = self.published["bandwidth"] if stopped else None
        if period != "1m":  # peer and family medians are 1M only
            return bandwidth_chart(period, series, end=end, **common)
        family_n, family = self.family_medians.get(family_key(relay), (0, {}))
        medians = (("role", self.role_medians.get(common["bands"]["role"], {})), ("family", family))
        overlays = {name: {t: median[t] for t in series[0] if t in median} for name, median in medians}
        return bandwidth_chart(period, series, overlays=overlays, family_n=family_n, end=end, **common)

    def _relay_uptime(self, relay, common, stopped, key, period):
        block = ((self.uptime.get(relay["fingerprint"]) or {}).get("uptime") or {}).get(key) or {}
        percent = points(block, 100.0, self._since("uptime", period))
        if len(percent) < 2:
            return None
        ts = sorted(percent)
        return uptime_chart(period, ts, [percent[t] for t in ts], int(block.get("interval") or 0), common["identity"],
                            common["restart"], *((self.published["uptime"], parse_onionoo_timestamp(relay.get("last_seen")))
                                                 if stopped else ()))

    def contact(self, member_indexes, directory):
        """Write ``bandwidth-<period>`` charts for an operator's summed members; return ``{period: height}``."""
        members = [self.relays[i] for i in member_indexes]
        # Relays without contact info share one hash, but they are not an operator.
        if not any((relay.get("contact") or "").strip() for relay in members):
            return {}
        return self._charts(directory, "bandwidth", self._contact_bandwidth, members, operator_identity(members))

    def _contact_bandwidth(self, members, identity, key, period):
        series, summed = operator_throughput(members, self.bandwidth, key, self._since("bandwidth", period))
        if not series:
            return None
        # Operators mix roles: judge write/read against the role whose members carried the most traffic.
        traffic = Counter()
        for relay, carried in summed:
            traffic[role_from_flags(relay.get("flags"))] += carried
        bands = bands_for_role(max(sorted(traffic), key=traffic.get))
        advertised = sum(relay.get("advertised_bandwidth") or 0 for relay, _carried in summed) * MBIT
        # Every member stopped: show the gap up to relays_published, as for a relay.
        end = None if any(relay.get("running") is not False for relay in members) else self.published["bandwidth"]
        return bandwidth_chart(period, series, advertised, bands, identity, operator=True, end=end)
