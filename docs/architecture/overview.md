# Architecture Overview

**Audience**: Contributors  
**Scope**: System design, modules, and data flow

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         allium.py                               │
│   CLI entry point, URL validation, optional-dep check,          │
│   GC pause/freeze, ChartWriter setup, pressure-history refresh  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│               lib/coordinator.py + lib/workers.py               │
│   Threaded API fetching (threading.Thread, 7 enabled under      │
│   --apis all), retries, conditional requests, data/cache/       │
│                                                                 │
│   Onionoo: Details, Uptime, Bandwidth   1aeo: AROI, Exit DNS    │
│   CollecTor: Consensus, Descriptors (unless --no-consensus-eval)│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        lib/relays.py                            │
│        Core data model, enrichment, and precomputation          │
│                                                                 │
│  • Normalization & sorting      • Contact/family precomputation │
│  • Multi-API enrichment         • 21 AROI leaderboards          │
│  • 7-layer IntelligenceEngine   • Consensus & DNS evaluation    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│     lib/site_generator.py + lib/page_writer.py + worker_pool.py │
│   Standalone & sorted listings, fork_map() parallel rendering,  │
│   Jinja2 templates (autoescape), PNG/SVG charts, static sync,   │
│   search-index.json, Prometheus metrics, SEO & crawl-size guard │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                            www/                                 │
│  ~21,700 HTML pages, PNG/SVG charts, search-index.json, metrics │
└─────────────────────────────────────────────────────────────────┘
```

## Key Modules

### `allium.py`
CLI entry point. Parses options, checks URL schemes and `--base-url` safety (`validate_url_arguments`), checks optional PNG chart packages (`optional_deps.check`), disables cyclic GC while building the relay heap and calls `gc.freeze()` before rendering, initializes `ChartWriter`, refreshes daily pressure history (`lib/pressure_history.py`), triggers `generate_site()` (`lib/site_generator.py`), and exits via `os._exit(0)` when no tracer or profiler is active.

### `lib/coordinator.py`
Orchestrates parallel API fetching using `threading.Thread` (`fetch_all_apis_threaded`) across 7 enabled workers under `--apis all` (or 1 under `--apis details`; `--no-consensus-evaluation` skips the 2 CollecTor workers). Repairs Onionoo `first_seen` resets (`correct_first_seen`), constructs and enriches `Relays` (`enrich_with_api_data`), and probes directory authority latency (`probe_authority_latency`).

### `lib/workers.py`
Implements API fetching, guaranteed total-request timeouts (`_fetch_url_with_total_timeout`), exponential-backoff retries (`_retry_with_backoff`), HTTP conditional requests (`If-Modified-Since` / `304 Not Modified`), and JSON caching plus worker status tracking in `allium/data/cache/` and `allium/data/state.json`. Workers are declared in `API_CONFIGS` (7 enabled sources plus dormant `CONSENSUS_HEALTH_CONFIG`).

### `lib/relays.py`
Core `Relays` data model. Normalizes Onionoo relay records, sorts and groups by relay attributes (bandwidth, consensus weight, country, AS, family, contact, platform, first seen), aggregates group metrics, merges secondary APIs in `enrich_with_api_data()`, and runs parallel contact and family precomputation (`_precompute_all_contact_page_data`, `_precompute_all_family_page_data`).

### `lib/site_generator.py`, `lib/page_writer.py`, and `lib/worker_pool.py`
`site_generator.py` defines page inventories (`STANDALONE_PAGES`, `MISC_SORTED_PAGE_TYPES`, `SORTED_PAGE_KEYS`) and drives `generate_site()`. `page_writer.py` configures the Jinja2 environment (global autoescape, bytecode cache, per-process `_cached_relay_row_head` memoization) and renders detail and relay-info pages in parallel via `fork_map()` (`lib/worker_pool.py`), which bounds pipe chunk sizes and uses a parent-exit watchdog thread. `site_generator.py` also syncs static assets (`_sync_static_files`) and orchestrates search index, Prometheus metrics, SEO discovery, and crawl-size checks.

### `lib/charts/` and `lib/pressure_history.py`
`ChartWriter` (`lib/charts/render.py`) generates build-time PNG (`cairocffi` + `numpy`) or SVG charts for relays, contacts, whole-network history, and network pressure (`--chart-format`, `--chart-scale`, `--chart-colors`, `--chart-layout`). `lib/pressure_history.py` backfills and updates daily Tor Metrics and CollecTor server-descriptor pressure data in `allium/data/cache/pressure_history.json`.

### `lib/aroileaders.py`
AROI leaderboard calculations computing rankings across 21 categories for authenticated operators. Supports both CIISS spec v2 (RSA-fingerprint proofs) and v3 (ed25519 happy-family proofs); the AROI Validation Champions table surfaces v2/v3 split columns plus tiered v3 adoption badges (`Explorer` / `Migrating` / `Mostly` / `Complete` at ≥1 v3 relay / 25% / 75% / 100% thresholds).

### `lib/aroi_validation.py`
Single source of truth for CIISS spec parsing, validation-result processing, and v3 tier classification. Exports spec constants (`SUPPORTED_CIISSVERSIONS`, `V2_PROOF_TYPES`, `V3_PROOF_TYPES`, `PROOF_TYPE_STAT_KEYS`, `V3_TIER_*`), the regexes shared with `lib/relays.py`, and `V3_CATEGORY_LABELS` mapping every upstream `error_category` to a pasteable operator fix example. `get_contact_validation_status()` evaluates the per-contact cascade and emits `security_incident_relays` and `pending_onionoo_relays`.

### `lib/intelligence_engine.py`
7-layer analysis system (`analyze_all_layers`) computing network and operator intelligence:
1. Basic relationships
2. Concentration patterns
3. Performance correlation
4. Infrastructure dependency
5. Geographic clustering
6. Capacity distribution
7. Contact intelligence

### `lib/prometheus_metrics.py`, `lib/search_index.py`, `lib/seo.py`, and `lib/search_discovery.py`
- `lib/prometheus_metrics.py`: Emits schema-v2 Prometheus exposition metrics (`www/metrics`).
- `lib/search_index.py`: Builds minified `search-index.json` (using `ThreadPoolExecutor` above 1,000 relays).
- `lib/seo.py`: Normalizes canonical URLs, rewrites internal `.html` links to clean routes (`rewrite_internal_html_links`, parallelized via `fork_map()` for 256+ files), and enforces the 1,900,000-byte HTML crawl-size guard (`oversized_html_files`).
- `lib/search_discovery.py`: Generates `robots.txt` and `sitemap*.xml` from rendered canonical tags when an absolute HTTPS `--base-url` is configured.

### Supporting Utilities
- `lib/uptime_utils.py`: Normalizes Onionoo uptime values (0-999 → 0-100%), computes period averages, and detects outliers.
- `lib/bandwidth_formatter.py`: Formats bandwidth values in bits/s or bytes/s.
- `lib/country_utils.py`: Country classification, rare-country detection, and geographic diversity scoring.

## Data Flow

1. **Validate & Check**: `allium.py` validates URL flags (`validate_url_arguments`) and verifies optional PNG dependencies (`optional_deps.check`).
2. **Fetch**: `Coordinator` spawns threaded workers (`lib/workers.py`) to fetch up to 7 enabled API sources in parallel using conditional requests, retries, and `allium/data/cache/`.
3. **Process & Enrich**: `Relays` normalizes, sorts, categorizes, runs `IntelligenceEngine` and `aroileaders`, merges secondary APIs in `enrich_with_api_data()`, and precomputes contact/family page data in parallel via `fork_map()`.
4. **Charts & Freeze**: `allium.py` builds `ChartWriter`, refreshes daily pressure history (unless `--no-pressure-history`), and freezes the relay heap (`gc.freeze()`).
5. **Render & Write**: `site_generator.generate_site()` renders standalone, misc sorted, detail, and relay-info pages (plus charts) using Jinja2 and `fork_map()` (`lib/page_writer.py`), rewriting internal `.html` links in memory via `_write_html()`, and syncs `static/`.
6. **Index, Metrics & Verify**: Emits `search-index.json` and Prometheus `metrics`, sweeps any pre-existing HTML files with `rewrite_internal_html_links()`, generates `robots.txt` and `sitemap*.xml` for HTTPS `--base-url` builds, and checks the HTML crawl-size guard.

## Template System

### Inheritance

```
skeleton.html              # Base layout
    ├── index.html         # Top 500 relays (inherits skeleton)
    ├── aroi-leaderboards.html
    ├── relay-info.html
    ├── contact.html
    └── ...
