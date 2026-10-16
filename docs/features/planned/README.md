# Planned Features

This directory contains **proposals and enhancement plans** for features that are **not yet implemented** in Allium.

> Looking for behavior that is already shipped? See `docs/features/implemented/`.

Status of the eight-item shortlist (heat map, achievement wheel, improvement guidance, authority dashboard, peer cohorts, bridges, smart suggestions, failure prediction) is in [TOP_10_PRIORITIZED_FEATURES.md](./TOP_10_PRIORITIZED_FEATURES.md). That file matches the current generator. The milestone text below is the original proposal.

## 🚀 Status

These features represent the **roadmap** for future development. They are:
- ❌ **Mostly not implemented** in code. Shipped and partial items on the eight-item shortlist are called out in [TOP_10_PRIORITIZED_FEATURES.md](./TOP_10_PRIORITIZED_FEATURES.md)
- 📋 **Proposed** with varying levels of design detail
- 🎯 **Prioritized** by milestone and timeline
- 💡 **Open for community input** and contributions

---

## 📅 Implementation Roadmap

### Milestone 1: Interactive Visualizations (Q1 2025)
**File**: [milestone-1-graphs-charts.md](milestone-1-graphs-charts.md)  
**Timeline**: 12 weeks  
**Priority**: Critical Foundation

**Features**:
- Geographic heat map dashboard — still open as an Allium page ([TOP_10_PRIORITIZED_FEATURES.md](./TOP_10_PRIORITIZED_FEATURES.md)). Country and relay pages already link to RouteFluxMap; optional exports are [routefluxmap-enhancements.md](routefluxmap-enhancements.md). The milestone-1 D3 sketch assumes a browser library this repo does not use.
- Platform diversity visualization
- AROI achievement wheel
- Network authority donut charts
- Mobile-first responsive design

**Dependencies**: D3.js/Chart.js integration

### Milestone 2: Advanced Authority Monitoring (Q2 2025)
**File**: [milestone-2-authority-health.md](milestone-2-authority-health.md)  
**Timeline**: 12 weeks  
**Builds on**: Basic authority monitoring (implemented)

**Features**:
- Real-time authority status dashboard
- Consensus health scraping integration
- Authority performance analytics
- Authority geolocation tracking
- Consensus formation timeline

**Dependencies**: Real-time data pipeline

### Milestone 3: Intelligent Network Health (Q3 2025)
**File**: [milestone-3-network-health.md](milestone-3-network-health.md)  
**Timeline**: 12 weeks  
**Builds on**: Basic health dashboard (implemented)

**Features**:
- Real-time health monitoring (sub-5 second refresh)
- Predictive relay failure detection (>85% accuracy)
- Automated downtime alerts
- Network capacity forecasting

**Dependencies**: ML/AI infrastructure

### Milestone 4: AI/ML Analytics (Q4 2025)
**File**: [milestone-4-ai-analytics.md](milestone-4-ai-analytics.md)  
**Timeline**: 16 weeks  
**Priority**: Advanced Intelligence

**Features**:
- AI-powered anomaly detection
- Network optimization recommendations
- Predictive network modeling (3-month forecasts)
- Behavioral pattern analysis
- Network resilience modeling

**Dependencies**: ML pipeline, training data

### Milestone 5: Community Platform (Q1 2026)
**File**: [milestone-5-community-tools.md](milestone-5-community-tools.md)  
**Timeline**: 12 weeks  
**Priority**: Community Engagement

**Features**:
- Advanced operator dashboard
- Community API & developer tools (1000+ req/hour)
- Collaborative network planning
- Mobile apps (iOS/Android)
- Multi-language support

**Dependencies**: API infrastructure, mobile frameworks

---

## 📊 Individual Proposals

### Enhanced Analytics
- [onionoo_historical_bandwidth_metrics_proposal.md](onionoo_historical_bandwidth_metrics_proposal.md) - 10 new bandwidth-focused metrics
- [operator_comparison_metrics_proposal_top10.md](operator_comparison_metrics_proposal_top10.md) - 10 comparative metrics for operator benchmarking
- [comprehensive-1aeo-bandwidth-analysis.md](comprehensive-1aeo-bandwidth-analysis.md) - Deep bandwidth analysis
- [consensus-weight-metrics-proposal.md](consensus-weight-metrics-proposal.md) - Enhanced consensus weight tracking

### Advanced Features
- [routefluxmap-enhancements.md](routefluxmap-enhancements.md) - Optional RouteFluxMap data exports (country rarity, validated operators, AS links). Separate from the open Allium world map in [TOP_10_PRIORITIZED_FEATURES.md](./TOP_10_PRIORITIZED_FEATURES.md).
- [visualization-dashboard-proposal.md](visualization-dashboard-proposal.md) - Interactive visualization system
- [actionable-improvement-guidance.md](actionable-improvement-guidance.md) - Operator recommendations
- [multi-api-implementation-plan.md](multi-api-implementation-plan.md) - Additional API integrations

