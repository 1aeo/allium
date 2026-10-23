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


def _periods_from(key):
    """``key`` and each shorter Onionoo period. A young relay's whole history lives in a shorter one."""
    return ONIONOO_HISTORY_PERIODS[ONIONOO_HISTORY_PERIODS.index(key)::-1]


def _reported_end(lasts, interval):
    """Newest time every still-running member has reached, or None when ``lasts`` is empty.

    ``lasts`` is ``(timestamp, stopped)``. A stopped member does not hold the series. A running member more
    than two slots behind has stopped updating, so later slots keep the members that remain.
    """
    newest = max((last for last, _stopped in lasts), default=None)
    if newest is None:
        return None
    lag = timedelta(seconds=2 * interval)
    reporting = [last for last, stopped in lasts if not stopped and newest - last <= lag]
    return min(reporting, default=newest)


def operator_throughput(members, bandwidth_map, key, since=None):
    """Members' write and read summed per timestamp, like ``throughput``, plus ``(member, traffic)`` for the
    members summed (their write plus read over the window, in Mbit/s per slot).

    Sums on the period's most common sampling interval. Onionoo leaves out a
    relay's period when a shorter one holds its whole history, so a member
    without this period is summed from its next shorter one, averaged into this
    period's slots; members on other intervals are left out. Members' histories
    reach the newest slot at different times, so the sum stops at the newest slot
    every member still reporting has reached, not on a partial sum. A member no
    longer running has stopped for good: its end is a real drop, not a delay.
    """
    histories = []
    for relay in members:
        for k in _periods_from(key):
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
    end = _reported_end(lasts, interval)
    return _aligned({t: v for t, v in write.items() if end and t <= end}, read, interval) if end else None, summed


def operator_uptime(members, uptime_map, key, windows):
    """Mean running-flag percent per timestamp (the uptime chart's series), or None under two points.

    Same period fallback, interval and reporting cut as ``operator_throughput``. A member contributes
    ``uptime_points``, including the 0% after its history stops; a slot averages the members that have one.
    A malformed history is left out.
    """
    histories = []
    for relay in members:
        section = ((uptime_map.get(relay["fingerprint"]) or {}).get("uptime") or {})
        for period in _periods_from(key):
            block = section.get(period) or {}
            step = block.get("interval")
            if block.get("values") and isinstance(step, int) and step > 0:
                histories.append((period == key, step, block, period, section, relay))
                break
    steps = Counter(step for native, step, *_rest in histories if native)
    if not steps:
        return None
    interval = steps.most_common(1)[0][0]
    bins, lasts = {}, []
    for native, step, block, period, section, relay in histories:
        if interval % step:
            continue
        try:
            pts = _slotted(uptime_points(block, period, windows, relay, section), step, interval)
        except Exception:  # noqa: BLE001 -- one bad history must not drop the operator chart
            continue
        if not pts:
            continue
        for t, value in pts.items():
            if value != value or value in (float("inf"), float("-inf")):  # one NaN would make the mean NaN
                continue
            total, count = bins.get(t, (0.0, 0))
            bins[t] = (total + value, count + 1)
        lasts.append((max(pts), relay.get("running") is False))
    end = _reported_end(lasts, interval)
    ts = sorted(t for t in bins if end is not None and t <= end)
    return (ts, [bins[t][0] / bins[t][1] for t in ts], interval) if len(ts) >= 2 else None


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
