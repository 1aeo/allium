# Optimal ClickHouse Time-Series Schema Design for Tor Relay Data

Based on analysis of real relay data (lilpeep example) and ClickHouse best practices for time-series data.

## Design Decisions & Rationale

### 1. One Big Table vs Multiple Smaller Tables?

**Decision: Hybrid Approach - One Main Table + Supporting Tables**

**Rationale:**
- **Main measurements table** for hourly consensus snapshots (immutable)
- **Separate descriptor table** for less frequent updates (server descriptors change ~daily)
- **Reference tables** for slowly changing dimensions (AS info, GeoIP)

This approach balances:
- Query performance (fewer JOINs for common queries)
- Storage efficiency (no redundant descriptor data every hour)
- Ingestion simplicity (clear data boundaries)

### 2. Immutable vs Mutable Design?

**Decision: Strictly Immutable**

**Rationale:**
- Time-series data should never be updated
- Each row represents a point-in-time measurement
- Historical accuracy is paramount
- ClickHouse performs best with append-only workloads
- Enables efficient compression and partitioning

### 3. How to Store Per-Authority Data?

**Decision: Hybrid - Separate Columns for Flags, Nested for Extended Data**

**Rationale:**
- **Separate columns** for authority flags (using bitmaps) - fastest queries
- **Nested structure** for variable authority data (bandwidth measurements, stats)
- **Materialized columns** for consensus flags - eliminates computation

This provides:
- Fast filtering on specific authority opinions
- Flexibility for authority-specific data
- Efficient storage via bitmap encoding

### 4. Additional Design Considerations

**Fingerprint Storage:**
- Use binary FixedString(20) instead of hex strings (50% space saving)
- Create UDF for hex conversion in queries

**Timestamp Precision:**
- Use DateTime (second precision) for consensus times
- Bandwidth measurements can use same consensus timestamp

**Partitioning Strategy:**
- Monthly partitions for optimal query performance
- Automatic archival of old partitions

## Optimal Schema Design

