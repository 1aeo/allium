# Documentation Improvement Proposal

**Goal**: Transform 117+ fragmented files into ~12 focused, accurate, maintainable documents.

**Principles**: Concise. Technical. Present and future focused. No history in active docs.

---

## 1. Verified Problems

### 1.1 Broken Links (confirmed)

| Source File | Broken Reference |
|-------------|------------------|
| `docs/api/README.md` | `onionoo-details.md`, `onionoo-uptime.md`, `onionoo-bandwidth.md` |
| `docs/architecture/README.md` | `intelligence-engine-design.md`, `data-pipeline.md` |
| `docs/development/performance.md` | `architecture/overview.md`, `architecture/data-pipeline.md` |
| `docs/user-guide/quick-start.md` | `ADVANCED.md`, `TROUBLESHOOTING.md` |
| `docs/features/README.md` | `docs/FEATURE_VERIFICATION.md` (actual: `archive/tracking-docs/`) |
| `docs/scripts/README.md` | `docs/implementation/`, `docs/performance/` |

### 1.2 CLI Documentation Drift

| Issue | Docs Say | Code (`allium.py`) Has |
|-------|----------|------------------------|
| Details URL flag | `--onionoo-url` | `--onionoo-details-url` |
| Missing options | - | `--base-url`, `--aroi-url`, `--apis`, `--filter-downtime`, `--workers` |

### 1.3 Output Structure Drift

| Issue | Docs Say | Code Generates |
|-------|----------|----------------|
| Index page | Top 500 relays | AROI leaderboards |
| Top 500 | `index.html` | `top500.html` |
| Relay pages | `relay/<fp>.html` | `relay/<fp>/index.html` |
| Search index | Not documented | `search-index.json` |

### 1.4 Feature Count Drift

| Issue | Docs Say | Code Has |
|-------|----------|----------|
| AROI categories | 17 | 18 (includes AROI Validation Champions) |

### 1.5 Content Problems

| Issue | Impact |
|-------|--------|
| 117 markdown files | Unmaintainable |
| Historical content in active docs | "Migration complete," "before/after," dated milestones |
| Celebratory tone/emojis | Conflicts with technical focus |
| Duplicate roadmaps | 3+ files with overlapping content |
| Deep nesting (4+ levels) | Hard to navigate |

---

## 2. Proposed Structure

```
docs/
├── README.md                    # Entry point (links only, no content duplication)
├── STYLE.md                     # Documentation standards (keeps docs maintainable)
│
├── user-guide/
│   ├── quick-start.md           # Install, first run, verify output
│   ├── configuration.md         # All CLI options (matches --help exactly)
│   ├── deployment.md            # NEW: nginx, GitHub Pages, Cloudflare, --base-url
│   └── troubleshooting.md       # NEW: common errors, solutions
│
├── reference/
│   ├── current-capabilities.md  # Single source: what works now (verified against code)
│   ├── output-structure.md      # Generated file tree, page purposes
│   └── api-integration.md       # Onionoo + AROI validator + CollecTor (self-contained)
│
├── architecture/
│   ├── overview.md              # Data flow, module purposes
│   └── multiprocessing.md       # Keep (already accurate)
│
├── development/
│   ├── contributing.md          # Setup, PR process, code style
│   ├── testing.md               # How to run tests (no history)
│   └── security.md              # Practices (no audit history)
│
├── features/
│   └── planned/                 # KEEP AS-IS: Future work, roadmap, proposals
│       └── ...                  # All existing files untouched
│
└── screenshots/                 # Keep 2-3 key images
```

