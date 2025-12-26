# Consensus Troubleshooting Enhancement Plan

**Status**: 📋 Research Complete - Ready for Implementation  
**Created**: December 2025  
**Research Source**: tor-relays mailing list analysis & consensus-health.torproject.org  
**Target Users**: Relay operators troubleshooting consensus inclusion/flag issues

---

## Executive Summary

This document outlines a comprehensive plan to enhance Allium with consensus troubleshooting capabilities based on extensive research of actual relay operator questions from the tor-relays mailing list. The goal is to provide relay operators with self-service tools to understand why their relay may not be in consensus, why they're missing expected flags, or why their consensus weight is unexpectedly low.

---

## 📊 Research Findings: Common Consensus Questions from tor-relays

### Analysis Period
- Reviewed tor-relays mailing list archives from 2022-2024
- Identified recurring themes in operator questions
- Cross-referenced with consensus-health.torproject.org data availability

### Top 10 Consensus-Related Troubleshooting Questions

| Rank | Issue Category | Example Thread | Frequency |
|------|----------------|----------------|-----------|
| 1 | **Relay Not In Consensus** | "Exit relay not in consensus" (Oct 2024) | Very High |
| 2 | **Relay Dropped From Consensus** | "Please check if your relay has fallen out" (Oct 2024) | Very High |
| 3 | **Consensus Weight Issues** | "Directory authorities not giving weight to a relay" (Jun 2024) | High |
| 4 | **Consensus Weight Dropping** | "Consensus weight tanking" (Oct 2022) | High |
| 5 | **Missing Flags** | "Tor Weather: Node-Flag [Guard] Alert" (Sep 2023) | Medium-High |
| 6 | **Authority Reachability** | "IPv6 Tor authority is down?" (Jan 2023) | Medium |
| 7 | **Relay Identity Issues** | "Relay suddenly saying it's new" (Jan 2024) | Medium |
| 8 | **Stale Consensus** | "Consensus is too old" warnings (Feb 2024) | Medium |
| 9 | **IPv6 Issues** | IPv6 reachability affecting consensus | Medium |
| 10 | **Version Compliance** | Running obsolete Tor version affecting flags | Low-Medium |

---

## 🎯 Proposed Features - Per-Relay Consensus Diagnostics

All phases 1-4 add new sections to the individual **relay detail page** (`relay-info.html`), providing comprehensive consensus troubleshooting for each relay. Data is fetched from **CollecTor** and cached hourly.

### Relay Page Enhancement Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│ View Relay "YourRelayNickname"                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ [Existing relay info sections...]                                   │
│                                                                     │
│ ═══════════════════════════════════════════════════════════════════ │
│ 🔍 CONSENSUS DIAGNOSTICS (NEW - Phases 1-4)                        │
│ ═══════════════════════════════════════════════════════════════════ │
│                                                                     │
│ ┌─ Phase 1: Authority Votes ────────────────────────────────────┐  │
│ │ Which authorities voted for this relay?                        │  │
│ └────────────────────────────────────────────────────────────────┘  │
│                                                                     │
│ ┌─ Phase 2: Flag Eligibility ───────────────────────────────────┐  │
│ │ Why does/doesn't this relay have certain flags?               │  │
│ └────────────────────────────────────────────────────────────────┘  │
│                                                                     │
│ ┌─ Phase 3: Reachability Analysis ──────────────────────────────┐  │
│ │ Can authorities reach this relay? (IPv4/IPv6)                  │  │
│ └────────────────────────────────────────────────────────────────┘  │
│                                                                     │
│ ┌─ Phase 4: Bandwidth Measurements ─────────────────────────────┐  │
│ │ How do bandwidth authorities measure this relay?               │  │
│ └────────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

### Phase 1: Authority Votes Section (Critical Priority)

**Problem Solved**: "Why is my relay not in consensus?" / "Which authorities see my relay?"

**Location**: New section on `relay-info.html`

**Data Source**: CollecTor votes (`https://collector.torproject.org/recent/relay-descriptors/votes/`)

**Mockup**:
```
┌─────────────────────────────────────────────────────────────────────┐
│ 🗳️ Directory Authority Votes                                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ Consensus Status: ✅ IN CONSENSUS (8/9 authorities)                │
│ Data from: 2025-12-26 04:00 UTC consensus (CollecTor)              │
│                                                                     │
│ ┌────────────┬───────┬─────────────────────────┬──────────┬───────┐│
│ │ Authority  │ Voted │ Flags Assigned          │ Bandwidth│ Issue ││
│ ├────────────┼───────┼─────────────────────────┼──────────┼───────┤│
│ │ moria1     │  ✅   │ Fast Guard Stable Valid │ 45,000   │       ││
│ │ tor26      │  ✅   │ Fast Guard Stable Valid │ 44,800   │       ││
│ │ dizum      │  ✅   │ Fast Stable Valid       │ 43,200   │ ⚠️    ││
│ │ gabelmoo   │  ✅   │ Fast Guard Stable Valid │ 45,100   │       ││
│ │ dannenberg │  ✅   │ Fast Guard Stable Valid │ 44,950   │       ││
│ │ maatuska   │  ✅   │ Fast Guard Stable Valid │ 45,000   │       ││
│ │ longclaw   │  ✅   │ Fast Stable Valid       │ 43,800   │ ⚠️    ││
│ │ bastet     │  ✅   │ Fast Guard Stable Valid │ 44,700   │       ││
│ │ faravahar  │  ❌   │ Not in vote             │ N/A      │ ⚠️    ││
│ └────────────┴───────┴─────────────────────────┴──────────┴───────┘│
│                                                                     │
│ ⚠️ Issues Detected:                                                 │
│ • faravahar: Relay not in vote - check reachability to this auth   │
│ • dizum, longclaw: Not assigning Guard flag (see thresholds below) │
│                                                                     │
│ 💡 Troubleshooting Tips:                                            │
│ • Missing from 1-2 authorities → Likely reachability issue         │
│ • Missing from all → Check relay is running, ORPort accessible     │
│ • Different flags → Each authority has different thresholds        │
└─────────────────────────────────────────────────────────────────────┘
```

