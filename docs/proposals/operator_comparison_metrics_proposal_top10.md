# Operator Performance Comparison (OpUpComp) - Metrics Proposal

## Executive Summary

This proposal outlines 10 key metrics to add operator comparison functionality to contact detail pages, showing how each contact/operator compares to both the overall Tor network and operators with similar relay counts. Based on extensive research of tor-relays mailing list discussions and operator pain points, these metrics address the most common concerns and questions from relay operators.

## Research Background

From tor-relays mailing list analysis, the most common operator concerns include:
- Consensus weight vs advertised bandwidth discrepancies
- Bandwidth measurement and scanning effectiveness  
- Performance relative to similar-scale operators
- Resource optimization (CPU, memory, network)
- Geographic and infrastructure diversity
- Uptime and reliability benchmarks
- Network position and role optimization
- Hardware configuration effectiveness
- Security and attack mitigation
- Exit policy and traffic management

## Proposed Metrics (Priority Order)

### 1. **Network Uptime Performance Benchmark** (Priority: Critical)

**Format:** `Network Uptime 6mo: 2.3% lower than mean of 94.2%, and 4.5% below 95th percentile of 99.1%`

**Mockup:**
```
📊 Uptime Benchmarking - torworld.example.org              
├─────────────────────────────────────────────────────────┤
│ Your Score: 98.7%  Network Ranking: 92nd Percentile     │
│                                                         │
│ 🏆 Performance vs Network:                              │
│ • 95th percentile: 99.1% (↓ 0.4% below target)         │
│ • 90th percentile: 98.3% (✅ You exceed this)           │
│ • Network average: 94.2% (↑ 4.5% above average)        │
│ • 25th percentile: 91.7% (↑ 7.0% above low performers) │
└─────────────────────────────────────────────────────────┘
```

**Proposal:** Compare operator's 6-month uptime average against network percentiles. Critical because uptime directly impacts network stability and user experience. Helps operators understand if infrastructure investments are paying off.

**Data Sources:** Onionoo uptime API, existing `operator_reliability` calculations
**Implementation:** Extend `_calculate_operator_reliability()` method

---

### 2. **Consensus Weight Efficiency Rating** (Priority: Critical)

**Format:** `Consensus Weight Efficiency: 23% lower than operators with 50-100 relays (0.67 vs 0.87 ratio), 45% below network median`

**Mockup:**
```
⚖️ Consensus Weight Efficiency Analysis
├─────────────────────────────────────────────────────────┤
│ CW/Bandwidth Ratio: 0.67  Peer Group Avg: 0.87         │
│                                                         │
│ 📈 Efficiency Breakdown:                                │
│ • Similar operators (50-100 relays): 87% efficiency    │
│ • Your efficiency: 67% (↓ 23% below peer group)        │
│ • Network median: 75% (↓ 11% below median)             │
│ • Top 10% threshold: 92% (↓ 27% below excellence)      │
│                                                         │
│ 💡 Improvement Potential:                               │
│ • Focus on: Guard relay optimization                    │
│ • Consider: Infrastructure latency reduction            │
└─────────────────────────────────────────────────────────┘
```

**Proposal:** Addresses the #1 operator complaint - when consensus weight is much lower than advertised bandwidth. Compare consensus_weight/observed_bandwidth ratio against peers.

**Data Sources:** Existing consensus weight and bandwidth data
**Implementation:** New method `_calculate_cw_efficiency_benchmark()`

---

### 3. **Peer Group Performance Comparison** (Priority: High)

**Format:** `Operators with 100-200 relays Uptime 6mo: 1.2% higher than your 98.7%, 0.8% below their 95th percentile of 99.5%`

**Mockup:**
```
👥 Peer Group Analysis (100-200 Relay Operators)
├─────────────────────────────────────────────────────────┤
│ Your Rank: #3 out of 12 similar operators              │
│                                                         │
│ 🎯 Key Metrics vs Peers:                               │
│ • Uptime: 98.7% vs peer avg 97.5% (↑ 1.2% better)     │
│ • Bandwidth utilization: 76% vs peer avg 68% (↑ 8%)   │
│ • Consensus weight ratio: 0.67 vs peer avg 0.87 (↓23%) │
│ • Geographic diversity: 4 countries vs avg 2.1 (↑90%) │
│                                                         │
│ 🏆 Peer Rankings:                                       │
│ • Top performer: 99.1% uptime, 0.94 CW ratio           │
│ • Median performer: 96.8% uptime, 0.85 CW ratio        │
└─────────────────────────────────────────────────────────┘
```

