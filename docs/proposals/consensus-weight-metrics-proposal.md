# Consensus Weight Analytics: Top 10 New Metrics Proposal

**Author:** 1aeo  
**Date:** 2025-01-05  
**Branch:** proponioncs  
**Target Audience:** Large Scale Tor Operators & Tor Foundation  

## Executive Summary

This proposal introduces 10 new consensus weight-based metrics to enhance network monitoring and operator performance analysis using Onionoo API data. These metrics address critical gaps in understanding network centralization, consensus weight efficiency, temporal patterns, and operator impact on network health.

## Background

The Tor network's consensus weight system determines relay selection probability and overall network capacity distribution. Current allium metrics focus primarily on bandwidth and basic consensus weight fractions, missing crucial insights into consensus weight efficiency, temporal patterns, and centralization risks.

### Available Onionoo API Variables

**Primary Consensus Weight Data (`details` API):**
- `consensus_weight` - Raw consensus weight value assigned by directory authorities
- `consensus_weight_fraction` - Relay's fraction of total network consensus weight
- `guard_consensus_weight_fraction` - Fraction of guard consensus weight
- `middle_consensus_weight_fraction` - Fraction of middle consensus weight  
- `exit_consensus_weight_fraction` - Fraction of exit consensus weight
- `observed_bandwidth` - Measured relay bandwidth capacity
- `flags` - Relay flags (Guard, Exit, Fast, Stable, etc.)

**Supporting Data (`details` + `uptime` APIs):**
- `uptime.6_months.values` - Historical uptime percentages (daily values)
- `uptime.1_year.values` - Extended historical uptime data
- `first_seen` - Relay first appearance timestamp
- `last_seen` - Last observed timestamp
- `country` - Geographic location
- `as` - Autonomous System identifier

## Top 10 New Consensus Weight Metrics

### 1. Consensus Weight Efficiency Index (CWEI)

**Purpose:** Measure how efficiently operators convert bandwidth into consensus weight  
**Benefit:** Identifies under/over-weighted operators and potential measurement issues

**Formula:** `(consensus_weight / observed_bandwidth) * network_median_ratio`

**Onionoo Variables:** `consensus_weight`, `observed_bandwidth`