**Total: ~15 core active files + features/planned/* (untouched)**

**Deleted**:
- `docs/archive/` - Git preserves history
- `docs/scripts/` - All obsolete
- `docs/features/implemented/` - Consolidated to reference/
- `docs/studies/`

---

## 3. Detailed File Specifications

### 3.1 `docs/README.md` (Entry Point)

**Purpose**: Navigation hub only. No duplicated content.

```markdown
# Allium Documentation

## For Users
- [Quick Start](user-guide/quick-start.md) - Install and run
- [Configuration](user-guide/configuration.md) - CLI options
- [Deployment](user-guide/deployment.md) - Web server setup
- [Troubleshooting](user-guide/troubleshooting.md) - Common issues

## Reference
- [Current Capabilities](reference/current-capabilities.md) - What works now
- [Output Structure](reference/output-structure.md) - Generated files
- [API Integration](reference/api-integration.md) - Data sources

## For Contributors
- [Contributing](development/contributing.md) - Setup and PR process
- [Architecture](architecture/overview.md) - System design
- [Planned Features](features/planned/README.md) - Roadmap and proposals

## Archive
- [Historical Documents](archive/README.md) - Past reports (reference only)
```

**Size**: ~30 lines

---

### 3.2 `docs/STYLE.md` (Documentation Contract)

**Purpose**: Prevent drift. Define rules.

```markdown
# Documentation Standards

## Rules
1. No history in active docs (history → `archive/`)
2. No emojis in headings (allowed in body only when mirroring UI)
3. No dated milestones ("Q1 2025") - use Now/Next/Later
4. All CLI options must match `python3 allium.py --help` exactly
5. All output paths must match actual generated files

## Doc Template
Every doc must include:
- **Audience**: Who this is for
- **Scope**: What this covers
- **How to verify**: Command to confirm accuracy

## Review Checklist
- [ ] Links resolve
- [ ] CLI flags match code
- [ ] Output paths match generated files
- [ ] No "migration," "completed," "before/after" language
```

**Size**: ~50 lines

---

### 3.3 `docs/user-guide/configuration.md` (Must Match Code)

**Critical fixes needed**:

| Option | Default | Description |
|--------|---------|-------------|
| `--out` | `./www` | Output directory |
| `--onionoo-details-url` | `https://onionoo.torproject.org/details` | Details API |
| `--onionoo-uptime-url` | `https://onionoo.torproject.org/uptime` | Uptime API |
| `--onionoo-bandwidth-url` | `https://onionoo.torproject.org/bandwidth` | Bandwidth API |
| `--aroi-url` | `https://aroivalidator.1aeo.com/latest.json` | AROI validator |
| `--bandwidth-cache-hours` | `12` | Bandwidth cache TTL |
| `--display-bandwidth-units` | `bits` | `bits` or `bytes` |
| `--apis` | `all` | `details` (~400MB) or `all` (~2.4GB) |
| `--filter-downtime` | `7` | Filter relays offline >N days (0=disable) |
| `--workers` | `4` | Parallel workers (0=disable multiprocessing) |
| `--base-url` | `""` | Base URL for vanity URLs |
| `--progress` | `false` | Show progress |

**Usage profiles**:

```bash
# Low memory (~400MB)
python3 allium.py --apis details --workers 2

# Full analytics (~2.4GB)
python3 allium.py --apis all --progress

# Disable multiprocessing (debugging)
python3 allium.py --workers 0
```

---

### 3.4 `docs/user-guide/deployment.md` (NEW)

**Content**:
- `--base-url` behavior for subdirectory hosting
- nginx configuration example
- Apache configuration example
- GitHub Pages setup
- Cloudflare Pages setup (with `search-index.json` function)
- Cron automation for updates

---

### 3.5 `docs/user-guide/troubleshooting.md` (NEW)

**Content**: Collect scattered error handling into one place:
- "Jinja2 not found"
- "Permission denied"
- "Python version too old"
- "No module named 'lib'"
- Memory errors with `--apis all`
- Network/API failures

---

### 3.6 `docs/reference/current-capabilities.md` (Single Source of Truth)

**Purpose**: One canonical doc for "what works now." Must be verified against code.

**Content outline**:

```markdown
# Current Capabilities

## Generator
- Multi-threaded API fetching (details, uptime, bandwidth, AROI, CollecTor)
- Multiprocessing page generation (4 workers default)
- Memory modes: details-only (~400MB) or full (~2.4GB)

## AROI Leaderboards (18 categories)
1. Bandwidth Capacity Contributed
2. Consensus Weight Leaders
3. Exit Authority Champions
4. Guard Authority Champions
5. Exit Operators
6. Guard Operators
7. Reliability Masters (6-month, 25+ relays)
8. Legacy Titans (5-year, 25+ relays)
9. Bandwidth Served Masters (6-month, 25+ relays)
10. Bandwidth Served Legends (5-year, 25+ relays)
11. Most Diverse Operators
12. Platform Diversity Heroes
13. Non-EU Leaders
14. Frontier Builders
15. Network Veterans
16. IPv4 Address Leaders
17. IPv6 Address Leaders
18. AROI Validation Champions

## Network Health Dashboard
10-card system: relay counts, bandwidth, consensus weight, geographic diversity,
platform analysis, authority health, flag distribution, performance metrics.

## Directory Authorities Page
Uptime statistics, Z-score analysis, version compliance, consensus participation.

## Search Index
`search-index.json` for Cloudflare Pages function (relay search).

## Intelligence Engine
6-layer analysis: relationships, concentration, performance correlation,
infrastructure, geographic clustering, capacity distribution.
```

---

### 3.7 `docs/reference/output-structure.md` (NEW)

**Purpose**: Document actual generated file tree.

```markdown
# Output Structure

## Generated Files

www/
├── index.html                 # AROI leaderboards (main page)
├── top500.html                # Top 500 relays by consensus weight
├── network-health.html        # Network health dashboard
├── search-index.json          # Search data for Cloudflare function
├── misc/
│   ├── all.html               # All relays
│   ├── aroi-leaderboards.html # AROI leaderboards (duplicate)
│   ├── authorities.html       # Directory authorities
│   ├── families-by-*.html     # Family listings
│   ├── networks-by-*.html     # AS listings
│   ├── contacts-by-*.html     # Contact listings
│   ├── countries-by-*.html    # Country listings
│   └── platforms-by-*.html    # Platform listings
├── relay/<fingerprint>/index.html  # Individual relay pages
├── contact/<hash>/index.html       # Contact pages
├── country/<code>/index.html       # Country pages
├── as/<number>/index.html          # AS pages
├── family/<hash>/index.html        # Family pages
├── platform/<name>/index.html      # Platform pages
├── flag/<name>/index.html          # Flag pages
├── first_seen/<date>/index.html    # First seen pages
└── static/                         # CSS, images, flags
```

---

### 3.8 `docs/reference/api-integration.md` (Self-Contained)

**Purpose**: Replace broken stub links with actual content.

```markdown
# API Integration

## Data Sources

### Onionoo Details API
- **URL**: `https://onionoo.torproject.org/details`
- **Memory**: ~400MB during processing
- **Fields used**: fingerprint, nickname, flags, bandwidth, country, platform, etc.
- **Failure behavior**: Exit with error

### Onionoo Uptime API
- **URL**: `https://onionoo.torproject.org/uptime`
- **Memory**: ~2GB during processing
- **Fields used**: uptime history, flag history
- **Failure behavior**: Graceful degradation (reliability features disabled)

### Onionoo Bandwidth API
- **URL**: `https://onionoo.torproject.org/bandwidth`
- **Memory**: ~500MB during processing
- **Cache**: Configurable (default 12 hours)
- **Failure behavior**: Graceful degradation

### AROI Validator API
- **URL**: `https://aroivalidator.1aeo.com/latest.json`
- **Purpose**: Authenticated relay operator identification
- **Failure behavior**: AROI features disabled

### CollecTor Consensus (optional)
- **Purpose**: Consensus evaluation, flag thresholds
- **Failure behavior**: Graceful degradation
```

---

### 3.9 `docs/features/planned/README.md` (Update Existing)

**Purpose**: Update existing README to use Now/Next/Later framing instead of dated quarters.

**Changes to make**:
- Replace "Q1 2025", "Q2 2025" etc. with Now/Next/Later priorities
- Keep all existing proposal files as-is
- Update links if any are broken

```markdown
# Planned Features

## Priority: Now (Active Development)
- [Search Implementation](search-implementation-plan.md)

## Priority: Next (Planned)
- [Interactive Visualizations](milestone-1-graphs-charts.md)
- [Enhanced Authority Monitoring](milestone-2-authority-health.md)

## Priority: Later (Proposals)
- [Network Health Enhancements](milestone-3-network-health.md)
- [AI Analytics](milestone-4-ai-analytics.md)
- [Community Tools](milestone-5-community-tools.md)

## All Proposals
[Keep existing file listings...]
```

**Note**: Existing proposal files in `features/planned/` are kept. Only update the README index and remove dated timeline references where they appear.

---

## 4. Files to Delete/Move

### Move to Archive

```bash
# Historical reports - move to archive/
mv docs/POST_MERGE_CLEANUP_COMPLETE.md docs/archive/tracking-docs/
mv docs/features/implemented/IMPLEMENTED_FEATURES_SUMMARY.md docs/archive/
```

### Delete After Content Extracted

```bash
# Old structure - delete after new docs created
docs/features/implemented/     # 30+ files → reference/current-capabilities.md
docs/features/README.md        # → reference/ (features/planned/ README stays)
docs/user-guide/README.md      # Content moves to user-guide/*.md
docs/user-guide/features.md    # → reference/current-capabilities.md
docs/user-guide/updating.md    # → user-guide/configuration.md
docs/api/README.md             # → reference/api-integration.md
docs/development/README.md     # → development/contributing.md
docs/development/performance.md # Remove history, keep tips in contributing.md
docs/ROADMAP.md                # Consolidate with features/planned/README.md
docs/studies/                  # → archive/ or delete
```

### Keep As-Is

```bash
# Future work - keep existing structure
docs/features/planned/         # Keep all files, update README only
docs/features/planned/README.md # Update to Now/Next/Later framing
```

### Scripts Decision: DELETE ENTIRE DIRECTORY

`docs/scripts/` contains 11 Python files. **Analysis result: Delete all.**

| Script | Reason to Delete |
|--------|------------------|
| `comprehensive-validation.py` | Hardcoded paths (`/home/tor/metrics/...`), historical |
| `memory-profiler.py` | Hardcoded paths, historical |
| `performance-tester.py` | Hardcoded paths, historical |
| `before-after-performance.py` | **Dangerous** - modifies code directly, historical |
| `focused-country-benchmark.py` | Historical, optimization complete |
| `simple-validation.py` | Hardcoded paths, historical |
| `validate-aroi-totals.py` | Expects non-existent `allium/data.json` |
| `validate-flag-uptime-calculations.py` | Redundant - tests exist in `tests/test_uptime_utils.py` |
| `fix-html-injection-vulnerabilities.py` | One-time fix already applied |
| `reporting/tier1_report_generator.py` | Historical report generator |

**Action**: `rm -rf docs/scripts/`

---

## 5. Writing Style Rules

### Do

| Pattern | Example |
|---------|---------|
| Present tense | "Allium generates 18 AROI leaderboards" |
| Action-first | "Run `pytest` to execute tests" |
| Specific numbers | "Uses ~2.4GB memory with `--apis all`" |
| Code references | "See `lib/aroileaders.py`" |

### Don't

| Pattern | Why |
|---------|-----|
| "We successfully implemented..." | History |
| "Migration completed on..." | History |
| "Q1 2025" | Dates go stale |
| "Before/after" | History |
| "🎯 Executive Summary" | Excessive emojis |

### Emoji Rules

- **Allowed**: In body text when mirroring UI labels (e.g., "⏰ Reliability Masters")
- **Not allowed**: In headings, navigation, or general prose

---

## 6. Verification Procedures

### 6.1 Link Integrity Check

```bash
# Install markdown link checker
npm install -g markdown-link-check

# Check all docs
find docs -name "*.md" -exec markdown-link-check {} \;

# Or add CI job:
# .github/workflows/docs.yml
```

### 6.2 CLI Accuracy Check

```bash
# Generate CLI reference from code
python3 allium/allium.py --help > /tmp/cli-help.txt

# Compare against docs/user-guide/configuration.md
# All options must match exactly (names, defaults, descriptions)
```

### 6.3 Output Accuracy Check

```bash
# Generate with minimal API
python3 allium/allium.py --out /tmp/allium-test --apis details --progress

# Verify documented paths exist
test -f /tmp/allium-test/index.html || echo "FAIL: index.html"
test -f /tmp/allium-test/top500.html || echo "FAIL: top500.html"
test -f /tmp/allium-test/network-health.html || echo "FAIL: network-health.html"
test -f /tmp/allium-test/search-index.json || echo "FAIL: search-index.json"
test -d /tmp/allium-test/misc || echo "FAIL: misc/"
test -d /tmp/allium-test/relay || echo "FAIL: relay/"

# Check relay page structure (should be relay/<fp>/index.html)
ls /tmp/allium-test/relay/*/index.html | head -1
```

### 6.4 Feature Accuracy Check

```bash
# Count AROI categories in generated HTML
grep -c "category" /tmp/allium-test/misc/aroi-leaderboards.html

