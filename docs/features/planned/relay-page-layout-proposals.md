# Relay Page Layout Redesign Proposals

## Executive Summary

This document proposes 5 alternative layout designs for individual relay pages that better organize information, improve hierarchy, and enhance the user experience for:
1. **New relay operators** trying to understand their relay's status
2. **Operators troubleshooting** common issues (not in consensus, low bandwidth, missing flags, etc.)

Based on analysis of the [tor-relays mailing list](https://lists.torproject.org/pipermail/tor-relays/), the most common troubleshooting topics include:
- Relay not appearing in consensus
- Missing or lost flags (Guard, Exit, Stable, Fast)
- Low consensus weight / bandwidth measurement issues
- IPv6 reachability problems
- Family configuration errors (alleged vs effective)
- DDoS attacks and mitigation
- ISP/provider blocklisting
- Version and update issues

---

## Current State Analysis

### Current Template Structure
The existing `relay-info.html` template uses:
- Two-column Bootstrap grid layout
- Flat definition lists (`<dl>/<dt>/<dd>`)
- Limited section grouping
- Emoji icons scattered throughout (to be removed)
- Consensus Evaluation section at the bottom (detailed but overwhelming)

### Current Information Organization
| Left Column | Right Column |
|-------------|--------------|
| Nickname, Fingerprint | Bandwidth Capacity |
| AROI, Contact | Network Participation |
| Exit Policies (IPv4, IPv6, Full) | OR/Exit/Dir Addresses |
| Family (Effective, Alleged, Indirect) | Location (City, Region, Country) |
| | Latitude/Longitude, Map Link |
| | AS Number/Name |
| | Flags |
| | Uptime metrics |
| | Seen dates |
| | Platform/Version |

### Pain Points Identified
1. **No clear troubleshooting path** - Users must hunt for relevant data
2. **Information overload** - Too much shown at once without prioritization
3. **Poor section grouping** - Related items scattered across columns
4. **Consensus Evaluation buried** - Most diagnostic data is at the bottom
5. **No "at-a-glance" status** - Must read details to understand relay health
6. **Emoji clutter** - Inconsistent visual language

---

## Design Principles (All Proposals)

1. **Remove all emoji icons** - Use text labels or subtle visual indicators instead
2. **Add anchor links** to every major section for deep linking
3. **Prioritize troubleshooting** - Put health/status info prominently
4. **Progressive disclosure** - Quick summary first, details on demand
5. **Semantic grouping** - Related information together
6. **Mobile-friendly** - Responsive design considerations

---

## Proposal 1: "Troubleshooting-First" Dashboard Layout

### Concept
Lead with relay health status and common issues at the top, then organize detailed sections below in order of troubleshooting frequency.

### Layout Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│ RELAY HEADER                                                            │
│ Nickname: MyRelay | Fingerprint: ABCD1234...                           │
│ Quick Links: [Family] [Contact] [AS Network] [Country]                  │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ HEALTH STATUS PANEL (Collapsible, expanded by default)         #status │
├─────────────────────────────────────────────────────────────────────────┤
│ ● In Consensus: YES (9/9 authorities)                                   │
│ ● Running: 47 days | Last Restart: 2024-11-12                          │
│ ● Bandwidth Measured: YES (by 6 bandwidth authorities)                  │
│ ● Flags: Guard, Stable, Fast, Valid, Running, V2Dir, HSDir             │
│ ● Issues Detected: None                                                 │
│   OR: [Warning] IPv6 reachability partial (3/5 authorities)            │
└─────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────┐  ┌────────────────────────────────────┐
│ NETWORK ROLE          #network │  │ BANDWIDTH              #bandwidth  │
├────────────────────────────────┤  ├────────────────────────────────────┤
│ Consensus Weight: 0.15%        │  │ Observed: 125 Mbit/s               │
│ Guard Probability: 0.12%       │  │ Advertised: 100 Mbit/s             │
│ Middle Probability: 0.18%      │  │ Rate Limit: 150 Mbit/s             │
│ Exit Probability: 0.00%        │  │ Burst Limit: 200 Mbit/s            │
│ Position: Guard-focused        │  │ Measured by Authorities: 98 Mbit/s │
└────────────────────────────────┘  └────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ CONSENSUS EVALUATION (For troubleshooting)         #consensus-evaluation│
├─────────────────────────────────────────────────────────────────────────┤
│ [Summary table showing your relay vs thresholds]                        │
│ [Per-authority voting details - collapsed by default]                   │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ FLAGS & ELIGIBILITY                                       #flags        │
├─────────────────────────────────────────────────────────────────────────┤
│ Current Flags: Guard, Stable, Fast, Valid, Running, V2Dir, HSDir       │
│                                                                         │
│ Flag Requirements Summary:                                              │
│ ┌─────────┬────────────┬────────────┬────────────┐                     │
│ │ Flag    │ Your Value │ Threshold  │ Status     │                     │
│ ├─────────┼────────────┼────────────┼────────────┤                     │
│ │ Guard   │ WFU 99.2%  │ ≥98%       │ Meets      │                     │
│ │         │ TK 45 days │ ≥8 days    │ Meets      │                     │
│ │         │ BW 125Mb/s │ ≥2 MB/s    │ Meets      │                     │
│ │ Stable  │ MTBF 30d   │ ≥7 days    │ Meets      │                     │
│ │ Fast    │ 125 Mbit/s │ ≥100 KB/s  │ Meets      │                     │
│ │ HSDir   │ WFU 99.2%  │ ≥98%       │ Meets      │                     │
│ └─────────┴────────────┴────────────┴────────────┘                     │
└─────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────┐  ┌────────────────────────────────────┐
│ CONNECTIVITY          #network │  │ LOCATION               #location   │
├────────────────────────────────┤  ├────────────────────────────────────┤
│ OR Addresses:                  │  │ Country: Germany (DE)              │
│   • 192.0.2.1:9001            │  │ Region: Bavaria                    │
│   • [2001:db8::1]:9001        │  │ City: Munich                       │
│ Exit Address: none             │  │ Coordinates: 48.13, 11.58         │
│ Dir Address: 192.0.2.1:9030   │  │ AS: AS24940 (Hetzner Online GmbH) │
│                                │  │ View on Interactive Map            │
│ IPv4 Reachable: 9/9 auths     │  │                                    │
│ IPv6 Reachable: 3/5 testers   │  │                                    │
└────────────────────────────────┘  └────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ FAMILY CONFIGURATION                                       #family      │
├─────────────────────────────────────────────────────────────────────────┤
│ Effective Family: 5 relays [View Family Page]                          │
│ Alleged Family: 2 relays (they don't list you back)                    │
│ Indirect Family: 0 relays                                              │
│                                                                         │
│ [Expandable list of fingerprints]                                      │
└─────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────┐  ┌────────────────────────────────────┐
│ UPTIME HISTORY        #uptime  │  │ SOFTWARE              #software    │
├────────────────────────────────┤  ├────────────────────────────────────┤
│ Current: UP for 47 days        │  │ Platform: Linux (tor 0.4.8.12)    │
│ Flag Uptime (1M/6M/1Y/5Y):     │  │ Version Status: Recommended       │
│   99.2% / 98.5% / 97.1% / N/A  │  │ Hibernating: No                   │
│ Overall Uptime:                │  │                                    │
│   99.1% / 98.2% / 96.8% / N/A  │  │ Last Changed Address: 2024-01-15  │
│                                │  │                                    │
│ First Seen: 2023-06-01         │  │                                    │
│ Last Seen: 2024-12-29 (now)    │  │                                    │
└────────────────────────────────┘  └────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ EXIT POLICY                                               #exit-policy  │
├─────────────────────────────────────────────────────────────────────────┤
│ IPv4 Summary: reject *:*                                               │
│ IPv6 Summary: reject *:*                                               │
│                                                                         │
│ [Expandable: Full Exit Policy]                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ OPERATOR INFORMATION                                      #operator     │
├─────────────────────────────────────────────────────────────────────────┤
│ AROI: example.com [View operator page]                                 │
│ Contact: admin@example.com                                             │
└─────────────────────────────────────────────────────────────────────────┘
```

### Anchor Links
- `#status` - Health Status Panel
- `#network` - Network Role
- `#bandwidth` - Bandwidth Metrics
- `#consensus-evaluation` - Authority Voting Details
- `#flags` - Flags & Eligibility
- `#connectivity` - OR/Exit/Dir Addresses
- `#location` - Geographic Information
- `#family` - Family Configuration
- `#uptime` - Uptime History
- `#software` - Platform & Version
- `#exit-policy` - Exit Policy
- `#operator` - Operator Information

### Pros
- Health status immediately visible
- Troubleshooting-oriented information hierarchy
- Flag requirements clearly explained
- Progressive disclosure (expandable sections)

### Cons
- Longer vertical scroll
- May be overwhelming for casual browsers

---

## Proposal 2: "Card-Based" Modular Layout

### Concept
Organize information into distinct, visually-separated cards that can be scanned quickly. Each card addresses a specific aspect of relay operation.

### Layout Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│ RELAY: MyRelay (ABCD1234...)                                           │
│ Status: IN CONSENSUS | Running 47 days | Guard, Stable, Fast           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────────┐
│ QUICK STATUS  #quick│ │ NETWORK ROLE #role  │ │ BANDWIDTH      #bw     │
│                     │ │                     │ │                         │
│ Consensus: YES      │ │ Weight: 0.15%       │ │ Observed: 125 Mbit/s   │
│ Measured: YES       │ │ Guard: 0.12%        │ │ Advertised: 100 Mbit/s │
│ Reachable: IPv4+v6  │ │ Middle: 0.18%       │ │ Measured: 98 Mbit/s    │
│ Hibernating: No     │ │ Exit: 0.00%         │ │ Limits: 150/200 Mbit/s │
│ Issues: None        │ │ Type: Guard-focused │ │ Status: Healthy        │
└─────────────────────┘ └─────────────────────┘ └─────────────────────────┘

┌──────────────────────────────────────┐ ┌────────────────────────────────┐
│ FLAGS & REQUIREMENTS     #flags      │ │ REACHABILITY   #reachability   │
│                                      │ │                                │
│ Active Flags:                        │ │ OR Address: 192.0.2.1:9001    │
│ Guard Stable Fast Valid Running      │ │ OR IPv6: [2001:db8::1]:9001   │
│ V2Dir HSDir                          │ │ Exit Address: none             │
│                                      │ │ Dir Address: 192.0.2.1:9030   │
│ Requirements Met:                    │ │                                │
│ • Guard: WFU 99.2%≥98%, TK 45d≥8d   │ │ IPv4: 9/9 authorities          │
│ • Stable: MTBF 30d≥7d, Up 47d       │ │ IPv6: 3/5 testers (partial)    │
│ • Fast: 125Mb/s≥100KB/s             │ │                                │
│ • HSDir: WFU 99.2%≥98%, TK≥25h      │ │ Verified Hostname: relay.ex.co │
└──────────────────────────────────────┘ └────────────────────────────────┘

┌──────────────────────────────────────┐ ┌────────────────────────────────┐
│ LOCATION                #location    │ │ FAMILY           #family       │
│                                      │ │                                │
│ Country: Germany (DE) [flag]         │ │ Effective: 5 relays [View]     │
│ Region: Bavaria                      │ │ Alleged: 2 (not mutual)        │
│ City: Munich                         │ │ Indirect: 0                    │
│ Coordinates: 48.13°, 11.58°         │ │                                │
│                                      │ │ Config Status: OK              │
│ Network: AS24940                     │ │ (All family members mutual)    │
│ Provider: Hetzner Online GmbH        │ │                                │
│ [View on Interactive Map]            │ │ [Expand fingerprint list]      │
└──────────────────────────────────────┘ └────────────────────────────────┘

┌──────────────────────────────────────┐ ┌────────────────────────────────┐
│ UPTIME & HISTORY        #uptime      │ │ SOFTWARE        #software      │
│                                      │ │                                │
│ Current Status: UP                   │ │ Platform: Linux                │
│ Running Since: 2024-11-12 (47d)      │ │ Tor Version: 0.4.8.12          │
│                                      │ │ Version Status: Recommended    │
│ Historical Uptime (1M/6M/1Y/5Y):    │ │                                │
│   Flag: 99.2% / 98.5% / 97.1% / N/A │ │ Hibernating: No                │
│   Overall: 99.1% / 98.2% / 96.8%    │ │                                │
│                                      │ │ Address Last Changed:          │
│ First Seen: 2023-06-01 (1.5 years)  │ │   2024-01-15                   │
│ Last Seen: Now                       │ │                                │
└──────────────────────────────────────┘ └────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ EXIT POLICY                                              #exit-policy   │
│                                                                         │
│ Type: Non-Exit Relay (rejects all exit traffic)                        │
│                                                                         │
│ IPv4 Summary: reject *:*                                               │
│ IPv6 Summary: reject *:*                                               │
│                                                                         │
│ [Show Full Policy]                                                     │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ CONSENSUS EVALUATION (Diagnostic Details)         #consensus-evaluation │
│                                                                         │
│ Summary: Relay meets all requirements for current flags                 │
│                                                                         │
│ [Expand: Authority Voting Details]                                     │
│ [Expand: Per-Authority Measurements]                                   │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ OPERATOR                                                 #operator      │
│                                                                         │
│ AROI Domain: example.com [Operator Page]                               │
│ Contact: admin@example.com [Contact Page]                              │
└─────────────────────────────────────────────────────────────────────────┘
```

### Anchor Links
- `#quick` - Quick Status
- `#role` - Network Role
- `#bw` - Bandwidth
- `#flags` - Flags & Requirements
- `#reachability` - Reachability
- `#location` - Location
- `#family` - Family
- `#uptime` - Uptime & History
- `#software` - Software
- `#exit-policy` - Exit Policy
- `#consensus-evaluation` - Consensus Evaluation
- `#operator` - Operator

### Pros
- Visual separation makes scanning easy
- Cards can be reordered based on user preference (future)
- Clear information boundaries
- Good for both desktop and tablet

### Cons
- More whitespace usage
- Cards may feel disconnected

---

## Proposal 3: "Tab-Based" Compact Layout

### Concept
Use a tabbed interface to reduce information overload while keeping everything accessible. Primary tab shows essential status; other tabs provide detailed information.

### Layout Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│ RELAY: MyRelay                                                         │
│ Fingerprint: ABCD1234EFGH5678...                                       │
│ Links: [Family (5)] [Operator: example.com] [AS24940] [Germany]        │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ [Overview] [Performance] [Connectivity] [Policy] [Diagnostics]          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ TAB: OVERVIEW (default)                                    #overview    │
│ ═══════════════════════════════════════════════════════════════════════│
│                                                                         │
│ RELAY HEALTH                                                           │
│ ┌─────────────┬─────────────┬─────────────┬─────────────┐              │
│ │ Consensus   │ Running     │ Measured    │ Issues      │              │
│ │ YES (9/9)   │ 47 days     │ YES         │ None        │              │
│ └─────────────┴─────────────┴─────────────┴─────────────┘              │
│                                                                         │
│ ACTIVE FLAGS                                                           │
│ Guard | Stable | Fast | Valid | Running | V2Dir | HSDir                │
│                                                                         │
│ NETWORK ROLE                                                           │
│ Consensus Weight: 0.15% | Guard: 0.12% | Middle: 0.18% | Exit: 0.00%  │
│ Position: Guard-focused relay                                          │
│                                                                         │
│ LOCATION                                                               │
│ Munich, Bavaria, Germany | AS24940 (Hetzner) | [Map]                   │
│                                                                         │
│ SOFTWARE                                                               │
│ Linux / Tor 0.4.8.12 (Recommended) | Not Hibernating                   │
│                                                                         │
│ TIMESTAMPS                                                             │
│ First Seen: 2023-06-01 (1.5 years) | Last Seen: Now | Uptime: 47 days │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

TAB: PERFORMANCE                                            #performance
═══════════════════════════════════════════════════════════════════════

BANDWIDTH METRICS
┌──────────────────────┬──────────────────────┐
│ Observed Bandwidth   │ 125 Mbit/s           │
│ Advertised Bandwidth │ 100 Mbit/s           │
│ Rate Limit           │ 150 Mbit/s           │
│ Burst Limit          │ 200 Mbit/s           │
│ Authority Measured   │ 98 Mbit/s (median)   │
└──────────────────────┴──────────────────────┘

FLAG ELIGIBILITY
┌──────────┬─────────────────┬────────────────┬──────────┐
│ Flag     │ Your Value      │ Threshold      │ Status   │
├──────────┼─────────────────┼────────────────┼──────────┤
│ Guard    │ WFU: 99.2%      │ ≥98%           │ MEETS    │
│          │ TK: 45 days     │ ≥8 days        │ MEETS    │
│          │ BW: 125 Mbit/s  │ ≥2 MB/s        │ MEETS    │
│ Stable   │ MTBF: 30 days   │ ≥7 days        │ MEETS    │
│          │ Uptime: 47 days │ varies         │ MEETS    │
│ Fast     │ 125 Mbit/s      │ ≥100 KB/s      │ MEETS    │
│ HSDir    │ WFU: 99.2%      │ ≥98%           │ MEETS    │
│          │ TK: 45 days     │ ≥25 hours      │ MEETS    │
└──────────┴─────────────────┴────────────────┴──────────┘

UPTIME HISTORY
┌──────────────┬────────┬────────┬────────┬────────┐
│ Period       │ 1 Month│ 6 Month│ 1 Year │ 5 Year │
├──────────────┼────────┼────────┼────────┼────────┤
│ Flag Uptime  │ 99.2%  │ 98.5%  │ 97.1%  │ N/A    │
│ Overall      │ 99.1%  │ 98.2%  │ 96.8%  │ N/A    │
└──────────────┴────────┴────────┴────────┴────────┘


TAB: CONNECTIVITY                                          #connectivity
═══════════════════════════════════════════════════════════════════════

NETWORK ADDRESSES
OR Address:   192.0.2.1:9001
OR IPv6:      [2001:db8::1]:9001
Exit Address: none
Dir Address:  192.0.2.1:9030

Verified Hostname: relay.example.com

REACHABILITY
IPv4: Reachable by 9/9 authorities
IPv6: Reachable by 3/5 testers (partial - some authorities don't test IPv6)

LOCATION DETAILS
Country:     Germany (DE)
Region:      Bavaria
City:        Munich
Coordinates: 48.1351° N, 11.5820° E

NETWORK PROVIDER
AS Number:   AS24940
AS Name:     Hetzner Online GmbH
[View on BGP.tools] [View AS Network Page]

[View on Interactive Map]


TAB: POLICY                                                      #policy
═══════════════════════════════════════════════════════════════════════

EXIT POLICY TYPE
This relay is configured as a non-exit relay (rejects all exit traffic).

IPv4 EXIT POLICY SUMMARY
reject *:*

IPv6 EXIT POLICY SUMMARY  
reject *:*

FULL EXIT POLICY
reject *:*

FAMILY CONFIGURATION                                           #family
Effective Family Members: 5 relays
  - FINGERPRINT1... [View]
  - FINGERPRINT2... [View]
  - FINGERPRINT3... [View]
  - FINGERPRINT4... [View]
  - FINGERPRINT5... (this relay)

Alleged Family Members: 2 relays
  (These relays are in your MyFamily but don't list you back)
  - FINGERPRINT6... [View]
  - FINGERPRINT7... [View]

Indirect Family Members: 0 relays
  (Relays that list you but you don't list back)

[View Full Family Page]


TAB: DIAGNOSTICS                                            #diagnostics
═══════════════════════════════════════════════════════════════════════

CONSENSUS EVALUATION
Data from Tor CollecTor (authority votes)

Consensus Status: IN CONSENSUS (9/9 authorities voted)

IDENTIFIED ISSUES: None

FLAG ELIGIBILITY BY AUTHORITY
[Detailed per-authority table...]

PER-AUTHORITY VOTING DETAILS
[Detailed table with all authority measurements...]

BANDWIDTH VALUES EXPLAINED
• Relay Reported = Your relay's self-reported bandwidth (used for flag eligibility)
• Authority Measured = Bandwidth measured by sbws scanner (used for consensus weight)
```

### Anchor Links
- `#overview` - Overview tab
- `#performance` - Performance tab
- `#connectivity` - Connectivity tab
- `#policy` - Policy tab (exit policy + family)
- `#diagnostics` - Diagnostics tab (consensus evaluation)
- `#family` - Family section within Policy tab

### Pros
- Reduces initial cognitive load
- Users choose what to explore
- Clean, focused interface
- Deep links to specific tabs work well

### Cons
- Requires CSS-only tab implementation (no JS)
- Information less visible at once
- May require more clicks to find info

---

## Proposal 4: "Status-Centric" Accordion Layout

### Concept
Use collapsible accordion sections with clear status indicators. Top section always shows relay health; other sections expand on demand.

### Layout Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│ RELAY: MyRelay | ABCD1234EFGH5678...                                   │
│ Family (5) | example.com | AS24940 | Germany                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ [▼] HEALTH STATUS                                           #health    │
│     Status: HEALTHY | In Consensus | All Systems Operational           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ● Consensus Status     IN CONSENSUS (9/9 authorities)                 │
│  ● Bandwidth Measured   YES (by 6 bandwidth authorities)               │
│  ● IPv4 Reachability    FULL (9/9 authorities)                         │
│  ● IPv6 Reachability    PARTIAL (3/5 testers)                          │
│  ● Flags                Guard, Stable, Fast, Valid, Running, V2Dir,HSDir│
│  ● Uptime               47 days (since 2024-11-12)                     │
│  ● Hibernating          No                                             │
│                                                                         │
│  Issues: None detected                                                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ [►] NETWORK ROLE & BANDWIDTH                               #bandwidth   │
│     Guard-focused | 0.15% consensus weight | 125 Mbit/s observed       │
├ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┤
│ (Collapsed - click to expand)                                          │
│                                                                         │
│ BANDWIDTH CAPACITY                                                     │
│ Observed: 125 Mbit/s | Advertised: 100 Mbit/s                         │
│ Rate Limit: 150 Mbit/s | Burst Limit: 200 Mbit/s                      │
│ Authority Measured: 98 Mbit/s (median of 6 authorities)               │
│                                                                         │
│ NETWORK PARTICIPATION                                                  │
│ Consensus Weight: 0.15% | Guard: 0.12% | Middle: 0.18% | Exit: 0.00% │
│ Position: Guard-focused (high guard probability, no exit)             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ [►] FLAGS & ELIGIBILITY                                        #flags   │
│     7 flags active | All requirements met                              │
├ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┤
│ (Collapsed - click to expand)                                          │
│                                                                         │
│ CURRENT FLAGS                                                          │
│ Guard | Stable | Fast | Valid | Running | V2Dir | HSDir               │
│                                                                         │
│ ELIGIBILITY REQUIREMENTS                                               │
│ [Table showing your values vs thresholds for each flag]               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ [►] CONNECTIVITY & ADDRESSES                           #connectivity    │
│     192.0.2.1:9001 | IPv6 enabled | Munich, DE                         │
├ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┤
│ (Collapsed content...)                                                 │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ [►] FAMILY CONFIGURATION                                     #family    │
│     5 effective members | 2 alleged (not mutual)                       │
├ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┤
│ (Collapsed content...)                                                 │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ [►] UPTIME HISTORY                                          #uptime     │
│     99.2% (1M) | First seen 2023-06-01                                 │
├ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┤
│ (Collapsed content...)                                                 │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ [►] EXIT POLICY                                        #exit-policy     │
│     Non-exit relay (rejects all)                                       │
├ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┤
│ (Collapsed content...)                                                 │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ [►] SOFTWARE & VERSION                                    #software     │
│     Linux | Tor 0.4.8.12 (Recommended)                                 │
├ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┤
│ (Collapsed content...)                                                 │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ [►] CONSENSUS EVALUATION                        #consensus-evaluation   │
│     All authorities agree | No issues detected                         │
├ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┤
│ (Collapsed - detailed authority voting tables)                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ [►] OPERATOR INFORMATION                                  #operator     │
│     example.com | admin@example.com                                    │
├ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┤
│ (Collapsed content...)                                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Features
- Each accordion header shows key summary info
- Health Status section always expanded by default
- CSS-only accordion using `:target` selector
- Status indicators in headers (color-coded or text)

### Anchor Links
- `#health` - Health Status (default expanded)
- `#bandwidth` - Network Role & Bandwidth
- `#flags` - Flags & Eligibility
- `#connectivity` - Connectivity & Addresses
- `#family` - Family Configuration
- `#uptime` - Uptime History
- `#exit-policy` - Exit Policy
- `#software` - Software & Version
- `#consensus-evaluation` - Consensus Evaluation
- `#operator` - Operator Information

### Pros
- Compact initial view
- Summary visible for all sections
- Users control depth of exploration
- Good for mobile

### Cons
- Requires CSS implementation for accordion
- May hide important details

---

## Proposal 5: "Sidebar Navigation" Layout

### Concept
Fixed sidebar with navigation links; main content area shows selected section. Good for quick jumping between sections on larger screens.

### Layout Structure

```
┌──────────────────┬──────────────────────────────────────────────────────┐
│ RELAY NAVIGATION │ MAIN CONTENT AREA                                    │
│                  │                                                      │
│ MyRelay          │ ═══════════════════════════════════════════════════ │
│ ABCD1234...      │                                                      │
│                  │ HEALTH STATUS                              #health   │
│ ─────────────────│                                                      │
│                  │ Overall Status: HEALTHY                              │
│ ● Health Status  │                                                      │
│   Network Role   │ ┌─────────────┬─────────────┬─────────────┐         │
│   Bandwidth      │ │ Consensus   │ Measured    │ Reachable   │         │
│   Flags          │ │ YES (9/9)   │ YES (6 auth)│ IPv4+v6     │         │
│   Connectivity   │ └─────────────┴─────────────┴─────────────┘         │
│   Location       │                                                      │
│   Family         │ Active Flags: Guard, Stable, Fast, Valid, Running,  │
│   Uptime         │               V2Dir, HSDir                          │
│   Exit Policy    │                                                      │
│   Software       │ Running: 47 days (since 2024-11-12)                 │
│   Diagnostics    │ Hibernating: No                                     │
│   Operator       │ Issues Detected: None                               │
│                  │                                                      │
│ ─────────────────│ ─────────────────────────────────────────────────── │
│                  │                                                      │
│ QUICK LINKS      │ NETWORK ROLE                              #network   │
│ [Family Page]    │                                                      │
│ [Operator Page]  │ Consensus Weight: 0.15%                             │
│ [AS Network]     │ Guard Probability: 0.12%                            │
│ [Country]        │ Middle Probability: 0.18%                           │
│ [Interactive Map]│ Exit Probability: 0.00%                             │
│                  │                                                      │
│ ─────────────────│ Position Type: Guard-focused relay                   │
│                  │                                                      │
│ RELAY INFO       │ Underutilization Warning: None                      │
│ Platform: Linux  │                                                      │
│ Version: 0.4.8.12│ ─────────────────────────────────────────────────── │
│ Status: Running  │                                                      │
│                  │ BANDWIDTH                                 #bandwidth │
│                  │                                                      │
│                  │ ┌────────────────────┬─────────────────────┐        │
│                  │ │ Metric             │ Value               │        │
│                  │ ├────────────────────┼─────────────────────┤        │
│                  │ │ Observed           │ 125 Mbit/s          │        │
│                  │ │ Advertised         │ 100 Mbit/s          │        │
│                  │ │ Rate Limit         │ 150 Mbit/s          │        │
│                  │ │ Burst Limit        │ 200 Mbit/s          │        │
│                  │ │ Authority Measured │ 98 Mbit/s (median)  │        │
│                  │ └────────────────────┴─────────────────────┘        │
│                  │                                                      │
│                  │ ─────────────────────────────────────────────────── │
│                  │                                                      │
│                  │ FLAGS & ELIGIBILITY                         #flags   │
│                  │                                                      │
│                  │ Current Flags: Guard Stable Fast Valid Running      │
│                  │                V2Dir HSDir                          │
│                  │                                                      │
│                  │ Flag Requirements:                                  │
│                  │ [Eligibility table...]                              │
│                  │                                                      │
│                  │ ─────────────────────────────────────────────────── │
│                  │                                                      │
│                  │ [... more sections continue below ...]              │
│                  │                                                      │
└──────────────────┴──────────────────────────────────────────────────────┘
```

### Mobile Behavior
On narrow screens, sidebar collapses to a horizontal nav menu at the top.

### Anchor Links
- `#health` - Health Status
- `#network` - Network Role
- `#bandwidth` - Bandwidth
- `#flags` - Flags & Eligibility
- `#connectivity` - Connectivity
- `#location` - Location
- `#family` - Family
- `#uptime` - Uptime
- `#exit-policy` - Exit Policy
- `#software` - Software
- `#diagnostics` - Diagnostics/Consensus Evaluation
- `#operator` - Operator

### Pros
- Excellent navigation for desktop
- Full content visible (no accordions/tabs to click)
- Sidebar shows relay summary at a glance
- Professional, documentation-style feel

### Cons
- Less effective on mobile (requires collapse)
- More complex CSS/layout
- Takes horizontal space from content

---

## Section Content Specifications (All Proposals)

### Required Anchor Links (Minimum Set)

| Anchor ID | Section Name | Priority |
|-----------|--------------|----------|
| `#health` or `#status` | Health/Status Overview | Critical |
| `#bandwidth` | Bandwidth Metrics | High |
| `#flags` | Flags & Eligibility | High |
| `#connectivity` | Network Addresses | High |
| `#consensus-evaluation` | Authority Voting | High |
| `#family` | Family Configuration | Medium |
| `#uptime` | Uptime History | Medium |
| `#location` | Geographic Location | Medium |
| `#exit-policy` | Exit Policy | Medium |
| `#software` | Platform & Version | Low |
| `#operator` | Operator/Contact Info | Low |

### Information Removal (All Proposals)

**Remove all emoji icons:**
- ✓ ✗ checkmarks → Use text "Yes/No" or "Meets/Below"
- 🔍 magnifying glass → Remove
- 📊 chart → Remove
- ⏱️ timer → Remove
- 🗺️ map → Use text "View on Interactive Map"
- ⚠️ warning → Use text "[Warning]" or colored indicator
- 💡 lightbulb → Use text "Tip:" or "Suggestion:"

### Content Priorities for Troubleshooting

**Always Visible (Top Priority):**
1. In consensus status (Yes/No + authority count)
2. Running status (uptime duration)
3. Current flags
4. Bandwidth measured status
5. Any detected issues/warnings

**Second Level (Expandable/Below Fold):**
1. Flag eligibility details (thresholds vs current values)
2. Per-authority voting breakdown
3. IPv4/IPv6 reachability details
4. Family configuration issues

**Third Level (On Demand):**
1. Full exit policy
2. Complete fingerprint lists
3. Historical data explanations
4. Data source attributions

---

## Recommendation

**Primary Recommendation: Proposal 1 (Troubleshooting-First Dashboard)**

Rationale:
- Best addresses the core use case of troubleshooting
- Health status panel immediately answers "Is my relay working?"
- Logical flow from status → details → diagnostics
- Maintains all current content without hiding it
- Clear section structure with comprehensive anchor links

**Secondary Recommendation: Proposal 4 (Status-Centric Accordion)**

Rationale:
- More compact for users who browse multiple relays
- Summary visible in headers for quick scanning
- Good mobile experience
- CSS-only implementation possible

---

## Implementation Notes

### CSS-Only Interactive Elements

All proposals avoid JavaScript requirements:
- Use `:target` selector for accordion/tab behavior
- Use checkbox hack for hamburger menus (already implemented)
- Use CSS hover/focus states for tooltips (already implemented)

### Maintaining Backward Compatibility

- Existing anchor links should redirect or be aliased
- URL structure remains unchanged
- All current data fields preserved

### Accessibility Considerations

- Proper heading hierarchy (h1 → h2 → h3)
- ARIA labels for interactive elements
- Sufficient color contrast for status indicators
- Keyboard navigation support

---

## Next Steps

1. Gather feedback on proposals
2. Select preferred layout (or hybrid approach)
3. Create detailed HTML/CSS mockup
4. Implement template changes
5. Test with sample relay data
6. Review and iterate

---

*Document Version: 1.0*  
*Created: 2024-12-29*  
*Based on analysis of tor-relays mailing list and current template structure*
