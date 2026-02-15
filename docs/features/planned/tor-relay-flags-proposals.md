# Tor Relay Flags: Implementation Proposals

5 detailed proposals for extending the Eligibility Flag Vote Details table to cover all major Tor relay flags from the official dir-spec.

**Reference:** https://spec.torproject.org/dir-spec/ (Section 3.4.2)

**Related Documents:**
- [Relay Page Layout Consolidated](relay-page-layout-consolidated.md) - Main UI/UX plan
- [Tor Relay Flags Analysis](tor-relay-flags-analysis.md) - Complete flag specification reference

---

## 1. Executive Summary

### 1.1 Purpose and Goals

This document proposes extending the Eligibility Flag Vote Details table to provide operators with complete visibility into flag requirements. Goals:

1. **Complete flag coverage** - Add eligibility tracking for Exit, Running, Valid, V2Dir, and MiddleOnly
2. **Actionable diagnostics** - Help operators understand why they have/don't have flags
3. **Consistent format** - Follow existing table structure and styling patterns
4. **Minimal backend changes** - Leverage existing data sources where possible

### 1.2 Implementation Status Tracker

> **Last Updated:** 2026-02-15

#### Legend
- ✅ **Fully Implemented** - Code complete and deployed
- 🔶 **Partially Implemented** - Some parts done, others pending
- ⏳ **Not Started** - Planning complete, implementation pending

---

| Proposal | Flag | Status | Location | Notes |
|----------|------|--------|----------|-------|
| 1 | Exit | ✅ Implemented | `collector_fetcher.py`, `consensus_evaluation.py`, `relays.py`, `relay-info.html` | **Priority 1** — Guard-parity implementation across all 6 page layers. |
| 2 | Running | ⏳ Not Started | `consensus_evaluation.py` | **Priority 4** — Already extensively shown in Health Status, Summary, Per-Auth tables (3+ places). Low remaining gap. |
| 3 | Valid | ⏳ Not Started | `consensus_evaluation.py` | **Priority 5** — Already extensively shown in Health Status, Summary, Per-Auth tables (3+ places). Low remaining gap. |
| 4 | V2Dir | ⏳ Not Started | `consensus_evaluation.py` | **Priority 3** — Currently only shown as Guard prereq row. Medium gap. |
| 5 | MiddleOnly | ⏳ Not Started | `consensus_evaluation.py` | **Priority 2** — Zero presence in codebase. High gap for affected operators. |

---

### 1.3 Implementation Priority (Revised 2026-02-15)

> **Priority Revision Note:** The original priority (Running first) was based on theoretical operator value. Since then, the relay page has been significantly enhanced with Health Status grid, Summary table, and Per-Authority Details table — all of which already show Running, Valid, and V2Dir extensively. The revised priority is based on **actual remaining gap size** rather than theoretical value.

| Priority | Proposal | Flag | Effort | Gap Size | Rationale |
|----------|----------|------|--------|----------|-----------|
| **1** | **Proposal 1: Exit** | Exit | Medium | **Large** | **Biggest gap**: exit operators have no eligibility breakdown anywhere on the page. Exit policy shown in dt/dd section but not integrated into the eligibility table, Summary table, or Per-Auth table. Detailed Guard-parity plan below. |
| **2** | **Proposal 5: MiddleOnly** | MiddleOnly | Low | **Large** | **Zero presence**: restricted operators have no way to discover that their relay has MiddleOnly flag. `grep` for MiddleOnly returns zero results in Python files. |
| **3** | **Proposal 4: V2Dir** | V2Dir | Low | **Medium** | Only shown as Guard prerequisite row in eligibility table + vote count in Eligible Flags row. No standalone eligibility information with DirPort/tunnelled-dir-server details. |
| **4** | **Proposal 2: Running** | Running | Low | **Small** | Already shown in Health Status (consensus + vote count), Summary table (Running row with IPv4 details), and Per-Authority Details (Running + v4/v6 columns). Adding to eligibility table would be redundant but consistent. |
| **5** | **Proposal 3: Valid** | Valid | Low | **Small** | Already shown in Health Status (version + recommended status), Summary table (Valid row), and Per-Authority Details (Valid column + version info). Adding to eligibility table would be redundant but consistent. |

**What Changed (2026-01-25 → 2026-02-15):**
- Running dropped from Priority 1 → 4 (now extensively covered in 3+ page sections)
- Valid dropped from Priority 3 → 5 (same reason)
- Exit rose from Priority 2 → 1 (biggest remaining gap for operators)
- MiddleOnly rose from Priority 5 → 2 (zero presence is worse than partial coverage)
- V2Dir stayed at Priority 3 (medium gap, only shown as Guard prereq)

---

## 2. Current Implementation Reference

> **Last Updated:** 2026-02-15
>
> **Architecture Note:** As of 2026-02-15, `relays.py` was refactored from a ~5,900-line
> monolithic file into 8 focused modules. The consensus evaluation pipeline
> (`collector_fetcher.py`, `consensus_evaluation.py`) was **not** affected — all flag
> eligibility code remains in the same files. The call to `format_relay_consensus_evaluation()`
> remains in `relays.py` (now ~1,100 lines). The extracted modules are:
>
> | Module | Lines | Purpose |
> |--------|-------|---------|
> | `relays.py` | ~1,100 | Core relay class, Onionoo fetch, consensus evaluation call |
> | `page_writer.py` | ~1,020 | HTML page generation |
> | `network_health.py` | ~1,300 | Network statistics and health metrics |
> | `operator_analysis.py` | ~1,350 | Operator/contact analysis |
> | `categorization.py` | ~750 | Relay categorization |
> | `flag_analysis.py` | ~380 | Flag uptime analysis |
> | `ip_utils.py` | ~94 | IP address utilities |
> | `time_utils.py` | ~118 | Time formatting utilities |

### 2.1 Existing Table Structure

The Eligibility Flag Vote Details table in `relay-info.html` currently tracks:

| Flag | Metrics | Rows |
|------|---------|------|
| Fast | Speed | 1 |
| Stable | MTBF, Uptime | 2 |
| HSDir | Prereq: Stable, Prereq: Fast, WFU, Time Known | 4 |
| Guard | Prereq: Fast, Prereq: Stable, Prereq: V2Dir, WFU, Time Known, Bandwidth | 6 |
| Exit | Exit Policy (ports 80+443) | 1 |

**Total Current Rows:** 14

### 2.2 Row Data Structure

Each row in `_format_flag_requirements_table()` uses this structure:

```python
{
    'flag': str,              # Flag name (e.g., 'Guard')
    'flag_tooltip': str,      # Full flag description
    'flag_color': str,        # CSS color for flag cell
    'metric': str,            # Metric name (e.g., 'WFU')
    'metric_tooltip': str,    # Metric description
    'value': str,             # Relay's value (e.g., '99.2%')
    'value_source': str,      # 'relay' or 'da' 
    'threshold': str,         # Required threshold (e.g., '≥98%')
    'status': str,            # 'meets', 'below', or 'partial'
    'status_text': str,       # Human-readable status
    'status_color': str,      # CSS color for status
    'status_tooltip': str,    # Status explanation
    'rowspan': int,           # Number of rows to span (0 if continuation)
}
```

### 2.3 Status Colors Reference

```python
STATUS_COLORS = {
    'meets': '#28a745',   # Green
    'below': '#dc3545',   # Red
    'partial': '#ffc107', # Yellow/amber
}
```

### 2.4 Value Source Annotations

- `(R)` - Value from relay descriptor/Onionoo
- `(DA)` - Value from Directory Authority votes

---

## 3. Proposal 1: Exit Flag Eligibility (Guard-Parity Implementation)

> **Priority:** 1 (Highest)
> **Status:** ⏳ Not Started
> **Last Updated:** 2026-02-15
> **Effort:** Medium (6 layers of changes following established Guard pattern)

### 3.1 Rationale

Exit is one of the most important flags but currently has **the largest gap** of any flag on the relay page:
- No eligibility breakdown in the Eligibility Flag Vote Details table
- No row in the Summary table
- No dedicated column in the Per-Authority Details table
- `_analyze_flag_eligibility()` in collector_fetcher doesn't track Exit
- `_format_flag_summary()` doesn't process Exit (so the "Eligible Flags" row shows incorrect data)

Exit operators rely on the Exit flag for their relay's purpose. They need clear, structured eligibility information matching the quality of Guard/Stable/Fast/HSDir tracking.

### 3.2 Requirements (from dir-spec)

```
Exit flag requires:
- Allows exits to at least one /8 address space on port 80
- Allows exits to at least one /8 address space on port 443
```

**Historical Note:** Before Tor 0.3.2, required exits to at least 2 of: 80, 443, 6667.

### 3.3 Data Sources

| Data | Source | Field | Usage |
|------|--------|-------|-------|
| Exit policy summary | Onionoo | `exit_policy_summary` | Port 80/443 check |
| Exit policy (full) | Onionoo | `exit_policy` | Detailed rule analysis |
| IPv6 exit policy | Onionoo | `exit_policy_v6_summary` | IPv6 exit info |
| Exit flag per authority | CollecTor votes | `'Exit' in auth_flags` | Per-authority assignment |
| Exit addresses | Onionoo | `exit_addresses` | Display |
| Exit probability | Onionoo | `exit_probability` | Display |

**Key Difference from Guard:** Guard has numeric thresholds (WFU, TK, BW) from `flag-thresholds` in each CollecTor vote. Exit has **no numeric thresholds** — it's purely policy-based (ports 80+443 with ≥1 /8). So Exit tracking is simpler per-authority (flag assigned yes/no) but needs relay-side policy analysis.

### 3.4 Guard Pattern Reference (What We're Following)

The Guard flag is tracked across 6 layers of the relay page. Exit must follow the same pattern:

| Layer | Guard Implementation | Exit Equivalent |
|-------|---------------------|-----------------|
| **1. collector_fetcher** | `eligibility['guard']` with eligible_count, assigned_count, per-auth details (WFU/TK/BW comparisons) | `eligibility['exit']` with eligible_count, assigned_count, per-auth details (flag assigned yes/no) |
| **2. _format_flag_summary** | Processes `flag_eligibility['guard']` → `summary['guard']` with status_class | Process `flag_eligibility['exit']` → `summary['exit']` with status_class |
| **3. _format_relay_values** | `guard_bw_*`, `guard_prereq_*_count`, `wfu_*`, `tk_*` | `exit_allows_80/443`, `exit_eligible`, `exit_policy_display`, `exit_assigned_count` |
| **4. _format_flag_requirements_table** | 6 rows (3 prereqs + WFU + TK + BW) | 1 row (Exit Policy) |
| **5. Summary table** | 3 rows (Guard WFU, Guard TK, Guard BW) | 1 row (Exit Policy) |
| **6. Per-Auth table** | 3 columns (Guard BW, Guard WFU, Guard TK) | 1 column (Exit flag yes/no per authority) |

### 3.5 Implementation: Layer 1 — collector_fetcher._analyze_flag_eligibility()

**File:** `allium/lib/consensus/collector_fetcher.py`

**What to change:** Add `exit` to the eligibility dict and track per-authority Exit flag assignment.

```python
# In _analyze_flag_eligibility(), add to eligibility dict initialization:
eligibility = {
    'guard': {'eligible_count': 0, 'assigned_count': 0, 'details': []},
    'stable': {'eligible_count': 0, 'assigned_count': 0, 'details': []},
    'fast': {'eligible_count': 0, 'assigned_count': 0, 'details': []},
    'hsdir': {'eligible_count': 0, 'assigned_count': 0, 'details': []},
    'exit': {'eligible_count': 0, 'assigned_count': 0, 'details': []},  # NEW
}

# In the per-authority loop, after HSDir processing, add:

# Exit flag tracking
# Per dir-spec: Exit requires allowing exits to ≥1 /8 on ports 80 AND 443
# Unlike Guard/Stable/Fast/HSDir, Exit has no numeric thresholds in flag-thresholds.
# We track per-authority flag assignment since the policy check happens authority-side.
has_exit_flag = 'Exit' in auth_flags
if has_exit_flag:
    eligibility['exit']['eligible_count'] += 1
    eligibility['exit']['assigned_count'] += 1

eligibility['exit']['details'].append({
    'authority': auth_name,
    'eligible': has_exit_flag,
    'assigned': has_exit_flag,
})
```

### 3.6 Implementation: Layer 2 — consensus_evaluation._format_flag_summary()

**File:** `allium/lib/consensus/consensus_evaluation.py`

**What to change:** Add `'exit'` to the flag iteration list so `flag_summary.exit` is populated.

```python
# Change:
for flag_name in ['fast', 'stable', 'hsdir', 'guard']:
# To:
for flag_name in ['fast', 'stable', 'hsdir', 'guard', 'exit']:
```

**Impact:** This fixes the "Eligible Flags" row which currently calls `add_eligibility_flag('exit')` but gets `None` because `flag_summary.exit` doesn't exist. After this change, Exit will show the correct authority count in the Eligible Flags display.

### 3.7 Implementation: Layer 3 — consensus_evaluation._format_relay_values()

**File:** `allium/lib/consensus/consensus_evaluation.py`

**What to change:** Add `exit_policy_summary` parameter and compute exit-specific relay values.

**Step 1:** Update function signature for `format_relay_consensus_evaluation()`:

```python
def format_relay_consensus_evaluation(
    evaluation, flag_thresholds=None, current_flags=None,
    observed_bandwidth=0, use_bits=False, relay_uptime=None,
    version=None, recommended_version=None,
    exit_policy_summary=None,  # NEW: Onionoo exit policy data
):
```

**Step 2:** Pass `exit_policy_summary` into `_format_relay_values()`:

```python
'relay_values': _format_relay_values(
    evaluation, flag_thresholds, observed_bandwidth, use_bits, relay_uptime,
    exit_policy_summary=exit_policy_summary,  # NEW
),
```

**Step 3:** Add exit policy analysis to `_format_relay_values()`:

```python
def _format_relay_values(consensus_data, flag_thresholds=None,
                         observed_bandwidth=0, use_bits=False,
                         relay_uptime=None, exit_policy_summary=None):
    # ... existing code ...
    
    # Exit policy analysis (from Onionoo exit_policy_summary)
    exit_analysis = _analyze_exit_policy(exit_policy_summary)
    
    return {
        # ... existing keys ...
        
        # Exit policy values (NEW)
        'exit_allows_80': exit_analysis['allows_80'],
        'exit_allows_443': exit_analysis['allows_443'],
        'exit_eligible': exit_analysis['eligible'],
        'exit_policy_display': exit_analysis['display'],
        'exit_assigned_count': flag_eligibility.get('exit', {}).get('assigned_count', 0),
    }
```

**Step 4:** Add exit policy analysis helper function:

```python
def _analyze_exit_policy(exit_policy_summary: dict) -> dict:
    """Analyze exit policy for Exit flag eligibility.
    
    Per Tor dir-spec Section 3.4.2: Exit flag requires allowing exits to at least
    one /8 address space on BOTH port 80 AND port 443.
    
    Args:
        exit_policy_summary: From Onionoo relay['exit_policy_summary']
            Format: {'accept': ['80', '443', '6667'], 'reject': [...]}
            or: {'reject': ['25', '119', ...]}  (implicit accept-all minus rejects)
    
    Returns:
        dict with: allows_80, allows_443, eligible, display
    """
    if not exit_policy_summary:
        return {'allows_80': False, 'allows_443': False,
                'eligible': False, 'display': 'No exit policy'}
    
    accept_rules = exit_policy_summary.get('accept', [])
    reject_rules = exit_policy_summary.get('reject', [])
    
    # Onionoo exit_policy_summary format:
    # - If 'accept' key exists: only listed ports are allowed
    # - If only 'reject' key exists: all ports allowed EXCEPT listed ones
    if accept_rules:
        allows_80 = _port_in_rules(accept_rules, 80)
        allows_443 = _port_in_rules(accept_rules, 443)
    elif reject_rules:
        allows_80 = not _port_in_rules(reject_rules, 80)
        allows_443 = not _port_in_rules(reject_rules, 443)
    else:
        allows_80 = False
        allows_443 = False
    
    eligible = allows_80 and allows_443
    
    p80 = 'Yes' if allows_80 else 'No'
    p443 = 'Yes' if allows_443 else 'No'
    display = f"Port 80: {p80} | Port 443: {p443}"
    
    return {
        'allows_80': allows_80,
        'allows_443': allows_443,
        'eligible': eligible,
        'display': display,
    }


def _port_in_rules(rules: list, port: int) -> bool:
    """Check if a port is covered by a list of exit policy rules.
    
    Onionoo exit_policy_summary rules are strings like:
    '80', '443', '80-443', '1-65535'
    """
    for rule in rules:
        if '-' in str(rule):
            try:
                start, end = str(rule).split('-')
                if int(start) <= port <= int(end):
                    return True
            except (ValueError, IndexError):
                continue
        else:
            try:
                if int(rule) == port:
                    return True
            except ValueError:
                continue
    return False
```

### 3.8 Implementation: Layer 4 — consensus_evaluation._format_flag_requirements_table()

**File:** `allium/lib/consensus/consensus_evaluation.py`

**What to change:** Add Exit row after the Guard rows, before `return rows`.

```python
# ========== Exit flag (1 row) ==========
# Per Tor dir-spec: Exit requires allowing exits to ≥1 /8 on ports 80 AND 443
# Unlike Guard (6 rows with prereqs + metrics), Exit has 1 row (policy-based)
exit_color = get_flag_color('exit')
exit_tooltip = FLAG_TOOLTIPS['exit']

exit_allows_80 = rv.get('exit_allows_80', False)
exit_allows_443 = rv.get('exit_allows_443', False)
exit_eligible = rv.get('exit_eligible', False)

if exit_eligible:
    exit_status = 'meets'
    exit_extra = ''
elif exit_allows_80 or exit_allows_443:
    exit_status = 'partial'
    port = '80' if exit_allows_80 else '443'
    exit_extra = f' (only port {port})'
else:
    exit_status = 'below'
    exit_extra = ''

rows.append(_make_row(
    'Exit', exit_tooltip, exit_color,
    'Exit Policy', METRIC_TOOLTIPS['policy_exit'],
    _format_relay_value_html(rv.get('exit_policy_display', 'N/A')),
    'relay',
    'Allows ≥1 /8 on ports 80 AND 443',
    exit_status,
    _get_status_text(exit_status, exit_extra),
    rowspan=1,
))
```

**Add to METRIC_TOOLTIPS dict:**
```python
'policy_exit': "Exit policy must allow traffic to at least one /8 address space "
               "on both port 80 AND port 443. Source: Onionoo exit_policy_summary.",
```

**Resulting table row:**

| Flag | Metric | Status | Relay Value | Threshold Required |
|------|--------|--------|-------------|-------------------|
| **Exit** | Exit Policy | Meets | **Port 80: Yes \| Port 443: Yes** (R) | Allows ≥1 /8 on ports 80 AND 443 |

### 3.9 Implementation: Layer 5 — Summary Table (relay-info.html)

**File:** `allium/templates/relay-info.html`

**What to change:** Add Exit Policy row to the Summary table. Place it after the "Fast Speed" row and before the "HSDir WFU" row (matching the flag order: Fast → Stable → HSDir → Guard → Exit).

**Placement rationale:** The Summary table currently follows this order:
1. In Consensus
2. Running
3. Valid
4. Consensus Weight
5. Guard WFU / Guard TK / Guard BW
6. Stable Uptime / Stable MTBF
7. Fast Speed
8. HSDir WFU / HSDir TK
9. IPv6 Reachable (conditional)

Exit should be inserted at position 8 (before HSDir), or at the end before IPv6:

```html
<tr>
    <td title="Source: Onionoo | Field: exit_policy_summary | Exit flag requires allowing exits to ≥1 /8 address space on both ports 80 and 443.">
        Exit Policy <span style="color: #6c757d; font-size: 10px;">(Relay Reported)</span>
    </td>
    <td title="Source: Onionoo | Field: exit_policy_summary | Relay's exit policy summary">
        {{ rv.exit_policy_display }}
    </td>
    <td title="Tor dir-spec Section 3.4.2: Exit requires exits to ≥1 /8 on ports 80 AND 443">
        Allows ≥1 /8 on ports 80 AND 443
    </td>
    <td>
        {% if rv.exit_eligible %}
            <span style="color: #28a745; font-weight: bold;">EXIT ELIGIBLE</span>
        {% elif rv.exit_allows_80 or rv.exit_allows_443 %}
            <span style="color: #ffc107; font-weight: bold;">
                PARTIAL - only port {% if rv.exit_allows_80 %}80{% else %}443{% endif %}
            </span>
        {% else %}
            <span style="color: #dc3545; font-weight: bold;">NON-EXIT (no port 80+443)</span>
        {% endif %}
    </td>
</tr>
```

### 3.10 Implementation: Layer 6 — Per-Authority Details Table (relay-info.html)

**File:** `allium/templates/relay-info.html`

**What to change:** Add a dedicated "Exit" column to the Per-Authority Details table. Place it after the "Valid" column (group all flag-assignment columns together: Running, Valid, **Exit**).

**Column header:**
```html
<th title="Source: CollecTor | File: vote | Field: 's' line contains 'Exit' | Authority assigned Exit flag based on relay's exit policy allowing ≥1 /8 on ports 80+443">Exit</th>
```

**Column body (per-authority row):**
```html
<td>
    {% if vote.voted and vote.flags %}
        {% if 'Exit' in vote.flags %}
            <span style="color: #28a745;" title="Authority assigned Exit flag - relay's exit policy meets requirements">Yes</span>
        {% else %}
            <span style="color: #6c757d;" title="Authority did not assign Exit flag - relay's exit policy does not meet Exit requirements (need ≥1 /8 on ports 80+443)">No</span>
        {% endif %}
    {% else %}
        <span style="color: #6c757d;">—</span>
    {% endif %}
</td>
```

### 3.11 Implementation: Caller Changes (relays.py)

**File:** `allium/lib/relays.py`

**What to change:** Pass `exit_policy_summary` to `format_relay_consensus_evaluation()`.

```python
# In the relay processing loop where format_relay_consensus_evaluation is called:
exit_policy_summary = relay.get('exit_policy_summary', {})
formatted_consensus_evaluation = format_relay_consensus_evaluation(
    raw_consensus_evaluation, flag_thresholds, current_flags, observed_bandwidth,
    use_bits=self.use_bits,
    relay_uptime=relay_uptime,
    version=version,
    recommended_version=recommended_version,
    exit_policy_summary=exit_policy_summary,  # NEW: pass exit policy for Exit flag analysis
)
```

### 3.12 Complete Data Flow (Exit vs Guard Comparison)

```
Guard Data Flow:
  CollecTor vote files
    → collector_fetcher._analyze_flag_eligibility() → eligibility['guard'] (wfu/tk/bw details)
    → consensus_evaluation._format_relay_values() → guard_bw_*, guard_prereq_*, wfu_*, tk_*
    → consensus_evaluation._format_flag_requirements_table() → 6 table rows
    → relay-info.html: Eligible Flags row + Eligibility table + Summary table + Per-Auth table

Exit Data Flow (NEW):
  Onionoo API (exit_policy_summary) + CollecTor vote files
    → relays.py passes exit_policy_summary to format_relay_consensus_evaluation()
    → collector_fetcher._analyze_flag_eligibility() → eligibility['exit'] (assigned flag tracking)
    → consensus_evaluation._format_relay_values() → exit_allows_80/443, exit_eligible, exit_policy_display
    → consensus_evaluation._format_flag_requirements_table() → 1 table row
    → relay-info.html: Eligible Flags row + Eligibility table + Summary table + Per-Auth table
```

### 3.13 Complete Table Structure After Implementation

After implementing Exit, the Eligibility Flag Vote Details table will have:

```
╔═══════════════╤════════════════════╤════════╤══════════════════════════╤═════════════════════════════╗
║ Flag          │ Metric             │ Status │ Relay Value              │ Threshold Required          ║
╠═══════════════╪════════════════════╪════════╪══════════════════════════╪═════════════════════════════╣
║ Fast          │ Speed              │ Meets  │ 15.2 MB/s (R)            │ ≥100 KB/s OR top 7/8        ║
╟───────────────┼────────────────────┼────────┼──────────────────────────┼─────────────────────────────╢
║ Stable        │ MTBF               │ Meets  │ 28.5 days (DA)           │ ≥19-30d (varies)            ║
║               │ Uptime             │ Meets  │ 45.3 days (R)            │ ≥19-30d (varies)            ║
╟───────────────┼────────────────────┼────────┼──────────────────────────┼─────────────────────────────╢
║ HSDir         │ Prereq: Stable     │ Meets  │ 9/9 authorities          │ ≥5/9 authorities            ║
║               │ Prereq: Fast       │ Meets  │ 9/9 authorities          │ ≥5/9 authorities            ║
║               │ WFU                │ Meets  │ 99.2% (DA)               │ ≥98%                        ║
║               │ Time Known         │ Meets  │ 45.3 days (DA)           │ ≥25h (most)                 ║
╟───────────────┼────────────────────┼────────┼──────────────────────────┼─────────────────────────────╢
║ Guard         │ Prereq: Fast       │ Meets  │ 9/9 authorities          │ ≥5/9 authorities            ║
║               │ Prereq: Stable     │ Meets  │ 9/9 authorities          │ ≥5/9 authorities            ║
║               │ Prereq: V2Dir      │ Meets  │ 9/9 authorities          │ ≥5/9 authorities            ║
║               │ WFU                │ Meets  │ 99.2% (DA)               │ ≥98% (all authorities)      ║
║               │ Time Known         │ Meets  │ 45.3 days (DA)           │ ≥8 days (all authorities)   ║
║               │ Bandwidth          │ Meets  │ 15.2 MB/s (R)            │ ≥2 MB/s OR top 25%          ║
╟───────────────┼────────────────────┼────────┼──────────────────────────┼─────────────────────────────╢
║ Exit          │ Exit Policy        │ Meets  │ Port 80: Yes | 443: Yes  │ Allows ≥1 /8 on 80+443     ║  ← NEW
╚═══════════════╧════════════════════╧════════╧══════════════════════════╧═════════════════════════════╝
```

**Row count:** 13 → 14 (adding 1 Exit row)

### 3.14 Files to Modify (Complete List)

