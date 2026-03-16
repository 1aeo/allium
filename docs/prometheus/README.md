# AEO1 Prometheus Metrics

Prometheus endpoint for monitoring Tor exit relay DNS health and AROI validation status.

**Endpoint:** `https://metrics.1aeo.com/metrics`  
**Schema:** v2  
**Update frequency:** Every 30 minutes (allium regeneration cycle)  
**Format:** Prometheus text exposition format 0.0.4

---

## Quick Start

### Scrape Config

```yaml
scrape_configs:
  - job_name: 'aeo1_tor_metrics'
    scrape_interval: 1m
    scrape_timeout: 30s
    static_configs:
      - targets: ['metrics.1aeo.com']
    scheme: https
```

### Install Alert Rules

```bash
cp alerts_dns_health.yml /etc/prometheus/rules/
cp alerts_aroi.yml /etc/prometheus/rules/
kill -HUP $(pidof prometheus)
```

---

## Metrics Reference

### Meta (always emitted)

| Metric | Labels | Description |
|--------|--------|-------------|
| `aeo1_build_info` | `schema`, `generator` | Schema version/build info (v2) |
| `aeo1_generation_timestamp_seconds` | — | Metrics file generation time |
| `aeo1_source_up` | `source` | 1=data source available, 0=unavailable |
| `aeo1_source_last_success_timestamp_seconds` | `source` | Last successful ingest timestamp, 0 if never |

`source` values: `exitdnshealth`, `aroi`

### Exit DNS Health — Aggregates

| Metric | Labels | Description |
|--------|--------|-------------|
| `aeo1_exit_consensus_relays_count` | — | Total exit relays in consensus |
| `aeo1_exit_tested_relays_count` | — | Relays with DNS test results |
| `aeo1_exit_unreachable_relays_count` | — | Relays unreachable during latest scan |
| `aeo1_exit_dns_success_ratio` | — | Success fraction (0..1) |
| `aeo1_exit_reachability_ratio` | — | Reachability fraction (0..1) |
| `aeo1_exit_dns_errors_count` | `error_type` | Error count by type |
| `aeo1_exit_dns_latency_ms_stat` | `stat` | Latency statistics (ms) |
| `aeo1_exit_scan_timestamp_seconds` | — | Exit DNS scan timestamp |

`error_type` values: `fail`, `timeout`, `wrong_ip`, `socks_error`, `network_error`, `error`, `exception`, `unknown`  
`stat` values: `p50`, `p95`, `p99`, `avg`, `min`, `max`

### Exit DNS Health — Per Relay (exit relays only)

| Metric | Frozen Labels | Description |
|--------|---------------|-------------|
| `aeo1_exit_dns_failed` | `fingerprint`, `familyid`, `status` | 1=failed, 0=healthy/untested |
| `aeo1_exit_dns_latency_ms` | `fingerprint`, `familyid` | Latency (ms), omitted when unavailable |
| `aeo1_exit_dns_consecutive_failures` | `fingerprint`, `familyid` | Consecutive failure streak |
| `aeo1_exit_relay_info` | `fingerprint`, `familyid`, `nick`, `verifiedaroi` | Relay metadata (always 1, non-ABI) |

`status` values: `success`, `dns_fail`, `timeout`, `relay_unreachable`, `untested`

### AROI Monitoring — Relay State Model (schema v2)

AROI status is represented by a single canonical relay state enum.

| Metric | Labels | Description |
|--------|--------|-------------|
| `aeo1_aroi_relay_state` | `fingerprint`, `familyid`, `state` | Per-relay AROI state (always 1 for emitted state) |
| `aeo1_aroi_relays_count` | `state` | Aggregate relay count by state |
| `aeo1_aroi_scan_timestamp_seconds` | — | AROI scan timestamp |
| `aeo1_aroi_relay_info` | `fingerprint`, `familyid`, `nick`, `domain`, `proof_type` | Configured relay metadata (always 1, non-ABI) |

Frozen `state` label values:
- `not_configured`
- `configured_unchecked`
- `configured_checked_invalid`
- `configured_checked_valid`

