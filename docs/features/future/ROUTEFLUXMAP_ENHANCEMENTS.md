# RouteFluxMap Integration Enhancements

**Status**: 🔲 Future Enhancement  
**Priority**: Low  
**Prerequisites**: Core integration complete (Phases 1-3 live)

---

## Overview

The core RouteFluxMap ↔ Allium integration is **complete and live**:
- ✅ Bidirectional cross-linking between sites
- ✅ Relay deep links (`#relay=FINGERPRINT`)
- ✅ Country deep links (`#CC=XX`)
- ✅ UPPERCASE country code alignment

This document covers **optional future enhancements** to deepen the integration.

---

## 1. Shared Data Exports

Export Allium's analytics data for RouteFluxMap to consume.

### 1.1 Country Rarity Classifications

Allium has sophisticated country rarity scoring. Export for RouteFluxMap visualization:

```
www/shared/classifications.json
```

```json
{
  "version": "1.0.0",
  "generated": "2024-12-24T00:00:00Z",
  "tiers": {
    "legendary": { "countries": ["KP", "TM", "ER"], "color": "#FFD700" },
    "rare": { "countries": ["AF", "TD", "CF"], "color": "#9333EA" },
    "uncommon": { "countries": ["MN", "UY", "KZ"], "color": "#3B82F6" },
    "common": { "countries": ["US", "DE", "FR"], "color": "#22C55E" }
  }
}
```

**RouteFluxMap usage:** Color country choropleth by rarity tier instead of client count.

### 1.2 AROI Operator Data

Export validated AROI operators for map visualization:

```
www/shared/aroi-operators.json
```

```json
{
  "operators": [
    {
      "contact_hash": "abc123",
      "nickname": "TorOperator",
      "relay_count": 5,
      "total_bandwidth": 500000000,
      "countries": ["US", "DE", "NL"],
      "aroi_score": 95.5
    }
  ]
}
```

### 1.3 Implementation

**Allium:** Create `lib/shared_data_exporter.py`:

```python
class SharedDataExporter:
    def __init__(self, relays_data, output_dir):
        self.relays_data = relays_data
        self.shared_dir = Path(output_dir) / 'shared'
    
    def export_all(self):
        self.shared_dir.mkdir(exist_ok=True)
        self.export_classifications()
        self.export_aroi_operators()
```

**RouteFluxMap:** Optionally fetch and apply:

```typescript
const classifications = await fetch(`${metricsUrl}/shared/classifications.json`);
// Use tier colors for country choropleth
```

---

## 2. AROI Visualization Layer

Display AROI leaderboard champions on the map.

### Concept

```
┌────────────────────────────────────────────────────────────┐
│  🏆 AROI Champions on Map                                  │
│                                                            │
│  [World map with operator relay locations highlighted]     │
│                                                            │
│  Legend: 🥇 Top 10  🥈 Top 50  🥉 Top 100                   │
└────────────────────────────────────────────────────────────┘
```

### Features
- Highlight relays by AROI-validated operators
- Toggle layer on/off
- Click operator cluster → show leaderboard rank

---

## 3. AS Detail Links (Low Priority)

Add `getASMetricsUrl()` helper for future AS tooltips:

```typescript
export function getASMetricsUrl(asNumber: string): string {
  const match = asNumber.match(/(\d+)/);
  if (!match) return `${config.metricsUrl}/as/`;
  return `${config.metricsUrl}/as/AS${match[1]}/`;
}
```

**Note:** RouteFluxMap doesn't currently show AS data in tooltips, so this is low priority.

---

## Action Items

| Task | Owner | Priority |
|------|-------|----------|
| Create `SharedDataExporter` class | Allium | Medium |
| Export `classifications.json` | Allium | Medium |
| Export `aroi-operators.json` | Allium | Low |
| Consume classifications in RouteFluxMap | RouteFluxMap | Low |
| AROI visualization layer | RouteFluxMap | Low |
| `getASMetricsUrl()` helper | RouteFluxMap | Low |

---

## Related

- Live integration: https://routefluxmap.1aeo.com ↔ https://metrics.1aeo.com
- Allium repo: https://github.com/1aeo/allium
- RouteFluxMap repo: https://github.com/1aeo/routefluxmap
