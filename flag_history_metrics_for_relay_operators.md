# Flag History Metrics for Tor Relay Operators

## Overview

This document describes comprehensive flag history metrics implemented using the Onionoo uptime API to help Tor relay operators understand their flag performance, stability, and reliability over time. These metrics provide deep insights into how consistently relays maintain their assigned flags and perform their network roles.

## Core Metrics Implementation

### 1. Flag Consistency Analysis

**Purpose**: Measures how stable relay flags are over time, helping operators understand flag reliability.

**Metrics Provided**:
- **Stable Flags**: Flags with ≥95% uptime (excellent consistency)
- **Intermittent Flags**: Flags with 80-95% uptime (moderate consistency) 
- **Unstable Flags**: Flags with <80% uptime (poor consistency)
- **Overall Consistency Score**: Weighted average across all flags

**Display Example**:
```
Flag Consistency Summary:
✓ 3 stable flags (≥95% uptime) • ⚠ 1 intermittent flags (80-95%) • ✗ 0 unstable flags (<80%)
```

**Technical Implementation**:
- Analyzes flag-specific uptime data from Onionoo API
- Uses 1-month data primarily, with 6-month fallback
- Categorizes flags based on reliability thresholds
- Provides detailed reliability scores per flag

### 2. Role Performance Analysis

**Purpose**: Analyzes performance by specific relay roles (Guard, Exit, etc.) with importance weighting.

**Metrics Provided**:
- **Flag-Specific Reliability**: Individual performance for each flag
- **Role Descriptions**: Human-readable explanations of each flag's purpose
- **Performance Grades**: Excellent, Good, Fair, Poor, Critical
- **Importance Weighting**: Critical flags (Running, Authority) weighted higher

**Display Example**:
```
Flag Reliability by Role:
[Guard]     ████████████████████ 98.7%  Entry guard availability [Excellent]
[Exit]      ███████████████████  97.2%  Exit node availability [Good]
[Running]   ████████████████████ 99.1%  Basic operational status [Excellent]
[Fast]      ███████████████████  96.8%  High-performance availability [Good]
```

**Flag Importance Weights**:
- **Running**: 1.0 (Critical - basic operational status)
- **Authority**: 1.0 (Critical - directory authority)
- **Guard**: 0.9 (High importance - entry point role)
- **Exit**: 0.9 (High importance - exit point role)
- **Valid**: 0.9 (High importance - relay validity)
- **Stable**: 0.8 (High importance - reliability indicator)
- **Fast**: 0.7 (Medium importance - performance indicator)
- **HSDir**: 0.6 (Medium importance - hidden service directory)
- **V2Dir**: 0.5 (Lower importance - directory service)

### 3. Flag Stability Score

**Purpose**: Provides an overall weighted score for relay flag reliability.

**Calculation Method**:
- Weights each flag by importance (see above)
- Calculates reliability percentage for each flag
- Computes weighted average: `Σ(flag_reliability × flag_weight) / Σ(flag_weights)`
- Assigns performance grade based on final score

**Grade Thresholds**:
- **Excellent**: ≥98%
- **Good**: 95-98%
- **Fair**: 90-95%
- **Poor**: 80-90%
- **Critical**: <80%

**Display Example**:
```
Overall Flag Stability Score: 98.7% (Excellent)
```

### 4. Comparative Analysis vs Network Benchmarks

**Purpose**: Compares relay flag performance against expected network benchmarks.

**Benchmarks Used**:
- **Running**: 98.0% (Expected for basic operational status)
- **Guard**: 95.0% (Expected for guard eligibility)
- **Exit**: 95.0% (Expected for exit capability)
- **Fast**: 90.0% (Expected for fast flag)
- **Stable**: 97.0% (Expected for stable flag)
- **Authority**: 99.0% (Expected for authorities)

**Metrics Provided**:
- **Above/Below Benchmark**: Count of flags meeting benchmarks
- **Performance Difference**: Actual performance vs benchmark
- **Benchmark Status**: Whether each flag meets expected standards

