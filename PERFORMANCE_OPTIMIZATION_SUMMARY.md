# Network Uptime Percentiles Performance Optimization

## Problem Identified

The network uptime percentiles feature introduced a **10x performance degradation** in contact page generation due to inefficient calculation strategy.

### Root Cause
- `calculate_network_uptime_percentiles()` was called **for every single contact page**
- With 8000+ network relays and 6 percentile calculations per contact
- **Identical calculations** were repeated thousands of times
- Complexity: O(N × M) where N = contacts, M = network relays

### Performance Impact
- **Before**: Each contact page took ~10x longer to generate
- **Mathematical impossibility**: Calculating identical network data for each contact

## Solution Implemented

### Optimization Strategy
1. **Calculate network percentiles ONCE** when uptime data is processed
2. **Cache the result** as `self.network_uptime_percentiles`
3. **Reuse cached data** for all contact pages

### Code Changes

#### 1. Enhanced `_reprocess_uptime_data()` (allium/lib/relays.py)
```python
# PERFORMANCE OPTIMIZATION: Calculate network-wide uptime percentiles ONCE for all contacts
if hasattr(self, 'uptime_data') and self.uptime_data:
    from .uptime_utils import calculate_network_uptime_percentiles
    self._log_progress("Calculating network uptime percentiles (6-month period)...")
    self.network_uptime_percentiles = calculate_network_uptime_percentiles(self.uptime_data, '6_months')
    if self.network_uptime_percentiles:
        total_relays = self.network_uptime_percentiles.get('total_relays', 0)
        self._log_progress(f"Network percentiles calculated: {total_relays:,} relays analyzed")
```

#### 2. Optimized `_calculate_operator_reliability()` (allium/lib/relays.py)
```python
# PERFORMANCE OPTIMIZATION: Use cached network percentiles instead of recalculating
# Network percentiles are calculated once in _reprocess_uptime_data for all contacts
if hasattr(self, 'network_uptime_percentiles') and self.network_uptime_percentiles:
    reliability_stats['network_uptime_percentiles'] = self.network_uptime_percentiles
```

### Removed Inefficiency
- **Removed**: `calculate_network_uptime_percentiles(self.uptime_data, '6_months')` from contact loop
- **Added**: Single calculation with cached reuse

## Performance Results

### Validation Test Results
```
⏱️  OLD approach: 0.702s (50 calculations)
⚡ NEW approach: 0.014s (1 calculation + 50 cache hits)
🎯 Performance improvement: 49.7x faster
```

### Expected Production Impact
- **Complexity reduced**: O(N × M) → O(M)
- **Expected improvement**: 10-100x faster contact page generation
- **Memory efficiency**: Single percentiles calculation instead of thousands
- **Computational savings**: ~99% reduction in redundant calculations

## Technical Benefits

### 1. Mathematical Consistency
- Network percentiles are identical for all contacts
- Single calculation ensures consistent results
- Eliminates potential floating-point variations

### 2. Resource Efficiency
- **CPU**: Massive reduction in redundant statistical calculations
- **Memory**: Single percentiles object instead of thousands
- **I/O**: No repeated processing of uptime data

### 3. Maintainability
- Centralized percentiles calculation
- Clear separation of concerns
- Easier debugging and validation

## Implementation Details

### Execution Flow
1. **Data Loading**: Coordinator loads uptime data
2. **Processing**: `_reprocess_uptime_data()` calculates network percentiles once
3. **Caching**: Result stored in `self.network_uptime_percentiles`
4. **Contact Pages**: Each contact reuses cached percentiles
5. **Display**: Network percentiles formatted consistently

### Error Handling
- Graceful fallback if percentiles calculation fails
- Maintains existing functionality if uptime data unavailable
- Proper logging for debugging

## Validation Confirmed

✅ **All Tests Passed (3/3)**
- Network percentiles caching works correctly
- 49.7x performance improvement measured
- Mathematical consistency maintained
- Operator position calculations accurate

## Future Considerations

### Additional Optimization Opportunities
1. **Relay uptime caching**: Cache individual relay uptime calculations
2. **Statistical outlier caching**: Cache outlier calculations per period
3. **Memory optimization**: Consider lazy loading for large datasets

### Monitoring
- Add performance metrics to track page generation times
- Monitor memory usage with large contact datasets
- Log percentiles calculation time for debugging

---

**Impact**: Resolved 10x performance degradation in contact page generation while maintaining all existing functionality and mathematical accuracy.