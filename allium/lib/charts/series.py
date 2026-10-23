"""Onionoo history series for the relay and operator charts."""

import functools
from bisect import bisect_left
from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import median

from ..time_utils import ONIONOO_HISTORY_PERIODS, PERIOD_SHORT_NAMES, parse_onionoo_timestamp
from ..uptime_utils import DEFAULT_UPTIME_FACTOR, block_window
from .bands import role_from_flags

# Onionoo graph-history key -> chart period id ("1_month" -> "1m"), in page order: a chart section shows its first.
PERIODS = tuple((key, PERIOD_SHORT_NAMES[key].lower()) for key in ONIONOO_HISTORY_PERIODS)
PERIOD_SPAN = {"1m": "last 30 days", "6m": "last 6 months", "1y": "last year", "5y": "last 5 years"}
# A history that stopped updating keeps its old slots; charts only show the period's own window.
WINDOW = {"1m": timedelta(days=31), "6m": timedelta(days=183), "1y": timedelta(days=366),
          "5y": timedelta(days=1827)}
MBIT = 8e-6  # bytes/s -> Mbit/s
# Write/read is compared only on days with traffic both ways and a mean of write and read of at least this
# (the band census's cut): quieter days leave the relay's write/read strip and the family and peer medians.
MIN_ACTIVE_KBYTES = 50
MIN_ACTIVE_MBIT = MIN_ACTIVE_KBYTES * 1000 * MBIT
# p2 and p98 of a handful of relays are not a census. The live network is thousands.
MIN_NETWORK_CENSUS = 30
# Fewest family members counted (see active_ratio) for a family median: the median includes the relay
# itself, so with two members it is the mean of this relay and the other, and moves half as far as this relay.
MIN_FAMILY = 3


@functools.lru_cache(maxsize=1 << 12)
def _slots(first, interval, count):
    """The ``count`` slot times of a history block from ``first`` (``()`` without it). The network's blocks
    share about 2,000 (first, interval, length) layouts, so each is built once per process."""
    step = timedelta(seconds=interval)
    return tuple(first + i * step for i in range(count)) if first else ()


def points(block, scale=1.0, since=None, factor=1.0):
    """``{timestamp: value}`` for the numeric slots of an Onionoo history block from ``since`` on.

    Values are multiplied by the block's ``factor`` (the ``factor`` argument
    when it has none) and ``scale``: bandwidth blocks then give bytes/s *
    scale, uptime blocks (factor 1/999) fractions.
    """
    block = block or {}
    values = block.get("values") or ()
    times = _slots(parse_onionoo_timestamp(block.get("first")), int(block.get("interval") or 0), len(values))
    scale *= float(factor if block.get("factor") is None else block["factor"])
    start = bisect_left(times, since) if since else 0
    return {t: v * scale for t, v in zip(times[start:], values[start:]) if isinstance(v, (int, float))}


def uptime_points(block, key, windows, relay=None, section=None):
    """``{timestamp: percent}`` an uptime chart draws for one Onionoo block: its slots inside Onionoo's current
    window, then the window slots it lacks after its end, the slots the relay page averages
    (``uptime_utils.block_window``, given the document's ``uptime_windows``, the relay's details entry and the
    block's section). An offline relay's history stops at its last consensus, but Onionoo counts the time since
    as down: the first missing slot holds the relay's last hours, the rest are 0%. The whole block when there is
    no window. A block without a ``factor`` is read as the page reads it (``DEFAULT_UPTIME_FACTOR``)."""
    drawn = points(block, 100.0, factor=DEFAULT_UPTIME_FACTOR)
    where = block_window(block or {}, key, windows, relay, section)
    if where is None:
        return drawn
    lo, hi, padding, credit = where
    kept = _slots(parse_onionoo_timestamp(block.get("first")), int(block["interval"]), len(block["values"]))[lo:hi]
    drawn = {t: drawn[t] for t in kept if t in drawn}
    for i, midpoint in enumerate(padding):
        drawn[datetime.fromtimestamp(midpoint, timezone.utc)] = credit * 100.0 if i == 0 else 0.0
    return drawn


def _aligned(write, read, interval):
    """``(ts, write, read, interval)`` where both directions have a value, or None under two points."""
    ts = sorted(write.keys() & read.keys())
    return (ts, [write[t] for t in ts], [read[t] for t in ts], interval) if len(ts) >= 2 else None


def _blocks(bandwidth_row, key):
    """The write and read history blocks of one Onionoo period, ``{}`` when missing."""
    return (((bandwidth_row or {}).get("write_history") or {}).get(key) or {},
            ((bandwidth_row or {}).get("read_history") or {}).get(key) or {})


