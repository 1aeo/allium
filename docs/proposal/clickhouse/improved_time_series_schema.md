# Improved Time-Series ClickHouse Schema for Tor Metrics

Based on analysis of real Tor descriptor data from June 28, 2025.

## Core Time-Series Tables

### 1. Relay Status Time Series (Main Table)

This is the primary time-series table that captures every relay's state at each consensus interval (hourly).

```sql
CREATE TABLE relay_status_series
(
    -- Time dimensions
    consensus_time DateTime,
    valid_after DateTime,
    fresh_until DateTime,
    valid_until DateTime,
    
    -- Relay identifiers
    fingerprint FixedString(40),
    nickname String,
    digest FixedString(40),  -- From consensus descriptor digest
    
    -- Network location (changes tracked over time)
    ip IPv4,
    or_port UInt16,
    dir_port UInt16,
    
    -- Consensus flags array (what the network agreed on)
    consensus_flags Array(String),  -- [Fast, Guard, HSDir, Running, Stable, V2Dir, Valid, Exit, etc.]
    
    -- Bandwidth and weights
    consensus_weight UInt32,        -- From 'w Bandwidth=' line
    
    -- Version info
    version String,                 -- e.g., "Tor 0.4.8.16"
    
    -- Protocol support
    protocols Map(String, String),  -- From 'pr' line: {Conflux: "1", Cons: "1-2", etc.}
    
    -- Exit policy summary (null for non-exit relays)
    exit_policy_summary String,     -- From 'p' line
    
    -- Relay restart detection
    published_time DateTime,        -- From 'r' line, helps detect restarts
    
    INDEX idx_fingerprint fingerprint TYPE bloom_filter GRANULARITY 1,
    INDEX idx_nickname nickname TYPE bloom_filter GRANULARITY 1,
    INDEX idx_flags consensus_flags TYPE bloom_filter GRANULARITY 1
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(consensus_time)
ORDER BY (consensus_time, fingerprint)
TTL consensus_time + INTERVAL 5 YEAR;
```

### 2. Per-Authority Measurements Table

Captures how each directory authority views each relay (votes before consensus).

```sql
CREATE TABLE authority_measurements
(
    consensus_time DateTime,
    authority_nickname String,      -- dannenberg, longclaw, bastet, etc.
    authority_fingerprint FixedString(40),
    
    relay_fingerprint FixedString(40),
    
    -- Authority-specific flags
    flags Array(String),
    
    -- Authority-specific measurements
    measured_bandwidth UInt64,      -- If this authority measured it
    unmeasured UInt8,              -- Flag if authority didn't measure
    
    INDEX idx_relay relay_fingerprint TYPE bloom_filter GRANULARITY 1
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(consensus_time)
ORDER BY (consensus_time, authority_nickname, relay_fingerprint)
TTL consensus_time + INTERVAL 2 YEAR;
```

### 3. Bandwidth Authority Measurements

Detailed bandwidth measurements from bandwidth authorities.

```sql
CREATE TABLE bandwidth_measurements
(
    measurement_time DateTime,
    
    relay_fingerprint FixedString(40),
    relay_nickname String,
    
    -- Bandwidth authority scanner results
    measured_bw UInt64,             -- Measured bandwidth in KB/s
    scanner String,                 -- Which scanner measured it
    
    -- Additional measurement metadata when available
    error_stream UInt8,             -- Had errors during measurement
    error_circ UInt8,               -- Circuit errors
    error_misc UInt8,               -- Other errors
    
    INDEX idx_relay relay_fingerprint TYPE bloom_filter GRANULARITY 1
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(measurement_time)
ORDER BY (measurement_time, relay_fingerprint)
TTL measurement_time + INTERVAL 1 YEAR;
```

### 4. Relay Descriptor Details

Extended relay information from server descriptors (published less frequently than consensus).