### 5. Role-Based Reliability

**Purpose**: Aggregates flag data into major role categories for easier understanding.

**Role Categories**:
- **Entry Guard**: Based on Guard flag reliability
- **Exit Node**: Based on Exit flag reliability  
- **Basic Operation**: Based on Running flag reliability
- **Directory Services**: Average of V2Dir and HSDir flags

**Display Example**:
```
Role-Specific Reliability:
🛡️ Entry Guard: 98.7%
🚪 Exit Node: 97.2%
⚡ Basic Operation: 99.1%
📁 Directory Services: 94.8%
```

### 6. Operator-Wide Analysis

**Purpose**: Provides fleet-wide analysis for operators running multiple relays.

**Metrics Provided**:
- **Overall Fleet Stability**: Average stability across all operator relays
- **Role Performance Breakdown**: Performance statistics by role across fleet
- **Problem Relay Identification**: Relays with stability scores <80%
- **Excellent Performer Recognition**: Relays with stability scores ≥95%
- **Performance Distribution**: Min, max, average, and standard deviation per role

**Categories**:
- **Excellent Performers**: Relays with ≥95% stability scores
- **Problem Relays**: Relays with <80% stability scores
- **Best/Worst Performing Roles**: Identification of strongest/weakest roles

### 7. Issues Detection & Recommendations

**Purpose**: Automatically identifies problems and provides actionable recommendations.

**Issue Detection**:
- Flags with reliability below 85%
- Missing critical flags (Running, Guard, Exit, Authority, Valid)
- Concerning flag performance patterns

**Recommendation Engine**:
- **Infrastructure Review**: For flags with poor reliability
- **Role Configuration**: Suggests Guard/Exit role configuration if missing
- **Maintenance Practices**: Recommendations for excellent performers

**Example Recommendations**:
```
📋 Recommendations:
• Excellent flag reliability - maintain current practices
• Consider configuring relay for Guard or Exit role
• Review relay configuration for concerning flags
```

**Example Issues**:
```
⚠️ Issues Detected:
• Running flag reliability below 85% (82.3%)
• Guard flag inconsistent performance detected
• Critical flag configuration missing
```

## Data Sources & Technical Details

### Onionoo API Integration

**Data Source**: Tor Project's Onionoo uptime API (`https://onionoo.torproject.org/uptime`)

**API Structure Used**:
```json
{
  "relays": [
    {
      "fingerprint": "ABC123...",
      "flags": {
        "Running": {
          "1_month": {"values": [999, 998, 999, ...]},
          "6_months": {"values": [...]},
          "1_year": {"values": [...]},
          "5_years": {"values": [...]}
        },
        "Guard": {
          "1_month": {"values": [...]},
          ...
        }
      }
    }
  ]
}
```

**Data Processing**:
- Values normalized from 0-999 scale to 0-100 percentage
- Primary analysis uses 1-month data for recent performance
- Fallback to 6-month data if 1-month unavailable
- Statistical outlier detection using 2σ threshold

### Implementation Architecture

**Core Components**:
1. **FlagHistoryAnalyzer**: Main analysis engine
2. **Flag History Utilities**: Shared processing functions
3. **Template Integration**: Display components for relay pages
4. **Coordinator Integration**: Data processing pipeline

**Processing Flow**:
1. Onionoo uptime data fetched via coordinator
2. Flag history analyzer processes raw data
3. Individual relay analysis performed
4. Operator-wide aggregation computed
5. Display data generated for templates
6. Templates render comprehensive flag metrics

### Performance Considerations

**Optimization Strategies**:
- Shared utility functions to avoid code duplication
- Cached analysis results attached to relay objects
- Progressive data processing (individual → operator-wide)
- Fallback mechanisms for missing data

**Memory Efficiency**:
- Flag data processed incrementally
- Analysis results stored efficiently
- Display data pre-computed for templates
- Minimal redundant calculations

