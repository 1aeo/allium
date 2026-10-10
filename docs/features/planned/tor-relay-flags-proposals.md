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

> **Last Updated:** 2026-01-25

#### Legend
- ✅ **Fully Implemented** - Code complete and deployed
- 🔶 **Partially Implemented** - Some parts done, others pending
- ⏳ **Not Started** - Planning complete, implementation pending

---

| Proposal | Flag | Status | Location | Notes |
|----------|------|--------|----------|-------|
| 1 | Exit | ⏳ Not Started | `consensus_evaluation.py` | Exit policy analysis |
| 2 | Running | ⏳ Not Started | `consensus_evaluation.py` | IPv4/IPv6 reachability |
| 3 | Valid | ⏳ Not Started | `consensus_evaluation.py` | Version + blacklist |
| 4 | V2Dir | ⏳ Not Started | `consensus_evaluation.py` | DirPort/tunnelled |
| 5 | MiddleOnly | ⏳ Not Started | `consensus_evaluation.py` | Security restriction |

---

### 1.3 Implementation Priority

| Priority | Proposal | Effort | Value | Rationale |
|----------|----------|--------|-------|-----------|
| 1 | **Proposal 2: Running** | Low | High | Core diagnostic info for reachability issues |
| 2 | **Proposal 1: Exit** | Medium | High | Important for exit operators, policy validation |
| 3 | **Proposal 3: Valid** | Low | Medium | Version issues are common troubleshooting topic |
| 4 | **Proposal 4: V2Dir** | Low | Medium | Guard prerequisite explanation |
| 5 | **Proposal 5: MiddleOnly** | Low | Low | Newer flag, rare occurrence |

---

## 2. Current Implementation Reference

### 2.1 Existing Table Structure

The current Eligibility Flag Vote Details table in `relay-info.html` tracks:

| Flag | Metrics | Rows |
|------|---------|------|
| Guard | WFU, Time Known, Bandwidth | 3 |
| Stable | MTBF, Uptime | 2 |
| Fast | Speed | 1 |
| HSDir | WFU, Time Known | 2 |

**Total Current Rows:** 8

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

## 3. Proposal 1: Exit Flag Eligibility

### 3.1 Rationale

Exit is one of the most important flags but currently has no eligibility breakdown in the details table. Exit operators need to verify their exit policy meets requirements.

### 3.2 Requirements (from dir-spec)

```
Exit flag requires:
- Allows exits to at least one /8 address space on port 80
- Allows exits to at least one /8 address space on port 443
```

### 3.3 Data Sources

| Data | Source | Onionoo Field |
|------|--------|---------------|
| Exit policy summary | Onionoo | `exit_policy_summary` |
| Exit addresses | Onionoo | `exit_addresses` |
| Exit probability | Onionoo | `exit_probability` |

### 3.4 Implementation

Add to `_format_flag_requirements_table()` in `consensus_evaluation.py`:

