# ClickHouse Analytics Integration Proposal for Allium

## Executive Summary

This proposal outlines the integration of ClickHouse database to transform Allium from a point-in-time static site generator into a comprehensive historical analytics platform for Tor relay operators. By ingesting and analyzing 18+ years of consensus and descriptor data (2007-2025), we can provide unprecedented insights into network evolution, operator performance trends, and predictive analytics.

## Data Architecture

### Primary Data Sources

1. **Consensus Files** (2007-2025)
   - Network-wide relay status snapshots every hour
   - Contains: fingerprint, nickname, flags, consensus weight, IP, ports
   - Volume: ~157,000 files × ~1MB = ~157GB compressed

2. **Server Descriptors**
   - Detailed relay specifications
   - Contains: bandwidth rates, platform, uptime, contact info
   - Volume: ~500GB compressed

3. **Extra Info Descriptors**
   - Extended statistics and metrics
   - Contains: country stats, transport data, cell stats
   - Volume: ~300GB compressed

4. **Bandwidth Files**
   - Authority bandwidth measurements
   - Contains: measured bandwidth values per relay
   - Volume: ~50GB compressed

### ClickHouse Schema Design

```sql
-- Main consensus history table
CREATE TABLE consensus_history
(
    consensus_time DateTime,
    fingerprint FixedString(40),
    nickname String,
    ip IPv4,
    or_port UInt16,
    dir_port UInt16,
    flags Array(String),
    consensus_weight UInt32,
    bandwidth_measured UInt64,
    version String,
    os String,
    contact String,
    as_number UInt32,
    as_name String,
    country_code FixedString(2),
    region String,
    city String,
    latitude Float32,
    longitude Float32
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(consensus_time)
ORDER BY (consensus_time, fingerprint)
SETTINGS index_granularity = 8192;

-- Aggregated daily statistics
CREATE TABLE relay_daily_stats
(
    date Date,
    fingerprint FixedString(40),
    avg_consensus_weight UInt32,
    max_consensus_weight UInt32,
    min_consensus_weight UInt32,
    hours_online UInt8,
    flag_stability Map(String, UInt8),
    bandwidth_avg UInt64,
    exit_probability Float32,
    guard_probability Float32
)
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (date, fingerprint);

-- Operator analytics table
CREATE TABLE operator_history
(
    date Date,
    contact String,
    relay_count UInt16,
    total_consensus_weight UInt64,
    total_bandwidth UInt64,
    countries Array(String),
    unique_ases UInt16,
    platform_diversity Float32,
    network_fraction Float32
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (date, contact);
```

## Top 20 ClickHouse Analytics Enhancements

### 1. **Historical Bandwidth Charts**
- **Location**: Network Health Dashboard
- **Feature**: Interactive time-series graphs showing network-wide bandwidth trends
- **Query**: Aggregate bandwidth by day/week/month with moving averages
- **Value**: Visualize network growth and capacity trends

### 2. **Relay Lifetime Analysis**
- **Location**: Individual relay pages
- **Feature**: Complete lifecycle visualization from first seen to current
- **Query**: Track consensus weight, flags, and uptime throughout relay history
- **Value**: Understand relay stability and performance evolution

### 3. **Operator Performance Trending**
- **Location**: Contact/Operator pages
- **Feature**: Historical charts of operator's network contribution
- **Query**: Aggregate all relays by contact over time
- **Value**: Show operator growth, reliability trends, and network impact

### 4. **Geographic Diversity Timeline**
- **Location**: Country pages, Network Health
- **Feature**: Animated heatmap showing relay distribution evolution
- **Query**: Country relay counts and consensus weights over time
- **Value**: Visualize geographic expansion and concentration risks

### 5. **AS Centralization Analysis**
- **Location**: AS pages, Network Health
- **Feature**: Historical AS concentration metrics with alerts
- **Query**: Track top AS providers' network percentage over time
- **Value**: Identify centralization trends and diversity improvements

### 6. **Consensus Weight Contribution Leaderboards**
- **Location**: AROI Leaderboards
- **Feature**: Daily/Monthly/Yearly historical leaderboards
- **Query**: Rank operators by consensus weight for any time period
- **Value**: Recognize historical contributions and track ranking changes

### 7. **Flag Stability Analytics**
- **Location**: Relay pages
- **Feature**: Heatmaps showing flag presence over time
- **Query**: Track Guard, Exit, Stable, Fast flags by hour
- **Value**: Identify reliability patterns and flag loss events

### 8. **Network Event Detection**
- **Location**: Network Health Dashboard
- **Feature**: Automatic anomaly detection and event timeline
- **Query**: Statistical analysis for sudden changes in network metrics
- **Value**: Alert operators to network-wide issues or attacks

### 9. **Platform Evolution Tracking**
- **Location**: Platform pages
- **Feature**: Stacked area charts of OS/version distribution
- **Query**: Aggregate platform data over time
- **Value**: Track Tor version adoption and OS diversity

