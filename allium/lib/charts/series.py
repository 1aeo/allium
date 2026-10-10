"""Onionoo bandwidth and uptime series helpers. No matplotlib."""

import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from ..time_utils import parse_onionoo_timestamp
from ..uptime_utils import build_uptime_map
from .identity import role_from_flags

MIN_THROUGHPUT_BPS = 50000
MIN_ALIGNED_POINTS = 2
# Match ``uptime_utils._compute_uptime_percentage_and_datapoints`` (0–999 → %).
UPTIME_PERCENT_SCALE = 100.0 / 999.0
_FP_RE = re.compile(r"^[0-9A-Fa-f]{40}$")
_CONTACT_RE = re.compile(r"^[0-9A-Fa-f]{32}$")
_ONIONOO_TS = "%Y-%m-%d %H:%M:%S"


def history_block(period_data):
    """Normalize one Onionoo graph-history object. Keep ``values`` holes."""
    if not period_data:
        return None
    values = period_data.get("values")
    if not values:
        return None
    return {
        "first": period_data.get("first"),
        "last": period_data.get("last"),
        "interval": period_data.get("interval"),
        "factor": period_data.get("factor"),
        "values": list(values),
    }


def timestamps_for_block(block):
    """One timestamp per Onionoo values slot, including holes."""
    if not block or not block.get("values"):
        return []
    first = parse_onionoo_timestamp(block.get("first"))
    if first is None:
        return []
    interval = int(block.get("interval") or 0)
    return [first + timedelta(seconds=i * interval) for i in range(len(block["values"]))]


def history_series(block):
    """``(timestamps, bytes/s)`` skipping Onionoo nulls."""
    factor = float((block or {}).get("factor") or 1)
    ts, vals = [], []
    for t, raw in zip(timestamps_for_block(block), (block or {}).get("values") or []):
        if raw is None:
            continue
        ts.append(t)
        vals.append(raw * factor)
    return ts, vals


def bytes_to_mbit(vals):
    return [v * 8.0 / 1000000.0 for v in vals]


def advertised_mbit(advertised_bandwidth):
    return (advertised_bandwidth or 0) * 8.0 / 1000000.0


# Onionoo /bandwidth graph keys → published PNG suffix. 1M is the default hero.
SPARK_ONIONOO = (
    ("6_months", "6m"),
    ("1_year", "1y"),
    ("5_years", "5y"),
)
PERIOD_KEYS = (("1_month", "1m"),) + SPARK_ONIONOO
PERIOD_HTML_NAME = {
    "1m": "index.html",
    "6m": "6m.html",
    "1y": "1y.html",
    "5y": "5y.html",
}
PERIOD_TITLE_SPAN = {
    "1m": "last 30 days",
    "6m": "last 6 months",
    "1y": "last year",
    "5y": "last 5 years",
}
PERIOD_SHORT = {"1m": "1M", "6m": "6M", "1y": "1Y", "5y": "5Y"}


def period_blocks(bandwidth_relay, onionoo_key):
    bandwidth_relay = bandwidth_relay or {}
    write = history_block((bandwidth_relay.get("write_history") or {}).get(onionoo_key))
    read = history_block((bandwidth_relay.get("read_history") or {}).get(onionoo_key))
    return write, read


def aligned_1m_series(write_1m, read_1m):
    """Intersect write/read 1M points. None when thinner than two dots."""
    w_ts, w_vals = history_series(write_1m)
    r_ts, r_vals = history_series(read_1m)
    if not w_ts or not r_ts:
        return None
    wmap = dict(zip(w_ts, w_vals))
    rmap = dict(zip(r_ts, r_vals))
    keys = sorted(set(wmap) & set(rmap))
    if len(keys) < MIN_ALIGNED_POINTS:
        return None
    write_bps = [wmap[t] for t in keys]
    read_bps = [rmap[t] for t in keys]
    return {
        "ts": keys,
        "write_bps": write_bps,
        "read_bps": read_bps,
        "write_m": bytes_to_mbit(write_bps),
        "read_m": bytes_to_mbit(read_bps),
    }


