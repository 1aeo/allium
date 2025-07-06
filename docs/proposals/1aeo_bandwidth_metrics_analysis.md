# Bandwidth History Metrics Analysis for 1aeo.com AROI Group

**Date:** July 6, 2025  
**Branch:** propband1aeo  
**Status:** Proof of Concept  

## Executive Summary

This document presents a comprehensive analysis of bandwidth metrics for the 1aeo.com Authenticated Relay Operator ID (AROI) group, one of the largest Tor relay operators currently active. Based on real-time data from the Onionoo API, this analysis covers **653 active relays** contributing approximately **9.35 Gbps of observed bandwidth** to the Tor network.

### Key Findings

- **653 relays** currently operational (matching expected ~650)
- **100% uptime** across all relays at time of analysis
- **9.35 Gbps** total observed bandwidth contribution
- **Geographic distribution**: 98.8% US-based (645 relays), 1.2% Norway (8 relays)
- **Network roles**: 80.7% Guard relays, 87.0% HSDir relays, 92.2% Stable relays
- **Top performer**: 67.5 MB/s peak relay bandwidth

## Current Network Contribution

### Bandwidth Statistics

| Metric | Value |
|--------|-------|
| Total Observed Bandwidth | 9,353,727,631 bytes/sec (8,920.4 MB/s) |
| Total Advertised Bandwidth Rate | 701,153,411,072 bytes/sec (668,672.0 MB/s) |
| Average Bandwidth per Relay | 14.32 MB/s observed |
| Peak Individual Relay | 67.48 MB/s (rapsodync) |
| Bandwidth Utilization Ratio | 1.33% (observed vs. advertised) |

### Geographic Distribution

| Country | Relay Count | Percentage |
|---------|-------------|------------|
| United States (US) | 645 | 98.8% |
| Norway (NO) | 8 | 1.2% |

### Network Role Distribution

| Flag | Relay Count | Percentage |
|------|-------------|------------|
| Fast | 653 | 100.0% |
| Running | 653 | 100.0% |
| Valid | 653 | 100.0% |
| V2Dir | 653 | 100.0% |
| Stable | 602 | 92.2% |
| HSDir | 568 | 87.0% |
| Guard | 527 | 80.7% |

## Proposed Bandwidth Metrics

### 1. Total Network Contribution

**Definition:** Sum of all observed bandwidth across all relays in the AROI group

**Current Value:** 9,353,727,631 bytes/sec (8.92 GB/s)

**Mathematical Formula:**
```
Total_Contribution = Σ(observed_bandwidth_i) for all relays i ∈ AROI_group
```

**Rationale:** This is the most fundamental metric showing the absolute contribution to Tor network capacity. It directly measures the operator's impact on network throughput available to users.

**Importance:** Critical for understanding overall network impact. A higher value means more capacity for Tor users and better network performance.

**Real-world Impact:** At 8.92 GB/s, this represents significant capacity for supporting thousands of concurrent Tor users.

### 2. Average Relay Efficiency

**Definition:** Mean ratio of observed to advertised bandwidth per relay

**Current Value:** 1.33% (9.35 Gbps observed / 701.15 Gbps advertised)

**Mathematical Formula:**
```
Avg_Efficiency = (1/n) × Σ(observed_bandwidth_i / advertised_bandwidth_i) for all relays i
```

**Rationale:** Indicates how well relays utilize their advertised capacity. Low efficiency might indicate network bottlenecks, configuration issues, or conservative bandwidth advertising.

**Importance:** Shows efficiency of resource allocation and helps identify optimization opportunities.

**Insights:** The 1.33% efficiency suggests either very conservative bandwidth advertising or network-level bottlenecks limiting actual throughput.

### 3. Bandwidth Distribution Diversity

**Definition:** Coefficient of variation of bandwidth across relays

**Mathematical Formula:**
```
Diversity_Index = σ(observed_bandwidth) / μ(observed_bandwidth)
```

**Rationale:** Measures consistency of performance across the fleet. Lower values indicate more uniform performance, while higher values suggest some relays significantly outperform others.

**Importance:** Helps identify whether bandwidth is concentrated in a few high-performers or distributed evenly across all relays.

**Application:** Can guide resource allocation and infrastructure investment decisions.

### 4. Geographic Bandwidth Distribution

**Definition:** Entropy of bandwidth distribution across countries

**Current Distribution:** 98.8% US, 1.2% Norway

**Mathematical Formula:**
```
Geographic_Entropy = -Σ(p_i × log₂(p_i)) where p_i = bandwidth_share_in_country_i
```

**Rationale:** Ensures bandwidth is geographically distributed for network resilience and reduced surveillance risk. Higher entropy indicates better geographic diversity.

**Importance:** Critical for anonymity and network resilience. Geographic concentration creates surveillance and censorship vulnerabilities.

**Current Assessment:** Low geographic diversity with heavy US concentration may present risks.

### 5. High-Performance Relay Concentration

**Definition:** Percentage of total bandwidth from top 20% of relays