```sql
-- =====================================================
-- MAIN TIME-SERIES TABLE: Hourly Relay Measurements
-- =====================================================
CREATE TABLE relay_measurements (
    -- === TEMPORAL KEYS ===
    measurement_hour DateTime,                      -- Truncated to hour
    consensus_valid_after DateTime,                 -- Exact consensus timestamp
    
    -- === RELAY IDENTITY ===
    fingerprint FixedString(20),                   -- Binary SHA1 (not hex)
    ed25519_master_key Nullable(FixedString(32)), -- Binary Ed25519
    nickname LowCardinality(String),               -- Current nickname
    
    -- === NETWORK LOCATION ===
    ipv4 IPv4,                                     -- Primary IPv4
    ipv6 Nullable(IPv6),                          -- IPv6 if available
    or_port UInt16,
    dir_port UInt16,
    
    -- === CONSENSUS RESULTS (What was agreed) ===
    consensus_weight UInt32,                       -- Final consensus weight
    consensus_flags UInt32,                        -- Bitmap of consensus flags
    -- Individual consensus flags as computed columns for fast filtering
    flag_exit UInt8 MATERIALIZED bitTest(consensus_flags, 0),
    flag_fast UInt8 MATERIALIZED bitTest(consensus_flags, 1),
    flag_guard UInt8 MATERIALIZED bitTest(consensus_flags, 2),
    flag_hsdir UInt8 MATERIALIZED bitTest(consensus_flags, 3),
    flag_running UInt8 MATERIALIZED bitTest(consensus_flags, 4),
    flag_stable UInt8 MATERIALIZED bitTest(consensus_flags, 5),
    flag_v2dir UInt8 MATERIALIZED bitTest(consensus_flags, 6),
    flag_valid UInt8 MATERIALIZED bitTest(consensus_flags, 7),
    
    -- === PER-AUTHORITY FLAGS (8 authorities) ===
    -- Each authority gets a UInt32 bitmap for their flag votes
    flags_moria1 UInt32,
    flags_tor26 UInt32,
    flags_dizum UInt32,
    flags_gabelmoo UInt32,
    flags_dannenberg UInt32,
    flags_maatuska UInt32,
    flags_faravahar UInt32,
    flags_longclaw UInt32,
    flags_bastet UInt32,
    
    -- === BANDWIDTH MEASUREMENTS ===
    -- Consensus bandwidth (median of authority measurements)
    bandwidth_consensus UInt32,
    
    -- Per-authority bandwidth measurements (0 if unmeasured)
    bw_measured_moria1 UInt32,
    bw_measured_tor26 UInt32,
    bw_measured_dizum UInt32,
    bw_measured_gabelmoo UInt32,
    bw_measured_dannenberg UInt32,
    bw_measured_maatuska UInt32,
    bw_measured_faravahar UInt32,
    bw_measured_longclaw UInt32,
    bw_measured_bastet UInt32,
    
    -- Count of authorities that measured this relay
    measured_by_count UInt8,
    
    -- === ADDITIONAL AUTHORITY DATA ===
    -- For variable per-authority data like stats, use Nested
    authority_stats Nested (
        authority LowCardinality(String),
        mtbf UInt32,                              -- Mean time between failure
        wmtbf UInt32,                             -- Weighted MTBF
        wfu Float32,                              -- Weighted fractional uptime
        tk UInt32                                 -- Time known
    ),
    
    -- === VERSION & PLATFORM ===
    version LowCardinality(String),                -- e.g., "Tor 0.4.8.16"
    version_status Enum8('recommended' = 1, 'acceptable' = 2, 'outdated' = 3, 'obsolete' = 4),
    
    -- === PROTOCOLS ===
    protocols Map(String, String),                 -- {Conflux: "1", Cons: "1-2", ...}
    
    -- === EXIT POLICY ===
    exit_policy_summary LowCardinality(String),    -- Compressed summary from consensus
    exit_ports_bitmap UInt64,                      -- Bitmap of allowed ports (common ones)
    
    -- === DESCRIPTOR DIGEST ===
    descriptor_digest FixedString(20),             -- Links to descriptor table
    
    -- === GEOGRAPHIC CONTEXT ===
    country_code FixedString(2),                   -- From GeoIP
    as_number UInt32,                              -- From GeoIP
    as_name LowCardinality(String),               -- Denormalized for performance
    
    -- === COMPUTED FIELDS ===
    is_exit UInt8 ALIAS flag_exit,
    is_guard UInt8 ALIAS flag_guard,
    is_hsdir UInt8 ALIAS flag_hsdir,
    
    -- === INDICES ===
    INDEX idx_nickname nickname TYPE bloom_filter GRANULARITY 4,
    INDEX idx_country country_code TYPE set(100) GRANULARITY 4,
    INDEX idx_version version TYPE set(100) GRANULARITY 4,
    INDEX idx_exit_ports exit_ports_bitmap TYPE bloom_filter GRANULARITY 4
    
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(measurement_hour)
ORDER BY (fingerprint, measurement_hour)
TTL measurement_hour + INTERVAL 5 YEAR
SETTINGS 
    index_granularity = 8192,
    compress_block_size = 65536,
    mark_cache_size = 5368709120; -- 5GB mark cache

-- =====================================================
-- DESCRIPTOR TABLE: Less Frequent Updates
-- =====================================================
CREATE TABLE relay_descriptors (
    -- === IDENTITY & TIME ===
    descriptor_digest FixedString(20) PRIMARY KEY,
    fingerprint FixedString(20),
    published DateTime,
    
    -- === BANDWIDTH DETAILS ===
    bandwidth_rate UInt64,                         -- bytes/sec
    bandwidth_burst UInt64,                        -- bytes/sec
    bandwidth_observed UInt64,                     -- bytes/sec
    
    -- === KEYS ===
    ed25519_master_key FixedString(32),
    ntor_onion_key FixedString(32),
    
    -- === OPERATOR INFO ===
    contact String CODEC(ZSTD(3)),
    contact_hash UInt64 MATERIALIZED cityHash64(contact),
    
    -- === FAMILY ===
    family Array(FixedString(20)),                 -- Binary fingerprints
    
    -- === PLATFORM ===
    platform String CODEC(ZSTD(3)),               -- Full platform string
    os_name LowCardinality(String) MATERIALIZED extract(platform, 'on ([^ ]+)'),
    
    -- === UPTIME ===
    uptime_seconds UInt32,
    
    -- === EXIT POLICY ===
    exit_policy_full String CODEC(ZSTD(3)),      -- Complete policy
    
    INDEX idx_fingerprint fingerprint TYPE bloom_filter GRANULARITY 1,
    INDEX idx_published published TYPE minmax GRANULARITY 1
    
) ENGINE = ReplacingMergeTree(published)  -- Latest descriptor wins
PARTITION BY toYYYYMM(published)
ORDER BY descriptor_digest;

-- =====================================================
-- BANDWIDTH SCANNER RESULTS
-- =====================================================
CREATE TABLE bandwidth_measurements (
    measurement_time DateTime,
    fingerprint FixedString(20),
    
    -- Scanner results
    scanner_node LowCardinality(String),          -- Which scanner
    bw UInt32,                                    -- Measured bandwidth
    bw_mean UInt32,
    bw_median UInt32,
    
    -- Consensus context
    consensus_bandwidth UInt32,
    consensus_bandwidth_is_unmeasured UInt8,
    
    -- Descriptor values at measurement time
    desc_bw_avg UInt64,
    desc_bw_burst UInt64,
    desc_bw_observed_last UInt64,
    desc_bw_observed_mean UInt64,
    
    -- Measurement quality
    error_stream UInt8,
    error_circ UInt8,
    error_misc UInt8,
    success UInt8,
    
    -- Scanner metadata
    relay_recent_measurement_attempt_count UInt8,
    relay_recent_priority_list_count UInt8,
    
    INDEX idx_fingerprint fingerprint TYPE bloom_filter GRANULARITY 4
    
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(measurement_time)
ORDER BY (fingerprint, measurement_time)
TTL measurement_time + INTERVAL 1 YEAR;

-- =====================================================
-- EXTRA INFO STATISTICS
-- =====================================================
CREATE TABLE relay_extra_info (
    published DateTime,
    fingerprint FixedString(20),
    
    -- Bandwidth history (last values from arrays)
    write_bytes_last_day UInt64,
    read_bytes_last_day UInt64,
    
    -- Directory request stats
    dirreq_v3_ips Map(String, UInt32),           -- By country
    dirreq_v3_reqs Map(String, UInt32),          -- By country
    
    -- Response stats
    dirreq_v3_resp_ok UInt32,
    dirreq_v3_resp_not_enough_sigs UInt32,
    dirreq_v3_resp_unavailable UInt32,
    dirreq_v3_resp_not_found UInt32,
    dirreq_v3_resp_not_modified UInt32,
    dirreq_v3_resp_busy UInt32,
    
    -- Padding stats
    padding_enabled_read_total UInt64,
    padding_enabled_write_total UInt64,
    
    INDEX idx_fingerprint fingerprint TYPE bloom_filter GRANULARITY 1
    
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(published)
ORDER BY (fingerprint, published)
TTL published + INTERVAL 6 MONTHS;

-- =====================================================
-- MATERIALIZED VIEWS FOR COMMON QUERIES
-- =====================================================

-- Network-wide statistics per hour
CREATE MATERIALIZED VIEW network_stats_hourly
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(measurement_hour)
ORDER BY measurement_hour
AS SELECT
    measurement_hour,
    count() as total_relays,
    countIf(flag_exit) as exit_count,
    countIf(flag_guard) as guard_count,
    sum(consensus_weight) as total_consensus_weight,
    countDistinct(country_code) as unique_countries,
    countDistinct(as_number) as unique_as_count,
    countDistinct(version) as unique_versions,
    
    -- Authority agreement metrics
    avg(measured_by_count) as avg_measured_by_authorities,
    
    -- Per-flag relay counts
    sumIf(1, flag_running) as running_count,
    sumIf(1, flag_stable) as stable_count,
    sumIf(1, flag_fast) as fast_count,
    sumIf(1, flag_hsdir) as hsdir_count,
    sumIf(1, flag_v2dir) as v2dir_count
    
FROM relay_measurements
GROUP BY measurement_hour;

-- Per-relay lifecycle tracking
CREATE MATERIALIZED VIEW relay_lifecycle
ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(first_seen_date)
ORDER BY (fingerprint, first_seen_date)
AS SELECT
    fingerprint,
    toDate(min(measurement_hour)) as first_seen_date,
    min(measurement_hour) as first_seen,
    max(measurement_hour) as last_seen,
    
    -- Nickname history
    groupUniqArray(nickname) as nicknames_used,
    
    -- IP changes
    groupUniqArray(ipv4) as ipv4_addresses,
    countDistinct(ipv4) as ip_change_count,
    
    -- Consensus weight stats
    avg(consensus_weight) as avg_consensus_weight,
    max(consensus_weight) as max_consensus_weight,
    
    -- Flag persistence
    sum(flag_guard) / count() as guard_fraction,
    sum(flag_exit) / count() as exit_fraction,
    sum(flag_stable) / count() as stable_fraction,
    sum(flag_running) / count() as running_fraction,
    
    -- Total measurements
    count() as measurement_count
    
FROM relay_measurements
GROUP BY fingerprint;

-- =====================================================
-- HELPER FUNCTIONS
-- =====================================================

-- Convert binary fingerprint to hex for display
CREATE FUNCTION fingerprint_to_hex AS (fp) -> hex(fp);

-- Convert hex to binary for lookups
CREATE FUNCTION hex_to_fingerprint AS (h) -> unhex(h);

-- Decode flag bitmap to array
CREATE FUNCTION decode_flags AS (bitmap) -> 
    arrayFilter(x -> x.2, [
        ('Exit', bitTest(bitmap, 0)),
        ('Fast', bitTest(bitmap, 1)),
        ('Guard', bitTest(bitmap, 2)),
        ('HSDir', bitTest(bitmap, 3)),
        ('Running', bitTest(bitmap, 4)),
        ('Stable', bitTest(bitmap, 5)),
        ('V2Dir', bitTest(bitmap, 6)),
        ('Valid', bitTest(bitmap, 7))
    ]);
```

