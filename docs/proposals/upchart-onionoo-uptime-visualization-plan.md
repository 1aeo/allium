# Upchart: Onionoo Uptime API Visualization Plan

**Branch:** upchart  
**Date:** 2025-01-27  
**Status:** Proposal  

## Executive Summary

This proposal outlines a comprehensive plan to create chart visualizations based on the Onionoo uptime API data. After researching the available data from the Tor network's Onionoo service, we have identified the top 10 most valuable chart types that will provide actionable insights into Tor network reliability and performance.

## Onionoo Uptime API Overview

### Available Data Sources

The Onionoo uptime API (`https://onionoo.torproject.org/uptime`) provides:

1. **Relay Uptime Objects**
   - Fractional uptime data (0 to 1 scale)
   - Time periods: 1_month, 6_months, 1_year, 5_years
   - Relay flags uptime (Running, Exit, Guard, HSDir, Stable, Fast, Valid, etc.)

2. **Bridge Uptime Objects**
   - Similar structure to relay uptime
   - Sanitized data for privacy protection

3. **Graph History Objects**
   - Temporal data with configurable intervals
   - Normalized values (0-999) with scaling factors
   - UTC timestamps for first and last data points

### Filtering Capabilities

- **Geographic:** Country, region, city
- **Network:** Autonomous System (AS), IP ranges
- **Technical:** Tor version, operating system, relay flags
- **Temporal:** Date ranges, first/last seen periods
- **Type:** Relay vs bridge classification

## Top 10 Chart Visualizations (Prioritized)

### 1. **Global Network Reliability Dashboard** ⭐⭐⭐⭐⭐

**Priority:** Highest  
**Business Value:** Critical network health overview  
**Technical Complexity:** Medium  

**Description:** Real-time dashboard showing overall Tor network uptime statistics with key performance indicators.

**Mockup Features:**
```
┌─ Global Tor Network Health ─────────────────────────────┐
│ Overall Network Uptime: 94.2% ↗ (+0.8% vs last month) │
│                                                         │
│ Key Metrics:                                            │
│ • Active Relays: 7,234 ■■■■■■■■■□                       │
│ • Exit Relays: 1,847 ■■■■■■■□□□                         │
│ • Guard Relays: 2,391 ■■■■■■■■■□                        │
│ • Bridge Nodes: 1,205 ■■■■■■□□□□                        │
│                                                         │
│ Network Stability Trend (30 days):                     │
│ 100% ┤                                                 │
│  95% ┤    ╭─╮     ╭─╮                                  │
│  90% ┤ ╭─╯   ╰─╮ ╱   ╰─╮                               │
│  85% ┤╱         ╰╱       ╰─                            │
│      └────────────────────────────────────────────────┤
│       Week 1   Week 2   Week 3   Week 4               │
└─────────────────────────────────────────────────────────┘
```

**Data Requirements:**
- Aggregate uptime data across all relays
- Real-time status updates
- Historical trend data (1 month minimum)

---

### 2. **Geographic Uptime Heatmap** ⭐⭐⭐⭐⭐

**Priority:** Highest  
**Business Value:** Critical for identifying regional reliability issues  
**Technical Complexity:** High  

**Description:** Interactive world map showing Tor network uptime by country/region with color-coded reliability indicators.

**Mockup Features:**
```
┌─ Tor Network Geographic Reliability ───────────────────┐
│                                                         │
│     🌍 Interactive World Map                            │
│                                                         │
│ Legend: Uptime Percentage                               │
│ ■ 95-100% (Excellent)     ■ 85-90% (Fair)             │
│ ■ 90-95% (Good)           ■ <85% (Poor)               │
│                                                         │
│ Top Countries by Reliability:                          │
│ 🇩🇪 Germany     97.2% ■■■■■■■■■■                        │
│ 🇳🇱 Netherlands 96.8% ■■■■■■■■■■                        │
│ 🇺🇸 United States 94.1% ■■■■■■■■■□                      │
│ 🇫🇷 France      93.7% ■■■■■■■■■□                        │
│ 🇨🇭 Switzerland 93.2% ■■■■■■■■■□                        │
│                                                         │
│ Filters: [All Countries ▼] [Last 30 Days ▼]           │
└─────────────────────────────────────────────────────────┘
```

