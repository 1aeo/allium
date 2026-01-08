# AROI Validated Relay Display Redesign

**Date:** January 6, 2026  
**Status:** ✅ Implemented  
**Implemented:** January 6, 2026  
**Impact:** User Experience for Operator Pages

---

## Executive Summary

This feature redesigns the AROI operator page to clearly separate **authorized relays** (fingerprint in domain owner's proof file) from **unauthorized claims** (relays claiming the domain but not in the proof file). This addresses two real-world scenarios that impact operator pages and ensures the validation status accurately reflects only the domain owner's intended relays.

---

## Problem Solved

### The Core Issue

Any relay can claim association with a domain by setting `url:<domain>` in their contact info. This creates two distinct scenarios:

| Scenario | Description | Impact |
|----------|-------------|--------|
| **A) Legitimate** | Domain owner operates the relay AND added fingerprint to proof | Relay validates correctly ✓ |
| **B) Illegitimate** | Someone falsely claims a domain they don't control | Now clearly separated as "Unauthorized" |

### Previous Behavior vs. New Behavior

#### Metric 1: Overall AROI Validation Status

| Status | Previous | Now |
|--------|----------|-----|
| `validated` | All AROI relays pass | All **authorized** relays pass |
| `unauthorized` | N/A | **NEW:** Relays not in proof file |
| `misconfigured` | N/A | **NEW:** DNS/SSL/connection errors |
| `not_configured` | N/A | **NEW:** Missing AROI fields |

#### Metric 2: Relay List Display

| Element | Previous | Now |
|---------|----------|-----|
| Main relay table | All relays mixed together | **4 separate sections by category** |
| Unauthorized claims | Mixed with warning icon | **Red dashed border section** |
| Misconfigured relays | Mixed with warning icon | **Yellow border section** |

---

## Implementation Details

### Backend Changes (`allium/lib/aroi_validation.py`)

The `get_contact_validation_status()` function now returns:

```python
result = {
    'has_aroi': False,
    'validation_status': 'not_configured',  # validated | unauthorized | misconfigured | not_configured
    
    # Complete AROI relays (all 3 fields present)
    'validated_relays': [],        # Fingerprint in proof, validation passed
    'unauthorized_relays': [],     # "fingerprint not found" errors
    'misconfigured_relays': [],    # DNS/SSL/timeout errors
    
    # Incomplete AROI relays
    'incomplete_relays': [],       # 1-2 AROI fields present
    'not_configured_relays': [],   # 0 AROI fields
    
    # Fingerprint sets for O(1) lookups in templates
    'validated_fingerprints': set(),
    'unauthorized_fingerprints': set(),
    'misconfigured_fingerprints': set(),
    
    'validation_summary': {
        'total_relays': len(relays),
        'validated_count': 0,
        'unauthorized_count': 0,
        'misconfigured_count': 0,
        'incomplete_count': 0,
        'not_configured_count': 0,
        # Granular counts for tooltips...
    },
}
```

### Error Classification Logic

```python
# Unauthorized: Fingerprint/record not found in proof file
is_unauthorized = (
    'fingerprint not found' in error_lower or
    ('not found' in error_lower and 'record' in error_lower and 'nxdomain' not in error_lower)
)

# Misconfigured: DNS/SSL/connection errors (operator's own relay with config issues)
# All other errors fall into this category
```

### Template Changes

#### 4-Section Layout (`contact-relay-list.html`)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ✅ VALIDATED RELAYS (green border)                                     │
│  Fingerprints verified in AROI proof file                               │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  ⚠️ MISCONFIGURED RELAYS (yellow border)                                │
│  DNS/SSL/connection errors - operator's own relays with config issues   │
└─────────────────────────────────────────────────────────────────────────┘

┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┐
│  🚫 UNAUTHORIZED RELAYS (red dashed border)                             │
│  Fingerprint NOT in proof file - potential impersonation                │
└ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┘

┌─────────────────────────────────────────────────────────────────────────┐
│  ⬜ NOT CONFIGURED RELAYS (gray border)                                 │
│  Missing AROI fields - incomplete or no AROI setup                      │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Validation Icons (`macros.html`)

| Icon | Meaning | Link Target |
|------|---------|-------------|
| ✓ (green) | Validated - fingerprint in proof | N/A |
| 🚫 (red) | Unauthorized - not in proof | `#unauthorized-relays` |
| ⚠ (yellow) | Misconfigured - DNS/SSL error | `#misconfigured-relays` |

