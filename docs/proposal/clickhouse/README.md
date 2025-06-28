# ClickHouse Integration Proposal for Allium

This directory contains the comprehensive proposal for integrating ClickHouse database with allium to enable historical analytics and time-series analysis of Tor relay data.

## Documents

### `clickhouse_sonnet_overview.md`
The main proposal document containing:

- **Executive Summary**: High-level overview of the ClickHouse integration
- **Real-world Schema Design**: Time-series optimized schema based on actual CollecTor data format
- **Top 20 Analytics Enhancements**: Specific improvements for allium web pages
- **Technical Implementation**: Detailed development plan and resource requirements
- **Infrastructure Requirements**: Hardware and deployment specifications based on real data volumes

## Key Features

### Comprehensive Schema
- Based on actual CollecTor consensus data format (https://collector.torproject.org/)
- Single wide table design optimized for time-series analysis
- Custom data types for efficient storage (binary fingerprints, compressed text)
- Materialized views for common aggregation patterns

### Historical Analytics (2007-2025)
- 18+ years of Tor network evolution data
- Per-relay tracking across all consensus measurements
- Operator performance trends and leaderboard evolution
- Geographic and platform diversity analysis

### Real-world Implementation
- Infrastructure sizing based on actual data volumes (~3.5MB consensus files)
- Performance targets and resource calculations
- Integration plan with existing allium architecture
- Security and privacy considerations

## Data Sources

The proposal leverages multiple real Tor network data sources:

1. **CollecTor Archives**: Historical consensus documents (2007-2025)
2. **Onionoo API**: Real-time relay information and uptime data
3. **Directory Authority Votes**: Per-authority flag assignments
4. **Bandwidth Authority Files**: Measured bandwidth data

## Next Steps

1. Review technical implementation details
2. Validate resource requirements and infrastructure costs
3. Plan development phases and milestone timeline
4. Begin initial ClickHouse prototype development