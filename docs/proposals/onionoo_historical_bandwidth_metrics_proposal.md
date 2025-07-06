# Bandwidth Analytics Enhancement Proposal
## Top 10 New Metrics for Large-Scale Tor Operators and Tor Foundation

### Executive Summary

This proposal outlines 10 new bandwidth-focused metrics for Allium that leverage the rich historical data available from the Onionoo API (`onionoo.torproject.org/bandwidth` and `onionoo.torproject.org/uptime`). These metrics are specifically designed to benefit large-scale Tor operators managing multiple relays and the Tor Foundation's network oversight responsibilities.

The proposed metrics utilize existing Onionoo API fields that are currently underutilized in the Allium codebase, focusing on temporal analysis, capacity planning, and network health insights.

### Current State Analysis

**Current Onionoo API Usage:**
- Primary: `observed_bandwidth` (point-in-time bandwidth)
- Secondary: `consensus_weight`, `guard_probability`, `exit_probability`
- Endpoints: `/details` and `/uptime` APIs

**Current Limitations:**
- No historical bandwidth trend analysis
- Limited capacity planning insights
- No bandwidth efficiency or utilization metrics
- Missing network-wide bandwidth correlation analysis

---

## Top 10 Proposed Historical Bandwidth Metrics

### 1. Bandwidth Stability Index (BSI)

**Purpose:** Measures consistency of bandwidth performance over time for capacity planning.

**Target Users:** Large operators managing infrastructure investments, Tor Foundation for network stability assessment.

**Benefits:**
- Identifies reliable vs. volatile relay performance
- Helps operators optimize infrastructure allocation
- Enables the Tor Foundation to identify stable network contributors

**Onionoo Data Sources:**
- `bandwidth_history` → `write_history` (download bandwidth over time)
- `bandwidth_history` → `read_history` (upload bandwidth over time)
- Time range: 1 week, 1 month, 3 months

**Calculation:** Coefficient of variation (standard deviation / mean) of bandwidth over time periods.

**Mockup:**
```
┌─────────────────────────────────────────────────────────────┐
│ Bandwidth Stability Index - Last 30 Days                   │
├─────────────────────────────────────────────────────────────┤
│ Operator: example.org                                       │
│ ┌─────────────────┬──────────┬──────────┬─────────────────┐ │
│ │ Relay           │ BSI Score│ Category │ Bandwidth Range │ │
│ ├─────────────────┼──────────┼──────────┼─────────────────┤ │
│ │ ExampleRelay1   │ 0.12     │ Stable   │ 95-105 Mbit/s   │ │
│ │ ExampleRelay2   │ 0.35     │ Moderate │ 45-85 Mbit/s    │ │
│ │ ExampleRelay3   │ 0.67     │ Volatile │ 20-120 Mbit/s   │ │
│ └─────────────────┴──────────┴──────────┴─────────────────┘ │
│ Network Average BSI: 0.28 (Stable)                         │
└─────────────────────────────────────────────────────────────┘
```

### 2. Peak Hour Utilization Ratio (PHUR)

**Purpose:** Analyzes bandwidth efficiency during global peak traffic hours vs. off-peak.

**Target Users:** Large operators for traffic engineering, Tor Foundation for load balancing insights.

**Benefits:**
- Optimizes relay placement across time zones
- Identifies underutilized capacity during peak hours
- Helps balance global network load

**Onionoo Data Sources:**
- `bandwidth_history` → `write_history` with hourly granularity
- `bandwidth_history` → `read_history` with hourly granularity
- Combined with UTC timezone analysis

**Calculation:** Ratio of average bandwidth during peak hours (12:00-20:00 UTC) vs. off-peak hours.

