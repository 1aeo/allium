# AEO1 Prometheus Metrics

**Audience**: Operators, Contributors  
**Scope**: Prometheus exposition schema v2, alert rules, recording rules, and query reference

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

### Install Alert and Recording Rules

```bash
cp alerts_dns_health.yml /etc/prometheus/rules/
cp alerts_aroi.yml /etc/prometheus/rules/
cp recording_rules.yml /etc/prometheus/rules/
kill -HUP $(pidof prometheus)
```

Install `recording_rules.yml` alongside `alerts_aroi.yml`: the `AroiV3SuccessRateLow` alert in `alerts_aroi.yml` queries `aeo1_aroi_v3_success_ratio_derived`, which is produced by `recording_rules.yml`.

---

## Metrics Reference

### Meta (always emitted)

| Metric | Labels | Description |
|--------|--------|-------------|
| `aeo1_build_info` | `schema`, `generator` | Schema version/build info (`v2`) |
| `aeo1_generation_timestamp_seconds` | - | Metrics file generation time |
| `aeo1_source_up` | `source` | 1=data source available, 0=unavailable |
| `aeo1_source_last_success_timestamp_seconds` | `source` | Last successful ingest timestamp, 0 if never |

`source` values: `exitdnshealth`, `aroi`

### Exit DNS Health: Aggregates

| Metric | Labels | Description |
|--------|--------|-------------|
| `aeo1_exit_consensus_relays_count` | - | Total exit relays in consensus |
| `aeo1_exit_tested_relays_count` | - | Relays with DNS test results |
| `aeo1_exit_unreachable_relays_count` | - | Relays unreachable during latest scan |
| `aeo1_exit_dns_success_ratio` | - | Success fraction (0..1) |
| `aeo1_exit_reachability_ratio` | - | Reachability fraction (0..1) |
| `aeo1_exit_dns_errors_count` | `error_type` | Error count by type |
| `aeo1_exit_dns_latency_ms_stat` | `stat` | Latency statistics (ms) |
| `aeo1_exit_scan_timestamp_seconds` | - | Exit DNS scan timestamp |

`error_type` values: `fail`, `timeout`, `wrong_ip`, `socks_error`, `network_error`, `error`, `exception`, `unknown`  
`stat` values: `p50`, `p95`, `p99`, `avg`, `min`, `max`

### Exit DNS Health: Per Relay (exit relays only)

| Metric | Frozen Labels | Description |
|--------|---------------|-------------|
| `aeo1_exit_dns_failed` | `fingerprint`, `familyid`, `status` | 1=failed, 0=healthy/untested |
| `aeo1_exit_dns_latency_ms` | `fingerprint`, `familyid` | Latency (ms), omitted when unavailable |
| `aeo1_exit_dns_consecutive_failures` | `fingerprint`, `familyid` | Consecutive failure streak |
| `aeo1_exit_relay_info` | `fingerprint`, `familyid`, `nick`, `verifiedaroi` | Relay metadata (always 1, non-ABI) |

`status` values: `success`, `dns_fail`, `timeout`, `relay_unreachable`, `untested` (`untested` emits `aeo1_exit_dns_failed ... 0`).

### Exit DNS Health: Upstream Resolvers

Estimates of which resolver each exit's DNS lookups come from, from sampled queries at the
validator's authoritative DNS over recent scans (3.5-day half-life). Emitted only when the
exitdnshealth report carries them (`metadata.resolvers`, per-exit `resolver`); older reports
and failed resolver runs emit none of these series, never zeros. Additive: schema v2 is unchanged.

| Metric | Labels | Description |
|--------|--------|-------------|
| `aeo1_exit_dns_public_resolver_share_ratio` | `provider` | Share of exit DNS lookups sent via a public resolver service, weighted by exit probability when available (0..1); omitted while no exit is covered |
| `aeo1_exit_resolver_covered_relays_count` | - | Exits with DNS success and enough sampled queries (5+ estimated) to count toward the shares |
| `aeo1_exit_public_resolver_relays_count` | - | Exits with DNS success whose primary resolver (named at 25+ estimated queries) is a public service |
| `aeo1_exit_dns_resolver_queries_count` | `fingerprint`, `familyid`, `provider` | Estimated queries from the exit by resolver, decayed (per relay; only resolvers with data) |

