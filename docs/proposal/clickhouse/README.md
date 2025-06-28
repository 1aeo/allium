# ClickHouse Analytics Integration for Allium

This branch contains a comprehensive proposal for integrating ClickHouse database into the Allium project to provide historical analytics for Tor relay operators.

## Branch Contents

### 1. [clickhouse_opus_overview.md](docs/proposal/clickhouse/clickhouse_opus_overview.md)
The main proposal document outlining:
- Executive summary of the ClickHouse integration
- Data architecture for 18+ years of Tor network data (2007-2025)
- ClickHouse schema design optimized for time-series analytics
- **Top 20 analytics enhancements** with specific implementation details
- Implementation strategy with 4-phase rollout plan
- Performance projections and technical benefits

### 2. [improved_time_series_schema.md](improved_time_series_schema.md)
Enhanced time-series schema based on real Tor descriptor data analysis:
- **Core Tables**: 6 specialized time-series tables capturing relay status, authority measurements, bandwidth data, descriptors, extra info, and GeoIP
- **Materialized Views**: 5 pre-aggregated views for relay lifecycle, network health, operator analytics, AS metrics, and country statistics
- **Real Data**: Schema designed from actual consensus and descriptor formats from June 28, 2025
- **Query Examples**: Production-ready queries for common analytics use cases
- **Performance Optimizations**: Compression, indexing, and partitioning strategies

### 3. [optimal_timeseries_schema_design.md](optimal_timeseries_schema_design.md) ⭐ **NEWEST**
The definitive schema design based on real relay data (lilpeep example) addressing key design questions:
- **Design Decisions**: Comprehensive rationale for schema choices
- **Hybrid Approach**: Main measurements table + supporting tables
- **Authority Data**: Innovative bitmap encoding for per-authority flags and measurements
- **Storage Optimization**: Binary fingerprints, materialized columns, strategic denormalization
- **Query Examples**: Complex queries showing authority disagreements, network health analysis
- **Performance**: 90% space reduction for flags, 50% for fingerprints, ~25GB/year for 9000 relays

Key innovations:
- Per-authority flag columns using bitmaps (flags_moria1, flags_gabelmoo, etc.)
- Separate bandwidth measurements per authority
- Nested structure for variable authority statistics
- Binary encoding for fingerprints and keys
- Materialized columns for common flag queries

### 4. [TECHNICAL_SPEC_INGESTION.md](docs/proposal/clickhouse/TECHNICAL_SPEC_INGESTION.md)
Detailed technical specification covering:
- Data ingestion pipeline architecture
- Parsing logic for consensus files, server descriptors, extra-info, and bandwidth files
- ETL pipeline with code examples
- Real-time ingestion strategy
- Performance optimization techniques
- Error handling and recovery mechanisms
- Storage optimization with partitioning and compression

## Key Schema Design Decisions

### Time-Series Focus
The improved schema treats Tor network data as time-series data with:
- **Hourly snapshots** of every relay's state from consensus documents
- **Change tracking** for nicknames, IPs, ports, and flags over time
- **Lifecycle analysis** including first seen, last seen, restarts, and IP changes
- **Historical aggregations** by operator, AS, country, and version

### Optimal Design Principles
Based on extensive analysis:
1. **Hybrid table structure** - Main measurements + supporting tables
2. **Immutable design** - No updates, only inserts
3. **Smart denormalization** - Balance between query speed and storage
4. **Binary encoding** - 50% space savings on fingerprints
5. **Bitmap flags** - 90% space savings on flag arrays
6. **Per-authority columns** - Fast queries on authority opinions

### Core Tables Structure

1. **relay_measurements** - Main time-series table with hourly snapshots including all authority data
2. **relay_descriptors** - Detailed relay info (updates less frequently)
3. **bandwidth_measurements** - Scanner measurement details
4. **relay_extra_info** - Statistical data from extra-info descriptors
5. **network_stats_hourly** - Pre-aggregated network statistics
6. **relay_lifecycle** - Pre-computed relay history tracking

### Capturing Authority Opinions

The schema captures both individual directory authority opinions and consensus:
- 8 authority flag columns (flags_moria1, flags_gabelmoo, etc.) as bitmaps
- 8 authority bandwidth measurements (bw_measured_moria1, etc.)
- Consensus flags and bandwidth as separate fields
- Authority statistics in nested structure for flexibility

## Key Highlights

### Top 20 ClickHouse Analytics Enhancements

