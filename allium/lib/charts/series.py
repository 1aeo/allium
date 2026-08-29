"""Onionoo bandwidth series helpers. No matplotlib."""

import re
from datetime import timedelta

from ..bandwidth_utils import build_bandwidth_map
from ..time_utils import parse_onionoo_timestamp, published_clock
from .identity import role_from_flags

MIN_THROUGHPUT_BPS = 50000
MIN_ALIGNED_POINTS = 2
_FP_RE = re.compile(r"^[0-9A-Fa-f]{40}$")


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


def month_blocks(bandwidth_relay):
    return period_blocks(bandwidth_relay, "1_month")


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


def period_title_span(suffix):
    return PERIOD_TITLE_SPAN.get(suffix) or suffix


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


def period_html_name(suffix):
    return PERIOD_HTML_NAME.get(suffix) or "%s.html" % suffix


def period_views(drawable_periods):
    """``(filename, hero, sparks)`` for each drawable period as the hero."""
    wanted = set(drawable_periods or ())
    ordered = tuple(suffix for _key, suffix in PERIOD_KEYS if suffix in wanted)
    return tuple(
        (PERIOD_HTML_NAME[hero], hero, tuple(p for p in ordered if p != hero))
        for hero in ordered
    )


def spark_shared_ylim(periods, advertised_bandwidth=0):
    """Shared Mbit ceiling for one relay's sparks, or None."""
    ceiling = advertised_mbit(advertised_bandwidth)
    for parsed in (periods or {}).values():
        series = parsed.get("series")
        if not series:
            continue
        ceiling = max(ceiling, max(series["write_m"] + series["read_m"] + [0.0]))
    return ceiling or None


def has_1m_graph(bandwidth_relay):
    """Thin boolean for tests. Production uses ``series_by_fp``."""
    return aligned_1m_series(*month_blocks(bandwidth_relay)) is not None


def _daily_ratios(series, min_bps=MIN_THROUGHPUT_BPS):
    if not series:
        return {}
    out = {}
    for t, w, r in zip(series["ts"], series["write_bps"], series["read_bps"]):
        if r and (w + r) / 2.0 >= min_bps:
            out[t] = w / r
    return out


def daily_ratios(bandwidth_relay, min_bps=MIN_THROUGHPUT_BPS):
    """``{timestamp: write/read}`` for overlay medians. Skips thin days."""
    return _daily_ratios(aligned_1m_series(*month_blocks(bandwidth_relay)), min_bps)


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


def chartable_fingerprints(
    details_relays, bandwidth_map, fingerprints=None, limit=0, series=None,
):
    """Fingerprints with a drawable 1M graph. ``limit`` keeps the first N."""
    if series is None:
        series = series_by_fp(details_relays, bandwidth_map)
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
        if fp not in series:
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
