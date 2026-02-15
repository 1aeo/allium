# Multi-API Implementation Plan

**Status**: 🚧 In Planning  
**Started**: 2025-01-06  
**Target Completion**: TBD  
**Branch**: `multi_api`

---

## 📋 Executive Summary

This document outlines the plan to restructure Allium to support multiple API sources with different completion times, enabling dynamic page updates and graceful degradation when APIs are unavailable.

### Current State
- **Single API**: Only onionoo details (~1 minute)
- **Synchronous**: Sequential execution, waits for completion
- **Modular**: Core logic in `lib/relays.py` (~1,100 lines) with extracted modules: `page_writer.py`, `network_health.py`, `operator_analysis.py`, `categorization.py`, `flag_analysis.py`, `time_utils.py`, `ip_utils.py` (refactored 2026-02-15 from monolithic ~5,900 line file)

### Target State
- **5 APIs** running in parallel with different completion times
- **Dynamic rendering**: Pages update as each API completes
- **Graceful degradation**: Use cached data when APIs fail/timeout
- **Maintainable**: Simple, debuggable architecture

---

## 🎯 Requirements

### APIs to Support
| API | Completion Time | Purpose | Priority |
|-----|----------------|---------|----------|
| Onionoo details | 1 min | Relay information | Critical |
| Onionoo uptime | 1 min | Relay uptime stats | High |
| CollecTor | 5 min | Authority data | Medium |
| Consensus health scraping | 10 min | Directory authority health | Medium |
| AROI verifier | 15 min | Contact verification | Low |

### Key Requirements
- ✅ **Parallel execution**: All APIs run concurrently
- ✅ **Dynamic updates**: Pages refresh as data becomes available
- ✅ **Incremental rendering**: Don't wait for slow APIs after first run
- ✅ **Fault tolerance**: Continue with cached data if APIs fail
- ✅ **Simple maintenance**: Easy to add/remove/disable APIs
- ✅ **Backwards compatibility**: Existing functionality preserved

---

## 🔍 Architecture Research Summary

### Options Evaluated

| Option | Complexity | Maintenance | Performance | Verdict |
|--------|------------|-------------|-------------|---------|
| **Event-Driven Architecture** | High | High | Medium | ❌ Too complex |
| **Async Task Manager** | High | Medium | High | ❌ Requires full rewrite |
| **Plugin Architecture** | Very High | Medium | High | ❌ Over-engineered |
| **Simple Worker Pool** | Medium | Good | Medium | ✅ **Recommended** |
| **Microservice-Style** | Very High | Low | High | ❌ Too complex |

### Decision Rationale
**Option 4 (Simple Worker Pool)** was selected because:
- ✅ **Closest to current patterns**: Builds on existing code structure
- ✅ **Minimal learning curve**: Uses familiar Python threading
- ✅ **Incremental migration**: Can extract existing functions
- ✅ **Debuggable**: File-based state and clear execution flow

---

## 🏗️ Recommended Solution: Option 4A (Minimal Threading Extension)

### Architecture Overview
```
allium/
├── allium.py              # MODIFIED (add threading coordination)
├── lib/
│   ├── relays.py         # MODIFIED (thread-safe data processing) ~1,100 lines
│   ├── page_writer.py    # HTML generation (extracted from relays.py)
│   ├── network_health.py # Network statistics (extracted from relays.py)
│   ├── operator_analysis.py # Operator/contact analysis (extracted from relays.py)
│   ├── categorization.py # Relay categorization (extracted from relays.py)
│   ├── flag_analysis.py  # Flag uptime analysis (extracted from relays.py)
│   ├── time_utils.py     # Time formatting (extracted from relays.py)
│   ├── ip_utils.py       # IP utilities (extracted from relays.py)
│   └── workers.py        # NEW (simple API worker functions)
├── data/cache/           # NEW (individual API cache files)
└── templates/            # UNCHANGED
```