| File | Layer | Changes |
|------|-------|---------|
| `allium/lib/consensus/collector_fetcher.py` | 1 (Backend) | Add `eligibility['exit']` with assigned_count tracking in `_analyze_flag_eligibility()` |
| `allium/lib/consensus/consensus_evaluation.py` | 2 (Backend) | Add `'exit'` to flag iteration in `_format_flag_summary()` |
| `allium/lib/consensus/consensus_evaluation.py` | 3 (Backend) | Add `exit_policy_summary` param + `_analyze_exit_policy()` + exit relay_values in `_format_relay_values()` |
| `allium/lib/consensus/consensus_evaluation.py` | 4 (Backend) | Add Exit row in `_format_flag_requirements_table()` + `METRIC_TOOLTIPS['policy_exit']` |
| `allium/lib/relays.py` | Caller | Pass `exit_policy_summary` to `format_relay_consensus_evaluation()` |
| `allium/templates/relay-info.html` | 5 (Template) | Add Exit Policy row to Summary table |
| `allium/templates/relay-info.html` | 6 (Template) | Add Exit column to Per-Authority Details table (header + body) |

### 3.15 Testing Checklist

#### Exit Relay (has Exit flag)
- [ ] Eligible Flags row shows correct Exit count (X/9) with green color
- [ ] Eligibility table shows Exit row with "Port 80: Yes | Port 443: Yes" and green "Meets"
- [ ] Summary table shows Exit Policy row with green "EXIT ELIGIBLE"
- [ ] Per-Auth table shows Exit column with green "Yes" for authorities that assigned Exit

#### Non-Exit Relay (no Exit flag)
- [ ] Eligible Flags row shows Exit count (0/9) with red color
- [ ] Eligibility table shows Exit row with "Port 80: No | Port 443: No" and red "Below"
- [ ] Summary table shows Exit Policy row with red "NON-EXIT"
- [ ] Per-Auth table shows Exit column with grey "No" for all authorities

#### Partial Exit (allows 80 but not 443, or vice versa)
- [ ] Eligibility table shows yellow "Partial" status with port details
- [ ] Summary table shows yellow "PARTIAL" status

#### Edge Cases
- [ ] Relay with `exit_policy_summary: {}` (empty) — shows "No exit policy"
- [ ] Relay with `exit_policy_summary: {'reject': ['25', '119']}` — correctly detects 80+443 as allowed
- [ ] Relay with `exit_policy_summary: {'accept': ['80-443']}` — correctly detects range coverage
- [ ] Relay with `exit_policy_summary: {'accept': ['1-65535']}` — correctly detects full coverage

---

## 4. Proposal 2: Running/Reachability Flag Details

### 4.1 Rationale

Running is the core flag determining if a relay is in consensus. Currently we show vote counts but not the detailed reachability breakdown that helps operators diagnose connectivity issues.

### 4.2 Requirements (from dir-spec)

```
Running flag requires:
- Authority successfully connected within last 45 minutes
- Must pass reachability on ALL published ORPorts:
  * IPv4 ORPort (required)
  * IPv6 ORPort (if advertised AND authority tests IPv6)
```

### 4.3 Data Sources

| Data | Source | Field |
|------|--------|-------|
| IPv4 reachability | CollecTor votes | Per-authority Running votes |
| IPv6 reachability | CollecTor votes | Per-authority vote flags |
| Has IPv6 | Onionoo | `or_addresses` (check for IPv6) |

### 4.4 Implementation

Add to `_format_flag_requirements_table()` in `consensus_evaluation.py`:

```python
def _add_running_flag_rows(self, rows, relay, rv, authority_data):
    """Add Running flag eligibility rows to the table."""
    
    running_color = self._get_flag_color('running', relay.get('flags', []))
    
    # Calculate IPv4 reachability from authority votes
    ipv4_reachable = rv.get('running_votes', 0)
    total_authorities = rv.get('total_authorities', 9)
    majority_required = (total_authorities // 2) + 1
    
    # Check if relay has IPv6
    or_addresses = relay.get('or_addresses', [])
    has_ipv6 = any(':' in addr and not addr.startswith('[') or 
                   addr.startswith('[') for addr in or_addresses)
    
    # Determine rowspan (1 if no IPv6, 2 if has IPv6)
    rowspan = 2 if has_ipv6 else 1
    
    # IPv4 row
    ipv4_status = 'meets' if ipv4_reachable >= majority_required else 'below'
    rows.append({
        'flag': 'Running',
        'flag_tooltip': "Relay is reachable: Authority connected within "
                       "last 45 minutes on all published ORPorts.",
        'flag_color': running_color,
        'metric': 'IPv4 Reachability',
        'metric_tooltip': "Authority must successfully connect to relay's "
                         "IPv4 ORPort within 45 minutes.",
        'value': f"{ipv4_reachable}/{total_authorities} authorities reached",
        'value_source': 'da',
        'threshold': f'≥{majority_required}/{total_authorities} authorities (majority)',
        'status': ipv4_status,
        'status_text': 'Reachable' if ipv4_status == 'meets' else 'Unreachable',
        'status_color': STATUS_COLORS[ipv4_status],
        'status_tooltip': RUNNING_STATUS_TOOLTIPS[ipv4_status],
        'rowspan': rowspan,
    })
    
    # IPv6 row (if relay has IPv6)
    if has_ipv6:
        # Count IPv6 testing authorities (those with AuthDirHasIPv6Connectivity)
        ipv6_tested = rv.get('ipv6_tested_count', 0)
        ipv6_reachable = rv.get('ipv6_reachable_count', 0)
        
        # IPv6 is optional enhancement, not required for Running
        ipv6_status = 'meets' if ipv6_reachable > 0 else 'partial'
        
        rows.append({
            'flag': 'Running',
            'flag_tooltip': '',  # Empty - using rowspan
            'flag_color': running_color,
            'metric': 'IPv6 Reachability',
            'metric_tooltip': "IPv6 testing by authorities with "
                             "AuthDirHasIPv6Connectivity enabled.",
            'value': f"{ipv6_reachable}/{ipv6_tested} tested authorities reached",
            'value_source': 'da',
            'threshold': 'Optional (enhances routing)',
            'status': ipv6_status,
            'status_text': 'Reachable' if ipv6_status == 'meets' else 'Partial/None',
            'status_color': STATUS_COLORS[ipv6_status],
            'status_tooltip': IPV6_STATUS_TOOLTIPS.get(ipv6_status, ''),
            'rowspan': 0,  # Continuation row
        })
```

### 4.5 Table Row Preview

| Flag | Metric | Status | Relay Value | Threshold Required |
|------|--------|--------|-------------|-------------------|
| **Running** | IPv4 Reachability | Meets | 9/9 authorities reached (DA) | ≥5/9 authorities (majority) |
| | IPv6 Reachability | Meets | 7/7 tested authorities reached (DA) | Optional (enhances routing) |

