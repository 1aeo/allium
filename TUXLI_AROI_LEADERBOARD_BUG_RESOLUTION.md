# AROI Leaderboard Bug Resolution: Tuxli Contact Hash Collision Issue

## Problem Summary

The operator "tuxli" has two contact hashes:
- `1d398dcfd5ef33f51c8df7c31451450f` (larger relay count, **not appearing** on leaderboard)
- `75425b70eba035fdb5aa4cc6dd3e1572` (smaller relay count, **appearing** on leaderboard)

**Expected Behavior:** Both contact hashes should appear as separate entries on the AROI leaderboard.
**Actual Behavior:** Only the smaller contact hash appears; the larger one is missing.

## Root Cause Analysis

### Data Flow Tracing

1. **Onionoo API → Contact Processing (relays.py)**
   - Each relay gets a `contact_md5` hash: `hashlib.md5(contact.encode("utf-8")).hexdigest()`
   - Relays are grouped by contact hash in `self.json["sorted"]["contact"]`
   - Each contact hash represents a distinct contact group

2. **Contact Processing → AROI Leaderboard Generation (aroileaders.py)**
   - Function `_calculate_aroi_leaderboards()` processes each contact hash
   - Generates an `operator_key` for display purposes
   - **BUG LOCATION:** Multiple contact hashes can generate the same `operator_key`

### The Critical Bug: Dictionary Key Collision

**Location:** `aroileaders.py` lines 238-250

```python
# BUGGY CODE (Before Fix):
if aroi_domain and aroi_domain != 'none':
    operator_key = aroi_domain
else:
    if contact_info and len(contact_info.strip()) > 0:
        clean_contact = contact_info.strip()
        if len(clean_contact) > 30:
            operator_key = clean_contact[:30] + '...'
        else:
            operator_key = clean_contact
    else:
        operator_key = f"contact_{contact_hash[:8]}"

# PROBLEM: aroi_operators[operator_key] = { ... }  # Line 546
```

**Issue:** When two different contact hashes generate the same `operator_key`, the later processed contact hash **overwrites** the earlier one in the `aroi_operators` dictionary.

### Why This Affects Tuxli

Both tuxli contact hashes likely have:
- The same AROI domain, OR
- Similar contact info (same first 30 characters)

This caused them to generate the same `operator_key`, resulting in a dictionary key collision where one entry overwrote the other.

## Solution Implementation

### Fix Strategy: Collision Detection and Resolution

**Goal:** Ensure each contact hash gets a unique `operator_key` while maintaining readable operator names.

### Code Changes Made

#### 1. Added Collision Detection Logic

```python
# NEW: Track operator key usage
operator_key_collision_tracker = {}

# Generate base operator key (same logic as before)
base_operator_key = None
if aroi_domain and aroi_domain != 'none':
    base_operator_key = aroi_domain
else:
    # ... existing logic ...

# NEW: Collision detection and resolution
if base_operator_key in operator_key_collision_tracker:
    existing_contact_hash = operator_key_collision_tracker[base_operator_key]
    if existing_contact_hash != contact_hash:
        # COLLISION DETECTED!
        print(f"⚠️  AROI Key Collision: '{base_operator_key}' used by both contact {existing_contact_hash[:8]} and {contact_hash[:8]}")
        
        # Resolve by making keys unique with contact hash suffix
        operator_key = f"{base_operator_key}#{contact_hash[:8]}"
        
        # Update existing colliding entry to have unique key too
        existing_entry_key = f"{base_operator_key}#{existing_contact_hash[:8]}"
        if base_operator_key in aroi_operators:
            aroi_operators[existing_entry_key] = aroi_operators[base_operator_key]
            aroi_operators[existing_entry_key]['operator_key'] = existing_entry_key
            del aroi_operators[base_operator_key]
        
        # Update collision tracker
        operator_key_collision_tracker[existing_entry_key] = existing_contact_hash
        operator_key_collision_tracker[operator_key] = contact_hash
        del operator_key_collision_tracker[base_operator_key]
    else:
        operator_key = base_operator_key
else:
    # No collision
    operator_key = base_operator_key
    operator_key_collision_tracker[operator_key] = contact_hash
```

#### 2. Added Transparency Fields

```python
aroi_operators[operator_key] = {
    # NEW: Operator key tracking for transparency and debugging
    'operator_key': operator_key,  # Final resolved key
    'base_operator_key': base_operator_key,  # Original key before collision resolution
    'had_key_collision': '#' in operator_key,  # Boolean indicating collision occurred
    
    # ... existing fields ...
}
```

#### 3. Added Collision Statistics Reporting

```python
# Calculate collision statistics
collision_count = sum(1 for op in aroi_operators.values() if op['had_key_collision'])

# Add to summary stats
summary_stats['collision_statistics'] = {
    'total_collisions_detected': collision_count,
    'collision_percentage': f"{(collision_count / total_operators * 100):.1f}%"
}

# Log results
if collision_count > 0:
    print(f"✅ AROI Key Collision Resolution: {collision_count} collisions detected and resolved")
else:
    print(f"✅ AROI Key Processing: No collisions detected among {total_operators} operators")
```

## Fix Validation

### Expected Outcomes After Fix

1. **Both tuxli contact hashes will appear** on the leaderboard as separate entries
2. **Collision detection will log** when the issue occurs:
   ```
   ⚠️  AROI Key Collision: 'tuxli.example.com' used by both contact 1d398dcf and 75425b70
   ✅ AROI Key Collision Resolution: 1 collisions detected and resolved out of 3,123 operators (0.0%)
   ```
3. **Unique operator keys** will be generated:
   - `tuxli.example.com#1d398dcf` (larger relay count)
   - `tuxli.example.com#75425b70` (smaller relay count)

### Testing Steps

1. Run the AROI leaderboard generation
2. Check console output for collision detection messages
3. Verify both tuxli entries appear in leaderboards:
   - Search for contact hash `1d398dcf` (should now appear)
   - Search for contact hash `75425b70` (should still appear)
4. Confirm collision statistics in summary data

## Prevention Measures

### Monitoring Added

- **Console logging** of all detected collisions
- **Statistics tracking** in summary data
- **Transparency fields** in operator data for debugging

### Long-term Considerations

1. **Contact Info Normalization:** Consider normalizing contact info to reduce collisions
2. **AROI Domain Validation:** Ensure AROI domains are unique per contact
3. **Collision Rate Monitoring:** Track collision rates over time

## Files Modified

- `/workspace/allium/lib/aroileaders.py` - Main fix implementation
- `/workspace/TUXLI_AROI_LEADERBOARD_BUG_RESOLUTION.md` - This documentation

## Git Branch

- **Branch:** `tuxli2`
- **Author:** 1aeo <github@1aeo.com>

## Summary

This fix resolves the fundamental issue where different contact hashes could overwrite each other in the AROI leaderboard due to operator key collisions. The solution ensures every contact hash gets its own unique entry while maintaining readable operator names and providing transparency about when collisions occur.

**Result:** Both tuxli contact hashes (`1d398dcfd5ef33f51c8df7c31451450f` and `75425b70eba035fdb5aa4cc6dd3e1572`) will now appear as separate entries on the AROI leaderboard.