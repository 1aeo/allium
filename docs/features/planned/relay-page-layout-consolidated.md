# Relay Page Layout: Consolidated Top 5 Improvements

Consolidated recommendations from Gemini 3 Pro and Opus 4.5 proposals, optimized for new relay operators and troubleshooting common issues.

**Constraints Applied:**
- Tabs and sidebar navigation deprioritized
- Information density maximized with top-to-bottom layout
- Most important information at top
- All existing content preserved (no new charts)
- All emoji icons removed, replaced with text labels
- Anchor hyperlinks for all major sections

---

## Common Relay Troubleshooting Issues (from tor-relays@lists.torproject.org)

Based on mailing list analysis, relay operators most frequently troubleshoot:

1. **Relay not appearing in consensus** - Most critical, first thing operators check
2. **Missing or lost flags** (Guard, Stable, Fast, HSDir) - Second most common concern
3. **Low consensus weight / bandwidth measurement** - Affects traffic allocation
4. **IPv6 reachability problems** - Partial reachability confuses operators
5. **Family configuration errors** - Alleged vs effective family mismatches
6. **Version and update issues** - Recommended vs obsolete version status
7. **Uptime/stability problems** - Why relays lose Stable flag

---

## Top 5 Improvements

### 1. Health Status Summary at Page Top

**Source:** Both proposals recommend status-first approach

**Implementation:**
Move critical "is my relay working?" information to the very top of the page, immediately after the header.

```
+------------------------------------------------------------------+
| RELAY HEALTH STATUS                                    #status   |
+------------------------------------------------------------------+
| Consensus: IN CONSENSUS (9/9 authorities)                        |
| Running: UP for 47 days (since 2024-11-12)                       |
| Bandwidth Measured: Yes (by 6 bandwidth authorities)             |
| Flags: Guard, Stable, Fast, Valid, Running, V2Dir, HSDir         |
| Issues: None detected                                            |
|   -or-                                                           |
| Issues:                                                          |
|   [Warning] IPv6 reachability partial (3/5 authorities)          |
|   [Error] Version is obsolete - upgrade recommended              |
+------------------------------------------------------------------+
```

**Key Elements:**
- **Consensus status** - Most critical for troubleshooting (Yes/No + authority count)
- **Running status** - Current uptime duration and last restart date
- **Bandwidth measured** - Whether bandwidth authorities have measured this relay
- **Current flags** - All active flags in text format
- **Issues/Warnings** - Dynamic section showing detected problems with actionable advice

**Anchor:** `#status`

**Rationale:** New operators ask "Is my relay working?" first. This answers that question without scrolling.

---

### 2. Section Reordering by Troubleshooting Priority

**Source:** Opus 4.5 "Troubleshooting-First" + Gemini "Troubleshooter Workflow"

**New Section Order (top to bottom):**

| Order | Section | Anchor |
|-------|---------|--------|
| 1 | Health Status Summary | `#status` |
| 2 | Connectivity and Addresses | `#connectivity` |
| 3 | Flags and Eligibility | `#flags` |
| 4 | Bandwidth Metrics | `#bandwidth` |
| 5 | Consensus Evaluation Summary | `#consensus-summary` |
| 6 | Uptime and Stability | `#uptime` |
| 7 | Family Configuration | `#family` |
| 8 | Software and Version | `#software` |
| 9 | Exit Policy | `#exit-policy` |
| 10 | Location and Network | `#location` |
| 11 | Per-Authority Vote Details | `#authority-votes` |
| 12 | Operator Information | `#operator` |

#### Detailed Ordering Rationale

The ordering follows a **troubleshooting decision tree** - each section answers questions that logically lead to the next:

**1. Health Status Summary** - "Is my relay working at all?"
- This is the first question every operator asks
- If the answer is "yes, everything fine" - operator can stop here
- If "no" or "partially" - they continue down the page to diagnose
- Mailing list evidence: Nearly every troubleshooting thread starts with "my relay is/isn't in consensus"

**2. Connectivity and Addresses** - "Can the network reach my relay?"
- If relay is NOT in consensus, the first thing to check is reachability
- Shows OR port, Dir port, IPv4/IPv6 reachability status
- Most common cause of "not in consensus": firewall/NAT blocking ports
- Mailing list evidence: "Check your firewall" is the #1 response to "relay not working" posts
- Troubleshooting dependency: Must be reachable before flags can be assigned