```sql
CREATE TABLE relay_descriptors
(
    published_time DateTime,
    
    fingerprint FixedString(40),
    
    -- Detailed bandwidth info from descriptor
    bandwidth_rate UInt64,          -- bytes/sec
    bandwidth_burst UInt64,         -- bytes/sec
    bandwidth_observed UInt64,      -- bytes/sec
    
    -- Platform details
    platform String,                -- e.g., "Tor 0.4.8.16 on Linux"
    os_name String,                 -- Extracted: Linux, Windows, etc.
    os_version String,              -- Extracted version
    tor_version String,             -- Extracted Tor version
    
    -- Contact and operator info
    contact String,
    
    -- Family declaration
    family Array(String),           -- Other relays in same family
    
    -- Uptime tracking
    uptime UInt64,                  -- Seconds since last restart
    
    -- Hibernation status
    hibernating UInt8,
    
    -- Full exit policy (detailed)
    exit_policy Array(String),
    
    -- Bridge distribution (if bridge)
    bridge_distribution String,
    
    INDEX idx_fingerprint fingerprint TYPE bloom_filter GRANULARITY 1,
    INDEX idx_contact contact TYPE bloom_filter GRANULARITY 1
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(published_time)
ORDER BY (published_time, fingerprint)
TTL published_time + INTERVAL 3 YEAR;
```

### 5. Extra Info Statistics

Statistical data from extra-info descriptors.

```sql
CREATE TABLE relay_extra_info
(
    published_time DateTime,
    
    fingerprint FixedString(40),
    
    -- Connection statistics
    conn_bi_direct_stats Map(String, UInt64),  -- Bidirectional connection stats
    
    -- Directory request stats by country
    dirreq_v3_ips Map(String, UInt32),        -- {us: 1024, de: 512, ...}
    dirreq_v3_reqs Map(String, UInt32),       -- Directory requests by country
    
    -- Bridge stats (if applicable)
    bridge_ips Map(String, UInt32),           -- Bridge users by country
    
    -- Cell statistics
    cell_processed_cells UInt64,
    cell_queued_cells UInt64,
    cell_time_in_queue UInt32,
    
    -- Padding statistics
    padding_counts Map(String, UInt64),
    
    -- Exit statistics (if exit)
    exit_kibibytes_written Map(UInt16, UInt64),  -- By port
    exit_kibibytes_read Map(UInt16, UInt64),     -- By port
    exit_streams_opened Map(UInt16, UInt64),     -- By port
    
    INDEX idx_fingerprint fingerprint TYPE bloom_filter GRANULARITY 1
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(published_time)
ORDER BY (published_time, fingerprint)
TTL published_time + INTERVAL 1 YEAR;
```

### 6. GeoIP Enrichment Table

Separate table for IP geolocation data (updated independently).

```sql
CREATE TABLE geoip_data
(
    ip_start IPv4,
    ip_end IPv4,
    
    country_code FixedString(2),
    country_name String,
    
    as_number UInt32,
    as_name String,
    
    city String,
    region String,
    latitude Float32,
    longitude Float32,
    
    -- Geopolitical metadata
    is_eu UInt8,
    internet_freedom_score Float32,  -- External data source
    
    date_updated Date
)
ENGINE = MergeTree()
ORDER BY (ip_start, ip_end)
SETTINGS index_granularity = 8192;
```

## Materialized Views for Efficient Queries

### 1. Relay Lifecycle View

Tracks first seen, last seen, restarts, and IP changes.

```sql
CREATE MATERIALIZED VIEW relay_lifecycle
ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (fingerprint, date)
AS SELECT
    toDate(consensus_time) as date,
    fingerprint,
    
    -- Lifecycle tracking
    min(consensus_time) as first_seen_today,
    max(consensus_time) as last_seen_today,
    
    -- Nickname changes
    groupUniqArray(nickname) as nicknames_used,
    
    -- IP/Port changes
    groupUniqArray(tuple(ip, or_port)) as ip_port_combinations,
    countDistinct(ip) as unique_ips,
    
    -- Restart detection (new published time)
    groupUniqArray(published_time) as published_times,
    count(DISTINCT published_time) as restart_count,
    
    -- Consensus weight stats
    avg(consensus_weight) as avg_consensus_weight,
    max(consensus_weight) as max_consensus_weight,
    min(consensus_weight) as min_consensus_weight,
    
    -- Flag stability
    sumMap(arrayMap(x -> tuple(x, 1), consensus_flags)) as flag_hours,
    count() as total_consensuses
FROM relay_status_series
GROUP BY date, fingerprint;
```

