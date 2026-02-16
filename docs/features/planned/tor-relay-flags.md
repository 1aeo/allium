# Tor Relay Flags: Specification, Analysis & Implementation

Consolidated reference for all Tor relay flags: dir-spec requirements, current Allium implementation status, and detailed implementation plans for each flag.

**Authoritative Reference:** https://spec.torproject.org/dir-spec/ (Section 3.4.2 - Assigning flags in a vote)

**Related Documents:**
- [Relay Page Layout Consolidated](relay-page-layout-consolidated.md) - Main UI/UX plan

---

## 1. Executive Summary

### 1.1 Purpose and Goals

1. **Complete specification coverage** — Document ALL flags from the dir-spec
2. **Clear requirements** — Show exact thresholds and conditions for each flag
3. **Implementation tracking** — Single source of truth for what's implemented vs. planned
4. **Operator education** — Help operators understand why they have/don't have certain flags

### 1.2 Flag Categories

| Category | Flags | Description |
|----------|-------|-------------|
| Core Eligibility | Valid, Running | Basic flags required to be in consensus |
| Performance | Fast, Stable | Quality indicators for relay selection |
| Role | Guard, Exit, HSDir, V2Dir | Special capabilities in the network |
| Authority | Authority | Directory Authority identification |
| Negative/Warning | BadExit, MiddleOnly, Sybil, StaleDesc | Flags indicating problems |
| Consensus | NoEdConsensus | Ed25519 key consensus issues |
| Deprecated | Named, Unnamed | No longer assigned |

---

## 2. Implementation Status

> **Last Updated:** 2026-02-16

### 2.1 Per-Flag Implementation Status

| Flag | Eligibility Table | Summary Table | Per-Auth Table | Health/Warnings | Status |
|------|------------------|---------------|----------------|-----------------|--------|
| **Guard** | ✅ 6 rows (3 prereqs + WFU, TK, BW) | ✅ 3 rows | ✅ 3 columns | — | ✅ Complete |
| **Stable** | ✅ 2 rows (MTBF, Uptime) | ✅ 2 rows | ✅ 2 columns | — | ✅ Complete |
| **Fast** | ✅ 1 row (Speed) | ✅ 1 row | ✅ 1 column | — | ✅ Complete |
| **HSDir** | ✅ 4 rows (2 prereqs + WFU, TK) | ✅ 2 rows | ✅ 2 columns | — | ✅ Complete |
| **Exit** | ✅ 1 row (Exit Policy) | ✅ 1 row | ✅ 1 column | — | ✅ Implemented 2026-02-15 |
| **MiddleOnly** | ✅ Conditional row (when flagged) | ✅ Conditional row | ✅ 1 column | ✅ Warning + diagnostics | ✅ Implemented 2026-02-16 |
| **Running** | ❌ None | ✅ Running row | ✅ Running column | ✅ Health Status | Low priority (already in 3+ places) |
| **Valid** | ❌ None | ✅ Valid row | ✅ Valid column | ✅ Health Status | Low priority (already in 3+ places) |
| **V2Dir** | 🔶 Guard prereq row only | — | — | — | ⏳ Medium priority |
| **Authority** | N/A | — | — | ✅ Flags list | Display-only |
| **BadExit** | N/A | — | — | ✅ Flags list + diagnostics | Display-only |
| **StaleDesc** | N/A | — | — | ✅ Warning + Per-Auth Desc Published | Warning display |
| **Sybil** | N/A | — | — | — | Internal flag, not in consensus |
| **NoEdConsensus** | N/A | — | — | ⚠️ Consensus status | Rare, low priority |

### 2.2 Implementation Priority

| Priority | Flag | Gap Size | Status |
|----------|------|----------|--------|
| ~~1~~ | ~~**Exit**~~ | ~~Large~~ | ✅ Implemented (2026-02-15) |
| ~~2~~ | ~~**MiddleOnly**~~ | ~~Large — zero presence~~ | ✅ Implemented (2026-02-16) |
| 3 | **V2Dir** | Medium — only as Guard prereq | ⏳ Not Started |
| 4 | **Running** | Small — already in 3+ places | ⏳ Not Started |
| 5 | **Valid** | Small — already in 3+ places | ⏳ Not Started |

### 2.3 Architecture Overview

> As of 2026-02-15, `relays.py` was refactored from ~5,900 lines into 8 focused modules.
> The consensus evaluation pipeline (`collector_fetcher.py`, `consensus_evaluation.py`) was **not** affected.