**Proposal:** Groups operators by relay count ranges (1-5, 6-25, 26-100, 100-500, 500+) and compares key metrics. Addresses operators' desire to compare against similar-scale peers.

**Data Sources:** Existing contact aggregation data
**Implementation:** New method `_generate_peer_group_comparisons()`

---

### 4. **Resource Utilization Efficiency Score** (Priority: High)

**Format:** `Resource Efficiency: 89% higher than network average, 12% above similar operators (50-100 relays)`

**Mockup:**
```
🖥️ Resource Utilization Analysis
├─────────────────────────────────────────────────────────┤
│ Efficiency Score: 89%  Network Ranking: 85th percentile│
│                                                         │
│ 💻 Performance Indicators:                              │
│ • Bandwidth per relay: 12.4 MB/s vs network avg 8.1    │
│ • Overload incidents: 0 vs peer avg 2.3 per month      │
│ • TCP port efficiency: 94% vs network avg 76%          │
│ • Memory utilization: Optimal (no OOM events)          │
│                                                         │
│ 🎯 Optimization Status:                                 │
│ • CPU: Well-balanced (no onionskin drops)              │
│ • Network: Excellent peering performance               │
│ • Platform: Modern stack (Linux 6.x)                   │
└─────────────────────────────────────────────────────────┘
```

**Proposal:** Analyzes bandwidth-per-relay, overload states, and resource constraints. Helps operators understand if their hardware investments are optimal.

**Data Sources:** MetricsPort data, overload flags, bandwidth efficiency calculations
**Implementation:** Extend existing overload detection logic

---

### 5. **Network Position Effectiveness Rating** (Priority: High)

**Format:** `Network Position: Guard-focused role 34% more effective than similar operators, Exit coverage 67% below optimal`

**Mockup:**
```
🛡️ Network Position Analysis
├─────────────────────────────────────────────────────────┤
│ Primary Role: Guard-focused (87% guard traffic)        │
│                                                         │
│ 📊 Position Effectiveness:                              │
│ • Guard performance: 134% of peer average (excellent)  │
│ • Middle efficiency: 98% of peer average (adequate)    │
│ • Exit contribution: 33% of potential (improvement)    │
│                                                         │
│ 🎯 Strategic Assessment:                                │
│ • Guard role: Exceeding expectations (+34%)            │
│ • Network impact: High value in current position       │
│ • Growth opportunity: Consider exit policy expansion    │
│                                                         │
│ 🏆 Compared to similar operators (50-100 relays):      │
│ • Guard consensus weight: Top 15%                      │
│ • Overall network influence: Top 25%                   │
└─────────────────────────────────────────────────────────┘
```

**Proposal:** Evaluates how effectively an operator fills their network role (guard/middle/exit) compared to peers.

**Data Sources:** Flag distributions, consensus weight analysis
**Implementation:** New method `_analyze_network_position_effectiveness()`

---

### 6. **Geographic and Infrastructure Diversity Score** (Priority: Medium)

**Format:** `Infrastructure Diversity: 67% above network median (4 ASes vs avg 1.8), 23% above similar operators`

**Mockup:**
```
🌍 Diversity & Resilience Analysis
├─────────────────────────────────────────────────────────┤
│ Diversity Score: 85%  Network Ranking: 78th percentile │
│                                                         │
│ 🏗️ Infrastructure Spread:                              │
│ • Autonomous Systems: 4 vs network avg 1.8 (↑122%)    │
│ • Countries: 3 vs peer avg 1.4 (↑114%)                │
│ • Platform diversity: Great (Linux + FreeBSD)          │
│                                                         │
│ ⚖️ Risk Assessment:                                      │
│ • Single-point failures: Low risk (good distribution)  │
│ • Censorship resistance: High (3 jurisdictions)        │
│ • Network resilience: Above average contribution       │
│                                                         │
│ 🎯 Compared to 50-100 relay operators:                 │
│ • ASN diversity: Top 20% (excellent)                   │
│ • Geographic spread: Top 25% (very good)               │
└─────────────────────────────────────────────────────────┘
```

