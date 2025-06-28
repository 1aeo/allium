# ClickHouse Historical Analytics Proposal for Allium
*Enhancing Tor Relay Analytics with Time-Series Intelligence*

## Executive Summary

This proposal outlines a comprehensive strategy to integrate ClickHouse database with the allium Tor relay analytics platform to provide historical data analysis, trend visualization, pattern recognition, and anomaly detection. By ingesting CollecTor consensus weight files from 2007 to June 2025, we can create a powerful historical analytics engine that significantly enhances the current real-time monitoring capabilities.

## 📊 Current State Analysis

### Existing Allium Capabilities
- **Real-time analytics** from Onionoo API (refreshed every 30 minutes)
- **12 AROI leaderboard categories** with current rankings
- **Network health dashboard** with instant metrics
- **Static analysis** of current relay states
- **Geographic and platform diversity** analysis
- **Bandwidth and consensus weight** current measurements

### Current Limitations
- **No historical trending** - only current snapshots
- **No pattern analysis** over time
- **No anomaly detection** capabilities
- **Limited time-series data** (only basic uptime from Onionoo)
- **No historical leaderboards** or ranking changes
- **No bandwidth evolution** tracking
- **No seasonal pattern** recognition

## 🎯 ClickHouse Integration Strategy

### Data Ingestion Architecture

#### Primary Data Sources
1. **CollecTor Consensus Archives** (2007-2025)
   - Hourly consensus documents with complete relay state snapshots
   - ~1.3 billion individual relay measurements across 18 years
   - Relay fingerprints, bandwidth, consensus weights, flags, geographic data
   - Platform information, contact details, family relationships
   - Complete audit trail of network evolution

2. **Onionoo API Integration** (Real-time)
   - Live relay data refreshed every 30 minutes
   - Current uptime statistics and performance metrics  
   - Active relay status and recent changes
   - Seamless integration with historical data via shared fingerprint keys

#### TSDB Design Philosophy
- **Single wide table**: Each row = complete relay observation at point in time
- **No joins required**: All related data denormalized for query performance
- **Time-partitioned**: Monthly partitions for optimal data lifecycle management
- **Column-optimized**: Custom data types and compression for storage efficiency
- **Materialized views**: Pre-computed aggregations for instant dashboard queries

#### ClickHouse Schema Design Based on Real CollecTor Data

