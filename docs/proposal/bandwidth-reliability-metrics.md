# Bandwidth Reliability Metrics Implementation Proposal

**Status**: 📋 **PROPOSAL** - Comprehensive plan for future implementation  
**Date**: January 2025  
**Author**: Development Team  

## Executive Summary

This proposal outlines a comprehensive plan for implementing bandwidth reliability metrics for Tor relay operators, mirroring the existing uptime reliability system. The proposed implementation would add detailed bandwidth analysis including observed bandwidth, network position percentiles, bandwidth stability, growth trends, and flag-specific bandwidth capacity analysis.

## 🎯 Objectives

1. **Primary Goal**: Propose bandwidth reliability metrics for operator contact pages
2. **Secondary Goal**: Design flag-specific bandwidth capacity analysis
3. **Performance Goal**: Plan seamless integration with existing uptime processing
4. **UI Goal**: Specify consistent styling matching existing reliability patterns

## 📊 Technical Architecture

### Data Flow Pipeline

```
Onionoo Bandwidth API
       ↓
Coordinator.create_relay_set()
       ↓
RelaySet._reprocess_bandwidth_data()
       ↓
RelaySet._calculate_operator_reliability()
       ↓
bandwidth_utils.calculate_operator_bandwidth_reliability()
       ↓
RelaySet._compute_contact_display_data()
       ↓
contact.html Jinja2 Template
```

### Proposed Implementation Components

#### 1. Data Processing Layer (`allium/lib/bandwidth_utils.py`)

**Proposed New Functions:**

```python
def calculate_operator_bandwidth_reliability(operator_relays, bandwidth_data, periods=['1_month', '6_months', '1_year', '5_years'])
```
- **Purpose**: Calculate comprehensive bandwidth metrics for an operator
- **Returns**: Dictionary with observed bandwidth, stability metrics, growth trends
- **Performance**: Single-pass calculation, O(n) complexity

```python
def calculate_network_position_percentiles(operator_bandwidth, network_percentiles)
```
- **Purpose**: Determine operator's position in network bandwidth distribution
- **Returns**: Percentile ranking (0-100)
- **Integration**: Uses pre-calculated network percentiles for efficiency

```python
def process_operator_flag_bandwidth_reliability(operator_relays, bandwidth_data, flag_statistics)
```
- **Purpose**: Calculate flag-specific bandwidth capacity
- **Returns**: Per-flag bandwidth analysis with network comparisons
- **Flags Analyzed**: Guard, Exit, Fast, Stable, Running, HSDir, Authority, V2Dir

**Proposed Code Location**: `allium/lib/bandwidth_utils.py` (new functions to be added)

#### 2. Relay Processing Layer (`allium/lib/relays.py`)

**Proposed Function Enhancements:**

```python
def _reprocess_bandwidth_data(self)
```
- **Purpose**: Calculate network-wide bandwidth percentiles and flag statistics
- **Proposed Location**: New function to be added
- **Integration**: Would be called alongside `_reprocess_uptime_data()` for efficiency
- **Output**: Would set `self.network_bandwidth_percentiles` and `self.network_flag_bandwidth_statistics`

```python
def _calculate_operator_reliability(self, contact_hash, operator_relays)
```
- **Proposed Enhancement**: Would add bandwidth reliability calculation alongside uptime
- **Current Location**: Existing function to be enhanced
- **Integration**: Would call `calculate_operator_bandwidth_reliability()` from bandwidth_utils
- **Output**: Would provide combined reliability stats with both uptime and bandwidth metrics

```python
def _compute_contact_flag_bandwidth_analysis(self, operator_relays)
```
- **Purpose**: Would generate flag-specific bandwidth analysis for operator
- **Proposed Location**: New function to be added
- **Output**: Would provide flag reliability data with color coding for performance indicators