# Should match docs (currently 18)
```

### 6.5 Present/Future Separation Check

```bash
# Search for history language in active docs (should return nothing)
# Note: features/planned/ is excluded since roadmap docs may reference timelines
grep -rn "migration\|completed on\|before/after" docs/ \
  --include="*.md" \
  --exclude-dir=archive \
  --exclude-dir=planned

# If results, those docs need editing
```

---

## 7. Implementation Plan

### Phase 1: Create New Structure (Safe - No Deletions)

1. Create `docs/STYLE.md`
2. Create `docs/user-guide/deployment.md`
3. Create `docs/user-guide/troubleshooting.md`
4. Create `docs/reference/` directory
5. Create `docs/reference/current-capabilities.md`
6. Create `docs/reference/output-structure.md`
7. Create `docs/reference/api-integration.md`
8. Create `docs/architecture/overview.md`

### Phase 2: Fix Existing Files

1. Fix `docs/user-guide/configuration.md` - correct CLI flags, add missing options
2. Fix `docs/user-guide/quick-start.md` - remove broken links, fix output paths
3. Fix `docs/development/testing.md` - remove history sections
4. Fix `docs/development/security.md` - remove history sections
5. Update `docs/README.md` to new navigation structure

### Phase 3: Update Planned Features

1. Update `docs/features/planned/README.md` - Now/Next/Later framing (remove Q1/Q2 dates)
2. Consolidate `docs/ROADMAP.md` content into `docs/features/planned/README.md`
3. Fix any broken links within planned features docs
4. Rename files with spaces (e.g., `2nd - ARCHITECTURE_COMPARISON.md` → `architecture-comparison.md`)

### Phase 4: Delete Obsolete

1. Delete `docs/archive/` entirely (Git preserves history)
2. Delete `docs/scripts/` entirely (all obsolete)
3. Delete `docs/POST_MERGE_CLEANUP_COMPLETE.md`
4. Delete `docs/features/implemented/` (after content extracted to reference/)
5. Delete `docs/features/README.md` (navigation now in docs/README.md)
6. Delete `docs/ROADMAP.md` (consolidated into features/planned/README.md)
7. Delete `docs/studies/`
8. Delete empty/stub API docs

### Phase 6: Verify

Run all verification procedures from Section 6.

---

## 8. Acceptance Criteria

### Correctness
- [ ] All CLI options in docs match `python3 allium.py --help`
- [ ] All output paths in docs match actual generated files
- [ ] AROI category count matches code (18)
- [ ] API URLs match code defaults

### Conciseness
- [ ] No doc exceeds 400 lines
- [ ] No duplicate content across files
- [ ] No history language in active docs

### Completeness
- [ ] User can install, configure, deploy using only user-guide/
- [ ] Contributor can setup, test, PR using only development/
- [ ] All current features documented in reference/

### Maintainability
- [ ] STYLE.md defines clear rules
- [ ] Single source of truth for each topic
- [ ] Verification scripts exist and pass

### Navigation
- [ ] All internal links resolve
- [ ] docs/README.md provides clear paths
- [ ] No more than 2 clicks to any doc

---

## 9. Decisions Made

| Question | Decision |
|----------|----------|
| **Archive policy** | Delete `docs/archive/` entirely (Git preserves history) |
| **Scripts** | Delete `docs/scripts/` entirely (all obsolete/redundant) |
| **Screenshots** | Keep in `docs/screenshots/` |
| **Root README** | Keep detailed (362 lines) |
| **Planned features** | Don't touch `docs/features/planned/` - keep as-is |
| **Spec template** | Required for new specs only, existing planned features untouched |