---

### Phase 2: Flag Eligibility Section (High Priority)

**Problem Solved**: "Why doesn't my relay have Guard?" / "Why did I lose Stable?"

**Location**: New section on `relay-info.html` (below Authority Votes)

**Data Source**: Flag thresholds extracted from CollecTor votes

**Mockup**:
```
┌─────────────────────────────────────────────────────────────────────┐
│ 🎯 Flag Eligibility Analysis                                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ Current Flags: Fast, Stable, Valid, V2Dir, HSDir                   │
│ Missing Flags: Guard ← Analysis below                               │
│                                                                     │
│ ══ Guard Flag Requirements ════════════════════════════════════════ │
│ ┌────────────────────┬────────────┬────────────┬──────────────────┐│
│ │ Requirement        │ Your Value │ Threshold  │ Status           ││
│ ├────────────────────┼────────────┼────────────┼──────────────────┤│
│ │ WFU (Uptime)       │ 96.2%      │ ≥98%       │ ❌ Below (-1.8%) ││
│ │ Time Known         │ 45 days    │ ≥8 days    │ ✅ Above         ││
│ │ Bandwidth (w/Exit) │ 25 MB/s    │ ≥29 MB/s   │ ❌ Below (-14%)  ││
│ │ Bandwidth (no Exit)│ 25 MB/s    │ ≥28 MB/s   │ ❌ Below (-11%)  ││
│ └────────────────────┴────────────┴────────────┴──────────────────┘│
│                                                                     │
│ 💡 To gain Guard flag:                                              │
│    • Increase uptime to ≥98% (currently 96.2%)                     │
│    • Increase bandwidth to ≥29 MB/s (currently 25 MB/s)            │
│                                                                     │
│ ══ Stable Flag Requirements ═══════════════════════════════════════ │
│ ┌────────────────────┬────────────┬────────────┬──────────────────┐│
│ │ Requirement        │ Your Value │ Threshold  │ Status           ││
│ ├────────────────────┼────────────┼────────────┼──────────────────┤│
│ │ Uptime             │ 20.2 days  │ ≥20.2 days │ ✅ At threshold  ││
│ │ MTBF               │ 45.1 days  │ ≥36.2 days │ ✅ Above         ││
│ └────────────────────┴────────────┴────────────┴──────────────────┘│
│                                                                     │
│ ══ Fast Flag Requirements ═════════════════════════════════════════ │
│ ┌────────────────────┬────────────┬────────────┬──────────────────┐│
│ │ Requirement        │ Your Value │ Threshold  │ Status           ││
│ ├────────────────────┼────────────┼────────────┼──────────────────┤│
│ │ Bandwidth          │ 25 MB/s    │ ≥102 KB/s  │ ✅ Above         ││
│ └────────────────────┴────────────┴────────────┴──────────────────┘│
│                                                                     │
│ ══ HSDir Flag Requirements ════════════════════════════════════════ │
│ ┌────────────────────┬────────────┬────────────┬──────────────────┐│
│ │ Requirement        │ Your Value │ Threshold  │ Status           ││
│ ├────────────────────┼────────────┼────────────┼──────────────────┤│
│ │ WFU (Uptime)       │ 96.2%      │ ≥98%       │ ❌ Below         ││
│ │ Time Known         │ 45 days    │ ≥9.9 days  │ ✅ Above         ││
│ └────────────────────┴────────────┴────────────┴──────────────────┘│
│                                                                     │
│ ℹ️ Thresholds from: moria1 vote (network median may vary slightly)  │
└─────────────────────────────────────────────────────────────────────┘
```

---

### Phase 3: Reachability Analysis Section (High Priority)

**Problem Solved**: "Can directory authorities reach my relay?" / "Why is IPv6 not working?"

**Location**: New section on `relay-info.html` (below Flag Eligibility)

**Data Source**: CollecTor votes (presence in vote = reachable, flags indicate IPv6 status)