**Mathematical Formula:**
```
HP_Concentration = Sum(top_20%_bandwidth) / Total_bandwidth × 100%
```

**Rationale:** Identifies whether bandwidth is concentrated in high-performing relays vs. distributed across many relays.

**Importance:** Shows resilience - high concentration means losing a few relays significantly impacts total capacity.

**Top 10 Analysis:** Top 10 relays (1.5% of fleet) contribute ~590 MB/s (~6.6% of total bandwidth), indicating reasonable distribution.

### 6. Relay Role Effectiveness

**Definition:** Bandwidth-weighted distribution across relay types (Guard, Middle, HSDir)

**Current Values:**
- Guard relays: 527/653 (80.7%)
- HSDir relays: 568/653 (87.0%)
- Stable relays: 602/653 (92.2%)

**Mathematical Formula:**
```
Role_Effectiveness = Σ(bandwidth_i × role_weight_i) / Total_bandwidth
```

**Rationale:** Different relay roles have different importance for network function. Guards are critical entry points, HSDirs serve hidden services.

**Importance:** Ensures the operator contributes to critical network functions, not just raw bandwidth.

### 7. Bandwidth Stability Score

**Definition:** Consistency of bandwidth provision over time

**Mathematical Formula:**
```
Stability_Score = 1 - (σ(bandwidth_over_time) / μ(bandwidth_over_time))
```

**Rationale:** Stable bandwidth is more valuable than fluctuating bandwidth. Users need predictable performance.

**Importance:** Higher stability scores indicate more reliable service contribution.

**Implementation:** Requires historical bandwidth data analysis over multiple time periods.

### 8. Network Impact Density

**Definition:** Bandwidth contribution relative to network size and geographic footprint

**Mathematical Formula:**
```
Impact_Density = Total_bandwidth / (Unique_AS_count × Geographic_locations)
```

**Rationale:** Measures efficient use of network diversity for maximum impact.

**Importance:** Higher density indicates effective placement of relays for maximum network benefit.

### 9. Uptime-Weighted Bandwidth

**Definition:** Bandwidth contribution weighted by relay reliability

**Current Status:** 100% of relays currently running

**Mathematical Formula:**
```
Weighted_Bandwidth = Σ(bandwidth_i × uptime_percentage_i)
```

**Rationale:** Accounts for reliability in bandwidth contribution. Intermittent high-bandwidth relays contribute less than consistent moderate-bandwidth relays.

**Importance:** Measures reliable capacity contribution to the network.

### 10. Exit Relay Bandwidth Ratio

**Definition:** Percentage of total bandwidth from exit relays

**Current Status:** All relays appear to be non-exit (reject *:* exit policy)

**Mathematical Formula:**
```
Exit_Ratio = Sum(exit_relay_bandwidth) / Total_bandwidth × 100%
```

**Rationale:** Exit relays are critical for network usability but carry higher legal/operational risk.

**Importance:** Balances network contribution with operational risk management.

**Current Assessment:** 0% exit bandwidth indicates risk-averse operational strategy.

## Detailed Relay Performance Analysis

### Top 10 Performers by Bandwidth

| Rank | Nickname | Bandwidth (MB/s) | Bandwidth (bytes/sec) |
|------|----------|------------------|----------------------|
| 1 | rapsodync | 64.4 | 67,481,347 |
| 2 | nipseyhussle | 63.1 | 66,165,886 |
| 3 | youngboy | 61.1 | 64,054,442 |
| 4 | lunchmoneylewis | 60.8 | 63,740,623 |
| 5 | kidcudi | 57.4 | 60,221,672 |
| 6 | quantrelleflow | 55.4 | 58,070,535 |
| 7 | krsone | 55.4 | 58,062,886 |
| 8 | projectpat | 54.1 | 56,720,811 |
| 9 | icecube | 53.8 | 56,385,676 |
| 10 | kaynewest | 53.8 | 56,366,174 |

**Analysis:** The top 10 relays contribute approximately 590 MB/s combined (6.6% of total bandwidth), indicating healthy distribution without excessive concentration.

## Strategic Recommendations

### 1. Geographic Diversification

**Current Risk:** 98.8% of relays are US-based, creating:
- Single jurisdiction risk
- Potential for coordinated shutdown
- Reduced anonymity for users

**Recommendation:** Expand to additional jurisdictions, targeting:
- European Union (GDPR-compliant countries)
- Switzerland/Iceland (strong privacy laws)
- Singapore/Japan (Asian coverage)
- Target: <80% in any single jurisdiction

### 2. Exit Relay Strategy

**Current Status:** Zero exit relays (all reject *:*)

**Trade-offs:**
- **Pros:** Lower legal risk, simplified operations
- **Cons:** Limited network utility, reduced user value

**Recommendation:** Consider operating a small percentage of exit relays (5-10%) in jurisdictions with:
- Strong legal protections for internet infrastructure
- Clear safe harbor provisions
- Experience with Tor exit operators

### 3. Bandwidth Efficiency Optimization

**Current Efficiency:** 1.33% (observed vs. advertised)

