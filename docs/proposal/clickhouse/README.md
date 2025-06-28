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

### 2. [TECHNICAL_SPEC_INGESTION.md](docs/proposal/clickhouse/TECHNICAL_SPEC_INGESTION.md)
Detailed technical specification covering:
- Data ingestion pipeline architecture
- Parsing logic for consensus files, server descriptors, extra-info, and bandwidth files
- ETL pipeline with code examples
- Real-time ingestion strategy
- Performance optimization techniques
- Error handling and recovery mechanisms
- Storage optimization with partitioning and compression

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

### Performance Targets
- Full network history scan: <1 second
- Complex aggregations: <100ms
- Real-time dashboard updates: <50ms
- Ingestion rate: 100k+ consensus records/second

## Benefits for Tor Network

1. **For Relay Operators**:
   - Historical performance tracking
   - Predictive analytics for planning
   - Achievement recognition system
   - Comparative analysis with network averages

2. **For Tor Project**:
   - Network health monitoring
   - Trend analysis for strategic planning
   - Early warning system for anomalies
   - Data-driven decision making

3. **For Researchers**:
   - 18+ years of network evolution data
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

## Next Steps

1. Review and approve the proposal
2. Set up development ClickHouse instance
3. Begin historical data collection from collector.torproject.org
4. Prototype first visualization on test data
5. Gather operator feedback on desired analytics

---

**Note**: This proposal is based on analysis of real Tor consensus and descriptor formats from collector.torproject.org, ensuring all suggested features are technically feasible with available data.