### 10. **Exit Policy Analytics**
- **Location**: Exit relay pages
- **Feature**: Historical exit policy changes and impact
- **Query**: Track exit policy modifications and traffic estimates
- **Value**: Understand exit capacity evolution

### 11. **Predictive Relay Scoring**
- **Location**: Relay pages, operator dashboards
- **Feature**: ML-based predictions of relay stability
- **Query**: Analyze historical patterns to predict future performance
- **Value**: Help operators identify at-risk relays

### 12. **Network Growth Projections**
- **Location**: Network Health Dashboard
- **Feature**: Forecasting models for bandwidth and relay count
- **Query**: Time-series analysis with seasonal decomposition
- **Value**: Planning for network capacity needs

### 13. **Operator Retention Analysis**
- **Location**: AROI Analytics section
- **Feature**: Cohort analysis of operator lifecycles
- **Query**: Track operator first appearance and duration
- **Value**: Understand operator churn and retention factors

### 14. **Consensus Weight Distribution**
- **Location**: Network Health Dashboard
- **Feature**: Gini coefficient and distribution curves over time
- **Query**: Calculate weight distribution metrics daily
- **Value**: Monitor network decentralization progress

### 15. **IPv6 Adoption Timeline**
- **Location**: Network Health, relay pages
- **Feature**: Progressive adoption charts by country/AS
- **Query**: Track IPv6 ORPort and reachability over time
- **Value**: Visualize IPv6 deployment progress

### 16. **Relay Family Evolution**
- **Location**: Family pages
- **Feature**: Interactive family tree showing relay relationships
- **Query**: Track family declarations and MyFamily changes
- **Value**: Understand operator infrastructure evolution

### 17. **Bandwidth Authority Comparison**
- **Location**: Network Health Dashboard
- **Feature**: Historical measurement consistency analysis
- **Query**: Compare bandwidth measurements across authorities
- **Value**: Identify measurement anomalies and improvements

### 18. **Geographic Correlation Analysis**
- **Location**: Country pages
- **Feature**: Correlation between relay density and internet freedom
- **Query**: Combine relay data with external freedom indices
- **Value**: Strategic insights for network expansion

### 19. **Operator Milestone Tracking**
- **Location**: Operator pages, AROI leaderboards
- **Feature**: Achievement system based on historical data
- **Query**: Identify first-time achievements and records
- **Value**: Gamification and recognition for long-term contributors

### 20. **Network Resilience Scoring**
- **Location**: Network Health Dashboard
- **Feature**: Real-time resilience metrics based on diversity
- **Query**: Calculate redundancy across geography, AS, and operators
- **Value**: Quantify network robustness against failures

## Implementation Strategy

### Phase 1: Data Ingestion Pipeline (Weeks 1-4)
1. Set up ClickHouse cluster with replication
2. Create ETL pipeline for historical data import
3. Implement real-time consensus parser
4. Validate data integrity and completeness

### Phase 2: Core Analytics (Weeks 5-8)
1. Develop materialized views for common queries
2. Create API endpoints for data access
3. Implement caching layer for performance
4. Build data quality monitoring

### Phase 3: Visualization Integration (Weeks 9-12)
1. Add Chart.js/D3.js for interactive visualizations
2. Enhance existing pages with historical context
3. Create new analytics-focused pages
4. Implement progressive enhancement

### Phase 4: Advanced Features (Weeks 13-16)
1. Deploy anomaly detection algorithms
2. Implement predictive models
3. Add real-time alerting system
4. Create operator API for custom queries

## Technical Benefits

1. **Sub-second Queries**: ClickHouse's columnar storage enables fast analytics on billions of consensus records
2. **Real-time Updates**: Streaming ingestion for live network monitoring
3. **Compression**: 10-30x compression ratios for historical data
4. **Scalability**: Horizontal scaling for growing data volumes
5. **SQL Interface**: Familiar query language for custom analytics

## Performance Projections

- **Storage**: ~1TB uncompressed → ~50-100GB in ClickHouse
- **Query Speed**: 
  - Full network history scan: <1 second
  - Complex aggregations: <100ms
  - Real-time dashboards: <50ms updates
- **Ingestion**: 100k+ consensus records/second

## Risk Mitigation

1. **Data Privacy**: No additional PII collected beyond public consensus
2. **Storage Costs**: Efficient compression and tiered storage
3. **Query Complexity**: Pre-aggregated views for common patterns
4. **Maintenance**: Automated data lifecycle management

## Conclusion

Integrating ClickHouse will transform Allium from a static snapshot tool into a dynamic analytics platform. This provides relay operators with unprecedented insights into their historical performance, network trends, and predictive analytics for planning. The Tor Project benefits from better network visibility, improved operator retention through gamification, and data-driven decision making for network health.

## Next Steps

1. Review and approve proposal
2. Set up development ClickHouse instance
3. Begin historical data collection from collector.torproject.org
4. Prototype first visualization on test data
5. Gather operator feedback on desired analytics

---

*This proposal is based on analysis of real Tor consensus and descriptor formats, ensuring all suggested features are technically feasible with available data.*