def series_by_fp(details_relays, bandwidth_map):
    """One walk: hero 1M plus any drawable 6M/1Y/5Y blocks."""
    out = {}
    bandwidth_map = bandwidth_map or {}
    for relay in details_relays or []:
        fp = relay.get("fingerprint")
        if not is_relay_fingerprint(fp):
            continue
        bw = bandwidth_map.get(fp)
        by_period = {}
        for onionoo_key, suffix in PERIOD_KEYS:
            write, read = period_blocks(bw, onionoo_key)
            aligned = aligned_1m_series(write, read)
            if aligned is None:
                continue
            by_period[suffix] = {"write": write, "read": read, "series": aligned}
        hero = by_period.get("1m")
        if not hero:
            continue
        out[fp] = {
            "write_1m": hero["write"],
            "read_1m": hero["read"],
            "series": hero["series"],
            "periods": by_period,
        }
    return out


def spark_suffixes(parsed):
    """Ordered non-1M period ids that have a drawable graph."""
    periods = (parsed or {}).get("periods") or {}
    return tuple(suffix for _key, suffix in SPARK_ONIONOO if suffix in periods)


def drawable_suffixes(parsed):
    """Ordered period ids (including 1M) that have a drawable graph."""
    periods = (parsed or {}).get("periods") or {}
    return tuple(suffix for _key, suffix in PERIOD_KEYS if suffix in periods)


def uptime_percent_series(block):
    """``(timestamps, percent)`` from an Onionoo uptime block.

    ``None`` is a hole (skipped). ``0`` is a real 0% observation. Does not
    use ``history_series`` (that multiplies by bandwidth ``factor``).
    """
    ts, pct = [], []
    if not block:
        return ts, pct
    values = block.get("values") or []
    for t, raw in zip(timestamps_for_block(block), values):
        if raw is None:
            continue
        if isinstance(raw, (int, float)) and 0 <= raw <= 999:
            ts.append(t)
            pct.append(raw * UPTIME_PERCENT_SCALE)
    return ts, pct


def uptime_by_fp(uptime_data):
    """One walk of ``uptime_data['relays']`` → drawable uptime periods.

    Does not require a bandwidth 1M series. Relays with only longer
    periods still chart. Fingerprints must be 40-hex.
    """
    out = {}
    for fp, row in build_uptime_map(uptime_data).items():
        if not is_relay_fingerprint(fp):
            continue
        periods_obj = row.get("uptime") or {}
        by_period = {}
        for onionoo_key, suffix in PERIOD_KEYS:
            block = history_block(periods_obj.get(onionoo_key))
            ts, _pct = uptime_percent_series(block)
            if len(ts) < MIN_ALIGNED_POINTS:
                continue
            by_period[suffix] = block
        if by_period:
            out[fp] = {"periods": by_period}
    return out


def period_interval_label(block):
    """Onionoo ``interval`` seconds → ``1-day`` / ``1-week`` / ``1-hour``."""
    if isinstance(block, dict):
        raw = block.get("interval")
    else:
        raw = block
    try:
        seconds = int(raw or 0)
    except (TypeError, ValueError):
        return ""
    if seconds <= 0:
        return ""
    for unit_s, name in ((604800, "week"), (86400, "day"), (3600, "hour")):
        if seconds % unit_s == 0:
            n = seconds // unit_s
            return "1-{}".format(name) if n == 1 else "{}-{}".format(n, name)
    return ""


def period_axis_caption(suffix, block=None):
    """Date-axis caption such as ``6M · 1-day``."""
    short = PERIOD_SHORT.get(suffix) or suffix
    bin_label = period_interval_label(block)
    if bin_label:
        return "{} · {}".format(short, bin_label)
    return short


def period_views(drawable_periods):
    """``(filename, hero, sparks)`` for each drawable period as the hero."""
    wanted = set(drawable_periods or ())
    ordered = tuple(suffix for _key, suffix in PERIOD_KEYS if suffix in wanted)
    return tuple(
        (PERIOD_HTML_NAME[hero], hero, tuple(p for p in ordered if p != hero))
        for hero in ordered
    )


