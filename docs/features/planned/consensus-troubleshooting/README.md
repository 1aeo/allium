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

## 🎯 Proposed Features by Priority

### Phase 1: Per-Relay Vote Lookup (Critical Priority)

**Problem Solved**: "Why is my relay not in consensus?" / "Which authorities see my relay?"

**Implementation**:
Add a **"Directory Authority Votes"** section to each relay detail page (`relay-info.html`) showing:

```
┌─────────────────────────────────────────────────────────────────────┐
│ 🗳️ Directory Authority Votes for YourRelayNickname                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ ✅ In Consensus: Yes (8/9 authorities voted for this relay)        │
│                                                                     │
│ Authority    │ Voted │ Flags Assigned          │ Bandwidth  │ Issue │
│ ────────────────────────────────────────────────────────────────── │
│ moria1       │  ✅   │ Fast Guard Stable Valid │ 45000      │       │
│ tor26        │  ✅   │ Fast Guard Stable Valid │ 44800      │       │
│ dizum        │  ✅   │ Fast Stable Valid       │ 43200      │ No Guard │
│ gabelmoo     │  ✅   │ Fast Guard Stable Valid │ 45100      │       │
│ dannenberg   │  ✅   │ Fast Guard Stable Valid │ 44950      │       │
│ maatuska     │  ✅   │ Fast Guard Stable Valid │ 45000      │       │
│ longclaw     │  ✅   │ Fast Stable Valid       │ 43800      │ No Guard │
│ bastet       │  ✅   │ Fast Guard Stable Valid │ 44700      │       │
│ faravahar    │  ❌   │ Not in vote             │ N/A        │ ⚠️ Missing │
│                                                                     │
│ ⚠️ Alerts:                                                          │
│ • faravahar did not include this relay in vote - check reachability │
│ • dizum, longclaw: Not assigning Guard flag                        │
│                                                                     │
│ 📖 Troubleshooting Guide:                                           │
│ • If missing from 1-2 authorities: May be reachability issue       │
│ • If missing flags: Check thresholds below                          │
│ • If missing from all: Check relay is running and ports are open   │
└─────────────────────────────────────────────────────────────────────┘
```

**Data Source**: Parse individual authority votes from:
- `http://[authority-ip]/tor/status-vote/current/authority`
- Cache votes and refresh every consensus period (1 hour)

**Technical Implementation**:
```python
# lib/vote_parser.py
class VoteParser:
    """Parse and compare directory authority votes for relay troubleshooting."""
    
    AUTHORITIES = {
        'moria1': 'http://128.31.0.39:9231/tor/status-vote/current/authority',
        'tor26': 'http://217.196.147.77:80/tor/status-vote/current/authority',
        'dizum': 'http://45.66.35.11:80/tor/status-vote/current/authority',
        'gabelmoo': 'http://131.188.40.189:80/tor/status-vote/current/authority',
        'dannenberg': 'http://193.23.244.244:80/tor/status-vote/current/authority',
        'maatuska': 'http://171.25.193.9:443/tor/status-vote/current/authority',
        'longclaw': 'http://199.58.81.140:80/tor/status-vote/current/authority',
        'bastet': 'http://204.13.164.118:80/tor/status-vote/current/authority',
        'faravahar': 'http://216.218.219.41:80/tor/status-vote/current/authority',
    }
    
    def get_relay_vote_status(self, fingerprint: str) -> dict:
        """Get voting status from all authorities for a specific relay."""
        vote_status = {}
        for auth_name, vote_url in self.AUTHORITIES.items():
            vote_status[auth_name] = self._check_relay_in_vote(fingerprint, vote_url)
        return vote_status
```

---

### Phase 2: Flag Threshold Comparison (High Priority)

**Problem Solved**: "Why doesn't my relay have the Guard flag?" / "Why did I lose Stable?"

**Implementation**:
Add **"Flag Eligibility Analysis"** section showing current thresholds vs relay stats:

```
┌─────────────────────────────────────────────────────────────────────┐
│ 🎯 Flag Eligibility Analysis for YourRelayNickname                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ Current Flags: Fast, Stable, Valid, V2Dir, HSDir                   │
│ Missing Flags: Guard (analysis below)                               │
│                                                                     │
│ Guard Flag Requirements (from consensus-health):                    │
│ ┌──────────────────────────────────────────────────────────────┐   │
│ │ Metric           │ Your Value │ Threshold │ Status           │   │
│ ├──────────────────┼────────────┼───────────┼──────────────────┤   │
│ │ WFU (Uptime)     │ 96.2%      │ ≥98%      │ ❌ Below (1.8%)  │   │
│ │ Time Known       │ 45 days    │ ≥8 days   │ ✅ Above         │   │
│ │ Bandwidth        │ 25 MB/s    │ ≥29 MB/s  │ ❌ Below (14%)   │   │
│ └──────────────────┴────────────┴───────────┴──────────────────┘   │
│                                                                     │
│ 💡 Recommendation: To gain Guard flag, increase:                    │
│    • Uptime to ≥98% (currently 96.2%)                              │
│    • Bandwidth to ≥29 MB/s (currently 25 MB/s)                     │
│                                                                     │
│ Stable Flag Requirements:                                           │
│ ┌──────────────────────────────────────────────────────────────┐   │
│ │ Metric           │ Your Value │ Threshold │ Status           │   │
│ ├──────────────────┼────────────┼───────────┼──────────────────┤   │
│ │ Uptime           │ 45 days    │ ≥20 days  │ ✅ Above         │   │
│ │ MTBF             │ 89 days    │ ≥45 days  │ ✅ Above         │   │
│ └──────────────────┴────────────┴───────────┴──────────────────┘   │
│                                                                     │
│ Fast Flag Requirements:                                             │
│ ┌──────────────────────────────────────────────────────────────┐   │
│ │ Metric           │ Your Value │ Threshold │ Status           │   │
│ ├──────────────────┼────────────┼───────────┼──────────────────┤   │
│ │ Bandwidth        │ 25 MB/s    │ ≥102 KB/s │ ✅ Above         │   │
│ └──────────────────┴────────────┴───────────┴──────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

**Data Source**: Parse flag thresholds from consensus-health.torproject.org:
```
flag-thresholds stable-uptime=1749590 stable-mtbf=31256159 fast-speed=1048000 
guard-wfu=0.98 guard-tk=691200 guard-bw-inc-exits=29000000 guard-bw-exc-exits=28000000
```

---

### Phase 3: Authority Reachability Diagnostic (High Priority)

**Problem Solved**: "Can the directory authorities reach my relay?"

**Implementation**:
Add **"Authority Reachability Check"** to relay page:

```
┌─────────────────────────────────────────────────────────────────────┐
│ 🌐 Authority Reachability for YourRelayNickname                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ IPv4 ORPort (1.2.3.4:9001):                                        │
│   moria1:    ✅ Reachable (included in vote)                       │
│   tor26:     ✅ Reachable (included in vote)                       │
│   ...                                                               │
│                                                                     │
│ IPv6 ORPort ([2001:db8::1]:9001):                                  │
│   moria1:    ✅ ReachableIPv6 flag assigned                        │
│   tor26:     ❌ NoIPv6Consensus - not reachable via IPv6           │
│   dizum:     N/A - Does not test IPv6                              │
│   ...                                                               │
│                                                                     │
│ ⚠️ IPv6 Issues Detected:                                            │
│ • tor26 cannot reach your IPv6 address                             │
│ • Recommendation: Check IPv6 connectivity to 217.196.147.77        │
│                                                                     │
│ 📋 Self-Check Commands:                                             │
│ ping6 -c2 2001:858:2:2:aabb:0:563b:1526 && \                       │
│ ping6 -c2 2620:13:4000:6000::1000:118 && \                         │
│ ping6 -c2 2001:67c:289c::9 && echo "IPv6 OK"                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

### Phase 4: Consensus Weight Analysis (Medium Priority)

**Problem Solved**: "Why is my consensus weight so low?" / "Why did my consensus weight drop?"

**Implementation**:
Add **"Consensus Weight Analysis"** showing:

```
┌─────────────────────────────────────────────────────────────────────┐
│ 📊 Consensus Weight Analysis for YourRelayNickname                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ Current Weight: 45,000 (0.23% of network)                          │
│ Measured: ✅ Yes (by 5/6 bandwidth authorities)                    │
│                                                                     │
│ Bandwidth Authority Measurements:                                   │
│ ┌──────────────────────────────────────────────────────────────┐   │
│ │ Authority    │ Measured │ Value    │ Deviation             │   │
│ ├──────────────┼──────────┼──────────┼───────────────────────┤   │
│ │ moria1       │ ✅       │ 46,200   │ +2.7%                 │   │
│ │ gabelmoo     │ ✅       │ 44,100   │ -2.0%                 │   │
│ │ maatuska     │ ✅       │ 45,800   │ +1.8%                 │   │
│ │ longclaw     │ ✅       │ 44,500   │ -1.1%                 │   │
│ │ bastet       │ ✅       │ 44,900   │ -0.2%                 │   │
│ │ faravahar    │ ✅       │ 45,500   │ +1.1%                 │   │
│ │ dizum        │ ❌       │ N/A      │ Not a bw authority    │   │
│ │ dannenberg   │ ❌       │ N/A      │ Not a bw authority    │   │
│ └──────────────┴──────────┴──────────┴───────────────────────┘   │
│                                                                     │
│ Weight Efficiency:                                                  │
│ • Observed BW: 50 MB/s                                             │
│ • Consensus Weight: 45,000                                         │
│ • Efficiency: 90% (network median: 85%)                            │
│                                                                     │
│ ℹ️ If Unmeasured:                                                   │
│ • Relay needs to be measured by ≥3 bandwidth authorities           │
│ • New relays may take 1-2 weeks to be fully measured               │
│ • Check bandwidth authority reachability                           │
└─────────────────────────────────────────────────────────────────────┘
```

**Data Source**: Parse bandwidth files from:
- `http://[authority-ip]/tor/status-vote/next/bandwidth`

---

### Phase 5: Consensus Troubleshooting Wizard (Medium Priority)

**Problem Solved**: Guided troubleshooting for common consensus issues

**Implementation**:
Create a new page `misc/consensus-troubleshooter.html`:

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

### Phase 6: Enhanced Directory Authorities Page (Medium Priority)

**Problem Solved**: Centralized view of authority health and voting patterns

**Enhancements to existing `misc-authorities.html`**:

```
┌─────────────────────────────────────────────────────────────────────┐
│ 🏛️ Directory Authorities - Enhanced View                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ Consensus Status: ✅ Current (Valid 04:00-05:00 UTC)               │
│ Next Consensus: 05:00 UTC (in 23 minutes)                          │
│                                                                     │
│ Authority Voting Summary:                                           │
│ ┌────────────────┬────────┬────────┬────────┬────────┬──────────┐ │
│ │ Authority      │ Online │ Voted  │ BW Auth│ Relays │ Last Vote│ │
│ ├────────────────┼────────┼────────┼────────┼────────┼──────────┤ │
│ │ moria1         │ ✅     │ ✅     │ ✅     │ 10,064 │ 14:32    │ │
│ │ tor26          │ ✅     │ ✅     │ ✅     │ 9,903  │ 14:31    │ │
│ │ dizum          │ ✅     │ ✅     │ ❌     │ 10,671 │ 14:33    │ │
│ │ gabelmoo       │ ✅     │ ✅     │ ✅     │ 9,845  │ 14:32    │ │
│ │ dannenberg     │ ✅     │ ✅     │ ❌     │ 9,756  │ 14:31    │ │
│ │ maatuska       │ ✅     │ ✅     │ ✅     │ 9,912  │ 14:32    │ │
│ │ longclaw       │ ✅     │ ✅     │ ✅     │ 9,889  │ 14:33    │ │
│ │ bastet         │ ✅     │ ✅     │ ✅     │ 9,901  │ 14:32    │ │
│ │ faravahar      │ ✅     │ ✅     │ ✅     │ 9,878  │ 14:31    │ │
│ └────────────────┴────────┴────────┴────────┴────────┴──────────┘ │
│                                                                     │
│ Flag Thresholds (Current Consensus):                                │
│ ┌──────────────────────────────────────────────────────────────┐   │
│ │ Flag    │ Requirement                       │ Current Value  │   │
│ ├─────────┼───────────────────────────────────┼────────────────┤   │
│ │ Stable  │ Uptime ≥ median                   │ ≥20.2 days     │   │
│ │ Stable  │ MTBF ≥ median                     │ ≥36.2 days     │   │
│ │ Fast    │ Bandwidth ≥ 7/8 * median          │ ≥102 KB/s      │   │
│ │ Guard   │ WFU ≥ 98%                         │ ≥98%           │   │
│ │ Guard   │ Time Known ≥ 8 days               │ ≥8 days        │   │
│ │ Guard   │ Bandwidth (with exits) ≥          │ ≥29 MB/s       │   │
│ │ Guard   │ Bandwidth (without exits) ≥       │ ≥28 MB/s       │   │
│ │ HSDir   │ WFU ≥ 98%                         │ ≥98%           │   │
│ │ HSDir   │ Time Known ≥ median               │ ≥9.9 days      │   │
│ └─────────┴───────────────────────────────────┴────────────────┘   │
│                                                                     │
│ Quick Links to Authority Data:                                      │
│ • [Consensus] [Votes] [Descriptors] [Bandwidth Files]              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Technical Implementation Plan

### Data Sources Integration

| Data Source | URL Pattern | Data Provided | Refresh Rate |
|-------------|-------------|---------------|--------------|
| Authority Votes | `http://[auth-ip]/tor/status-vote/current/authority` | Per-relay flags, measured values | 1 hour |
| Bandwidth Files | `http://[auth-ip]/tor/status-vote/next/bandwidth` | Bandwidth measurements | 1 hour |
| Consensus | `http://[auth-ip]/tor/status-vote/current/consensus` | Final consensus data | 1 hour |
| Consensus Health | `https://consensus-health.torproject.org/` | Aggregated metrics, thresholds | 15 min |