**Proposal:** Measures infrastructure and geographic distribution effectiveness. Addresses operators' questions about optimal relay placement.

**Data Sources:** Existing intelligence engine data, AS and country distributions
**Implementation:** Leverage existing `intelligence_engine.py` calculations

---

### 7. **Bandwidth Measurement Coverage Score** (Priority: Medium)

**Format:** `Bandwidth Measurements: 92% of relays measured vs network average 76%, 15% above similar operators`

**Mockup:**
```
📏 Bandwidth Measurement Analysis
├─────────────────────────────────────────────────────────┤
│ Measurement Rate: 92%  Network Ranking: 82nd percentile│
│                                                         │
│ 🔍 Authority Coverage:                                  │
│ • Measured relays: 92% vs network avg 76% (↑21%)      │
│ • Unmeasured relays: 4 of 50 relays (needs attention) │
│ • Authority consensus: High agreement across DirAuths │
│                                                         │
│ 📊 Performance Impact:                                  │
│ • Measured relays: Contributing 96% of capacity        │
│ • Unmeasured relays: 4% potential capacity lost        │
│ • Network visibility: Excellent measurement profile    │
│                                                         │
│ 🎯 Optimization Opportunities:                          │
│ • Focus: 4 unmeasured relays need investigation        │
│ • Consider: Network connectivity improvements           │
└─────────────────────────────────────────────────────────┘
```

**Proposal:** Tracks what percentage of operator's relays are being measured by bandwidth authorities. Critical for consensus weight optimization.

**Data Sources:** Consensus votes, measurement status from directory authorities
**Implementation:** New method `_analyze_measurement_coverage()`

---

### 8. **Network Traffic Load Balance Rating** (Priority: Medium)

**Format:** `Traffic Distribution: 23% more balanced than network average, 8% better than similar operators`

**Mockup:**
```
⚖️ Network Load Balance Analysis
├─────────────────────────────────────────────────────────┤
│ Balance Score: 78%  Network Ranking: 71st percentile   │
│                                                         │
│ 🌊 Traffic Distribution:                                │
│ • Guard traffic: 45% (ideal 30-60% range) ✅           │
│ • Middle traffic: 35% (balanced contribution) ✅        │
│ • Exit traffic: 20% (healthy exit ratio) ✅            │
│                                                         │
│ 📈 Load Efficiency:                                     │
│ • Peak utilization: 78% (good headroom)                │
│ • Load variance: ±12% (stable performance)             │
│ • Congestion events: 0 in past month (excellent)       │
│                                                         │
│ 🎯 Compared to similar operators:                       │
│ • More balanced than 71% of network                    │
│ • Better stability than peer average                   │
└─────────────────────────────────────────────────────────┘
```

**Proposal:** Analyzes how well traffic is distributed across operator's relays. Helps identify bottlenecks and optimization opportunities.

**Data Sources:** Traffic distribution data, load patterns
**Implementation:** New method `_analyze_traffic_load_balance()`

---

### 9. **Platform and Configuration Optimization Score** (Priority: Medium)

**Format:** `Platform Optimization: 34% above network average, using best practices for 89% of configurations`

**Mockup:**
```
🔧 Platform & Configuration Analysis
├─────────────────────────────────────────────────────────┤
│ Optimization Score: 89%  Ranking: 86th percentile      │
│                                                         │
│ 💻 Platform Performance:                                │
│ • Modern Linux kernel: 94% vs network avg 67% (↑40%)  │
│ • Tor version: Latest stable (excellent)               │
│ • IPv6 support: 100% enabled vs network avg 84%       │
│                                                         │
│ ⚙️ Configuration Health:                                │
│ • Port selection: Optimal (443, 80, 9001)              │
│ • Exit policy: Well-configured for role                │
│ • Family configuration: Properly implemented           │
│                                                         │
│ 🏆 Best Practices:                                      │
│ • Security: Above average implementation               │
│ • Performance: Optimized for high-traffic             │
│ • Compliance: Meets all network standards             │
└─────────────────────────────────────────────────────────┘
```

