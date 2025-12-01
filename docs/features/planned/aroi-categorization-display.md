# AROI Categorization - Future Enhancements

**Date:** November 30, 2025  
**Status:** 📋 Planned

---

## Executive Summary

While the AROI (Authenticated Relay Operator Identifier) categorization logic is fully implemented and working, the **actionable feedback is not yet displayed to operators**. This document outlines the template updates needed to show operators exactly which AROI field(s) they're missing and how to fix them.

---

## Current State vs. Desired State

### What Works Now ✅

1. **Backend categorization** - Relays are correctly categorized into 7 states
2. **Metrics calculation** - Network-wide counts are accurate
3. **Operator validation status** - Badge shows validated/unvalidated/partial
4. **Error details** - Generic error messages appear for validation failures

### What's Missing ❌

1. **Specific missing field feedback** - Operators don't see which field is missing
2. **Actionable guidance** - No instructions on how to complete AROI setup
3. **Network dashboard breakdown** - Categorization counts not visible

---

## The Gap: What Operators See Now

### Current Error Display (Generic)

**Location:** Contact page, bottom error box  
**Example:**

```
⚠️ AROI Validation Issues (0/1 relays validated)

• MyRelay1 • Fingerprint not found in https://example.com/.well-known/tor-relay/rsa-fingerprint.txt
  • Proof type: uri-rsa • Fingerprint: ABC123...
```

**Problem:** This error message assumes the operator has a complete AROI setup. If they're missing a field, they get no feedback.

---

## Planned Enhancement #1: Contact Page Error Box

### New Specific Feedback

**Template:** `allium/templates/contact.html` (lines 549-584)

#### Current Code Structure

```jinja2
{% for relay in contact_validation_status.unvalidated_relays %}
<li>
    <strong>{{ relay.nickname|escape }}</strong>
    <span style="color: #dc3545;">{{ relay.error|escape }}</span>
    {% if relay.proof_type and relay.proof_type != 'unknown' %}
        <span style="color: #666;">• Proof type: {{ relay.proof_type }}</span>
    {% endif %}
</li>
{% endfor %}
```

#### Proposed Enhancement

Add relay category checking to provide specific guidance:

```jinja2
{% for relay in contact_validation_status.unvalidated_relays %}
<li>
    <strong>{{ relay.nickname|escape }}</strong>
    
    {# Check if relay has a category indicating missing field(s) #}
    {% if relay.category == 'no_proof' %}
        <span style="color: #dc3545;">⚠️ Missing AROI proof field</span>
        <div style="margin-left: 20px; margin-top: 5px; color: #856404;">
            <strong>How to fix:</strong> Add <code style="background: #fff; padding: 2px 5px; border: 1px solid #ccc;">proof:dns-rsa</code> 
            or <code style="background: #fff; padding: 2px 5px; border: 1px solid #ccc;">proof:uri-rsa</code> to your contact string.
            <br>
            <small><a href="https://nusenu.github.io/ContactInfo-Information-Sharing-Specification/#3-proof-types" 
                      target="_blank" style="color: #856404;">Learn about AROI proof types →</a></small>
        </div>
        
    {% elif relay.category == 'no_domain' %}
        <span style="color: #dc3545;">⚠️ Missing AROI domain field</span>
        <div style="margin-left: 20px; margin-top: 5px; color: #856404;">
            <strong>How to fix:</strong> Add <code style="background: #fff; padding: 2px 5px; border: 1px solid #ccc;">url:yourdomain.com</code> to your contact string.
            <br>
            <small><a href="https://nusenu.github.io/ContactInfo-Information-Sharing-Specification/#2-url" 
                      target="_blank" style="color: #856404;">Learn about AROI URL field →</a></small>
        </div>
        
    {% elif relay.category == 'no_ciissversion' %}
        <span style="color: #dc3545;">⚠️ Missing AROI version field</span>
        <div style="margin-left: 20px; margin-top: 5px; color: #856404;">
            <strong>How to fix:</strong> Add <code style="background: #fff; padding: 2px 5px; border: 1px solid #ccc;">ciissversion:2</code> to your contact string.
            <br>
            <small><a href="https://nusenu.github.io/ContactInfo-Information-Sharing-Specification/#1-ciissversion" 
                      target="_blank" style="color: #856404;">Learn about AROI version →</a></small>
        </div>
        
    {% elif relay.category == 'no_aroi' %}
        <span style="color: #666;">ℹ️ AROI setup incomplete (missing 2+ fields)</span>
        <div style="margin-left: 20px; margin-top: 5px; color: #666;">
            <strong>To enable AROI validation, add all 3 required fields:</strong>
            <code style="background: #fff; padding: 2px 5px; border: 1px solid #ccc;">ciissversion:2 proof:dns-rsa url:yourdomain.com</code>
            <br>
            <small><a href="https://nusenu.github.io/ContactInfo-Information-Sharing-Specification/" 
                      target="_blank" style="color: #666;">Read the AROI Specification →</a></small>
        </div>
        
    {% else %}
        {# Standard validation error (has complete AROI but verification failed) #}
        <span style="color: #dc3545;">{{ relay.error|escape }}</span>
        {% if relay.proof_type and relay.proof_type != 'unknown' %}
            <span style="color: #666;">• Proof type: {{ relay.proof_type }}</span>
        {% endif %}
    {% endif %}
    
    <span style="color: #666;">• Fingerprint: <code style="font-size: 11px;">{{ relay.fingerprint }}</code></span>
</li>
{% endfor %}
```