**Mockup**:
```
┌─────────────────────────────────────────────────────────────────────┐
│ 🌐 Authority Reachability Analysis                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ ══ IPv4 Reachability (1.2.3.4:9001) ═══════════════════════════════ │
│ ┌────────────┬────────────┬─────────────────────────────────────┐  │
│ │ Authority  │ Reachable  │ Evidence                            │  │
│ ├────────────┼────────────┼─────────────────────────────────────┤  │
│ │ moria1     │ ✅ Yes     │ Included in vote with Running flag  │  │
│ │ tor26      │ ✅ Yes     │ Included in vote with Running flag  │  │
│ │ dizum      │ ✅ Yes     │ Included in vote with Running flag  │  │
│ │ gabelmoo   │ ✅ Yes     │ Included in vote with Running flag  │  │
│ │ dannenberg │ ✅ Yes     │ Included in vote with Running flag  │  │
│ │ maatuska   │ ✅ Yes     │ Included in vote with Running flag  │  │
│ │ longclaw   │ ✅ Yes     │ Included in vote with Running flag  │  │
│ │ bastet     │ ✅ Yes     │ Included in vote with Running flag  │  │
│ │ faravahar  │ ❌ No      │ NOT in faravahar's vote             │  │
│ └────────────┴────────────┴─────────────────────────────────────┘  │
│                                                                     │
│ ══ IPv6 Reachability ([2001:db8::1]:9001) ═════════════════════════ │
│ ┌────────────┬────────────┬─────────────────────────────────────┐  │
│ │ Authority  │ Reachable  │ Flags / Notes                       │  │
│ ├────────────┼────────────┼─────────────────────────────────────┤  │
│ │ moria1     │ ✅ Yes     │ ReachableIPv6 flag assigned         │  │
│ │ tor26      │ ❌ No      │ NoIPv6Consensus flag                │  │
│ │ dizum      │ ⚪ N/A     │ Does not test IPv6                  │  │
│ │ gabelmoo   │ ✅ Yes     │ ReachableIPv6 flag assigned         │  │
│ │ dannenberg │ ✅ Yes     │ ReachableIPv6 flag assigned         │  │
│ │ maatuska   │ ✅ Yes     │ ReachableIPv6 flag assigned         │  │
│ │ longclaw   │ ⚪ N/A     │ Does not test IPv6                  │  │
│ │ bastet     │ ✅ Yes     │ ReachableIPv6 flag assigned         │  │
│ │ faravahar  │ ❌ No      │ NOT in vote (IPv4 issue first)      │  │
│ └────────────┴────────────┴─────────────────────────────────────┘  │
│                                                                     │
│ ⚠️ Reachability Issues Detected:                                    │
│ • faravahar cannot reach your relay via IPv4                       │
│ • tor26 cannot reach your relay via IPv6                           │
│                                                                     │
│ 📋 Self-Diagnostic Commands:                                        │
│ # Test IPv6 connectivity to authorities:                           │
│ ping6 -c2 2001:858:2:2:aabb:0:563b:1526 &&  # moria1               │
│ ping6 -c2 2001:638:a000:4140::ffff:189 &&   # gabelmoo             │
│ ping6 -c2 2001:678:558:1000::244 &&         # dannenberg           │
│ ping6 -c2 2620:13:4000:6000::1000:118 &&    # bastet               │
│ echo "IPv6 connectivity OK"                                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

### Phase 4: Bandwidth Measurements Section (Medium Priority)

**Problem Solved**: "Why is my consensus weight so low?" / "Why is my relay unmeasured?"

**Location**: New section on `relay-info.html` (below Reachability)

**Data Source**: CollecTor bandwidth files (`https://collector.torproject.org/recent/relay-descriptors/bandwidths/`)

