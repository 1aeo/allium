# RouteFluxMap Integration Plan for Allium

**Status**: 🚀 Phase 1 & 3 Code Complete, Phase 2 Pending  
**Last Updated**: December 24, 2024  
**Document Type**: Technical Integration Strategy

> **Quick Status:**
> - ✅ **Phase 1**: Cross-linking config complete (code in repo, pending Allium redeploy)
> - 🔲 **Phase 2**: RouteFluxMap → Allium country links (not started)
> - ✅ **Phase 3**: Allium → RouteFluxMap links complete (pending redeploy)
> - 🔲 **Phase 4+**: Optional data schema enhancements  

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

## Integration Strategy: API Bridge with Deep Links ⭐

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

#### 1.1 RouteFluxMap Configuration — ✅ FULLY IMPLEMENTED

RouteFluxMap has `metricsUrl` configured and pointing to Allium:

```typescript
// routefluxmap/src/lib/config.ts
export const config = {
  metricsUrl: import.meta.env.PUBLIC_METRICS_URL || '',  // Set to metrics.1aeo.com
  // ...
};

// getRelayMetricsUrl() helper exists and works
export function getRelayMetricsUrl(fingerprint: string): string { ... }
```

**Implementation Status:**
- ✅ `config.ts` has `metricsUrl` env var support
- ✅ `getRelayMetricsUrl()` helper function exists
- ✅ `RelayPopup.tsx` uses `getRelayMetricsUrl()` for "View on Metrics" links
- ✅ `PUBLIC_METRICS_URL=https://metrics.1aeo.com` configured in production
- ✅ Relay deep linking via `#relay=FINGERPRINT` URL hash (commit `208b43c2`)

**Live Instances:**
- RouteFluxMap: https://routefluxmap.1aeo.com ✅
- Allium: https://metrics.1aeo.com ✅

#### 1.2 URL Schema Alignment — ✅ CODE COMPLETE, ⏳ PENDING DEPLOYMENT

**Current URL Patterns (Live Site):**

| Entity | RouteFluxMap Links To | Live Allium | Code in Repo |
|--------|----------------------|-------------|--------------|
| Relay | `/relay/{FINGERPRINT}` | `/relay/{FINGERPRINT}/` ✅ | ✅ Compatible |
| Country | `/country/{CC}` (uppercase) | `/country/{cc}/` (lowercase) | `/country/{CC}/` ✅ |
| AS | `/as/AS{number}` | `/as/AS{number}/` ✅ | ✅ Compatible |

**Status:**
- ✅ Allium code normalizes country codes to UPPERCASE (`relay["country"] = relay["country"].upper()`)
- ✅ `country_utils.py` sets converted to UPPERCASE (commit `eb2a4178`)
- ⏳ Live site still serves lowercase URLs (pending redeployment)

**Verified Live (current):**
```
https://metrics.1aeo.com/country/us/  → 200 OK (lowercase - current)
https://metrics.1aeo.com/country/US/  → 404 (pending deployment)
```

#### 1.3 Allium URL Compatibility — ✅ FULLY IMPLEMENTED

**Commit `eb2a4178`:** "feat: add RouteFluxMap integration with country code normalization"

Changes implemented:
- ✅ Country codes normalized to UPPERCASE throughout codebase
- ✅ Templates use `{{ relay['country']|escape }}` (now outputs uppercase)
- ✅ Flag image paths use `|lower` filter for backwards compatibility

---

### Phase 2: Add Country Deep Links from RouteFluxMap (Day 3-5) — 🔲 NOT YET IMPLEMENTED

RouteFluxMap's `CountryLayer.tsx` shows country data on hover. Add click-through to Allium country pages.

**Current State:**
- ✅ `CountryLayer.tsx` exists with hover tooltips
- ✅ `CountryTooltip` component shows country name and client count
- 🔲 **No link to Allium country pages yet**
- 🔲 **`getCountryMetricsUrl()` helper doesn't exist yet**
- 🔲 **`getASMetricsUrl()` helper doesn't exist yet**

