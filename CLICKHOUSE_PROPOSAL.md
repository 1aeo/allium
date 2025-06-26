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
   - Consensus weight measurements
   - Relay status changes
   - Flag assignments over time
   - Bandwidth measurements
   - Geographic distribution changes

2. **Onionoo API Integration** (Real-time)
   - Current relay data
   - Recent uptime statistics
   - Active relay information

#### ClickHouse Schema Design

```sql
-- Core relay metrics table
CREATE TABLE relay_metrics (
    timestamp DateTime64(3),
    fingerprint String,
    nickname String,
    consensus_weight UInt64,
    observed_bandwidth UInt64,
    advertised_bandwidth UInt64,
    guard_consensus_weight UInt64,
    middle_consensus_weight UInt64,
    exit_consensus_weight UInt64,
    flags Array(String),
    country LowCardinality(String),
    as_number UInt32,
    as_name String,
    platform String,
    contact String,
    contact_hash String,
    running UInt8,
    first_seen DateTime,
    ip_address IPv4
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (fingerprint, timestamp)
SETTINGS index_granularity = 8192;

-- Operator aggregations table
CREATE TABLE operator_metrics (
    timestamp DateTime64(3),
    contact_hash String,
    aroi_domain String,
    total_consensus_weight UInt64,
    total_bandwidth UInt64,
    relay_count UInt32,
    guard_count UInt32,
    middle_count UInt32,
    exit_count UInt32,
    country_count UInt32,
    as_count UInt32,
    platform_diversity_score Float32,
    geographic_diversity_score Float32
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (contact_hash, timestamp);

-- Network health metrics table
CREATE TABLE network_health (
    timestamp DateTime64(3),
    total_relays UInt32,
    total_consensus_weight UInt64,
    total_bandwidth UInt64,
    guard_relays UInt32,
    middle_relays UInt32,
    exit_relays UInt32,
    unique_countries UInt32,
    unique_as_count UInt32,
    geographic_concentration Float32,
    as_concentration Float32
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY timestamp;
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
1. **Archive Processing**
   - Consensus file parsing
   - Historical data extraction
   - Time-series data normalization

2. **Data Quality Assurance**
   - Consistency validation
   - Gap identification and handling
   - Performance optimization

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
- **ClickHouse Cluster**: 3-node setup with 32GB RAM, 1TB SSD each
- **Data Storage**: ~5TB for historical data, ~100GB/year growth
- **Processing Power**: 16-core CPU for data ingestion and queries

### Development
- **Backend Development**: 3-4 months full-time equivalent
- **Frontend Integration**: 1-2 months full-time equivalent
- **Testing and Optimization**: 1 month full-time equivalent

## 🚀 Success Metrics

### Technical Metrics
- **Query Performance**: <2 seconds for complex historical queries
- **Data Freshness**: <30 minutes lag for real-time updates
- **Uptime**: 99.9% availability for analytics queries
- **Storage Efficiency**: <10GB per year of historical data

### User Engagement
- **Page Views**: 50% increase in analytics page engagement
- **Session Duration**: 30% increase in time spent on historical analysis
- **User Retention**: 25% increase in return visitors
- **Feature Adoption**: 80% of operators using historical features

## 🎯 Conclusion

Integrating ClickHouse with allium will transform the platform from a real-time monitoring tool into a comprehensive historical analytics powerhouse. The 20 proposed enhancements will provide unprecedented insights into Tor network evolution, operator performance trends, and network health patterns.

This enhancement will position allium as the definitive platform for Tor network analysis, serving relay operators, researchers, and the broader Tor community with data-driven insights spanning nearly two decades of network history.

The investment in ClickHouse infrastructure will pay dividends through improved operator decision-making, enhanced network planning capabilities, and valuable research insights that benefit the entire Tor ecosystem.