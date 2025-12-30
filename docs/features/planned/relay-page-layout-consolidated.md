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

### 0. Design Decisions (Prerequisites)

Before the 5 improvements, these design decisions address layout and structure:

#### Single Column Width on Desktop

**Problem:** A single narrow column on a wide desktop screen wastes space and looks odd.

**Solution:** Use a fluid-width single column with a maximum width for readability:

```css
/* Single column that fills available width, maxes at readable limit */
.relay-page-content {
    max-width: 1400px;      /* Prevent overly wide lines on 4K monitors */
    width: 100%;            /* Fill available space */
    margin: 0 auto;         /* Center on very wide screens */
    padding: 0 20px;        /* Breathing room on edges */
}

/* Tables and data sections can use full width */
.relay-section {
    width: 100%;
}

/* On narrower screens, use full width */
@media (max-width: 1400px) {
    .relay-page-content {
        max-width: 100%;
    }
}
```

**Why 1400px?** Wide enough for data tables with many columns (like the per-authority table), but not so wide that text becomes hard to scan. Bootstrap's `container-xl` uses 1320px for reference.

#### Relay Identity in Page Header (Not a "Section")

**Problem:** Original proposal put "Operator Information" at position 12 (bottom), but operators need to confirm they're viewing the correct relay immediately.

**Solution:** Relay identity stays in the **page header** (not a numbered section). This is already how the current template works:

```
+==================================================================+
| View Relay "MyRelay"                              [PAGE HEADER]  |
| Fingerprint: ABCD1234EFGH5678...                                 |
| Contact: admin@example.com | AROI: example.com                   |
| Family: 5 relays | AS12345 | Germany | Linux                     |
+==================================================================+
|                                                                  |
| [SECTIONS START HERE - Health Status, Connectivity, etc.]        |
```

**What stays in header:**
- Nickname (large, prominent)
- Fingerprint (full, copyable)
- Contact info (for verification: "yes, this is my relay")
- AROI domain (if set)
- Quick links: Family count, AS, Country, Platform

**What moves to sections below:**
- Detailed family member lists → `#family` section
- Detailed contact parsing → stays in header, no separate section needed

This means "Operator Information" is **removed as a section** - it's in the header where it belongs.

#### Consensus Summary: Removed (Redundant)

**Problem:** The proposed "Consensus Summary" section overlaps significantly with:
- Health Status (consensus status, flags, issues)
- Connectivity (reachability counts)
- Flags (eligibility counts)
- Bandwidth (measured values)

**Analysis of overlap:**

| Data Point | Health Status | Connectivity | Flags | Bandwidth | Consensus Summary |
|------------|---------------|--------------|-------|-----------|-------------------|
| In consensus (Y/N) | Yes | - | - | - | Yes (redundant) |
| Authority vote count | Yes | - | - | - | Yes (redundant) |
| Reachability IPv4/v6 | - | Yes | - | - | Yes (redundant) |
| Current flags | Yes | - | Yes | - | Yes (redundant) |
| Flag eligibility counts | - | - | Yes | - | Yes (redundant) |
| Measured bandwidth | - | - | - | Yes | Yes (redundant) |
| Issues/warnings | Yes | - | - | - | Yes (redundant) |

**Solution:** Remove "Consensus Summary" as a separate section. Its content is distributed to the appropriate sections:

- Consensus status, vote count, issues → **Health Status**
- Reachability counts → **Connectivity**
- Flag eligibility → **Flags**
- Bandwidth measurements → **Bandwidth**

The **Per-Authority Details** table remains as the deep-dive section for advanced troubleshooting.

#### Revised Section List (11 sections, not 12)

| Order | Section | Anchor |
|-------|---------|--------|
| - | Page Header (Identity, Contact, Quick Links) | - |
| 1 | Health Status Summary | `#status` |
| 2 | Connectivity and Addresses | `#connectivity` |
| 3 | Flags and Eligibility | `#flags` |
| 4 | Bandwidth Metrics | `#bandwidth` |
| 5 | Uptime and Stability | `#uptime` |
| 6 | Family Configuration | `#family` |
| 7 | Software and Version | `#software` |
| 8 | Exit Policy | `#exit-policy` |
| 9 | Location and Network | `#location` |
| 10 | Per-Authority Vote Details | `#authority-votes` |

---

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
| - | Page Header (Identity, Contact) | n/a |
| 1 | Health Status Summary | `#status` |
| 2 | Connectivity and Addresses | `#connectivity` |
| 3 | Flags and Eligibility | `#flags` |
| 4 | Bandwidth Metrics | `#bandwidth` |
| 5 | Uptime and Stability | `#uptime` |
| 6 | Family Configuration | `#family` |
| 7 | Software and Version | `#software` |
| 8 | Exit Policy | `#exit-policy` |
| 9 | Location and Network | `#location` |
| 10 | Per-Authority Vote Details | `#authority-votes` |

