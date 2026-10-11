"""Bandwidth chart subtitles: what stood out in throughput and in write/read. Empty on thin history or all-clear."""

from datetime import timedelta

from ..time_utils import SECONDS_PER_DAY

ALL_PERIOD = {"1m": "all month", "6m": "all 6 months", "1y": "all year", "5y": "all 5 years"}
# Dates on these periods' charts carry the year: their windows can hold the same month and day twice.
YEAR_PERIODS = ("1y", "5y")


def mbit(value):
    """``45,790`` / ``4.1`` / ``0.74``: whole Mbit/s from 10 up, two significant digits below."""
    return "{:,.0f}".format(value) if value >= 10 else "{:.2g}".format(value)


def format_day(dt, year=False):
    """``Jul 22`` (``Jul 22 '25`` with ``year``) without a leading zero. Portable (no ``%-d``)."""
    return "{} {}{}".format(dt.strftime("%b"), dt.day, dt.strftime(" '%y") if year else "")


def format_day_span(dates, step=timedelta(days=1), year=False):
    """``Jul 22–23, Aug 2``: runs of dates at most ``step`` apart, or ``Jul 2–Sep 9 (12 days)`` past three runs."""
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

    if len(runs) > 3:
        unit = "days" if step <= timedelta(days=1) else "times"
        return "{} ({} {})".format(span(dates[0], dates[-1]), len(dates), unit)
    return ", ".join(span(start, end) for start, end in runs)


def _left_typical(times, overlay, bands):
    """True if the overlay is outside typical at half or more of ``times``, None without values there."""
    hits = [not bands["typical_lo"] <= overlay[t] <= bands["typical_hi"] for t in times if overlay.get(t) is not None]
    return sum(hits) >= (len(hits) + 1) // 2 if hits else None


def subtitles(rows, advertised, overlays, bands, period="1m", interval=SECONDS_PER_DAY):
    """``(throughput, write/read)`` subtitles for ``rows`` of ``(t, write, read, ratio)``."""
    if len(rows) < 3:
        return "", ""
    role, peers = bands["role"], bands["peers"]
    tlo, thi, ilo, ihi = bands["typical_lo"], bands["typical_hi"], bands["invest_lo"], bands["invest_hi"]
    invest = [row for row in rows if not ilo <= row[3] <= ihi]
    mean_write, mean_read, mean_ratio = (sum(column) / len(rows) for column in list(zip(*rows))[1:])
    typical = tlo <= mean_ratio <= thi
    outside = not ilo <= mean_ratio <= ihi
    write_heavy = [row[3] for row in invest if row[3] > thi]
    read_heavy = [row[3] for row in invest if row[3] < tlo]
    util = 100.0 * mean_write / advertised if advertised else None
    # The larger excursion past the typical band names the spike (the callout shows the write side).
    if write_heavy and (not read_heavy or max(write_heavy) / thi >= tlo / max(min(read_heavy), 1e-9)):
        spike = "Write"
    else:
        spike = "Read" if read_heavy else None
    persistent = outside and len(invest) >= max(5, len(rows) // 3)
    spiked = util is not None and spike and not persistent
    # "Dropped" means low against advertised too, not just a small relay.
    dropped = util is not None and not spiked and util < 25 and mean_write < 20 and mean_read < 20
    if not (spiked or dropped or invest) and typical:
        return "", ""

    invest_ts = [row[0] for row in invest]
    span = format_day_span(invest_ts, timedelta(seconds=interval or SECONDS_PER_DAY), year=period in YEAR_PERIODS)
    when = " " + span if span else ""
    util_bit = mbit(mean_write) + " Mbit/s" + (" ({:.0f}% of advertised)".format(util) if util is not None else "")
    if spiked:
        throughput = "{} spiked{} · {}".format(spike, when, util_bit)
    elif dropped:
        throughput = "Write and read both dropped {} · {}".format(span or ALL_PERIOD[period], util_bit)
    else:
        throughput = util_bit

    if not invest:
        ratio = "" if typical else "Write/read {:.2f} · inside the {} band with other {}".format(mean_ratio, role, peers)
    elif _left_typical(invest_ts, overlays.get("role", {}), bands):
        ratio = "Outside the band with other {}{}".format(peers, when)
    elif _left_typical(invest_ts, overlays.get("family", {}), bands):
        ratio = "Outside the {} band{} with the family · other {} stayed".format(role, when, peers)
    else:
        # Family and peer lines are only drawn (and only checked) on 1M relay charts.
        ratio = "Outside the {} band{}{}".format(role, when, " · family and peers stayed" if overlays else "")
    return throughput, ratio
