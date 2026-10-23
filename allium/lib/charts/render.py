"""Relay and operator history charts, written as PNG (or SVG) next to their HTML pages or under charts/."""

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
from ..uptime_utils import _block_uptime_percentage_and_datapoints, uptime_windows
from .bands import (
    RATIO_SCALE_HI, RATIO_SCALE_LO, band_legend_labels, bands_for_role, census_footnote, ratio_strip_data_hi,
    role_from_flags,
)
from .identity import chart_identity, operator_from_contact, operator_identity
from .outcome import YEAR_PERIODS, format_day, format_day_span, mbit, ratio_subtitle, ratio_text, throughput_subtitle
from .series import (
    MBIT, MIN_ACTIVE_KBYTES, PERIOD_SPAN, PERIODS, WINDOW, active_ratio, family_key, network_ratio_bands,
    network_uptime, operator_throughput, peer_medians, throughput, uptime_points, uptime_section,
)
from .svg import (
    AXIS, BLUE, CALLOUT_BG, CYAN, DASHDOT, DASHED, DOTTED, GREEN, MUTED, ORANGE, PURPLE, RED, TEXT,
    Panel, Svg, legend, nice_ticks, text_width, view_end,
)

WIDTH, LEFT = 1080, 138
PLOT_WIDTH = WIDTH - LEFT - 24
CREDIT = "Produced by 1aeo at 1aeo.com"  # every chart's source, bottom right
# --chart-layout charts writes <out>/charts/relay/<fingerprint>/ and <out>/charts/contact/<hash>/, apart from the pages
CHARTS_DIR = "charts"
logger = logging.getLogger(__name__)


def _refuse_symlink(path):
    """A chart directory that is a symbolic link would delete files outside the output tree."""
    if os.path.islink(path):
        raise OSError("%s is a symbolic link; refusing to delete charts through it" % path)


def clear_chart_tree(output_dir):
    """Delete ``<out>/charts/relay``, ``contact`` and ``network``, then ``<out>/charts`` when that empties it,
    and ``<out>/network`` (the network charts written beside network-health.html).

    Call it on every build before any page is written. With relay/ and contact/, which the page writer rebuilds
    (and the charts beside the pages with them), it leaves only the charts this build writes, in its own layout:
    a build that writes them beside the pages, or none, drops the tree an earlier --chart-layout charts build left.
    Anything else in charts/ stays. A tree it cannot remove stops the build, as relay/ and contact/ do, and so
    does a charts/ or network/ that is a symbolic link: deleting through it would reach outside the output directory.
    """
    root = os.path.join(output_dir, CHARTS_DIR)
    _refuse_symlink(root)
    for kind in ("relay", "contact", "network"):
        path = os.path.join(root, kind)
        if os.path.exists(path):
            shutil.rmtree(path)
    try:
        os.rmdir(root)
    except OSError:  # missing, or holds something allium did not write
        pass
    beside = os.path.join(output_dir, "network")
    _refuse_symlink(beside)
    if os.path.isdir(beside):
        shutil.rmtree(beside)


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


