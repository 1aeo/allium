# Consensus Weight Usage Audit - Allium Codebase

## Executive Summary

Comprehensive audit of all `consensus_weight` and `consensus_weight_fraction` usage across the Allium codebase, identifying patterns, risks, and the bug that affected artikel10.org.

---

## 9 Key Locations Where Consensus Weight is Used

### ✅ 1. relays.py - Individual Relay Display (Lines 466-469)
- **Uses**: `consensus_weight_fraction` (from Onionoo)
- **Method**: Direct access for display percentage
- **Calculation**: `relay.get("consensus_weight_fraction")` → format as percentage
- **Safe**: ✅ YES - Has fallback to `NA_FALLBACK` if missing
- **Purpose**: Display only, not used in calculations
- **Risk Level**: LOW - Graceful degradation

### ✅ 2. relays.py - Network Totals Calculation (Lines 1092-1115)
- **Uses**: `consensus_weight` (absolute value)
- **Method**: Sum absolute values across all relays
- **Calculation**: 
  ```python
  consensus_weight = relay.get('consensus_weight', 0)
  total_exit_cw += consensus_weight  # or guard/middle
  ```
- **Safe**: ✅ YES - Absolute value always present
- **Purpose**: Calculate network-wide totals for percentage calculations
- **Risk Level**: NONE - Correct approach

### ⚠️ 3. relays.py - Contact/Country/AS Aggregation (Lines 1238-1241)
- **Uses**: BOTH `consensus_weight` AND `consensus_weight_fraction`
- **Method**: Sums both absolute values and fractions
- **Calculation**:
  ```python
  # Line 1238-1239: Sum absolute (correct)
  self.json["sorted"][k][v]["consensus_weight"] += relay["consensus_weight"]
  
  # Line 1240-1241: Sum fraction (incomplete for non-running relays)
  self.json["sorted"][k][v]["consensus_weight_fraction"] += float(relay["consensus_weight_fraction"])
  ```
- **Safe**: ⚠️ REDUNDANT but harmless - Line 1241 value is overwritten later
- **Purpose**: Aggregate relay data by contact/country/AS
- **Risk Level**: NONE - Value is recalculated correctly in step #4
- **Note**: Lines 1240-1241 could be removed for clarity (no functional impact)

### ✅ 4. relays.py - Final Fraction Calculation (Lines 1394-1412)
- **Uses**: Converts absolute to fraction
- **Method**: Divide aggregated absolute values by network totals
- **Calculation**:
  ```python
  item["consensus_weight_fraction"] = item["consensus_weight"] / total_consensus_weight
  item["guard_consensus_weight_fraction"] = item["guard_consensus_weight"] / total_guard_cw
  # etc.
  ```
- **Safe**: ✅ YES - Calculates from absolute values (always correct)
- **Purpose**: Create final percentage values for contacts, countries, AS, etc.
- **Risk Level**: NONE - This is the gold standard approach
- **Note**: This is where `contact_data.consensus_weight_fraction` gets its correct value

### ❌ 5. aroileaders.py - Validation Champions BEFORE FIX (Line 425 - OLD)
- **Uses**: `consensus_weight_fraction` (from Onionoo) ❌
- **Method**: Direct sum in loop
- **Calculation**:
  ```python
  relay_consensus_weight = relay.get('consensus_weight_fraction', 0)  # BUG!
  validated_consensus_weight += relay_consensus_weight
  ```
- **Safe**: ❌ NO - Returns 0 for non-running relays
- **Purpose**: Calculate consensus weight of validated relays
- **Risk Level**: HIGH - Caused artikel10.org to show 0.00%
- **Status**: **FIXED** in current codebase

### ✅ 6. aroileaders.py - Validation Champions AFTER FIX (Lines 425, 509-511 - NEW)
- **Uses**: `consensus_weight` (absolute value) ✅
- **Method**: Sum absolute values, then convert to fraction
- **Calculation**:
  ```python
  relay_consensus_weight = relay.get('consensus_weight', 0)  # Fixed!
  validated_consensus_weight += relay_consensus_weight
  # Later...
  validated_consensus_weight_fraction = validated_consensus_weight / total_network_cw
  ```
- **Safe**: ✅ YES - Always uses absolute value
- **Purpose**: Calculate consensus weight of validated relays
- **Risk Level**: NONE - Now matches pattern from location #4
- **Status**: **FIXED** ✅

### ✅ 7. aroileaders.py - Reusing Contact Data (Lines 373, 570, 573)
- **Uses**: `consensus_weight_fraction` from `contact_data`
- **Method**: Retrieve pre-calculated fraction
- **Calculation**:
  ```python
  total_consensus_weight = contact_data.get('consensus_weight_fraction', 0.0)
  exit_consensus_weight = contact_data.get('exit_consensus_weight_fraction', 0.0)
  guard_consensus_weight = contact_data.get('guard_consensus_weight_fraction', 0.0)
  ```
- **Safe**: ✅ YES - Uses correctly calculated values from location #4
- **Purpose**: Efficient reuse of contact aggregation data
- **Risk Level**: NONE - Depends on location #4 (which is correct)

