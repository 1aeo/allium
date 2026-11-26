# Planned Features

**Audience**: Contributors
**Scope**: Open feature roadmap organized by Now / Next / Later. Shipped capabilities live in [Implemented Features](../implemented/README.md); archived proposals and design drafts remain in Git history.

## Now

- **Extended authority monitoring** (`misc/authorities.html`, `allium/lib/consensus/`): `misc/authorities.html` already covers Onionoo-discovered authorities (plus display-only `KNOWN_OFFLINE_AUTHORITIES` in `allium/lib/consensus/collector_fetcher.py`), consensus freshness, vote counts, consensus method, version compliance, multi-period uptime and 1M z-score, `sbws` bandwidth-scanner status, TCP connect latency via `probe_authority_latency`, and flag thresholds; relay pages show `format_relay_consensus_evaluation`. Still open: a 30-day authority scorecard and extended consensus health analytics. Extend `allium/lib/consensus/` and `misc/authorities.html`, and avoid turning the dormant `consensus_health` worker (`CONSENSUS_HEALTH_CONFIG.enabled = False` in `allium/lib/workers.py`) into a parallel `probe_authority_latency`.
- **Actionable operator improvement guidance & size-based peer cohorts** (`allium/templates/contact.html`, `allium/lib/operator_analysis.py`): Contact pages already display AROI placements, CW/BW percentiles, multi-period uptime, and bandwidth stability/outliers, 1M relay charts include role and family medians (`peer_medians`), and listing pages print `smart_context` summaries. Still open: gap-to-rank recommendations, size-based peer cohorts grouping operators by relay count, and a suggestions panel / similar-operator links reusing precomputed contact stats.

## Next

- **Static geographic heat map & AROI achievement wheel** (`allium/lib/charts/`): Country/platform breakdowns and 21 AROI leaderboard tables are shipped, while a world heat map page and achievement wheel remain open. Build via the static PNG/SVG pipeline in `allium/lib/charts/` (PNG default for Tor Browser Safest level; no D3, Chart.js, TopoJSON, or browser JS chart libraries).
- **Optional RouteFluxMap export hooks**: Country (`#CC=`) and relay (`#relay=`) pages already link out to RouteFluxMap; optional exported JSON feeds (country rarity, validated operators, AS links) remain open.

## Later

- **Bridge network health**: Fetch Onionoo bridge endpoints (`type=bridge`) and render bridge health pages (`collector_fetcher.py` uses `"bridge"` only for the removed-authority display list).
- **Predictive relay failure modeling**: Add failure-risk scoring on top of existing descriptive uptime and bandwidth outlier detection.
- **Historical ClickHouse analytics**: Long-term historical query and analytics storage backend.

## How to Verify

```bash
# Health worker is registered and disabled; authority probing runs via probe_authority_latency
grep -n "CONSENSUS_HEALTH_CONFIG" -A 10 allium/lib/workers.py
grep -n "def probe_authority_latency" -A 8 allium/lib/page_writer.py

# Confirm bridge fetch, browser chart libraries, and failure model remain absent
grep -rn "type=bridge" allium || true
grep -rnE "chart\.js|d3\.js|topojson" allium || true
grep -rnE "failure prediction|predictive_analytics" allium || true
```
