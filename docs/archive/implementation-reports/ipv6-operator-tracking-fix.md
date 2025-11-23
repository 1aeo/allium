# IPv6 Operator Tracking Fix

## Issue Summary

The Network Health Dashboard was showing 0 values for IPv6 operator metrics:
- `both_ipv4_ipv6_operators` was 0 (should be almost everybody)
- `ipv4_only_operators` was 0 (should be more than 0)

## Root Cause

In `allium/lib/relays.py` line 3343, the code was trying to access `relay.get('hashed_contact')` but this field doesn't exist. The actual field name is `contact_md5` which is created by the `_add_hashed_contact()` method.

## Fix Applied

**Changed line 3343 from:**
```python
contact_hash = relay.get('hashed_contact')
```

**To:**
```python
contact_hash = relay.get('contact_md5')
```

**Additional fix for AS name safety:**
```python
'as_name_truncated': as_name[:8] if as_name and len(as_name) > 8 else (as_name or f'AS{as_number}'),
```

## Validation

- Created comprehensive test showing both metrics now return non-zero values
- Verified existing functionality remains intact
- Confirmed IPv6 support detection works correctly

## Impact

The Network Health Dashboard now accurately displays IPv6 adoption metrics across relay operators, providing valuable insights for network diversity analysis. 