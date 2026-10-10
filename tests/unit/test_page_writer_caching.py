"""Tests for the page-generation caches and worker result serialization."""

import json
import os
import tempfile

from allium.lib import page_writer
from allium.lib.file_io_utils import create_cache_manager
from allium.lib.time_utils import parse_onionoo_timestamp


class _RelaySet:
    def __init__(self, relays):
        self.json = {"relays": relays}


def test_precomputed_results_relink_to_parent_relays(monkeypatch):
    # _init_precompute_worker sets module globals; let monkeypatch restore them
    monkeypatch.setattr(page_writer, "_precompute_relay_set", None)
    monkeypatch.setattr(page_writer, "_precompute_relay_indexes", None)
    relays = [{"fingerprint": "A" * 40, "nickname": "a"},
              {"fingerprint": "B" * 40, "nickname": "b"}]
    page_writer._init_precompute_worker(_RelaySet(relays))
    result = {
        "contact_validation_status": {
            "validated_relays": [{"relay": relays[1], "error": None}],
            "unauthorized_relays": [{"relay": dict(relays[0])}],  # a copy, not shared
        },
        "count": 2,
    }

    payload = page_writer._dump_precomputed(result)
    parent_relays = [dict(relay) for relay in relays]
    loaded = page_writer.load_precomputed(payload, parent_relays)

    status = loaded["contact_validation_status"]
    assert status["validated_relays"][0]["relay"] is parent_relays[1]
    assert status["unauthorized_relays"][0]["relay"] == relays[0]
    assert status["unauthorized_relays"][0]["relay"] is not parent_relays[0]
    assert loaded["count"] == 2


def _row_macro():
    calls = []

    def macro(relay, show_validation_icon, validation_icon_type):
        calls.append((relay["fingerprint"], show_validation_icon, validation_icon_type))
        return f"<tr>{relay['fingerprint']}:{len(calls)}</tr>"
    return macro, calls


def test_relay_row_cache_reuses_rows_with_identical_inputs():
    cache = page_writer._RelayRowCache()
    macro, calls = _row_macro()
    relay = {"fingerprint": "A" * 40}
    args = ("../../", "family", False, {"A" * 40}, set(), set(), None, None)

    first = cache.head(macro, relay, True, None, *args)
    second = cache.head(macro, relay, True, None, *args)

    assert first == second
    assert len(calls) == 1


def test_relay_row_cache_keys_on_validation_icon_membership():
    cache = page_writer._RelayRowCache()
    macro, calls = _row_macro()
    relay = {"fingerprint": "A" * 40}

    validated = cache.head(macro, relay, True, None, "../../", "family", False,
                           {"A" * 40}, set(), set(), None, None)
    unauthorized = cache.head(macro, relay, True, None, "../../", "family", False,
                              set(), {"A" * 40}, set(), None, None)
    security = cache.head(macro, relay, True, 'security_incident', "../../", "family",
                          False, set(), set(), set(), {"A" * 40}, None)

    assert len({validated, unauthorized, security}) == 3
    assert len(calls) == 3


def test_relay_row_cache_ignores_sets_for_fixed_icon_types():
    cache = page_writer._RelayRowCache()
    macro, calls = _row_macro()
    relay = {"fingerprint": "A" * 40}

    cache.head(macro, relay, True, 'validated', "../../", "family", False,
               {"A" * 40}, set(), set(), None, None)
    cache.head(macro, relay, True, 'validated', "../../", "family", False,
               set(), {"A" * 40}, set(), None, None)

    assert len(calls) == 1


def test_relay_row_cache_keys_on_page_values_and_relay_identity():
    cache = page_writer._RelayRowCache()
    macro, calls = _row_macro()
    relay = {"fingerprint": "A" * 40}
    same_fingerprint = {"fingerprint": "A" * 40}
    sets = (set(), set(), set(), None, None)

    cache.head(macro, relay, True, None, "../../", "family", False, *sets)
    cache.head(macro, relay, True, None, "../", "family", False, *sets)
    cache.head(macro, relay, True, None, "../../", "contact", False, *sets)
    cache.head(macro, relay, True, None, "../../", "family", True, *sets)
    cache.head(macro, same_fingerprint, True, None, "../../", "family", False, *sets)

    assert len(calls) == 5


def test_parse_onionoo_timestamp_handles_non_strings():
    parsed = parse_onionoo_timestamp("2024-01-05 10:20:30")
    assert parsed.isoformat() == "2024-01-05T10:20:30+00:00"
    assert parse_onionoo_timestamp("2024-01-05 10:20:30") is parsed
    assert parse_onionoo_timestamp("not a timestamp") is None
    assert parse_onionoo_timestamp(None) is None
    assert parse_onionoo_timestamp(["2024-01-05 10:20:30"]) is None


def test_cache_files_are_compact_sorted_json():
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = create_cache_manager(temp_dir)
        data = {"z": [1, {"b": 2, "a": None}], "a": "x"}
        assert manager.save_cache("compact", data)
        with open(os.path.join(temp_dir, "compact.json"), encoding="utf-8") as f:
            text = f.read()
        assert text == '{"a":"x","z":[1,{"a":null,"b":2}]}'
        assert manager.load_cache("compact") == data
        assert json.loads(text) == data


def test_write_html_rewrites_links_and_normalizes_newlines(tmp_path):
    path = tmp_path / "page.html"
    page_writer._write_html(str(path), '<a href="../x/index.html">x</a>\r\nline\rend')
    assert path.read_bytes() == b'<a href="../x/">x</a>\nline\nend'


def test_write_html_keeps_pages_without_rewritable_links_unchanged(tmp_path):
    path = tmp_path / "page.html"
    page_writer._write_html(str(path), '<a href="https://a.test/x.html">x</a>\r\n')
    assert path.read_bytes() == b'<a href="https://a.test/x.html">x</a>\r\n'


def test_relay_row_head_reads_only_what_the_row_cache_keys_on():
    """relay_row_head output is reused across pages and sort variants, so it
    may only depend on its arguments and the page values in the cache key."""
    from jinja2 import nodes

    source = page_writer.ENV.loader.get_source(page_writer.ENV, "contact-relay-list.html")[0]
    template = page_writer.ENV.parse(source)
    macro = next(node for node in template.find_all(nodes.Macro)
                 if node.name == "relay_row_head")

    assigned = {arg.name for arg in macro.args}
    assigned |= {name.name for name in macro.find_all(nodes.Name) if name.ctx in ("store", "param")}
    loaded = {name.name for name in macro.find_all(nodes.Name) if name.ctx == "load"}
    keyed = {"relays", "page_ctx", "key", "validated_fps", "unauthorized_fps",
             "misconfigured_fps", "security_fps", "pending_fps", "aroi_validation_icon"}
    assert loaded - assigned <= keyed

    filters = {node.name for node in macro.find_all(nodes.Filter)}
    assert not filters & {"format_time_ago", "format_timestamp_ago"}
