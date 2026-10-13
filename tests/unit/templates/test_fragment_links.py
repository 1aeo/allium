"""Links to a #fragment land on an element of the page they open.

The Flags and Eligibility section (#flags) renders only for relays with a
consensus evaluation. Contact and family listings render an AROI section
(#<category>-relays) only on the pages that list one of its relays, so a
later page or another sort order can leave it out; relay pages show the
operator's AROI badge without any of those sections.
"""

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from allium.lib import page_writer
from allium.lib.consensus.collector_fetcher import AUTHORITIES_BY_NAME
from allium.lib.consensus.consensus_evaluation import format_relay_consensus_evaluation
from allium.lib.contact_sorting import AROI_SECTION_LISTS
from allium.lib.progress_logger import ProgressLogger
from allium.lib.relays import Relays
from allium.lib.site_generator import generate_site
from helpers.html_links import dead_fragment_links

PUBLISHED = "2026-10-11 12:00:00"
BIG_AROI = "ciissversion:2 proof:uri-rsa url:big.example"
MISCONFIGURED_AROI = "ciissversion:2 proof:uri-rsa url:misconf.example"  # no validator result
VALIDATED = ["1" * 40, "2" * 40]     # big.example's two fastest relays: its listings' first page
UNAUTHORIZED = ["3" * 40, "4" * 40]  # its next two, first by nickname
LEAKED = "A" * 40                    # its slowest: a leaked family key, alone on page 3
MISCONFIGURED = ["5" * 40, "8" * 40]
NO_AROI = "9" * 40                   # in MISCONFIGURED's family, alone on its second page
NO_EVALUATION, EVALUATED = "6" * 40, "7" * 40
FAMILY = [*MISCONFIGURED, NO_AROI]
AROI_RESULTS = {"metadata": {}, "statistics": {}, "results": [
    *({"fingerprint": fp, "valid": True, "domain": "big.example", "proof_type": "uri-rsa"}
      for fp in VALIDATED),
    *({"fingerprint": fp, "valid": False, "domain": "big.example", "proof_type": "uri-rsa",
       "error": "Fingerprint not found", "error_category": "uri_content_mismatch"}
      for fp in UNAUTHORIZED),
    {"fingerprint": LEAKED, "valid": False, "domain": "big.example", "proof_type": "uri-rsa",
     "error": "secret_family_key published", "error_category": "secret_key_leaked"},
]}


def _relay(fingerprint, nickname, observed_bandwidth=1_000_000, contact=None, **extra):
    """An Onionoo details relay, with fields overridden by extra."""
    relay = {
        "nickname": nickname,
        "fingerprint": fingerprint,
        "running": True,
        "observed_bandwidth": observed_bandwidth,
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
        "contact": contact or f"{nickname} <{nickname}@example.org>",
    }
    relay.update(extra)
    return relay


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    """A site whose relay listings show 2 relays per page, and its relays by fingerprint."""
    out = tmp_path_factory.mktemp("site")
    details = {"version": "8.0", "relays_published": PUBLISHED, "relays": [
        _relay(VALIDATED[0], "zvalid1", 9_000_000, BIG_AROI),
        _relay(VALIDATED[1], "zvalid2", 8_000_000, BIG_AROI),
        _relay(UNAUTHORIZED[0], "aunauth1", 2_000_000, BIG_AROI),
        _relay(UNAUTHORIZED[1], "aunauth2", 1_000_000, BIG_AROI),
        _relay(LEAKED, "mleaked", 500_000, BIG_AROI),
        _relay(MISCONFIGURED[0], "misconf1", 5_000_000, MISCONFIGURED_AROI, effective_family=FAMILY),
        _relay(MISCONFIGURED[1], "misconf2", 4_000_000, MISCONFIGURED_AROI, effective_family=FAMILY),
        _relay(NO_AROI, "noaroi", 100_000, effective_family=FAMILY),
        _relay(NO_EVALUATION, "unevaluated"),
        _relay(EVALUATED, "evaluated"),
    ]}
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(page_writer, "RELAY_PAGE_SIZE", 2)
        relay_set = Relays(output_dir=str(out), onionoo_url="https://onionoo.example.invalid/details",
                           relay_data=details, filter_downtime_days=7, mp_workers=0)
        relay_set.enrich_with_api_data(aroi_validation_data=AROI_RESULTS)
        relay_set.authority_latency_status = {}  # no live probes of the authorities
        relays = {relay["fingerprint"]: relay for relay in relay_set.json["relays"]}
        relays[EVALUATED]["consensus_evaluation"] = format_relay_consensus_evaluation({
            "fingerprint": EVALUATED, "in_consensus": True, "vote_count": 1,
            "authority_votes": [
                {"authority": name, "fingerprint": AUTHORITIES_BY_NAME[name], "voted": name == "moria1",
                 "flags": ["Running", "Valid"] if name == "moria1" else []}
                for name in ("bastet", "moria1")
            ],
        })
        generate_site(relay_set, SimpleNamespace(output_dir=str(out), base_url="", progress=False),
                      ProgressLogger(progress_enabled=False))
    return SimpleNamespace(out=out, relays=relays)


def _read(site, *path):
    """The text of a generated page."""
    return site.out.joinpath(*path).read_text()


