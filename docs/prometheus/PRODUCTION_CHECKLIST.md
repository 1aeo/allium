# Prometheus v2 Production Go/No-Go Checklist

**Audience**: Operators, Contributors  
**Scope**: Pre-production verification gates for Prometheus schema v2 changes

Use this checklist before promoting schema v2 changes to production.

## Go/No-Go Gates

| Gate | Validation | Pass Criteria | Status |
|---|---|---|---|
| 1. Unit + contract tests | `python3 -m unittest -v tests.unit.test_prometheus_metrics tests.unit.test_prometheus_schema_contract` | All tests pass | ☐ |
| 2. Prometheus rules syntax | `promtool check rules docs/prometheus/alerts_aroi.yml docs/prometheus/alerts_dns_health.yml docs/prometheus/recording_rules.yml` | `SUCCESS: ...` for all rule files | ☐ |
| 3. Rule/metric contract | `python3 -m unittest -v tests.unit.test_prometheus_schema_contract` | No unknown `aeo1_` references in alerts/rules | ☐ |
| 4. Full site generation parity | Generate baseline/candidate outputs with all APIs and compare (see [CONTRIBUTING.md](../../CONTRIBUTING.md#output-comparison-major-changes)) | Diffs reviewed; no unexpected static changes | ☐ |
| 5. Static asset integrity | SHA256 manifest diff of `www_*/static` | Zero hash diffs | ☐ |
| 6. Dashboard/query parity | Review all dashboards and alerts using legacy metric names | No live references to removed v1 AROI metrics | ☐ |
| 7. Staging scrape health | Deploy to staging Prometheus target | No scrape parse errors, no series churn anomalies | ☐ |
| 8. Alert dry run | Evaluate key alert expressions in staging | Alerts evaluate as expected for valid/invalid/unchecked states | ☐ |
| 9. Cardinality budget | Inspect series count and scrape size in staging | Within retention/storage budget | ☐ |
| 10. Rollback readiness | Document rollback commit + operational steps | Rollback tested or clearly rehearsed | ☐ |

---

## Mandatory command bundle (local)

Run from repo root:

```bash
python3 -m unittest -v tests.unit.test_prometheus_metrics tests.unit.test_prometheus_schema_contract
promtool check rules docs/prometheus/alerts_aroi.yml docs/prometheus/alerts_dns_health.yml docs/prometheus/recording_rules.yml
```

If you changed generation, templating, or metrics behavior, generate `allium/www_baseline` and `allium/www_candidate` following the **Output Comparison (Major Changes)** workflow in [CONTRIBUTING.md](../../CONTRIBUTING.md#output-comparison-major-changes), then verify static asset integrity:

```bash
# Static-only integrity check (paths match baseline/candidate output dirs)
(cd allium/www_baseline/static && find . -type f | sort | xargs sha256sum) > /tmp/prodcheck_static_baseline.sha256
(cd allium/www_candidate/static && find . -type f | sort | xargs sha256sum) > /tmp/prodcheck_static_candidate.sha256
diff -u /tmp/prodcheck_static_baseline.sha256 /tmp/prodcheck_static_candidate.sha256
```

---

## Staging validation (required before production)

1. Confirm `up{job="aeo1_tor_metrics"} == 1`.
2. Confirm freshness:
   - `time() - aeo1_generation_timestamp_seconds`
   - `time() - aeo1_exit_scan_timestamp_seconds`
   - `time() - aeo1_aroi_scan_timestamp_seconds`
3. Confirm source availability:
   - `aeo1_source_up{source="exitdnshealth"}`
   - `aeo1_source_up{source="aroi"}`
4. Confirm canonical AROI states appear and sum as expected:
   - `aeo1_aroi_relays_count`
   - `aeo1_aroi_relays_count_by_version`
5. Spot-check joins:
   - `aeo1_aroi_relay_state{state="configured_checked_invalid"} == 1 and on(fingerprint) aeo1_aroi_relay_info`

---

## Rollout recommendation

1. Canary deploy (single environment/instance).
2. Observe at least 2 scrape intervals and one full allium regeneration cycle.
3. Promote to full production only if all gates are green.
