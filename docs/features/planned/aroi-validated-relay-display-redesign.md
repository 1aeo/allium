# AROI Validated Relay Display Redesign

**Date:** January 6, 2026  
**Status:** 📋 Proposed  
**Priority:** High  
**Impact:** User Experience for Operator Pages

---

## Executive Summary

This proposal redesigns the AROI operator page to clearly separate **authorized relays** (fingerprint in domain owner's proof file) from **unauthorized claims** (relays claiming the domain but not in the proof file). This addresses two real-world scenarios that impact operator pages and ensures the validation status accurately reflects only the domain owner's intended relays.

---

## Problem Statement

### The Core Issue

Currently, **any relay** can claim association with a domain by setting `url:<domain>` in their contact info. This creates two distinct scenarios:

| Scenario | Description | Current Impact |
|----------|-------------|----------------|
| **A) Legitimate** | Domain owner operates the relay AND added fingerprint to proof | Relay validates correctly ✓ |
| **B) Illegitimate** | Someone falsely claims a domain they don't control | Validation fails, but pollutes operator page |

### Impact on Two Key Metrics

Both scenarios affect the operator page in problematic ways:

#### Metric 1: Overall AROI Validation Status

| Status | Current Calculation | Problem |
|--------|---------------------|---------|
| `validated` | 100% of AROI relays pass | **Illegitimate claims can never achieve this** |
| `partially_validated` | Some pass, some fail | **Legitimate operator shows partial due to unauthorized claims** |
| `unvalidated` | 0% pass | Correct for pure attackers |

**Example:** An operator with 50 validated relays shows "partially_validated" because 3 unauthorized relays are falsely claiming their domain.

#### Metric 2: Relay List Display

| Current Behavior | Problem |
|------------------|---------|
| All relays claiming domain shown in main table | Unauthorized relays mixed with legitimate ones |
| ⚠ warning icon with "Fingerprint not found" | Doesn't distinguish "forgot to add" vs "unauthorized claim" |
| Counts towards total relay count | Inflates operator's apparent relay count |

---

## Proposed Solution: Dual-Section Design

### Design Principle

The domain owner's **AROI proof file** (DNS TXT record or URI proof) serves as the **canonical allowlist** of authorized relays:

- **Fingerprint IN proof file** = Domain owner explicitly authorized this relay
- **Fingerprint NOT IN proof file** = Unauthorized claim (regardless of intent)

### Visual Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│  📋 Contact & Network Overview                                          │
│                                                                         │
│  • AROI: example.com ✓ Validated (47 relays)                           │
│  • ⚠️ 3 unauthorized relays claiming this domain (view details)         │
│  • Contact: contact@example.com                                         │
│  • Hash: abc123...                                                      │
│                                                                         │
│  Network Summary:                                                       │
│  • Bandwidth Capacity: ~1.5 GB/s (Guard: 800 MB, Exit: 500 MB)         │
│  • Network Influence: 0.45% of overall consensus weight                │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  📡 Authorized Relays (47)                                              │
│  ┌─────┬──────────────┬────────────┬─────────┬───────────────────────┐  │
│  │ ✓   │ Nickname     │ Bandwidth  │ Country │ ...                   │  │
│  ├─────┼──────────────┼────────────┼─────────┼───────────────────────┤  │
│  │ ✓   │ MyRelay1     │ 150 MB/s   │ DE      │ ...                   │  │
│  │ ✓   │ MyRelay2     │ 200 MB/s   │ NL      │ ...                   │  │
│  │ ✓   │ MyRelay3     │ 180 MB/s   │ FR      │ ...                   │  │
│  └─────┴──────────────┴────────────┴─────────┴───────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘

┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┐
│  🚨 Unauthorized Claims (3)                                             │
│                                                                         │
│  These relays claim association with example.com but their fingerprints │
│  are NOT in your AROI proof file.                                       │
│                                                                         │
│  ┌───────┬──────────────┬──────────────────┬────────────┬─────────────┐ │
│  │ 🚫    │ Nickname     │ Fingerprint      │ First Seen │ Action      │ │
│  ├───────┼──────────────┼──────────────────┼────────────┼─────────────┤ │
│  │ 🚫    │ FakeRelay1   │ ABC123DEF456...  │ 2 days ago │ [Inspect]   │ │
│  │ 🚫    │ FakeRelay2   │ 789GHI012JKL...  │ 5 days ago │ [Inspect]   │ │
│  │ 🚫    │ Imposter3    │ MNO345PQR678...  │ 1 week ago │ [Inspect]   │ │
│  └───────┴──────────────┴──────────────────┴────────────┴─────────────┘ │
│                                                                         │
│  💡 If this is your relay: Add the fingerprint to your AROI proof file  │
│     to authorize it.                                                    │
└ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┘
```

---

## Detailed Implementation

### 1. Backend Changes: Enhanced Validation Status Calculation

**File:** `allium/lib/aroi_validation.py`

Update `get_contact_validation_status()` to separate authorized vs unauthorized relays:

```python
def get_contact_validation_status(relays: List[Dict], validation_data: Optional[Dict] = None, 
                                   validation_map: Optional[Dict] = None) -> Dict:
    """
    Get validation status for a specific contact's relays.
    
    NEW: Separates relays into authorized (fingerprint in proof) vs unauthorized claims.
    
    Returns:
        - Overall validation status based ONLY on authorized relays
        - Separate lists for authorized relays vs unauthorized claims
        - Summary statistics for both categories
    """
    result = {
        'has_aroi': False,
        'validation_status': 'no_aroi',  # Based only on authorized relays
        
        # === AUTHORIZED RELAYS (fingerprint in proof file) ===
        'validated_relays': [],           # Authorized AND validation passed
        'misconfigured_relays': [],       # Authorized but validation failed (other errors)
        
        # === UNAUTHORIZED CLAIMS (fingerprint NOT in proof file) ===
        'unauthorized_claims': [],        # Claims with "fingerprint not found" error
        
        # === LEGACY (for backward compatibility) ===
        'unvalidated_relays': [],         # All relays that failed validation
        
        'validation_summary': {
            'total_relays': len(relays),
            'relays_with_aroi': 0,
            
            # Authorized relay counts (for status calculation)
            'authorized_count': 0,        # validated_count
            'misconfigured_count': 0,     # Other validation errors
            
            # Unauthorized claim count (excluded from status)
            'unauthorized_count': 0,      # "Fingerprint not found" errors
            
            'validation_rate': 0.0        # Based only on authorized relays
        },
        
        'validation_available': False,
        'show_detailed_errors': True
    }
    
    # ... processing logic ...
    
    for relay in relays:
        fingerprint = relay.get('fingerprint')
        aroi_domain = relay.get('aroi_domain', 'none')
        nickname = relay.get('nickname', 'Unnamed')
        
        # Skip relays without AROI setup
        if not aroi_domain or aroi_domain == 'none':
            continue
            
        result['has_aroi'] = True
        result['validation_summary']['relays_with_aroi'] += 1
        
        # Check validation result
        val_result = validation_map.get(fingerprint, {})
        
        if val_result.get('valid', False):
            # === AUTHORIZED & VALIDATED ===
            result['validated_relays'].append({
                'fingerprint': fingerprint,
                'nickname': nickname,
                'aroi_domain': aroi_domain,
                'proof_type': val_result.get('proof_type', 'unknown'),
                'proof_uri': val_result.get('proof_uri', ''),
                'is_authorized': True
            })
            result['validation_summary']['authorized_count'] += 1
        else:
            error = val_result.get('error', 'Unknown error')
            
            # Check if this is an UNAUTHORIZED CLAIM vs other error
            if 'fingerprint not found' in error.lower():
                # === UNAUTHORIZED CLAIM ===
                # Fingerprint not in proof file - domain owner did not authorize
                result['unauthorized_claims'].append({
                    'fingerprint': fingerprint,
                    'nickname': nickname,
                    'aroi_domain': aroi_domain,
                    'error': error,
                    'proof_type': val_result.get('proof_type', 'unknown'),
                    'is_unauthorized': True,
                    'first_seen': relay.get('first_seen', 'Unknown')
                })
                result['validation_summary']['unauthorized_count'] += 1
            else:
                # === AUTHORIZED BUT MISCONFIGURED ===
                # Other errors (DNS failure, SSL error, etc.) - likely operator's own relay
                result['misconfigured_relays'].append({
                    'fingerprint': fingerprint,
                    'nickname': nickname,
                    'aroi_domain': aroi_domain,
                    'error': error,
                    'proof_type': val_result.get('proof_type', 'unknown'),
                    'is_authorized': True  # Assumed authorized, just has config issues
                })
                result['validation_summary']['misconfigured_count'] += 1
            
            # Also add to legacy unvalidated_relays for backward compatibility
            result['unvalidated_relays'].append({...})
    
    # === CALCULATE STATUS BASED ONLY ON AUTHORIZED RELAYS ===
    authorized_total = (result['validation_summary']['authorized_count'] + 
                       result['validation_summary']['misconfigured_count'])
    
    if authorized_total == 0:
        if result['validation_summary']['unauthorized_count'] > 0:
            result['validation_status'] = 'no_authorized_relays'
        else:
            result['validation_status'] = 'no_aroi'
    elif result['validation_summary']['misconfigured_count'] == 0:
        result['validation_status'] = 'validated'  # All authorized relays pass
    else:
        result['validation_status'] = 'partially_validated'
    
    # Calculate validation rate based only on authorized relays
    if authorized_total > 0:
        result['validation_summary']['validation_rate'] = (
            result['validation_summary']['authorized_count'] / authorized_total * 100
        )
    
    return result
