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

#### ClickHouse Schema Design

```sql
-- Custom data types for optimal storage and performance
CREATE TYPE IF NOT EXISTS RelayFingerprint AS FixedString(20);  -- 20 bytes for SHA-1 binary
CREATE TYPE IF NOT EXISTS ContactHash AS FixedString(16);       -- 16 bytes for MD5 binary

-- Single wide measurement table - each row is a complete relay observation
CREATE TABLE relay_measurements (
    -- Time and identification
    measurement_time DateTime64(3),
    consensus_valid_after DateTime,
    relay_fingerprint RelayFingerprint,
    relay_nickname LowCardinality(String),
    
    -- Network identity
    ip_address IPv4,
    ipv6_address Nullable(IPv6),
    or_port UInt16,
    dir_port UInt16,
    
    -- Bandwidth measurements (bytes/second)
    observed_bandwidth UInt64,
    advertised_bandwidth UInt64,
    bandwidth_rate UInt64,
    bandwidth_burst UInt64,
    
    -- Consensus weights (raw values)
    consensus_weight UInt64,
    consensus_weight_fraction Float64,
    guard_probability Float64,
    middle_probability Float64,
    exit_probability Float64,
    
    -- Flags as bitmap for efficient storage and queries
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
    
    -- Geographic and network data
    country_code FixedString(2),
    as_number UInt32,
    as_name LowCardinality(String),
    
    -- Platform and version (efficient storage)
    platform_os LowCardinality(String),
    platform_version LowCardinality(String),
    tor_version LowCardinality(String),
    version_status LowCardinality(String),  -- recommended, obsolete, etc.
    
    -- Contact and family
    contact_hash ContactHash,
    contact_raw String CODEC(ZSTD),  -- Compressed storage for full contact
    aroi_domain LowCardinality(String),
    family_fingerprints Array(RelayFingerprint),
    effective_family_count UInt16,
    
    -- Lifecycle tracking
    first_seen DateTime,
    last_seen DateTime,
    is_first_measurement UInt8,
    is_last_measurement UInt8,
    days_since_first_seen UInt32,
    
    -- Exit policy summary (for quick filtering)
    allows_port_80 UInt8,
    allows_port_443 UInt8,
    exit_policy_summary String CODEC(ZSTD),
    
    -- Additional measurements
    uptime_1_month Nullable(Float32),
    uptime_3_months Nullable(Float32),
    uptime_1_year Nullable(Float32),
    
    -- Network position context (denormalized for performance)
    total_network_consensus_weight UInt64,
    total_network_bandwidth UInt64,
    network_relay_count UInt32
    
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(measurement_time)
ORDER BY (relay_fingerprint, measurement_time)
SETTINGS index_granularity = 8192;

-- Materialized views for common aggregation patterns

-- Latest state per relay (for current status queries)
CREATE MATERIALIZED VIEW relay_latest_state
ENGINE = ReplacingMergeTree(measurement_time)
ORDER BY relay_fingerprint
AS SELECT 
    relay_fingerprint,
    argMax(measurement_time, measurement_time) as last_measurement,
    argMax(relay_nickname, measurement_time) as current_nickname,
    argMax(observed_bandwidth, measurement_time) as current_bandwidth,
    argMax(consensus_weight, measurement_time) as current_consensus_weight,
    argMax(flag_running, measurement_time) as is_running,
    argMax(country_code, measurement_time) as current_country,
    argMax(contact_hash, measurement_time) as current_contact_hash
FROM relay_measurements
GROUP BY relay_fingerprint;

-- Hourly network aggregates (for network health dashboard)
CREATE MATERIALIZED VIEW network_hourly_stats
ENGINE = SummingMergeTree()
ORDER BY measurement_hour
AS SELECT 
    toStartOfHour(measurement_time) as measurement_hour,
    count() as total_measurements,
    uniq(relay_fingerprint) as unique_relays,
    sum(observed_bandwidth) as total_bandwidth,
    sum(consensus_weight) as total_consensus_weight,
    sum(flag_guard) as guard_count,
    sum(flag_exit) as exit_count,
    sum(flag_running) as running_count,
    uniq(country_code) as unique_countries,
    uniq(as_number) as unique_as_count
FROM relay_measurements
GROUP BY measurement_hour;

-- Daily operator aggregates (for AROI leaderboards)
CREATE MATERIALIZED VIEW operator_daily_stats
ENGINE = SummingMergeTree()
ORDER BY (measurement_date, contact_hash)
AS SELECT 
    toDate(measurement_time) as measurement_date,
    contact_hash,
    any(aroi_domain) as aroi_domain,
    count() as total_measurements,
    uniq(relay_fingerprint) as relay_count,
    sum(observed_bandwidth) as total_bandwidth,
    sum(consensus_weight) as total_consensus_weight,
    sum(flag_guard) as guard_count,
    sum(flag_exit) as exit_count,
    uniq(country_code) as country_count,
    uniq(as_number) as as_count,
    uniq(platform_os) as platform_count
FROM relay_measurements
WHERE contact_hash != '\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0'  -- Exclude empty contacts
GROUP BY measurement_date, contact_hash;

-- Indexes for common query patterns
CREATE INDEX idx_country ON relay_measurements (country_code) TYPE bloom_filter(0.01);
CREATE INDEX idx_as ON relay_measurements (as_number) TYPE bloom_filter(0.01);
CREATE INDEX idx_flags ON relay_measurements (flag_guard, flag_exit, flag_running) TYPE bloom_filter(0.01);

-- Projection for time-series aggregations (ClickHouse 22+)
ALTER TABLE relay_measurements ADD PROJECTION bandwidth_time_series (
    SELECT 
        toStartOfDay(measurement_time) as day,
        relay_fingerprint,
        avg(observed_bandwidth) as avg_bandwidth,
        max(observed_bandwidth) as max_bandwidth,
        avg(consensus_weight) as avg_consensus_weight
    GROUP BY day, relay_fingerprint
);
```

