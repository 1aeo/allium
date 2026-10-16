# Feature shortlist status

**Audience**: Contributors
**Scope**: Which of the eight features originally proposed in this file are in the generator, and which are still open. Longer design notes stay in the linked proposals. Shipped behavior is also listed in `docs/reference/current-capabilities.md` and `docs/features/implemented/`.

This file is a status index. It does not add features.

## Status

| Item | Status | In the generator now | Still open |
|------|--------|----------------------|------------|
| Geographic heat map | Open | Country tables; country pages link out to RouteFluxMap | A world map |
| AROI achievement wheel | Open | 21 leaderboard categories as tables | A wheel or doughnut chart |
| Improvement guidance | Open | Rankings, CW/BW percentiles, uptime, bandwidth stability on contact pages | Gap-to-rank recommendations |
| Directory authority health | Partial | `misc/authorities.html` and `allium/lib/consensus/` | 30-day scorecard; the health API worker is registered but off |
| Peer cohorts by relay count | Open | Network CW/BW percentiles; role and family medians on 1-month charts | Groups of operators with a similar relay count |
| Bridge health dashboard | Open | No Onionoo bridge fetch and no bridge pages | The bridge dashboard |
| Smart suggestions | Partial | `smart_context` summary lines on listing pages | A suggestions panel and similar-operator links |
| Predictive failure detection | Open | Descriptive uptime and bandwidth outliers | A failure-risk model |

## Already in the generator

The original shortlist treated the following as done. The paths below match the current tree.

- **AROI leaderboards.** `_rank_operators` in `allium/lib/aroileaders.py` builds 21 categories: `bandwidth`, `consensus_weight`, `exit_authority`, `guard_authority`, `exit_operators`, `guard_operators`, `reliability_masters`, `legacy_titans`, `most_diverse`, `platform_volume`, `platform_breadth`, `non_eu_volume`, `non_eu_breadth`, `frontier_builders`, `network_veterans`, `ipv4_leaders`, `ipv6_leaders`, `bandwidth_masters`, `bandwidth_legends`, `validated_relays`, `total_data_champions`. Templates: `allium/templates/aroi-leaderboards.html`. `allium/lib/site_generator.py` writes that template to `index.html`.
- **Network health dashboard.** `allium/templates/network-health-dashboard.html` is written to `network-health.html`. Ribbon cards: relay counts, bandwidth capacity, relay uptime, operator participation, geographic participation, provider participation, bandwidth utilization, version compliance, operating systems, happy families, exit policies, exit DNS health. Data: `allium/lib/network_health.py`.
- **Contact intelligence.** `IntelligenceEngine.analyze_all_layers` in `allium/lib/intelligence_engine.py` returns seven sections: `basic_relationships`, `concentration_patterns`, `performance_correlation`, `infrastructure_dependency`, `geographic_clustering`, `capacity_distribution`, `contact_intelligence`. Pages read them from `relays.json.smart_context`.
- **Operator reliability, CW/BW, and bandwidth stability.** `allium/lib/operator_analysis.py` and `allium/templates/contact.html`.
- **Country and platform breakdowns.** `misc-countries.html`, `misc-platforms.html`, and the per-country and per-platform pages.

## Open and partial items

### Geographic heat map (open)

`misc-countries.html` and the geographic card on `network-health.html` show country counts, Five Eyes and Fourteen Eyes shares, and regional concentration. `allium/templates/country.html` links to RouteFluxMap. The repository has no D3, Chart.js, or TopoJSON dependency, and no geographic-map module.

Sketches: `milestone-1-graphs-charts.md`, `visualization-dashboard-proposal.md`. Those sketches assume a browser chart library. Charts that did ship are build-time PNG and SVG with no page JavaScript (`docs/features/implemented/history-charts.md`, `allium/lib/charts/`). PNG is the default because Tor Browser's Safest level disables SVG. A map still has to fit that static generator. This file does not specify one.

### AROI achievement wheel (open)

Leaderboards are HTML tables and text badges. There is no doughnut chart. The milestone-1 sketches are historical UI sketches, under the same static-generation constraint as the heat map.

### Actionable improvement guidance (open)

Contact pages show AROI category placements, CW/BW against the network average and percentile, uptime for 1 month / 6 months / 1 year / 5 years, and bandwidth coefficient of variation and trend. They do not compute the gap to rank 1 or recommend where to add relays. Proposal: `actionable-improvement-guidance.md`. Its layout sketch does not match the current contact page.

### Directory authority health (partial)

`misc/authorities.html` is built by `get_directory_authorities_data` in `allium/lib/page_writer.py`.

Present on that page:

- Authorities discovered from Onionoo, plus display-only known-offline rows in `KNOWN_OFFLINE_AUTHORITIES` (`allium/lib/consensus/collector_fetcher.py`). Those rows are not voters.
- Consensus freshness, vote relay counts, consensus method, and recommended-version compliance.
- Uptime for 1 month, 6 months, 1 year, and 5 years, with a 1-month z-score.
- Bandwidth-scanner column from CollecTor vote files.
- TCP connect time to each voting authority's directory port. `probe_authority_latency` runs from the coordinator before rendering and passes discovered Onionoo addresses into `AuthorityMonitor` (2 second timeout). The page shows slow and down counts and lists failed probes in `authority_alerts`.
- Flag thresholds parsed from CollecTor votes.

Relay pages show consensus inclusion and authority vote counts (`allium/templates/relay-info.html`, `format_relay_consensus_evaluation` in `allium/lib/consensus/consensus_evaluation.py`).

`fetch_consensus_health` in `allium/lib/workers.py` also wraps `AuthorityMonitor`. `CONSENSUS_HEALTH_CONFIG.enabled` is false, so `Coordinator.iter_enabled_worker_entries` does not run that worker. Latency for the authorities page comes from `probe_authority_latency`.

Not present:

- A 30-day star scorecard.
- A separate flag-distribution panel on the authorities page. Flag counts are metrics on the network health relay-counts card.
- Client auto-refresh. The site is static HTML.
- An HTTP fetch of each authority's consensus document. The latency check is a TCP connect.

`probe_authority_latency` takes directory addresses from Onionoo `or_addresses` and `dir_address`. `DEFAULT_AUTHORITY_ENDPOINTS` in `allium/lib/consensus/authority_monitor.py` is the fallback when discovery returns no endpoints. Address lists in previous revisions of this file are not endpoints to deploy.

Further sketches: `milestone-2-authority-health.md`, `directory-authorities/directory-authorities-monitoring.md`.

### Peer cohorts by relay count (open)

Contact pages compare an operator with network CW/BW percentiles. One-month relay charts overlay family medians and role medians from `peer_medians` in `allium/lib/charts/series.py` (other guards, other exits, or other middles). Nothing groups operators by relay count. Proposal: `operator_comparison_metrics_proposal_top10.md`.

### Bridge network health (open)

The generator does not request Onionoo bridge details and does not render bridge pages. The word "bridge" in `collector_fetcher.py` names the short known-offline authority list, not the bridge network. Proposal: `bridges/bridge-network-health-dashboard-proposal.md`.

### Smart suggestions (partial)

`index.html`, `all.html`, `misc-countries.html`, `misc-networks.html`, `misc-platforms.html`, and `misc-contacts.html` print `smart_context` summary lines (country and AS concentration, capacity spread, version sync, geographic clustering). There is no suggestions panel, no similar-operator list, and no query-string filter. Proposal: `smart_context_links/`.

### Predictive relay failure detection (open)

Contact pages mark uptime and bandwidth outliers. No module assigns a failure probability or a 48-hour risk list. Proposals: `milestone-3-network-health.md`, `milestone-4-ai-analytics.md`.

## Generator work this shortlist did not name

- Bandwidth and Running-flag history charts on relay pages, and summed bandwidth on contact pages. `docs/features/implemented/history-charts.md`.
- CollecTor server-descriptor freshness for Happy Families classification. `docs/features/implemented/collector-descriptor-freshness-policy.md`.
- Exit DNS health on the network health dashboard. `allium/lib/exit_dns_health.py`.
- `search-index.json` written by `allium/lib/search_index.py` for a Cloudflare Pages Function. That function is not in this repository. Proposal: `search-implementation-plan.md`.

## What to work on next

1. Extend `allium/lib/consensus/` and `misc/authorities.html`. Do not add a second authority monitor, and do not turn the dormant `consensus_health` worker into a parallel implementation of `probe_authority_latency`.
2. Improvement guidance and size-based peer comparison can use data already computed for contact pages. Both are still open.
3. A heat map or an achievement wheel is still open. Follow the static chart pipeline in `allium/lib/charts/` (no browser chart library).
4. Bridges and failure prediction remain separate projects. Use the proposals linked above.

## How to verify

From the repository root:

```bash
# 21 leaderboard categories in _rank_operators
rg -n "leaderboards = \{" -A 40 allium/lib/aroileaders.py

# Seven intelligence sections
rg -n "def analyze_all_layers" -A 14 allium/lib/intelligence_engine.py

# Authorities page: votes, bandwidth scanner, latency, alerts, flag thresholds
rg -n "Voted|BW Auth|Latency \(ms\)|authority_alerts|flag-thresholds" allium/templates/misc-authorities.html

# Health worker is registered and disabled; page probe is separate
rg -n "CONSENSUS_HEALTH_CONFIG" -A 14 allium/lib/workers.py
rg -n "def probe_authority_latency" -A 8 allium/lib/page_writer.py

# No Onionoo bridge fetch, no browser chart library, no failure model in application code
rg -n "type=bridge" allium || true
rg -n "chart\\.js|d3\\.js|topojson" --glob '!docs/**' . || true
rg -n "failure prediction|predictive_analytics" allium || true
```