def merged_period_views(bw_periods, up_periods):
    """Same period HTML files for bandwidth + uptime. Not a second file family.

    Each row is ``(filename, hero, bw_sparks, extra)`` where ``extra`` sets
    per-page uptime flags. Bandwidth sparks stay bandwidth-only.
    """
    bw_wanted = set(bw_periods or ())
    up_wanted = set(up_periods or ())
    bw_ordered = tuple(s for _k, s in PERIOD_KEYS if s in bw_wanted)
    up_ordered = tuple(s for _k, s in PERIOD_KEYS if s in up_wanted)
    heroes = tuple(s for _k, s in PERIOD_KEYS if s in bw_wanted or s in up_wanted)
    rows = []
    if "1m" not in heroes:
        rows.append((
            "index.html",
            "1m",
            tuple(bw_ordered),
            {
                "has_bandwidth_chart": False,
                "uptime_show_hero": False,
                "uptime_spark_periods": tuple(up_ordered),
            },
        ))
    for hero in heroes:
        extra = {
            "has_bandwidth_chart": hero in bw_wanted,
            "uptime_show_hero": hero in up_wanted,
            "uptime_spark_periods": tuple(p for p in up_ordered if p != hero),
        }
        bw_sparks = (
            tuple(p for p in bw_ordered if p != hero) if hero in bw_wanted else ()
        )
        rows.append((PERIOD_HTML_NAME[hero], hero, bw_sparks, extra))
    return tuple(rows)


def _daily_ratios(series, min_bps=MIN_THROUGHPUT_BPS):
    if not series:
        return {}
    out = {}
    for t, w, r in zip(series["ts"], series["write_bps"], series["read_bps"]):
        if r and (w + r) / 2.0 >= min_bps:
            out[t] = w / r
    return out


def align_overlay_values(median_by_ts, write_1m):
    return [median_by_ts.get(ts) for ts in timestamps_for_block(write_1m)] if median_by_ts else []


def overlay_lookup(drawn_ts, overlay, write_1m=None):
    """Values for ``drawn_ts`` from an aligned ``{n, values}`` overlay."""
    if not overlay or not overlay.get("values"):
        return None
    if write_1m:
        by_ts = {
            t: v for t, v in zip(timestamps_for_block(write_1m), overlay["values"])
            if v is not None
        }
        return [by_ts.get(t) for t in drawn_ts]
    if len(overlay["values"]) == len(drawn_ts):
        return list(overlay["values"])
    return None


def normalize_fingerprint(value):
    return str(value or "").lstrip("$").upper()


def is_relay_fingerprint(value):
    """True for a 40-char hex fingerprint (optional leading ``$``)."""
    return bool(_FP_RE.match(str(value or "").lstrip("$")))


def is_contact_hash(value):
    """True for a 32-char hex contact MD5. Never a 40-hex fingerprint."""
    text = str(value or "")
    return bool(_CONTACT_RE.match(text)) and not is_relay_fingerprint(text)


def is_contact_chart(spec):
    """True when ``ChartSpec.chart_id`` is a contact_* family."""
    return str(getattr(spec, "chart_id", "") or "").startswith("contact_")


def contacts_from_relay_slice(details_relays, selected_fps):
    """Contact MD5s whose members include a sliced relay fingerprint.

    ``--charts-limit`` / ``--fingerprint`` still slice relays. There is no
    ``--contacts-limit``. Hashes that fail ``is_contact_hash`` are skipped.
    """
    wanted = frozenset(selected_fps or ())
    out = []
    seen = set()
    for relay in details_relays or []:
        fp = relay.get("fingerprint")
        if fp not in wanted:
            continue
        hid = relay.get("contact_md5")
        if not is_contact_hash(hid) or hid in seen:
            continue
        seen.add(hid)
        out.append(hid)
    return out


