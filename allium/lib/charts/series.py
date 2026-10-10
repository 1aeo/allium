"""Onionoo history series for the relay and operator charts."""

from collections import Counter
from datetime import timedelta

from ..time_utils import ONIONOO_HISTORY_PERIODS, PERIOD_SHORT_NAMES, parse_onionoo_timestamp
from .identity import role_from_flags

# Onionoo graph-history key -> chart period id ("1_month" -> "1m"). 1M is the relay page's own period.
PERIODS = tuple((key, PERIOD_SHORT_NAMES[key].lower()) for key in ONIONOO_HISTORY_PERIODS)
PERIOD_SPAN = {"1m": "last 30 days", "6m": "last 6 months", "1y": "last year", "5y": "last 5 years"}
# A history that stopped updating keeps its old slots; charts only show the period's own window.
WINDOW = {"1m": timedelta(days=31), "6m": timedelta(days=183), "1y": timedelta(days=366),
          "5y": timedelta(days=1827)}
MBIT = 8e-6  # bytes/s -> Mbit/s
# Relays below this mean throughput are left out of the family and peer medians.
MIN_OVERLAY_MBIT = 50000 * MBIT


def points(block, scale=1.0, since=None):
    """``{timestamp: value}`` for the numeric slots of an Onionoo history block from ``since`` on.

    Values are multiplied by the block's ``factor`` and ``scale``: bandwidth
    blocks then give bytes/s * scale, uptime blocks (factor 1/999) fractions.
    """
    first = parse_onionoo_timestamp((block or {}).get("first"))
    if first is None:
        return {}
    step = timedelta(seconds=int(block.get("interval") or 0))
    scale *= float(block.get("factor") or 1)
    out = {first + i * step: v * scale for i, v in enumerate(block.get("values") or ())
           if isinstance(v, (int, float))}
    return {t: v for t, v in out.items() if t >= since} if since else out


def _aligned(write, read, interval):
    """``(ts, write, read, interval)`` where both directions have a value, or None under two points."""
    ts = sorted(write.keys() & read.keys())
    return (ts, [write[t] for t in ts], [read[t] for t in ts], interval) if len(ts) >= 2 else None


def _blocks(bandwidth_row, key):
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
    rows = []
    for relay in members:
        write, read = _blocks(bandwidth_map.get(relay["fingerprint"]), key)
        if write.get("values") and read.get("values") and write.get("interval") == read.get("interval"):
            rows.append((int(write["interval"] or 0), write, read, relay))
    if not rows:
        return None, []
    interval = Counter(row[0] for row in rows).most_common(1)[0][0]
    rows = [row for row in rows if row[0] == interval]
    write, read = Counter(), Counter()
    for _interval, w, r, _relay in rows:
        write.update(points(w, MBIT, since))
        read.update(points(r, MBIT, since))
    return _aligned(write, read, interval), [row[3] for row in rows]


def family_key(relay):
    """Onionoo's sorted effective family (which includes the relay) when it has other members."""
    family = relay.get("effective_family") or ()
    return tuple(family) if len(family) > 1 else None


def _median(values):
    values = sorted(values)
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2.0


def peer_medians(relays, bandwidth_map, since=None):
    """Daily write/read medians per role and per effective family, from every relay's 1M history.

    Returns ``({role: {ts: median}}, {family: (n, {ts: median})})``. A relay
    only counts on days its mean throughput reaches ``MIN_OVERLAY_MBIT``.
    """
    by_role, by_family = {}, {}
    for relay in relays:
        series = throughput(bandwidth_map.get(relay["fingerprint"]), "1_month", since)
        if not series:
            continue
        daily = {t: w / r for t, w, r in zip(*series[:3]) if r and (w + r) / 2 >= MIN_OVERLAY_MBIT}
        if not daily:
            continue
        by_role.setdefault(role_from_flags(relay.get("flags")), []).append(daily)
        key = family_key(relay)
        if key:
            by_family.setdefault(key, []).append(daily)

    def medians(dailies):
        days = {}
        for daily in dailies:
            for t, ratio in daily.items():
                days.setdefault(t, []).append(ratio)
        return {t: _median(ratios) for t, ratios in days.items()}

    return (
        {role: medians(dailies) for role, dailies in by_role.items()},
        {key: (len(dailies), medians(dailies)) for key, dailies in by_family.items() if len(dailies) >= 2},
    )