`provider` values for `aeo1_exit_dns_public_resolver_share_ratio`: `google`, `cloudflare`, `quad9`, `opendns`, `ffmuc` (Freifunk München), `all`; all six are emitted whenever the share block is present.  
`provider` values for `aeo1_exit_dns_resolver_queries_count`: the five above plus `local` (version-1 reports: the exit's own address or origin AS), `local_24` (same IPv4 /24 or IPv6 /64, including the exit's own address), `local_22` (same IPv4 /22 or IPv6 /48), `local_as` (same origin AS, outside those prefixes), `local_operator` (same operator, other network), `other`, `unknown` (origin AS lookup failed). `local` stays valid for version-1 reports. The four `local_*` values are additive; schema v2 is unchanged.

```promql
# Resolver mix of your exits
sum by (provider) (aeo1_exit_dns_resolver_queries_count{familyid="YOUR_FAMILY_ID"})

# Largest resolver per exit
topk by (fingerprint) (1, aeo1_exit_dns_resolver_queries_count)
```

### AROI Monitoring: Relay State Model (schema v2)

AROI status is represented by a single canonical relay state enum.

| Metric | Labels | Description |
|--------|--------|-------------|
| `aeo1_aroi_relay_state` | `fingerprint`, `familyid`, `state`, `ciissversion`, `proof_type_family` | Per-relay AROI state (always 1 for emitted state) |
| `aeo1_aroi_relays_count` | `state` | Aggregate relay count by state |
| `aeo1_aroi_relays_count_by_version` | `state`, `ciissversion` | Aggregate relay count by state and declared `ciissversion` (all 16 series emitted) |
| `aeo1_aroi_scan_timestamp_seconds` | - | AROI scan timestamp |
| `aeo1_aroi_relay_info` | `fingerprint`, `familyid`, `nick`, `domain`, `proof_type` | Configured relay metadata (always 1, non-ABI) |

Label value enums:
- `state` (frozen): `not_configured`, `configured_unchecked`, `configured_checked_invalid`, `configured_checked_valid`
- `ciissversion`: `none`, `2`, `3`, `unknown`
- `proof_type_family`: `none`, `rsa`, `familyid`, `unknown`

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

## Schema v1 to v2 Reference

Schema v2 replaces `aeo1_aroi_valid` and `aeo1_aroi_success_ratio` with `aeo1_aroi_relay_state{state=...}` and `aeo1_aroi_relays_count{state=...}`, and emits `aeo1_exit_dns_failed{status="untested"} 0` (not failed).

### Migration checklist

1. Replace `aeo1_aroi_valid` references with `aeo1_aroi_relay_state{state="configured_checked_invalid"}` or `state="configured_checked_valid"`.
2. Alert on `state="configured_unchecked"` to detect validator coverage gaps.
3. Replace `aeo1_aroi_success_ratio` with expressions derived from `aeo1_aroi_relays_count` (or `recording_rules.yml`).
4. Validate updated rules in staging Prometheus before production rollout.

### Side-by-side query mapping