Note: "Operator Information" moved to Page Header. "Consensus Summary" removed (redundant - data distributed to sections 1-4).

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

**5. Uptime and Stability** - "Why did I lose my Stable/Guard flag?"
- Stable and Guard flags require sustained uptime
- Shows historical uptime percentages (1M/6M/1Y)
- Explains flag loss after restarts or outages
- Mailing list evidence: "I restarted my relay and lost Guard flag"
- Troubleshooting dependency: Explains flag eligibility failures from section 3

**6. Family Configuration** - "Why are my family members showing as 'alleged'?"
- Common misconfiguration: asymmetric family declarations
- Shows effective vs alleged vs indirect family members
- Mailing list evidence: Frequent questions about family setup errors
- Position rationale: Not critical for basic operation, but important for operators running multiple relays

**7. Software and Version** - "Is my Tor version OK?"
- Version issues are less urgent but can affect flags
- Shows recommended/obsolete status
- Position rationale: Usually not the cause of immediate problems, but good to verify
- Mailing list evidence: Occasional "upgrade your Tor" responses

**8. Exit Policy** - "What traffic does my relay allow?"
- Reference information, rarely the cause of troubleshooting issues
- Mostly static configuration data
- Position rationale: Operators know their exit policy; this is for verification

**9. Location and Network** - "Where is my relay located?"
- Geographic and AS information
- Rarely relevant to troubleshooting
- Position rationale: Reference data, not diagnostic

**10. Per-Authority Vote Details** - "Which specific authority is not voting for me?"
- Advanced diagnostics for edge cases
- Detailed per-authority breakdown
- Position rationale: Only needed when Health Status or Flags sections show problems
- Used by experienced operators or when guided by support

**Page Header (not a numbered section)** - "Am I looking at the right relay?"
- Nickname, Fingerprint, Contact, AROI displayed prominently at page top
- Position rationale: Identity verification happens before any troubleshooting
- Always visible without scrolling

#### The Troubleshooting Flow Visualized

```
START: "My relay isn't working"
         │
         ▼
    ┌─────────────────┐
    │ PAGE HEADER     │ ──── "Is this my relay?" (Nickname, Fingerprint, Contact)
    └────────┬────────┘
             │ Yes, this is my relay...
             ▼
    ┌─────────────────┐
    │ 1. HEALTH STATUS│ ──── "In consensus? Running? Any issues?"
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
             │ If flag was lost recently...
             ▼
    ┌─────────────────┐
    │ 5. UPTIME       │ ──── "Did downtime cause flag loss?"
    └────────┬────────┘
             │ Running multiple relays...
             ▼
    ┌─────────────────┐
    │ 6. FAMILY       │ ──── "Is family configured correctly?"
    └────────┬────────┘
             │ Check software version...
             ▼
    ┌─────────────────┐
    │ 7. SOFTWARE     │ ──── "Is my Tor version recommended?"
    └────────┬────────┘
             │
             ▼
    ┌─────────────────────────────────────────┐
    │ 8-10. REFERENCE & ADVANCED              │
    │ Exit Policy, Location, Per-Authority    │
    │ Vote Details (deep diagnostics)         │
    └─────────────────────────────────────────┘
```

#### Current vs Proposed Layout

```
CURRENT (two-column, scattered):        PROPOSED (single-column, flow):
                                  
Header:                                 Header (Identity - always visible):
  - Nickname                              - Nickname (large)
                                          - Fingerprint (full, copyable)
Left Column:                              - Contact / AROI
  - Nickname/Fingerprint                  - Quick links (Family, AS, Country)
  - AROI/Contact          ─┐            
  - Exit Policies          │            Sections (full-width, top-to-bottom):
  - Family                 │              1. Health Status [NEW]
                           │              2. Connectivity + Reachability
Right Column:              │              3. Flags + Eligibility Table
  - Bandwidth              │              4. Bandwidth + Consensus Weight
  - Network Participation  │              5. Uptime/Stability
  - OR/Exit/Dir Addresses  ├─ scattered   6. Family (detailed)
  - Location               │              7. Software/Version
  - Flags                  │              8. Exit Policy
  - Uptime                 │              9. Location/AS
  - Platform/Version      ─┘              10. Per-Authority Details
                                  
Bottom (separate section):
  - Consensus Evaluation (detailed)
```

**Why single-column?** Two-column layouts force users to scan horizontally and make mental connections between scattered data. A linear flow matches how troubleshooting actually works: check one thing, then the next logical thing.

