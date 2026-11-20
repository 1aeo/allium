"""Network pressure charts: overload, Guard, HSDir, and directory bytes served.

One image per Allium period (1M, 6M, 1Y, 5Y). The usual range is the frozen
May 2025–May 2026 p10–p90, drawn the same way on every period.
"""

from datetime import datetime, timedelta, timezone

from ..pressure_history import (
    HIGH_SHARE, guard_below_since, hsdir_noise, latest_value, series_window, status_since,
)
from .render import CREDIT, LEFT, PLOT_WIDTH, WIDTH, _header
from .series import PERIOD_SPAN
from .svg import (
    BLUE, GREEN, MUTED, ORANGE, RED, Panel, Svg, legend, nice_ticks, text_width,
)


def _finish(svg, panel):
    foot = panel.top + panel.height + 42
    svg.text(12, foot, "Usual range is the May 2025–May 2026 p10–p90, frozen.", 11, MUTED)
    svg.text(WIDTH - 12, foot, CREDIT, 11, MUTED, "end")
    return svg.finish(foot + 14)


def _axis_end(stamps):
    span = max((stamps[-1] - stamps[0]).days, 1)
    pad = min(36, max(5, int(round(span * 0.1))))
    end = stamps[-1] + timedelta(days=pad)
    cap = datetime(stamps[-1].year, 12, 20, tzinfo=timezone.utc)
    if stamps[-1].month == 12 and stamps[-1].day > 20:
        cap = stamps[-1] + timedelta(days=4)
    return end if end < cap else cap


def _frame(svg, clip_id, y, stamps, y_hi, ticks, ylabel, yfmt, period, height=200):
    panel = Panel(svg, clip_id, LEFT, y, PLOT_WIDTH, height, stamps, 0, y_hi, _axis_end(stamps), 86400)
    panel.yaxis(ticks, ylabel, fmt=yfmt)
    panel.xaxis(period, labels=True)
    return panel


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


def _clip_band(svg, panel, values, lo, hi, color, clip_id, width=2.4):
    top, bottom = panel.y(hi), panel.y(lo)
    if bottom - top <= 1:
        return
    svg.clip(clip_id, panel.left, top, panel.width, bottom - top)
    panel.series(_marked(values, lambda value: lo < value <= hi), color, width, clip=clip_id)


def _enough(values):
    return sum(value is not None for value in values) >= 2


