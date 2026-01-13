# Tor Relay Flags: Complete Specification Analysis

## 1. All Flags Defined in the Tor Directory Spec

Reference: https://spec.torproject.org/dir-spec/ (Section 3.4.2 - Assigning flags in a vote)

### Currently Assigned Flags (Active)

| Flag | Requirements | Notes |
|------|-------------|-------|
| **Valid** | Router is running a version of Tor not known to be broken AND not blacklisted as suspicious | Basic eligibility flag |
| **Running** | Authority connected to relay successfully within last 45 minutes on all published ORPorts (IPv4 required, IPv6 if AuthDirHasIPv6Connectivity is set) | Core reachability flag |
| **Stable** | Active AND (Weighted MTBF ≥ median for active routers OR Weighted MTBF ≥ 7 days). Not assigned if running Tor version known to drop circuits stupidly. | Stability indicator |
| **Fast** | Active AND (bandwidth in top 7/8ths of active routers OR bandwidth ≥ 100 KB/s) | Bandwidth indicator |
| **Guard** | All of: Fast + Stable + WFU ≥ median for familiar routers + "familiar" + (bandwidth ≥ 2MB/s OR top 25%) + V2Dir | Entry guard eligibility |
| **Exit** | Allows exits to at least one /8 address space on each of ports 80 AND 443 | Exit node capability |
| **Authority** | Authority generating the document believes the router is an authority | Special: Directory Authorities only |
| **V2Dir** | Has open directory port OR tunnelled-dir-server line, AND runs supported directory protocol version | Directory mirror capability |
| **HSDir** | Stores/serves v2 hidden service descriptors + Stable + Fast + uptime ≥ 96 hours (MinUptimeHidServDirectoryV2) | Hidden Service Directory |
| **BadExit** | Listed on the "bad exit" list (misbehaving exit node) | Negative flag |
| **MiddleOnly** | Authority believes relay is unsuitable for use except as middle relay. Automatically removes: Exit, Guard, HSDir, V2Dir. Adds BadExit if that flag exists. | Added in Tor 0.4.7.2-alpha |
| **StaleDesc** | Published time on descriptor is over 18 hours in the past | Warning flag (added in 0.4.0.1-alpha) |
| **Sybil** | More than 2 relays on single IP (AuthDirMaxServersPerAddr). Removes Running/Valid. | Negative flag - attack detection |
| **NoEdConsensus** | Produced in consensus (not voted) when votes don't produce majority consensus about relay's Ed25519 key | Consensus method 22+ |

### Deprecated/Removed Flags

| Flag | Status | Notes |
|------|--------|-------|
| **Named** | Deprecated | Formerly indicated canonical nickname→identity binding |
| **Unnamed** | Deprecated | Formerly indicated ambiguous nickname |

---

## 2. Detailed Requirements for Each Flag

### Valid
```
Requirements:
- Running a Tor version NOT known to be broken
- NOT blacklisted as suspicious by the authority
- Has valid descriptor with acceptable address

Purpose: Basic eligibility - must have Valid to be used by clients
```

### Running  
```
Requirements:
- Authority successfully connected to relay's ORPort within last 45 minutes
- Must pass reachability test on ALL published ORPorts:
  * IPv4 ORPort (required)
  * IPv6 ORPort (if relay advertises one AND authority has AuthDirHasIPv6Connectivity 1)

Purpose: Proves relay is online and reachable
```

### Stable
```
Requirements (either):
- Active AND Weighted MTBF ≥ median for known active routers, OR
- Active AND Weighted MTBF ≥ 7 days

Weighted MTBF Calculation:
- Weighted mean of all intervals when router was observed up
- Intervals weighted by α^n (n = time since interval ended)
- α chosen so measurements >1 month old have minimal influence

Disqualifications:
- Running Tor 0.1.1.10-alpha through 0.1.1.16-rc (dropped circuits)

Purpose: Indicates reliable uptime for long-lived connections
```

### Fast
```
Requirements:
- Active (Running + Valid + not Hibernating)
- Bandwidth in top 7/8ths for known active routers, OR
- Bandwidth ≥ 100 KB/s (AuthDirFastGuarantee)

Purpose: Indicates sufficient bandwidth for general use
```

