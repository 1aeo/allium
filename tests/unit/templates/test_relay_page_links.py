"""Relay pages link only relays that have a page.

Onionoo's family lists name fingerprints it doesn't list as relays, and
relays the downtime filter dropped; vote files name authorities by V3
signing key. None of those have a relay/<FP>/ page, so they render as text.
"""

import os
import re

from allium.lib import page_writer
from allium.lib.consensus.collector_fetcher import AUTHORITIES_BY_NAME
from allium.lib.consensus.consensus_evaluation import format_relay_consensus_evaluation
from allium.lib.relays import Relays

PUBLISHED = "2026-10-11 12:00:00"
OWNER = "A" * 40
KEPT = "B" * 40
DROPPED = "C" * 40     # in Onionoo's details, not seen for 30 days
UNKNOWN = "D" * 40     # not in Onionoo's details at all
INDIRECT_UNKNOWN = "E" * 40
MORIA1 = "1A25C6358DB91342AA51720A5038B72742732498"  # relay fingerprint, not V3 key
OLD_MORIA1 = "9695DFC35FFEB861329B9F1AB04C46397020CE31"  # its identity before a key change
NOT_IN_NETWORK = "(not in the network)"


def _relay(fingerprint, nickname, last_seen=PUBLISHED, running=True, flags=None, **extra):
    relay = {
        "nickname": nickname,
        "fingerprint": fingerprint,
        "running": running,
        "observed_bandwidth": 1_000_000,
        "consensus_weight": 100,
        "flags": flags or ["Running", "Valid", "Fast"],
        "first_seen": "2024-01-01 00:00:00",
        "last_seen": last_seen,
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


def _render_relay_pages(tmp_path):
    details = {
        "version": "8.0",
        "relays_published": PUBLISHED,
        "relays": [
            _relay(OWNER, "owner",
                   effective_family=[OWNER, KEPT, DROPPED],
                   alleged_family=[KEPT, DROPPED, UNKNOWN, "nicknameonly"],
                   indirect_family=[INDIRECT_UNKNOWN]),
            _relay(KEPT, "kept", effective_family=[OWNER, KEPT], indirect_family=[OWNER]),
            _relay(DROPPED, "dropped", last_seen="2026-09-11 12:00:00", running=False),
            _relay(MORIA1, "moria1", flags=["Authority", "Running", "Valid"]),
            # Onionoo keeps the old identity, with its last flags, for a week
            _relay(OLD_MORIA1, "moria1", last_seen="2026-10-09 12:00:00", running=False,
                   flags=["Authority", "Running", "Valid"], observed_bandwidth=500_000),
        ],
    }
    relay_set = Relays(
        output_dir=str(tmp_path),
        onionoo_url="https://onionoo.example.invalid/details",
        relay_data=details,
        filter_downtime_days=7,
        mp_workers=0,
    )
    relay_set.enrich_with_api_data()
    assert {r["fingerprint"] for r in relay_set.json["relays"]} == {OWNER, KEPT, MORIA1, OLD_MORIA1}

    relays = {r["fingerprint"]: r for r in relay_set.json["relays"]}
    # Authority votes as CollecTor reports them: keyed by V3 signing key
    relays[OWNER]["consensus_evaluation"] = format_relay_consensus_evaluation({
        "fingerprint": OWNER,
        "in_consensus": True,
        "vote_count": 1,
        "authority_votes": [
            {"authority": name, "fingerprint": AUTHORITIES_BY_NAME[name],
             "voted": name == "moria1", "flags": ["Running", "Valid"] if name == "moria1" else []}
            for name in ("bastet", "moria1")
        ],
    })

    # Exit DNS health first hops come from an external API
    relays[OWNER].update(exit_dns_health_status="success", exit_dns_health_first_hop=DROPPED,
                         exit_dns_health_first_hop_nickname="dropped")
    relays[KEPT].update(exit_dns_health_status="success", exit_dns_health_first_hop=OWNER.lower(),
                        exit_dns_health_first_hop_nickname="owner", exit_dns_health_first_hop_country="de")

    page_writer.write_relay_info(relay_set)
    return tmp_path / "relay"


def _page(relay_dir, fingerprint):
    return (relay_dir / fingerprint / "index.html").read_text()


def _section(html, start_id, end_id):
    return html[html.index(f'id="{start_id}"'):html.index(f'id="{end_id}"')]


def test_alleged_members_link_only_relays_with_a_page(tmp_path):
    relay_dir = _render_relay_pages(tmp_path)
    alleged = _section(_page(relay_dir, OWNER), "mf-alleged", "mf-indirect")

    assert f'<a href="../{KEPT}/">{KEPT}</a>' in alleged
    for missing in (DROPPED, UNKNOWN, "nicknameonly"):
        assert f"../{missing}/" not in alleged
        assert re.search(rf'{missing} <span class="al-status-muted"[^>]*>{re.escape(NOT_IN_NETWORK)}</span>',
                         alleged), missing
    assert f'<a href="../{KEPT}/">{KEPT}</a> <span' not in alleged


def test_effective_and_indirect_members_use_the_same_rule(tmp_path):
    relay_dir = _render_relay_pages(tmp_path)
    owner = _page(relay_dir, OWNER)

    effective = _section(owner, "mf-effective", "mf-alleged")
    assert f"{OWNER} (this relay)" in effective
    assert f'<a href="../{KEPT}/">{KEPT}</a>' in effective
    assert f"../{DROPPED}/" not in effective
    assert f'{DROPPED} <span class="al-status-muted"' in effective

    indirect = owner[owner.index('id="mf-indirect"'):]
    indirect = indirect[:indirect.index("</dl>")]
    assert f"../{INDIRECT_UNKNOWN}/" not in indirect
    assert f"{INDIRECT_UNKNOWN} <span" in indirect

    assert f'<a href="../{OWNER}/">{OWNER}</a>' in _page(relay_dir, KEPT)


def test_authority_votes_link_the_authority_relay_page(tmp_path):
    relay_dir = _render_relay_pages(tmp_path)
    owner = _page(relay_dir, OWNER)

    assert re.search(rf'<a href="\.\./\.\./relay/{MORIA1}/"[^>]*>\s*<strong>moria1\b', owner)
    assert f"relay/{OLD_MORIA1}/" not in owner
    for v3_key in AUTHORITIES_BY_NAME.values():
        assert v3_key not in owner
    assert re.search(r'<td>\s*<strong>bastet\b', owner)  # shown, no page to link


def test_no_relay_page_links_a_missing_relay_page(tmp_path):
    relay_dir = _render_relay_pages(tmp_path)
    pages = set(os.listdir(relay_dir))

    for fingerprint in pages:
        html = _page(relay_dir, fingerprint)
        targets = re.findall(r'href="\.\./([^"/.][^"/]*)/"', html)
        targets += re.findall(r'href="\.\./\.\./relay/([^"/]+)/', html)
        assert set(targets) <= pages, (fingerprint, set(targets) - pages)


def test_exit_dns_first_hop_links_only_relays_with_a_page(tmp_path):
    relay_dir = _render_relay_pages(tmp_path)

    def first_hop(fingerprint):
        html = _page(relay_dir, fingerprint)
        start = html.index("<dt>First Hop</dt>")
        return html[start:html.index("</dd>", start)]

    dropped = first_hop(OWNER)
    assert f"../{DROPPED}/" not in dropped
    assert re.search(rf'dropped\s+<span [^>]*>{DROPPED}</span> <span class="al-status-muted"[^>]*>'
                     rf'{re.escape(NOT_IN_NETWORK)}', dropped)
    assert re.search(rf'owner \(DE\)\s+<a href="\.\./{OWNER}/" title="Guard relay used to build test circuit"',
                     first_hop(KEPT))
