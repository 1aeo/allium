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
- **Primary operator link (AROI or Family):**
  - If AROI present: Show AROI domain as primary link (more accurate operator grouping)
  - If no AROI: Show Family count as primary link (fingerprint-based grouping)
- Quick links: AS, Country, Platform

**AROI vs Family Priority:**
- AROI provides verified operator identity with more accurate relay grouping
- Family is fingerprint-based and can have mismatches (alleged/indirect)
- When AROI is present, it supersedes Family as the primary "see all my relays" link
- Family link still appears in the Family section for detailed breakdown

**What moves to sections below:**
- Detailed family member lists → `#family` section
- Detailed contact parsing → stays in header, no separate section needed

This means operator identity info is in the header where it belongs, not buried in a separate section.

#### Why No Separate "Consensus Summary" Section?

Consensus summary data is distributed across the relevant sections rather than duplicated in a separate summary:

| Data Point | Shown In Section |
|------------|------------------|
| In consensus (Y/N) | Health Status |
| Authority vote count | Health Status |
| Reachability IPv4/v6 | Connectivity and Location |
| Current flags | Health Status, Flags |
| Flag eligibility counts | Flags |
| Measured bandwidth | Bandwidth |
| Issues/warnings | Health Status |

The **Per-Authority Details** table (section 9) provides the detailed per-authority breakdown for advanced troubleshooting.

#### Section List

| Order | Section | Anchor |
|-------|---------|--------|
| - | Page Header (Identity, Contact, Quick Links) | - |
| 1 | Health Status Summary | `#status` |
| 2 | Connectivity and Location | `#connectivity` |
| 3 | Flags and Eligibility | `#flags` |
| 4 | Bandwidth Metrics | `#bandwidth` |
| 5 | Uptime and Stability | `#uptime` |
| 6 | Operator and Family | `#operator` |
| 7 | Software and Version | `#software` |
| 8 | Exit Policy | `#exit-policy` |
| 9 | Per-Authority Vote Details | `#authority-votes` |


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
| 2 | Connectivity and Location | `#connectivity` |
| 3 | Flags and Eligibility | `#flags` |
| 4 | Bandwidth Metrics | `#bandwidth` |
| 5 | Uptime and Stability | `#uptime` |
| 6 | Operator and Family | `#operator` |
| 7 | Software and Version | `#software` |
| 8 | Exit Policy | `#exit-policy` |
| 9 | Per-Authority Vote Details | `#authority-votes` |


#### Detailed Ordering Rationale

The ordering follows a **troubleshooting decision tree** - each section answers questions that logically lead to the next:

**1. Health Status Summary** - "Is my relay working at all?"
- This is the first question every operator asks
- If the answer is "yes, everything fine" - operator can stop here
- If "no" or "partially" - they continue down the page to diagnose
- Mailing list evidence: Nearly every troubleshooting thread starts with "my relay is/isn't in consensus"

**2. Connectivity and Location** - "Can the network reach my relay? Where is it?"
- Combines addresses + reachability + AS info + geographic location in one section
- If relay is NOT in consensus, the first thing to check is reachability
- Shows OR port, Dir port, IPv4/IPv6 reachability status
- Also shows AS number (relevant for ISP/network troubleshooting) and geographic location
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

**6. Operator and Family** - "Who runs this relay? What other relays do they operate?"
- Shows AROI domain and relay count (when present) - verified operator identity
- Shows Family breakdown: effective vs alleged vs indirect members
- Common misconfiguration: asymmetric family declarations ("alleged" members)
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

**9. Per-Authority Vote Details** - "Which specific authority is not voting for me?"
- Advanced diagnostics for edge cases
- Detailed per-authority breakdown (the table with all 9 authorities)
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
    │ 2. CONNECTIVITY │ ──── "Can authorities reach my ports? What AS/location?"
    │    & LOCATION   │      (addresses, reachability, AS, country)
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
    │ 6. OPERATOR &   │ ──── "Who runs this? Is family configured correctly?"
    │    FAMILY       │      (AROI verified identity + fingerprint-based family)
    └────────┬────────┘
             │ Check software version...
             ▼
    ┌─────────────────┐
    │ 7. SOFTWARE     │ ──── "Is my Tor version recommended?"
    └────────┬────────┘
             │
             ▼
    ┌─────────────────────────────────────────┐
    │ 8-9. REFERENCE & ADVANCED               │
    │ Exit Policy, Per-Authority Vote Details │
    │ (deep diagnostics - no duplicate tables)│
    └─────────────────────────────────────────┘
```

#### Current vs Proposed Layout

```
CURRENT (two-column, scattered):        PROPOSED (single-column, flow):
                                  
Header:                                 Header (Identity - always visible):
  - Nickname                              - Nickname (large)
                                          - Fingerprint (full, copyable)
Left Column:                              - Contact
  - Nickname/Fingerprint                  - Operator (AROI) or Family link
  - AROI/Contact          ─┐            
  - Exit Policies          │            Sections (full-width, top-to-bottom):
  - Family                 │              1. Health Status
                           │              2. Connectivity & Location
Right Column:              │              3. Flags + Eligibility Table
  - Bandwidth              │              4. Bandwidth + Consensus Weight
  - Network Participation  │              5. Uptime/Stability
  - OR/Exit/Dir Addresses  ├─ scattered   6. Operator & Family
  - Location               │              7. Software/Version
  - Flags                  │              8. Exit Policy
  - Uptime                 │              9. Per-Authority Details
  - Platform/Version      ─┘
                                  
Bottom (separate section):
  - Consensus Evaluation (detailed)
