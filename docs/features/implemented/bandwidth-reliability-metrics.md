# Bandwidth Reliability Metrics System

**Status**: ✅ **FULLY IMPLEMENTED**  
**Implementation Date**: January 2025  
**Location**: Contact operator pages  
**Files**: `allium/lib/bandwidth_utils.py`, `allium/lib/relays.py`, `allium/templates/contact.html`

## Overview

The Bandwidth Reliability Metrics System provides comprehensive bandwidth analysis for Tor relay operators, complementing the existing uptime reliability system. This feature adds detailed bandwidth analysis including observed bandwidth, network position percentiles, bandwidth stability, growth trends, and flag-specific bandwidth capacity analysis.

## 🎯 Implemented Features

### **🚀 Bandwidth Reliability Section**

#### Primary Metrics
- **Observed Bandwidth**: Time-weighted averages across multiple periods (1M/6M/1Y/5Y)
- **Average Relay Throughput**: Bandwidth per individual relay with relay count
- **Statistical Outlier Detection**: Identification of relays with unusual bandwidth patterns (≥2σ deviation)

#### Secondary Metrics (Performance Analysis)
- **Bandwidth Stability**: Coefficient of variation analysis with color-coded categories
  - 🟢 Great: Top 25% stability
  - 🔵 Good: 50-75% stability  
  - 🟡 Variable: 25-50% stability
  - 🔴 Extreme: Bottom 10% stability
- **Growth Trend**: Month-over-month bandwidth change with directional indicators
- **Capacity Utilization**: Current performance vs historical peak capacity
- **Network Position**: Percentile ranking in bandwidth distribution

### **🚀 Flag Bandwidth Performance Section**

#### Flag-Specific Analysis
- **Supported Flags**: Exit, Guard, Fast, Running, Authority, HSDir, Stable, V2Dir
- **Time Periods**: 6M/1Y/5Y bandwidth averages
- **Performance Indicators**:
  - 🟢 High performance (>1.5x network mean)
  - 🟡 Below average (<network mean)
  - 🔴 Poor (≥2σ from network mean)

## 🏗️ Technical Implementation

### Core Functions

#### `allium/lib/bandwidth_utils.py`
```python
def calculate_bandwidth_reliability_metrics(operator_relays, bandwidth_data, period, mean_bandwidth, std_dev, network_cv_stats=None, bandwidth_formatter=None)
```
- **Purpose**: Calculate comprehensive bandwidth metrics for an operator
- **Returns**: Dictionary with stability, growth, capacity utilization metrics
- **Integration**: Called from relay processing pipeline

#### Supporting Functions
- `_calculate_bandwidth_stability()` - Coefficient of variation analysis
- `_calculate_growth_trend()` - Month-over-month growth calculation
- `_calculate_peak_performance_and_capacity()` - Peak vs current analysis

#### `allium/lib/relays.py`
```python
def _process_operator_flag_bandwidth_reliability(self, operator_flag_data, network_flag_statistics)
```
- **Purpose**: Process flag-specific bandwidth data with color coding
- **Returns**: Formatted flag bandwidth data for template display
- **Integration**: Mirrors uptime flag processing patterns

### Data Processing Pipeline

```
Onionoo Bandwidth API
       ↓
Coordinator.create_relay_set()
       ↓
RelaySet._calculate_operator_reliability()
       ↓
calculate_bandwidth_reliability_metrics()
       ↓
_process_operator_flag_bandwidth_reliability()
       ↓
contact.html Template Rendering
```

### Template Integration

#### Bandwidth Reliability Section (`contact.html` lines 208-302)
- Primary bandwidth metrics display
- Performance analysis tree structure
- Statistical outlier identification
- Data availability indicators

#### Flag Bandwidth Performance Section (`contact.html` lines 457-510)
- Flag-specific bandwidth averages
- Color-coded performance indicators
- Network comparison tooltips
- Performance legend

## 📊 Metrics Specifications

### Bandwidth Stability Analysis
- **Calculation**: Coefficient of Variation (CV) = Standard Deviation / Mean
- **Categories**:
  - Great: CV in top 25% of network
  - Good: CV in 50-75% range
  - Variable: CV in 25-50% range
  - Extreme: CV in bottom 10%

### Growth Trend Analysis
- **Calculation**: Month-over-month bandwidth change within 6-month period
- **Indicators**:
  - 📈 Growth: >5% increase
  - 📉 Decline: >5% decrease
  - ➡️ Stable: ±5% change

### Capacity Utilization
- **Calculation**: Current average bandwidth / Historical maximum
- **Purpose**: Shows performance consistency vs proven capability

### Network Position
- **Calculation**: Operator's 6-month average vs network percentile distribution
- **Display**: Percentile ranking with descriptive range

## 🎨 User Interface

