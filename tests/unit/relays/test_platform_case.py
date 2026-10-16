"""Platform names that differ only by case share one page key."""

import json
import os

from allium.lib import page_writer
from allium.lib.page_writer import write_pages_by_key
from allium.lib.relays import Relays
from allium.lib.search_index import generate_search_index


PUBLISHED = "2026-10-11 12:00:00"
GOTOR = "Tor 0.4.9.11 (gotor) on linux"


def _relay(i, platform):
    """Build an Onionoo relay record with the given identity and platform."""
    return {"fingerprint": f"{i:040X}", "nickname": f"relay{i}", "running": True,
            "observed_bandwidth": 1_000_000, "consensus_weight": 100, "flags": ["Running", "Valid", "Fast"],
            "first_seen": "2024-01-01 00:00:00", "last_seen": PUBLISHED, "last_restarted": "2026-10-01 00:00:00",
            "country": "de", "country_name": "Germany", "as": "AS100", "as_name": "Example",
            "or_addresses": [f"192.0.2.{i}:9001"], "platform": platform,
            "contact": f"relay{i} <relay{i}@example.org>"}


def _relay_set(tmp_path, platforms):
    """Build a processed relay set from the supplied platform strings."""
    return Relays(output_dir=str(tmp_path), onionoo_url="https://onionoo.example.invalid/details",
                  relay_data={"version": "8.0", "relays_published": PUBLISHED,
                              "relays": [_relay(i, p) for i, p in enumerate(platforms, 1)]}, mp_workers=0)


def test_gotor_lowercase_platform_files_under_the_tor_spelling(tmp_path):
    """Group gotor's lowercase Linux with C Tor while preserving raw platforms."""
    platforms = ["Tor 0.4.8.10 on Linux"] * 2 + [GOTOR]
    relay_set = _relay_set(tmp_path, platforms)
    relays = relay_set.json["relays"]
    assert all(relay["platform"] == "Linux" for relay in relays)
    assert sorted(relay["platform_raw"] for relay in relays) == sorted(platforms)
    assert list(relay_set.json["sorted"]["platform"]) == ["Linux"]
    assert len(relay_set.json["sorted"]["platform"]["Linux"]["relays"]) == 3


def test_known_platforms_keep_the_tor_spelling_when_lowercase_outnumbers_it(tmp_path):
    """Use canonical spellings for known platforms regardless of relay counts."""
    platforms = (["Tor 0.4.8.10 on FreeBSD"]
                 + ["Tor 0.4.9.11 (gotor) on freebsd"] * 2
                 + ["Tor 0.4.9.11 (gotor) on darwin", "Tor 0.4.9.11 (gotor) on windows"])
    relay_set = _relay_set(tmp_path, platforms)
    assert sorted(relay_set.json["sorted"]["platform"]) == ["Darwin", "FreeBSD", "Windows"]


def test_unknown_platforms_differing_by_case_prefer_the_capitalised_then_most_reported_spelling(tmp_path):
    """Prefer mixed or uppercase unknown names, then the most reported spelling."""
    platforms = (["Tor 0.4.8.10 on haiku"] * 2
                 + ["Tor 0.4.8.10 on Haiku"]
                 + ["Tor 0.4.8.10 on Plan9"]
                 + ["Tor 0.4.8.10 on PLAN9"] * 2)
    relay_set = _relay_set(tmp_path, platforms)
    assert sorted(relay_set.json["sorted"]["platform"]) == ["Haiku", "PLAN9"]


def test_unknown_platform_keeps_its_reported_spelling(tmp_path):
    """Preserve an unknown platform's spelling when no case variants exist."""
    relay_set = _relay_set(tmp_path, ["Tor 0.4.8.10 on plan9"])
    assert relay_set.json["relays"][0]["platform"] == "plan9"


def test_platform_spellings_table_is_case_only():
    """Ensure canonical platform mappings change only letter case."""
    from allium.lib.relays import PLATFORM_SPELLINGS
    assert PLATFORM_SPELLINGS["linux"] == "Linux"
    assert all(value.lower() == key for key, value in PLATFORM_SPELLINGS.items())


def test_known_names_keep_their_tor_spelling(tmp_path):
    """Keep canonical platform names after trimming prefixes and versions."""
    relay_set = _relay_set(tmp_path, [
        "Tor 0.4.8.10 on GNU/Linux-libre",
        "Tor 0.4.8.10 on Windows 10 [or later]",
    ])
    assert relay_set.json["relays"][0]["platform"] == "Linux-libre"
    assert relay_set.json["relays"][1]["platform"] == "Windows"


def test_platform_case_variants_get_one_page_and_one_link(tmp_path):
    """Render one platform directory and canonical relay links for case variants."""
    relay_set = _relay_set(tmp_path, ["Tor 0.4.8.10 on Linux", GOTOR])
    write_pages_by_key(relay_set, "platform")
    page_writer.write_relay_info(relay_set)
    assert os.listdir(tmp_path / "platform") == ["Linux"]
    gotor = next(relay for relay in relay_set.json["relays"] if relay["platform_raw"] == GOTOR)
    html = (tmp_path / "relay" / gotor["fingerprint"] / "index.html").read_text(encoding="utf-8")
    assert '<a href="../../platform/Linux/">Linux</a>' in html
    assert "platform/linux/" not in html
    assert GOTOR in html


def test_search_lists_one_platform_for_case_variants(tmp_path):
    """List case variants under one canonical platform in the search index."""
    relay_set = _relay_set(tmp_path, ["Tor 0.4.8.10 on Linux", GOTOR])
    index_path = tmp_path / "search-index.json"
    generate_search_index(relay_set.json, str(index_path), use_parallel=False)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["lookups"]["platforms"] == ["Linux"]
