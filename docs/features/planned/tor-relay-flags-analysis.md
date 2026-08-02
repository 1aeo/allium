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

> **Last Updated:** 2026-01-25

| Flag | Eligibility Tracking | Details Table | Notes |
|------|---------------------|---------------|-------|
| **Guard** | ✅ Full | ✅ 3 metrics | WFU, TK, Bandwidth |
| **Stable** | ✅ Full | ✅ 2 metrics | MTBF, Uptime |
| **Fast** | ✅ Full | ✅ 1 metric | Speed |
| **HSDir** | ✅ Full | ✅ 2 metrics | WFU, TK |
| **Exit** | ⚠️ Partial | ❌ None | Shown in flags list, no eligibility breakdown |
| **Running** | ⚠️ Partial | ❌ None | Vote count shown, no detailed metrics |
| **Valid** | ⚠️ Partial | ❌ None | Vote count shown, no version analysis |
| **V2Dir** | ⚠️ Partial | ❌ None | Vote count shown, no requirements shown |
| **Authority** | ✅ Display | N/A | Shown if applicable |
| **BadExit** | ✅ Display | N/A | Shown if applicable |
| **StaleDesc** | ✅ Warning | N/A | Shown as warning |
| **MiddleOnly** | ❌ None | ❌ None | Not implemented (newer flag) |
| **Sybil** | ❌ None | ❌ None | Internal flag, not displayed |
| **NoEdConsensus** | ⚠️ Partial | N/A | Shown in consensus status |

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

### 3.1 Eligibility Flag Vote Details Table (Currently Implemented)

The current implementation tracks 4 flags with detailed eligibility metrics:

| Flag | Metrics Tracked | Data Sources |
|------|----------------|--------------|
| **Guard** | WFU, Time Known (TK), Bandwidth | DA votes, relay descriptor |
| **Stable** | MTBF, Uptime | DA votes, Onionoo |
| **Fast** | Speed | Relay descriptor, Onionoo |
| **HSDir** | WFU, Time Known (TK) | DA votes |

**Location:** `allium/lib/consensus/consensus_evaluation.py` → `_format_flag_requirements_table()`

### 3.2 Flags Shown Without Detailed Eligibility

| Flag | Current Display | Gap |
|------|----------------|-----|
| **Exit** | Listed in "Current Flags" | No exit policy breakdown |
| **Running** | Vote count (X/9) | No reachability details |
| **Valid** | Vote count (X/9) | No version/blacklist info |
| **V2Dir** | Vote count (X/9) | No DirPort/tunnelled status |
| **Authority** | Listed if applicable | N/A |
| **BadExit** | Listed if applicable | N/A |
| **StaleDesc** | Warning displayed | N/A |

### 3.3 Flags Not Currently Tracked

| Flag | Reason | Priority |
|------|--------|----------|
| **MiddleOnly** | Newer flag (Tor 0.4.7.2+) | Medium |
| **Sybil** | Internal flag, not in consensus | Low |
| **NoEdConsensus** | Rare, consensus-level | Low |

---

## 4. Gap Analysis and Recommendations

### 4.1 High Priority Gaps

| Gap | Impact | Recommendation |
|-----|--------|----------------|
| **Running reachability details** | Operators can't diagnose IPv4/IPv6 issues | Add to eligibility table |
| **Exit policy analysis** | Exit operators can't verify requirements | Add to eligibility table |
| **Valid version check** | Operators don't know if version is "broken" | Add to eligibility table |

### 4.2 Medium Priority Gaps

| Gap | Impact | Recommendation |
|-----|--------|----------------|
| **V2Dir requirements** | Guard prerequisites unclear | Add to eligibility table |
| **MiddleOnly detection** | Operators unaware of restrictions | Add detection and display |

### 4.3 Proposed New Eligibility Table Structure

See [Tor Relay Flags Proposals](tor-relay-flags-proposals.md) for detailed implementation proposals.

**Summary of proposed additions:**
1. **Exit flag** - Exit policy (ports 80 + 443) analysis
2. **Running flag** - IPv4/IPv6 reachability breakdown
3. **Valid flag** - Version status and blacklist check
4. **V2Dir flag** - DirPort and tunnelled-dir-server status
5. **MiddleOnly flag** - Security restriction detection

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