```sql
-- Custom data types for optimal storage and performance
CREATE TYPE IF NOT EXISTS RelayFingerprint AS FixedString(20);    -- 20 bytes for SHA-1 binary
CREATE TYPE IF NOT EXISTS Ed25519Key AS FixedString(32);          -- 32 bytes for Ed25519 keys
CREATE TYPE IF NOT EXISTS ContactHash AS FixedString(16);         -- 16 bytes for MD5 binary
CREATE TYPE IF NOT EXISTS DescriptorDigest AS FixedString(20);    -- 20 bytes for descriptor hash

-- Core relay measurements table - each row is a complete relay state observation from consensus
CREATE TABLE relay_measurements (
    -- === TEMPORAL IDENTIFICATION ===
    measurement_time DateTime64(3),                               -- When this measurement was taken
    consensus_valid_after DateTime,                               -- Consensus document timestamp
    consensus_fresh_until DateTime,                               -- When consensus expires
    consensus_method UInt8,                                       -- Consensus method used
    
    -- === RELAY IDENTIFICATION ===
    relay_fingerprint RelayFingerprint,                           -- RSA identity key fingerprint (binary)
    relay_ed25519_key Ed25519Key,                                 -- Ed25519 master identity key
    relay_nickname LowCardinality(String),                        -- Current nickname in this consensus
    descriptor_digest DescriptorDigest,                           -- Hash of server descriptor
    descriptor_published DateTime,                                -- When server descriptor was published
    
    -- === NETWORK CONNECTIVITY ===
    ipv4_address IPv4,                                           -- Primary IPv4 address
    ipv6_address Nullable(IPv6),                                 -- IPv6 address if available
    or_port UInt16,                                              -- Onion Router port
    dir_port UInt16,                                             -- Directory port (0 if none)
    or_addresses Array(String),                                  -- Additional OR addresses from descriptor
    
    -- === BANDWIDTH MEASUREMENTS ===
    -- From server descriptor
    bandwidth_rate UInt64,                                       -- Sustained rate (bytes/sec)
    bandwidth_burst UInt64,                                      -- Burst capacity (bytes/sec)  
    bandwidth_observed UInt64,                                   -- Observed bandwidth (bytes/sec)
    bandwidth_advertised UInt64,                                 -- Advertised bandwidth (bytes/sec)
    
    -- From consensus (bandwidth authorities measurements)
    bandwidth_measured UInt64,                                   -- Measured by bandwidth authorities
    bandwidth_unmeasured UInt8,                                  -- 1 if not measured by >=3 authorities
    bandwidth_shared UInt64,                                     -- Shared bandwidth in consensus
    
    -- === CONSENSUS PARTICIPATION ===
    consensus_weight UInt64,                                     -- Raw consensus weight value
    consensus_weight_fraction Float64,                           -- Fraction of total network CW
    measured_by_authorities UInt8,                               -- Number of authorities that measured
    
    -- Guard/Middle/Exit probabilities from consensus
    guard_probability Float64,                                   -- Probability as guard
    middle_probability Float64,                                  -- Probability as middle
    exit_probability Float64,                                    -- Probability as exit
    
    -- === DIRECTORY AUTHORITY FLAGS (per authority + consensus) ===
    -- Consensus flags (final agreed flags)
    flag_authority UInt8,
    flag_bad_exit UInt8,
    flag_exit UInt8,
    flag_fast UInt8,
    flag_guard UInt8,
    flag_hsdir UInt8,
    flag_named UInt8,
    flag_running UInt8,
    flag_stable UInt8,
    flag_unnamed UInt8,
    flag_valid UInt8,
    flag_v2dir UInt8,
    flag_sybil UInt8,
    flag_stable_desc UInt8,
    flag_middle_only UInt8,
    
    -- Per-authority flags (array of 9 authorities, each UInt16 bitmap)
    authority_flags Array(UInt16),                               -- Flags per authority for analysis
    authority_count UInt8,                                       -- Number of authorities that voted
    
    -- === PERFORMANCE METRICS ===
    -- Relay lifecycle
    first_seen DateTime,                                          -- First appearance in consensus
    last_restarted Nullable(DateTime),                           -- Last restart timestamp
    last_changed_address Nullable(DateTime),                     -- Last IP address change
    uptime_seconds Nullable(UInt32),                            -- Uptime in seconds
    
    -- Historical reliability (from Onionoo-style data)
    uptime_1_month Nullable(Float32),                           -- 1-month uptime percentage
    uptime_3_months Nullable(Float32),                          -- 3-month uptime percentage  
    uptime_1_year Nullable(Float32),                            -- 1-year uptime percentage
    uptime_5_years Nullable(Float32),                           -- 5-year uptime percentage
    
    -- === GEOGRAPHIC & NETWORK CLASSIFICATION ===
    country_code FixedString(2),                                -- ISO country code
    country_name LowCardinality(String),                        -- Full country name
    as_number UInt32,                                           -- Autonomous System number
    as_name LowCardinality(String),                            -- AS organization name
    as_type LowCardinality(String),                            -- Hosting, ISP, etc.
    
    -- === PLATFORM & SOFTWARE ===
    platform_raw String CODEC(ZSTD),                           -- Full platform string from descriptor
    tor_version LowCardinality(String),                         -- Parsed Tor version
    tor_version_major UInt8,                                    -- Major version (0)
    tor_version_minor UInt8,                                    -- Minor version (4)
    tor_version_micro UInt8,                                    -- Micro version (8)
    operating_system LowCardinality(String),                    -- Linux, Windows, FreeBSD, etc.
    os_version LowCardinality(String),                          -- OS version if parseable
    version_recommended UInt8,                                  -- 1 if recommended, 0 if not
    version_status LowCardinality(String),                      -- "recommended", "obsolete", etc.
    
    -- === CONTACT & OPERATOR INFORMATION ===
    contact_raw String CODEC(ZSTD),                            -- Full contact string
    contact_hash ContactHash,                                   -- MD5 hash for grouping
    contact_aroi LowCardinality(String),                       -- Extracted AROI domain
    contact_email LowCardinality(String),                      -- Extracted email domain
    contact_pgp_key String CODEC(ZSTD),                        -- PGP key if present
    
    -- === FAMILY RELATIONSHIPS ===
    family_declared Array(RelayFingerprint),                    -- Declared family members
    family_effective Array(RelayFingerprint),                   -- Effective family (mutual)
    family_certificate_present UInt8,                           -- 1 if has family certificate
    family_cert_digest Nullable(FixedString(32)),              -- SHA256 of family cert
    
    -- === EXIT POLICY ANALYSIS ===
    exit_policy_raw String CODEC(ZSTD),                        -- Full exit policy
    exit_policy_summary String CODEC(ZSTD),                    -- Compressed summary
    exit_policy_v4_summary String CODEC(ZSTD),                 -- IPv4 summary
    exit_policy_v6_summary String CODEC(ZSTD),                 -- IPv6 summary
    
    -- Quick exit policy flags for common ports
    allows_port_22 UInt8,      -- SSH
    allows_port_53 UInt8,      -- DNS  
    allows_port_80 UInt8,      -- HTTP
    allows_port_110 UInt8,     -- POP3
    allows_port_143 UInt8,     -- IMAP
    allows_port_443 UInt8,     -- HTTPS
    allows_port_993 UInt8,     -- IMAPS
    allows_port_995 UInt8,     -- POP3S
    
    -- Exit policy categories
    is_exit_unrestricted UInt8,                                 -- Allows most ports
    is_exit_web_only UInt8,                                     -- Only 80/443
    is_exit_mail_only UInt8,                                    -- Only mail ports
    has_ipv4_restrictions UInt8,                                -- Has IP restrictions
    has_ipv6_restrictions UInt8,                                -- Has IPv6 restrictions
    
    -- === CRYPTOGRAPHIC KEYS ===
    onion_key_rsa String CODEC(ZSTD),                          -- RSA onion key (deprecated)
    ntor_onion_key FixedString(32),                            -- Curve25519 ntor key
    ed25519_signing_cert String CODEC(ZSTD),                   -- Ed25519 certificate
    
    -- === NETWORK CONTEXT (denormalized for performance) ===
    total_network_consensus_weight UInt64,                      -- Total CW in this consensus
    total_network_bandwidth UInt64,                             -- Total observed bandwidth  
    total_network_relays UInt32,                                -- Total relay count
    network_guard_relays UInt32,                                -- Guard relay count
    network_exit_relays UInt32,                                 -- Exit relay count
    network_unique_countries UInt32,                            -- Countries represented
    network_unique_as_count UInt32,                             -- Unique AS count
    
    -- === DATA PROVENANCE ===
    data_source LowCardinality(String),                         -- "consensus", "descriptor", "onionoo"
    processing_version UInt8,                                   -- Schema version for migrations
    ingestion_time DateTime DEFAULT now()                       -- When row was inserted
    
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(measurement_time) 
ORDER BY (relay_fingerprint, measurement_time)
SETTINGS index_granularity = 8192,
         allow_nullable_key = 1;

-- === MATERIALIZED VIEWS FOR COMMON AGGREGATIONS ===

-- Current relay state (replacing MergeTree with latest data)
CREATE MATERIALIZED VIEW current_relay_state
ENGINE = ReplacingMergeTree(measurement_time)
ORDER BY relay_fingerprint
POPULATE
AS SELECT 
    relay_fingerprint,
    argMax(measurement_time, measurement_time) as last_seen,
    argMax(relay_nickname, measurement_time) as current_nickname,
    argMax(bandwidth_observed, measurement_time) as current_bandwidth,
    argMax(consensus_weight, measurement_time) as current_consensus_weight,
    argMax(flag_running, measurement_time) as is_running,
    argMax(flag_guard, measurement_time) as is_guard,
    argMax(flag_exit, measurement_time) as is_exit,
    argMax(country_code, measurement_time) as current_country,
    argMax(contact_hash, measurement_time) as current_contact_hash,
    argMax(contact_aroi, measurement_time) as current_aroi,
    argMax(tor_version, measurement_time) as current_tor_version,
    argMax(version_recommended, measurement_time) as version_is_recommended
FROM relay_measurements
GROUP BY relay_fingerprint;

-- Hourly network health metrics (for dashboards)
CREATE MATERIALIZED VIEW network_hourly_health
ENGINE = SummingMergeTree()
ORDER BY consensus_hour
POPULATE  
AS SELECT 
    toStartOfHour(consensus_valid_after) as consensus_hour,
    count() as total_relay_observations,
    uniq(relay_fingerprint) as unique_relays,
    
    -- Bandwidth aggregations
    sum(bandwidth_observed) as total_observed_bandwidth,
    sum(bandwidth_measured) as total_measured_bandwidth,
    avg(bandwidth_observed) as avg_observed_bandwidth,
    
    -- Consensus weight aggregations  
    sum(consensus_weight) as total_consensus_weight,
    avg(consensus_weight_fraction) as avg_consensus_weight_fraction,
    
    -- Flag-based counts
    sum(flag_running) as running_relays,
    sum(flag_guard) as guard_relays,
    sum(flag_exit) as exit_relays,
    sum(flag_stable) as stable_relays,
    sum(flag_fast) as fast_relays,
    sum(flag_valid) as valid_relays,
    sum(flag_bad_exit) as bad_exit_relays,
    sum(flag_authority) as authority_relays,
    
    -- Geographic diversity
    uniq(country_code) as unique_countries,
    uniq(as_number) as unique_as_numbers,
    
    -- Platform diversity
    uniq(operating_system) as unique_operating_systems,
    uniq(tor_version) as unique_tor_versions,
    sum(version_recommended) as recommended_version_relays,
    
    -- Exit policy analysis
    sum(allows_port_80) as http_exits,
    sum(allows_port_443) as https_exits,
    sum(is_exit_unrestricted) as unrestricted_exits,
    
    -- Contact/operator metrics
    uniq(contact_hash) as unique_operators,
    uniqIf(contact_hash, contact_aroi != '') as aroi_operators
    
FROM relay_measurements
GROUP BY consensus_hour;

-- Daily operator performance (for AROI leaderboards)
CREATE MATERIALIZED VIEW operator_daily_performance
ENGINE = SummingMergeTree()
ORDER BY (measurement_date, contact_hash)
POPULATE
AS SELECT 
    toDate(consensus_valid_after) as measurement_date,
    contact_hash,
    
    -- Operator identification
    any(contact_aroi) as aroi_domain,
    any(contact_raw) as contact_info,
    
    -- Relay counts and types
    uniq(relay_fingerprint) as relay_count,
    sum(flag_guard) as guard_relay_count,
    sum(flag_exit) as exit_relay_count,
    sum(flag_running) as running_relay_count,
    sum(flag_stable) as stable_relay_count,
    
    -- Performance metrics
    sum(bandwidth_observed) as total_bandwidth,
    sum(consensus_weight) as total_consensus_weight,
    avg(consensus_weight_fraction) as avg_consensus_weight_fraction,
    sum(bandwidth_measured) as total_measured_bandwidth,
    
    -- Diversity metrics
    uniq(country_code) as country_count,
    uniq(as_number) as as_count,
    uniq(operating_system) as platform_count,
    uniq(tor_version) as version_count,
    
    -- Geographic presence
    groupArray(country_code) as countries,
    groupArray(as_number) as as_numbers,
    
    -- Reliability metrics
    avg(uptime_1_month) as avg_uptime_1month,
    avg(uptime_1_year) as avg_uptime_1year,
    min(first_seen) as earliest_first_seen,
    
    -- Exit capabilities
    sum(allows_port_80) as http_exit_count,
    sum(allows_port_443) as https_exit_count,
    sum(is_exit_unrestricted) as unrestricted_exit_count
    
FROM relay_measurements
WHERE contact_hash != unhex('00000000000000000000000000000000')  -- Exclude empty contacts
GROUP BY measurement_date, contact_hash;

-- Daily exit policy analysis
CREATE MATERIALIZED VIEW exit_policy_daily_analysis  
ENGINE = SummingMergeTree()
ORDER BY measurement_date
POPULATE
AS SELECT
    toDate(consensus_valid_after) as measurement_date,
    
    -- Total exit counts
    sum(flag_exit) as total_exits,
    
    -- Port-specific exits
    sum(allows_port_22) as ssh_exits,
    sum(allows_port_53) as dns_exits, 
    sum(allows_port_80) as http_exits,
    sum(allows_port_443) as https_exits,
    sum(allows_port_993) as imaps_exits,
    
    -- Policy categories
    sum(is_exit_unrestricted) as unrestricted_exits,
    sum(is_exit_web_only) as web_only_exits,
    sum(is_exit_mail_only) as mail_only_exits,
    sum(has_ipv4_restrictions) as ipv4_restricted_exits,
    sum(has_ipv6_restrictions) as ipv6_restricted_exits,
    
    -- Geographic distribution of exits
    uniqIf(country_code, flag_exit = 1) as exit_countries,
    uniqIf(as_number, flag_exit = 1) as exit_as_numbers
    
FROM relay_measurements
GROUP BY measurement_date;

-- === INDEXES FOR QUERY OPTIMIZATION ===
CREATE INDEX idx_country_code ON relay_measurements (country_code) TYPE bloom_filter(0.01);
CREATE INDEX idx_as_number ON relay_measurements (as_number) TYPE bloom_filter(0.01);
CREATE INDEX idx_tor_version ON relay_measurements (tor_version) TYPE bloom_filter(0.01);
CREATE INDEX idx_contact_aroi ON relay_measurements (contact_aroi) TYPE bloom_filter(0.01);
CREATE INDEX idx_flags_composite ON relay_measurements (flag_running, flag_guard, flag_exit, flag_stable) TYPE bloom_filter(0.01);

-- === PROJECTIONS FOR TIME-SERIES PERFORMANCE ===
ALTER TABLE relay_measurements ADD PROJECTION daily_bandwidth_projection (
    SELECT 
        toDate(consensus_valid_after) as date,
        relay_fingerprint,
        contact_hash,
        avg(bandwidth_observed) as avg_bandwidth,
        max(bandwidth_observed) as max_bandwidth,
        avg(consensus_weight) as avg_consensus_weight,
        sum(flag_running) as uptime_hours
    GROUP BY date, relay_fingerprint, contact_hash
);

ALTER TABLE relay_measurements ADD PROJECTION operator_performance_projection (
    SELECT
        toStartOfMonth(consensus_valid_after) as month,
        contact_hash,
        contact_aroi,
        uniq(relay_fingerprint) as relay_count,
        sum(bandwidth_observed) as total_bandwidth,
        sum(consensus_weight) as total_consensus_weight,
        uniq(country_code) as country_diversity,
        avg(uptime_1_month) as avg_reliability
    GROUP BY month, contact_hash, contact_aroi
);
```

