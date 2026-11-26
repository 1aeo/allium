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
# A trailing bandwidth slot with fewer than this share of the previous slot's relays is still
# being filled in. Onionoo's daily graphs do not all end on the same noon (on 2026-10-23 the
# newest 1-month slot had about 3/4 of the relays and 70% of the write). Summing it draws a
# false drop. Exactly 9/10 stays. A lower count that continues is relays leaving, and stays.
PARTIAL_TAIL_NUMERATOR = 9
PARTIAL_TAIL_DENOMINATOR = 10
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


def _mapping(value):
    """A dict, or ``{}`` when a history field is missing or not an object."""
    return value if isinstance(value, dict) else {}


def _blocks(bandwidth_row, key):
    """The write and read history blocks of one Onionoo period, ``{}`` when missing or malformed."""
    row = _mapping(bandwidth_row)
    return (_mapping(_mapping(row.get("write_history")).get(key)),
            _mapping(_mapping(row.get("read_history")).get(key)))


def _percentiles(values, quantiles):
    """Linear percentiles, the same index as ``numpy.percentile``: ``(n - 1) * quantile / 100``."""
    values, last = sorted(values), len(values) - 1
    out = []
    for quantile in quantiles:
        rank = last * quantile / 100.0
        lo = int(rank)
        frac = rank - lo
        out.append(values[lo] if not frac else values[lo] * (1.0 - frac) + values[min(lo + 1, last)] * frac)
    return out


def _census_ratio(write, read):
    """``sum(write) / sum(read)`` on the shared timestamps, or None under the relay chart's census cut.

    At least three points, and a mean of write and read of at least 50 KB/s.
    """
    both = write.keys() & read.keys()
    if len(both) < 3:
        return None
    total_w, total_r = sum(write[t] for t in both), sum(read[t] for t in both)
    if total_r and total_w + total_r >= 2 * MIN_ACTIVE_MBIT * len(both):
        return total_w / total_r


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


def _without_partial_tail(write, read, counts):
    """``write`` without a trailing slot much thinner than the slot before it.

    ``counts`` is how many relays were summed at each timestamp. The cut repeats while the new
    end is still that thin, and always leaves at least two timestamps. ``_aligned`` drops the
    matching read values. Nothing is removed from the start: a long period opens with fewer relays.
    """
    ts = sorted(write.keys() & read.keys())
    kept = len(ts)
    while len(ts) > 2 and counts[ts[-1]] * PARTIAL_TAIL_DENOMINATOR < counts[ts[-2]] * PARTIAL_TAIL_NUMERATOR:
        ts.pop()
    if len(ts) == kept:
        return write
    keep = set(ts)
    return {t: value for t, value in write.items() if t in keep}


