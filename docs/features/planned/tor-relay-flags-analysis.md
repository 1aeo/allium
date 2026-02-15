# Tor Relay Flags: Complete Specification Analysis

Complete analysis of all Tor relay flags from the official dir-spec, their requirements, and current implementation status in Allium.

**Reference Document:** https://spec.torproject.org/dir-spec/ (Section 3.4.2 - Assigning flags in a vote)

**Related Documents:**
- [Relay Page Layout Consolidated](relay-page-layout-consolidated.md) - Main UI/UX plan
- [Tor Relay Flags Proposals](tor-relay-flags-proposals.md) - Implementation proposals for adding flag tracking

---

## 1. Executive Summary

### 1.1 Purpose and Goals

This document provides a comprehensive reference for all Tor relay flags defined in the official directory specification. Goals:

1. **Complete specification coverage** - Document ALL flags from the dir-spec
2. **Clear requirements** - Show exact thresholds and conditions for each flag
3. **Implementation gap analysis** - Identify what Allium currently tracks vs. what's missing
4. **Operator education** - Help operators understand why they have/don't have certain flags

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

### 1.3 Implementation Status Summary

> **Last Updated:** 2026-02-15

| Flag | Eligibility Table | Other Page Coverage | Notes |
|------|------------------|---------------------|-------|
| **Guard** | ✅ 6 rows (3 prereqs + WFU, TK, BW) | Summary table, Per-Auth table | Full Guard-parity across all page layers |
| **Stable** | ✅ 2 rows (MTBF, Uptime) | Summary table, Per-Auth table | Full coverage |
| **Fast** | ✅ 1 row (Speed) | Summary table, Per-Auth table | Full coverage |
| **HSDir** | ✅ 4 rows (2 prereqs + WFU, TK) | Summary table, Per-Auth table | Full coverage |
| **Exit** | ❌ None | Flags list, Exit Policy section (dt/dd) | **Biggest gap**: exit operators have no eligibility breakdown |
| **Running** | ❌ None | ✅ Health Status, Summary table, Per-Auth column | Extensively shown elsewhere; low priority for eligibility table |
| **Valid** | ❌ None | ✅ Health Status, Summary table, Per-Auth column | Extensively shown elsewhere; low priority for eligibility table |
| **V2Dir** | 🔶 Guard prereq row only | Eligible Flags row (vote count) | Shown as Guard dependency; no standalone eligibility section |
| **Authority** | N/A | ✅ Flags list | Display-only (not operator-actionable) |
| **BadExit** | N/A | ✅ Flags list | Display-only (not operator-actionable) |
| **StaleDesc** | N/A | ✅ Warning in Health Status + Per-Auth Desc Published | Warning display |
| **MiddleOnly** | ❌ None | ❌ Zero presence in codebase | **Not tracked anywhere** — restricted operators have no visibility |
| **Sybil** | ❌ None | ❌ None | Internal flag, not in consensus — cannot display |
| **NoEdConsensus** | N/A | ⚠️ Shown in consensus status | Rare flag, low priority |

---

## 2. Complete Flag Reference

### 2.1 Core Eligibility Flags

#### Valid

**Purpose:** Basic eligibility - relay must have Valid flag to be used by clients.

**Requirements:**
```
1. Running a Tor version NOT known to be broken
2. NOT blacklisted as suspicious by the authority
3. Has valid descriptor with acceptable address
```

**Disqualifying Conditions:**
- Version on the "broken" list
- Blacklisted by authority
- Invalid descriptor or address

**Operator Relevance:** HIGH - Without Valid, relay cannot be used at all.

---

#### Running

**Purpose:** Proves relay is online and reachable.

**Requirements:**
```
1. Authority successfully connected to relay's ORPort within last 45 minutes
2. Must pass reachability test on ALL published ORPorts:
   - IPv4 ORPort (required)
   - IPv6 ORPort (if relay advertises one AND authority has AuthDirHasIPv6Connectivity 1)
```

**Operator Relevance:** CRITICAL - Without Running, relay is not in consensus.

**Troubleshooting:**
- Check firewall allows inbound on ORPort
- Verify NAT/port forwarding is configured
- For IPv6: ensure dual-stack connectivity

---

