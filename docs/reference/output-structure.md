# Output Structure

**Audience**: Users, Contributors  
**Scope**: Generated file tree and page purposes

## Directory Layout

```
www/
├── index.html                      # AROI leaderboards (main landing page)
├── top500.html                     # Top 500 relays by consensus weight
├── network-health.html             # Network health dashboard
├── search-index.json               # Search data for Cloudflare Pages function
│
├── misc/
│   ├── all.html                    # All relays listing
│   ├── aroi-leaderboards.html      # AROI leaderboards (duplicate of index)
│   ├── authorities.html            # Directory authorities monitoring
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
│       └── index.html              # Individual relay details
│
├── contact/
│   └── <hash>/
│       └── index.html              # Operator profile and relay list
│
├── country/
│   └── <code>/
│       └── index.html              # Country-specific relay listing
│
├── as/
│   └── <number>/
│       └── index.html              # AS-specific relay listing
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
└── static/
    ├── *.css                       # Stylesheets
    ├── *.png                       # Country and relay flag images
    └── ...                         # Other static assets
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
Main landing page showing AROI leaderboards with 18 categories of authenticated operator rankings.

### `top500.html`
Top 500 relays sorted by consensus weight fraction. Quick overview of the most influential relays.

### `network-health.html`
10-card dashboard showing network health metrics: relay counts, bandwidth, consensus weight distribution, geographic diversity, platform analysis, and authority health.

### `search-index.json`
JSON file containing relay search data for use with Cloudflare Pages serverless function. Includes nicknames, fingerprints, and family groupings.

### `misc/authorities.html`
Directory authority monitoring page with uptime statistics, Z-score analysis, and consensus participation metrics.

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

## How to Verify

```bash
# Generate output
python3 allium/allium.py --out /tmp/test --apis details

# Check structure
find /tmp/test -type f -name "*.html" | wc -l  # Should be ~21,000+
ls /tmp/test/relay/*/index.html | head -5      # Relay pages
ls /tmp/test/contact/*/index.html | head -5    # Contact pages

# Verify key files
test -f /tmp/test/index.html && echo "index.html exists"
test -f /tmp/test/top500.html && echo "top500.html exists"
test -f /tmp/test/search-index.json && echo "search-index.json exists"
```
