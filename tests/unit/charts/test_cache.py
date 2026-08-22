"""Tests for chart cache keys and sidecar hit/miss."""

import os

from allium.lib.charts.cache import (
    CACHE_SCHEMA_VERSION,
    build_relay_bandwidth_1m_payload,
    cache_dir,
    cache_hit,
    cache_key,
    cached_png_path,
    history_block,
    published_png_path,
    sidecar_matches,
    sidecar_path,
)
from allium.lib.charts.registry import RELAY_BANDWIDTH_1M

JEANGRAE = "02B1C5DFBCBEC735435652050DE1AF0BB0B108CF"

_BASE_RELAY = {
    "fingerprint": JEANGRAE,
    "nickname": "jeangrae",
    "contact": "url:1aeo.com proof:uri-rsa ciissversion:2",
    "flags": ["Fast", "Guard", "HSDir", "Running", "Stable", "V2Dir"],
    "advertised_bandwidth": 82000000,
    "last_restarted": "2025-10-01 00:00:00",
    "overload_general_timestamp": None,
}

_BASE_BW = {
    "fingerprint": JEANGRAE,
    "write_history": {
        "1_month": {
            "first": "2026-07-16 12:00:00",
            "last": "2026-08-15 12:00:00",
            "interval": 86400,
            "factor": 250.0,
            "values": [10, 20, None, 30],
        }
    },
    "read_history": {
        "1_month": {
            "first": "2026-07-16 12:00:00",
            "last": "2026-08-15 12:00:00",
            "interval": 86400,
            "factor": 250.0,
            "values": [12, 18, None, 28],
        }
    },
}


def _payload(**overrides):
    relay = dict(_BASE_RELAY)
    bandwidth = dict(_BASE_BW)
    extra = {
        "relays_published": "2026-08-15 06:00:00",
        "bandwidth_units": "bits",
        "bands_frozen_from": "2026-08-15 19:00:00",
    }
    if "relay" in overrides:
        relay.update(overrides.pop("relay"))
    if "bandwidth_relay" in overrides:
        bandwidth.update(overrides.pop("bandwidth_relay"))
    extra.update(overrides)
    return build_relay_bandwidth_1m_payload(
        relay,
        bandwidth_relay=bandwidth,
        **extra
    )


def test_history_block_keeps_nones_and_order():
    block = history_block({
        "first": "a",
        "last": "b",
        "interval": 86400,
        "factor": 1.5,
        "values": [1, None, 3],
        "count": 99,
    })
    assert block == {
        "first": "a",
        "last": "b",
        "interval": 86400,
        "factor": 1.5,
        "values": [1, None, 3],
    }


def test_history_block_empty_is_none():
    assert history_block(None) is None
    assert history_block({}) is None
    assert history_block({"values": []}) is None


def test_cache_key_is_64_char_sha256():
    key = cache_key(_payload())
    assert len(key) == 64
    assert set(key) <= set("0123456789abcdef")


def test_cache_key_stable_across_insertion_order():
    payload = _payload()
    shuffled = {k: payload[k] for k in reversed(list(payload))}
    assert cache_key(payload) == cache_key(shuffled)


def test_same_payload_same_key():
    assert cache_key(_payload()) == cache_key(_payload())


def test_write_series_change_changes_key():
    other = dict(_BASE_BW)
    other["write_history"] = {
        "1_month": {
            "first": "2026-07-16 12:00:00",
            "last": "2026-08-15 12:00:00",
            "interval": 86400,
            "factor": 250.0,
            "values": [10, 21, None, 30],
        }
    }
    assert cache_key(_payload()) != cache_key(_payload(bandwidth_relay=other))


def test_identity_and_advertised_and_role_change_key():
    base = cache_key(_payload())
    assert base != cache_key(_payload(relay={"nickname": "other"}))
    assert base != cache_key(_payload(relay={"contact": "url:example.com"}))
    assert base != cache_key(_payload(relay={"advertised_bandwidth": 1}))
    assert base != cache_key(_payload(relay={"flags": ["Exit", "Fast"]}))
    assert base != cache_key(_payload(relay={"last_restarted": "2026-01-01 00:00:00"}))
    assert base != cache_key(_payload(relay={"overload_general_timestamp": 1}))