### Core Pattern
```python
# Simple worker functions
def fetch_onionoo_details():
    try:
        data = _do_onionoo_fetch()  # Existing logic
        _save_cache('onionoo_details', data)
        _mark_ready('onionoo_details')
        return data
    except Exception as e:
        _mark_stale('onionoo_details', str(e))
        return _load_cache('onionoo_details')

# Simple coordination
def main():
    workers = [
        threading.Thread(target=fetch_onionoo_details),
        threading.Thread(target=fetch_onionoo_uptime),
        # ... other workers
    ]
    
    for worker in workers:
        worker.start()
    
    monitor_and_render()  # Watch for completion, update pages
```

### Benefits
- **90% of benefits with 20% of complexity**
- **Only 1 new file, ~120 new lines of code**
- **Natural evolution of existing patterns**
- **Easy to understand and debug**

---

## 📅 Implementation Plan

### Phase 1: Foundation (Week 1) ✅ **COMPLETED**
**Goal**: Extract onionoo logic and add threading support

#### Tasks
- [x] **Create `lib/workers.py`** (~320 lines)
  - [x] Extract `_fetch_onionoo_details()` → `fetch_onionoo_details()`
  - [x] Add cache management functions (`_save_cache`, `_load_cache`)
  - [x] Add status tracking functions (`_mark_ready`, `_mark_stale`)
  - [x] Add placeholder functions for future APIs

- [x] **Create `lib/coordinator.py`** (~150 lines)
  - [x] Simple coordinator for managing API workers
  - [x] Backwards compatible function for seamless integration
  - [x] Progress logging in same format as main allium.py

- [x] **Modify `allium.py`** (+2 lines)
  - [x] Add coordinator imports
  - [x] Replace direct `Relays()` call with `create_relay_set_with_coordinator()`
  - [x] Maintain full backwards compatibility

- [x] **Modify `lib/relays.py`** (minimal changes — now ~1,100 lines after modular extraction)
  - [x] Make data processing thread-safe
  - [x] Accept data as input rather than fetching internally (`relay_data` parameter)
  - [x] Support both old and new initialization patterns

#### Success Criteria
- ✅ Same functionality as before - **VERIFIED**
- ✅ Threading infrastructure in place - **IMPLEMENTED**
- ✅ All existing tests pass - **CONFIRMED**
- ✅ Cache system working (`allium/data/cache/`) - **OPERATIONAL**
- ✅ Worker status tracking (`allium/data/state.json`) - **FUNCTIONAL**
- ✅ Full site generation working - **TESTED AND VERIFIED**

#### **🎉 Implementation Results**
- **Files Created**: `lib/workers.py`, `lib/coordinator.py`
- **Cache Directory**: `allium/data/cache/` with JSON files and timestamps
- **State Tracking**: `allium/data/state.json` with worker status monitoring
- **Backwards Compatibility**: 100% maintained - existing usage patterns work unchanged
- **New Architecture**: Ready for Phase 2 multi-API expansion

#### Code Changes Summary
| File | Lines Added | Lines Modified | Description |
|------|-------------|----------------|-------------|
| `lib/workers.py` | +100 | 0 | New worker functions |
| `allium.py` | +20 | 5 | Threading coordination |
| `lib/relays.py` | +10 | ~1,100 | Thread-safe modifications (post-refactor, was ~5,900) |

---

### Phase 2: Add Second API (Week 2)
**Goal**: Prove the pattern works with onionoo uptime

#### Tasks
- [ ] **Add to `lib/workers.py`**
  - [ ] `fetch_onionoo_uptime()` function
  - [ ] Cache management for uptime data
  - [ ] Error handling and fallbacks

- [ ] **Add incremental rendering**
  - [ ] Monitor function to watch for API completion
  - [ ] Re-render only affected pages when uptime data arrives
  - [ ] Status indicators for stale/fresh data

#### Success Criteria
- ✅ Pages update when uptime data becomes available
- ✅ Graceful degradation when uptime API fails
- ✅ Performance improvement visible

#### Expected Timeline
- **Day 1-2**: Implement uptime worker
- **Day 3-4**: Add incremental rendering
- **Day 5**: Testing and refinement

---

### Phase 3: Scale to All APIs (Week 3-4)
**Goal**: Add remaining 3 APIs

#### Tasks
- [ ] **Add worker functions**
  - [ ] `fetch_collector_data()` (CollecTor API)
  - [ ] `fetch_consensus_health()` (consensus health scraping)
  - [ ] `fetch_aroi_verifier()` (AROI verification)