**Mockup**:
```
┌─────────────────────────────────────────────────────────────────────┐
│ 📊 Bandwidth Authority Measurements                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ Consensus Weight: 45,000 (0.23% of network)                        │
│ Measurement Status: ✅ MEASURED (by 6/7 bandwidth authorities)     │
│                                                                     │
│ ┌────────────┬──────────┬───────────┬────────────┬────────────────┐│
│ │ BW Auth    │ Measured │ bw Value  │ Deviation  │ Last Scan      ││
│ ├────────────┼──────────┼───────────┼────────────┼────────────────┤│
│ │ moria1     │ ✅       │ 46,200    │ +2.7%      │ 2h ago         ││
│ │ tor26      │ ✅       │ 44,800    │ -0.4%      │ 1h ago         ││
│ │ gabelmoo   │ ✅       │ 44,100    │ -2.0%      │ 3h ago         ││
│ │ maatuska   │ ✅       │ 45,800    │ +1.8%      │ 2h ago         ││
│ │ longclaw   │ ✅       │ 44,500    │ -1.1%      │ 1h ago         ││
│ │ bastet     │ ✅       │ 44,900    │ -0.2%      │ 2h ago         ││
│ │ faravahar  │ ❌       │ N/A       │ N/A        │ Not measured   ││
│ └────────────┴──────────┴───────────┴────────────┴────────────────┘│
│                                                                     │
│ 📈 Weight Analysis:                                                 │
│ • Observed Bandwidth: 50 MB/s (from descriptor)                    │
│ • Consensus Weight: 45,000                                          │
│ • Weight/Bandwidth Ratio: 0.90 (network median: 0.85)              │
│ • Efficiency: ✅ Above average                                      │
│                                                                     │
│ ℹ️ Measurement Notes:                                                │
│ • dizum, dannenberg do not run bandwidth scanners                  │
│ • Relay must be measured by ≥3 authorities to be "Measured"        │
│ • New relays may take 1-2 weeks to be fully measured               │
│ • Measurement variance ±5% between authorities is normal           │
│                                                                     │
│ ⚠️ If your relay shows "Unmeasured":                                │
│ • Check reachability to bandwidth authorities (see above)          │
│ • Ensure relay has been running continuously for >1 week           │
│ • High packet loss can prevent accurate measurements               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🏛️ Directory Authority Health Dashboard (Phases 5-6)

**Merged from**: [TOP_10_PRIORITIZED_FEATURES.md Feature #4](https://github.com/1aeo/allium/blob/cursor/future-features-review-5147/docs/features/planned/TOP_10_PRIORITIZED_FEATURES.md)

This section extends the per-relay diagnostics (Phases 1-4) with a **network-wide Directory Authority Health Dashboard** that monitors the health and performance of all 9 directory authorities.

### Current Implementation Status

| Component | Status | Location |
|-----------|--------|----------|
| Basic authority table | ✅ Implemented | `misc-authorities.html` |
| Authority uptime stats (1M/6M/1Y/5Y) | ✅ Implemented | `relays.py` |
| Z-score outlier detection | ✅ Implemented | `relays.py` |
| Version compliance tracking | ✅ Implemented | `misc-authorities.html` |
| `fetch_consensus_health()` | ⚠️ Placeholder only | `workers.py` |
| Real-time voting status | ❌ Not implemented | — |
| Latency monitoring | ❌ Not implemented | — |
| Consensus formation analysis | ❌ Not implemented | — |
| Alert system | ❌ Not implemented | — |

---

### Phase 5: Directory Authority Health Dashboard (Medium Priority)

**Problem Solved**: "Is there a problem with the Tor network itself?" / "Are all authorities functioning?"

**Location**: Enhanced `misc-authorities.html` or new `misc-authorities-health.html`

**Data Sources**: 
- CollecTor (votes, consensus, bandwidth files)
- Direct HTTP latency checks to authority directory ports
- Onionoo (authority details, uptime - already integrated)

#### Main Dashboard Mockup
```
┌─────────────────────────────────────────────────────────────────┐
│ 🏛️ Directory Authority Health Dashboard                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ ┌───────────────────┐ ┌───────────────────┐ ┌─────────────────┐│
│ │ Consensus Status  │ │ Authority Voting  │ │ Network Sync    ││
│ │                   │ │                   │ │                 ││
│ │ ✅ CURRENT        │ │ 9/9 ACTIVE        │ │ 99.2% SYNC      ││
│ │ Fresh: 14:32 UTC  │ │ Last Vote: Recent │ │ 8.9/9 Agreement ││
│ │ Next: 15:00 UTC   │ │ All Participating │ │                 ││
│ └───────────────────┘ └───────────────────┘ └─────────────────┘│
│                                                                 │
│ Directory Authorities Status (Real-Time):                       │
│ ┌──────────────────────────────────────────────────────────────┐│
│ │ Authority    │ Status │ Vote │ BW Scan │ Latency │ Uptime   ││
│ ├──────────────┼────────┼──────┼─────────┼─────────┼──────────┤│
│ │ moria1       │ 🟢 OK  │ ✅   │ ✅      │ 12ms    │ 99.9%    ││
│ │ tor26        │ 🟢 OK  │ ✅   │ ✅      │ 8ms     │ 99.9%    ││
│ │ dizum        │ 🟢 OK  │ ✅   │ ❌ N/A  │ 15ms    │ 99.8%    ││
│ │ gabelmoo     │ 🟢 OK  │ ✅   │ ✅      │ 11ms    │ 99.9%    ││
│ │ dannenberg   │ 🟢 OK  │ ✅   │ ❌ N/A  │ 19ms    │ 99.7%    ││
│ │ maatuska     │ 🟢 OK  │ ✅   │ ✅      │ 7ms     │ 99.9%    ││
│ │ faravahar    │ 🟡 SLOW│ ✅   │ ⚠️      │ 89ms    │ 97.8%    ││
│ │ longclaw     │ 🟢 OK  │ ✅   │ ✅      │ 14ms    │ 99.6%    ││
│ │ bastet       │ 🟢 OK  │ ✅   │ ✅      │ 16ms    │ 99.5%    ││
│ └──────────────┴────────┴──────┴─────────┴─────────┴──────────┘│
│                                                                 │
│ ⚠️ Active Alerts (1):                                           │
│ ┌──────────────────────────────────────────────────────────────┐│
│ │ 🟡 WARNING: faravahar bandwidth scanning slower than usual   ││
│ │    Response time: 89ms (threshold: 50ms) • Since: 14:15 UTC  ││
│ └──────────────────────────────────────────────────────────────┘│
│                                                                 │
│ Recent Consensus Events:                                        │
│ • 14:32 - Consensus published successfully (9/9 authorities)   │
│ • 14:31 - Voting round completed in 127 seconds                │
│ • 14:29 - All authorities synchronized                         │
│                                                                 │
│ Last updated: 14:45:23 UTC • Auto-refresh: 60s                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Consensus Health Metrics View
```
┌─────────────────────────────────────────────────────────────────┐
│ 📊 Consensus Health Metrics                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Current Consensus (2025-01-06 15:00:00):                       │
│ ┌──────────────────────────────────────────────────────────────┐│
│ │ Method: 33              Valid: 15:00-16:00 UTC               ││
│ │ Relays: 8,247           Voting Delay: 300s                   ││
│ │ Authorities: 9/9        Distribution Delay: 300s             ││
│ │ Bandwidth Sum: 1.2TB/s  Consensus Size: 2.3MB               ││
│ └──────────────────────────────────────────────────────────────┘│
│                                                                 │
│ Flag Distribution:                                              │
│ ┌──────────────────────────────────────────────────────────────┐│
│ │ Running  ████████████████████████████████ 7,234 (87.7%)     ││
│ │ Fast     ████████████████████████████     6,891 (83.6%)     ││
│ │ Stable   ████████████████████████         5,678 (68.9%)     ││
│ │ Guard    ████████████████                 2,845 (34.5%)     ││
│ │ Exit     ███████████                      1,923 (23.3%)     ││
│ │ V2Dir    ████████████████████████████████ 7,156 (86.8%)     ││
│ │ HSDir    ███████████████████████████████  6,987 (84.7%)     ││
│ └──────────────────────────────────────────────────────────────┘│
│                                                                 │
│ Flag Thresholds (Current):                                      │
│ ┌──────────────────────────────────────────────────────────────┐│
│ │ Flag    │ Requirement              │ Current Value           ││
│ ├─────────┼──────────────────────────┼─────────────────────────┤│
│ │ Stable  │ Uptime ≥ median          │ ≥20.2 days              ││
│ │ Stable  │ MTBF ≥ median            │ ≥36.2 days              ││
│ │ Fast    │ Bandwidth ≥ 7/8 * median │ ≥102 KB/s               ││
│ │ Guard   │ WFU ≥ 98%                │ ≥98%                    ││
│ │ Guard   │ Time Known ≥ 8 days      │ ≥8 days                 ││
│ │ Guard   │ Bandwidth (inc exits)    │ ≥29 MB/s                ││
│ │ Guard   │ Bandwidth (exc exits)    │ ≥28 MB/s                ││
│ │ HSDir   │ WFU ≥ 98%                │ ≥98%                    ││
│ │ HSDir   │ Time Known ≥ median      │ ≥9.9 days               ││
│ └─────────┴──────────────────────────┴─────────────────────────┘│
│                                                                 │
│ Quality Indicators:                                             │
│ ✅ Consensus freshness: Excellent (12 minutes until stale)     │
│ ✅ Authority participation: 100% (9/9)                         │
│ ✅ Flag consistency: 98.7% agreement across authorities        │
└─────────────────────────────────────────────────────────────────┘
```

