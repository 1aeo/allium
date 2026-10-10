"""Small SVG plotting kit for the history charts: no matplotlib, no JavaScript.

Colors and type follow the 1aeo.com/blog charts: a dark #1e1e1e canvas,
DejaVu Sans, light text, and green / blue / orange / red / purple / cyan series.
"""

import math
import re
from datetime import datetime, timedelta, timezone
from html import escape

from .outcome import format_day

BG = "#1e1e1e"
LEGEND_BG = "#242424"
LEGEND_EDGE = "#3c3c3c"
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
# Characters XML 1.0 forbids; operator-controlled contact strings could carry them.
_CONTROL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")

# DejaVu Sans advance widths in 1/100 em for " " .. "~" (Verdana, the usual
# fallback, is about as wide), so layouts hold in either font.
_WIDTHS = [int(w) for w in (
    "32 40 46 84 64 95 78 27 39 39 50 84 32 36 32 34 64 64 64 64 64 64 64 64 64 64 34 34 84 84 84 53 "
    "100 68 69 70 77 63 58 77 75 29 29 66 56 86 75 79 60 79 69 63 61 73 68 99 69 61 69 39 34 39 84 50 "
    "50 61 63 55 63 62 35 63 63 28 28 58 28 97 63 61 63 63 41 52 39 63 59 82 59 59 52 64 34 64 84"
).split()]


def text_width(text, size, bold=False):
    em = sum(_WIDTHS[ord(c) - 32] if 32 <= ord(c) < 127 else 60 for c in text)
    return em * size / (89.0 if bold else 100.0)


def _dash(dash):
    return ' stroke-dasharray="%s"' % dash if dash else ""


class Svg(object):
    """Collects SVG elements; ``str()`` gives the finished document."""

    def __init__(self, width):
        self.width = width
        self.parts = []

    def text(self, x, y, text, size, color=TEXT, anchor="start", bold=False, rotate=False):
        self.parts.append('<text x="%.1f" y="%.1f" font-size="%g" fill="%s"%s%s%s>%s</text>' % (
            x, y, size, color,
            ' text-anchor="%s"' % anchor if anchor != "start" else "",
            ' font-weight="bold"' if bold else "",
            ' transform="rotate(-90 %.1f %.1f)"' % (x, y) if rotate else "",
            escape(_CONTROL.sub("", text), quote=False).replace("  ", "&#160;&#160;")))  # keep double spaces

    def line(self, x1, y1, x2, y2, color, width=1.0, dash=None):
        self.parts.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%g"%s/>' % (
            x1, y1, x2, y2, color, width, _dash(dash)))

    def rect(self, x, y, w, h, fill, opacity=None, stroke=None, rx=0):
        self.parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"%s%s%s/>' % (
            x, y, w, h, fill, ' opacity="%g"' % opacity if opacity else "",
            ' stroke="%s"' % stroke if stroke else "", ' rx="%g"' % rx if rx else ""))

    def path(self, d, color, width, dash=None, fill="none", clip=None):
        if d:
            self.parts.append('<path d="%s" fill="%s" stroke="%s" stroke-width="%g" stroke-linejoin="round"%s%s/>' % (
                d, fill, color, width, _dash(dash), ' clip-path="url(#%s)"' % clip if clip else ""))

    def document(self, height):
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h:.0f}" viewBox="0 0 {w} {h:.0f}" '
            'font-family="DejaVu Sans, Verdana, sans-serif"><rect width="100%" height="100%" fill="{bg}"/>'
            '{body}</svg>\n'
        ).format(w=self.width, h=height, bg=BG, body="".join(self.parts))


