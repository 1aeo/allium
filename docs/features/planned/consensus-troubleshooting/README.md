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

### Phase 1: Authority Votes & Reachability Section (Critical Priority)

**Problem Solved**: "Why is my relay not in consensus?" / "Which authorities see my relay?" / "Can authorities reach me?"

**Location**: New section on `relay-info.html`

**Data Source**: CollecTor votes (most recent hour only) - `https://collector.torproject.org/recent/relay-descriptors/votes/`

**Key Insight**: Reachability is determined by presence in vote - if an authority can't reach your relay, it won't appear in their vote.

**Mockup**:
```
┌─────────────────────────────────────────────────────────────────────┐
│ 🗳️ Directory Authority Votes & Reachability                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ Consensus Status: ✅ IN CONSENSUS (8/9 authorities)                │
│ Data from: 2025-12-26 04:00 UTC (latest CollecTor)                 │
│                                                                     │
│ ┌────────────┬───────┬──────┬──────┬─────────────────────┬────────┐│
│ │ Authority  │ IPv4  │ IPv6 │ Vote │ Flags Assigned      │Bandwidth│
│ ├────────────┼───────┼──────┼──────┼─────────────────────┼────────┤│
│ │ moria1     │  ✅   │  ✅  │  ✅  │ Fast Guard Stable   │ 45,000 ││
│ │ tor26      │  ✅   │  ❌  │  ✅  │ Fast Guard Stable   │ 44,800 ││
│ │ dizum      │  ✅   │  ⚪  │  ✅  │ Fast Stable Valid   │ 43,200 ││
│ │ gabelmoo   │  ✅   │  ✅  │  ✅  │ Fast Guard Stable   │ 45,100 ││
│ │ dannenberg │  ✅   │  ✅  │  ✅  │ Fast Guard Stable   │ 44,950 ││
│ │ maatuska   │  ✅   │  ✅  │  ✅  │ Fast Guard Stable   │ 45,000 ││
│ │ longclaw   │  ✅   │  ⚪  │  ✅  │ Fast Stable Valid   │ 43,800 ││
│ │ bastet     │  ✅   │  ✅  │  ✅  │ Fast Guard Stable   │ 44,700 ││
│ │ faravahar  │  ❌   │  ❌  │  ❌  │ —                   │ —      ││
│ └────────────┴───────┴──────┴──────┴─────────────────────┴────────┘│
│                                                                     │
│ Legend: ✅ Reachable/In Vote  ❌ Not Reachable  ⚪ Not Tested       │
│                                                                     │
│ ⚠️ Issues Detected:                                                 │
│ • faravahar: Cannot reach relay (not in vote)                      │
│ • tor26: IPv6 not reachable (NoIPv6Consensus flag)                 │
│ • dizum, longclaw: Not assigning Guard flag                        │
└─────────────────────────────────────────────────────────────────────┘
```

