# Architecture Overview

**Audience**: Contributors  
**Scope**: System design and data flow

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         allium.py                                │
│                      (Entry Point)                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      coordinator.py                              │
│              (Orchestrates data fetching)                        │
│                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │ Details  │ │  Uptime  │ │Bandwidth │ │   AROI   │ │Collect.│ │
│  │  Worker  │ │  Worker  │ │  Worker  │ │  Worker  │ │ Worker │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        relays.py                                 │
│                   (Core Processing)                              │
│                                                                  │
│  • Data normalization          • Contact aggregation             │
│  • Sorting/grouping            • Statistics calculation          │
│  • Uptime integration          • Intelligence engine             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Page Generation                               │
│              (Multiprocessing Workers)                           │
│                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │ Worker 1 │ │ Worker 2 │ │ Worker 3 │ │ Worker 4 │            │
│  │ (relays) │ │(contacts)│ │(countries│ │  (misc)  │            │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      templates/                                  │
│                   (Jinja2 Templates)                             │
│                                                                  │
│  skeleton.html → Base layout, navigation, CSS                    │
│  macros.html   → Reusable components                             │
│  *.html        → Page-specific templates                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        www/                                      │
│                  (Generated Output)                              │
│                                                                  │
│  ~21,700 HTML pages + search-index.json + static assets          │
└─────────────────────────────────────────────────────────────────┘
```

## Key Modules

### `allium.py`
Entry point. Parses CLI arguments, initializes coordinator, triggers page generation.

### `lib/coordinator.py`
Orchestrates parallel API fetching using ThreadPoolExecutor. Manages:
- 5 concurrent API workers
- Progress logging
- Error handling and graceful degradation

### `lib/relays.py`
Core data processing class. Responsibilities:
- Data normalization from Onionoo format
- Sorting by multiple keys (bandwidth, consensus weight, country, etc.)
- Contact/family aggregation
- Integration with uptime and bandwidth data
- Template rendering via Jinja2

### `lib/workers.py`
Multiprocessing workers for page generation. Uses fork-based process pool with copy-on-write memory sharing.

### `lib/aroileaders.py`
AROI leaderboard calculations. Computes rankings across 18 categories
for authenticated operators. Supports both CIISS spec v2 (RSA-fingerprint
proofs) and v3 (ed25519 happy-family proofs); the AROI Validation
Champions table surfaces v2/v3 split columns plus tiered v3 migration
badges (Explorer / Migrating / Mostly / Complete) at 1% / 25% / 75% /
100% v3 adoption thresholds.

### `lib/aroi_validation.py`
Single source of truth for CIISS spec parsing, validation-result
processing, and v3 tier classification. Exports the constants
(`SUPPORTED_CIISSVERSIONS`, `V2_PROOF_TYPES`, `V3_PROOF_TYPES`,
`PROOF_TYPE_STAT_KEYS`, `V3_TIER_*`), the regex pair shared with
`lib/relays.py`, and the `V3_CATEGORY_LABELS` dict that maps every
upstream `error_category` to a pasteable-example operator hint.
`get_contact_validation_status` does the per-contact cascade and emits
the peer-issue buckets (`security_incident_relays`,
`pending_onionoo_relays`) consumed by templates.

### `lib/uptime_utils.py`
Uptime data processing. Normalizes Onionoo values (0-999 → 0-100%), calculates averages, detects outliers.

### `lib/intelligence_engine.py`
6-layer analysis system providing smart context:
1. Basic relationships
2. Concentration patterns
3. Performance correlation
4. Infrastructure dependency
5. Geographic clustering
6. Capacity distribution

### `lib/bandwidth_formatter.py`
Formats bandwidth values with appropriate units (bits/s or bytes/s).

### `lib/country_utils.py`
Country classification, rare country detection, geographic analysis.

## Data Flow

1. **Fetch**: Coordinator spawns workers to fetch from 5 API sources in parallel
2. **Parse**: JSON responses parsed into Python dictionaries
3. **Process**: `relays.py` normalizes, sorts, and aggregates data
4. **Enrich**: Uptime/bandwidth data merged, intelligence analysis computed
5. **Render**: Jinja2 templates render HTML with processed data
6. **Write**: Multiprocessing workers write pages to disk in parallel

## Template System

### Inheritance

```
skeleton.html          # Base layout
    └── index.html     # Inherits skeleton
    └── relay-info.html
    └── contact.html
    └── ...
```

### Macros

`macros.html` and `aroi_macros.html` define reusable components:
- Navigation breadcrumbs
- Relay tables
- Badge displays
- Pagination controls

### Autoescape

XSS protection via Jinja2 autoescape. All user-controlled data escaped by default.

## Performance Characteristics

| Metric | Typical Value |
|--------|---------------|
| Generation time | 2-5 minutes |
| Peak memory (`--apis all`) | ~2.4GB |
| Peak memory (`--apis details`) | ~400MB |
| Output pages | ~21,700 |
| Output size | ~500MB |

## See Also

- [Multiprocessing Architecture](multiprocessing.md) - Detailed parallel processing design
- [API Integration](../reference/api-integration.md) - Data sources
- [Output Structure](../reference/output-structure.md) - Generated files