#### Implementation Components

| Component | File | Purpose |
|-----------|------|---------|
| Authority Latency Checker | `lib/consensus/authority_monitor.py` | Direct HTTP checks to authority directory ports |
| Consensus Parser | `lib/consensus/collector_fetcher.py` | Parse consensus docs from CollecTor |
| Vote Tracker | `lib/consensus/collector_fetcher.py` | Track voting participation |
| Bandwidth Tracker | `lib/consensus/collector_fetcher.py` | Monitor BW scanner activity |
| Alert System | `lib/consensus/authority_alerts.py` | Generate alerts from health data |

---

### Phase 6: Historical Analytics & Troubleshooting Wizard (Lower Priority)

#### Part A: Authority Performance Analytics (Historical)

**Problem Solved**: "How reliable is each authority over time?"

**Location**: Additional section on authority health dashboard

**Data Required**: Historical storage (database or file-based)

```
┌─────────────────────────────────────────────────────────────────┐
│ 📈 Authority Performance Analytics (30 days)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Performance Scorecard:                                          │
│ ┌──────────────────────────────────────────────────────────────┐│
│ │ Authority    Uptime  Votes  BW-Scan  Consensus  Score        ││
│ ├──────────────────────────────────────────────────────────────┤│
│ │ moria1       99.8%   100%   98.2%    99.1%     ⭐⭐⭐⭐⭐      ││
│ │ tor26        99.9%   100%   97.8%    99.3%     ⭐⭐⭐⭐⭐      ││
│ │ dizum        99.4%   99.7%  N/A      98.9%     ⭐⭐⭐⭐        ││
│ │ gabelmoo     99.7%   100%   98.9%    99.2%     ⭐⭐⭐⭐⭐      ││
│ │ dannenberg   99.2%   99.8%  N/A      98.6%     ⭐⭐⭐⭐        ││
│ │ maatuska     99.9%   100%   99.1%    99.4%     ⭐⭐⭐⭐⭐      ││
│ │ faravahar    97.8%   98.9%  89.2%    97.1%     ⭐⭐⭐          ││
│ │ longclaw     99.5%   100%   97.4%    99.0%     ⭐⭐⭐⭐        ││
│ │ bastet       99.6%   99.9%  98.7%    99.3%     ⭐⭐⭐⭐⭐      ││
│ └──────────────────────────────────────────────────────────────┘│
│                                                                 │
│ Performance Score Calculation:                                  │
│ • Uptime: 30% weight (core availability)                       │
│ • Voting: 25% weight (consensus participation)                 │
│ • BW Scanning: 20% weight (measurement accuracy)               │
│ • Consensus Agreement: 25% weight (flag consistency)           │
│                                                                 │
│ Network Impact Analysis:                                        │
│ • Consensus Reliability: 99.4% (Excellent)                     │
│ • Authority Redundancy: 9 active (tolerates 4 failures)        │
│ • Geographic Distribution: 6 countries, 3 continents           │
└─────────────────────────────────────────────────────────────────┘
```