## User Interface & Display

### Individual Relay Pages

**Location**: Displayed in relay-info.html after current flags section

**Layout Features**:
- **Color-coded performance indicators**: Green (excellent), Yellow (good/fair), Red (poor/critical)
- **Grid-based flag performance display**: Easy visual scanning
- **Role-specific reliability boxes**: Major roles prominently displayed
- **Consistency summary**: Quick flag stability overview
- **Actionable recommendations**: Specific improvement suggestions
- **Issue alerts**: Highlighted problems requiring attention

### Operator Contact Pages

**Integration**: Added to contact page display data for comprehensive operator analysis

**Fleet Overview Features**:
- Overall fleet stability scoring
- Role performance distribution
- Problem relay identification
- Best performer recognition
- Comparative fleet analysis

## Benefits for Relay Operators

### 1. **Operational Visibility**
- Understand flag consistency over time
- Identify infrastructure problems early
- Track role performance trends
- Monitor reliability improvements

### 2. **Performance Optimization**
- Benchmark against network standards
- Identify underperforming relays
- Focus maintenance efforts effectively
- Improve overall network contribution

### 3. **Strategic Planning**
- Understand role suitability (Guard vs Exit)
- Plan infrastructure upgrades
- Optimize relay configurations
- Set reliability targets

### 4. **Network Contribution**
- Maximize Tor network value
- Ensure reliable relay operation
- Support network health goals
- Improve user experience

## Technical Implementation Examples

### Analyzing a Single Relay
```python
from allium.lib.flag_history_utils import FlagHistoryAnalyzer

# Initialize with Onionoo uptime data
analyzer = FlagHistoryAnalyzer(uptime_data)

# Analyze specific relay
analysis = analyzer.analyze_relay_flag_history(fingerprint)

# Access results
stability_score = analysis['flag_stability_score']['overall_score']
role_performance = analysis['role_performance']
recommendations = analysis['flag_metrics_summary']['recommendations']
```

### Operator Fleet Analysis
```python
# Analyze entire operator fleet
fleet_analysis = analyzer.analyze_operator_flag_performance(operator_relays)

# Access fleet metrics
fleet_stability = fleet_analysis['overall_flag_stability']
problem_relays = fleet_analysis['problem_relays']
excellent_performers = fleet_analysis['excellent_performers']
```

### Template Integration
```html
<!-- In relay-info.html -->
{% if relay.flag_history.has_flag_data %}
<dt>🏷️ Flag History & Performance</dt>
<dd>
    <div>Overall Score: {{ relay.flag_history.overall_score }}%</div>
    <!-- Additional display components -->
</dd>
{% endif %}
```

## Future Enhancements

### Potential Improvements
1. **Flag Transition Timeline**: Detailed analysis of when flags were gained/lost
2. **Predictive Analytics**: Forecasting flag stability trends
3. **Network-wide Comparisons**: Benchmarking against actual network averages
4. **Historical Trend Charts**: Visual flag performance over time
5. **Alert System**: Automated notifications for flag performance issues

### Integration Opportunities
1. **AROI Leaderboards**: Flag stability as ranking factor
2. **Intelligence Engine**: Flag reliability in network analysis
3. **Downtime Monitoring**: Flag-specific downtime analysis
4. **Performance Correlation**: Link flag stability to bandwidth/consensus weight

## Conclusion

The flag history metrics provide Tor relay operators with unprecedented visibility into their relay flag performance and reliability. By leveraging the Onionoo uptime API's flag-specific data, operators can:

- **Monitor** flag consistency and reliability over time
- **Understand** their relay's role performance in the network  
- **Identify** issues before they impact network contribution
- **Optimize** relay configurations for better flag stability
- **Benchmark** performance against network standards
- **Plan** infrastructure improvements strategically

These metrics transform raw flag uptime data into actionable insights that help operators run more reliable relays and contribute more effectively to the Tor network's health and performance.