## 🔧 ClickHouse Schema Design Decisions

### Critical Design Questions & Answers

#### Q1: One Big Table vs Multiple Smaller Tables?
**Answer: One Big Wide Table** ✅

**Reasoning**:
- **Better compression**: Related time-series data compresses better together
- **Fewer JOINs**: Eliminates expensive JOIN operations for analytics
- **Simpler queries**: All relay data available in single table scan
- **Better performance**: ClickHouse optimized for wide tables with columnar storage
- **Atomic consistency**: Each row represents complete relay state at point in time

#### Q2: Immutable per Relay per Time Period or Mutable?
**Answer: Immutable** ✅

**Reasoning**:
- **Perfect for time-series**: Each consensus creates new immutable snapshot
- **Historical integrity**: Can analyze exactly what network looked like at any point
- **No UPDATE complexity**: Only INSERT operations needed
- **Better compression**: Immutable data compresses more efficiently
- **Audit trail**: Complete history preserved for analysis

#### Q3: One Row per Relay per Hour with All Directory Authority Information?
**Answer: Yes, with Hybrid Storage Approach** ✅

**Reasoning**:
- **Single source of truth**: Each row = complete relay state at consensus time
- **Efficient analytics**: Time-series queries don't need complex aggregation
- **Authority analysis**: Can analyze both consensus and per-authority differences