#### 2.1 Create Country Link Helper — 🔲 TODO

```typescript
// routefluxmap/src/lib/config.ts - ADD these functions

/**
 * Build URL to country detail page on metrics site
 * @param countryCode - ISO 3166-1 alpha-2 code (e.g., 'US', 'DE')
 */
export function getCountryMetricsUrl(countryCode: string): string {
  const cleanCode = countryCode.toUpperCase().replace(/[^A-Z]/g, '');
  
  if (!/^[A-Z]{2}$/.test(cleanCode)) {
    console.warn(`Invalid country code: ${countryCode}`);
    return config.metricsUrl;
  }
  
  // After Allium migration: use UPPERCASE
  return `${config.metricsUrl}/country/${cleanCode}/`;
}

/**
 * Build URL to AS detail page on metrics site
 * @param asNumber - AS number (e.g., 'AS12345' or '12345')
 */
export function getASMetricsUrl(asNumber: string): string {
  const match = asNumber.match(/(\d+)/);
  if (!match) {
    console.warn(`Invalid AS number: ${asNumber}`);
    return config.metricsUrl;
  }
  
  return `${config.metricsUrl}/as/AS${match[1]}/`;
}
```

**Implementation Notes:**
- Add both functions to `src/lib/config.ts` alongside existing `getRelayMetricsUrl()`
- Country codes use UPPERCASE after Allium migration (Section 4.1.2)
- AS numbers already compatible (both use `AS{number}` format)

#### 2.2 Update Country Tooltip Component — 🔲 TODO

**Current `CountryTooltip` (in `CountryLayer.tsx`):**
- Shows country name and estimated client count
- No link to external metrics

**Enhanced version with Allium link:**

```typescript
// routefluxmap/src/components/map/CountryLayer.tsx - Enhance CountryTooltip

import { getCountryMetricsUrl } from '../../lib/config';

interface CountryTooltipProps {
  countryCode: string;
  countryName: string;
  clientCount: number;
  hasBounds: boolean;
  lower: number;
  upper: number;
  x: number;
  y: number;
}

export const CountryTooltip = forwardRef<HTMLDivElement, CountryTooltipProps>(
  ({ countryCode, countryName, clientCount, hasBounds, lower, upper, x, y }, ref) => {
    const metricsUrl = getCountryMetricsUrl(countryCode);
    
    return (
      <div
        ref={ref}
        className="absolute z-20 bg-black/90 text-white text-sm px-3 py-2 rounded-lg 
                   shadow-lg border border-purple-500/30 pointer-events-auto"
        style={{ left: x + TOOLTIP_OFFSET, top: y + TOOLTIP_OFFSET }}
      >
        <div className="font-medium text-purple-400">{countryName}</div>
        <div className="text-gray-400">
          ~{formatCompact(clientCount)} Tor clients
        </div>
        {hasBounds && (
          <div className="text-gray-500 text-xs">
            Est. range: {formatRange(lower, upper)}
          </div>
        )}
        {/* NEW: Link to Allium country page */}
        <a
          href={metricsUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-tor-green hover:underline mt-1.5 pt-1.5 
                     border-t border-white/10 block"
        >
          View relay details →
        </a>
      </div>
    );
  }
);
```

**Key Changes:**
1. Import `getCountryMetricsUrl` from config
2. Add `pointer-events-auto` to make tooltip clickable
3. Add link with external icon to Allium country page
4. Style link to match existing UI (tor-green color)
```

---

### Phase 3: Add RouteFluxMap Link from Allium (Day 6-7) — ✅ FULLY IMPLEMENTED

**Commit `eb2a4178`:** "feat: add RouteFluxMap integration with country code normalization"
**Commit `40134430`:** "Add 1AEO cross-site navigation and footer branding"

**Implementation Status:**
- ✅ Cross-site navigation bar with RouteFluxMap link in `skeleton.html`
- ✅ Footer with 1AEO branding and links
- ✅ Country pages have "View on Interactive Map" link (`#CC=XX`)
- ✅ Relay pages have "View on Interactive Map" link (`#relay=FINGERPRINT`)