def operator_throughput(members, bandwidth_map, key, since=None, until_slowest=True, ratios=None):
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
    A trailing slot under 9/10 of the previous slot's relays is left off instead (``_without_partial_tail``):
    that slot is still incomplete, and summing it draws a false drop. A lower count that continues stays.
    ``ratios``, when a list, collects each member's own-period census ratio from that same parse
    (``network_ratio_bands``).
    """
    histories = []
    for relay in members:
        for k in _periods_from(key):
            write, read = _blocks(bandwidth_map.get(relay["fingerprint"]), k)
            if not (write.get("values") and read.get("values") and write.get("interval") == read.get("interval")):
                continue
            try:
                step = int(write.get("interval") or 0)
            except (TypeError, ValueError):
                continue  # try the next shorter period; a bad block must not drop the other members
            if step <= 0:
                continue  # not a slot size; a shorter history of this relay may still be
            histories.append((k == key, step, write, read, relay))
            break
    own = Counter(step for native, step, *_rest in histories if native)
    if not own:
        return None, []
    interval = own.most_common(1)[0][0]
    write, read, summed, lasts = Counter(), Counter(), [], []
    # Relay counts for the network chart's incomplete-tail cut. Operator charts do not use it.
    covered = Counter() if not until_slowest else None
    for native, step, wblock, rblock, relay in histories:
        on_grid = step and interval % step == 0
        if not on_grid and not (ratios is not None and native):
            continue  # off this period's grid, and not a census member
        try:
            wpts, rpts = (points(block, MBIT, since) for block in (wblock, rblock))
        except Exception:  # noqa: BLE001 -- one malformed history must not drop the whole sum
            continue
        if ratios is not None and native:
            ratio = _census_ratio(wpts, rpts)
            if ratio is not None:
                ratios.append(ratio)
        if not on_grid:
            continue
        if step != interval:  # a shorter history averaged into this period's slots
            wpts, rpts = (_slotted(pts, step, interval) for pts in (wpts, rpts))
        # As on a member's own chart, only days with both directions: a one-sided day would skew write/read.
        both = wpts.keys() & rpts.keys()
        if both:
            write.update({t: wpts[t] for t in both})
            read.update({t: rpts[t] for t in both})
            summed.append((relay, sum(wpts[t] + rpts[t] for t in both)))
            lasts.append((max(wpts.keys() | rpts.keys()), relay.get("running") is False))
            if covered is not None:
                covered.update(both)
    if until_slowest:
        end = _reported_end(lasts, interval)
        write = {t: value for t, value in write.items() if end and t <= end}
    elif covered:
        write = _without_partial_tail(write, read, covered)
    return _aligned(write, read, interval), summed


def operator_uptime(members, uptime_map, key, windows):
    """Mean running-flag percent per timestamp (the uptime chart's series), or None under two points.

    Same period fallback, interval and reporting cut as ``operator_throughput``. A member contributes
    ``uptime_points``, including the 0% after its history stops; a slot averages the members that have one.
    A malformed history is left out.
    """
    histories = []
    for relay in members:
        section = uptime_section(uptime_map, relay["fingerprint"])
        for period in _periods_from(key):
            block = _mapping(section.get(period))
            step = block.get("interval")
            if isinstance(step, bool) or not isinstance(step, int) or step <= 0:
                continue
            try:
                raw = uptime_points(block, period, windows, relay, section)
            except Exception:  # noqa: BLE001 -- one bad history must not drop the operator chart
                continue
            pts = {t: value for t, value in raw.items()
                   if value == value and value not in (float("inf"), float("-inf"))}
            if not pts:  # nulls or NaN only: try a shorter period instead of voting this interval
                continue
            histories.append((period == key, step, pts, relay))
            break
    steps = Counter(step for native, step, *_rest in histories if native)
    if not steps:
        return None
    interval = steps.most_common(1)[0][0]
    bins, lasts = {}, []
    for _native, step, pts, relay in histories:
        if interval % step:
            continue
        if step != interval:
            pts = _slotted(pts, step, interval)
        if not pts:
            continue
        for t, value in pts.items():
            total, count = bins.get(t, (0.0, 0))
            bins[t] = (total + value, count + 1)
        lasts.append((max(pts), relay.get("running") is False))  # latest finite point, not a trailing NaN
    end = _reported_end(lasts, interval)
    ts = sorted(t for t in bins if end is not None and t <= end)
    return (ts, [bins[t][0] / bins[t][1] for t in ts], interval) if len(ts) >= 2 else None


def network_ratio_bands(ratios):
    """p10/p90 and p2/p98 of census ratios from ``operator_throughput``, or None below ``MIN_NETWORK_CENSUS``.

    ``typical_lo``/``typical_hi`` and ``invest_lo``/``invest_hi`` are what ``bandwidth_chart`` paints.
    ``peers`` is read when a ratio subtitle mentions the peer median; the network chart draws none.
    """
    if len(ratios) < MIN_NETWORK_CENSUS:
        return None
    p2, p10, p90, p98 = _percentiles(ratios, (2, 10, 90, 98))
    return {"role": "network", "peers": "relays", "n": len(ratios), "typical_lo": p10, "typical_hi": p90,
            "invest_lo": p2, "invest_hi": p98}


def uptime_section(uptime_map, fingerprint):
    """The Onionoo uptime object for one relay, or ``{}``."""
    row = _mapping(uptime_map).get(fingerprint)
    return _mapping(_mapping(row).get("uptime"))


def network_uptime(relays, uptime_map, key, windows):
    """Mean running-flag percent at each timestamp of one Onionoo period.

    A relay counts only when it has that period's block (a new relay has no 5-year history, so it does not
    pull the early average) and that block uses the period's most common sampling interval. A timestamp
    almost nobody shares at the end, such as one relay's padded trailing slot, is left out. Early slots stay:
    a long period starts with fewer relays because younger relays have no history yet. Returns
    ``(ts, percents, interval, average, counts)`` or None under two timestamps. ``counts`` is how many
    relays were averaged at each timestamp. ``average`` is the mean of the drawn points, the figure
    ``uptime_chart`` prints, or 0.0 under the same rule as a relay chart: fewer than 30 slots, or 1% or
    less, and the chart states no average.
    """
    intervals, rows = Counter(), []
    for relay in relays:
        section = uptime_section(uptime_map, relay["fingerprint"])
        block = _mapping(section.get(key))
        values = block.get("values")
        # A list of nulls or strings has a length but no samples, so it must not cast the interval vote.
        if not isinstance(values, (list, tuple)) or len(values) < 2 or not any(
                isinstance(value, (int, float)) for value in values):
            continue
        try:
            step = int(block.get("interval") or 0)
        except (TypeError, ValueError):
            continue  # a block that is not Onionoo's; it must not become the period's interval
        if step <= 0 or block.get("interval") != step:
            continue  # int(1.5) is 1; a fraction must not vote as a one-second sample
        intervals[step] += 1
        rows.append((step, relay, section, block))
    if not intervals:
        return None
    interval = intervals.most_common(1)[0][0]
    totals, counts = {}, {}
    for step, relay, section, block in rows:
        if step != interval:
            continue
        try:
            drawn = uptime_points(block, key, windows, relay, section)
        except Exception:  # noqa: BLE001 -- one malformed history must not drop the network chart
            continue
        for stamp, value in drawn.items():
            totals[stamp] = totals.get(stamp, 0.0) + value
            counts[stamp] = counts.get(stamp, 0) + 1
    busiest = max(counts.values(), default=0)
    ts = sorted(totals)
    # Only the trailing edge: a padded slot after the history, not the early years of a long period.
    while len(ts) > 2 and counts[ts[-1]] * 10 < busiest:
        ts.pop()
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
