# Screenshots Directory

This directory contains screenshots used in the main README.md file to showcase allium's key features.

## Required Screenshots

### 1. AROI Leaderboards Dashboard (`aroi-leaderboards.png`)
**What to capture:**
- Main AROI leaderboards page showing all 10 leaderboard categories
- Should show the dashboard layout with leaderboard previews
- Include the "AROI Champions Dashboard" header
- Show at least a few entries in each leaderboard for context

**How to capture:**
1. Run `./allium.py --progress` to generate the site
2. Open `www/misc/aroi-leaderboards.html` in browser  
3. Take full-page screenshot
4. Save as `aroi-leaderboards.png`

### 2. AROI Operator Profile (`aroi-operator-profile.png`)
**What to capture:**
- Individual operator profile page showing detailed metrics
- Should include operator achievements, geographic diversity, platform stats
- Show relay portfolio and performance analytics
- Include the operator's name/identifier for context

**How to capture:**
1. Navigate to any contact page from the generated site (e.g., `www/contact/[hash]/index.html`)
2. Find an operator with good AROI metrics and multiple relays
3. Take full-page screenshot showing the complete profile
4. Save as `aroi-operator-profile.png`

### 3. Family Network Analysis (`family-network-analysis.png`)
**What to capture:**
- Family grouping page showing relay families
- Should show bandwidth distributions, consensus weight analysis
- Include geographic diversity information
- Show multiple families for comparison

**How to capture:**
1. Navigate to family pages (e.g., `www/family/[hash]/index.html`)
2. Find a family with multiple relays and good geographic/platform diversity
3. Take screenshot showing the family analysis details
4. Save as `family-network-analysis.png`

## Image Requirements

- **Format:** PNG (preferred) or JPG
- **Resolution:** High-resolution for clarity (at least 1200px wide)
- **Content:** Should be representative of actual allium output
- **Privacy:** Avoid personal information if possible (use generic examples)

## Adding Screenshots

1. Capture screenshots following the guidelines above
2. Save them in this directory with the exact filenames specified
3. Ensure images are clear and demonstrate the key features effectively
4. Test that the README.md displays them correctly

## Notes

- Screenshots should show the actual allium interface, not mockups
- Include enough detail to showcase the sophistication of the analytics
- Focus on the unique AROI features that distinguish allium from other tools
- Consider showing screenshots with realistic data but avoid sensitive information 