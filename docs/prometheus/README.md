# AEO1 Prometheus Metrics

Prometheus endpoint for monitoring Tor exit relay DNS health and AROI validation status.

**Endpoint:** `https://metrics.1aeo.com/metrics`  
**Schema:** v1  
**Update frequency:** Every 30 minutes (allium regeneration cycle)  
**Format:** Prometheus text exposition format 0.0.4

---

## Quick Start

### Scrape Config

```yaml
scrape_configs:
  - job_name: 'aeo1_tor_metrics'
    # 1m recommended. Data updates every 30 min but Prometheus needs
    # sub-5m scrapes for reliable alerting (default lookback is 5m).
    # Endpoint is ~220KB gzipped — 1m scraping is fine.
    scrape_interval: 1m
    scrape_timeout: 30s
    static_configs:
      - targets: ['metrics.1aeo.com']
    scheme: https
```

### Install Alert Rules

```bash
# Copy alert rules to your Prometheus rules directory
cp alerts_dns_health.yml /etc/prometheus/rules/
cp alerts_aroi.yml /etc/prometheus/rules/

# Edit: replace YOUR_FAMILY_ID and YOUR_DOMAIN with your values
vim /etc/prometheus/rules/alerts_dns_health.yml
vim /etc/prometheus/rules/alerts_aroi.yml

# Reload Prometheus
kill -HUP $(pidof prometheus)
```

---

## Metrics Reference

### Meta (always emitted)

| Metric | Labels | Description |
|--------|--------|-------------|
| `aeo1_build_info` | `schema`, `generator` | Schema version (always 1) |
| `aeo1_generation_timestamp_seconds` | — | When this file was generated |
| `aeo1_source_up` | `source` | 1=data available, 0=unavailable |
| `aeo1_source_last_success_timestamp_seconds` | `source` | Last successful ingest, 0 if never |

`source` values: `exitdnshealth`, `aroi`

### Exit DNS Health — Aggregates

| Metric | Labels | Description |
|--------|--------|-------------|
| `aeo1_exit_consensus_relays_count` | — | Total exit relays in consensus |
| `aeo1_exit_tested_relays_count` | — | Relays with DNS test results |
| `aeo1_exit_unreachable_relays_count` | — | Relays with circuit failures |
| `aeo1_exit_dns_success_ratio` | — | Success fraction (0..1) |
| `aeo1_exit_reachability_ratio` | — | Reachability fraction (0..1) |
| `aeo1_exit_dns_errors_count` | `error_type` | Error count by type |
| `aeo1_exit_dns_latency_ms_stat` | `stat` | Latency statistics (ms) |
| `aeo1_exit_scan_timestamp_seconds` | — | When DNS scan ran |

`error_type` values: `fail`, `timeout`, `wrong_ip`, `socks_error`, `network_error`, `exception`  
`stat` values: `p50`, `p95`, `p99`, `avg`, `min`, `max`

### Exit DNS Health — Per-Relay (exit relays only)

| Metric | Frozen Labels | Description |
|--------|---------------|-------------|
| `aeo1_exit_dns_failed` | `fingerprint`, `familyid`, `status` | 1=failed, 0=healthy |
| `aeo1_exit_dns_latency_ms` | `fingerprint`, `familyid` | Latency (ms), omitted if untested |
| `aeo1_exit_dns_consecutive_failures` | `fingerprint`, `familyid` | Consecutive failure streak |
| `aeo1_exit_relay_info` | `fingerprint`, `familyid`, `nick`, `verifiedaroi` | Relay metadata (always 1, non-ABI) |

`status` values: `success`, `dns_fail`, `timeout`, `relay_unreachable`

### AROI Monitoring — Aggregates

| Metric | Labels | Description |
|--------|--------|-------------|
| `aeo1_aroi_network_relays_count` | — | Total relays in network |
| `aeo1_aroi_configured_relays_count` | — | Relays with all 3 AROI fields |
| `aeo1_aroi_valid_relays_count` | — | Configured + validated |
| `aeo1_aroi_success_ratio` | — | Validation fraction (0..1) |
| `aeo1_aroi_proof_type_count` | `proof_type`, `result` | Count by proof type |
| `aeo1_aroi_scan_timestamp_seconds` | — | When AROI scan ran |

`proof_type` values: `uri-rsa`, `dns-rsa`  
`result` values: `valid`, `total`

### AROI Monitoring — Per-Relay (configured relays only)

| Metric | Frozen Labels | Description |
|--------|---------------|-------------|
| `aeo1_aroi_valid` | `fingerprint`, `familyid` | 1=valid, 0=failing |
| `aeo1_aroi_relay_info` | `fingerprint`, `familyid`, `nick`, `domain`, `proof_type` | Relay metadata (always 1, non-ABI) |

---

## PromQL Cheatsheet

### DNS Health — Filter by Family

```promql
# All relays in my family:
aeo1_exit_dns_failed{familyid="YOUR_FAMILY_ID"}

# Failing relays in my family:
aeo1_exit_dns_failed{familyid="YOUR_FAMILY_ID"} == 1

# Count of healthy vs failing:
count(aeo1_exit_dns_failed{familyid="YOUR_FAMILY_ID"} == 0)  # healthy
count(aeo1_exit_dns_failed{familyid="YOUR_FAMILY_ID"} == 1)  # failing

# Average latency for my family:
avg(aeo1_exit_dns_latency_ms{familyid="YOUR_FAMILY_ID"})

# Relays with escalating failures:
aeo1_exit_dns_consecutive_failures{familyid="YOUR_FAMILY_ID"} > 2
```

### DNS Health — Filter by AROI Domain

```promql
# All relays for my AROI domain (join with info metric):
aeo1_exit_dns_failed == 1
  and on(fingerprint) aeo1_exit_relay_info{verifiedaroi="www.1aeo.com"}

# Nicknames of my failing relays:
aeo1_exit_relay_info
  and on(fingerprint) (aeo1_exit_dns_failed{familyid="YOUR_FAMILY_ID"} == 1)
```

### AROI Monitoring

```promql
# My relays with broken AROI:
aeo1_aroi_valid{familyid="YOUR_FAMILY_ID"} == 0

# AROI failing for a specific domain:
aeo1_aroi_valid == 0
  and on(fingerprint) aeo1_aroi_relay_info{domain="www.1aeo.com"}

# Network AROI adoption rate:
aeo1_aroi_success_ratio
```

### Freshness

```promql
# How old is the metrics file:
time() - aeo1_generation_timestamp_seconds

# How old is the DNS scan data:
time() - aeo1_exit_scan_timestamp_seconds

# Is the endpoint reachable:
up{job="aeo1_tor_metrics"}
```

---

## Schema Policy

- **v1 is frozen**: metric names, types, and frozen label keys will not change
- **Non-ABI metrics** (`_info` metrics): label keys may evolve without schema bump
- **New metrics** may be added without schema bump
- **Breaking changes** (renames, type changes, frozen label changes): require schema version bump in `aeo1_build_info`
- **`familyid` encoding**: currently 64-char uppercase hex (CollecTor Ed25519 key). Will change to base64 when onionoo adds `family_ids` support — this will require a schema bump

---

## Data Freshness

| Source | Update Frequency | Metric |
|--------|-----------------|--------|
| Allium generation | Every 30 min | `aeo1_generation_timestamp_seconds` |
| Exit DNS health scan | Every 6-12 hours | `aeo1_exit_scan_timestamp_seconds` |
| AROI validation | Every few hours | `aeo1_aroi_scan_timestamp_seconds` |
| CollecTor family keys | Hourly incremental | (embedded in `familyid` labels) |