**Data Requirements:**
- Country-level uptime aggregation
- Geographic coordinate mapping
- Real-time updates with historical baselines

---

### 3. **Relay Performance Comparison Matrix** ⭐⭐⭐⭐⭐

**Priority:** High  
**Business Value:** Essential for network optimization  
**Technical Complexity:** Medium  

**Description:** Comparative analysis of relay performance across different roles (Guard, Middle, Exit) and configurations.

**Mockup Features:**
```
┌─ Relay Role Performance Analysis ──────────────────────┐
│                                                         │
│ Average Uptime by Role (Last 6 Months):                │
│                                                         │
│ Guard Relays    ■■■■■■■■■□ 95.7%                        │
│ Middle Relays   ■■■■■■■■■■ 97.1%                        │
│ Exit Relays     ■■■■■■■■□□ 91.3%                        │
│ Directory       ■■■■■■■■■□ 94.8%                        │
│ HSDir           ■■■■■■■■■■ 96.4%                        │
│                                                         │
│ Performance Correlation:                                │
│ Bandwidth vs Uptime      ↗ +0.73 (Strong positive)     │
│ Age vs Stability         ↗ +0.61 (Moderate positive)   │
│ Flag Count vs Reliability ↗ +0.58 (Moderate positive)  │
│                                                         │
│ [Export Data] [Detailed View] [Configure Timeframe]    │
└─────────────────────────────────────────────────────────┘
```

**Data Requirements:**
- Relay flag classification data
- Multi-timeframe uptime statistics
- Performance correlation metrics

---

### 4. **Temporal Reliability Trends** ⭐⭐⭐⭐⭐

**Priority:** High  
**Business Value:** Critical for capacity planning and issue detection  
**Technical Complexity:** Medium  

**Description:** Time-series analysis showing uptime patterns over different periods with anomaly detection.

**Mockup Features:**
```
┌─ Network Uptime Trends & Patterns ─────────────────────┐
│                                                         │
│ 6-Month Trend Analysis:                                │
│ 100% ┤                               ●                 │
│  98% ┤     ●─●─●     ●─●─●─●     ●─●─●                 │
│  96% ┤ ●─●─●     ●─●─●       ●─●─●                     │
│  94% ┤●                                                │
│      └────┬────┬────┬────┬────┬────┬─────────────────┤
│          Jan  Feb  Mar  Apr  May  Jun               │
│                                                         │
│ Detected Patterns:                                      │
│ 🔍 Weekly dip on Sundays (-2.1% avg)                   │
│ 🔍 Monthly improvement trend (+0.3%/month)             │
│ ⚠️  Anomaly detected: April 15-17 (-8.2%)              │
│                                                         │
│ Seasonal Analysis: [View] Predictive Model: [View]     │
└─────────────────────────────────────────────────────────┘
```

**Data Requirements:**
- High-resolution temporal data
- Pattern recognition algorithms
- Anomaly detection capabilities

---

### 5. **Exit Relay Availability Monitor** ⭐⭐⭐⭐⭐

**Priority:** High  
**Business Value:** Critical for network functionality  
**Technical Complexity:** Medium-High  

**Description:** Specialized monitoring for exit relays, the most critical and vulnerable network components.

**Mockup Features:**
```
┌─ Exit Relay Critical Monitoring ───────────────────────┐
│                                                         │
│ Exit Relay Health Summary:                              │
│ Total Exit Relays: 1,847    Available: 1,682 (91.1%)  │
│                                                         │
│ Availability by Exit Policy:                           │
│ Open Exit (All Ports)     ■■■■■■■■□□ 89.3% (164 relays) │
│ Reduced Exit (Web+Email)  ■■■■■■■■■□ 92.7% (1,205)      │
│ Limited Exit (Web Only)   ■■■■■■■■■■ 94.1% (313)        │
│                                                         │
│ Geographic Distribution:                                │
│ 🇺🇸 USA      487 relays ■■■■■■■■■■ 26.4%                │
│ 🇩🇪 Germany  312 relays ■■■■■■■□□□ 16.9%                │
│ 🇳🇱 Netherlands 198 ■■■■■□□□□□ 10.7%                    │
│                                                         │
│ ⚠️  Critical Alerts: 3 countries below 85% threshold   │
│ [View Details] [Configure Alerts] [Export Report]      │
└─────────────────────────────────────────────────────────┘
```