**3. Flags and Eligibility** - "Why don't I have [Guard/Stable/Fast] flag?"
- Once connectivity is confirmed, operators ask about missing flags
- Second most common mailing list question after consensus issues
- Shows clear threshold requirements vs current values
- Troubleshooting dependency: Connectivity must work before flags matter

**4. Bandwidth Metrics** - "Why is my consensus weight so low?"
- After flags, operators want to know why they're not getting traffic
- Shows observed vs advertised vs authority-measured bandwidth
- Explains discrepancy between relay's capacity and actual usage
- Mailing list evidence: "I have 1 Gbit/s but only getting 10 Mbit/s traffic"
- Troubleshooting dependency: Flags affect bandwidth allocation (Guard/Fast)

**5. Consensus Evaluation Summary** - "What do the authorities think of my relay?"
- Condensed view of authority voting and measurements
- Bridges the gap between "what I configured" and "what authorities see"
- Quick diagnostic without scrolling to detailed tables
- Troubleshooting dependency: Summarizes results of connectivity + flags + bandwidth checks

**6. Uptime and Stability** - "Why did I lose my Stable/Guard flag?"
- Stable and Guard flags require sustained uptime
- Shows historical uptime percentages (1M/6M/1Y)
- Explains flag loss after restarts or outages
- Mailing list evidence: "I restarted my relay and lost Guard flag"
- Troubleshooting dependency: Explains flag eligibility failures from section 3

**7. Family Configuration** - "Why are my family members showing as 'alleged'?"
- Common misconfiguration: asymmetric family declarations
- Shows effective vs alleged vs indirect family members
- Mailing list evidence: Frequent questions about family setup errors
- Position rationale: Not critical for basic operation, but important for operators running multiple relays

**8. Software and Version** - "Is my Tor version OK?"
- Version issues are less urgent but can affect flags
- Shows recommended/obsolete status
- Position rationale: Usually not the cause of immediate problems, but good to verify
- Mailing list evidence: Occasional "upgrade your Tor" responses

**9. Exit Policy** - "What traffic does my relay allow?"
- Reference information, rarely the cause of troubleshooting issues
- Mostly static configuration data
- Position rationale: Operators know their exit policy; this is for verification

**10. Location and Network** - "Where is my relay located?"
- Geographic and AS information
- Rarely relevant to troubleshooting
- Position rationale: Reference data, not diagnostic

**11. Per-Authority Vote Details** - "Which specific authority is not voting for me?"
- Advanced diagnostics for edge cases
- Detailed per-authority breakdown
- Position rationale: Only needed when summary (section 5) shows problems
- Used by experienced operators or when guided by support

**12. Operator Information** - "How do I contact the operator?"
- Contact info and AROI
- Position rationale: Reference data, not needed for self-troubleshooting

#### The Troubleshooting Flow Visualized

```
START: "My relay isn't working"
         │
         ▼
    ┌─────────────────┐
    │ 1. HEALTH STATUS │ ──── "In consensus? Running? Any issues?"
    └────────┬────────┘
             │ If NOT in consensus or has issues...
             ▼
    ┌─────────────────┐
    │ 2. CONNECTIVITY │ ──── "Can authorities reach my ports?"
    └────────┬────────┘
             │ If reachable but missing flags...
             ▼
    ┌─────────────────┐
    │ 3. FLAGS        │ ──── "What flags am I missing? What thresholds?"
    └────────┬────────┘
             │ If flags OK but low traffic...
             ▼
    ┌─────────────────┐
    │ 4. BANDWIDTH    │ ──── "Why is my measured BW different from capacity?"
    └────────┬────────┘
             │ Need more detail on authority measurements...
             ▼
    ┌─────────────────┐
    │ 5. CONSENSUS    │ ──── "Summary of what authorities see"
    │    SUMMARY      │
    └────────┬────────┘
             │ If flag was lost recently...
             ▼
    ┌─────────────────┐
    │ 6. UPTIME       │ ──── "Did downtime cause flag loss?"
    └────────┬────────┘
             │ Running multiple relays...
             ▼
    ┌─────────────────┐
    │ 7. FAMILY       │ ──── "Is family configured correctly?"
    └────────┬────────┘
             │ Check software version...
             ▼
    ┌─────────────────┐
    │ 8. SOFTWARE     │ ──── "Is my Tor version recommended?"
    └────────┬────────┘
             │
             ▼
    ┌─────────────────────────────────────────┐
    │ 9-12. REFERENCE DATA                    │
    │ Exit Policy, Location, Authority Detail,│
    │ Operator Info                           │
    └─────────────────────────────────────────┘
```