def date_ticks(period, ts, end):
    """Tick datetimes and labels: weekly (Tuesdays) for 1M, monthly 6M, bimonthly 1Y, yearly 5Y.

    A history too short to reach two of those dates gets its first and last day labelled.
    """
    start = ts[0]
    if period == "1m":
        day = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
        day += timedelta(days=(1 - day.weekday()) % 7)
        ticks = [(t, format_day(t)) for t in (day + timedelta(days=7 * i) for i in range((end - day).days // 7 + 1))
                 if start <= t <= end]
    elif period == "5y":
        ticks = [(datetime(y, 1, 1, tzinfo=timezone.utc), str(y)) for y in range(start.year + 1, end.year + 1)]
    else:  # month starts, every other month on 1Y
        fmt, every = "%b '%y" if start.year != ts[-1].year else "%b", 2 if period == "1y" else 1
        months = (datetime(m // 12, m % 12 + 1, 1, tzinfo=timezone.utc)
                  for m in range(start.year * 12 + start.month - 1, end.year * 12 + end.month) if m % 12 % every == 0)
        ticks = [(t, t.strftime(fmt)) for t in months if t >= start]
    if len(ticks) < 2:
        ticks = [(t, format_day(t, year=period in ("1y", "5y"))) for t in (ts[0], ts[-1])]
    return ticks


def nice_ticks(top, most=6):
    """0, step, 2*step ... up to ``top`` with a 1/2/2.5/5 x 10^n step."""
    step = 10 ** math.floor(math.log10(top / most))
    step *= next(m for m in (1, 2, 2.5, 5, 10) if top / (m * step) <= most)
    return [i * step for i in range(int(top / step + 1e-9) + 1)]


def view_end(ts):
    """The time axis ends 3% past the last point."""
    return ts[-1] + (ts[-1] - ts[0]) * 0.03


class Panel(object):
    """A plot area with a UTC-time x axis and a linear y axis."""

    def __init__(self, svg, clip_id, left, top, width, height, ts, ylo, yhi):
        self.svg, self.clip = svg, clip_id
        self.left, self.top, self.width, self.height = left, top, width, height
        self.t0, self.end = ts[0].timestamp(), view_end(ts)
        self.tspan = (self.end.timestamp() - self.t0) or 1.0
        self.ylo, self.yspan = ylo, (yhi - ylo) or 1.0
        svg.parts.append('<clipPath id="%s"><rect x="%.1f" y="%.1f" width="%.1f" height="%.1f"/></clipPath>' % (
            clip_id, left, top, width, height))

    def x(self, t):
        return self.left + (t.timestamp() - self.t0) / self.tspan * self.width

    def y(self, value):
        return self.top + self.height - (value - self.ylo) / self.yspan * self.height

    def series(self, ts, values, color, width, dash=None):
        """Polyline that breaks at None / NaN values and across missing history (gaps over two steps)."""
        gap = 2 * min((b - a for a, b in zip(ts, ts[1:])), default=timedelta(0))
        d, pen, last = [], "M", None
        for t, v in zip(ts, values):
            if v is None or v != v:
                pen = "M"
                continue
            if last and t - last > gap:
                pen = "M"
            d.append("%s%.1f %.1f" % (pen, self.x(t), self.y(v)))
            pen, last = "L", t
        self.svg.path("".join(d), color, width, dash, clip=self.clip)

    def hband(self, lo, hi, color, opacity):
        lo, hi = max(lo, self.ylo), min(hi, self.ylo + self.yspan)
        if hi > lo:
            self.svg.rect(self.left, self.y(hi), self.width, self.y(lo) - self.y(hi), color, opacity)

    def hline(self, value, color, width, dash=None):
        self.svg.line(self.left, self.y(value), self.left + self.width, self.y(value), color, width, dash)

    def vline(self, t, color, width, dash=None):
        self.svg.line(self.x(t), self.top, self.x(t), self.top + self.height, color, width, dash)

    def yaxis(self, ticks, label, size=13, styles=None):
        """Grid lines and labels; ``styles`` maps a tick to ``(text, color, bold)``."""
        for tick in ticks:
            y = self.y(tick)
            text, color, bold = (styles or {}).get(tick) or ("{:,g}".format(tick), MUTED, False)
            self.svg.line(self.left, y, self.left + self.width, y, GRID, 1)
            self.svg.text(self.left - 8, y + size * 0.35, text, size - bold, color, "end", bold)
        self.svg.text(12 + size, self.top + self.height / 2, label, size, MUTED, "middle", rotate=True)

    def xaxis(self, period, ts, labels=True, size=13):
        """Date gridlines with their labels, then the left and bottom axis lines."""
        bottom = self.top + self.height
        for tick, text in date_ticks(period, ts, self.end):
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
