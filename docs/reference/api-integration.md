# API Integration

**Audience**: Contributors  
**Scope**: Data sources, endpoints, and failure behavior

## Data Sources

### Onionoo Details API

| Property | Value |
|----------|-------|
| **URL** | `https://onionoo.torproject.org/details` |
| **CLI Flag** | `--onionoo-details-url` |
| **Memory** | ~400MB during processing |
| **Required** | Yes |
| **Failure** | Exit with error |

**Fields used**: fingerprint, nickname, flags, observed_bandwidth, consensus_weight, consensus_weight_fraction, country, platform, as, as_name, contact, family, first_seen, last_seen, or_addresses, exit_policy_summary, measured, running

### Onionoo Uptime API

| Property | Value |
|----------|-------|
| **URL** | `https://onionoo.torproject.org/uptime` |
| **CLI Flag** | `--onionoo-uptime-url` |
| **Memory** | ~2GB during processing |
| **Required** | Only with `--apis all` |
| **Failure** | Graceful degradation (reliability features disabled) |

**Fields used**: uptime history (1_month, 6_months, 1_year, 5_years), flag-specific uptime history. Also cross-checked against `/details` first_seen — see below.

**Data format**: Values 0-999 representing uptime percentage (divided by 999 * 100 = percentage)

### Workaround: first_seen correction from Uptime API

Onionoo's `/details` endpoint periodically resets `first_seen` for many
relays (see upstream issues
[#40018](https://gitlab.torproject.org/tpo/network-health/metrics/onionoo/-/issues/40018),
[#40028](https://gitlab.torproject.org/tpo/network-health/metrics/onionoo/-/issues/40028),
[#40033](https://gitlab.torproject.org/tpo/network-health/metrics/onionoo/-/issues/40033),
[#40042](https://gitlab.torproject.org/tpo/network-health/metrics/onionoo/-/issues/40042)).
As of 2026-05-13, ~88% of running relays share a single reset timestamp
of `2026-04-06 23:00:00`. The `/uptime` endpoint stores history
independently and survives the reset.

Before constructing the relay set, Allium cross-checks each relay's
`first_seen` against the earliest non-null entry in its uptime history. If
the uptime endpoint observed the relay earlier than `/details` claims,
`first_seen` is moved to the uptime-derived timestamp and the original
value is preserved under `first_seen_onionoo_raw` for diagnostics.

The correction is conservative (only moves `first_seen` earlier, never
later), defensively bounded (rejects pre-2004 garbage values), and a
silent no-op when `/uptime` data is unavailable (e.g. `--apis details`).
Implementation: `allium/lib/first_seen_correction.py`. Repair stats are
surfaced on the coordinator's relay set as `first_seen_repair_stats` and
logged once per run. This module is intended to be removed once the
upstream bug is fixed.

### Onionoo Bandwidth API

| Property | Value |
|----------|-------|
| **URL** | `https://onionoo.torproject.org/bandwidth` |
| **CLI Flag** | `--onionoo-bandwidth-url` |
| **Memory** | ~500MB during processing |
| **Cache** | Configurable via `--bandwidth-cache-hours` (default: 12) |
| **Failure** | Graceful degradation |

**Fields used**: Historical bandwidth data for trend analysis

### AROI Validator API

| Property | Value |
|----------|-------|
| **URL** | `https://aroivalidator.1aeo.com/latest.json` |
| **CLI Flag** | `--aroi-url` |
| **Memory** | Minimal |
| **Required** | No |
| **Failure** | AROI validation features disabled |
| **Schema versions tested** | 1, 2 (see `AROIVALIDATOR_TESTED_SCHEMAS`) |

**Purpose**: Provides cryptographic proof of relay operator identity for
AROI leaderboards. Allium consumes the validator's output for both
**CIISS ContactInfo specification version 2** (RSA-fingerprint proofs:
`dns-rsa`, `uri-rsa`) and **version 3** (ed25519 happy-family proofs:
`dns-familyid-ed25519`, `uri-familyid-ed25519`). Both versions are
supported concurrently during the migration window — operators are
nudged toward v3 but not forced.

**Schema-version handshake**: Allium reads
`metadata.aroivalidator_schema_version` and logs a one-time warning
when an unrecognized schema is received but does **not** reject the
data — this is forward-compatible by design. The schema version is
surfaced as `aroi_schema_version` in `network_health` metrics and shown
as a footnote on the dashboard. When the validator adds a new
`error_category` value, allium logs a one-time warning so we know to
update `V3_CATEGORY_LABELS` in `aroi_validation.py`.

### CollecTor Consensus (Optional)

| Property | Value |
|----------|-------|
| **Source** | Tor Project CollecTor |
| **Purpose** | Flag thresholds, consensus evaluation |
| **Failure** | Graceful degradation |

**Fields used**: Consensus parameters, flag assignment thresholds

## API Mode Selection

```bash
# Details only (~400MB memory)
python3 allium.py --apis details

# All APIs (~2.4GB memory)  
python3 allium.py --apis all
```

| Mode | APIs Enabled | Memory | Features |
|------|--------------|--------|----------|
| `details` | Details only | ~400MB | Basic relay info, no reliability metrics |
| `all` | Details + Uptime + Bandwidth | ~2.4GB | Full features including reliability |

## Error Handling

### Required APIs

**Details API failure**: Generator exits with error. Cannot proceed without core relay data.

```
❌ Error: Failed to initialize relay data
```

### Optional APIs

**Uptime/Bandwidth API failure**: Generator continues with reduced functionality.

```
⚠️ Uptime API unavailable - reliability features disabled
```

**AROI Validator failure**: AROI validation features disabled, leaderboards still generated from contact info.

## Caching

### Bandwidth Cache

```bash
# Default: 12 hours
python3 allium.py --bandwidth-cache-hours 12

# Disable caching (always fetch fresh)
python3 allium.py --bandwidth-cache-hours 0

# Extended cache (24 hours)
python3 allium.py --bandwidth-cache-hours 24
```

Cache stored in output directory as `.bandwidth_cache.json`.

## Rate Limiting

Allium respects Tor Project API guidelines:
- HTTP conditional requests (If-Modified-Since)
- Reasonable request intervals
- Graceful handling of rate limit responses

## External Resources

- [Onionoo Protocol](https://metrics.torproject.org/onionoo.html) - Official API documentation
- [CollecTor](https://collector.torproject.org/) - Raw Tor network data
- [Tor Metrics](https://metrics.torproject.org/) - Official Tor Project metrics

## How to Verify

```bash
# Test API connectivity
curl -I https://onionoo.torproject.org/details
curl -I https://onionoo.torproject.org/uptime

# Generate with verbose output to see API status
python3 allium/allium.py --apis all --progress 2>&1 | grep -i "api\|fetch"
```