### Specialized Systems
- [bridges/](bridges/) - Bridge network health dashboard
- [clickhouse/](clickhouse/) - High-performance analytics backend
- [smart_context_links/](smart_context_links/) - Enhanced context linking system
- [uptime/](uptime/) - Advanced uptime analytics

### Roadmap Documents
- [allium-roadmap-2025.md](allium-roadmap-2025.md) - Complete 2025 roadmap
- [roadmap-index.md](roadmap-index.md) - Roadmap overview

### Other Proposals
- [directory-authorities/](directory-authorities/) - Advanced authority monitoring
- [onionoo_uptime_analysis.md](onionoo_uptime_analysis.md) - Enhanced uptime features
- [RELIABILITY_SYSTEM_UPDATES.md](RELIABILITY_SYSTEM_UPDATES.md) - Future reliability enhancements

---

## 🎯 Implementation Priorities

### High Priority (Next 6 Months)
1. Geographic heat map and AROI achievement wheel (Milestone 1). Build-time history charts are already documented in `../implemented/history-charts.md`.
2. Additional historical bandwidth metrics in [onionoo_historical_bandwidth_metrics_proposal.md](onionoo_historical_bandwidth_metrics_proposal.md). Relay and contact pages already plot Onionoo bandwidth history.
3. Operator comparison by similar relay count. Network percentiles and role/family chart medians already exist. See [TOP_10_PRIORITIZED_FEATURES.md](./TOP_10_PRIORITIZED_FEATURES.md).

### Medium Priority (6-12 Months)
4. Remaining directory-authority ideas (Milestone 2). `misc/authorities.html` and `allium/lib/consensus/` already cover votes, TCP latency, bandwidth-scanner status, and flag thresholds.
5. Predictive relay failure detection (Milestone 3). The network health dashboard itself is generated.
6. Suggestions panel on top of existing `smart_context` lines.

### Long-Term (12+ Months)
7. 🤖 AI/ML analytics (Milestone 4)
8. 👥 Community platform (Milestone 5)
9. 🌉 Bridge network monitoring
10. 💾 ClickHouse integration

---

## 💡 Contributing

### Implementing a Planned Feature

1. **Choose a feature** from this directory
2. **Review the proposal** thoroughly
3. **Check dependencies** - ensure prerequisites are met
4. **Open an issue** on GitHub announcing intent
5. **Implement** following development guidelines
6. **Test** comprehensively
7. **Document** in user guides
8. **Move** to `implemented/` directory after verification

### Proposing a New Feature

1. **Check existing proposals** to avoid duplication
2. **Use proposal template** (see existing files for format)
3. **Include**: Problem, solution, technical approach, dependencies, timeline
4. **Submit PR** with proposal document
5. **Discuss** with community
6. **Refine** based on feedback

---

## 📚 Proposal Format

Each proposal should include:

### Header
- **Status**: ❌ Not implemented
- **Timeline**: Estimated implementation time
- **Priority**: High/Medium/Low
- **Dependencies**: What must exist first

### Content
- **Problem Statement**: What needs solving
- **Proposed Solution**: How to solve it
- **Technical Approach**: Implementation details
- **Performance Targets**: Expected metrics
- **User Benefits**: Value proposition
- **Implementation Plan**: Step-by-step approach

---

## 🔗 Related Documentation

- **[Implemented Features](../implemented/)** - Behavior docs that match the code
- **[Shortlist status](./TOP_10_PRIORITIZED_FEATURES.md)** - Shipped, partial, and open items from the eight-item list
- **[Current capabilities](../../reference/current-capabilities.md)** - Generator output and AROI categories
- **[Architecture overview](../../architecture/overview.md)** - System design
- **[Testing](../../development/testing.md)** - How to run tests

---

## 📊 Statistics

| Metric | Count |
|--------|-------|
| **Total Proposals** | 20+ documents |
| **Milestones** | 5 major milestones |
| **Timeline** | Q1 2025 - Q1 2026 |
| **Estimated Features** | 100+ individual features |

---

## ⚠️ Important Notes

- **Not a guarantee of absence**: Many proposals here are not in the generator. Shipped and partial items on the eight-item shortlist are recorded in [TOP_10_PRIORITIZED_FEATURES.md](./TOP_10_PRIORITIZED_FEATURES.md). Implemented behavior docs live in `docs/features/implemented/`.
- **Subject to Change**: Proposals may be modified based on feedback
- **No Timeline Guarantee**: Timelines are estimates, not commitments
- **Community Driven**: All proposals welcome community input

---

**Status**: Proposal catalog. Confirm shortlist items in [TOP_10_PRIORITIZED_FEATURES.md](./TOP_10_PRIORITIZED_FEATURES.md) before treating them as unimplemented.