## Query Examples Using This Schema

### 1. Relay History with Authority Disagreements
```sql
SELECT 
    measurement_hour,
    nickname,
    consensus_weight,
    decode_flags(consensus_flags) as consensus_flags,
    -- Show bandwidth measurement variance
    arrayFilter(x -> x > 0, [
        bw_measured_moria1,
        bw_measured_gabelmoo,
        bw_measured_dannenberg,
        bw_measured_maatuska,
        bw_measured_faravahar,
        bw_measured_longclaw,
        bw_measured_bastet
    ]) as authority_measurements,
    -- Count flag disagreements
    countDistinct([
        flags_moria1,
        flags_gabelmoo,
        flags_dannenberg,
        flags_maatuska,
        flags_faravahar,
        flags_longclaw,
        flags_bastet
    ]) as flag_disagreement_count
FROM relay_measurements
WHERE fingerprint = hex_to_fingerprint('3D0D3172FA0C11AC7206883832F65BB8695CB1DF')
ORDER BY measurement_hour DESC
LIMIT 24;  -- Last 24 hours
```

### 2. Network Health by Authority Agreement
```sql
WITH authority_agreement AS (
    SELECT 
        measurement_hour,
        fingerprint,
        -- Calculate agreement score
        (8 - countDistinct([
            flags_moria1, flags_tor26, flags_dizum, flags_gabelmoo,
            flags_dannenberg, flags_maatuska, flags_faravahar, flags_longclaw
        ])) / 8.0 as agreement_score
    FROM relay_measurements
    WHERE measurement_hour >= now() - INTERVAL 1 DAY
)
SELECT 
    measurement_hour,
    avg(agreement_score) as avg_authority_agreement,
    countIf(agreement_score < 0.75) as relays_with_disagreement,
    count() as total_relays
FROM authority_agreement
GROUP BY measurement_hour
ORDER BY measurement_hour;
```

