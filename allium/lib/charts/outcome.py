"""Bandwidth chart subtitles: facts about what each panel draws, so they hold by construction."""

from datetime import timedelta

from ..time_utils import SECONDS_PER_DAY
from .series import MIN_ACTIVE_KBYTES

# Dates on these periods' charts carry the year: their windows can hold the same month and day twice.
YEAR_PERIODS = ("1y", "5y")


def mbit(value):
    """``45,790`` / ``4.1`` / ``0.74`` / ``<0.01``: whole Mbit/s from 10 up, two significant digits below."""
    if 0 < value < 0.01:
        return "<0.01"
    return "{:,.0f}".format(value) if value >= 10 else "{:.2g}".format(value)


def format_day(dt, year=False):
    """``Jul 22`` (``Jul 22 '25`` with ``year``) without a leading zero. Portable (no ``%-d``)."""
    return "{} {}{}".format(dt.strftime("%b"), dt.day, dt.strftime(" '%y") if year else "")


def format_day_span(dates, step=timedelta(days=1), year=False, of=None, most=3):
    """``Jul 22–23, Aug 2``: runs of dates at most ``step`` apart; past ``most`` runs ``Jul 2–Sep 9 (12 of 30
    days)``, ``of`` being how many dates there were to pick from (``points`` for steps over a day); with
    ``most`` below 0 only ``on 12 of 30 days``."""
    dates = sorted(dates)
    runs = []
    for date in dates:
        if runs and date - runs[-1][1] <= step:
            runs[-1][1] = date
        else:
            runs.append([date, date])

    def span(start, end):
        if start == end:
            return format_day(start, year)
        if (start.year, start.month) == (end.year, end.month) and not year:
            return "{} {}–{}".format(start.strftime("%b"), start.day, end.day)
        return "{}–{}".format(format_day(start, year), format_day(end, year))

    count = "{}{} {}".format(len(dates), " of {}".format(of) if of else "", "days" if step <= timedelta(days=1) else "points")
    if most < 0:
        return "on " + count
    if len(runs) > most:
        return "{} ({})".format(span(dates[0], dates[-1]), count)
    return ", ".join(span(start, end) for start, end in runs)


def ratio_text(value, *edges):
    """``1.12``, with more decimals where two would print one of ``edges`` that the value is not on: ``1.0097``
    under a band starting at 1.01."""
    for digits in range(2, 8):
        text = "{:.{}f}".format(value, digits)
        if not any(text == "{:.{}f}".format(edge, digits) and value != edge for edge in edges):
            break
    return text


def throughput_subtitle(ts, write, advertised, period="1m"):
    """``Write avg 48 Mbit/s (44% of advertised), peak 170 Mbit/s Sep 16``: the share of today's advertised
    bandwidth only up to 100% (a long period's mean can exceed what a relay advertises now), no peak at 0."""
    mean = sum(write) / len(write)
    peak_t, peak = max(zip(ts, write), key=lambda point: point[1])
    share = 100.0 * mean / advertised if 0 < mean <= advertised else None
    return "Write avg {} Mbit/s{}{}".format(
        mbit(mean), "" if share is None else " ({} of advertised)".format("<1%" if share < 0.5 else "%.0f%%" % share),
        ", peak {} Mbit/s {}".format(mbit(peak), format_day(peak_t, year=period in YEAR_PERIODS)) if peak else "")


def ratio_subtitle(rows, overlays, bands, period="1m", interval=SECONDS_PER_DAY, most=3):
    """Write/read over ``rows`` of ``(t, write, read, write/read)``, the days with enough traffic to compare.

    The overall ratio (of sums, as the band census) and its band, then the days beyond p2–p98 on each side, then
    whether the family and peer medians in ``overlays`` (1M relay charts) left it on the same side on at least
    half of those days. ``most`` runs of days are listed per side before they collapse (``format_day_span``).
    """
    if not rows:
        return "Under {} KB/s throughout: too little traffic to compare".format(MIN_ACTIVE_KBYTES)
    tlo, thi, ilo, ihi = bands["typical_lo"], bands["typical_hi"], bands["invest_lo"], bands["invest_hi"]
    overall = sum(row[1] for row in rows) / sum(row[2] for row in rows)
    band = "typical" if tlo <= overall <= thi else "uncommon" if ilo <= overall <= ihi else "investigate"
    parts = ["Write/read {} overall ({})".format(ratio_text(overall, tlo, thi, ilo, ihi), band)]
    beyond = {row[0]: row[3] > ihi for row in rows if not ilo <= row[3] <= ihi}  # day -> above p98 (or below p2)
    step, year = timedelta(seconds=interval or SECONDS_PER_DAY), period in YEAR_PERIODS
    for label, side in (("above p98", True), ("below p2", False)):
        days = [t for t, high in beyond.items() if high is side]
        if days:
            parts.append("{} {}".format(label, format_day_span(days, step, year, len(rows), most)))
    if not beyond:
        return parts[0] + " · inside p2–p98 throughout"

    def shared(overlay):
        """True if ``overlay`` was beyond p2–p98 on the relay's side on at least half of those days, None
        without values on them."""
        hits = [overlay[t] > ihi if high else overlay[t] < ilo for t, high in beyond.items() if overlay.get(t) is not None]
        return 2 * sum(hits) >= len(hits) if hits else None

    left = {key: shared(overlays.get(key) or {}) for key in ("family", "role")}
    moved = [word for key, word in (("family", "the family"), ("role", "other " + bands["peers"])) if left[key]]
    stayed = [word for key, word in (("family", "family"), ("role", "peers")) if left[key] is False]
    if moved:
        parts.append("out with " + " and ".join(moved))
    if stayed:
        parts.append(" and ".join(stayed) + " stayed in")
    return " · ".join(parts)
