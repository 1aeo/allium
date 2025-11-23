# Documentation Reorganization Plan - REVISED

**Date**: 2025-11-23
**Status**: APPROVED - Ready for Phase 1
**Approach**: Conservative - Start simple, verify at each step

---

## 🎯 Key Changes from Original Plan

### User Feedback Incorporated:
1. ✅ **Performance & Security**: Keep at high level (current status), archive only implementation details
2. ✅ **Example Data**: Move 1aeo_relays_data.json to development/example-data/ for mock testing
3. ✅ **Features/Roadmap**: Keep organized at higher level, verify against codebase
4. ✅ **Verification**: Check output directory directly, no localhost needed
5. ✅ **Aggressiveness**: Less aggressive, keep more historical context
6. ✅ **Execution**: Start simple, check-in for validation before proceeding

---

## 📊 Target Structure

```
docs/
├── README.md                          # Simple navigation (20 lines)
├── ROADMAP.md                         # NEW - High-level future vision
│
├── user-guide/                        # User-facing docs
│   ├── README.md
│   ├── quick-start.md                 # MOVED from GETTING_STARTED.md
│   ├── configuration.md               # NEW
│   ├── updating.md                    # NEW
│   └── features.md                    # NEW - what allium does
│
├── features/                          # REORGANIZED
│   ├── README.md                      # Clear implemented vs planned
│   ├── implemented/                   # NEW - verified features only
│   │   └── [verified after testing]
│   └── planned/                       # NEW - future features
│       └── [unimplemented proposals]
│
├── architecture/                      # System design
│   ├── README.md
│   ├── overview.md                    # NEW
│   ├── data-pipeline.md               # NEW
│   └── template-optimization.md       # RENAMED
│
├── development/                       # Developer docs
│   ├── README.md                      # NEW
│   ├── contributing.md                # NEW
│   ├── testing.md                     # MOVED from TEST_NAMING_STANDARDS.md
│   ├── example-data/                  # NEW
│   │   ├── README.md                  # Explain mock data
│   │   └── 1aeo_relays_data.json      # MOVED from proposals/
│   ├── performance.md                 # NEW - current status & priorities
│   └── security.md                    # NEW - current status & priorities
│
├── api/                               # API docs
│   ├── README.md
│   ├── onionoo-details.md
│   ├── onionoo-uptime.md
│   └── onionoo-bandwidth.md
│
├── scripts/                           # Dev scripts
│   └── README.md                      # IMPROVED
│
├── screenshots/                       # Visual assets
│
└── archive/                           # Historical docs
    ├── README.md                      # Index with dates
    ├── implementation-reports/        # Completed impl details
    ├── performance-details/           # Historical perf details
    └── security-details/              # Historical security details
```

---

## 🚀 PHASE 1: FOUNDATION (THIS PHASE)

### Step 1.1: ✅ Generate BEFORE Snapshot
**Status**: COMPLETED
**Output**: `/tmp/allium-before/`
**Verified**:
- 21,716 HTML files generated successfully
- AROI leaderboards present (13 categories found)
- Network health dashboard present
- Directory authorities page present
- All main features confirmed working

### Step 1.2: Create Verification Document
**Status**: COMPLETED
**File**: `docs/FEATURE_VERIFICATION.md`
**Purpose**: Document what actually exists in generated output before any changes

### Step 1.3: Create New Directory Structure (NEXT)
**Actions**:
```bash
# Create new directories (empty for now)
mkdir -p docs/user-guide
mkdir -p docs/features/implemented
mkdir -p docs/features/planned
mkdir -p docs/development/example-data
mkdir -p docs/api
mkdir -p docs/archive/implementation-reports
mkdir -p docs/archive/performance-details
mkdir -p docs/archive/security-details
```

### Step 1.4: Create README Files
**Actions**: Create placeholder README files for each new directory explaining purpose

---

## 📋 PHASE 2: PERFORMANCE & SECURITY (AFTER PHASE 1 VALIDATION)

### Current State:
- `docs/performance/` has 4 files (README + 3 optimization reports)
- `docs/security/` has 4 files (README + 3 audit reports)

### Transformation:

#### New: `docs/development/performance.md`
```markdown
# Performance Guide

## Current Status
- Page load times: <2s for most pages
- Memory usage: ~3GB peak during generation
- Generation time: ~5 minutes for full site

## Active Priorities
1. Reduce memory usage to <2GB
2. Optimize template rendering
3. Improve caching strategies

## Performance Testing
[Link to testing procedures]

## Historical Reports
See [archive/performance-details/](../archive/performance-details/)
```

#### New: `docs/development/security.md`
```markdown
# Security Guide

## Current Status
- XSS Protection: ✅ Jinja2 autoescape enabled
- Input Validation: ✅ All external data sanitized
- Output Sanitization: ✅ HTML escaping utilities

## Active Priorities
1. Regular dependency updates
2. Security code reviews
3. Penetration testing

## Security Testing
[Link to testing procedures]

## Historical Audits
See [archive/security-details/](../archive/security-details/)
```

