# Allium Uptime Integration Proposals

This directory contains comprehensive proposals for integrating Onionoo API uptime data into the allium Tor relay analytics platform.

## Overview

The uptime integration roadmap provides 10 detailed ideas to enhance allium with comprehensive reliability analytics, giving relay operators better visibility into their network performance and helping users understand overall Tor network health.

## Proposal Documents

### 📋 [Main Proposal: Uptime Integration Roadmap](./uptime_integration_roadmap.md)
**Ideas 1-5**: Core uptime integration features including:
- Reliability Champions Leaderboard (new competitive category)
- Individual Relay Uptime History Charts (detailed visualization)
- Network Health Dashboard (aggregate statistics)
- Flag-Specific Uptime Analysis (Guard/Exit/Authority reliability)
- Operator Reliability Portfolio (comprehensive operator dashboard)

### 📋 [Supplementary Ideas: Advanced Features](./uptime_integration_remaining_ideas.md)
**Ideas 6-10**: Advanced analytics and intelligence features:
- Historical Network Stability Trends (long-term analysis)
- Uptime-Based Relay Recommendations (smart selection)
- Real-time Downtime Alerts (network monitoring)
- Comparative Uptime Analysis (benchmarking)
- Uptime Prediction Modeling (predictive analytics)

## Quick Implementation Guide

### Phase 1: Foundation (Weeks 1-2) 🚀
```bash
# Priority implementations for immediate impact
1. Reliability Champions Leaderboard
2. Network Health Dashboard
```

### Phase 2: Operator Tools (Weeks 3-4) 🛠️
```bash
# Enhanced operator visibility features
3. Individual Relay Uptime Charts
4. Operator Reliability Portfolio
```

### Phase 3: Advanced Analytics (Weeks 5-6) 📊
```bash
# Deep network analysis features
5. Flag-Specific Uptime Analysis
6. Historical Network Stability Trends
```

### Phase 4: Intelligence Features (Weeks 7-8) 🧠
```bash
# Smart recommendations and monitoring
7. Uptime-Based Relay Recommendations
8. Real-time Downtime Alerts
```

### Phase 5: Future Features 🔮
```bash
# Advanced modeling and prediction
9. Comparative Uptime Analysis
10. Uptime Prediction Modeling
```

## Technical Architecture

### Core Components

#### 1. Onionoo Integration Layer
```python
# New uptime data fetching infrastructure
class UptimeDataFetcher:
    def fetch_uptime_data(self, fingerprints: List[str]) -> Dict
    def process_uptime_history(self, uptime_data: Dict) -> Dict
    def calculate_reliability_scores(self, relays: List[Dict]) -> Dict
```

#### 2. Database Extensions
```sql
-- New tables for uptime caching and analysis
CREATE TABLE uptime_cache (
    fingerprint VARCHAR(40) PRIMARY KEY,
    uptime_data JSON,
    last_updated TIMESTAMP,
    INDEX idx_last_updated (last_updated)
);

CREATE TABLE reliability_scores (
    contact_hash VARCHAR(64),
    reliability_score DECIMAL(5,3),
    trend_direction ENUM('improving', 'stable', 'declining'),
    last_calculated TIMESTAMP,
    PRIMARY KEY (contact_hash, last_calculated)
);
```

#### 3. Template Enhancements
```html
<!-- New uptime-specific macros and components -->
{% from "uptime_macros.html" import uptime_chart, reliability_badge, trend_indicator %}

<!-- Enhanced relay detail pages -->
{{ uptime_chart(relay.uptime_data, periods=['1_month', '6_months', '1_year']) }}

<!-- New leaderboard categories -->
{{ reliability_leaderboard(aroi_operators.reliability_champions) }}
```

### API Endpoints

#### Onionoo Uptime API Usage
```bash
# Individual relay uptime
GET https://onionoo.torproject.org/uptime?lookup={fingerprint}

# Bulk relay uptime (for operators)
GET https://onionoo.torproject.org/uptime?lookup={fp1},{fp2},{fp3}

# Response structure:
{
  "relays": [{
    "fingerprint": "...",
    "uptime": {
      "1_month": {
        "first": "2024-01-01 00:00:00",
        "last": "2024-01-31 23:00:00", 
        "interval": 3600,
        "factor": 1.0,
        "values": [999, 999, 0, 999, ...]  // 0-999 normalized values
      }
    },
    "flags": {
      "Running": { "1_month": {...} },
      "Guard": { "1_month": {...} },
      "Exit": { "1_month": {...} }
    }
  }]
}
```

## Visual Mockups

### 1. Reliability Champions Badge
```
┌─────────────────────────────────────┐
│ ⏰ Reliability Master               │
│ torworld.example.org                │
│ 99.7% Uptime Score                  │
│ 847 relays • 45.2 Gbit/s           │
│ 6-month weighted reliability        │
└─────────────────────────────────────┘
```