### 2. Network Health Metrics

Aggregated network-wide statistics.

```sql
CREATE MATERIALIZED VIEW network_health_hourly
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(consensus_time)
ORDER BY consensus_time
AS SELECT
    consensus_time,
    
    -- Relay counts
    count() as total_relays,
    countIf(has(consensus_flags, 'Exit')) as exit_relays,
    countIf(has(consensus_flags, 'Guard')) as guard_relays,
    countIf(has(consensus_flags, 'Fast')) as fast_relays,
    countIf(has(consensus_flags, 'Stable')) as stable_relays,
    
    -- Bandwidth metrics
    sum(consensus_weight) as total_consensus_weight,
    avg(consensus_weight) as avg_consensus_weight,
    quantile(0.5)(consensus_weight) as median_consensus_weight,
    
    -- Version distribution
    countDistinct(version) as unique_versions,
    
    -- Geographic distribution
    countDistinct(ip) as unique_ips,
    
    -- IPv6 support (would need additional field)
    -- countIf(ipv6_orport != '') as ipv6_relays,
    
    -- Platform diversity
    countDistinct(extract(version, 'on (.+)$')) as unique_platforms
FROM relay_status_series
GROUP BY consensus_time;
```

### 3. Operator Analytics

Aggregated by contact information.

```sql
CREATE MATERIALIZED VIEW operator_metrics_daily
ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (date, contact_hash)
AS SELECT
    toDate(published_time) as date,
    cityHash64(contact) as contact_hash,  -- Privacy protection
    contact,
    
    -- Relay operations
    countDistinct(fingerprint) as relay_count,
    
    -- Bandwidth contribution
    sum(bandwidth_observed) as total_bandwidth,
    
    -- Geographic diversity
    countDistinct(extract(platform, 'on (.+)$')) as platform_diversity,
    groupUniqArray(fingerprint) as relay_fingerprints,
    
    -- Family consistency
    arrayDistinct(arrayFlatten(groupArray(family))) as declared_family
FROM relay_descriptors
WHERE contact != ''
GROUP BY date, contact_hash, contact;
```

### 4. AS-Level Aggregation

Network diversity by autonomous system.

```sql
CREATE MATERIALIZED VIEW as_metrics_daily
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (date, as_number)
AS SELECT
    toDate(r.consensus_time) as date,
    g.as_number,
    g.as_name,
    
    countDistinct(r.fingerprint) as relay_count,
    sum(r.consensus_weight) as total_consensus_weight,
    
    -- Flag distribution in AS
    countIf(has(r.consensus_flags, 'Exit')) as exit_count,
    countIf(has(r.consensus_flags, 'Guard')) as guard_count,
    
    -- Concentration risk
    sum(r.consensus_weight) / (SELECT sum(consensus_weight) 
                               FROM relay_status_series 
                               WHERE toDate(consensus_time) = date) as network_fraction
FROM relay_status_series r
LEFT JOIN geoip_data g ON r.ip >= g.ip_start AND r.ip <= g.ip_end
GROUP BY date, as_number, as_name;
```

### 5. Country-Level Metrics

Geographic distribution and trends.

```sql
CREATE MATERIALIZED VIEW country_metrics_daily
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (date, country_code)
AS SELECT
    toDate(r.consensus_time) as date,
    g.country_code,
    g.country_name,
    
    countDistinct(r.fingerprint) as relay_count,
    sum(r.consensus_weight) as total_consensus_weight,
    
    -- Operators in country
    countDistinct(d.contact) as unique_operators,
    
    -- Network diversity
    countDistinct(g.as_number) as unique_as_count,
    
    -- Relay types
    countIf(has(r.consensus_flags, 'Exit')) as exit_count,
    countIf(has(r.consensus_flags, 'Guard')) as guard_count,
    
    -- Average metrics
    avg(r.consensus_weight) as avg_relay_weight
FROM relay_status_series r
LEFT JOIN geoip_data g ON r.ip >= g.ip_start AND r.ip <= g.ip_end
LEFT JOIN relay_descriptors d ON r.fingerprint = d.fingerprint 
    AND r.published_time = d.published_time
GROUP BY date, country_code, country_name;
```

