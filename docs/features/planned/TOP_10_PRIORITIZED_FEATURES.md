# Top Prioritized Future Features for Allium (Updated)

**Status**: 📊 Code Review Complete - Features NOT Yet Implemented  
**Date**: December 2024  
**Document Type**: Strategic Feature Prioritization  

---

## Codebase Review Summary

After comprehensive review of the actual Allium codebase, several features from the original list have been **fully or partially implemented**. This updated document focuses only on features that require new development.

### Already Implemented (Removed from Priority List)

| Feature | Implementation Status | Location |
|---------|----------------------|----------|
| **AROI Leaderboards** | ✅ Fully implemented (18 categories, champions, rankings) | `aroi-leaderboards.html`, `aroileaders.py` |
| **Network Health Dashboard** | ✅ Fully implemented (relay counts, bandwidth, uptime, AROI validation) | `network-health-dashboard.html` |
| **Intelligence Engine** | ✅ Fully implemented (14 layers, contact intelligence) | `intelligence_engine.py` |
| **Operator Reliability Metrics** | ✅ Fully implemented (uptime, bandwidth stability, flag reliability) | `relays.py`, `contact.html` |
| **CW/BW Performance Analysis** | ✅ Fully implemented (ratios, percentiles, network comparison) | `intelligence_engine.py`, `contact.html` |
| **Geographic Diversity Stats** | ✅ Fully implemented (EU/Non-EU, Five Eyes, rare countries) | `network-health-dashboard.html` |
| **Platform Diversity Tables** | ✅ Fully implemented (non-Linux heroes, platform breakdown) | `aroi-leaderboards.html` |
| **Bandwidth Stability Analysis** | ✅ Fully implemented (CV, trend, capacity utilization) | `contact.html` |

---

## 🏆 Revised Top Features - NOT YET IMPLEMENTED

### #1: Interactive Geographic Heat Map Dashboard
**Priority Score: 95/100** | **Timeline: 4-6 weeks** | **Status: NOT IMPLEMENTED**

#### What's Missing
- ❌ No D3.js or Chart.js integration
- ❌ No interactive world map visualization  
- ❌ No color-coded country rendering
- ❌ No hover tooltips or click interactions
- ❌ Current implementation: Static tables only

#### What Exists (Can Be Reused)
- ✅ Country classification system exists
- ✅ Country relay counts available in `sorted['country']`
- ✅ Rare/frontier country categorization exists

#### Mockup
```
┌─────────────────────────────────────────────────────────────────┐
│ 🌍 Tor Network Global Distribution                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│    [Interactive World Map with Color-Coded Countries]           │
│                                                                 │
│    ┌────────────────────────────────────────────────────────┐  │
│    │                                                        │  │
│    │   🔴 USA (2,847)  🔵 Germany (1,923)  🟢 France (847) │  │
│    │                                                        │  │
│    │   [WORLD MAP WITH CLICKABLE REGIONS]                  │  │
│    │                                                        │  │
│    │   Color Legend:                                        │  │
│    │   ■ Legendary (1-5)  ■ Epic (6-20)  ■ Rare (21-49)   │  │
│    │   ■ Emerging (50-200)  ■ Common (201+)               │  │
│    │                                                        │  │
│    └────────────────────────────────────────────────────────┘  │
│                                                                 │
│    Hover Tooltip Example:                                       │
│    ┌─────────────────────────┐                                 │
│    │ 🇲🇳 Mongolia (MN)       │                                 │
│    │ 3 relays • 0.1% weight  │                                 │
│    │ Tier: Legendary 🏆       │                                 │
│    │ Top Operator: mn-relay   │                                 │
│    │ [View Country →]         │                                 │
│    └─────────────────────────┘                                 │
│                                                                 │
│ Summary: 195 countries • 8,247 relays • 67% EU / 33% Non-EU    │
│                                                                 │
│ [Filter: All] [Guards Only] [Exits Only] [By Tier ▼]           │
└─────────────────────────────────────────────────────────────────┘
```

#### Implementation Recommendations
1. **Add D3.js and TopoJSON** for geographic projections
2. **Create `static/js/geographic-heatmap.js`** with map rendering
3. **Add `allium/lib/geographic_visualization.py`** for data preparation
4. **Progressive enhancement**: Static SVG → Interactive → Animated