**Mockup:**
```
┌─ Consensus Weight Efficiency Index ─────────────────────────────┐
│ Operator: example.org                                           │
│ CWEI Score: 1.24 (24% above network median)                    │
│ ──────────────────────────────────────────────────────────────  │
│ Raw Efficiency: 0.0156 CW/Mbps                                 │
│ Network Median: 0.0126 CW/Mbps                                 │
│ Interpretation: ✓ Well-measured, optimal weight assignment     │
│                                                                 │
│ Efficiency Distribution:                                        │
│ [▓▓▓▓▓▓▓▓░░] Operator (85th percentile)                        │
│ [▓▓▓▓▓░░░░░] Network Median (50th percentile)                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Consensus Weight Stability Score (CWSS)

**Purpose:** Track consensus weight consistency over time to identify reliable operators  
**Benefit:** Helps Tor Foundation identify stable vs. volatile network contributors

**Formula:** `1 - (std_deviation(daily_cw_fraction) / mean(daily_cw_fraction))`

**Onionoo Variables:** `consensus_weight_fraction` (historical), `uptime.6_months.values`

**Mockup:**
```
┌─ Consensus Weight Stability Score (6 month) ────────────────────┐
│ Operator: large-operator.net                                    │
│ CWSS: 0.94 (94% stability - Excellent)                         │
│ ──────────────────────────────────────────────────────────────  │
│ Mean CW Fraction: 2.34%                                        │
│ Std Deviation: 0.14%                                           │
│ CV (Coefficient of Variation): 6.0%                            │
│                                                                 │
│ 6-Month Trend:                                                 │
│ 2.5% ┤   ╭─╮     ╭─╮                                           │
│ 2.3% ┤ ╭─╯   ╰─╮ ╯   ╰─╮                                       │
│ 2.1% ┤ ╯         ╰╯       ╰─╮                                   │
│ 1.9% ┤                       ╰───                              │
│      └─Jan──Feb──Mar──Apr──May──Jun                           │
│                                                                 │
│ Rating: ★★★★★ (Network-stabilizing operator)                   │
└─────────────────────────────────────────────────────────────────┘
```

### 3. Network Share Momentum Index (NSMI)

**Purpose:** Track operator growth/decline velocity in network share  
**Benefit:** Early warning system for concerning centralization trends

**Formula:** `(current_cw_fraction - 90day_avg_cw_fraction) / 90day_avg_cw_fraction`

**Onionoo Variables:** `consensus_weight_fraction` (current and historical)

**Mockup:**
```
┌─ Network Share Momentum Index ──────────────────────────────────┐
│ Operator: growing-operator.org                                  │
│ NSMI: +15.3% (Growing market share)                            │
│ ──────────────────────────────────────────────────────────────  │
│ Current Share: 3.45%                                           │
│ 90-Day Average: 2.99%                                          │
│ Net Change: +0.46 percentage points                            │
│                                                                 │
│ Growth Analysis:                                                │
│ • Added 23 new relays (avg 1.8 Gbps each)                     │
│ • Consensus weight grew 18% faster than bandwidth             │
│ • Geographic expansion: 5 new countries                        │
│                                                                 │
│ Risk Assessment:                                                │
│ ⚠️  Monitor: Approaching 5% network threshold                  │
│ ✓  Diversity: Multi-country, multi-AS deployment              │
│                                                                 │
│ Momentum Category: 📈 Positive Growth (Monitor)                │
└─────────────────────────────────────────────────────────────────┘
```

### 4. Consensus Weight Concentration Risk (CWCR)

**Purpose:** Calculate Herfindahl-Hirschman Index for consensus weight distribution  
**Benefit:** Quantifies network centralization risk for Tor Foundation oversight

**Formula:** `HHI = Σ(operator_cw_fraction²)` where HHI > 2500 indicates concentration

**Onionoo Variables:** `consensus_weight_fraction` (all operators)

**Mockup:**
```
┌─ Network Consensus Weight Concentration Analysis ──────────────┐
│ Current HHI: 1,847 (Moderately Concentrated)                   │
│ ──────────────────────────────────────────────────────────────  │
│ Concentration Status: ✓ Healthy Competition                    │
│ Risk Level: 🟨 Medium (Monitor top operators)                  │
│                                                                 │
│ Top 10 Operators Control: 34.2% of network CW                 │
│ Top 25 Operators Control: 51.8% of network CW                 │
│                                                                 │
│ Concentration Trends (6 months):                               │
│ 2000 ┤                         ╭─╮                              │
│ 1800 ┤                   ╭─╮ ╭─╯   ╰─╮ ← Current                │ 
│ 1600 ┤ ╭─╮           ╭─╯   ╰─╯         ╰─╮                     │
│ 1400 ┤ ╯   ╰─╮   ╭─╯                     ╰─                    │
│ 1200 ┤       ╰───╯                                             │
│      └─Jan──Feb──Mar──Apr──May──Jun                           │
│                                                                 │
│ ⚠️  Alert Thresholds:                                          │
│ • HHI > 2500: High concentration risk                          │
│ • Single operator > 10%: Centralization concern               │
│ • Top 5 operators > 50%: Market dominance                     │
└─────────────────────────────────────────────────────────────────┘
```

### 5. Role-Specific Weight Distribution (RSWD)

**Purpose:** Analyze consensus weight distribution across Guard/Middle/Exit roles  
**Benefit:** Identify role-specific bottlenecks and capacity imbalances

**Formula:** Multiple metrics tracking guard/middle/exit consensus weight ratios

**Onionoo Variables:** `guard_consensus_weight_fraction`, `middle_consensus_weight_fraction`, `exit_consensus_weight_fraction`, `flags`

**Mockup:**
```
┌─ Role-Specific Weight Distribution ─────────────────────────────┐
│ Operator: multi-role-operator.com                              │
│ ──────────────────────────────────────────────────────────────  │
│ Guard Role Distribution:                                        │
│ • Operator Share: 4.2% of all guard consensus weight          │
│ • Network Position: #3 guard operator                         │
│ • Role Efficiency: 1.18x (above average guard weighting)      │
│                                                                 │
│ Exit Role Distribution:                                         │
│ • Operator Share: 6.8% of all exit consensus weight           │
│ • Network Position: #1 exit operator ⚠️                       │
│ • Role Efficiency: 1.31x (strong exit weighting)              │
│                                                                 │
│ Middle Role Distribution:                                       │
│ • Operator Share: 2.1% of all middle consensus weight         │
│ • Network Position: #12 middle operator                       │
│ • Role Efficiency: 0.89x (below average middle weighting)     │
│                                                                 │
│ Role Balance Analysis:                                          │
│ ┌─────────┬─────────┬─────────┬─────────┐                     │
│ │ Role    │ Relays  │ CW %    │ Network │                     │
│ ├─────────┼─────────┼─────────┼─────────┤                     │
│ │ Guard   │ 45      │ 4.2%    │ #3      │                     │
│ │ Exit    │ 12      │ 6.8%    │ #1 ⚠️   │                     │
│ │ Middle  │ 28      │ 2.1%    │ #12     │                     │
│ └─────────┴─────────┴─────────┴─────────┘                     │
│                                                                 │
│ 🎯 Strategic Recommendation:                                   │
│ • Consider exit role dominance (>5% threshold)                │
│ • Opportunity to improve middle role weighting                │
└─────────────────────────────────────────────────────────────────┘
```

### 6. Consensus Weight Persistence Score (CWPS)

**Purpose:** Measure how long operators maintain consensus weight levels  
**Benefit:** Assess operator reliability and network infrastructure stability

**Formula:** `average_days_at_current_cw_level * uptime_factor * stability_factor`

**Onionoo Variables:** `consensus_weight_fraction` (historical), `first_seen`, `uptime.6_months.values`

**Mockup:**
```
┌─ Consensus Weight Persistence Analysis ────────────────────────┐
│ Operator: veteran-operator.net                                 │
│ CWPS: 847 (Very High Persistence)                             │
│ ──────────────────────────────────────────────────────────────  │
│ Current CW Level: 2.8% (±0.2% range)                          │
│ Time at Level: 418 days                                        │
│ Operator Age: 1,342 days (3.7 years)                          │
│ Uptime Factor: 0.96 (96% average uptime)                      │
│                                                                 │
│ Persistence Timeline:                                           │
│ 3.5% ┤                                                         │
│ 3.0% ┤     ╭─────────────────────────────╮                     │
│ 2.5% ┤ ╭───╯                             ╰─────── Current      │
│ 2.0% ┤ ╯                                                       │
│ 1.5% ┤                                                         │
│ 1.0% ┤                                                         │
│      └─2021────2022────2023────2024────2025                   │
│                                                                 │
│ Persistence Factors:                                            │
│ ✓ Long-term commitment (3+ years)                             │
│ ✓ Stable infrastructure (consistent CW)                       │
│ ✓ High reliability (96% uptime)                               │
│ ✓ Gradual growth pattern (no spikes)                          │
│                                                                 │
│ Network Trust Score: ★★★★★ (Maximum reliability)               │
└─────────────────────────────────────────────────────────────────┘
```

### 7. Peak Traffic Contribution Index (PTCI)

**Purpose:** Identify operators providing consensus weight during network stress  
**Benefit:** Recognize operators who maintain capacity when network needs it most

**Formula:** `operator_cw_fraction_during_peaks / operator_cw_fraction_baseline`

**Onionoo Variables:** `consensus_weight_fraction` (time-series), `uptime` data during network events

**Mockup:**
```
┌─ Peak Traffic Contribution Analysis ───────────────────────────┐
│ Operator: resilient-operator.org                               │
│ PTCI Score: 1.34 (34% above baseline during peaks)            │
│ ──────────────────────────────────────────────────────────────  │
│ Baseline CW Share: 1.8%                                        │
│ Peak Period CW Share: 2.4%                                     │
│ Peak Uplift: +0.6 percentage points                           │
│                                                                 │
│ Recent Peak Events Analysis:                                    │
│ ┌──────────────────┬──────────┬──────────┬──────────┐          │
│ │ Event Date       │ Duration │ Your CW  │ Network  │          │
│ ├──────────────────┼──────────┼──────────┼──────────┤          │
│ │ Dec 15 DDoS      │ 6 hours  │ 2.6%     │ -15% cap │          │
│ │ Nov 28 Outage    │ 3 hours  │ 2.8%     │ -22% cap │          │
│ │ Oct 12 Attack    │ 8 hours  │ 2.2%     │ -8% cap  │          │
│ └──────────────────┴──────────┴──────────┴──────────┘          │
│                                                                 │
│ Peak Performance Metrics:                                       │
│ • Consistency: 9/10 (maintained >95% uptime during peaks)     │
│ • Scalability: 8/10 (absorbed 34% extra traffic load)         │
│ • Response: 10/10 (no relay failures during stress)           │
│                                                                 │
│ 🏆 Network Resilience Award:                                   │
│ ★★★★★ Critical Infrastructure Operator                        │
│                                                                 │
│ Impact: Helped maintain network stability during 3 major       │
│ events, absorbing 12.3% of displaced traffic collectively.     │
└─────────────────────────────────────────────────────────────────┘
```

### 8. Geographic Consensus Weight Diversity (GCWD)

**Purpose:** Measure consensus weight distribution across geographic regions  
**Benefit:** Assess resistance to region-specific attacks and regulatory risks

**Formula:** `shannon_entropy(cw_by_country) * country_count_factor`

**Onionoo Variables:** `consensus_weight_fraction`, `country`, geographic distribution

**Mockup:**
```
┌─ Geographic Consensus Weight Diversity ────────────────────────┐
│ Operator: global-operator.net                                  │
│ GCWD Score: 2.84 (High Geographic Diversity)                  │
│ ──────────────────────────────────────────────────────────────  │
│ Countries: 12                                                  │
│ Continents: 4                                                  │
│ Shannon Entropy: 2.84 bits                                     │
│                                                                 │
│ Consensus Weight by Region:                                     │
│ ┌─────────────────┬─────────┬──────────┬──────────┐            │
│ │ Country         │ Relays  │ CW Share │ Uptime   │            │
│ ├─────────────────┼─────────┼──────────┼──────────┤            │
│ │ 🇩🇪 Germany      │ 8       │ 32.1%    │ 98.2%    │            │
│ │ 🇺🇸 United States│ 6       │ 24.7%    │ 97.8%    │            │
│ │ 🇫🇷 France       │ 4       │ 15.3%    │ 96.1%    │            │
│ │ 🇳🇱 Netherlands  │ 3       │ 12.8%    │ 99.1%    │            │
│ │ 🇸🇪 Sweden       │ 2       │ 8.9%     │ 94.7%    │            │
│ │ 🇨🇭 Switzerland  │ 2       │ 6.2%     │ 98.9%    │            │
│ │ Other (6)       │ 9       │ 15.0%    │ 96.4%    │            │
│ └─────────────────┴─────────┴──────────┴──────────┘            │
│                                                                 │
│ Risk Assessment:                                                │
│ ✓ No single country >50% (best practice)                      │
│ ✓ Multi-continental distribution                               │
│ ⚠️ EU concentration: 66.4% (consider non-EU expansion)        │
│                                                                 │
│ Jurisdictional Resilience: ★★★★☆ (Very Good)                  │
│ Recommendation: Add capacity in Asia-Pacific region           │
└─────────────────────────────────────────────────────────────────┘
```

### 9. Consensus Weight Load Balancing Index (CWLBI)

**Purpose:** Measure how evenly consensus weight is distributed across operator's relays  
**Benefit:** Identify efficiency opportunities and potential single points of failure

**Formula:** `1 - gini_coefficient(relay_cw_distribution_within_operator)`

**Onionoo Variables:** `consensus_weight` per relay within operator group

**Mockup:**
```
┌─ Consensus Weight Load Balancing Analysis ─────────────────────┐
│ Operator: balanced-operator.com                                │
│ CWLBI Score: 0.73 (Good load distribution)                    │
│ ──────────────────────────────────────────────────────────────  │
│ Total Relays: 24                                              │
│ Gini Coefficient: 0.27 (lower is more equal)                  │
│ Load Balance Grade: B+ (Good)                                  │
│                                                                 │
│ Relay Load Distribution:                                        │
│ ┌─────────────────┬─────────┬──────────┬──────────┐            │
│ │ Load Tier       │ Relays  │ Avg CW   │ CW Share │            │
│ ├─────────────────┼─────────┼──────────┼──────────┤            │
│ │ High (>1.5x avg)│ 3       │ 2,150    │ 32.1%    │            │
│ │ Medium (0.8-1.5x)│ 16      │ 850      │ 58.2%    │            │
│ │ Low (<0.8x avg) │ 5       │ 390      │ 9.7%     │            │
│ └─────────────────┴─────────┴──────────┴──────────┘            │
│                                                                 │
│ Load Distribution Visualization:                                │
│ 2500 ┤ ●                                                       │
│ 2000 ┤ ●     ●                                                 │
│ 1500 ┤ ●   ● ● ●                                               │
│ 1000 ┤ ● ● ● ● ● ● ● ● ● ●                                     │
│  500 ┤ ● ● ● ● ● ● ● ● ● ● ● ● ● ●                             │
│    0 ┤ ● ● ● ● ● ● ● ● ● ● ● ● ● ● ● ● ● ● ● ● ● ● ● ●         │
│      └─ Relays (sorted by consensus weight) ──                │
│                                                                 │
│ 💡 Optimization Opportunities:                                 │
│ • Consider upgrading 5 low-performing relays                  │
│ • 3 high-load relays may be capacity bottlenecks              │
│ • Target CWLBI >0.80 for optimal distribution                 │
│                                                                 │
│ Single Point of Failure Risk: 🟨 Medium                       │
└─────────────────────────────────────────────────────────────────┘
```

### 10. Consensus Weight ROI (Return on Investment) Score

**Purpose:** Evaluate consensus weight achieved per unit of infrastructure investment  
**Benefit:** Help operators optimize resource allocation and identify efficient configurations

**Formula:** `(consensus_weight_fraction / estimated_monthly_cost) * 10000`

**Onionoo Variables:** `consensus_weight_fraction`, `observed_bandwidth`, server count estimation

**Mockup:**
```
┌─ Consensus Weight Return on Investment Analysis ───────────────┐
│ Operator: efficient-operator.org                               │
│ CW-ROI Score: 47.3 (Above Average Efficiency)                 │
│ ──────────────────────────────────────────────────────────────  │
│ Network Share: 1.89%                                          │
│ Estimated Monthly Cost: $4,200                                │
│ Cost per CW Point: $22.22                                     │
│                                                                 │
│ Investment Breakdown:                                           │
│ ┌─────────────────┬─────────┬──────────┬──────────┐            │
│ │ Resource Type   │ Units   │ Est Cost │ CW Yield │            │
│ ├─────────────────┼─────────┼──────────┼──────────┤            │
│ │ High-end servers│ 8       │ $2,400   │ 1.12%    │            │
│ │ Mid-tier servers│ 12      │ $1,200   │ 0.58%    │            │
│ │ Budget servers  │ 6       │ $360     │ 0.19%    │            │
│ │ Bandwidth costs │ -       │ $240     │ -        │            │
│ └─────────────────┴─────────┴──────────┴──────────┘            │
│                                                                 │
│ Efficiency Metrics:                                             │
│ • CW per $ invested: 0.045% per $100/month                    │
│ • Network percentile: 67th (above average)                    │
│ • Geographic efficiency: 0.157% CW per country                │
│                                                                 │
│ ROI Optimization Recommendations:                               │
│ 💰 High Impact:                                                │
│ • Replace 6 budget servers with 2 mid-tier (+0.08% CW)       │
│ • Migrate to lower-cost bandwidth provider (-$60/month)       │
│                                                                 │
│ 📈 Medium Impact:                                              │
│ • Deploy in underserved regions (rare countries)              │
│ • Optimize relay configurations for better CW scoring         │
│                                                                 │
│ Projected Optimized ROI: 52.1 (+10% improvement)              │
│ Investment Grade: ★★★★☆ (Strong efficiency)                   │
└─────────────────────────────────────────────────────────────────┘
```

## Implementation Roadmap

### Phase 1: Foundation (1-2 months)
1. **Consensus Weight Efficiency Index (CWEI)** - Core efficiency metric
2. **Network Share Momentum Index (NSMI)** - Growth tracking
3. **Consensus Weight Concentration Risk (CWCR)** - Network health monitoring

### Phase 2: Operational Excellence (2-3 months)
4. **Consensus Weight Stability Score (CWSS)** - Reliability tracking  
5. **Role-Specific Weight Distribution (RSWD)** - Multi-role analysis
6. **Consensus Weight Load Balancing Index (CWLBI)** - Internal optimization

### Phase 3: Strategic Intelligence (3-4 months)  
7. **Consensus Weight Persistence Score (CWPS)** - Long-term commitment analysis
8. **Peak Traffic Contribution Index (PTCI)** - Crisis response evaluation
9. **Geographic Consensus Weight Diversity (GCWD)** - Geographic risk assessment
10. **Consensus Weight ROI Score** - Economic efficiency analysis

## Technical Requirements

### Data Collection
- Enhanced historical data retention (12+ months)
- Real-time consensus weight monitoring
- Integration with existing uptime and geographic analysis

### Dashboard Integration
- New "Consensus Weight Analytics" section in operator dashboards
- Network health dashboard widgets for Tor Foundation
- Alert system for concentration risks and anomalies

### Performance Considerations
- Batch processing for historical calculations
- Caching for frequently accessed metrics
- Incremental updates for real-time indicators

## Expected Benefits

### For Large Scale Operators
- **Optimize Resource Allocation:** CWEI and ROI metrics guide infrastructure investments
- **Monitor Network Position:** NSMI and RSWD track competitive standing
- **Improve Reliability:** CWSS and PTCI enhance network contribution quality
- **Geographic Strategy:** GCWD guides expansion decisions

### For Tor Foundation  
- **Network Health Monitoring:** CWCR provides early centralization warnings
- **Operator Assessment:** CWPS and PTCI identify most reliable contributors
- **Policy Guidance:** RSWD and GCWD inform network balance policies
- **Crisis Response:** PTCI tracks network resilience during attacks

## Risk Mitigation

- **Privacy Protection:** All metrics use aggregated data only
- **Gaming Resistance:** Multiple correlated metrics prevent manipulation
- **Threshold Alerts:** Automated warnings for concerning trends
- **Historical Context:** Long-term baselines prevent false alarms

## Conclusion

These 10 consensus weight metrics provide comprehensive insights into network health, operator efficiency, and centralization risks. Implementation will enhance Tor's network monitoring capabilities while providing valuable optimization guidance for large-scale operators.

The metrics leverage existing Onionoo API data efficiently and complement current allium analytics without disrupting established workflows. Focus on consensus weight analysis addresses a critical gap in current monitoring capabilities and supports the Tor network's long-term health and resilience.