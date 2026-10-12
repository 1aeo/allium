"""Upstream resolver rows on exit relay pages and the network health dashboard.

Renders real pages from a small relay set enriched with an exitdnshealth report
that carries resolver data (results[].resolver, metadata.resolvers), one from an
upstream cold start (no exit covered yet), and one without any (older reports,
failed resolver runs).
"""

import copy
import re

import pytest
from jinja2 import ChoiceLoader, DictLoader

from allium.lib import page_writer
from allium.lib.relays import Relays
from allium.lib.site_generator import STANDALONE_PAGES, _build_page_context

PUBLISHED = "2026-10-11 12:00:00"
PUBLIC = "A" * 40     # labelled, public resolver
LOCAL = "B" * 40      # labelled, local resolver
COLD = "C" * 40       # some queries, not labelled yet
UNSEEN = "D" * 40     # tested, no resolver data yet
HOSTILE = "E" * 40    # unexpected values from upstream
GUARD = "F" * 40      # not an exit
EXITS = (PUBLIC, LOCAL, COLD, UNSEEN, HOSTILE)
EXIT_FLAGS = ["Exit", "Fast", "Running", "Valid"]

RESOLVERS = {
    "version": 1, "weighted": True, "exits_total": 2674, "exits_covered": 2670, "exits_labelled": 2608,
    "exits_using_public": 512,
    "public_share_pct": {"google": 10.5, "cloudflare": 7.99, "quad9": 2.0, "opendns": 0.0, "ffmuc": 1.12, "all": 21.61},
    "share_pct": {"google": 10.5, "cloudflare": 7.99, "quad9": 2.0, "opendns": 0.0, "ffmuc": 1.12,
                  "local": 66.69, "other": 11.7, "unknown": 0.0},
}
# What upstream publishes before any exit has enough queries: every share is a 0.0 placeholder
COLD_START = dict(RESOLVERS, weighted=False, exits_covered=0, exits_labelled=0, exits_using_public=0,
                  public_share_pct=dict.fromkeys(RESOLVERS["public_share_pct"], 0.0),
                  share_pct=dict.fromkeys(RESOLVERS["share_pct"], 0.0))


def _relay(fingerprint, nickname, flags):
    return {
        "nickname": nickname, "fingerprint": fingerprint, "running": True, "flags": flags,
        "observed_bandwidth": 1_000_000, "consensus_weight": 100, "exit_probability": 0.1,
        "first_seen": "2024-01-01 00:00:00", "last_seen": PUBLISHED, "last_restarted": "2026-10-01 00:00:00",
        "platform": "Tor 0.4.8.10 on Linux", "country": "de", "country_name": "Germany",
        "as": "AS100", "as_name": "Example Networks", "or_addresses": ["192.0.2.1:9001"],
        "contact": f"{nickname} <{nickname}@example.org>",
    }


def _report(resolvers):
    """An exitdnshealth report; resolvers=None is a report without any resolver data."""
    per_exit = {
        PUBLIC: {"primary": "google", "public": True, "queries": {"google": 61.3, "local": 4.2}},
        LOCAL: {"primary": "local", "public": False, "queries": {"local": 199.0, "other": 1.0}},
        COLD: {"primary": None, "public": None, "queries": {"other": 3.5}},
        HOSTILE: {"primary": "<script>alert(1)</script>", "public": "<b>yes</b>",
                  "queries": {"<img src=x onerror=alert(1)>": 30, "google": "<i>9</i>"}},
    }
    results = []
    for fp in EXITS:
        result = {"exit_fingerprint": fp, "status": "success", "timing": {"total_ms": 900}}
        if resolvers is not None and fp in per_exit:
            result["resolver"] = per_exit[fp]
        results.append(result)
    metadata = {"timestamp": "2026-10-12T07:27:12Z", "dns_success_rate_percent": 100.0,
                "tested_relays": 5, "consensus_relays": 5, "dns_success": 5}
    if resolvers is not None:
        metadata["resolvers"] = copy.deepcopy(resolvers)
    return {"metadata": metadata, "results": results}


def _relay_set(tmp_path, resolvers):
    details = {
        "version": "8.0",
        "relays_published": PUBLISHED,
        "relays": [_relay(fp, f"exit{fp[0].lower()}", EXIT_FLAGS) for fp in EXITS]
        + [_relay(GUARD, "guard", ["Guard", "Fast", "Running", "Valid"])],
    }
    relay_set = Relays(output_dir=str(tmp_path), onionoo_url="https://onionoo.example.invalid/details",
                       relay_data=details, filter_downtime_days=7, mp_workers=0)
    relay_set.enrich_with_api_data(exit_dns_health_data=_report(resolvers))
    return relay_set


def _relay_pages(relay_set):
    page_writer.write_relay_info(relay_set)
    return {fp: open(f"{relay_set.output_dir}/relay/{fp}/index.html").read() for fp in EXITS + (GUARD,)}


def _render(tmp_path, resolvers):
    relay_set = _relay_set(tmp_path, resolvers)
    pages = _relay_pages(relay_set)
    page_def = next(p for p in STANDALONE_PAGES if p["template"] == "network-health-dashboard.html")
    dashboard = tmp_path / "network-health.html"
    page_writer.write_misc(relay_set, page_def["template"], str(dashboard),
                           page_ctx=_build_page_context(page_def, relay_set))
    return pages, dashboard.read_text()


