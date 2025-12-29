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

| Order | Section | Anchor | Why This Position |
|-------|---------|--------|-------------------|
| 1 | Health Status Summary | `#status` | Answers "is it working?" |
| 2 | Connectivity and Addresses | `#connectivity` | Check network reachability |
| 3 | Flags and Eligibility | `#flags` | Second most common issue |
| 4 | Bandwidth Metrics | `#bandwidth` | Consensus weight concerns |
| 5 | Consensus Evaluation Summary | `#consensus-summary` | Quick diagnostic overview |
| 6 | Uptime and Stability | `#uptime` | Why flags might be missing |
| 7 | Family Configuration | `#family` | Common misconfiguration |
| 8 | Software and Version | `#software` | Version-related issues |
| 9 | Exit Policy | `#exit-policy` | Reference data |
| 10 | Location and Network | `#location` | Reference data |
| 11 | Per-Authority Vote Details | `#authority-votes` | Advanced diagnostics |
| 12 | Operator Information | `#operator` | Contact/AROI |

**Current vs Proposed Flow:**

```
CURRENT (scattered):              PROPOSED (troubleshooting flow):
                                  
Left Column:                      Top-to-Bottom:
  - Nickname/Fingerprint            1. Health Status [NEW]
  - AROI/Contact                    2. Connectivity (OR/Exit/Dir addresses)
  - Exit Policies                   3. Flags + Eligibility Table
  - Family                          4. Bandwidth (observed/advertised/measured)
                                    5. Consensus Evaluation Summary
Right Column:                       6. Uptime/Stability metrics
  - Bandwidth                       7. Family configuration
  - Network Participation           8. Software/Version
  - OR/Exit/Dir Addresses           9. Exit Policy
  - Location                        10. Location/AS
  - Flags                           11. Per-Authority Details (collapsed)
  - Uptime                          12. Operator info
  - Platform/Version                
                                  
Bottom:                           
  - Consensus Evaluation          
```

**Rationale:** Linear troubleshooting flow from "basic connectivity" to "advanced diagnostics."

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
