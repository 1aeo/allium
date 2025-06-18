# Network Uptime Display Updates

## Changes Implemented

### A) Label Update
- **Changed**: "Avg" → "Median" in Network Uptime (6mo) display
- **Rationale**: The value shown is actually the median (50th percentile), not arithmetic mean
- **Technical**: More accurate labeling of the robust statistical measure used

### B) Color Coding Implementation

Color coding for operator position matches the operator intelligence section styling:

#### Color Scheme
- **🟢 Green (`#2e7d2e`)**: Above median performance 
  - Matches "All" in version compliance section
  - Indicates good network reliability performance
  
- **🟡 Dark Yellow (`#cc9900`)**: Below median but above 5th percentile
  - Matches "Okay" in geographic/network diversity ratings  
  - Indicates acceptable but below-average performance
  
- **🔴 Red (`#c82333`)**: Below 5th percentile
  - Matches "Poor" in geographic/network diversity ratings
  - Indicates concerning reliability performance

## Example Outputs

### High Performer (Above Median)
```html
<strong>Network Uptime (6mo):</strong> 5th Pct: 85%, 25th Pct: 95%, Median: 98%, 
<span style="color: #2e7d2e; font-weight: bold;">Operator: 99%</span>, 75th Pct: 99%
```

### Average Performer (Below Median)  
```html
<strong>Network Uptime (6mo):</strong> 5th Pct: 85%, 25th Pct: 95%, 
<span style="color: #cc9900; font-weight: bold;">Operator: 97%</span>, Median: 98%
```

### Poor Performer (Below 5th Percentile)
```html
<strong>Network Uptime (6mo):</strong> 
<span style="color: #c82333; font-weight: bold;">Operator: 80%</span>, 5th Pct: 85%
```

## Technical Implementation

### Modified Function
- **File**: `allium/lib/uptime_utils.py`
- **Function**: `format_network_percentiles_display()`

### Key Changes
1. **Label Update**: `f"Avg: {network_avg:.0f}%"` → `f"Median: {network_median:.0f}%"`

2. **Color Logic**: Added percentile-based color determination:
   ```python
   if percentile_range == '<5th':
       operator_color = '#c82333'  # Red
   elif operator_uptime >= percentiles.get('50th', 0):
       operator_color = '#2e7d2e'  # Green  
   else:
       operator_color = '#cc9900'  # Dark yellow
   ```

3. **Formatted Output**: Color-coded operator entry with bold styling:
   ```python
   operator_entry = f'<span style="color: {operator_color}; font-weight: bold;">Operator: {operator_uptime:.0f}%</span>'
   ```

## Validation Results

✅ **All Tests Passed**
- "Avg" successfully renamed to "Median"
- Color coding correctly applied:
  - Above median: Green `#2e7d2e` ✅
  - Below median: Dark yellow `#cc9900` ✅  
  - Below 5th percentile: Red `#c82333` ✅

## Visual Consistency

The color scheme maintains visual consistency with the operator intelligence section:

| Intelligence Section | Network Uptime | Color Code |
|---------------------|----------------|------------|
| "All" (version compliance) | Above median | `#2e7d2e` (Green) |
| "Okay" (diversity ratings) | Below median | `#cc9900` (Dark yellow) |
| "Poor" (diversity ratings) | Below 5th percentile | `#c82333` (Red) |

## Impact

- **Accuracy**: Correct labeling of median vs. average
- **Visual Clarity**: Color coding provides immediate performance assessment
- **Consistency**: Matches existing operator intelligence styling
- **User Experience**: Quick visual identification of operator reliability performance

---

**Status**: ✅ Implemented and validated - Network Uptime display now shows "Median" with color-coded operator positions matching the operator intelligence section.