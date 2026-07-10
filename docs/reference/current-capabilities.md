# Current Capabilities

**Audience**: All  
**Scope**: Complete list of working features

## Generator

### Data Sources

| Source | Purpose | Memory |
|--------|---------|--------|
| Onionoo Details API | Core relay data | ~400MB |
| Onionoo Uptime API | Historical uptime | ~2GB |
| Onionoo Bandwidth API | Historical bandwidth | ~500MB |
| AROI Validator API | Authenticated operators (CIISS v2 + v3 dual-spec) | Minimal |
| CollecTor Consensus | Flag thresholds (optional) | Minimal |

### Processing

- Multi-threaded API fetching (5 parallel workers)
- Multiprocessing page generation (4 workers default, configurable)
- Memory modes: `--apis details` (~400MB) or `--apis all` (~2.4GB)
- Downtime filtering: excludes relays offline >7 days (configurable)

### Output

Generates ~21,700 HTML pages including:
- `index.html` - AROI leaderboards (main page)
- `top500.html` - Top 500 relays by consensus weight
- `network-health.html` - Network health dashboard
- `search-index.json` - Search data for Cloudflare Pages function
- Individual pages for relays, contacts, countries, ASes, families, platforms, flags

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

### Reliability Excellence (25+ relays required)

- **8. Reliability Masters** - 6-month average uptime
- **9. Legacy Titans** - 5-year average uptime
- **10. Bandwidth Served Masters** - 6-month bandwidth performance
- **11. Bandwidth Served Legends** - 5-year bandwidth performance

### Diversity & Geographic Leadership

Each diversity dimension has two co-equal boards — Volume (relay count on the
non-dominant side of the network) and Breadth (distinct spread within one
operator) — so neither kind of diversity is buried under the other's metric.

- **12. Diversity All-Rounders (Overall)** - Multi-factor diversity scoring
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
- Paginated rankings (Top 10, 11-20, 21-25)
- Independent category navigation

## Network Health Dashboard

10-card monitoring system at `network-health.html`:

1. Relay counts (total, exit, guard, middle)
2. Bandwidth capacity distribution
3. Consensus weight distribution
4. Geographic diversity metrics
5. Platform analysis
6. Network efficiency (measured vs unmeasured)
7. Authority health
8. Flag distribution
9. Version compliance
10. Performance indicators

## Directory Authorities Page

`misc/authorities.html` provides:
- Authority uptime statistics
- Z-score outlier detection
- Version compliance tracking
- Consensus participation monitoring

## Reliability System

### Multi-Period Analysis
- 1-month, 6-month, 1-year, 5-year uptime tracking
- Flag-specific uptime (Exit > Guard > Fast > Running priority)
- "Match Overall Uptime" detection for clean display

### Operator Portfolios
- Network percentile positioning
- Statistical outlier detection (≥2σ deviations)
- Performance trend analysis

## Intelligence Engine

6-layer analysis system providing smart context across templates:

1. **Basic Relationships** - Network statistics
2. **Concentration Patterns** - Risk assessment
3. **Performance Correlation** - CW/BW ratio analysis
4. **Infrastructure Dependency** - Critical AS identification
5. **Geographic Clustering** - Regional distribution
6. **Capacity Distribution** - Network balance

## Search Index

`search-index.json` generated for Cloudflare Pages function:
- Relay search by nickname, fingerprint
- Family groupings
- Compressed format for fast loading

## How to Verify

```bash
# Generate and check output
python3 allium/allium.py --out /tmp/test --apis details --progress

# Verify key files exist
ls /tmp/test/index.html /tmp/test/top500.html /tmp/test/network-health.html
ls /tmp/test/search-index.json
ls /tmp/test/misc/aroi-leaderboards.html /tmp/test/misc/authorities.html

# Count AROI categories in generated HTML
grep -c "leaderboard-category" /tmp/test/misc/aroi-leaderboards.html
```
