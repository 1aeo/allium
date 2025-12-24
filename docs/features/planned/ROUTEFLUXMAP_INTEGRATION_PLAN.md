# RouteFluxMap Integration Plan for Allium

**Status**: 📊 Integration Analysis Complete  
**Date**: December 2024  
**Document Type**: Technical Integration Strategy  

---

## Executive Summary

**RouteFluxMap** (https://github.com/1aeo/routefluxmap) is an excellent fit for Allium's **Feature #1: Interactive Geographic Heat Map Dashboard**. In fact, RouteFluxMap already implements most of what Feature #1 proposes, plus additional capabilities like real-time particle animations and historical data navigation.

### Compatibility Score: 95/100

| Aspect | Score | Notes |
|--------|-------|-------|
| **Feature Overlap** | 98% | RouteFluxMap covers all Feature #1 requirements |
| **Data Compatibility** | 95% | Both use Onionoo API as primary data source |
| **Technical Complementarity** | 92% | Modern TypeScript/React vs Python static generation |
| **Deployment Alignment** | 90% | Both support static deployment |
| **Strategic Value** | 100% | Perfect synergy - visualization + analytics |

---

## Feature #1 Requirements vs RouteFluxMap Capabilities

### What Feature #1 Proposed

```
Interactive Geographic Heat Map Dashboard
- ✅ Interactive world map with color-coded countries
- ✅ Hover tooltips showing relay counts
- ✅ Click-through to country detail pages
- ✅ Mobile-responsive with touch zoom/pan
- ✅ < 2 second load time
- ✅ WCAG 2.1 AA accessibility compliance
```

### What RouteFluxMap Already Provides

| Feature #1 Requirement | RouteFluxMap Implementation | Status |
|------------------------|----------------------------|--------|
| Interactive world map | WebGL-powered Deck.gl + MapLibre GL | ✅ **Exceeds** |
| Color-coded countries | Country choropleth with client count data | ✅ **Implemented** |
| Hover tooltips | `CountryTooltip` and `RelayTooltip` components | ✅ **Implemented** |
| Click-through navigation | Country statistics panel on click | ✅ **Implemented** |
| Mobile responsive | `useIsMobile` hook + touch controls | ✅ **Implemented** |
| Fast load time | Static JSON + optimized WebGL | ✅ **Implemented** |
| Relay markers by location | Aggregated nodes with bandwidth sizing | ✅ **Bonus Feature** |
| Particle flow animation | WebGL particle canvas | ✅ **Bonus Feature** |
| Historical data | Date slider with bandwidth chart | ✅ **Bonus Feature** |
| Search functionality | `RelaySearch` component | ✅ **Bonus Feature** |

---

## Technical Architecture Comparison

### Allium (Current)

```
┌─────────────────────────────────────────────────────────┐
│  Python Static Site Generator                           │
│  ├── Jinja2 Templates → HTML pages                     │
│  ├── Onionoo API → relay/country data                  │
│  └── Static hosting (any web server)                   │
└─────────────────────────────────────────────────────────┘

Technology Stack:
- Python 3.8+
- Jinja2 templating
- Static HTML/CSS output
- Country classification (country_utils.py)
- AROI leaderboards (aroileaders.py)
- Intelligence engine (intelligence_engine.py)
```

### RouteFluxMap

```
┌─────────────────────────────────────────────────────────┐
│  Astro/React Static Site                                │
│  ├── React + Deck.gl + MapLibre → Interactive Map      │
│  ├── Onionoo/Collector API → relay data                │
│  └── Cloudflare Pages/R2 for hosting + data            │
└─────────────────────────────────────────────────────────┘

Technology Stack:
- Astro (static site framework)
- React (UI components)
- Deck.gl (WebGL layers)
- MapLibre GL (base maps)
- Tailwind CSS
- TypeScript
```

---

## Integration Strategies

### Strategy A: Embedded Iframe (Quick Win) 🚀

**Timeline: 1-2 days**

Embed RouteFluxMap as an iframe in Allium's generated pages.

```html
<!-- allium/templates/geographic-map.html -->
{% extends "skeleton.html" %}
{% block content %}
<div class="map-container">
    <h2>🌍 Tor Network Global Distribution</h2>
    <iframe 
        src="https://routefluxmap.1aeo.com"
        width="100%" 
        height="600"
        frameborder="0"
        title="Interactive Tor Network Map">
    </iframe>
    <p class="map-note">
        Powered by <a href="https://github.com/1aeo/routefluxmap">RouteFluxMap</a>
    </p>
</div>
{% endblock %}
```

**Pros:**
- Zero development effort
- Instant deployment
- RouteFluxMap maintained separately
- No code changes to Allium

**Cons:**
- Iframe limitations (can't deep-link to Allium pages)
- Separate deployment/hosting
- Limited styling control
- No data sharing between projects

---

### Strategy B: API Bridge with Deep Links (Recommended) ⭐

**Timeline: 2-3 weeks**

Connect RouteFluxMap to Allium via configuration, enabling seamless navigation between the visualization and detailed analytics.

**Pros:**
- Seamless user experience
- Each project remains independent
- Users can navigate from visualization to detailed analytics
- Easy to maintain separately
- Minimal code changes required

**Cons:**
- Two deployments to manage
- Data not perfectly synchronized (hourly vs on-demand)

---

## Strategy B: Detailed Implementation Guide

### Phase 1: Configure Cross-Linking (Day 1-2)

#### 1.1 RouteFluxMap Configuration

RouteFluxMap already has built-in support for external metrics URLs via environment variables:

```typescript
// routefluxmap/src/lib/config.ts (already exists)
export const config = {
  metricsUrl: import.meta.env.PUBLIC_METRICS_URL || '',
  // ...
};

// Helper function already exists:
export function getRelayMetricsUrl(fingerprint: string): string {
  const cleanFingerprint = fingerprint
    .replace(/[$:\s-]/g, '')
    .toUpperCase();
  
  if (!/^[0-9A-F]{40}$/.test(cleanFingerprint)) {
    return `${config.metricsUrl}/relay/0000000000000000000000000000000000000000`;
  }
  
  return `${config.metricsUrl}/relay/${cleanFingerprint}`;
}
```

**Action Required:** Set the environment variable in RouteFluxMap's deployment:

```bash
# routefluxmap/deploy/config.env
PUBLIC_METRICS_URL=https://allium.1aeo.com
PUBLIC_SITE_URL=https://routefluxmap.1aeo.com
```

This single change makes all "View on Metrics" links in `RelayPopup.tsx` point to Allium.

#### 1.2 URL Schema Alignment

**Current URL Patterns:**

| Entity | RouteFluxMap Links To | Allium Generates |
|--------|----------------------|------------------|
| Relay | `/relay/{fingerprint}` | `/relay/{fingerprint}/index.html` |
| Country | `/country/{CC}` | `/country/{cc}/index.html` |
| AS | `/as/{ASN}` | `/as/{ASN}/index.html` |
| Contact | `/contact/{hash}` | `/contact/{hash}/index.html` |

**Key Observations:**
1. RouteFluxMap uses uppercase fingerprints (canonical Tor format)
2. Allium uses lowercase country codes in URLs
3. Both use directory-style URLs with trailing slashes

#### 1.3 Allium URL Compatibility

Allium already generates directory-based URLs. The template shows:

```jinja2
{# allium/templates/relay-info.html #}
<a href="{{ page_ctx.path_prefix }}country/{{ relay['country']|escape }}/">
    {{ relay['country_name']|escape }}
</a>
```

**No changes needed** - Allium's directory structure (`/relay/{fp}/index.html`) works with clean URLs when served by any web server.

---

### Phase 2: Add Country Deep Links from RouteFluxMap (Day 3-5)

RouteFluxMap's `CountryLayer.tsx` shows country data on hover. Add click-through to Allium country pages.

#### 2.1 Create Country Link Helper

```typescript
// routefluxmap/src/lib/config.ts - ADD this function

/**
 * Build URL to country detail page on metrics site
 * @param countryCode - ISO 3166-1 alpha-2 code (e.g., 'US', 'DE')
 */
export function getCountryMetricsUrl(countryCode: string): string {
  // Allium uses lowercase country codes
  const cleanCode = countryCode.toUpperCase().replace(/[^A-Z]/g, '');
  
  if (!/^[A-Z]{2}$/.test(cleanCode)) {
    console.warn(`Invalid country code: ${countryCode}`);
    return config.metricsUrl;
  }
  
  return `${config.metricsUrl}/country/${cleanCode.toLowerCase()}/`;
}

/**
 * Build URL to AS detail page on metrics site
 * @param asNumber - AS number (e.g., 'AS12345' or '12345')
 */
export function getASMetricsUrl(asNumber: string): string {
  // Extract numeric part, handle 'AS12345' or '12345' formats
  const match = asNumber.match(/(\d+)/);
  if (!match) {
    console.warn(`Invalid AS number: ${asNumber}`);
    return config.metricsUrl;
  }
  
  return `${config.metricsUrl}/as/AS${match[1]}/`;
}
```

#### 2.2 Update Country Tooltip Component

```typescript
// routefluxmap/src/components/map/CountryLayer.tsx - Enhance CountryTooltip

import { getCountryMetricsUrl } from '../../lib/config';

interface CountryTooltipProps {
  countryCode: string;
  countryName: string;
  clientCount: number;
  relayCount?: number;  // NEW: from Allium data
  x: number;
  y: number;
}

export const CountryTooltip = forwardRef<HTMLDivElement, CountryTooltipProps>(
  ({ countryCode, countryName, clientCount, relayCount, x, y }, ref) => {
    const metricsUrl = getCountryMetricsUrl(countryCode);
    
    return (
      <div
        ref={ref}
        className="absolute z-20 bg-black/80 backdrop-blur-sm border border-tor-green/30 
                   rounded-lg px-3 py-2 text-sm pointer-events-auto"
        style={{ left: x + TOOLTIP_OFFSET, top: y + TOOLTIP_OFFSET }}
      >
        <div className="font-bold text-tor-green">{countryName}</div>
        <div className="text-gray-300">
          ~{formatCompact(clientCount)} Tor users
        </div>
        {relayCount !== undefined && (
          <div className="text-gray-400 text-xs">
            {relayCount} relays
          </div>
        )}
        <a
          href={metricsUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-tor-green hover:underline mt-1 block"
        >
          View country details →
        </a>
      </div>
    );
  }
);
```

---

### Phase 3: Add RouteFluxMap Link from Allium (Day 6-7)

#### 3.1 Update Allium Index Template

```jinja2
{# allium/templates/index.html - Add map link in navigation/feature section #}

<div class="feature-cards">
  <a href="https://routefluxmap.1aeo.com" 
     class="feature-card" 
     target="_blank"
     rel="noopener noreferrer">
    <span class="feature-icon">🌍</span>
    <span class="feature-title">Interactive Network Map</span>
    <span class="feature-desc">Real-time visualization of Tor relays worldwide</span>
    <span class="badge badge-live">Live</span>
  </a>
</div>
```

#### 3.2 Add Map Link to Country Pages

```jinja2
{# allium/templates/country.html - Add link to see country on map #}

{% block description %}
{{ country_name }} ({{ country_abbr }}) summary:
{{ detail_summary(...) }}

<div class="external-links">
  <a href="https://routefluxmap.1aeo.com/#CC={{ country_abbr }}" 
     class="btn btn-outline"
     target="_blank">
    🗺️ View on Interactive Map
  </a>
</div>
{% endblock %}
```

#### 3.3 Add Map Link to Relay Pages

```jinja2
{# allium/templates/relay-info.html - Add link near coordinates #}

{% if relay['latitude'] and relay['longitude'] %}
<dt>Location on Map</dt>
<dd>
  <a href="https://routefluxmap.1aeo.com/#ML={{ relay['longitude'] }},{{ relay['latitude'] }},8"
     target="_blank"
     rel="noopener noreferrer"
     class="btn btn-sm btn-outline">
    🗺️ View on Interactive Map
  </a>
</dd>
{% endif %}
```

---

### Phase 4: Unified Data Schema (Day 8-12)

Both projects consume Onionoo API data but transform it differently. This section defines a **unified data schema** that both systems can share, eliminating redundancy and ensuring consistency.

---

#### 4.1 Source of Truth Analysis

| Data Type | Best Source | Rationale |
|-----------|-------------|-----------|
| **Relay coordinates** | RouteFluxMap | Has MaxMind GeoIP integration with better accuracy |
| **Relay metadata** | Onionoo API (shared) | Both already use this |
| **Country classifications** | Allium | Has sophisticated rarity scoring system |
| **AROI/operator data** | Allium | Has AROI validation and operator analytics |
| **Client counts** | RouteFluxMap | Already fetches from Tor Metrics API |
| **Historical data** | RouteFluxMap | Has Tor Collector integration |

**Recommendation: Each system exports what it does best, other system consumes it.**

---

#### 4.1.1 Data Format Alignment Decision

**Key Decision: Allium adopts RouteFluxMap's data formats**

| Format | RouteFluxMap | Allium (Current) | Allium (Modified) |
|--------|--------------|------------------|-------------------|
| **Country codes** | UPPERCASE (`US`, `DE`) | lowercase (`us`, `de`) | **→ UPPERCASE** |
| **Fingerprints** | UPPERCASE (40-char hex) | UPPERCASE | No change |
| **AS numbers** | `AS12345` or `12345` | `AS12345` | No change |

**Rationale:**
- RouteFluxMap has **historical data** spanning months/years that would be expensive to migrate
- Allium generates **fresh data on each build** with no historical data to maintain
- Therefore, **Allium should adapt to RouteFluxMap's format**

This is a one-time migration for Allium with no backward compatibility concerns.

---

#### 4.1.2 Allium Country Code Migration (UPPERCASE)

**Files requiring modification:**

##### 1. `allium/lib/country_utils.py` - Convert all sets to UPPERCASE

```python
# BEFORE (lowercase)
CORE_REGIONS = {
    'north_america': {'us', 'ca', 'mx'},
    'europe': {'de', 'fr', 'gb', 'nl', ...},
    ...
}
EU_POLITICAL_REGION = {'at', 'be', 'bg', 'hr', 'cy', ...}
FRONTIER_COUNTRIES = {'mn', 'tn', 'uy', 'kz', ...}

# AFTER (UPPERCASE)
CORE_REGIONS = {
    'north_america': {'US', 'CA', 'MX'},
    'europe': {'DE', 'FR', 'GB', 'NL', ...},
    ...
}
EU_POLITICAL_REGION = {'AT', 'BE', 'BG', 'HR', 'CY', ...}
FRONTIER_COUNTRIES = {'MN', 'TN', 'UY', 'KZ', ...}
```

**Update all comparison functions to use `.upper()` instead of `.lower()`:**

```python
# BEFORE
def get_country_region(country_code):
    country_lower = country_code.lower()
    for region, countries in CORE_REGIONS.items():
        if country_lower in countries:
            return region
    return 'other'

# AFTER
def get_country_region(country_code):
    country_upper = country_code.upper()
    for region, countries in CORE_REGIONS.items():
        if country_upper in countries:
            return region
    return 'other'
```

##### 2. `allium/lib/relays.py` - Normalize country codes at ingestion

```python
# In the relay processing loop, normalize country to UPPERCASE early
def _process_relay(self, relay):
    # Normalize country code to UPPERCASE (RouteFluxMap compatibility)
    if relay.get('country'):
        relay['country'] = relay['country'].upper()
    
    # Rest of processing...
```

##### 3. `allium/lib/aroileaders.py` - Update comparisons

```python
# BEFORE
for country in unique_operator_countries:
    if country and country.lower() in valid_rare_countries:
        operator_rare_countries.add(country.upper())

# AFTER (no conversion needed - already uppercase)
for country in unique_operator_countries:
    if country and country in valid_rare_countries:
        operator_rare_countries.add(country)
```

##### 4. `allium/lib/intelligence_engine.py` - Update comparisons

```python
# BEFORE
if country_code.lower() in five_eyes_codes:
    five_eyes_weight += weight

# AFTER
if country_code.upper() in five_eyes_codes:
    five_eyes_weight += weight
```

##### 5. Templates - No changes needed

Templates already work with whatever case the data uses:
```jinja2
{# This works with both 'us' and 'US' #}
<a href="{{ page_ctx.path_prefix }}country/{{ relay['country']|escape }}/">
```

**Note:** URL paths will change from `/country/us/` to `/country/US/`. This is fine since Allium regenerates all pages on each build.

---

#### 4.1.3 Complete Country Code Migration Script

Create a one-time migration script to update all country code sets:

```python
#!/usr/bin/env python3
"""
migrate_country_codes.py - Convert Allium country codes to UPPERCASE

Run this script once to update all country code definitions.
"""

import re
import os

FILES_TO_UPDATE = [
    'allium/lib/country_utils.py',
    'allium/lib/aroileaders.py', 
    'allium/lib/intelligence_engine.py',
    'allium/lib/relays.py',
]

def convert_set_to_uppercase(match):
    """Convert a set literal from lowercase to uppercase."""
    content = match.group(0)
    # Find all 2-letter lowercase codes and uppercase them
    return re.sub(r"'([a-z]{2})'", lambda m: f"'{m.group(1).upper()}'", content)

def convert_lower_to_upper(content):
    """Convert .lower() calls to .upper() for country code comparisons."""
    # Pattern: variable.lower() in country context
    content = re.sub(
        r'(country[_\w]*)\s*\.lower\(\)',
        r'\1.upper()',
        content
    )
    return content

def process_file(filepath):
    """Process a single file."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    original = content
    
    # Convert set literals with country codes
    # Match patterns like {'us', 'ca', 'mx'} or {'de', 'fr', 'gb', ...}
    content = re.sub(
        r"\{(?:'[a-z]{2}'(?:,\s*)?)+\}",
        convert_set_to_uppercase,
        content
    )
    
    # Convert .lower() to .upper() for country variables
    content = convert_lower_to_upper(content)
    
    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"✓ Updated: {filepath}")
        return True
    else:
        print(f"  No changes: {filepath}")
        return False

def main():
    print("Converting Allium country codes to UPPERCASE...\n")
    
    updated = 0
    for filepath in FILES_TO_UPDATE:
        if os.path.exists(filepath):
            if process_file(filepath):
                updated += 1
        else:
            print(f"  Not found: {filepath}")
    
    print(f"\n✅ Updated {updated} files")
    print("\nNext steps:")
    print("1. Run tests: pytest tests/")
    print("2. Rebuild: python3 allium/allium.py --out ./www --progress")
    print("3. Verify URLs: ls www/country/")

if __name__ == '__main__':
    main()
```

---

#### 4.1.4 Validation After Migration

```bash
# Verify country directories are now UPPERCASE
ls www/country/
# Expected: AD/ AE/ AF/ ... US/ ... ZW/

# Verify country links work
grep -r "country/" www/*.html | head -5
# Expected: href="/country/US/" not href="/country/us/"

# Run existing tests (should pass after migration)
pytest tests/ -v
```

---

#### 4.2 Unified Relay Schema

Define a shared JSON schema that both systems can produce and consume:

```typescript
// shared/schemas/unified-relay.ts
// This schema can be implemented in both TypeScript and Python

interface UnifiedRelay {
  // === CORE IDENTITY (from Onionoo) ===
  fingerprint: string;        // 40-char hex, UPPERCASE (canonical)
  nickname: string;
  
  // === NETWORK INFO ===
  or_addresses: string[];     // Original format: ["1.2.3.4:9001", "[::1]:9001"]
  ip: string;                 // Primary IPv4 (extracted)
  ipv6?: string;              // Primary IPv6 if available
  port: number;
  
  // === GEOGRAPHIC (prefer RouteFluxMap's GeoIP) ===
  country: string;            // UPPERCASE 2-letter ISO code
  latitude: number;
  longitude: number;
  city?: string;
  region?: string;
  
  // === BANDWIDTH ===
  observed_bandwidth: number; // bytes/sec (raw from Onionoo)
  advertised_bandwidth?: number;
  consensus_weight?: number;
  consensus_weight_fraction?: number;
  
  // === FLAGS ===
  flags: string[];            // Full array: ["Running", "Guard", "Exit", "HSDir"]
  flags_compact: string;      // Compact: "MGE" (for visualization)
  is_exit: boolean;
  is_guard: boolean;
  is_hsdir: boolean;
  
  // === TIMESTAMPS ===
  first_seen: string;         // ISO format
  last_seen: string;
  last_restarted?: string;
  
  // === NETWORK IDENTITY ===
  as_number: string;          // "AS12345" format (with prefix)
  as_name?: string;
  
  // === OPERATOR (from Allium) ===
  contact?: string;
  contact_md5?: string;
  aroi_domain?: string;
  aroi_validated?: boolean;
  
  // === ALLIUM ENRICHMENTS ===
  country_rarity_tier?: 'legendary' | 'epic' | 'rare' | 'emerging' | 'common';
  country_rarity_score?: number;
  uptime_6m?: number;         // 6-month uptime percentage
  version?: string;
  version_status?: 'recommended' | 'experimental' | 'obsolete' | 'unrecommended';
  platform?: string;          // "linux", "freebsd", "windows", etc.
}
```

---

#### 4.3 Field Transformation Rules

**From Onionoo → Unified Format:**

```python
# allium/lib/schema_transforms.py

def onionoo_to_unified(relay: dict) -> dict:
    """Transform Onionoo relay to unified schema."""
    
    # Extract IP and port from or_addresses
    or_addr = relay.get('or_addresses', ['0.0.0.0:9001'])[0]
    ip, port = parse_or_address(or_addr)
    
    # Normalize country code
    country = (relay.get('country') or 'XX').upper()
    
    # Compact flags
    flags = relay.get('flags', [])
    flags_compact = ''.join([
        'G' if 'Guard' in flags else '',
        'E' if 'Exit' in flags else '',
        'H' if 'HSDir' in flags else '',
    ]) or 'M'
    
    # AS number normalization
    as_raw = relay.get('as') or ''
    as_number = as_raw if as_raw.startswith('AS') else f'AS{as_raw}' if as_raw else ''
    
    return {
        # Core identity
        'fingerprint': relay.get('fingerprint', '').upper(),
        'nickname': relay.get('nickname', 'Unnamed'),
        
        # Network
        'or_addresses': relay.get('or_addresses', []),
        'ip': ip,
        'port': int(port),
        
        # Geographic
        'country': country,
        'latitude': relay.get('latitude') or 0.0,
        'longitude': relay.get('longitude') or 0.0,
        'city': relay.get('city_name'),
        'region': relay.get('region_name'),
        
        # Bandwidth
        'observed_bandwidth': relay.get('observed_bandwidth', 0),
        'advertised_bandwidth': relay.get('advertised_bandwidth'),
        'consensus_weight': relay.get('consensus_weight'),
        'consensus_weight_fraction': relay.get('consensus_weight_fraction'),
        
        # Flags
        'flags': flags,
        'flags_compact': flags_compact,
        'is_exit': 'Exit' in flags,
        'is_guard': 'Guard' in flags,
        'is_hsdir': 'HSDir' in flags,
        
        # Timestamps
        'first_seen': relay.get('first_seen', ''),
        'last_seen': relay.get('last_seen', ''),
        'last_restarted': relay.get('last_restarted'),
        
        # Network identity
        'as_number': as_number,
        'as_name': relay.get('as_name'),
        
        # Operator
        'contact': relay.get('contact'),
        'contact_md5': relay.get('contact_md5'),
        'aroi_domain': relay.get('aroi_domain'),
        
        # Version info
        'version': relay.get('version'),
        'version_status': relay.get('version_status'),
        'platform': relay.get('platform'),
    }


def parse_or_address(addr: str) -> tuple:
    """Parse OR address like '1.2.3.4:9001' or '[::1]:9001'."""
    if addr.startswith('['):
        # IPv6: [::1]:9001
        bracket_end = addr.rfind(']')
        ip = addr[1:bracket_end]
        port = addr[bracket_end + 2:] if bracket_end + 2 < len(addr) else '9001'
    else:
        # IPv4: 1.2.3.4:9001
        parts = addr.rsplit(':', 1)
        ip = parts[0]
        port = parts[1] if len(parts) > 1 else '9001'
    return ip, port
```

**From Unified → RouteFluxMap AggregatedNode:**

```python
def unified_to_routefluxmap_node(relay: dict) -> dict:
    """Transform unified relay to RouteFluxMap's AggregatedNode format."""
    lat = relay['latitude']
    lng = relay['longitude']
    
    return {
        'lat': lat,
        'lng': lng,
        'x': (lng + 180) / 360,  # Normalized for WebGL
        'y': mercator_y(lat),     # Mercator projection
        'bandwidth': relay['observed_bandwidth'],
        'label': relay['nickname'],
        'relays': [{
            'nickname': relay['nickname'],
            'fingerprint': relay['fingerprint'],
            'bandwidth': relay['observed_bandwidth'],
            'flags': relay['flags_compact'],
            'ip': relay['ip'],
            'port': str(relay['port']),
            # Extended fields (Allium enrichments)
            'aroi_domain': relay.get('aroi_domain'),
            'rarity_tier': relay.get('country_rarity_tier'),
        }]
    }


def mercator_y(lat: float) -> float:
    """Convert latitude to Mercator Y coordinate [0,1]."""
    import math
    lat_rad = lat * (math.pi / 180)
    merc_n = math.log(math.tan(math.pi / 4 + lat_rad / 2))
    return 0.5 + merc_n / (2 * math.pi)
```

---

#### 4.4 Unified Country Schema

```typescript
// shared/schemas/unified-country.ts

interface UnifiedCountry {
  // === IDENTITY ===
  code: string;               // UPPERCASE 2-letter ISO code
  code3?: string;             // 3-letter ISO code
  name: string;
  
  // === RELAY STATS (from Allium) ===
  relay_count: number;
  guard_count: number;
  exit_count: number;
  middle_count: number;
  bandwidth_total: number;    // bytes/sec
  consensus_weight_fraction: number;
  
  // === CLIENT STATS (from RouteFluxMap/Tor Metrics) ===
  client_count?: number;      // Estimated daily users
  client_lower?: number;      // Confidence interval lower
  client_upper?: number;      // Confidence interval upper
  
  // === ALLIUM CLASSIFICATIONS ===
  rarity_tier: 'legendary' | 'epic' | 'rare' | 'emerging' | 'common';
  rarity_score: number;
  region: 'north_america' | 'europe' | 'asia_pacific' | 'eastern_europe' | 'other';
  is_eu: boolean;
  is_five_eyes: boolean;
  is_fourteen_eyes: boolean;
  
  // === GEOGRAPHIC (for visualization) ===
  centroid: {
    latitude: number;
    longitude: number;
  };
}
```

---

#### 4.5 Shared Data Export Files

Create a `/shared/` directory in Allium's output that RouteFluxMap can consume:

```
www/
├── relay/                    # Allium relay pages
├── country/                  # Allium country pages
├── shared/                   # NEW: Shared data for RouteFluxMap
│   ├── relays.json           # Unified relay list
│   ├── countries.json        # Unified country data
│   ├── classifications.json  # Country rarity tiers
│   ├── aroi-operators.json   # Validated AROI operators
│   └── metadata.json         # Generation timestamp, version
```

**Export Implementation:**

```python
# allium/lib/shared_data_exporter.py
"""
Export processed Allium data in shared format for RouteFluxMap consumption.
"""

import json
import os
from datetime import datetime
from typing import Dict, List

from .country_utils import (
    assign_rarity_tier,
    calculate_relay_count_factor,
    calculate_network_percentage_factor,
    calculate_geopolitical_factor,
    calculate_regional_factor,
    get_country_region,
    is_eu_political,
)


class SharedDataExporter:
    """Export Allium data in formats consumable by RouteFluxMap."""
    
    VERSION = '1.0.0'
    
    def __init__(self, relays_data: Dict, output_dir: str):
        self.relays_data = relays_data
        self.output_dir = os.path.join(output_dir, 'shared')
        os.makedirs(self.output_dir, exist_ok=True)
    
    def export_all(self) -> None:
        """Export all shared data files."""
        self.export_metadata()
        self.export_relays()
        self.export_countries()
        self.export_classifications()
        self.export_aroi_operators()
    
    def export_metadata(self) -> None:
        """Export generation metadata."""
        metadata = {
            'version': self.VERSION,
            'generatedAt': datetime.utcnow().isoformat() + 'Z',
            'source': 'allium',
            'relaysPublished': self.relays_data.get('relays_published', ''),
            'totalRelays': len(self.relays_data.get('relays', [])),
            'format': 'unified-schema-v1',
        }
        self._write_json('metadata.json', metadata)
    
    def export_relays(self) -> None:
        """Export unified relay list (lightweight for RouteFluxMap)."""
        relays = []
        
        for relay in self.relays_data.get('relays', []):
            # Skip relays without coordinates
            if not relay.get('latitude') or not relay.get('longitude'):
                continue
            
            unified = {
                'fp': relay.get('fingerprint', '').upper(),
                'nick': relay.get('nickname', ''),
                'lat': relay.get('latitude'),
                'lng': relay.get('longitude'),
                'bw': relay.get('observed_bandwidth', 0),
                'cc': (relay.get('country') or 'XX').upper(),
                'flags': self._compact_flags(relay.get('flags', [])),
                'as': relay.get('as', ''),
            }
            
            # Add optional enrichments
            if relay.get('aroi_domain') and relay['aroi_domain'] != 'none':
                unified['aroi'] = relay['aroi_domain']
            
            relays.append(unified)
        
        output = {
            'version': self.VERSION,
            'generatedAt': datetime.utcnow().isoformat() + 'Z',
            'count': len(relays),
            'relays': relays,
        }
        self._write_json('relays.json', output)
    
    def export_countries(self) -> None:
        """Export country statistics."""
        sorted_data = self.relays_data.get('sorted', {})
        country_data = sorted_data.get('country', {})
        total_relays = len(self.relays_data.get('relays', []))
        
        countries = {}
        for cc, data in country_data.items():
            relay_count = len(data.get('relays', []))
            
            countries[cc.upper()] = {
                'name': data.get('country_name', cc),
                'relays': relay_count,
                'guards': data.get('guard_count', 0),
                'exits': data.get('exit_count', 0),
                'bandwidth': data.get('bandwidth', 0),
                'cwFraction': data.get('consensus_weight_fraction', 0),
            }
        
        output = {
            'version': self.VERSION,
            'generatedAt': datetime.utcnow().isoformat() + 'Z',
            'totalRelays': total_relays,
            'countries': countries,
        }
        self._write_json('countries.json', output)
    
    def export_classifications(self) -> None:
        """Export country rarity classifications."""
        sorted_data = self.relays_data.get('sorted', {})
        country_data = sorted_data.get('country', {})
        total_relays = len(self.relays_data.get('relays', []))
        
        classifications = {}
        for cc, data in country_data.items():
            relay_count = len(data.get('relays', []))
            
            # Calculate rarity score using Allium's algorithm
            rarity_score = (
                (calculate_relay_count_factor(relay_count) * 4) +
                (calculate_network_percentage_factor(relay_count, total_relays) * 3) +
                (calculate_geopolitical_factor(cc) * 2) +
                (calculate_regional_factor(cc) * 1)
            )
            
            classifications[cc.upper()] = {
                'tier': assign_rarity_tier(rarity_score),
                'score': rarity_score,
                'region': get_country_region(cc),
                'isEU': is_eu_political(cc),
                'relays': relay_count,
                'networkPct': (relay_count / total_relays * 100) if total_relays > 0 else 0,
            }
        
        # Include tier color definitions
        tier_colors = {
            'legendary': {'hex': '#FFD700', 'rgb': [255, 215, 0]},
            'epic': {'hex': '#8A2BE2', 'rgb': [138, 43, 226]},
            'rare': {'hex': '#1E90FF', 'rgb': [30, 144, 255]},
            'emerging': {'hex': '#32CD32', 'rgb': [50, 205, 50]},
            'common': {'hex': '#808080', 'rgb': [128, 128, 128]},
        }
        
        output = {
            'version': self.VERSION,
            'generatedAt': datetime.utcnow().isoformat() + 'Z',
            'totalRelays': total_relays,
            'tierColors': tier_colors,
            'countries': classifications,
        }
        self._write_json('classifications.json', output)
    
    def export_aroi_operators(self) -> None:
        """Export validated AROI operator data."""
        sorted_data = self.relays_data.get('sorted', {})
        contact_data = sorted_data.get('contact', {})
        
        operators = []
        for contact_hash, data in contact_data.items():
            aroi_domain = data.get('aroi_domain')
            if not aroi_domain or aroi_domain == 'none':
                continue
            
            # Check if validated
            is_validated = data.get('is_validated_aroi', False)
            
            operators.append({
                'domain': aroi_domain,
                'contactHash': contact_hash,
                'validated': is_validated,
                'relayCount': len(data.get('relays', [])),
                'bandwidth': data.get('bandwidth', 0),
                'countries': list(set(data.get('countries', []))),
            })
        
        # Sort by relay count descending
        operators.sort(key=lambda x: x['relayCount'], reverse=True)
        
        output = {
            'version': self.VERSION,
            'generatedAt': datetime.utcnow().isoformat() + 'Z',
            'totalOperators': len(operators),
            'operators': operators,
        }
        self._write_json('aroi-operators.json', output)
    
    def _compact_flags(self, flags: List[str]) -> str:
        """Compact flags to single string."""
        result = ''
        if 'Guard' in flags:
            result += 'G'
        if 'Exit' in flags:
            result += 'E'
        if 'HSDir' in flags:
            result += 'H'
        return result or 'M'
    
    def _write_json(self, filename: str, data: Dict) -> None:
        """Write JSON file with consistent formatting."""
        path = os.path.join(self.output_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, separators=(',', ':'))  # Compact JSON
```

---

#### 4.6 RouteFluxMap Consumption

Update RouteFluxMap to optionally consume Allium's enriched data:

```typescript
// routefluxmap/src/lib/utils/allium-data.ts

interface AlliumClassifications {
  version: string;
  totalRelays: number;
  tierColors: Record<string, { hex: string; rgb: number[] }>;
  countries: Record<string, {
    tier: 'legendary' | 'epic' | 'rare' | 'emerging' | 'common';
    score: number;
    region: string;
    isEU: boolean;
    relays: number;
    networkPct: number;
  }>;
}

let classificationsCache: AlliumClassifications | null = null;

/**
 * Fetch country classifications from Allium's shared data export.
 * Falls back gracefully if Allium data unavailable.
 */
export async function fetchAlliumClassifications(
  alliumUrl: string
): Promise<AlliumClassifications | null> {
  if (classificationsCache) return classificationsCache;
  
  try {
    const response = await fetch(`${alliumUrl}/shared/classifications.json`, {
      signal: AbortSignal.timeout(5000)
    });
    
    if (!response.ok) return null;
    
    classificationsCache = await response.json();
    return classificationsCache;
  } catch (err) {
    console.warn('Failed to fetch Allium classifications:', err);
    return null;
  }
}

/**
 * Get country color based on Allium's rarity classification.
 */
export function getCountryColorByRarity(
  countryCode: string,
  classifications: AlliumClassifications | null
): [number, number, number, number] {
  const DEFAULT_COLOR: [number, number, number, number] = [128, 128, 128, 200];
  
  if (!classifications) return DEFAULT_COLOR;
  
  const country = classifications.countries[countryCode.toUpperCase()];
  if (!country) return DEFAULT_COLOR;
  
  const tierColor = classifications.tierColors[country.tier];
  if (!tierColor) return DEFAULT_COLOR;
  
  return [...tierColor.rgb, 255] as [number, number, number, number];
}
```

---

#### 4.7 Country Code Normalization

After the migration (Section 4.1.2), both systems use **UPPERCASE** country codes. RouteFluxMap already uses uppercase, and Allium will be modified to match.

**Canonical Format:** `UPPERCASE 2-letter ISO 3166-1 alpha-2`

Examples: `US`, `DE`, `GB`, `JP`

##### Shared Normalization Utility (Optional)

If either system receives data from external sources, use this normalizer:

```python
# allium/lib/country_utils.py - ADD this function

# Country code aliases for edge cases
COUNTRY_CODE_ALIASES = {
    'UK': 'GB',  # United Kingdom (common but non-standard)
    'EN': 'GB',  # England (non-standard)
    'EL': 'GR',  # Greece (EU uses EL, ISO uses GR)
}

def normalize_country_code(code: str) -> str:
    """
    Normalize country code to UPPERCASE 2-letter ISO format.
    
    This is the canonical format used by both Allium and RouteFluxMap.
    
    Args:
        code: Country code in any case, possibly with aliases
        
    Returns:
        UPPERCASE 2-letter ISO code, or 'XX' if invalid
    """
    if not code:
        return 'XX'
    
    # Clean and uppercase
    clean = ''.join(c for c in code if c.isalpha()).upper()[:2]
    
    if len(clean) != 2:
        return 'XX'
    
    # Apply aliases
    return COUNTRY_CODE_ALIASES.get(clean, clean)
```

```typescript
// routefluxmap/src/lib/utils/country-codes.ts
// RouteFluxMap already uses UPPERCASE, but add alias handling for consistency

const COUNTRY_CODE_ALIASES: Record<string, string> = {
  'UK': 'GB',
  'EN': 'GB', 
  'EL': 'GR',
};

export function normalizeCountryCode(code: string): string {
  if (!code) return 'XX';
  
  const clean = code.replace(/[^a-zA-Z]/g, '').toUpperCase().slice(0, 2);
  
  if (clean.length !== 2) return 'XX';
  
  return COUNTRY_CODE_ALIASES[clean] || clean;
}
```

##### After Migration: No Conversion Needed

Once Allium is migrated to UPPERCASE (Section 4.1.2):

```python
# BEFORE (required conversion)
routefluxmap_code = allium_country.upper()  # 'us' → 'US'

# AFTER (no conversion needed)
routefluxmap_code = allium_country  # Already 'US'
```

This eliminates all `.lower()` / `.upper()` conversions at integration boundaries.

---

#### 4.8 Integration in Allium Build Process

Add shared data export to Allium's build:

```python
# allium/allium.py - add after page generation completes

from lib.shared_data_exporter import SharedDataExporter

# ... existing code ...

# Export shared data for RouteFluxMap integration
if args.progress:
    progress_logger.log("Exporting shared data for visualization integration...")

exporter = SharedDataExporter(RELAY_SET.json, args.output_dir)
exporter.export_all()

if args.progress:
    progress_logger.log("Shared data export complete")
```

---

#### 4.9 Data Flow Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           UNIFIED DATA FLOW                                  │
└─────────────────────────────────────────────────────────────────────────────┘

                         ┌─────────────────────┐
                         │    ONIONOO API      │
                         │  (Primary Source)   │
                         │  country: 'us'      │  ← lowercase from API
                         └──────────┬──────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
          ┌─────────────────┐ ┌──────────┐ ┌──────────────────┐
          │     ALLIUM      │ │ MaxMind  │ │   Tor Metrics    │
          │   (Analytics)   │ │  GeoIP   │ │  (Client Data)   │
          │                 │ │          │ │                  │
          │ CONVERTS TO:    │ │          │ │                  │
          │ country: 'US'   │ │          │ │                  │
          └────────┬────────┘ └────┬─────┘ └────────┬─────────┘
                   │               │                │
                   │       ┌───────┴────────┐       │
                   │       │  ROUTEFLUXMAP  │       │
                   │       │ (Visualization)│◄──────┘
                   │       │                │
                   │       │ ALREADY USES:  │
                   │       │ country: 'US'  │
                   │       └───────┬────────┘
                   │               │
                   ▼               ▼
          ┌─────────────────────────────────────────┐
          │      SHARED DATA (UPPERCASE CODES)      │
          │                                         │
          │  /shared/relays.json      ← Allium      │
          │  /shared/countries.json   ← Allium      │
          │  /shared/classifications.json ← Allium  │
          │  /shared/aroi-operators.json  ← Allium  │
          │                                         │
          │  All country codes: 'US', 'DE', 'GB'    │
          │  No conversion needed at boundaries!    │
          └─────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         WHY ALLIUM ADAPTS                                    │
└─────────────────────────────────────────────────────────────────────────────┘

  RouteFluxMap                              Allium
  ────────────                              ──────
  ✗ Has historical data                    ✓ No historical data
    (months of JSON files)                   (regenerates on each build)
    
  ✗ Hard to migrate                        ✓ Easy to migrate
    (would break existing URLs,              (one-time code change,
     client caches, bookmarks)               no backward compat needed)
     
  ✓ Keep format as-is                      ✓ Adapt to match RouteFluxMap
    (UPPERCASE country codes)                (convert to UPPERCASE)

RESULT: Zero conversion overhead at integration boundaries
```

**Benefits of Allium Adapting:**

✅ **No data migration** - RouteFluxMap's historical archives untouched
✅ **No URL changes** - RouteFluxMap URLs stay the same
✅ **Single format** - Both systems use UPPERCASE, no runtime conversion
✅ **Simpler code** - Remove all `.lower()` / `.upper()` at boundaries
✅ **Future-proof** - New integrations also use UPPERCASE standard

---

### Phase 5: Shared Rarity/Classification Data (Day 13-14)

Allium has rich country classification data. Export it for RouteFluxMap visualization:

#### 5.1 Export Country Classifications

```python
# allium/lib/routefluxmap_exporter.py - ADD this function

def export_country_classifications(
    country_data: Dict,
    total_relays: int,
    output_path: str
) -> None:
    """
    Export Allium's country rarity classifications for RouteFluxMap.
    This enables RouteFluxMap to color countries by rarity tier.
    """
    from .country_utils import (
        calculate_relay_count_factor,
        calculate_network_percentage_factor,
        calculate_geopolitical_factor,
        calculate_regional_factor,
        assign_rarity_tier,
        get_country_region,
        is_eu_political,
    )
    
    classifications = {}
    
    for cc, data in country_data.items():
        relay_count = len(data.get('relays', []))
        
        # Calculate multi-factor rarity score
        rarity_score = (
            (calculate_relay_count_factor(relay_count) * 4) +
            (calculate_network_percentage_factor(relay_count, total_relays) * 3) +
            (calculate_geopolitical_factor(cc) * 2) +
            (calculate_regional_factor(cc) * 1)
        )
        
        classifications[cc.upper()] = {
            'relay_count': relay_count,
            'rarity_score': rarity_score,
            'rarity_tier': assign_rarity_tier(rarity_score),
            'region': get_country_region(cc),
            'is_eu': is_eu_political(cc),
            'network_percentage': (relay_count / total_relays * 100) if total_relays > 0 else 0,
        }
    
    output = {
        'version': '1.0.0',
        'generatedAt': datetime.utcnow().isoformat() + 'Z',
        'totalRelays': total_relays,
        'countries': classifications,
        'tierDefinitions': {
            'legendary': {'minScore': 15, 'color': '#FFD700'},  # Gold
            'epic': {'minScore': 10, 'color': '#8A2BE2'},       # Purple
            'rare': {'minScore': 6, 'color': '#1E90FF'},        # Blue
            'emerging': {'minScore': 3, 'color': '#32CD32'},    # Green
            'common': {'minScore': 0, 'color': '#808080'},      # Gray
        }
    }
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
```

#### 5.2 RouteFluxMap Rarity Visualization

```typescript
// routefluxmap/src/lib/utils/rarity.ts (NEW FILE)

export interface CountryClassification {
  relay_count: number;
  rarity_score: number;
  rarity_tier: 'legendary' | 'epic' | 'rare' | 'emerging' | 'common';
  region: string;
  is_eu: boolean;
  network_percentage: number;
}

export interface ClassificationData {
  countries: Record<string, CountryClassification>;
  tierDefinitions: Record<string, { minScore: number; color: string }>;
}

// Tier colors (RGBA 0-255)
export const TIER_COLORS: Record<string, [number, number, number, number]> = {
  legendary: [255, 215, 0, 255],    // Gold
  epic: [138, 43, 226, 255],        // Purple  
  rare: [30, 144, 255, 255],        // Blue
  emerging: [50, 205, 50, 255],     // Green
  common: [128, 128, 128, 200],     // Gray
};

export function getCountryColor(
  countryCode: string,
  classifications: ClassificationData | null
): [number, number, number, number] {
  if (!classifications?.countries) {
    return TIER_COLORS.common;
  }
  
  const data = classifications.countries[countryCode.toUpperCase()];
  if (!data) {
    return TIER_COLORS.common;
  }
  
  return TIER_COLORS[data.rarity_tier] || TIER_COLORS.common;
}
```

---

### URL Hash Parameters for Deep Linking

RouteFluxMap supports URL hash parameters for state persistence. Use these for deep linking from Allium:

| Parameter | Format | Example | Description |
|-----------|--------|---------|-------------|
| `date` | `YYYY-MM-DD` | `#date=2024-12-15` | View historical data |
| `ML` | `lng,lat,zoom` | `#ML=-40.5,30.2,5` | Map location |
| `CC` | 2-letter code | `#CC=US` | Highlight country |

**Deep Link Examples:**

```
# View Germany on the map
https://routefluxmap.1aeo.com/#CC=DE

# Jump to a specific relay location
https://routefluxmap.1aeo.com/#ML=8.68,50.11,8

# View historical data for December 1st
https://routefluxmap.1aeo.com/#date=2024-12-01

# Combined: View US relays on January 1st
https://routefluxmap.1aeo.com/#date=2024-01-01&CC=US
```

---

### Phase 6: Testing & Validation (Day 15-17)

#### 6.1 Cross-Link Testing Checklist

```bash
# Test relay links from RouteFluxMap to Allium
curl -I "https://allium.1aeo.com/relay/7EAAC4D0E1AC54E888C49F2F0C6BF5B2DDFB4C4A/"
# Expected: HTTP 200

# Test country links
curl -I "https://allium.1aeo.com/country/us/"
# Expected: HTTP 200

# Test AS links
curl -I "https://allium.1aeo.com/as/AS24940/"
# Expected: HTTP 200

# Test deep links from Allium to RouteFluxMap
curl -I "https://routefluxmap.1aeo.com/#CC=DE"
# Expected: HTTP 200 (SPA handles hash routing)
```

#### 6.2 Data Consistency Validation

```python
# scripts/validate_integration.py
"""
Validate data consistency between Allium and RouteFluxMap.
Run after both systems have refreshed their data.
"""

import json
import requests
from typing import Set

def get_allium_fingerprints(allium_url: str) -> Set[str]:
    """Get all relay fingerprints from Allium's JSON output."""
    resp = requests.get(f"{allium_url}/misc/relays.json")
    data = resp.json()
    return {r['fingerprint'].upper() for r in data.get('relays', [])}

def get_routefluxmap_fingerprints(rfm_data_url: str) -> Set[str]:
    """Get all relay fingerprints from RouteFluxMap's data."""
    resp = requests.get(f"{rfm_data_url}/index.json")
    index = resp.json()
    latest_date = index['dates'][-1]
    
    resp = requests.get(f"{rfm_data_url}/relays-{latest_date}.json")
    data = resp.json()
    
    fingerprints = set()
    for node in data.get('nodes', []):
        for relay in node.get('relays', []):
            fingerprints.add(relay['fingerprint'].upper())
    return fingerprints

def validate_consistency():
    allium_fps = get_allium_fingerprints("https://allium.1aeo.com")
    rfm_fps = get_routefluxmap_fingerprints("https://data.routefluxmap.1aeo.com")
    
    # Calculate overlap
    common = allium_fps & rfm_fps
    only_allium = allium_fps - rfm_fps
    only_rfm = rfm_fps - allium_fps
    
    print(f"Allium relays: {len(allium_fps)}")
    print(f"RouteFluxMap relays: {len(rfm_fps)}")
    print(f"Common: {len(common)} ({len(common)/len(allium_fps)*100:.1f}%)")
    print(f"Only in Allium: {len(only_allium)}")
    print(f"Only in RouteFluxMap: {len(only_rfm)}")
    
    # Acceptable threshold: 95% overlap (data refresh timing differences)
    overlap_pct = len(common) / max(len(allium_fps), len(rfm_fps)) * 100
    assert overlap_pct > 95, f"Data overlap too low: {overlap_pct:.1f}%"
    print(f"✅ Validation passed: {overlap_pct:.1f}% overlap")

if __name__ == '__main__':
    validate_consistency()
```

#### 6.3 End-to-End User Flow Testing

| Test Case | Steps | Expected Result |
|-----------|-------|-----------------|
| **Relay Discovery** | 1. Open RouteFluxMap<br>2. Click relay marker<br>3. Click "View on Metrics" | Opens Allium relay page |
| **Country Exploration** | 1. Open Allium country page<br>2. Click "View on Map" | RouteFluxMap centers on country |
| **Deep Link Sharing** | 1. Copy RouteFluxMap URL with hash<br>2. Open in new browser | Same view loads |
| **Mobile Navigation** | 1. Open RouteFluxMap on mobile<br>2. Tap relay<br>3. Follow link | Allium loads correctly |

---

### Deployment Configuration

#### RouteFluxMap Environment Variables

```bash
# routefluxmap/deploy/config.env

# Point all metrics links to Allium
PUBLIC_METRICS_URL=https://allium.1aeo.com

# RouteFluxMap's own URL (for sharing)
PUBLIC_SITE_URL=https://routefluxmap.1aeo.com

# Data storage (unchanged)
PUBLIC_DATA_URL=https://data.routefluxmap.1aeo.com
```

#### Allium Configuration (Optional)

```bash
# If Allium needs to know RouteFluxMap's URL for templates
ROUTEFLUXMAP_URL=https://routefluxmap.1aeo.com
```

---

### Strategy C: Monorepo Merge (Full Integration) 🔄

**Timeline: 4-6 weeks**

Merge RouteFluxMap into Allium repository as a visualization subproject.

#### Proposed Directory Structure

```
allium/
├── allium.py                    # Main Python generator
├── lib/                         # Python libraries
├── templates/                   # Jinja2 templates
├── static/                      # Static assets (icons, CSS)
├── visualization/               # NEW: RouteFluxMap merge
│   ├── src/
│   │   ├── components/
│   │   │   ├── map/            # TorMap, CountryLayer, etc.
│   │   │   └── ui/             # Controls, sliders
│   │   ├── lib/                # TypeScript utilities
│   │   └── pages/              # Astro pages
│   ├── scripts/
│   │   └── fetch-all-data.ts   # Data pipeline
│   ├── public/
│   │   └── data/               # JSON data files
│   ├── package.json
│   └── astro.config.mjs
├── www/                         # Output directory
│   ├── index.html              # Allium pages
│   ├── country/
│   ├── relay/
│   └── map/                    # NEW: RouteFluxMap output
│       └── index.html
└── docs/
```

#### Unified Build Script

```bash
#!/bin/bash
# scripts/build-all.sh

# Build Allium (Python)
python3 allium.py --out ./www --progress

# Build RouteFluxMap (Node.js)
cd visualization
npm run build
cp -r dist/* ../www/map/

echo "✅ Full build complete: www/"
```

#### Unified Data Pipeline

```python
# allium/lib/geo_data_exporter.py (NEW)
"""
Export Allium's relay data in RouteFluxMap format for visualization.
"""

import json
from .relays import Relays

def export_relay_json_for_visualization(relays: Relays, output_path: str):
    """
    Convert Allium's relay data to RouteFluxMap's JSON format.
    
    This allows RouteFluxMap to consume the same data that Allium uses,
    ensuring consistency between visualization and analytics.
    """
    nodes = []
    
    for relay in relays.json['relays']:
        if relay.get('latitude') and relay.get('longitude'):
            nodes.append({
                'lat': relay['latitude'],
                'lng': relay['longitude'],
                'bandwidth': relay.get('observed_bandwidth', 0),
                'label': relay.get('nickname', 'Unknown'),
                'relays': [{
                    'nickname': relay.get('nickname', 'Unknown'),
                    'fingerprint': relay.get('fingerprint', ''),
                    'bandwidth': relay.get('observed_bandwidth', 0),
                    'flags': _encode_flags(relay.get('flags', [])),
                    'ip': relay.get('or_addresses', [''])[0].split(':')[0],
                    'port': relay.get('or_addresses', [''])[0].split(':')[-1]
                }]
            })
    
    output = {
        'published': relays.json.get('relays_published', ''),
        'nodes': nodes,
        'bandwidth': sum(n['bandwidth'] for n in nodes),
        'relayCount': len(nodes)
    }
    
    with open(output_path, 'w') as f:
        json.dump(output, f)

def _encode_flags(flags: list) -> str:
    """Encode relay flags as compact string."""
    flag_map = {'Guard': 'G', 'Exit': 'E', 'HSDir': 'H'}
    return ''.join(flag_map.get(f, 'M') for f in flags if f in flag_map) or 'M'
```

**Pros:**
- Single repository, unified versioning
- Shared data ensures consistency
- Single deployment
- Unified CI/CD pipeline

**Cons:**
- More complex build process (Python + Node.js)
- Larger repository
- Need to maintain two tech stacks

---

### Strategy D: MicroFrontend Architecture (Advanced) 🏗️

**Timeline: 6-8 weeks**

Deploy RouteFluxMap as a web component that Allium can embed anywhere.

#### RouteFluxMap as Web Component

```typescript
// routefluxmap/src/components/TorMapWebComponent.tsx
import { createRoot } from 'react-dom/client';
import TorMap from './map/TorMap';

class TorMapElement extends HTMLElement {
  connectedCallback() {
    const root = createRoot(this);
    const metricsUrl = this.getAttribute('metrics-url') || '';
    root.render(<TorMap metricsUrl={metricsUrl} />);
  }
}

customElements.define('tor-map', TorMapElement);
```

#### Usage in Allium Templates

```html
<!-- allium/templates/index.html -->
<script type="module" src="https://routefluxmap.1aeo.com/tor-map.js"></script>

<tor-map metrics-url="https://allium.1aeo.com"></tor-map>
```

**Pros:**
- Maximum flexibility
- Can embed visualization anywhere
- Framework-agnostic integration
- Independent versioning

**Cons:**
- Most complex to implement
- Requires web component bundling expertise
- Larger initial JS bundle

---

## Recommended Integration Path

### Phase 1: Quick Win (Week 1)
1. **Implement Strategy A** (iframe embed)
2. Add navigation link from Allium to RouteFluxMap
3. Validate user experience

### Phase 2: Deep Integration (Weeks 2-3)
1. **Implement Strategy B** (API bridge)
2. Configure RouteFluxMap `metricsUrl` to point to Allium
3. Add clean URL routing in Allium
4. Test bidirectional navigation

### Phase 3: Full Merge (Optional, Weeks 4-6)
1. **Evaluate Strategy C** based on Phase 2 learnings
2. If beneficial: merge repositories
3. Implement unified build and data pipeline

---

---

## Strategy B: Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        USER WORKFLOW                                         │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────────┐
                              │   User visits   │
                              │   Allium site   │
                              └────────┬────────┘
                                       │
                          ┌────────────┴────────────┐
                          ▼                         ▼
              ┌───────────────────┐    ┌───────────────────────┐
              │  Browse relays,   │    │  Click "View on Map"  │
              │  countries, AROI  │    │  (deep link to RFM)   │
              └─────────┬─────────┘    └───────────┬───────────┘
                        │                          │
                        ▼                          ▼
              ┌───────────────────┐    ┌───────────────────────┐
              │  View detailed    │    │  RouteFluxMap opens   │
              │  relay analytics  │    │  at specific location │
              └───────────────────┘    └───────────┬───────────┘
                                                   │
                                       ┌───────────┴───────────┐
                                       ▼                       ▼
                           ┌─────────────────┐    ┌─────────────────┐
                           │ Explore map,    │    │ Click relay     │
                           │ see animations  │    │ "View Metrics"  │
                           └─────────────────┘    └────────┬────────┘
                                                           │
                                                           ▼
                                               ┌───────────────────────┐
                                               │  Returns to Allium    │
                                               │  relay detail page    │
                                               └───────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                        TECHNICAL INTEGRATION                                 │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────┐         ┌─────────────────────────────────────┐
  │       ALLIUM            │         │         ROUTEFLUXMAP                │
  │  (Python Static Gen)    │         │      (Astro/React/WebGL)            │
  ├─────────────────────────┤         ├─────────────────────────────────────┤
  │                         │         │                                     │
  │  /relay/{fingerprint}/  │◄────────│  RelayPopup "View Metrics" link     │
  │  /country/{cc}/         │◄────────│  CountryTooltip "View details" link │
  │  /as/{asn}/             │◄────────│  (future) AS detail links           │
  │  /contact/{hash}/       │         │                                     │
  │                         │         │                                     │
  │  Templates include:     │─────────►  /#CC={cc} (country deep link)      │
  │  "View on Map" links    │─────────►  /#ML={lng},{lat},{zoom} (location) │
  │                         │─────────►  /#date={YYYY-MM-DD} (historical)   │
  │                         │         │                                     │
  └────────────┬────────────┘         └──────────────────┬──────────────────┘
               │                                         │
               │                                         │
               ▼                                         ▼
  ┌─────────────────────────┐         ┌─────────────────────────────────────┐
  │     ONIONOO API         │         │           ONIONOO API               │
  │  (Tor Project)          │         │  + Tor Collector (historical)       │
  │                         │         │  + MaxMind GeoIP                    │
  │  - /details             │         │                                     │
  │  - /uptime              │         │  Same source, different processing  │
  │  - /bandwidth           │         │                                     │
  └─────────────────────────┘         └─────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                        CONFIGURATION                                         │
└─────────────────────────────────────────────────────────────────────────────┘

  RouteFluxMap config.env:              Allium templates:
  ┌─────────────────────────────┐       ┌─────────────────────────────────┐
  │ PUBLIC_METRICS_URL=         │       │ ROUTEFLUXMAP_URL=               │
  │   https://allium.1aeo.com   │       │   https://routefluxmap.1aeo.com │
  └─────────────────────────────┘       └─────────────────────────────────┘
         │                                        │
         │  Enables:                              │  Enables:
         │  - getRelayMetricsUrl()                │  - "View on Map" buttons
         │  - getCountryMetricsUrl()              │  - Deep link generation
         │  - getASMetricsUrl()                   │
         ▼                                        ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                    SEAMLESS BIDIRECTIONAL NAVIGATION                    │
  └─────────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start: Strategy B Implementation

### Minimal Changes Required

**Step 1: RouteFluxMap (1 line change)**

```bash
# Edit: routefluxmap/deploy/config.env
PUBLIC_METRICS_URL=https://allium.1aeo.com
```

That's it! All "View on Metrics" links now point to Allium.

**Step 2: Allium (Optional, for bidirectional links)**

```jinja2
{# Add to allium/templates/relay-info.html near coordinates section #}
{% if relay['latitude'] and relay['longitude'] %}
<a href="https://routefluxmap.1aeo.com/#ML={{ relay['longitude'] }},{{ relay['latitude'] }},8" 
   target="_blank">🗺️ View on Map</a>
{% endif %}
```

**Step 3: Deploy both projects**

```bash
# RouteFluxMap
cd routefluxmap && npm run deploy:pages

# Allium
cd allium && python3 allium.py --out ./www && rsync -av ./www/ server:/var/www/allium/
```

### That's the entire integration!

The minimal implementation requires changing **1 environment variable** in RouteFluxMap. Everything else is optional enhancement.

---

## Data Format Compatibility

### Allium's Country Data (from country_utils.py)

```python
# Country classification tiers
RARITY_TIERS = {
    'legendary': 15+,   # 🏆 Ultra-rare
    'epic': 10-14,      # ⭐ Very rare
    'rare': 6-9,        # 🎖️ Rare
    'emerging': 3-5,    # 📍 Growing
    'common': 0-2       # Standard
}
```

### RouteFluxMap's Country Data (from types.ts)

```typescript
interface CountryHistogram {
  [countryCode: string]: number | {
    count: number;
    lower: number;  // Confidence interval
    upper: number;
  };
}
```

### Mapping Strategy

Both projects can share country classification data:

```python
# allium/lib/geo_data_exporter.py
def export_country_classifications(country_data, output_path):
    """
    Export Allium's rarity classifications for RouteFluxMap visualization.
    """
    classifications = {}
    
    for cc, data in country_data.items():
        rarity_score = calculate_rarity_score(cc, data)
        classifications[cc] = {
            'relay_count': len(data.get('relays', [])),
            'rarity_tier': assign_rarity_tier(rarity_score),
            'rarity_score': rarity_score,
            'is_frontier': is_frontier_country(cc),
            'region': get_country_region(cc)
        }
    
    with open(output_path, 'w') as f:
        json.dump(classifications, f)
```

RouteFluxMap can then color countries by rarity tier:

```typescript
// routefluxmap enhancement
const TIER_COLORS = {
  legendary: [255, 215, 0],   // Gold
  epic: [138, 43, 226],       // Purple
  rare: [30, 144, 255],       // Blue
  emerging: [50, 205, 50],    // Green
  common: [128, 128, 128]     // Gray
};
```

---

## Synergy Opportunities

### 1. Unified AROI Visualization

RouteFluxMap could visualize AROI leaderboards:

```
┌────────────────────────────────────────────────────────────┐
│  🏆 AROI Champions on Map                                  │
│                                                            │
│  [World map with operator relay locations highlighted]     │
│                                                            │
│  Legend:                                                   │
│  🥇 #1 Bandwidth Champion: torworld.org (847 Gbps)        │
│  🥈 #2 Geographic Champion: globalnet (47 countries)      │
│  🥉 #3 Exit Champion: exitpro.org (312 exits)             │
└────────────────────────────────────────────────────────────┘
```

### 2. Historical AROI Trends

RouteFluxMap's date slider + Allium's AROI data = time-travel through leaderboards:

```typescript
// Fetch AROI data for selected date
const aroiData = await fetch(`/data/aroi-${selectedDate}.json`);
```

### 3. Intelligence Engine Overlays

Allium's 6-layer intelligence engine could power map overlays:

- **Concentration risk**: Heat map of HHI scores by ASN
- **Geographic diversity**: Show underrepresented regions
- **Version distribution**: Color by Tor version

---

## Implementation Checklist

### Immediate Actions (This Sprint)

- [ ] Add link to RouteFluxMap from Allium index page
- [ ] Configure RouteFluxMap `metricsUrl` to point to Allium
- [ ] Test cross-navigation workflow

### Short-term (Next Sprint)

- [ ] Implement iframe embed option in Allium
- [ ] Add clean URL routing for `/country/{CC}` and `/relay/{fingerprint}`
- [ ] Create data export script for country classifications

### Medium-term (Month 2)

- [ ] Evaluate monorepo merge benefits
- [ ] Implement unified data pipeline
- [ ] Add AROI visualization layer to RouteFluxMap

### Long-term (Quarter 2)

- [ ] Web component packaging
- [ ] Real-time data synchronization
- [ ] ML-powered anomaly detection visualization

---

## Conclusion

**RouteFluxMap is not just compatible with Allium's Feature #1 - it exceeds the requirements.** Instead of building a geographic visualization from scratch (4-6 weeks as planned), Allium can leverage RouteFluxMap immediately, saving significant development time.

The recommended approach is:

1. **Start with Strategy B** (API Bridge) for quick value delivery
2. **Evaluate monorepo merge** after validating the integration
3. **Enhance RouteFluxMap** with Allium-specific features (AROI visualization, rarity tiers)

This integration transforms both projects:
- **Allium** gains world-class visualization without building it
- **RouteFluxMap** gains deep analytics and operator insights

**Combined, they become a complete Tor network intelligence platform.**

---

---

## Summary: Strategy B Action Items

### Immediate (Day 1-2)

- [ ] **Allium**: Run country code migration script (Section 4.1.3)
- [ ] **Allium**: Update `country_utils.py` - convert sets to UPPERCASE
- [ ] **Allium**: Update comparison functions `.lower()` → `.upper()`
- [ ] **Allium**: Test build and verify `/country/US/` URLs work
- [ ] **RouteFluxMap**: Set `PUBLIC_METRICS_URL=https://allium.1aeo.com` in `config.env`
- [ ] **RouteFluxMap**: Deploy with new configuration
- [ ] Verify cross-linking: Click relay → "View on Metrics" → Allium page loads

### Short-term (Week 1)

- [ ] **RouteFluxMap**: Add `getCountryMetricsUrl()` helper
- [ ] **RouteFluxMap**: Update `CountryTooltip` with country detail links
- [ ] **Allium**: Add "View on Map" links to templates (relay, country pages)
- [ ] Verify bidirectional navigation works

### Medium-term (Week 2-3)

- [ ] **Allium**: Create `SharedDataExporter` class
- [ ] **Allium**: Export `/shared/classifications.json` with rarity tiers
- [ ] **RouteFluxMap**: Optionally fetch Allium classifications for coloring
- [ ] Add validation script to check data consistency

### Optional Enhancements

- [ ] Export AROI leaderboard data for RouteFluxMap visualization
- [ ] Add relay search from Allium that opens RouteFluxMap at location
- [ ] Create shared data pipeline for synchronized updates

---

## Files to Modify

### RouteFluxMap (Minimal Changes - Has Historical Data)

| File | Change | Priority |
|------|--------|----------|
| `deploy/config.env` | Set `PUBLIC_METRICS_URL` | **Required** |
| `src/lib/config.ts` | Add `getCountryMetricsUrl()`, `getASMetricsUrl()` | Recommended |
| `src/components/map/CountryLayer.tsx` | Add country detail links | Recommended |
| `src/lib/utils/allium-data.ts` | **NEW**: Fetch Allium shared data | Optional |

**Note:** RouteFluxMap requires minimal changes since it already uses the correct data formats (UPPERCASE country codes). Allium adapts to match.

### Allium (Data Schema Alignment - No Historical Data)

#### Country Code Migration (One-Time)

| File | Change | Priority |
|------|--------|----------|
| `lib/country_utils.py` | Convert all country code sets to UPPERCASE | **Required** |
| `lib/country_utils.py` | Change `.lower()` → `.upper()` in functions | **Required** |
| `lib/aroileaders.py` | Change `.lower()` → `.upper()` comparisons | **Required** |
| `lib/intelligence_engine.py` | Change `.lower()` → `.upper()` comparisons | **Required** |
| `lib/relays.py` | Normalize country to UPPERCASE at ingestion | **Required** |

#### Feature Integration

| File | Change | Priority |
|------|--------|----------|
| `templates/relay-info.html` | Add "View on Map" link | Recommended |
| `templates/country.html` | Add "View on Map" link | Recommended |
| `templates/index.html` | Add RouteFluxMap feature card | Recommended |
| `lib/shared_data_exporter.py` | **NEW**: Export shared JSON files | Recommended |
| `allium.py` | Call `SharedDataExporter.export_all()` | Recommended |

### Shared Output Files (Generated by Allium)

| File | Contents | Consumer |
|------|----------|----------|
| `www/shared/metadata.json` | Generation timestamp, version | RouteFluxMap |
| `www/shared/relays.json` | Lightweight relay list with Allium enrichments | RouteFluxMap |
| `www/shared/countries.json` | Country statistics | RouteFluxMap |
| `www/shared/classifications.json` | Rarity tiers with colors | RouteFluxMap |
| `www/shared/aroi-operators.json` | Validated AROI operators | RouteFluxMap |

---

## Key URLs Reference

| Resource | URL |
|----------|-----|
| **Allium** | https://allium.1aeo.com |
| **RouteFluxMap** | https://routefluxmap.1aeo.com |
| **RouteFluxMap GitHub** | https://github.com/1aeo/routefluxmap |
| **Allium GitHub** | https://github.com/1aeo/allium |

### Deep Link Formats

```
# RouteFluxMap deep links (from Allium)
https://routefluxmap.1aeo.com/#CC=US                    # Highlight country
https://routefluxmap.1aeo.com/#ML=-122.4,37.8,10        # Jump to location
https://routefluxmap.1aeo.com/#date=2024-12-01          # Historical view
https://routefluxmap.1aeo.com/#date=2024-12-01&CC=DE    # Combined

# Allium deep links (from RouteFluxMap)
https://allium.1aeo.com/relay/{FINGERPRINT}/            # Relay details
https://allium.1aeo.com/country/{cc}/                   # Country summary
https://allium.1aeo.com/as/AS{number}/                  # AS network view
```

---

**Document Status**: Complete  
**Last Updated**: December 2024  
**Next Review**: After Phase 1 implementation
