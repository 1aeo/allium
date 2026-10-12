"""Pages link a country, platform or first_seen page only when it is written.

write_pages_by_key writes one page per key of relay_set.json["sorted"].
Onionoo reports an unknown country as "??" and can omit platform; sort_relay
files neither, so those show as text. The authorities page links an
authority's first_seen page by its YYYY-MM-DD key.
"""

import os
import re
from types import SimpleNamespace

import pytest

from allium.lib.progress_logger import ProgressLogger
from allium.lib.relays import Relays
from allium.lib.site_generator import SORTED_PAGE_KEYS, generate_site

PUBLISHED = "2026-10-11 12:00:00"
KNOWN = "A" * 40
NOWHERE = "B" * 40     # country "??", empty platform, alone in its AS
UNLISTED = "C" * 40    # no country or platform in Onionoo's details
MORIA1 = "D" * 40
DIZUM = "E" * 40       # an authority in "??"
RENAMED = "F" * 40     # platform "_Linux", which the page writer would rename
CATEGORY_HREF = re.compile(r'href="([^"]*\b(?:%s)/[^"]*)"' % "|".join(SORTED_PAGE_KEYS))


def _relay(fingerprint, nickname, **extra):
    """An Onionoo details relay in DE on Linux, with fields overridden by extra."""
    relay = {
        "nickname": nickname,
        "fingerprint": fingerprint,
        "running": True,
        "observed_bandwidth": 1_000_000,
        "consensus_weight": 100,
        "flags": ["Running", "Valid", "Fast"],
        "first_seen": "2024-01-01 00:00:00",
        "last_seen": PUBLISHED,
        "last_restarted": "2026-10-01 00:00:00",
        "platform": "Tor 0.4.8.10 on Linux",
        "country": "de",
        "country_name": "Germany",
        "as": "AS100",
        "as_name": "Example Networks",
        "or_addresses": ["192.0.2.1:9001"],
        "contact": f"{nickname} <{nickname}@example.org>",
    }
    relay.update(extra)
    return relay


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    """A whole site generated from the test relays, and their relay set."""
    out = tmp_path_factory.mktemp("site")
    unlisted = _relay(UNLISTED, "unlisted", **{"as": "AS100"})
    for field in ("country", "country_name", "platform"):
        del unlisted[field]
    details = {
        "version": "8.0",
        "relays_published": PUBLISHED,
        "relays": [
            _relay(KNOWN, "known"),
            _relay(NOWHERE, "nowhere", country="??", country_name=None, platform="",
                   **{"as": "AS200"}),
            unlisted,
            _relay(MORIA1, "moria1", flags=["Authority", "Running", "Valid"],
                   first_seen="2017-10-14 00:00:00", country="us", country_name="United States"),
            _relay(DIZUM, "dizum", flags=["Authority", "Running", "Valid"],
                   country="??", country_name=None, **{"as": "AS300"}),
            _relay(RENAMED, "renamed", platform="Tor 0.4.8.10 on _Linux"),
        ],
    }
    relay_set = Relays(
        output_dir=str(out),
        onionoo_url="https://onionoo.example.invalid/details",
        relay_data=details,
        filter_downtime_days=7,
        mp_workers=0,
    )
    relay_set.enrich_with_api_data()
    relay_set.authority_latency_status = {}  # no live probes of the authorities
    generate_site(relay_set, SimpleNamespace(output_dir=str(out), base_url="", progress=False),
                  ProgressLogger(progress_enabled=False))
    return SimpleNamespace(out=out, relay_set=relay_set)


def _read(site, *path):
    """The text of a generated page."""
    return site.out.joinpath(*path).read_text()


def test_has_page_is_true_only_for_written_category_pages(site):
    """has_page() holds for exactly the keys that get a category page."""
    relay_set = site.relay_set
    assert relay_set.has_page("country", "DE")
    assert relay_set.has_page("platform", "Linux")
    assert relay_set.has_page("first_seen", "2017-10-14")
    for category, key in (("country", "??"), ("country", None), ("platform", ""), ("platform", None),
                          ("platform", "_Linux"), ("first_seen", "20171014"), ("nonexistent", "DE")):
        assert not relay_set.has_page(category, key), (category, key)
    for category in ("country", "platform", "first_seen"):
        for key in relay_set.json["sorted"][category]:
            assert site.out.joinpath(category, key, "index.html").is_file()