```python
def _compute_contact_display_data(self, contact_hash, operator_relays)
```
- **Proposed Enhancement**: Would add bandwidth metrics formatting and flag bandwidth analysis
- **Current Location**: Existing function to be enhanced
- **Output**: Would provide formatted bandwidth data ready for template rendering

#### 3. Coordination Layer (`allium/lib/coordinator.py`)

**Proposed Integration Point:**

```python
# Process bandwidth data for reliability analysis (grouped with uptime processing)
if bandwidth_data:
    relay_set._reprocess_bandwidth_data()
```
- **Proposed Location**: Enhancement to existing coordinator logic
- **Purpose**: Would ensure bandwidth processing occurs alongside uptime processing
- **Performance**: Would add single additional function call in existing workflow

#### 4. Template Layer (`allium/templates/contact.html`)

**Proposed New Template Sections:**

```html
<!-- 📊 Bandwidth Reliability Section -->
{% if contact_data.reliability and contact_data.reliability.bandwidth_reliability %}
<div class="metric-section">
    <h3>📊 Bandwidth Reliability</h3>
    <!-- Primary Metrics -->
    <!-- Secondary Metrics -->
    <!-- Data Availability -->
</div>
{% endif %}

<!-- 📊 Flag Bandwidth Reliability Section -->
{% if contact_data.flag_bandwidth_analysis %}
<div class="metric-section">
    <h3>📊 Flag Bandwidth Reliability</h3>
    <!-- Flag-specific bandwidth capacity -->
    <!-- Color-coded performance indicators -->
</div>
{% endif %}
```

**Proposed Location**: Would be added after existing reliability sections

## 📈 Metrics Specifications

### Primary Bandwidth Metrics

#### 1. **Observed Bandwidth**
- **Calculation**: Time-weighted averages across multiple periods
- **Periods**: 30 days, 90 days, 6 months, 1 year, 5 years
- **Units**: Automatically scaled (MB/s, GB/s)
- **Display**: `6mo 45.2 GB/s (3), 1y 38.7 GB/s (3), 5y 32.1 GB/s (2)`

#### 2. **Network Position Percentile**
- **Calculation**: Operator's bandwidth ranking vs all network operators
- **Range**: 0-100th percentile
- **Display**: `85th percentile in bandwidth distribution`

#### 3. **Bandwidth Stability**
- **Calculation**: Coefficient of variation (std dev / mean)
- **Categories**: 
  - Excellent: CV < 15%
  - Good: CV 15-30%
  - Variable: CV > 30%
- **Display**: `Excellent stability (CV: 8.3%)`

#### 4. **Peak vs Average Ratio**
- **Calculation**: Historical peak bandwidth / current average
- **Purpose**: Identify performance consistency
- **Display**: `87% of historical peak (52.1 GB/s)`

### Secondary Bandwidth Metrics

#### 5. **Growth Trend**
- **Calculation**: Month-over-month bandwidth change
- **Indicators**: 📈 (growth), 📉 (decline), ➡️ (stable)
- **Display**: `📈 +12.3% month-over-month`

#### 6. **Capacity Utilization**
- **Calculation**: Current bandwidth / historical maximum
- **Range**: 0-100%
- **Display**: `87% of historical peak capacity`

### Flag-Specific Metrics

#### Flag Bandwidth Capacity
- **Flags Analyzed**: Guard, Exit, Fast, Stable, Running, HSDir, Authority, V2Dir
- **Periods**: 1M/6M/1Y/5Y bandwidth averages
- **Performance Indicators**:
  - 🟢 Green: Top 10% network bandwidth for flag type
  - 🟡 Yellow: Bottom 10% network bandwidth for flag type
  - ⚪ White: Average performance

## 🎨 User Interface Mockups

### Complete Contact Page Layout