def _percentile(values, quantile):
    """Linear percentile, the same index as ``numpy.percentile``: ``(n - 1) * quantile / 100``."""
    values = sorted(values)
    if len(values) == 1:
        return values[0]
    rank = (len(values) - 1) * quantile / 100.0
    lo = int(rank)
    hi = min(lo + 1, len(values) - 1)
    frac = rank - lo
    return values[lo] * (1.0 - frac) + values[hi] * frac


def active_ratio(write, read):
    """Write/read on a day with traffic enough to compare (``MIN_ACTIVE_MBIT``), else None."""
    return write / read if read and (write + read) / 2 >= MIN_ACTIVE_MBIT else None


def throughput(bandwidth_row, key, since=None):
    """One relay's write and read in Mbit/s for an Onionoo period (see ``_aligned``)."""
    write, read = _blocks(bandwidth_row, key)
    return _aligned(points(write, MBIT, since), points(read, MBIT, since), int(write.get("interval") or 0))


def _slotted(pts, step, interval):
    """``pts``, ``step`` seconds apart, averaged into ``interval``-long slots, whole slots only. Onionoo's slots
    start at multiples of their interval since the epoch, with their point mid-slot, so shorter ones nest."""
    if step == interval:
        return pts
    slots = {}
    for t, v in pts.items():
        slots.setdefault(t - timedelta(seconds=t.timestamp() % interval - interval / 2), []).append(v)
    return {t: sum(vs) / len(vs) for t, vs in slots.items() if len(vs) * step == interval}


def operator_throughput(members, bandwidth_map, key, since=None, until_slowest=True):
    """Members' write and read summed per timestamp, like ``throughput``, plus ``(member, traffic)`` for the
    members summed (their write plus read over the window, in Mbit/s per slot).

    Sums on the period's most common sampling interval. Onionoo leaves out a
    relay's period when a shorter one holds its whole history, so a member
    without this period is summed from its next shorter one, averaged into this
    period's slots; members on other intervals are left out. Members' histories
    reach the newest slot at different times, so with ``until_slowest`` the sum stops at the newest slot
    every member still reporting has reached, not on a partial sum. A member no
    longer running has stopped for good: its end is a real drop, not a delay.
    The network chart passes ``until_slowest=False``: one relay a slot behind must not hide the rest.
    """
    histories = []
    for relay in members:
        for k in ONIONOO_HISTORY_PERIODS[ONIONOO_HISTORY_PERIODS.index(key)::-1]:  # this period, then shorter ones
            write, read = _blocks(bandwidth_map.get(relay["fingerprint"]), k)
            if write.get("values") and read.get("values") and write.get("interval") == read.get("interval"):
                histories.append((k == key, int(write.get("interval") or 0), write, read, relay))
                break
    own = Counter(step for native, step, *_rest in histories if native)
    if not own:
        return None, []
    interval = own.most_common(1)[0][0]
    write, read, summed, lasts = Counter(), Counter(), [], []
    for _native, step, w, r, relay in histories:
        if not step or interval % step:
            continue
        w, r = (_slotted(points(block, MBIT, since), step, interval) for block in (w, r))
        # As on a member's own chart, only days with both directions: a one-sided day would skew write/read.
        both = w.keys() & r.keys()
        if both:
            write.update({t: w[t] for t in both})
            read.update({t: r[t] for t in both})
            summed.append((relay, sum(w[t] + r[t] for t in both)))
            lasts.append((max(w.keys() | r.keys()), relay.get("running") is False))
    if until_slowest:
        newest = max((last for last, _stopped in lasts), default=None)
        reporting = [last for last, stopped in lasts if not stopped and newest - last <= timedelta(seconds=2 * interval)]
        end = min(reporting, default=newest)
        if end:
            write = {t: value for t, value in write.items() if t <= end}
        else:
            write = {}
    return _aligned(write, read, interval), summed


def network_ratio_bands(relays, bandwidth_map, key, since=None):
    """Write/read percentiles of the whole network for one Onionoo period, or None.

    The relay chart's census, counted across every relay instead of one role: each relay's
    ratio of sums (sum of write / sum of read), kept when it has at least three aligned
    points and a mean of write and read of at least 50 KB/s. ``typical_lo``/``typical_hi``
    are p10/p90 and ``invest_lo``/``invest_hi`` are p2/p98, which ``bandwidth_chart`` paints.
    A relay without this period's own history is left out, rather than filled from a shorter
    period the way the network sum is. None below ``MIN_NETWORK_CENSUS`` relays.
    """
    ratios = []
    for relay in relays:
        row = throughput(bandwidth_map.get(relay["fingerprint"]), key, since)
        if not row:
            continue
        ts, write, read, _interval = row
        if len(ts) < 3 or not sum(read):
            continue
        if sum(write) + sum(read) < 2 * MIN_ACTIVE_MBIT * len(ts):
            continue
        ratios.append(sum(write) / sum(read))
    if len(ratios) < MIN_NETWORK_CENSUS:
        return None
    p2, p10, p90, p98 = (_percentile(ratios, q) for q in (2, 10, 90, 98))
    # ``peers`` is what the ratio subtitle says when a peer median leaves the band with the line. The network
    # chart has no peer median, so the word is unused; the subtitle still looks the key up.
    return {"role": "network", "peers": "relays", "n": len(ratios), "typical_lo": p10, "typical_hi": p90,
            "invest_lo": p2, "invest_hi": p98}