**Column Definitions**:
- **IPv4**: Authority can reach relay via IPv4 (derived from presence in vote with Running flag)
- **IPv6**: Authority can reach relay via IPv6 (derived from ReachableIPv6 flag; ⚪ = authority doesn't test IPv6)
- **Vote**: Relay included in authority's vote
- **Flags**: Flags assigned by this authority
- **Bandwidth**: Bandwidth value in authority's vote

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

### Phase 3: Bandwidth Measurements Section (Medium Priority)

**Problem Solved**: "Why is my consensus weight so low?" / "Why is my relay unmeasured?"

**Location**: New section on `relay-info.html` (below Flag Eligibility)

**Data Source**: CollecTor bandwidth files (most recent hour only) - `https://collector.torproject.org/recent/relay-descriptors/bandwidths/`

**Mockup**:
```
┌─────────────────────────────────────────────────────────────────────┐
│ 📊 Bandwidth Authority Measurements                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ Consensus Weight: 45,000 (0.23% of network)                        │
│ Measurement Status: ✅ MEASURED (by 6/7 bandwidth authorities)     │
│                                                                     │
│ ┌────────────┬──────────┬───────────┬────────────┬─────────────────┐
│ │ BW Auth    │ Measured │ bw Value  │ Deviation* │ Relay Uptime    │
│ ├────────────┼──────────┼───────────┼────────────┼─────────────────┤
│ │ moria1     │ ✅       │ 46,200    │ +2.7%      │ 45 days         │
│ │ tor26      │ ✅       │ 44,800    │ -0.4%      │ 45 days         │
│ │ gabelmoo   │ ✅       │ 44,100    │ -2.0%      │ 45 days         │
│ │ maatuska   │ ✅       │ 45,800    │ +1.8%      │ 45 days         │
│ │ longclaw   │ ✅       │ 44,500    │ -1.1%      │ 45 days         │
│ │ bastet     │ ✅       │ 44,900    │ -0.2%      │ 45 days         │
│ │ faravahar  │ ❌       │ —         │ 🔴 N/A     │ 45 days         │
│ └────────────┴──────────┴───────────┴────────────┴─────────────────┘
│                                                                     │
│ * Deviation from average. Hover for details.                       │
│   Values outside ±5% highlighted in red (indicates measurement     │
│   inconsistency - may warrant investigation).                      │
│                                                                     │
│ ⚠️ faravahar: Not measured (check reachability in votes above)     │
└─────────────────────────────────────────────────────────────────────┘
```

**Column Definitions**:
- **BW Auth**: Bandwidth authority name (only shows 7 BW authorities, not all 9 DAs)
- **Measured**: Whether this authority has measured the relay
- **bw Value**: Bandwidth value assigned by this authority
- **Deviation**: Deviation from average measurement across all authorities
  - Values within ±5% = normal (black text)
  - Values outside ±5% = 🔴 red (indicates potential measurement issue)
  - Tooltip shows: "Normal variance is ±5%. Larger deviations may indicate network issues."
- **Relay Uptime**: Current relay uptime (relays need ~1-2 weeks uptime to be fully measured)

---

## 🏛️ Directory Authority Health Dashboard (Phase 4)

**Merged from**: [TOP_10_PRIORITIZED_FEATURES.md Feature #4](https://github.com/1aeo/allium/blob/cursor/future-features-review-5147/docs/features/planned/TOP_10_PRIORITIZED_FEATURES.md)

### Phase 4: Enhanced Directory Authorities Page (Medium Priority)

**Problem Solved**: "Is there a problem with the Tor network itself?" / "Are all authorities functioning?"

**Location**: Enhanced existing `misc-authorities.html` (NOT a new page)

**Data Sources** (most recent data only - no historical parsing):
- CollecTor votes (latest hour) - voting participation, relay counts
- CollecTor consensus (latest) - flag distribution, thresholds
- Direct HTTP latency checks to authority directory ports
- Onionoo (authority uptime - already integrated)

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
| Flag thresholds display | ❌ Not implemented | — |
| Alert system | ❌ Not implemented | — |

### Enhanced Page Mockup (Single Page - All Content)

```
┌─────────────────────────────────────────────────────────────────┐
│ 🏛️ Directory Authorities                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Consensus: ✅ FRESH │ 9/9 Voted │ Next: 15:00 UTC (23 min) │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ ══ Authority Status ════════════════════════════════════════════│
│ ┌──────────┬────────┬──────┬───────┬─────────┬────────┬───────┐│
│ │Authority │ Status │ Vote │BW Auth│ Latency │ Uptime │Relays ││
│ ├──────────┼────────┼──────┼───────┼─────────┼────────┼───────┤│
│ │ moria1   │ 🟢 OK  │  ✅  │  ✅   │  12ms   │ 99.9%  │ 8,247 ││
│ │ tor26    │ 🟢 OK  │  ✅  │  ✅   │   8ms   │ 99.9%  │ 8,193 ││
│ │ dizum    │ 🟢 OK  │  ✅  │  —    │  15ms   │ 99.8%  │ 8,301 ││
│ │ gabelmoo │ 🟢 OK  │  ✅  │  ✅   │  11ms   │ 99.9%  │ 8,245 ││
│ │dannenberg│ 🟢 OK  │  ✅  │  —    │  19ms   │ 99.7%  │ 8,156 ││
│ │ maatuska │ 🟢 OK  │  ✅  │  ✅   │   7ms   │ 99.9%  │ 8,212 ││
│ │ longclaw │ 🟢 OK  │  ✅  │  ✅   │  14ms   │ 99.6%  │ 8,189 ││
│ │ bastet   │ 🟢 OK  │  ✅  │  ✅   │  16ms   │ 99.5%  │ 8,201 ││
│ │faravahar │ 🟡 SLOW│  ✅  │  ✅   │  89ms   │ 97.8%  │ 8,178 ││
│ └──────────┴────────┴──────┴───────┴─────────┴────────┴───────┘│
│                                                                 │
│ ⚠️ Alerts: faravahar responding slowly (89ms, threshold: 50ms) │
│                                                                 │
│ ══ Current Flag Thresholds (from latest consensus) ═════════════│
│ ┌─────────┬──────────────────────────┬─────────────────────────┐│
│ │ Flag    │ Requirement              │ Current Threshold       ││
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
│ ══ Flag Distribution (from latest consensus) ═══════════════════│
│ Running  ████████████████████████████████ 7,234 (87.7%)        │
│ Fast     ████████████████████████████     6,891 (83.6%)        │
│ Stable   ████████████████████████         5,678 (68.9%)        │
│ Guard    ████████████████                 2,845 (34.5%)        │
│ Exit     ███████████                      1,923 (23.3%)        │
│ V2Dir    ████████████████████████████████ 7,156 (86.8%)        │
│ HSDir    ███████████████████████████████  6,987 (84.7%)        │
│                                                                 │
│ ══ Existing Sections (already implemented) ═════════════════════│
│ [Authority Uptime Z-Scores] [Version Compliance] [Contact Info] │
│                                                                 │
│ Last updated: 14:45 UTC • Data from: CollecTor + Direct HTTP   │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation Components

| Component | File | Purpose |
|-----------|------|---------|
| Authority Latency Checker | `lib/consensus/authority_monitor.py` | Direct HTTP checks |
| Vote/Consensus Parser | `lib/consensus/collector_fetcher.py` | Parse latest CollecTor data |
| Alert System | `lib/consensus/authority_alerts.py` | Generate alerts |
| Template | `misc-authorities.html` | Enhanced (not new page) |

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
│       ├── collector_fetcher.py      # Fetch latest votes + bandwidth from CollecTor
│       ├── authority_monitor.py      # Direct HTTP latency checks (Phase 4)
│       └── authority_alerts.py       # Simple alert generation (Phase 4)
├── templates/
│   ├── relay-info.html               # MODIFY: Add consensus diagnostics (Phases 1-3)
│   └── misc-authorities.html         # MODIFY: Add health indicators (Phase 4)
└── cache/
    └── consensus/
        └── collector_data.json       # Cached latest CollecTor data (hourly)
```

**Note**: No new pages created. All features enhance existing pages.

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

**Data Scope**: Most recent CollecTor data only (latest hour). NO historical data parsing.

### 🚀 Milestone 1: Per-Relay Diagnostics (Phases 1-3) - 4 Weeks

#### Sprint 1: Core Infrastructure (Week 1)
- [ ] Create `lib/consensus/` directory structure
- [ ] Implement `collector.py` - CollecTor configuration
- [ ] Implement `authorities.py` - Authority fingerprint mapping
- [ ] Implement `collector_fetcher.py` - Fetch latest votes + bandwidth files

#### Sprint 2: Worker Integration (Week 2)
- [ ] Add `fetch_collector_data()` worker to `lib/workers.py`
- [ ] Implement `get_relay_diagnostics()` lookup function
- [ ] Set up hourly caching (only latest CollecTor data)
- [ ] Test with multi-API coordinator

#### Sprint 3: Relay Page Implementation (Week 3)
- [ ] Add Phase 1 (Authority Votes & Reachability) section to `relay-info.html`
- [ ] Add Phase 2 (Flag Eligibility) section to `relay-info.html`
- [ ] Add Phase 3 (Bandwidth Measurements) section to `relay-info.html`
- [ ] Add CSS styles for diagnostic components

#### Sprint 4: Testing & Polish (Week 4)
- [ ] Unit tests for CollecTor parsing
- [ ] Integration tests with real data
- [ ] Performance testing (7000+ relays)
- [ ] Error handling and graceful degradation

---

### 🏛️ Milestone 2: Authority Dashboard Enhancement (Phase 4) - 2-3 Weeks

#### Sprint 5: Authority Health Data (Week 5)
- [ ] Implement `authority_monitor.py` - Direct HTTP latency checks
- [ ] Add consensus freshness indicators (from latest consensus)
- [ ] Add voting participation count (from latest votes)
- [ ] Add flag thresholds display (from latest votes)

#### Sprint 6: Enhanced misc-authorities.html (Week 6)
- [ ] Add status indicators (online/slow/degraded/offline)
- [ ] Add flag distribution bars (from latest consensus)
- [ ] Implement `authority_alerts.py` - Simple alert generation
- [ ] Update template with all new sections

---

### Success Criteria

#### Phases 1-3 (Per-Relay Diagnostics):
- [ ] Authority vote + reachability lookup for any relay (< 100ms)
- [ ] Flag eligibility analysis with threshold comparison
- [ ] Bandwidth measurement display from 7 BW authorities
- [ ] Deviation values color-coded (red if outside ±5%)
- [ ] < 2 second page load time for relay-info.html

#### Phase 4 (Authority Dashboard):
- [ ] Latency checks for all 9 authorities
- [ ] Voting participation count from latest hour
- [ ] Flag thresholds from latest consensus
- [ ] Flag distribution visualization
- [ ] Simple alert display for offline/slow authorities

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

## 🔮 Future: Historical Data Features (Not In Scope)

The following features require historical data storage and parsing, which adds significant compute overhead. These are **NOT part of the current implementation plan** and are documented here for future consideration.

### Deferred Features

| Feature | Requires | Why Deferred |
|---------|----------|--------------|
| Authority performance scorecards | 30-day historical data | Requires DB/file storage, hourly aggregation |
| 7-day/30-day trend graphs | Historical time series | Requires storing hourly snapshots |
| Voting participation history | Per-hour vote tracking | Requires cumulative storage |
| Performance degradation detection | Trend analysis | Requires ML/statistical models |
| Troubleshooting wizard | Historical comparison | Could use Onionoo instead |

### Future Implementation Notes

If historical features are desired later:
1. **Storage**: Add SQLite or file-based storage for hourly snapshots
2. **Retention**: Keep 30 days of hourly data (~720 snapshots)
3. **Aggregation**: Run daily job to compute statistics
4. **Compute**: Estimate ~5-10 min per hourly parse if re-processing

### Troubleshooting Wizard Alternative

Instead of historical data, the troubleshooting wizard could:
- Use Onionoo's existing historical uptime data
- Link directly to relay detail pages with diagnostics
- Provide static guidance based on common issues

---

**Document Status**: Ready for implementation  
**Data Scope**: Most recent CollecTor data only (latest hour) - NO historical parsing  
**Primary Data Source**: Tor Project CollecTor (https://collector.torproject.org)  
**Merged From**: [TOP_10_PRIORITIZED_FEATURES.md Feature #4](https://github.com/1aeo/allium/blob/cursor/future-features-review-5147/docs/features/planned/TOP_10_PRIORITIZED_FEATURES.md)

### Implementation Summary

| Milestone | Target | Phases | Timeline |
|-----------|--------|--------|----------|
| **Milestone 1** | Per-relay diagnostics (`relay-info.html`) | 1-3 | 4 weeks |
| **Milestone 2** | Authority dashboard (`misc-authorities.html`) | 4 | 2-3 weeks |

**Total Effort**: 6-7 weeks  
**Next Steps**: Sprint 1 - Core Infrastructure
