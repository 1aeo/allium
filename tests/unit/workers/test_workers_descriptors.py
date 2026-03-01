"""Unit tests for CollecTor descriptor freshness policy."""

import base64
import copy
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from allium.lib.workers import fetch_collector_descriptors


def _spaced_fp(fingerprint):
    return " ".join(fingerprint[i:i + 4] for i in range(0, len(fingerprint), 4))


def _cert_block_with_family_key(key_hex):
    cert_bytes = bytearray(140)
    cert_bytes[39] = 1  # one extension
    cert_bytes[40:42] = (32).to_bytes(2, "big")
    cert_bytes[42] = 0x04  # family signing key extension
    cert_bytes[43] = 0
    cert_bytes[44:76] = bytes.fromhex(key_hex)
    encoded = base64.b64encode(bytes(cert_bytes)).decode("ascii")
    return "\n".join([
        "-----BEGIN ED25519 CERT-----",
        encoded,
        "-----END ED25519 CERT-----",
    ])


def _descriptor_text(fingerprint, published, with_family_cert=False, family_key_hex=None):
    lines = [
        "router relaytest 127.0.0.1 9001 0 0",
        f"fingerprint {_spaced_fp(fingerprint)}",
        f"published {published}",
    ]
    if with_family_cert:
        lines.append("family-cert")
        lines.append(_cert_block_with_family_key(family_key_hex))
    return "\n".join(lines) + "\n"


def _recent_filename(hours_ago, minutes_offset=0):
    ts = datetime.utcnow() - timedelta(hours=hours_ago, minutes=minutes_offset)
    return ts.strftime("%Y-%m-%d-%H-%M-%S") + "-server-descriptors"


def _listing_html(filenames):
    links = "\n".join(f'<a href="{name}">{name}</a>' for name in filenames)
    return f"<html><body>{links}</body></html>".encode("utf-8")


def _base_cache(fingerprint, family_key):
    return {
        "family_cert_fingerprints": [fingerprint],
        "all_seen_fingerprints": [fingerprint],
        "family_cert_groups": {family_key: [fingerprint]},
        "coverage_hours": 36,
        "fetched_at": datetime.utcnow().isoformat(),
    }


def _run_with_mocks(initial_store, listing_filenames, file_contents):
    store = copy.deepcopy(initial_store)

    def fake_load_cache(name):
        data = store.get(name)
        return copy.deepcopy(data)

    def fake_save_cache(name, data):
        store[name] = copy.deepcopy(data)
        return True

    def fake_retry_with_backoff(fetch_fn=None, args=None, **kwargs):
        url = args[0]
        if url.endswith("/recent/relay-descriptors/server-descriptors/"):
            return _listing_html(listing_filenames)
        if url in file_contents:
            return file_contents[url]
        raise AssertionError(f"Unexpected URL: {url}")

    base_url = "https://collector.torproject.org/recent/relay-descriptors/server-descriptors/"

    cache_manager = MagicMock()
    cache_manager.get_cache_age.return_value = 7200  # force refresh path

    with patch("allium.lib.consensus.is_consensus_evaluation_enabled", return_value=True), \
         patch("allium.lib.workers._cache_manager", cache_manager), \
         patch("allium.lib.workers._load_cache", side_effect=fake_load_cache), \
         patch("allium.lib.workers._save_cache", side_effect=fake_save_cache), \
         patch("allium.lib.workers._retry_with_backoff", side_effect=fake_retry_with_backoff), \
         patch("allium.lib.workers._mark_ready") as mock_mark_ready, \
         patch("allium.lib.workers._mark_stale") as mock_mark_stale:
        result = fetch_collector_descriptors()

    return {
        "result": result,
        "store": store,
        "mock_mark_ready": mock_mark_ready,
        "mock_mark_stale": mock_mark_stale,
        "base_url": base_url,
    }


def test_stale_source_keeps_prior_cache_unchanged():
    fp_old = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    key_old = "11" * 32
    cache = _base_cache(fp_old, key_old)
    filename = _recent_filename(hours_ago=6, minutes_offset=10)
    store = {
        "collector_descriptors": cache,
        "collector_descriptors_files": {},
    }

    run = _run_with_mocks(
        initial_store=store,
        listing_filenames=[filename],
        file_contents={},
    )

    assert run["result"] == cache
    run["mock_mark_stale"].assert_called_once()
    run["mock_mark_ready"].assert_not_called()