| Module | Lines | Purpose |
|--------|-------|---------|
| `relays.py` | ~1,100 | Core relay class, Onionoo fetch, consensus evaluation call |
| `page_writer.py` | ~1,020 | HTML page generation |
| `network_health.py` | ~1,300 | Network statistics and health metrics |
| `operator_analysis.py` | ~1,350 | Operator/contact analysis |
| `categorization.py` | ~750 | Relay categorization |
| `flag_analysis.py` | ~380 | Flag uptime analysis |
| `ip_utils.py` | ~94 | IP address utilities |
| `time_utils.py` | ~118 | Time formatting utilities |

**Consensus evaluation pipeline:**
1. `collector_fetcher._analyze_flag_eligibility()` → per-authority eligibility
2. `consensus_evaluation._format_relay_values()` → aggregated stats + relay values
3. `consensus_evaluation._format_flag_requirements_table()` → pre-computed row dicts
4. Template iterates `diag.flag_requirements_table` rows directly

---

## 3. Complete Flag Reference

### 3.1 Core Eligibility Flags

#### Valid

**Purpose:** Basic eligibility — relay must have Valid flag to be used by clients.

**Requirements:**
```
1. Running a Tor version NOT known to be broken
2. NOT blacklisted as suspicious by the authority
3. Has valid descriptor with acceptable address
```

**Operator Relevance:** HIGH — Without Valid, relay cannot be used at all.

#### Running

**Purpose:** Proves relay is online and reachable.

**Requirements:**
```
1. Authority successfully connected to relay's ORPort within last 45 minutes
2. Must pass reachability test on ALL published ORPorts:
   - IPv4 ORPort (required)
   - IPv6 ORPort (if relay advertises one AND authority has AuthDirHasIPv6Connectivity 1)
```

**Operator Relevance:** CRITICAL — Without Running, relay is not in consensus.

### 3.2 Performance Flags

#### Stable

**Purpose:** Indicates reliable uptime for long-lived connections (SSH, IRC, etc.)

**Requirements (meet EITHER):**
```
Option A: Active AND Weighted MTBF ≥ median for known active routers
Option B: Active AND Weighted MTBF ≥ 7 days
```

**Disqualifying Conditions:**
- Running Tor 0.1.1.10-alpha through 0.1.1.16-rc (dropped circuits)

**Operator Relevance:** HIGH — Required for Guard eligibility.

#### Fast

**Purpose:** Indicates sufficient bandwidth for general use.

**Requirements (meet EITHER):**
```
Option A: Active AND bandwidth in top 7/8ths for known active routers
Option B: Active AND bandwidth ≥ 100 KB/s (AuthDirFastGuarantee)
```

**Operator Relevance:** HIGH — Required for Guard eligibility.

### 3.3 Role Flags

#### Guard

**Purpose:** Entry point to Tor network — needs high reliability.

**Requirements (ALL must be true):**
```
1. Has Fast flag
2. Has Stable flag
3. Weighted Fractional Uptime (WFU) ≥ median for "familiar" active routers
4. Is "familiar" (1/8 of all active nodes appeared more recently, OR around for a few weeks)
5. Bandwidth ≥ AuthDirGuardBWGuarantee (2 MB/s default) OR in top 25% fastest
6. Has V2Dir flag
```

**Operator Relevance:** CRITICAL — Most desired flag, significant traffic and network impact.

#### Exit

**Purpose:** Can relay traffic to regular internet.

**Requirements:**
```
Allows exits to at least one /8 address space on BOTH:
- Port 80
- Port 443
```

**Operator Relevance:** HIGH — Determines if relay is exit node. Legal implications.

#### HSDir

**Purpose:** Hidden Service Directory — stores .onion descriptors.

**Requirements (ALL must be true):**
```
1. Stores and serves v2 hidden service descriptors
2. Has Stable flag
3. Has Fast flag
4. Authority believes uptime ≥ 96 hours (MinUptimeHidServDirectoryV2)
```

**Operator Relevance:** MEDIUM — Supports hidden services, no special requirements beyond stability.

#### V2Dir

**Purpose:** Can serve directory information to clients.

**Requirements (meet EITHER plus cache condition):**
```
Option A: Has open directory port (DirPort)
Option B: Has tunnelled-dir-server line in router descriptor

AND: Running Tor version with supported directory protocol
AND: Not disabled with "DirCache 0"
```

**Operator Relevance:** MEDIUM — Required for Guard flag. Most modern relays have this automatically.

### 3.4 Authority Flag

#### Authority

**Purpose:** Identifies Directory Authority relays.

**Requirements:** The authority generating the network-status believes it's an authority.

**Operator Relevance:** N/A — Only assigned to the 9 directory authorities.