def _end(document, fields):
    newest = None
    for key, row in document.get("days", {}).items():
        if any(isinstance(row.get(field), (int, float)) for field in fields):
            day = datetime.strptime(key, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if newest is None or day > newest:
                newest = day
    return newest


def overload_chart(document, period):
    end = _end(document, ("overload_share",))
    if end is None:
        return None
    stamps, values = series_window(document, "overload_share", end, period)
    if not _enough(values):
        return None
    band = (document.get("bands") or {}).get("overload") or {}
    p10, p90 = band.get("p10"), band.get("p90")
    status, began, _share = status_since(document, p90 if p90 is not None else HIGH_SHARE)
    latest_day, latest = latest_value(document, "overload_share")
    latest_text = ""
    if latest_day is not None:
        latest_text = "%.1f%% on %s %d" % (latest, latest_day.strftime("%b"), latest_day.day)
    status_text = (status.capitalize() + " since %s %d · " % (began.strftime("%b"), began.day)
                   if status and began else "")
    svg = Svg(WIDTH)
    y = _header(svg, "Tor network", "Relays reporting overload · " + PERIOD_SPAN[period],
                (status_text + latest_text).strip(" ·") or "Share of relays publishing a descriptor that day")
    svg.text(LEFT, y, "A level, about a day late. Pressure, not a cause.", 12, MUTED)
    y += 18
    rows = []
    if p10 is not None and p90 is not None:
        rows.append([("patch", GREEN, 0.28, "Usual range (p10–p90)  %.1f%%–%.1f%%" % (p10, p90))])
        rows.append([
            ("patch", ORANGE, 0.28, "Elevated  to %.0f%%" % HIGH_SHARE),
            ("patch", RED, 0.28, "High  above %.0f%%" % HIGH_SHARE),
        ])
    if rows:
        y += legend(svg, LEFT, y, rows)
    peak = max(value for value in values if value is not None)
    yhi = 30 if peak <= 24 else max(30, peak * 1.15)
    ticks = [0, 6, 12, 18, 24] if yhi <= 30 else nice_ticks(yhi)
    panel = _frame(svg, "o" + period, y + 6, stamps, yhi, ticks, "Share (%)", "{:.0f}", period)
    if p10 is not None and p90 is not None:
        panel.hband(p10, p90, GREEN, 0.18)
        panel.hband(p90, HIGH_SHARE, ORANGE, 0.08)
        panel.hband(HIGH_SHARE, yhi, RED, 0.07)
        panel.series(values, GREEN, 2.2)
        _clip_band(svg, panel, values, p90, HIGH_SHARE, ORANGE, "oe" + period)
        _clip_band(svg, panel, values, HIGH_SHARE, yhi, RED, "oh" + period)
    else:
        panel.series(values, GREEN, 2.2)
    if latest is not None:
        color = RED if p90 is not None and latest > p90 else GREEN
        _latest(svg, panel, values, "%.1f%%" % latest, color)
    return _finish(svg, panel)


def guard_chart(document, period):
    end = _end(document, ("guard",))
    if end is None:
        return None
    stamps, values = series_window(document, "guard", end, period, flags=True)
    if not _enough(values):
        return None
    band = (document.get("bands") or {}).get("guard") or {}
    p10, p90 = band.get("p10"), band.get("p90")
    began, days = guard_below_since(document, p10)
    if began:
        subtitle = "Confirms a sustained problem · under the usual range since %s %d · %d days" % (
            began.strftime("%b"), began.day, days)
    else:
        subtitle = "Daily average count"
    latest_day, latest = latest_value(document, "guard", flags=True)
    svg = Svg(WIDTH)
    y = _header(svg, "", "Relays with the Guard flag · " + PERIOD_SPAN[period], subtitle)
    entries = [("line", GREEN, None, "Inside usual range")]
    if p10 is not None:
        entries.append(("line", RED, None, "Outside usual range"))
        entries.append(("patch", GREEN, 0.22, "Usual range (p10–p90)  %s–%s" % ("{:,}".format(p10), "{:,}".format(p90))))
    y += legend(svg, LEFT, y, [entries])
    panel = _frame(svg, "g" + period, y + 6, stamps, 7500, [0, 1500, 3000, 4500, 6000, 7500],
                   "Relays", "{:,.0f}", period)
    panel.series(values, GREEN, 2.2)
    if p10 is not None and p90 is not None:
        panel.hband(p10, p90, GREEN, 0.14)
        _clip_band(svg, panel, values, p90, 7500, RED, "ga" + period)
        _clip_band(svg, panel, values, 0, p10, RED, "gb" + period)
    if latest is not None:
        color = RED if p10 is not None and latest < p10 else GREEN
        _latest(svg, panel, values, "{:,}".format(latest), color)
    return _finish(svg, panel)


def hsdir_chart(document, period):
    end = _end(document, ("hsdir",))
    if end is None:
        return None
    stamps, values = series_window(document, "hsdir", end, period, flags=True)
    if not _enough(values):
        return None
    band = (document.get("bands") or {}).get("hsdir") or {}
    p10, p90 = band.get("p10"), band.get("p90")
    off, counted = hsdir_noise(document)
    if counted:
        subtitle = "Context · %d of %d quiet-year days were more than 10%% off a 28-day median" % (off, counted)
    else:
        subtitle = "Daily average count, for context"
    svg = Svg(WIDTH)
    y = _header(svg, "", "Relays with the HSDir flag · " + PERIOD_SPAN[period], subtitle)
    entries = [("line", BLUE, None, "Daily average")]
    if p10 is not None:
        entries.append(("patch", GREEN, 0.22, "Usual range (p10–p90)  %s–%s" % (
            "{:,}".format(p10), "{:,}".format(p90))))
    y += legend(svg, LEFT, y, [entries])
    panel = _frame(svg, "h" + period, y + 6, stamps, 7500, [0, 1500, 3000, 4500, 6000, 7500],
                   "Relays", "{:,.0f}", period)
    if p10 is not None and p90 is not None:
        panel.hband(p10, p90, GREEN, 0.12)
    panel.series(values, BLUE, 1.8)
    _latest_day, latest = latest_value(document, "hsdir", flags=True)
    if latest is not None:
        _latest(svg, panel, values, "{:,}".format(latest), BLUE)
    return _finish(svg, panel)


def directory_chart(document, period):
    end = _end(document, ("directory",))
    if end is None:
        return None
    stamps, values = series_window(document, "directory", end, period)
    if not _enough(values):
        return None
    band = (document.get("bands") or {}).get("directory") or {}
    p10, p90 = band.get("p10"), band.get("p90")
    svg = Svg(WIDTH)
    y = _header(svg, "", "Directory bytes served · " + PERIOD_SPAN[period],
                "Bytes relays sent while answering directory requests")
    entries = [("line", GREEN, None, "Inside usual range"), ("line", RED, None, "Above usual range")]
    if p10 is not None and p90 is not None:
        entries.append(("patch", GREEN, 0.22, "Usual range (p10–p90)  %.1f–%.1f" % (p10, p90)))
    y += legend(svg, LEFT, y, [entries])
    peak = max(value for value in values if value is not None)
    yhi = 80 if peak <= 70 else max(80, peak * 1.15)
    ticks = [0, 20, 40, 60, 80] if yhi <= 80 else nice_ticks(yhi)
    panel = _frame(svg, "d" + period, y + 6, stamps, yhi, ticks, "Gbit/s", "{:.0f}", period, height=176)
    panel.series(values, GREEN, 2.0)
    if p10 is not None and p90 is not None:
        panel.hband(p10, p90, GREEN, 0.16)
        _clip_band(svg, panel, values, p90, yhi, RED, "dw" + period, width=2.2)
    _latest_day, latest = latest_value(document, "directory")
    if latest is not None:
        color = RED if p90 is not None and latest > p90 else GREEN
        _latest(svg, panel, values, "%.0f" % latest, color)
    return _finish(svg, panel)


CHARTS = (
    ("overload", overload_chart),
    ("guard", guard_chart),
    ("hsdir", hsdir_chart),
    ("directory", directory_chart),
)
