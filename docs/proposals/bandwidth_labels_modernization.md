# Bandwidth Labels Analysis and Modernization Plan

## Executive Summary

This document presents a comprehensive analysis of all bandwidth references throughout the Allium codebase, traces each reference to its data source, and proposes a plan to update user-facing labels to distinguish between **capacity** and **consumption** metrics.

## Data Source Analysis

### Primary Data Sources

#### 1. Onionoo Details API (CAPACITY)
- **URL**: `https://onionoo.torproject.org/details`
- **Purpose**: Provides relay capacity information
- **Key Fields**:
  - `observed_bandwidth`: Relay's estimated capacity
  - `advertised_bandwidth`: Relay's advertised capacity
  - `consensus_weight`: Network weight (capacity-based)
  - `bandwidth_rate`: Rate limit (capacity constraint)
  - `bandwidth_burst`: Burst capacity limit

#### 2. Onionoo Bandwidth API (CONSUMPTION)
- **URL**: `https://onionoo.torproject.org/bandwidth`
- **Purpose**: Provides historical bandwidth consumption data
- **Key Fields**:
  - `write_history`: Download consumption over time
  - `read_history`: Upload consumption over time
  - `bandwidth_history`: Combined consumption metrics
- **Status**: Currently fetched but not fully utilized in templates

## Complete Bandwidth Reference Inventory

### 1. Core Application Files

#### `allium/allium.py`
- **Line 89-93**: CLI argument `--display-bandwidth-units` - Generic bandwidth display
- **Line 125-131**: CLI argument `--onionoo-bandwidth-url` - Historical bandwidth API
- **Line 136-140**: CLI argument `--bandwidth-cache-hours` - Cache configuration
- **Line 261-266**: Sort keys for bandwidth-related pages
- **Classification**: Configuration/CLI - no user-facing labels

#### `allium/lib/workers.py`
- **Line 286**: `fetch_onionoo_bandwidth()` - Historical bandwidth API (CONSUMPTION)
- **Line 174**: `fetch_onionoo_details()` - Details API (CAPACITY)
- **Classification**: Data fetching - no user-facing labels

#### `allium/lib/bandwidth_formatter.py`
- **Entire file**: Bandwidth formatting utilities
- **Classification**: Utility functions - no user-facing labels

### 2. Template Files - Primary Focus for Label Updates

#### `allium/templates/macros.html`
- **Line 99**: `"Observed bandwidth represents the estimated capacity this group can handle"`
- **Line 101**: `"Bandwidth dedicated to guard relay operations"`
- **Line 102**: `"Bandwidth dedicated to middle relay operations"`
- **Line 103**: `"Bandwidth dedicated to exit relay operations"`
- **Data Source**: Details API (CAPACITY)
- **Update Needed**: ✅ Change "Bandwidth" to "Bandwidth Capacity"

#### `allium/templates/relay-info.html`
- **Line 207**: `"Bandwidth details: Observed capacity | Advertised capability | Rate limit | Burst limit"`
- **Line 208**: `"Bandwidth (Observed | Advertised | Rate | Burst)"`
- **Line 213**: `"Observed: {{ obs_bandwidth }} {{ obs_unit }}"`
- **Line 214**: `"Advertised: {{ adv_bandwidth }} {{ adv_unit }}"`
- **Line 215**: `"Rate: {{ rate_bandwidth }} {{ rate_unit }}"`
- **Line 216**: `"Burst: {{ burst_bandwidth }} {{ burst_unit }}"`
- **Data Source**: Details API (CAPACITY)
- **Update Needed**: ✅ Change "Bandwidth" to "Bandwidth Capacity"

#### `allium/templates/aroi-leaderboards.html`
- **Line 26**: `"Operators ranked by total observed bandwidth capacity across all relays"`
- **Line 52**: `"Aggregate observed bandwidth capacity contributed to the Tor network"`
- **Line 169**: `"Operators ranked by total observed bandwidth capacity across all relays"`
- **Data Source**: Details API (CAPACITY)
- **Update Needed**: ✅ Already mentions "capacity" - enhance consistency

