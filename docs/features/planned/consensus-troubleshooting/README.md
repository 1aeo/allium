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

## 🚀 Phase 1: Per-Relay Consensus Diagnostics

**Location**: `relay-info.html` - New "Consensus Diagnostics" section

**Data Sources**: CollecTor votes + bandwidth files (fetched once/hour, indexed by fingerprint)

### Features

| Section | Data Source | What It Shows |
|---------|-------------|---------------|
| **Authority Votes & Reachability** | CollecTor votes | Which authorities voted, IPv4/IPv6 reachability, flags assigned |
| **Flag Eligibility** | CollecTor votes (thresholds) | Why relay has/doesn't have Guard, Stable, Fast, HSDir flags |
| **Bandwidth Measurements** | CollecTor bandwidth files | Per-authority bw values, deviation (red if >±5%), relay uptime |

### Mockup

```
┌─────────────────────────────────────────────────────────────────────┐
│ 🔍 Consensus Diagnostics                                            │
│ Data from: 2025-12-26 04:00 UTC (latest CollecTor)                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ ══ Authority Votes & Reachability ══════════════════════════════════│
│ Status: ✅ IN CONSENSUS (8/9 authorities)                          │
│                                                                     │
│ ┌────────────┬──────┬──────┬──────┬─────────────────────┬─────────┐│
│ │ Authority  │ IPv4 │ IPv6 │ Vote │ Flags               │Bandwidth││
│ ├────────────┼──────┼──────┼──────┼─────────────────────┼─────────┤│
│ │ moria1     │  ✅  │  ✅  │  ✅  │ Fast Guard Stable   │ 45,000  ││
│ │ tor26      │  ✅  │  ❌  │  ✅  │ Fast Guard Stable   │ 44,800  ││
│ │ dizum      │  ✅  │  ⚪  │  ✅  │ Fast Stable         │ 43,200  ││
│ │ faravahar  │  ❌  │  ❌  │  ❌  │ —                   │ —       ││
│ └────────────┴──────┴──────┴──────┴─────────────────────┴─────────┘│
│ ⚠️ faravahar: Cannot reach relay • dizum: Not assigning Guard      │
│                                                                     │
│ ══ Flag Eligibility (Guard) ════════════════════════════════════════│
│ ┌────────────────────┬────────────┬────────────┬───────────────────┐│
│ │ Requirement        │ Your Value │ Threshold  │ Status            ││
│ ├────────────────────┼────────────┼────────────┼───────────────────┤│
│ │ WFU (Uptime)       │ 96.2%      │ ≥98%       │ ❌ Below (-1.8%)  ││
│ │ Time Known         │ 45 days    │ ≥8 days    │ ✅ Above          ││
│ │ Bandwidth          │ 25 MB/s    │ ≥29 MB/s   │ ❌ Below (-14%)   ││
│ └────────────────────┴────────────┴────────────┴───────────────────┘│
│                                                                     │
│ ══ Bandwidth Measurements ══════════════════════════════════════════│
│ Measured by: 6/7 bandwidth authorities                              │
│ ┌────────────┬──────────┬───────────┬────────────┬─────────────────┐│
│ │ BW Auth    │ Measured │ bw Value  │ Deviation* │ Relay Uptime    ││
│ ├────────────┼──────────┼───────────┼────────────┼─────────────────┤│
│ │ moria1     │ ✅       │ 46,200    │ +2.7%      │ 45 days         ││
│ │ gabelmoo   │ ✅       │ 44,100    │ -2.0%      │ 45 days         ││
│ │ faravahar  │ ❌       │ —         │ 🔴 N/A     │ 45 days         ││
│ └────────────┴──────────┴───────────┴────────────┴─────────────────┘│
│ * Values outside ±5% shown in red (hover for details)              │
└─────────────────────────────────────────────────────────────────────┘
```

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

### Mockup