def _contact(site, fingerprint, filename="index.html"):
    """A page of the contact listing of the relay's operator."""
    return _read(site, "contact", site.relays[fingerprint]["contact_md5"], filename)


def test_every_fragment_link_lands_on_its_target(site):
    """No generated page links a #fragment that the page it opens lacks."""
    assert dead_fragment_links(site.out) == []


def test_health_status_links_flags_only_when_the_section_renders(site):
    """Consensus and Flags link #flags only on pages with the Flags and Eligibility section."""
    unevaluated = _read(site, "relay", NO_EVALUATION, "index.html")
    assert 'id="flags"' not in unevaluated
    assert 'href="#flags"' not in unevaluated
    assert ">Consensus</dt>" in unevaluated and ">Flags</dt>" in unevaluated

    evaluated = _read(site, "relay", EVALUATED, "index.html")
    assert 'id="flags"' in evaluated
    assert '<a href="#flags" class="anchor-link">Consensus</a>' in evaluated
    assert '<a href="#flags" class="anchor-link">Flags</a>' in evaluated


def test_relay_badge_links_its_operator_contact_section(site):
    """A relay's operator badge opens the section on the operator's contact page."""
    md5 = site.relays[MISCONFIGURED[0]]["contact_md5"]
    html = _read(site, "relay", MISCONFIGURED[0], "index.html")
    assert f'href="../../contact/{md5}/#misconfigured-relays"' in html
    assert 'href="#misconfigured-relays"' not in html
    assert 'id="misconfigured-relays"' in _contact(site, MISCONFIGURED[0])

    # The leaked key's section is on the third page of big.example's listing
    md5 = site.relays[VALIDATED[0]]["contact_md5"]
    html = _read(site, "relay", VALIDATED[0], "index.html")
    assert f'href="../../contact/{md5}/page-3#security_incident-relays"' in html
    assert 'id="security_incident-relays"' in _contact(site, VALIDATED[0], "page-3.html")


def test_contact_links_a_section_on_the_page_that_shows_it(site):
    """Contact listings link the first page of their own sort order that shows the section."""
    index = _contact(site, VALIDATED[0])
    # By bandwidth the unauthorized relays are on page 2, the leaked key on page 3
    assert 'id="unauthorized-relays"' not in index
    assert 'href="page-2#unauthorized-relays"' in index
    assert 'id="security_incident-relays"' not in index
    assert index.count('href="page-3#security_incident-relays"') == 2  # badge and sub-bullet
    assert 'href="#unauthorized-relays"' in _contact(site, VALIDATED[0], "page-2.html")
    # By nickname the unauthorized relays are on page 1 only
    assert 'href="#unauthorized-relays"' in _contact(site, VALIDATED[0], "by-nickname.html")
    assert 'href="by-nickname#unauthorized-relays"' in _contact(site, VALIDATED[0], "by-nickname-page-2.html")


def test_family_page_links_a_section_on_its_first_page(site):
    """A family's second page links the misconfigured relays its first page lists."""
    html = _read(site, "family", MISCONFIGURED[0], "page-2.html")
    assert 'id="misconfigured-relays"' not in html
    assert 'href="./#misconfigured-relays"' in html


def test_aroi_section_hrefs_finds_the_first_page_showing_each_section(monkeypatch):
    """Sections map to this page, another page of the listing, or nothing."""
    monkeypatch.setattr(page_writer, "RELAY_PAGE_SIZE", 2)
    relays = [{"fingerprint": fp} for fp in "ABCDE"]

    def entries(*fps):
        """Validation status list entries for these fingerprints."""
        return [{"relay": {"fingerprint": fp}} for fp in fps]

    status = {"has_aroi": True, "validation_status": "validated",
              "validated_relays": entries("A"), "unauthorized_relays": entries("E", "C"),
              "incomplete_relays": entries("D"), "misconfigured_relays": entries("Z")}  # Z is listed nowhere

    assert page_writer._aroi_section_hrefs(status, relays, "by-status.html", 2) == {
        "validated": "by-status#validated-relays",
        "unauthorized": "#unauthorized-relays",
        "not_configured": "#not_configured-relays",
    }
    assert page_writer._aroi_section_hrefs(status, relays, "index.html", page_dir="../../contact/h/") == {
        "validated": "../../contact/h/#validated-relays",
        "unauthorized": "../../contact/h/page-2#unauthorized-relays",
        "not_configured": "../../contact/h/page-2#not_configured-relays",
    }
    assert page_writer._aroi_section_hrefs(status, relays, "index.html", 3)["validated"] == "./#validated-relays"
    for unsectioned in (None, {**status, "has_aroi": False}, {**status, "validation_status": "not_configured"}):
        assert page_writer._aroi_section_hrefs(unsectioned, relays, "index.html", 1) == {}


def test_aroi_section_lists_match_the_listing_sections():
    """AROI_SECTION_LISTS names every section contact-relay-list.html links from the badge."""
    template = Path(page_writer.ABS_PATH, "..", "templates", "contact-relay-list.html").read_text()
    sections = set(re.findall(r"aroi_section_header\([^)]*'(\w+)'\)", template)) - {"v3_migration"}
    assert sections == set(AROI_SECTION_LISTS)
