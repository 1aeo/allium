# ClickHouse-Powered Historical Analytics for Tor Relay Data

**Branch:** `chrealdescriptorso3`  
**Author:** 1aeo <github@1aeo.com>  
**Date:** 2025-06-24

---

## 1. Overview
Allium already presents snapshots of Tor relay information, but it lacks deep historical context, trend visualisation and anomaly detection.  By ingesting the raw relay-descriptor corpus (2007-06 → Now) directly into ClickHouse we unlock millisecond-fast, SQL-level access to **≈270 GiB** of authoritative network data.  This proposal details a storage model, ingestion pipeline and 20 concrete improvements to the current Allium web experience – all validated against the *real* fields found in today's consensus & descriptor files.

## 2. Data Sources (validated 2025-06-24 12:30 UTC)
| Source | Example URL | Record Count (last hour) |
|--------|-------------|--------------------------|
| Hourly consensuses | `…/consensuses/2025-06-24-12-00-00-consensus` | 5 688 relays |
| Bandwidth lists | `…/consensus-bandwidth/2025-06-24-12-00-00-bandwidth` | 5 350 relays |
| Server descriptors | `…/server-descriptors/2025-06-24-12-00-00-server-descriptors` | 5 622 relays |
| Extra-info descriptors | `…/extra-infos/2025-06-24-12-00-00-extra-infos` | 5 600 relays |

Fields confirmed present: `r` (router line), `s` (flags), `w Bandwidth=`, `opt v Tor=`, `p accept`/`reject`, `family`, `software`, `uptime`, `observed_bandwidth`, `write_history`, `read_history`, etc.

## 3. ClickHouse Schema (v1)
```sql
CREATE TABLE relay_consensus (
    ts              DateTime,      -- valid-after rounded to hour
    fingerprint     FixedString(20),
    nickname        LowCardinality(String),
    address         IPv4,
    or_port         UInt16,
    dir_port        UInt16,
    flags           Array(String),
    bandwidth       UInt32,        -- from `w Bandwidth=`
    measured_bw     UInt32 NULL,   -- from bandwidth file
    consensus_weight UInt32 NULL,  -- weight assigned by bwauth
    version         LowCardinality(String),
    country         LowCardinality(String)  -- via MaxMind lookup
) ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (fingerprint, ts);
```
(Additional tables: `relay_descriptor`, `family_map`, `bw_weight_vote`, `as_stats`, `tor_param_changes` … see Appendix A.)


## 4. Ingestion Pipeline
1. **Bootstrap import (one-off)**  
   • 2007-01-01 → 2025-06-01, ≈240 k compressed files, 270 GiB.  
   • Parallel download via `aria2c` (16 threads).  
   • Parse with Rust or Go streaming parser (handles BZ2/GZip/XZ on the fly).  
   • Batch INSERT into ClickHouse every 5 000 rows with HTTP line-based INSERT.
2. **Realtime tail-follow**  
   • Hourly cron: fetch the latest consensus, bandwidth list, descriptors (detected via directory listing).  
   • Latency <3 min behind dir-auth publication.
3. **Schema-versioning**  
   • Loader records file SHA256 & schema_rev to allow idempotent re-ingest.

## 5. Integration with Allium
A lightweight internal service (`/api/ch/<sql|report>`) forwards parameterised queries to ClickHouse-HTTP and returns JSON/CSV to the Django & Svelte front-ends.  Response ≤50 ms for 10-year range queries with proper projections.

## 6. Top 20 Analytics Enhancements
1. **Bandwidth history chart** per relay (+ mini-sparkline in list view).
2. **Consensus-weight timeline** with 7-day MA; highlight promotions/demotions.
3. **Daily / Monthly / Yearly leaderboards** (weight, measured_bw, uptime).
4. **Operator-level contributions** aggregated by Contact e-mail / Org.
5. **Churn heat-map** – join time vs leave time per relay; daily new vs retired relays.
6. **Flag-transition tracker** (e.g., Guard→Exit) and mean dwell time in each role.
7. **Relay software & version adoption** curve; early adopters leaderboard.
8. **Family composition visualiser** – stacked bandwidth share per family over time.
9. **AS-level centrality analysis** – top N ASNs by weight with growth trend.
10. **Geo-scatter world map** with historic density slider (2007→now).
11. **Sybil cluster detector** – k-NN model on uptime, bw, IP proximity, etc.; timeline view.
12. **Consensus parameter change diff** – alert when Dir-auth votes deviate.
13. **Exit policy churn** – diff of allowed ports; top new services each month.
14. **Directory authority reliability** – voting participation %, dropouts.
15. **Resource-utilisation anomalies** – spikes in `read_history`/`write_history` vs consensus bw.
16. **Unmeasured-to-measured transition lag** tracker – monitors bwauth coverage.
17. **Guard rotation intervals** – CDF & per-relay distribution.
18. **IPv6 adoption metrics** – share of relays offering IPv6 ORPort over time.
19. **DoS parameter impact explorer** – correlate `DoSCircuitCreation*` params with failure rates.
20. **Predictive capacity forecasting** – Holt-Winters on aggregate bw to warn of downturns.

## 7. Example Query Snippets
```sql
-- 7-day bandwidth history for a relay
SELECT ts, bandwidth
FROM relay_consensus
WHERE fingerprint = 'AAoQ1DAR6kkoo19hBAX5K0QztNw'
  AND ts >= now() - INTERVAL 7 DAY
ORDER BY ts;

-- Daily operator leaderboard
SELECT toDate(ts) AS d, contact, sum(consensus_weight) AS cw
FROM relay_consensus
JOIN relay_descriptor USING (fingerprint, ts)
GROUP BY d, contact
ORDER BY d, cw DESC;
```

## 8. Roadmap & Milestones
| Phase | Deliverable | ETA |
|-------|-------------|-----|
| P0 | Infra: ClickHouse cluster on 3 × c6a.large (NVMe-SSD) | +1 w |
| P1 | Loader MVP, backfill 2007-2010 sample | +2 w |
| P2 | Full 2007->Now import, hourly sync | +6 w |
| P3 | Allium Dash additions (items 1-4) | +8 w |
| P4 | Advanced analytics (items 5-12) | +12 w |
| P5 | Predictive & anomaly alerting (items 13-20) | +16 w |

## 9. Risks & Mitigations
* **Data volume growth** – ClickHouse compression ratio 3-5 ×; yearly growth <15 GB.
* **Schema drift** – strict versioning & fuzz-tester comparing consensus parsing outputs.
* **Legal / privacy** – store only public relay metadata, no user traffic.

---
### Appendix A – Additional Table Sketches
• `relay_descriptor` – uptime, software, bandwidth_obs, exit_policy.  
• `bw_vote` – per-auth bandwidth measurements.  
• `vote_params` – key-value Tor consensus params.  
• `as_stats` – daily aggregate per-ASN share.

*Generated automatically from real data fetched on 2025-06-24 12:30 UTC.*