**Mockup:**
```
┌─────────────────────────────────────────────────────────────┐
│ Peak Hour Utilization Analysis - Geographic Distribution    │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────┬────────────┬─────────────┬─────────────────┐ │
│ │ Region      │ Peak Ratio │ Efficiency  │ Recommendation  │ │
│ ├─────────────┼────────────┼─────────────┼─────────────────┤ │
│ │ North America│ 1.35      │ High        │ Maintain        │ │
│ │ Europe      │ 0.87       │ Moderate    │ Scale Up        │ │
│ │ Asia-Pacific│ 0.65       │ Low         │ Optimize        │ │
│ └─────────────┴────────────┴─────────────┴─────────────────┘ │
│ Your relays: 47 across 3 regions                           │
│ Suggested actions: +12 EU relays, -3 APAC relays          │
└─────────────────────────────────────────────────────────────┘
```

### 3. Bandwidth Growth Trajectory (BGT)

**Purpose:** Tracks bandwidth scaling patterns for capacity planning and investment decisions.

**Target Users:** Large operators planning expansion, Tor Foundation for network growth monitoring.

**Benefits:**
- Predicts future bandwidth needs
- Identifies successful scaling patterns
- Enables proactive infrastructure planning

**Onionoo Data Sources:**
- `bandwidth_history` over 3, 6, and 12-month periods
- `first_seen` for relay age correlation
- `observed_bandwidth` for current capacity

**Calculation:** Linear regression slope of bandwidth over time, adjusted for relay count changes.

**Mockup:**
```
┌─────────────────────────────────────────────────────────────┐
│ Bandwidth Growth Trajectory - 12 Month Analysis            │
├─────────────────────────────────────────────────────────────┤
│ Current Total: 47.3 Gbit/s across 156 relays               │
│                                                             │
│ 50G ┤                                                  ●●   │
│ 45G ┤                                            ●●●        │
│ 40G ┤                                      ●●●              │
│ 35G ┤                                ●●●                    │
│ 30G ┤                          ●●●                          │
│ 25G ┤                    ●●●                                │
│ 20G ┤              ●●●                                      │
│     └┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬───┤
│      Jan  Mar  May  Jul  Sep  Nov  Jan  Mar  May  Jul Sep  │
│                                                             │
│ Growth Rate: +2.1 Gbit/s per month (+4.4% monthly)         │
│ Projected 6-month capacity: 59.6 Gbit/s                    │
│ Investment efficiency: 67.8 Mbit/s per new relay           │
└─────────────────────────────────────────────────────────────┘
```

### 4. Consensus Weight to Bandwidth Efficiency (CWBE)

**Purpose:** Measures how effectively relays convert bandwidth into consensus weight (Tor network influence).

**Target Users:** Large operators optimizing relay configuration, Tor Foundation for network efficiency analysis.

**Benefits:**
- Identifies misconfigured or underperforming relays
- Optimizes bandwidth allocation across relay types
- Detects potential network gaming or abuse

**Onionoo Data Sources:**
- `consensus_weight` from details API
- `observed_bandwidth` from details API  
- `guard_probability`, `middle_probability`, `exit_probability`

**Calculation:** Ratio of consensus weight to observed bandwidth, normalized by network averages.

**Mockup:**
```
┌─────────────────────────────────────────────────────────────┐
│ Consensus Weight to Bandwidth Efficiency                   │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────┬──────────┬──────────┬─────────────────┐ │
│ │ Efficiency Range│ Count    │ Total BW │ Action Required │ │
│ ├─────────────────┼──────────┼──────────┼─────────────────┤ │
│ │ High (>1.2x)    │ 23 relays│ 18.4 GB/s│ Maintain        │ │
│ │ Normal (0.8-1.2)│ 89 relays│ 24.1 GB/s│ Monitor         │ │
│ │ Low (<0.8x)     │ 12 relays│ 4.8 GB/s │ Investigate     │ │
│ └─────────────────┴──────────┴──────────┴─────────────────┘ │
│                                                             │
│ Top Efficiency Factors:                                     │
│ • Exit policy diversity: +15% efficiency                   │
│ • IPv6 support: +8% efficiency                            │
│ • Port diversity: +12% efficiency                         │
│                                                             │
│ Low Efficiency Alerts:                                      │
│ • 3 relays: Potential bandwidth capping                    │
│ • 2 relays: Suboptimal exit policy                        │
└─────────────────────────────────────────────────────────────┘
```

