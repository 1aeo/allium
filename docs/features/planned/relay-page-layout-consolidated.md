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
- **Operator info (AROI) with validation status:**
  - Operator domain and relay count (links to operator page)
  - AROI validation status: "Validated (10/12 relays)" or "Partially Validated" or "Unvalidated"
  - This relay's validation: "This relay: Validated" or "This relay: Unvalidated"
- **Family info (always shown, separate from AROI):**
  - Family count with link to family page
  - Fingerprint-based grouping (may differ from AROI count)
- Quick links: AS, Country, Platform

**AROI and Family - Both Displayed:**
- **AROI:** Verified operator identity with accurate relay grouping. Shows validation status at operator level (how many relays validated) and relay level (is THIS relay validated).
- **Family:** Fingerprint-based grouping. Always shown separately. May have mismatches (alleged/indirect members).
- Both provide value: AROI for verified identity, Family for declared relationships.

**What moves to sections below:**
- Detailed family member lists (effective/alleged/indirect) → `#operator` section
- Detailed AROI validation details → `#operator` section
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
| Header row | AROI Operator | Domain + relay count (link to operator page) |
| Header row | AROI Validation | "Validated (X/Y)" or "Partially Validated" or "Unvalidated" |
| Header row | This Relay AROI | "This relay: Validated" or "This relay: Unvalidated" |
| Header row | Family | Relay count (link to family page) - always shown |
| Header h4 | AS link | Quick link |
| Header h4 | Country link | Quick link |
| Header h4 | Platform link | Quick link |
| Header | Last fetch timestamp | Data freshness indicator |

**AROI and Family - Both Displayed:**
- **Operator (AROI):** Shows operator domain and relay count. Links to operator page.
- **AROI Validation Status:** Shows how many of operator's relays are cryptographically validated.
  - "Validated (10/12 relays)" - all or most relays validated
  - "Partially Validated (5/12 relays)" - some relays validated
  - "Unvalidated" - no validation proof found
- **This Relay AROI:** Shows if THIS specific relay's fingerprint is in the AROI proof.
  - "This relay: Validated" - fingerprint found in proof
  - "This relay: Unvalidated" - fingerprint not in proof (error shown on hover)