### Example Analytical Queries

```sql
-- 1. Bandwidth evolution for a specific operator over time
SELECT 
    toStartOfMonth(measurement_time) as month,
    sum(observed_bandwidth) / 1e9 as total_gbps,
    uniq(relay_fingerprint) as relay_count,
    sum(consensus_weight) / sum(total_network_consensus_weight) * 100 as network_share_pct
FROM relay_measurements 
WHERE contact_hash = unhex('1234567890abcdef1234567890abcdef')
    AND measurement_time >= now() - INTERVAL 2 YEAR
GROUP BY month
ORDER BY month;

-- 2. Find relays with anomalous bandwidth patterns (sudden drops/spikes)
WITH relay_bandwidth AS (
    SELECT 
        relay_fingerprint,
        measurement_time,
        observed_bandwidth,
        lag(observed_bandwidth, 1) OVER (PARTITION BY relay_fingerprint ORDER BY measurement_time) as prev_bandwidth
    FROM relay_measurements 
    WHERE measurement_time >= now() - INTERVAL 7 DAY
)
SELECT 
    relay_fingerprint,
    measurement_time,
    observed_bandwidth / 1e6 as current_mbps,
    prev_bandwidth / 1e6 as prev_mbps,
    (observed_bandwidth - prev_bandwidth) / prev_bandwidth * 100 as change_pct
FROM relay_bandwidth
WHERE abs(change_pct) > 50 AND prev_bandwidth > 1e6  -- >50% change, >1 MB/s baseline
ORDER BY abs(change_pct) DESC;

-- 3. Top operators by consensus weight growth in last 6 months
SELECT 
    contact_hash,
    any(aroi_domain) as operator,
    sum(total_consensus_weight) as current_weight,
    sum(total_consensus_weight) - sumIf(total_consensus_weight, measurement_date < today() - 180) as growth,
    growth / sumIf(total_consensus_weight, measurement_date < today() - 180) * 100 as growth_pct
FROM operator_daily_stats
WHERE measurement_date >= today() - 180
GROUP BY contact_hash
HAVING growth_pct > 10  -- >10% growth
ORDER BY growth DESC;

-- 4. Geographic diversity trends over time
SELECT 
    measurement_hour,
    unique_countries,
    unique_relays,
    unique_countries / unique_relays * 100 as countries_per_100_relays,
    entropy(groupArray(relay_count)) as geographic_entropy  -- Higher = more diverse
FROM (
    SELECT 
        toStartOfDay(measurement_time) as measurement_hour,
        country_code,
        uniq(relay_fingerprint) as relay_count
    FROM relay_measurements
    WHERE measurement_time >= now() - INTERVAL 1 YEAR
    GROUP BY measurement_hour, country_code
) grouped_by_country
JOIN (
    SELECT 
        toStartOfDay(measurement_time) as measurement_hour,
        uniq(country_code) as unique_countries,
        uniq(relay_fingerprint) as unique_relays
    FROM relay_measurements
    WHERE measurement_time >= now() - INTERVAL 1 YEAR
    GROUP BY measurement_hour
) network_stats USING measurement_hour
GROUP BY measurement_hour, unique_countries, unique_relays
ORDER BY measurement_hour;

-- 5. Relay churn analysis - identify operators with high turnover
SELECT 
    contact_hash,
    any(aroi_domain) as operator,
    uniq(relay_fingerprint) as total_unique_relays,
    uniqIf(relay_fingerprint, is_first_measurement = 1) as new_relays,
    uniqIf(relay_fingerprint, is_last_measurement = 1) as departed_relays,
    (new_relays + departed_relays) / total_unique_relays as churn_rate
FROM relay_measurements
WHERE measurement_time >= now() - INTERVAL 90 DAY
    AND contact_hash != '\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0'
GROUP BY contact_hash
HAVING total_unique_relays >= 5  -- Only operators with 5+ relays
ORDER BY churn_rate DESC;
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

### Infrastructure
- **ClickHouse Cluster**: 3-node setup with 64GB RAM, 2TB NVMe SSD each
- **Data Storage**: 
  - Historical data (2007-2025): ~2TB compressed with ZSTD
  - Annual growth: ~200GB/year (consensus every hour = ~8760 measurements/relay/year)
  - With ~8000 relays: ~70M measurements/year
- **Processing Power**: 32-core CPU for parallel data ingestion and complex aggregations
- **Network**: 10Gbps for initial data migration from CollecTor archives

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