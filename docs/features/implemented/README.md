# Implemented Features

**Audience**: Contributors and Users
**Scope**: Consolidated overview of implemented generator capabilities and links to detailed operational docs. See [Planned Features](../planned/README.md) for open work.

## Operational Docs

- [collector-descriptor-freshness-policy.md](collector-descriptor-freshness-policy.md) — Freshness and downgrade-protection policy for CollecTor server-descriptor-based Happy Families classification.
- [history-charts.md](history-charts.md) — Build-time PNG/SVG history charts across relay, contact, network health, and network pressure pages, including caching, layouts, and CSS period switching.

## Shipped Capabilities

- **Multi-API parallel fetching & caching**: 7 enabled workers under `--apis all`, conditional requests, and graceful cache fallback (`allium/lib/coordinator.py`, `allium/lib/workers.py`).
- **AROI v2 + v3 validation & 21 operator leaderboards**: CIISS v2/v3 validation, tiered v3 migration badges, and leaked-key security incident surfacing (`allium/lib/aroi_validation.py`, `allium/lib/aroileaders.py`).
- **Multi-period reliability & uptime analytics**: 1M/6M/1Y/5Y tracking, flag-specific uptime priority (`Exit > Guard > Fast > Running`), network percentiles, `≥2σ` outlier detection, and `first_seen` repair from `/uptime` (`allium/lib/uptime_utils.py`, `allium/lib/operator_analysis.py`, `allium/lib/first_seen_correction.py`).
- **Network Health Dashboard**: 12 metric cards plus whole-network bandwidth and uptime history charts (`network-health.html`, `allium/lib/network_health.py`).
- **Daily Network Pressure tracking**: Daily overload share, Guard count, HSDir count, and directory bytes served against frozen baseline bands (`network-pressure.html`, `allium/lib/pressure_history.py`, `allium/lib/charts/pressure.py`).
- **Directory Authorities monitoring & per-relay consensus evaluation**: CollecTor vote parsing, flag thresholds, TCP latency probing, and centralized relay diagnostics (`misc/authorities.html`, `allium/lib/consensus/`, `allium/lib/relay_diagnostics.py`).
- **7-layer Intelligence Engine & smart context summaries**: Precomputed relationship, concentration, performance, infrastructure, geography, capacity, and contact insights (`allium/lib/intelligence_engine.py`, `allium/lib/operator_analysis.py`).
- **Build-time PNG/SVG history charts**: Relay, contact, whole-network, and pressure charts rendered with zero JavaScript and CSS `:target` period switching (`allium/lib/charts/`, [history-charts.md](history-charts.md)).
- **Exit DNS Health & upstream resolver tracking**: Per-exit DNS resolution status, failure streaks, and upstream resolver share tracking (`allium/lib/exit_dns_health.py`).
- **Happy Families CollecTor descriptor freshness & downgrade protection**: Source-age gating and two-step downgrade confirmation for `family-cert` classification (`allium/lib/workers.py`, [collector-descriptor-freshness-policy.md](collector-descriptor-freshness-policy.md)).
- **Server-side Search Index v1.7**: Compact JSON relay, family, and lookup index for Cloudflare Pages search (`search-index.json`, `allium/lib/search_index.py`).
- **SEO clean routes & crawler discovery**: Clean links, `robots.txt` and `sitemap.xml` generation for absolute HTTPS `--base-url`, pagination, and a 1.9 MB per-page HTML crawl-size guard (`allium/lib/seo.py`, `allium/lib/search_discovery.py`).
- **Prometheus exposition v2 metrics**: Text exposition metrics for Exit DNS Health and AROI validation status (`metrics`, `allium/lib/prometheus_metrics.py`, [docs/prometheus/README.md](../../prometheus/README.md)).
- **API Diagnostics page**: Data-source freshness, cache status, and section dependency reporting (`misc/diagnostics.html`, `allium/lib/api_diagnostics.py`).
- **Fork-based multiprocessing page generation & precomputation**: Copy-on-write forked workers and precomputed contact/family data (`allium/lib/worker_pool.py`, `allium/lib/page_writer.py`).
- **RouteFluxMap deep links**: Direct links from country (`#CC=`) and relay (`#relay=`) pages plus site navigation and footer (`allium/templates/country.html`, `allium/templates/relay-info.html`, `allium/templates/skeleton.html`).

## How to Verify

```bash
python3 allium/allium.py --help
pytest tests/unit/
```