def test_authority_age_links_its_first_seen_page(site):
    """The Age column links first_seen/<YYYY-MM-DD>/, the date's page."""
    html = _read(site, "misc", "authorities.html")

    assert 'href="../first_seen/2017-10-14/"' in html
    assert "first_seen/20171014" not in html
    assert site.out.joinpath("first_seen", "2017-10-14", "index.html").is_file()


def test_authority_in_unknown_country_shows_it_as_text(site):
    """An authority in "??" shows Unknown where its country link would be."""
    html = _read(site, "misc", "authorities.html")

    assert "country/??" not in html
    assert 'href="../country/US/"' in html
    assert re.search(r'bgp\.tools/AS300"[^>]*>[^<]*</a>\s*</td>\s*<td>\s*Unknown\s*</td>', html)


def test_relay_page_shows_unknown_country_and_platform_as_text(site):
    """A relay page links only a country or platform that has a page."""
    for fingerprint in (NOWHERE, UNLISTED):
        html = _read(site, "relay", fingerprint, "index.html")
        assert "country/" not in html, fingerprint
        assert "platform/" not in html, fingerprint
        assert "Country: unknown" in html
        assert "Platform: unknown" in html

    known = _read(site, "relay", KNOWN, "index.html")
    assert '<a href="../../country/DE/">Germany</a>' in known
    assert '<a href="../../platform/Linux/">Linux</a>' in known
    assert "Country: unknown" not in known
    assert "Platform: unknown" not in known


def test_a_key_the_writer_would_rename_has_no_page_or_link(site):
    """A platform written to a renamed folder ("_Linux" -> "Linux-<hash>") is shown as text."""
    assert os.listdir(site.out / "platform") == ["Linux"]

    html = _read(site, "relay", RENAMED, "index.html")
    assert "platform/_Linux" not in html
    assert "Platform: unknown" in html
    assert "Tor 0.4.8.10 on _Linux" in html  # the reported platform is still shown


def test_relay_rows_and_listings_show_unknown_as_text(site):
    """Relay rows, the networks listing and contact pages show "??" and no platform as text."""
    all_relays = _read(site, "misc", "all.html")
    assert "country/??" not in all_relays
    assert "platform//" not in all_relays
    assert 'href="../country/DE/"' in all_relays
    assert 'href="../platform/Linux/"' in all_relays

    networks = _read(site, "misc", "networks-by-overall-bandwidth.html")
    assert "country/??" not in networks
    # AS200's only relay has country "??": its country cell is text
    assert re.search(r'href="https://bgp\.tools/AS200">[^<]*</a>\s*</td>\s*<td>Unknown</td>', networks)

    contact_md5 = next(r["contact_md5"] for r in site.relay_set.json["relays"]
                       if r["fingerprint"] == NOWHERE)
    contact = _read(site, "contact", contact_md5, "index.html")
    assert "country/??" not in contact
    assert "platform//" not in contact
    assert re.search(r"<strong>Countries:</strong>\s*unknown \(1\)", contact)


def test_no_page_links_a_missing_category_page(site):
    """Every category link on every page has a page behind it."""
    checked = 0
    for dirpath, _, files in os.walk(site.out):
        for name in files:
            if not name.endswith(".html"):
                continue
            with open(os.path.join(dirpath, name), encoding="utf-8") as f:
                hrefs = CATEGORY_HREF.findall(f.read())
            for href in hrefs:
                if href.startswith(("http:", "https:")):
                    continue
                page = os.path.relpath(os.path.join(dirpath, name), site.out)
                path = href.split("#", 1)[0]
                # normpath would fold an empty key (platform//) into the category directory
                assert "//" not in path, (page, href)
                base = str(site.out) if path.startswith("/") else dirpath
                target = os.path.normpath(os.path.join(base, path.lstrip("/")))
                assert os.path.isfile(target) or os.path.isfile(os.path.join(target, "index.html")), (
                    page, href)
                checked += 1
    assert checked > 100