- **Family:** Always shown separately. Fingerprint-based grouping with link to family page.

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
║  EXAMPLE WITH AROI:                                                                                                  ║
║  Operator: example.com (12 relays) [View All]       AROI: Validated (10/12 relays) | This relay: Validated           ║
║  Family: 5 relays [View]                                                                                             ║
║  ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────── ║
║  AS24940  |  Germany  |  Linux                                                     Last updated: 2024-12-29 14:30 UTC║
║                                                                                                                      ║
║  EXAMPLE WITHOUT AROI (Family always shown):                                                                         ║
║  Family: 3 relays [View]                                                                                             ║
║  ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────── ║
║  AS24940  |  Germany  |  Linux                                                     Last updated: 2024-12-29 14:30 UTC║
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
┃ Operator (AROI)                                     ┃ Family (fingerprint-based)                      [#effective-family]┃
┃                                                     ┃                                                                  ┃
┃   Domain: example.com                               ┃ Effective Family: 5 relays [View Family Page]                   ┃
┃   Relays by this operator: 12 [View All]            ┃   ABCD1234EFGH5678... (this relay)                               ┃
┃                                                     ┃   WXYZ9876LMNO5432...                                            ┃
┃   AROI Validation:                                  ┃   HIJK4567DEFG8901...                                            ┃
┃     Operator: Validated (10/12 relays)              ┃   STUV2345WXYZ6789...                                            ┃
┃     This relay: Validated (DNS-RSA proof)           ┃   EFGH8901IJKL2345...                                            ┃
┃                                                     ┃                                                        [#alleged-family]┃
┃   Contact: admin@example.com                        ┃ Alleged Family: 2 relays                                        ┃
┃                                                     ┃   (They don't list you back - check their MyFamily config)      ┃
┃ When NO AROI:                                       ┃   QRST1111UVWX2222...                                            ┃
┃   Operator: Not specified                           ┃   MNOP3333STUV4444...                                            ┃
┃   Contact: admin@example.com                        ┃                                                       [#indirect-family]┃
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
║  WITH AROI:                               ║
║  Operator: example.com (12 relays)        ║
║  AROI: Validated (10/12 relays)           ║
║  This relay: Validated                    ║
║  Family: 5 relays                         ║
║                                           ║
║  WITHOUT AROI (Family always shown):      ║
║  Family: 3 relays                         ║
║                                           ║
║  AS24940 | DE | Linux                     ║
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
┃ Operator (AROI)                           ┃
┃   Domain: example.com                     ┃
┃   Relays: 12 [View All]                   ┃
┃   AROI: Validated (10/12)                 ┃
┃   This relay: Validated                   ┃
┃   Contact: admin@example.com              ┃
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

#### 1.4 Move Contact to Page Header, Add AROI + Family with Validation Status

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

Shows BOTH AROI operator AND Family, plus AROI validation status at operator and relay level.

```jinja2
{# ============== OPERATOR & FAMILY ROW ============== #}
{# Shows AROI operator info (when present) AND Family info (always) #}
<div class="header-operator-row" style="margin-bottom: 8px;">
    {# AROI Operator Info - when AROI domain is present #}
    {% if relay['aroi_domain'] and relay['aroi_domain'] != 'none' -%}
        <div class="aroi-info" style="margin-bottom: 4px;">
            {# Operator link #}
            {% if base_url and relay['aroi_domain'] in validated_aroi_domains -%}
                <a href="{{ base_url }}/{{ relay['aroi_domain']|lower|escape }}/" title="Verified operator - view all relays">
                    <strong>Operator:</strong> {{ relay['aroi_domain']|escape }}</a>
            {% else -%}
                <a href="{{ page_ctx.path_prefix }}contact/{{ relay['contact_md5'] }}/" title="Operator page">
                    <strong>Operator:</strong> {{ relay['aroi_domain']|escape }}</a>
            {% endif -%}
            
            {# AROI Validation Status - Operator level #}
            {% if contact_validation_status and contact_validation_status.validation_summary -%}
                {% set vs = contact_validation_status.validation_summary -%}
                {% set status = contact_validation_status.validation_status -%}
                | <span class="aroi-status">AROI: 
                {% if status == 'validated' -%}
                    <span style="color: #28a745;" title="All {{ vs.validated_count }} relays have valid AROI proof">
                        Validated ({{ vs.validated_count }}/{{ vs.total_relays }})</span>
                {% elif status == 'partially_validated' -%}
                    <span style="color: #ffc107;" title="{{ vs.validated_count }} of {{ vs.total_relays }} relays validated">
                        Partially Validated ({{ vs.validated_count }}/{{ vs.total_relays }})</span>
                {% else -%}
                    <span style="color: #dc3545;" title="No relays have AROI validation proof">Unvalidated</span>
                {% endif -%}
                </span>
                
                {# AROI Validation Status - This Relay #}
                {% set this_fp = relay.fingerprint -%}
                | <span class="aroi-relay-status">This relay: 
                {% if this_fp in contact_validation_status.validated_fingerprints -%}
                    <span style="color: #28a745;" title="This relay's fingerprint found in AROI proof">Validated</span>
                {% else -%}
                    <span style="color: #dc3545;" title="This relay's fingerprint not in AROI proof">Unvalidated</span>
                {% endif -%}
                </span>
            {% elif relay['aroi_domain'] in validated_aroi_domains -%}
                | <span style="color: #28a745;">AROI: Validated</span>
            {% else -%}
                | <span style="color: #ffc107;">AROI: Unvalidated</span>
            {% endif -%}
        </div>
    {% endif -%}
    
    {# Family Info - always shown (separate from AROI) #}
    <div class="family-info">
        {% if relay['effective_family']|length > 1 -%}
            <a href="{{ page_ctx.path_prefix }}family/{{ relay['fingerprint']|escape }}/" title="View family members">
                <strong>Family:</strong> {{ relay['effective_family']|length }} relays</a>
        {% else -%}
            <strong>Family:</strong> {{ relay['effective_family']|length }} relay
        {% endif -%}
        {% if relay['alleged_family'] and relay['alleged_family']|length > 0 -%}
            <span style="color: #856404; font-size: 11px;" title="You list these relays but they don't list you back">
                ({{ relay['alleged_family']|length }} alleged)</span>
        {% endif -%}
    </div>
</div>

{# ============== QUICK LINKS ROW ============== #}
<h4>
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
- `relay['aroi_domain']` (str) - AROI domain from contact info parsing
- `relay['contact_md5']` (str) - MD5 hash of contact for contact page link
- `relay['contact']` (str) - Raw contact string
- `relay['effective_family']` (list) - List of family member fingerprints
- `relay['alleged_family']` (list) - Relays you list but don't list you back
- `validated_aroi_domains` (set) - Set of validated AROI domains (from template context)
- `base_url` (str) - Base URL for validated AROI links
- `contact_validation_status` (dict) - Full AROI validation status (see section 2.3.1)
- `contact_validation_status.validation_status` (str) - 'validated', 'partially_validated', 'unvalidated'
- `contact_validation_status.validation_summary` (dict) - Contains validated_count, total_relays
- `contact_validation_status.validated_fingerprints` (set) - Set of validated relay fingerprints

**Display Logic Summary:**

| Condition | Operator (AROI) Row | AROI Validation Status | Family Row |
|-----------|---------------------|------------------------|------------|
| Has AROI + validated | Show domain link | "Validated (X/Y)" + "This relay: Validated/Unvalidated" | **Always shown** - count + link |
| Has AROI + partial | Show domain link | "Partially Validated (X/Y)" + "This relay: ..." | **Always shown** - count + link |
| Has AROI + unvalidated | Show domain link | "Unvalidated" | **Always shown** - count + link |
| No AROI | Not shown | Not shown | **Always shown** - count + link |

**Key Rule:** Family is ALWAYS displayed in header, regardless of AROI presence.

---

### Phase 2: Layout Restructure

**Estimated Effort:** 8-16 hours
**Files to Modify:** 
- `allium/templates/relay-info.html` (major restructure)
- `allium/templates/skeleton.html` (CSS additions)

#### 2.1 Add Health Status Summary Section at Top

**File:** `allium/templates/relay-info.html`

**Overview:**
The enhanced Health Status section displays 14 metrics in 8 display cells using a responsive two-column layout (60/40 split). On desktop (≥768px), metrics display in a 60/40 column split. On mobile (<768px), metrics stack in priority order.

**Desktop Wireframe (60/40 split):**

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Health Status                                                               [#status] ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Consensus      IN CONSENSUS — 9/9 authorities      ┃ Reachability  IPv4: 9/9 | v6: 5/5┃
┃ Flags          Guard, Stable, Fast, HSDir... (7)   ┃ Uptime        UP 1mo 1w | 99%(1M)┃
┃ Cons. Weight   0.04% of network (98 Mbit/s meas.)  ┃ Bandwidth     419 Mbit/s (Meas.) ┃
┃ First Seen     2y 3mo ago                          ┃ Version       0.4.8.14 [OK]      ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Issues Detected:                                                                      ┃
┃   • High consensus weight deviation: Large variation across authorities...            ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

**Mobile Wireframe (single column, <768px):**

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Health Status               [#status] ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Consensus    IN CONSENSUS — 9/9       ┃
┃ Reachability IPv4: 9/9 | v6: 5/5      ┃
┃ Flags        Guard, Stable, Fast... 7 ┃
┃ Uptime       UP 1mo 1w | 99% (1M)     ┃
┃ Cons. Weight 0.04% (98 Mbit/s meas.)  ┃
┃ Bandwidth    419 Mbit/s (Measured)    ┃
┃ First Seen   2y 3mo ago               ┃
┃ Version      0.4.8.14 [OK]            ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Issues Detected:                      ┃
┃   • High consensus weight deviation...┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

**Metrics Mapping (14 metrics → 8 cells):**

| Cell | Label | Metrics Merged | Source Variables | Example Display |
|------|-------|----------------|------------------|-----------------|
| 1 | Consensus | Consensus In/Out + Authority Vote Count | `diag.in_consensus`, `diag.vote_count`, `diag.total_authorities` | IN CONSENSUS — 9/9 authorities |
| 2 | Reachability | IPv4 Count + IPv6 Count | `diag.reachability_summary.ipv4.*`, `diag.reachability_summary.ipv6.*` | IPv4: 9/9 \| v6: 5/5 |
| 3 | Flags | Flags List + Count | `relay['flags']` | Guard, Stable, Fast, HSDir... (7) |
| 4 | Uptime | Current Session + Historical 1M% | `relay['uptime_display']`, `relay['uptime_api_display']` | UP 1mo 1w \| 99% (1M) |
| 5 | Cons. Weight | Network Fraction + Authority Median | `relay['consensus_weight_fraction']`, `diag.bandwidth_summary.median_display` | 0.04% of network (98 Mbit/s meas.) |
| 6 | Bandwidth | Observed Bandwidth + Measured Status | `relay['observed_bandwidth']`, `relay['measured']`, `diag.bandwidth_summary.measurement_count` | 419 Mbit/s (Measured by 6) |
| 7 | First Seen | Relay Age | `relay['first_seen']` | 2y 3mo ago |
| 8 | Version | Version + Recommended Status | `relay['version']`, `relay['recommended_version']`, `relay['version_status']` | 0.4.8.14 [OK] or 0.4.7.8 [Warning] obsolete |

**Priority Order (for mobile stacking):**

| Priority | Metric | Rationale |
|----------|--------|-----------|
| 1 | Consensus | "Is my relay working at all?" — #1 question |
| 2 | Reachability | If not in consensus, check this first |
| 3 | Flags | "What roles can my relay play?" |
| 4 | Uptime | "How stable is my relay?" |
| 5 | Cons. Weight | "How much traffic am I getting?" |
| 6 | Bandwidth | "Is my bandwidth being measured?" |
| 7 | First Seen | "How old is my relay?" — explains missing flags |
| 8 | Version | Least urgent — good to know but rarely the problem |

**CSS (add to `<style>` section in relay-info.html):**

```css
/* Health Status Grid Layout */
.health-status-grid {
    display: grid;
    grid-template-columns: 1.2fr 1fr;  /* 60/40 split */
    gap: 8px 24px;
}

.health-status-grid dl {
    margin: 0;
    font-size: 14px;
}

.health-status-grid .health-row {
    display: flex;
    align-items: baseline;
    margin-bottom: 8px;
}

.health-status-grid dt {
    width: 100px;
    font-weight: bold;
    color: #495057;
    flex-shrink: 0;
}

.health-status-grid dd {
    margin: 0;
    flex: 1;
}

/* Responsive: Stack on mobile */
@media (max-width: 767px) {
    .health-status-grid {
        grid-template-columns: 1fr;
    }
}
```

**HTML/Jinja2 Template (insert after header, after line 67):**

```jinja2
{# ============== HEALTH STATUS SUMMARY (Enhanced) ============== #}
{# Displays 14 metrics in 8 cells using responsive 2-column layout #}
{% set diag = relay.consensus_evaluation if relay.consensus_evaluation and relay.consensus_evaluation.available else none %}

<div id="status" style="margin: 15px 0; padding: 15px; background: #f8f9fa; border-radius: 8px; border-left: 4px solid {% if diag and diag.in_consensus %}#28a745{% elif 'Running' in relay['flags'] %}#28a745{% else %}#dc3545{% endif %};">

<h4 style="margin-top: 0; margin-bottom: 12px;">
    <div class="section-header">
        <a href="#status" class="anchor-link">Health Status</a>
    </div>
</h4>

<div class="health-status-grid">
    {# LEFT COLUMN (60%) #}
    <dl>
        {# Row 1 Left: Consensus Status (merges: in_consensus + vote_count) #}
        <div class="health-row">
            <dt>Consensus</dt>
            <dd>
                {% if diag -%}
                    {% if diag.in_consensus -%}
                        <span style="color: #28a745; font-weight: bold;">IN CONSENSUS</span>
                        <span style="color: #6c757d;">— {{ diag.vote_count }}/{{ diag.total_authorities }} authorities</span>
                    {% else -%}
                        <span style="color: #dc3545; font-weight: bold;">NOT IN CONSENSUS</span>
                        <span style="color: #6c757d;">— {{ diag.vote_count }}/{{ diag.total_authorities }} authorities (need {{ diag.majority_required }})</span>
                    {% endif -%}
                {% elif 'Running' in relay['flags'] -%}
                    <span style="color: #28a745; font-weight: bold;">IN CONSENSUS</span>
                    <span style="color: #6c757d;">— has Running flag</span>
                {% else -%}
                    <span style="color: #dc3545; font-weight: bold;">NOT IN CONSENSUS</span>
                {% endif -%}
            </dd>
        </div>

        {# Row 2 Left: Flags #}
        <div class="health-row">
            <dt>Flags</dt>
            <dd>
                {% set flag_list = relay['flags']|reject('equalto', 'StaleDesc')|list -%}
                {% set flag_count = flag_list|length -%}
                {% for flag in flag_list -%}
                    <a href="{{ page_ctx.path_prefix }}flag/{{ flag.lower()|escape }}/">{{ flag|escape }}</a>{% if not loop.last %}, {% endif %}
                {% endfor -%}
                <span style="color: #6c757d;">({{ flag_count }})</span>
                {% if 'StaleDesc' in relay['flags'] -%}
                    <br><span style="color: #dc3545; font-size: 12px;">[Warning] StaleDesc</span>
                {% endif -%}
            </dd>
        </div>

        {# Row 3 Left: Consensus Weight (merges: fraction + authority median) #}
        <div class="health-row">
            <dt>Cons. Weight</dt>
            <dd>
                {% if relay['consensus_weight_fraction'] -%}
                    <span title="Fraction of total network consensus weight">{{ "%.2f"|format(relay['consensus_weight_fraction'] * 100) }}% of network</span>
                    {% if diag and diag.bandwidth_summary and diag.bandwidth_summary.median_display -%}
                        <span style="color: #6c757d;">({{ diag.bandwidth_summary.median_display }} meas.)</span>
                    {% endif -%}
                {% else -%}
                    <span style="color: #6c757d;">N/A</span>
                {% endif -%}
            </dd>
        </div>

        {# Row 4 Left: First Seen #}
        <div class="health-row">
            <dt>First Seen</dt>
            <dd>
                {% if relay['first_seen'] -%}
                    <a href="{{ page_ctx.path_prefix }}first_seen/{{ relay['first_seen'].split(' ', 1)[0]|escape }}/">{{ relay['first_seen']|format_time_ago }}</a>
                {% else -%}
                    <span style="color: #6c757d;">Unknown</span>
                {% endif -%}
            </dd>
        </div>
    </dl>

    {# RIGHT COLUMN (40%) #}
    <dl>
        {# Row 1 Right: Reachability (merges: IPv4 + IPv6) #}
        <div class="health-row">
            <dt>Reachability</dt>
            <dd>
                {% if diag and diag.reachability_summary -%}
                    IPv4: <span style="color: {% if diag.reachability_summary.ipv4.status_class == 'success' %}#28a745{% else %}#dc3545{% endif %}; font-weight: bold;">{{ diag.reachability_summary.ipv4.reachable_count }}/{{ diag.reachability_summary.ipv4.total }}</span>
                    {% if diag.reachability_summary.ipv6.total > 0 -%}
                        | v6: <span style="color: {% if diag.reachability_summary.ipv6.status_class == 'success' %}#28a745{% elif diag.reachability_summary.ipv6.status_class == 'muted' %}#6c757d{% else %}#dc3545{% endif %}; font-weight: bold;">{{ diag.reachability_summary.ipv6.reachable_count }}/{{ diag.reachability_summary.ipv6.total }}</span>
                    {% endif -%}
                {% else -%}
                    <span style="color: #6c757d;">N/A</span>
                {% endif -%}
            </dd>
        </div>

        {# Row 2 Right: Uptime (merges: current session + historical 1M%) #}
        <div class="health-row">
            <dt>Uptime</dt>
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
                {% if relay.get('uptime_api_display') -%}
                    {# Extract 1M percentage from uptime_api_display (format: "X%/Y%/Z%/W%") #}
                    {% set uptime_parts = relay['uptime_api_display']|striptags|replace('%', '')|replace(' ', '')|split('/') -%}
                    {% if uptime_parts and uptime_parts[0] -%}
                        | <span style="color: #6c757d;">{{ uptime_parts[0] }}% (1M)</span>
                    {% endif -%}
                {% endif -%}
            </dd>
        </div>

        {# Row 3 Right: Bandwidth (merges: observed + measured status) #}
        <div class="health-row">
            <dt>Bandwidth</dt>
            <dd>
                {% set obs_unit = relay['observed_bandwidth']|determine_unit(relays.use_bits) -%}
                {% set obs_bandwidth = relay['observed_bandwidth']|format_bandwidth_with_unit(obs_unit) -%}
                <span title="Relay's observed bandwidth capacity">{{ obs_bandwidth }} {{ obs_unit }}</span>
                {% if diag and diag.bandwidth_summary and diag.bandwidth_summary.measurement_count -%}
                    <span style="color: #28a745;">(Measured by {{ diag.bandwidth_summary.measurement_count }})</span>
                {% elif relay['measured'] -%}
                    <span style="color: #28a745;">(Measured)</span>
                {% elif relay['measured'] is none -%}
                    <span style="color: #6c757d;">(Unknown)</span>
                {% else -%}
                    <span style="color: #856404;">(Not measured)</span>
                {% endif -%}
            </dd>
        </div>

        {# Row 4 Right: Version (merges: version + recommended status) #}
        <div class="health-row">
            <dt>Version</dt>
            <dd>
                {% if relay['version'] -%}
                    <span>{{ relay['version']|escape }}</span>
                    {% if relay['recommended_version'] is not none -%}
                        {% if relay['recommended_version'] -%}
                            <span style="color: #28a745;" title="Version is recommended">[OK]</span>
                        {% else -%}
                            <span style="color: #dc3545;" title="Version is {{ relay['version_status']|default('not recommended') }}">[Warning] {{ relay['version_status']|default('not recommended')|escape }}</span>
                        {% endif -%}
                    {% endif -%}
                {% else -%}
                    <span style="color: #6c757d;">Unknown</span>
                {% endif -%}
            </dd>
        </div>
    </dl>
</div>

{# Issues and Warnings - Full width below grid #}
{% if diag and diag.issues %}
{% set real_issues = diag.issues | selectattr('severity', 'ne', 'info') | list %}
{% set info_notes = diag.issues | selectattr('severity', 'equalto', 'info') | list %}

{% if real_issues %}
<div style="margin-top: 12px; padding: 10px; background: #fff3cd; border-radius: 4px; border-left: 3px solid #ffc107;">
    <strong style="color: #856404;">Issues Detected:</strong>
    <ul style="margin: 5px 0 0 0; padding-left: 20px;">
    {% for issue in real_issues %}
        <li style="margin-bottom: 5px;">
            <span style="color: {% if issue.severity == 'error' %}#dc3545{% else %}#856404{% endif %}; font-weight: bold;">
                {{ issue.title }}
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
<div style="margin-top: 10px; padding: 10px; background: #d1ecf1; border-radius: 4px; border-left: 3px solid #17a2b8;">
    <strong style="color: #0c5460;">Notes:</strong>
    <ul style="margin: 5px 0 0 0; padding-left: 20px;">
    {% for note in info_notes %}
        <li style="font-size: 12px;">{{ note.title }}: {{ note.description }}</li>
    {% endfor %}
    </ul>
</div>
{% endif %}
{% elif diag %}
<div style="margin-top: 12px; padding: 10px; background: #d4edda; border-radius: 4px; border-left: 3px solid #28a745;">
    <span style="color: #155724;"><strong>No issues detected.</strong> Relay appears to be operating normally.</span>
</div>
{% endif %}

</div>
```

**Display Logic Details:**

| Metric | Logic |
|--------|-------|
| **Consensus** | IF `diag.in_consensus`: "IN CONSENSUS — {vote_count}/{total} authorities"<br>ELSE: "NOT IN CONSENSUS — {vote_count}/{total} (need {majority})"<br>FALLBACK: Check Running flag |
| **Reachability** | "IPv4: {reachable}/{total}" + IF ipv6.total > 0: " \| v6: {reachable}/{total}" |
| **Flags** | "{flag1}, {flag2}... ({count})" + IF StaleDesc: show warning |
| **Uptime** | "{uptime_display}" + IF uptime_api_display: " \| {1M%}% (1M)" |
| **Cons. Weight** | "{fraction * 100}% of network" + IF median: "({median} meas.)" |
| **Bandwidth** | "{observed formatted}" + measurement status indicator |
| **First Seen** | "{first_seen\|format_time_ago}" (e.g., "2y 3mo ago") |
| **Version** | "{version}" + IF recommended: "[OK]" ELIF not: "[Warning] {status}" |

**Data Source Reference:**

| Variable | Source | Description |
|----------|--------|-------------|
| `diag` | `relay.consensus_evaluation` | Consensus evaluation object (from CollecTor) |
| `diag.in_consensus` | CollecTor votes | Boolean: relay in consensus |
| `diag.vote_count` | CollecTor votes | Number of authorities that voted for relay |
| `diag.total_authorities` | CollecTor votes | Total directory authorities (typically 9) |
| `diag.majority_required` | Calculated | floor(total/2) + 1 (typically 5) |
| `diag.reachability_summary.ipv4.reachable_count` | CollecTor votes | Authorities that reached relay via IPv4 |
| `diag.reachability_summary.ipv4.total` | CollecTor votes | Authorities that tested IPv4 |
| `diag.reachability_summary.ipv6.reachable_count` | CollecTor votes | Authorities that reached relay via IPv6 |
| `diag.reachability_summary.ipv6.total` | CollecTor votes | Authorities that test IPv6 (not all do) |
| `diag.bandwidth_summary.median_display` | CollecTor votes | Median of authority-measured bandwidth |
| `diag.bandwidth_summary.measurement_count` | CollecTor votes | Number of authorities that measured bandwidth |
| `diag.issues` | Consensus evaluation | List of detected issues/warnings |
| `relay['flags']` | Onionoo API | List of current flags |
| `relay['uptime_display']` | Calculated | Formatted current uptime (e.g., "UP 1mo 1w 4d") |
| `relay['uptime_api_display']` | Onionoo API | Historical uptime percentages (1M/6M/1Y/5Y) |
| `relay['consensus_weight_fraction']` | Onionoo API | Fraction of total network consensus weight |
| `relay['observed_bandwidth']` | Onionoo API | Relay's self-reported observed bandwidth (bytes/s) |
| `relay['measured']` | Onionoo API | Boolean: bandwidth measured by ≥3 authorities |
| `relay['first_seen']` | Onionoo API | UTC timestamp when relay first appeared |
| `relay['version']` | Onionoo API | Tor software version |
| `relay['recommended_version']` | Onionoo API | Boolean: version is recommended |
| `relay['version_status']` | Onionoo API | Status: recommended, experimental, obsolete, etc. |

**Testing Checklist:**

- [ ] Health Status section displays at top of relay page
- [ ] Two-column layout displays correctly on desktop (≥768px)
- [ ] Single-column layout stacks correctly on mobile (<768px)
- [ ] Priority order maintained when stacked (Consensus → Reachability → Flags → Uptime → Cons. Weight → Bandwidth → First Seen → Version)
- [ ] Consensus status shows correct IN/NOT IN with authority count
- [ ] Reachability shows IPv4 count; shows IPv6 only if relay has IPv6
- [ ] Flags list displays with count; StaleDesc shows warning
- [ ] Uptime shows current session + 1M historical percentage
- [ ] Consensus Weight shows network fraction + authority median
- [ ] Bandwidth shows observed capacity + measured status
- [ ] First Seen displays formatted time ago
- [ ] Version shows version number + recommended/obsolete status
- [ ] Issues section displays below grid when issues exist
- [ ] "No issues detected" message shows when relay is healthy
- [ ] All anchor links work (#status)
- [ ] Colors indicate status (green=good, red=bad, yellow=warning, gray=unknown)

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
            {% else -%}
                <a href="{{ page_ctx.path_prefix }}contact/{{ relay['contact_md5'] }}/">{{ relay['aroi_domain']|escape }}</a>
            {% endif -%}
        {% else -%}
            Not specified
        {% endif -%}
    </dd>
    
    {# AROI Validation Status - Operator level (how many relays validated) #}
    {% if contact_validation_status and contact_validation_status.validation_summary -%}
    <dt>Operator Validation</dt>
    <dd>
        {% set vs = contact_validation_status.validation_summary -%}
        {% set status = contact_validation_status.validation_status -%}
        {% if status == 'validated' -%}
            <span style="color: #28a745;" title="All {{ vs.validated_count }} relays have valid AROI proof">
                Validated ({{ vs.validated_count }}/{{ vs.total_relays }} relays)</span>
        {% elif status == 'partially_validated' -%}
            <span style="color: #ffc107;" title="{{ vs.validated_count }} of {{ vs.total_relays }} relays have valid proof">
                Partially Validated ({{ vs.validated_count }}/{{ vs.total_relays }} relays)</span>
        {% else -%}
            <span style="color: #dc3545;" title="No relays have AROI validation proof">Unvalidated</span>
        {% endif -%}
    </dd>
    
    {# AROI Validation Status - This relay specifically #}
    <dt>This Relay</dt>
    <dd>
        {% set this_fp = relay.fingerprint -%}
        {% if this_fp in contact_validation_status.validated_fingerprints -%}
            <span style="color: #28a745;" title="This relay's fingerprint found in AROI proof">Validated</span>
            {% for vr in contact_validation_status.validated_relays if vr.fingerprint == this_fp -%}
                <span style="font-size: 11px; color: #666;">({{ vr.proof_type }})</span>
            {% endfor -%}
        {% elif relay['aroi_domain'] and relay['aroi_domain'] != 'none' -%}
            <span style="color: #dc3545;" title="AROI configured but fingerprint not in proof">Unvalidated</span>
            {% for ur in contact_validation_status.unvalidated_relays if ur.fingerprint == this_fp -%}
                <span style="font-size: 11px; color: #856404;">({{ ur.error }})</span>
            {% endfor -%}
        {% else -%}
            <span style="color: #6c757d;">N/A (no AROI configured)</span>
        {% endif -%}
    </dd>
    {% endif -%}
    
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
    When validated, it cryptographically proves relay ownership.
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
- `contact_validation_status` (dict) - Full AROI validation data (see section 2.3.1)
- `contact_validation_status.validation_status` (str) - 'validated', 'partially_validated', 'unvalidated'
- `contact_validation_status.validation_summary` (dict) - {validated_count, total_relays, validation_rate}
- `contact_validation_status.validated_fingerprints` (set) - Set of validated relay fingerprints
- `contact_validation_status.validated_relays` (list) - List with fingerprint, proof_type details
- `contact_validation_status.unvalidated_relays` (list) - List with fingerprint, error details

---

#### 2.3.1 Backend: Pass AROI Validation Status to Relay Pages

**Purpose:**
Display detailed AROI validation status for the operator, showing how many relays are cryptographically validated vs unvalidated.

**Backend Requirement:**
To enable AROI validation status in relay pages, `contact_validation_status` must be passed to the template.

**File:** `allium/lib/relays.py` (in `write_relay_info()` method)

**Add to `write_relay_info()`:**
```python
def write_relay_info(self):
    """..."""
    relay_list = self.json["relays"]
    template = ENV.get_template("relay-info.html")
    output_path = os.path.join(self.output_dir, "relay")
    # ... existing setup code ...

    for relay in relay_list:
        if not relay["fingerprint"].isalnum():
            continue
        
        # ... existing code for contact_display_data and standard_contexts ...
        
        # NEW: Get AROI validation status for this relay's contact
        contact_validation_status = self._get_contact_validation_status_for_relay(relay)
        
        rendered = template.render(
            relay=relay, 
            page_ctx=page_ctx, 
            relays=self, 
            contact_display_data=contact_display_data,
            contact_validation_status=contact_validation_status,  # NEW
            validated_aroi_domains=self.validated_aroi_domains if hasattr(self, 'validated_aroi_domains') else set(),
            base_url=self.base_url
        )
        # ... rest of method ...

def _get_contact_validation_status_for_relay(self, relay):
    """
    Get AROI validation status for a single relay's contact.
    
    Returns dict with:
    - validation_status: 'validated', 'partially_validated', 'unvalidated'
    - validation_summary: {validated_count, unvalidated_count, total_relays, validation_rate}
    - validated_relays: list of {fingerprint, nickname, proof_type}
    - unvalidated_relays: list of {fingerprint, nickname, error}
    """
    contact_hash = relay.get('contact_md5')
    if not contact_hash:
        return None
    
    # Check if validation status was already computed for this contact
    contact_data = self.json.get("sorted", {}).get("contact", {}).get(contact_hash)
    if contact_data and 'contact_validation_status' in contact_data:
        return contact_data['contact_validation_status']
    
    # Compute on-demand (fallback for edge cases)
    relay_indices = contact_data.get("relays", []) if contact_data else []
    members = [self.json["relays"][idx] for idx in relay_indices] if relay_indices else [relay]
    return self._get_contact_validation_status(members)
```

**Template Enhancement:**

**File:** `allium/templates/relay-info.html` (in Operator and Family section)

**Enhanced AROI Validation Display:**
```jinja2
{# In Operator Identity section, after AROI Domain #}

{% if contact_validation_status and contact_validation_status.validation_summary %}
    <dt>Validation Status</dt>
    <dd>
        {% set vs = contact_validation_status.validation_summary %}
        {% set status = contact_validation_status.validation_status %}
        {% if status == 'validated' %}
            <span style="color: #28a745;" title="All {{ vs.validated_count }} relays cryptographically validated">
                Validated ({{ vs.validated_count }}/{{ vs.total_relays }})
            </span>
        {% elif status == 'partially_validated' %}
            <span style="color: #ffc107;" title="{{ vs.validated_count }} of {{ vs.total_relays }} relays validated">
                Partially Validated ({{ vs.validated_count }}/{{ vs.total_relays }})
            </span>
        {% else %}
            <span style="color: #dc3545;" title="No relays have AROI validation">
                Unvalidated
            </span>
        {% endif %}
    </dd>
{% endif %}

{# Show this relay's specific validation status #}
{% if contact_validation_status %}
    {% set this_fp = relay.fingerprint %}
    {% if this_fp in contact_validation_status.validated_fingerprints %}
        <dt>This Relay</dt>
        <dd>
            <span style="color: #28a745;" title="This relay's fingerprint was found in AROI proof">
                Validated
            </span>
            {% for vr in contact_validation_status.validated_relays if vr.fingerprint == this_fp %}
                <span style="font-size: 11px; color: #666;">({{ vr.proof_type }})</span>
            {% endfor %}
        </dd>
    {% elif relay['aroi_domain'] and relay['aroi_domain'] != 'none' %}
        <dt>This Relay</dt>
        <dd>
            <span style="color: #dc3545;" title="This relay has AROI configured but is not validated">
                Unvalidated
            </span>
            {% for ur in contact_validation_status.unvalidated_relays if ur.fingerprint == this_fp %}
                <span style="font-size: 11px; color: #856404;">({{ ur.error }})</span>
            {% endfor %}
        </dd>
    {% endif %}
{% endif %}
```

**New Variables Available in Template:**
| Variable | Type | Description |
|----------|------|-------------|
| `contact_validation_status` | dict/None | Full validation status for this contact |
| `contact_validation_status.validation_status` | str | 'validated', 'partially_validated', 'unvalidated' |
| `contact_validation_status.validation_summary.validated_count` | int | Count of validated relays |
| `contact_validation_status.validation_summary.unvalidated_count` | int | Count of unvalidated relays |
| `contact_validation_status.validation_summary.total_relays` | int | Total relay count |
| `contact_validation_status.validation_summary.validation_rate` | float | Percentage (0-100) |
| `contact_validation_status.validated_relays` | list | List of validated relay details |
| `contact_validation_status.unvalidated_relays` | list | List of unvalidated relay details |
| `contact_validation_status.validated_fingerprints` | set | Set of validated fingerprints for O(1) lookup |

**Data Source:** `allium/lib/aroi_validation.py` - `get_contact_validation_status()` function

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

/* Fingerprint display - full and easily selectable (no JS needed) */
.fingerprint-full {
    font-family: Consolas, "Courier New", monospace;
    font-size: 12px;
    word-break: break-all;
    user-select: all;  /* Select entire text on click */
    cursor: pointer;
    background: #f8f9fa;
    padding: 4px 8px;
    border-radius: 4px;
    display: inline-block;
}

.fingerprint-full:hover {
    background: #e8e8e8;
}

.fingerprint-full:focus,
.fingerprint-full::selection {
    background: #cce5ff;
    outline: 2px solid #007bff;
}
```

---

#### 2.5 Move Fingerprint to Header, Make Full and Selectable

**File:** `allium/templates/relay-info.html`

**Update Header Section (lines 35-38):**

```jinja2
<div id="content" class="relay-page-content">
<h2>View Relay "{{ relay['nickname'] }}"</h2>

{# Full fingerprint - CSS makes it easily selectable for copying #}
<p style="margin-bottom: 10px;">
    <strong>Fingerprint:</strong> 
    <code class="fingerprint-full" id="relay-fingerprint" title="Click to select, then Ctrl+C to copy">{{ relay['fingerprint']|escape }}</code>
</p>

{% set relay_data = {'nickname': relay['nickname'], 'fingerprint': relay['fingerprint'], 'as_number': relay['as']} %}
{{ navigation('all', page_ctx) }}
```

**CSS-only copy approach (in skeleton.html):**

```css
/* Fingerprint styling - full width, easily selectable */
.fingerprint-full {
    font-family: monospace;
    font-size: 12px;
    background: #f5f5f5;
    padding: 4px 8px;
    border-radius: 4px;
    user-select: all;  /* Select entire text on click */
    cursor: pointer;
    display: inline-block;
    word-break: break-all;
}

.fingerprint-full:hover {
    background: #e8e8e8;
}

/* Visual hint on focus */
.fingerprint-full:focus,
.fingerprint-full::selection {
    background: #cce5ff;
    outline: 2px solid #007bff;
}
```

**How it works:**
- `user-select: all` makes the entire fingerprint select on a single click
- User then presses Ctrl+C (or Cmd+C) to copy
- No JavaScript required
- Title attribute provides hint to users

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

#### 3.4 Add Data Source Comparison Table and Keep Per-Authority Details

**File:** `allium/templates/relay-info.html`

The Consensus Evaluation section (`#consensus-evaluation`) should include:
1. **NEW:** Data Source Comparison table (Onionoo vs CollecTor side-by-side)
2. **KEEP:** Per-Authority Details table for advanced troubleshooting

This is the appropriate location for the side-by-side comparison because users who reach this section are in "troubleshooting mode" and want to understand data discrepancies.

**Add Data Source Comparison Table (insert before Per-Authority Details):**

```jinja2
{# ============== DATA SOURCE COMPARISON ============== #}
{# For troubleshooting: Compare Onionoo (aggregated) vs CollecTor (per-authority) data #}
{% if diag %}
<div style="margin-bottom: 20px;">
<h4 style="margin-bottom: 10px;">
<div class="section-header">
<a href="#data-sources" class="anchor-link">Data Source Comparison</a>
</div>
</h4>
<p class="text-muted" style="font-size: 12px; margin-bottom: 10px;">
Compare aggregated Onionoo API data with per-authority CollecTor data. Discrepancies may indicate data freshness differences or authority-specific issues.
</p>

<table class="table table-condensed table-striped" style="font-size: 13px; max-width: 800px;">
<thead>
    <tr>
        <th style="width: 25%;">Metric</th>
        <th style="width: 37%;">Onionoo (API)</th>
        <th style="width: 38%;">Dir. Authorities (CollecTor)</th>
    </tr>
</thead>
<tbody>
    <tr>
        <td><strong>Consensus Status</strong></td>
        <td>
            {% if 'Running' in relay['flags'] -%}
                <span style="color: #28a745;">In consensus</span> (has Running flag)
            {% else -%}
                <span style="color: #dc3545;">Not in consensus</span>
            {% endif -%}
        </td>
        <td>
            {% if diag.in_consensus -%}
                <span style="color: #28a745;">In consensus</span>
            {% else -%}
                <span style="color: #dc3545;">Not in consensus</span>
            {% endif -%}
            — {{ diag.vote_count }}/{{ diag.total_authorities }} voted (need {{ diag.majority_required }})
        </td>
    </tr>
    <tr>
        <td><strong>Bandwidth Measured</strong></td>
        <td>
            {% if relay['measured'] is not none -%}
                {% if relay['measured'] -%}
                    <span style="color: #28a745;">Yes</span> (≥3 authorities)
                {% else -%}
                    <span style="color: #dc3545;">No</span>
                {% endif -%}
            {% else -%}
                <span style="color: #6c757d;">Unknown</span>
            {% endif -%}
        </td>
        <td>
            {% if diag.bandwidth_summary and diag.bandwidth_summary.measurement_count -%}
                <span style="color: #28a745;">{{ diag.bandwidth_summary.measurement_count }} measurements</span>
                {% if diag.bandwidth_summary.median_display -%}
                    (median: {{ diag.bandwidth_summary.median_display }})
                {% endif -%}
            {% else -%}
                <span style="color: #6c757d;">0 measurements</span>
            {% endif -%}
        </td>
    </tr>
    <tr>
        <td><strong>Flags</strong></td>
        <td>
            {% for flag in relay['flags'] -%}
                {% if flag != 'StaleDesc' -%}
                    {{ flag|escape }}{% if not loop.last %}, {% endif %}
                {% endif -%}
            {% endfor -%}
        </td>
        <td>
            {% if diag.flag_summary -%}
                {% for flag_name, flag_data in diag.flag_summary.items() %}
                    {% set display_name = 'HSDir' if flag_name.lower() == 'hsdir' else flag_name|capitalize %}
                    <span style="color: {% if flag_data.status_class == 'success' %}#28a745{% elif flag_data.status_class == 'danger' %}#dc3545{% else %}#856404{% endif %};">
                        {{ display_name }}: {{ flag_data.eligible_count }}/{{ flag_data.total_authorities }}
                    </span>{% if not loop.last %}, {% endif %}
                {% endfor %}
            {% else -%}
                <span style="color: #6c757d;">No data</span>
            {% endif -%}
        </td>
    </tr>
</tbody>
</table>
</div>
{% endif %}
```

**Keep Per-Authority Details Table:**

The existing Per-Authority Details table (currently lines ~671-920) should be **kept** as Section 9 (`#authority-votes`).

**Enhancements:**
1. Update section header to use new anchor pattern
2. Add introductory text explaining when to use this table
3. Keep the explanatory info boxes at the bottom

```jinja2
{# ============== PER-AUTHORITY VOTE DETAILS ============== #}
<section id="authority-votes" class="relay-section">
<h4>
<div class="section-header">
<a href="#authority-votes" class="anchor-link">Per-Authority Vote Details</a>
</div>
</h4>

<p class="text-muted" style="font-size: 12px; margin-bottom: 10px;">
Advanced troubleshooting: Shows which specific directory authority is or isn't voting for your relay.
Data from <a href="https://collector.torproject.org/recent/relay-descriptors/votes/" target="_blank" rel="noopener">Tor CollecTor</a>
{% if relays.collector_fetched_at %}(fetched {{ relays.collector_fetched_at.replace('T', ' ').split('.')[0] }}){% endif %}.
</p>

{# Existing per-authority table content #}
...
```

**Variables Used for Data Source Comparison:**

| Variable | Type | Source | Purpose |
|----------|------|--------|---------|
| `relay['flags']` | list | Onionoo | Current consensus flags |
| `relay['measured']` | bool | Onionoo | Bandwidth measured status |
| `diag.in_consensus` | bool | CollecTor | Consensus status from votes |
| `diag.vote_count` | int | CollecTor | Number of authorities voting |
| `diag.total_authorities` | int | CollecTor | Total authorities (9) |
| `diag.majority_required` | int | CollecTor | Votes needed (5) |
| `diag.bandwidth_summary.measurement_count` | int | CollecTor | Bandwidth measurements |
| `diag.bandwidth_summary.median_display` | str | CollecTor | Median bandwidth value |
| `diag.flag_summary` | dict | CollecTor | Per-flag eligibility counts |

---

#### 3.5 Add Backward-Compatible Anchor Aliases

**File:** `allium/templates/relay-info.html`

**CSS-only approach (no JavaScript):**

Place invisible anchor elements immediately before the target sections they should redirect to:

```jinja2
{# Backward-compatible anchor aliases #}
{# Place these invisible spans immediately before their target sections #}

{# Before #connectivity section: #}
<span id="network" style="position: absolute; visibility: hidden;"></span>
<span id="location" style="position: absolute; visibility: hidden;"></span>
<section id="connectivity" ...>

{# Before #operator section: #}
<span id="family" style="position: absolute; visibility: hidden;"></span>
<section id="operator" ...>
```

**Styling in skeleton.html:**

```css
/* Anchor aliases - invisible but targetable */
span#network, span#location, span#family {
    position: absolute;
    visibility: hidden;
    pointer-events: none;
}
```

**How it works:**
- When a user visits `#network`, the browser scrolls to the invisible `<span id="network">` 
- Since the span is positioned immediately before `#connectivity`, the user sees the correct section
- No JavaScript required - pure CSS/HTML solution

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
| `contact_validation_status` | dict/None | Full AROI validation status for relay's contact | `aroi_validation.py` |
| `contact_display_data` | dict | Pre-computed contact display data | `relays.py` |

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
- [ ] AROI validation status shows validated/partially/unvalidated with counts
- [ ] Per-relay validation indicator shows for current relay
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