#### Files to Create/Modify
- `allium/lib/geographic_visualization.py` (NEW)
- `allium/templates/geographic_heatmap.html` (NEW)
- `static/js/geographic-heatmap.js` (NEW)
- `static/css/visualization.css` (NEW)

---

### #2: AROI Achievement Wheel Visualization
**Priority Score: 88/100** | **Timeline: 3-4 weeks** | **Status: PARTIALLY IMPLEMENTED**

#### What's Missing
- ❌ No Chart.js doughnut/wheel visualization
- ❌ No interactive rotating wheel UI
- ❌ No animated transitions between categories
- ❌ Current implementation: Tables only (no charts)

#### What Exists (Can Be Reused)
- ✅ All 18 AROI categories with full data
- ✅ Champion badges and rankings
- ✅ Complete leaderboard calculations in `aroileaders.py`

#### Mockup
```
┌─────────────────────────────────────────────────────────────────┐
│ 🏆 AROI Champions Achievement Wheel                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                    Champions Achievement Wheel                   │
│                                                                 │
│                         ⚡ Bandwidth                             │
│                        torworld.org                              │
│                            │                                     │
│                    ┌───────┴───────┐                            │
│        🏗️ Rare ──┤               ├── 🌍 Geographic              │
│       Countries   │      🏆       │    globalnet.org             │
│                   │   CHAMPIONS   │                              │
│        💻 ────────┤               ├────── ⚖️ Consensus          │
│      Platform     │               │      heavyweight.net         │
│                   └───────┬───────┘                              │
│                           │                                      │
│               ⏰ Reliability  🚪 Exit                            │
│                                                                  │
│    [Click any segment to view full category leaderboard]        │
└─────────────────────────────────────────────────────────────────┘
```

#### Implementation Recommendations
1. **Use Chart.js** for doughnut chart with custom segments
2. **Add click handlers** linking to existing leaderboard sections
3. **Animate segment highlights** on hover
4. **Mobile-responsive** with touch interactions

---

### #3: Actionable Improvement Guidance System
**Priority Score: 85/100** | **Timeline: 4-6 weeks** | **Status: NOT IMPLEMENTED**

#### What's Missing
- ❌ No "Path to Improvement" section on operator pages
- ❌ No gap analysis vs top performers
- ❌ No personalized action recommendations
- ❌ No difficulty/impact scoring for suggestions
- ❌ No progress tracking toward goals

#### What Exists (Can Be Reused)
- ✅ AROI leaderboard rankings exist
- ✅ Contact rankings already show position in each category
- ✅ Performance metrics available (CW/BW, uptime, diversity)

#### Mockup
```
┌─────────────────────────────────────────────────────────────────┐
│ 🎯 Path to Improvement - youroperator.org                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────┐│
│ │ Bandwidth Gap   │ │ Diversity Gap   │ │ Biggest Opportunity ││
│ │                 │ │                 │ │                     ││
│ │ +234.5 Gbps     │ │ +8.2 points     │ │ 🌍 Geographic       ││
│ │ to reach #1     │ │ to reach #1     │ │ +5 ranks possible   ││
│ │ (#12 → #1)      │ │ (#23 → #1)      │ │                     ││
│ └─────────────────┘ └─────────────────┘ └─────────────────────┘│
│                                                                 │
│ 🚀 HIGH IMPACT ACTIONS                                          │
│ ┌──────────────────────────────────────────────────────────────┐│
│ │ ✅ Add 5 relays in South America                             ││
│ │    Impact: +2.4 diversity score • Moves you #23 → #18       ││
│ │    Resources: [Brazil VPS Guide] [Argentina Hosting]         ││
│ │                                                              ││
│ │ ✅ Enable IPv6 on 12 relays currently IPv4-only              ││
│ │    Impact: +3% bandwidth measurement accuracy                ││
│ │    Difficulty: Low • [IPv6 Setup Guide]                      ││
│ └──────────────────────────────────────────────────────────────┘│
│                                                                 │
│ 📊 PROGRESS TRACKING                                            │
│ ┌──────────────────────────────────────────────────────────────┐│
│ │ Bandwidth:  ████████████████░░░░ 78% to goal                 ││
│ │ Diversity:  ██████████░░░░░░░░░░ 52% to goal                 ││
│ │ Reliability: ███████████████████░ 94% (maintaining)          ││
│ └──────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

#### Implementation Recommendations
1. **Create `improvement_guidance.py`** for gap analysis calculations
2. **Add improvement section to `contact.html`** template
3. **Build recommendation database** with difficulty/impact scores
4. **Link to external resources** (VPS guides, setup docs)

---

### #4: Directory Authority Health Dashboard (EXPANDED)
**Priority Score: 82/100** | **Timeline: 4-6 weeks** | **Status: PARTIALLY IMPLEMENTED**

---

#### Current Implementation Status

| Component | Status | Location |
|-----------|--------|----------|
| Basic authority table | ✅ Implemented | `misc-authorities.html` |
| Authority uptime stats (1M/6M/1Y/5Y) | ✅ Implemented | `relays.py` |
| Z-score outlier detection | ✅ Implemented | `relays.py` |
| Version compliance tracking | ✅ Implemented | `misc-authorities.html` |
| `fetch_consensus_health()` | ⚠️ Placeholder only | `workers.py` line 519-551 |
| Real-time voting status | ❌ Not implemented | — |
| Latency monitoring | ❌ Not implemented | — |
| Consensus formation analysis | ❌ Not implemented | — |
| Alert system | ❌ Not implemented | — |
| CollecTor API integration | ❌ Not implemented | — |

---

#### What's Missing (Detailed)

##### 1. Real-Time Authority Health Checks
```python
# Current placeholder in workers.py:
def fetch_consensus_health(progress_logger=None):
    # Placeholder implementation - returns empty data
    empty_data = {"health_status": {}, "version": "placeholder"}
    return empty_data