### 5. Network Load Distribution Index (NLDI)

**Purpose:** Analyzes how operator bandwidth is distributed across guard, middle, and exit functions.

**Target Users:** Large operators for role optimization, Tor Foundation for network balance assessment.

**Benefits:**
- Optimizes relay role distribution
- Identifies bottlenecks in network topology
- Improves overall network efficiency

**Onionoo Data Sources:**
- `flags` array (Guard, Exit, Middle identification)
- `guard_probability`, `middle_probability`, `exit_probability`
- `observed_bandwidth` for each relay type

**Calculation:** Shannon entropy of bandwidth distribution across relay functions.

**Mockup:**
```
┌─────────────────────────────────────────────────────────────┐
│ Network Load Distribution - Operator vs Network Comparison │
├─────────────────────────────────────────────────────────────┤
│ Your Distribution:          Network Optimal:               │
│ ┌─────────┬─────────────┐  ┌─────────┬─────────────────┐   │
│ │ Guard   │ ████████ 45%│  │ Guard   │ ██████████ 55% │   │
│ │ Middle  │ ██████ 35%  │  │ Middle  │ ████████ 40%   │   │
│ │ Exit    │ ████ 20%    │  │ Exit    │ █ 5%           │   │
│ └─────────┴─────────────┘  └─────────┴─────────────────┘   │
│                                                             │
│ Distribution Score: 0.73 (Good)                             │
│ Optimization Suggestions:                                   │
│ • Convert 3 middle relays to guard (+15% network value)    │
│ • Maintain current exit capacity (meets network needs)     │
│ • Consider geographic redistribution for guards            │
│                                                             │
│ Impact Analysis:                                            │
│ • Network resilience: +8% with suggested changes           │
│ • User experience: +5% faster circuit building             │
└─────────────────────────────────────────────────────────────┘
```

### 6. Bandwidth Correlation Score (BCS)

**Purpose:** Identifies synchronized bandwidth patterns that might indicate infrastructure issues or coordinated attacks.

**Target Users:** Large operators for infrastructure monitoring, Tor Foundation for security analysis.

**Benefits:**
- Early detection of infrastructure failures
- Identifies potential coordinated attacks
- Improves network security monitoring

**Onionoo Data Sources:**
- `bandwidth_history` time series data
- Relay geographical and AS information
- `uptime_history` for correlation with availability

**Calculation:** Cross-correlation coefficient between relay bandwidth patterns within operator networks.

**Mockup:**
```
┌─────────────────────────────────────────────────────────────┐
│ Bandwidth Correlation Analysis - Anomaly Detection         │
├─────────────────────────────────────────────────────────────┤
│ Last 7 Days Analysis:                                       │
│                                                             │
│ High Correlation Clusters (>0.8):                          │
│ ┌─────────────────┬──────────┬─────────────────────────────┐ │
│ │ Cluster         │ Relays   │ Potential Cause             │ │
│ ├─────────────────┼──────────┼─────────────────────────────┤ │
│ │ DC-East-Rack-A  │ 12       │ Shared network infrastructure│ │
│ │ EU-Provider-X   │ 8        │ Provider bandwidth throttling│ │
│ │ APAC-Unknown    │ 4        │ ⚠️  Potential coordination    │ │
│ └─────────────────┴──────────┴─────────────────────────────┘ │
│                                                             │
│ Anomaly Scores:                                             │
│ • 2024-01-15 14:00: Score 0.92 (⚠️  Investigation needed)   │
│ • 2024-01-12 09:30: Score 0.78 (Normal correlation)        │
│                                                             │
│ Security Recommendations:                                   │
│ • Monitor APAC-Unknown cluster for 48 hours                │
│ • Verify EU-Provider-X throttling is legitimate            │
└─────────────────────────────────────────────────────────────┘
```