#### Q4: Nested Arrays vs Separate Columns for Directory Authority Data?
**Answer: Hybrid Approach - Consensus Flags as Columns + Authority Data as Structured** ✅

**Reasoning**:
- **Fast filtering**: Individual flag columns (UInt8) for consensus flags
- **Authority analysis**: Structured approach for per-authority data
- **Query efficiency**: Common queries on consensus flags are fastest
- **Detailed analysis**: Authority disagreement analysis still possible

### Optimal Schema Design Based on Real Data

```sql
-- Custom types optimized for Tor data
CREATE TYPE RelayFingerprint AS FixedString(20);     -- SHA-1 binary (40 hex chars / 2)
CREATE TYPE Ed25519Key AS FixedString(32);           -- Ed25519 key binary
CREATE TYPE AuthorityID AS Enum8(
    'moria1' = 1, 'maatuska' = 2, 'gabelmoo' = 3, 'dannenberg' = 4,
    'longclaw' = 5, 'dizum' = 6, 'bastet' = 7, 'faravahar' = 8
);

-- Single wide table capturing complete relay state per consensus
CREATE TABLE relay_consensus_measurements (
    -- === TEMPORAL DIMENSIONS ===
    consensus_time DateTime64(3),                    -- Consensus valid-after timestamp  
    consensus_fresh_until DateTime,                  -- When consensus expires
    consensus_valid_until DateTime,                  -- Hard expiry time
    
    -- === RELAY IDENTIFICATION ===
    fingerprint RelayFingerprint,                    -- RSA identity (binary)
    ed25519_master_key Ed25519Key,                   -- Ed25519 identity (binary)
    nickname LowCardinality(String),                 -- Current nickname
    descriptor_digest FixedString(20),               -- Server descriptor hash
    descriptor_published DateTime,                   -- Descriptor timestamp
    
    -- === NETWORK CONNECTIVITY ===
    ipv4_address IPv4,                               -- Primary IPv4
    ipv6_address Nullable(IPv6),                     -- IPv6 if available
    or_port UInt16,                                  -- OR port (usually 443)
    dir_port UInt16,                                 -- Directory port (0 if none)
    
    -- === CONSENSUS FLAGS (FINAL AGREED) ===
    -- Individual columns for fast filtering (from consensus 's' line)
    flag_fast UInt8,
    flag_guard UInt8, 
    flag_exit UInt8,
    flag_stable UInt8,
    flag_running UInt8,
    flag_valid UInt8,
    flag_hsdir UInt8,
    flag_v2dir UInt8,
    flag_authority UInt8,
    flag_bad_exit UInt8,
    flag_named UInt8,
    flag_unnamed UInt8,
    flag_middle_only UInt8,
    
    -- === BANDWIDTH MEASUREMENTS ===
    -- From consensus 'w' line
    consensus_bandwidth UInt32,                      -- Agreed bandwidth (KB/s)
    consensus_weight UInt64,                         -- Computed consensus weight
    
    -- From bandwidth authority files (when available)
    measured_bandwidth UInt32,                       -- bw= from bandwidth files
    measured_bandwidth_mean UInt64,                  -- bw_mean= (bytes/s)
    measured_bandwidth_median UInt64,                -- bw_median= (bytes/s)
    bandwidth_is_unmeasured UInt8,                   -- From bandwidth authority
    
    -- From server descriptor 'bandwidth' line  
    descriptor_bandwidth_rate UInt64,                -- Sustained rate (bytes/s)
    descriptor_bandwidth_burst UInt64,               -- Burst rate (bytes/s)
    descriptor_bandwidth_observed UInt64,            -- Observed rate (bytes/s)
    
    -- === DIRECTORY AUTHORITY ANALYSIS ===
    -- Per-authority voting data for disagreement analysis
    authority_data Nested(
        authority_id AuthorityID,
        flags Array(LowCardinality(String)),          -- Flags assigned by this authority
        measured_bandwidth UInt32,                    -- This authority's measurement
        has_measurement UInt8,                        -- 1 if authority measured
        voting_weight UInt16                          -- Authority's voting weight
    ),
    
    -- Authority participation metrics
    total_authorities_voting UInt8,                  -- Number of authorities that voted
    authorities_agreeing_running UInt8,             -- How many said Running
    authorities_agreeing_guard UInt8,               -- How many said Guard  
    authorities_agreeing_exit UInt8,                -- How many said Exit
    
    -- === RELAY PERFORMANCE METRICS ===
    -- From server descriptor
    uptime_seconds UInt32,                           -- Uptime from descriptor
    platform LowCardinality(String),                -- Platform string
    tor_version LowCardinality(String),              -- Tor version
    
    -- From bandwidth authority measurements
    bandwidth_measurement_success_rate Float32,      -- Success rate for measurements
    bandwidth_stream_ratio Float32,                  -- r_strm from bandwidth files
    bandwidth_error_rate Float32,                    -- Error ratio
    
    -- === PROTOCOLS & CAPABILITIES ===
    protocols Map(String, String),                   -- From 'pr' line: {Cons: "1-2", ...}
    
    -- === EXIT POLICY ===
    exit_policy_summary String CODEC(ZSTD),         -- From 'p' line (compressed)
    exit_policy_allows_80 UInt8,                    -- Quick HTTP check
    exit_policy_allows_443 UInt8,                   -- Quick HTTPS check
    exit_policy_allows_22 UInt8,                    -- Quick SSH check
    
    -- === CONTACT & OPERATOR ===
    contact_line String CODEC(ZSTD),                -- Full contact string
    contact_email_domain LowCardinality(String),    -- Extracted email domain
    contact_aroi LowCardinality(String),            -- AROI operator identifier
    
    -- === FAMILY RELATIONSHIPS ===
    family_fingerprints Array(RelayFingerprint),    -- Declared family members
    family_count UInt16,                            -- Number of family members
    
    -- === GEOGRAPHIC & NETWORK ===
    country_code FixedString(2),                    -- ISO country code  
    asn UInt32,                                     -- Autonomous System Number
    as_organization LowCardinality(String),         -- AS organization name
    
    -- === TRAFFIC STATISTICS (from extra-info) ===
    -- Only latest values to avoid huge arrays
    read_bytes_last_hour UInt64,                    -- Most recent read-history value
    write_bytes_last_hour UInt64,                   -- Most recent write-history value
    dirreq_read_last_hour UInt64,                   -- Directory request read
    dirreq_write_last_hour UInt64,                  -- Directory request write
    
    -- Hidden service statistics (privacy-safe aggregated values)
    hidserv_v3_cells_relayed UInt64,               -- V3 onion service cells
    hidserv_v3_onions_seen UInt32,                 -- V3 onions seen (privacy safe)
    
    -- === NETWORK CONTEXT ===
    total_consensus_weight_network UInt64,          -- Total network consensus weight
    total_relays_network UInt32,                   -- Total relays in consensus
    total_guard_relays_network UInt32,             -- Total guard relays
    total_exit_relays_network UInt32,              -- Total exit relays
    
    -- === METADATA ===
    processing_timestamp DateTime DEFAULT now(),    -- When row was created
    data_completeness_score UInt8                   -- 0-100 based on available data sources

) ENGINE = MergeTree()
PARTITION BY toYYYYMM(consensus_time)
ORDER BY (fingerprint, consensus_time)
SETTINGS 
    index_granularity = 8192,
    allow_nullable_key = 1;

-- Indexes for common query patterns
CREATE INDEX idx_flags ON relay_consensus_measurements 
    (flag_running, flag_guard, flag_exit, flag_stable) TYPE bloom_filter(0.01);
    
CREATE INDEX idx_operator ON relay_consensus_measurements 
    (contact_aroi) TYPE bloom_filter(0.01);
    
CREATE INDEX idx_network ON relay_consensus_measurements 
    (country_code, asn) TYPE bloom_filter(0.01);

-- Materialized view for authority disagreement analysis
CREATE MATERIALIZED VIEW authority_disagreement_analysis
ENGINE = SummingMergeTree()
ORDER BY (consensus_time, fingerprint)
AS SELECT
    consensus_time,
    fingerprint,
    nickname,
    
    -- Flag disagreement metrics
    abs(toInt16(authorities_agreeing_running) - toInt16(total_authorities_voting * flag_running)) as running_disagreement,
    abs(toInt16(authorities_agreeing_guard) - toInt16(total_authorities_voting * flag_guard)) as guard_disagreement,
    abs(toInt16(authorities_agreeing_exit) - toInt16(total_authorities_voting * flag_exit)) as exit_disagreement,
    
    -- Bandwidth measurement variance
    arrayReduce('stddevPop', authority_data.measured_bandwidth) as bandwidth_measurement_variance,
    length(authority_data.authority_id) as authorities_measured_bandwidth,
    
    contact_aroi
FROM relay_consensus_measurements
WHERE total_authorities_voting >= 6;  -- Only when most authorities voted
```

