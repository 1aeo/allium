# Consensus Evaluation Feature

**Status**: ✅ Implemented  
**Version**: 1.0.0  
**Data Source**: Tor Project CollecTor + Onionoo API

---

## Overview

The Consensus Evaluation feature provides relay operators with detailed insights into how directory authorities view their relays. This helps operators understand:

- Why their relay may not be in consensus
- Why they're missing certain flags (Guard, Stable, HSDir, etc.)
- Which authorities can/cannot reach their relay
- What thresholds they need to meet for each flag

## Where to Find It

### Relay Pages (`relay-info.html`)

Each relay page has a **Consensus Evaluation** section (anchor: `#consensus-evaluation`) that shows:

1. **Summary Table** - Your relay's values vs. thresholds for each flag
2. **Per-Authority Table** - How each of the 9 voting directory authorities views your relay
3. **Identified Issues** - Specific problems detected with your relay
4. **Advice** - Actionable suggestions to improve your relay's status

### Authorities Page (`misc/authorities.html`)

The authorities dashboard shows:

1. **Authority Health** - Online status, latency, and voting status for all 9 authorities
2. **Flag Thresholds Table** - Exact thresholds each authority uses for flag assignment
3. **Bandwidth Authority Status** - Which authorities run bandwidth scanners (sbws)

---

## Common Relay Operator Questions

### Question 1: "Why is my relay not in consensus?"

| Where to Look | What You'll See |
|---------------|-----------------|
| **Summary Table → Running** | Shows "X/9 authorities reached this relay" |
| **Per-Authority Table** | Shows which specific authorities can reach you (green ✓ or red ✗) |
| **Identified Issues** | Lists "faravahar cannot reach relay" if specific authorities fail |

**Root causes**:
- Not enough authorities can reach your relay (need 5/9 majority)
- IPv4 reachability issues with specific authorities
- Firewall blocking specific authority IP addresses

---

### Question 2: "Why did I lose my Guard flag?"

| Where to Look | What You'll See |
|---------------|-----------------|
| **Summary Table → Guard WFU** | Your WFU value vs. threshold (≥98% required) |
| **Summary Table → Guard TK** | Your Time Known vs. threshold (≥8 days required) |
| **Summary Table → Guard BW** | Your bandwidth vs. threshold (≥2 MB/s OR top 25%) |
| **Per-Authority Table → Guard columns** | Per-authority WFU, TK, BW comparison |

**Guard Requirements** (from Tor dir-spec):
- **WFU** ≥ 98% (Weighted Fractional Uptime)
- **TK** ≥ 8 days (Time Known - how long authority has tracked relay)
- **Bandwidth** ≥ 2 MB/s (AuthDirGuardBWGuarantee) OR in top 25%
- Must also have **Fast** and **Stable** flags
- Must have **V2Dir** flag (supports directory protocol)

---

### Question 3: "Why did I lose my Stable flag?"

| Where to Look | What You'll See |
|---------------|-----------------|
| **Summary Table → Stable Uptime** | Your uptime vs. range (varies by authority) |
| **Summary Table → Stable MTBF** | Your MTBF vs. range |
| **Authorities Page → Flag Thresholds** | Each authority's `stable-uptime` and `stable-mtbf` values |

**Stable Requirements**:
- Uptime at or above the network median
- MTBF (Mean Time Between Failures) at or above median
- Thresholds vary by authority (typically 14-20 days)

---

### Question 4: "Relay shows offline but is running fine"

| Where to Look | What You'll See |
|---------------|-----------------|
| **Per-Authority Table → v4/v6 columns** | Which authorities can/cannot reach you |
| **Identified Issues** | Lists unreachable authorities |
| **Authorities Page → Latency** | Check if authority itself is having problems |

**Root causes**:
- Firewall blocking specific authority IPs
- Geographic routing issues
- Authority having temporary problems (check Authority Health page)

---

### Question 5: "Low consensus weight / bandwidth"

| Where to Look | What You'll See |
|---------------|-----------------|
| **Summary Table → Consensus Weight** | Median of all authority measurements |
| **Per-Authority Table → Cons Wt column** | Each authority's measured bandwidth |
| **Per-Authority Table → BW Scan column** | Which authorities run bandwidth scanners |