### 3.5 Negative and Warning Flags

#### BadExit

**Purpose:** Marks misbehaving exit nodes.

**Assignment:** Listed on authority's "bad exit" list.

**Reasons:** Traffic manipulation, SSL stripping, content injection, DNS manipulation.

**Operator Relevance:** CRITICAL (negative) — Relay is not used for exit traffic.

#### MiddleOnly

**Purpose:** Restricts suspicious relays to middle position only.

**Assignment:** Authority believes relay unsuitable for use except as middle relay.

**Effects when assigned:**
- Removes: Exit, Guard, HSDir, V2Dir
- Adds: BadExit (if that flag exists in consensus)

**Added:** Tor 0.4.7.2-alpha

**Reasons:** Suspicious behavior patterns, Sybil risk indicators, policy violations not severe enough for full removal.

**Operator Relevance:** CRITICAL (negative) — Significant restriction on relay usage.

#### StaleDesc

**Purpose:** Warns about outdated relay descriptor.

**Requirements:** Descriptor's published time is >18 hours old.

**Operator Relevance:** MEDIUM — Indicates relay may have connectivity issues.

#### Sybil

**Purpose:** Sybil attack detection/mitigation.

**Requirements:** Authority sees >2 relays on same IP (AuthDirMaxServersPerAddr).

**Effects:** Removes Running and Valid flags from excess relays.

**Operator Relevance:** HIGH — If running multiple relays on same IP, only 2 will be in consensus.

### 3.6 Consensus and Deprecated Flags

#### NoEdConsensus

**Purpose:** Ed25519 key identity uncertainty. Applied in consensus computation, not voted by authorities.

**Operator Relevance:** LOW — Usually indicates temporary consensus issues.

#### Named / Unnamed (Deprecated)

No longer assigned by authorities.

---

## 4. Current Allium Implementation Details

### 4.1 Eligibility Flag Vote Details Table

The table uses `_format_flag_requirements_table()` to pre-compute all row data in Python.

| Flag | Rows | Metrics Tracked | Data Sources |
|------|------|----------------|--------------|
| **Fast** | 1 | Speed | Relay descriptor vs CollecTor `fast-speed` threshold |
| **Stable** | 2 | MTBF, Uptime | DA votes + Onionoo vs CollecTor thresholds |
| **HSDir** | 4 | Prereq: Stable, Prereq: Fast, WFU, TK | DA votes vs CollecTor thresholds |
| **Guard** | 6 | Prereq: Fast, Prereq: Stable, Prereq: V2Dir, WFU, TK, BW | DA votes + relay descriptor vs CollecTor thresholds |
| **Exit** | 1 | Exit Policy (ports 80+443) | Onionoo exit_policy_summary |
| **MiddleOnly** | 0-1 | Security Status (conditional) | CollecTor vote flags |

**Total Rows:** 14 (base) + 0-1 (conditional MiddleOnly)

### 4.2 Row Data Structure

```python
{
    'flag': str,              # Flag name (e.g., 'Guard')
    'flag_tooltip': str,      # Full flag description
    'flag_color': str,        # CSS color for flag cell
    'metric': str,            # Metric name (e.g., 'WFU')
    'metric_tooltip': str,    # Metric description
    'value': str,             # Relay's value
    'value_source': str,      # 'relay' or 'da'
    'threshold': str,         # Required threshold
    'status': str,            # 'meets', 'below', or 'partial'
    'status_text': str,       # Human-readable status
    'status_color': str,      # CSS color for status
    'status_tooltip': str,    # Status explanation
    'rowspan': int,           # Number of rows to span
}
```

### 4.3 Status Colors

```python
STATUS_COLORS = {
    'meets': '#28a745',   # Green
    'partial': '#856404', # Yellow/amber
    'below': '#dc3545',   # Red
}
```

### 4.4 Eligible Flags Row

Shows authority vote/eligibility counts for 8 flags in canonical order:

Running → Valid → V2Dir → Fast → Stable → HSDir → Guard → Exit

### 4.5 Summary Table (12+ Rows)

Provides Metric / Dir Auth Measured / Dir Auth Threshold / Status columns for all major metrics.

### 4.6 Per-Authority Details Table (18+ Columns)

Per-authority breakdown showing Running, Valid, Exit, MiddleOnly, BW Scan, v4, v6, Flags, Fast, Guard BW/WFU/TK, Stable MTBF/Uptime, HSDir WFU/TK, Desc Published, Cons Wt.

---

## 5. Implemented Flag Details

### 5.1 Exit Flag (✅ Implemented 2026-02-15)

**Layers implemented:**