def member_fingerprints_for_contact(
    contact_hash, details_relays, contact_groups=None,
):
    """Member fingerprints from ``sorted['contact'][hash]['relays']`` indices.

    Indices point into ``details_relays`` (the same list as ``json['relays']``).
    Falls back to walking details by ``contact_md5`` when the group is missing.
    """
    if not is_contact_hash(contact_hash):
        return []
    details_relays = details_relays or []
    if contact_groups:
        group = contact_groups.get(contact_hash)
        if group is None:
            wanted = contact_hash.lower()
            for key, val in contact_groups.items():
                if is_contact_hash(key) and key.lower() == wanted:
                    group = val
                    break
        idxs = (group or {}).get("relays") or []
        fps = []
        for idx in idxs:
            if not isinstance(idx, int) or idx < 0 or idx >= len(details_relays):
                continue
            fp = details_relays[idx].get("fingerprint")
            if is_relay_fingerprint(fp):
                fps.append(fp)
        if fps:
            return fps
    wanted = contact_hash.lower()
    fps = []
    for relay in details_relays:
        hid = relay.get("contact_md5")
        if not is_contact_hash(hid) or hid.lower() != wanted:
            continue
        fp = relay.get("fingerprint")
        if is_relay_fingerprint(fp):
            fps.append(fp)
    return fps


def _onionoo_ts(dt):
    if isinstance(dt, datetime) and dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime(_ONIONOO_TS)


def _sum_at_timestamps(timestamps, values, factor, dest):
    factor = float(factor or 1)
    for ts, raw in zip(timestamps, values or []):
        if raw is None:
            continue
        dest[ts] = dest.get(ts, 0.0) + (raw * factor)


def aggregate_operator_bandwidth(member_fps, bandwidth_map, onionoo_key):
    """Sum member write/read at shared timestamps for one Onionoo period.

    Aggregation is **sum** of bytes/s across members that have a value at
    that timestamp. ``extract_operator_daily_bandwidth_totals`` is
    index-aligned and returns averages — do not use it for the x-axis.

    Members without this period's ``history_block`` are omitted. Members
    whose write/read intervals disagree, or that do not match the most
    common interval, are skipped. Does not invent a ``1_month`` series
    when no member publishes that block.

    Returns ``{"write", "read", "member_n"}`` history_blocks (factor 1.0)
    or ``None`` when the aligned series is thinner than two points.
    """
    bandwidth_map = bandwidth_map or {}
    candidates = []
    for fp in member_fps or []:
        if not is_relay_fingerprint(fp):
            continue
        write, read = period_blocks(bandwidth_map.get(fp), onionoo_key)
        if not write or not read:
            continue
        try:
            interval = int(write.get("interval") or 0)
            read_interval = int(read.get("interval") or 0)
        except (TypeError, ValueError):
            continue
        if interval <= 0 or interval != read_interval:
            continue
        w_ts = timestamps_for_block(write)
        r_ts = timestamps_for_block(read)
        if not w_ts or not r_ts:
            continue
        candidates.append((interval, write, read, w_ts, r_ts))
    if not candidates:
        return None
    interval = Counter(item[0] for item in candidates).most_common(1)[0][0]
    chosen = [item for item in candidates if item[0] == interval]
    write_sums = {}
    read_sums = {}
    for _interval, write, read, w_ts, r_ts in chosen:
        _sum_at_timestamps(w_ts, write.get("values"), write.get("factor"), write_sums)
        _sum_at_timestamps(r_ts, read.get("values"), read.get("factor"), read_sums)
    if not write_sums or not read_sums:
        return None
    all_ts = sorted(set(write_sums) | set(read_sums))
    first = all_ts[0]
    last = all_ts[-1]
    n_slots = int(round((last - first).total_seconds() / interval)) + 1
    if n_slots < MIN_ALIGNED_POINTS:
        return None
    write_values = []
    read_values = []
    for i in range(n_slots):
        ts = first + timedelta(seconds=i * interval)
        write_values.append(write_sums.get(ts))
        read_values.append(read_sums.get(ts))
    write_block = {
        "first": _onionoo_ts(first),
        "last": _onionoo_ts(last),
        "interval": interval,
        "factor": 1.0,
        "values": write_values,
    }
    read_block = {
        "first": _onionoo_ts(first),
        "last": _onionoo_ts(last),
        "interval": interval,
        "factor": 1.0,
        "values": read_values,
    }
    if aligned_1m_series(write_block, read_block) is None:
        return None
    return {
        "write": write_block,
        "read": read_block,
        "member_n": len(chosen),
    }


