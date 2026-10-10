"""Locked C outcome subtitles. Empty on thin history or all-clear."""

from datetime import timedelta

from .identity import peers_word

ALL_PERIOD = {"1m": "all month", "6m": "all 6 months", "1y": "all year", "5y": "all 5 years"}


def mbit(value):
    """``45,790`` / ``4.1`` / ``0.74``: whole Mbit/s from 10 up, two significant digits below."""
    return "{:,.0f}".format(value) if value >= 10 else "{:.2g}".format(value)


def format_day(dt, year=False):
    """``Jul 22`` (``Jul 22 '25`` with ``year``) without a leading zero. Portable (no ``%-d``)."""
    return "{} {}{}".format(dt.strftime("%b"), dt.day, dt.strftime(" '%y") if year else "")


def format_day_time(dt):
    """``Aug 28, 22:00 UTC``."""
    return "{}, {} UTC".format(format_day(dt), dt.strftime("%H:%M"))


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


def _left_typical(ts, overlay, bands, days):
    """True if the overlay is outside typical on most of those days, None without values."""
    hits = [not bands["typical_lo"] <= overlay[t] <= bands["typical_hi"]
            for t in ts if t.date() in days and overlay.get(t) is not None]
    return sum(hits) >= max(1, (len(hits) + 1) // 2) if hits else None


def subtitles(rows, advertised, overlays, bands, period="1m", interval=86400):
    """``(throughput, write/read)`` subtitles for ``rows`` of ``(t, write, read, ratio)``."""
    role = bands["role"] or "relay"
    invest = [row for row in rows if not bands["invest_lo"] <= row[3] <= bands["invest_hi"]]
    if len(rows) < 3:
        return "", ""
    n = float(len(rows))
    mean_ratio = sum(row[3] for row in rows) / n
    mean_write = sum(row[1] for row in rows) / n
    mean_read = sum(row[2] for row in rows) / n
    if bands["typical_lo"] <= mean_ratio <= bands["typical_hi"]:
        zone = "typical"
    elif bands["invest_lo"] <= mean_ratio <= bands["invest_hi"]:
        zone = "uncommon"
    else:
        zone = "investigate"
    write_heavy = [row[3] for row in invest if row[3] > bands["typical_hi"]]
    read_heavy = [row[3] for row in invest if row[3] < bands["typical_lo"]]
    util = 100.0 * mean_write / advertised if advertised else None
    # The larger excursion past the typical band names the spike (the callout shows the write side).
    if write_heavy and (not read_heavy or max(write_heavy) / bands["typical_hi"]
                        >= bands["typical_lo"] / max(min(read_heavy), 1e-9)):
        spike = "write"
    else:
        spike = "read" if read_heavy else None
    persistent = zone == "investigate" and len(invest) >= max(5, len(rows) // 3)
    if util is None:
        thru = "unknown"
    elif spike and not persistent:
        thru = "spike"
    elif util < 25:
        # "Dropped" means low against advertised too, not just a small relay.
        thru = "crash" if mean_write < 20 and mean_read < 20 else "low"
    else:
        thru = "near" if util >= 70 else "steady"
    if thru not in ("spike", "crash") and not invest and zone == "typical":
        return "", ""

    span = format_day_span([row[0] for row in invest], timedelta(seconds=interval or 86400),
                           year=period in ("1y", "5y"))
    util_bit = mbit(mean_write) + " Mbit/s"
    if util is not None:
        util_bit += " ({:.0f}% of advertised)".format(util)
    if thru == "spike":
        throughput = "{} spiked{}".format("Write" if spike == "write" else "Read", " " + span if span else "")
        throughput += " · " + util_bit
    elif thru == "crash":
        throughput = "Write and read both dropped {} · {}".format(span or ALL_PERIOD[period], util_bit)
    else:
        throughput = util_bit

    days = {row[0].date() for row in invest}
    ts = [row[0] for row in rows]
    peers = peers_word(bands["role"])
    when = " " + span if span else ""
    if not invest:
        ratio = ""
    elif _left_typical(ts, overlays.get("role", {}), bands, days):
        ratio = "Outside the band with other {}{}".format(peers, when)
    elif _left_typical(ts, overlays.get("family", {}), bands, days):
        ratio = "Outside the {} band{} with the family · other {} stayed".format(role, when, peers)
    else:
        # Family and peer lines are only drawn (and only checked) on 1M relay charts.
        ratio = "Outside the {} band{}{}".format(role, when, " · family and peers stayed" if overlays else "")
    if not ratio and zone != "typical":
        ratio = "Write/read {:.2f} · inside the {} band with other {}".format(mean_ratio, role, peers)
    return throughput, ratio
