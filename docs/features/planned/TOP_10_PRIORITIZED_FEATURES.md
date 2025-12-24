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

### #4: Directory Authority Health Dashboard
**Priority Score: 82/100** | **Timeline: 4-6 weeks** | **Status: NOT IMPLEMENTED**

#### What's Missing
- ❌ `fetch_consensus_health()` in `workers.py` is a placeholder
- ❌ No real-time authority status monitoring
- ❌ No voting round tracking
- ❌ No consensus formation analysis
- ❌ No latency/responsiveness monitoring
- ❌ No alert system for authority issues

#### What Exists (Can Be Reused)
- ✅ Basic authority list in `misc-authorities.html`
- ✅ Authority flag detection in relay data
- ✅ Infrastructure for multi-API data fetching

#### Mockup
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
│ └───────────────────┘ └───────────────────┘ └─────────────────┘│
│                                                                 │
│ Directory Authorities Status:                                   │
│ ┌──────────────────────────────────────────────────────────────┐│
│ │ Authority    │ Status │ Vote │ BW Scan │ Latency │ Uptime   ││
│ ├──────────────┼────────┼──────┼─────────┼─────────┼──────────┤│
│ │ moria1       │ 🟢 OK  │ ✅   │ ✅      │ 12ms    │ 99.9%    ││
│ │ tor26        │ 🟢 OK  │ ✅   │ ✅      │ 8ms     │ 99.9%    ││
│ │ faravahar    │ 🟡 SLOW│ ✅   │ ⚠️      │ 89ms    │ 97.8%    ││
│ └──────────────┴────────┴──────┴─────────┴─────────┴──────────┘│
│                                                                 │
│ ⚠️ Active Alerts:                                               │
│ • faravahar bandwidth scanning slower than usual (89ms)        │
│                                                                 │
│ Last updated: 14:45:23 UTC • Auto-refresh: 60s                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Implementation Recommendations
1. **Implement `fetch_consensus_health()`** in `workers.py`
2. **Add CollecTor API integration** for consensus data
3. **Create `directory_authority_monitor.py`** for status tracking
4. **Add `misc-authorities-health.html`** template

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