### Guard
```
Requirements (ALL must be true):
1. Has Fast flag
2. Has Stable flag
3. Weighted Fractional Uptime (WFU) ≥ median for "familiar" active routers
4. Is "familiar" (1/8 of all active nodes appeared more recently, OR around for a few weeks)
5. Bandwidth ≥ AuthDirGuardBWGuarantee (2 MB/s default) OR in top 25% fastest
6. Has V2Dir flag

WFU Calculation:
- Fraction of time router is up in any given day
- Downtime and uptime in past counts less (weighted)

Purpose: Entry point to Tor network - needs high reliability
```

### Exit
```
Requirements:
- Allows exits to at least one /8 address space on BOTH:
  * Port 80
  * Port 443

Note: Before Tor 0.3.2, required exits to at least 2 of: 80, 443, 6667

Purpose: Can relay traffic to regular internet
```

### Authority
```
Requirements:
- The authority generating the network-status believes it's an authority

Purpose: Identifies Directory Authority relays
```

### V2Dir
```
Requirements:
- Has open directory port (DirPort), OR
- Has tunnelled-dir-server line in router descriptor
- Running Tor version with supported directory protocol

Note: Relays with "DirCache 0" or very low rate limits omit tunnelled-dir-server

Purpose: Can serve directory information to clients
```

### HSDir
```
Requirements:
1. Stores and serves v2 hidden service descriptors
2. Has Stable flag
3. Has Fast flag  
4. Authority believes uptime ≥ 96 hours (MinUptimeHidServDirectoryV2)

Purpose: Hidden Service Directory - stores .onion descriptors
```

### BadExit
```
Requirements:
- Listed on authority's "bad exit" list

Purpose: Marks misbehaving exit nodes (traffic manipulation, MITM, etc.)
```

### MiddleOnly
```
Requirements:
- Authority believes relay unsuitable for use except as middle relay

Effects when assigned:
- Removes: Exit, Guard, HSDir, V2Dir
- Adds: BadExit (if that flag exists in consensus)

Added: Tor 0.4.7.2-alpha

Purpose: Restricts suspicious relays to middle position only
```

### StaleDesc
```
Requirements:
- Descriptor's published time is >18 hours old

Added: Tor 0.4.0.1-alpha

Purpose: Warns about outdated relay descriptor
```

### Sybil
```
Requirements:
- Authority sees >2 relays on same IP (AuthDirMaxServersPerAddr)

Effects:
- Removes Running and Valid flags from excess relays

Selection priority for keeping relays:
1. Prefer authorities over non-authorities
2. Prefer Running over non-Running
3. Prefer high-bandwidth over low-bandwidth

Purpose: Sybil attack detection/mitigation
```

### NoEdConsensus
```
Requirements:
- Votes don't produce majority consensus about relay's Ed25519 key
- Applied in consensus computation (not voted by authorities)

Added: Consensus method 22+

Purpose: Indicates Ed25519 key identity uncertainty
```

---

## 3. Current Implementation Status in Allium

### Flags with Full Eligibility Tracking (in "Eligibility Flag Vote Details" table):
- ✅ Guard (WFU, TK, Bandwidth requirements)
- ✅ Stable (MTBF, Uptime requirements)  
- ✅ Fast (Speed/bandwidth requirements)
- ✅ HSDir (WFU, TK requirements)

### Flags Shown but Without Detailed Eligibility Table:
- ⚠️ Exit - shown in "Current Flags" but no eligibility breakdown
- ⚠️ Running - shown in vote count but no detailed metrics
- ⚠️ Valid - shown in vote count but no detailed requirements
- ⚠️ V2Dir - shown in vote count but no detailed requirements
- ⚠️ Authority - shown if applicable
- ⚠️ BadExit - shown if applicable
- ⚠️ StaleDesc - shown as warning if applicable
- ⚠️ NoEdConsensus - shown in consensus status

### Flags Not Currently Tracked:
- ❌ MiddleOnly - not implemented (newer flag from Tor 0.4.7.2-alpha)
- ❌ Sybil - not shown (negative internal flag)

---

## 4. Summary of Gaps

The current "Eligibility Flag Vote Details" table tracks:
1. **Guard** - 3 metrics (WFU, TK, Bandwidth)
2. **Stable** - 2 metrics (MTBF, Uptime)
3. **Fast** - 1 metric (Speed)
4. **HSDir** - 2 metrics (WFU, TK)

Missing from detailed tracking:
1. **Exit** - Exit policy requirements (ports 80 + 443)
2. **Running** - Reachability requirements
3. **Valid** - Version + non-blacklisted requirements
4. **V2Dir** - Directory port/tunnelled-dir-server requirements
5. **MiddleOnly** - New flag (Tor 0.4.7.2+)