**Data Requirements:**
- Exit policy classification
- Real-time availability tracking
- Geographic distribution analysis

---

### 6. **Bridge Network Resilience Dashboard** ⭐⭐⭐⭐⭐

**Priority:** High  
**Business Value:** Essential for censorship circumvention  
**Technical Complexity:** High  

**Description:** Specialized monitoring for bridge relays with privacy-aware visualizations.

**Mockup Features:**
```
┌─ Bridge Network Resilience (Privacy-Safe View) ────────┐
│                                                         │
│ Bridge Availability Status:                            │
│ Total Active Bridges: 1,205                            │
│ Average Uptime: 88.7% ⚠️ (Below 90% threshold)         │
│                                                         │
│ Transport Type Distribution:                            │
│ obfs4        ■■■■■■■■■■ 74.2% (894 bridges)            │
│ vanilla      ■■■■□□□□□□ 18.1% (218 bridges)            │
│ snowflake    ■■□□□□□□□□ 5.2% (63 bridges)             │
│ meek         ■□□□□□□□□□ 2.5% (30 bridges)             │
│                                                         │
│ Regional Availability (Anonymized):                    │
│ High-Censorship Regions:   78.3% ⚠️                    │
│ Medium-Censorship Regions: 91.2% ✓                     │
│ Low-Censorship Regions:    94.7% ✓                     │
│                                                         │
│ Trend: 7-day availability ↗ +3.2%                      │
│ [Privacy Controls] [Transport Analysis] [Alerts]       │
└─────────────────────────────────────────────────────────┘
```

**Data Requirements:**
- Bridge transport classification
- Anonymized geographic indicators
- Censorship resistance metrics

---

### 7. **Network Fault Analysis & Root Cause Dashboard** ⭐⭐⭐⭐⭐

**Priority:** High  
**Business Value:** Essential for rapid incident response  
**Technical Complexity:** High  

**Description:** Advanced analytics for identifying and diagnosing network reliability issues.

**Mockup Features:**
```
┌─ Network Fault Analysis & Diagnostics ─────────────────┐
│                                                         │
│ Active Issues Detected: 🔴 3 Critical  🟡 7 Warning    │
│                                                         │
│ Issue #1: Eastern Europe Relay Drop                    │
│ Impact: 312 relays affected (-15.2% regional capacity) │
│ Duration: 4h 23m    First Detected: 14:32 UTC         │
│ Likely Cause: AS-level routing issue                   │
│ ┌─Affected Countries────────────────────────────────┐   │
│ │ 🇵🇱 Poland    -89 relays (-67%)                  │   │
│ │ 🇨🇿 Czech Rep -45 relays (-71%)                  │   │
│ │ 🇭🇺 Hungary   -38 relays (-58%)                  │   │
│ └─────────────────────────────────────────────────────┘   │
│                                                         │
│ Automated Response: ✓ Alert sent to operators          │
│                    ✓ Load balanced to other regions   │
│                    ⏳ Investigating with AS providers  │
│                                                         │
│ [Incident Timeline] [Affected Relays] [Response Log]   │
└─────────────────────────────────────────────────────────┘
```

**Data Requirements:**
- Real-time anomaly detection
- Correlation analysis across multiple dimensions
- Automated alerting systems

---

### 8. **Tor Version Adoption & Stability Analysis** ⭐⭐⭐⭐⭐

**Priority:** Medium-High  
**Business Value:** Important for development planning  
**Technical Complexity:** Medium  

**Description:** Analysis of Tor software version distribution and their respective reliability profiles.