```

**Needed:**
- Direct HTTP checks to each authority's directory port
- Response time measurement (latency in ms)
- Timeout detection and error classification
- Status categorization: `online`, `slow`, `degraded`, `timeout`, `offline`

##### 2. Voting Round Monitoring
- Track when each authority submits its vote
- Measure voting round duration (typically 127-180 seconds)
- Detect authorities that miss voting windows
- Historical voting participation rate

##### 3. Bandwidth Scanning Status
- Track which authorities are actively measuring relay bandwidth
- Identify scanning delays or failures
- Compare measurement consistency across authorities

##### 4. Consensus Formation Analysis
- Parse consensus documents from CollecTor
- Track `valid-after`, `fresh-until`, `valid-until` timestamps
- Detect stale consensus conditions
- Calculate authority agreement percentage on relay flags

##### 5. Alert System
- Configurable thresholds for warnings and critical alerts
- Categories: connectivity, performance, consensus, voting
- Real-time alert generation and history

---

#### Detailed Mockups

##### Main Dashboard View
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
│ │ dizum        │ 🟢 OK  │ ✅   │ ✅      │ 15ms    │ 99.8%    ││
│ │ gabelmoo     │ 🟢 OK  │ ✅   │ ✅      │ 11ms    │ 99.9%    ││
│ │ dannenberg   │ 🟢 OK  │ ✅   │ ✅      │ 19ms    │ 99.7%    ││
│ │ maatuska     │ 🟢 OK  │ ✅   │ ✅      │ 7ms     │ 99.9%    ││
│ │ faravahar    │ 🟡 SLOW│ ✅   │ ⚠️      │ 89ms    │ 97.8%    ││
│ │ longclaw     │ 🟢 OK  │ ✅   │ ✅      │ 14ms    │ 99.6%    ││
│ │ bastet       │ 🟢 OK  │ ✅   │ ✅      │ 16ms    │ 99.5%    ││
│ └──────────────┴────────┴──────┴─────────┴─────────┴──────────┘│
│                                                                 │
│ ⚠️ Active Alerts (1):                                           │
│ ┌──────────────────────────────────────────────────────────────┐│
│ │ 🟡 WARNING: faravahar bandwidth scanning slower than usual   ││
│ │    Response time: 89ms (threshold: 50ms)                     ││
│ │    Since: 14:15 UTC • Impact: Low                            ││
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

##### Consensus Health Metrics View
```
┌─────────────────────────────────────────────────────────────────┐
│ 📊 Consensus Health Metrics                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Current Consensus (2025-01-06 15:00:00):                       │
│ ┌──────────────────────────────────────────────────────────────┐│
│ │ Method: 28              Valid: 15:00-16:00 UTC               ││
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
│ Quality Indicators:                                             │
│ ✅ Consensus freshness: Excellent (12 minutes until stale)     │
│ ✅ Authority participation: 100% (9/9)                         │
│ ✅ Flag consistency: 98.7% agreement across authorities        │
│ ⚠️  Network diversity: APAC region underrepresented (8.3%)     │
└─────────────────────────────────────────────────────────────────┘
```

##### Authority Performance Analytics View
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
│ │ dizum        99.4%   99.7%  96.1%    98.9%     ⭐⭐⭐⭐        ││
│ │ gabelmoo     99.7%   100%   98.9%    99.2%     ⭐⭐⭐⭐⭐      ││
│ │ dannenberg   99.2%   99.8%  94.3%    98.6%     ⭐⭐⭐⭐        ││
│ │ maatuska     99.9%   100%   99.1%    99.4%     ⭐⭐⭐⭐⭐      ││
│ │ faravahar    97.8%   98.9%  89.2%    97.1%     ⭐⭐⭐          ││
│ │ longclaw     99.5%   100%   97.4%    99.0%     ⭐⭐⭐⭐        ││
│ │ bastet       99.6%   99.9%  98.7%    99.3%     ⭐⭐⭐⭐⭐      ││
│ └──────────────────────────────────────────────────────────────┘│
│                                                                 │
│ Network Impact Analysis:                                        │
│ • Consensus Reliability: 99.4% (Excellent)                     │
│ • Authority Redundancy: 9 active (Optimal - tolerates 4 failures)│
│ • Single Point of Failure Risk: Low                            │
│ • Geographic Distribution: 6 countries, 3 continents           │
│                                                                 │
│ Performance Score Calculation:                                  │
│ • Uptime: 30% weight (core availability)                       │
│ • Voting: 25% weight (consensus participation)                 │
│ • BW Scanning: 20% weight (measurement accuracy)               │
│ • Consensus Agreement: 25% weight (flag consistency)           │
└─────────────────────────────────────────────────────────────────┘
```

