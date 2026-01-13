# 5 Proposals for Adding Spec Flags to the Eligibility Flag Vote Details Table

Based on analysis of the Tor dir-spec (https://spec.torproject.org/dir-spec/) and the current implementation in `relay-info.html` and `consensus_evaluation.py`.

---

## Proposal 1: Add Exit Flag Eligibility (Exit Policy Analysis)

**Rationale:** Exit is one of the most important flags but currently has no eligibility breakdown in the details table.

**Implementation:**

Add to `_format_flag_requirements_table()` in `consensus_evaluation.py`:

```python
# Exit flag (1 row) - based on exit policy
exit_color = get_flag_color('exit')
# Check if relay allows exits on ports 80 and 443 to at least one /8
exit_allows_80 = relay_allows_port(80)  # needs implementation
exit_allows_443 = relay_allows_port(443)
exit_eligible = exit_allows_80 and exit_allows_443

rows.append({
    'flag': 'Exit',
    'flag_tooltip': "Exit node: Allows traffic to regular internet. Requires allowing exits to ≥1 /8 on both ports 80 and 443.",
    'flag_color': exit_color,
    'metric': 'Exit Policy',
    'metric_tooltip': "Relay's exit policy must allow exits to at least one /8 address space on both port 80 AND port 443.",
    'value': f"Port 80: {'✓' if exit_allows_80 else '✗'} | Port 443: {'✓' if exit_allows_443 else '✗'}",
    'value_source': 'relay',
    'threshold': 'Allows ≥1 /8 on ports 80 AND 443',
    'status': 'meets' if exit_eligible else 'below',
    'status_text': 'Exit Eligible' if exit_eligible else 'Non-Exit',
    'status_color': STATUS_COLORS['meets' if exit_eligible else 'below'],
    'status_tooltip': STATUS_TOOLTIPS['meets' if exit_eligible else 'below'],
    'rowspan': 1,
})
```

**Table Row Preview:**

| Flag | Metric | Status | Relay Value | Threshold Required |
|------|--------|--------|-------------|-------------------|
| **Exit** | Exit Policy | Meets | Port 80: ✓ \| Port 443: ✓ (R) | Allows ≥1 /8 on ports 80 AND 443 |

---

## Proposal 2: Add Running/Reachability Flag Details

**Rationale:** Running is the core flag determining if a relay is in consensus, but we don't show the detailed reachability breakdown in the eligibility table.

**Implementation:**

Add to `_format_flag_requirements_table()`:

```python
# Running flag (1-2 rows) - based on reachability
running_color = get_flag_color('running')
ipv4_reachable = rv.get('ipv4_reachable_count', 0)
ipv4_total = rv.get('total_authorities', 9)

rows.append({
    'flag': 'Running',
    'flag_tooltip': "Relay is reachable: Authority connected within last 45 minutes on all published ORPorts.",
    'flag_color': running_color,
    'metric': 'IPv4 Reachability',
    'metric_tooltip': "Authority must successfully connect to relay's IPv4 ORPort within 45 minutes.",
    'value': f"{ipv4_reachable}/{ipv4_total} authorities reached",
    'value_source': 'da',
    'threshold': f'≥{majority_required}/{ipv4_total} authorities (majority)',
    'status': 'meets' if ipv4_reachable >= majority_required else 'below',
    'status_text': f"{'Reachable' if ipv4_reachable >= majority_required else 'Unreachable'}",
    'status_color': STATUS_COLORS['meets' if ipv4_reachable >= majority_required else 'below'],
    'rowspan': 2 if has_ipv6 else 1,
})

# Add IPv6 row if relay has IPv6
if has_ipv6:
    ipv6_reachable = rv.get('ipv6_reachable_count', 0)
    ipv6_tested = rv.get('ipv6_tested_count', 0)
    rows.append({
        'flag': 'Running',
        'metric': 'IPv6 Reachability',
        'metric_tooltip': "IPv6 testing by authorities that have AuthDirHasIPv6Connectivity enabled.",
        'value': f"{ipv6_reachable}/{ipv6_tested} tested authorities reached",
        'threshold': 'Optional (enhances routing)',
        'status': 'meets' if ipv6_reachable > 0 else 'partial',
        'rowspan': 0,
    })
```

**Table Row Preview:**

| Flag | Metric | Status | Relay Value | Threshold Required |
|------|--------|--------|-------------|-------------------|
| **Running** | IPv4 Reachability | Meets | 9/9 authorities reached (DA) | ≥5/9 authorities (majority) |
| | IPv6 Reachability | Meets | 7/7 tested authorities reached (DA) | Optional (enhances routing) |

---

## Proposal 3: Add Valid Flag with Version Check

**Rationale:** Valid depends on Tor version and blacklist status - we should show whether the relay's version is "known broken."

**Implementation:**

Add to `_format_flag_requirements_table()`:

```python
# Valid flag (2 rows) - version check and blacklist status
valid_color = get_flag_color('valid')
version = rv.get('version', 'Unknown')
version_ok = rv.get('recommended_version', True)  # From Onionoo
blacklisted = rv.get('is_blacklisted', False)

rows.append({
    'flag': 'Valid',
    'flag_tooltip': "Relay is verified: Running non-broken Tor version and not blacklisted.",
    'flag_color': valid_color,
    'metric': 'Tor Version',
    'metric_tooltip': "Tor version must not be known to be broken. Outdated versions may lose Valid flag.",
    'value': f"{version} {'(Recommended)' if version_ok else '(Not Recommended)'}" if version else 'Unknown',
    'value_source': 'relay',
    'threshold': 'Not in broken versions list',
    'status': 'meets' if version_ok else 'below',
    'status_text': 'OK' if version_ok else 'Outdated/Broken',
    'status_color': STATUS_COLORS['meets' if version_ok else 'below'],
    'rowspan': 2,
})

rows.append({
    'flag': 'Valid',
    'metric': 'Blacklist Status',
    'metric_tooltip': "Relay must not be on authority's suspicious/blacklist.",
    'value': 'Not Blacklisted' if not blacklisted else 'BLACKLISTED',
    'threshold': 'Not blacklisted by authorities',
    'status': 'meets' if not blacklisted else 'below',
    'status_text': 'Clear' if not blacklisted else 'Flagged',
    'rowspan': 0,
})
```

**Table Row Preview:**

| Flag | Metric | Status | Relay Value | Threshold Required |
|------|--------|--------|-------------|-------------------|
| **Valid** | Tor Version | Meets | 0.4.8.12 (Recommended) (R) | Not in broken versions list |
| | Blacklist Status | Meets | Not Blacklisted | Not blacklisted by authorities |

---

## Proposal 4: Add V2Dir Flag Requirements

**Rationale:** V2Dir is a prerequisite for Guard flag, but we don't explain what V2Dir requires.

**Implementation:**

Add to `_format_flag_requirements_table()`:

```python
# V2Dir flag (1 row) - directory server capability
v2dir_color = get_flag_color('v2dir')
has_dir_port = rv.get('dir_port', 0) > 0
has_tunnelled = rv.get('has_tunnelled_dir_server', False)
has_dir_cache = not rv.get('dir_cache_disabled', False)
v2dir_eligible = (has_dir_port or has_tunnelled) and has_dir_cache

rows.append({
    'flag': 'V2Dir',
    'flag_tooltip': "Directory Server: Can serve directory info to clients. Required for Guard flag.",
    'flag_color': v2dir_color,
    'metric': 'Dir Capability',
    'metric_tooltip': "Relay needs open DirPort OR tunnelled-dir-server line, and DirCache not disabled.",
    'value': f"DirPort: {rv.get('dir_port', 0) or 'None'} | Tunnelled: {'Yes' if has_tunnelled else 'No'}",
    'value_source': 'relay',
    'threshold': 'DirPort > 0 OR tunnelled-dir-server',
    'status': 'meets' if v2dir_eligible else 'below',
    'status_text': 'V2Dir Capable' if v2dir_eligible else 'No V2Dir',
    'status_color': STATUS_COLORS['meets' if v2dir_eligible else 'below'],
    'rowspan': 1,
})
```

**Table Row Preview:**

| Flag | Metric | Status | Relay Value | Threshold Required |
|------|--------|--------|-------------|-------------------|
| **V2Dir** | Dir Capability | Meets | DirPort: 9030 \| Tunnelled: Yes (R) | DirPort > 0 OR tunnelled-dir-server |

---

## Proposal 5: Add MiddleOnly Flag Detection (New Tor 0.4.7+ Flag)

**Rationale:** MiddleOnly is a newer security flag (Tor 0.4.7.2+) that restricts suspicious relays. Users should be informed if their relay is flagged.

**Implementation:**

Add to `_format_flag_requirements_table()`:

```python
# MiddleOnly flag (1 row) - security restriction (if flagged)
# Only show if relay has MiddleOnly flag or is at risk
has_middle_only = 'MiddleOnly' in current_flags

if has_middle_only or show_all_flags:  # show_all_flags could be a config option
    middle_only_color = STATUS_COLORS['below'] if has_middle_only else STATUS_COLORS['meets']
    
    rows.append({
        'flag': 'MiddleOnly',
        'flag_tooltip': "Security restriction: Relay can only be used as middle hop. Removes Exit, Guard, HSDir, V2Dir flags. Added in Tor 0.4.7.2.",
        'flag_color': middle_only_color,
        'metric': 'Security Status',
        'metric_tooltip': "Authorities assign MiddleOnly if relay is deemed unsuitable except as middle relay (suspicious behavior, Sybil risk, etc.).",
        'value': 'RESTRICTED' if has_middle_only else 'Not Restricted',
        'value_source': 'da',
        'threshold': 'Not flagged by authorities',
        'status': 'below' if has_middle_only else 'meets',
        'status_text': 'Middle Only (Restricted)' if has_middle_only else 'Unrestricted',
        'status_color': STATUS_COLORS['below' if has_middle_only else 'meets'],
        'status_tooltip': "MiddleOnly restricts relay to middle position only. If flagged, check for: multiple relays on same IP, suspicious traffic patterns, or policy violations.",
        'rowspan': 1,
    })
```

**Table Row Preview (if flagged):**

| Flag | Metric | Status | Relay Value | Threshold Required |
|------|--------|--------|-------------|-------------------|
| **MiddleOnly** | Security Status | ⚠️ Below | RESTRICTED (DA) | Not flagged by authorities |

---

## Implementation Priority Recommendation

| Priority | Proposal | Effort | Value |
|----------|----------|--------|-------|
| 1 | **Proposal 2: Running/Reachability** | Low | High - Core diagnostic info |
| 2 | **Proposal 1: Exit Policy** | Medium | High - Important for exit operators |
| 3 | **Proposal 3: Valid + Version** | Low | Medium - Version issues are common |
| 4 | **Proposal 4: V2Dir** | Low | Medium - Guard prerequisite explanation |
| 5 | **Proposal 5: MiddleOnly** | Low | Low (rare) - Future-proofing |

---

## Consolidated Table Structure (All Proposals Combined)

Final table would have these flag rows:

```
+---------------+--------------------+--------+------------------+-------------------------+
| Flag          | Metric             | Status | Relay Value      | Threshold Required      |
+---------------+--------------------+--------+------------------+-------------------------+
| Guard         | WFU                | Meets  | 99.2% (DA)       | ≥98% (all authorities)  |
|               | Time Known         | Meets  | 45.3 days (DA)   | ≥8 days (all auth)      |
|               | Bandwidth          | Meets  | 15.2 MB/s (R)    | ≥2 MB/s OR top 25%      |
+---------------+--------------------+--------+------------------+-------------------------+
| Stable        | MTBF               | Meets  | 28.5 days (DA)   | ≥19-30d (varies)        |
|               | Uptime             | Meets  | 45.3 days (R)    | ≥19-30d (varies)        |
+---------------+--------------------+--------+------------------+-------------------------+
| Fast          | Speed              | Meets  | 15.2 MB/s (R)    | ≥100 KB/s OR top 7/8    |
+---------------+--------------------+--------+------------------+-------------------------+
| HSDir         | WFU                | Meets  | 99.2% (DA)       | ≥98%                    |
|               | Time Known         | Meets  | 45.3 days (DA)   | ≥25h-10d (varies)       |
+---------------+--------------------+--------+------------------+-------------------------+
| Exit          | Exit Policy        | Meets  | 80: ✓ | 443: ✓  | Allows ≥1 /8 on 80+443  |  [NEW]
+---------------+--------------------+--------+------------------+-------------------------+
| Running       | IPv4 Reachability  | Meets  | 9/9 reached (DA) | ≥5/9 majority           |  [NEW]
|               | IPv6 Reachability  | Meets  | 7/7 reached (DA) | Optional                |  [NEW]
+---------------+--------------------+--------+------------------+-------------------------+
| Valid         | Tor Version        | Meets  | 0.4.8.12 (R)     | Not in broken list      |  [NEW]
|               | Blacklist Status   | Meets  | Not Blacklisted  | Not blacklisted         |  [NEW]
+---------------+--------------------+--------+------------------+-------------------------+
| V2Dir         | Dir Capability     | Meets  | DirPort: 9030 (R)| DirPort OR tunnelled    |  [NEW]
+---------------+--------------------+--------+------------------+-------------------------+
| MiddleOnly*   | Security Status    | Meets  | Not Restricted   | Not flagged             |  [NEW*]
+---------------+--------------------+--------+------------------+-------------------------+
```

\* MiddleOnly row only shown if relay is flagged or if "show all flags" option is enabled.

---

## Notes

1. All implementations follow the existing pattern in `_format_flag_requirements_table()`
2. Source annotations `(DA)` and `(R)` maintained for consistency
3. Color coding follows existing `STATUS_COLORS` dict
4. Tooltips follow existing `FLAG_TOOLTIPS` pattern
5. Data sources:
   - Exit policy: Onionoo `exit_policy_summary`
   - Reachability: CollecTor vote analysis
   - Version: Onionoo `recommended_version`
   - V2Dir: Onionoo `dir_address` + descriptor
   - MiddleOnly: Consensus flags
