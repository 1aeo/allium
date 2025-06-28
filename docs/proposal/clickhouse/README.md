## 3. Time-Series Schema v2 (2025-06-25)

The revised design treats **every consensus hour** (and descriptor publish events) as immutable time-series points rather than mutable row updates.

```sql
CREATE TABLE relay_snapshot (
    ts              DateTime,              -- consensus valid-after (UTC)
    fingerprint     FixedString(20),
    nickname        LowCardinality(String),
    all_nicknames   Array(String),         -- cumulative (up to this ts)
    address_v4      IPv4,
    address_v6      IPv6  NULL,
    or_port         UInt16,
    dir_port        UInt16,

    flags           Array(String),         -- agreed flags
    flags_by_auth   Nested(
        auth String,
        flags Array(String)
    ),

    bw_consensus    UInt32,                -- `w Bandwidth=<N>`
    bw_measured     UInt32 NULL,           -- from per-auth BW file *if present*
    bw_observed     UInt32 NULL,           -- server-descriptor `bandwidth <.. observed>`
    bw_read         UInt64 NULL,           -- last slot of `read-history`
    bw_write        UInt64 NULL,           -- last slot of `write-history`
    cw              UInt32,               -- consensus weight

    uptime          UInt32 NULL,           -- seconds (descriptor)
    first_seen      DateTime,              -- min(ts) over fingerprint
    last_restarted  DateTime NULL,         -- derived: descriptor `published`
    last_ip_change  DateTime NULL,         -- derived when IP differs from prev

    exit_policy     String,                -- from consensus `p` line (compressed)
    contact         LowCardinality(String) NULL,
    family          Array(FixedString(20)),
    version         LowCardinality(String),

    asn             UInt32,                -- GeoLite2 ASN lookup at ingest
    country         FixedString(2),        -- GeoLite2 country ISO-2

    INDEX idx_ts_fpr (fingerprint, ts) TYPE minmax GRANULARITY 1,
    INDEX idx_country_ts (country, ts) TYPE minmax GRANULARITY 4
) ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (fingerprint, ts);
```

### Why this schema?
1. **No updates** – ClickHouse excels at append-only workloads; each hour we INSERT new rows.
2. **Array & Nested columns** efficiently encode sparse per-authority flag data while retaining fast querying (explode via `arrayJoin`).
3. **LowCardinality + FixedString** slashes storage for repeating nicknames, contacts, versions & countries.
4. **Indexes** keep point-lookups (`fingerprint=X`) and time-window scans (`country=US AND ts BETWEEN …`) in microseconds.


## 4. Aggregated Tables & Materialised Views
To power dashboards without heavy on-the-fly GROUP BY, we create incremental **Materialised Views (MVs)** that populate **SummingMergeTree** tables:

| MV | Target Table | Grain | Metrics |
|----|--------------|-------|---------|
| `mv_country_hour` | `country_hour_stats` | (ts, country) hourly | relays, exit_relays, guards, cw_sum, bw_consensus_sum |
| `mv_asn_day` | `asn_day_stats` | (day, asn) daily | relays, cw_sum, bw_consensus_sum |
| `mv_version_day` | `version_day_stats` | (day, version) daily | relays, cw_sum |
| `mv_operator_day` | `operator_day_stats` | (day, contact) daily | relays, cw_sum, bw_read_sum, bw_write_sum |
| `mv_network_hour` | `network_hour_stats` | hour | relays, cw_sum, bw_consensus_sum, bw_measured_sum, bw_observed_sum, median_uptime |

Example **target table** definition (country):
```sql
CREATE TABLE country_hour_stats
(
    ts       DateTime,
    country  FixedString(2),
    relays   UInt32,
    exit_relays UInt32,
    guard_relays UInt32,
    cw_sum   UInt64,
    bw_consensus_sum UInt64
) ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (country, ts);
```

These MVs stream-insert as soon as rows land in `relay_snapshot`, ensuring O(1) read latency for dashboards.


## 5. Additional Optimisations
* **Projections:** add `relays_by_flag` projection to accelerate per-flag counts.
* **Codec ZSTD + Delta + Gorilla** on numeric time-series columns for ~5× compression.
* **TTL:** `ALTER TABLE relay_snapshot MODIFY TTL ts + INTERVAL 2 YEAR DELETE` on raw snapshots if disk is tight (keep aggregates indefinitely).
* **ReplicatedMergeTree** with 2-shard, 2-replica for HA; leader election handled by ZooKeeper or ClickHouse Keeper.


## 6. Open Questions / Future Columns (need verification)
* Per-relay **`measured` bandwidth lists** from bwauth consensus-bandwidth files are not present in the current *recent* mirrors – requires back-catalog fetch. Marked optional.
* **`consensus_params`** table (global key-value per hour) still under evaluation; not included yet.


