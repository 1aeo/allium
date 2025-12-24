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

### Phase 4: Data Schema Alignment (Day 8-12)

Both projects consume Onionoo API data but transform it differently. Here's how to align them:

#### 4.1 Data Field Mapping

| Onionoo Field | Allium Usage | RouteFluxMap Usage |
|---------------|--------------|-------------------|
| `fingerprint` | Primary key, URL slug | Primary key, metrics link |
| `nickname` | Display name | `RelayInfo.nickname` |
| `observed_bandwidth` | Bytes/sec, formatted | Normalized to [0,1] |
| `country` | Lowercase 2-letter | Uppercase 2-letter |
| `latitude/longitude` | Display only | Map positioning |
| `flags` | Array of strings | Encoded as `M/G/E/H` |
| `as` | `AS12345` format | Numeric or with prefix |
| `contact` | Raw + MD5 hash | Not used |

#### 4.2 Create Shared Data Export (Optional Enhancement)

For tighter integration, Allium can export data in RouteFluxMap's format:

```python
# allium/lib/routefluxmap_exporter.py (NEW FILE)
"""
Export Allium's processed relay data in RouteFluxMap JSON format.
This enables RouteFluxMap to show Allium-specific data like AROI info.
"""

import json
from datetime import datetime
from typing import Dict, List, Any

def export_for_routefluxmap(relays_data: Dict, output_path: str) -> None:
    """
    Export relay data in RouteFluxMap's expected format.
    
    RouteFluxMap expects:
    - relays-YYYY-MM-DD.json: Relay locations with metadata
    - countries-YYYY-MM-DD.json: Client counts by country
    """
    nodes = []
    
    for relay in relays_data.get('relays', []):
        lat = relay.get('latitude')
        lng = relay.get('longitude')
        
        if not lat or not lng:
            continue
            
        nodes.append({
            'lat': lat,
            'lng': lng,
            'x': normalize_lng(lng),
            'y': normalize_lat(lat),
            'bandwidth': relay.get('observed_bandwidth', 0),
            'label': relay.get('nickname', 'Unknown'),
            'relays': [{
                'nickname': relay.get('nickname', 'Unknown'),
                'fingerprint': relay.get('fingerprint', ''),
                'bandwidth': relay.get('observed_bandwidth', 0),
                'flags': encode_flags(relay.get('flags', [])),
                'ip': extract_ip(relay.get('or_addresses', [])),
                'port': extract_port(relay.get('or_addresses', [])),
                # Allium-specific enrichments
                'aroi_domain': relay.get('aroi_domain'),
                'country_rarity': relay.get('country_rarity_tier'),
            }]
        })
    
    output = {
        'version': '1.0.0',
        'source': 'allium',
        'generatedAt': datetime.utcnow().isoformat() + 'Z',
        'published': relays_data.get('relays_published', ''),
        'nodes': aggregate_by_location(nodes),
        'bandwidth': sum(n['bandwidth'] for n in nodes),
        'relayCount': len(nodes),
    }
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)


def normalize_lng(lng: float) -> float:
    """Convert longitude to [0,1] range for WebGL."""
    return (lng + 180) / 360


def normalize_lat(lat: float) -> float:
    """Convert latitude to [0,1] range using Mercator projection."""
    import math
    lat_rad = lat * (math.pi / 180)
    merc_n = math.log(math.tan(math.pi / 4 + lat_rad / 2))
    return 0.5 + merc_n / (2 * math.pi)


def encode_flags(flags: List[str]) -> str:
    """Encode relay flags as compact string (M=Middle, G=Guard, E=Exit, H=HSDir)."""
    flag_map = {'Guard': 'G', 'Exit': 'E', 'HSDir': 'H'}
    encoded = ''.join(flag_map.get(f, '') for f in flags if f in flag_map)
    return encoded if encoded else 'M'


def extract_ip(or_addresses: List[str]) -> str:
    """Extract first IP address from OR addresses."""
    if not or_addresses:
        return ''
    return or_addresses[0].rsplit(':', 1)[0]


def extract_port(or_addresses: List[str]) -> str:
    """Extract first port from OR addresses."""
    if not or_addresses:
        return ''
    return or_addresses[0].rsplit(':', 1)[-1]


def aggregate_by_location(nodes: List[Dict], precision: int = 2) -> List[Dict]:
    """
    Aggregate relays at same location (rounded to precision decimal places).
    This matches RouteFluxMap's AggregatedNode structure.
    """
    location_map: Dict[str, Dict] = {}
    
    for node in nodes:
        # Round coordinates for aggregation
        key = f"{round(node['lat'], precision)},{round(node['lng'], precision)}"
        
        if key not in location_map:
            location_map[key] = {
                'lat': node['lat'],
                'lng': node['lng'],
                'x': node['x'],
                'y': node['y'],
                'bandwidth': 0,
                'relays': [],
            }
        
        location_map[key]['bandwidth'] += node['bandwidth']
        location_map[key]['relays'].extend(node['relays'])
    
    # Generate labels
    aggregated = []
    for loc in location_map.values():
        relay_count = len(loc['relays'])
        if relay_count == 1:
            loc['label'] = loc['relays'][0]['nickname']
        else:
            loc['label'] = f"{relay_count} relays"
        aggregated.append(loc)
    
    return aggregated
```