#### Visual Mockup: What Operators Will See

**Scenario 1: Missing only proof field**
```
⚠️ AROI Validation Issues (0/3 relays validated)

• MyRelay1 • ⚠️ Missing AROI proof field
    How to fix: Add proof:dns-rsa or proof:uri-rsa to your contact string.
    Learn about AROI proof types →
    • Fingerprint: ABC123...

• MyRelay2 • ⚠️ Missing AROI proof field
    How to fix: Add proof:dns-rsa or proof:uri-rsa to your contact string.
    Learn about AROI proof types →
    • Fingerprint: DEF456...
```

**Scenario 2: Missing multiple different fields**
```
⚠️ AROI Validation Issues (1/4 relays validated)

• MyRelay1 • ⚠️ Missing AROI domain field
    How to fix: Add url:yourdomain.com to your contact string.
    Learn about AROI URL field →
    • Fingerprint: ABC123...

• MyRelay2 • ⚠️ Missing AROI version field
    How to fix: Add ciissversion:2 to your contact string.
    Learn about AROI version →
    • Fingerprint: DEF456...

• MyRelay3 • ℹ️ AROI setup incomplete (missing 2+ fields)
    To enable AROI validation, add all 3 required fields: ciissversion:2 proof:dns-rsa url:yourdomain.com
    Read the AROI Specification →
    • Fingerprint: GHI789...
```

**Scenario 3: Complete AROI but validation failed**
```
⚠️ AROI Validation Issues (0/2 relays validated)

• MyRelay1 • Fingerprint not found in https://example.com/.well-known/tor-relay/rsa-fingerprint.txt
    • Proof type: uri-rsa • Fingerprint: ABC123...

• MyRelay2 • DNS TXT record not found for _tor.example.com
    • Proof type: dns-rsa • Fingerprint: DEF456...
```

---

## Planned Enhancement #2: Backend Changes

### Add Category to Relay Data

**File:** `allium/lib/aroi_validation.py` - `get_contact_validation_status()` function

**Current:** Relay data includes nickname, fingerprint, error, proof_type  
**Needed:** Add `category` field to relay data