```

### Macros

`macros.html`, `aroi_macros.html`, and `misc_listing_macros.html` define reusable components:
- Navigation breadcrumbs and pagination controls
- Relay tables and row-head memoization hooks
- AROI validation badges and detail boxes

### Autoescape

XSS protection via Jinja2 `autoescape=True` in `lib/page_writer.py`. User-controlled Onionoo strings are escaped by default.

## Performance Characteristics

| Metric | Typical Value |
|--------|---------------|
| Generation time (steady state) | 2-5 minutes |
| Peak memory (`--apis all`) | ~2.4GB |
| Peak memory (`--apis details`) | ~400MB |
| Output pages | ~21,700 |
| Output size | ~500MB HTML + PNG/SVG charts (~3.6GB PNG charts) |

**Pressure history backfill vs steady state**: The initial run without `--no-pressure-history` downloads and backfills historical Tor Metrics and CollecTor server-descriptor archives into `allium/data/cache/pressure_history.json`. Steady-state runs only refresh unsealed recent days. Pass `--no-pressure-history` to skip the archive backfill and load existing cached history directly.

## How to Verify

```bash
python3 allium/allium.py --help
pytest tests/unit/coordinator/test_coordinator.py tests/unit/test_seo.py
```

## See Also

- [Multiprocessing Architecture](multiprocessing.md) - Detailed parallel processing design
- [API Integration](../reference/api-integration.md) - Data sources
- [Output Structure](../reference/output-structure.md) - Generated files