- [ ] **Enhance coordination**
  - [ ] Timeout handling per API
  - [ ] Error fallback to cached data
  - [ ] Status tracking and reporting
  - [ ] Progress indicators

#### Success Criteria
- ✅ All 5 APIs running in parallel
- ✅ Proper fallbacks for each API
- ✅ Performance monitoring in place
- ✅ Documentation updated

#### Expected Timeline
- **Week 3**: CollecTor and consensus health APIs
- **Week 4**: AROI verifier and final integration

---

## 🔧 Technical Implementation Details

### File Changes Overview

#### New Files
```python
# lib/workers.py - Simple API worker functions
def fetch_onionoo_details():
    """Current onionoo logic extracted to simple function"""
    pass

def fetch_onionoo_uptime():
    """Fetch uptime data from onionoo"""
    pass

def fetch_collector_data():
    """Fetch data from CollecTor API"""
    pass

def fetch_consensus_health():
    """Scrape consensus health information"""
    pass

def fetch_aroi_verifier():
    """Verify AROI contact information"""
    pass

# Cache and state management functions
def _save_cache(api_name, data):
    """Save API data to cache file"""
    pass

def _load_cache(api_name):
    """Load API data from cache file"""
    pass

def _mark_ready(api_name):
    """Mark API as successfully completed"""
    pass

def _mark_stale(api_name, error):
    """Mark API as failed/stale"""
    pass
```

#### Modified Files
```python
# allium.py - Add coordination logic
import threading
from lib.workers import *

def main():
    """Modified entry point with worker coordination"""
    workers = []
    
    # Start all API workers
    for worker_func in [fetch_onionoo_details, fetch_onionoo_uptime, 
                       fetch_collector_data, fetch_consensus_health]:
        workers.append(threading.Thread(target=worker_func))
    
    for worker in workers:
        worker.start()
    
    # Monitor and render incrementally
    monitor_and_render()

def monitor_and_render():
    """Watch for API completion, update pages incrementally"""
    while any_workers_running():
        time.sleep(5)
        
        for api_name in get_newly_completed():
            update_pages_for_api(api_name)
            mark_api_processed(api_name)

# lib/relays.py - Make thread-safe (note: relays.py is now ~1,100 lines after modular extraction)
class RelayProcessor:
    """Renamed from Relays, focused on data processing only"""
    def __init__(self, relay_data):
        self.json = relay_data  # Data passed in, not fetched
        # Remove all API fetching logic
```

### Cache Strategy
```
data/cache/
├── onionoo_details.json      # Relay data
├── onionoo_uptime.json       # Uptime statistics  
├── collector.json            # Authority data
├── consensus_health.json     # Health metrics
├── aroi_verifier.json        # Contact verification
└── timestamps.json           # Last update times
```

### State Management
```json
{
  "apis": {
    "onionoo_details": {
      "status": "ready",
      "last_update": "2025-01-06T10:30:00Z",
      "duration_ms": 45000,
      "error": null
    },
    "onionoo_uptime": {
      "status": "stale", 
      "last_update": "2025-01-06T09:15:00Z",
      "duration_ms": 120000,
      "error": "Connection timeout"
    }
  },
  "rendering": {
    "last_full_render": "2025-01-06T10:30:00Z",
    "pending_updates": ["consensus_health"]
  }
}
```

### Incremental Rendering Strategy
```python
def update_pages_for_api(api_name):
    """Re-render only pages affected by this API"""
    if api_name == 'onionoo_details':
        # Core relay data affects most pages
        render_index_page()
        render_relay_listings()
        render_network_stats()
        
    elif api_name == 'onionoo_uptime':
        # Uptime only affects relay detail pages
        render_relay_info_pages()
        
    elif api_name == 'collector':
        # Authority data affects authority pages
        render_authority_pages()
        
    elif api_name == 'consensus_health':
        # Health data affects monitoring pages
        render_health_dashboard()
        
    elif api_name == 'aroi_verifier':
        # AROI data affects contact verification
        render_contact_verification_pages()
```

---

## 📊 Expected Outcomes