```python
def _add_exit_flag_rows(self, rows, relay, rv):
    """Add Exit flag eligibility row to the table."""
    
    exit_color = self._get_flag_color('exit', relay.get('flags', []))
    
    # Analyze exit policy from Onionoo data
    exit_policy = relay.get('exit_policy_summary', {})
    accept = exit_policy.get('accept', [])
    reject = exit_policy.get('reject', [])
    
    # Check if relay allows exits on required ports
    # Simplified check - in practice, need to verify /8 coverage
    allows_80 = self._policy_allows_port(accept, reject, 80)
    allows_443 = self._policy_allows_port(accept, reject, 443)
    exit_eligible = allows_80 and allows_443
    
    # Format display value
    port_80_status = 'Yes' if allows_80 else 'No'
    port_443_status = 'Yes' if allows_443 else 'No'
    value = f"Port 80: {port_80_status} | Port 443: {port_443_status}"
    
    status = 'meets' if exit_eligible else 'below'
    status_text = 'Exit Eligible' if exit_eligible else 'Non-Exit'
    
    rows.append({
        'flag': 'Exit',
        'flag_tooltip': "Exit node: Allows traffic to regular internet. "
                       "Requires allowing exits to ≥1 /8 on both ports 80 and 443.",
        'flag_color': exit_color,
        'metric': 'Exit Policy',
        'metric_tooltip': "Relay's exit policy must allow exits to at least "
                         "one /8 address space on both port 80 AND port 443.",
        'value': value,
        'value_source': 'relay',
        'threshold': 'Allows ≥1 /8 on ports 80 AND 443',
        'status': status,
        'status_text': status_text,
        'status_color': STATUS_COLORS[status],
        'status_tooltip': EXIT_STATUS_TOOLTIPS[status],
        'rowspan': 1,
    })


def _policy_allows_port(self, accept_rules, reject_rules, port):
    """Check if exit policy allows traffic on a specific port.
    
    Simplified implementation - full implementation would need to
    verify coverage of at least one /8 address space.
    """
    # Check accept rules for port
    for rule in accept_rules:
        if self._rule_matches_port(rule, port):
            return True
    
    # If we have reject rules that cover this port everywhere, it's blocked
    for rule in reject_rules:
        if rule == f'{port}' or rule == f'*:{port}':
            return False
    
    return False


def _rule_matches_port(self, rule, port):
    """Check if a policy rule matches a specific port."""
    # Handle formats like "80", "80-443", "*:80", "0.0.0.0/0:80"
    if ':' in rule:
        port_part = rule.split(':')[-1]
    else:
        port_part = rule
    
    if '-' in port_part:
        start, end = port_part.split('-')
        return int(start) <= port <= int(end)
    
    return port_part == str(port) or port_part == '*'
```

### 3.5 Table Row Preview

| Flag | Metric | Status | Relay Value | Threshold Required |
|------|--------|--------|-------------|-------------------|
| **Exit** | Exit Policy | Meets | Port 80: Yes \| Port 443: Yes (R) | Allows ≥1 /8 on ports 80 AND 443 |

### 3.6 Files to Modify

| File | Changes |
|------|---------|
| `allium/lib/consensus/consensus_evaluation.py` | Add `_add_exit_flag_rows()` method |
| `allium/templates/relay-info.html` | No changes (uses existing table structure) |

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
║ Guard         │ WFU                │ Meets  │ 99.2% (DA)               │ ≥98% (all authorities)      ║
║               │ Time Known         │ Meets  │ 45.3 days (DA)           │ ≥8 days (all auth)          ║
║               │ Bandwidth          │ Meets  │ 15.2 MB/s (R)            │ ≥2 MB/s OR top 25%          ║
╟───────────────┼────────────────────┼────────┼──────────────────────────┼─────────────────────────────╢
║ Stable        │ MTBF               │ Meets  │ 28.5 days (DA)           │ ≥19-30d (varies)            ║
║               │ Uptime             │ Meets  │ 45.3 days (R)            │ ≥19-30d (varies)            ║
╟───────────────┼────────────────────┼────────┼──────────────────────────┼─────────────────────────────╢
║ Fast          │ Speed              │ Meets  │ 15.2 MB/s (R)            │ ≥100 KB/s OR top 7/8        ║
╟───────────────┼────────────────────┼────────┼──────────────────────────┼─────────────────────────────╢
║ HSDir         │ WFU                │ Meets  │ 99.2% (DA)               │ ≥98%                        ║
║               │ Time Known         │ Meets  │ 45.3 days (DA)           │ ≥25h-10d (varies)           ║
╟───────────────┼────────────────────┼────────┼──────────────────────────┼─────────────────────────────╢
║ Exit          │ Exit Policy        │ Meets  │ 80: Yes | 443: Yes (R)   │ Allows ≥1 /8 on 80+443      ║  ← NEW
╟───────────────┼────────────────────┼────────┼──────────────────────────┼─────────────────────────────╢
║ Running       │ IPv4 Reachability  │ Meets  │ 9/9 reached (DA)         │ ≥5/9 majority               ║  ← NEW
║               │ IPv6 Reachability  │ Meets  │ 7/7 reached (DA)         │ Optional                    ║  ← NEW
╟───────────────┼────────────────────┼────────┼──────────────────────────┼─────────────────────────────╢
║ Valid         │ Tor Version        │ Meets  │ 0.4.8.12 (R)             │ Not in broken list          ║  ← NEW
║               │ Blacklist Status   │ Meets  │ Not Blacklisted (DA)     │ Not blacklisted             ║  ← NEW
╟───────────────┼────────────────────┼────────┼──────────────────────────┼─────────────────────────────╢
║ V2Dir         │ Dir Capability     │ Meets  │ DirPort: 9030 (R)        │ DirPort OR tunnelled        ║  ← NEW
╟───────────────┼────────────────────┼────────┼──────────────────────────┼─────────────────────────────╢
║ MiddleOnly*   │ Security Status    │ Meets  │ Not Restricted (DA)      │ Not flagged                 ║  ← NEW*
╚═══════════════╧════════════════════╧════════╧══════════════════════════╧═════════════════════════════╝
```

\* MiddleOnly row only shown if relay is flagged or if "show all flags" option is enabled.

### 8.2 Row Count Summary

| Category | Current | After Proposals |
|----------|---------|-----------------|
| Existing flags (Guard, Stable, Fast, HSDir) | 8 rows | 8 rows |
| New flags (Exit, Running, Valid, V2Dir, MiddleOnly) | 0 rows | 7-8 rows |
| **Total** | **8 rows** | **15-16 rows** |

### 8.3 Integration with Existing Code

Add a master function to integrate all flag rows:

```python
def _format_flag_requirements_table(self, relay, rv, authority_data):
    """Format the complete flag requirements table with all flags."""
    rows = []
    
    # Existing flag rows
    self._add_guard_flag_rows(rows, relay, rv)
    self._add_stable_flag_rows(rows, relay, rv)
    self._add_fast_flag_rows(rows, relay, rv)
    self._add_hsdir_flag_rows(rows, relay, rv)
    
    # New flag rows (Proposals 1-5)
    self._add_exit_flag_rows(rows, relay, rv)
    self._add_running_flag_rows(rows, relay, rv, authority_data)
    self._add_valid_flag_rows(rows, relay, rv)
    self._add_v2dir_flag_rows(rows, relay, rv)
    self._add_middleonly_flag_rows(rows, relay, rv, show_all=False)
    
    return rows
