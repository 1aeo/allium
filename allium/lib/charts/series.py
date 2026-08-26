"""Onionoo bandwidth series helpers. No matplotlib."""

import re
from datetime import datetime, timedelta, timezone

from .identity import role_from_flags

MIN_THROUGHPUT_BPS = 50000
MIN_ALIGNED_POINTS = 2
_FP_RE = re.compile(r"^[0-9A-Fa-f]{40}$")


def parse_onionoo_ts(value):
    """Parse Onionoo ``YYYY-MM-DD HH:MM:SS`` as UTC."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if not value:
        return None
    return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=timezone.utc
    )


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
    first = parse_onionoo_ts(block.get("first"))
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


def month_blocks(bandwidth_relay):
    bandwidth_relay = bandwidth_relay or {}
    write = history_block((bandwidth_relay.get("write_history") or {}).get("1_month"))
    read = history_block((bandwidth_relay.get("read_history") or {}).get("1_month"))
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


def has_1m_graph(bandwidth_relay):
    write_1m, read_1m = month_blocks(bandwidth_relay)
    return aligned_1m_series(write_1m, read_1m) is not None


def daily_ratios(bandwidth_relay, min_bps=MIN_THROUGHPUT_BPS):
    """``{timestamp: write/read}`` for overlay medians. Skips thin days."""
    series = aligned_1m_series(*month_blocks(bandwidth_relay))
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


def build_bandwidth_map(bandwidth_data):
    out = {}
    if not bandwidth_data:
        return out
    for row in bandwidth_data.get("relays") or []:
        fp = row.get("fingerprint")
        if fp:
            out[fp] = row
    return out


def chartable_fingerprints(details_relays, bandwidth_map, fingerprints=None, limit=0):
    """Fingerprints with a drawable 1M graph. ``limit`` keeps the first N."""
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
        if not is_relay_fingerprint(fp):
            continue
        if wanted is not None and normalize_fingerprint(fp) not in wanted:
            continue
        if has_1m_graph(bandwidth_map.get(fp)):
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


def precompute_overlays(details_relays, bandwidth_map):
    """Role medians once, family medians once per ``effective_family``."""
    role_days, role_n = {}, {}
    family_days, family_n = {}, {}
    for relay in details_relays or []:
        daily = daily_ratios(bandwidth_map.get(relay.get("fingerprint")))
        if not daily:
            continue
        role = role_from_flags(relay.get("flags"))
        role_n[role] = role_n.get(role, 0) + 1
        bucket = role_days.setdefault(role, {})
        for ts, ratio in daily.items():
            bucket.setdefault(ts, []).append(ratio)
        key = family_group_key(relay)
        if not key:
            continue
        family_n[key] = family_n.get(key, 0) + 1
        fbucket = family_days.setdefault(key, {})
        for ts, ratio in daily.items():
            fbucket.setdefault(ts, []).append(ratio)
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