**Note**: Only 6 of 9 authorities run bandwidth scanners (sbws):
- bastet, gabelmoo, longclaw, maatuska, moria1, tor26

The other 3 (dannenberg, dizum, faravahar) use relay-advertised bandwidth.

---

### Question 6: "IPv6 reachability issues"

| Where to Look | What You'll See |
|---------------|-----------------|
| **Summary Table → IPv6 Reachable** | X/Y authorities tested (not all test IPv6) |
| **Per-Authority Table → v6 column** | Per-authority: "✓" (yes), "✗" (no), "N/T" (not tested) |

**Note**: Not all authorities test IPv6 reachability. "N/T" means that authority doesn't perform IPv6 testing.

---

### Question 7: "What are the exact flag criteria?"

| Where to Look | What You'll See |
|---------------|-----------------|
| **Authorities Page → Flag Thresholds Table** | All thresholds for all flags from each authority |
| **Summary Table → Threshold column** | Threshold for each metric |

---

### Question 8: "First seen date / Time Known reset"

| Where to Look | What You'll See |
|---------------|-----------------|
| **Summary Table → Guard TK** | Your Time Known value |
| **Per-Authority Table → Guard TK column** | TK from each authority |

**Root causes**:
- New relay identity key
- Authority lost track of relay (long downtime)
- Key rotation

---

### Question 9: "Why is authority X not voting for my relay?"

| Where to Look | What You'll See |
|---------------|-----------------|
| **Per-Authority Table → Running column** | Whether each authority voted for you |
| **Per-Authority Table → v4 column** | IPv4 reachability per authority |
| **Identified Issues** | Specific authority reachability problems |

---

### Question 10: "Is a specific authority having problems?"

| Where to Look | What You'll See |
|---------------|-----------------|
| **Authorities Page → Online Status** | Authority health (online/offline) |
| **Authorities Page → Latency** | Response time (green < 200ms, yellow < 500ms, red > 500ms) |
| **Authorities Page → Voted** | Whether authority submitted a vote this hour |

---

### Question 11: "Flags gone after restart"

| Where to Look | What You'll See |
|---------------|-----------------|
| **Summary Table → Guard TK** | TK may have reset if identity key changed |
| **Summary Table → Guard WFU** | WFU may have dropped due to downtime |

**Root causes**:
- Identity key regeneration resets TK to 0
- Downtime drops WFU below thresholds
- Takes time for authorities to re-measure bandwidth

---

### Question 12: "How do I get the HSDir flag?"

**HSDir Requirements**:
- **WFU** ≥ 98% (Weighted Fractional Uptime)
- **TK** ≥ 25 hours (dir-spec default, moria1 uses ~10 days)
- Must have **Stable** flag

| Where to Look | What You'll See |
|---------------|-----------------|
| **Summary Table → HSDir WFU** | Your WFU vs. threshold |
| **Summary Table → HSDir TK** | Your TK vs. threshold (shows which authorities are stricter) |

---

### Question 13: "Different sites show different data"

All data sources are indicated with tooltips. Hover over any value to see:
- **Source**: CollecTor or Onionoo
- **File**: Which data file (vote, details, etc.)
- **Field**: Exact field name (e.g., `stats wfu=X`)

---

## Flag Thresholds Reference

### Guard Flag

| Requirement | Threshold | Source |
|-------------|-----------|--------|
| WFU (Weighted Fractional Uptime) | ≥ 98% | `flag-thresholds guard-wfu` |
| TK (Time Known) | ≥ 8 days | `flag-thresholds guard-tk` |
| Bandwidth | ≥ 2 MB/s OR top 25% | `AuthDirGuardBWGuarantee` or `guard-bw-inc-exits` |
| Fast flag | Required | Must already have |
| Stable flag | Required | Must already have |
| V2Dir flag | Required | Directory protocol support |

### Stable Flag

| Requirement | Threshold | Source |
|-------------|-----------|--------|
| Uptime | At or above network median | `flag-thresholds stable-uptime` |
| MTBF | At or above network median | `flag-thresholds stable-mtbf` |

### Fast Flag

| Requirement | Threshold | Source |
|-------------|-----------|--------|
| Bandwidth | ≥ 100 KB/s OR top 7/8ths | `flag-thresholds fast-speed` |

