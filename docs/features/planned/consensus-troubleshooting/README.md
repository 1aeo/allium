# Consensus Troubleshooting Enhancement Plan

**Status**: 📋 Ready for Implementation  
**Data Scope**: Most recent CollecTor data only (latest hour) - NO historical parsing  
**Estimated Effort**: 6-7 weeks total

---

## Executive Summary

Add consensus troubleshooting features to Allium using CollecTor as the primary data source. All data is fetched once per hour (matching consensus cycle), indexed by relay fingerprint, and looked up in O(1) during page generation.

**Two Phases**:
1. **Phase 1**: Per-relay diagnostics on `relay-info.html` (4 weeks)
2. **Phase 2**: Enhanced `misc-authorities.html` dashboard (2-3 weeks)

---

## 📋 Common Relay Operator Questions & Where to Find Answers

These are real questions from the **tor-relays mailing list** and **Tor Project forums**. This plan addresses each one.

### Question 1: "Why is my relay not in consensus?"
**Examples**: "Relay forest18 is still not on the consensus", "Exit relay not in consensus", "One of my relays does not get a consensus weight"

| Where to Look | What You'll See |
|---------------|-----------------|
| **Relay Page → Summary Table** | Shows "NOT IN CONSENSUS (X/9 authorities)" in red text with tooltip explaining majority requirement |
| **Relay Page → Detail Table** | Shows which authorities CAN reach your relay (IPv4 green/red text) and which voted for it |
| **Relay Page → Issues Summary** | Lists specific problems: "faravahar cannot reach relay" |

**Root causes this identifies**:
- Not enough authorities can reach your relay (need 5/9 majority)
- IPv4 reachability issues with specific authorities
- Relay too new (check Time Known column)

---

### Question 2: "Why did I lose my Guard flag?"
**Examples**: "Loss of Guard and HS Dir flags", "Relay no longer acting as a guard node?", "Unexpected classification with my guard relay"

| Where to Look | What You'll See |
|---------------|-----------------|
| **Relay Page → WFU Column** | Your WFU value vs threshold (≥98% required). Red text if below. |
| **Relay Page → Time Known Column** | Your TK value vs threshold (≥8 days required). Red text if below. |
| **Relay Page → Guard BW Column** | Per-authority: "≥30 MB/s" (red) or "≥10 MB/s" (green) - thresholds VARY |
| **Relay Page → Values Summary** | "BELOW (red) - cannot get Guard from ANY authority" or "PARTIAL (yellow) - meets for 5/9" |
| **Relay Page → Advice** | "Increase WFU to ≥98%. Current uptime pattern is too variable." |

**Root causes this identifies**:
- WFU dropped below 98% (uptime instability)
- Time Known reset (key rotation, relay restart with new identity)
- Bandwidth below some authorities' thresholds
- Tooltip shows exact field: `Source: CollecTor | File: vote | Field: stats wfu=X`

---

### Question 3: "Why did I lose my Stable flag?"
**Examples**: "Loss of Stable flag", "Relay MIGHTYWANG consensus issues and loss of STABLE flag"

| Where to Look | What You'll See |
|---------------|-----------------|
| **Relay Page → Detail Table → Stable** | Per-authority threshold: "≥19.6d" (green) or "≥14.2d" (red) |
| **Relay Page → Values Summary → Stable Uptime** | "varies: 14.2-19.8 days" with your value |
| **Authority Health Page → Flag Thresholds Table** | All 9 authorities' `stable-uptime` thresholds side-by-side |

**Root causes this identifies**:
- Uptime below threshold (varies 14-20 days by authority)
- Recent restart reset your stable uptime counter

---

### Question 4: "Consensus frequently reports relay down, despite relay passing traffic"
**Examples**: "Metrics falsely showing my relay as offline", "tor relay shows offline @ tor relay search while running"

| Where to Look | What You'll See |
|---------------|-----------------|
| **Relay Page → Per-Authority Table → IPv4/IPv6 columns** | Which specific authorities can/cannot reach you |
| **Relay Page → Issues Summary** | "faravahar cannot reach relay" - identifies the specific authority |
| **Authority Health Page → Latency Column** | Authority latency (if authority itself is slow/down) |
| **Authority Health Page → Voted Column** | Whether authority submitted vote this hour |

