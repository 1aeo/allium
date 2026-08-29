"""Tests for chart cache keys and sidecar hit/miss."""

import os

from allium.lib.charts.cache import (
    CACHE_SCHEMA_VERSION,
    build_relay_bandwidth_1m_payload,
    cache_dir,
    cache_hit,
    cache_key,
    cached_png_path,
    publish_png,
    published_png_path,
    sidecar_matches,
    sidecar_path,
    write_sidecar,
)
from allium.lib.charts.pipeline import RELAY_BANDWIDTH_1M
from allium.lib.charts.series import history_block, is_relay_fingerprint
from tests.unit.charts.conftest import FP_JEANGRAE, make_bw, make_relay

_F3_TS_MS = 1786597200000


def _bw(**extra):
    return make_bw(
        write_values=[10, 20, None, 30],
        read_values=[12, 18, None, 28],
        factor=250.0,
        first="2026-07-16 12:00:00",
        last="2026-08-15 12:00:00",
        **extra
    )


def _payload(**overrides):
    relay = make_relay()
    bandwidth = _bw()
    extra = {
        "relays_published": "2026-08-15 06:00:00",
        "bands_frozen_from": "2026-08-15 19:00:00",
    }
    if "relay" in overrides:
        relay.update(overrides.pop("relay"))
    if "bandwidth_relay" in overrides:
        bandwidth.update(overrides.pop("bandwidth_relay"))
    extra.update(overrides)
    return build_relay_bandwidth_1m_payload(relay, bandwidth_relay=bandwidth, **extra)


def test_cache_key_covers_drawn_fields_only():
    base_payload = _payload()
    base = cache_key(base_payload)
    assert len(base) == 64
    assert set(base) <= set("0123456789abcdef")
    assert cache_key(_payload()) == base
    shuffled = {k: base_payload[k] for k in reversed(list(base_payload))}
    assert cache_key(shuffled) == base
    other = _bw()
    other["write_history"] = {
        "1_month": dict(other["write_history"]["1_month"], values=[10, 21, None, 30]),
    }
    assert cache_key(_payload(bandwidth_relay=other)) != base
    for relay in (
        {"nickname": "other"},
        {"contact": "url:example.com"},
        {"advertised_bandwidth": 1},
        {"flags": ["Exit", "Fast"]},
        {"last_restarted": "2026-01-01 00:00:00"},
        {"overload_general_timestamp": 1},
    ):
        assert cache_key(_payload(relay=relay)) != base
    assert cache_key(_payload(renderer_version="2")) != base
    assert cache_key(_payload(bands_frozen_from="2030-01-01 00:00:00")) != base
    guard = {
        "role": "Guard", "typical_lo": 1.01, "typical_hi": 1.17,
        "invest_lo": 0.99, "invest_hi": 1.58, "n": 4444,
    }
    assert cache_key(_payload(bands=guard)) != base
    assert cache_key(_payload(bands=guard)) != cache_key(
        _payload(bands=dict(guard, typical_hi=1.18))
    )
    family = {"n": 24, "values": [1.01, 1.02]}
    assert cache_key(_payload(family_overlay=family)) != base
    payload = _payload()
    for leaked in (
        "observed_bandwidth", "consensus_weight", "last_seen", "uptime",
        "as_name", "contact", "votes", "relays_published", "bandwidth_units",
    ):
        assert leaked not in payload
    assert payload["schema_version"] == CACHE_SCHEMA_VERSION
    assert payload["currently_overloaded"] is False
    assert payload["role"] == "Guard"
    assert payload["operator"] == "1aeo.com"
    assert payload["write_1m"]["values"][2] is None