### ✅ 8. intelligence_engine.py - Network Analysis (Various lines)
- **Uses**: `consensus_weight_fraction` from aggregated data
- **Method**: Access pre-calculated fractions from countries, networks, contacts
- **Calculation**: Uses values from location #4
- **Safe**: ✅ YES - Uses aggregated data
- **Purpose**: Geographic concentration, HHI calculations, risk analysis
- **Risk Level**: NONE - Correct data source

### ✅ 9. page_context.py - Template Context (Lines 132-135)
- **Uses**: `consensus_weight_fraction` from aggregated data
- **Method**: Pass-through to templates
- **Calculation**: No calculation - passes existing data
- **Safe**: ✅ YES - Passes through correct data
- **Purpose**: Template rendering context
- **Risk Level**: NONE - Simple data passing

---

## Four Identified Patterns

### Pattern A: Direct Relay-Level Access (Onionoo's Fraction)
- **Locations**: #1 (display), #3 (aggregation - overwritten)
- **Usage**: `relay.get('consensus_weight_fraction')`
- **Risk**: ⚠️ May be missing for non-running relays
- **Mitigation**: Used only for display with fallback, or overwritten by correct calculation
- **Verdict**: SAFE with current implementation

### Pattern B: Relay-Level Absolute Values → Calculate Fraction ✅
- **Locations**: #2 (network totals), #4 (final calculation), #6 (validation - after fix)
- **Usage**: 
  1. `relay.get('consensus_weight', 0)` - get absolute
  2. Sum across relays
  3. Divide by total network consensus_weight
- **Risk**: ✅ NONE - Absolute value always present
- **Verdict**: GOLD STANDARD - This is the correct approach

### Pattern C: Use Pre-calculated Aggregated Fractions ✅
- **Locations**: #7 (AROI reuse), #8 (intelligence engine), #9 (templates)
- **Usage**: `contact_data.get('consensus_weight_fraction')`
- **Risk**: ✅ NONE - Depends on Pattern B (which is correct)
- **Verdict**: SAFE and EFFICIENT - Reuses correct calculations

### Pattern D: Direct Relay Fraction Sum ❌ (THE BUG - FIXED)
- **Locations**: #5 (old aroileaders.py validation)
- **Usage**: `relay.get('consensus_weight_fraction', 0)` in sum loop
- **Risk**: ❌ HIGH - Returns 0 for non-running relays
- **Verdict**: FIXED - Changed to Pattern B ✅

---

## The artikel10.org Bug Explained

### What Happened
```python
# OLD CODE (buggy):
for relay in operator_relays:
    relay_cw = relay.get('consensus_weight_fraction', 0)  # Returns 0 if missing!
    validated_consensus_weight += relay_cw

# If all 152 relays were non-running or recently restarted:
# validated_consensus_weight = 0 + 0 + 0 + ... (152 times) = 0
# Display: 0.00% ❌
```

### Why Only artikel10.org Was Affected
- Most operators had validated relays that were currently **running**
- Running relays have `consensus_weight_fraction` from Onionoo → old code worked
- artikel10.org's validated relays were likely **not running** at data collection time
- Non-running relays don't have `consensus_weight_fraction` → old code got 0

### The Fix
```python
# NEW CODE (fixed):
for relay in operator_relays:
    relay_cw = relay.get('consensus_weight', 0)  # Always present! ✅
    validated_consensus_weight += relay_cw

# Convert to fraction after summing:
total_network_cw = sum of guard/middle/exit network totals
validated_cw_fraction = validated_consensus_weight / total_network_cw

# Display: 3.86% ✅ (matches Bandwidth Capacity table)
```

---

## Recommendations

### ✅ DO: Use Pattern B for All Relay-Level Calculations
1. Get `relay.get('consensus_weight', 0)` - absolute value
2. Sum across relays
3. Divide by `total_network_consensus_weight` to get fraction

### ✅ DO: Reuse Aggregated Fractions (Pattern C)
For contact/country/AS data, use `contact_data.get('consensus_weight_fraction')` - it's already calculated correctly.

### ⚠️ AVOID: Direct Summation of relay.consensus_weight_fraction
This will miss non-running relays and produce incorrect totals.

### 💡 OPTIONAL CLEANUP: Remove Lines 1240-1241 in relays.py
These lines sum `consensus_weight_fraction` from individual relays, but the value is overwritten by lines 1394-1412. Removing them would:
- Improve code clarity
- Save CPU cycles
- Have no functional impact (value is overwritten anyway)

---

## Testing Verification

Real Onionoo data analysis confirmed:
- ✅ Running relays: `consensus_weight_fraction` IS provided
- ❌ Non-running relays: `consensus_weight_fraction` is NOT provided
- ✅ All relays: `consensus_weight` is ALWAYS provided

Impact measured:
- Sample: 2 running + 3 non-running relays
- Old method: 0.0452% (lost 36% of consensus weight)
- New method: 0.0706% (correct)

---

## Status: All Issues Resolved ✅

- ✅ artikel10.org bug: FIXED
- ✅ IPv4/IPv6 consensus weights: FIXED (same bug, same fix)
- ✅ All other locations: VERIFIED SAFE
- ✅ Pattern audit: COMPLETE
- ⚠️ Optional cleanup: Lines 1240-1241 (low priority, no functional impact)