```
👤 Contact: 1aeo
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Relay Reliability
• Total Relay Uptime: 6mo 98.7% (3), 1y 97.2% (3), 5y 96.8% (2)
  ├─ Consensus Uptime: 6mo 98.9% (3), 1y 97.5% (3), 5y 97.1% (2)
  └─ Reachability: 6mo 98.5% (3), 1y 96.9% (3), 5y 96.5% (2)
  ○ Data available for 3/3 relays

📊 Bandwidth Reliability                                    ← NEW SECTION
• Observed Bandwidth: 6mo 45.2 GB/s (3), 1y 38.7 GB/s (3), 5y 32.1 GB/s (2)
  ├─ Growth Trend: 📈 +12.3% month-over-month
  ├─ Network Position: 85th percentile in bandwidth distribution
  └─ Capacity Utilization: 87% of historical peak (52.1 GB/s)
  ○ Bandwidth Stability: Excellent stability (CV: 8.3%)

Bandwidth data available for 3/3 relays

📊 Flag Reliability
Fast: 6mo 87.3% (2), 1y 85.1% (2), 5y 83.7% (1)
Guard: 6mo 91.2% (1), 1y 89.8% (1), 5y 88.5% (1)
Stable: 6mo 94.5% (2), 1y 92.1% (2), 5y 90.8% (1)

📊 Flag Bandwidth Reliability                               ← NEW SECTION
Flag-specific bandwidth capacity (1M/6M/1Y/5Y):

🛡️ Entry Guard: 🟢 89.4 MB/s / 78.3 MB/s / 67.1 MB/s / 58.9 MB/s
🚪 Exit Node: 🟢 156.8 MB/s / 145.2 MB/s / 134.7 MB/s / 128.3 MB/s  
⚡ Fast Relay: ⚪ 92.1 MB/s / 84.6 MB/s / 76.2 MB/s / 69.8 MB/s
🟢 Running Operation: ⚪ 85.7 MB/s / 79.3 MB/s / 72.4 MB/s / 66.1 MB/s

🟢 Green: Top 10% network bandwidth, 🟡 Yellow: Bottom 10% network bandwidth

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Bandwidth Reliability Section Detail

```html
<div class="metric-section">
    <h3>📊 Bandwidth Reliability</h3>
    
    <!-- Primary Metrics -->
    <div class="metric-primary">
        <span class="metric-bullet">•</span>
        <span class="metric-label">Observed Bandwidth:</span>
        <span class="metric-values">
            6mo 45.2 GB/s (3), 1y 38.7 GB/s (3), 5y 32.1 GB/s (2)
        </span>
    </div>
    
    <!-- Secondary Metrics Tree -->
    <div class="metric-secondary-tree">
        <div class="metric-branch">
            <span class="tree-connector">├─</span>
            <span class="metric-label">Growth Trend:</span>
            <span class="trend-up">📈 +12.3% month-over-month</span>
        </div>
        <div class="metric-branch">
            <span class="tree-connector">├─</span>
            <span class="metric-label">Network Position:</span>
            <span class="percentile-high">85th percentile in bandwidth distribution</span>
        </div>
        <div class="metric-branch">
            <span class="tree-connector">└─</span>
            <span class="metric-label">Capacity Utilization:</span>
            <span class="utilization-good">87% of historical peak (52.1 GB/s)</span>
        </div>
    </div>
    
    <!-- Stability Metric -->
    <div class="metric-stability">
        <span class="metric-bullet">○</span>
        <span class="metric-label">Bandwidth Stability:</span>
        <span class="stability-excellent">Excellent stability (CV: 8.3%)</span>
    </div>
    
    <!-- Data Availability -->
    <div class="data-availability">
        Bandwidth data available for 3/3 relays
    </div>
</div>
```

## 💾 Data Handling Implementation

### Input Data Sources

#### 1. Onionoo Bandwidth API
- **Endpoint**: `https://onionoo.torproject.org/bandwidth`
- **Data Structure**: Historical bandwidth readings per relay
- **Time Periods**: 5+ years of historical data
- **Processing**: Cached locally for 12 hours