```python
# In get_contact_validation_status(), when building unvalidated_relays list:
result['unvalidated_relays'].append({
    'nickname': nickname,
    'fingerprint': fingerprint,
    'error': error,
    'proof_type': proof_type,
    'category': _categorize_relay_by_validation(relay, validation_map)  # NEW
})
```

**Impact:** Templates can now access `relay.category` to display specific guidance.

---

## Planned Enhancement #3: Network Health Dashboard

### Show Categorization Breakdown

**Template:** `allium/templates/network-health-dashboard.html`

**Location:** AROI Validation Status card (around line 360-380)

#### Current Display

```
📊 AROI Validation Status

Total Relays with AROI: 5,432 (54.3% of all relays)

Validated: 4,123 (75.9% of relays with AROI)
  ✓ Verification successful

Unvalidated: 1,309 (24.1% of relays with AROI)
  ✗ Verification failed
```

#### Proposed Enhancement

Add breakdown section for incomplete setups:

```html
<div class="metric-grid" style="grid-template-columns: repeat(3, 1fr); margin-top: 15px;">
    <div class="metric-item" 
         title="Relays with ciissversion + url but missing only the proof field (proof:dns-rsa or proof:uri-rsa). 
                These operators are 1 field away from complete AROI setup.">
        <span class="metric-value" style="color: #ffc107;">
            {{ "{:,}".format(relays.json.network_health.aroi_no_proof_count) }}
        </span>
        <span class="metric-label">Missing Proof Only</span>
        <div style="font-size: 11px; color: #666; margin-top: 2px;">
            {{ "%.1f%%"|format(relays.json.network_health.aroi_no_proof_percentage) }} of all relays
        </div>
    </div>
    
    <div class="metric-item" 
         title="Relays with ciissversion + proof but missing only the url field. 
                These operators are 1 field away from complete AROI setup.">
        <span class="metric-value" style="color: #ffc107;">
            {{ "{:,}".format(relays.json.network_health.aroi_no_domain_count) }}
        </span>
        <span class="metric-label">Missing Domain Only</span>
        <div style="font-size: 11px; color: #666; margin-top: 2px;">
            {{ "%.1f%%"|format(relays.json.network_health.aroi_no_domain_percentage) }} of all relays
        </div>
    </div>
    
    <div class="metric-item" 
         title="Relays with proof + url but missing only the ciissversion field. 
                These operators are 1 field away from complete AROI setup.">
        <span class="metric-value" style="color: #ffc107;">
            {{ "{:,}".format(relays.json.network_health.aroi_no_ciissversion_count) }}
        </span>
        <span class="metric-label">Missing Version Only</span>
        <div style="font-size: 11px; color: #666; margin-top: 2px;">
            {{ "%.1f%%"|format(relays.json.network_health.aroi_no_ciissversion_percentage) }} of all relays
        </div>
    </div>
</div>

<div class="metric-item primary" 
     title="Relays missing 2 or more AROI fields. These operators have not completed AROI setup."
     style="margin-top: 15px;">
    <span class="metric-value">
        {{ "{:,}".format(relays.json.network_health.relays_no_aroi) }}
    </span>
    <span class="metric-label">No AROI Setup (Missing 2+ fields)</span>
    <div style="font-size: 11px; color: #666; margin-top: 2px;">
        {{ "%.1f%%"|format(relays.json.network_health.relays_no_aroi_percentage) }} of all relays
    </div>
</div>
```

#### Visual Mockup

```
📊 AROI Validation Status

Total Relays with AROI: 5,432 (54.3% of all relays)

✅ Validated: 4,123 (75.9%)
   Verification successful

❌ Unvalidated: 1,309 (24.1%)
   Has all 3 fields but verification failed

──────────────────────────────────────
Incomplete Setup Breakdown:

⚠️ Missing Proof Only: 234      ⚠️ Missing Domain Only: 156      ⚠️ Missing Version Only: 89
   2.3% of all relays              1.6% of all relays               0.9% of all relays

ℹ️ No AROI Setup (Missing 2+ fields): 4,568
   45.7% of all relays
```