```

### 2. Template Changes: Summary Bullet in Header

**File:** `allium/templates/contact.html`

Add unauthorized claims alert in the Contact & Network Overview section:

```jinja2
{# In Contact & Network Overview section #}
<div style="padding: 15px; background-color: #f8f9fa; border-left: 4px solid #007bff; margin-bottom: 20px;">
    <h4 style="margin-top: 0; color: #495057;">📋 Contact & Network Overview</h4>
    
    <ul style="list-style-type: disc; padding-left: 20px; margin-bottom: 0;">
        {# AROI with validation badge - NOW BASED ON AUTHORIZED RELAYS ONLY #}
        {% if has_aroi_domain and contact_validation_status %}
        <li><strong>AROI:</strong> {{ aroi_domain|escape }}
            {# Show status based on authorized relays only #}
            {% set summary = contact_validation_status.validation_summary %}
            {% if contact_validation_status.validation_status == 'validated' %}
                <span style="color: #28a745; font-weight: bold;">
                    ✓ Validated ({{ summary.authorized_count }} relay{{ 's' if summary.authorized_count != 1 else '' }})
                </span>
            {% elif contact_validation_status.validation_status == 'partially_validated' %}
                <span style="color: #ffc107; font-weight: bold;">
                    ⚠ Partially Validated 
                    ({{ summary.authorized_count }}/{{ summary.authorized_count + summary.misconfigured_count }} authorized relays)
                </span>
            {% elif contact_validation_status.validation_status == 'no_authorized_relays' %}
                <span style="color: #dc3545; font-weight: bold;">
                    ❌ No Authorized Relays
                </span>
            {% endif %}
        </li>
        
        {# === NEW: UNAUTHORIZED CLAIMS ALERT === #}
        {% if summary.unauthorized_count > 0 %}
        <li style="background-color: #fff3cd; padding: 5px 10px; border-radius: 4px; margin-top: 5px;">
            <span style="color: #856404;">
                ⚠️ <strong>{{ summary.unauthorized_count }}</strong> unauthorized relay{{ 's' if summary.unauthorized_count != 1 else '' }} 
                claiming this domain
                <a href="#unauthorized-claims" style="color: #856404; margin-left: 5px;">(view details)</a>
            </span>
        </li>
        {% endif %}
        {% endif %}
        
        {# Rest of contact info... #}
    </ul>
</div>
```

### 3. Template Changes: Relay Table (Authorized Only)

**File:** `allium/templates/contact-relay-list.html`

Modify the relay table to show only authorized relays:

```jinja2
{# Section header showing authorized relay count #}
<h3 style="margin-top: 20px;">📡 Authorized Relays 
    {% if contact_validation_status %}
        ({{ contact_validation_status.validation_summary.authorized_count + 
            contact_validation_status.validation_summary.misconfigured_count }})
    {% else %}
        ({{ relay_subset|length }})
    {% endif %}
</h3>

<table class="table table-condensed">
    {# ... table headers ... #}
    <tbody>
        {# Filter to only authorized relays (validated + misconfigured) #}
        {% set authorized_fps = contact_validation_status.validated_fingerprints|default({}) %}
        {% set misconfigured_fps = contact_validation_status.misconfigured_fingerprints|default({}) %}
        {% set unauthorized_fps = contact_validation_status.unauthorized_fingerprints|default({}) %}
        
        {% for relay in relay_list %}
            {# Skip unauthorized claims in main table #}
            {% if relay['fingerprint'] not in unauthorized_fps %}
            <tr>
                <td>
                    {% if relay['running'] %}
                        <span class="circle circle-online" title="This relay is online"></span>
                    {% else %}
                        <span class="circle circle-offline" title="This relay is offline"></span>
                    {% endif %}
                    
                    {# Validation icon #}
                    {% if relay['fingerprint'] in authorized_fps %}
                        <span style="color: #28a745; margin-left: 4px;" 
                              title="AROI Validated: Fingerprint verified in proof file">✓</span>
                    {% elif relay['fingerprint'] in misconfigured_fps %}
                        <a href="#misconfigured-relays" 
                           style="color: #ffc107; margin-left: 4px; text-decoration: none;" 
                           title="AROI Configuration Issue: See details below">⚠</a>
                    {% endif %}
                </td>
                {# ... rest of relay columns ... #}
            </tr>
            {% endif %}
        {% endfor %}
    </tbody>
</table>
```

### 4. Template Changes: Unauthorized Claims Section

**File:** `allium/templates/macros.html`

Add a new macro for the unauthorized claims section:

```jinja2
{% macro unauthorized_claims_section(contact_validation_status, page_ctx) -%}
{% if contact_validation_status and contact_validation_status.unauthorized_claims|length > 0 %}
<div id="unauthorized-claims" style="margin-top: 30px; border: 2px dashed #dc3545; padding: 20px; border-radius: 8px;">
    <h3 style="color: #dc3545; margin-top: 0;">
        🚨 Unauthorized Claims ({{ contact_validation_status.unauthorized_claims|length }})
    </h3>
    
    <p style="color: #666; margin-bottom: 15px;">
        The following relays claim association with 
        <strong>{{ contact_validation_status.unauthorized_claims[0].aroi_domain|escape }}</strong> 
        but their fingerprints are <strong>NOT in the AROI proof file</strong>. This could indicate:
    </p>
    
    <ul style="color: #666; margin-bottom: 15px; padding-left: 20px;">
        <li><strong>Illegitimate claim:</strong> Someone is falsely claiming your domain identity</li>
        <li><strong>Your own relay:</strong> You haven't added this relay's fingerprint to your proof file yet</li>
    </ul>
    
    <table class="table table-condensed" style="background-color: #fff5f5;">
        <thead>
            <tr style="background-color: #f8d7da;">
                <th>Status</th>
                <th>Nickname</th>
                <th>Fingerprint</th>
                <th>Error Detail</th>
                <th>First Seen</th>
                <th>Action</th>
            </tr>
        </thead>
        <tbody>
            {% for claim in contact_validation_status.unauthorized_claims %}
            <tr>
                <td><span style="color: #dc3545; font-weight: bold;">🚫 Unauthorized</span></td>
                <td>{{ claim.nickname|escape }}</td>
                <td>
                    <code style="font-size: 11px; background-color: #f8f9fa; padding: 2px 4px;">
                        {{ claim.fingerprint[:16] }}...
                    </code>
                </td>
                <td style="font-size: 12px; color: #666;">
                    {{ claim.error|escape|truncate(50) }}
                </td>
                <td>{{ claim.first_seen|format_time_ago if claim.first_seen else 'Unknown' }}</td>
                <td>
                    <a href="{{ page_ctx.path_prefix }}relay/{{ claim.fingerprint }}/" 
                       title="View relay details to investigate this claim"
                       style="color: #007bff;">
                        Inspect →
                    </a>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    
    {# Help box for operators #}
    <div style="margin-top: 15px; padding: 12px; background-color: #e8f4fd; border-radius: 4px; border-left: 4px solid #007bff;">
        <strong>💡 If this is your relay:</strong><br>
        Add the fingerprint to your 
        <a href="https://nusenu.github.io/ContactInfo-Information-Sharing-Specification/" 
           target="_blank" style="color: #007bff;">AROI proof file</a> 
        to authorize it and remove it from this list.
        
        <div style="margin-top: 8px; font-size: 12px; color: #666;">
            <strong>DNS-RSA:</strong> Add TXT record: <code>_tor.&lt;fingerprint&gt;.{{ contact_validation_status.unauthorized_claims[0].aroi_domain|escape }}</code><br>
            <strong>URI-RSA:</strong> Add fingerprint to: <code>/.well-known/tor-relay/rsa-fingerprint.txt</code>
        </div>
    </div>
</div>
{% endif %}
{%- endmacro %}
```

### 5. Template Changes: Misconfigured Relays Section

For operator's own relays that have configuration issues (not unauthorized claims):

```jinja2
{% macro misconfigured_relays_section(contact_validation_status, page_ctx) -%}
{% if contact_validation_status and contact_validation_status.misconfigured_relays|length > 0 %}
<div id="misconfigured-relays" style="margin-top: 30px; border: 2px solid #ffc107; padding: 20px; border-radius: 8px;">
    <h3 style="color: #856404; margin-top: 0;">
        ⚠️ Your Relays with Configuration Issues 
        ({{ contact_validation_status.misconfigured_relays|length }})
    </h3>
    
    <p style="color: #666; margin-bottom: 15px;">
        These relays appear to be yours (AROI configured) but validation failed due to 
        configuration issues. Fix these to achieve full validation status:
    </p>
    
    <table class="table table-condensed" style="background-color: #fff8e1;">
        <thead>
            <tr style="background-color: #ffecb3;">
                <th>Status</th>
                <th>Nickname</th>
                <th>Proof Type</th>
                <th>Error</th>
                <th>Action</th>
            </tr>
        </thead>
        <tbody>
            {% for relay in contact_validation_status.misconfigured_relays %}
            <tr>
                <td><span style="color: #ffc107; font-weight: bold;">⚠ Config Issue</span></td>
                <td>
                    <a href="{{ page_ctx.path_prefix }}relay/{{ relay.fingerprint }}/">
                        {{ relay.nickname|escape }}
                    </a>
                </td>
                <td>{{ relay.proof_type }}</td>
                <td style="font-size: 12px; color: #dc3545;">{{ relay.error|escape }}</td>
                <td>
                    <a href="https://nusenu.github.io/ContactInfo-Information-Sharing-Specification/#troubleshooting" 
                       target="_blank">Fix Guide →</a>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endif %}
{%- endmacro %}
```

---

## How This Solves Both Scenarios

### Scenario A: Legitimate Operator

| Situation | Before | After |
|-----------|--------|-------|
| All relays validated | ✓ Validated (50 relays) | ✓ Validated (50 relays) |
| Some relays misconfigured | ⚠ Partially (45/50) | ⚠ Partially (45/50) - Config issues listed |
| Unauthorized claims exist | ⚠ Partially (50/53) ❌ | ✓ Validated (50 relays) + 3 unauthorized claims listed separately |

**Key improvement:** Unauthorized claims no longer degrade the operator's validation status.

### Scenario B: Illegitimate Claims

| Situation | Before | After |
|-----------|--------|-------|
| Pure attacker (no valid relays) | ❌ Unvalidated (0/5) | ❌ No Authorized Relays + 5 unauthorized claims |
| Mixed with real operator | Pollutes operator page | Clearly separated in "Unauthorized Claims" section |

**Key improvement:** Domain owners can clearly see which relays are unauthorized and investigate them.

---

## Handling Both Operator Preferences

### Preference 1: "Don't show illegitimate relays on my page"

**Solution:** Unauthorized relays are:
- **Excluded** from the main relay table
- **Excluded** from the validation status calculation
- **Excluded** from the relay count in the header

The operator's page shows only their authorized relays.

### Preference 2: "Show me who's claiming my domain so I can investigate"

**Solution:** Unauthorized relays are:
- **Always visible** in a clearly separated "Unauthorized Claims" section at the bottom (important information should not be hidden)
- **Actionable** with "Inspect" links to view relay details
- **Informative** with fingerprints and first-seen dates for investigation

---

## Summary: Impact on Both Metrics

### Metric 1: Overall AROI Validation Status

| Calculation | Before | After |
|-------------|--------|-------|
| Input | All relays claiming domain | Only authorized relays (fingerprint in proof) |
| `validated` | All relays pass | All **authorized** relays pass |
| `partially_validated` | Some pass, some fail | Some authorized relays have config issues |
| `unvalidated` | All fail | All authorized relays fail (config issues only) |
| `no_authorized_relays` | N/A | **NEW:** No relays in proof file, only unauthorized claims |

### Metric 2: Relay List Display

| Display Element | Before | After |
|-----------------|--------|-------|
| Main relay table | All relays claiming domain | **Only authorized relays** |
| Relay count in header | All relays | **Only authorized relays** |
| Unauthorized claims | Mixed in with warning icon | **Separate section at bottom** |
| Misconfigured relays | Mixed in with warning icon | **Separate section with fix guidance** |

---

## Implementation Checklist

### Phase 1: Backend Changes
- [ ] Update `get_contact_validation_status()` to separate authorized vs unauthorized
- [ ] Add `misconfigured_relays` list for authorized relays with config issues
- [ ] Add `unauthorized_claims` list for "fingerprint not found" errors
- [ ] Update validation status calculation to exclude unauthorized claims
- [ ] Add fingerprint sets for O(1) template lookups

### Phase 2: Template Changes
- [ ] Add unauthorized claims alert in Contact & Network Overview
- [ ] Filter main relay table to show only authorized relays
- [ ] Create `unauthorized_claims_section` macro (always visible)
- [ ] Create `misconfigured_relays_section` macro
- [ ] Update relay count in headers

### Phase 3: Testing
- [ ] Unit tests for new categorization logic
- [ ] Test with operators who have unauthorized claims
- [ ] Test with operators who have misconfigured relays
- [ ] Test with pure unauthorized claim scenarios
- [ ] Verify backward compatibility

---

## Files to Modify

1. **`allium/lib/aroi_validation.py`**
   - Update `get_contact_validation_status()` function
   - Add new categorization logic for authorized vs unauthorized

2. **`allium/templates/contact.html`**
   - Add unauthorized claims alert in header
   - Call new macros in `after_table` block

3. **`allium/templates/contact-relay-list.html`**
   - Filter relay table to exclude unauthorized claims
   - Update relay count in section header

4. **`allium/templates/macros.html`**
   - Add `unauthorized_claims_section` macro
   - Add `misconfigured_relays_section` macro
   - Update `aroi_validation_badge` macro

---

## Success Criteria

1. ✅ Operator's validation status based only on authorized relays
2. ✅ Unauthorized claims clearly separated from main relay list
3. ✅ Summary bullet shows unauthorized claim count at top of page
4. ✅ Operators can investigate unauthorized claims via "Inspect" links
5. ✅ Misconfigured relays (operator's own) shown with actionable guidance
6. ✅ Unauthorized claims section always visible (important security information)
7. ✅ Backward compatibility maintained for existing pages

---

## Timeline Estimate

- **Phase 1 (Backend):** 3-4 hours
- **Phase 2 (Templates):** 4-5 hours
- **Phase 3 (Testing):** 2-3 hours

**Total:** ~10-12 hours development time

---

## Related Documentation

- **Current Implementation:** `allium/lib/aroi_validation.py`
- **AROI Spec:** https://nusenu.github.io/ContactInfo-Information-Sharing-Specification/
- **Validation API:** https://aroivalidator.1aeo.com/latest.json
- **Related Proposals:** 
  - `docs/features/planned/aroi-validation-integration-plan.md`
  - `docs/features/planned/aroi-categorization-display.md`

---

**Last Updated:** January 6, 2026  
**Author:** Allium Development Team