### 3. Operator Performance Over Time
```sql
SELECT 
    d.contact,
    toStartOfDay(m.measurement_hour) as day,
    count(DISTINCT m.fingerprint) as relay_count,
    sum(m.consensus_weight) as total_consensus_weight,
    avg(m.consensus_weight) as avg_consensus_weight,
    countDistinct(m.country_code) as countries,
    countDistinct(m.as_number) as autonomous_systems
FROM relay_measurements m
INNER JOIN relay_descriptors d ON m.descriptor_digest = d.descriptor_digest
WHERE 
    d.contact LIKE '%tor[]1aeo.com%'
    AND m.measurement_hour >= now() - INTERVAL 30 DAY
GROUP BY d.contact, day
ORDER BY day DESC;
```

### 4. Authority-Specific Analysis
```sql
-- Compare how different authorities view the network
SELECT 
    'moria1' as authority,
    countIf(bitTest(flags_moria1, 2)) as guard_count,
    countIf(bitTest(flags_moria1, 0)) as exit_count,
    avg(bw_measured_moria1) as avg_measured_bw
FROM relay_measurements
WHERE measurement_hour = toStartOfHour(now())
UNION ALL
SELECT 
    'gabelmoo' as authority,
    countIf(bitTest(flags_gabelmoo, 2)) as guard_count,
    countIf(bitTest(flags_gabelmoo, 0)) as exit_count,
    avg(bw_measured_gabelmoo) as avg_measured_bw
FROM relay_measurements
WHERE measurement_hour = toStartOfHour(now());
```