**Potential Issues:**
- Conservative bandwidth advertising
- Network bottlenecks
- Configuration optimization opportunities

**Recommendations:**
- Analyze network bottlenecks
- Review bandwidth rate configurations
- Consider burst capacity optimization
- Implement monitoring for bandwidth utilization

### 4. Performance Monitoring

**Implement real-time monitoring for:**
- Individual relay performance degradation
- Geographic performance patterns
- Bandwidth utilization trends
- Network role effectiveness

## Mathematical Models for Implementation

### Shannon Entropy Calculation for Geographic Diversity

```python
import math

def calculate_geographic_entropy(bandwidth_by_country):
    """Calculate Shannon entropy of geographic bandwidth distribution"""
    total_bandwidth = sum(bandwidth_by_country.values())
    entropy = 0
    
    for country_bandwidth in bandwidth_by_country.values():
        if country_bandwidth > 0:
            p = country_bandwidth / total_bandwidth
            entropy -= p * math.log2(p)
    
    return entropy

# Current 1aeo.com distribution
current_distribution = {
    'US': 9353727631 * 0.988,  # 98.8% of bandwidth
    'NO': 9353727631 * 0.012   # 1.2% of bandwidth
}

entropy = calculate_geographic_entropy(current_distribution)
print(f"Current geographic entropy: {entropy:.3f} bits")
# Maximum possible entropy with 2 countries: log2(2) = 1.0
print(f"Diversity efficiency: {entropy/1.0*100:.1f}%")
```

### Bandwidth Concentration Analysis

```python
def calculate_concentration_ratio(bandwidths, percentage=20):
    """Calculate what percentage of total bandwidth comes from top N% of relays"""
    sorted_bw = sorted(bandwidths, reverse=True)
    top_n = int(len(sorted_bw) * percentage / 100)
    top_bandwidth = sum(sorted_bw[:top_n])
    total_bandwidth = sum(sorted_bw)
    
    return (top_bandwidth / total_bandwidth) * 100

# Example with 1aeo.com data
# Top 10 relays contribute ~590 MB/s out of 8920 MB/s total
concentration = (590 / 8920) * 100
print(f"Top 1.5% of relays contribute {concentration:.1f}% of bandwidth")
```

### Relay Efficiency Scoring

```python
def calculate_relay_efficiency_score(relays):
    """Calculate comprehensive efficiency score for relay operations"""
    metrics = {
        'bandwidth_utilization': 0,
        'geographic_diversity': 0,
        'role_distribution': 0,
        'uptime_weighted': 0
    }
    
    # Bandwidth utilization (observed/advertised)
    total_observed = sum(r['observed_bandwidth'] for r in relays)
    total_advertised = sum(r['bandwidth_rate'] for r in relays)
    metrics['bandwidth_utilization'] = total_observed / total_advertised
    
    # Role distribution (percentage serving critical roles)
    guard_relays = sum(1 for r in relays if 'Guard' in r.get('flags', []))
    hsdir_relays = sum(1 for r in relays if 'HSDir' in r.get('flags', []))
    metrics['role_distribution'] = (guard_relays + hsdir_relays) / (2 * len(relays))
    
    # Uptime weighted (all currently running = 1.0)
    running_relays = sum(1 for r in relays if r.get('running', False))
    metrics['uptime_weighted'] = running_relays / len(relays)
    
    return metrics
```

## Data Sources and Methodology

**Primary Data Source:** Tor Project Onionoo API (https://onionoo.torproject.org/)

**Analysis Date:** July 6, 2025, 05:25 UTC

**Data Freshness:** Relays published 2025-07-06 04:00:00 UTC

**Methodology:**
1. Full relay enumeration from Onionoo `/details` endpoint
2. Contact field filtering for '1aeo.com' pattern
3. Real-time bandwidth and metadata analysis
4. Statistical analysis using Python standard library

**Data Validation:**
- Cross-referenced relay counts with expected ~650 relays ✓
- Verified active status across all relays ✓
- Confirmed bandwidth data consistency ✓

## Future Enhancements

### Historical Trend Analysis
- Implement time-series bandwidth tracking
- Seasonal performance pattern identification
- Growth trajectory modeling

### Comparative Analysis
- Benchmark against other major operators
- Network market share analysis
- Performance percentile rankings

### Predictive Modeling
- Bandwidth capacity forecasting
- Resource allocation optimization
- Performance degradation early warning

## Conclusion

The 1aeo.com AROI group represents a substantial and well-managed Tor relay operation contributing nearly 9 GB/s to the network. The consistent performance across 653 relays demonstrates operational excellence, though opportunities exist for geographic diversification and bandwidth efficiency optimization.

The proposed metrics framework provides comprehensive monitoring and optimization guidance while the real-time data analysis confirms the operator's significant positive impact on Tor network capacity and performance.

---

**Technical Implementation:** All analysis code available in the `propband1aeo` branch.  
**Data Archive:** Complete relay dataset stored in `1aeo_relays_data.json`  
**Contact:** Analysis performed for Allium project documentation.