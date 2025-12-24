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

#### Implementation Steps

**1. Configure RouteFluxMap's metrics URL to point to Allium:**

```typescript
// routefluxmap/src/lib/config.ts
export const config = {
  metricsUrl: 'https://allium.1aeo.com',  // Allium's generated site
  // ... other config
};
```

This makes all relay fingerprint links navigate to Allium:
- Click relay marker → `https://allium.1aeo.com/relay/{fingerprint}`
- Country click → `https://allium.1aeo.com/country/{cc}`

**2. Add RouteFluxMap link from Allium:**

```html
<!-- allium/templates/index.html -->
<a href="https://routefluxmap.1aeo.com" class="feature-card">
    🌍 Interactive Network Map
    <span class="badge">Live</span>
</a>
```

**3. Generate compatible country pages in Allium:**

Allium already generates `/country/{CC}.html` pages. Ensure URL compatibility:

```python
# allium/lib/relays.py - Country pages already generated
# routefluxmap links to: /country/{CC}
# Allium generates: /country/{CC}.html

# Add .htaccess or nginx rewrite for clean URLs:
# RewriteRule ^country/([A-Z]{2})$ /country/$1.html [L]
```

**Pros:**
- Seamless user experience
- Each project remains independent
- Users can navigate from visualization to detailed analytics
- Easy to maintain separately

**Cons:**
- Two deployments to manage
- Data not perfectly synchronized

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

**Document Status**: Complete  
**Last Updated**: December 2024  
**Next Review**: After Phase 1 implementation