#### Current vs Proposed Layout

```
CURRENT (two-column, scattered):        PROPOSED (single-column, flow):
                                  
Left Column:                            Top-to-Bottom:
  - Nickname/Fingerprint                  1. Health Status [NEW]
  - AROI/Contact          ─┐              2. Connectivity
  - Exit Policies          │              3. Flags + Eligibility
  - Family                 │              4. Bandwidth
                           │              5. Consensus Summary
Right Column:              │              6. Uptime/Stability
  - Bandwidth              │              7. Family
  - Network Participation  │              8. Software/Version
  - OR/Exit/Dir Addresses  ├─ scattered   9. Exit Policy
  - Location               │              10. Location/AS
  - Flags                  │              11. Per-Authority Details
  - Uptime                 │              12. Operator info
  - Platform/Version      ─┘
                                  
Bottom (separate section):
  - Consensus Evaluation (detailed)
```

**Why single-column?** Two-column layouts force users to scan horizontally and make mental connections between scattered data. A linear flow matches how troubleshooting actually works: check one thing, then the next logical thing.

---

### 3. Flag Eligibility Table with Clear Thresholds

**Source:** Both proposals emphasize flag eligibility visibility

**Implementation:**
Add a dedicated flag eligibility section showing requirements vs current values.

```
+------------------------------------------------------------------+
| FLAG ELIGIBILITY                                        #flags   |
+------------------------------------------------------------------+
| Current Flags: Guard, Stable, Fast, Valid, Running, V2Dir, HSDir |
|                                                                  |
| Requirements:                                                    |
| +----------+---------------+---------------+----------+          |
| | Flag     | Your Value    | Threshold     | Status   |          |
| +----------+---------------+---------------+----------+          |
| | Guard    | WFU 99.2%     | >=98%         | Meets    |          |
| |          | TK 45 days    | >=8 days      | Meets    |          |
| |          | BW 125 Mbit/s | >=2 MB/s      | Meets    |          |
| | Stable   | MTBF 30 days  | >=7 days      | Meets    |          |
| |          | Uptime 47 days| >=7 days      | Meets    |          |
| | Fast     | 125 Mbit/s    | >=100 KB/s    | Meets    |          |
| | HSDir    | WFU 99.2%     | >=98%         | Meets    |          |
| |          | TK 45 days    | >=25 hours    | Meets    |          |
| +----------+---------------+---------------+----------+          |
|                                                                  |
| Missing Flags: Exit (no exit policy configured)                  |
+------------------------------------------------------------------+
```

**Key Elements:**
- **Current flags** listed prominently
- **Table showing each flag's requirements:**
  - Your relay's current value
  - Threshold required (with source)
  - Status: Meets / Below / Partial
- **Missing flags** with explanation why (optional)

**Anchor:** `#flags`

**Rationale:** "Why don't I have Guard flag?" is a top mailing list question. This answers it directly.

---

### 4. Remove All Emoji Icons, Use Text Labels

**Source:** User requirement, both proposals support

**Changes:**

| Current | Replace With |
|---------|--------------|
| Checkmark icon | Text: "Yes" or "Meets" |
| X icon | Text: "No" or "Below" |
| Warning icon | Text: "[Warning]" |
| Map icon | Text: "View on Interactive Map" |
| Magnifying glass icon | Remove (section title sufficient) |
| Light bulb icon | Text: "Tip:" or "Suggestion:" |
| Chart icon | Remove |
| Clock/timer icon | Remove |

**Status Indicators (text-based):**
```
IN CONSENSUS     (green text, bold)
NOT IN CONSENSUS (red text, bold)
PARTIAL          (yellow/amber text, bold)
MEETS            (green text)
BELOW            (red text)
[Warning]        (yellow/amber text with brackets)
[Error]          (red text with brackets)
[Info]           (blue text with brackets)
```