#### Part B: Troubleshooting Wizard

**Problem Solved**: Guided troubleshooting for users who don't know their relay's fingerprint

**Location**: New standalone page `misc/consensus-troubleshooter.html`

```
┌─────────────────────────────────────────────────────────────────────┐
│ 🔧 Consensus Troubleshooting Wizard                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ Enter your relay fingerprint: [____________________________] [Go]  │
│                                                                     │
│ Or select a common issue:                                          │
│                                                                     │
│ ❓ My relay is not appearing in the consensus                      │
│    → Check: Running status, OR port accessibility, authority votes │
│                                                                     │
│ ❓ My relay lost the Guard flag                                     │
│    → Check: WFU threshold, bandwidth threshold, uptime history     │
│                                                                     │
│ ❓ My consensus weight dropped significantly                        │
│    → Check: Bandwidth measurements, network congestion, restarts   │
│                                                                     │
│ ❓ My relay shows "Unmeasured" status                               │
│    → Check: Bandwidth authority reachability, relay age            │
│                                                                     │
│ ❓ IPv6 is not working for my relay                                 │
│    → Check: IPv6 authority reachability, ReachableIPv6 flag        │
│                                                                     │
│ ❓ My relay identity/fingerprint changed unexpectedly               │
│    → Check: Key files, relay restart history, first_seen date      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## ⏱️ Directory Authority Update Frequencies

Understanding when data updates is critical for effective troubleshooting:

### Consensus Timing (Tor Directory Protocol)

| Event | Timing | Notes |
|-------|--------|-------|
| **Consensus Valid Period** | 1 hour | Each consensus is valid for 1 hour (e.g., 04:00-05:00 UTC) |
| **Voting Round Start** | XX:00 UTC | Authorities begin voting at the top of each hour |
| **Vote Publication** | XX:00-XX:05 UTC | All 9 authorities publish their votes |
| **Consensus Published** | ~XX:05-XX:10 UTC | Final consensus computed and published |
| **Fresh Until** | +1 hour | Consensus remains fresh for voting period |
| **Valid Until** | +3 hours | Consensus remains valid (with warnings) for 3 hours |

### Data Update Frequencies by Type

| Data Type | Update Frequency | Typical Latency | Size |
|-----------|-----------------|-----------------|------|
| **Consensus** | Every hour (XX:00 UTC) | ~5-10 min after valid-after | ~3.8 MB |
| **Authority Votes** | Every hour (XX:00 UTC) | ~5-35 min after valid-after | ~5.7-6.5 MB each |
| **Bandwidth Files** | Every ~1 hour | ~36-40 min offset | ~7.3-7.7 MB each |
| **Flag Thresholds** | Every hour (in votes) | Derived from votes | N/A |

### Bandwidth Authority Schedule

Only 7 of the 9 directory authorities run bandwidth scanners:

| Authority | Is BW Authority | Measurement Interval |
|-----------|-----------------|---------------------|
| moria1 | ✅ Yes | ~1 hour |
| tor26 | ✅ Yes | ~1 hour |
| dizum | ❌ No | N/A |
| gabelmoo | ✅ Yes | ~1 hour |
| dannenberg | ❌ No | N/A |
| maatuska | ✅ Yes | ~1 hour |
| longclaw | ✅ Yes | ~1 hour |
| bastet | ✅ Yes | ~1 hour |
| faravahar | ✅ Yes | ~1 hour |

---

## 🏗️ Technical Implementation Plan

### Data Sources Integration

**⭐ RECOMMENDED: Use Tor Project CollecTor (Centralized)**

CollecTor aggregates all directory authority data in one place, eliminating the need to fetch from each authority individually:

| Data Source | URL Pattern | Data Provided | Update Frequency |
|-------------|-------------|---------------|------------------|
| **CollecTor Votes** | `https://collector.torproject.org/recent/relay-descriptors/votes/` | All authority votes | Hourly (~5-35 min delay) |
| **CollecTor Consensus** | `https://collector.torproject.org/recent/relay-descriptors/consensuses/` | Final consensus | Hourly (~5-40 min delay) |
| **CollecTor Bandwidth** | `https://collector.torproject.org/recent/relay-descriptors/bandwidths/` | All BW authority files | ~Hourly per authority |
| **Consensus Health** | `https://consensus-health.torproject.org/` | Aggregated metrics, thresholds | ~15 min |

### CollecTor File Naming Convention