## Query Examples

### 1. Relay History Timeline
```sql
-- Get complete history for a specific relay
SELECT 
    consensus_time,
    nickname,
    consensus_flags,
    consensus_weight,
    concat(toString(ip), ':', toString(or_port)) as address
FROM relay_status_series
WHERE fingerprint = 'AAoQ1DAR6kkoo19hBAX5K0QztNw'
ORDER BY consensus_time DESC
LIMIT 1000;
```

### 2. Network Growth Over Time
```sql
-- Monthly network growth statistics
SELECT
    toStartOfMonth(consensus_time) as month,
    avg(total_relays) as avg_relay_count,
    avg(total_consensus_weight) as avg_network_capacity,
    avg(exit_relays) as avg_exit_count,
    avg(guard_relays) as avg_guard_count
FROM network_health_hourly
WHERE consensus_time >= now() - INTERVAL 1 YEAR
GROUP BY month
ORDER BY month;
```

### 3. Operator Ranking by Consensus Weight
```sql
-- Top operators by total consensus weight contribution
SELECT
    contact,
    sum(relay_count) as total_relays,
    sum(total_bandwidth) as total_bandwidth_contributed,
    count(DISTINCT date) as days_active
FROM operator_metrics_daily
WHERE date >= today() - INTERVAL 30 DAY
GROUP BY contact
ORDER BY total_bandwidth_contributed DESC
LIMIT 100;
```

### 4. Geographic Diversity Trends
```sql
-- Country diversity over time
SELECT
    date,
    count() as countries_with_relays,
    sum(relay_count) as total_relays,
    max(relay_count) as max_relays_per_country,
    entropy(relay_count) as geographic_entropy
FROM country_metrics_daily
WHERE date >= today() - INTERVAL 90 DAY
GROUP BY date
ORDER BY date;
```

### 5. Relay Uptime and Stability
```sql
-- Find most stable relays
WITH relay_availability AS (
    SELECT
        fingerprint,
        countIf(has(consensus_flags, 'Running')) / count() as uptime_fraction,
        countIf(has(consensus_flags, 'Stable')) / countIf(has(consensus_flags, 'Running')) as stable_fraction,
        count() as measurements
    FROM relay_status_series
    WHERE consensus_time >= now() - INTERVAL 30 DAY
    GROUP BY fingerprint
    HAVING measurements > 24 * 25  -- At least 25 days of data
)
SELECT
    r.fingerprint,
    any(r.nickname) as nickname,
    uptime_fraction,
    stable_fraction,
    measurements
FROM relay_availability r
ORDER BY uptime_fraction DESC, stable_fraction DESC
LIMIT 100;
```

## Performance Optimizations

1. **Compression**: Use ZSTD compression for string fields and LZ4 for numeric fields
2. **Sampling**: For very old data, consider sampling strategies
3. **Projection**: Create projections for common query patterns
4. **Dictionary Encoding**: Use LowCardinality for repeated strings like version, flags

```sql
-- Optimize the main table
ALTER TABLE relay_status_series
    MODIFY COLUMN nickname LowCardinality(String),
    MODIFY COLUMN version LowCardinality(String),
    MODIFY COLUMN consensus_flags Array(LowCardinality(String));
```

## Data Retention Policy

- **relay_status_series**: 5 years (full detail)
- **authority_measurements**: 2 years
- **bandwidth_measurements**: 1 year
- **relay_descriptors**: 3 years
- **relay_extra_info**: 1 year
- **Materialized views**: Indefinite (aggregated data)

## Missing Data Handling

Based on the analysis, some data that would be valuable but isn't available in current descriptors:
- **IPv6 ORPort**: Not in consensus format (would need server descriptors)
- **Detailed bandwidth authority data**: Only aggregated measurements available
- **Historical exit policies**: Only summary in consensus

These limitations are noted, and the schema works with actually available data.