### 7. Capacity Reserve Ratio (CRR)

**Purpose:** Measures available bandwidth headroom during peak usage periods.

**Target Users:** Large operators for emergency planning, Tor Foundation for network resilience assessment.

**Benefits:**
- Ensures network resilience during traffic spikes
- Optimizes resource allocation
- Improves emergency response capabilities

**Onionoo Data Sources:**
- `bandwidth_history` peak vs. average analysis
- `observed_bandwidth` maximum capacity
- Network-wide traffic pattern analysis

**Calculation:** Ratio of unutilized bandwidth during peak hours to total available bandwidth.

**Mockup:**
```
┌─────────────────────────────────────────────────────────────┐
│ Capacity Reserve Analysis - Network Resilience Metrics     │
├─────────────────────────────────────────────────────────────┤
│ Current Reserve Status: 23.4% (Healthy)                    │
│                                                             │
│ Reserve by Region:                                          │
│ ┌─────────────┬─────────────┬─────────────┬───────────────┐ │
│ │ Region      │ Total Cap   │ Peak Usage  │ Reserve %     │ │
│ ├─────────────┼─────────────┼─────────────┼───────────────┤ │
│ │ North America│ 18.5 Gbit/s │ 14.2 Gbit/s │ 23.2% ✅     │ │
│ │ Europe      │ 22.1 Gbit/s │ 18.9 Gbit/s │ 14.5% ⚠️      │ │
│ │ Asia-Pacific│ 6.7 Gbit/s  │ 4.8 Gbit/s  │ 28.4% ✅     │ │
│ └─────────────┴─────────────┴─────────────┴───────────────┘ │
│                                                             │
│ Risk Assessment:                                            │
│ • Europe: Consider +3 Gbit/s expansion                     │
│ • Emergency capacity: 11.1 Gbit/s available                │
│ • DDoS resilience: Can absorb 2.3x normal attack volume    │
│                                                             │
│ Recommendations:                                            │
│ • Target reserve ratio: 20-30% for optimal resilience      │
│ • Priority deployment: 2 x 1.5Gbit/s European relays       │
└─────────────────────────────────────────────────────────────┘
```

### 8. Quality of Service Consistency (QoSC)

**Purpose:** Tracks bandwidth consistency across different time periods to assess service quality.

**Target Users:** Large operators for SLA monitoring, Tor Foundation for network quality assessment.

**Benefits:**
- Monitors service quality commitments
- Identifies performance degradation trends
- Improves user experience predictability

**Onionoo Data Sources:**
- `bandwidth_history` with hourly/daily granularity
- `uptime_history` correlation
- Multi-timeframe analysis (1d, 7d, 30d)

**Calculation:** Weighted variance of bandwidth delivery across time periods, adjusted for planned maintenance.

**Mockup:**
```
┌─────────────────────────────────────────────────────────────┐
│ Quality of Service Consistency - Performance Dashboard     │
├─────────────────────────────────────────────────────────────┤
│ Overall QoS Score: 8.7/10 (Excellent)                      │
│                                                             │
│ Consistency Metrics:                                        │
│ ┌─────────────┬─────────────┬─────────────┬───────────────┐ │
│ │ Time Period │ Availability│ BW Variance │ QoS Rating    │ │
│ ├─────────────┼─────────────┼─────────────┼───────────────┤ │
│ │ Last 24h    │ 99.8%       │ 4.2%        │ 9.1/10 ✅     │ │
│ │ Last 7d     │ 99.6%       │ 6.8%        │ 8.8/10 ✅     │ │
│ │ Last 30d    │ 98.9%       │ 8.3%        │ 8.4/10 ✅     │ │
│ └─────────────┴─────────────┴─────────────┴───────────────┘ │
│                                                             │
│ Performance Trends:                                         │
│ • Bandwidth: ↗️ +12% improvement over 30 days               │
│ • Uptime: ↗️ +0.3% improvement over 30 days                 │
│ • Latency: → Stable within target range                    │
│                                                             │
│ Service Level Achievement:                                  │
│ • Target uptime (99.5%): ✅ Exceeded                        │
│ • Target bandwidth variance (<10%): ✅ Met                  │
│ • User satisfaction estimate: 94% (Excellent)              │
└─────────────────────────────────────────────────────────────┘
```