### 2.2 Performance Flags

#### Stable

**Purpose:** Indicates reliable uptime for long-lived connections (SSH, IRC, etc.)

**Requirements (meet EITHER):**
```
Option A: Active AND Weighted MTBF ≥ median for known active routers
Option B: Active AND Weighted MTBF ≥ 7 days
```

**Weighted MTBF Calculation:**
- Weighted mean of all intervals when router was observed up
- Intervals weighted by α^n (n = time since interval ended)
- α chosen so measurements >1 month old have minimal influence

**Disqualifying Conditions:**
- Running Tor 0.1.1.10-alpha through 0.1.1.16-rc (dropped circuits)

**Operator Relevance:** HIGH - Required for Guard eligibility, affects circuit selection.

---

#### Fast

**Purpose:** Indicates sufficient bandwidth for general use.

**Requirements (meet EITHER):**
```
Option A: Active AND bandwidth in top 7/8ths for known active routers
Option B: Active AND bandwidth ≥ 100 KB/s (AuthDirFastGuarantee)
```

**"Active" Means:**
- Has Running flag
- Has Valid flag
- Not hibernating

**Operator Relevance:** HIGH - Required for Guard eligibility, affects traffic allocation.

---

### 2.3 Role Flags

#### Guard

**Purpose:** Entry point to Tor network - needs high reliability.

**Requirements (ALL must be true):**
```
1. Has Fast flag
2. Has Stable flag
3. Weighted Fractional Uptime (WFU) ≥ median for "familiar" active routers
4. Is "familiar" (1/8 of all active nodes appeared more recently, OR around for a few weeks)
5. Bandwidth ≥ AuthDirGuardBWGuarantee (2 MB/s default) OR in top 25% fastest
6. Has V2Dir flag
```

**WFU Calculation:**
- Fraction of time router is up in any given day
- Downtime and uptime in past counts less (weighted)

**Operator Relevance:** CRITICAL - Most desired flag, significant traffic and network impact.

---

#### Exit

**Purpose:** Can relay traffic to regular internet.

**Requirements:**
```
Allows exits to at least one /8 address space on BOTH:
- Port 80
- Port 443
```

**Historical Note:** Before Tor 0.3.2, required exits to at least 2 of: 80, 443, 6667.

**Operator Relevance:** HIGH - Determines if relay is exit node. Legal implications.

---

#### HSDir

**Purpose:** Hidden Service Directory - stores .onion descriptors.

**Requirements (ALL must be true):**
```
1. Stores and serves v2 hidden service descriptors
2. Has Stable flag
3. Has Fast flag
4. Authority believes uptime ≥ 96 hours (MinUptimeHidServDirectoryV2)
```

**Operator Relevance:** MEDIUM - Supports hidden services, no special requirements beyond stability.

---

#### V2Dir

**Purpose:** Can serve directory information to clients.

**Requirements (meet EITHER plus cache condition):**
```
Option A: Has open directory port (DirPort)
Option B: Has tunnelled-dir-server line in router descriptor

AND: Running Tor version with supported directory protocol
AND: Not disabled with "DirCache 0"
```

**Note:** Relays with "DirCache 0" or very low rate limits omit tunnelled-dir-server.

**Operator Relevance:** MEDIUM - Required for Guard flag. Most modern relays have this automatically.

---

### 2.4 Authority Flag

#### Authority

**Purpose:** Identifies Directory Authority relays.

**Requirements:**
```
The authority generating the network-status believes it's an authority
```

**Operator Relevance:** N/A - Only assigned to the 9 directory authorities.

---

### 2.5 Negative and Warning Flags

#### BadExit

**Purpose:** Marks misbehaving exit nodes.

**Assignment:**
```
Listed on authority's "bad exit" list
```

**Reasons for BadExit:**
- Traffic manipulation (MITM attacks)
- SSL stripping
- Injecting content
- DNS manipulation
- Other policy violations

**Operator Relevance:** CRITICAL (negative) - Relay is not used for exit traffic.

---

#### MiddleOnly

**Purpose:** Restricts suspicious relays to middle position only.

**Assignment:**
```
Authority believes relay unsuitable for use except as middle relay
```