### 4.6 Files to Modify

| File | Changes |
|------|---------|
| `allium/lib/consensus/consensus_evaluation.py` | Add `_add_running_flag_rows()` method |
| `allium/lib/consensus/consensus_evaluation.py` | Add IPv6 reachability counting logic |

---

## 5. Proposal 3: Valid Flag with Version Check

### 5.1 Rationale

Valid depends on Tor version and blacklist status. Operators should be able to see if their version is considered "broken" by authorities.

### 5.2 Requirements (from dir-spec)

```
Valid flag requires:
- Running a Tor version NOT known to be broken
- NOT blacklisted as suspicious by the authority
- Has valid descriptor with acceptable address
```

### 5.3 Data Sources

| Data | Source | Onionoo Field |
|------|--------|---------------|
| Tor version | Onionoo | `version` |
| Version status | Onionoo | `version_status` (recommended/obsolete/etc) |
| Recommended | Onionoo | `recommended_version` (boolean) |

### 5.4 Implementation

Add to `_format_flag_requirements_table()` in `consensus_evaluation.py`:

```python
def _add_valid_flag_rows(self, rows, relay, rv):
    """Add Valid flag eligibility rows to the table."""
    
    valid_color = self._get_flag_color('valid', relay.get('flags', []))
    
    # Get version information
    version = relay.get('version', 'Unknown')
    version_status = relay.get('version_status', 'unknown')
    recommended = relay.get('recommended_version', True)
    
    # Determine if version is okay
    version_ok = recommended and version_status not in ['obsolete', 'unrecommended']
    
    # We can't directly know blacklist status, assume not blacklisted 
    # if relay has Valid flag
    has_valid = 'Valid' in relay.get('flags', [])
    blacklisted = not has_valid and version_ok  # Infer from flags
    
    # Version row
    version_display = version if version else 'Unknown'
    if version_status:
        version_display += f" ({version_status.title()})"
    
    version_row_status = 'meets' if version_ok else 'below'
    rows.append({
        'flag': 'Valid',
        'flag_tooltip': "Relay is verified: Running non-broken Tor version "
                       "and not blacklisted.",
        'flag_color': valid_color,
        'metric': 'Tor Version',
        'metric_tooltip': "Tor version must not be known to be broken. "
                         "Outdated versions may lose Valid flag.",
        'value': version_display,
        'value_source': 'relay',
        'threshold': 'Not in broken versions list',
        'status': version_row_status,
        'status_text': 'OK' if version_ok else 'Outdated/Broken',
        'status_color': STATUS_COLORS[version_row_status],
        'status_tooltip': VERSION_STATUS_TOOLTIPS[version_row_status],
        'rowspan': 2,
    })
    
    # Blacklist row
    blacklist_status = 'meets' if not blacklisted else 'below'
    rows.append({
        'flag': 'Valid',
        'flag_tooltip': '',
        'flag_color': valid_color,
        'metric': 'Blacklist Status',
        'metric_tooltip': "Relay must not be on authority's suspicious/blacklist.",
        'value': 'Not Blacklisted' if not blacklisted else 'BLACKLISTED',
        'value_source': 'da',
        'threshold': 'Not blacklisted by authorities',
        'status': blacklist_status,
        'status_text': 'Clear' if not blacklisted else 'Flagged',
        'status_color': STATUS_COLORS[blacklist_status],
        'status_tooltip': BLACKLIST_STATUS_TOOLTIPS[blacklist_status],
        'rowspan': 0,
    })
```

### 5.5 Table Row Preview

| Flag | Metric | Status | Relay Value | Threshold Required |
|------|--------|--------|-------------|-------------------|
| **Valid** | Tor Version | Meets | 0.4.8.12 (Recommended) (R) | Not in broken versions list |
| | Blacklist Status | Meets | Not Blacklisted (DA) | Not blacklisted by authorities |

### 5.6 Files to Modify

| File | Changes |
|------|---------|
| `allium/lib/consensus/consensus_evaluation.py` | Add `_add_valid_flag_rows()` method |

---

## 6. Proposal 4: V2Dir Flag Requirements

### 6.1 Rationale

V2Dir is a prerequisite for Guard flag, but operators don't see what V2Dir requires. This helps explain why a relay might not be getting Guard.

### 6.2 Requirements (from dir-spec)

```
V2Dir flag requires (EITHER):
- Has open directory port (DirPort), OR
- Has tunnelled-dir-server line in router descriptor

AND:
- Running Tor version with supported directory protocol
- DirCache not disabled
```

### 6.3 Data Sources

| Data | Source | Onionoo Field |
|------|--------|---------------|
| DirPort | Onionoo | `dir_address` |
| Has V2Dir flag | Onionoo | `flags` |

Note: `tunnelled-dir-server` status is not directly available from Onionoo but can be inferred.

### 6.4 Implementation

Add to `_format_flag_requirements_table()` in `consensus_evaluation.py`:

```python
def _add_v2dir_flag_rows(self, rows, relay, rv):
    """Add V2Dir flag eligibility row to the table."""
    
    v2dir_color = self._get_flag_color('v2dir', relay.get('flags', []))
    
    # Check if relay has DirPort
    dir_address = relay.get('dir_address', None)
    has_dir_port = dir_address is not None and dir_address != ''
    
    # Extract port number if available
    if has_dir_port and ':' in dir_address:
        dir_port = dir_address.split(':')[-1]
    else:
        dir_port = None
    
    # Check if relay has V2Dir flag (implies tunnelled-dir-server works)
    has_v2dir = 'V2Dir' in relay.get('flags', [])
    
    # If no DirPort but has V2Dir, must have tunnelled-dir-server
    has_tunnelled = has_v2dir and not has_dir_port
    
    # Format display
    if has_dir_port:
        value = f"DirPort: {dir_port}"
    elif has_tunnelled:
        value = "DirPort: None | Tunnelled: Yes"
    else:
        value = "DirPort: None | Tunnelled: No"
    
    v2dir_eligible = has_dir_port or has_tunnelled or has_v2dir
    status = 'meets' if v2dir_eligible else 'below'
    
    rows.append({
        'flag': 'V2Dir',
        'flag_tooltip': "Directory Server: Can serve directory info to clients. "
                       "Required for Guard flag.",
        'flag_color': v2dir_color,
        'metric': 'Dir Capability',
        'metric_tooltip': "Relay needs open DirPort OR tunnelled-dir-server line, "
                         "and DirCache not disabled.",
        'value': value,
        'value_source': 'relay',
        'threshold': 'DirPort > 0 OR tunnelled-dir-server',
        'status': status,
        'status_text': 'V2Dir Capable' if v2dir_eligible else 'No V2Dir',
        'status_color': STATUS_COLORS[status],
        'status_tooltip': V2DIR_STATUS_TOOLTIPS[status],
        'rowspan': 1,
    })
```

