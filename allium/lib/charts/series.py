"""Onionoo bandwidth series helpers. No matplotlib."""

from datetime import datetime, timedelta, timezone

from .cache import history_block
from .identity import operator_from_contact, role_from_flags

# Same cut as the frozen census and the mockup overlay builder.
MIN_THROUGHPUT_BPS = 50000
# Need two aligned write+read points to draw; thinner history is skipped.
MIN_ALIGNED_POINTS = 2


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


def parse_ms(ms):
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)


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
    if not block or not block.get("values"):
        return [], []
    first = parse_onionoo_ts(block.get("first"))
    if first is None:
        return [], []
    interval = int(block.get("interval") or 0)
    factor = float(block.get("factor") or 1)
    ts, vals = [], []
    for i, raw in enumerate(block["values"]):
        if raw is None:
            continue
        ts.append(first + timedelta(seconds=i * interval))
        vals.append(raw * factor)
    return ts, vals


def bytes_to_mbit(vals):
    return [v * 8.0 / 1000000.0 for v in vals]


def advertised_mbit(advertised_bandwidth):
    return (advertised_bandwidth or 0) * 8.0 / 1000000.0


def month_blocks(bandwidth_relay):
    """Return (write_1m, read_1m) history blocks, or (None, None)."""
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
    return {
        "ts": keys,
        "write_bps": [wmap[t] for t in keys],
        "read_bps": [rmap[t] for t in keys],
        "write_m": bytes_to_mbit([wmap[t] for t in keys]),
        "read_m": bytes_to_mbit([rmap[t] for t in keys]),
    }


def has_1m_graph(bandwidth_relay):
    write_1m, read_1m = month_blocks(bandwidth_relay)
    return aligned_1m_series(write_1m, read_1m) is not None


def daily_ratios(bandwidth_relay, min_bps=MIN_THROUGHPUT_BPS):
    """``{timestamp: write/read}`` for overlay medians. Skips thin days."""
    write_1m, read_1m = month_blocks(bandwidth_relay)
    series = aligned_1m_series(write_1m, read_1m)
    if not series:
        return {}
    out = {}
    for t, w, r in zip(series["ts"], series["write_bps"], series["read_bps"]):
        if not r:
            continue
        if (w + r) / 2.0 < min_bps:
            continue
        out[t] = w / r
    return out


def align_overlay_values(median_by_ts, write_1m):
    """Values list aligned to this relay's 1M slots (including holes)."""
    if not median_by_ts:
        return []
    values = []
    for ts in timestamps_for_block(write_1m):
        values.append(median_by_ts.get(ts))
    return values


def overlay_by_timestamp(ts, overlay):
    """Map an aligned overlay onto the drawn timestamps."""
    if not overlay or not overlay.get("values") or not ts:
        return {}
    write_ts = timestamps_for_block({
        "first": overlay.get("first") or (ts[0].strftime("%Y-%m-%d %H:%M:%S") if ts else None),
        "interval": overlay.get("interval") or 86400,
        "values": overlay["values"],
    })
    if len(write_ts) != len(overlay["values"]) and ts:
        # Fallback: zip against the drawn series when lengths match that.
        if len(overlay["values"]) == len(ts):
            return {
                t: v for t, v in zip(ts, overlay["values"]) if v is not None
            }
    out = {}
    for t, v in zip(write_ts, overlay["values"]):
        if v is None:
            continue
        out[t] = v
    return out


def overlay_lookup(drawn_ts, overlay, write_1m=None):
    """Values for ``drawn_ts`` from an aligned ``{n, values}`` overlay."""
    if not overlay or not overlay.get("values"):
        return None
    if write_1m:
        full_ts = timestamps_for_block(write_1m)
        by_ts = {
            t: v for t, v in zip(full_ts, overlay["values"]) if v is not None
        }
        return [by_ts.get(t) for t in drawn_ts]
    if len(overlay["values"]) == len(drawn_ts):
        return list(overlay["values"])
    return None


def contact_group_key(relay):
    """Stable operator group: contact hash, else url: host."""
    relay = relay or {}
    md5 = relay.get("contact_md5")
    if md5:
        return "md5:" + md5
    host = operator_from_contact(relay.get("contact"))
    if host:
        return "host:" + host
    return ""


def build_bandwidth_map(bandwidth_data):
    """Fingerprint → raw /bandwidth relay. Local to avoid a hot-path import."""
    out = {}
    if not bandwidth_data:
        return out
    for row in bandwidth_data.get("relays") or []:
        fp = row.get("fingerprint")
        if fp:
            out[fp] = row
    return out


def chartable_fingerprints(details_relays, bandwidth_map):
    """Fingerprints that have a drawable 1M write+read graph."""
    fps = []
    for relay in details_relays or []:
        fp = relay.get("fingerprint")
        if not fp or not str(fp).isalnum():
            continue
        if has_1m_graph(bandwidth_map.get(fp)):
            fps.append(fp)
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
    """Role and contact-group daily-median write/read maps.

    Computed once in the parent. Workers receive aligned ``{n, values}``.
    Operator overlay is omitted later when the contact group has one relay.
    """
    role_days = {}
    role_n = {}
    contact_days = {}
    contact_n = {}
    for relay in details_relays or []:
        fp = relay.get("fingerprint")
        daily = daily_ratios(bandwidth_map.get(fp))
        if not daily:
            continue
        role = role_from_flags(relay.get("flags"))
        role_n[role] = role_n.get(role, 0) + 1
        bucket = role_days.setdefault(role, {})
        for ts, ratio in daily.items():
            bucket.setdefault(ts, []).append(ratio)
        key = contact_group_key(relay)
        if not key:
            continue
        contact_n[key] = contact_n.get(key, 0) + 1
        cbucket = contact_days.setdefault(key, {})
        for ts, ratio in daily.items():
            cbucket.setdefault(ts, []).append(ratio)

    role_median = {}
    for role, days in role_days.items():
        role_median[role] = {ts: _median(vals) for ts, vals in days.items()}
    contact_median = {}
    for key, days in contact_days.items():
        contact_median[key] = {ts: _median(vals) for ts, vals in days.items()}
    return {
        "role_median": role_median,
        "role_n": role_n,
        "contact_median": contact_median,
        "contact_n": contact_n,
    }


def overlays_for_relay(relay, write_1m, precomputed):
    """Aligned family/role overlays for the cache payload and the renderer."""
    role = role_from_flags(relay.get("flags"))
    role_n = (precomputed.get("role_n") or {}).get(role, 0)
    role_median = (precomputed.get("role_median") or {}).get(role) or {}
    role_overlay = None
    if role_median:
        role_overlay = {
            "n": role_n,
            "values": align_overlay_values(role_median, write_1m),
        }
    key = contact_group_key(relay)
    contact_n = (precomputed.get("contact_n") or {}).get(key, 0)
    family_overlay = None
    if key and contact_n >= 2:
        contact_median = (precomputed.get("contact_median") or {}).get(key) or {}
        family_overlay = {
            "n": contact_n,
            "values": align_overlay_values(contact_median, write_1m),
        }
    return family_overlay, role_overlay