### Key Design Decisions Explained

#### 1. **Authority Data Storage Strategy**
- **Consensus flags**: Individual UInt8 columns for fastest filtering
- **Per-authority details**: Nested structure for detailed analysis
- **Disagreement tracking**: Dedicated fields for authority agreement counts
- **Performance**: Can query consensus flags without touching authority data

#### 2. **Data Type Optimization** 
- **RelayFingerprint**: FixedString(20) for binary SHA-1 (50% space savings)
- **AuthorityID**: Enum8 for authority identification (1 byte vs strings)
- **Compressed strings**: ZSTD compression for large text fields
- **LowCardinality**: For repeated values like versions, platforms

#### 3. **Bandwidth Data Strategy**
- **Multiple sources**: Consensus, bandwidth authorities, descriptors
- **Measurement quality**: Track which authorities measured vs estimated
- **Performance metrics**: Success rates and error tracking from bandwidth files

#### 4. **Query Optimization Features**
- **Partitioning**: By month for time-range queries
- **Primary key**: (fingerprint, consensus_time) for relay time-series
- **Bloom filters**: For categorical filtering (flags, operators, countries)
- **Projections**: Pre-computed aggregations for common patterns

### Example Queries Using Real lilpeep Data

```sql
-- 1. Authority disagreement analysis for lilpeep
SELECT 
    consensus_time,
    nickname,
    flag_hsdir as consensus_hsdir,
    arrayExists(x -> x = 'HSDir', arrayConcat(authority_data.flags)) as some_auth_voted_hsdir,
    authorities_agreeing_running,
    total_authorities_voting,
    authority_data.authority_id as authorities,
    authority_data.flags as authority_flags
FROM relay_consensus_measurements 
WHERE fingerprint = unhex('3D0D3172FA0C11AC7206883832F65BB8695CB1DF')
    AND consensus_time >= '2025-06-28 19:00:00'
    AND consensus_time <= '2025-06-28 21:00:00';

-- 2. Bandwidth measurement variance across authorities for lilpeep
SELECT 
    consensus_time,
    consensus_bandwidth,
    measured_bandwidth,
    authority_data.authority_id as authorities,
    authority_data.measured_bandwidth as auth_measurements,
    descriptor_bandwidth_observed / 1000 as descriptor_bw_kbps,
    arrayReduce('avg', authority_data.measured_bandwidth) as avg_authority_measurement,
    arrayReduce('stddevPop', authority_data.measured_bandwidth) as measurement_variance
FROM relay_consensus_measurements
WHERE fingerprint = unhex('3D0D3172FA0C11AC7206883832F65BB8695CB1DF')
    AND consensus_time >= '2025-06-28 19:00:00'
ORDER BY consensus_time;

-- 3. Network-wide authority disagreement patterns
SELECT 
    consensus_time,
    countIf(running_disagreement > 2) as relays_running_disagreement,
    countIf(guard_disagreement > 2) as relays_guard_disagreement,
    countIf(bandwidth_measurement_variance > 1000) as relays_bw_variance,
    avg(bandwidth_measurement_variance) as avg_bw_measurement_variance,
    total_relays_network
FROM authority_disagreement_analysis
WHERE consensus_time >= today() - 7
GROUP BY consensus_time
ORDER BY consensus_time;
```

### Additional Schema Questions Answered

#### Q5: How to handle 8 directory authorities + 1 consensus efficiently?
**Solution**: Store consensus as primary columns, authorities in nested structure
- Fast queries on consensus data (90% of use cases)
- Detailed authority analysis when needed (10% of use cases)
- Authority disagreement pre-computed in materialized view

#### Q6: How to handle missing data across sources?
**Solution**: Nullable fields + data completeness scoring
- Track which data sources were available for each measurement
- Score from 0-100 based on available data (consensus=40, descriptors=30, bandwidth=20, extra-info=10)
- Enable data quality analysis and gap identification