### 6.5 Table Row Preview

| Flag | Metric | Status | Relay Value | Threshold Required |
|------|--------|--------|-------------|-------------------|
| **V2Dir** | Dir Capability | Meets | DirPort: 9030 (R) | DirPort > 0 OR tunnelled-dir-server |

### 6.6 Files to Modify

| File | Changes |
|------|---------|
| `allium/lib/consensus/consensus_evaluation.py` | Add `_add_v2dir_flag_rows()` method |

---

## 7. Proposal 5: MiddleOnly Flag Detection

### 7.1 Rationale

MiddleOnly is a newer security flag (Tor 0.4.7.2+) that restricts suspicious relays to middle position only. Operators should be informed if their relay has this restriction.

### 7.2 Requirements (from dir-spec)

```
MiddleOnly is assigned when:
- Authority believes relay unsuitable for use except as middle relay

Effects:
- Removes: Exit, Guard, HSDir, V2Dir flags
- Adds: BadExit flag (if it exists in consensus)
```

### 7.3 Data Sources

| Data | Source | Field |
|------|--------|-------|
| MiddleOnly flag | Consensus | `flags` |

### 7.4 Implementation

Add to `_format_flag_requirements_table()` in `consensus_evaluation.py`:

```python
def _add_middleonly_flag_rows(self, rows, relay, rv, show_all=False):
    """Add MiddleOnly flag detection row to the table.
    
    Args:
        show_all: If True, show row even if relay doesn't have MiddleOnly.
                  If False, only show if relay has the flag.
    """
    
    current_flags = relay.get('flags', [])
    has_middle_only = 'MiddleOnly' in current_flags
    
    # Only show row if relay has MiddleOnly or show_all is enabled
    if not has_middle_only and not show_all:
        return
    
    # MiddleOnly is a negative flag - red if present
    if has_middle_only:
        middle_only_color = STATUS_COLORS['below']  # Red
        status = 'below'
        value = 'RESTRICTED'
        status_text = 'Middle Only (Restricted)'
    else:
        middle_only_color = STATUS_COLORS['meets']  # Green
        status = 'meets'
        value = 'Not Restricted'
        status_text = 'Unrestricted'
    
    rows.append({
        'flag': 'MiddleOnly',
        'flag_tooltip': "Security restriction: Relay can only be used as middle hop. "
                       "Removes Exit, Guard, HSDir, V2Dir flags. Added in Tor 0.4.7.2.",
        'flag_color': middle_only_color,
        'metric': 'Security Status',
        'metric_tooltip': "Authorities assign MiddleOnly if relay is deemed unsuitable "
                         "except as middle relay (suspicious behavior, Sybil risk, etc.).",
        'value': value,
        'value_source': 'da',
        'threshold': 'Not flagged by authorities',
        'status': status,
        'status_text': status_text,
        'status_color': STATUS_COLORS[status],
        'status_tooltip': "MiddleOnly restricts relay to middle position only. "
                         "If flagged, check for: multiple relays on same IP, "
                         "suspicious traffic patterns, or policy violations.",
        'rowspan': 1,
    })
```

### 7.5 Table Row Preview (if flagged)

| Flag | Metric | Status | Relay Value | Threshold Required |
|------|--------|--------|-------------|-------------------|
| **MiddleOnly** | Security Status | Below | RESTRICTED (DA) | Not flagged by authorities |

### 7.6 Files to Modify

| File | Changes |
|------|---------|
| `allium/lib/consensus/consensus_evaluation.py` | Add `_add_middleonly_flag_rows()` method |

---

## 8. Consolidated Implementation

### 8.1 Complete Table Structure (All Proposals)

After implementing all 5 proposals, the Eligibility Flag Vote Details table will have:

```
╔═══════════════╤════════════════════╤════════╤══════════════════════════╤═════════════════════════════╗
║ Flag          │ Metric             │ Status │ Relay Value              │ Threshold Required          ║
╠═══════════════╪════════════════════╪════════╪══════════════════════════╪═════════════════════════════╣
║ Fast          │ Speed              │ Meets  │ 15.2 MB/s (R)            │ ≥100 KB/s OR top 7/8        ║
╟───────────────┼────────────────────┼────────┼──────────────────────────┼─────────────────────────────╢
║ Stable        │ MTBF               │ Meets  │ 28.5 days (DA)           │ ≥19-30d (varies)            ║
║               │ Uptime             │ Meets  │ 45.3 days (R)            │ ≥19-30d (varies)            ║
╟───────────────┼────────────────────┼────────┼──────────────────────────┼─────────────────────────────╢
║ HSDir         │ Prereq: Stable     │ Meets  │ 9/9 authorities          │ ≥5/9 authorities            ║
║               │ Prereq: Fast       │ Meets  │ 9/9 authorities          │ ≥5/9 authorities            ║
║               │ WFU                │ Meets  │ 99.2% (DA)               │ ≥98%                        ║
║               │ Time Known         │ Meets  │ 45.3 days (DA)           │ ≥25h-10d (varies)           ║
╟───────────────┼────────────────────┼────────┼──────────────────────────┼─────────────────────────────╢
║ Guard         │ Prereq: Fast       │ Meets  │ 9/9 authorities          │ ≥5/9 authorities            ║
║               │ Prereq: Stable     │ Meets  │ 9/9 authorities          │ ≥5/9 authorities            ║
║               │ Prereq: V2Dir      │ Meets  │ 9/9 authorities          │ ≥5/9 authorities            ║
║               │ WFU                │ Meets  │ 99.2% (DA)               │ ≥98% (all authorities)      ║
║               │ Time Known         │ Meets  │ 45.3 days (DA)           │ ≥8 days (all authorities)   ║
║               │ Bandwidth          │ Meets  │ 15.2 MB/s (R)            │ ≥2 MB/s OR top 25%          ║
╟───────────────┼────────────────────┼────────┼──────────────────────────┼─────────────────────────────╢
║ Exit          │ Exit Policy        │ Meets  │ 80: Yes | 443: Yes (R)   │ Allows ≥1 /8 on 80+443      ║  ← P1 (Priority 1)
╟───────────────┼────────────────────┼────────┼──────────────────────────┼─────────────────────────────╢
║ Running*      │ IPv4 Reachability  │ Meets  │ 9/9 reached (DA)         │ ≥5/9 majority               ║  ← P2 (Priority 4)
║               │ IPv6 Reachability  │ Meets  │ 7/7 reached (DA)         │ Optional                    ║
╟───────────────┼────────────────────┼────────┼──────────────────────────┼─────────────────────────────╢
║ Valid*        │ Tor Version        │ Meets  │ 0.4.8.12 (R)             │ Not in broken list          ║  ← P3 (Priority 5)
║               │ Blacklist Status   │ Meets  │ Not Blacklisted (DA)     │ Not blacklisted             ║
╟───────────────┼────────────────────┼────────┼──────────────────────────┼─────────────────────────────╢
║ V2Dir         │ Dir Capability     │ Meets  │ DirPort: 9030 (R)        │ DirPort OR tunnelled        ║  ← P4 (Priority 3)
╟───────────────┼────────────────────┼────────┼──────────────────────────┼─────────────────────────────╢
║ MiddleOnly**  │ Security Status    │ Meets  │ Not Restricted (DA)      │ Not flagged                 ║  ← P5 (Priority 2)
╚═══════════════╧════════════════════╧════════╧══════════════════════════╧═════════════════════════════╝
```

