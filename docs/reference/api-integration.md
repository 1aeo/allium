# API Integration

**Audience**: Contributors  
**Scope**: Data sources, coordinator workers, caching, and failure behavior

## Coordinator Workers

`allium/lib/coordinator.py` derives its worker list from `API_CONFIGS` in `allium/lib/workers.py`. Under `--apis all`, 7 enabled workers run in parallel threads; `--apis details` runs only Onionoo Details. An 8th entry (`consensus_health`, authority TCP probes) is registered with `enabled=False`.

| Worker (`api_name`) | Mode / Gate | Default Source / Flag | Cache File (`allium/data/cache/`) | Max Cache Age | Critical |
|---|---|---|---|---|---|
| `onionoo_details` | `details`, `all` | `https://onionoo.torproject.org/details` (`--onionoo-details-url`) | `onionoo_details.json` | 6h | Yes |
| `onionoo_uptime` | `all` | `https://onionoo.torproject.org/uptime` (`--onionoo-uptime-url`) | `onionoo_uptime.json` | 12h | No |
| `onionoo_bandwidth` | `all` | `https://onionoo.torproject.org/bandwidth` (`--onionoo-bandwidth-url`) | `onionoo_bandwidth.json` | `--bandwidth-cache-hours` (12h) | No |
| `aroi_validation` | `all` | `https://aroivalidator.1aeo.com/latest.json` (`--aroi-url`) | `aroi_validation.json` | 1h | No |
| `exit_dns_health` | `all` | `https://exitdnshealth.1aeo.com/latest.json` (`--exit-dns-health-url`) | `exit_dns_health.json` | 12h | No |
| `collector_consensus` | `all`, without `--no-consensus-evaluation` | `https://collector.torproject.org` | `collector_consensus.json` | 1h | No |
| `collector_descriptors` | `all`, without `--no-consensus-evaluation` | `https://collector.torproject.org/recent/relay-descriptors/server-descriptors/` | `collector_descriptors.json` (+ `collector_descriptors_files.json`) | 1h | No |

### 1. Onionoo Details (`onionoo_details`)

- **Memory**: ~400MB during processing
- **Required**: Yes (failure exits if no valid cache exists)
- **Fields used**: `fingerprint`, `nickname`, `flags`, `observed_bandwidth`, `advertised_bandwidth`, `consensus_weight`, `consensus_weight_fraction`, `country`, `platform`, `as`, `as_name`, `contact`, `family`, `effective_family`, `alleged_family`, `first_seen`, `last_seen`, `last_restarted`, `or_addresses`, `exit_policy_summary`, `measured`, `running`, `overload_general_timestamp`

### 2. Onionoo Uptime (`onionoo_uptime`)