def test_relays_published_tick_and_overload_flip():
    earlier = _payload(relays_published="2026-08-15 06:00:00")
    later = _payload(relays_published="2026-08-15 12:00:00")
    assert "relays_published" not in earlier
    assert cache_key(earlier) == cache_key(later)
    overloaded = make_relay(overload_general_timestamp=_F3_TS_MS)
    inside = build_relay_bandwidth_1m_payload(
        overloaded, bandwidth_relay=_bw(),
        relays_published="2026-08-15 06:00:00",
        bands_frozen_from="2026-08-15 19:00:00",
    )
    still = build_relay_bandwidth_1m_payload(
        overloaded, bandwidth_relay=_bw(),
        relays_published="2026-08-15 12:00:00",
        bands_frozen_from="2026-08-15 19:00:00",
    )
    expired = build_relay_bandwidth_1m_payload(
        overloaded, bandwidth_relay=_bw(),
        relays_published="2026-08-20 06:00:00",
        bands_frozen_from="2026-08-15 19:00:00",
    )
    assert inside["currently_overloaded"] is True
    assert still["currently_overloaded"] is True
    assert expired["currently_overloaded"] is False
    assert cache_key(inside) == cache_key(still)
    assert cache_key(inside) != cache_key(expired)


def test_period_payload_and_preparsed_blocks():
    write = history_block(_bw()["write_history"]["1_month"])
    read = history_block(_bw()["read_history"]["1_month"])
    assert cache_key(_payload()) == cache_key(_payload(write_1m=write, read_1m=read))
    six = build_relay_bandwidth_1m_payload(
        make_relay(), period="6m", write=write, read=read,
    )
    year = build_relay_bandwidth_1m_payload(
        make_relay(), period="1y", write=write, read=read,
    )
    assert six["chart_id"] == "relay_bandwidth_6m"
    assert six["period"] == "6m"
    assert "family_overlay" not in six
    assert "role_overlay" not in six
    assert cache_key(six) != cache_key(year)
    assert cache_key(six) != cache_key(_payload())
    missing = build_relay_bandwidth_1m_payload(
        make_relay(), bandwidth_relay={"fingerprint": FP_JEANGRAE},
    )
    assert missing["write_1m"] is None
    assert len(cache_key(missing)) == 64


def test_cache_paths_sidecar_and_publish(temp_dir):
    spec = RELAY_BANDWIDTH_1M
    out = "/tmp/www"
    assert cache_dir(out, spec) == "/tmp/www/.chart-cache/relay_bandwidth_1m"
    assert published_png_path(out, spec, FP_JEANGRAE) == (
        "/tmp/www/relay/{}/bandwidth-1m.png".format(FP_JEANGRAE)
    )
    for bad in ("../etc/passwd", "not-hex", "A" * 39, ""):
        assert is_relay_fingerprint(bad) is False
        try:
            sidecar_path(temp_dir, spec, bad)
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError for %r" % (bad,))

    key = cache_key(_payload())
    side = sidecar_path(temp_dir, spec, FP_JEANGRAE)
    assert sidecar_matches(side, key) is False
    assert cache_hit(temp_dir, spec, FP_JEANGRAE, key) is False
    os.makedirs(cache_dir(temp_dir, spec))
    write_sidecar(side, key, spec.chart_id, FP_JEANGRAE)
    assert sidecar_matches(side, key) is True
    assert sidecar_matches(side, "0" * 64) is False
    with open(side, "w", encoding="utf-8") as handle:
        handle.write("not-json")
    assert sidecar_matches(side, key) is False
    write_sidecar(side, key, spec.chart_id, FP_JEANGRAE)
    png = cached_png_path(temp_dir, spec, FP_JEANGRAE)
    with open(png, "wb"):
        pass
    assert cache_hit(temp_dir, spec, FP_JEANGRAE, key) is False
    with open(png, "wb") as handle:
        handle.write(b"png-bytes")
    assert cache_hit(temp_dir, spec, FP_JEANGRAE, key) is True
    dest = published_png_path(temp_dir, spec, FP_JEANGRAE)
    assert publish_png(png, dest) is True
    with open(dest, "rb") as handle:
        assert handle.read() == b"png-bytes"
    os.remove(dest)
    assert publish_png(png, dest) is True
    assert os.path.isfile(dest)