```
# Consensus files
2025-12-26-04-00-00-consensus

# Vote files (includes authority fingerprint)
2025-12-26-04-00-00-vote-[AUTHORITY_FINGERPRINT]-[VOTE_DIGEST]

# Bandwidth files (includes digest)
2025-12-26-04-36-17-bandwidth-[FILE_DIGEST]
```

### Benefits of Using CollecTor

| Benefit | Description |
|---------|-------------|
| **Single Source** | Fetch all data from one reliable endpoint |
| **No Authority Load** | Don't burden individual authorities with requests |
| **Historical Data** | Access recent files (last 72 hours in `/recent/`) |
| **Reliable** | Tor Project infrastructure with good uptime |
| **Consistent Format** | Standardized file naming and structure |

### Alternative: Direct Authority Fetching

Only use direct authority fetching if:
- CollecTor is unavailable
- Need real-time data (within minutes of publication)
- Testing authority reachability specifically

| Data Source | URL Pattern | Notes |
|-------------|-------------|-------|
| Authority Votes | `http://[auth-ip]:[dir-port]/tor/status-vote/current/authority` | Real-time, per-authority |
| Bandwidth Files | `http://[auth-ip]:[dir-port]/tor/status-vote/next/bandwidth` | Only 7 authorities |
| Consensus | `http://[auth-ip]:[dir-port]/tor/status-vote/current/consensus` | Real-time |

### New Files Required

```
allium/
├── lib/
│   └── consensus/
│       ├── __init__.py
│       ├── collector.py              # CollecTor configuration
│       ├── authorities.py            # Authority fingerprint mapping
│       ├── collector_fetcher.py      # Main data fetcher (votes + bandwidth)
│       ├── threshold_analyzer.py     # Flag threshold analysis
│       ├── authority_monitor.py      # Real-time authority latency checks (Phase 5)
│       └── authority_alerts.py       # Alert generation system (Phase 5)
├── templates/
│   ├── relay-info.html               # MODIFY: Add consensus diagnostics (Phases 1-4)
│   ├── misc-authorities.html         # MODIFY: Add health indicators (Phase 5)
│   ├── misc-authorities-health.html  # NEW: Full authority health dashboard (Phase 5)
│   └── misc-troubleshooter.html      # NEW: Troubleshooting wizard (Phase 6)
├── static/
│   └── css/
│       └── diagnostics.css           # NEW: Styles for diagnostic components
└── cache/
    └── consensus/
        ├── collector_data.json       # Cached CollecTor data (votes + bandwidth)
        └── authority_health.json     # Cached authority latency checks
```

### Integration with Multi-API Architecture

This implementation uses a single unified `CollectorFetcher` class that fetches all needed data from CollecTor:

```python
# lib/workers.py - Single worker for all consensus data

from lib.consensus.collector_fetcher import CollectorFetcher

_collector_fetcher = None

def fetch_collector_data():
    """
    Fetch ALL consensus troubleshooting data from CollecTor.
    
    Single worker fetches:
    - 9 authority votes (for Phases 1-3)
    - 7 bandwidth files (for Phase 4)
    - Flag thresholds (extracted from votes)
    
    Data is indexed by relay fingerprint for O(1) lookup during page generation.
    """
    global _collector_fetcher
    
    _collector_fetcher = CollectorFetcher()
    data = _collector_fetcher.fetch_all_data(timeout=120)
    
    # Log results
    vote_count = len([v for v in data['votes'].values() if 'error' not in v])
    bw_count = len([b for b in data['bandwidth_files'].values() if 'error' not in b])
    relay_count = len(data['relay_index'])
    
    logger.info(f"CollecTor: {vote_count}/9 votes, {bw_count}/7 BW files, {relay_count} relays")
    
    _save_cache('collector_data', data)
    return data

def get_relay_diagnostics(fingerprint: str) -> dict:
    """
    Get complete diagnostics for a relay (called during page generation).
    Returns data for all 4 phases on the relay-info.html page.
    """
    global _collector_fetcher
    
    if _collector_fetcher is None:
        cached = _load_cache('collector_data')
        if cached:
            _collector_fetcher = CollectorFetcher()
            _collector_fetcher.votes = cached.get('votes', {})
            _collector_fetcher.bandwidth_files = cached.get('bandwidth_files', {})
            _collector_fetcher.relay_index = cached.get('relay_index', {})
            _collector_fetcher.flag_thresholds = cached.get('flag_thresholds', {})
    
    return _collector_fetcher.get_relay_diagnostics(fingerprint)
```

See `technical-implementation.md` for complete `CollectorFetcher` class implementation.

---

## 📅 Implementation Timeline

### 🚀 Milestone 1: Per-Relay Diagnostics (Phases 1-4) - 5 Weeks

#### Sprint 1: Core Infrastructure (Week 1)
- [ ] Create `lib/consensus/` directory structure
- [ ] Implement `collector.py` - CollecTor configuration
- [ ] Implement `authorities.py` - Authority fingerprint mapping
- [ ] Implement `collector_fetcher.py` - Main data fetcher