Interpretation:
- `configured_checked_invalid` = validation was attempted and failed
- `configured_unchecked` = relay is configured, but validator had no result for its fingerprint

---

## PromQL Cheatsheet (v2)

### AROI State Queries

```promql
# Family: checked + invalid relays
aeo1_aroi_relay_state{familyid="YOUR_FAMILY_ID",state="configured_checked_invalid"} == 1

# Family: checked + valid relays
aeo1_aroi_relay_state{familyid="YOUR_FAMILY_ID",state="configured_checked_valid"} == 1

# Domain: checked + invalid relays
aeo1_aroi_relay_state{state="configured_checked_invalid"} == 1
  and on(fingerprint) aeo1_aroi_relay_info{domain="YOUR_DOMAIN"}

# Domain: configured but unchecked relays
aeo1_aroi_relay_state{state="configured_unchecked"} == 1
  and on(fingerprint) aeo1_aroi_relay_info{domain="YOUR_DOMAIN"}
```

### Derived Ratios (from canonical counts)

```promql
# Success ratio over configured relays
aeo1_aroi_relays_count{state="configured_checked_valid"}
/
(aeo1_aroi_relays_count{state="configured_unchecked"}
 + aeo1_aroi_relays_count{state="configured_checked_invalid"}
 + aeo1_aroi_relays_count{state="configured_checked_valid"})

# Checked coverage ratio over configured relays
(aeo1_aroi_relays_count{state="configured_checked_invalid"}
 + aeo1_aroi_relays_count{state="configured_checked_valid"})
/
(aeo1_aroi_relays_count{state="configured_unchecked"}
 + aeo1_aroi_relays_count{state="configured_checked_invalid"}
 + aeo1_aroi_relays_count{state="configured_checked_valid"})
```

### Freshness

```promql
time() - aeo1_generation_timestamp_seconds
time() - aeo1_exit_scan_timestamp_seconds
time() - aeo1_aroi_scan_timestamp_seconds
up{job="aeo1_tor_metrics"}
```

---

## Migration: v1 → v2

### Breaking changes

- Removed legacy per-relay `aeo1_aroi_valid` (ambiguous for unchecked relays).
- Removed emitted `aeo1_aroi_success_ratio`; compute via `aeo1_aroi_relays_count{state=...}`.
- Canonical relay state now encoded in `aeo1_aroi_relay_state{state=...}`.

### Side-by-side query mapping (including domain/family joins)

| Intent | v1 | v2 |
|---|---|---|
| Family failures | `aeo1_aroi_valid{familyid="YOUR_FAMILY_ID"} == 0` | `aeo1_aroi_relay_state{familyid="YOUR_FAMILY_ID",state="configured_checked_invalid"} == 1` |
| Family valid | `aeo1_aroi_valid{familyid="YOUR_FAMILY_ID"} == 1` | `aeo1_aroi_relay_state{familyid="YOUR_FAMILY_ID",state="configured_checked_valid"} == 1` |
| Domain failures | `aeo1_aroi_valid == 0 and on(fingerprint) aeo1_aroi_relay_info{domain="YOUR_DOMAIN"}` | `aeo1_aroi_relay_state{state="configured_checked_invalid"} == 1 and on(fingerprint) aeo1_aroi_relay_info{domain="YOUR_DOMAIN"}` |
| Domain valid | `aeo1_aroi_valid == 1 and on(fingerprint) aeo1_aroi_relay_info{domain="YOUR_DOMAIN"}` | `aeo1_aroi_relay_state{state="configured_checked_valid"} == 1 and on(fingerprint) aeo1_aroi_relay_info{domain="YOUR_DOMAIN"}` |
| Domain unchecked | not expressible cleanly | `aeo1_aroi_relay_state{state="configured_unchecked"} == 1 and on(fingerprint) aeo1_aroi_relay_info{domain="YOUR_DOMAIN"}` |

---

## Schema Policy

- **v2 state labels are frozen** for `aeo1_aroi_relay_state` and `aeo1_aroi_relays_count`.
- **Non-ABI `_info` metrics** may evolve label keys without schema bump.
- **New additive metrics** may be added without schema bump.
- **Breaking changes** require schema bump in `aeo1_build_info`.