**Effects when assigned:**
- Removes: Exit, Guard, HSDir, V2Dir
- Adds: BadExit (if that flag exists in consensus)

**Added:** Tor 0.4.7.2-alpha

**Reasons for MiddleOnly:**
- Suspicious behavior patterns
- Sybil risk indicators
- Policy violations not severe enough for full removal

**Operator Relevance:** CRITICAL (negative) - Significant restriction on relay usage.

---

#### StaleDesc

**Purpose:** Warns about outdated relay descriptor.

**Requirements:**
```
Descriptor's published time is >18 hours old
```

**Added:** Tor 0.4.0.1-alpha

**Operator Relevance:** MEDIUM - Indicates relay may have connectivity issues preventing descriptor updates.

---

#### Sybil

**Purpose:** Sybil attack detection/mitigation.

**Requirements:**
```
Authority sees >2 relays on same IP (AuthDirMaxServersPerAddr)
```

**Effects:**
- Removes Running and Valid flags from excess relays

**Selection priority for keeping relays:**
1. Prefer authorities over non-authorities
2. Prefer Running over non-Running
3. Prefer high-bandwidth over low-bandwidth

**Operator Relevance:** HIGH - If running multiple relays on same IP, only 2 will be in consensus.

---

### 2.6 Consensus Flags

#### NoEdConsensus

**Purpose:** Indicates Ed25519 key identity uncertainty.

**Requirements:**
```
Votes don't produce majority consensus about relay's Ed25519 key
(Applied in consensus computation, not voted by authorities)
```

**Added:** Consensus method 22+

**Operator Relevance:** LOW - Usually indicates temporary consensus issues.

---

### 2.7 Deprecated Flags

#### Named (Deprecated)

**Former Purpose:** Indicated canonical nickname→identity binding.

**Status:** No longer assigned by authorities.

---

#### Unnamed (Deprecated)

**Former Purpose:** Indicated ambiguous nickname.

**Status:** No longer assigned by authorities.

---

## 3. Current Allium Implementation

> **Last Updated:** 2026-02-15

### 3.1 Eligibility Flag Vote Details Table (Currently Implemented)

The current implementation tracks 4 flags with detailed eligibility metrics in the "Eligibility Flag Vote Details" table. This table uses `_format_flag_requirements_table()` to pre-compute all row data in Python.

| Flag | Rows | Metrics Tracked | Data Sources |
|------|------|----------------|--------------|
| **Fast** | 1 | Speed | Relay descriptor (observed_bandwidth) vs CollecTor `fast-speed` threshold |
| **Stable** | 2 | MTBF, Uptime | DA votes (mtbf) + Onionoo (last_restarted) vs CollecTor `stable-mtbf`/`stable-uptime` |
| **HSDir** | 4 | Prereq: Stable, Prereq: Fast, WFU, TK | DA votes (wfu, tk) vs CollecTor `hsdir-wfu`/`hsdir-tk` |
| **Guard** | 6 | Prereq: Fast, Prereq: Stable, Prereq: V2Dir, WFU, TK, BW | DA votes + relay descriptor vs multiple CollecTor thresholds |

**Total Rows:** 13

**Location:** `allium/lib/consensus/consensus_evaluation.py` → `_format_flag_requirements_table()`

**Backend Pipeline:**
1. `collector_fetcher._analyze_flag_eligibility()` → computes per-authority eligibility for guard/stable/fast/hsdir
2. `consensus_evaluation._format_relay_values()` → aggregates DA stats (majority/median/min/max) and relay values
3. `consensus_evaluation._format_flag_requirements_table()` → builds pre-computed row dicts for template
4. Template iterates `diag.flag_requirements_table` rows directly (no complex Jinja2 logic)

### 3.2 Eligible Flags Row (All 8 Flags Displayed)

The "Eligible Flags" row shows authority vote/eligibility counts for all 8 flags in canonical order:

| Flag | Display Type | Source |
|------|-------------|--------|
| **Running** | Vote-based (X/9) | `diag.vote_count` — all voting authorities |
| **Valid** | Vote-based (X/9) | `diag.vote_count` — all voting authorities |
| **V2Dir** | Vote-based (X/9) | `diag.vote_count` — all voting authorities |
| **Fast** | Eligibility-based (X/9) | `flag_summary.fast.eligible_count` |
| **Stable** | Eligibility-based (X/9) | `flag_summary.stable.eligible_count` |
| **HSDir** | Eligibility-based (X/9) | `flag_summary.hsdir.eligible_count` |
| **Guard** | Eligibility-based (X/9) | `flag_summary.guard.eligible_count` |
| **Exit** | Eligibility-based (X/9) | `flag_summary.exit.eligible_count` — **Note: currently returns None (exit not in flag_summary loop)** |

**Location:** `consensus_evaluation._format_eligible_flags_display()`

### 3.3 Summary Table (12+ Rows)

The "Summary: Your Relay vs Consensus" table provides a full breakdown with Metric, Dir Auth Measured, Dir Auth Threshold, and Status columns:

| Row | Data Source |
|-----|-------------|
| In Consensus | CollecTor vote count |
| Running (IPv4 Reachable) | CollecTor vote count |
| Valid | CollecTor vote count |
| Consensus Weight | CollecTor bandwidth measurements (median) |
| Guard WFU | CollecTor DA votes (wfu stat) |
| Guard TK | CollecTor DA votes (tk stat) |
| Guard BW | Onionoo observed_bandwidth |
| Stable Uptime | Onionoo last_restarted vs CollecTor stable-uptime |
| Stable MTBF | CollecTor DA votes (mtbf stat) |
| Fast Speed | Onionoo observed_bandwidth vs CollecTor fast-speed |
| HSDir WFU | CollecTor DA votes (wfu stat) |
| HSDir TK | CollecTor DA votes (tk stat) |
| IPv6 Reachable | CollecTor vote 'a' line (conditional) |

**Location:** `relay-info.html` → `#relay-summary` section

### 3.4 Per-Authority Details Table (17 Columns)

The "Per-Authority Details" table shows per-authority breakdown:

| Column | Guard-Specific | General |
|--------|---------------|---------|
| Authority | | ✅ |
| Running | | ✅ (Yes/No) |
| Valid | | ✅ (Yes/No) |
| BW Scan | | ✅ (Y/N) |
| v4 | | ✅ (Yes/No) |
| v6 | | ✅ (conditional) |
| Flags | | ✅ (color-coded list) |
| Fast (Relay\|T) | | ✅ |
| Guard BW (Relay\|Threshold) | ✅ | |
| Guard WFU (M\|T) | ✅ | |
| Guard TK (M\|T) | ✅ | |
| Stable MTBF (M\|T) | | ✅ |
| Stable Uptime (Relay\|T) | | ✅ |
| HSDir WFU (M\|T) | | ✅ |
| HSDir TK (M\|T) | | ✅ |
| Desc Published | | ✅ |
| Cons Wt | | ✅ |

**Location:** `relay-info.html` → `#authority-votes` section

### 3.5 Flags Not Currently Tracked

| Flag | Current Presence | Gap Size | Priority |
|------|-----------------|----------|----------|
| **Exit** | Flags list + exit policy section (dt/dd) | **Large** — No eligibility table rows, no Summary row, no Per-Auth column | **High** |
| **MiddleOnly** | Zero presence anywhere in codebase | **Large** — Operators have no way to discover restrictions | **High** |
| **V2Dir** | Guard prereq row + Eligible Flags vote count | **Medium** — No standalone eligibility breakdown | **Medium** |
| **Running** | Health Status + Summary + Per-Auth + Eligible Flags | **Small** — Extensively covered, just not in eligibility table | **Low** |
| **Valid** | Health Status + Summary + Per-Auth + Eligible Flags | **Small** — Extensively covered, just not in eligibility table | **Low** |
| **Sybil** | None | N/A | N/A — Internal flag, not in consensus |
| **NoEdConsensus** | Consensus status display | **Small** — Rare flag | **Low** |

---

## 4. Gap Analysis and Recommendations

> **Last Updated:** 2026-02-15
>
> **Important Context:** Since the original analysis (2026-01-25), the relay page has been significantly enhanced. Running, Valid, and V2Dir now have extensive coverage in the Health Status grid, Summary table, and Per-Authority Details table. This changes the priority ordering — the largest remaining gaps are Exit (no eligibility breakdown at all) and MiddleOnly (zero presence anywhere).