**Rationale:** Text labels are more accessible, searchable, and don't require icon fonts.

---

### 5. Comprehensive Anchor Links for Deep Linking

**Source:** Both proposals, user requirement

**Required Anchor IDs:**

| Anchor ID | Section | Priority |
|-----------|---------|----------|
| `#status` | Health Status Summary | Critical |
| `#connectivity` | OR/Exit/Dir Addresses, Reachability | High |
| `#flags` | Flags and Eligibility | High |
| `#bandwidth` | Bandwidth Metrics | High |
| `#consensus-summary` | Consensus Evaluation Summary | High |
| `#consensus-evaluation` | Full Consensus Evaluation (existing) | High |
| `#authority-votes` | Per-Authority Vote Table | Medium |
| `#uptime` | Uptime and Stability | Medium |
| `#family` | Family Configuration | Medium |
| `#effective-family` | Effective Family Members (existing) | Medium |
| `#alleged-family` | Alleged Family Members (existing) | Medium |
| `#indirect-family` | Indirect Family Members (existing) | Medium |
| `#software` | Platform and Version | Medium |
| `#exit-policy` | Exit Policy (existing) | Low |
| `#ipv4-exit-policy-summary` | IPv4 Exit Policy Summary (existing) | Low |
| `#ipv6-exit-policy-summary` | IPv6 Exit Policy Summary (existing) | Low |
| `#location` | Geographic Location | Low |
| `#operator` | Operator/Contact Info | Low |
| `#relay-summary` | Summary Table (existing) | Low |

**Implementation:**
Each section header should be clickable and link to itself:

```html
<h3 id="status">
  <a href="#status" class="anchor-link">Health Status</a>
</h3>
```

**Use Cases:**
- Troubleshooting guides can link directly to `relay/FINGERPRINT/#flags`
- IRC/email support can reference `#authority-votes` for advanced debugging
- Documentation can deep-link to specific sections

---

## Implementation Summary

### Phase 1: Quick Wins (template changes only)
1. Remove all emoji icons, replace with text labels
2. Add missing anchor links to all sections
3. Ensure existing anchor links work correctly

### Phase 2: Layout Restructure
1. Add Health Status Summary section at top
2. Reorder sections by troubleshooting priority
3. Consolidate two-column layout into single-column flow

### Phase 3: Content Enhancement
1. Add Flag Eligibility table (if data available)
2. Improve Issues/Warnings display with actionable advice
3. Add "Missing Flags" explanation section

---

## Proposed Page Structure (ASCII Wireframe)