#### Validation Badge (`aroi_validation_badge` macro)

| Status | Display |
|--------|---------|
| `validated` | ✓ Validated (green) |
| `unauthorized` | 🚫 Unauthorized (red) |
| `misconfigured` | ⚠ Misconfigured (yellow) |
| `not_configured` | (no badge) |

---

## How This Solves Both Scenarios

### Scenario A: Legitimate Operator

| Situation | Previous | Now |
|-----------|----------|-----|
| All relays validated | ✓ Validated (50 relays) | ✓ Validated (50 relays) |
| Some relays misconfigured | ⚠ Partially (45/50) | ⚠ Misconfigured section shows errors |
| Unauthorized claims exist | ⚠ Partially (50/53) ❌ | ✓ Validated (50 relays) + unauthorized section |

**Key improvement:** Unauthorized claims no longer degrade the operator's validation status.

### Scenario B: Illegitimate Claims

| Situation | Previous | Now |
|-----------|----------|-----|
| Pure attacker (no valid relays) | ❌ Unvalidated (0/5) | 🚫 Unauthorized (5 relays in red section) |
| Mixed with real operator | Polluted operator page | Clearly separated sections |

**Key improvement:** Domain owners can clearly see which relays are unauthorized.

---

## Handling Both Operator Preferences

### Preference 1: "Don't count illegitimate relays in my status"

✅ **Solved:** Unauthorized relays are excluded from the validation status badge. An operator with 50 validated relays shows "✓ Validated" even if 3 unauthorized relays claim their domain.

### Preference 2: "Show me who's claiming my domain"

✅ **Solved:** Unauthorized relays are always visible in a clearly separated red-bordered section with:
- 🚫 icon for each relay
- Full error details
- "Inspect →" links to investigate
- Help text explaining how to authorize legitimate relays

---

## Files Modified

1. **`allium/lib/aroi_validation.py`**
   - Updated `get_contact_validation_status()` with new categorization
   - Added error classification logic (unauthorized vs misconfigured)
   - Added fingerprint sets for O(1) template lookups

2. **`allium/templates/contact-relay-list.html`**
   - Implemented 4-section layout for AROI operators
   - Added section headers with counts and styling
   - Added detail boxes for each category

3. **`allium/templates/macros.html`**
   - Updated `aroi_validation_icon()` with 🚫 for unauthorized
   - Updated `aroi_validation_badge()` with new statuses
   - Added `aroi_section_header()` macro
   - Added `aroi_relay_detail_box()` macro

4. **`allium/templates/contact.html`**
   - Updated to use new validation status display

5. **`tests/test_aroi_validation.py`**
   - Added tests for new categorization logic

---

## Implementation Checklist

### Phase 1: Backend Changes
- [x] Update `get_contact_validation_status()` to separate authorized vs unauthorized
- [x] Add `misconfigured_relays` list for DNS/SSL/timeout errors
- [x] Add `unauthorized_relays` list for "fingerprint not found" errors
- [x] Add new validation statuses: `validated`, `unauthorized`, `misconfigured`, `not_configured`
- [x] Add fingerprint sets for O(1) template lookups

### Phase 2: Template Changes
- [x] Implement 4-section layout for operator pages
- [x] Create section headers with category-specific styling
- [x] Add detail boxes with error information
- [x] Update validation icons (🚫 for unauthorized, ⚠ for misconfigured)
- [x] Update validation badge macro

### Phase 3: Testing
- [x] Unit tests for new categorization logic
- [x] Test with operators who have unauthorized claims
- [x] Test with operators who have misconfigured relays
- [x] Verify backward compatibility

---

## Success Criteria - All Met

1. ✅ Operator's validation status based only on authorized relays
2. ✅ Unauthorized claims clearly separated in red-bordered section
3. ✅ Misconfigured relays shown in yellow-bordered section
4. ✅ Operators can investigate unauthorized claims via "Inspect" links
5. ✅ Unauthorized claims section always visible (important security information)
6. ✅ Backward compatibility maintained for existing pages

---

## Related Documentation

- **Implementation:** `allium/lib/aroi_validation.py`
- **AROI Spec:** https://nusenu.github.io/ContactInfo-Information-Sharing-Specification/
- **Validation API:** https://aroivalidator.1aeo.com/latest.json
- **Related:** `docs/features/implemented/aroi-categorization-fix.md`

---

**Last Updated:** January 6, 2026  
**Author:** Allium Development Team