### 4.1 High Priority Gaps

| Gap | Impact | Existing Coverage | Recommendation |
|-----|--------|-------------------|----------------|
| **Exit policy eligibility** | Exit operators have no eligibility breakdown — the most impactful missing feature | Exit shown in flags list and exit policy section (dt/dd format), but no structured eligibility analysis | Add Exit rows to eligibility table + Summary table + Per-Auth column (follow Guard pattern) |
| **MiddleOnly detection** | Restricted operators have zero visibility — this flag is not tracked anywhere in the codebase | None — `grep` for MiddleOnly returns zero results in Python files | Add MiddleOnly detection and display |

### 4.2 Medium Priority Gaps

| Gap | Impact | Existing Coverage | Recommendation |
|-----|--------|-------------------|----------------|
| **V2Dir standalone eligibility** | Guard prerequisite unclear for operators who don't have V2Dir | Shown as Guard prereq row in eligibility table + vote count in Eligible Flags | Consider adding standalone V2Dir row with DirPort/tunnelled-dir-server info |

### 4.3 Low Priority Gaps (Already Covered Elsewhere)

| Gap | Impact | Existing Coverage | Recommendation |
|-----|--------|-------------------|----------------|
| **Running in eligibility table** | Minor — operators already see reachability in 3+ places | ✅ Health Status (consensus + vote count), Summary table (Running row), Per-Auth table (Running + v4/v6 columns) | Optional: add to eligibility table for completeness |
| **Valid in eligibility table** | Minor — operators already see version/status in 3+ places | ✅ Health Status (version + recommended), Summary table (Valid row), Per-Auth table (Valid column) | Optional: add to eligibility table for completeness |

### 4.4 Proposed New Eligibility Table Structure

See [Tor Relay Flags Proposals](tor-relay-flags-proposals.md) for detailed implementation proposals.

**Updated priority order (by gap size, not theoretical value):**

| Priority | Flag | Gap Size | Proposal |
|----------|------|----------|----------|
| 1 | **Exit** | Large — no eligibility breakdown | Proposal 1: Detailed Guard-parity plan with code for all 6 layers |
| 2 | **MiddleOnly** | Large — zero presence | Proposal 5: Security restriction detection |
| 3 | **V2Dir** | Medium — only as prereq | Proposal 4: Standalone eligibility info |
| 4 | **Running** | Small — already in 3+ places | Proposal 2: IPv4/IPv6 reachability (optional) |
| 5 | **Valid** | Small — already in 3+ places | Proposal 3: Version check (optional) |

---

## 5. Thresholds Reference

### 5.1 Bandwidth Thresholds

| Threshold | Value | Flag Affected |
|-----------|-------|---------------|
| AuthDirFastGuarantee | 100 KB/s | Fast |
| AuthDirGuardBWGuarantee | 2 MB/s | Guard |
| Top 7/8ths bandwidth | Varies | Fast |
| Top 25% bandwidth | Varies | Guard |

### 5.2 Time Thresholds

| Threshold | Value | Flag Affected |
|-----------|-------|---------------|
| MinUptimeHidServDirectoryV2 | 96 hours | HSDir |
| Minimum MTBF | 7 days (alternative) | Stable |
| "Familiar" time | ~weeks | Guard |
| Descriptor staleness | 18 hours | StaleDesc |
| Reachability window | 45 minutes | Running |

### 5.3 Authority Thresholds

| Threshold | Value | Context |
|-----------|-------|---------|
| AuthDirMaxServersPerAddr | 2 relays | Sybil detection |
| Majority for consensus | 5/9 | Flag assignment |

---

## 6. References

- **Tor Dir-Spec:** https://spec.torproject.org/dir-spec/ (Section 3.4.2)
- **Tor Spec 328 (Overload):** https://spec.torproject.org/proposals/328-relay-overload-report.html
- **Onionoo API:** https://metrics.torproject.org/onionoo.html
- **Relay Page Layout Plan:** [relay-page-layout-consolidated.md](relay-page-layout-consolidated.md)
- **Implementation Proposals:** [tor-relay-flags-proposals.md](tor-relay-flags-proposals.md)