**Why identity in header?** Operators need to confirm they're viewing the correct relay before doing anything else. The header is always visible at the top, and on most screens remains visible while scrolling (or can be quickly scrolled back to).

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
| `#uptime` | Uptime and Stability | High |
| `#authority-votes` | Per-Authority Vote Table | High |
| `#family` | Family Configuration | Medium |
| `#effective-family` | Effective Family Members (existing) | Medium |
| `#alleged-family` | Alleged Family Members (existing) | Medium |
| `#indirect-family` | Indirect Family Members (existing) | Medium |
| `#software` | Platform and Version | Medium |
| `#exit-policy` | Exit Policy (existing) | Low |
| `#ipv4-exit-policy-summary` | IPv4 Exit Policy Summary (existing) | Low |
| `#ipv6-exit-policy-summary` | IPv6 Exit Policy Summary (existing) | Low |
| `#location` | Geographic Location | Low |
| `#relay-summary` | Summary Table (existing) | Low |
| `#consensus-evaluation` | Full Consensus Evaluation (existing, alias for authority-votes) | Low |

Note: Operator/contact info is in the page header, not a separate section. The `#consensus-summary` anchor was removed as that section was merged into Health Status.

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
4. Move Contact/AROI to be more prominent in page header

### Phase 2: Layout Restructure
1. Add Health Status Summary section at top (new section)
2. Reorder sections by troubleshooting priority (see Section 2)
3. Consolidate two-column layout into single-column flow
4. Add CSS for fluid-width single column (max-width: 1400px)
5. Move Fingerprint to header, make full and copyable

### Phase 3: Content Enhancement
1. Add Flag Eligibility table to Flags section (data already available from consensus_evaluation)
2. Improve Issues/Warnings display with actionable advice
3. Move reachability counts from Consensus Evaluation to Connectivity section
4. Ensure Per-Authority Details table is at bottom for advanced users

---

## Complete Item Mapping: Current → Proposed

Every item from the current relay page mapped to the proposed structure:

### Page Header (Identity - Not a Section)

| Current Location | Item | Notes |
|------------------|------|-------|
| Title | Nickname | Large, prominent |
| Left column | Fingerprint | Full, copyable |
| Left column | Contact | Link to contact page |
| Left column | AROI | Link to operator page |
| Header h4 | Family link (count) | Quick link |
| Header h4 | AS link | Quick link |
| Header h4 | Country link | Quick link |
| Header h4 | Platform link | Quick link |
| Header | Last fetch timestamp | Data freshness indicator |

### Section 1: Health Status (`#status`)

| Current Location | Item | Notes |
|------------------|------|-------|
| Consensus Eval | Consensus Status | IN/NOT IN CONSENSUS |
| Consensus Eval | Vote count | X/9 authorities |
| Right column | Flags list | Current active flags |
| Right column | Measured indicator | ✓/✗ → Yes/No text |
| Right column | Uptime/Downtime | UP/DOWN + duration |
| Consensus Eval | Identified Issues | Error/Warning list |
| Consensus Eval | Notes | Info items |

### Section 2: Connectivity (`#connectivity`)

| Current Location | Item | Notes |
|------------------|------|-------|
| Right column | OR Address | With verified/unverified hostnames |
| Right column | Exit Address | If applicable |
| Right column | Dir Address | Link to directory |
| Consensus Eval | IPv4 Reachability | X/9 authorities |
| Consensus Eval | IPv6 Reachability | X/Y testers (if has IPv6) |

### Section 3: Flags and Eligibility (`#flags`)

| Current Location | Item | Notes |
|------------------|------|-------|
| Right column | Flags count + list | With flag icons → text only |
| Consensus Eval | Flag Eligibility summary | Guard/Stable/Fast/HSDir: X/9 |
| Consensus Eval | Running/Valid/V2Dir counts | X/9 each |
| Summary Table | Guard WFU (value vs threshold) | From consensus eval |
| Summary Table | Guard TK (value vs threshold) | From consensus eval |
| Summary Table | Guard BW (value vs threshold) | From consensus eval |
| Summary Table | Stable Uptime (value vs threshold) | From consensus eval |
| Summary Table | Stable MTBF (value vs threshold) | From consensus eval |
| Summary Table | Fast Speed (value vs threshold) | From consensus eval |
| Summary Table | HSDir WFU (value vs threshold) | From consensus eval |
| Summary Table | HSDir TK (value vs threshold) | From consensus eval |

### Section 4: Bandwidth (`#bandwidth`)

| Current Location | Item | Notes |
|------------------|------|-------|
| Right column | Observed Bandwidth | Self-reported |
| Right column | Advertised Bandwidth | Min of rate/burst/observed |
| Right column | Rate Limit | Configured limit |
| Right column | Burst Limit | Configured burst |
| Right column | Measured indicator | By bandwidth authorities |
| Right column | Consensus Weight % | Network participation |
| Right column | Guard Probability % | Position probability |
| Right column | Middle Probability % | Position probability |
| Right column | Exit Probability % | Position probability |
| Right column | Underutilized warning | If applicable |
| Consensus Eval | Authority Measured BW | Median/Min/Max |
| Summary Table | Consensus Weight row | From consensus eval |

### Section 5: Uptime and Stability (`#uptime`)