**Mockup Features:**
```
┌─ Tor Version Stability & Adoption Metrics ─────────────┐
│                                                         │
│ Version Distribution (Active Relays):                  │
│                                                         │
│ 0.4.8.x ■■■■■■■■■■ 67.2% (4,863 relays) Stable ✓      │
│ 0.4.7.x ■■■■■□□□□□ 24.1% (1,744 relays) Legacy ⚠️      │
│ 0.4.9.x ■■□□□□□□□□ 6.8% (492 relays) Alpha ⚠️          │
│ Other   ■□□□□□□□□□ 1.9% (135 relays) Mixed              │
│                                                         │
│ Reliability by Version:                                │
│ 0.4.8.10: 96.7% uptime ■■■■■■■■■■ (Recommended)        │
│ 0.4.8.9:  95.1% uptime ■■■■■■■■■□                      │
│ 0.4.7.16: 94.8% uptime ■■■■■■■■■□                      │
│ 0.4.9.1:  91.2% uptime ■■■■■■■■□□ (Alpha - expected)    │
│                                                         │
│ Upgrade Trends: 📈 23% moved to 0.4.8.x this month    │
│ [Version Details] [Upgrade Recommendations]            │
└─────────────────────────────────────────────────────────┘
```

**Data Requirements:**
- Tor version string parsing
- Version-specific uptime correlation
- Adoption trend tracking

---

### 9. **Autonomous System (AS) Network Quality Report** ⭐⭐⭐⭐⭐

**Priority:** Medium-High  
**Business Value:** Important for network diversity  
**Technical Complexity:** Medium-High  

**Description:** Analysis of Tor relay performance by hosting provider and autonomous system.

**Mockup Features:**
```
┌─ Hosting Provider & AS Performance Analysis ───────────┐
│                                                         │
│ Top Autonomous Systems by Relay Count & Performance:   │
│                                                         │
│ AS13335 (Cloudflare)     147 relays | 98.2% uptime ★★★ │
│ AS16509 (Amazon AWS)     134 relays | 95.7% uptime ★★★ │
│ AS24940 (Hetzner)        98 relays  | 97.1% uptime ★★★ │
│ AS8560 (IONOS)           87 relays  | 93.4% uptime ★★☆ │
│ AS14061 (DigitalOcean)   76 relays  | 96.3% uptime ★★★ │
│                                                         │
│ Diversity Metrics:                                      │
│ Total Unique AS: 1,247                                 │
│ Top 10 AS Concentration: 34.2% (Healthy ✓)            │
│ Geographic AS Distribution: Well-distributed ✓          │
│                                                         │
│ Risk Assessment:                                        │
│ ⚠️  AS8560 showing declining performance trend          │
│ ✓  Good diversity - no single AS >10% of network       │
│                                                         │
│ [AS Details] [Diversity Report] [Contact Providers]    │
└─────────────────────────────────────────────────────────┘
```

**Data Requirements:**
- AS number mapping and organization names
- AS-specific uptime aggregation
- Network diversity calculations

---

### 10. **Predictive Capacity Planning Dashboard** ⭐⭐⭐⭐⭐

**Priority:** Medium  
**Business Value:** Important for long-term network health  
**Technical Complexity:** High  

**Description:** Machine learning-powered predictions for network capacity and reliability trends.

**Mockup Features:**
```
┌─ Predictive Network Capacity Analysis ─────────────────┐
│                                                         │
│ 6-Month Capacity Forecast:                             │
│                                                         │
│ Predicted Network Growth:                               │
│ Current Capacity: 7,234 relays                         │
│ 3-Month Projection: 7,580 relays (+4.8%) ↗             │
│ 6-Month Projection: 8,120 relays (+12.2%) ↗            │
│                                                         │
│ Reliability Forecast:                                  │
│ 100% ┤                     ┌─ Predicted                 │
│  95% ┤ ●─●─●─●─●─●─●─●─●─●─┘                            │
│  90% ┤                                                 │
│      └─────────────────────────────────────────────────┤
│       Current    +1mo    +3mo    +6mo                 │
│                                                         │
│ Risk Factors Identified:                               │
│ 🔍 Aging hardware in 23% of long-running relays        │
│ 🔍 Potential exit relay shortage in Q3                 │
│ ✓  Strong geographic expansion trend                   │
│                                                         │
│ Confidence Interval: ±2.3%  Model Accuracy: 89.4%     │
│ [Model Details] [Risk Mitigation] [Export Forecast]    │
└─────────────────────────────────────────────────────────┘
```