#### Sprint 2: Worker Integration (Week 2)
- [ ] Add `fetch_collector_data()` worker to `lib/workers.py`
- [ ] Implement `get_relay_diagnostics()` lookup function
- [ ] Set up hourly caching for CollecTor data
- [ ] Test with multi-API coordinator

#### Sprint 3: Relay Page - Phases 1-2 (Week 3)
- [ ] Add Phase 1 (Authority Votes) section to `relay-info.html`
- [ ] Add Phase 2 (Flag Eligibility) section to `relay-info.html`
- [ ] Add CSS styles for diagnostic components
- [ ] Implement Jinja2 filters for formatting

#### Sprint 4: Relay Page - Phases 3-4 (Week 4)
- [ ] Add Phase 3 (Reachability Analysis) section
- [ ] Add Phase 4 (Bandwidth Measurements) section
- [ ] Add troubleshooting tips and recommendations
- [ ] Implement error handling and graceful degradation

#### Sprint 5: Testing & Polish (Week 5)
- [ ] Unit tests for CollecTor parsing
- [ ] Integration tests with real data
- [ ] Performance testing with 7000+ relays
- [ ] Documentation and user guide

---

### 🏛️ Milestone 2: Authority Health Dashboard (Phases 5-6) - 4-6 Weeks

#### Sprint 6: Real-Time Authority Monitoring (Week 6-7)
- [ ] Implement `authority_monitor.py` - Direct HTTP latency checks
- [ ] Add real-time status indicators (online/slow/degraded/offline)
- [ ] Integrate latency data into existing `misc-authorities.html`
- [ ] Add authority status summary cards

#### Sprint 7: Consensus & Voting Analysis (Week 8)
- [ ] Add consensus document parsing (valid-after, fresh-until, etc.)
- [ ] Implement vote tracking (votes submitted per period)
- [ ] Add flag distribution chart from consensus
- [ ] Display consensus freshness indicators

#### Sprint 8: Alert System & Dashboard (Week 9)
- [ ] Implement `authority_alerts.py` - Alert generation
- [ ] Create comprehensive authority health dashboard
- [ ] Add alert thresholds and history
- [ ] Create `misc-authorities-health.html` template

#### Sprint 9: Historical Analytics (Week 10-11) - Optional
- [ ] Set up historical data storage (file-based or database)
- [ ] Implement 7-day/30-day trend graphs
- [ ] Add performance scorecard calculations
- [ ] Create troubleshooting wizard page

---

### Success Criteria

#### Phases 1-4 (Per-Relay Diagnostics):
- [ ] Authority vote lookup for any relay (< 100ms response)
- [ ] Flag eligibility analysis with threshold comparison
- [ ] IPv4/IPv6 reachability per authority
- [ ] Bandwidth measurement display from all 7 BW authorities
- [ ] < 2 second page load time for relay-info.html

#### Phases 5-6 (Authority Health Dashboard):
- [ ] Real-time latency checks for all 9 authorities (< 10s total)
- [ ] Consensus document parsing from CollecTor (hourly)
- [ ] Voting participation tracking (9 votes per consensus)
- [ ] Bandwidth measurement activity tracking
- [ ] Alert system for offline authorities and stale consensus
- [ ] Flag distribution visualization from latest consensus

---

## 📈 Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Operator self-service rate | 80% | Reduction in mailing list consensus questions |
| Page load time | <3s | Lighthouse performance score |
| Data freshness | <1 hour | Time since last vote fetch |
| Feature adoption | 50% | Relay detail page views with vote section |

---

## 🔗 Related Documentation

- [Multi-API Implementation Plan](../multi-api-implementation-plan.md)
- [Directory Authorities Implementation](../directory-authorities/README.md)
- [Milestone 2: Authority Health](../milestone-2-authority-health.md)
- [Consensus Weight Metrics Proposal](../consensus-weight-metrics-proposal.md)

---

## 📚 References

### Tor Project Resources
- [Consensus Health Page](https://consensus-health.torproject.org/)
- [tor-relays Mailing List](https://lists.torproject.org/pipermail/tor-relays/)
- [Tor Directory Protocol Specification](https://spec.torproject.org/dir-spec)

### Example Mailing List Threads (Research Sources)
- "Exit relay not in consensus" - October 2024
- "Please check if your relay has fallen out of the consensus" - October 2024
- "Directory authorities not giving weight to a relay" - June 2024
- "Consensus weight tanking" - October 2022
- "IPv6 Tor authority is down?" - January 2023

---

**Document Status**: Research complete, ready for implementation  
**Primary Data Source**: Tor Project CollecTor (https://collector.torproject.org)  
**Merged From**: [TOP_10_PRIORITIZED_FEATURES.md Feature #4](https://github.com/1aeo/allium/blob/cursor/future-features-review-5147/docs/features/planned/TOP_10_PRIORITIZED_FEATURES.md)

### Feature Summary

| Milestone | Target | Phases | Timeline |
|-----------|--------|--------|----------|
| **Milestone 1** | Per-relay diagnostics (`relay-info.html`) | 1-4 | 5 weeks |
| **Milestone 2** | Authority health dashboard | 5-6 | 4-6 weeks |

**Next Steps**: Technical review and Sprint 1 implementation kickoff