| Intent | v1 | v2 |
|---|---|---|
| Family failures | `aeo1_aroi_valid{familyid="YOUR_FAMILY_ID"} == 0` | `aeo1_aroi_relay_state{familyid="YOUR_FAMILY_ID",state="configured_checked_invalid"} == 1` |
| Family valid | `aeo1_aroi_valid{familyid="YOUR_FAMILY_ID"} == 1` | `aeo1_aroi_relay_state{familyid="YOUR_FAMILY_ID",state="configured_checked_valid"} == 1` |
| Domain failures | `aeo1_aroi_valid == 0 and on(fingerprint) aeo1_aroi_relay_info{domain="YOUR_DOMAIN"}` | `aeo1_aroi_relay_state{state="configured_checked_invalid"} == 1 and on(fingerprint) aeo1_aroi_relay_info{domain="YOUR_DOMAIN"}` |
| Domain valid | `aeo1_aroi_valid == 1 and on(fingerprint) aeo1_aroi_relay_info{domain="YOUR_DOMAIN"}` | `aeo1_aroi_relay_state{state="configured_checked_valid"} == 1 and on(fingerprint) aeo1_aroi_relay_info{domain="YOUR_DOMAIN"}` |
| Domain unchecked | not expressible cleanly | `aeo1_aroi_relay_state{state="configured_unchecked"} == 1 and on(fingerprint) aeo1_aroi_relay_info{domain="YOUR_DOMAIN"}` |

---

## Operator Runbook (quick triage)

When an AROI alert fires:

1. **Check source freshness**: `aeo1_source_up{source="aroi"}` and `time() - aeo1_aroi_scan_timestamp_seconds`
2. **Identify state**: `configured_checked_invalid` (validator checked and failed) vs `configured_unchecked` (no result for relay fingerprint)
3. **Drill down per relay**: `aeo1_aroi_relay_state{state="configured_checked_invalid"} == 1 and on(fingerprint) aeo1_aroi_relay_info`
4. **Assess blast radius**: `aeo1_aroi_relays_count{state="configured_checked_invalid"}` and `aeo1_aroi_relays_count{state="configured_unchecked"}`

## Aggregate-only dashboard mode (low cardinality)

If you do not need per-relay visuals, build dashboards from `aeo1_aroi_relays_count` and `aeo1_aroi_relays_count_by_version` only:

```promql
# State distribution (4-series panel)
aeo1_aroi_relays_count

# Checked coverage over configured relays
(aeo1_aroi_relays_count{state="configured_checked_invalid"}
 + aeo1_aroi_relays_count{state="configured_checked_valid"})
/
(aeo1_aroi_relays_count{state="configured_unchecked"}
 + aeo1_aroi_relays_count{state="configured_checked_invalid"}
 + aeo1_aroi_relays_count{state="configured_checked_valid"})

# Success over configured relays
aeo1_aroi_relays_count{state="configured_checked_valid"}
/
(aeo1_aroi_relays_count{state="configured_unchecked"}
 + aeo1_aroi_relays_count{state="configured_checked_invalid"}
 + aeo1_aroi_relays_count{state="configured_checked_valid"})
```

## Recording rules (required by `alerts_aroi.yml`)

`docs/prometheus/recording_rules.yml` defines precomputed ratio series, including `aeo1_aroi_v3_success_ratio_derived` (required by the `AroiV3SuccessRateLow` alert in `alerts_aroi.yml`), `aeo1_aroi_checked_ratio_derived`, `aeo1_aroi_success_ratio_derived`, and `aeo1_aroi_v3_adoption_ratio_derived`:

```bash
cp recording_rules.yml /etc/prometheus/rules/
kill -HUP $(pidof prometheus)
```

## Production Go/No-Go Checklist

Before deploying schema updates to production, run the gate checklist in [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md).

---

## Schema Policy

- **v2 state values and core label keys are frozen**; `ciissversion` and `proof_type_family` are bounded additive labels on `aeo1_aroi_relay_state`.
- **Non-ABI `_info` metrics** may evolve label keys without schema bump.
- **New additive metrics** (such as `aeo1_aroi_relays_count_by_version`) may be added without schema bump.
- **Breaking changes** require a schema bump in `aeo1_build_info`.

## How to Verify

```bash
python3 -m unittest -v tests.unit.test_prometheus_metrics tests.unit.test_prometheus_schema_contract
promtool check rules docs/prometheus/alerts_aroi.yml docs/prometheus/alerts_dns_health.yml docs/prometheus/recording_rules.yml
```