**Data Requirements:**
- Historical growth patterns
- Machine learning model integration
- Multiple variable correlation analysis

---

## Implementation Strategy

### Phase 1: Foundation (Weeks 1-2)
1. Set up data pipeline from Onionoo uptime API
2. Implement basic charting infrastructure 
3. Create responsive web framework
4. Build charts #1 (Global Dashboard) and #2 (Geographic Heatmap)

### Phase 2: Core Analytics (Weeks 3-4)
1. Implement charts #3 (Relay Comparison) and #4 (Temporal Trends)
2. Add advanced filtering capabilities
3. Create data export functionality
4. Build charts #5 (Exit Relay Monitor) and #6 (Bridge Dashboard)

### Phase 3: Advanced Features (Weeks 5-6)
1. Implement charts #7 (Fault Analysis) and #8 (Version Analysis)
2. Add real-time data streaming
3. Create automated alerting system
4. Build charts #9 (AS Analysis) and #10 (Predictive Dashboard)

### Phase 4: Polish & Deployment (Weeks 7-8)
1. User interface refinement
2. Performance optimization
3. Comprehensive testing
4. Documentation completion
5. Production deployment

## Technical Architecture

### Data Flow
```
Onionoo API → Data Processor → Time Series DB → Chart Renderer → Web UI
     ↓              ↓              ↓               ↓           ↓
- Real-time    - Validation   - Historical    - Interactive  - User
- Historical   - Aggregation  - Analytics     - Real-time    - Responsive
- Filtering    - Transform    - Storage       - Export       - Mobile-ready
```

### Technology Stack
- **Frontend:** React/Vue.js with D3.js for advanced visualizations
- **Backend:** Python/FastAPI or Node.js for API integration
- **Database:** InfluxDB or TimescaleDB for time-series data
- **Visualization:** Chart.js, D3.js, and custom components
- **Deployment:** Docker containers with CI/CD pipeline

## Success Metrics

### Quantitative Goals
- **Performance:** Page load times <2 seconds
- **Accuracy:** 99.5% data accuracy vs Onionoo source
- **Reliability:** 99.9% uptime for visualization service
- **Coverage:** Support for 100% of available Onionoo uptime data

### Qualitative Goals
- **Usability:** Intuitive interface requiring minimal training
- **Actionability:** Clear insights leading to network improvements
- **Scalability:** Architecture supporting future data volume growth
- **Accessibility:** WCAG 2.1 AA compliance for inclusive access

## Risk Assessment & Mitigation

### Technical Risks
- **Onionoo API Rate Limits:** Implement intelligent caching and request batching
- **Data Volume Scaling:** Use efficient data structures and lazy loading
- **Real-time Performance:** Implement WebSocket connections with fallback polling

### Operational Risks
- **Data Privacy:** Ensure bridge data anonymization meets privacy standards
- **Security:** Implement secure API access and data handling practices
- **Maintenance:** Create comprehensive monitoring and automated health checks

## Conclusion

This comprehensive visualization plan will transform Onionoo uptime data into actionable insights for the Tor network community. The prioritized chart types address the most critical needs for network monitoring, reliability assessment, and capacity planning while providing both operational dashboards and strategic analysis tools.

The implementation will deliver immediate value through basic monitoring capabilities while building toward advanced predictive analytics that will help ensure the long-term health and growth of the Tor network.

---

**Next Steps:**
1. Review and approve this proposal
2. Set up development environment and branch
3. Begin Phase 1 implementation
4. Schedule regular progress reviews and stakeholder feedback sessions