## Performance Optimizations

### 1. Bitmap Encoding for Flags
- 32 flags fit in a UInt32 (we use ~15 flags)
- Materialized columns for commonly queried flags
- 90% space reduction vs string arrays

### 2. Binary Fingerprints
- 20 bytes vs 40 bytes (hex) = 50% reduction
- Faster comparisons and joins
- Helper functions for conversion

### 3. Separate Descriptor Table
- Eliminates redundancy (descriptors change ~daily, consensus hourly)
- Reduces main table size by ~40%
- Faster ingestion

### 4. Optimized Data Types
- LowCardinality for repeated strings
- FixedString for known-length fields
- Enum8 for version status

### 5. Strategic Materialized Views
- Pre-aggregated network stats
- Relay lifecycle tracking
- Eliminates expensive GROUP BY queries

## Storage Estimates

For 9,000 relays measured hourly:
- **Main table**: ~180 bytes/row × 9,000 × 24 × 365 = ~14 GB/year (compressed)
- **Descriptors**: ~1 KB/descriptor × 9,000 × 365 = ~3 GB/year (compressed)
- **Bandwidth measurements**: ~100 bytes/measurement × 9,000 × 24 × 365 = ~8 GB/year
- **Total**: ~25 GB/year compressed (from ~250 GB raw)

## Conclusion

This schema design optimizes for:
1. **Query performance** - Denormalized design with materialized columns
2. **Storage efficiency** - Binary encoding, compression, appropriate data types
3. **Flexibility** - Captures all authority opinions while maintaining consensus
4. **Maintainability** - Clear separation of concerns, immutable design
5. **Scalability** - Efficient partitioning and TTL management

The hybrid approach balances the benefits of both wide tables (query performance) and normalized design (storage efficiency) while maintaining the complete authority voting record.