---

## Planned Enhancement #4: Relay Detail Pages

### Show Category on Individual Relay Pages

**Template:** `allium/templates/relay-info.html`

**Location:** Near AROI validation status section

#### Proposed Addition

```jinja2
{% if relay.aroi_domain and relay.aroi_domain != 'none' %}
    <strong>AROI Domain:</strong> {{ relay.aroi_domain|escape }}
    {# Show validation badge #}
    {% if relay.aroi_validated %}
        <span style="color: #28a745;">✓ Validated</span>
    {% else %}
        <span style="color: #dc3545;">✗ Unvalidated</span>
    {% endif %}
{% elif relay.aroi_category %}
    {# Show specific missing field guidance #}
    <strong>AROI Status:</strong>
    {% if relay.aroi_category == 'no_proof' %}
        <span style="color: #ffc107;">⚠️ Missing proof field</span>
        <small>(Add proof:dns-rsa or proof:uri-rsa)</small>
    {% elif relay.aroi_category == 'no_domain' %}
        <span style="color: #ffc107;">⚠️ Missing domain field</span>
        <small>(Add url:yourdomain.com)</small>
    {% elif relay.aroi_category == 'no_ciissversion' %}
        <span style="color: #ffc107;">⚠️ Missing version field</span>
        <small>(Add ciissversion:2)</small>
    {% elif relay.aroi_category == 'no_aroi' %}
        <span style="color: #666;">ℹ️ No AROI setup</span>
        <small>(Missing 2+ fields)</small>
    {% endif %}
{% endif %}
```

---

## Variables Available (Backend Already Provides)

The categorization logic already calculates these values. Templates just need to access them:

### Network-Wide Metrics (Already Calculated)

```python
metrics = {
    'aroi_validated_count': 4123,
    'aroi_unvalidated_count': 1309,
    'aroi_no_proof_count': 234,           # NEW - ready to display
    'aroi_no_domain_count': 156,          # NEW - ready to display
    'aroi_no_ciissversion_count': 89,     # NEW - ready to display
    'relays_no_aroi': 4568,
    
    # Percentages
    'aroi_no_proof_percentage': 2.3,      # NEW - ready to display
    'aroi_no_domain_percentage': 1.6,     # NEW - ready to display
    'aroi_no_ciissversion_percentage': 0.9, # NEW - ready to display
}
```

**Access in templates:**
- `relays.json.network_health.aroi_no_proof_count`
- `relays.json.network_health.aroi_no_domain_count`
- `relays.json.network_health.aroi_no_ciissversion_count`

### Per-Relay Category (Needs Minor Backend Addition)

**Status:** Helper function exists, just need to expose it to templates

**Current:**
```python
category = _categorize_relay_by_validation(relay, validation_map)
# Used internally for counting, not passed to templates
```

**Needed:**
```python
# In get_contact_validation_status():
result['unvalidated_relays'].append({
    'nickname': nickname,
    'fingerprint': fingerprint,
    'error': error,
    'proof_type': proof_type,
    'category': category  # ADD THIS
})

# In relay processing for individual pages:
relay['aroi_category'] = _categorize_relay_by_validation(relay, validation_map)
```

**Template access:**
- `relay.category` (in contact page error list)
- `relay.aroi_category` (in relay detail page)

---

## Implementation Checklist

### Phase 1: Backend Exposure (Minimal Changes)

- [ ] Update `get_contact_validation_status()` to include `category` in unvalidated_relays
- [ ] Update relay processing to add `aroi_category` field
- [ ] Verify metrics are already available in templates

### Phase 2: Contact Page Enhancement

- [ ] Update `contact.html` error box to check `relay.category`
- [ ] Add if/elif chain for specific field guidance
- [ ] Add "How to fix" instructions with code examples
- [ ] Add links to AROI specification sections
- [ ] Test with real operator pages