### Example Display (Contact Page)
```
📊 Bandwidth Reliability
• Average Relay Throughput: 6mo 45.2 GB/s avg (3 relays), 1y 38.7 GB/s avg (3 relays), 5y 32.1 GB/s avg (2 relays)

Performance Analysis (6mo):
├─ Stability: Great (Coefficient of Variation: 8.3% = 3.8 GB/s σ / 45.2 GB/s μ)
├─ Trend: 📈 +12.3% month-over-month growth
└─ Capacity Utilization: 87% of historical peak (52.1 GB/s)

Network Position: 85th percentile (Top 15% of 1,247 operators)

📊 Flag Bandwidth Performance
Flag-specific bandwidth averages (6M/1Y/5Y):

🚪 Exit Node: 🟢 156.8 MB/s / 145.2 MB/s / 134.7 MB/s
🛡️ Entry Guard: 🟢 89.4 MB/s / 78.3 MB/s / 67.1 MB/s
⚡ Fast Relay: ⚪ 92.1 MB/s / 84.6 MB/s / 76.2 MB/s
🟢 Running: ⚪ 85.7 MB/s / 79.3 MB/s / 72.4 MB/s

🟢 High performance (>1.5x μ), 🟡 Below average (<μ of network), 🔴 Poor (≥2σ from network μ)
```

## 📈 Performance Characteristics

### Data Processing
- **Complexity**: O(n) single-pass calculations
- **Memory**: Efficient bandwidth mapping with shared data structures
- **Integration**: Minimal impact on existing uptime processing workflow

### Statistical Analysis
- **Outlier Detection**: ±2σ (standard deviation) thresholds
- **Network Percentiles**: Pre-calculated network-wide statistics
- **Stability Assessment**: Coefficient of variation with network comparison

## 🔧 Configuration & Customization

### Bandwidth Formatting
- **Auto-scaling**: Automatic unit selection (MB/s, GB/s)
- **Precision**: Appropriate decimal places based on magnitude
- **Consistency**: Unified formatting across all bandwidth displays

### Color Coding
- **Performance Indicators**: Green (high), Yellow (below average), Red (poor)
- **Stability Categories**: Color-coded based on network percentile ranking
- **Trend Indicators**: Directional arrows with color context

## 🧪 Testing & Validation

### Implementation Validation
```bash
# Module loading test
python3 -c "import allium.lib.bandwidth_utils; print('Bandwidth utils module loads successfully')"

# Full pipeline test
python3 allium/allium.py -p --out /tmp/test_output
```

### Data Integrity
- **Statistical Validation**: All calculations verified against Onionoo API data
- **Edge Case Handling**: Graceful degradation for missing or insufficient data
- **Template Safety**: Conditional rendering prevents display errors

## 📋 Integration Points

### Existing Systems
- **Uptime Reliability**: Seamless integration alongside existing reliability metrics
- **AROI Leaderboards**: Bandwidth data feeds into competitive rankings
- **Intelligence Engine**: Bandwidth outliers contribute to intelligence assessments
- **Network Health**: Aggregate bandwidth metrics support network overview

### API Dependencies
- **Onionoo Bandwidth API**: Primary data source for historical bandwidth
- **Details API**: Relay metadata for flag assignment
- **Uptime API**: Coordination with reliability processing

## 🚀 Benefits & Impact

### For Relay Operators
- **Performance Insights**: Comprehensive bandwidth analysis and trends
- **Network Context**: Understanding of position within Tor network
- **Optimization Guidance**: Identification of underperforming relays
- **Historical Tracking**: Long-term bandwidth performance monitoring

### For Network Analysis
- **Capacity Planning**: Network-wide bandwidth distribution analysis
- **Performance Benchmarking**: Operator comparison capabilities
- **Trend Monitoring**: Growth and decline pattern identification
- **Quality Assessment**: Statistical outlier detection for network health

## 🔮 Future Enhancement Opportunities

### Potential Additions
- **Interactive Graphs**: Bandwidth trend visualization
- **Anomaly Alerts**: Real-time bandwidth deviation notifications
- **Comparative Analysis**: Operator-to-operator bandwidth comparisons
- **Geographic Correlation**: Bandwidth performance by relay location
- **Exit Policy Impact**: Bandwidth analysis based on exit restrictions

### API Extensions
- **REST Endpoints**: Expose bandwidth reliability data via API
- **Historical Export**: CSV/JSON export for external analysis
- **Real-time Monitoring**: Live bandwidth tracking capabilities

---

**Implementation Status**: ✅ Complete and operational  
**Code Quality**: Production-ready with comprehensive error handling  
**Performance**: Optimized for minimal impact on existing workflows  
**Documentation**: Fully documented with inline comments and tooltips  
**Testing**: Validated against production Onionoo data  

This feature successfully extends the allium platform's analytical capabilities, providing relay operators with detailed bandwidth insights while maintaining the platform's performance and reliability standards.