| Current Location | Item | Notes |
|------------------|------|-------|
| Right column | Flag Uptime (1M/6M/1Y/5Y) | Role-specific uptime |
| Right column | Uptime (1M/6M/1Y/5Y) | Overall uptime |
| Right column | Uptime/Downtime | Current UP/DOWN + duration |
| Right column | First Seen | With link to date page |
| Right column | Last Seen | Timestamp |
| Right column | Last Restarted | Timestamp |
| Right column | Hibernating | Yes/No |

### Section 6: Family Configuration (`#family`)

| Current Location | Item | Notes |
|------------------|------|-------|
| Left column | Effective Family count | With "View" link |
| Left column | Effective Family list | Fingerprint links |
| Left column | Alleged Family count | They don't list you back |
| Left column | Alleged Family list | Fingerprint links |
| Left column | Indirect Family count | They list you, you don't list them |
| Left column | Indirect Family list | Fingerprint links |

### Section 7: Software and Version (`#software`)

| Current Location | Item | Notes |
|------------------|------|-------|
| Right column | Platform (Short) | Link to platform page |
| Right column | Platform (Long/Raw) | Full platform string |
| Right column | Version | Running version |
| Right column | Recommended | Yes/No |
| Right column | Version Status | recommended/obsolete/etc |
| Right column | Last Changed Address or Port | Timestamp |

### Section 8: Exit Policy (`#exit-policy`)

| Current Location | Item | Notes |
|------------------|------|-------|
| Left column | IPv4 Exit Policy Summary | accept/reject summary |
| Left column | IPv6 Exit Policy Summary | accept/reject summary |
| Left column | Exit Policy (full) | Complete policy list |

### Section 9: Location and Network (`#location`)

| Current Location | Item | Notes |
|------------------|------|-------|
| Right column | City | If available |
| Right column | Region | If available |
| Right column | Country | With flag icon and link |
| Right column | Latitude | Coordinates |
| Right column | Longitude | Coordinates |
| Right column | Interactive Map link | External link |
| Right column | AS Number | With link to AS page |
| Right column | AS Name | With BGP.tools link |

### Section 10: Per-Authority Vote Details (`#authority-votes`)

| Current Location | Item | Notes |
|------------------|------|-------|
| Consensus Eval | Summary Table header | "Your Relay vs Consensus" |
| Consensus Eval | Summary Table (full) | All metrics with thresholds |
| Consensus Eval | Per-Authority Details table | Full voting breakdown |
| Consensus Eval | Bandwidth Values Explained | Info box |
| Consensus Eval | Stable Uptime Explained | Info box |
| Consensus Eval | Data source attribution | CollecTor link |

---

## Proposed Page Structure: Desktop Wireframe (max-width: 1400px)

Two columns inside each section to maximize information density on wide screens.