#### 2. Relay Details API
- **Endpoint**: `https://onionoo.torproject.org/details`
- **Data Structure**: Relay metadata including flags
- **Usage**: Flag assignment for bandwidth analysis

### Data Processing Pipeline

#### Stage 1: Raw Data Extraction
```python
# allium/lib/bandwidth_utils.py
def extract_relay_bandwidth_for_period(relays, bandwidth_data, period):
    """Extract bandwidth values for specified time period"""
    # Input: List of relay objects, bandwidth API data, time period
    # Output: {"bandwidth_values": [float], "relay_count": int, "data_points": int}
```

#### Stage 2: Statistical Analysis
```python
def calculate_operator_bandwidth_reliability(operator_relays, bandwidth_data, periods):
    """Calculate comprehensive bandwidth metrics"""
    # Calculations:
    # - Time-weighted averages per period
    # - Coefficient of variation for stability
    # - Peak vs average ratios
    # - Month-over-month growth trends
```

#### Stage 3: Network Context
```python
def calculate_network_position_percentiles(operator_bandwidth, network_percentiles):
    """Determine network ranking position"""
    # Input: Operator's 6-month average bandwidth
    # Process: Compare against network-wide percentile distribution
    # Output: Percentile ranking (0-100)
```

#### Stage 4: Flag Analysis
```python
def process_operator_flag_bandwidth_reliability(operator_relays, bandwidth_data, flag_statistics):
    """Generate flag-specific bandwidth analysis"""
    # Process: Calculate per-flag bandwidth for operator
    # Compare: Against network averages for each flag type
    # Output: Color-coded performance indicators
```

### Data Storage Architecture

#### Network-Wide Statistics
```python
# Stored in RelaySet instance
self.network_bandwidth_percentiles = {
    'percentile_10': float,   # 10th percentile bandwidth
    'percentile_25': float,   # 25th percentile bandwidth  
    'percentile_50': float,   # Median bandwidth
    'percentile_75': float,   # 75th percentile bandwidth
    'percentile_90': float,   # 90th percentile bandwidth
    'count': int             # Number of operators analyzed
}

self.network_flag_bandwidth_statistics = {
    'Running': {
        '1_month': {'mean': float, 'median': float, 'percentile_10': float, 'percentile_90': float},
        '6_months': {...},
        '1_year': {...},
        '5_years': {...}
    },
    'Guard': {...},
    'Exit': {...},
    # ... for all flag types
}
```

#### Operator-Specific Data
```python
# Returned by calculate_operator_bandwidth_reliability()
{
    'overall_bandwidth': {
        '1_month': {'average': float, 'data_points': int, 'relay_count': int},
        '6_months': {...},
        '1_year': {...},
        '5_years': {...}
    },
    'bandwidth_stability': {
        '6_months': {'coefficient_variation': float, 'stability_rating': str}
    },
    'peak_analysis': {
        'historical_peak': float,
        'current_utilization': float,
        'peak_period': str
    },
    'growth_trend': {
        'month_over_month_change': float,
        'trend_direction': str,  # 'increasing', 'decreasing', 'stable'
        'trend_icon': str        # '📈', '📉', '➡️'
    }
}
```

## 🔧 Implementation Plan

### 📋 Proposed Implementation Components

1. **Core Calculation Functions** (`bandwidth_utils.py`)
   - `calculate_operator_bandwidth_reliability()` - Comprehensive metrics calculation
   - `calculate_network_position_percentiles()` - Network ranking determination
   - `process_operator_flag_bandwidth_reliability()` - Flag-specific analysis
   - `calculate_bandwidth_statistical_outliers()` - Outlier detection

2. **Relay Processing Integration** (`relays.py`)
   - `_reprocess_bandwidth_data()` - Network statistics calculation
   - Enhanced `_calculate_operator_reliability()` - Combined uptime/bandwidth metrics
   - `_compute_contact_flag_bandwidth_analysis()` - Flag bandwidth processing
   - Enhanced `_compute_contact_display_data()` - Data formatting for templates

