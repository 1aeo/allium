"""Small SVG plotting kit for the history charts: no matplotlib, no JavaScript.

Colors and type follow the 1aeo.com/blog charts: a dark #1e1e1e canvas,
DejaVu Sans, light text, and green / blue / orange / red / purple / cyan series.
"""

import math
import re
from datetime import datetime, timedelta, timezone
from html import escape

from .outcome import YEAR_PERIODS, format_day

BG = "#1e1e1e"
LEGEND_BG = "#242424"
LEGEND_EDGE = "#3c3c3c"
CALLOUT_BG = "#161a20"
GRID = "#323232"
AXIS = "#555555"
TEXT = "#e6e6e6"
MUTED = "#9a9a9a"
GREEN = "#00ff7f"
BLUE = "#4da6ff"
ORANGE = "#ffb454"
RED = "#ff6b6b"
PURPLE = "#b48cff"
CYAN = "#38bdf8"
DASHED, DOTTED, DASHDOT = "7 4", "1.5 3", "9 3.5 2 3.5"
# Characters XML 1.0 forbids, and lone surrogates (UTF-8 cannot encode them):
# operator-controlled contact strings could carry them.
_CONTROL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")

# DejaVu Sans advance widths in 1/100 em for " " .. "~" (Verdana, the usual
# fallback, is about as wide), so layouts hold in either font.
_WIDTHS = dict(zip(map(chr, range(32, 127)), map(int, (
    "32 40 46 84 64 95 78 27 39 39 50 84 32 36 32 34 64 64 64 64 64 64 64 64 64 64 34 34 84 84 84 53 "
    "100 68 69 70 77 63 58 77 75 29 29 66 56 86 75 79 60 79 69 63 61 73 68 99 69 61 69 39 34 39 84 50 "
    "50 61 63 55 63 62 35 63 63 28 28 58 28 97 63 61 63 63 41 52 39 63 59 82 59 59 52 64 34 64 84"
).split())))


def text_width(text, size, bold=False):
    return sum(_WIDTHS.get(c, 60) for c in text) * size / (89.0 if bold else 100.0)


def _dash(dash):
    return ' stroke-dasharray="%s"' % dash if dash else ""


class Svg(object):
    """Collects SVG elements. ``document()`` gives the SVG text and ``ops`` the same drawing for ``raster.png``."""

    def __init__(self, width):
        self.width, self.height = width, 0
        self.parts, self.ops = [], []

    def text(self, x, y, text, size, color=TEXT, anchor="start", bold=False, rotate=False):
        text = _CONTROL.sub("", text)
        self.ops.append(("text", x, y, text, size, color, anchor, bold, rotate))
        self.parts.append('<text x="%.1f" y="%.1f" font-size="%g" fill="%s"%s%s%s>%s</text>' % (
            x, y, size, color,
            ' text-anchor="%s"' % anchor if anchor != "start" else "",
            ' font-weight="bold"' if bold else "",
            ' transform="rotate(-90 %.1f %.1f)"' % (x, y) if rotate else "",
            escape(text, quote=False).replace("  ", "&#160;&#160;")))  # keep double spaces

    def line(self, x1, y1, x2, y2, color, width=1.0, dash=None):
        self.ops.append(("line", x1, y1, x2, y2, color, width, dash))
        self.parts.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%g"%s/>' % (
            x1, y1, x2, y2, color, width, _dash(dash)))

    def rect(self, x, y, w, h, fill, opacity=None, stroke=None, rx=0):
        self.ops.append(("rect", x, y, w, h, fill, opacity, stroke, rx))
        self.parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"%s%s%s/>' % (
            x, y, w, h, fill, ' opacity="%g"' % opacity if opacity else "",
            ' stroke="%s"' % stroke if stroke else "", ' rx="%g"' % rx if rx else ""))

    def path(self, d, color, width, dash=None, fill="none", clip=None):
        """``d`` uses M, L, l, h and z only, each with its own coordinates, which ``raster`` replays."""
        if d:
            self.ops.append(("path", d, color, width, dash, fill, clip))
            self.parts.append('<path d="%s" fill="%s" stroke="%s" stroke-width="%g" stroke-linejoin="round"%s%s/>' % (
                d, fill, color, width, _dash(dash), ' clip-path="url(#%s)"' % clip if clip else ""))

    def dot(self, x, y, r, color):
        """A filled dot, drawn as a 12-sided path (``raster`` replays paths, not circles)."""
        self.path("M" + "L".join("%.1f %.1f" % (x + r * math.cos(a * math.pi / 6), y + r * math.sin(a * math.pi / 6))
                                 for a in range(12)) + "z", color, 1, fill=color)

    def clip(self, clip_id, x, y, w, h):
        self.ops.append(("clip", clip_id, x, y, w, h))
        self.parts.append('<clipPath id="%s"><rect x="%.1f" y="%.1f" width="%.1f" height="%.1f"/></clipPath>' % (
            clip_id, x, y, w, h))

    def finish(self, height):
        self.height = int(round(height))
        return self

    def document(self):
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            'font-family="DejaVu Sans, Verdana, sans-serif"><rect width="100%" height="100%" fill="{bg}"/>'
            '{body}</svg>\n'
        ).format(w=self.width, h=self.height, bg=BG, body="".join(self.parts))


