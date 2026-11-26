# Current Capabilities

**Audience**: All  
**Scope**: Complete list of working features

## Generator

### Data Sources

Under `--apis all`, 7 enabled coordinator workers fetch data in parallel threads, followed by the daily CollecTor pressure-history backfill (`allium/lib/pressure_history.py`):

| Source | Purpose | Memory |
|--------|---------|--------|
| Onionoo Details API | Core relay data (critical) | ~400MB |
| Onionoo Uptime API | Historical uptime & `first_seen` repair | ~2GB |
| Onionoo Bandwidth API | Historical bandwidth & overload evaluation | ~500MB |
| AROI Validator API | Authenticated operators (CIISS v2 + v3 dual-spec) | Minimal |
| Exit DNS Health API | Exit relay DNS resolution & upstream resolvers | Minimal |
| CollecTor Consensus | Authority votes, flag thresholds & consensus evaluation | Minimal |
| CollecTor Server Descriptors | Happy Families `family-cert` Ed25519 keys | Minimal |
| CollecTor Pressure History | Daily overload, Guard, HSDir & directory bytes series | Minimal |

### Processing

- Threaded API fetching (`allium/lib/coordinator.py` and `allium/lib/workers.py`, 7 enabled workers under `--apis all`) plus post-coordinator pressure history backfill (`--no-pressure-history` skips download)
- Multiprocessing page generation (`--workers` defaults to `max(4, os.cpu_count() or 4)`; `0` disables multiprocessing)
- Memory modes: `--apis details` (~400MB) or `--apis all` (~2.4GB)
- Downtime filtering: excludes relays not seen for >7 days before the Onionoo snapshot (`--filter-downtime`, `0` disables)

### Output

Generates ~21,700 HTML pages and supporting artifacts:
- `index.html` - AROI leaderboards (main page)
- `top500.html` - Top 500 relays by consensus weight
- `network-health.html` - Network health dashboard
- `network-pressure.html` - Daily network pressure charts
- `misc/diagnostics.html` - API source health, freshness, and dependency map
- `metrics` - Prometheus v2 exposition metrics (see [Prometheus Metrics](../prometheus/README.md))
- `search-index.json` - Search data (schema v1.7) for Cloudflare Pages function
- `robots.txt` and `sitemap.xml` - Generated when `--base-url` is an absolute `https://` URL
- Individual pages for relays, contacts, countries, ASes, families, platforms, flags, and `first_seen` dates
- Build-time PNG/SVG history charts (1M/6M/1Y/5Y) for relays, contacts, whole-network health, and network pressure (see [History Charts](../features/implemented/history-charts.md))
- RouteFluxMap links: nav and footer in `allium/templates/skeleton.html`, `#CC=` plus the uppercase ISO code on country pages, `#relay=` plus the fingerprint on relay pages (further map proposals are tracked in [Planned Features](../features/planned/README.md))

## AROI Leaderboards (21 Categories)

Authenticated Relay Operator Identification system ranking verified operators.

### Capacity & Performance

- **1. Bandwidth Capacity Contributed** - Total observed bandwidth
- **2. Consensus Weight Leaders** - Network routing influence
- **3. Total Data Transferred Champions (5-Year)** - Cumulative data served (read + write)

### Network Role Specialization

- **4. Exit Authority Champions** - Exit consensus weight
- **5. Guard Authority Champions** - Guard consensus weight
- **6. Exit Operators** - Exit relay count
- **7. Guard Operators** - Guard relay count

### Reliability Excellence (`>25` relays / `26+ relays` required)

- **8. Reliability Masters** - 6-month average uptime
- **9. Legacy Titans** - 5-year average uptime
- **10. Bandwidth Served Masters** - 6-month bandwidth performance
- **11. Bandwidth Served Legends** - 5-year bandwidth performance

### Diversity & Geographic Leadership

Each diversity dimension has two co-equal boards — Volume (relay count on the non-dominant side of the network) and Breadth (distinct spread within one operator) — so neither kind of diversity is buried under the other's metric.