#### 3.1 Update Allium Index Template — ✅ IMPLEMENTED

```html
<!-- 1AEO Cross-Site Navigation (in skeleton.html) -->
<a href="https://www.1aeo.com">Home</a>
<a href="https://metrics.1aeo.com" class="active">Metrics</a>
<a href="https://aroivalidator.1aeo.com">AROI Validator</a>
<a href="https://routefluxmap.1aeo.com">RouteFluxMap</a>
```

#### 3.2 Add Map Link to Country Pages — ✅ IMPLEMENTED

```jinja2
{# allium/templates/country.html #}
<li>
  <a href="https://routefluxmap.1aeo.com/#CC={{ country_abbr }}" 
     target="_blank" rel="noopener" 
     title="View {{ country_name }} on RouteFluxMap interactive visualization">
    🗺️ View on Interactive Map
  </a>
</li>
```

#### 3.3 Add Map Link to Relay Pages — ✅ IMPLEMENTED

```jinja2
{# allium/templates/relay-info.html #}
<dt>Interactive Map</dt>
<dd>
  <a href="https://routefluxmap.1aeo.com/#relay={{ relay['fingerprint']|escape }}" 
     target="_blank" rel="noopener" 
     title="View this relay on RouteFluxMap interactive visualization">
    🗺️ View on Interactive Map
  </a>
</dd>
```

**Note:** Uses `#relay=FINGERPRINT` format which RouteFluxMap now supports (commit `208b43c2`).

#### 3.4 Add Map Link to AS/Network Pages — 🔲 NOT IMPLEMENTED (Optional)

AS pages don't have RouteFluxMap links yet. This is optional since RouteFluxMap doesn't support AS filtering via URL hash.

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

#### 4.1.2 Allium Country Code Migration (UPPERCASE) — ✅ IMPLEMENTED

**Status:** Completed in commit `eb2a4178`

**Changes Made:**

##### 1. `allium/lib/country_utils.py` — ✅ Done
- All sets converted to UPPERCASE (`{'US', 'CA', 'MX'}` etc.)
- NOTE header added documenting UPPERCASE convention

##### 2. `allium/lib/relays.py` — ✅ Done
- Country codes normalized at ingestion: `relay["country"] = relay["country"].upper()`

##### 3. `allium/lib/aroileaders.py` — ✅ Done
- Updated comparisons to use uppercase

##### 4. `allium/lib/intelligence_engine.py` — ✅ Done
- Updated comparisons to use uppercase

##### 5. Templates — ✅ Done
- Flag image paths use `|lower` filter for backwards compatibility
- Country URLs now use uppercase codes

**Verification (after redeployment):**

```bash
# Should return 200 after Allium redeployment
curl -s "https://metrics.1aeo.com/country/US/" -o /dev/null -w "%{http_code}"

# Current state (before redeployment)
# /country/us/ → 200 OK (lowercase still works)
# /country/US/ → 404 (uppercase not deployed yet)
```

<details>
<summary>Migration Details (Historical Reference)</summary>

```python
# Example change in country_utils.py:
# BEFORE (lowercase)
CORE_REGIONS = {
    'north_america': {'us', 'ca', 'mx'},
    ...
}

# AFTER (UPPERCASE) - now implemented
CORE_REGIONS = {
    'north_america': {'US', 'CA', 'MX'},
    ...
}
```

```python
# Example change in relays.py:
def _process_relay(self, relay):
    if relay.get('country'):
        relay['country'] = relay['country'].upper()  # Added
```

</details>

---

#### 4.1.3 Validation After Migration — ✅ READY FOR DEPLOYMENT

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

---

## Alternative Approaches (Future Consideration)

### Monorepo Merge
If deeper integration is needed later, RouteFluxMap could be merged into the Allium repository as a `visualization/` subdirectory with a unified build script. This would enable single deployment and shared data pipelines but adds complexity (Python + Node.js build).