def uptime_section(uptime_map, fingerprint):
    """The Onionoo uptime object for one relay, or ``{}``."""
    return ((uptime_map or {}).get(fingerprint) or {}).get("uptime") or {}


def network_uptime(relays, uptime_map, key, windows):
    """Mean running-flag percent at each timestamp of one Onionoo period.

    A relay counts only when it has that period's block (a new relay has no 5-year history, so it does not
    pull the early average) and that block uses the period's most common sampling interval. A timestamp
    almost nobody shares, such as one relay's padded trailing slot, is left out. Returns
    ``(ts, percents, interval, average, counts)`` or None under two timestamps. ``counts`` is how many
    relays were averaged at each timestamp. ``average`` is the mean of the drawn points, the figure
    ``uptime_chart`` prints, or 0.0 under the same rule as a relay chart: fewer than 30 slots, or 1% or
    less, and the chart states no average.
    """
    intervals = Counter()
    for relay in relays:
        block = uptime_section(uptime_map, relay["fingerprint"]).get(key) or {}
        if len(block.get("values") or ()) >= 2:
            intervals[int(block.get("interval") or 0)] += 1
    if not intervals:
        return None
    interval = intervals.most_common(1)[0][0]
    totals, counts = {}, {}
    for relay in relays:
        section = uptime_section(uptime_map, relay["fingerprint"])
        block = section.get(key) or {}
        if int(block.get("interval") or 0) != interval or len(block.get("values") or ()) < 2:
            continue
        drawn = uptime_points(block, key, windows, relay, section)
        for stamp, value in drawn.items():
            totals[stamp] = totals.get(stamp, 0.0) + value
            counts[stamp] = counts.get(stamp, 0) + 1
    busiest = max(counts.values(), default=0)
    ts = [stamp for stamp in sorted(totals) if counts[stamp] * 10 >= busiest]
    if len(ts) < 2:
        return None
    percent = [totals[stamp] / counts[stamp] for stamp in ts]
    average = sum(percent) / len(percent)
    # _compute_uptime_percentage_and_datapoints: a relay chart shows no average under 30 slots or at 1% or less.
    if len(percent) < 30 or average <= 1.0:
        average = 0.0
    return ts, percent, interval, average, [counts[stamp] for stamp in ts]


def family_key(relay):
    """Onionoo's sorted effective family (which includes the relay) when it has other members."""
    family = relay.get("effective_family") or ()
    return tuple(family) if len(family) > 1 else None


def peer_medians(relays, bandwidth_map, since=None):
    """Daily write/read medians per role and per effective family, from every relay's 1M history.

    Returns ``({role: {ts: median}}, {family: (n, {ts: median})})``. A relay
    only counts on days with an ``active_ratio``.
    """
    by_role, by_fp = {}, {}
    for relay in relays:
        try:
            series = throughput(bandwidth_map.get(relay["fingerprint"]), "1_month", since)
        except Exception:  # noqa: BLE001 -- a malformed history: ChartWriter._save skips that relay's charts too
            continue
        ratios = ((t, active_ratio(w, r)) for t, w, r in zip(*series[:3])) if series else ()
        daily = {t: ratio for t, ratio in ratios if ratio is not None}
        if daily:
            by_role.setdefault(role_from_flags(relay.get("flags")), []).append(daily)
            by_fp[relay["fingerprint"]] = daily

    def medians(dailies, least=1):
        days = {}
        for daily in dailies:
            for t, ratio in daily.items():
                days.setdefault(t, []).append(ratio)
        return {t: median(ratios) for t, ratios in days.items() if len(ratios) >= least}

    # A family's median is over its members, as the relay page lists them: effective families are not always
    # the same from each member's side, so the relays sharing one family tuple are not the whole family. Each
    # day needs MIN_FAMILY members counted too, or the median there could be this relay alone.
    families = {}
    for key in dict.fromkeys(filter(None, map(family_key, relays))):
        dailies = [by_fp[fp] for fp in key if fp in by_fp]
        if len(dailies) >= MIN_FAMILY:
            families[key] = (len(dailies), medians(dailies, MIN_FAMILY))
    return {role: medians(dailies) for role, dailies in by_role.items()}, families