#### Q7: How to optimize for both current state and historical analysis?
**Solution**: Materialized views + projections
- Current state view with latest data per relay
- Historical projections for time-series aggregations
- Authority analysis view for consensus health monitoring

This schema design optimally handles the real-world complexity of Tor data while maintaining excellent query performance for both simple dashboard queries and complex analytical research.

### Example Analytical Queries Based on Real Data

```sql
-- 1. Operator bandwidth evolution with consensus weight correlation
SELECT 
    toStartOfMonth(consensus_valid_after) as month,
    contact_aroi as operator,
    sum(bandwidth_observed) / 1e9 as total_gbps,
    sum(bandwidth_measured) / 1e9 as measured_gbps,
    uniq(relay_fingerprint) as relay_count,
    avg(consensus_weight_fraction) * 100 as avg_network_influence_pct,
    uniq(country_code) as country_diversity,
    sum(flag_guard) as guard_relays,
    sum(flag_exit) as exit_relays
FROM relay_measurements 
WHERE contact_aroi = 'torservers.net'  -- Real operator example
    AND consensus_valid_after >= now() - INTERVAL 2 YEAR
    AND flag_running = 1
GROUP BY month, contact_aroi
ORDER BY month;

-- 2. Authority disagreement analysis - find relays with inconsistent flags
SELECT 
    relay_fingerprint,
    relay_nickname,
    consensus_valid_after,
    authority_count,
    flag_running,
    flag_guard,
    flag_exit,
    -- Decode authority-specific flags to see disagreements
    arraySum(authority_flags) as total_authority_votes,
    authority_count,
    contact_aroi
FROM relay_measurements
WHERE consensus_valid_after >= now() - INTERVAL 7 DAY
    AND authority_count >= 7  -- Most authorities voted
    AND (flag_running != (arraySum(authority_flags) > authority_count/2))  -- Disagreement
ORDER BY consensus_valid_after DESC, authority_count DESC;

-- 3. Exit policy evolution analysis with geographic correlation
SELECT 
    toDate(consensus_valid_after) as date,
    country_code,
    count(*) as total_exits,
    sum(is_exit_unrestricted) as unrestricted_exits,
    sum(allows_port_80) as http_exits,
    sum(allows_port_443) as https_exits,
    sum(allows_port_22) as ssh_exits,
    avg(bandwidth_observed) / 1e6 as avg_exit_bandwidth_mbps,
    sum(bandwidth_observed) / 1e9 as total_exit_bandwidth_gbps
FROM relay_measurements
WHERE flag_exit = 1 
    AND consensus_valid_after >= now() - INTERVAL 1 YEAR
    AND flag_running = 1
GROUP BY date, country_code
HAVING total_exits >= 5  -- Countries with meaningful exit presence
ORDER BY date DESC, total_exit_bandwidth_gbps DESC;

-- 4. Platform diversity and version upgrade patterns
SELECT 
    toStartOfMonth(consensus_valid_after) as month,
    operating_system,
    tor_version,
    count(*) as relay_count,
    sum(bandwidth_observed) / 1e9 as total_bandwidth_gbps,
    sum(version_recommended) as recommended_count,
    sum(version_recommended) / count(*) * 100 as recommended_percentage,
    uniq(contact_hash) as unique_operators
FROM relay_measurements
WHERE consensus_valid_after >= now() - INTERVAL 1 YEAR
    AND flag_running = 1
GROUP BY month, operating_system, tor_version
HAVING relay_count >= 10  -- Significant versions only
ORDER BY month DESC, total_bandwidth_gbps DESC;

-- 5. AROI operator performance benchmarking with reliability scoring
SELECT 
    contact_aroi as operator,
    uniq(relay_fingerprint) as total_relays,
    sum(bandwidth_observed) / 1e9 as total_bandwidth_gbps,
    sum(consensus_weight_fraction) * 100 as network_influence_pct,
    uniq(country_code) as geographic_diversity,
    uniq(as_number) as network_diversity,
    
    -- Reliability metrics
    avg(uptime_1_month) as avg_monthly_uptime,
    avg(uptime_1_year) as avg_yearly_uptime,
    min(first_seen) as operator_first_seen,
    dateDiff('day', min(first_seen), now()) as operator_age_days,
    
    -- Exit capabilities
    sum(flag_exit) as exit_relays,
    sum(is_exit_unrestricted) as unrestricted_exits,
    sum(allows_port_80 * flag_exit) as http_exits,
    
    -- Performance efficiency (CW/BW ratio)
    sum(consensus_weight) / sum(bandwidth_observed) * 1e6 as cw_bw_efficiency
FROM relay_measurements
WHERE consensus_valid_after >= now() - INTERVAL 30 DAY  -- Last 30 days
    AND contact_aroi != ''  -- Only AROI operators
    AND flag_running = 1
GROUP BY contact_aroi
HAVING total_relays >= 3  -- Meaningful operators only
ORDER BY network_influence_pct DESC
LIMIT 25;

-- 6. Network concentration risk analysis by AS and geography
WITH top_as_analysis AS (
    SELECT 
        as_number,
        as_name,
        sum(bandwidth_observed) / 1e9 as total_bandwidth_gbps,
        sum(consensus_weight_fraction) * 100 as network_influence_pct,
        uniq(relay_fingerprint) as relay_count,
        uniq(contact_hash) as operator_count,
        uniq(country_code) as country_presence
    FROM relay_measurements
    WHERE consensus_valid_after >= now() - INTERVAL 7 DAY
        AND flag_running = 1
    GROUP BY as_number, as_name
    ORDER BY network_influence_pct DESC
    LIMIT 20
),
geographic_concentration AS (
    SELECT 
        country_code,
        sum(bandwidth_observed) / 1e9 as country_bandwidth_gbps,
        sum(consensus_weight_fraction) * 100 as country_influence_pct,
        uniq(as_number) as as_diversity
    FROM relay_measurements
    WHERE consensus_valid_after >= now() - INTERVAL 7 DAY
        AND flag_running = 1
    GROUP BY country_code
    ORDER BY country_influence_pct DESC
    LIMIT 10
)
SELECT 
    'AS Concentration Risk' as analysis_type,
    as_number as identifier,
    as_name as name,
    total_bandwidth_gbps as bandwidth_gbps,
    network_influence_pct,
    relay_count,
    operator_count as diversity_metric
FROM top_as_analysis
UNION ALL
SELECT 
    'Geographic Concentration Risk' as analysis_type,
    country_code as identifier,
    country_code as name,  -- Could join with country names table
    country_bandwidth_gbps as bandwidth_gbps,
    country_influence_pct as network_influence_pct,
    NULL as relay_count,
    as_diversity as diversity_metric
FROM geographic_concentration
ORDER BY network_influence_pct DESC;

-- 7. Historical consensus weight redistribution analysis
SELECT 
    toStartOfMonth(consensus_valid_after) as month,
    contact_aroi,
    sum(consensus_weight_fraction) * 100 as monthly_influence,
    lag(sum(consensus_weight_fraction) * 100, 1) OVER (
        PARTITION BY contact_aroi 
        ORDER BY toStartOfMonth(consensus_valid_after)
    ) as prev_month_influence,
    monthly_influence - prev_month_influence as influence_change
FROM relay_measurements
WHERE consensus_valid_after >= now() - INTERVAL 1 YEAR
    AND contact_aroi != ''
    AND flag_running = 1
GROUP BY month, contact_aroi
HAVING monthly_influence > 0.5  -- Operators with >0.5% network influence
ORDER BY month DESC, abs(influence_change) DESC;
```