```

**Why single-column?** Two-column layouts force users to scan horizontally and make mental connections between scattered data. A linear flow matches how troubleshooting actually works: check one thing, then the next logical thing.

**Why identity in header?** Operators need to confirm they're viewing the correct relay before doing anything else. The header is always visible at the top.

**Why Connectivity and Location together?** AS number is troubleshooting-relevant (ISP blocks, network issues). IP addresses without their network/geographic context is incomplete. All "where is this relay on the network" info belongs together.

**Why Operator and Family together?** Both answer "who runs this relay and what other relays do they operate?" AROI provides verified operator identity; Family provides fingerprint-based grouping. Showing both together reveals the relationship and any discrepancies.

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
| `#connectivity` | Connectivity and Location | High |
| `#flags` | Flags and Eligibility | High |
| `#bandwidth` | Bandwidth Metrics | High |
| `#uptime` | Uptime and Stability | High |
| `#operator` | Operator and Family | Medium |
| `#authority-votes` | Per-Authority Vote Table | High |
| `#effective-family` | Effective Family Members (within #operator) | Medium |
| `#alleged-family` | Alleged Family Members (within #operator) | Medium |
| `#indirect-family` | Indirect Family Members (within #operator) | Medium |
| `#software` | Platform and Version | Medium |
| `#exit-policy` | Exit Policy (existing) | Low |
| `#ipv4-exit-policy-summary` | IPv4 Exit Policy Summary (existing) | Low |
| `#ipv6-exit-policy-summary` | IPv6 Exit Policy Summary (existing) | Low |

**Backward-Compatible Aliases:**
- `#family` → redirects to `#operator`
- `#consensus-evaluation` → redirects to `#authority-votes`

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
4. Move Contact to page header, make AROI primary link when present

### Phase 2: Layout Restructure
1. Add Health Status Summary section at top (new section)
2. Merge addresses + reachability + AS + geo into **"Connectivity and Location"** section (`#connectivity`)
3. Merge AROI + Family into **"Operator and Family"** section (`#operator`)
4. Reorder sections by troubleshooting priority (9 sections total)
5. Consolidate two-column layout into single-column flow (with 2-col inside sections on desktop)
6. Add CSS for fluid-width single column (max-width: 1400px)
7. Move Fingerprint to header, make full and copyable

### Phase 3: Content Enhancement
1. Add Flag Eligibility table to Flags section (data already available from consensus_evaluation)
2. Improve Issues/Warnings display with actionable advice
3. **Remove** "Summary: Your Relay vs Consensus" table (duplicate of sections 1, 3, 4)
4. Keep Per-Authority Details table for advanced troubleshooting
5. Add backward-compatible anchor aliases (`#network` → `#connectivity`, `#family` → `#operator`, `#location` → `#connectivity`)

---

## Complete Item Mapping: Current → Proposed

Every item from the current relay page mapped to the proposed structure:

### Page Header (Identity - Not a Section)

| Current Location | Item | Notes |
|------------------|------|-------|
| Title | Nickname | Large, prominent |
| Left column | Fingerprint | Full, copyable |
| Left column | Contact | Link to contact page |
| Left column | AROI | **Primary operator link when present** |
| Header h4 | Family link (count) | **Fallback when no AROI** |
| Header h4 | AS link | Quick link |
| Header h4 | Country link | Quick link |
| Header h4 | Platform link | Quick link |
| Header | Last fetch timestamp | Data freshness indicator |

**AROI vs Family Priority Logic:**
- **If AROI present:** Show "Operator: {domain} ({count} relays)" as primary link
  - AROI provides verified operator identity
  - More accurate relay count (all relays by this operator)
  - Links to operator page with full relay list
- **If no AROI:** Show "Family: {count} relays" as primary link
  - Fingerprint-based family grouping
  - May include alleged/indirect mismatches
  - Links to family page

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

### Section 2: Connectivity and Location (`#connectivity`)

| Current Location | Item | Notes |
|------------------|------|-------|
| Right column | OR Address | With verified/unverified hostnames |
| Right column | Exit Address | If applicable |
| Right column | Dir Address | Link to directory |
| Consensus Eval | IPv4 Reachability | X/9 authorities |
| Consensus Eval | IPv6 Reachability | X/Y testers (if has IPv6) |
| Right column | City | If available |
| Right column | Region | If available |
| Right column | Country | With flag icon and link |
| Right column | Latitude | Coordinates |
| Right column | Longitude | Coordinates |
| Right column | Interactive Map link | External link |
| Right column | AS Number | With link to AS page |
| Right column | AS Name | With BGP.tools link |

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

### Section 6: Operator and Family (`#operator`)

| Current Location | Item | Notes |
|------------------|------|-------|
| Left column | AROI domain | Verified operator identifier (when present) |
| Left column | AROI relay count | All relays by this operator |
| Left column | AROI validation status | Validated vs unvalidated |
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

### Section 9: Per-Authority Vote Details (`#authority-votes`)

| Current Location | Item | Notes |
|------------------|------|-------|
| Consensus Eval | Per-Authority Details table | Per-authority voting breakdown |
| Consensus Eval | Bandwidth Values Explained | Helpful context for the table |
| Consensus Eval | Stable Uptime Explained | Helpful context for the table |
| Consensus Eval | Data source attribution | CollecTor link |

This section shows which SPECIFIC authority is/isn't voting - essential for advanced troubleshooting.

---

## Proposed Page Structure: Desktop Wireframe (max-width: 1400px)

Two columns inside each section to maximize information density on wide screens.

```
╔══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                              PAGE HEADER                                                             ║
║  View Relay "MyRelay"                                                                                                ║
║  Fingerprint: ABCD1234EFGH5678IJKL9012MNOP3456QRST7890UVWX                                            [Copy Button]  ║
║  Contact: admin@example.com                                                                                          ║
║  ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────── ║
║                                                                                                                      ║
║  WHEN AROI PRESENT (preferred):                                                                                      ║
║  Operator: example.com (12 relays) [View All]  |  AS24940  |  Germany  |  Linux       Last updated: 2024-12-29 14:30 ║
║                 ↑ Primary link - verified operator with accurate relay count                                         ║
║                                                                                                                      ║
║  WHEN NO AROI (fallback):                                                                                            ║
║  Family: 5 relays [View]  |  AS24940  |  Germany  |  Linux                         Last updated: 2024-12-29 14:30 UTC║
║            ↑ Fallback link - fingerprint-based family (may have alleged/indirect mismatches)                         ║
║                                                                                                                      ║
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
┃ CONNECTIVITY AND LOCATION                                                                            [#connectivity] ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Addresses                                           ┃ Location                                                        ┃
┃                                                     ┃                                                                  ┃
┃   OR Address:                                       ┃   Country: Germany (DE)                                          ┃
┃     relay.example.com (verified)                    ┃   Region: Bavaria                                                ┃
┃     192.0.2.1:9001                                  ┃   City: Munich                                                   ┃
┃     [2001:db8::1]:9001                              ┃   Coordinates: 48.13, 11.58                                      ┃
┃   Exit Address: none                                ┃   View on Interactive Map                                        ┃
┃   Dir Address: 192.0.2.1:9030                       ┃                                                                  ┃
┃                                                     ┃ Autonomous System                                                ┃
┃ Reachability (per Directory Authorities)            ┃                                                                  ┃
┃                                                     ┃   AS Number: AS24940                                             ┃
┃   IPv4: 9/9 authorities                             ┃   AS Name: Hetzner Online GmbH                                   ┃
┃   IPv6: 3/5 testers (4 don't test IPv6)             ┃   BGP.tools                                                      ┃
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
┃ OPERATOR AND FAMILY                                                                                     [#operator] ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Operator (AROI) - when present                      ┃ Family (fingerprint-based)                      [#effective-family]┃
┃                                                     ┃                                                                  ┃
┃   Domain: example.com (validated)                   ┃ Effective Family: 5 relays [View Family Page]                   ┃
┃   Relays by this operator: 12                       ┃   ABCD1234EFGH5678... (this relay)                               ┃
┃   [View All Operator Relays]                        ┃   WXYZ9876LMNO5432...                                            ┃
┃                                                     ┃   HIJK4567DEFG8901...                                            ┃
┃                                                     ┃   STUV2345WXYZ6789...                                            ┃
┃                                                     ┃   EFGH8901IJKL2345...                                            ┃
┃                                                     ┃                                                        [#alleged-family]┃
┃ When NO AROI:                                       ┃ Alleged Family: 2 relays                                        ┃
┃   Operator: Not specified                           ┃   (They don't list you back - check their MyFamily config)      ┃
┃   Contact: admin@example.com                        ┃   QRST1111UVWX2222...                                            ┃
┃   Use Family for relay grouping →                   ┃   MNOP3333STUV4444...                                            ┃
┃                                                     ┃                                                       [#indirect-family]┃
┃                                                     ┃ Indirect Family: 0 relays                                       ┃
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
┃ PER-AUTHORITY VOTE DETAILS                                                                        [#authority-votes] ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Data from Tor CollecTor (authority votes, fetched 2024-12-29 14:00 UTC)                                              ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Per-Authority Voting Details (for advanced troubleshooting - which specific authority is/isn't voting?)              ┃
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
║                                           ║
║  WHEN AROI PRESENT:                       ║
║  Operator: example.com (12 relays)        ║
║  AS24940 | DE | Linux                     ║
║                                           ║
║  WHEN NO AROI:                            ║
║  Family: 5 relays                         ║
║  AS24940 | DE | Linux                     ║
║                                           ║
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
┃ CONNECTIVITY & LOCATION  [#connectivity]  ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Addresses                                 ┃
┃   OR: relay.example.com (verified)        ┃
┃       192.0.2.1:9001                      ┃
┃       [2001:db8::1]:9001                  ┃
┃   Exit: none                              ┃
┃   Dir: 192.0.2.1:9030                     ┃
┃                                           ┃
┃ Reachability                              ┃
┃   IPv4: 9/9 authorities                   ┃
┃   IPv6: 3/5 testers                       ┃
┃         (4 don't test IPv6)               ┃
┃                                           ┃
┃ Location                                  ┃
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
┃ OPERATOR AND FAMILY        [#operator]    ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Operator (AROI) - when present            ┃
┃   Domain: example.com (validated)         ┃
┃   Relays: 12 [View All]                   ┃
┃                                           ┃
┃ When NO AROI:                             ┃
┃   Operator: Not specified                 ┃
┃   Contact: admin@example.com              ┃
┃                                           ┃
┃ Family (fingerprint-based)                ┃
┃                                           ┃
┃ Effective: 5 relays [View Family]         ┃
┃   ABCD1234... (this relay)                ┃
┃   WXYZ9876...                             ┃
┃   HIJK4567...                             ┃
┃   STUV2345...                             ┃
┃   EFGH8901...                             ┃
┃                                           ┃
┃ Alleged: 2 relays                         ┃
┃   (They don't list you back)              ┃
┃   QRST1111...                             ┃
┃   MNOP3333...                             ┃
┃                                           ┃
┃ Indirect: 0 relays                        ┃
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
┃ PER-AUTHORITY DETAILS  [#authority-votes] ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Data from Tor CollecTor                   ┃
┃ (fetched 2024-12-29 14:00 UTC)            ┃
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

## Detailed Implementation Specifications

This section provides complete technical details for implementing each phase, including specific files, variables, code changes, and new functionality to add.

---

### Phase 1: Quick Wins (Template Changes Only)

**Estimated Effort:** 2-4 hours
**Files to Modify:** `allium/templates/relay-info.html`

#### 1.1 Remove All Emoji Icons, Replace with Text Labels

**File:** `allium/templates/relay-info.html`

**Specific Changes:**

| Line(s) | Current | Replace With |
|---------|---------|--------------|
| ~224 | `✓` (checkmark for measured bandwidth) | `Measured` |
| ~226 | `✗` (X for unmeasured bandwidth) | `Not Measured` |
| ~229 | `?` (question mark for unknown) | `Unknown` |
| ~242 | `⚠️ Underutilized` | `[Warning] Underutilized` |
| ~323 | `🗺️ View on Interactive Map` | `View on Interactive Map` |
| ~455 | `🔍 Consensus Evaluation` | `Consensus Evaluation` |
| ~506 | `⚠️ High deviation` | `[Warning] High deviation` |
| ~520 | `💡 {{ issue.suggestion }}` | `Suggestion: {{ issue.suggestion }}` |
| ~719-750+ | All `✓` and `✗` in authority table | `Yes` / `No` |
| ~889 | `⚠️` for StaleDesc | `[Warning]` |

**Template Code Replacements:**

```jinja2
{# BEFORE (line ~224): #}
<span style="color: #28a745; font-weight: bold;" title="Bandwidth capacity measured...">✓</span>

{# AFTER: #}
<span style="color: #28a745; font-weight: bold;" title="Bandwidth capacity measured...">Measured</span>
```

```jinja2
{# BEFORE (line ~226): #}
<span style="color: #dc3545; font-weight: bold;" title="Bandwidth capacity not measured...">✗</span>

{# AFTER: #}
<span style="color: #dc3545; font-weight: bold;" title="Bandwidth capacity not measured...">Not Measured</span>
```

```jinja2
{# BEFORE (line ~520): #}
<li style="color: #666; font-size: 12px;">💡 {{ issue.suggestion|safe }}</li>

{# AFTER: #}
<li style="color: #666; font-size: 12px;"><strong>Suggestion:</strong> {{ issue.suggestion|safe }}</li>
```

```jinja2
{# BEFORE (line ~455): #}
<a href="#consensus-evaluation" class="anchor-link">🔍 Consensus Evaluation</a>

{# AFTER: #}
<a href="#consensus-evaluation" class="anchor-link">Consensus Evaluation</a>
```

**Authority Table Cell Updates (lines ~719-912):**

Replace all instances of:
- `<span style="color: #28a745;">✓</span>` → `<span style="color: #28a745;">Yes</span>`
- `<span style="color: #dc3545;">✗</span>` → `<span style="color: #dc3545;">No</span>`
- `<span style="color: #6c757d;">—</span>` → `<span style="color: #6c757d;">N/A</span>` (keep dash for empty cells)

---

#### 1.2 Add Missing Anchor Links to All Sections

**File:** `allium/templates/relay-info.html`

**Current Anchors (already exist):**
- `#ipv4-exit-policy-summary` (line 104)
- `#ipv6-exit-policy-summary` (line 120)
- `#exit-policy` (line 136)
- `#effective-family` (line 148)
- `#alleged-family` (line 170)
- `#indirect-family` (line 189)
- `#consensus-evaluation` (line 453)
- `#relay-summary` (line 539)
- `#authority-votes` (line 672)

**Anchors to Add (wrap existing `<dt>` elements):**

| New Anchor ID | Current Element | Line Approx |
|---------------|-----------------|-------------|
| `#bandwidth-capacity` | `<dt>Bandwidth Capacity...` | ~231 |
| `#network-participation` | `<dt>Network Participation...` | ~254 |
| `#or-address` | `<dt>OR Address</dt>` | ~269 |
| `#exit-address` | `<dt>Exit Address</dt>` | ~287 |
| `#dir-address` | `<dt>Dir Address</dt>` | ~301 |
| `#location` | `<dt>City | Region | Country</dt>` | ~317 |
| `#coordinates` | `<dt>Latitude, Longitude</dt>` | ~342 |
| `#interactive-map` | `<dt>Interactive Map</dt>` | ~352 |
| `#autonomous-system` | `<dt>Autonomous System...` | ~360 |
| `#flags` | `<dt>Flags: ...</dt>` | ~377 |
| `#flag-uptime` | `<dt>Flag Uptime...</dt>` | ~394 |
| `#uptime-history` | `<dt>Uptime (1M/6M/1Y/5Y)</dt>` | ~410 |
| `#uptime-downtime` | `<dt>Uptime / Downtime</dt>` | ~422 |
| `#first-last-seen` | `<dt>Seen (First | Last)</dt>` | ~438 |
| `#last-restarted` | `<dt>Last Restarted</dt>` | ~446 |
| `#last-changed-address` | `<dt>Last Changed Address or Port</dt>` | ~458 |
| `#hibernating` | `<dt>Hibernating</dt>` | ~470 |
| `#platform` | `<dt>Platform (Short | Long)</dt>` | ~482 |
| `#version` | `<dt>Version (Running...)</dt>` | ~490 |

**Template Pattern for Adding Anchors:**

```jinja2
{# BEFORE: #}
<dt title="...">
Bandwidth Capacity (Observed | Advertised | Rate Limit | Burst Limit)
</dt>

{# AFTER: #}
<dt id="bandwidth-capacity" title="...">
<div class="section-header">
<a href="#bandwidth-capacity" class="anchor-link">Bandwidth Capacity (Observed | Advertised | Rate Limit | Burst Limit)</a>
</div>
</dt>
```

---

#### 1.3 Ensure Existing Anchor Links Work Correctly

**Verification Steps:**
1. Test all existing anchors navigate correctly
2. Verify `:target` CSS highlighting works (already in template lines ~25-31)
3. Ensure anchor links don't break on page load

**CSS Already Present (lines 25-31):**
```css
:target {
    background-color: rgba(255, 193, 7, 0.2);
    padding: 8px;
    border-radius: 4px;
    margin: -8px;
    transition: background-color 0.3s;
}
```

---

#### 1.4 Move Contact to Page Header, Make AROI Primary Link

**File:** `allium/templates/relay-info.html`

**Current Structure (lines 39-56):**
```jinja2
<h4>
{% if relay['effective_family']|length > 1 -%}
<a href="{{ page_ctx.path_prefix }}family/{{ relay['fingerprint']|escape }}/">Family: {{ relay['effective_family']|length }} relays</a>
{% else -%}
Family: {{ relay['effective_family']|length }} relay
{% endif -%} | 
{% if relay['as'] -%}
<a href="{{ page_ctx.path_prefix }}as/{{ relay['as']|escape }}/">{{ relay['as']|escape }}</a>
...
</h4>
```

**New Structure (replace lines 39-56):**

```jinja2
<h4>
{# AROI takes priority when present - verified operator identity #}
{% if relay['aroi_domain'] and relay['aroi_domain'] != 'none' -%}
    {% if base_url and relay['aroi_domain'] in validated_aroi_domains -%}
        <a href="{{ base_url }}/{{ relay['aroi_domain']|lower|escape }}/" title="Verified operator - view all relays">Operator: {{ relay['aroi_domain']|escape }}</a>
    {% else -%}
        <a href="{{ page_ctx.path_prefix }}contact/{{ relay['contact_md5'] }}/" title="Operator (unverified AROI)">Operator: {{ relay['aroi_domain']|escape }}</a>
    {% endif -%}
{% elif relay['effective_family']|length > 1 -%}
    {# Fallback to Family when no AROI #}
    <a href="{{ page_ctx.path_prefix }}family/{{ relay['fingerprint']|escape }}/" title="View family members">Family: {{ relay['effective_family']|length }} relays</a>
{% else -%}
    Family: {{ relay['effective_family']|length }} relay
{% endif -%} | 
{% if relay['contact'] -%}
    <a href="{{ page_ctx.path_prefix }}contact/{{ relay['contact_md5'] }}/" title="Contact information">{{ relay['contact']|truncate(40)|escape }}</a> | 
{% endif -%}
{% if relay['as'] -%}
<a href="{{ page_ctx.path_prefix }}as/{{ relay['as']|escape }}/">{{ relay['as']|escape }}</a>
{% else -%}
AS: unknown
{% endif -%} | 
{% if relay['country'] -%}
<a href="{{ page_ctx.path_prefix }}country/{{ relay['country']|escape }}/">{{ relay['country_name']|escape }}</a>
{% else -%}
Country: unknown
{% endif -%} | 
<a href="{{ page_ctx.path_prefix }}platform/{{ relay['platform']|escape }}/">{{ relay['platform']|escape }}</a>
</h4>
```

**Variables Used:**
- `relay['aroi_domain']` - AROI domain from contact info parsing
- `relay['contact_md5']` - MD5 hash of contact for contact page link
- `relay['contact']` - Raw contact string
- `relay['effective_family']` - List of family member fingerprints
- `validated_aroi_domains` - Set of validated AROI domains (from template context)
- `base_url` - Base URL for validated AROI links

---

### Phase 2: Layout Restructure

**Estimated Effort:** 8-16 hours
**Files to Modify:** 
- `allium/templates/relay-info.html` (major restructure)
- `allium/templates/skeleton.html` (CSS additions)

#### 2.1 Add Health Status Summary Section at Top

**File:** `allium/templates/relay-info.html`

**Insert After Navigation (after line 38):**

```jinja2
{# ============== SECTION 1: HEALTH STATUS SUMMARY ============== #}
<section id="status" class="relay-section">
<h3>
<div class="section-header">
<a href="#status" class="anchor-link">Health Status</a>
</div>
</h3>

<div class="row">
<div class="col-md-6">
<dl class="dl-horizontal-compact">
    <dt>Consensus Status</dt>
    <dd>
        {% if relay.consensus_evaluation and relay.consensus_evaluation.available -%}
            {% if relay.consensus_evaluation.in_consensus -%}
                <span style="color: #28a745; font-weight: bold;">IN CONSENSUS</span>
                ({{ relay.consensus_evaluation.vote_count }}/{{ relay.consensus_evaluation.total_authorities }} authorities)
            {% else -%}
                <span style="color: #dc3545; font-weight: bold;">NOT IN CONSENSUS</span>
                ({{ relay.consensus_evaluation.vote_count }}/{{ relay.consensus_evaluation.total_authorities }} authorities, need {{ relay.consensus_evaluation.majority_required }})
            {% endif -%}
        {% else -%}
            <span style="color: #6c757d;">Data unavailable</span>
        {% endif -%}
    </dd>
    
    <dt>Running Status</dt>
    <dd>
        {% if relay.get('uptime_display') -%}
            {% if relay['uptime_display'].startswith('DOWN') -%}
                <span style="color: #dc3545; font-weight: bold;">{{ relay['uptime_display']|escape }}</span>
            {% else -%}
                <span style="color: #28a745;">{{ relay['uptime_display']|escape }}</span>
            {% endif -%}
        {% else -%}
            <span style="color: #6c757d;">Unknown</span>
        {% endif -%}
    </dd>
    
    <dt>Bandwidth Measured</dt>
    <dd>
        {% if relay['measured'] is not none -%}
            {% if relay['measured'] -%}
                <span style="color: #28a745;">Yes</span> (by bandwidth authorities)
            {% else -%}
                <span style="color: #dc3545;">No</span> (using relay-reported values)
            {% endif -%}
        {% else -%}
            <span style="color: #6c757d;">Unknown</span>
        {% endif -%}
    </dd>
</dl>
</div>

<div class="col-md-6">
<dl class="dl-horizontal-compact">
    <dt>Current Flags</dt>
    <dd>
        {% for flag in relay['flags'] -%}
            {% if flag != 'StaleDesc' -%}
                <a href="{{ page_ctx.path_prefix }}flag/{{ flag.lower()|escape }}/">{{ flag|escape }}</a>{% if not loop.last %}, {% endif %}
            {% endif -%}
        {% endfor -%}
        {% if 'StaleDesc' in relay['flags'] -%}
            <br><span style="color: #dc3545;">[Warning] StaleDesc - descriptor is stale</span>
        {% endif -%}
    </dd>
</dl>
</div>
</div>

{# Issues and Warnings #}
{% if relay.consensus_evaluation and relay.consensus_evaluation.available and relay.consensus_evaluation.issues %}
{% set real_issues = relay.consensus_evaluation.issues | selectattr('severity', 'ne', 'info') | list %}
{% set info_notes = relay.consensus_evaluation.issues | selectattr('severity', 'equalto', 'info') | list %}

{% if real_issues %}
<div class="alert alert-warning" style="margin-top: 10px;">
    <strong>Issues Detected:</strong>
    <ul style="margin-bottom: 0; padding-left: 20px;">
    {% for issue in real_issues %}
        <li>
            <span style="color: {% if issue.severity == 'error' %}#dc3545{% else %}#856404{% endif %}; font-weight: bold;">
                [{{ issue.severity|capitalize }}] {{ issue.title }}
            </span>: {{ issue.description|safe }}
            {% if issue.suggestion %}
            <br><span style="color: #666; font-size: 12px;"><strong>Suggestion:</strong> {{ issue.suggestion|safe }}</span>
            {% endif %}
        </li>
    {% endfor %}
    </ul>
</div>
{% endif %}

{% if info_notes %}
<div class="alert alert-info" style="margin-top: 10px;">
    <strong>Notes:</strong>
    <ul style="margin-bottom: 0; padding-left: 20px;">
    {% for note in info_notes %}
        <li>{{ note.title }}: {{ note.description }}</li>
    {% endfor %}
    </ul>
</div>
{% endif %}
{% else %}
<div class="alert alert-success" style="margin-top: 10px;">
    <strong>No issues detected.</strong> Relay appears to be operating normally.
</div>
{% endif %}

</section>
```

**Variables Used:**
- `relay.consensus_evaluation.available` (bool) - Whether consensus data is available
- `relay.consensus_evaluation.in_consensus` (bool) - In consensus or not
- `relay.consensus_evaluation.vote_count` (int) - Number of authorities voting for relay
- `relay.consensus_evaluation.total_authorities` (int) - Total voting authorities (9)
- `relay.consensus_evaluation.majority_required` (int) - Votes needed (5)
- `relay.consensus_evaluation.issues` (list) - List of issue dicts with `severity`, `title`, `description`, `suggestion`
- `relay['uptime_display']` (str) - "UP for X days" or "DOWN for X hours"
- `relay['measured']` (bool/None) - Whether bandwidth is authority-measured
- `relay['flags']` (list) - Current flag list

---

#### 2.2 Merge Addresses + Reachability + AS + Geo into "Connectivity and Location"

**New Section Structure:**

```jinja2
{# ============== SECTION 2: CONNECTIVITY AND LOCATION ============== #}
<section id="connectivity" class="relay-section">
<h3>
<div class="section-header">
<a href="#connectivity" class="anchor-link">Connectivity and Location</a>
</div>
</h3>

<div class="row">
{# Left Column: Addresses and Reachability #}
<div class="col-md-6">
<h4>Addresses</h4>
<dl class="dl-horizontal-compact">
    <dt>OR Address</dt>
    <dd>
        {% if relay['verified_host_names'] -%}
            {% for hostname in relay['verified_host_names'] -%}
                <span class="verified-hostname" title="Verified hostname">{{ hostname|escape }}</span>{% if not loop.last %}, {% endif %}
            {% endfor %}<br>
        {% elif relay['unverified_host_names'] -%}
            {% for hostname in relay['unverified_host_names'] -%}
                <span class="unverified-hostname" title="Unverified hostname">{{ hostname|escape }}</span>{% if not loop.last %}, {% endif %}
            {% endfor %}<br>
        {% endif -%}
        {% for address in relay['or_addresses'] -%}
            {{ address }}{% if not loop.last %}<br>{% endif %}
        {% endfor -%}
    </dd>
    
    <dt>Exit Address</dt>
    <dd>{{ relay['exit_address']|escape if relay['exit_address'] else 'none' }}</dd>
    
    <dt>Dir Address</dt>
    <dd>
        {% if relay['dir_address'] -%}
            <a href="http://{{ relay['dir_address']|escape }}">{{ relay['dir_address']|escape }}</a>
        {% else -%}
            none
        {% endif -%}
    </dd>
</dl>

<h4>Reachability (Directory Authorities)</h4>
<dl class="dl-horizontal-compact">
    {% if relay.consensus_evaluation and relay.consensus_evaluation.available and relay.consensus_evaluation.reachability_summary %}
    {% set reach = relay.consensus_evaluation.reachability_summary %}
    <dt>IPv4</dt>
    <dd>
        <span style="color: {% if reach.ipv4.status_class == 'success' %}#28a745{% else %}#dc3545{% endif %}; font-weight: bold;">
            {{ reach.ipv4.reachable_count }}/{{ reach.ipv4.total }}
        </span> authorities can reach this relay
    </dd>
    
    {# Only show IPv6 if relay has IPv6 address #}
    {% set ns = namespace(has_ipv6=false) %}
    {% for addr in relay.or_addresses|default([]) %}
        {% if '[' in addr %}{% set ns.has_ipv6 = true %}{% endif %}
    {% endfor %}
    {% if ns.has_ipv6 %}
    <dt>IPv6</dt>
    <dd>
        <span style="color: {% if reach.ipv6.status_class == 'success' %}#28a745{% elif reach.ipv6.status_class == 'muted' %}#6c757d{% else %}#dc3545{% endif %}; font-weight: bold;">
            {{ reach.ipv6.reachable_count }}/{{ reach.ipv6.total }}
        </span> testers can reach IPv6
        {% if reach.ipv6.not_tested %}
            <span style="color: #6c757d; font-size: 11px;">({{ reach.ipv6.not_tested|length }} don't test IPv6)</span>
        {% endif %}
    </dd>
    {% endif %}
    {% else %}
    <dt>Status</dt>
    <dd><span style="color: #6c757d;">Reachability data unavailable</span></dd>
    {% endif %}
</dl>
</div>

{# Right Column: Location and AS #}
<div class="col-md-6">
<h4>Location</h4>
<dl class="dl-horizontal-compact">
    <dt>Country</dt>
    <dd>
        {% if relay['country'] -%}
            <a href="{{ page_ctx.path_prefix }}country/{{ relay['country']|escape }}/">
                <img src="{{ page_ctx.path_prefix }}static/images/cc/{{ relay['country']|lower|escape }}.png"
                     title="{{ relay['country_name']|escape }}" alt="{{ relay['country_name']|escape }}">
            </a> {{ relay['country_name']|escape }}
        {% else -%}
            Unknown
        {% endif -%}
    </dd>
    
    {% if relay['region_name'] %}
    <dt>Region</dt>
    <dd>{{ relay['region_name']|escape }}</dd>
    {% endif %}
    
    {% if relay['city_name'] %}
    <dt>City</dt>
    <dd>{{ relay['city_name']|escape }}</dd>
    {% endif %}
    
    {% if relay['latitude'] and relay['longitude'] and relay['latitude'] != 0 and relay['longitude'] != 0 %}
    <dt>Coordinates</dt>
    <dd>{{ relay['latitude']|escape }}, {{ relay['longitude']|escape }}</dd>
    {% endif %}
    
    <dt>Interactive Map</dt>
    <dd><a href="https://routefluxmap.1aeo.com/#relay={{ relay['fingerprint']|escape }}" target="_blank" rel="noopener">View on Interactive Map</a></dd>
</dl>

<h4>Autonomous System</h4>
<dl class="dl-horizontal-compact">
    <dt>AS Number</dt>
    <dd>
        {% if relay['as'] -%}
            <a href='{{ page_ctx.path_prefix }}as/{{ relay['as']|escape }}/'>{{ relay['as']|escape }}</a>
        {% else -%}
            Unknown
        {% endif -%}
    </dd>
    
    <dt>AS Name</dt>
    <dd>
        {% if relay['as_name'] -%}
            {{ relay['as_name']|escape }}
            {% if relay['as'] %}(<a href='https://bgp.tools/{{ relay['as']|escape }}'>BGP.tools</a>){% endif %}
        {% else -%}
            Unknown
        {% endif -%}
    </dd>
</dl>
</div>
</div>
</section>
```

**Variables Used:**
- `relay['or_addresses']` (list) - List of OR addresses with ports
- `relay['exit_address']` (str/None) - Exit IP if different from OR
- `relay['dir_address']` (str/None) - Directory address:port
- `relay['verified_host_names']` (list) - Verified DNS hostnames
- `relay['unverified_host_names']` (list) - Unverified DNS hostnames
- `relay['country']` (str) - Two-letter country code
- `relay['country_name']` (str) - Full country name
- `relay['region_name']` (str/None) - Region/state name
- `relay['city_name']` (str/None) - City name
- `relay['latitude']`, `relay['longitude']` (float) - Coordinates
- `relay['as']` (str) - AS number (e.g., "AS24940")
- `relay['as_name']` (str) - AS organization name
- `relay.consensus_evaluation.reachability_summary` (dict) - IPv4/IPv6 reachability data

---

#### 2.3 Merge AROI + Family into "Operator and Family" Section

**New Section Structure:**

```jinja2
{# ============== SECTION 6: OPERATOR AND FAMILY ============== #}
<section id="operator" class="relay-section">
<h3>
<div class="section-header">
<a href="#operator" class="anchor-link">Operator and Family</a>
</div>
</h3>

<div class="row">
{# Left Column: Operator (AROI) #}
<div class="col-md-6">
<h4>Operator Identity</h4>
<dl class="dl-horizontal-compact">
    <dt>AROI Domain</dt>
    <dd>
        {% if relay['aroi_domain'] and relay['aroi_domain'] != 'none' -%}
            {% if base_url and relay['aroi_domain'] in validated_aroi_domains -%}
                <a href="{{ base_url }}/{{ relay['aroi_domain']|lower|escape }}/">{{ relay['aroi_domain']|escape }}</a>
                <span style="color: #28a745; margin-left: 4px;" title="AROI Validated">Validated</span>
            {% else -%}
                <a href="{{ page_ctx.path_prefix }}contact/{{ relay['contact_md5'] }}/">{{ relay['aroi_domain']|escape }}</a>
                <span style="color: #ffc107; margin-left: 4px;" title="AROI Unvalidated">Unvalidated</span>
            {% endif -%}
        {% else -%}
            Not specified
        {% endif -%}
    </dd>
    
    <dt>Contact</dt>
    <dd style="word-wrap: break-word; word-break: break-all; max-width: 100%;">
        {% if relay['contact'] -%}
            <a href="{{ page_ctx.path_prefix }}contact/{{ relay['contact_md5'] }}/">{{ relay['contact']|escape }}</a>
        {% else -%}
            <a href="{{ page_ctx.path_prefix }}contact/{{ relay['contact_md5'] }}/">none</a>
        {% endif -%}
    </dd>
</dl>

{% if relay['aroi_domain'] and relay['aroi_domain'] != 'none' %}
<div class="alert alert-info" style="font-size: 12px; padding: 8px;">
    <strong>About AROI:</strong> The Autonomous Relay Operator Identifier provides verified operator identity.
    When validated, it accurately groups all relays by this operator.
    <a href="https://nusenu.github.io/ContactInfo-Information-Sharing-Specification/" target="_blank" rel="noopener">Learn more</a>
</div>
{% endif %}
</div>

{# Right Column: Family (fingerprint-based) #}
<div class="col-md-6">
<h4>Family Configuration</h4>
<dl class="dl-horizontal-compact">
    <dt id="effective-family">Effective Family</dt>
    <dd>
        {{ relay['effective_family']|length }} relay{% if relay['effective_family']|length != 1 %}s{% endif %}
        {% if relay['effective_family']|length > 1 %}
            (<a href="{{ page_ctx.path_prefix }}family/{{ relay['fingerprint']|escape }}/">View Family Page</a>)
        {% endif %}
        <pre class="pre-scrollable" style="max-height: 100px; font-size: 11px; margin-top: 5px;">{% for fp in relay['effective_family'] -%}
{% if relay['effective_family']|length > 1 and fp != relay['fingerprint'] -%}
<a href="../{{ fp|escape }}/">{{ fp|escape }}</a>
{% else -%}
{{ fp|escape }}{% if fp == relay['fingerprint'] %} (this relay){% endif %}
{% endif -%}
{% endfor -%}</pre>
    </dd>
    
    <dt id="alleged-family">Alleged Family</dt>
    <dd>
        {{ relay['alleged_family']|length if relay['alleged_family'] else 0 }} relay{% if not relay['alleged_family'] or relay['alleged_family']|length != 1 %}s{% endif %}
        {% if relay['alleged_family'] %}
        <span style="color: #856404; font-size: 11px;">(they don't list you back)</span>
        <pre class="pre-scrollable" style="max-height: 60px; font-size: 11px; margin-top: 5px;">{% for fp in relay['alleged_family'] -%}
<a href="../{{ fp|escape }}/">{{ fp|escape }}</a>
{% endfor -%}</pre>
        {% endif %}
    </dd>
    
    <dt id="indirect-family">Indirect Family</dt>
    <dd>
        {{ relay['indirect_family']|length if relay['indirect_family'] else 0 }} relay{% if not relay['indirect_family'] or relay['indirect_family']|length != 1 %}s{% endif %}
        {% if relay['indirect_family'] %}
        <span style="color: #856404; font-size: 11px;">(they list you, you don't list them)</span>
        <pre class="pre-scrollable" style="max-height: 60px; font-size: 11px; margin-top: 5px;">{% for fp in relay['indirect_family'] -%}
<a href="../{{ fp|escape }}/">{{ fp|escape }}</a>
{% endfor -%}</pre>
        {% endif %}
    </dd>
</dl>
</div>
</div>
</section>
```

**Variables Used:**
- `relay['aroi_domain']` (str/None) - AROI domain from contact info
- `relay['contact']` (str) - Raw contact string
- `relay['contact_md5']` (str) - MD5 hash for contact page URL
- `relay['effective_family']` (list) - Mutual family members
- `relay['alleged_family']` (list/None) - You list them, they don't list you
- `relay['indirect_family']` (list/None) - They list you, you don't list them
- `validated_aroi_domains` (set) - Set of validated AROI domains
- `base_url` (str) - Base URL for validated AROI links

---

#### 2.4 Add CSS for Fluid-Width Single Column

**File:** `allium/templates/skeleton.html`

**Add to `<style>` section (after line ~1284):**

```css
/* ============================================
   RELAY PAGE LAYOUT - Phase 2 CSS
   ============================================ */

/* Fluid-width single column with max-width for readability */
.relay-page-content {
    max-width: 1400px;      /* Prevent overly wide lines on 4K monitors */
    width: 100%;            /* Fill available space */
    margin: 0 auto;         /* Center on very wide screens */
    padding: 0 20px;        /* Breathing room on edges */
}

/* Full-width sections */
.relay-section {
    width: 100%;
    margin-bottom: 25px;
    padding-bottom: 15px;
    border-bottom: 1px solid #eee;
}

.relay-section:last-child {
    border-bottom: none;
}

/* Section headers with anchor links */
.relay-section h3 {
    margin-top: 0;
    margin-bottom: 15px;
    padding-bottom: 8px;
    border-bottom: 2px solid #337ab7;
}

.relay-section h4 {
    margin-top: 15px;
    margin-bottom: 10px;
    font-size: 14px;
    font-weight: bold;
    color: #555;
}

/* Compact definition lists for two-column layout inside sections */
.dl-horizontal-compact dt {
    float: left;
    width: 140px;
    clear: left;
    text-align: right;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: normal;
    color: #666;
    padding-right: 10px;
    margin-bottom: 5px;
}

.dl-horizontal-compact dd {
    margin-left: 150px;
    margin-bottom: 5px;
}

/* Responsive: Stack columns on narrow screens */
@media (max-width: 991px) {
    .relay-page-content {
        max-width: 100%;
        padding: 0 10px;
    }
    
    .dl-horizontal-compact dt {
        float: none;
        width: auto;
        text-align: left;
        margin-bottom: 2px;
    }
    
    .dl-horizontal-compact dd {
        margin-left: 0;
        margin-bottom: 10px;
    }
}

/* Scroll margin for anchor links (ensures header doesn't cover content) */
.relay-section,
.relay-section h3,
.relay-section h4,
[id] {
    scroll-margin-top: 20px;
}

/* Fingerprint display - full and copyable */
.fingerprint-full {
    font-family: Consolas, "Courier New", monospace;
    font-size: 12px;
    word-break: break-all;
    user-select: all;
    cursor: text;
    background: #f8f9fa;
    padding: 4px 8px;
    border-radius: 4px;
}

/* Copy button styling */
.copy-button {
    font-size: 11px;
    padding: 2px 6px;
    margin-left: 8px;
    cursor: pointer;
    border: 1px solid #ccc;
    background: #fff;
    border-radius: 3px;
}

.copy-button:hover {
    background: #f0f0f0;
}
```

---

#### 2.5 Move Fingerprint to Header, Make Full and Copyable

**File:** `allium/templates/relay-info.html`

**Update Header Section (lines 35-38):**

```jinja2
<div id="content" class="relay-page-content">
<h2>View Relay "{{ relay['nickname'] }}"</h2>

{# Full fingerprint with copy functionality #}
<p style="margin-bottom: 10px;">
    <strong>Fingerprint:</strong> 
    <code class="fingerprint-full" id="relay-fingerprint">{{ relay['fingerprint']|escape }}</code>
    <button class="copy-button" onclick="navigator.clipboard.writeText('{{ relay['fingerprint']|escape }}'); this.textContent='Copied!'; setTimeout(()=>this.textContent='Copy', 1500);">Copy</button>
</p>

{% set relay_data = {'nickname': relay['nickname'], 'fingerprint': relay['fingerprint'], 'as_number': relay['as']} %}
{{ navigation('all', page_ctx) }}
```

---

#### 2.6 Section Reordering - Complete Template Structure

**File:** `allium/templates/relay-info.html`

**New Section Order:**

```jinja2
{# ============== PAGE HEADER ============== #}
{# Nickname, Fingerprint (full, copyable), Contact, AROI/Family, Quick Links #}

{# ============== SECTION 1: HEALTH STATUS (#status) ============== #}
{# Consensus status, Running status, Flags, Issues/Warnings #}

{# ============== SECTION 2: CONNECTIVITY AND LOCATION (#connectivity) ============== #}
{# Addresses, Reachability, Location, AS info #}

{# ============== SECTION 3: FLAGS AND ELIGIBILITY (#flags) ============== #}
{# Current flags, Flag eligibility table with thresholds #}

{# ============== SECTION 4: BANDWIDTH (#bandwidth) ============== #}
{# Observed/Advertised/Rate/Burst, Network participation, Authority-measured #}

{# ============== SECTION 5: UPTIME AND STABILITY (#uptime) ============== #}
{# Current status, Historical uptime, First/Last seen, Hibernating #}

{# ============== SECTION 6: OPERATOR AND FAMILY (#operator) ============== #}
{# AROI info, Contact, Effective/Alleged/Indirect family #}

{# ============== SECTION 7: SOFTWARE AND VERSION (#software) ============== #}
{# Platform, Version, Recommended status, Last changed #}

{# ============== SECTION 8: EXIT POLICY (#exit-policy) ============== #}
{# IPv4/IPv6 summary, Full policy #}

{# ============== SECTION 9: PER-AUTHORITY VOTE DETAILS (#authority-votes) ============== #}
{# Detailed per-authority table, Explanatory info boxes #}
```

---

### Phase 3: Content Enhancement

**Estimated Effort:** 4-8 hours
**Files to Modify:**
- `allium/templates/relay-info.html`
- `allium/lib/consensus/consensus_evaluation.py`

#### 3.1 Add Flag Eligibility Table to Flags Section

**File:** `allium/templates/relay-info.html`

**In Section 3 (Flags), add after current flags display:**

```jinja2
{# Flag Eligibility Requirements Table #}
{% if relay.consensus_evaluation and relay.consensus_evaluation.available and relay.consensus_evaluation.relay_values %}
{% set rv = relay.consensus_evaluation.relay_values %}

<h4>Flag Requirements (Your Value vs Threshold)</h4>
<div class="table-responsive">
<table class="table table-condensed table-striped" style="font-size: 12px;">
<thead>
<tr>
    <th style="width: 15%;">Flag</th>
    <th style="width: 15%;">Metric</th>
    <th style="width: 25%;">Your Value</th>
    <th style="width: 25%;">Threshold Required</th>
    <th style="width: 20%;">Status</th>
</tr>
</thead>
<tbody>
    {# Guard Flag Requirements #}
    <tr>
        <td rowspan="3"><strong>Guard</strong></td>
        <td>WFU</td>
        <td>{{ rv.wfu_display }}</td>
        <td>≥98% (all authorities)</td>
        <td>
            {% if rv.wfu_meets %}
                <span style="color: #28a745; font-weight: bold;">Meets</span>
            {% else %}
                <span style="color: #dc3545; font-weight: bold;">Below</span>
            {% endif %}
        </td>
    </tr>
    <tr>
        <td>Time Known</td>
        <td>{{ rv.tk_display }}</td>
        <td>≥8 days (all authorities)</td>
        <td>
            {% if rv.tk_meets %}
                <span style="color: #28a745; font-weight: bold;">Meets</span>
            {% else %}
                <span style="color: #dc3545; font-weight: bold;">Below</span>
                {% if rv.tk_days_needed > 0 %}
                    (need {{ "%.1f"|format(rv.tk_days_needed) }} more days)
                {% endif %}
            {% endif %}
        </td>
    </tr>
    <tr>
        <td>Bandwidth</td>
        <td>{{ rv.observed_bw_display }}</td>
        <td>≥{{ rv.guard_bw_guarantee_display }} OR top 25%</td>
        <td>
            {% if rv.guard_bw_meets_guarantee %}
                <span style="color: #28a745; font-weight: bold;">Meets (≥2 MB/s)</span>
            {% elif rv.guard_bw_meets_some %}
                <span style="color: #ffc107; font-weight: bold;">Partial (top 25% for {{ rv.guard_bw_meets_count }})</span>
            {% else %}
                <span style="color: #dc3545; font-weight: bold;">Below</span>
            {% endif %}
        </td>
    </tr>
    
    {# Stable Flag Requirements #}
    <tr>
        <td rowspan="2"><strong>Stable</strong></td>
        <td>MTBF</td>
        <td>{{ rv.mtbf_display|default('N/A') }}</td>
        <td>≥{{ rv.stable_mtbf_min_display }} - {{ rv.stable_mtbf_typical_display }}</td>
        <td>
            {% if rv.stable_mtbf_meets_all|default(false) %}
                <span style="color: #28a745; font-weight: bold;">Meets</span>
            {% elif rv.stable_mtbf_meets_count|default(0) >= relay.consensus_evaluation.majority_required %}
                <span style="color: #ffc107; font-weight: bold;">Partial</span>
            {% else %}
                <span style="color: #dc3545; font-weight: bold;">Below</span>
            {% endif %}
        </td>
    </tr>
    <tr>
        <td>Uptime</td>
        <td>{{ rv.stable_uptime_display }}</td>
        <td>≥{{ rv.stable_uptime_min_display }} - {{ rv.stable_uptime_typical_display }}</td>
        <td>
            {% if rv.stable_uptime_meets_all %}
                <span style="color: #28a745; font-weight: bold;">Meets</span>
            {% elif rv.stable_uptime_meets_count >= relay.consensus_evaluation.majority_required %}
                <span style="color: #ffc107; font-weight: bold;">Partial</span>
            {% else %}
                <span style="color: #dc3545; font-weight: bold;">Below</span>
            {% endif %}
        </td>
    </tr>
    
    {# Fast Flag Requirements #}
    <tr>
        <td><strong>Fast</strong></td>
        <td>Speed</td>
        <td>{{ rv.fast_speed_display }}</td>
        <td>≥{{ rv.fast_minimum_display }} (guarantee) OR top 7/8</td>
        <td>
            {% if rv.fast_meets_minimum %}
                <span style="color: #28a745; font-weight: bold;">Meets (≥100 KB/s)</span>
            {% elif rv.fast_meets_all %}
                <span style="color: #28a745; font-weight: bold;">Meets</span>
            {% elif rv.fast_meets_count > 0 %}
                <span style="color: #ffc107; font-weight: bold;">Partial</span>
            {% else %}
                <span style="color: #dc3545; font-weight: bold;">Below</span>
            {% endif %}
        </td>
    </tr>
    
    {# HSDir Flag Requirements #}
    <tr>
        <td rowspan="2"><strong>HSDir</strong></td>
        <td>WFU</td>
        <td>{{ rv.wfu_display }}</td>
        <td>≥{{ "%.1f"|format(rv.hsdir_wfu_threshold * 100) }}%</td>
        <td>
            {% if rv.hsdir_wfu_meets %}
                <span style="color: #28a745; font-weight: bold;">Meets</span>
            {% else %}
                <span style="color: #dc3545; font-weight: bold;">Below</span>
            {% endif %}
        </td>
    </tr>
    <tr>
        <td>Time Known</td>
        <td>{{ rv.tk_display }}</td>
        <td>≥{{ rv.hsdir_tk_consensus_display }} (most) / {{ rv.hsdir_tk_max_display }} (strictest)</td>
        <td>
            {% if rv.hsdir_tk_meets %}
                <span style="color: #28a745; font-weight: bold;">Meets</span>
            {% else %}
                <span style="color: #dc3545; font-weight: bold;">Below</span>
            {% endif %}
        </td>
    </tr>
</tbody>
</table>
</div>
{% endif %}
```

**Variables Used (all from `relay.consensus_evaluation.relay_values`):**
- `wfu_display`, `wfu_meets` - WFU percentage and threshold comparison
- `tk_display`, `tk_meets`, `tk_days_needed` - Time Known values
- `observed_bw_display`, `guard_bw_guarantee_display`, `guard_bw_meets_guarantee`, `guard_bw_meets_some`, `guard_bw_meets_count` - Guard bandwidth
- `stable_mtbf_min_display`, `stable_mtbf_typical_display`, `stable_mtbf_meets_all`, `stable_mtbf_meets_count` - Stable MTBF
- `stable_uptime_display`, `stable_uptime_min_display`, `stable_uptime_typical_display`, `stable_uptime_meets_all`, `stable_uptime_meets_count` - Stable uptime
- `fast_speed_display`, `fast_minimum_display`, `fast_meets_minimum`, `fast_meets_all`, `fast_meets_count` - Fast bandwidth
- `hsdir_wfu_threshold`, `hsdir_wfu_meets`, `hsdir_tk_consensus_display`, `hsdir_tk_max_display`, `hsdir_tk_meets` - HSDir requirements

---

#### 3.2 Improve Issues/Warnings Display with Actionable Advice

**File:** `allium/lib/consensus/consensus_evaluation.py`

**Enhance `_identify_issues()` function (lines ~881-1120):**

The function already generates issues with suggestions. Enhancements to add:

**New Issue Categories to Add:**

```python
# Add to _identify_issues() function

# =========================================================================
# VERSION ISSUES
# =========================================================================
if 'version_status' in relay_data:  # Will need to pass relay_data to function
    version_status = relay_data.get('version_status', '')
    if version_status == 'obsolete':
        issues.append({
            'severity': 'warning',
            'category': 'version',
            'title': 'Obsolete Tor version',
            'description': f"Running version {relay_data.get('version', 'unknown')} which is obsolete",
            'suggestion': 'Upgrade to the latest stable Tor version. Check https://www.torproject.org/download/tor/ for current releases. On Debian/Ubuntu: apt update && apt upgrade tor',
            'doc_ref': 'https://community.torproject.org/relay/setup/',
        })
    elif version_status == 'unrecommended':
        issues.append({
            'severity': 'info',
            'category': 'version',
            'title': 'Unrecommended Tor version',
            'description': f"Running version {relay_data.get('version', 'unknown')} which is not recommended",
            'suggestion': 'Consider upgrading to a recommended version for best compatibility and security.',
        })

# =========================================================================
# FAMILY CONFIGURATION ISSUES
# =========================================================================
if relay_data.get('alleged_family'):
    alleged_count = len(relay_data['alleged_family'])
    issues.append({
        'severity': 'warning',
        'category': 'family',
        'title': 'Alleged family members detected',
        'description': f"{alleged_count} relay(s) in your MyFamily don't list you back",
        'suggestion': f"Contact the operators of these relays to add your fingerprint to their MyFamily configuration, or remove them from yours. Fingerprints: {', '.join(relay_data['alleged_family'][:3])}{'...' if alleged_count > 3 else ''}",
        'doc_ref': 'https://community.torproject.org/relay/setup/guard/#myfamily',
    })

if relay_data.get('indirect_family'):
    indirect_count = len(relay_data['indirect_family'])
    issues.append({
        'severity': 'info',
        'category': 'family',
        'title': 'Indirect family members detected',
        'description': f"{indirect_count} relay(s) list you as family but you don't list them",
        'suggestion': f"If you operate these relays, add them to your MyFamily. If not, no action needed. Fingerprints: {', '.join(relay_data['indirect_family'][:3])}{'...' if indirect_count > 3 else ''}",
    })

# =========================================================================
# AROI CONFIGURATION ISSUES
# =========================================================================
if relay_data.get('aroi_domain') and relay_data['aroi_domain'] != 'none':
    if relay_data.get('fingerprint') not in validated_fps:  # Need to pass validated_fps
        issues.append({
            'severity': 'info',
            'category': 'aroi',
            'title': 'AROI not validated',
            'description': f"AROI domain {relay_data['aroi_domain']} is configured but not cryptographically validated",
            'suggestion': 'Set up AROI validation using DNS-RSA or URI-RSA proof. See https://nusenu.github.io/ContactInfo-Information-Sharing-Specification/',
            'doc_ref': 'https://nusenu.github.io/ContactInfo-Information-Sharing-Specification/',
        })
```

**Function Signature Update:**

```python
def _identify_issues(
    consensus_data: dict, 
    current_flags: list = None, 
    observed_bandwidth: int = 0,
    relay_data: dict = None,  # NEW: Pass full relay data for version/family checks
    validated_fps: set = None  # NEW: Pass validated fingerprints for AROI checks
) -> List[dict]:
```

---

#### 3.3 Remove "Summary: Your Relay vs Consensus" Table

**File:** `allium/templates/relay-info.html`

**Delete Lines ~538-668:**

Remove the entire "Summary: Your Relay vs Consensus" section:
- Starts at: `{# ============== TABLE 1: SUMMARY (Quick Answers) ============== #}` (line ~538)
- Ends at: `{% endif %}` after the table (line ~668)

**Rationale:** This data is now distributed across:
- Health Status section (#status) - consensus status, vote count, issues
- Flags and Eligibility section (#flags) - flag requirements table
- Bandwidth section (#bandwidth) - measured bandwidth values

---

#### 3.4 Keep Per-Authority Details Table

**File:** `allium/templates/relay-info.html`

The Per-Authority Details table (lines ~671-920) should be **kept** as Section 9 (`#authority-votes`).

**Enhancements:**
1. Update section header to use new anchor pattern
2. Add introductory text explaining when to use this table
3. Keep the explanatory info boxes at the bottom

```jinja2
{# ============== SECTION 9: PER-AUTHORITY VOTE DETAILS ============== #}
<section id="authority-votes" class="relay-section">
<h3>
<div class="section-header">
<a href="#authority-votes" class="anchor-link">Per-Authority Vote Details</a>
</div>
</h3>

<p class="text-muted" style="font-size: 12px; margin-bottom: 10px;">
Advanced troubleshooting: Shows which specific directory authority is or isn't voting for your relay.
Data from <a href="https://collector.torproject.org/recent/relay-descriptors/votes/" target="_blank" rel="noopener">Tor CollecTor</a>
{% if relays.collector_fetched_at %}(fetched {{ relays.collector_fetched_at.replace('T', ' ').split('.')[0] }}){% endif %}.
</p>

{# Existing per-authority table content #}
...
```

---

#### 3.5 Add Backward-Compatible Anchor Aliases

**File:** `allium/templates/relay-info.html`

**Add at the top of the content div (after line 35):**

```jinja2
{# Backward-compatible anchor aliases - invisible anchor points for old URLs #}
<span id="network" style="display: none;"></span>
<span id="family" style="display: none;"></span>
<span id="location" style="display: none;"></span>
<span id="consensus-evaluation" style="display: none;"></span>

{# JavaScript for redirect (optional, for better UX) #}
<script>
// Redirect old anchors to new ones
document.addEventListener('DOMContentLoaded', function() {
    const redirects = {
        '#network': '#connectivity',
        '#location': '#connectivity', 
        '#family': '#operator',
        '#consensus-evaluation': '#authority-votes'
    };
    if (redirects[window.location.hash]) {
        window.location.hash = redirects[window.location.hash];
    }
});
</script>
```

**Alternative CSS-only approach (no JavaScript):**

```css
/* In skeleton.html CSS section */

/* Anchor aliases - position at the target section */
#network, #location {
    position: absolute;
    /* These will be positioned via template to sit at #connectivity */
}

#family {
    position: absolute;
    /* Positioned at #operator */
}
```

---

## Summary of All Files to Modify

### Template Files

| File | Phase | Changes |
|------|-------|---------|
| `allium/templates/relay-info.html` | 1, 2, 3 | Major restructure: emoji removal, new sections, reordering, flag table |
| `allium/templates/skeleton.html` | 2 | CSS additions for fluid layout, section styling |
| `allium/templates/macros.html` | 1 | Minor: update breadcrumb for relay pages (optional) |

### Python Files

| File | Phase | Changes |
|------|-------|---------|
| `allium/lib/consensus/consensus_evaluation.py` | 3 | Enhance `_identify_issues()` with new issue categories |

### Data/Variables Reference

**Variables Available in `relay-info.html` Template:**

| Variable | Type | Description | Source |
|----------|------|-------------|--------|
| `relay` | dict | Full relay data from Onionoo | `relays.json['relays'][i]` |
| `relay.consensus_evaluation` | dict | Formatted consensus data | `consensus_evaluation.py` |
| `relay.consensus_evaluation.relay_values` | dict | Threshold comparisons | `_format_relay_values()` |
| `relay.consensus_evaluation.authority_table` | list | Per-authority votes | `_format_authority_table_enhanced()` |
| `relay.consensus_evaluation.issues` | list | Detected issues | `_identify_issues()` |
| `relay.consensus_evaluation.reachability_summary` | dict | IPv4/IPv6 reach | `_format_reachability_summary()` |
| `relay.consensus_evaluation.bandwidth_summary` | dict | BW statistics | `_format_bandwidth_summary()` |
| `relay.consensus_evaluation.flag_summary` | dict | Flag eligibility | `_format_flag_summary()` |
| `relays` | Relays | Parent relay set object | `allium/lib/relays.py` |
| `relays.use_bits` | bool | Display in bits or bytes | CLI flag |
| `relays.timestamp` | str | Data freshness timestamp | Onionoo |
| `page_ctx` | dict | Page context (path_prefix, etc.) | `page_context.py` |
| `base_url` | str | Base URL for AROI links | Config |
| `validated_aroi_domains` | set | Validated AROI domains | AROI validation |

**Key Relay Fields Used:**

| Field | Type | Description |
|-------|------|-------------|
| `relay['nickname']` | str | Relay nickname |
| `relay['fingerprint']` | str | 40-char hex fingerprint |
| `relay['contact']` | str | Contact info string |
| `relay['contact_md5']` | str | MD5 hash for contact page |
| `relay['aroi_domain']` | str | AROI domain or 'none' |
| `relay['flags']` | list | Current consensus flags |
| `relay['or_addresses']` | list | OR addresses with ports |
| `relay['exit_address']` | str | Exit IP if different |
| `relay['dir_address']` | str | Directory address |
| `relay['country']` | str | 2-letter country code |
| `relay['country_name']` | str | Full country name |
| `relay['as']` | str | AS number (e.g., "AS24940") |
| `relay['as_name']` | str | AS organization name |
| `relay['observed_bandwidth']` | int | Observed BW in bytes/s |
| `relay['advertised_bandwidth']` | int | Advertised BW |
| `relay['measured']` | bool | BW authority measured |
| `relay['effective_family']` | list | Mutual family fingerprints |
| `relay['alleged_family']` | list | Alleged family |
| `relay['indirect_family']` | list | Indirect family |
| `relay['version']` | str | Tor version |
| `relay['version_status']` | str | recommended/obsolete/etc |
| `relay['uptime_display']` | str | "UP for X days" |
| `relay['last_restarted']` | str | Restart timestamp |

---

## Testing Checklist

### Phase 1 Testing
- [ ] All emoji icons replaced with text
- [ ] All new anchor links navigate correctly
- [ ] `:target` highlighting works for all anchors
- [ ] AROI appears as primary link when present
- [ ] Family appears as fallback when no AROI
- [ ] Contact info displays in header

### Phase 2 Testing
- [ ] Health Status section appears at top
- [ ] Issues/warnings display correctly
- [ ] Connectivity and Location section combines all address/geo data
- [ ] Operator and Family section shows AROI + family together
- [ ] Single-column layout fills width appropriately
- [ ] Responsive layout works on mobile (<768px)
- [ ] Fingerprint is full and copyable
- [ ] All 9 sections render in correct order

### Phase 3 Testing
- [ ] Flag Eligibility table shows all metrics
- [ ] Green/red/yellow status indicators work
- [ ] New issue categories appear (version, family, AROI)
- [ ] "Summary: Your Relay vs Consensus" table is removed
- [ ] Per-Authority Details table is preserved
- [ ] Backward-compatible anchors redirect correctly
- [ ] No duplicate information across sections

---

## References

- Gemini 3 Pro Proposal: `docs/RELAY_PAGE_REDESIGN_PROPOSAL.md`
- Opus 4.5 Proposal: `docs/features/planned/relay-page-layout-proposals.md`
- Current Template: `allium/templates/relay-info.html`
- Consensus Evaluation: `allium/lib/consensus/consensus_evaluation.py`
- tor-relays Mailing List: https://lists.torproject.org/pipermail/tor-relays/

---

*Document Version: 1.1*
*Created: 2024-12-29*
*Updated: 2024-12-29 - Added detailed implementation specifications*
*Consolidated from Gemini 3 Pro and Opus 4.5 proposals*
