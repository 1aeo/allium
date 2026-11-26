# Output Structure

**Audience**: Users, Contributors  
**Scope**: Generated file tree and page purposes

## Directory Layout

```
www/
├── index.html                      # AROI leaderboards (main landing page)
├── top500.html                     # Top 500 relays by consensus weight
├── network-health.html             # Network health dashboard (12 cards + network history)
├── network-pressure.html           # Daily network pressure series and charts
├── search-index.json               # Search data (compact schema v1.7)
├── metrics                         # Prometheus v2 exposition metrics
├── robots.txt                      # Generated only with an absolute https:// --base-url
├── sitemap.xml                     # Canonical-only public URL inventory (https:// --base-url)
│
├── misc/
│   ├── all.html                    # All relays listing (paginated)
│   ├── all-page-2.html             # Additional clean-route pagination pages
│   ├── aroi-leaderboards.html      # AROI leaderboards (canonicalizes to index.html)
│   ├── authorities.html            # Directory authorities monitoring
│   ├── diagnostics.html            # API source health, freshness, and dependency map
│   ├── families-by-bandwidth.html  # Families sorted by bandwidth
│   ├── families-by-consensus-weight.html
│   ├── networks-by-bandwidth.html  # AS networks sorted by bandwidth
│   ├── networks-by-consensus-weight.html
│   ├── contacts-by-bandwidth.html  # Operators sorted by bandwidth
│   ├── contacts-by-consensus-weight.html
│   ├── countries-by-bandwidth.html # Countries sorted by bandwidth
│   ├── countries-by-consensus-weight.html
│   ├── platforms-by-bandwidth.html # Platforms sorted by bandwidth
│   └── platforms-by-consensus-weight.html
│
├── relay/
│   └── <fingerprint>/
│       ├── index.html              # Individual relay details
│       └── *.{png,svg}             # Relay bandwidth/uptime charts (--chart-layout beside)
│
├── contact/
│   └── <hash>/
│       ├── index.html              # Operator profile and relay list
│       └── *.{png,svg}             # Operator charts (--chart-layout beside)
│
├── network/                        # Network history charts (--chart-layout beside)
├── pressure/                       # Network pressure charts (--chart-layout beside)
├── charts/                         # With --chart-layout charts:
│   ├── relay/<fingerprint>/        #   Relay history charts
│   ├── contact/<hash>/             #   Operator history charts
│   ├── network/                    #   Network history charts
│   └── pressure/                   #   Network pressure charts
│
├── country/
│   └── <code>/
│       └── index.html              # Country-specific relay listing
│
├── as/
│   └── <as>/
│       └── index.html              # AS listing; directory is Onionoo `as` (example: AS6939)
│
├── family/
│   └── <hash>/
│       └── index.html              # Family relay listing
│
├── platform/
│   └── <name>/
│       └── index.html              # Platform-specific relay listing
│
├── flag/
│   └── <name>/
│       └── index.html              # Flag-specific relay listing
│
├── first_seen/
│   └── <date>/
│       └── index.html              # Relays first seen on date
│
├── <aroi-domain>/                  # With --base-url: copy of a validated AROI
│   ├── index.html                  # operator's contact pages (index, by-*.html,
│   └── page-N.html                 # page-N.html); removed once the domain is gone
│
└── static/
    ├── favicon.ico                  # Multi-resolution 1AEO favicon
    ├── css/                         # Stylesheets
    └── images/                      # Country and relay flag images
```

## Page Counts (Typical)

| Category | Approximate Count |
|----------|-------------------|
| Relay pages | ~7,000 |
| Contact pages | ~3,000 |
| Country pages | ~90 |
| AS pages | ~1,500 |
| Family pages | ~5,000 |
| Platform pages | ~50 |
| Flag pages | ~10 |
| First seen pages | ~4,000 |
| Misc pages | ~100 |
| **Total** | **~21,700** |

## Key Files

### `index.html`
Main landing page showing AROI leaderboards with 21 categories of authenticated operator rankings.

### `top500.html`
Top 500 relays sorted by consensus weight fraction. Quick overview of the most influential relays.

### `network-health.html`
12-card dashboard plus Network History charts covering relay counts, bandwidth capacity availability, relay uptime, operator participation, geographic participation, provider participation, bandwidth utilization, version compliance, unique operating systems, Happy Families key migration, exit policies, and exit DNS health.

### `network-pressure.html`
Daily network-pressure charts (`Relays Reporting Overload`, `Relays with Guard Flag`, `Relays with HSDir Flag`, and `Directory Bytes Served`) across 1M, 6M, 1Y, and 5Y windows against frozen baseline ranges.

### `misc/diagnostics.html`
Operational diagnostics page (`noindex,follow`) showing per-API cache age, freshness status, worker state, AROI schema/validation diagnostics, and the site-section dependency matrix.

### `metrics`
Prometheus text exposition format (`0.0.4`, schema v2) exporting exit DNS health, upstream resolver shares, AROI state counts, and build metadata. See [Prometheus Metrics](../prometheus/README.md).

### `search-index.json`
Minified JSON search index (schema v1.7) for the Cloudflare Pages serverless function (deployed via `1aeo/allium-deploy`), storing compact relay, family, and lookup maps.

### `robots.txt` and `sitemap.xml`
Both `robots.txt` and `sitemap.xml` are generated **only** when `--base-url` is an absolute `https://` URL. Otherwise `allium/lib/search_discovery.py` skips them and removes any stale `robots.txt`, `sitemap.xml`, or `sitemap-*.xml` files from the output directory. When generated, `sitemap.xml` includes only indexable canonical URLs (omitting `noindex` pages and collapsing duplicate sort/vanity routes), automatically sharding into `sitemap-N.xml` when exceeding protocol limits.

### `misc/authorities.html`
Directory authority monitoring page with uptime statistics, Z-score analysis, latency probes, and consensus participation metrics.

## URL Patterns

| Pattern | Example |
|---------|---------|
| Relay | `/relay/9695DFC35FFEB861329B9F1AB04C46397020CE31/` |
| Contact | `/contact/a1b2c3d4/` |
| Country | `/country/us/` |
| AS | `/as/AS13335/` |
| Family | `/family/e5f6g7h8/` |
| Platform | `/platform/Linux/` |
| Flag | `/flag/Exit/` |
| Validated AROI operator (with `--base-url`) | `/example.org/` |

Standalone `.html` files are published as clean routes: `top500.html` is linked as `/top500`, and `misc/all.html` as `/misc/all`. Generated `.html` files remain on disk for static-host compatibility.

## How to Verify

```bash
# Fast generation with crawler discovery enabled
python3 allium/allium.py --out /tmp/test --apis details \
  --base-url https://metrics.example.com --no-pressure-history

# Check structure and key outputs
find /tmp/test -type f -name "*.html" | wc -l
ls /tmp/test/relay/*/index.html | head -5
ls /tmp/test/contact/*/index.html | head -5
ls /tmp/test/index.html /tmp/test/top500.html /tmp/test/network-health.html \
   /tmp/test/network-pressure.html /tmp/test/misc/diagnostics.html \
   /tmp/test/search-index.json /tmp/test/metrics /tmp/test/robots.txt /tmp/test/sitemap.xml
```