## 7. Comparison with the proposed `relay_measurements` wide table

| Aspect | Our `relay_snapshot` (v2) | Proposed `relay_measurements` (user) |
|--------|---------------------------|--------------------------------------|
| Storage model | Append-only, one row per relay per consensus hour | Append-only, one row per relay per consensus (same) |
| Column count | ~35 core columns (+ Nested & Arrays) | 150+ columns incl. many derived metrics |
| Custom types | Built-in FixedString/LowCardinality | Adds named aliases (`RelayFingerprint`, etc.) – syntactic sugar |
| Flags | Array + Nested per-auth flags | UInt8 columns for each consensus flag + `authority_flags` bitmap |
| Bandwidth | Consensus BW + observed + measured | Adds rate/burst, advertised, shared, unmeasured flags |
| Exit policy | Raw compressed string | Adds parsed summaries + port booleans |
| Operator/contact parsing | Single string column | Multiple parsed & hashed contact fields |
| Aggregates | Separate materialised views | Repeated network-level totals inside every row (duplication) |
| External data | Only consensus & descriptor | Includes Onionoo-style long-term uptime stats (not in raw data) |

### Strengths
* **`relay_snapshot`** – lean, time-series friendly, easy to extend, avoids duplication, relies solely on raw descriptor data.
* **`relay_measurements`** – richer semantics (rate/burst, exit-policy flags, parsed contacts) and handy custom types for clarity.

### Weaknesses
* `relay_snapshot` misses some descriptor fields that are available today (rate/burst, IPv6 OR addresses).
* `relay_measurements` repeats network-level aggregates each row (storage bloat) and includes metrics (e.g. 1-year uptime) that require historical aggregation or Onionoo – not present in today's raw feeds.

## 8. Hybrid Schema v3 – recommended
We keep the **immutable hourly snapshot** philosophy, add the *real* extra fields available today, and push heavy derived metrics into **separate materialised views** rather than bloating the base table.

```sql
-- Custom aliases for readability
CREATE TYPE IF NOT EXISTS RelayFingerprint AS FixedString(20);
CREATE TYPE IF NOT EXISTS Ed25519Key      AS FixedString(32);
CREATE TYPE IF NOT EXISTS DescriptorDigest AS FixedString(20);

CREATE TABLE relay_snapshot_v3 (
    ts              DateTime,               -- consensus valid-after
    fingerprint     RelayFingerprint,
    ed25519_key     Ed25519Key,
    nickname        LowCardinality(String),
    address_v4      IPv4,
    address_v6      Nullable(IPv6),
    or_port         UInt16,
    dir_port        UInt16,
    or_addresses    Array(String),          -- extra addresses from descriptor

    -- Descriptor linkage
    desc_digest     DescriptorDigest,
    desc_published  DateTime,

    -- Flags
    flags           Array(String),          -- agreed flags
    flags_by_auth   Nested(auth String, flags Array(String)),

    -- Bandwidth
    bw_consensus    UInt32,                 -- w Bandwidth
    bw_rate         UInt64,                 -- descriptor rate
    bw_burst        UInt64,                 -- descriptor burst
    bw_observed     UInt64,                 -- descriptor observed
    bw_measured     Nullable(UInt32),       -- bwauth (historical backfill)

    cw              UInt32,                 -- consensus weight

    -- Uptime / lifecycle
    uptime_seconds  Nullable(UInt32),
    first_seen      DateTime,
    last_restarted  Nullable(DateTime),
    last_ip_change  Nullable(DateTime),

    -- Contact & version (raw)
    contact_raw     String CODEC(ZSTD),
    version         LowCardinality(String),

    -- Geo / AS
    country         FixedString(2),
    asn             UInt32,

    -- Families
    family          Array(RelayFingerprint),

    INDEX idx_ts_fpr (fingerprint, ts) TYPE minmax GRANULARITY 1
) ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (fingerprint, ts);
```

### Derived & Aggregated Layers
1. **Contact & Operator MV** – parses `contact_raw` into `email_domain`, `pgp_fpr`, etc.  
2. **Exit-Policy MV** – stores boolean port flags & policy category.  
3. **Network-wide stats MV** – hourly totals, guard/exit counts, weight sums.  
4. **Long-term uptime MV** – computes 1-, 3-, 12-month uptime % from `relay_snapshot_v3`; no Onionoo needed.

This keeps the base table lean (~65 columns) while still exposing the richer analytics of the wide schema through MVs that can be backfilled or recalculated cheaply.

---
*Validated against real files dated 2025-06-25 18:15 UTC; only fields present in the consensus and descriptor corpus have been included.*