---

#### Data Sources Required

| Source | Endpoint | Data Provided |
|--------|----------|---------------|
| **Onionoo API** | `/details?flag=Authority` | Authority relay details (✅ implemented) |
| **Onionoo API** | `/uptime?flag=Authority` | Historical uptime (✅ implemented) |
| **CollecTor** | `/recent/relay-descriptors/consensuses/` | Consensus documents |
| **CollecTor** | `/recent/relay-descriptors/votes/` | Authority votes |
| **Direct HTTP** | `http://{authority}:{port}/tor/status-vote/current/consensus` | Real-time latency |

---

#### Implementation Plan

##### Phase 1: Real-Time Authority Health (Week 1-2)
```python
# File: allium/lib/authority_monitor.py

class DirectoryAuthorityMonitor:
    """Monitor directory authority health in real-time."""
    
    AUTHORITIES = {
        'moria1': {'address': '128.31.0.34:9131', 'fingerprint': '9695DFC35FFEB861...'},
        'tor26': {'address': '86.59.21.38:80', 'fingerprint': '847B1F850344D787...'},
        'dizum': {'address': '45.66.33.45:80', 'fingerprint': '7EA6EAD6FD830830...'},
        'gabelmoo': {'address': '131.188.40.189:80', 'fingerprint': 'F2044413DAC2E02E...'},
        'dannenberg': {'address': '193.23.244.244:80', 'fingerprint': '585769C78764D58...'},
        'maatuska': {'address': '171.25.193.9:443', 'fingerprint': 'BD6A829255CB653...'},
        'faravahar': {'address': '154.35.175.225:80', 'fingerprint': 'CF6D0AAFB385BE7...'},
        'longclaw': {'address': '199.58.81.140:80', 'fingerprint': '74A910646BCEEFB...'},
        'bastet': {'address': '204.13.164.118:80', 'fingerprint': '24E2F139121D4394...'},
    }
    
    async def check_all_authorities(self) -> Dict:
        """Check health of all authorities in parallel."""
        tasks = [self._check_single_authority(name, info) 
                 for name, info in self.AUTHORITIES.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return self._process_results(results)
    
    async def _check_single_authority(self, name: str, info: Dict) -> Dict:
        """Check a single authority's directory port."""
        start = time.time()
        try:
            url = f"http://{info['address']}/tor/status-vote/current/consensus"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    latency_ms = (time.time() - start) * 1000
                    return {
                        'name': name,
                        'status': 'online' if response.status == 200 else 'degraded',
                        'latency_ms': round(latency_ms, 1),
                        'http_status': response.status
                    }
        except asyncio.TimeoutError:
            return {'name': name, 'status': 'timeout', 'latency_ms': None}
        except Exception as e:
            return {'name': name, 'status': 'offline', 'error': str(e)}
```