### HSDir Flag

| Requirement | Threshold | Source |
|-------------|-----------|--------|
| WFU | ≥ 98% | `flag-thresholds hsdir-wfu` |
| TK | ≥ 25 hours (dir-spec default) | `flag-thresholds hsdir-tk` |
| Stable flag | Required | Must already have |

**Note**: moria1 uses a stricter ~10 days for HSDir TK. Other authorities use the dir-spec default of 25 hours.

---

## Data Sources

### CollecTor (collector.torproject.org)

Primary source for consensus evaluation data:

| Data Type | Path | Refresh Rate |
|-----------|------|--------------|
| Authority Votes | `/recent/relay-descriptors/votes/` | Hourly |
| Bandwidth Files | `/recent/relay-descriptors/bandwidths/` | Hourly |

**Vote File Fields Used**:
- `r` line: Relay identity, nickname, published time
- `s` line: Flags assigned by authority
- `a` line: IPv6 address (if reachable)
- `w Bandwidth=X`: Consensus weight
- `stats wfu=X tk=X mtbf=X`: Relay statistics
- `flag-thresholds`: Authority's thresholds for flag assignment
- `bandwidth-file-headers`: Indicates authority runs sbws scanner

### Onionoo (onionoo.torproject.org)

Supplementary data:

| Data Type | Endpoint | Fields Used |
|-----------|----------|-------------|
| Relay Details | `/details` | `observed_bandwidth`, `flags`, `fingerprint`, Authority discovery |
| Uptime | `/uptime` | Historical uptime data |

---

## Refresh Rates

| Data | Refresh Rate | Cache Duration |
|------|--------------|----------------|
| CollecTor votes | 1 hour | 1 hour (3 hour max for fallback) |
| CollecTor bandwidth | 1 hour | 1 hour |
| Authority latency | 5 minutes | 5 minutes |
| Onionoo data | 30 minutes | Varies |

---

## Identified Issues & Advice Messages

The system automatically identifies issues and provides advice:

### Consensus Issues

| Issue | Severity | Advice |
|-------|----------|--------|
| Not in consensus | Error | "Check reachability from all authority locations" |
| Low vote count | Error | "Only X/9 authorities voted for this relay" |

### Reachability Issues

| Issue | Severity | Advice |
|-------|----------|--------|
| IPv4 unreachable | Error | "Check firewall rules for: [authority names]" |
| IPv6 partial | Warning | Specific authorities listed |

### Flag Eligibility Issues

| Issue | Severity | Advice |
|-------|----------|--------|
| WFU below 98% | Warning | "Increase WFU to ≥98%. Current uptime pattern is too variable." |
| TK below 8 days | Info | "Wait X more days for Guard eligibility" |
| BW below 2 MB/s | Warning | "Need: BW ≥2 MB/s, WFU ≥98%, TK ≥8 days" |

---

## Technical Details

### Module Structure

```
lib/consensus/
├── __init__.py                 # Exports, feature flag
├── collector_fetcher.py        # CollecTor data fetching and indexing
├── authority_monitor.py        # Authority health monitoring
├── consensus_evaluation.py     # Data formatting for templates
└── flag_thresholds.py          # Centralized threshold constants/logic
```

### Feature Flag

```bash
# Disable consensus evaluation feature
export ALLIUM_CONSENSUS_EVALUATION=false
```

Default: `true` (enabled)

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ALLIUM_CONSENSUS_EVALUATION` | `true` | Enable/disable feature |

---

## Troubleshooting

### "No evaluation data available"

- CollecTor may be unreachable
- Relay may be new (not yet in any votes)
- Check cache age indicator

### "Partial data"

- Some authorities may have failed to respond
- Check Authority Health page for offline authorities

### Outdated data

- Check "Last updated" timestamp
- Data refreshes hourly from CollecTor

---

## References

- [Tor Directory Specification](https://spec.torproject.org/dir-spec/)
- [CollecTor Documentation](https://collector.torproject.org/)
- [Onionoo API Documentation](https://metrics.torproject.org/onionoo.html)

---

**Implementation Date**: December 2024  
**Based on**: [Consensus Troubleshooting Enhancement Plan](../../planned/consensus-troubleshooting/README.md)