### 2. Network Health Dashboard
```
┌─────────────────────────────────────┐
│ 🏥 Tor Network Health              │
├─────────────────────────────────────┤
│ [97.3%]  [94.1%]  [8,247] [223]    │
│ Current  30-Day   Online  Offline   │
│                                     │
│ Distribution:                       │
│ ████████ Excellent (>95%): 67.2%    │
│ ████ Good (90-95%): 23.1%           │
│ ██ Fair (80-90%): 7.8%              │
│ ▌ Poor (<80%): 1.9%                 │
└─────────────────────────────────────┘
```

### 3. Individual Relay Uptime Chart
```
┌─────────────────────────────────────┐
│ ⏰ Uptime History                   │
│ [1 Month] [6 Months] [1 Year]      │
│                                     │
│ 100% ┌─────────────────────────────┐ │
│  95% │ ████████████████████████████│ │
│  90% │                             │ │
│      └─────────────────────────────┘ │
│       Jan  Feb  Mar  Apr  May  Jun  │
│                                     │
│ Avg: 98.7% • Current: Online       │
└─────────────────────────────────────┘
```

### 4. Operator Reliability Dashboard
```
┌─────────────────────────────────────┐
│ 📊 Reliability Dashboard            │
│ torworld.example.org                │
├─────────────────────────────────────┤
│           98.7%                     │
│    Overall Reliability Score        │
│                                     │
│ [43] [12] [3] [1]                   │
│ Exc  Good Fair Poor                 │
│                                     │
│ Individual Relays:                  │
│ relay01 98.7% Excellent ✓          │
│ relay02 97.1% Good     ✓           │
│ relay03 89.2% Fair     ⚠️           │
└─────────────────────────────────────┘
```

## Performance Considerations

### Caching Strategy
- **Level 1**: In-memory cache for frequently accessed relays (5 minutes TTL)
- **Level 2**: Database cache for uptime data (30 minutes TTL)
- **Level 3**: Pre-computed reliability scores (daily refresh)

### API Rate Limiting
- Batch Onionoo requests for efficiency
- Maximum 50 fingerprints per request
- Respect Onionoo rate limits and caching headers
- Background processing for large operators

### Data Processing
- Asynchronous uptime data collection
- Progressive loading for large datasets
- Sampling strategies for network-wide statistics
- Background calculation of complex metrics

## Impact Assessment

### For Relay Operators 👥
- **Better Visibility**: Comprehensive uptime analytics and trends
- **Actionable Insights**: Specific recommendations for infrastructure improvement
- **Performance Benchmarking**: Compare against network averages and peers
- **Early Warning System**: Predictive alerts for potential issues

### For Users 🌍
- **Informed Selection**: Choose relays based on reliability data
- **Network Understanding**: Learn about overall Tor network health
- **Transparency**: Clear visibility into network operations
- **Education**: Understand the importance of relay reliability

### For Network Health 💪
- **Incentivized Reliability**: Competitive recognition for stable operators
- **Community Recognition**: Public acknowledgment of reliable contributors
- **Data-Driven Monitoring**: Enhanced network health tracking
- **Troubleshooting Support**: Better tools for diagnosing network issues

## Getting Started

### Prerequisites
```bash
# Ensure allium development environment is set up
cd allium/
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Development Setup
```bash
# Create feature branch for uptime integration
git checkout -b feature/uptime-integration

# Start with Phase 1 implementation
cd allium/lib/
# Implement _fetch_uptime_data() in relays.py
# Add reliability_champions to aroileaders.py
```

### Testing
```bash
# Test with small dataset first
python3 allium.py --progress --onionoo-url "https://onionoo.torproject.org/details?limit=50"

# Verify uptime data integration
curl "https://onionoo.torproject.org/uptime?lookup=fingerprint1,fingerprint2"
```

## Contributing

See the main [CONTRIB.md](../../CONTRIB.md) for general contribution guidelines.

### Uptime Integration Specific Guidelines
1. **API Usage**: Respect Onionoo API rate limits and use caching
2. **Performance**: Always consider the impact on generation time
3. **User Experience**: Provide clear explanations of uptime metrics
4. **Error Handling**: Gracefully handle Onionoo API failures
5. **Testing**: Test with both synthetic and real uptime data

## Questions and Support

- **General Allium**: See main project documentation
- **Uptime Integration**: Create issues with `uptime-integration` label
- **Performance**: Tag issues with `performance` for optimization discussions
- **Design Feedback**: Use `ui-ux` label for visual mockup feedback

---

**Last Updated**: January 2025  
**Status**: Proposal Phase - Ready for Implementation  
**Estimated Effort**: 8-12 weeks for full implementation across all phases 