## 🏆 Top 20 ClickHouse Analytics Enhancements

### 1. **Historical AROI Leaderboards with Trend Analysis**
- **Enhancement**: Time-series leaderboards showing ranking changes over months/years
- **Current Page**: AROI Leaderboards (`misc/aroi-leaderboards.html`)
- **ClickHouse Value**: Track operator performance evolution, identify rising/declining operators
- **Implementation**: Add trend arrows, ranking change indicators, historical position graphs

### 2. **Bandwidth History Charts on Network Health Dashboard**
- **Enhancement**: Real-time bandwidth evolution charts with 1-day, 1-week, 1-month, 1-year views
- **Current Page**: Network Health Dashboard (`network-health.html`)
- **ClickHouse Value**: Visualize network capacity growth, identify bandwidth patterns
- **Implementation**: Interactive time-series charts showing total/guard/exit bandwidth trends

### 3. **Consensus Weight Contribution Timeline per Relay Operator**
- **Enhancement**: Individual operator consensus weight history with milestone tracking
- **Current Page**: Contact pages (`contact/*.html`)
- **ClickHouse Value**: Show operator growth trajectory, network influence changes
- **Implementation**: Line charts with consensus weight percentage over time

### 4. **Historic Daily/Monthly/Yearly Leaderboards with Patterns**
- **Enhancement**: Archived leaderboard snapshots with seasonal pattern analysis
- **Current Page**: All AROI categories
- **ClickHouse Value**: Identify seasonal operators, historical champions, trend patterns
- **Implementation**: Calendar-based leaderboard browser with pattern highlighting

### 5. **Relay Uptime and Reliability Trend Analysis**
- **Enhancement**: Long-term uptime patterns with reliability scoring evolution
- **Current Page**: Individual relay pages (`relay/*.html`)
- **ClickHouse Value**: Predict reliability, identify improvement/degradation trends
- **Implementation**: Reliability trend charts with predictive analytics

### 6. **Geographic Expansion Timeline Visualization**
- **Enhancement**: Animated world map showing Tor network geographic growth
- **Current Page**: Country-based pages (`country/*.html`)
- **ClickHouse Value**: Visualize network decentralization progress, geographic milestones
- **Implementation**: Time-lapse country emergence with diversity metrics

### 7. **Anomaly Detection for Relay Performance**
- **Enhancement**: Automatic detection of unusual bandwidth, consensus weight, or uptime patterns
- **Current Page**: Network Health Dashboard
- **ClickHouse Value**: Early warning system for network issues, operator problems
- **Implementation**: ML-based anomaly alerts with historical context

### 8. **Platform Diversity Evolution Tracking**
- **Enhancement**: OS and software version adoption trends over time
- **Current Page**: Platform pages (`misc/misc-platforms.html`)
- **ClickHouse Value**: Track software diversity health, version adoption patterns
- **Implementation**: Stacked area charts showing platform distribution evolution

### 9. **AS (Autonomous System) Concentration Risk Analysis**
- **Enhancement**: Network provider concentration tracking with risk alerts
- **Current Page**: Network pages (`misc/misc-networks.html`)
- **ClickHouse Value**: Monitor network centralization risks, diversification progress
- **Implementation**: Concentration index trends with threshold alerts

### 10. **Relay Lifecycle Analysis and Predictive Modeling**
- **Enhancement**: Relay lifespan patterns, churn analysis, and longevity predictions
- **Current Page**: Individual relay pages
- **ClickHouse Value**: Understand operator behavior, predict network stability
- **Implementation**: Lifecycle visualization with survival analysis

### 11. **Bandwidth Efficiency Trends and Optimization Insights**
- **Enhancement**: Historical CW/BW ratios with efficiency improvement tracking
- **Current Page**: Contact operator pages
- **ClickHouse Value**: Guide operators on optimization opportunities
- **Implementation**: Efficiency trend charts with optimization recommendations

### 12. **Directory Authority Performance Historical Analysis**
- **Enhancement**: Authority uptime, consensus agreement, and performance trends
- **Current Page**: Directory Authorities page (`misc/authorities.html`)
- **ClickHouse Value**: Monitor consensus health, authority reliability patterns
- **Implementation**: Authority health dashboards with historical performance

### 13. **Exit Policy Evolution and Traffic Analysis**
- **Enhancement**: Exit policy changes over time, port restriction trends
- **Current Page**: Network Health Dashboard
- **ClickHouse Value**: Understand exit capacity evolution, policy impact analysis
- **Implementation**: Exit policy timeline with traffic capacity implications

### 14. **Operator Reliability Percentile Tracking**
- **Enhancement**: Operator reliability rankings with percentile movement over time
- **Current Page**: Contact pages with reliability metrics
- **ClickHouse Value**: Track operator performance evolution within network distribution
- **Implementation**: Percentile rank charts with peer comparison

### 15. **Network Capacity Planning with Growth Projections**
- **Enhancement**: Capacity trend analysis with growth prediction models
- **Current Page**: Network Health Dashboard
- **ClickHouse Value**: Support network planning, capacity forecasting
- **Implementation**: Growth projection charts with scenario modeling

### 16. **Seasonal Pattern Analysis for Network Activity**
- **Enhancement**: Identify recurring patterns in relay activity, bandwidth usage
- **Current Page**: All statistics pages
- **ClickHouse Value**: Understand network behavior cycles, plan maintenance
- **Implementation**: Seasonal decomposition charts with pattern highlighting

### 17. **Relay Family Evolution and Relationship Mapping**
- **Enhancement**: Family relationship changes, operator mergers/splits over time
- **Current Page**: Family pages (`family/*.html`)
- **ClickHouse Value**: Track operator collaboration patterns, family dynamics
- **Implementation**: Family tree evolution with relationship timeline

### 18. **IPv6 Adoption Progress Tracking**
- **Enhancement**: IPv6 deployment trends across operators and countries
- **Current Page**: Network Health Dashboard
- **ClickHouse Value**: Monitor network modernization, IPv6 adoption patterns
- **Implementation**: IPv6 adoption charts by operator/country over time