```
╔══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                              PAGE HEADER                                                             ║
║  View Relay "MyRelay"                                                                                                ║
║  Fingerprint: ABCD1234EFGH5678IJKL9012MNOP3456QRST7890UVWX                                            [Copy Button]  ║
║  Contact: admin@example.com                              AROI: example.com [View Operator Page]                      ║
║  ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────── ║
║  Family: 5 relays | AS24940 | Germany | Linux                                     Last updated: 2024-12-29 14:30 UTC ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════╝

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ HEALTH STATUS                                                                                              [#status] ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Consensus Status                                    ┃ Current Flags                                                   ┃
┃   IN CONSENSUS (9/9 authorities)                    ┃   Guard, Stable, Fast, Valid, Running, V2Dir, HSDir             ┃
┃                                                     ┃                                                                  ┃
┃ Running Status                                      ┃ Bandwidth Measured                                              ┃
┃   UP for 47 days (since 2024-11-12)                 ┃   Yes (by 6 bandwidth authorities)                              ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Issues: None detected                                                                                                ┃
┃   -or-                                                                                                               ┃
┃ Issues:                                                                                                              ┃
┃   [Warning] IPv6 reachability partial - 3/5 authorities can reach IPv6                                               ┃
┃             Suggestion: Check IPv6 firewall rules, ensure port 9001 is open for IPv6                                 ┃
┃   [Error] Version is obsolete - upgrade recommended                                                                  ┃
┃             Suggestion: Upgrade to latest stable Tor version                                                         ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ CONNECTIVITY                                                                                        [#connectivity] ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ OR Address                                          ┃ Reachability (per Directory Authorities)                        ┃
┃   relay.example.com (verified)                      ┃                                                                  ┃
┃   192.0.2.1:9001                                    ┃   IPv4: 9/9 authorities                                          ┃
┃   [2001:db8::1]:9001                                ┃   IPv6: 3/5 testers (4 authorities don't test IPv6)             ┃
┃                                                     ┃                                                                  ┃
┃ Exit Address                                        ┃                                                                  ┃
┃   none                                              ┃                                                                  ┃
┃                                                     ┃                                                                  ┃
┃ Dir Address                                         ┃                                                                  ┃
┃   192.0.2.1:9030                                    ┃                                                                  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ FLAGS AND ELIGIBILITY                                                                                      [#flags] ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Current Flags: Guard, Stable, Fast, Valid, Running, V2Dir, HSDir                                                     ┃
┃ Eligibility:   Guard 9/9 | Stable 9/9 | Fast 9/9 | HSDir 9/9 | Running 9/9 | Valid 9/9 | V2Dir 9/9                   ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Flag Requirements (Your Value vs Threshold)                                                                          ┃
┃ ┌──────────────┬─────────────────────┬─────────────────────────────────────────┬─────────────────────────────────┐   ┃
┃ │ Flag         │ Your Value          │ Threshold Required                      │ Status                          │   ┃
┃ ├──────────────┼─────────────────────┼─────────────────────────────────────────┼─────────────────────────────────┤   ┃
┃ │ Guard        │ WFU: 99.2%          │ >=98% (all authorities)                 │ Meets                           │   ┃
┃ │              │ TK: 45 days         │ >=8 days (all authorities)              │ Meets                           │   ┃
┃ │              │ BW: 125 Mbit/s      │ >=2 MB/s OR top 25%                     │ Meets (>=2 MB/s guarantee)      │   ┃
┃ ├──────────────┼─────────────────────┼─────────────────────────────────────────┼─────────────────────────────────┤   ┃
┃ │ Stable       │ MTBF: 30 days       │ >=5-7 days (varies by authority)        │ Meets - all authorities         │   ┃
┃ │              │ Uptime: 47 days     │ >=5-7 days (varies by authority)        │ Meets - all authorities         │   ┃
┃ ├──────────────┼─────────────────────┼─────────────────────────────────────────┼─────────────────────────────────┤   ┃
┃ │ Fast         │ Speed: 125 Mbit/s   │ >=100 KB/s (guarantee) OR top 7/8       │ Meets (>=100 KB/s guarantee)    │   ┃
┃ ├──────────────┼─────────────────────┼─────────────────────────────────────────┼─────────────────────────────────┤   ┃
┃ │ HSDir        │ WFU: 99.2%          │ >=98% (all authorities)                 │ Meets                           │   ┃
┃ │              │ TK: 45 days         │ >=25 hours (most) / 10 days (moria1)    │ Meets                           │   ┃
┃ └──────────────┴─────────────────────┴─────────────────────────────────────────┴─────────────────────────────────┘   ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ BANDWIDTH                                                                                              [#bandwidth] ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Relay-Reported Bandwidth                            ┃ Network Participation                                           ┃
┃                                                     ┃                                                                  ┃
┃   Observed:    125 Mbit/s                           ┃   Consensus Weight:  0.15%                                       ┃
┃   Advertised:  100 Mbit/s                           ┃   Guard Probability: 0.12%                                       ┃
┃   Rate Limit:  150 Mbit/s                           ┃   Middle Probability: 0.18%                                      ┃
┃   Burst Limit: 200 Mbit/s                           ┃   Exit Probability:  0.00%                                       ┃
┃                                                     ┃                                                                  ┃
┃ Authority-Measured Bandwidth                        ┃                                                                  ┃
┃                                                     ┃                                                                  ┃
┃   Measured: Yes (by 6 authorities)                  ┃                                                                  ┃
┃   Median: 98 Mbit/s                                 ┃                                                                  ┃
┃   Min: 95 Mbit/s | Max: 102 Mbit/s                  ┃                                                                  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ UPTIME AND STABILITY                                                                                      [#uptime] ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Current Status                                      ┃ Historical Uptime                                               ┃
┃                                                     ┃                                                                  ┃
┃   Status: UP for 47 days                            ┃   Flag Uptime (1M/6M/1Y/5Y):                                     ┃
┃   Last Restarted: 2024-11-12 (47 days ago)          ┃     99.2% / 98.5% / 97.1% / N/A                                  ┃
┃   Hibernating: No                                   ┃                                                                  ┃
┃                                                     ┃   Overall Uptime (1M/6M/1Y/5Y):                                  ┃
┃ First/Last Seen                                     ┃     99.1% / 98.2% / 96.8% / N/A                                  ┃
┃                                                     ┃                                                                  ┃
┃   First Seen: 2023-06-01 (1.5 years ago)            ┃                                                                  ┃
┃   Last Seen: 2024-12-29 14:30 (now)                 ┃                                                                  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ FAMILY CONFIGURATION                                                                                      [#family] ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Effective Family: 5 relays [View Family Page]       ┃ Alleged Family: 2 relays                                        ┃
┃                                                     ┃   (They don't list you back - check their MyFamily config)      ┃
┃   ABCD1234EFGH5678... (this relay)                  ┃                                                                  ┃
┃   WXYZ9876LMNO5432...                               ┃   QRST1111UVWX2222...                                            ┃
┃   HIJK4567DEFG8901...                               ┃   MNOP3333STUV4444...                                            ┃
┃   STUV2345WXYZ6789...                               ┃                                                                  ┃
┃   EFGH8901IJKL2345...                               ┃ Indirect Family: 0 relays                                       ┃
┃                                                     ┃   (They list you, but you don't list them)                      ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ SOFTWARE AND VERSION                                                                                    [#software] ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Platform                                            ┃ Version                                                         ┃
┃                                                     ┃                                                                  ┃
┃   Short: Linux                                      ┃   Running: 0.4.8.12                                              ┃
┃   Full: Tor 0.4.8.12 on Linux                       ┃   Recommended: Yes                                               ┃
┃                                                     ┃   Status: recommended                                            ┃
┃ Address Changes                                     ┃                                                                  ┃
┃                                                     ┃                                                                  ┃
┃   Last Changed: 2024-01-15                          ┃                                                                  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ EXIT POLICY                                                                                          [#exit-policy] ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ IPv4 Exit Policy Summary                            ┃ IPv6 Exit Policy Summary                                        ┃
┃                                                     ┃                                                                  ┃
┃   reject: *:*                                       ┃   reject: *:*                                                    ┃
┃   (This is a non-exit relay)                        ┃   (This is a non-exit relay)                                     ┃
┃                                                     ┃                                                                  ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Full Exit Policy [Expandable]                                                                                        ┃
┃   reject *:*                                                                                                         ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ LOCATION AND NETWORK                                                                                    [#location] ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Geographic Location                                 ┃ Autonomous System                                               ┃
┃                                                     ┃                                                                  ┃
┃   Country: Germany (DE)                             ┃   AS Number: AS24940                                             ┃
┃   Region: Bavaria                                   ┃   AS Name: Hetzner Online GmbH                                   ┃
┃   City: Munich                                      ┃   BGP.tools                                                      ┃
┃                                                     ┃                                                                  ┃
┃   Coordinates: 48.13, 11.58                         ┃                                                                  ┃
┃   View on Interactive Map                           ┃                                                                  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ PER-AUTHORITY VOTE DETAILS                                                                        [#authority-votes] ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Data from Tor CollecTor (authority votes, fetched 2024-12-29 14:00 UTC)                                              ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Summary: Your Relay vs Consensus Thresholds                                                           [#relay-summary]┃
┃ ┌────────────────────┬─────────────────────┬──────────────────────────────┬──────────────────────────────────────┐    ┃
┃ │ Metric             │ Your Value          │ Threshold                    │ Status                               │    ┃
┃ ├────────────────────┼─────────────────────┼──────────────────────────────┼──────────────────────────────────────┤    ┃
┃ │ In Consensus       │ 9/9 authorities     │ >=5/9 (majority)             │ IN CONSENSUS                         │    ┃
┃ │ Running            │ 9/9 authorities     │ >=5/9 (majority)             │ RUNNING                              │    ┃
┃ │ Valid              │ 9/9 authorities     │ >=5/9 (majority)             │ VALID                                │    ┃
┃ │ Consensus Weight   │ 98 KB/s (median)    │ N/A                          │ -                                    │    ┃
┃ │ Guard WFU          │ 99.2%               │ >=98%                        │ MEETS                                │    ┃
┃ │ Guard TK           │ 45 days             │ >=8 days                     │ MEETS                                │    ┃
┃ │ Guard BW           │ 125 Mbit/s          │ >=2 MB/s OR top 25%          │ MEETS                                │    ┃
┃ │ ... (more rows)    │                     │                              │                                      │    ┃
┃ └────────────────────┴─────────────────────┴──────────────────────────────┴──────────────────────────────────────┘    ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Per-Authority Voting Details (for advanced troubleshooting)                                                          ┃
┃ ┌───────────┬────────┬───────┬────────┬────┬────┬─────────────────────┬───────────┬────────────┬─────────┬─────────┐ ┃
┃ │ Authority │ Running│ Valid │ BW Scan│ v4 │ v6 │ Flags               │ Fast      │ Guard BW   │ Guard   │ Cons Wt │ ┃
┃ │           │        │       │        │    │    │                     │ (R|T)     │ (R|T)      │ WFU/TK  │         │ ┃
┃ ├───────────┼────────┼───────┼────────┼────┼────┼─────────────────────┼───────────┼────────────┼─────────┼─────────┤ ┃
┃ │ moria1    │ Yes    │ Yes   │ Y      │ Yes│ Yes│ Guard Stable Fast...│ 125M|100K │ 125M|2M    │ 99%|98% │ 98 KB/s │ ┃
┃ │ tor26     │ Yes    │ Yes   │ Y      │ Yes│ -  │ Guard Stable Fast...│ 125M|100K │ 125M|2M    │ 99%|98% │ 97 KB/s │ ┃
┃ │ ... (7 more authorities)                                                                                           │ ┃
┃ └───────────┴────────┴───────┴────────┴────┴────┴─────────────────────┴───────────┴────────────┴─────────┴─────────┘ ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ [Info Box] Bandwidth Values Explained:                                                                               ┃
┃   Relay Reported = Self-reported from descriptor (for flag eligibility)                                              ┃
┃   Authority Measured = Measured by sbws scanner (for consensus weight/path selection)                                ┃
┃                                                                                                                      ┃
┃ [Info Box] Stable Uptime (Two Data Sources):                                                                         ┃
┃   Relay Uptime = From Onionoo API (last_restarted)                                                                   ┃
┃   Authority Threshold = From CollecTor vote files (flag-thresholds)                                                  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

---

## Proposed Page Structure: Mobile Wireframe (single column, <768px)

Single column layout for narrow screens. All content stacks vertically.

```
╔═══════════════════════════════════════════╗
║            PAGE HEADER                    ║
║  View Relay "MyRelay"                     ║
║                                           ║
║  Fingerprint:                             ║
║  ABCD1234EFGH5678IJKL9012MN...   [Copy]   ║
║                                           ║
║  Contact: admin@example.com               ║
║  AROI: example.com                        ║
║                                           ║
║  Family: 5 | AS24940 | DE | Linux         ║
║  Updated: 2024-12-29 14:30 UTC            ║
╚═══════════════════════════════════════════╝

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ HEALTH STATUS                   [#status] ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Consensus Status                          ┃
┃   IN CONSENSUS (9/9 authorities)          ┃
┃                                           ┃
┃ Running Status                            ┃
┃   UP for 47 days (since 2024-11-12)       ┃
┃                                           ┃
┃ Current Flags                             ┃
┃   Guard, Stable, Fast, Valid,             ┃
┃   Running, V2Dir, HSDir                   ┃
┃                                           ┃
┃ Bandwidth Measured                        ┃
┃   Yes (by 6 bandwidth authorities)        ┃
┃                                           ┃
┃ Issues                                    ┃
┃   None detected                           ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ CONNECTIVITY           [#connectivity]    ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ OR Address                                ┃
┃   relay.example.com (verified)            ┃
┃   192.0.2.1:9001                          ┃
┃   [2001:db8::1]:9001                      ┃
┃                                           ┃
┃ Exit Address                              ┃
┃   none                                    ┃
┃                                           ┃
┃ Dir Address                               ┃
┃   192.0.2.1:9030                          ┃
┃                                           ┃
┃ Reachability                              ┃
┃   IPv4: 9/9 authorities                   ┃
┃   IPv6: 3/5 testers                       ┃
┃         (4 don't test IPv6)               ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ FLAGS AND ELIGIBILITY          [#flags]   ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Current Flags                             ┃
┃   Guard, Stable, Fast, Valid,             ┃
┃   Running, V2Dir, HSDir                   ┃
┃                                           ┃
┃ Eligibility                               ┃
┃   Guard: 9/9  | Stable: 9/9               ┃
┃   Fast: 9/9   | HSDir: 9/9                ┃
┃   Running: 9/9 | Valid: 9/9               ┃
┃                                           ┃
┃ Flag Requirements                         ┃
┃ ┌─────────┬──────────┬─────────┐          ┃
┃ │ Flag    │ You│Req  │ Status  │          ┃
┃ ├─────────┼──────────┼─────────┤          ┃
┃ │ Guard   │          │         │          ┃
┃ │  WFU    │99%│>=98% │ Meets   │          ┃
┃ │  TK     │45d│>=8d  │ Meets   │          ┃
┃ │  BW     │125M│>=2M │ Meets   │          ┃
┃ ├─────────┼──────────┼─────────┤          ┃
┃ │ Stable  │          │         │          ┃
┃ │  MTBF   │30d│>=5d  │ Meets   │          ┃
┃ │  Uptime │47d│>=5d  │ Meets   │          ┃
┃ ├─────────┼──────────┼─────────┤          ┃
┃ │ Fast    │125M│>=100K│ Meets  │          ┃
┃ ├─────────┼──────────┼─────────┤          ┃
┃ │ HSDir   │          │         │          ┃
┃ │  WFU    │99%│>=98% │ Meets   │          ┃
┃ │  TK     │45d│>=25h │ Meets   │          ┃
┃ └─────────┴──────────┴─────────┘          ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ BANDWIDTH                  [#bandwidth]   ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Relay-Reported                            ┃
┃   Observed:   125 Mbit/s                  ┃
┃   Advertised: 100 Mbit/s                  ┃
┃   Rate Limit: 150 Mbit/s                  ┃
┃   Burst:      200 Mbit/s                  ┃
┃                                           ┃
┃ Authority-Measured                        ┃
┃   Measured: Yes (6 authorities)           ┃
┃   Median: 98 Mbit/s                       ┃
┃   Min: 95 | Max: 102 Mbit/s               ┃
┃                                           ┃
┃ Network Participation                     ┃
┃   Consensus Weight: 0.15%                 ┃
┃   Guard Prob:       0.12%                 ┃
┃   Middle Prob:      0.18%                 ┃
┃   Exit Prob:        0.00%                 ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ UPTIME AND STABILITY         [#uptime]    ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Current Status                            ┃
┃   Status: UP for 47 days                  ┃
┃   Last Restarted: 2024-11-12              ┃
┃   Hibernating: No                         ┃
┃                                           ┃
┃ Historical Uptime                         ┃
┃   Flag Uptime (1M/6M/1Y/5Y):              ┃
┃     99.2% / 98.5% / 97.1% / N/A           ┃
┃                                           ┃
┃   Overall Uptime (1M/6M/1Y/5Y):           ┃
┃     99.1% / 98.2% / 96.8% / N/A           ┃
┃                                           ┃
┃ First/Last Seen                           ┃
┃   First: 2023-06-01 (1.5y ago)            ┃
┃   Last:  2024-12-29 14:30 (now)           ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ FAMILY CONFIGURATION          [#family]   ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Effective Family: 5 relays                ┃
┃   [View Family Page]                      ┃
┃   ABCD1234... (this relay)                ┃
┃   WXYZ9876...                             ┃
┃   HIJK4567...                             ┃
┃   STUV2345...                             ┃
┃   EFGH8901...                             ┃
┃                                           ┃
┃ Alleged Family: 2 relays                  ┃
┃   (They don't list you back)              ┃
┃   QRST1111...                             ┃
┃   MNOP3333...                             ┃
┃                                           ┃
┃ Indirect Family: 0 relays                 ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ SOFTWARE AND VERSION        [#software]   ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Platform                                  ┃
┃   Short: Linux                            ┃
┃   Full: Tor 0.4.8.12 on Linux             ┃
┃                                           ┃
┃ Version                                   ┃
┃   Running: 0.4.8.12                       ┃
┃   Recommended: Yes                        ┃
┃   Status: recommended                     ┃
┃                                           ┃
┃ Address Changes                           ┃
┃   Last Changed: 2024-01-15                ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ EXIT POLICY               [#exit-policy]  ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ IPv4 Exit Policy Summary                  ┃
┃   reject: *:*                             ┃
┃   (This is a non-exit relay)              ┃
┃                                           ┃
┃ IPv6 Exit Policy Summary                  ┃
┃   reject: *:*                             ┃
┃                                           ┃
┃ Full Exit Policy [Tap to expand]          ┃
┃   reject *:*                              ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ LOCATION AND NETWORK        [#location]   ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Geographic Location                       ┃
┃   Country: Germany (DE)                   ┃
┃   Region: Bavaria                         ┃
┃   City: Munich                            ┃
┃   Coordinates: 48.13, 11.58               ┃
┃   View on Interactive Map                 ┃
┃                                           ┃
┃ Autonomous System                         ┃
┃   AS Number: AS24940                      ┃
┃   AS Name: Hetzner Online GmbH            ┃
┃   BGP.tools                               ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ PER-AUTHORITY DETAILS  [#authority-votes] ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Data from Tor CollecTor                   ┃
┃ (fetched 2024-12-29 14:00 UTC)            ┃
┃                                           ┃
┃ Summary Table [Tap to expand]             ┃
┃   In Consensus: 9/9 - IN CONSENSUS        ┃
┃   Running: 9/9 - RUNNING                  ┃
┃   Valid: 9/9 - VALID                      ┃
┃   Consensus Weight: 98 KB/s               ┃
┃   Guard WFU: 99.2% >= 98% - MEETS         ┃
┃   Guard TK: 45d >= 8d - MEETS             ┃
┃   ... (more metrics)                      ┃
┃                                           ┃
┃ Per-Authority Table                       ┃
┃   [Horizontal scroll on mobile]           ┃
┃ ┌────────┬─────┬─────┬────┬────┬────────┐ ┃
┃ │Auth    │Run  │Valid│v4  │v6  │Flags   │ ┃
┃ ├────────┼─────┼─────┼────┼────┼────────┤ ┃
┃ │moria1  │Yes  │Yes  │Yes │Yes │Guard...│ ┃
┃ │tor26   │Yes  │Yes  │Yes │-   │Guard...│ ┃
┃ │dizum   │Yes  │Yes  │Yes │Yes │Guard...│ ┃
┃ │...     │     │     │    │    │        │ ┃
┃ └────────┴─────┴─────┴────┴────┴────────┘ ┃
┃   [Scroll right for more columns →]       ┃
┃                                           ┃
┃ Info: Bandwidth Values Explained          ┃
┃   [Tap to expand]                         ┃
┃                                           ┃
┃ Info: Stable Uptime Sources               ┃
┃   [Tap to expand]                         ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
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