def test_degraded_source_allows_upgrades_but_freezes_downgrades():
    fp_old = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    fp_new = "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
    key_old = "11" * 32
    key_new = "22" * 32
    published = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    cache = _base_cache(fp_old, key_old)
    filename = _recent_filename(hours_ago=3, minutes_offset=5)
    url = f"https://collector.torproject.org/recent/relay-descriptors/server-descriptors/{filename}"
    content = (
        _descriptor_text(fp_old, published, with_family_cert=False)
        + _descriptor_text(fp_new, published, with_family_cert=True, family_key_hex=key_new)
    ).encode("utf-8")

    run = _run_with_mocks(
        initial_store={
            "collector_descriptors": cache,
            "collector_descriptors_files": {},
        },
        listing_filenames=[filename],
        file_contents={url: content},
    )

    result = run["result"]
    assert result["source_freshness"] == "degraded"
    assert set(result["family_cert_fingerprints"]) == {fp_old, fp_new}
    groups = result["family_cert_groups"]
    assert groups[key_old] == [fp_old]
    assert groups[key_new] == [fp_new]
    run["mock_mark_ready"].assert_called_once()


def test_fresh_source_first_no_cert_observation_stays_pending():
    fp_old = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    key_old = "11" * 32
    published = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    cache = _base_cache(fp_old, key_old)
    filename = _recent_filename(hours_ago=1, minutes_offset=0)
    url = f"https://collector.torproject.org/recent/relay-descriptors/server-descriptors/{filename}"
    content = _descriptor_text(fp_old, published, with_family_cert=False).encode("utf-8")

    run = _run_with_mocks(
        initial_store={
            "collector_descriptors": cache,
            "collector_descriptors_files": {},
        },
        listing_filenames=[filename],
        file_contents={url: content},
    )

    result = run["result"]
    assert result["source_freshness"] == "fresh"
    assert fp_old in result["family_cert_fingerprints"]
    pending = result["hf_transition_state"]["pending_no_cert"]
    assert pending[fp_old]["count"] == 1


def test_fresh_source_second_no_cert_observation_confirms_downgrade():
    fp_old = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    key_old = "11" * 32
    published = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    cache = _base_cache(fp_old, key_old)
    filename = _recent_filename(hours_ago=1, minutes_offset=0)
    url = f"https://collector.torproject.org/recent/relay-descriptors/server-descriptors/{filename}"
    content = _descriptor_text(fp_old, published, with_family_cert=False).encode("utf-8")

    store = {
        "collector_descriptors": cache,
        "collector_descriptors_files": {},
    }

    first_run = _run_with_mocks(
        initial_store=store,
        listing_filenames=[filename],
        file_contents={url: content},
    )
    second_run = _run_with_mocks(
        initial_store=first_run["store"],
        listing_filenames=[filename],
        file_contents={url: content},
    )

    result = second_run["result"]
    assert result["source_freshness"] == "fresh"
    assert fp_old not in result["family_cert_fingerprints"]
    assert fp_old not in result["hf_transition_state"]["pending_no_cert"]
    assert result["family_cert_groups"] == {}


def test_fresh_source_large_published_delta_confirms_on_first_observation():
    fp_old = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    key_old = "11" * 32
    old_cert_published = (datetime.utcnow() - timedelta(hours=30)).strftime("%Y-%m-%d %H:%M:%S")
    no_cert_published = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    cache = _base_cache(fp_old, key_old)
    cache["hf_transition_state"] = {
        "pending_no_cert": {},
        "last_cert_published": {fp_old: old_cert_published},
    }

    filename = _recent_filename(hours_ago=1, minutes_offset=0)
    url = f"https://collector.torproject.org/recent/relay-descriptors/server-descriptors/{filename}"
    content = _descriptor_text(fp_old, no_cert_published, with_family_cert=False).encode("utf-8")

    run = _run_with_mocks(
        initial_store={
            "collector_descriptors": cache,
            "collector_descriptors_files": {},
        },
        listing_filenames=[filename],
        file_contents={url: content},
    )

    result = run["result"]
    assert result["source_freshness"] == "fresh"
    assert fp_old not in result["family_cert_fingerprints"]
    assert result["hf_transition_state"]["pending_no_cert"] == {}