##### Phase 2: Consensus Health Integration (Week 2-3)
```python
# File: allium/lib/consensus_health_scraper.py

class ConsensusHealthScraper:
    """Scrape and analyze consensus documents from CollecTor."""
    
    COLLECTOR_URL = "https://collector.torproject.org/recent/relay-descriptors/consensuses/"
    
    async def fetch_latest_consensus(self) -> Dict:
        """Fetch and parse the most recent consensus document."""
        # 1. List available consensus files
        # 2. Download most recent
        # 3. Parse header (valid-after, fresh-until, method, etc.)
        # 4. Calculate flag distribution
        # 5. Return structured data
        
    def parse_consensus_document(self, content: str) -> Dict:
        """Parse consensus document and extract metrics."""
        return {
            'valid_after': self._extract_timestamp('valid-after', content),
            'fresh_until': self._extract_timestamp('fresh-until', content),
            'valid_until': self._extract_timestamp('valid-until', content),
            'consensus_method': self._extract_method(content),
            'relay_count': self._count_relays(content),
            'flag_distribution': self._calculate_flag_distribution(content),
            'total_bandwidth': self._sum_bandwidth(content)
        }
```

##### Phase 3: Alert System (Week 3-4)
```python
# File: allium/lib/authority_alerts.py

class AuthorityAlertSystem:
    """Generate alerts based on authority health status."""
    
    THRESHOLDS = {
        'latency_warning': 50,      # ms
        'latency_critical': 200,    # ms
        'uptime_warning': 99.0,     # %
        'uptime_critical': 95.0,    # %
        'offline_critical': 2,      # number of authorities
    }
    
    def generate_alerts(self, authority_status: List[Dict], consensus_data: Dict) -> List[Dict]:
        """Generate alerts based on current status."""
        alerts = []
        
        # Check offline authorities
        offline = [a for a in authority_status if a['status'] in ['offline', 'timeout']]
        if len(offline) >= self.THRESHOLDS['offline_critical']:
            alerts.append({
                'level': 'critical',
                'category': 'connectivity',
                'message': f"{len(offline)} authorities offline: {', '.join(a['name'] for a in offline)}",
                'since': datetime.utcnow().isoformat()
            })
        
        # Check slow authorities
        slow = [a for a in authority_status 
                if a.get('latency_ms', 0) > self.THRESHOLDS['latency_warning']]
        for auth in slow:
            alerts.append({
                'level': 'warning',
                'category': 'performance', 
                'message': f"{auth['name']} response time: {auth['latency_ms']}ms",
                'since': datetime.utcnow().isoformat()
            })
        
        return alerts
```

##### Phase 4: Template & Integration (Week 4)
- Create `misc-authorities-health.html` template with all views
- Update `workers.py` to use real implementation
- Add to navigation and coordinator

---

#### Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `allium/lib/authority_monitor.py` | **CREATE** | Real-time authority health checks |
| `allium/lib/consensus_health_scraper.py` | **CREATE** | CollecTor consensus parsing |
| `allium/lib/authority_alerts.py` | **CREATE** | Alert generation system |
| `allium/lib/authority_analytics.py` | **CREATE** | Performance scoring |
| `allium/lib/workers.py` | **MODIFY** | Implement `fetch_consensus_health()` |
| `allium/templates/misc-authorities-health.html` | **CREATE** | New dashboard template |
| `allium/templates/misc-authorities.html` | **MODIFY** | Add link to health dashboard |

---

#### Success Criteria

- [ ] Real-time latency checks for all 9 authorities (< 5s refresh)
- [ ] Consensus document parsing from CollecTor
- [ ] Voting participation tracking with historical data
- [ ] Flag distribution visualization
- [ ] Performance scorecard with 30-day metrics
- [ ] Alert system with configurable thresholds
- [ ] Geographic distribution map of authorities
- [ ] < 2 second page load time

---

#### Dependencies

