"""Network pressure charts for the 1M, 6M, 1Y, and 5Y switcher.

The usual range is the frozen May 2025–May 2026 p10–p90 on every period.
"""

from datetime import datetime, timedelta, timezone

from ..pressure_history import (
    HIGH_SHARE, guard_below_since, hsdir_noise, latest_value, series_window, status_since,
)
from .render import CREDIT, LEFT, PLOT_WIDTH, WIDTH, _header
from .series import PERIOD_SPAN
from .svg import BLUE, GREEN, MUTED, ORANGE, RED, Panel, Svg, legend, nice_ticks, text_width

_FOOT = "Usual range is the May 2025–May 2026 p10–p90, frozen."
_COUNT_TICKS = [0, 1500, 3000, 4500, 6000, 7500]


def _finish(svg, panel):
    foot = panel.top + panel.height + 42
    svg.text(12, foot, _FOOT, 11, MUTED)
    svg.text(WIDTH - 12, foot, CREDIT, 11, MUTED, "end")
    return svg.finish(foot + 14)


def _axis_end(stamps):
    span = max((stamps[-1] - stamps[0]).days, 1)
    end = stamps[-1] + timedelta(days=min(36, max(5, int(round(span * 0.1)))))
    cap = datetime(stamps[-1].year, 12, 20, tzinfo=timezone.utc)
    if stamps[-1].month == 12 and stamps[-1].day > 20:
        cap = stamps[-1] + timedelta(days=4)
    return end if end < cap else cap


def _latest(svg, panel, values, text, color):
    indexes = [index for index, value in enumerate(values) if value is not None]
    if not indexes:
        return
    index = indexes[-1]
    x, y = panel.xs[index], panel.y(values[index])
    svg.dot(x, y, 4, color)
    width = text_width(text, 13, bold=True)
    if panel.left + panel.width - x < width + 16:
        svg.text(max(panel.left + 4, x - 14 - width), y - 12, text, 13, color, bold=True)
    else:
        svg.text(x + 10, y + 4, text, 13, color, bold=True)


def _marked(values, pred):
    hit = [value is not None and pred(value) for value in values]
    return [value if any(hit[max(index - 1, 0):index + 2]) else None for index, value in enumerate(values)]


def _clip_band(svg, panel, values, lo, hi, color, clip_id, width=2.4, below=False):
    """Redraw the line inside ``lo``–``hi``. The clip keeps the stroke in that band.

    ``below`` includes ``lo`` and stops short of ``hi`` (counts under the usual range: ``hi`` is p10 and still
    inside). Otherwise the band starts above ``lo`` (p90) and includes the top of the scale.
    """
    top, bottom = panel.y(hi), panel.y(lo)
    if bottom - top <= 1:
        return
    svg.clip(clip_id, panel.left, top, panel.width, bottom - top)
    pred = (lambda value: lo <= value < hi) if below else (lambda value: lo < value <= hi)
    panel.series(_marked(values, pred), color, width, clip=clip_id)


def _enough(values):
    return sum(value is not None for value in values) >= 2


def _shared_end(document):
    """One end date for all four panels, so their x-axes line up."""
    newest = None
    for field, flags in (("overload_share", False), ("guard", True), ("hsdir", True), ("directory", False)):
        day, _value = latest_value(document, field, flags)
        if day is None:
            continue
        stamp = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        if newest is None or stamp > newest:
            newest = stamp
    return newest


def _through(document, field, flags, text):
    """Name the last day when this series stops before the shared axis."""
    end = _shared_end(document)
    day, _value = latest_value(document, field, flags)
    if end is None or day is None or day >= end.date():
        return text
    return "%s · through %s %d" % (text, day.strftime("%b"), day.day)