```

---

## 9. Testing Checklist

### 9.1 Per-Proposal Testing

#### Proposal 1: Exit Flag
- [ ] Exit relay shows "Port 80: Yes | Port 443: Yes"
- [ ] Non-exit relay shows "Port 80: No | Port 443: No" (or partial)
- [ ] Status correctly shows "Exit Eligible" or "Non-Exit"

#### Proposal 2: Running Flag
- [ ] IPv4 reachability shows correct vote count
- [ ] IPv6 row appears only for relays with IPv6 addresses
- [ ] IPv6 shows correct tested/reached counts

#### Proposal 3: Valid Flag
- [ ] Version displays with status (Recommended/Obsolete)
- [ ] Blacklist status shows "Not Blacklisted" for valid relays
- [ ] Relays without Valid flag show appropriate status

#### Proposal 4: V2Dir Flag
- [ ] DirPort shown when available
- [ ] "Tunnelled: Yes" shown when no DirPort but has V2Dir
- [ ] Status correctly reflects V2Dir eligibility

#### Proposal 5: MiddleOnly Flag
- [ ] Row hidden for normal relays (by default)
- [ ] Row appears with red status for restricted relays
- [ ] Tooltip explains implications

### 9.2 Integration Testing

- [ ] All rows render in correct order
- [ ] Table width/layout handles all columns
- [ ] Rowspan works correctly for multi-row flags
- [ ] Colors and tooltips display properly
- [ ] Mobile responsive layout works

---

## 10. References

- **Tor Dir-Spec:** https://spec.torproject.org/dir-spec/ (Section 3.4.2)
- **Existing Implementation:** `allium/lib/consensus/consensus_evaluation.py`
- **Template:** `allium/templates/relay-info.html`
- **Flag Analysis:** [tor-relay-flags-analysis.md](tor-relay-flags-analysis.md)
- **Relay Page Layout:** [relay-page-layout-consolidated.md](relay-page-layout-consolidated.md)
