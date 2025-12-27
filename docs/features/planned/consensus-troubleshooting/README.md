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

### Consensus Voting Requirement

Per Tor Directory Spec: A relay appears in the consensus if **at least half (majority)** of authorities vote for it.
- With 9 authorities: **5 votes required** (⌊9/2⌋ + 1 = 5)
- `in_consensus = vote_count >= 5`

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
- [ ] Per-relay vote/reachability lookup (< 100ms)
- [ ] Flag eligibility analysis with thresholds
- [ ] Bandwidth measurements with deviation coloring
- [ ] No increase in hourly compute time (data indexed once)
- [ ] Baseline comparison shows only expected changes

### Phase 2
- [ ] `pytest tests/test_authority_monitor.py -v` passes
- [ ] Authority latency checks (< 10s total)
- [ ] Flag thresholds from latest consensus
- [ ] Flag distribution visualization
- [ ] Simple alert for offline/slow authorities
- [ ] Final regression test passes

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
