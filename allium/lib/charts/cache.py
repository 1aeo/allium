"""Content-hash cache for chart PNGs. Key is SHA-256 of drawn fields."""

import hashlib
import json
import os
import shutil

from ..stability_utils import current_overload_status
from .identity import operator_from_contact, role_from_flags
from .registry import RELAY_BANDWIDTH_1M_ID
from .series import history_block, is_relay_fingerprint, published_clock

# Bump when the payload layout changes.
CACHE_SCHEMA_VERSION = 3


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


def _overload_fields(relay, bandwidth_relay=None):
    """The three Onionoo overload fields, bandwidth preferred over details."""
    relay = relay or {}
    bandwidth_relay = bandwidth_relay or {}
    return {
        "overload_general_timestamp": relay.get("overload_general_timestamp"),
        "overload_ratelimits": _overload_ratelimits(
            bandwidth_relay.get("overload_ratelimits")
            or relay.get("overload_ratelimits")
        ),
        "overload_fd_exhausted": _overload_fd(
            bandwidth_relay.get("overload_fd_exhausted")
            or relay.get("overload_fd_exhausted")
        ),
    }


def currently_overloaded(relay, bandwidth_relay=None, relays_published=""):
    """True when overload is active at the published clock (not wall time)."""
    return bool(current_overload_status(
        _overload_fields(relay, bandwidth_relay),
        published_clock(relays_published),
    ))


def bands_key_fields(bands):
    """Numeric row that changes pixels. None if bands were not supplied."""
    if not bands:
        return None
    return {
        "role": bands.get("role") or "",
        "typical_lo": bands.get("typical_lo"),
        "typical_hi": bands.get("typical_hi"),
        "invest_lo": bands.get("invest_lo"),
        "invest_hi": bands.get("invest_hi"),
        "n": bands.get("n") or 0,
    }


def build_relay_bandwidth_1m_payload(
    relay,
    bandwidth_relay=None,
    relays_published="",
    family_overlay=None,
    role_overlay=None,
    bands=None,
    bands_frozen_from="",
    renderer_version="1",
    write_1m=None,
    read_1m=None,
):
    """Canonical payload for ``relay_bandwidth_1m``.

    ``relays_published`` is the 72h clock only; the payload stores
    derived ``currently_overloaded``. Band numbers live in ``bands`` so
    a census edit without a new ``frozen_from`` still misses.
    """
    relay = relay or {}
    bandwidth_relay = bandwidth_relay or {}
    flags = list(relay.get("flags") or [])
    fields = _overload_fields(relay, bandwidth_relay)
    if write_1m is None:
        write_1m = history_block(
            (bandwidth_relay.get("write_history") or {}).get("1_month")
        )
    if read_1m is None:
        read_1m = history_block(
            (bandwidth_relay.get("read_history") or {}).get("1_month")
        )
    return {
        "schema_version": CACHE_SCHEMA_VERSION,
        "chart_id": RELAY_BANDWIDTH_1M_ID,
        "renderer_version": str(renderer_version),
        "fingerprint": relay.get("fingerprint") or "",
        "currently_overloaded": bool(current_overload_status(
            fields, published_clock(relays_published),
        )),
        "nickname": relay.get("nickname") or "",
        "operator": operator_from_contact(relay.get("contact")),
        "advertised_bandwidth": relay.get("advertised_bandwidth") or 0,
        "flags": sorted(flags),
        "role": role_from_flags(flags),
        "last_restarted": relay.get("last_restarted") or "",
        "overload_general_timestamp": fields["overload_general_timestamp"],
        "overload_ratelimits": fields["overload_ratelimits"],
        "overload_fd_exhausted": fields["overload_fd_exhausted"],
        "write_1m": write_1m,
        "read_1m": read_1m,
        "family_overlay": family_overlay,
        "role_overlay": role_overlay,
        "bands": bands_key_fields(bands),
        "bands_frozen_from": bands_frozen_from or "",
    }


def cache_key(payload):
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def cache_dir(output_dir, spec):
    return os.path.join(output_dir, ".chart-cache", spec.cache_subdir)


def _fp_cache_path(output_dir, spec, fingerprint, suffix):
    if not is_relay_fingerprint(fingerprint):
        raise ValueError("invalid relay fingerprint")
    return os.path.join(cache_dir(output_dir, spec), fingerprint + suffix)


def sidecar_path(output_dir, spec, fingerprint):
    return _fp_cache_path(output_dir, spec, fingerprint, ".json")


def cached_png_path(output_dir, spec, fingerprint):
    return _fp_cache_path(output_dir, spec, fingerprint, ".png")


def published_png_path(output_dir, spec, fingerprint):
    if not is_relay_fingerprint(fingerprint):
        raise ValueError("invalid relay fingerprint")
    return os.path.join(output_dir, spec.output_path(fingerprint))


def sidecar_matches(path, key):
    if not path or not os.path.isfile(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get("key") == key


def cache_hit(output_dir, spec, fingerprint, key):
    if not is_relay_fingerprint(fingerprint):
        return False
    if not sidecar_matches(sidecar_path(output_dir, spec, fingerprint), key):
        return False
    png = cached_png_path(output_dir, spec, fingerprint)
    try:
        return os.path.isfile(png) and os.path.getsize(png) > 0
    except OSError:
        return False


def write_sidecar(path, key, chart_id, fingerprint):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(
            {"key": key, "chart_id": chart_id, "fingerprint": fingerprint},
            handle, separators=(",", ":"),
        )
        handle.write("\n")
    os.replace(tmp, path)
    return path


def publish_png(src, dest):
    """Hardlink cache PNG into the relay directory; copy if link fails."""
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