def date_ticks(period, ts, end):
    """Tick datetimes and labels up to the axis' ``end``: weekly (Tuesdays) for 1M, monthly 6M, bimonthly 1Y,
    yearly 5Y.

    Under two of those, 1M ticks daily; past that, the first and last points are labelled too (with the hour
    when one shares its day with another label), each only where it keeps an eighth of the axis clear of the
    other labels.
    """
    start = ts[0]
    if period == "1m":
        midnight = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
        tuesday = midnight + timedelta(days=(1 - midnight.weekday()) % 7)
        ticks = [(t, format_day(t)) for t in (tuesday + timedelta(weeks=i) for i in range((end - tuesday).days // 7 + 1))
                 if t >= start]
        if len(ticks) < 2:
            ticks = [(t, format_day(t)) for t in (midnight + timedelta(days=i) for i in range((end - midnight).days + 1))
                     if t >= start]
    elif period == "5y":
        ticks = [(datetime(y, 1, 1, tzinfo=timezone.utc), str(y)) for y in range(start.year + 1, end.year + 1)]
    else:  # month starts, every other month on 1Y
        fmt, every = "%b '%y" if start.year != end.year else "%b", 2 if period == "1y" else 1
        months = (datetime(m // 12, m % 12 + 1, 1, tzinfo=timezone.utc)
                  for m in range(start.year * 12 + start.month - 1, end.year * 12 + end.month) if m % 12 % every == 0)
        ticks = [(t, t.strftime(fmt)) for t in months if t >= start]
    if len(ticks) < 2:
        ends = [(t, format_day(t, year=period in YEAR_PERIODS)) for t in (start, ts[-1])]
        days = [label for _t, label in ticks + ends]
        if len(set(days)) < len(days):
            ends = [(t, "{} {:%H:%M}".format(label, t)) for t, label in ends]
        for t, label in ends:
            if all(abs(t - tick) * 8 >= end - start for tick, _label in ticks):
                ticks.append((t, label))
        ticks.sort()
    return ticks


def nice_ticks(top, most=6):
    """0, step, 2*step ... up to ``top`` with a 1/2/2.5/5 x 10^n step."""
    step = 10 ** math.floor(math.log10(top / most))
    step *= next(m for m in (1, 2, 2.5, 5, 10) if top / (m * step) <= most)
    return [i * step for i in range(int(top / step + 1e-9) + 1)]


def view_end(ts, end=None):
    """The time axis ends 3% past the last point, or at ``end`` (the period's window) when that is later, so a
    history that stopped before then shows as a gap."""
    last = ts[-1] + (ts[-1] - ts[0]) * 0.03
    return max(last, end) if end else last


class Panel(object):
    """A plot area with a UTC-time x axis and a linear y axis."""

    def __init__(self, svg, clip_id, left, top, width, height, ts, ylo, yhi, end=None, interval=0):
        self.svg, self.clip, self.ts = svg, clip_id, ts
        self.left, self.top, self.width, self.height = left, top, width, height
        self.t0, self.end = ts[0].timestamp(), view_end(ts, end)
        self.tspan = (self.end.timestamp() - self.t0) or 1.0
        self.ylo, self.yspan = ylo, (yhi - ylo) or 1.0
        # Every series shares the times: place them once, and break lines across missing history, even one
        # slot (a step over 1.5 sampling intervals, or 1.5 times the shortest step when the interval is unknown).
        self.xs = [self.x(t) for t in ts]
        steps = [b - a for a, b in zip(ts, ts[1:])]
        gap = 1.5 * (timedelta(seconds=interval) if interval else min(steps, default=timedelta(0)))
        self.breaks = [True] + [step > gap for step in steps]
        svg.clip(clip_id, left, top, width, height)

    def x(self, t):
        return self.left + (t.timestamp() - self.t0) / self.tspan * self.width

    def y(self, value):
        return self.top + self.height - (value - self.ylo) / self.yspan * self.height

    def runs(self, values):
        """Indexes of ``values`` in the runs a line joins: it breaks at None / NaN values and across missing history."""
        runs = []
        for i, (v, brk) in enumerate(zip(values, self.breaks)):
            if v is None or v != v:
                continue
            if brk or not runs or runs[-1][-1] != i - 1:
                runs.append([])
            runs[-1].append(i)
        return runs

    def series(self, values, color, width, dash=None, clip=None):
        """Polyline of ``values`` over the panel's times, one per run; a point with no neighbour to join is a short
        dash, so it still shows."""
        d = []
        for run in self.runs(values):
            points = [(self.xs[i], self.y(values[i])) for i in run]
            d.append("M%.1f %.1f" % points[0] + "".join("L%.1f %.1f" % point for point in points[1:]) if run[1:] else
                     "M%.1f %.1fh%g" % (points[0][0] - width, points[0][1], 2 * width))
        self.svg.path("".join(d), color, width, dash, clip=clip or self.clip)

    def hband(self, lo, hi, color, opacity):
        lo, hi = max(lo, self.ylo), min(hi, self.ylo + self.yspan)
        if hi > lo:
            self.svg.rect(self.left, self.y(hi), self.width, self.y(lo) - self.y(hi), color, opacity)

    def hline(self, value, color, width, dash=None):
        self.svg.line(self.left, self.y(value), self.left + self.width, self.y(value), color, width, dash)

    def vline(self, t, color, width, dash=None):
        self.svg.line(self.x(t), self.top, self.x(t), self.top + self.height, color, width, dash)

    def yaxis(self, ticks, label, size=13, fmt="{:,g}"):
        """Grid lines and their labels."""
        for tick in ticks:
            self.hline(tick, GRID, 1)
            self.svg.text(self.left - 8, self.y(tick) + size * 0.35, fmt.format(tick), size, MUTED, "end")
        self.svg.text(12 + size, self.top + self.height / 2, label, size, MUTED, "middle", rotate=True)

    def band_label(self, text, lo, hi, color, ticks, fmt="{:.1f}", size=12, room=13):
        """Name the y range ``lo``–``hi`` beside the axis, inside the range: at its middle, or the spot nearest the
        middle ``room`` px clear of the ``yaxis`` labels of ``ticks``; in a range too narrow for that, beside the
        label of its tick nearest the middle."""
        top, bottom = self.y(min(hi, self.ylo + self.yspan)), self.y(max(lo, self.ylo))
        mid, marks = (top + bottom) / 2, {tick: self.y(tick) for tick in ticks}
        spots = [y for y in [mid] + [mark + step for mark in marks.values() for step in (-room, room)]
                 if top <= y <= bottom and all(abs(y - mark) >= room for mark in marks.values())]
        inside = [tick for tick in ticks if lo <= tick <= hi]
        x = self.left - 8
        if spots or not inside:
            y = min(spots or [mid], key=lambda spot: abs(spot - mid))
        else:
            tick = min(inside, key=lambda tick: abs(marks[tick] - mid))
            y, x = marks[tick], x - text_width(fmt.format(tick), 13) - 8  # 13: yaxis' label size
        self.svg.text(x, y + size * 0.35, text, size, color, "end", bold=True)

    def xaxis(self, period, labels=True, size=13):
        """Date gridlines with their labels, then the left and bottom axis lines."""
        bottom = self.top + self.height
        for tick, text in date_ticks(period, self.ts, self.end):
            x = self.x(tick)
            self.svg.line(x, self.top, x, bottom + 5, GRID, 1)
            if labels:
                self.svg.text(x, bottom + 8 + size, text, size, MUTED, "middle")
        self.svg.line(self.left, self.top, self.left, bottom, AXIS, 1)
        self.svg.line(self.left, bottom, self.left + self.width, bottom, AXIS, 1)


def legend(svg, x, y, rows, size=11.5):
    """Framed rows of ``(kind, color, style, label)`` entries. Returns the height.

    ``kind`` is ``line`` (style = dash), ``patch`` (style = fill opacity)
    or ``marker`` (a diamond). A legend too wide for the canvas moves left.
    """
    pad, swatch, gap, row_h = 8, 22, 16, size * 1.55
    widths = [[swatch + 6 + text_width(entry[3], size) for entry in row] for row in rows]
    total = max(sum(row) + gap * (len(row) - 1) for row in widths) + pad * 2
    height = pad * 2 + row_h * len(rows) - (row_h - size * 1.2)
    x = min(x, svg.width - 12 - total)
    svg.rect(x, y, total, height, LEGEND_BG, stroke=LEGEND_EDGE, rx=4)
    for r, (row, row_widths) in enumerate(zip(rows, widths)):
        cy, cx = y + pad + size * 0.6 + r * row_h, x + pad
        for (kind, color, style, label), width in zip(row, row_widths):
            if kind == "line":
                svg.line(cx, cy, cx + swatch, cy, color, 2.2, style)
            elif kind == "patch":
                svg.rect(cx, cy - size * 0.4, swatch, size * 0.8, color, style, stroke=color)
            elif kind == "marker":
                svg.path("M%.1f %.1fl5 -5l5 5l-5 5z" % (cx + swatch / 2 - 5, cy), color, 1, fill=color)
            svg.text(cx + swatch + 6, cy + size * 0.35, label, size)
            cx += width + gap
    return height