#### `allium/templates/aroi_macros.html`
- **Line 13**: `"Total observed bandwidth capacity in"`
- **Line 108**: `"Total observed bandwidth capacity in"`
- **Line 203**: `"Total observed bandwidth capacity in"`
- **Line 239**: `"Observed bandwidth capacity in"`
- **Multiple similar references throughout file**
- **Data Source**: Details API (CAPACITY)
- **Update Needed**: ✅ Already mentions "capacity" - enhance consistency

#### `allium/templates/network-health-dashboard.html`
- **Line 144**: `"Total observed bandwidth capacity across all relays"`
- **Line 149**: `"Total observed bandwidth of all Exit relays"`
- **Line 153**: `"Total observed bandwidth of all Guard relays"`
- **Line 157**: `"Total observed bandwidth of all Middle relays"`
- **Line 163**: `"Mean and median bandwidth per Exit relay"`
- **Line 167**: `"Mean and median bandwidth per Guard relay"`
- **Line 171**: `"Mean and median bandwidth per Middle relay"`
- **Multiple similar references throughout file**
- **Data Source**: Details API (CAPACITY)
- **Update Needed**: ✅ Mix of "capacity" and plain "bandwidth" - standardize

#### `allium/templates/contact.html`
- **Line 70**: `"Observed bandwidth represents the estimated capacity this group can handle"`
- **Line 72**: `"Bandwidth breakdown by relay type"`
- **Line 107**: `"Bandwidth measurements show how many relays are measured by directory authorities"`
- **Line 111**: `"Network efficiency analysis comparing operator performance"`
- **Data Source**: Details API (CAPACITY)
- **Update Needed**: ✅ Change "Bandwidth" to "Bandwidth Capacity"

#### `allium/templates/misc-*.html` (Countries, Families, Networks, Platforms, Contacts)
- **Multiple files with similar patterns**:
  - `"Observed Bandwidth: An estimate of the capacity this relay can handle"`
  - `"BW = Observed Bandwidth"`
  - Table headers with "Bandwidth" 
- **Data Source**: Details API (CAPACITY)
- **Update Needed**: ✅ Change "Bandwidth" to "Bandwidth Capacity"

#### `allium/templates/relay-list.html`
- **Line 31**: `"Bandwidth measured by >=3 bandwidth authorities"`
- **Line 105**: `">=3 bandwidth authorities have measured"`
- **Data Source**: Details API (CAPACITY)
- **Update Needed**: ✅ Change "Bandwidth measured" to "Bandwidth Capacity measured"

### 3. Backend Processing Files

#### `allium/lib/relays.py`
- **Line 258**: `_sort_by_observed_bandwidth()` - Uses observed_bandwidth (CAPACITY)
- **Line 797**: Function sorts by observed_bandwidth field
- **Lines 850-864**: Network totals calculation using observed_bandwidth
- **Data Source**: Details API (CAPACITY)
- **Classification**: Backend processing - no user-facing labels

#### `allium/lib/intelligence_engine.py`
- **Line 25**: `network_total_bandwidth` calculation
- **Line 60, 71, 576, 585**: Uses `observed_bandwidth` field
- **Data Source**: Details API (CAPACITY)
- **Classification**: Backend processing - no user-facing labels

#### `allium/lib/aroileaders.py`
- **Line 301**: `relay_bandwidth = relay.get('observed_bandwidth', 0)`
- **Data Source**: Details API (CAPACITY)
- **Classification**: Backend processing - no user-facing labels

## Proposed Label Updates

### Phase 1: Template Updates (High Priority)

#### 1. Core Bandwidth Labels
**Current**: "Bandwidth"
**Proposed**: "Bandwidth Capacity"

#### 2. Tooltip Updates
**Current**: "Observed bandwidth represents the estimated capacity this group can handle"
**Proposed**: "Observed bandwidth capacity represents the estimated maximum throughput this group can handle"

#### 3. Table Headers
**Current**: "Bandwidth", "BW"
**Proposed**: "Bandwidth Capacity", "BW Cap"