def _resolver_row(html):
    """Text of the Upstream Resolver <dd>, whitespace collapsed; None when the row is absent."""
    match = re.search(r">Upstream Resolver</dt>\s*<dd>(.*?)</dd>", html, re.DOTALL)
    if not match:
        return None
    return " ".join(re.sub(r"<[^>]+>", " ", match.group(1)).split())


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    return _render(tmp_path_factory.mktemp("with_resolvers"), RESOLVERS)


@pytest.fixture(scope="module")
def rendered_without(tmp_path_factory):
    return _render(tmp_path_factory.mktemp("without_resolvers"), None)


def test_public_resolver_row(rendered):
    pages, _ = rendered
    assert _resolver_row(pages[PUBLIC]) == \
        "Google (public resolver) Google 94%, Local 6% (~66 estimated queries)"


def test_local_resolver_row(rendered):
    pages, _ = rendered
    assert _resolver_row(pages[LOCAL]) == \
        "Local (exit's own network) Local &gt;99%, Other &lt;1% (~200 estimated queries)"


def test_not_yet_labelled_row(rendered):
    pages, _ = rendered
    assert _resolver_row(pages[COLD]) == "Not enough data Other 100% (~4 estimated queries)"
    assert _resolver_row(pages[UNSEEN]) == "Not enough data"


def test_hostile_values_are_bounded_and_escaped(rendered):
    pages, _ = rendered
    html = pages[HOSTILE]
    assert _resolver_row(html) == "Other Other 100% (~30 estimated queries)"
    for raw in ("<script>alert(1)</script>", "<img src=x", "<b>yes</b>", "<i>9</i>"):
        assert raw not in html


def test_non_exit_has_no_resolver_row(rendered):
    pages, _ = rendered
    assert _resolver_row(pages[GUARD]) is None


def test_no_resolver_row_without_resolver_data(rendered_without):
    pages, _ = rendered_without
    for fp in EXITS + (GUARD,):
        assert "Upstream Resolver" not in pages[fp], fp


def test_pages_without_resolver_data_are_byte_identical(tmp_path, monkeypatch):
    """Older reports and failed resolver runs render relay pages exactly as before the row existed."""
    relay_set = _relay_set(tmp_path, None)
    pages = _relay_pages(relay_set)

    # The template as it was: the DNS Result block, one blank line, the Cross-Validation block
    source = page_writer.ENV.loader.get_source(page_writer.ENV, "relay-info.html")[0]
    endif = "            {% endif %}\n"
    end = source.index("            {% if relay.exit_dns_health_cv_total is not none %}")
    start = source.rindex(endif, 0, source.index("{# Upstream resolver.")) + len(endif)
    assert "Upstream Resolver" in source[start:end] and "Upstream Resolver" not in source[:start] + source[end:]
    without_row = page_writer.ENV.overlay(loader=ChoiceLoader([
        DictLoader({"relay-info.html": source[:start] + "\n" + source[end:]}), page_writer.ENV.loader]))
    monkeypatch.setattr(page_writer, "ENV", without_row)

    assert _relay_pages(relay_set) == pages


def _dashboard_tiles(html):
    """{label: value} for the resolver tiles of the Exit DNS Health card."""
    card = html[html.index('id="exit-dns-health"'):]
    card = card[:card.index("exitdnshealth.1aeo.com</a>")]
    return dict((label.strip(), value.strip()) for value, label in re.findall(
        r'<span class="metric-value">([^<]*)</span>\s*<span class="metric-label">([^<]*)</span>', card))


def test_dashboard_resolver_row(rendered):
    _, html = rendered
    tiles = _dashboard_tiles(html)
    assert {k: tiles[k] for k in ("Google", "Cloudflare", "Quad9", "OpenDNS", "Freifunk München",
                                  "All Public", "Local", "Other", "Unknown", "Exits Covered")} == {
        "Google": "10.5%", "Cloudflare": "8.0%", "Quad9": "2.0%", "OpenDNS": "0.0%", "Freifunk München": "1.1%",
        "All Public": "21.6%", "Local": "66.7%", "Other": "11.7%", "Unknown": "0.0%", "Exits Covered": "2,670 / 2,674",
    }
    assert "Upstream resolvers: estimated share of exit DNS lookups, weighted by exit probability." in html
    assert "2,608 have enough to name a primary resolver; 512 of those use a public one." in html
    assert "Upstream resolvers: not available." not in html


def test_dashboard_cold_start_shows_no_zero_shares(tmp_path):
    _, html = _render(tmp_path, COLD_START)
    tiles = _dashboard_tiles(html)
    for label in ("Google", "Cloudflare", "Quad9", "OpenDNS", "Freifunk München", "All Public", "Local", "Other",
                  "Unknown"):
        assert tiles[label] == "n/a", label
    assert tiles["Exits Covered"] == "0 / 2,674"
    assert "Upstream resolvers: estimated share of exit DNS lookups, unweighted." in html


def test_dashboard_without_resolver_data(rendered_without):
    _, html = rendered_without
    tiles = _dashboard_tiles(html)
    assert "Upstream resolvers: not available." in html
    assert not {"Google", "All Public", "Exits Covered"} & set(tiles)
    assert tiles["Tested / Consensus Exits"] == "5 / 5"  # the rest of the card is unchanged