def _step_name(interval):
    """``4-hour`` / ``1-day`` / ``10-day``, or "" when ``interval`` is not a whole hour, day, or week."""
    for size, name in ((SECONDS_PER_WEEK, "week"), (SECONDS_PER_DAY, "day"), (SECONDS_PER_HOUR, "hour")):
        if interval and interval % size == 0:
            return "{}-{}".format(interval // size, name)
    return ""


def _footer(svg, panel, period, interval, footnote=""):
    """Date-axis caption (``6M · 1-day``) under longer periods, then a line with the footnote on the left and
    the CREDIT on the right. Returns the height."""
    y = panel.top + panel.height + 38
    if period != "1m":
        step = _step_name(interval)
        caption = period.upper() + (" · " + step if step else "")
        y += 20
        svg.text(LEFT + PLOT_WIDTH / 2, y, caption, 13, MUTED, "middle")
    y += 24
    if footnote:
        svg.text(12, y, footnote, 11, MUTED)
    svg.text(WIDTH - 12, y, CREDIT, 11, MUTED, "end")
    return y + 12


def _spike_callout(svg, panel, high, yhi, clear_of, period, bands, interval):
    """Label the highest of the ``high`` write/read rows (above the role's p98), with its neighbouring slots
    (``interval`` apart), on the throughput lines; ``yhi`` is the top of the write/read strip's scale.

    The label sits right of the peak (left when it would not fit, else over it, inside the plot) in the band the
    y range keeps free under the legend, whose bottom is ``clear_of``.
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
    right = panel.left + panel.width
    box_x = x + 19 if x + 19 + width <= right else x - 19 - width if x - 19 - width >= panel.left else \
        min(max(panel.left, x - width / 2), right - width)
    svg.line(x, y, min(max(x, box_x), box_x + width), clear_of + 30, MUTED, 1)
    svg.rect(box_x, clear_of + 6, width, 24, CALLOUT_BG, stroke=RED, rx=5)
    svg.text(box_x + 7, clear_of + 22.5, label, 11.5, RED, bold=True)


def _restart_entry(restart, ts, end=None):
    """``[]``, or the restart's legend entry when the restart is on the time axis."""
    if restart and ts[0] <= restart <= view_end(ts, end):
        return [("line", PURPLE, DASHDOT, "Last restarted  " + format_day(restart))]
    return []


def bandwidth_chart(period, series, advertised, bands, identity, restart=None, overload=None,
                    overlays=None, family_n=0, operator=False, end=None, unit="Mbit/s", subject=None,
                    footnote=None):
    """Throughput panel over a write/read panel.

    ``series`` is ``(ts, write, read, interval)`` in Mbit/s (``series.throughput``). ``bands`` are the role's
    frozen write/read bands; None draws the same panels without grading the ratio against a role (the network
    sum is not one role). ``unit`` of ``"Gbit/s"`` scales the throughput panel by 1,000; the ratio stays on the
    Mbit/s series. ``overlays`` maps ``"role"`` / ``"family"`` to ``{ts: median write/read}`` (1M relay charts
    only; ``family_n`` relays). ``end`` is the period window's end (``relays_published``): the time axis runs
    to it at least. ``subject`` is the ratio legend (otherwise ``This relay`` or ``This operator``).
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
    role = ("  ·  vs {} band".format(bands["role"]) if operator else "  ·  " + bands["role"]) if bands else ""
    restarted = _restart_entry(restart, ts, end)
    svg = Svg(WIDTH)
    # Ratio days and the write/read line use the Mbit/s series. Only the throughput panel is rescaled.
    if unit == "Gbit/s":
        shown_write = [value / 1000.0 for value in write]
        shown_read = [value / 1000.0 for value in read]
        shown_advertised = (advertised or 0) / 1000.0
    else:
        shown_write, shown_read, shown_advertised = write, read, advertised

    y = _header(svg, identity, "Throughput · " + span + ("" if operator or not bands else role),
                throughput_subtitle(ts, shown_write, shown_advertised, period, unit=unit))
    ceiling = max(max(shown_write), max(shown_read), shown_advertised) or 1.0
    # Headroom for the legend (two rows when overloaded) and, with a spike, its callout below it.
    high = [row for row in rows if bands and row[3] > bands["invest_hi"]]
    headroom = (1.45 if overload else 1.34) if high else (1.28 if overload else 1.26)
    top = Panel(svg, "t", LEFT, y, PLOT_WIDTH, 290, ts, 0, ceiling * headroom, end, interval)
    top.yaxis(nice_ticks(top.yspan), "Throughput ({})".format(unit))
    top.xaxis(period, labels=False)
    entries = [("line", GREEN, None, "Write (outbound)"), ("line", BLUE, None, "Read (inbound)")]
    if shown_advertised:
        top.hline(shown_advertised, ORANGE, 1.3, DASHED)
        entries.append(("line", ORANGE, DASHED, "Advertised  {} {}".format(mbit(shown_advertised), unit)))
    if restarted:
        top.vline(restart, PURPLE, 1.4, DASHDOT)
    top.series(shown_write, GREEN, 2.4)
    top.series(shown_read, BLUE, 1.7)
    y += 8 + legend(svg, LEFT + 8, y + 8, [entries + restarted] + ([[("marker", RED, None, overload)]] if overload else []))
    ylo, yhi = RATIO_SCALE_LO, ratio_strip_data_hi(bands) if bands else RATIO_SCALE_HI
    if high:
        _spike_callout(svg, top, high, yhi, y, period, bands, interval)

    y = _header(svg, "", "Write / read · " + span + role, ratio_sub, top.top + top.height + 8)
    who = subject or ("This operator" if operator else "This relay")
    entries = [("line", TEXT, None, who)] if rows else []
    if overlays.get("family"):
        entries.append(("line", MUTED, DOTTED, "Operator Family (median, n={})".format(family_n)))
    if overlays.get("role"):
        entries.append(("line", CYAN, DASHED, "Peers (network median)"))
    if bands:
        tlo, thi, ilo, ihi = bands["typical_lo"], bands["typical_hi"], bands["invest_lo"], bands["invest_hi"]
        out = [r is not None and not ilo <= r <= ihi for r in ratios]
        if any(out):
            entries.append(("dot", RED, None, "Outside p2–p98"))
        labels = band_legend_labels(bands)
        bands_row = [("patch", GREEN, 0.25, labels[0]), ("patch", ORANGE, 0.22, labels[1]),
                     ("patch", RED, 0.22, labels[2])]
    else:
        out, bands_row = [], []
    legend_rows = [row for row in (entries + restarted, bands_row) if row]
    y += 6 + (legend(svg, LEFT, y, legend_rows) if legend_rows else 0)
    strip = Panel(svg, "r", LEFT, y, PLOT_WIDTH, 150, ts, ylo, yhi, end, interval)
    if bands:
        for lo, hi, color, opacity in ((ylo, ilo, RED, 0.08), (ilo, tlo, ORANGE, 0.07), (tlo, thi, GREEN, 0.14),
                                       (thi, ihi, ORANGE, 0.07), (ihi, yhi, RED, 0.08)):
            strip.hband(lo, hi, color, opacity)
    # Plain labels on the fixed grid lines; the typical band and the top Investigate shelf are named in their own
    # ranges (beside a grid label where the range is too narrow to clear it).
    ticks = (ylo, 1.0, 1.5)
    strip.yaxis(ticks, "Write / read", fmt="{:.1f}")
    if bands:
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
    # to the strip above ihi and below ilo; and a dot where that red is only a tip or a sliver: on a day with no
    # joined neighbour out on its side, and on a day under 2 px past the band edge.
    if any(out):
        near = [v if any(out[max(i - 1, 0):i + 2]) else None for i, v in enumerate(clipped)]
        for clip, clip_top, clip_bottom in (("ri", strip.top, strip.y(ihi)), ("rl", strip.y(ilo), strip.top + strip.height)):
            svg.clip(clip, strip.left, clip_top, strip.width, clip_bottom - clip_top)
            strip.series(near, RED, 2.4, clip=clip)
    if bands:
        for high, edge in ((True, strip.y(ihi)), (False, strip.y(ilo))):
            for run in strip.runs([v if o and (v > ihi) == high else None for v, o in zip(ratios, out)]):
                for i in run:
                    dot_y = strip.y(ratios[i])
                    if ylo <= ratios[i] <= yhi and (not run[1:] or abs(dot_y - edge) < 2):
                        svg.dot(strip.xs[i], dot_y, 3.5, RED)  # off the scale, the edge marker below shows it
    for x, r in zip(strip.xs, ratios):
        if r is not None and not ylo <= r <= yhi:
            edge = strip.y(yhi if r > yhi else ylo)
            svg.path("M%.1f %.1fl5 %gh-10z" % (x, edge, 8 if r > yhi else -8), RED, 1, fill=RED)
    if restarted:
        strip.vline(restart, PURPLE, 1.4, DASHDOT)
    # An explicit footnote replaces the role census line. Relay charts pass none, so theirs stays the census.
    note = footnote if footnote is not None else (census_footnote(bands) if bands else "")
    return svg.finish(_footer(svg, strip, period, interval, note))


def _advertised_mbit(summed):
    """Current advertised capacity of the relays ``operator_throughput`` actually summed, in Mbit/s."""
    return sum((relay.get("advertised_bandwidth") or 0) for relay, _traffic in summed) * MBIT


def uptime_chart(period, ts, percent, interval, identity, restart, average, counts=None):
    """Running-flag uptime percent over one period, its legend above the plot. ``average`` is the relay page's
    figure for the period, the mean of what is drawn (0.0 when the page shows none: under 30 slots, or 1% or less).

    ``counts``, when given, is how many relays were averaged at each timestamp: a second panel, used by the
    network chart. A relay chart passes none, and draws exactly as before.
    """
    svg = Svg(WIDTH)
    subtitle = "Average {:.1f}%  ·  Onionoo Running flag".format(average) if average else ""
    y = _header(svg, identity, "Uptime · " + PERIOD_SPAN[period], subtitle)
    restarted = _restart_entry(restart, ts)
    y += 8 + legend(svg, LEFT, y, [[("line", GREEN, None, "Running flag")] + restarted])
    panel = Panel(svg, "u", LEFT, y, PLOT_WIDTH, 220, ts, 0, 105, interval=interval)
    panel.yaxis(range(0, 101, 20), "Uptime (%)")
    panel.xaxis(period, labels=not counts)
    if restarted:
        panel.vline(restart, PURPLE, 1.4, DASHDOT)
    panel.series(percent, GREEN, 2.2)
    if not counts:
        return svg.finish(_footer(svg, panel, period, interval))
    lo, hi = min(counts), max(counts)
    counted = "{:,} relays".format(lo) if lo == hi else "{:,}–{:,} relays".format(lo, hi)
    step = _step_name(interval)
    y = _header(svg, "", "Relays in that average",
                counted + (" · one count per {} slot".format(step) if step else ""), panel.top + panel.height + 8)
    y += 6 + legend(svg, LEFT, y, [[("line", MUTED, None, "Relays counted")] + restarted])
    lower = Panel(svg, "c", LEFT, y, PLOT_WIDTH, 130, ts, 0, hi * 1.15 or 1, interval=interval)
    lower.yaxis(nice_ticks(lower.yspan), "Relays")
    lower.xaxis(period)
    if restarted:
        lower.vline(restart, PURPLE, 1.4, DASHDOT)
    lower.series(counts, MUTED, 2.0)
    return svg.finish(_footer(svg, lower, period, interval))


def _overload_text(relay):
    """Legend text while the relay is overloaded (relays.py's verdict), with the newest report time among the
    reports that verdict counts (a rate-limit report counts only when a limit was hit). "Currently" only while
    it runs: an offline relay's verdict comes from its last descriptor."""
    if not relay.get("stability_is_overloaded"):
        return None
    facts = evaluate_overload(relay)
    stamps = [stamp for stamp in (facts["general_ts"] if facts["general_active"] else None,
                                  facts["ratelimits"].get("timestamp") if facts["ratelimit_hit"] else None,
                                  facts["fd_timestamp"]) if stamp]
    state = "overloaded" if relay.get("running") is False else "currently overloaded"
    if not stamps:
        return state
    last = datetime.fromtimestamp(max(stamps) / 1000.0, timezone.utc)
    return "{} · last report {}, {:%H:%M} UTC".format(state, format_day(last), last)


class ChartWriter(object):
    """Writes relay and operator charts next to their pages, or under ``root``.

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

    def __init__(self, relay_set, image_format="png", cache_dir=None, scale=2, colors="64", root=None):
        from ..operator_analysis import history_maps
        from ..workers import CACHE_DIR
        self.ext, self.raster, self.started = image_format, None, time.time()
        self.scale, self.colors = scale, colors
        self.root = root  # <out>/charts with --chart-layout charts; None writes beside the pages
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
        # Bandwidth windows end at the bandwidth document's relays_published, and so does the time axis of a stopped
        # relay or a stale history (_end). Uptime charts use Onionoo's own windows, from the uptime document's
        # publish time (it is cached apart)
        self.published = parse_onionoo_timestamp((relay_set.bandwidth_data or {}).get("relays_published"))
        self.uptime_windows = uptime_windows(relay_set.uptime_data)
        self.role_medians, self.family_medians = peer_medians(self.relays, self.bandwidth, self._since("1m"))

    def _since(self, period):
        """Start of a period's bandwidth window, None when undated."""
        return self.published - WINDOW[period] if self.published else None

    def folder(self, kind, name, beside):
        """The folder for the charts of relay or contact ``name`` (``kind`` "relay" or "contact"): ``beside``, the
        page's own, or ``<root>/<kind>/<name>`` with --chart-layout charts."""
        return os.path.join(self.root, kind, name) if self.root else beside

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
        os.makedirs(directory, exist_ok=True)  # a charts/ folder only for a relay or operator with a chart
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
                logger.warning("--out is not on the filesystem of %s: copying every PNG chart (~3.6 GB at the "
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
        # A relay no longer running gets no more bandwidth history (see _end; its uptime charts draw the time since
        # at 0%, as Onionoo counts it).
        stopped = relay.get("running") is False
        common = dict(advertised=(relay.get("advertised_bandwidth") or 0) * MBIT,
                      bands=bands_for_role(role_from_flags(relay.get("flags"))),
                      identity=chart_identity(relay.get("nickname"), operator_from_contact(relay.get("contact")),
                                              relay["fingerprint"]),
                      restart=parse_onionoo_timestamp(relay.get("last_restarted")), overload=_overload_text(relay))
        return (self._charts(directory, "bandwidth", self._relay_bandwidth, relay, common, stopped),
                self._charts(directory, "uptime", self._relay_uptime, relay, common))

    def _charts(self, directory, name, draw, *args):
        """``{period: height}`` of the ``<name>-<period>`` charts written, drawn by ``draw(*args, key, period)``."""
        heights = ((period, self._save(directory, name + "-" + period, draw, *args, key, period))
                   for key, period in PERIODS)
        return {period: height for period, height in heights if height}

    def _end(self, series, stopped):
        """relays_published, where a bandwidth chart's time axis runs on to so that a missing end shows as a gap: for
        a relay no longer running, or a history that ended over two slots and a day before it (a stale Onionoo
        block); None for a running relay's history, which only lags Onionoo's by a day or so."""
        ts, interval = series[0], series[3]
        if self.published and (stopped or self.published - ts[-1] > timedelta(days=1, seconds=2 * interval)):
            return self.published
        return None

    def _relay_bandwidth(self, relay, common, stopped, key, period):
        series = throughput(self.bandwidth.get(relay["fingerprint"]), key, self._since(period))
        if not series:
            return None
        end = self._end(series, stopped)
        if period != "1m":  # peer and family medians are 1M only
            return bandwidth_chart(period, series, end=end, **common)
        family_n, family = self.family_medians.get(family_key(relay), (0, {}))
        medians = (("role", self.role_medians.get(common["bands"]["role"], {})), ("family", family))
        overlays = {name: {t: median[t] for t in series[0] if t in median} for name, median in medians}
        return bandwidth_chart(period, series, overlays=overlays, family_n=family_n, end=end, **common)

    def _relay_uptime(self, relay, common, key, period):
        section = uptime_section(self.uptime, relay["fingerprint"])
        block = section.get(key) or {}
        average, slots = _block_uptime_percentage_and_datapoints(block, key, self.uptime_windows, relay, section)
        if slots < 2:  # padded slots alone are not a history
            return None
        percent = uptime_points(block, key, self.uptime_windows, relay, section)
        ts = sorted(percent)
        return uptime_chart(period, ts, [percent[t] for t in ts], int(block.get("interval") or 0), common["identity"],
                            common["restart"], average)

    def contact(self, member_indexes, directory):
        """Write ``bandwidth-<period>`` charts for an operator's summed members; return ``{period: height}``."""
        members = [self.relays[i] for i in member_indexes]
        # Relays without contact info share one hash, but they are not an operator; nor are relays whose contact is
        # exactly "none", which the contact page treats alike.
        if not any((relay.get("contact") or "").strip() and relay["contact"] != "none" for relay in members):
            return {}
        return self._charts(directory, "bandwidth", self._contact_bandwidth, members, operator_identity(members))

    def _contact_bandwidth(self, members, identity, key, period):
        series, summed = operator_throughput(members, self.bandwidth, key, self._since(period))
        if not series:
            return None
        # Operators mix roles: judge write/read against the role whose members carried the most traffic.
        traffic = Counter()
        for relay, carried in summed:
            traffic[role_from_flags(relay.get("flags"))] += carried
        bands = bands_for_role(max(sorted(traffic), key=traffic.get))
        end = self._end(series, all(relay.get("running") is False for relay in members))  # as for a relay
        advertised = _advertised_mbit(summed)
        return bandwidth_chart(period, series, advertised, bands, identity, operator=True, end=end)

    def network(self, directory):
        """Write the whole-network ``bandwidth-<period>`` and ``uptime-<period>`` charts.

        Return their ``{period: height}`` maps, bandwidth first, drawn periods only.
        """
        return (self._charts(directory, "bandwidth", self._network_bandwidth),
                self._charts(directory, "uptime", self._network_uptime))

    def _network_bandwidth(self, key, period):
        since = self._since(period)
        ratios = []
        series, summed = operator_throughput(
            self.relays, self.bandwidth, key, since, until_slowest=False, ratios=ratios)
        if not series:
            return None
        # The band is this period's census, collected while the sum was parsed. Below MIN_NETWORK_CENSUS
        # relays the sum is drawn with no band. Gbit/s matches the bandwidth card.
        bands = network_ratio_bands(ratios)
        footnote = ("{:,} relays · ≥{} KB/s, ≥3 points".format(bands["n"], MIN_ACTIVE_KBYTES) if bands else
                    "Sum of relay write and read")
        return bandwidth_chart(period, series, _advertised_mbit(summed), bands, "Tor network",
                               end=self._end(series, False), unit="Gbit/s", subject="Whole network",
                               operator=bool(bands), footnote=footnote)

    def _network_uptime(self, key, period):
        drawn = network_uptime(self.relays, self.uptime, key, self.uptime_windows)
        if not drawn:
            return None
        ts, percent, interval, average, counts = drawn
        return uptime_chart(period, ts, percent, interval, "Tor network", None, average, counts)