### 9. Temporal Bandwidth Efficiency (TBE)

**Purpose:** Analyzes bandwidth utilization patterns across different time periods to optimize resource allocation.

**Target Users:** Large operators for resource optimization, Tor Foundation for global load balancing.

**Benefits:**
- Optimizes resource allocation across time zones
- Reduces operational costs through efficient scheduling
- Improves global network balance

**Onionoo Data Sources:**
- `bandwidth_history` with timestamp analysis
- Geographic distribution data
- Peak/off-peak period definitions

**Calculation:** Ratio of actual bandwidth utilization to optimal theoretical utilization across time periods.

**Mockup:**
```
┌─────────────────────────────────────────────────────────────┐
│ Temporal Bandwidth Efficiency - 24-Hour Analysis           │
├─────────────────────────────────────────────────────────────┤
│ Global Efficiency Score: 76.3% (Good)                      │
│                                                             │
│ Hourly Utilization Pattern (UTC):                          │
│ 100% ┤                                                     │
│  80% ┤      ██████                ██████                   │
│  60% ┤    ████████████          ████████████               │
│  40% ┤  ████████████████      ████████████████             │
│  20% ┤████████████████████  ████████████████████           │
│   0% └┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬───┤
│      00 03 06 09 12 15 18 21 00 03 06 09 12 15 18 21     │
│                                                             │
│ Optimization Opportunities:                                 │
│ ┌─────────────┬─────────────┬─────────────┬───────────────┐ │
│ │ Time Period │ Current Eff.│ Target Eff. │ Action Needed │ │
│ ├─────────────┼─────────────┼─────────────┼───────────────┤ │
│ │ 00:00-06:00 │ 45%         │ 65%         │ +4 APAC relays│ │
│ │ 06:00-12:00 │ 89%         │ 85%         │ Optimal       │ │
│ │ 12:00-18:00 │ 92%         │ 90%         │ Optimal       │ │
│ │ 18:00-00:00 │ 67%         │ 80%         │ +2 EU relays  │ │
│ └─────────────┴─────────────┴─────────────┴───────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 10. Network Impact Multiplier (NIM)

**Purpose:** Calculates the multiplied impact of operator bandwidth on overall Tor network performance.

**Target Users:** Large operators to understand network contribution, Tor Foundation for strategic planning.

**Benefits:**
- Quantifies operator value to the Tor network
- Guides strategic capacity planning
- Improves network-wide optimization decisions

**Onionoo Data Sources:**
- `consensus_weight_fraction` for network influence
- `guard_probability`, `exit_probability` for role impact
- `bandwidth_history` for sustained contribution
- Network-wide statistics for comparison

**Calculation:** Weighted combination of bandwidth contribution, network position importance, and stability factors.

**Mockup:**
```
┌─────────────────────────────────────────────────────────────┐
│ Network Impact Multiplier - Strategic Value Analysis       │
├─────────────────────────────────────────────────────────────┤
│ Your Network Impact Score: 4.7x (High Impact)              │
│                                                             │
│ Impact Components:                                          │
│ ┌─────────────────────┬─────────────┬─────────────────────┐ │
│ │ Factor              │ Your Score  │ Network Average     │ │
│ ├─────────────────────┼─────────────┼─────────────────────┤ │
│ │ Raw Bandwidth       │ 3.2%        │ 0.1% (32x higher)  │ │
│ │ Geographic Coverage │ 8.7/10      │ 3.2/10              │ │
│ │ Role Diversity      │ 9.1/10      │ 5.4/10              │ │
│ │ Reliability         │ 99.2%       │ 97.1%               │ │
│ │ Exit Policy Value   │ 8.9/10      │ 6.2/10              │ │
│ └─────────────────────┴─────────────┴─────────────────────┘ │
│                                                             │
│ Strategic Value:                                            │
│ • Guards: Support 12.3% of new Tor circuits               │
│ • Exits: Enable 8.7% of hidden service connections        │
│ • Middle: Route 5.1% of all Tor traffic                   │
│                                                             │
│ Network Contribution Analysis:                              │
│ • User experience improvement: +15% faster circuit build   │
│ • Network resilience: +23% attack resistance               │
│ • Geographic diversity: +31% global coverage               │
│                                                             │
│ Optimization Recommendations:                               │
│ • High priority: Expand South American presence            │
│ • Medium priority: Add 2 more exit relays in Europe        │
│ • Maintain: Current Asian Pacific relay distribution       │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Data Pipeline Enhancement (Weeks 1-2)
1. Extend Onionoo API integration to fully utilize `bandwidth_history` fields
2. Implement time-series data storage and processing
3. Add historical data aggregation functions