### Phase 3: Network Health Dashboard

- [ ] Update `network-health-dashboard.html` AROI section
- [ ] Add 3 metric cards for missing fields (proof/domain/version)
- [ ] Add "No AROI Setup" card
- [ ] Style with appropriate colors (yellow for "almost there", gray for "not started")

### Phase 4: Relay Detail Pages (Optional)

- [ ] Update `relay-info.html` to show category
- [ ] Add guidance for individual relays

---

## Expected Impact

### For Operators

**Before:**
- Generic "Missing AROI fields" error (unhelpful)
- No guidance on what to add
- No distinction between "missing 1 field" vs. "missing all fields"

**After:**
- Specific "Missing AROI proof field" message (actionable)
- Direct instructions: "Add proof:dns-rsa to your contact string"
- Clear distinction between incomplete setup vs. validation failure
- Links to relevant specification sections

### For Network Admins

**Before:**
- Aggregate counts only (validated/unvalidated)
- No visibility into incomplete setups

**After:**
- Breakdown showing 234 operators missing only proof
- Ability to target outreach: "Add proof field to complete setup"
- Better understanding of AROI adoption bottlenecks

### Metrics Example

**Current dashboard:**
- "Unvalidated: 1,543 relays"

**Enhanced dashboard:**
- "Unvalidated: 1,309 relays (complete setup, failed validation)"
- "Missing proof only: 234 relays (add 1 field)"
- "Missing domain only: 156 relays (add 1 field)"
- "Missing version only: 89 relays (add 1 field)"
- "No AROI setup: 4,568 relays (need all 3 fields)"

**Insight:** 479 operators are "almost there" (missing only 1 field) vs. 4,568 who haven't started.

---

## Files to Modify

1. **`allium/lib/aroi_validation.py`**
   - Add `category` to relay data in `get_contact_validation_status()`
   - Expose category in relay processing

2. **`allium/templates/contact.html`**
   - Update error box (lines 549-584)
   - Add category-based guidance

3. **`allium/templates/network-health-dashboard.html`**
   - Add breakdown section (after line 380)
   - Display new metric cards

4. **`allium/templates/relay-info.html`** (optional)
   - Add AROI category display

---

## Testing Plan

1. **Unit Tests**
   - Verify category is included in unvalidated_relays
   - Test template rendering with different categories

2. **Integration Tests**
   - Generate pages for operators with each category
   - Verify correct guidance appears
   - Check dashboard metrics display

3. **User Acceptance**
   - Review with actual operator feedback
   - Ensure instructions are clear and actionable

---

## Timeline Estimate

- **Phase 1 (Backend):** 1-2 hours
- **Phase 2 (Contact pages):** 2-3 hours
- **Phase 3 (Dashboard):** 1-2 hours
- **Phase 4 (Relay pages):** 1 hour
- **Testing:** 2 hours

**Total:** ~8-10 hours development time

---

## Success Criteria

1. ✅ Operators see specific field guidance instead of generic errors
2. ✅ Network dashboard shows categorization breakdown
3. ✅ Links to AROI specification sections are functional
4. ✅ Visual distinction between "almost there" and "not started"
5. ✅ All error messages are actionable with clear next steps

---

## Conclusion

The categorization logic is **fully implemented and working**. The missing piece is **displaying this information to operators** in an actionable way. The template enhancements outlined here will complete the feature and provide significant value to both operators and network administrators.

**Status:** 📋 **Ready for Implementation**  
**Complexity:** 🟢 **Low** (mostly template updates)  
**Impact:** 🟢 **High** (actionable operator feedback)

---

**Related Documentation:**
- Implemented: `AROI_CATEGORIZATION_IMPLEMENTED.md`
- Code: `/workspace/allium/lib/aroi_validation.py`
- Templates: `/workspace/allium/templates/contact.html`, `network-health-dashboard.html`