def _open(document, field, period, flags=False, end=None):
    newest = end
    if newest is None:
        for key, row in (document.get("days") or {}).items():
            if not isinstance(row, dict) or not isinstance(row.get(field), (int, float)):
                continue
            try:
                day = datetime.strptime(key, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
            if newest is None or day > newest:
                newest = day
    if newest is None:
        return None
    stamps, values = series_window(document, field, newest, period, flags)
    if not _enough(values):
        return None
    return stamps, values


def _band(document, key):
    band = (document.get("bands") or {}).get(key) or {}
    return band.get("p10"), band.get("p90")


def _panel(svg, clip_id, y, stamps, yhi, ticks, ylabel, yfmt, period, height=200):
    panel = Panel(svg, clip_id, LEFT, y, PLOT_WIDTH, height, stamps, 0, yhi, _axis_end(stamps), 86400)
    panel.yaxis(ticks, ylabel, fmt=yfmt, close=True)
    panel.xaxis(period, labels=True)
    return panel


def _scale(values, floor, stay_under, headroom, floor_ticks):
    peak = max(value for value in values if value is not None)
    yhi = floor if peak <= stay_under else max(floor, peak * headroom)
    return yhi, (floor_ticks if yhi <= floor else nice_ticks(yhi))


def overload_chart(document, period):
    opened = _open(document, "overload_share", period, end=_shared_end(document))
    if not opened:
        return None
    stamps, values = opened
    p10, p90 = _band(document, "overload")
    status, began, _share = status_since(document, p90 if p90 is not None else HIGH_SHARE)
    latest_day, latest = latest_value(document, "overload_share")
    subtitle = "Share of relays publishing a descriptor that day"
    if status and began and latest_day is not None:
        subtitle = "%s since %s %d · %.1f%% on %s %d" % (
            status.capitalize(), began.strftime("%b"), began.day, latest, latest_day.strftime("%b"), latest_day.day)
    svg = Svg(WIDTH)
    y = _header(svg, "", "Relays Reporting Overload · " + PERIOD_SPAN[period], subtitle)
    if p10 is not None and p90 is not None:
        band = "Inside usual range (p10–p90)  %.1f%%–%.1f%%" % (p10, p90)
        y += legend(svg, LEFT, y, [[
            ("line", GREEN, None, band),
            ("line", ORANGE, None, "Up to %.0f%% outside usual range" % HIGH_SHARE),
            ("line", RED, None, "More than %.0f%% outside usual range" % HIGH_SHARE),
        ]], min_width=PLOT_WIDTH)
    yhi, ticks = _scale(values, 30, 24, 1.15, [0, 6, 12, 18, 24])
    panel = _panel(svg, "o" + period, y + 6, stamps, yhi, ticks, "Share (%)", "{:.0f}", period)
    panel.series(values, GREEN, 2.2)
    if p10 is not None and p90 is not None:
        panel.hband(p10, p90, GREEN, 0.18)
        if p90 < HIGH_SHARE:
            panel.hband(p90, HIGH_SHARE, ORANGE, 0.08)
            _clip_band(svg, panel, values, p90, HIGH_SHARE, ORANGE, "oe" + period)
        panel.hband(HIGH_SHARE, yhi, RED, 0.07)
        _clip_band(svg, panel, values, HIGH_SHARE, yhi, RED, "oh" + period)
    if latest is not None:
        _latest(svg, panel, values, "%.1f%%" % latest, RED if p90 is not None and latest > p90 else GREEN)
    return _finish(svg, panel)


def _count_chart(document, period, field, title, subtitle, color, outside, width, opacity, height=200):
    flags = field != "directory"
    subtitle = _through(document, field, flags, subtitle)
    opened = _open(document, field, period, flags=flags, end=_shared_end(document))
    if not opened:
        return None
    stamps, values = opened
    p10, p90 = _band(document, field)
    if field == "directory":
        yhi, ticks = _scale(values, 80, 70, 1.15, [0, 20, 40, 60, 80])
        ylabel, yfmt, point = "Gbit/s", "{:.0f}", "%.0f"
        usual = "%.1f–%.1f" % (p10, p90) if p10 is not None and p90 is not None else ""
    else:
        yhi, ticks = _scale(values, 7500, 7500, 1.1, _COUNT_TICKS)
        ylabel, yfmt, point = "Relays", "{:,.0f}", "{:,}"
        usual = "%s–%s" % (point.format(p10), point.format(p90)) if p10 is not None and p90 is not None else ""
    svg = Svg(WIDTH)
    y = _header(svg, "", title + " · " + PERIOD_SPAN[period], subtitle)
    if usual and outside:
        inside = "Inside usual range (p10–p90)  " + usual
    elif outside:
        inside = "Inside usual range"
    else:
        inside = "Daily average"
    entries = [("line", color, None, inside)]
    if field == "directory" or (outside and p10 is not None):
        entries.append(("line", RED, None, "Above usual range" if outside == "above" else "Outside usual range"))
    y += legend(svg, LEFT, y, [entries], min_width=PLOT_WIDTH)
    panel = _panel(svg, field[:1] + period, y + 6, stamps, yhi, ticks, ylabel, yfmt, period, height)
    if p10 is not None and p90 is not None:
        panel.hband(p10, p90, GREEN, opacity)
    panel.series(values, color, width)
    if outside == "both" and p10 is not None and p90 is not None:
        _clip_band(svg, panel, values, p90, yhi, RED, "a" + field + period)
        _clip_band(svg, panel, values, 0, p10, RED, "b" + field + period, below=True)
    elif outside == "above" and p90 is not None:
        _clip_band(svg, panel, values, p90, yhi, RED, "a" + field + period, width=2.2)
    _day, latest = latest_value(document, field, flags=field != "directory")
    if latest is not None:
        if outside == "above":
            hot = p90 is not None and latest > p90
        elif outside == "both":
            hot = p10 is not None and (latest < p10 or (p90 is not None and latest > p90))
        else:
            hot = False
        _latest(svg, panel, values, point % latest if field == "directory" else point.format(latest), RED if hot else color)
    return _finish(svg, panel)


def guard_chart(document, period):
    p10, _p90 = _band(document, "guard")
    began, days = guard_below_since(document, p10)
    subtitle = "Daily average count"
    if began:
        subtitle = "Confirms a sustained problem · under the usual range since %s %d · %d days" % (
            began.strftime("%b"), began.day, days)
    return _count_chart(document, period, "guard", "Relays with Guard Flag", subtitle, GREEN, "both", 2.2, 0.14)


def hsdir_chart(document, period):
    off, counted = hsdir_noise(document)
    subtitle = "Daily average count"
    if counted:
        # The counted days are the May 2025–May 2026 baseline. The median uses the previous 28 readings.
        subtitle = "May 2025–May 2026 · %d of %d days moved more than 10%% from the previous 28 readings" % (
            off, counted)
    return _count_chart(document, period, "hsdir", "Relays with HSDir Flag", subtitle, BLUE, "both", 1.8, 0.12)


def directory_chart(document, period):
    return _count_chart(
        document, period, "directory", "Directory Bytes Served",
        "Bytes relays sent while answering directory requests", GREEN, "above", 2.0, 0.16, height=176)


CHARTS = (
    ("overload", overload_chart),
    ("guard", guard_chart),
    ("hsdir", hsdir_chart),
    ("directory", directory_chart),
)