def contact_spark_suffixes(periods):
    """Ordered non-1M contact periods that have a drawable aggregate."""
    periods = periods or {}
    return tuple(suffix for _key, suffix in SPARK_ONIONOO if suffix in periods)


def contact_hero_period(periods):
    """First drawable period in ``PERIOD_KEYS`` order, or ``None``."""
    periods = periods or {}
    for _key, suffix in PERIOD_KEYS:
        if suffix in periods:
            return suffix
    return None


def family_group_key(relay):
    """Stable family id from Onionoo ``effective_family``. Not contact/AROI."""
    members = []
    for raw in (relay or {}).get("effective_family") or []:
        fp = normalize_fingerprint(raw)
        if fp:
            members.append(fp)
    self_fp = normalize_fingerprint((relay or {}).get("fingerprint"))
    if self_fp and self_fp not in members:
        members.append(self_fp)
    if not members:
        return ""
    return "fam:" + ",".join(sorted(set(members)))


def chartable_fingerprints(
    details_relays, bandwidth_map, fingerprints=None, limit=0, series=None,
    also=None,
):
    """Fingerprints with a drawable graph. ``limit`` keeps the first N.

    ``series`` is the bandwidth map (1M required there). ``also`` is an
    optional sibling map (uptime periods) so a relay without bandwidth 1M
    can still be sliced by ``--charts-limit`` / ``--fingerprint``.
    """
    if series is None:
        series = series_by_fp(details_relays, bandwidth_map)
    extra = also or {}
    wanted = None
    if fingerprints:
        wanted = frozenset(
            normalize_fingerprint(fp) for fp in fingerprints if fp
        )
    try:
        cap = int(limit or 0)
    except (TypeError, ValueError):
        cap = 0
    fps = []
    for relay in details_relays or []:
        fp = relay.get("fingerprint")
        if fp not in series and fp not in extra:
            continue
        if wanted is not None and normalize_fingerprint(fp) not in wanted:
            continue
        fps.append(fp)
        if cap > 0 and len(fps) >= cap:
            break
    return fps


def _median(values):
    values = sorted(values)
    n = len(values)
    if n == 0:
        return None
    mid = n // 2
    if n % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2.0


def _add_daily(bucket, n_map, key, daily):
    n_map[key] = n_map.get(key, 0) + 1
    dest = bucket.setdefault(key, {})
    for ts, ratio in daily.items():
        dest.setdefault(ts, []).append(ratio)


def precompute_overlays(details_relays, bandwidth_map, series=None):
    """Role medians once, family medians once per ``effective_family``."""
    if series is None:
        series = series_by_fp(details_relays, bandwidth_map)
    role_days, role_n = {}, {}
    family_days, family_n = {}, {}
    for relay in details_relays or []:
        parsed = series.get(relay.get("fingerprint"))
        daily = _daily_ratios(parsed["series"]) if parsed else None
        if not daily:
            continue
        _add_daily(role_days, role_n, role_from_flags(relay.get("flags")), daily)
        key = family_group_key(relay)
        if key:
            _add_daily(family_days, family_n, key, daily)
    return {
        "role_median": {
            role: {ts: _median(vals) for ts, vals in days.items()}
            for role, days in role_days.items()
        },
        "role_n": role_n,
        "family_median": {
            key: {ts: _median(vals) for ts, vals in days.items()}
            for key, days in family_days.items()
        },
        "family_n": family_n,
    }


def overlays_for_relay(relay, write_1m, precomputed):
    role = role_from_flags(relay.get("flags"))
    role_median = (precomputed.get("role_median") or {}).get(role) or {}
    role_overlay = None
    if role_median:
        role_overlay = {
            "n": (precomputed.get("role_n") or {}).get(role, 0),
            "values": align_overlay_values(role_median, write_1m),
        }
    key = family_group_key(relay)
    family_n = (precomputed.get("family_n") or {}).get(key, 0)
    family_overlay = None
    if key and family_n >= 2:
        family_median = (precomputed.get("family_median") or {}).get(key) or {}
        family_overlay = {
            "n": family_n,
            "values": align_overlay_values(family_median, write_1m),
        }
    return family_overlay, role_overlay