- `aiohttp` - Async HTTP requests for parallel authority checks
- `asyncio` - Async/await coordination
- `statistics` - Z-score and performance calculations (already available)

---

#### Value Proposition

| Audience | Benefit |
|----------|---------|
| **Tor Foundation** | Proactive monitoring of critical infrastructure |
| **Relay Operators** | Understanding why their relay flags might be delayed |
| **Researchers** | Transparency into consensus formation process |
| **Network Watchers** | Early warning for network-wide issues |

---

### #5: Peer Group Performance Comparison
**Priority Score: 79/100** | **Timeline: 4 weeks** | **Status: NOT IMPLEMENTED**

#### What's Missing
- ❌ No peer group classification (operators with similar relay count)
- ❌ No "compare to similar operators" feature
- ❌ No peer group rankings/percentiles
- ❌ No "you vs peer average" visualizations

#### What Exists (Can Be Reused)
- ✅ CW/BW ratio calculations and percentiles
- ✅ Operator reliability metrics
- ✅ Contact-level intelligence engine data

#### Mockup
```
┌─────────────────────────────────────────────────────────────────┐
│ 📊 Peer Group Comparison - youroperator.org (47 relays)         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ 👥 Peer Group: Operators with 25-75 relays (you rank #8 of 23)  │
│                                                                 │
│ ┌──────────────────────────────────────────────────────────────┐│
│ │ Metric              │ Your Score │ Peer Avg │ Network │ Rank ││
│ ├─────────────────────┼────────────┼──────────┼─────────┼──────┤│
│ │ ⚖️ CW Efficiency    │ 0.67       │ 0.87     │ 0.75    │ ↓23% ││
│ │ 📈 Bandwidth/Relay  │ 12.4 MB/s  │ 8.1 MB/s │ 6.2 MB/s│ ↑53% ││
│ │ ⏰ Uptime (6mo)     │ 98.7%      │ 97.5%    │ 94.1%   │ Top15││
│ │ 🌍 Geographic       │ 4 countries│ 2.1 avg  │ 1.4 avg │ Top20││
│ │ 🏗️ ASN Diversity   │ 6 ASes     │ 3.2 avg  │ 2.1 avg │ Top10││
│ └──────────────────────────────────────────────────────────────┘│
│                                                                 │
│ 🏆 Peer Group Leaders (25-75 relay operators):                  │
│ • #1: topoperator.org - 0.94 CW ratio, 99.1% uptime            │
│ • #2: reliablenet.com - 0.91 CW ratio, 98.9% uptime            │
│ • [You: #8] - 0.67 CW ratio, 98.7% uptime                      │
└─────────────────────────────────────────────────────────────────┘
```

---

### #6: Bridge Network Health Dashboard
**Priority Score: 73/100** | **Timeline: 5-6 weeks** | **Status: NOT IMPLEMENTED**

#### What's Missing
- ❌ No bridge data processing (only relays)
- ❌ No bridge-specific pages
- ❌ No transport protocol analysis (obfs4, webtunnel, etc.)
- ❌ No bridge distribution channel metrics

#### What Exists (Can Be Reused)
- ✅ Relay dashboard infrastructure can be adapted
- ✅ Network health card layout
- ✅ Bandwidth/uptime calculation patterns

#### Mockup
```
┌─────────────────────────────────────────────────────────────────┐
│ 🌉 Tor Bridge Network Health Dashboard                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────┐│
│ │ 📊 Bridge Count │ │ 🚇 Transports   │ │ ⏰ Bridge Uptime    ││
│ │                 │ │                 │ │                     ││
│ │ 2,739 Total     │ │ 4 Types Active  │ │ 94.2% Average       ││
│ │ 2,456 Running   │ │ obfs4: 67.4%    │ │                     ││
│ └─────────────────┘ └─────────────────┘ └─────────────────────┘│
│                                                                 │
│ Transport Protocol Analysis:                                    │
│ ┌──────────────────────────────────────────────────────────────┐│
│ │ obfs4     ████████████████████████████████████████ 67.4%    ││
│ │ webtunnel ████████████████ 24.0%                            ││
│ │ snowflake █████ 6.9%                                        ││
│ └──────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

### #7: Smart Context Links & Suggestions
**Priority Score: 70/100** | **Timeline: 8-10 weeks** | **Status: PARTIALLY IMPLEMENTED**

#### What's Missing
- ❌ No "Smart Suggestions" panel on pages
- ❌ No contextual navigation recommendations
- ❌ No "similar networks" or "similar operators" features
- ❌ No cross-page intelligence recommendations
- ❌ No URL-based smart filtering

#### What Exists (Can Be Reused)
- ✅ Intelligence Engine with 14 layers
- ✅ Contact intelligence calculations
- ✅ Network concentration analysis
- ✅ Geographic clustering analysis

#### Mockup
```
┌─────────────────────────────────────────────────────────────────┐
│ AS12345 - Hetzner Online GmbH                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ 💡 Smart Suggestions                                            │
│ ┌──────────────────────────────────────────────────────────────┐│
│ │ • Compare with 5 similar-capacity networks [→]               ││
│ │ • View geographic impact on Germany [→]                      ││
│ │ • Analyze 12 operators in this network [→]                   ││
│ │ • See historical AS growth trends [→]                        ││
│ └──────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