| Layer | File | What |
|-------|------|------|
| 1 | `collector_fetcher.py` | `eligibility['exit']` per-authority flag tracking |
| 2 | `consensus_evaluation.py` | `'exit'` in `_format_flag_summary()` loop |
| 3 | `consensus_evaluation.py` | `_analyze_exit_policy()`, `_port_in_rules()`, exit values in `_format_relay_values()` |
| 4 | `consensus_evaluation.py` | Exit row in `_format_flag_requirements_table()` |
| 5 | `relay-info.html` | Exit Policy row in Summary table |
| 6 | `relay-info.html` | Exit column in Per-Authority Details table |
| Caller | `relays.py` | Passes `exit_policy_summary` to `format_relay_consensus_evaluation()` |

**Data Flow:**
```
Onionoo (exit_policy_summary) + CollecTor (vote flags)
  → relays.py passes exit_policy_summary
  → collector_fetcher tracks per-authority Exit flag
  → consensus_evaluation analyzes exit policy (ports 80+443)
  → Template: Eligibility table (1 row) + Summary table + Per-Auth column
```

**Verification:** Full build comparison (21,700+ HTML files) showed zero unintended changes from Exit implementation.

### 5.2 MiddleOnly Flag (✅ Implemented 2026-02-16)

**Design:** MiddleOnly is a **negative/warning flag** (like BadExit), not an eligibility metric. It uses conditional display — rows/warnings only appear when the relay actually has the flag.

**Layers implemented:**

| Layer | File | What |
|-------|------|------|
| 1 | `collector_fetcher.py` | `eligibility['middleonly']` per-authority flag tracking |
| 2 | `consensus_evaluation.py` | `'middleonly'` in `_format_flag_summary()` loop |
| 3 | `consensus_evaluation.py` | `middleonly_flagged`, `middleonly_count` in `_format_relay_values()` |
| 4 | `consensus_evaluation.py` | Conditional MiddleOnly row in `_format_flag_requirements_table()` |
| 5 | `relay-info.html` | Warning in Health Status, conditional row in Summary table |
| 6 | `relay-info.html` | MiddleOnly column in Per-Authority Details table |
| Diagnostics | `relay_diagnostics.py` | MiddleOnly issue detection (like BadExit) |

**Key Differences from Exit:**
- No numeric thresholds — authority discretion only
- Conditional display — hidden for 99.9% of relays
- Warning treatment — red warning, not eligibility tracking
- Per-Auth shows "—" by default, "Yes" (red) only when flagged

---

## 6. Future Flag Proposals

### 6.1 V2Dir (Priority 3)

Add standalone V2Dir eligibility info beyond the current Guard prereq row.

**Data:** DirPort from Onionoo `dir_address`, V2Dir flag presence.

**Display:** 1 row showing DirPort number or "Tunnelled: Yes" inference.

### 6.2 Running (Priority 4 — Low)

Already extensively shown in Health Status, Summary, and Per-Auth tables. Adding to eligibility table would be redundant but consistent.

**Display:** 1-2 rows (IPv4 reachability, optional IPv6).

### 6.3 Valid (Priority 5 — Low)

Already extensively shown. Adding to eligibility table would show version check and blacklist status.

**Display:** 2 rows (Tor Version, Blacklist Status).

---

## 7. Thresholds Reference

### 7.1 Bandwidth Thresholds

| Threshold | Value | Flag Affected |
|-----------|-------|---------------|
| AuthDirFastGuarantee | 100 KB/s | Fast |
| AuthDirGuardBWGuarantee | 2 MB/s | Guard |
| Top 7/8ths bandwidth | Varies | Fast |
| Top 25% bandwidth | Varies | Guard |

### 7.2 Time Thresholds

| Threshold | Value | Flag Affected |
|-----------|-------|---------------|
| MinUptimeHidServDirectoryV2 | 96 hours | HSDir |
| Minimum MTBF | 7 days (alternative) | Stable |
| "Familiar" time | ~weeks | Guard |
| Descriptor staleness | 18 hours | StaleDesc |
| Reachability window | 45 minutes | Running |

### 7.3 Authority Thresholds

| Threshold | Value | Context |
|-----------|-------|---------|
| AuthDirMaxServersPerAddr | 2 relays | Sybil detection |
| Majority for consensus | 5/9 | Flag assignment |

---

## 8. References

- **Tor Dir-Spec:** https://spec.torproject.org/dir-spec/ (Section 3.4.2)
- **Onionoo API:** https://metrics.torproject.org/onionoo.html
- **Relay Page Layout Plan:** [relay-page-layout-consolidated.md](relay-page-layout-consolidated.md)