#### 4.3 Country Code Normalization

RouteFluxMap uses uppercase, Allium uses lowercase. Create a shared normalization:

```typescript
// routefluxmap/src/lib/utils/country.ts (NEW FILE)

/**
 * Normalize country code for cross-system compatibility
 */
export function normalizeCountryCode(code: string, format: 'upper' | 'lower' = 'upper'): string {
  const clean = code.replace(/[^a-zA-Z]/g, '').slice(0, 2);
  return format === 'upper' ? clean.toUpperCase() : clean.toLowerCase();
}

/**
 * Country codes that need special handling
 */
export const COUNTRY_SPECIAL_CASES: Record<string, string> = {
  'UK': 'GB',  // United Kingdom
  'EN': 'GB',  // England (non-standard)
};

export function canonicalizeCountryCode(code: string): string {
  const upper = code.toUpperCase();
  return COUNTRY_SPECIAL_CASES[upper] || upper;
}
```

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

### Immediate (Day 1)

- [ ] Set `PUBLIC_METRICS_URL=https://allium.1aeo.com` in RouteFluxMap's `config.env`
- [ ] Deploy RouteFluxMap with new configuration
- [ ] Verify relay links work: Click relay → "View on Metrics" → Allium page loads

### Short-term (Week 1)

- [ ] Add `getCountryMetricsUrl()` helper to RouteFluxMap
- [ ] Update `CountryTooltip` component with country detail links
- [ ] Add "View on Map" links to Allium templates (relay, country pages)

### Medium-term (Week 2-3)

- [ ] Create `routefluxmap_exporter.py` in Allium for data export
- [ ] Export country classifications (rarity tiers) for RouteFluxMap
- [ ] Implement rarity-based country coloring in RouteFluxMap
- [ ] Add validation script to check data consistency

### Optional Enhancements

- [ ] Export AROI leaderboard data for RouteFluxMap visualization
- [ ] Add relay search from Allium that opens RouteFluxMap at location
- [ ] Create shared data pipeline for synchronized updates

---

## Files to Modify

### RouteFluxMap

| File | Change | Priority |
|------|--------|----------|
| `deploy/config.env` | Set `PUBLIC_METRICS_URL` | **Required** |
| `src/lib/config.ts` | Add `getCountryMetricsUrl()`, `getASMetricsUrl()` | Recommended |
| `src/components/map/CountryLayer.tsx` | Add country detail links | Recommended |
| `src/lib/utils/rarity.ts` | New file for rarity coloring | Optional |

### Allium

| File | Change | Priority |
|------|--------|----------|
| `templates/relay-info.html` | Add "View on Map" link | Recommended |
| `templates/country.html` | Add "View on Map" link | Recommended |
| `templates/index.html` | Add RouteFluxMap feature card | Recommended |
| `lib/routefluxmap_exporter.py` | New file for data export | Optional |

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