### Web Component
RouteFluxMap could be packaged as a `<tor-map>` web component for embedding anywhere. This provides maximum flexibility but requires additional bundling work.

**Recommendation:** Start with the API Bridge approach (Phases 1-3). Evaluate these alternatives after validating the integration works well.

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

## Summary: Action Items by Phase

### Phase 1: Cross-Linking Configuration — ✅ COMPLETE (pending deployment)

| Task | Owner | Status | Notes |
|------|-------|--------|-------|
| Set `PUBLIC_METRICS_URL=https://metrics.1aeo.com` | RouteFluxMap | ✅ Done | Configured in production |
| Deploy RouteFluxMap with new config | RouteFluxMap | ✅ Done | Live at routefluxmap.1aeo.com |
| Add relay deep linking `#relay=FP` | RouteFluxMap | ✅ Done | Commit `208b43c2` |
| Update `country_utils.py` sets to UPPERCASE | Allium | ✅ Done | Commit `eb2a4178` |
| Update `.lower()` → `.upper()` in comparisons | Allium | ✅ Done | Commit `eb2a4178` |
| Normalize country codes at ingestion | Allium | ✅ Done | `relay["country"].upper()` |
| **Redeploy Allium with UPPERCASE URLs** | Allium | ⏳ PENDING | Live site still has lowercase |

### Phase 2: Country Deep Links from RouteFluxMap — 🔲 NOT STARTED

| Task | Owner | Status | Notes |
|------|-------|--------|-------|
| Add `getCountryMetricsUrl()` to `config.ts` | RouteFluxMap | 🔲 TODO | Section 2.1 |
| Add `getASMetricsUrl()` to `config.ts` | RouteFluxMap | 🔲 TODO | Section 2.1 |
| Update `CountryTooltip` with metrics link | RouteFluxMap | 🔲 TODO | Section 2.2 |
| Test country links work | Both | 🔲 TODO | Hover country → click link |

### Phase 3: RouteFluxMap Links from Allium — ✅ COMPLETE (pending deployment)

| Task | Owner | Status | Notes |
|------|-------|--------|-------|
| Add RouteFluxMap nav link | Allium | ✅ Done | In `skeleton.html` header |
| Add "View on Map" to country.html | Allium | ✅ Done | `#CC={{ country_abbr }}` |
| Add "View on Map" to relay-info.html | Allium | ✅ Done | `#relay={{ fingerprint }}` |
| **Redeploy Allium to go live** | Allium | ⏳ PENDING | Code in repo, not live |

### Phase 4+: Data Schema & Optional Enhancements

| Task | Owner | Priority | Notes |
|------|-------|----------|-------|
| Create `SharedDataExporter` class | Allium | Optional | Section 4.5 |
| Export `classifications.json` | Allium | Optional | Rarity tiers |
| Fetch Allium classifications | RouteFluxMap | Optional | For country coloring |
| Export AROI operator data | Allium | Optional | For visualization |

---

## Current Implementation Summary

### What's Done ✅

**RouteFluxMap (commit `208b43c2`):**
- `metricsUrl` configured to `https://metrics.1aeo.com`
- `getRelayMetricsUrl()` helper for relay links
- `RelayPopup` "View on Metrics" links work
- Relay deep linking via `#relay=FINGERPRINT` URL hash

**Allium (commits `eb2a4178`, `40134430`):**
- Country codes normalized to UPPERCASE in code
- Cross-site navigation with RouteFluxMap link
- Country pages: "View on Interactive Map" → `#CC=XX`
- Relay pages: "View on Interactive Map" → `#relay=FINGERPRINT`

### What's Pending ⏳

1. **Allium Redeployment** - Code changes in repo, live site still has lowercase country URLs
2. **Phase 2 (RouteFluxMap → Allium country links)** - Not started

### What's Remaining 🔲

- `getCountryMetricsUrl()` helper in RouteFluxMap
- `getASMetricsUrl()` helper in RouteFluxMap
- CountryTooltip enhancement with Allium links
- Optional: Shared data exports for rarity visualization

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