### Performance Improvements
- **Initial page load**: ~1 min (onionoo details only)
- **Full data availability**: ~15 min (all APIs complete)
- **Subsequent runs**: ~1 min (use cached data for slow APIs)
- **User experience**: Progressive enhancement as data arrives

### User Experience Flow
1. **0-1 min**: Basic relay information available (onionoo details)
2. **1-2 min**: Uptime statistics appear (onionoo uptime)
3. **5 min**: Authority information updated (CollecTor)
4. **10 min**: Health monitoring active (consensus health)
5. **15 min**: Contact verification complete (AROI)

### Maintenance Benefits
- **Simple debugging**: Clear worker functions and file-based state
- **Easy API addition**: New APIs = new worker functions
- **Familiar patterns**: Standard Python threading
- **Configuration-driven**: Enable/disable APIs easily

---

## 🛡️ Risk Mitigation & Testing

### Migration Strategy
1. **Backwards compatibility**: Keep existing entry point working
2. **Gradual rollout**: Enable new APIs one at a time
3. **Feature flags**: Can disable individual APIs via configuration
4. **Rollback plan**: All changes are additive

### Testing Plan
- [ ] **Unit tests**: Each worker function tested independently
- [ ] **Integration tests**: Full workflow with mocked APIs  
- [ ] **Performance tests**: Memory usage and timing validation
- [ ] **Failure tests**: API timeout and error scenarios
- [ ] **Load tests**: Multiple concurrent executions

### Monitoring & Observability
- [ ] **Timing metrics**: Track API response times
- [ ] **Error rates**: Monitor API failure frequencies
- [ ] **Cache hit rates**: Measure cache effectiveness
- [ ] **User experience**: Page load time improvements

---

## 📈 Progress Tracking

### Phase 1 Progress: Foundation
- [ ] **Planning Complete**: ✅ Architecture decided, plan documented
- [ ] **Environment Setup**: Clone repo, create branch, test current functionality
- [ ] **Worker Extraction**: Move onionoo logic to workers.py
- [ ] **Threading Integration**: Add coordination to allium.py
- [ ] **Testing**: Verify equivalent functionality
- [ ] **Documentation**: Update code comments and README

### Phase 2 Progress: Second API
- [ ] **Uptime API Implementation**: Add onionoo uptime worker
- [ ] **Incremental Rendering**: Implement selective page updates
- [ ] **Error Handling**: Add graceful degradation
- [ ] **Performance Validation**: Measure improvements
- [ ] **User Testing**: Verify experience improvement

### Phase 3 Progress: Full Implementation
- [ ] **CollecTor API**: Implement authority data fetching
- [ ] **Consensus Health**: Add health monitoring
- [ ] **AROI Verifier**: Add contact verification
- [ ] **Integration Testing**: Full system validation
- [ ] **Performance Optimization**: Fine-tune coordination
- [ ] **Documentation**: Complete implementation guide

---

## 🔗 Related Documentation

- [Original Architecture Analysis](../architecture/) - Current system documentation
- [Performance Benchmarks](../performance/) - Baseline measurements
- [API Specifications](../implementation/) - External API documentation
- [Testing Guidelines](../../tests/) - Testing standards and procedures

---

## 📝 Decision Log

| Date | Decision | Rationale | Impact |
|------|----------|-----------|---------|
| 2025-01-06 | Selected Option 4A (Minimal Threading) | Best balance of simplicity and functionality | Low complexity, high value |
| 2025-01-06 | File-based caching strategy | Familiar pattern, easy to debug | Consistent with current approach |
| 2025-01-06 | Threading over async/await | Team familiarity, incremental change | Lower learning curve |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.7+ with threading support
- Existing allium development environment
- Git branch: `multi_api`

### Quick Start
1. **Review this plan**: Understand the architecture and phases
2. **Set up development environment**: Ensure tests pass on current code
3. **Start Phase 1**: Begin with worker extraction
4. **Follow the checklist**: Use the progress tracking above
5. **Update this document**: Keep progress current

### Need Help?
- Review the original architecture research in the chat history
- Check existing similar patterns in the codebase
- Test each phase independently before moving to the next
- Document any deviations from this plan

---

**Last Updated**: 2025-01-06  
**Next Review**: After Phase 1 completion 