```
+==================================================================+
|  View Relay "MyRelay"                                            |
|  Family: 5 relays | AS12345 | Germany | Linux                    |
+==================================================================+

+------------------------------------------------------------------+
| HEALTH STATUS                                          [#status] |
+------------------------------------------------------------------+
| Consensus: IN CONSENSUS (9/9)  |  Running: UP 47 days            |
| Measured: Yes (6 auths)        |  Flags: Guard Stable Fast ...   |
| Issues: None                                                     |
+------------------------------------------------------------------+

+------------------------------------------------------------------+
| CONNECTIVITY                                      [#connectivity] |
+------------------------------------------------------------------+
| OR Address: 192.0.2.1:9001, [2001:db8::1]:9001                   |
| Exit Address: none                                               |
| Dir Address: 192.0.2.1:9030                                      |
| IPv4 Reachable: 9/9 authorities                                  |
| IPv6 Reachable: 3/5 testers (2 don't test IPv6)                  |
+------------------------------------------------------------------+

+------------------------------------------------------------------+
| FLAGS AND ELIGIBILITY                                   [#flags] |
+------------------------------------------------------------------+
| Current: Guard, Stable, Fast, Valid, Running, V2Dir, HSDir       |
|                                                                  |
| +----------+-------------+-------------+--------+                |
| | Flag     | Your Value  | Threshold   | Status |                |
| +----------+-------------+-------------+--------+                |
| | Guard    | WFU 99.2%   | >=98%       | Meets  |                |
| | Guard    | TK 45d      | >=8d        | Meets  |                |
| | Stable   | MTBF 30d    | >=7d        | Meets  |                |
| | Fast     | 125 Mbit/s  | >=100 KB/s  | Meets  |                |
| +----------+-------------+-------------+--------+                |
+------------------------------------------------------------------+

+------------------------------------------------------------------+
| BANDWIDTH                                           [#bandwidth] |
+------------------------------------------------------------------+
| Observed: 125 Mbit/s | Advertised: 100 Mbit/s                    |
| Rate Limit: 150 Mbit/s | Burst Limit: 200 Mbit/s                 |
| Authority Measured: Yes (median 98 Mbit/s)                       |
|                                                                  |
| Network Participation:                                           |
| Consensus Weight: 0.15% | Guard: 0.12% | Middle: 0.18% | Exit: 0%|
+------------------------------------------------------------------+

+------------------------------------------------------------------+
| CONSENSUS EVALUATION SUMMARY                 [#consensus-summary] |
+------------------------------------------------------------------+
| - In Consensus: 9/9 authorities (need >=5/9)                     |
| - Flag Eligibility: Guard 9/9 | Stable 9/9 | Fast 9/9 | HSDir 9/9|
| - Reachability: IPv4 9/9 | IPv6 3/5                              |
| - Consensus Weight: Median 98 KB/s (Min 95 | Max 102)            |
| - Issues: None detected                                          |
+------------------------------------------------------------------+

+------------------------------------------------------------------+
| UPTIME AND STABILITY                                   [#uptime] |
+------------------------------------------------------------------+
| Current: UP for 47 days                                          |
| Flag Uptime (1M/6M/1Y/5Y): 99.2% / 98.5% / 97.1% / N/A           |
| Overall Uptime (1M/6M/1Y/5Y): 99.1% / 98.2% / 96.8% / N/A        |
| First Seen: 2023-06-01 | Last Seen: now                          |
| Last Restarted: 2024-11-12                                       |
| Hibernating: No                                                  |
+------------------------------------------------------------------+

+------------------------------------------------------------------+
| FAMILY CONFIGURATION                                   [#family] |
+------------------------------------------------------------------+
| Effective Family: 5 relays [View Family Page]                    |
| Alleged Family: 2 relays (they don't list you back)              |
| Indirect Family: 0 relays                                        |
+------------------------------------------------------------------+

+------------------------------------------------------------------+
| SOFTWARE AND VERSION                                 [#software] |
+------------------------------------------------------------------+
| Platform: Linux (tor 0.4.8.12)                                   |
| Version Status: Recommended                                      |
| Last Changed Address: 2024-01-15                                 |
+------------------------------------------------------------------+

+------------------------------------------------------------------+
| EXIT POLICY                                        [#exit-policy] |
+------------------------------------------------------------------+
| IPv4 Summary: reject *:*                                         |
| IPv6 Summary: reject *:*                                         |
| [Full policy details...]                                         |
+------------------------------------------------------------------+

+------------------------------------------------------------------+
| LOCATION AND NETWORK                                 [#location] |
+------------------------------------------------------------------+
| Country: Germany (DE) | Region: Bavaria | City: Munich           |
| Coordinates: 48.13, 11.58                                        |
| AS: AS24940 (Hetzner Online GmbH)                                |
| View on Interactive Map                                          |
+------------------------------------------------------------------+

+------------------------------------------------------------------+
| PER-AUTHORITY VOTE DETAILS                     [#authority-votes] |
+------------------------------------------------------------------+
| [Detailed table showing per-authority voting information...]     |
| [This is the existing detailed consensus evaluation table]       |
+------------------------------------------------------------------+

+------------------------------------------------------------------+
| OPERATOR INFORMATION                                 [#operator] |
+------------------------------------------------------------------+
| AROI: example.com [View operator page]                           |
| Contact: admin@example.com                                       |
+------------------------------------------------------------------+
```

---

## References

- Gemini 3 Pro Proposal: `docs/RELAY_PAGE_REDESIGN_PROPOSAL.md`
- Opus 4.5 Proposal: `docs/features/planned/relay-page-layout-proposals.md`
- Current Template: `allium/templates/relay-info.html`
- tor-relays Mailing List: https://lists.torproject.org/pipermail/tor-relays/

---

*Document Version: 1.0*
*Created: 2024-12-29*
*Consolidated from Gemini 3 Pro and Opus 4.5 proposals*