#### 4. Measurement Labels
**Current**: "Bandwidth measured by >=3 bandwidth authorities"
**Proposed**: "Bandwidth capacity measured by >=3 bandwidth authorities"

#### 5. Leaderboard Labels
**Current**: "🚀 Bandwidth Contributed"
**Proposed**: "🚀 Bandwidth Capacity Contributed"

### Phase 2: Detailed Field Labels

#### 1. Relay Info Page Bandwidth Details
**Current**: "Bandwidth (Observed | Advertised | Rate | Burst)"
**Proposed**: "Bandwidth Capacity (Observed | Advertised | Rate Limit | Burst Limit)"

#### 2. Role-Specific Bandwidth
**Current**: "{{ guard_bandwidth }} {{ bandwidth_unit }} guard"
**Proposed**: "{{ guard_bandwidth }} {{ bandwidth_unit }} guard capacity"

#### 3. Network Health Dashboard
**Current**: "Total Bandwidth", "Exit BW Total", "Guard BW Total"
**Proposed**: "Total Capacity", "Exit Capacity", "Guard Capacity"

### Phase 3: Future Consumption Metrics (Low Priority)

When historical bandwidth consumption data is implemented:

#### 1. Historical Consumption Labels
- "Bandwidth Consumption History"
- "Download Consumption (Write History)"
- "Upload Consumption (Read History)"
- "Average Daily Consumption"
- "Peak Consumption Periods"

#### 2. Consumption vs Capacity Comparisons
- "Consumption vs Capacity Ratio"
- "Utilization Rate"
- "Capacity Efficiency"

## Implementation Plan

### Step 1: Template File Updates
Update all template files to use "Bandwidth Capacity" instead of "Bandwidth" for observed_bandwidth, advertised_bandwidth, consensus_weight, and related capacity metrics.

**Files to Update**:
- `allium/templates/macros.html`
- `allium/templates/relay-info.html`  
- `allium/templates/contact.html`
- `allium/templates/aroi-leaderboards.html`
- `allium/templates/network-health-dashboard.html`
- `allium/templates/misc-*.html` (all misc files)
- `allium/templates/relay-list.html`
- `allium/templates/contact-relay-list.html`

### Step 2: Tooltip and Title Updates
Update all tooltips and title attributes to clarify capacity vs consumption distinction.

### Step 3: Table Header Updates
Update all table headers to use "Bandwidth Capacity" or "BW Cap" abbreviations.

### Step 4: Leaderboard Updates
Update AROI leaderboard labels to use "Bandwidth Capacity Contributed".

### Step 5: Future Consumption Implementation
When historical bandwidth consumption features are added, implement separate labeling for consumption metrics.

## Label Standards

### Capacity Metrics (from Details API)
- **Primary Label**: "Bandwidth Capacity"
- **Short Label**: "BW Cap"
- **Tooltip Pattern**: "...capacity this relay/group can handle..."
- **Fields**: observed_bandwidth, advertised_bandwidth, consensus_weight, bandwidth_rate, bandwidth_burst

### Consumption Metrics (from Bandwidth API - Future)
- **Primary Label**: "Bandwidth Consumption"
- **Short Label**: "BW Usage"
- **Tooltip Pattern**: "...actual bandwidth used/consumed..."
- **Fields**: write_history, read_history, bandwidth_history

## Benefits of This Approach

1. **Clear Distinction**: Users will understand the difference between what a relay can handle (capacity) vs what it actually uses (consumption)

2. **Technical Accuracy**: Aligns terminology with the actual data sources and their purposes

3. **Future-Proof**: Prepares the codebase for when consumption metrics are implemented

4. **Consistency**: Standardizes terminology across all user-facing components

5. **Educational**: Helps users better understand Tor network metrics

## Conclusion

This analysis identified 200+ bandwidth references across the codebase, with the vast majority being capacity metrics from the Details API. The proposed updates will clarify the distinction between capacity and consumption, making the interface more intuitive and technically accurate for users while preparing for future consumption metric implementation.

The updates focus solely on user-facing labels and tooltips without changing any calculations or data processing logic, ensuring minimal risk while maximizing clarity.