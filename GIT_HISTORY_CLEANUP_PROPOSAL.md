# Git History Cleanup Proposal - opnetup Branch

## Current Situation
The `opnetup` branch has accumulated **100+ commits** with a very messy history including:
- Multiple unrelated features (AROI leaderboards, security fixes, etc.)
- Very long commit messages (some 500+ characters)
- Merge commits mixed throughout
- Work that belongs on other branches
- The actual network uptime percentiles work buried among other commits

## Core Network Uptime Percentiles Commits
The actual feature work consists of **~15 commits** since `554a951a8`:

### Key Commits to Preserve:
1. `554a951a8` - Add network uptime percentiles feature for contact pages
2. `584afcc4a` - Refactor network uptime percentiles to reduce code duplication  
3. `f5114fa65` - Fix mathematical impossibility in network uptime percentiles
4. `a1dcf6db9` - Implement data filtering for network uptime percentiles
5. `3326d2856` - Resolve mathematical impossibility with 70% threshold + median
6. `8cf1ceb98` - Implement honest network representation with >1% threshold
7. `a78805c79` - Implement final UI improvements for network uptime percentiles
8. `6ec43d988` - Enhance network percentiles tooltip with statistical methodology
9. `9dd6d0767` - Optimize network uptime percentiles calculation for performance
10. `650c552c2` - Enhance network uptime display with color coding and median label
11. `0f7f9e1ac` - Rename 'Median' to '50th Pct' for consistent percentile labeling

## Strategy 1: Interactive Rebase (Recommended)

### Approach
Create a clean, logical commit history while preserving development context.

### Steps
```bash
# 1. Create backup branch
git checkout opnetup
git branch opnetup-backup

# 2. Interactive rebase from merge-base
git rebase -i 4c459cf10506135f1cfc714434f362238b62329b

# 3. In the rebase editor, restructure commits:
#    - SQUASH related commits into logical features
#    - REWORD overly long commit messages
#    - DROP commits unrelated to network uptime percentiles
#    - REORDER commits for logical progression
```

### Target Commit Structure (7-8 commits)
1. **Core Implementation**: Squash `554a951a8` + `584afcc4a` + `398af7d5c`
   - "feat: add network uptime percentiles for contact pages with operator positioning"

2. **Mathematical Robustness**: Squash `f5114fa65` + `a1dcf6db9` + `7202bd734`
   - "fix: resolve mathematical impossibility in percentile calculations"

3. **Data Filtering Strategy**: Squash `3326d2856` + `8cf1ceb98`
   - "feat: implement honest network representation with median-based statistics"

4. **UI/UX Improvements**: Squash `a78805c79` + `6ec43d988`
   - "feat: enhance percentiles display with tooltips and positioning"

5. **Performance Optimization**: Keep `9dd6d0767`
   - "perf: optimize network percentiles calculation to prevent 10x slowdown"

6. **Display Consistency**: Squash `650c552c2` + `0f7f9e1ac`
   - "feat: add color coding and consistent percentile labeling"

7. **Documentation**: Squash `9d60ca7f0` + updates
   - "docs: add comprehensive implementation documentation and merge plan"

### Advantages
- ✅ Preserves development context and decision history
- ✅ Shows progression from initial implementation → bug fixes → optimization
- ✅ Maintains readable commit messages with clear purpose
- ✅ Educational value for future developers

### Disadvantages
- ⚠️ Requires manual rebase conflict resolution
- ⚠️ Time-intensive process (~1-2 hours)
- ⚠️ Risk of breaking if rebase goes wrong

## Strategy 2: Fresh Branch from Scratch (Faster)

### Approach
Create a completely new clean branch with only the network uptime percentiles work.

### Steps
```bash
# 1. Create new clean branch from current master
git checkout master
git pull origin master
git checkout -b opnetup-clean

# 2. Cherry-pick only the essential commits in logical order
git cherry-pick 554a951a8  # Core implementation
git cherry-pick 584afcc4a  # Code refactoring  
git cherry-pick f5114fa65  # Math fix
git cherry-pick a1dcf6db9  # Data filtering
git cherry-pick 8cf1ceb98  # Honest representation
git cherry-pick 9dd6d0767  # Performance optimization
git cherry-pick a78805c79  # UI improvements
git cherry-pick 650c552c2  # Color coding
git cherry-pick 0f7f9e1ac  # Consistent labeling

# 3. Squash into logical commits
git rebase -i HEAD~9

# 4. Add documentation
git add NETWORK_UPTIME_DISPLAY_UPDATE.md OPNETUP_MERGE_PLAN.md
git commit -m "docs: add comprehensive feature documentation and merge plan"

# 5. Replace original opnetup branch
git branch -D opnetup
git checkout -b opnetup
git push origin opnetup --force-with-lease
```

### Target Result (4-5 commits)
1. **Core Feature**: "feat: implement network uptime percentiles with operator positioning"
2. **Mathematical Robustness**: "fix: resolve data quality issues and mathematical impossibilities"  
3. **Performance & UI**: "feat: optimize calculation performance and enhance display"
4. **Final Polish**: "feat: add color coding and consistent percentile labeling"
5. **Documentation**: "docs: add comprehensive implementation documentation"

### Advantages
- ✅ **Clean, minimal history** (4-5 commits vs 100+)
- ✅ **Fast execution** (~30 minutes vs 2+ hours)
- ✅ **No rebase conflicts** - cherry-picking specific commits
- ✅ **Easy to review** - logical commit progression
- ✅ **Professional appearance** for merge into master

### Disadvantages
- ⚠️ Loses detailed development history
- ⚠️ Less educational value for understanding bug fixes
- ⚠️ Requires force-push to replace branch

## Recommendation

**Strategy 2: Fresh Branch from Scratch**

### Rationale
1. **Time Efficiency**: 30 minutes vs 2+ hours
2. **Lower Risk**: No complex rebase conflicts to resolve
3. **Cleaner Result**: Professional, focused commit history
4. **Easier Review**: Clear logical progression for merge approval
5. **Network Focus**: Only network uptime percentiles work, no distractions

### Risk Mitigation
- Create `opnetup-backup` branch before cleanup
- Validate all functionality after cleanup
- Keep merge plan documentation comprehensive

## Execution Plan

1. **Backup**: `git branch opnetup-backup`
2. **Execute Strategy 2**: Create clean branch with cherry-picked commits
3. **Validate**: Run performance and validation tests
4. **Update Documentation**: Ensure merge plan reflects clean history
5. **Replace Branch**: Force-push clean history to opnetup
6. **Ready for Merge**: Present clean 4-5 commit history for review

---

**Decision Required**: Which strategy would you prefer?
- **Strategy 1**: Detailed history preservation (2+ hours, complex)
- **Strategy 2**: Clean minimal history (30 minutes, simple)

Both strategies achieve the same end result - a clean, mergeable branch with the network uptime percentiles feature ready for production.