3. **Template Integration** (`contact.html`)
   - Bandwidth Reliability section - Primary and secondary metrics display
   - Flag Bandwidth Reliability section - Flag-specific capacity analysis
   - CSS styling integration - Consistent with existing patterns

4. **Coordinator Integration** (`coordinator.py`)
   - Bandwidth processing trigger alongside uptime processing

### 📊 Estimated Implementation Scope

- **Estimated New Lines**: ~400 lines of Python + ~80 lines of HTML/CSS
- **Files to Modify**: 4 files
- **Functions to Add**: 8 new functions
- **Functions to Enhance**: 4 existing functions
- **Template Sections to Add**: 2 major sections

### 🛡️ Proposed Error Handling & Edge Cases

1. **Missing Bandwidth Data**: Would implement graceful degradation with "No data available" messages
2. **Insufficient Data Points**: Would establish minimum thresholds for statistical calculations
3. **Network Calculation Failures**: Would use try-catch blocks with operator skipping
4. **Template Rendering**: Would implement conditional rendering based on data availability
5. **Performance Optimization**: Would use single-pass calculations and cached network statistics

## 🚀 Proposed Implementation & Testing Strategy

### Validation Approach

1. **Syntax Verification**: Would ensure all Python files pass `python3 -m py_compile`
2. **Pattern Consistency**: Would follow existing uptime reliability patterns
3. **Performance Impact**: Would minimize impact by reusing existing functions and data
4. **UI Integration**: Would match existing styling and responsive design

### Implementation Readiness Checklist

- 📋 **Code Implementation**: Functions to be implemented and tested
- 📋 **Error Handling**: Comprehensive try-catch blocks to be added
- 📋 **Performance Optimization**: Single-pass calculations and efficient data structures to be designed
- 📋 **UI Responsive**: Template sections to be designed for different screen sizes
- 📋 **Documentation**: Comprehensive inline comments and docstrings to be written
- 📋 **Backwards Compatibility**: No breaking changes to existing functionality

### Proposed Testing Approach

```bash
# Recommended testing commands for implementation:
python3 allium/allium.py -p --out /tmp/test_before  # Before implementation
python3 allium/allium.py -p --out /tmp/test_after   # After implementation

# Would compare outputs for operators like:
# - 1aeo (high-bandwidth operator)
# - nothingothide.nl (mid-range operator) 
# - Verify no regressions except new content
```

## 📋 Future Enhancements

### Phase 2 Potential Features

1. **Historical Trending**: Bandwidth graphs and trend visualization
2. **Anomaly Detection**: Alert indicators for unusual bandwidth patterns
3. **Comparative Analysis**: Operator vs operator bandwidth comparisons
4. **Geographic Analysis**: Bandwidth performance by relay location
5. **Exit Policy Impact**: Bandwidth analysis based on exit policy restrictions

### Integration Opportunities

1. **Network Health Dashboard**: Aggregate bandwidth metrics for network overview
2. **API Endpoints**: Expose bandwidth reliability data via REST API
3. **Real-time Monitoring**: Live bandwidth tracking and alerts
4. **Historical Data Export**: CSV/JSON export for external analysis

## 📝 Conclusion

This proposal outlines comprehensive bandwidth reliability metrics that would complement the existing uptime reliability system. The proposed solution would follow established code patterns and provide valuable insights for Tor relay operators to understand their bandwidth performance, network positioning, and growth trends.

The proposed implementation would achieve all stated objectives:
- 📋 Comprehensive bandwidth reliability metrics for contact pages
- 📋 Flag-specific bandwidth capacity analysis design
- 📋 Seamless integration plan with existing uptime processing workflow
- 📋 Consistent UI styling specification matching existing reliability sections

**This proposal provides a detailed roadmap for future implementation when development resources become available.**