**Proposal:** Evaluates platform choices and configuration optimizations. Addresses operators' questions about ideal hardware/software setups.

**Data Sources:** Platform statistics, version information, configuration analysis
**Implementation:** Extend existing platform categorization

---

### 10. **Security and Resilience Score** (Priority: Lower)

**Format:** `Security Posture: 45% above network baseline, 12% better than similar operators in attack mitigation`

**Mockup:**
```
🛡️ Security & Resilience Analysis
├─────────────────────────────────────────────────────────┤
│ Security Score: 82%  Network Ranking: 79th percentile  │
│                                                         │
│ 🔐 Security Metrics:                                    │
│ • DDoS mitigation: Active protection detected          │
│ • Connection filtering: Balanced (not overly strict)   │
│ • Update cadence: Excellent (current versions)         │
│                                                         │
│ 🛠️ Resilience Factors:                                 │
│ • Overload recovery: Fast recovery patterns            │
│ • Stability under load: Above average performance      │
│ • Network position security: Well-protected relays     │
│                                                         │
│ 📊 Compared to similar operators:                       │
│ • Attack resistance: Top 20%                           │
│ • Recovery efficiency: Top 30%                         │
│ • Overall resilience: Above peer average               │
└─────────────────────────────────────────────────────────┘
```

**Proposal:** Assesses security posture and attack resilience. Lower priority but important for exit operators facing attacks.

**Data Sources:** Overload patterns, attack signatures, recovery metrics
**Implementation:** New method `_analyze_security_resilience()`

---

## Implementation Plan

### Phase 1: Data Infrastructure (Weeks 1-2)
1. Extend `_compute_contact_display_data()` method in `relays.py`
2. Create new comparison calculation methods
3. Implement peer grouping logic
4. Add network percentile calculations

### Phase 2: Template Integration (Week 3)
1. Add metrics section to `contact.html` template  
2. Position metrics prominently at top of contact page
3. Create responsive design for mobile compatibility
4. Implement progressive disclosure for detailed breakdowns

### Phase 3: Testing and Refinement (Week 4)
1. Unit tests for all comparison calculations
2. Integration tests with real network data
3. Performance optimization for large operators
4. Documentation and operator guidance

## Template Integration

**Proposed Location:** Top of existing contact page, before current "Contact & Network Overview" section

```html
<!-- NEW: Operator Performance Comparison Section -->
<div class="operator-comparison-metrics" style="margin-bottom: 20px;">
    <h3 style="color: #495057; margin-bottom: 15px;">📊 Performance vs Network</h3>
    <div class="metrics-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px;">
        <!-- Top 4 critical metrics displayed prominently -->
        <div class="metric-card">{{ uptime_benchmark_display }}</div>
        <div class="metric-card">{{ consensus_weight_efficiency_display }}</div>
        <div class="metric-card">{{ peer_group_comparison_display }}</div>
        <div class="metric-card">{{ resource_utilization_display }}</div>
    </div>
    
    <!-- Expandable section for remaining 6 metrics -->
    <details style="margin-top: 15px;">
        <summary style="cursor: pointer; font-weight: bold;">📈 View Additional Performance Metrics</summary>
        <div class="additional-metrics" style="margin-top: 10px;">
            <!-- Remaining 6 metrics here -->
        </div>
    </details>
</div>
```

## Success Metrics

1. **Operator Engagement:** Increase contact page time-on-site by 40%
2. **Network Health:** Help operators identify optimization opportunities
3. **Community Value:** Reduce "how do I compare?" questions on tor-relays mailing list
4. **Data-Driven Decisions:** Enable operators to make informed infrastructure investments

## Future Enhancements

- Historical trending for all metrics
- Peer group chat/forum integration
- Automated improvement recommendations
- Performance prediction modeling
- Integration with relay operator tools

---

This proposal addresses the real pain points identified in tor-relays mailing list research while leveraging existing Allium data infrastructure for efficient implementation.