def test_renderer_version_and_bands_and_units_change_key():
    base = cache_key(_payload())
    assert base != cache_key(_payload(renderer_version="2"))
    assert base != cache_key(_payload(bands_frozen_from="2030-01-01 00:00:00"))
    other = build_relay_bandwidth_1m_payload(
        _BASE_RELAY,
        bandwidth_relay=_BASE_BW,
        relays_published="2026-08-15 06:00:00",
        bandwidth_units="bytes",
        bands_frozen_from="2026-08-15 19:00:00",
    )
    assert base != cache_key(other)


def test_vote_like_fields_are_not_in_payload():
    payload = _payload()
    for leaked in (
        "observed_bandwidth",
        "consensus_weight",
        "last_seen",
        "uptime",
        "as_name",
        "contact",
        "votes",
    ):
        assert leaked not in payload
    assert payload["schema_version"] == CACHE_SCHEMA_VERSION
    assert payload["role"] == "Guard"
    assert payload["operator"] == "1aeo.com"
    assert payload["write_1m"]["values"][2] is None


def test_overlay_change_changes_key():
    base = cache_key(_payload())
    family = {"n": 24, "values": [1.01, 1.02]}
    assert base != cache_key(_payload(family_overlay=family))
    assert cache_key(_payload(family_overlay=family)) == cache_key(
        _payload(family_overlay={"n": 24, "values": [1.01, 1.02]})
    )


def test_missing_1m_history_still_keys():
    payload = build_relay_bandwidth_1m_payload(
        _BASE_RELAY,
        bandwidth_relay={"fingerprint": JEANGRAE},
    )
    assert payload["write_1m"] is None
    assert payload["read_1m"] is None
    assert len(cache_key(payload)) == 64


def test_cache_paths():
    out = "/tmp/www"
    spec = RELAY_BANDWIDTH_1M
    assert cache_dir(out, spec) == "/tmp/www/.chart-cache/relay_bandwidth_1m"
    assert sidecar_path(out, spec, JEANGRAE).endswith(
        ".chart-cache/relay_bandwidth_1m/{}.json".format(JEANGRAE)
    )
    assert cached_png_path(out, spec, JEANGRAE).endswith(
        ".chart-cache/relay_bandwidth_1m/{}.png".format(JEANGRAE)
    )
    assert published_png_path(out, spec, JEANGRAE) == (
        "/tmp/www/relay/{}/bandwidth-1m.png".format(JEANGRAE)
    )


def test_sidecar_matches_and_cache_hit(temp_dir):
    spec = RELAY_BANDWIDTH_1M
    key = cache_key(_payload())
    assert sidecar_matches(sidecar_path(temp_dir, spec, JEANGRAE), key) is False
    assert cache_hit(temp_dir, spec, JEANGRAE, key) is False

    os.makedirs(cache_dir(temp_dir, spec))
    side = sidecar_path(temp_dir, spec, JEANGRAE)
    with open(side, "w", encoding="utf-8") as handle:
        handle.write('{"key": "%s", "chart_id": "relay_bandwidth_1m"}' % key)
    assert sidecar_matches(side, key) is True
    assert sidecar_matches(side, "0" * 64) is False
    assert cache_hit(temp_dir, spec, JEANGRAE, key) is False

    with open(cached_png_path(temp_dir, spec, JEANGRAE), "wb") as handle:
        handle.write(b"png")
    assert cache_hit(temp_dir, spec, JEANGRAE, key) is True


def test_corrupt_sidecar_is_a_miss(temp_dir):
    spec = RELAY_BANDWIDTH_1M
    os.makedirs(cache_dir(temp_dir, spec))
    side = sidecar_path(temp_dir, spec, JEANGRAE)
    with open(side, "w", encoding="utf-8") as handle:
        handle.write("not-json")
    assert sidecar_matches(side, "abc") is False