### New Files Required

```
allium/
├── lib/
│   ├── vote_parser.py          # Parse authority votes
│   ├── threshold_analyzer.py   # Analyze flag thresholds
│   ├── bandwidth_analyzer.py   # Analyze bandwidth measurements
│   └── consensus_fetcher.py    # Fetch consensus data from authorities
├── templates/
│   ├── relay-info.html         # MODIFY: Add vote section
│   ├── misc-authorities.html   # MODIFY: Add enhanced sections
│   └── misc-troubleshooter.html # NEW: Troubleshooting wizard
└── data/
    └── cache/
        ├── votes/              # Cached authority votes
        ├── bandwidth/          # Cached bandwidth files
        └── thresholds.json     # Cached flag thresholds
```

### Integration with Multi-API Architecture

This implementation aligns with the existing multi-API plan (`docs/features/planned/multi-api-implementation-plan.md`):

```python
# lib/workers.py - Add new worker functions

def fetch_authority_votes():
    """Fetch votes from all directory authorities."""
    try:
        votes = {}
        for auth_name, auth_url in AUTHORITY_VOTE_URLS.items():
            votes[auth_name] = _fetch_and_parse_vote(auth_url)
        _save_cache('authority_votes', votes)
        _mark_ready('authority_votes')
        return votes
    except Exception as e:
        _mark_stale('authority_votes', str(e))
        return _load_cache('authority_votes')

def fetch_bandwidth_files():
    """Fetch bandwidth files from bandwidth authorities."""
    try:
        bw_data = {}
        for auth_name in BANDWIDTH_AUTHORITIES:
            bw_data[auth_name] = _fetch_and_parse_bandwidth(auth_name)
        _save_cache('bandwidth_files', bw_data)
        _mark_ready('bandwidth_files')
        return bw_data
    except Exception as e:
        _mark_stale('bandwidth_files', str(e))
        return _load_cache('bandwidth_files')

def fetch_flag_thresholds():
    """Fetch current flag thresholds from consensus-health."""
    try:
        thresholds = _scrape_consensus_health_thresholds()
        _save_cache('flag_thresholds', thresholds)
        _mark_ready('flag_thresholds')
        return thresholds
    except Exception as e:
        _mark_stale('flag_thresholds', str(e))
        return _load_cache('flag_thresholds')
```

---

## 📅 Implementation Timeline

### Phase 1: Foundation (Weeks 1-2)
- [ ] Create `vote_parser.py` to parse authority votes
- [ ] Create `threshold_analyzer.py` for flag threshold analysis
- [ ] Implement vote caching system
- [ ] Add basic relay vote lookup API

### Phase 2: Relay Page Enhancement (Weeks 3-4)
- [ ] Modify `relay-info.html` to add vote section
- [ ] Add flag eligibility analysis section
- [ ] Implement visual indicators for vote status
- [ ] Add troubleshooting tips contextually

### Phase 3: Authority Page Enhancement (Weeks 5-6)
- [ ] Enhance `misc-authorities.html` with threshold display
- [ ] Add real-time vote/consensus links
- [ ] Show relay counts per authority
- [ ] Display bandwidth authority status

### Phase 4: Troubleshooting Wizard (Weeks 7-8)
- [ ] Create `misc-troubleshooter.html` template
- [ ] Implement guided troubleshooting flow
- [ ] Add fingerprint lookup functionality
- [ ] Create issue-specific diagnostic pages

### Phase 5: Testing & Documentation (Weeks 9-10)
- [ ] Comprehensive testing with real relay data
- [ ] Create user documentation
- [ ] Performance optimization
- [ ] Community feedback integration

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

**Document Status**: Research complete, ready for implementation review  
**Next Steps**: Technical review and Phase 1 implementation kickoff