```
┌─────────────────────────────────────────────────────────────────┐
│ 🏛️ Directory Authorities                                        │
├─────────────────────────────────────────────────────────────────┤
│ Consensus: ✅ FRESH │ 9/9 Voted │ Next: 15:00 UTC (23 min)     │
├─────────────────────────────────────────────────────────────────┤
│ ┌──────────┬────────┬──────┬───────┬─────────┬────────┬───────┐│
│ │Authority │ Status │ Vote │BW Auth│ Latency │ Uptime │Relays ││
│ ├──────────┼────────┼──────┼───────┼─────────┼────────┼───────┤│
│ │ moria1   │ 🟢 OK  │  ✅  │  ✅   │  12ms   │ 99.9%  │ 8,247 ││
│ │ faravahar│ 🟡 SLOW│  ✅  │  ✅   │  89ms   │ 97.8%  │ 8,178 ││
│ └──────────┴────────┴──────┴───────┴─────────┴────────┴───────┘│
│ ⚠️ Alert: faravahar responding slowly (89ms)                   │
├─────────────────────────────────────────────────────────────────┤
│ Flag Thresholds: Guard WFU≥98%, BW≥29MB/s │ Stable ≥20.2 days │
├─────────────────────────────────────────────────────────────────┤
│ Running 7,234 │ Fast 6,891 │ Guard 2,845 │ Exit 1,923          │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Compute Efficiency Design

### Data Flow (Minimizing Hourly Compute)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    HOURLY DATA FETCH (ONCE)                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  CollecTor API                                                      │
│  ├─ GET /recent/relay-descriptors/votes/      (~50MB, 9 files)     │
│  └─ GET /recent/relay-descriptors/bandwidths/ (~50MB, 7 files)     │
│                                                                     │
│         ↓ Parse ONCE                                                │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              RELAY INDEX (built once, O(1) lookup)          │   │
│  │                                                              │   │
│  │  relay_index[fingerprint] = {                               │   │
│  │      'votes': {auth_name: {flags, bandwidth, ...}},         │   │
│  │      'bandwidth': {auth_name: {bw_value, ...}}              │   │
│  │  }                                                           │   │
│  │                                                              │   │
│  │  ~7,000 relays indexed                                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│         ↓ Cache to disk                                             │
│                                                                     │
│  cache/consensus/collector_data.json                                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    PAGE GENERATION (per relay)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  get_relay_diagnostics(fingerprint):                                │
│      return relay_index[fingerprint]  # O(1) lookup, no parsing    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Efficiency Principles

| Principle | Implementation |
|-----------|----------------|
| **Fetch once, use many** | CollecTor data fetched once/hour, indexed, cached |
| **Parallel fetching** | Uses existing `Coordinator.fetch_all_apis_threaded()` pattern |
| **Index by fingerprint** | O(1) lookup during page generation, no per-relay parsing |
| **No re-parsing** | Index built once after fetch, persisted to cache |
| **Graceful degradation** | If fetch fails, use cached data (up to 3 hours old) |

### Integration with Existing Architecture

```python
# In lib/workers.py - NEW WORKER (follows existing pattern)
def fetch_collector_consensus_data(progress_logger=None):
    """
    Fetch votes + bandwidth from CollecTor.
    Runs in parallel with other API workers via Coordinator.
    """
    api_name = "collector_consensus"
    
    # Check cache age - only fetch if older than 1 hour
    cache_age = _cache_manager.get_cache_age(api_name)
    if cache_age and cache_age < 3600:
        return _load_cache(api_name)
    
    # Fetch from CollecTor (parallel HTTP requests for 9 votes + 7 bw files)
    votes = _fetch_collector_votes()        # ~5-10 sec
    bandwidth = _fetch_collector_bandwidth() # ~3-5 sec
    
    # Build relay index ONCE
    relay_index = _build_relay_index(votes, bandwidth)
    
    # Cache the indexed data
    data = {
        'votes': votes,
        'bandwidth': bandwidth,
        'relay_index': relay_index,
        'flag_thresholds': _extract_thresholds(votes),
        'fetched_at': time.time()
    }
    _save_cache(api_name, data)
    _mark_ready(api_name)
    
    return data

# In lib/coordinator.py - ADD TO api_workers LIST
self.api_workers.append(("collector_consensus", fetch_collector_consensus_data, [self._log_progress]))
```

---

## 📅 Implementation Timeline

### Phase 1: Per-Relay Diagnostics (4 weeks)

| Sprint | Focus | Deliverables |
|--------|-------|--------------|
| **Week 1** | Core Infrastructure | `lib/consensus/` module, `collector_fetcher.py`, relay index builder |
| **Week 2** | Worker Integration | Add to `workers.py`, integrate with `Coordinator`, caching |
| **Week 3** | Template Implementation | Update `relay-info.html` with diagnostics section, CSS |
| **Week 4** | Testing & Polish | Unit tests, integration tests, error handling |

### Phase 2: Authority Dashboard (2-3 weeks)

| Sprint | Focus | Deliverables |
|--------|-------|--------------|
| **Week 5** | Authority Health Data | `authority_monitor.py` for latency checks, alert system |
| **Week 6-7** | Template Enhancement | Update `misc-authorities.html`, flag thresholds, distribution bars |

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
└── cache/
    └── consensus/
        └── collector_data.json       # NEW: Cached indexed data
```

---

## ✅ Success Criteria

### Phase 1
- [ ] Per-relay vote/reachability lookup (< 100ms)
- [ ] Flag eligibility analysis with thresholds
- [ ] Bandwidth measurements with deviation coloring
- [ ] No increase in hourly compute time (data indexed once)

### Phase 2
- [ ] Authority latency checks (< 10s total)
- [ ] Flag thresholds from latest consensus
- [ ] Flag distribution visualization
- [ ] Simple alert for offline/slow authorities

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
