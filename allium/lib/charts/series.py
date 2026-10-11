"""Onionoo history series for the relay and operator charts."""

import functools
from bisect import bisect_left
from collections import Counter
from datetime import timedelta
from statistics import median

from ..time_utils import ONIONOO_HISTORY_PERIODS, PERIOD_SHORT_NAMES, parse_onionoo_timestamp
from .bands import role_from_flags

# Onionoo graph-history key -> chart period id ("1_month" -> "1m"), in page order: a chart section shows its first.
PERIODS = tuple((key, PERIOD_SHORT_NAMES[key].lower()) for key in ONIONOO_HISTORY_PERIODS)
PERIOD_SPAN = {"1m": "last 30 days", "6m": "last 6 months", "1y": "last year", "5y": "last 5 years"}
# A history that stopped updating keeps its old slots; charts only show the period's own window.
WINDOW = {"1m": timedelta(days=31), "6m": timedelta(days=183), "1y": timedelta(days=366),
          "5y": timedelta(days=1827)}
MBIT = 8e-6  # bytes/s -> Mbit/s
# Days a relay's mean of write and read is below this (50 KB/s, the band census's cut) are left out of the
# family and peer medians.
MIN_OVERLAY_MBIT = 50000 * MBIT
# Fewest family members counted (see MIN_OVERLAY_MBIT) for a family median: the median includes the relay
# itself, so with two members it is the mean of this relay and the other, and moves half as far as this relay.
MIN_FAMILY = 3


@functools.lru_cache(maxsize=1 << 12)
def _slots(first, interval, count):
    """The ``count`` slot times of a history block from ``first`` (``()`` without it). The network's blocks
    share about 2,000 (first, interval, length) layouts, so each is built once per process."""
    step = timedelta(seconds=interval)
    return tuple(first + i * step for i in range(count)) if first else ()


def points(block, scale=1.0, since=None):
    """``{timestamp: value}`` for the numeric slots of an Onionoo history block from ``since`` on.

    Values are multiplied by the block's ``factor`` and ``scale``: bandwidth
    blocks then give bytes/s * scale, uptime blocks (factor 1/999) fractions.
    """
    block = block or {}
    values = block.get("values") or ()
    times = _slots(parse_onionoo_timestamp(block.get("first")), int(block.get("interval") or 0), len(values))
    scale *= float(block.get("factor") or 1)
    start = bisect_left(times, since) if since else 0
    return {t: v * scale for t, v in zip(times[start:], values[start:]) if isinstance(v, (int, float))}


def _aligned(write, read, interval):
    """``(ts, write, read, interval)`` where both directions have a value, or None under two points."""
    ts = sorted(write.keys() & read.keys())
    return (ts, [write[t] for t in ts], [read[t] for t in ts], interval) if len(ts) >= 2 else None


def _blocks(bandwidth_row, key):
    """The write and read history blocks of one Onionoo period, ``{}`` when missing."""
    return (((bandwidth_row or {}).get("write_history") or {}).get(key) or {},
            ((bandwidth_row or {}).get("read_history") or {}).get(key) or {})


def throughput(bandwidth_row, key, since=None):
    """One relay's write and read in Mbit/s for an Onionoo period (see ``_aligned``)."""
    write, read = _blocks(bandwidth_row, key)
    return _aligned(points(write, MBIT, since), points(read, MBIT, since), int(write.get("interval") or 0))


def operator_throughput(members, bandwidth_map, key, since=None):
    """Members' write and read summed per timestamp, like ``throughput``, plus the members summed.

    Only members on the most common sampling interval are summed, so 1-day and
    2-day histories never mix.
    """
    by_interval = {}
    for relay in members:
        write, read = _blocks(bandwidth_map.get(relay["fingerprint"]), key)
        if write.get("values") and read.get("values") and write.get("interval") == read.get("interval"):
            by_interval.setdefault(int(write.get("interval") or 0), []).append((write, read, relay))
    if not by_interval:
        return None, []
    interval, rows = max(by_interval.items(), key=lambda item: len(item[1]))
    write, read = Counter(), Counter()
    for w, r, _relay in rows:
        w, r = points(w, MBIT, since), points(r, MBIT, since)
        # As on a member's own chart, only days with both directions: a one-sided day would skew write/read.
        write.update({t: v for t, v in w.items() if t in r})
        read.update({t: r[t] for t in w if t in r})
    return _aligned(write, read, interval), [row[2] for row in rows]


def family_key(relay):
    """Onionoo's sorted effective family (which includes the relay) when it has other members."""
    family = relay.get("effective_family") or ()
    return tuple(family) if len(family) > 1 else None


def peer_medians(relays, bandwidth_map, since=None):
    """Daily write/read medians per role and per effective family, from every relay's 1M history.

    Returns ``({role: {ts: median}}, {family: (n, {ts: median})})``. A relay
    only counts on days its mean throughput reaches ``MIN_OVERLAY_MBIT``.
    """
    by_role, by_fp = {}, {}
    for relay in relays:
        try:
            series = throughput(bandwidth_map.get(relay["fingerprint"]), "1_month", since)
        except Exception:  # noqa: BLE001 -- a malformed history: ChartWriter._save skips that relay's charts too
            continue
        daily = {t: w / r for t, w, r in zip(*series[:3]) if r and (w + r) / 2 >= MIN_OVERLAY_MBIT} if series else {}
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