**Root causes this identifies**:
- Specific authorities can't reach you (firewall, routing, geographic issues)
- Authority itself having problems (check Authority Health page)
- IPv6-only issues (some authorities don't test IPv6)

---

### Question 5: "Directory authorities not giving weight to a relay" / "Low consensus weight"
**Examples**: "Low consensus weight votes from European authorities", "consensus weight tanking", "Tor relay back to 1 weight"

| Where to Look | What You'll See |
|---------------|-----------------|
| **Relay Page → Meas. BW Column** | Measured bandwidth from each authority (N/A for non-BW authorities) |
| **Relay Page → BW Authority detection** | Which authorities run bandwidth scanners (from `bandwidth-file-headers`) |
| **Authority Health Page → BW Auth Column** | "Yes" (green) / "No" (red) for each authority's scanner status |

**Root causes this identifies**:
- Bandwidth scanner not measuring your relay yet
- Different authorities measuring different values
- Non-BW authorities (dizum, dannenberg, faravahar) don't contribute measurements

---

### Question 6: "Auto-discovered IPv6 address has not been found reachable"
**Examples**: "IPv6 reachability issues", "Bridge Operation IPv6 only - possible?"

| Where to Look | What You'll See |
|---------------|-----------------|
| **Relay Page → Detail Table → IPv6** | Per-authority: "Yes" (green), "No" (red), "N/T" (gray = not tested) |
| **Relay Page → Legend** | "⚪ = authority doesn't test IPv6" |

**Root causes this identifies**:
- Which authorities test IPv6 (not all do)
- IPv6 specifically blocked by some authorities
- Tooltip: `Source: CollecTor | File: vote | Field: 'a' line (IPv6 address)`

---

### Question 7: "What are the exact criteria for receiving [flag]?"
**Examples**: "Exact criteria for receiving a BadExit flag", "Intentionally obtaining a MiddleOnly flag"

| Where to Look | What You'll See |
|---------------|-----------------|
| **Authority Health Page → Flag Thresholds Table** | ALL thresholds for ALL flags from each authority |
| **Column tooltips** | Exact field names: `flag-thresholds guard-wfu=98%`, `stable-uptime=1693440` |

**Thresholds shown**:
- Guard: `guard-bw-inc-exits`, `guard-tk`, `guard-wfu`
- Stable: `stable-uptime`, `stable-mtbf`
- Fast: `fast-speed`
- HSDir: `hsdir-wfu`, `hsdir-tk`

---

### Question 8: "Relay's first seen date got reset"
**Examples**: "First seen date got reset", "Time Known reset"

| Where to Look | What You'll See |
|---------------|-----------------|
| **Relay Page → TK Column** | Time Known from each authority (in days) |
| **Relay Page → Values Summary → Time Known** | Your TK value vs threshold |

**Root causes this identifies**:
- New relay identity (key regeneration)
- TK resets when authorities lose track of relay
- Tooltip shows: `Source: CollecTor | File: vote | Field: stats tk=X`

---

### Question 9: "Why is authority X not voting for my relay?"
**Examples**: "Which authorities see my relay?"

| Where to Look | What You'll See |
|---------------|-----------------|
| **Relay Page → Per-Authority Table** | Full row per authority showing all data |
| **Relay Page → Voted status** | Which authorities included your relay in their vote |
| **Authority Health Page → Voted Column** | Whether authority submitted ANY vote this hour |

---

### Question 10: "Is there something wrong with a specific directory authority?"
**Examples**: Authority problems affecting multiple relays

| Where to Look | What You'll See |
|---------------|-----------------|
| **Authority Health Page → Table 1** | Online status, vote status, BW scanner, latency for all 9 authorities |
| **Authority Health Page → Alerts** | "⚠️ faravahar responding slowly (89ms)" |
| **Authority Health Page → Flag Thresholds** | Per-authority thresholds (catch anomalies) |

---

### Question 11: "Flags gone after restart"
**Examples**: "All my flags disappeared after restarting Tor"

| Where to Look | What You'll See |
|---------------|-----------------|
| **Relay Page → Time Known Column** | TK value resets if identity key changed |
| **Relay Page → WFU Column** | WFU may drop if restart caused downtime |
| **Relay Page → Flags Assigned Column** | Current flags from each authority |

**Root causes this identifies**:
- Identity key regeneration resets TK to 0
- Downtime during restart drops WFU below thresholds
- Authorities take time to re-measure bandwidth

---

### Question 12: "How do I get the HSDir flag?"
**Examples**: "Setting a relay as an HSDirectory?"

| Where to Look | What You'll See |
|---------------|-----------------|
| **Authority Health Page → HSDir WFU Column** | Per-authority threshold (typically 98%) |
| **Authority Health Page → HSDir TK Column** | Per-authority threshold (typically ~10 days) |
| **Relay Page → Values Summary** | Your WFU and TK vs HSDir thresholds |

**Requirements for HSDir** (from `flag-thresholds`):
- `hsdir-wfu` ≥ 98% (Weighted Fractional Uptime)
- `hsdir-tk` ≥ ~10 days (Time Known)
- Must have Stable flag

---

### Question 13: "Why does my relay show different data on different metrics sites?"
**Examples**: "Metrics falsely showing my relay as offline", discrepancies between sites

| Where to Look | What You'll See |
|---------------|-----------------|
| **All column tooltips** | Exact data source: "Source: CollecTor \| File: vote \| Field: X" |
| **Per-Authority Table** | Different authorities may see different things |

**Root causes this identifies**:
- Different authorities have different views of your relay
- Metrics sites may use different data sources or caching
- Our data shows EXACTLY where each value comes from

---

### Summary: Where Each Data Point Comes From

| Question | Data Source | Specific Field |
|----------|-------------|----------------|
| In consensus? | CollecTor votes | Relay has `r` entry in ≥5 votes |
| Guard flag? | CollecTor votes | `stats wfu=`, `stats tk=`, `flag-thresholds guard-*` |
| Stable flag? | CollecTor votes | `flag-thresholds stable-uptime` |
| Fast flag? | CollecTor votes | `flag-thresholds fast-speed` |
| HSDir flag? | CollecTor votes | `flag-thresholds hsdir-wfu`, `hsdir-tk` |
| Measured bandwidth? | CollecTor votes | `w Measured=X` |
| Authority reachability? | CollecTor votes | `r` line (IPv4), `a` line (IPv6) |
| BW scanner status? | CollecTor votes | `bandwidth-file-headers` line present |
| Authority health? | Direct HTTP + Onionoo | Latency, running status |

---

## 📊 Complete Flag Reference

Directory authorities publish these flags in their `known-flags` line:

```
Authority BadExit Exit Fast Guard HSDir MiddleOnly Running Stable StaleDesc Sybil V2Dir Valid
```

### Flags WITH Numeric Thresholds (from `flag-thresholds`)

These flags have thresholds we can display and compare against:

| Flag | Threshold Fields | Description | Shown On |
|------|------------------|-------------|----------|
| **Fast** | `fast-speed` | Relay bandwidth exceeds network median | Relay Page, Authority Health |
| **Guard** | `guard-bw-inc-exits`, `guard-bw-exc-exits`, `guard-tk`, `guard-wfu` | Entry guard eligibility | Relay Page, Authority Health |
| **HSDir** | `hsdir-wfu`, `hsdir-tk` | Hidden service directory eligibility | Relay Page, Authority Health |
| **Stable** | `stable-uptime`, `stable-mtbf` | Long-running relay | Relay Page, Authority Health |

**Threshold Details:**

| Threshold | Typical Value | Description |
|-----------|---------------|-------------|
| `fast-speed` | 0.1-1.0 MB/s | Minimum bandwidth for Fast flag |
| `guard-bw-inc-exits` | 10-35 MB/s | Guard bandwidth (including exits) |
| `guard-bw-exc-exits` | 10-35 MB/s | Guard bandwidth (excluding exits) |
| `guard-tk` | ~8 days (691200s) | Time authority has known relay |
| `guard-wfu` | 98% | Weighted Fractional Uptime |
| `stable-uptime` | 14-20 days | Uptime requirement for Stable |
| `stable-mtbf` | varies | Mean Time Between Failures |
| `hsdir-wfu` | 98% | WFU for HSDir |
| `hsdir-tk` | ~10 days | Time Known for HSDir |

### Flags WITHOUT Numeric Thresholds

These flags are determined by other criteria (not from `flag-thresholds`):

| Flag | How It's Determined | Can We Show? |
|------|---------------------|--------------|
| **Authority** | Hardcoded list of directory authorities | ✓ Yes (relay has Authority flag in Onionoo) |
| **BadExit** | Manually flagged by Tor Project for misbehaving exits | ✓ Yes (check if flag present) |
| **Exit** | Exit policy allows ports 80, 443 | ✓ Yes (check exit_policy field) |
| **MiddleOnly** | Manually assigned to suspicious relays | ✓ Yes (check if flag present) |
| **Running** | Authority can reach relay (reachability test) | ✓ Yes (check IPv4/IPv6 reachability) |
| **StaleDesc** | Descriptor older than 18 hours | ✓ Yes (check descriptor age) |
| **Sybil** | Suspected Sybil attack node (manual) | ✓ Yes (check if flag present) |
| **V2Dir** | Supports v2 directory protocol | ✓ Yes (check if flag present) |
| **Valid** | Meets minimum requirements (valid identity) | ✓ Yes (check if flag present) |

### Where Each Flag Is Shown

**Relay Page (`relay-info.html`):**

| Section | Flags Shown |
|---------|-------------|
| Summary Table | Fast, Guard, HSDir, Stable (with thresholds) |
| Detail Table → Flags Column | ALL flags assigned by each authority |
| Detail Table → Threshold Columns | Fast, Guard BW, Guard TK, Guard WFU, Stable, HSDir WFU, HSDir TK |

**Authority Health Page (`misc-authorities.html`):**

| Section | Flags Shown |
|---------|-------------|
| Flag Thresholds Table | All threshold-based flags (Fast, Guard, HSDir, Stable) |
| Network Flag Totals | Running, Fast, Stable, Guard, Exit, HSDir counts |

---

## 🚀 Phase 1: Per-Relay Consensus Diagnostics

**Location**: `relay-info.html` - New "Consensus Diagnostics" section

**Data Sources**: CollecTor votes + bandwidth files (fetched once/hour, indexed by fingerprint)

### Features

| Section | Data Source | What It Shows |
|---------|-------------|---------------|
**Single merged table** combining authority votes, bandwidth, and all flag thresholds:

| Column | Data Source | Description |
|--------|-------------|-------------|
| **Authority** | Onionoo (dynamic) | Authority name, links to relay page |
| **IPv4/IPv6** | CollecTor votes | Reachability status per authority |
| **Flags Assigned** | CollecTor votes | Which flags this authority is assigning |
| **Measured BW** | CollecTor votes | Measured bandwidth (N/A for non-BW authorities) |
| **WFU** | CollecTor votes (`stats wfu=`) | Relay's WFU value (threshold ≥98% in tooltip) |
| **Time Known** | CollecTor votes (`stats tk=`) | Relay's TK value (threshold ≥8 days in tooltip) |
| **Guard BW Req** | CollecTor thresholds | Per-authority threshold vs relay's value (varies) |
| **Stable Req** | CollecTor thresholds | Per-authority threshold vs relay's value (varies) |
| **Fast Req** | CollecTor thresholds | Per-authority threshold vs relay's value (varies) |

### Mockup

**Design notes**:
- **Single merged table** - Authority votes, bandwidth, and all threshold data in ONE table
- Authority names link to their dedicated relay page (e.g., `/relay/FINGERPRINT.html`)
- For **constant thresholds** (WFU ≥98%, Time Known ≥8 days): threshold shown in **column tooltip**, relay value shown in cell
- For **variable thresholds** (Guard BW, Stable Uptime, Fast Speed): both threshold and relay value shown
- Consensus requirement shown as **tooltip** (hover over status to see "5/9 = majority")
- Authority count is **dynamic** (discovered from Onionoo, not hardcoded)

**Data sources from CollecTor votes:**
- Per-relay stats: `wfu`, `tk` (time known), `mtbf`, `Measured` (bandwidth)
- Per-authority thresholds: `guard-wfu`, `guard-tk`, `guard-bw-inc-exits`, `stable-uptime`, `fast-speed`

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 🔍 Consensus Diagnostics                                                                                               │
│ Data from: 2025-12-26 04:00 UTC (latest CollecTor)                                                                    │
├────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                        │
│ Status: IN CONSENSUS (8/9 authorities) [ⓘ]    ← tooltip: "Consensus requires majority: 5/9 (9÷2+1=5)"                 │
│                                                                                                                        │
│ ══ Per-Authority Voting Details ════════════════════════════════════════════════════════════════════════════════════════│
│                                                                                                                        │
│ ┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐│
│ │ TWO-TABLE DESIGN RATIONALE:                                                                                        ││
│ │                                                                                                                    ││
│ │ TABLE 1 (Summary): Quick answers. "Why don't I have X flag?" - See your value vs consensus threshold.             ││
│ │                    Shows AGGREGATE data: your relay values vs majority consensus requirements.                     ││
│ │                                                                                                                    ││
│ │ TABLE 2 (Detail):  Diagnose specific issues. "Which authorities can't reach me?" - See per-authority breakdown.   ││
│ │                    Shows PER-AUTHORITY data: what each authority sees, their thresholds, your status with them.   ││
│ │                                                                                                                    ││
│ │ COLOR CODING: green text = meets threshold, red text = below threshold, yellow text = partial, gray text = N/A    ││
│ └────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘│
│                                                                                                                        │
│ ══ TABLE 1: SUMMARY (Your Relay vs Consensus) ══════════════════════════════════════════════════════════════════════════│
│                                                                                                                        │
│ Quick overview showing your relay's values vs what the MAJORITY of authorities require.                               │
│                                                                                                                        │
│ ┌─────────────────┬─────────────┬──────────────────────────┬───────────────────────────────────────────────────────────┐│
│ │ Metric [ⓘ]     │ Your Value  │ Consensus Threshold [ⓘ] │ Status                                                    ││
│ ├─────────────────┼─────────────┼──────────────────────────┼───────────────────────────────────────────────────────────┤│
│ │ In Consensus    │ 8/9 auths   │ ≥5/9 (majority)          │ IN CONSENSUS                                  (green)    ││
│ │ IPv4 Reachable  │ 8/9 auths   │ ≥5/9 (majority)          │ REACHABLE                                     (green)    ││
│ │ IPv6 Reachable  │ 5/7 tested  │ ≥majority of testers     │ PARTIAL - 2 auths can't reach                 (yellow)   ││
│ ├─────────────────┼─────────────┼──────────────────────────┼───────────────────────────────────────────────────────────┤│
│ │ WFU             │ 96.2%       │ ≥98% (guard-wfu)         │ BELOW - cannot get Guard/HSDir                (red)      ││
│ │ Time Known      │ 45 days     │ ≥8 days (guard-tk)       │ MEETS                                         (green)    ││
│ │ Guard BW        │ 25 MB/s     │ 10-35 MB/s (varies)      │ PARTIAL - meets 5/9 auths                     (yellow)   ││
│ │ Stable Uptime   │ 45 days     │ 14.2-19.8 days (varies)  │ MEETS - all auths                             (green)    ││
│ │ Stable MTBF     │ 340 days    │ varies by authority      │ MEETS - all auths                             (green)    ││
│ │ Fast Speed      │ 25 MB/s     │ 0.1-1.0 MB/s (varies)    │ MEETS - all auths                             (green)    ││
│ │ HSDir WFU       │ 96.2%       │ ≥98% (hsdir-wfu)         │ BELOW - cannot get HSDir                      (red)      ││
│ │ HSDir TK        │ 45 days     │ ≥10 days (hsdir-tk)      │ MEETS                                         (green)    ││
│ └─────────────────┴─────────────┴──────────────────────────┴───────────────────────────────────────────────────────────┘│
│                                                                                                                        │
│ 💡 Advice: To get Guard flag, increase WFU to ≥98% (maintain better uptime).                                          │
│                                                                                                                        │
│ Summary tooltips:                                                                                                      │
│   • Your Value [ⓘ]: "Source: CollecTor | File: vote | Field: stats wfu=X, stats tk=X, w Measured=X"                  │
│   • Consensus Threshold [ⓘ]: "Source: CollecTor | File: vote | Field: flag-thresholds [field]=X | Range across auths"│
│                                                                                                                        │
│ ══ TABLE 2: PER-AUTHORITY DETAILS (Diagnosis) ══════════════════════════════════════════════════════════════════════════│
│                                                                                                                        │
│ Detailed breakdown showing what EACH authority sees. Use this to diagnose specific issues.                            │
│ Text color: green = meets this authority's threshold, red = below threshold                                           │
│                                                                                                                        │
│ ┌────────────┬──────┬──────┬──────────────────┬──────────┬─────────┬─────────┬──────────┬──────────┬──────────┬──────────┐│
│ │ Authority  │ IPv4 │ IPv6 │ Flags Assigned   │ Meas. BW │ WFU     │ TK      │ Guard BW │ Stable   │ Fast     │ HSDir TK ││
│ ├────────────┼──────┼──────┼──────────────────┼──────────┼─────────┼─────────┼──────────┼──────────┼──────────┼──────────┤│
│ │ moria1 ↗   │ Yes  │ Yes  │ Fast Stable      │ 46.2 MB/s│ 96.2%*  │ 45d     │ ≥30 MB/s*│ ≥19.6d   │ ≥1.0 MB/s│ ≥9.8d    ││
│ │ tor26 ↗    │ Yes  │ No*  │ Fast Stable      │ 44.8 MB/s│ 96.2%*  │ 45d     │ ≥34 MB/s*│ ≥19.8d   │ ≥0.1 MB/s│ ≥9.8d    ││
│ │ dizum ↗    │ Yes  │ N/T  │ Fast Guard Stable│ N/A      │ 96.2%*  │ 45d     │ ≥10 MB/s │ ≥14.2d   │ ≥0.1 MB/s│ ≥9.8d    ││
│ │ gabelmoo ↗ │ Yes  │ Yes  │ Fast Stable      │ 44.1 MB/s│ 96.2%*  │ 45d     │ ≥35 MB/s*│ ≥19.6d   │ ≥0.1 MB/s│ ≥9.8d    ││
│ │ bastet ↗   │ Yes  │ Yes  │ Fast Guard Stable│ 43.9 MB/s│ 96.2%*  │ 45d     │ ≥10 MB/s │ ≥14.3d   │ ≥0.1 MB/s│ ≥9.8d    ││
│ │ dannenberg↗│ Yes  │ Yes  │ Fast Stable      │ N/A      │ 96.2%*  │ 45d     │ ≥35 MB/s*│ ≥19.2d   │ ≥0.1 MB/s│ ≥9.8d    ││
│ │ maatuska ↗ │ Yes  │ Yes  │ Fast Guard Stable│ 45.1 MB/s│ 96.2%*  │ 45d     │ ≥10 MB/s │ ≥19.3d   │ ≥0.1 MB/s│ ≥9.8d    ││
│ │ longclaw ↗ │ Yes  │ N/T  │ Fast Guard Stable│ 44.5 MB/s│ 96.2%*  │ 45d     │ ≥28 MB/s*│ ≥18.5d   │ ≥0.1 MB/s│ ≥9.8d    ││
│ │ faravahar↗ │ No*  │ No*  │ —                │ —        │ —       │ —       │ —        │ —        │ —        │ —        ││
│ └────────────┴──────┴──────┴──────────────────┴──────────┴─────────┴─────────┴──────────┴──────────┴──────────┴──────────┘│
│                                                                                                                        │
│ Color coding: green text = meets threshold, red text (marked with *) = below threshold                                │
│ N/T = Not Tested (gray), N/A = No bandwidth scanner (gray), ↗ = link to authority relay page                          │
│                                                                                                                        │
│ Detail table tooltips (per column):                                                                                    │
│ ┌──────────────────┬────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│ │ Column           │ Tooltip Content                                                                                │  │
│ ├──────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────┤  │
│ │ Authority        │ "Source: Onionoo | Field: nickname, fingerprint"                                              │  │
│ │ IPv4             │ "Source: CollecTor | File: vote | Relay reachable via IPv4 (has 'r' entry)"                   │  │
│ │ IPv6             │ "Source: CollecTor | File: vote | Field: 'a' line | N/T = authority doesn't test IPv6"        │  │
│ │ Flags Assigned   │ "Source: CollecTor | File: vote | Field: 's' line (ALL flags authority assigns)"              │  │
│ │ Meas. BW         │ "Source: CollecTor | File: vote | Field: w Measured=X | N/A = no bandwidth-file-headers"      │  │
│ │ WFU              │ "Source: CollecTor | Your: stats wfu=X | Threshold: guard-wfu=X (also used for hsdir-wfu)"    │  │
│ │ TK               │ "Source: CollecTor | Your: stats tk=X | Threshold: guard-tk=X"                                │  │
│ │ Guard BW         │ "Source: CollecTor | Your BW vs Threshold: guard-bw-inc-exits=X"                              │  │
│ │ Stable           │ "Source: CollecTor | Threshold: stable-uptime=X | Also needs stable-mtbf"                     │  │
│ │ Fast             │ "Source: CollecTor | Threshold: fast-speed=X"                                                 │  │
│ │ HSDir TK         │ "Source: CollecTor | Threshold: hsdir-tk=X | Also needs hsdir-wfu (same as guard-wfu)"        │  │
│ └──────────────────┴────────────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                                        │
│ Legend:                                                                                                                │
│   ↗ = link to authority relay page                                                                                     │
│   Green text = meets threshold, Red text = below threshold                                                             │
│   ⚪ = authority doesn't test this (IPv6)                                                                              │
│   N/A = authority does not run bandwidth scanner (detected from absence of bandwidth-file-headers in vote)             │
│   All thresholds are DYNAMIC - pulled from each authority's flag-thresholds line in their vote file                   │
│                                                                                                                        │
│ ⚠️ Issues: faravahar cannot reach relay • 4/9 authorities NOT assigning Guard (BW below threshold)                    │
│                                                                                                                        │
│ Note: ALL thresholds are pulled dynamically from each authority's vote file (flag-thresholds line).                   │
│ Even thresholds that typically appear consistent (like WFU 98%) could change - we never hardcode values.              │
│ BW Authority status is detected dynamically by checking for bandwidth-file-headers presence in each vote.             │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Data Available from CollecTor Votes

**All values are pulled dynamically** - no hardcoded constants. Even thresholds that appear consistent (like WFU 98%) could change.

**Per-relay stats** (in `stats` line of each relay entry):
| Field | Description | Example |
|-------|-------------|---------|
| `wfu` | Weighted Fractional Uptime | 0.957168 (95.7%) |
| `tk` | Time Known (seconds) | 853402 (~9.8 days) |
| `mtbf` | Mean Time Between Failures | 1203750817 |

**Per-relay bandwidth** (in `w` line):
| Field | Description | Example |
|-------|-------------|---------|
| `Bandwidth` | Advertised bandwidth | 10000 |
| `Measured` | Measured bandwidth (from BW scanner) | 66000 |

**Per-authority thresholds** (in `flag-thresholds` header) - **ALL pulled dynamically**:
| Field | Description | Typical Value |
|-------|-------------|---------------|
| `guard-wfu` | WFU threshold for Guard | ~98% |
| `guard-tk` | Time Known threshold for Guard | ~8 days |
| `guard-bw-inc-exits` | Guard BW threshold (with exits) | 10-35 MB/s |
| `guard-bw-exc-exits` | Guard BW threshold (no exits) | varies |
| `stable-uptime` | Stable flag uptime threshold | 14-20 days |
| `stable-mtbf` | Stable flag MTBF threshold | varies |
| `fast-speed` | Fast flag speed threshold | 0.1-1.0 MB/s |
| `hsdir-wfu` | HSDir WFU threshold | ~98% |
| `hsdir-tk` | HSDir Time Known threshold | varies |

**Known flags** (from `known-flags` line) - all flags authorities can assign:
```
Authority BadExit Exit Fast Guard HSDir MiddleOnly Running Stable StaleDesc Sybil V2Dir Valid
```

**BW Authority detection** - dynamically determined by presence of `bandwidth-file-headers` in vote file:
- If present → authority runs bandwidth scanner (sbws)
- If absent → authority does NOT run bandwidth scanner

---

## 🏛️ Phase 2: Enhanced Directory Authorities Page

**Location**: `misc-authorities.html` - Enhance existing page (no new pages)

**Data Sources**: CollecTor votes + consensus + Direct HTTP latency checks

### Features

| Section | Data Source | What It Shows |
|---------|-------------|---------------|
| **Consensus Status** | CollecTor consensus | Fresh/stale, valid-until, next consensus time |
| **Authority Status** | Direct HTTP + votes | Latency, vote status, relay counts |
| **Flag Thresholds** | CollecTor votes | Current Guard/Stable/Fast/HSDir thresholds |
| **Flag Distribution** | CollecTor consensus | Network-wide flag counts |

### Mockup - Complete Merged Page

**Design notes**:
- **Single page** - merges existing `misc-authorities.html` with new health/threshold features
- **Two tables** for readability:
  - Table 1: Main authority status (existing columns + Vote/BW Auth/Latency)
  - Table 2: Flag thresholds per authority (new)
- Authority list is **dynamic** - discovered from Onionoo API relays with "Authority" flag
- Authority names link to their relay pages

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Directory Authorities by Network Health                                                          │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                  │
│ Directory authorities vote on the status of relays in the Tor network and provide bandwidth     │
│ measurements. Monitor their health and consensus participation.                                  │
│                                                                                                  │
│ ┌─────────────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ SUMMARY                                                                                     │ │
│ ├─────────────────────────────────────────────────────────────────────────────────────────────┤ │
│ │ • Directory Authorities: 9 discovered (dynamic from Onionoo)                               │ │
│ │ • Consensus Status: FRESH (green) │ 9/9 Voted │ Next: 15:00 UTC (23 min)   [NEW]           │ │
│ │ • Version Compliance: 8/9 on recommended version │ 1/9 non-compliant                       │ │
│ │ • Uptime Status (1M): 7 above average │ 1 below average │ 1 problematic                    │ │
│ │ • Latency Status: 8/9 OK │ 1/9 slow                                        [NEW]           │ │
│ └─────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                                  │
│ Last updated: 2025-12-26 04:00:00. Data from Onionoo API + CollecTor.                           │
│                                                                                                  │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ TABLE 1: DIRECTORY AUTHORITY STATUS (existing + 3 new columns). Hover columns for source.        │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                  │
│ ┌─────────┬────────┬───────┬────────┬───────┬────────┬─────────────────┬─────────┬───────┬──────┐│
│ │Authority│ Online │Voted[ⓘ]│BW[ⓘ] │Lat[ⓘ]│ AS     │Uptime(1M/6M/1Y) │ Version │Rec.Ver│Ctry  ││
│ ├─────────┼────────┼───────┼────────┼───────┼────────┼─────────────────┼─────────┼───────┼──────┤│
│ │moria1 ↗ │ 🟢     │  Yes  │  Yes   │  12ms │AS3     │99.9/99.8/99.7   │ 0.4.8.9 │  Yes  │  US  ││
│ │tor26 ↗  │ 🟢     │  Yes  │  Yes   │  45ms │AS680   │99.8/99.7/99.5   │ 0.4.8.9 │  Yes  │  AT  ││
│ │dizum ↗  │ 🟢     │  Yes  │  No*   │  38ms │AS51167 │99.7/99.5/99.3   │ 0.4.8.9 │  Yes  │  NL  ││
│ │...      │ ...    │  ...  │  ...   │  ...  │...     │...              │ ...     │  ...  │  ... ││
│ └─────────┴────────┴───────┴────────┴───────┴────────┴─────────────────┴─────────┴───────┴──────┘│
│                                                                                                  │
│ Column tooltips (new columns marked [ⓘ]):                                                        │
│ ┌────────────┬─────────────────────────────────────────────────────────────────────────────────┐│
│ │ Column     │ Tooltip                                                                         ││
│ ├────────────┼─────────────────────────────────────────────────────────────────────────────────┤│
│ │ Authority  │ "Source: Onionoo | File: details | Field: nickname (has Authority flag)"       ││
│ │ Online     │ "Source: Onionoo | File: details | Field: running"                             ││
│ │ Voted [ⓘ] │ "Source: CollecTor | File: vote | Vote file exists for this consensus hour"    ││
│ │ BW [ⓘ]    │ "Source: CollecTor | File: vote | Has 'bandwidth-file-headers' line = scanner" ││
│ │ Lat [ⓘ]   │ "Source: Direct HTTP | HEAD request to dir_address | Response time in ms"      ││
│ │ AS         │ "Source: Onionoo | File: details | Field: as"                                  ││
│ │ Uptime     │ "Source: Onionoo | File: uptime | 1M/6M/1Y uptime percentages"                 ││
│ │ Version    │ "Source: Onionoo | File: details | Field: version"                             ││
│ │ Rec.Ver    │ "Source: Onionoo | File: details | Field: recommended_version"                 ││
│ │ Country    │ "Source: Onionoo | File: details | Field: country"                             ││
│ └────────────┴─────────────────────────────────────────────────────────────────────────────────┘│
│                                                                                                  │
│ ⚠️ Alerts: faravahar responding slowly (89ms) │ dannenberg on non-recommended version           │
│                                                                                                  │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ TABLE 2: FLAG THRESHOLDS BY AUTHORITY (ALL pulled dynamically from vote files)        [NEW]      │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                  │
│ Each authority calculates thresholds based on the relays it observes. Hover columns for source. │
│                                                                                                  │
│ ┌─────────┬──────────┬─────────┬─────────┬─────────┬──────────┬────────┬─────────┬─────────┐    │
│ │Authority│Guard BW  │Guard TK │Guard WFU│Stable   │Stable    │ Fast   │HSDir WFU│HSDir TK │    │
│ │         │[ⓘ]      │[ⓘ]     │[ⓘ]     │Uptime[ⓘ]│MTBF[ⓘ]  │[ⓘ]    │[ⓘ]     │[ⓘ]     │    │
│ ├─────────┼──────────┼─────────┼─────────┼─────────┼──────────┼────────┼─────────┼─────────┤    │
│ │moria1   │ 30 MB/s  │ 8.0 d   │ 98%     │ 19.6 d  │ 340 d    │1.0 MB/s│ 98%     │ 9.8 d   │    │
│ │tor26    │ 34 MB/s  │ 8.0 d   │ 98%     │ 19.8 d  │ 342 d    │0.1 MB/s│ 98%     │ 9.8 d   │    │
│ │dizum    │ 10 MB/s  │ 8.0 d   │ 98%     │ 14.2 d  │ 280 d    │0.1 MB/s│ 98%     │ 9.8 d   │    │
│ │...      │ ...      │ ...     │ ...     │ ...     │ ...      │ ...    │ ...     │ ...     │    │
│ └─────────┴──────────┴─────────┴─────────┴─────────┴──────────┴────────┴─────────┴─────────┘    │
│                                                                                                  │
│ Column tooltips (hover for data source):                                                         │
│ ┌─────────────┬──────────────────────────────────────────────────────────────────────────────┐  │
│ │ Column      │ Tooltip                                                                      │  │
│ ├─────────────┼──────────────────────────────────────────────────────────────────────────────┤  │
│ │ Authority   │ "Source: Onionoo | Field: nickname (relays with Authority flag)"            │  │
│ │ Guard BW    │ "Source: CollecTor | flag-thresholds guard-bw-inc-exits (varies 10-35 MB/s)"│  │
│ │ Guard TK    │ "Source: CollecTor | flag-thresholds guard-tk (typically 8 days)"           │  │
│ │ Guard WFU   │ "Source: CollecTor | flag-thresholds guard-wfu (typically 98%)"             │  │
│ │ Stable Up   │ "Source: CollecTor | flag-thresholds stable-uptime (varies 14-20 days)"     │  │
│ │ Stable MTBF │ "Source: CollecTor | flag-thresholds stable-mtbf (Mean Time Between Failures)"│
│ │ Fast        │ "Source: CollecTor | flag-thresholds fast-speed (varies by authority)"      │  │
│ │ HSDir WFU   │ "Source: CollecTor | flag-thresholds hsdir-wfu (typically 98%)"             │  │
│ │ HSDir TK    │ "Source: CollecTor | flag-thresholds hsdir-tk (typically ~10 days)"         │  │
│ └─────────────┴──────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                  │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ NETWORK FLAG TOTALS                                                                   [NEW]      │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                  │
│ Running: 7,234 │ Fast: 6,891 │ Stable: 6,012 │ Guard: 2,845 │ Exit: 1,923 │ HSDir: 5,678        │
│                                                                                                  │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ LEGEND                                                                                           │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                  │
│ • Online: 🟢 = Online, 🟡 = Slow (>100ms latency), 🔴 = Offline                                 │
│ • Voted: "Yes" (green) = Submitted vote | "No" (red) = No vote this period                      │
│ • BW Auth: "Yes" (green) = Has scanner | "No" (red, marked *) = No bandwidth scanner            │
│ • Latency: Response time to authority's directory port (checked hourly)              [NEW]      │
│ • Uptime Z-Score: Statistical deviation from average (green >0.3, red ≤-2.0)                    │
│ • Rec. Ver.: "Yes" (green) = Recommended version | "No" (red) = Not recommended                 │
│ • Flag Thresholds: ALL values pulled dynamically from each authority's vote file     [NEW]      │
│   - Guard: BW (guard-bw-inc-exits), TK (guard-tk), WFU (guard-wfu)                              │
│   - Stable: uptime (stable-uptime), MTBF (stable-mtbf)                                          │
│   - Fast: speed (fast-speed)                                                                    │
│   - HSDir: WFU (hsdir-wfu), TK (hsdir-tk)                                                       │
│   - Fast Speed: Bandwidth required for Fast flag (fast-speed)                                   │
│   - WFU: Weighted Fractional Uptime required (guard-wfu)                                        │
│                                                                                                  │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Data sources: Onionoo API (relay data) + CollecTor (votes, thresholds)                          │
│ Last updated: 2025-12-26 04:00:00 (refreshes hourly)                                            │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Page Structure Summary

**Single page** (`misc-authorities.html`) with **two tables** for readability:

| Section | Content |
|---------|---------|
| **Summary** | Authority count, consensus status, version compliance, uptime status, latency status |
| **Table 1: Authority Status** | Existing columns (Name, Online, AS, Country, Uptime, Version, Rec.Ver, First Seen, Last Restarted) + NEW columns (Voted, BW Auth, Latency) |
| **Table 2: Flag Thresholds** | Per-authority thresholds for ALL flags (Guard BW/TK/WFU, Stable, Fast, HSDir) - all dynamic |
| **Alerts** | Warnings about slow/down authorities, non-recommended versions |
| **Network Totals** | Flag distribution (Running, Fast, Stable, Guard, Exit, HSDir) |
| **Legend** | Explanation of all columns and indicators |

### New Columns Added to Existing Table (Table 1)

| Column | Source | Description |
|--------|--------|-------------|
| `Voted` | CollecTor | "Yes" (green) if authority submitted vote this consensus period |
| `BW Auth` | CollecTor (dynamic) | "Yes" (green) if vote contains `bandwidth-file-headers` (runs sbws scanner) |
| `Latency` | Direct HTTP | Response time to dir port (ms) |

**BW Authority Detection**: Dynamically determined from each authority's vote file by checking for the presence of the `bandwidth-file-headers` line. This is more reliable than a static list and automatically adapts if authorities start/stop running bandwidth scanners.

### New Section: Flag Thresholds Table (All Dynamic)

**All thresholds pulled dynamically from each authority's `flag-thresholds` line** - no hardcoded values.

| Column | Source Field | Description |
|--------|--------------|-------------|
| `Guard BW` | guard-bw-inc-exits | Bandwidth required for Guard flag |
| `Guard BW (no exit)` | guard-bw-exc-exits | Guard BW for non-exit relays |
| `Guard WFU` | guard-wfu | WFU required for Guard flag |
| `Guard TK` | guard-tk | Time Known required for Guard flag |
| `Stable Uptime` | stable-uptime | Uptime required for Stable flag |
| `Stable MTBF` | stable-mtbf | MTBF required for Stable flag |
| `Fast Speed` | fast-speed | Speed required for Fast flag |
| `HSDir WFU` | hsdir-wfu | WFU required for HSDir flag |
| `HSDir TK` | hsdir-tk | Time Known required for HSDir flag |

**All flags authorities can assign** (from `known-flags` line):
- Authority, BadExit, Exit, Fast, Guard, HSDir, MiddleOnly, Running, Stable, StaleDesc, Sybil, V2Dir, Valid

---

## ⚡ Compute Efficiency Design

### Dynamic Authority Discovery

Authority list is **not hardcoded** - discovered from Onionoo API by finding relays with "Authority" flag.

```python
# Discovered during Onionoo details processing
authorities = [r for r in relays if 'Authority' in r.get('flags', [])]
authority_count = len(authorities)  # Currently 9, but dynamic
majority_required = (authority_count // 2) + 1  # e.g., 9 → 5, 10 → 6
```

**Execution order** (CollecTor runs AFTER Onionoo):
1. `fetch_onionoo_details()` → Returns relays with flags
2. Extract authority list from relays with "Authority" flag
3. `fetch_collector_consensus_data(authorities)` → Pass discovered authorities
4. Build relay index using discovered authority list

### Consensus Voting Requirement (Dynamic)

Displayed as **tooltip** on individual relay pages (not inline text).

```jinja2
{# In relay-info.html - consensus status with tooltip #}
<span class="consensus-status" 
      title="Consensus requires majority vote: {{ majority_required }}/{{ authority_count }} authorities ({{ authority_count }}÷2+1)">
  {% if in_consensus %}IN CONSENSUS{% else %}NOT IN CONSENSUS{% endif %}
  ({{ vote_count }}/{{ authority_count }})
</span>
```

Formula: `majority_required = floor(authority_count / 2) + 1`
- 9 authorities → 5 required (current)
- 10 authorities → 6 required (if added)
- 8 authorities → 5 required (if one removed)

### Data Flow (Minimizing Hourly Compute)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    HOURLY DATA FETCH (ONCE)                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  CollecTor API (runs in parallel with other workers)               │
│  ├─ GET /recent/relay-descriptors/votes/      (~50MB, 9 files)     │
│  └─ GET /recent/relay-descriptors/bandwidths/ (~50MB, 7 files)     │
│                                                                     │
│         ↓ Parse ONCE, Index by fingerprint                         │
│                                                                     │
│  relay_index[fingerprint] = {                                       │
│      'votes': {auth_name: {flags, bandwidth, ...}},                │
│      'bandwidth': {auth_name: {bw_value, ...}}                     │
│  }                                                                  │
│                                                                     │
│         ↓ Cache to disk                                             │
│                                                                     │
│  cache/consensus/collector_data.json                                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  INTEGRATION: Uses EXISTING relay loops (NO new loops)             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  coordinator.create_relay_set():                                    │
│      relay_set.collector_data = {...}  # Attach indexed data       │
│                                                                     │
│  relays._reprocess_collector_data():  # NEW - follows existing     │
│      # Called from coordinator AFTER collector_data is attached    │
│      # Single pass through relays, like _reprocess_uptime_data()   │
│      for relay in self.json["relays"]:                             │
│          fp = relay['fingerprint']                                  │
│          relay['collector_diagnostics'] = index.get(fp)  # O(1)    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Modular Architecture (follows existing patterns)

```
lib/consensus/                        # NEW MODULE
├── __init__.py                       # Module init, exports
├── collector_fetcher.py              # CollectorFetcher class (fetch + parse)
├── authority_monitor.py              # Authority latency checks (Phase 2)
└── diagnostics.py                    # Per-relay diagnostic formatting

lib/workers.py                        # MODIFY (add worker function)
├── fetch_collector_consensus_data()  # Follows fetch_onionoo_uptime() pattern

lib/coordinator.py                    # MODIFY (add to api_workers)
├── api_workers.append(...)           # Add collector worker
├── get_collector_consensus_data()    # Getter method
└── create_relay_set()                # Attach + trigger reprocess

lib/relays.py                         # MODIFY (add reprocess method)
├── _reprocess_collector_data()       # Follows _reprocess_uptime_data() pattern
└── (NO NEW LOOPS - uses existing preprocessing)
```

### Key Efficiency Principles

| Principle | Implementation |
|-----------|----------------|
| **Fetch once, use many** | CollecTor data fetched once/hour, indexed, cached |
| **Parallel fetching** | Uses existing `Coordinator.fetch_all_apis_threaded()` pattern |
| **NO new relay loops** | `_reprocess_collector_data()` follows `_reprocess_uptime_data()` pattern |
| **Index by fingerprint** | O(1) lookup during reprocessing, no per-relay parsing |
| **Graceful degradation** | If fetch fails, use cached data (up to 3 hours old) |

### Integration with Existing Relay Processing

```python
# lib/relays.py - NEW METHOD (follows _reprocess_uptime_data pattern)
def _reprocess_collector_data(self):
    """
    Process CollecTor data for per-relay diagnostics.
    
    Called from coordinator AFTER collector_data is attached.
    Follows same pattern as _reprocess_uptime_data() and _reprocess_bandwidth_data().
    
    NO NEW LOOPS - attaches pre-indexed data to relays in single pass.
    """
    if not hasattr(self, 'collector_data') or not self.collector_data:
        return
    
    relay_index = self.collector_data.get('relay_index', {})
    flag_thresholds = self.collector_data.get('flag_thresholds', {})
    
    # Single pass through relays (same loop pattern as _reprocess_uptime_data)
    for relay in self.json["relays"]:
        fingerprint = relay.get('fingerprint', '')
        
        if fingerprint in relay_index:
            indexed_data = relay_index[fingerprint]
            relay['collector_diagnostics'] = {
                'vote_count': len(indexed_data.get('votes', {})),
                'in_consensus': len(indexed_data.get('votes', {})) >= 5,  # Majority
                'authority_votes': indexed_data.get('votes', {}),
                'bandwidth_measurements': indexed_data.get('bandwidth', {}),
            }
        else:
            relay['collector_diagnostics'] = None

# lib/coordinator.py - MODIFY create_relay_set() (around line 275)
# Add after existing reprocess calls:
if collector_data:
    relay_set._reprocess_collector_data()
```

---

## 🧪 Testing Strategy

### Baseline Validation (Before Starting)

```bash
#!/bin/bash
# scripts/capture_baseline.sh - Run BEFORE any code changes

cd /workspace/allium

echo "=== Step 1: Capture baseline output ==="
python allium.py --progress --output-dir baseline_output/ 2>&1 | tee baseline_run.log

echo "=== Step 2: Save file inventory ==="
find baseline_output/ -type f -name "*.html" | sort > baseline_files.txt
wc -l baseline_files.txt

echo "=== Step 3: Create normalized baseline (remove timestamps) ==="
# Strip timestamps for diff comparison
mkdir -p baseline_normalized/
for f in $(find baseline_output/ -name "*.html"); do
    # Remove dynamic content: timestamps, generation dates
    sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}/TIMESTAMP/g' "$f" | \
    sed -E 's/Generated: .*/Generated: TIMESTAMP/g' > \
    "baseline_normalized/$(basename $f)"
done

echo "=== Step 4: Run existing test suite ==="
pytest tests/ -v 2>&1 | tee baseline_tests.log

echo "=== Baseline captured ==="
```

### Unit Test Requirements

| New File | Test File | Run After |
|----------|-----------|-----------|
| `lib/consensus/__init__.py` | `tests/test_consensus_init.py` | File created |
| `lib/consensus/collector_fetcher.py` | `tests/test_collector_fetcher.py` | File created |
| `lib/consensus/authority_monitor.py` | `tests/test_authority_monitor.py` | File created |

### Test Checkpoints

```bash
# After EACH new file:
pytest tests/test_<new_file>.py -v

# After EACH week/milestone:
pytest tests/ -v

# After EACH phase - full validation:
./scripts/validate_phase.sh
```

### Baseline Diff Comparison Script

```bash
#!/bin/bash
# scripts/validate_phase.sh - Run after each phase

cd /workspace/allium

echo "=== Step 1: Generate current output ==="
python allium.py --progress --output-dir current_output/ 2>&1 | tee current_run.log

echo "=== Step 2: Normalize current output (remove timestamps) ==="
mkdir -p current_normalized/
for f in $(find current_output/ -name "*.html"); do
    sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}/TIMESTAMP/g' "$f" | \
    sed -E 's/Generated: .*/Generated: TIMESTAMP/g' > \
    "current_normalized/$(basename $f)"
done

echo "=== Step 3: Run full test suite ==="
pytest tests/ -v
TEST_RESULT=$?

echo "=== Step 4: Compare to baseline (excluding new sections) ==="
# Full diff showing ALL changes
diff -r baseline_normalized/ current_normalized/ \
    --exclude="*.log" \
    > full_diff.txt 2>&1

# Count changes by type
echo ""
echo "=== DIFF SUMMARY ==="
echo "Files only in baseline: $(grep -c 'Only in baseline' full_diff.txt || echo 0)"
echo "Files only in current:  $(grep -c 'Only in current' full_diff.txt || echo 0)"
echo "Files that differ:      $(grep -c 'differ$' full_diff.txt || echo 0)"

echo ""
echo "=== EXPECTED NEW SECTIONS (should appear in diff) ==="
grep -l "Consensus Diagnostics" current_output/relay/*.html 2>/dev/null | wc -l
echo "relay pages with new Consensus Diagnostics section"

echo ""
echo "=== UNEXPECTED CHANGES (review these!) ==="
# Show changes that are NOT the new feature sections
diff -r baseline_normalized/ current_normalized/ \
    --exclude="*.log" | \
    grep -v "Consensus Diagnostics" | \
    grep -v "Authority Votes" | \
    grep -v "Flag Eligibility" | \
    grep -v "Bandwidth Measurements" | \
    grep -v "Flag Thresholds" | \
    head -50

echo ""
echo "=== Full diff saved to: full_diff.txt ==="
echo "=== Test result: $TEST_RESULT ==="

exit $TEST_RESULT
```

---

## 📅 Implementation Timeline

### Phase 1: Per-Relay Diagnostics (4 weeks)

| Sprint | Focus | Deliverables | Tests |
|--------|-------|--------------|-------|
| **Week 1** | Core Infrastructure | `lib/consensus/__init__.py`, `collector_fetcher.py` | `pytest tests/test_collector_fetcher.py -v` |
| **Week 2** | Worker Integration | Add to `workers.py`, `Coordinator` | `pytest tests/test_workers.py tests/test_coordinator.py -v` |
| **Week 3** | Template Implementation | Update `relay-info.html`, CSS | `pytest tests/ -v` + manual template review |
| **Week 4** | Phase 1 Validation | Integration tests, error handling | **Full test suite + baseline comparison** |

**Phase 1 Completion Checklist:**
```bash
# 1. Run full test suite
pytest tests/ -v

# 2. Generate site and compare to baseline
python allium.py --progress --output-dir phase1_output/

# 3. Verify only expected changes
diff -r baseline_output/ phase1_output/ --brief

# 4. Verify new diagnostics section appears
grep -l "Consensus Diagnostics" phase1_output/relay/*.html | wc -l
# Expected: ~7000 files
```

### Phase 2: Authority Dashboard (2-3 weeks)

| Sprint | Focus | Deliverables | Tests |
|--------|-------|--------------|-------|
| **Week 5** | Authority Health | `authority_monitor.py` | `pytest tests/test_authority_monitor.py -v` |
| **Week 6-7** | Template Enhancement | Update `misc-authorities.html` | `pytest tests/ -v` + manual review |

**Phase 2 Completion Checklist:**
```bash
# 1. Run full test suite
pytest tests/ -v

# 2. Generate final site
python allium.py --progress --output-dir final_output/

# 3. Compare to baseline - only relay-info.html and misc-authorities.html should differ
diff -r baseline_output/ final_output/ --brief

# 4. Verify authority dashboard enhancements
grep -l "Flag Thresholds" final_output/misc/authorities.html
```

---

## 📁 Files to Create/Modify

```
allium/
├── lib/
│   ├── workers.py                    # MODIFY: Add fetch_collector_consensus_data()
│   ├── coordinator.py                # MODIFY: Add to api_workers list
│   └── consensus/
│       ├── __init__.py               # NEW
│       ├── collector_fetcher.py      # NEW: Fetch + parse + index
│       └── authority_monitor.py      # NEW: HTTP latency checks (Phase 2)
├── templates/
│   ├── relay-info.html               # MODIFY: Add diagnostics section
│   └── misc-authorities.html         # MODIFY: Add dashboard enhancements
├── cache/
│   └── consensus/
│       └── collector_data.json       # NEW: Cached indexed data
└── tests/
    ├── test_collector_fetcher.py     # NEW: Unit tests for collector_fetcher.py
    └── test_authority_monitor.py     # NEW: Unit tests for authority_monitor.py
```

---

## ✅ Success Criteria

### Phase 1
- [ ] `pytest tests/test_collector_fetcher.py -v` passes
- [ ] `pytest tests/test_workers_collector.py -v` passes  
- [ ] Per-relay vote/reachability lookup works correctly
- [ ] Flag eligibility analysis with thresholds displays
- [ ] Bandwidth measurements with deviation coloring displays
- [ ] Baseline comparison shows only expected changes
- [ ] Performance delta documented (informational)

### Phase 2
- [ ] `pytest tests/test_authority_monitor.py -v` passes
- [ ] Authority latency checks complete successfully
- [ ] Flag thresholds shown per authority in columns
- [ ] Network flag totals displayed
- [ ] Simple alert for offline/slow authorities
- [ ] Final regression test passes

---

---

## 🚀 Production Readiness Checklist

### Pre-Implementation

- [ ] **Baseline captured** - `./scripts/capture_baseline.sh` run and committed
- [ ] **Branch created** - Feature branch from main
- [ ] **Dependencies reviewed** - No new external dependencies required (uses stdlib)

### Error Handling Requirements

| Scenario | Handling | User Experience |
|----------|----------|-----------------|
| CollecTor unreachable | Use cache (up to 3 hours old) | Show "Data from: X hours ago" |
| CollecTor returns partial data | Use available data, log warning | Show partial diagnostics |
| Malformed vote/bandwidth file | Skip that authority, continue | "8/9 authorities available" |
| Cache corruption | Delete cache, refetch | Automatic recovery |
| Timeout during fetch | Use cache if available | Graceful degradation |

```python
# Error handling pattern (required in all new code)
try:
    result = risky_operation()
except SpecificException as e:
    logger.warning(f"Operation failed: {e}")
    result = fallback_value
    # NEVER let exceptions propagate to page generation
```

### Feature Flag (Gradual Rollout)

```python
# lib/config.py or environment variable
ENABLE_COLLECTOR_DIAGNOSTICS = os.environ.get('ALLIUM_COLLECTOR_DIAGNOSTICS', 'true').lower() == 'true'

# lib/coordinator.py - respect feature flag
if self.enabled_apis == 'all' and ENABLE_COLLECTOR_DIAGNOSTICS:
    self.api_workers.append(("collector_consensus", fetch_collector_consensus_data, [...]))
```

**Rollout plan**:
1. Week 1: Deploy with `ALLIUM_COLLECTOR_DIAGNOSTICS=false` (disabled)
2. Week 2: Enable on staging, monitor for 48 hours
3. Week 3: Enable on production, monitor closely
4. Week 4: Remove feature flag, code is permanent

### Rollback Plan

```bash
#!/bin/bash
# scripts/rollback.sh - Emergency rollback procedure

# Option 1: Disable feature via environment
export ALLIUM_COLLECTOR_DIAGNOSTICS=false
# Restart allium - feature disabled, no code changes needed

# Option 2: Git revert (if code issue)
git revert HEAD~N  # Revert last N commits
git push origin main

# Option 3: Deploy previous known-good version
git checkout v1.x.x  # Previous release tag
# Redeploy
```

### Performance Benchmarks (Measure, Don't Fail)

**Note**: These are guidelines for monitoring, not hard failure criteria. Measure before/after and document the delta.

| Metric | Baseline (Typical) | Target Delta | Measurement |
|--------|-------------------|--------------|-------------|
| Total generation time | ~180s | Document Δ | `time python allium.py` |
| Memory usage | ~2-4 GB | Document Δ | `get_memory_usage()` |
| CollecTor fetch time | N/A (new) | < 60s typical | Worker timing logs |
| Per-relay diagnostics | N/A (new) | < 1ms each | Profiling |
| relay-info.html size | ~15KB | Document Δ | `ls -la` |

```bash
# scripts/benchmark.sh - Run before and after implementation
#!/bin/bash
echo "=== Performance Benchmark (Informational) ==="

# Time full generation
START=$(date +%s.%N)
python allium.py --progress --output-dir bench_output/ 2>&1 | tee bench.log
END=$(date +%s.%N)
DURATION=$(echo "$END - $START" | bc)
echo "Total time: ${DURATION}s"

# Memory (from progress log)
echo "Peak memory usage:"
grep "Memory" bench.log | tail -1

# File sizes
echo "Sample relay-info.html sizes:"
ls -la bench_output/relay/ | head -5

# Compare to baseline (informational, not pass/fail)
if [ -f baseline_benchmark.txt ]; then
    BASELINE=$(cat baseline_benchmark.txt)
    DELTA=$(echo "$DURATION - $BASELINE" | bc)
    echo ""
    echo "=== DELTA REPORT (Informational) ==="
    echo "Baseline time: ${BASELINE}s"
    echo "Current time:  ${DURATION}s"
    echo "Delta:         ${DELTA}s"
    echo ""
    echo "NOTE: This is for documentation, not a pass/fail gate."
fi

echo "$DURATION" > current_benchmark.txt
```

### Security Considerations

| Risk | Mitigation |
|------|------------|
| CollecTor data tampering | HTTPS only, validate response structure |
| Injection via relay nicknames | Already escaped by `bulk_escaper` in `_preprocess_template_data()` |
| DoS via large response | Timeout + max response size limit |
| Cache poisoning | Validate JSON structure before caching |

```python
# Required validation in collector_fetcher.py
def _validate_vote_structure(self, vote_data: dict) -> bool:
    """Validate vote has expected structure before use."""
    required_keys = ['relays', 'authority']
    return all(key in vote_data for key in required_keys)
```

### CI/CD Integration

```yaml
# .github/workflows/collector-tests.yml (add to existing CI)
name: Collector Feature Tests

on: [push, pull_request]

jobs:
  test-collector:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r config/requirements.txt -r config/requirements-dev.txt
      
      - name: Run collector unit tests
        run: pytest tests/test_collector_fetcher.py tests/test_authority_monitor.py -v
      
      - name: Run full test suite
        run: pytest tests/ -v
      
      - name: Generate site (smoke test)
        run: |
          cd allium
          timeout 300 python allium.py --progress --output-dir ci_output/ || exit 1
      
      - name: Check for new diagnostics section
        run: |
          grep -l "Consensus Diagnostics" allium/ci_output/relay/*.html | wc -l
```

### Edge Cases and Failure Modes

| Edge Case | Expected Behavior | Test |
|-----------|-------------------|------|
| New relay (no votes yet) | `collector_diagnostics = None`, section hidden | Unit test |
| Relay in 4/9 votes (not consensus) | Show "NOT IN CONSENSUS (4/9)" | Unit test |
| Authority down during fetch | Skip that authority, show 8/9 | Integration test |
| All authorities down | Use cache, show "Data from: X ago" | Integration test |
| Relay has IPv6 but not tested | Show "⚪" (not tested) | Unit test |
| Bandwidth deviation >100% | Show red, cap display at ±999% | Unit test |
| Empty fingerprint | Skip relay, log warning | Unit test |
| Unicode in relay nickname | Already escaped, renders safely | Existing tests |

### Code Review Checklist

Before PR approval, reviewer must verify:

- [ ] **No new relay loops** - Uses `_reprocess_collector_data()` pattern
- [ ] **Error handling** - All external calls wrapped in try/except
- [ ] **Logging** - Appropriate log levels (info for success, warning for recoverable, error for failures)
- [ ] **Tests pass** - `pytest tests/ -v` all green
- [ ] **Baseline comparison** - `./scripts/validate_phase.sh` shows only expected changes
- [ ] **Performance documented** - Benchmark delta recorded (not a pass/fail gate)
- [ ] **Feature flag** - Can be disabled without code change
- [ ] **Documentation** - Code comments explain "why", not just "what"
- [ ] **Template escaping** - No raw user data in templates without escaping

### Documentation Requirements

| Document | Status | Location |
|----------|--------|----------|
| Implementation plan | This document | `docs/features/planned/consensus-troubleshooting/` |
| Technical spec | Complete | `technical-implementation.md` |
| User guide | Write after Phase 1 | `docs/features/implemented/consensus-diagnostics/` |
| API reference | In code docstrings | `lib/consensus/*.py` |
| Changelog entry | Write at release | `CHANGELOG.md` |

### Post-Deployment Monitoring

```bash
# Hourly cron job to verify feature health
#!/bin/bash
# scripts/monitor_collector.sh

# Check if diagnostics are being generated
DIAG_COUNT=$(grep -l "Consensus Diagnostics" /var/www/allium/relay/*.html 2>/dev/null | wc -l)
RELAY_COUNT=$(ls /var/www/allium/relay/*.html 2>/dev/null | wc -l)

if [ "$DIAG_COUNT" -lt "$((RELAY_COUNT * 90 / 100))" ]; then
    echo "WARNING: Only $DIAG_COUNT/$RELAY_COUNT relays have diagnostics"
    # Send alert
fi

# Check cache freshness
CACHE_AGE=$(stat -c %Y /path/to/cache/collector_consensus.json 2>/dev/null || echo 0)
NOW=$(date +%s)
AGE_HOURS=$(( (NOW - CACHE_AGE) / 3600 ))

if [ "$AGE_HOURS" -gt 3 ]; then
    echo "WARNING: CollecTor cache is $AGE_HOURS hours old"
    # Send alert
fi
```

---

## 🔮 Future: Historical Data Features (Not In Scope)

The following require historical data storage and are **NOT part of this plan**:

- Authority performance scorecards (30-day data)
- Trend graphs (7-day, 30-day)
- Voting participation history
- Troubleshooting wizard with historical comparison

---

**Primary Data Source**: Tor Project CollecTor (https://collector.torproject.org)  
**Merged From**: [TOP_10_PRIORITIZED_FEATURES.md Feature #4](https://github.com/1aeo/allium/blob/cursor/future-features-review-5147/docs/features/planned/TOP_10_PRIORITIZED_FEATURES.md)