- **12. Diversity All-Rounders (Overall)** - Diversity Index (0–100): mean of four co-equal sub-scores (Geographic, Platform, Network, Scale = diverse relays differing from the operator's dominant OS/country/AS); every yardstick derived from the live network each run
- **13. Non-Linux Powerhouses (Platform Volume)** - Non-Linux relay count (distinct OS tiebreaker)
- **14. OS Polyglots (Platform Breadth)** - Distinct OSes incl. Linux, 2+ to qualify (non-Linux relay tiebreaker)
- **15. Global Powerhouses (Non-EU Volume)** - Non-EU relay count (distinct country tiebreaker)
- **16. Jurisdiction Globetrotters (Non-EU Breadth)** - Distinct non-EU countries (non-EU relay tiebreaker)
- **17. Frontier Builders (Rare-Country Breadth)** - Distinct rare countries (rare-relay tiebreaker)

### Innovation & Infrastructure

- **18. Network Veterans** - Scale-weighted tenure
- **19. IPv4 Address Leaders** - Unique IPv4 diversity
- **20. IPv6 Address Leaders** - Unique IPv6 diversity
- **21. AROI Validation Champions** - Verified identity count

### Features
- Champion badge system
- Paginated rankings (Top 10, 11–20, 21–25)
- Independent CSS-only category navigation

## Network Health Dashboard

12 metric cards plus Network History charts at `network-health.html`:

1. **Relay Counts** - Total, Exit, Guard, Middle, Exit+Guard, Fast, Stable, Measured, Offline, Authorities, V2Dir, HSDir, IPv4/IPv6 dual-stack vs IPv4-only, BadExit, StaleDesc, Sybil, Overloaded, new relay windows, and mean/median age
2. **Bandwidth Capacity Availability** - Total capacity, 5yr total data transferred, role breakdowns, mean/median by role/flag, IPv4/IPv6 capacity, observed vs advertised diff
3. **Relay Uptime** - Overall 1mo mean, role/flag 1mo mean & median, and 1mo/6mo/1yr/5yr series
4. **Operator Participation** - AROI domain/relay coverage, validation counts, CIISS v2 vs v3 proof rates & declarations, schema version, contact/family adoption, AROI IPv6 adoption
5. **Geographic Participation** - Unique countries, top-3 countries by CW, EU/Non-EU/Rare/Five Eyes/Fourteen Eyes CW concentration, top AROI countries, IPv4/IPv6 country leaders
6. **Provider Participation** - Unique ASes, top-3 ASes, top-3/5/10 AS CW concentration, AS/country & AROI/family density, IPv4/IPv6 AS leaders
7. **Bandwidth Utilization** - CW/BW ratio mean/median overall, Guard/Exit, EU/Non-EU, and top-3/5/10 AS cohorts
8. **Version Compliance** - Recommended, Not Recommended, Experimental, Obsolete, Outdated counts, and top obsolete operators by CW
9. **Unique Operating Systems** - Unique platform count, top-3 platforms, and others
10. **Happy Families Key Migration** - Authority v0.4.9.x+ readiness, consensus method & vote support, family-ids/family-lists params, `family-cert` adoption, operator migration, and Tor ≥0.4.9.x readiness
11. **Exit Policies** - Unrestricted vs port-restricted exits, ports 80/443 coverage, public IP restrictions
12. **Exit DNS Health** - DNS success rate, tested/consensus exits, reachability rate, failure categories, circuit errors, and upstream resolver shares
- **Network History Charts** - Whole-network summed bandwidth and mean Running-flag uptime across 1M, 6M, 1Y, and 5Y

## Network Pressure

`network-pressure.html` tracks four daily time series across 1M, 6M, 1Y, and 5Y windows against frozen May 2025–May 2026 p10–p90 usual ranges:
- Relays Reporting Overload (`overload-general` share from CollecTor server descriptors)
- Relays with Guard Flag (Tor Metrics `relayflags.csv`)
- Relays with HSDir Flag (Tor Metrics `relayflags.csv`)
- Directory Bytes Served (`dirwrite` from Tor Metrics `dirbytes.csv`)

## API Diagnostics

`misc/diagnostics.html` (`noindex,follow`) provides operational visibility into every data source:
- Overall health banner and per-API status cards (`fresh`, `aging`, `stale`, `unavailable`) with cache age vs max age and worker errors
- AROI extended diagnostics (`aroivalidator` schema version, `ciissversion` counts, proof-type rollups, top v3 error categories, build-time warnings)
- Site Section → Data Source dependency matrix

## Directory Authorities Page

`misc/authorities.html` provides:
- Authority uptime statistics and latency probes
- Z-score outlier detection
- Version compliance tracking
- Consensus participation monitoring

## Reliability System

### Multi-Period Analysis
- 1-month, 6-month, 1-year, 5-year uptime tracking
- Flag-specific uptime (`Exit > Guard > Fast > Running` priority)
- "Match Overall Uptime" detection for clean display

### Operator Portfolios
- Network percentile positioning
- Statistical outlier detection (≥2σ deviations)
- Performance trend analysis

## Intelligence Engine

7-layer analysis system (`allium/lib/intelligence_engine.py`) pre-computing context across templates:

1. **Basic Relationships** - Network entity counts
2. **Concentration Patterns** - Country, AS, contact, and platform concentration
3. **Performance Correlation** - Measured percentage, underutilized detection, CW/BW efficiency ratio
4. **Infrastructure Dependency** - Unique Tor versions, critical AS identification (>5% weight), sync risk
5. **Geographic Clustering** - Five/Fourteen Eyes influence and regional HHI concentration index
6. **Capacity Distribution** - Gini coefficient and Guard/Exit capacity share
7. **Contact Intelligence** - Per-operator network rarity rating, measurement status, geographic diversity, CW/BW percentile rank, infrastructure diversity, and operational maturity

## Search Index

`search-index.json` (compact schema v1.7) generated for the Cloudflare Pages Function (`1aeo/allium-deploy`):
- Relay search by nickname, fingerprint, IP, AS, country, flag, and CIISS version
- Family groupings and validated AROI domain metadata

## How to Verify

```bash
# Fast local generation and check output
python3 allium/allium.py --out /tmp/test --apis details --progress --no-pressure-history

# Verify key files exist
ls /tmp/test/index.html /tmp/test/top500.html /tmp/test/network-health.html \
   /tmp/test/network-pressure.html /tmp/test/misc/diagnostics.html \
   /tmp/test/search-index.json /tmp/test/metrics \
   /tmp/test/misc/aroi-leaderboards.html /tmp/test/misc/authorities.html

# Count AROI category navigation links in generated HTML (should print 21)
grep -c 'aroi-nav-link' /tmp/test/misc/aroi-leaderboards.html
```
