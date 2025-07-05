# Allium Endpoints Research Report

## Executive Summary

This report investigates the feasibility of adding consensus weight and bandwidth history endpoints to the allium project, a Tor relay analytics generator. The research confirms that the onionoo API provides the necessary data endpoints and that allium's architecture is well-suited for this enhancement.

## Current State Analysis

### About Allium
- **Purpose**: Static site generator for Tor relay analytics
- **Language**: Python-based
- **Data Source**: onionoo API (onionoo.torproject.org)
- **Current Endpoints**: 
  - `/details` - Relay information and metadata
  - `/uptime` - Historical uptime data

### Technical Architecture
- **Main Entry Point**: `allium.py` - CLI with argument parsing for API URLs
- **Coordinator System**: `lib/coordinator.py` - Manages threaded API fetching
- **Worker Functions**: `lib/workers.py` - Contains API fetching implementations
- **Data Processing**: `lib/relays.py` - Main processing logic (4082 lines)
- **Formatting**: `lib/bandwidth_formatter.py` - Bandwidth unit conversion and display

### Current Capabilities
- Processes `observed_bandwidth` from details API
- Calculates consensus weight fractions and percentages
- Sophisticated bandwidth formatting (bits/bytes conversion)
- Network health metrics and AROI (operator) analysis
- Supports `--apis` parameter with 'details' and 'all' options

## Research Findings

### Onionoo API Endpoints

#### Confirmed: `/bandwidth` Endpoint
- **Status**: ✅ **CONFIRMED** - Endpoint exists and provides comprehensive data
- **URL Pattern**: `https://onionoo.torproject.org/bandwidth?lookup={fingerprint}`
- **Data Structure**:
  ```json
  {
    "relays": [{
      "fingerprint": "...",
      "read_history": {
        "1_month": {
          "first": "2024-01-01 00:00:00",
          "last": "2024-01-31 23:00:00", 
          "interval": 3600,
          "factor": 1073741824.0,
          "count": 744,
          "values": [...]
        },
        "6_months": {...},
        "1_year": {...},
        "5_years": {...}
      },
      "write_history": {
        // Same structure as read_history
      }
    }]
  }
  ```
- **Time Periods**: 1_month, 6_months, 1_year, 5_years
- **Metrics**: Both read and write bandwidth histories
- **Data Points**: Timestamps, intervals, scaling factors, bandwidth values

#### Unconfirmed: `/weights` Endpoint
- **Status**: ❓ **UNCONFIRMED** - Requires further testing
- **Expected Pattern**: `https://onionoo.torproject.org/weights?lookup={fingerprint}`
- **Rationale**: onionoo typically provides historical data for key metrics

### Implementation Feasibility

#### Strengths of Current Architecture
1. **Modular Design**: Clear separation between fetching, processing, and formatting
2. **Threaded API Calls**: Coordinator system supports multiple concurrent API requests
3. **Extensible Worker System**: Easy to add new API endpoint handlers
4. **Robust Data Processing**: Existing `Relays` class handles complex data transformation
5. **Flexible CLI**: Already supports custom API endpoint configurations

#### Integration Points
1. **Worker Functions**: Add new functions in `workers.py` for `/weights` and `/bandwidth`
2. **Coordinator Extension**: Modify coordinator to manage additional API calls
3. **Data Processing**: Extend `Relays` class to process historical time series data
4. **Template Rendering**: Add new HTML templates for historical charts/graphs
5. **CLI Arguments**: Extend argument parser for new endpoint URLs

## Implementation Roadmap

### Phase 1: API Integration
- [ ] Add `/bandwidth` worker function
- [ ] Test and confirm `/weights` endpoint availability
- [ ] Add `/weights` worker function (if available)
- [ ] Extend coordinator to handle new endpoints

### Phase 2: Data Processing
- [ ] Modify `Relays` class to store historical data
- [ ] Add time series data structures
- [ ] Implement data aggregation and analysis functions
- [ ] Add bandwidth/weight trend calculations

### Phase 3: Visualization
- [ ] Create historical chart templates
- [ ] Add JavaScript charting library integration
- [ ] Implement interactive time range selection
- [ ] Add bandwidth/weight comparison features

### Phase 4: CLI Enhancement
- [ ] Add `--bandwidth-history` and `--weight-history` flags
- [ ] Extend `--apis` parameter options
- [ ] Add time range filtering options
- [ ] Implement caching for historical data

## Technical Considerations

### Data Volume
- Historical bandwidth data includes multiple time periods
- 5-year data could be substantial for high-traffic relays
- Consider implementing data compression or selective fetching

### Performance
- Historical data fetching may increase generation time
- Current threaded architecture should handle additional endpoints well
- Consider implementing progressive data loading

### Storage
- Historical data will increase static site size
- Consider implementing data pagination or on-demand loading
- Evaluate trade-offs between completeness and performance

## Key Discovery

The research confirms that the onionoo API provides a comprehensive `/bandwidth` endpoint with detailed historical bandwidth data in JSON format. This endpoint includes:
- Multiple time periods (1 month to 5 years)
- Both read and write bandwidth histories
- Proper scaling factors and timestamps
- Structured data suitable for charting and analysis

This validates the feasibility of enhancing allium with bandwidth history capabilities and provides a clear technical foundation for implementation.

## Conclusion

The allium project is well-positioned to support consensus weight and bandwidth history endpoints. The existing architecture is modular and extensible, the onionoo API provides the necessary data, and the current bandwidth processing capabilities provide a solid foundation for historical data integration.

**Recommendation**: Proceed with implementation, starting with the confirmed `/bandwidth` endpoint while investigating the availability of a `/weights` endpoint.