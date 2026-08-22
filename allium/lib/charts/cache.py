"""Content-hash cache for chart PNGs.

Daily rebuilds that only tick votes, uptime scalars, or last_seen must
not redraw every figure. The key is the SHA-256 of the fields that
actually change pixels. See relay-page-chart-pipeline.md.
"""

import hashlib
import json
import os
import shutil

from .identity import operator_from_contact, role_from_flags
from .registry import RELAY_BANDWIDTH_1M_ID

# Bump when the payload layout changes (added/removed/renamed fields).
CACHE_SCHEMA_VERSION = 1

# Onionoo graph-history keys that change the drawn series.
_HISTORY_KEYS = ("first", "last", "interval", "factor", "values")


def history_block(period_data):
    """Normalize one Onionoo graph-history object for hashing.

    Missing or empty history becomes None (thin history / unpublished
    graph). None values inside ``values`` are kept — they are real
    Onionoo holes, not skipped days.
    """
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


def _overload_ratelimits(raw):
    if not raw:
        return None
    return {
        "timestamp": raw.get("timestamp"),
        "write-count": raw.get("write-count"),
        "read-count": raw.get("read-count"),
    }


def _overload_fd(raw):
    if not raw:
        return None
    return {"timestamp": raw.get("timestamp")}


def build_relay_bandwidth_1m_payload(
    relay,
    bandwidth_relay=None,
    relays_published="",
    bandwidth_units="bits",
    family_overlay=None,
    role_overlay=None,
    bands_frozen_from="",
    renderer_version="1",
):
    """Canonical payload for ``relay_bandwidth_1m``.

    ``relay`` is a details-API dict (nickname, flags, advertised,
    last_restarted, contact, overload_general_timestamp).
    ``bandwidth_relay`` is the matching ``/bandwidth`` relay dict, or
    None when that fingerprint has no bandwidth document.
    """
    relay = relay or {}
    bandwidth_relay = bandwidth_relay or {}
    flags = list(relay.get("flags") or [])
    write_history = bandwidth_relay.get("write_history") or {}
    read_history = bandwidth_relay.get("read_history") or {}
    return {
        "schema_version": CACHE_SCHEMA_VERSION,
        "chart_id": RELAY_BANDWIDTH_1M_ID,
        "renderer_version": str(renderer_version),
        "fingerprint": relay.get("fingerprint") or "",
        "relays_published": relays_published or "",
        "bandwidth_units": bandwidth_units or "bits",
        "nickname": relay.get("nickname") or "",
        "operator": operator_from_contact(relay.get("contact")),
        "advertised_bandwidth": relay.get("advertised_bandwidth") or 0,
        "flags": sorted(flags),
        "role": role_from_flags(flags),
        "last_restarted": relay.get("last_restarted") or "",
        "overload_general_timestamp": relay.get("overload_general_timestamp"),
        "overload_ratelimits": _overload_ratelimits(
            bandwidth_relay.get("overload_ratelimits")
            or relay.get("overload_ratelimits")
        ),
        "overload_fd_exhausted": _overload_fd(
            bandwidth_relay.get("overload_fd_exhausted")
            or relay.get("overload_fd_exhausted")
        ),
        "write_1m": history_block(write_history.get("1_month")),
        "read_1m": history_block(read_history.get("1_month")),
        "family_overlay": family_overlay,
        "role_overlay": role_overlay,
        "bands_frozen_from": bands_frozen_from or "",
    }


def cache_key(payload):
    """Return a 64-char hex SHA-256 of the canonical payload JSON."""
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def cache_dir(output_dir, spec):
    """Durable cache directory that write_relay_info() does not rmtree."""
    return os.path.join(output_dir, ".chart-cache", spec.cache_subdir)


def sidecar_path(output_dir, spec, fingerprint):
    return os.path.join(cache_dir(output_dir, spec), fingerprint + ".json")


def cached_png_path(output_dir, spec, fingerprint):
    return os.path.join(cache_dir(output_dir, spec), fingerprint + ".png")


def published_png_path(output_dir, spec, fingerprint):
    return os.path.join(output_dir, spec.output_path(fingerprint))


def sidecar_matches(path, key):
    """True when a sidecar exists and records this exact key."""
    if not path or not os.path.isfile(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get("key") == key


def cache_hit(output_dir, spec, fingerprint, key):
    """True when sidecar key matches and the cached PNG is present."""
    if not sidecar_matches(sidecar_path(output_dir, spec, fingerprint), key):
        return False
    return os.path.isfile(cached_png_path(output_dir, spec, fingerprint))


def write_sidecar(path, key, chart_id, fingerprint):
    """Atomically write the cache sidecar."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    payload = {
        "key": key,
        "chart_id": chart_id,
        "fingerprint": fingerprint,
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
        handle.write("\n")
    os.replace(tmp, path)
    return path


def publish_png(src, dest):
    """Hardlink cache PNG into the relay directory; copy if link fails.

    ``write_relay_info()`` rmtree's ``www/relay/``, so this always runs
    after HTML on a fresh directory.
    """
    if not src or not os.path.isfile(src):
        return False
    parent = os.path.dirname(dest)
    if parent:
        os.makedirs(parent, exist_ok=True)
    if os.path.exists(dest):
        os.remove(dest)
    try:
        os.link(src, dest)
    except OSError:
        shutil.copy2(src, dest)
    return True