1. **Historical Bandwidth Charts** - Network-wide bandwidth trends over time
2. **Relay Lifetime Analysis** - Complete lifecycle visualization for individual relays
3. **Operator Performance Trending** - Historical charts of operator contributions
4. **Geographic Diversity Timeline** - Evolution of relay distribution globally
5. **AS Centralization Analysis** - Track concentration risks over time
6. **Consensus Weight Contribution Leaderboards** - Historical rankings by time period
7. **Flag Stability Analytics** - Heatmaps showing flag presence patterns
8. **Network Event Detection** - Automatic anomaly detection
9. **Platform Evolution Tracking** - OS/version distribution over time
10. **Exit Policy Analytics** - Historical exit policy changes and impact
11. **Predictive Relay Scoring** - ML-based stability predictions
12. **Network Growth Projections** - Forecasting models for capacity planning
13. **Operator Retention Analysis** - Cohort analysis of operator lifecycles
14. **Consensus Weight Distribution** - Decentralization metrics over time
15. **IPv6 Adoption Timeline** - Progressive adoption visualization
16. **Relay Family Evolution** - Interactive family relationship trees
17. **Bandwidth Authority Comparison** - Measurement consistency analysis
18. **Geographic Correlation Analysis** - Relay density vs internet freedom
19. **Operator Milestone Tracking** - Achievement system for contributors
20. **Network Resilience Scoring** - Real-time diversity metrics

### Data Volume Estimates
- **Consensus Files**: ~157GB compressed (2007-2025)
- **Server Descriptors**: ~500GB compressed
- **Extra Info**: ~300GB compressed
- **Bandwidth Files**: ~50GB compressed
- **Total in ClickHouse**: ~50-100GB (10-30x compression)
- **Optimal schema**: ~25GB/year for 9000 relays

### Performance Targets
- Full network history scan: <1 second
- Complex aggregations: <100ms
- Real-time dashboard updates: <50ms
- Ingestion rate: 100k+ consensus records/second
- Authority disagreement analysis: <200ms

## Benefits for Tor Network

1. **For Relay Operators**:
   - Historical performance tracking with complete relay lifecycle
   - Authority voting patterns and disagreement analysis
   - Predictive analytics for planning and optimization
   - Achievement recognition system with historical leaderboards
   - Comparative analysis with network averages over time

2. **For Tor Project**:
   - Network health monitoring with anomaly detection
   - Authority consensus analysis and voting patterns
   - Trend analysis for strategic planning
   - Early warning system for network issues
   - Data-driven decision making with historical context

3. **For Researchers**:
   - 18+ years of network evolution data
   - Directory authority behavior analysis
   - Geographic and political correlation analysis
   - Network resilience studies
   - Decentralization progress tracking

## Implementation Approach

The proposal follows a phased approach:
- **Weeks 1-4**: Data ingestion pipeline setup
- **Weeks 5-8**: Core analytics development
- **Weeks 9-12**: Visualization integration
- **Weeks 13-16**: Advanced features and ML models

## Technical Stack
- **Database**: ClickHouse (columnar OLAP database)
- **Ingestion**: Python async pipeline with parallel processing
- **Visualization**: Chart.js/D3.js for interactive graphs
- **Caching**: Redis for query result caching
- **API**: RESTful endpoints for data access

## Sample Queries

### Relay Performance History
```sql
SELECT 
    measurement_hour,
    nickname,
    consensus_weight,
    decode_flags(consensus_flags) as consensus_flags,
    concat(toString(ipv4), ':', toString(or_port)) as address
FROM relay_measurements
WHERE fingerprint = hex_to_fingerprint('YOUR_RELAY_FINGERPRINT_HEX')
ORDER BY measurement_hour DESC;
```

### Authority Disagreement Analysis
```sql
SELECT 
    measurement_hour,
    countDistinct([flags_moria1, flags_gabelmoo, flags_dannenberg, 
                   flags_maatuska, flags_faravahar, flags_longclaw, 
                   flags_bastet]) as flag_disagreement_count,
    arrayFilter(x -> x > 0, [bw_measured_moria1, bw_measured_gabelmoo, 
                             bw_measured_dannenberg]) as bandwidth_measurements
FROM relay_measurements
WHERE fingerprint = hex_to_fingerprint('3D0D3172FA0C11AC7206883832F65BB8695CB1DF')
ORDER BY measurement_hour DESC
LIMIT 24;
```

### Top Operators by Contribution
```sql
SELECT
    d.contact,
    count(DISTINCT m.fingerprint) as relay_count,
    sum(m.consensus_weight) as total_consensus_weight
FROM relay_measurements m
INNER JOIN relay_descriptors d ON m.descriptor_digest = d.descriptor_digest
WHERE m.measurement_hour >= now() - INTERVAL 30 DAY
GROUP BY d.contact
ORDER BY total_consensus_weight DESC
LIMIT 100;
```

## Next Steps

1. Review and approve the optimal time-series schema design
2. Set up development ClickHouse instance
3. Begin historical data collection from collector.torproject.org
4. Implement data ingestion pipeline with new schema
5. Prototype visualizations using materialized views
6. Gather operator feedback on analytics priorities

---

**Note**: The optimal schema is based on analysis of real Tor consensus and descriptor formats from collector.torproject.org (June 2025 data), ensuring all features are technically feasible with actually available data. The lilpeep relay data was used as a concrete example to validate all schema design decisions.