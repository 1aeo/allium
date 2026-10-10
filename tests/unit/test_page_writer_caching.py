"""Tests for the page-generation caches and worker result serialization."""

import functools
from types import SimpleNamespace

from allium.lib import page_writer
from allium.lib.time_utils import parse_onionoo_timestamp


def test_precomputed_results_relink_to_parent_relays(monkeypatch):
    # _init_precompute_worker sets module globals; let monkeypatch restore them
    monkeypatch.setattr(page_writer, "_precompute_relay_set", None)
    monkeypatch.setattr(page_writer, "_precompute_relay_indexes", None)
    relays = [{"fingerprint": "A" * 40, "nickname": "a"},
              {"fingerprint": "B" * 40, "nickname": "b"}]
    page_writer._init_precompute_worker(SimpleNamespace(json={"relays": relays}))
    result = {
        "contact_validation_status": {
            "validated_relays": [{"relay": relays[1], "error": None}],
            "unauthorized_relays": [{"relay": dict(relays[0])}],  # a copy, not shared
        },
        "count": 2,
    }

    payload = page_writer._dump_precomputed(result)
    parent_relays = [dict(relay) for relay in relays]
    loaded = page_writer._load_precomputed(payload, parent_relays)

    status = loaded["contact_validation_status"]
    assert status["validated_relays"][0]["relay"] is parent_relays[1]
    assert status["unauthorized_relays"][0]["relay"] == relays[0]
    assert status["unauthorized_relays"][0]["relay"] is not parent_relays[0]
    assert loaded["count"] == 2


def _row_head(monkeypatch):
    """Return relay_row_head memoized over an empty cache, and its macro's calls."""
    monkeypatch.setattr(page_writer, "_relay_row_heads", {})
    calls = []

    def macro(relay, show_validation_icon, validation_icon_type):
        calls.append(relay["fingerprint"])
        return f"<tr>{relay['fingerprint']}:{len(calls)}</tr>"
    return functools.partial(page_writer._cached_relay_row_head, macro), calls


def test_relay_row_cache_keys_on_validation_icon_membership(monkeypatch):
    head, calls = _row_head(monkeypatch)
    relay = {"fingerprint": "A" * 40}
    page = ("../../", "family", False)

    validated = head(relay, True, None, *page, {"A" * 40}, set(), set(), None, None)
    assert head(relay, True, None, *page, {"A" * 40}, set(), set(), None, None) is validated
    unauthorized = head(relay, True, None, *page, set(), {"A" * 40}, set(), None, None)
    security = head(relay, True, 'security_incident', *page, set(), set(), set(), {"A" * 40}, None)
    # Fixed icon types render without reading the sets
    head(relay, True, 'validated', *page, {"A" * 40}, set(), set(), None, None)
    head(relay, True, 'validated', *page, set(), {"A" * 40}, set(), None, None)

    assert len({validated, unauthorized, security}) == 3
    assert len(calls) == 4


def test_relay_row_cache_keys_on_page_values_and_relay_identity(monkeypatch):
    head, calls = _row_head(monkeypatch)
    relay = {"fingerprint": "A" * 40}
    same_fingerprint = {"fingerprint": "A" * 40}
    sets = (set(), set(), set(), None, None)

    head(relay, True, None, "../../", "family", False, *sets)
    head(relay, True, None, "../", "family", False, *sets)
    head(relay, True, None, "../../", "contact", False, *sets)
    head(relay, True, None, "../../", "family", True, *sets)
    head(same_fingerprint, True, None, "../../", "family", False, *sets)

    assert len(calls) == 5


def test_parse_onionoo_timestamp_handles_non_strings():
    parsed = parse_onionoo_timestamp("2024-01-05 10:20:30")
    assert parsed.isoformat() == "2024-01-05T10:20:30+00:00"
    assert parse_onionoo_timestamp("2024-01-05 10:20:30") is parsed
    assert parse_onionoo_timestamp("not a timestamp") is None
    assert parse_onionoo_timestamp(None) is None
    assert parse_onionoo_timestamp(["2024-01-05 10:20:30"]) is None


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