\* Running and Valid already shown extensively in Health Status, Summary, and Per-Auth tables — adding to eligibility table is optional/low priority.
\*\* MiddleOnly row only shown if relay is flagged or if "show all flags" option is enabled.

### 8.2 Row Count Summary

| Category | Current (2026-02-15) | After All Proposals |
|----------|---------------------|---------------------|
| Fast | 1 row | 1 row |
| Stable | 2 rows | 2 rows |
| HSDir (2 prereqs + 2 metrics) | 4 rows | 4 rows |
| Guard (3 prereqs + 3 metrics) | 6 rows | 6 rows |
| **Subtotal (existing)** | **13 rows** | **13 rows** |
| Exit (P1, Priority 1) | 0 rows | 1 row |
| MiddleOnly (P5, Priority 2) | 0 rows | 0-1 rows (conditional) |
| V2Dir (P4, Priority 3) | 0 rows | 1 row |
| Running (P2, Priority 4) | 0 rows | 1-2 rows |
| Valid (P3, Priority 5) | 0 rows | 2 rows |
| **Total** | **13 rows** | **18-20 rows** |

### 8.3 Integration with Existing Code

The current `_format_flag_requirements_table()` function uses a flat structure (not per-flag methods). New flags should follow the same pattern — add code blocks inline in the function, using `_make_row()` and `_make_prereq_row()` helper functions.

```python
def _format_flag_requirements_table(rv, diag):
    """Format the complete flag requirements table with all display values pre-computed."""
    rows = []
    
    # Existing: Fast (1 row), Stable (2 rows), HSDir (4 rows), Guard (6 rows)
    # ... existing code for Fast, Stable, HSDir, Guard ...
    
    # NEW: Exit (1 row) — Priority 1
    # Per Tor dir-spec: Exit requires allowing exits to ≥1 /8 on ports 80 AND 443
    exit_color = get_flag_color('exit')
    # ... Exit row using _make_row() ...
    
    # FUTURE: MiddleOnly (0-1 rows) — Priority 2
    # FUTURE: V2Dir (1 row) — Priority 3
    # FUTURE: Running (1-2 rows) — Priority 4 (already shown in 3+ places)
    # FUTURE: Valid (2 rows) — Priority 5 (already shown in 3+ places)
    
    return rows
```

---

## 9. Testing Checklist

### 9.1 Proposal 1: Exit Flag (Priority 1 — Guard-Parity Testing)

See Section 3.15 for the complete Exit-specific testing checklist. Summary:

#### Layer-by-Layer Verification
- [ ] **Layer 1 (collector_fetcher):** `eligibility['exit']` populated with correct assigned_count per authority
- [ ] **Layer 2 (_format_flag_summary):** `flag_summary.exit` has correct eligible_count and status_class
- [ ] **Layer 3 (_format_relay_values):** `exit_allows_80`, `exit_allows_443`, `exit_eligible`, `exit_policy_display` all correct
- [ ] **Layer 4 (_format_flag_requirements_table):** Exit row appears after Guard rows with correct status/color
- [ ] **Layer 5 (Summary table):** Exit Policy row shows correct relay value and status
- [ ] **Layer 6 (Per-Auth table):** Exit column shows correct Yes/No per authority

#### Exit Relay (has Exit flag)
- [ ] All 6 layers show green "Meets" / "Yes" / "EXIT ELIGIBLE"
- [ ] Eligible Flags row shows correct Exit count (should be > 0)

#### Non-Exit Relay (no Exit flag)
- [ ] All 6 layers show red "Below" / "No" / "NON-EXIT"
- [ ] Eligible Flags row shows Exit: 0/9

#### Partial Exit (80 but not 443)
- [ ] Eligibility table shows yellow "Partial" with port detail
- [ ] Summary table shows yellow "PARTIAL"

#### Edge Cases
- [ ] Empty exit_policy_summary → "No exit policy"
- [ ] Reject-only policy → correctly infers allowed ports
- [ ] Range rules like "80-443" → correctly matches both ports
- [ ] Full range "1-65535" → correctly matches all ports

### 9.2 Per-Proposal Testing (Proposals 2-5)

#### Proposal 2: Running Flag (Priority 4)
- [ ] IPv4 reachability shows correct vote count
- [ ] IPv6 row appears only for relays with IPv6 addresses
- [ ] IPv6 shows correct tested/reached counts

#### Proposal 3: Valid Flag (Priority 5)
- [ ] Version displays with status (Recommended/Obsolete)
- [ ] Blacklist status shows "Not Blacklisted" for valid relays
- [ ] Relays without Valid flag show appropriate status

#### Proposal 4: V2Dir Flag (Priority 3)
- [ ] DirPort shown when available
- [ ] "Tunnelled: Yes" shown when no DirPort but has V2Dir
- [ ] Status correctly reflects V2Dir eligibility

#### Proposal 5: MiddleOnly Flag (Priority 2)
- [ ] Row hidden for normal relays (by default)
- [ ] Row appears with red status for restricted relays
- [ ] Tooltip explains implications

### 9.3 Integration Testing

- [ ] All rows render in correct order (Fast → Stable → HSDir → Guard → Exit)
- [ ] Table width/layout handles the additional Exit row
- [ ] Per-Auth table width handles the additional Exit column
- [ ] Rowspan works correctly for multi-row flags
- [ ] Colors and tooltips display properly
- [ ] Mobile responsive layout works with wider Per-Auth table

---

## 10. References

- **Tor Dir-Spec:** https://spec.torproject.org/dir-spec/ (Section 3.4.2)
- **Existing Implementation:** `allium/lib/consensus/consensus_evaluation.py`
- **Template:** `allium/templates/relay-info.html`
- **Flag Analysis:** [tor-relay-flags-analysis.md](tor-relay-flags-analysis.md)
- **Relay Page Layout:** [relay-page-layout-consolidated.md](relay-page-layout-consolidated.md)