### 19. **Consensus Weight Redistribution Analysis**
- **Enhancement**: Track consensus weight shifts between operators and regions
- **Current Page**: Various consensus weight pages
- **ClickHouse Value**: Monitor network power distribution, decentralization progress
- **Implementation**: Sankey diagrams showing weight flow over time

### 20. **Historical Performance Benchmarking**
- **Enhancement**: Compare current operator performance against historical benchmarks
- **Current Page**: All operator and relay pages
- **ClickHouse Value**: Contextualize current performance, track improvement
- **Implementation**: Performance comparison charts with historical percentiles

## 🔧 Technical Implementation Plan

### Phase 1: Data Infrastructure (Months 1-2)
1. **ClickHouse Cluster Setup**
   - Production cluster with replication
   - Development/staging environment
   - Backup and disaster recovery

2. **Data Ingestion Pipeline**
   - CollecTor archive processing (2007-2025)
   - Real-time Onionoo API integration
   - Data validation and quality checks

3. **Schema Implementation**
   - Core tables creation
   - Materialized views for aggregations
   - Indexing optimization

### Phase 2: Historical Data Migration (Months 2-3)
1. **CollecTor Archive Processing**
   - Parse consensus documents (2007-2025) from https://collector.torproject.org/
   - Extract relay measurements from vote/consensus files
   - Handle format changes across Tor versions
   - Binary fingerprint conversion and validation
   
2. **Data Pipeline Architecture**
   - Streaming ETL pipeline for large archive processing
   - Parallel processing of consensus files by date ranges
   - Deduplication logic for overlapping measurements
   - Custom data type conversion (hex fingerprints → binary, IPs → decimals)

3. **Data Quality Assurance**
   - Consistency validation across consensus periods
   - Gap identification and interpolation strategies
   - Performance optimization and batch insertion
   - Monitoring for data drift and anomalies

### Phase 3: Analytics Engine Development (Months 3-5)
1. **Query Layer Development**
   - Time-series aggregation functions
   - Trend analysis algorithms
   - Anomaly detection models

2. **API Development**
   - Historical data endpoints
   - Real-time query interface
   - Caching layer implementation

### Phase 4: Frontend Integration (Months 5-6)
1. **Allium Template Enhancement**
   - Historical chart integration
   - Interactive timeline components
   - Pattern visualization widgets

2. **Performance Optimization**
   - Query optimization
   - Caching strategies
   - Load testing and tuning

## 📈 Expected Benefits

### For Relay Operators
- **Performance insights** from historical trend analysis
- **Optimization guidance** based on efficiency patterns
- **Reliability tracking** with improvement metrics
- **Competitive analysis** against peer operators

### For Tor Network Analysis
- **Network health monitoring** with historical context
- **Capacity planning** with growth projections
- **Risk assessment** through concentration analysis
- **Policy impact evaluation** with historical comparisons

### For Research Community
- **Longitudinal studies** with 18+ years of data
- **Pattern analysis** for academic research
- **Anomaly detection** for security research
- **Network evolution** documentation

## 🛡️ Security and Privacy Considerations

### Data Protection
- **No personally identifiable information** stored
- **Relay fingerprints** as primary identifiers (already public)
- **Contact information** hashed for operator aggregation
- **Geographic data** limited to country-level

### Access Control
- **Read-only public access** for historical analytics
- **Administrative access** for data ingestion
- **Audit logging** for all database operations

## 💰 Resource Requirements

### Infrastructure Requirements (Updated Based on Real Data Analysis)

- **ClickHouse Cluster**: 5-node cluster for production reliability
  - **Master nodes** (3): 128GB RAM, 4TB NVMe SSD, 64 CPU cores each  
  - **Replica nodes** (2): 64GB RAM, 2TB NVMe SSD, 32 CPU cores each
  
- **Data Storage Calculations**:
  - **Raw consensus data**: ~3.5MB per consensus × 24 hours × 365 days = ~30GB/year
  - **Per-relay measurements**: ~8000 relays × 24 measurements/day × 365 days = ~70M measurements/year
  - **Row size estimate**: ~2KB per measurement (all fields) = ~140GB/year uncompressed
  - **With ZSTD compression**: ~35GB/year compressed (4:1 ratio)
  - **Historical backfill (2007-2025)**: ~630GB compressed
  - **Materialized views storage**: ~20% additional = ~150GB additional
  - **Total storage needed**: ~1TB for historical + ongoing data

- **Processing Requirements**:
  - **Ingestion rate**: 8000 relays × 24 measurements/day = ~2.2 measurements/second (low)
  - **Historical backfill**: Process 18 years of data over 2-week period = ~500K measurements/minute
  - **Query performance target**: <1 second for dashboard queries, <10 seconds for complex analytics
  - **Concurrent users**: 50-100 analysts and dashboards

- **Network Requirements**:
  - **CollecTor sync**: Download ~3.5MB every hour = minimal bandwidth
  - **Historical migration**: Download ~50GB CollecTor archives over 1 month
  - **User queries**: 1-10MB per complex query × 100 concurrent = moderate bandwidth

### Development
- **Backend Development**: 3-4 months full-time equivalent
- **Frontend Integration**: 1-2 months full-time equivalent
- **Testing and Optimization**: 1 month full-time equivalent

## 🚀 Success Metrics

### Technical Metrics
- **Query Performance**: <1 second for time-series aggregations, <5 seconds for complex multi-operator analytics
- **Data Ingestion**: >100K measurements/second during historical backfill
- **Data Freshness**: <5 minutes lag for real-time Onionoo updates
- **Uptime**: 99.9% availability for analytics queries with automatic failover
- **Storage Efficiency**: <3GB per million measurements (200GB/year for network)
- **Compression Ratio**: >10:1 with ZSTD and proper column encoding

### User Engagement
- **Page Views**: 50% increase in analytics page engagement
- **Session Duration**: 30% increase in time spent on historical analysis
- **User Retention**: 25% increase in return visitors
- **Feature Adoption**: 80% of operators using historical features

## 🎯 Conclusion

Integrating ClickHouse with allium will transform the platform from a real-time monitoring tool into a comprehensive historical analytics powerhouse. The 20 proposed enhancements will provide unprecedented insights into Tor network evolution, operator performance trends, and network health patterns.

This enhancement will position allium as the definitive platform for Tor network analysis, serving relay operators, researchers, and the broader Tor community with data-driven insights spanning nearly two decades of network history.

The investment in ClickHouse infrastructure will pay dividends through improved operator decision-making, enhanced network planning capabilities, and valuable research insights that benefit the entire Tor ecosystem.