### Phase 2: Metric Calculations (Weeks 3-4)
1. Implement the 10 core metrics calculation engines
2. Add statistical analysis functions (correlation, variance, trend analysis)
3. Create data validation and quality assurance processes

### Phase 3: Dashboard Integration (Weeks 5-6)
1. Design and implement dashboard templates for each metric
2. Add operator-specific views and filtering capabilities
3. Integrate with existing AROI and network health dashboards

### Phase 4: Testing and Optimization (Weeks 7-8)
1. Performance testing with large operator datasets
2. Accuracy validation against known network events
3. User interface optimization and accessibility improvements

---

## Technical Requirements

### Onionoo API Fields Utilized

**Primary Data Sources:**
- `bandwidth_history.read_history` - Upload bandwidth over time
- `bandwidth_history.write_history` - Download bandwidth over time  
- `observed_bandwidth` - Current bandwidth capacity
- `consensus_weight` - Network influence measurement
- `uptime_history` - Availability correlation data

**Supporting Data:**
- `flags` - Relay role identification (Guard, Exit, Middle)
- `guard_probability`, `exit_probability`, `middle_probability` - Role probabilities
- `first_seen` - Relay age for growth analysis
- `as_name`, `country` - Geographic distribution analysis
- `consensus_weight_fraction` - Network percentage calculations

### Data Storage Requirements
- 6-month rolling historical data storage (~2.4GB estimated)
- Time-series database optimization for trend analysis
- Efficient indexing for operator-specific queries

### Performance Considerations
- Incremental calculation updates (daily/hourly refresh cycles)
- Cached aggregations for dashboard performance
- Parallel processing for large operator datasets

---

## Expected Impact

### For Large-Scale Operators:
- **20-30% improvement** in capacity planning accuracy
- **15-25% reduction** in infrastructure waste through optimization
- **Enhanced security** through anomaly detection capabilities
- **Improved ROI** through strategic relay placement

### For Tor Foundation:
- **Comprehensive network health monitoring** across all bandwidth metrics
- **Strategic planning data** for network growth and optimization
- **Early warning systems** for network attacks or infrastructure issues
- **Evidence-based policy decisions** for network development

### For the Tor Network:
- **Improved overall performance** through optimized bandwidth allocation
- **Enhanced resilience** through better capacity reserve management
- **Better global coverage** through strategic geographic optimization
- **Higher service quality** through consistency monitoring

This proposal leverages the rich, underutilized data available from the Onionoo API to provide unprecedented insights into Tor network bandwidth patterns, enabling both large operators and the Tor Foundation to make data-driven decisions that improve network performance, security, and resilience.