### Archive Implementation Details:
- MOVE: `performance/aroi-leaderboard-ultra-optimization.md` → `archive/performance-details/`
- MOVE: `performance/duplicate-merging-optimization.md` → `archive/performance-details/`
- MOVE: `performance/jinja2-template-optimization-results.md` → `archive/performance-details/`
- MOVE: `security/aroi-security-audit-report.md` → `archive/security-details/`
- MOVE: `security/html-injection-audit-report.md` → `archive/security-details/`
- MOVE: `security/html-injection-fixes-summary.md` → `archive/security-details/`

---

## 📁 PHASE 3: EXAMPLE DATA (AFTER PHASE 2 VALIDATION)

### Current:
- `docs/proposals/1aeo_relays_data.json` (7.9MB)

### New Location:
- `docs/development/example-data/1aeo_relays_data.json`
- `docs/development/example-data/README.md`

### README Content:
```markdown
# Example Relay Data

## Purpose
This directory contains example/mock data for:
- Unit testing
- Development without network access
- Understanding data structure
- Documentation examples

## Files

### 1aeo_relays_data.json
**Size**: 7.9MB
**Type**: Real Onionoo API response (anonymized)
**Use Cases**:
- Mock data for unit tests
- Example of API response structure
- Development without live API calls

## Usage in Tests
```python
import json

# Load example data
with open('docs/development/example-data/1aeo_relays_data.json') as f:
    mock_data = json.load(f)

# Use in tests
def test_relay_processing():
    relays = Relays(mock_data)
    assert len(relays.json['relays']) > 0
```
```

---

## 🗂️ PHASE 4: FEATURES REORGANIZATION (AFTER PHASE 3 VALIDATION)

### Current State:
- 28 files in `docs/features/`
- Mix of implemented (✅) and proposed features
- Unclear which are actually working

### Approach:
1. **Keep all files initially** - no deletions
2. **Create subdirectories** - `implemented/` and `planned/`
3. **Move files based on verification** - use FEATURE_VERIFICATION.md
4. **Update features/README.md** - clear navigation

### Verified Implemented (Move to features/implemented/):
- After full verification complete, move only confirmed features

### Keep in features/ root:
- Feature specifications
- System design documents
- Active development docs

### Move to features/planned/:
- Milestone 1-5 docs
- Future proposals
- Enhancement ideas

---

## 🗑️ FILES TO DELETE (MINIMAL - AFTER ALL PHASES)

### Only Delete Obviously Redundant:
```
❌ docs/proposals/1aeo_relays_data.json (MOVE to development/example-data/)
❌ docs/features/RELIABILITY_SYSTEM_UPDATES.md (duplicates complete-reliability-system.md)
❌ docs/implementation/documentation-reorganization-report.md (meta-doc about old reorg)
❌ docs/implementation/merge_plan_top10page.md (completed merge)
❌ docs/implementation/pagination_documentation_update_summary.md (superseded)
```

### Everything Else: KEEP or ARCHIVE
- Keep historical context
- Archive completed work
- Preserve all ideas and proposals

---

## ✅ VALIDATION CHECKPOINTS

### After Phase 1:
- [ ] All new directories created
- [ ] New README files in place
- [ ] No existing files moved yet
- [ ] User approval before Phase 2

### After Phase 2:
- [ ] Performance.md and security.md created
- [ ] Historical reports archived
- [ ] User approval before Phase 3

### After Phase 3:
- [ ] Example data moved
- [ ] Unit tests still work
- [ ] User approval before Phase 4

### After Phase 4:
- [ ] Features organized
- [ ] All links updated
- [ ] Generate AFTER snapshot
- [ ] Compare BEFORE vs AFTER output
- [ ] User approval for completion

---

## 🎯 SUCCESS CRITERIA

### Must Maintain:
1. ✅ Generated output identical (21,716 files)
2. ✅ All features still working
3. ✅ No broken internal links
4. ✅ Easy to find documentation
5. ✅ Clear implemented vs planned separation

### Improvements:
1. ✅ Reduced clutter in docs/ root
2. ✅ Clear user vs developer docs
3. ✅ Better organized proposals/roadmap
4. ✅ Historical context preserved
5. ✅ Example data accessible for testing

---

## 📊 METRICS

### Current State:
- Total docs files: 82
- Docs root clutter: 11 items
- Proposals size: 9MB
- Unclear feature status: ~15 files

### Target State:
- Total docs files: ~70 (some consolidation)
- Docs root items: 7 directories + 2 files
- Proposals size: ~1MB (data moved)
- Clear feature status: 100% of files

---

**Next Action**: Execute Phase 1 - Create directory structure and placeholder READMEs

**Expected Time**: 30 minutes
**Risk Level**: LOW (only creating new directories/files, not moving anything yet)
**Validation Required**: Yes - user approval before Phase 2