- **Memory**: ~2GB during processing
- **Fields used**: `1_month`, `6_months`, `1_year`, `5_years` uptime series and flag-specific uptime histories (`Running`, `Guard`, `Exit`, `Fast`)
- **Data format**: Values `0–999` normalized to `0–100%` (minimum 30 daily data points for reliability metrics)
- **`first_seen` correction**: Upstream Onionoo `/details` periodically resets `first_seen` for many relays (issues [#40018](https://gitlab.torproject.org/tpo/network-health/metrics/onionoo/-/issues/40018), [#40028](https://gitlab.torproject.org/tpo/network-health/metrics/onionoo/-/issues/40028), [#40033](https://gitlab.torproject.org/tpo/network-health/metrics/onionoo/-/issues/40033), [#40042](https://gitlab.torproject.org/tpo/network-health/metrics/onionoo/-/issues/40042)). `allium/lib/first_seen_correction.py` repairs `first_seen` from the earliest non-null `/uptime` observation before building the relay set (moving dates earlier only, bounded against pre-2004 values), preserving the raw value in `first_seen_onionoo_raw` and recording `first_seen_repair_stats`.

### 3. Onionoo Bandwidth (`onionoo_bandwidth`)

- **Memory**: ~500MB during processing
- **Cache**: Returns fresh cache immediately when younger than `--bandwidth-cache-hours` (default `12`)
- **Fields used**: `write_history` and `read_history` across `1_month`, `6_months`, `1_year`, `5_years` for total data transferred, overload evaluation, and bandwidth history charts

### 4. AROI Validator (`aroi_validation`)

- **Memory**: Minimal
- **Purpose**: Cryptographic proof of operator domain ownership for AROI validation, leaderboards, Network Health, and Prometheus `metrics`. Supports both CIISS v2 (`dns-rsa`, `uri-rsa`) and CIISS v3 (`dns-familyid-ed25519`, `uri-familyid-ed25519`).
- **Schema handshake**: Reads `metadata.aroivalidator_schema_version` against `AROIVALIDATOR_TESTED_SCHEMAS = (1, 2)` in `allium/lib/aroi_validation.py`. Unrecognized schema versions or unknown `error_category` values emit one-time build warnings (surfaced on `misc/diagnostics.html`) without rejecting data.

### 5. Exit DNS Health (`exit_dns_health`)

- **Memory**: Minimal
- **Default URL**: `https://exitdnshealth.1aeo.com/latest.json` (12h cache matches scan cadence)
- **Purpose**: Per-exit DNS resolution status, failure categories, latency, upstream resolver shares, Network Health Exit DNS Health card, and Prometheus `metrics`

### 6. CollecTor Consensus (`collector_consensus`)

- **Gate**: Skipped with `--no-consensus-evaluation` or `--apis details`
- **Purpose**: Fetches directory authority votes and consensus parameters for per-relay consensus evaluation, flag threshold tracking, and Happy Families consensus-method readiness

### 7. CollecTor Server Descriptors (`collector_descriptors`)

- **Gate**: Skipped with `--no-consensus-evaluation` or `--apis details`
- **Purpose**: Downloads incremental hourly server descriptor files (36-hour coverage window, parsed per-file into `collector_descriptors_files.json`) to extract `family-cert` presence and Ed25519 signing keys (`family_cert_groups`) for Happy Families classification
- **Freshness & downgrade policy**: See [CollecTor Descriptor Freshness Policy](../features/implemented/collector-descriptor-freshness-policy.md)

## Post-Coordinator: CollecTor Pressure History

`allium/lib/pressure_history.py` runs in `allium/allium.py` after the coordinator builds the relay set (even with `--apis details`, though pressure charts are only rendered when `--apis all` and charts are enabled).

- **Sources**: Tor Metrics (`https://metrics.torproject.org/relayflags.csv`, `dirbytes.csv`) and CollecTor server-descriptor monthly `.tar.xz` archives plus `/recent/relay-descriptors/server-descriptors/`
- **Gate**: `--no-pressure-history` or `PYTEST_CURRENT_TEST` skips downloading and reads existing cache data instead
- **Caches**: `allium/data/cache/pressure_history.json` (daily sealed rows, frozen May 2025–May 2026 p10–p90 usual-range bands, `processed_months`) and `allium/data/cache/pressure_descriptor_files.json` (recent file parse cache)
- **Runtime**: ~90 minutes for initial monthly archive backfill on an empty cache; subsequent runs refresh only unsealed days and recent descriptor files

## API Mode Selection

| Mode | Enabled Workers | Typical Memory | Behavior |
|---|---|---|---|
| `details` | `onionoo_details` only | ~400MB | Core relay, family, contact, AS, country, platform, and flag pages; disables uptime, bandwidth, AROI validation, Exit DNS Health, CollecTor evaluation, and charts |
| `all` | All 7 enabled workers | ~2.4GB | Full analytics, reliability, bandwidth history, AROI validation, Exit DNS Health, CollecTor evaluation, and history charts |

## Failure & Degradation Behavior

- **Critical worker (`onionoo_details`)**: Falls back to valid cached `onionoo_details.json` on fetch error/timeout. When no details data is available, `Coordinator.fetch_onionoo_data()` logs `❌ Error: No details data available from onionoo API` and `allium.py` prints `⚠️  No onionoo data available - this might be due to network issues or the service being temporarily unavailable` and exits `0`. An empty relay list (`relays: []`) exits `1`.
- **Non-critical workers** (`onionoo_uptime`, `onionoo_bandwidth`, `aroi_validation`, `exit_dns_health`, `collector_consensus`, `collector_descriptors`): Each worker retries transient errors with exponential backoff, falls back to its cached `.json` on failure/timeout, or returns `None` and marks its worker status `stale` in `allium/data/state.json` (disabling only that feature while site generation continues).
- **Pressure history**: On network/archive errors, `allium.py` prints `⚠️ pressure history unavailable: <error>` and loads whatever history exists in `pressure_history.json`.

## Caching & Rate Limiting

All API, pressure, and chart caches live under `allium/data/` (not in the HTML output directory):

- **API JSON caches**: `allium/data/cache/<api_name>.json` (`onionoo_details.json`, `onionoo_uptime.json`, `onionoo_bandwidth.json`, `aroi_validation.json`, `exit_dns_health.json`, `collector_consensus.json`, `collector_descriptors.json`, `collector_descriptors_files.json`)
- **Conditional request headers**: `allium/data/cache/<api_name>_timestamp.txt` stores `Last-Modified` for `If-Modified-Since` requests on Onionoo endpoints
- **Pressure history caches**: `allium/data/cache/pressure_history.json` and `allium/data/cache/pressure_descriptor_files.json`
- **PNG chart cache**: `allium/data/cache/charts/` (keyed by drawing version and content hash; unused entries swept each build)
- **Worker diagnostics state**: `allium/data/state.json`

## External Resources

- [Onionoo Protocol](https://metrics.torproject.org/onionoo.html) - Official API documentation
- [CollecTor](https://collector.torproject.org/) - Raw Tor network data
- [Tor Metrics](https://metrics.torproject.org/) - Official Tor Project metrics

## How to Verify

```bash
# Test Onionoo connectivity
curl -I https://onionoo.torproject.org/details
curl -I https://onionoo.torproject.org/uptime

# Run allium without the pressure backfill and inspect API worker logs
python3 allium/allium.py --apis all --progress --no-pressure-history 2>&1 | grep -i "api\|fetch\|cache"
```