### #8: Predictive Relay Failure Detection
**Priority Score: 67/100** | **Timeline: 6-8 weeks** | **Status: NOT IMPLEMENTED**

#### What's Missing
- ❌ No predictive analytics/ML models
- ❌ No "at-risk relay" detection
- ❌ No failure prediction scoring
- ❌ No early warning alerts

#### What Exists (Can Be Reused)
- ✅ Historical uptime data available
- ✅ Bandwidth stability metrics (CV)
- ✅ Offline relay detection in contact pages

#### Mockup
```
┌─────────────────────────────────────────────────────────────────┐
│ 🔮 Predictive Analytics - At-Risk Relays (Next 48h)            │
├─────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────────┐│
│ │ Relay              │ Risk  │ Factors                │ Action ││
│ ├────────────────────┼───────┼────────────────────────┼────────┤│
│ │ relay01.example    │ 73% ⚠️│ Declining uptime,      │ Contact││
│ │                    │       │ BW instability         │ operator││
│ │ relay23.network    │ 58% ⚠️│ Consensus weight drop  │ Monitor││
│ └────────────────────┴───────┴────────────────────────┴────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Roadmap Summary

| Priority | Feature | Timeline | Status | Key Milestone |
|----------|---------|----------|--------|---------------|
| **#1** | Geographic Heat Map | 4-6 weeks | Not Started | M1 |
| **#2** | AROI Achievement Wheel | 3-4 weeks | Data Ready | M1 |
| **#3** | Improvement Guidance | 4-6 weeks | Not Started | M1-2 |
| **#4** | Authority Dashboard | 4-6 weeks | Placeholder | M2 |
| **#5** | Peer Group Comparison | 4 weeks | Not Started | M2 |
| **#6** | Bridge Health Dashboard | 5-6 weeks | Not Started | M2-3 |
| **#7** | Smart Context Links | 8-10 weeks | Foundation Ready | M2-3 |
| **#8** | Predictive Analytics | 6-8 weeks | Not Started | M3 |

---

## Recommended Starting Point

### 🚀 Start with Feature #1: Geographic Heat Map

**Reasons:**
1. **Foundation Building** - Sets up D3.js/Chart.js infrastructure for #2
2. **Immediate Visual Impact** - Most dramatic improvement to user experience
3. **Zero Dependencies** - All country data already exists
4. **Reusable Components** - Chart framework used by #2, #6, #8
5. **Community Appeal** - Showcases Tor's global reach

### Week 1-2 Quick Start Plan
```bash
# 1. Set up visualization framework
npm install d3 chart.js topojson-client

# 2. Create geographic data processor
touch allium/lib/geographic_visualization.py

# 3. Create template and JavaScript
touch allium/templates/geographic_heatmap.html
touch static/js/geographic-heatmap.js

# 4. Add CSS framework
touch static/css/visualization.css
```

### Success Criteria for Feature #1
- [ ] Interactive world map with color-coded countries
- [ ] Hover tooltips showing relay counts and top operators
- [ ] Click-through to country detail pages
- [ ] Mobile-responsive with touch zoom/pan
- [ ] < 2 second load time

---

**Document Status**: Updated after codebase review  
**Last Updated**: December 2024  
**Features Removed**: 2 (AROI Leaderboards - fully implemented, Network Health Dashboard - fully implemented)  
**Features Remaining**: 8 (requiring new development)
