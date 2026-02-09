# Relay AS Diversity Score — Implementation Proposal

**Status**: Proposal  
**Created**: February 2026  
**Branch**: `cursor/relay-as-diversity-proposals-719c`  
**Related**: AROI Leaderboards (`aroileaders.py`), Intelligence Engine (`intelligence_engine.py`), Country Diversity (`country_utils.py`)

---

## Problem Statement

The Tor network's resilience depends on relay distribution across many different Autonomous Systems (AS numbers). When a large fraction of relays are concentrated on a few hosting providers (e.g., OVH, Hetzner), the network becomes vulnerable to:

- **Single-point censorship**: A hosting provider can be compelled to shut down all relays at once.
- **Traffic correlation attacks**: An adversary controlling an AS can observe traffic entering and leaving the network.
- **Regulatory risk**: A single jurisdiction can affect a disproportionate share of the network.

Currently, Allium tracks AS-level data (relay counts, consensus weight fraction, unique contacts per AS) and has a basic `diversity_score` in `country_utils.py` that weights countries (x2.0), platforms (x1.5), and unique AS count (x1.0). However, there is **no mechanism to award bonus points to relays running on rare or underrepresented AS numbers**, nor to penalize concentration on dominant providers.

**Goal**: A relay on an unknown/rare AS number gets more points. A relay on OVH gets fewer points.

---

## Existing Technique: Country Rarity Scoring

The codebase already has a proven, simple, threshold-based rarity scoring system for **countries** in `country_utils.py`. The AS diversity score follows the same pattern.

### How Country Rarity Works Today

Each country is scored across 4 factors, each returning a small integer (0-6). The factors are multiplied by weights and summed into a final rarity score.

**Factor 1 — Relay Count** (`calculate_relay_count_factor`):

```python
def calculate_relay_count_factor(country_relay_count):
    if country_relay_count == 0:
        return 0
    return max(7 - country_relay_count, 0)
    # 1 relay = 6 pts, 2 relays = 5 pts, ... 7+ relays = 0 pts
```

**Factor 2 — Network Percentage** (`calculate_network_percentage_factor`):

```python
def calculate_network_percentage_factor(country_relays, total_network_relays):
    percentage = (country_relays / total_network_relays) * 100
    if percentage < 0.05:    return 6  # Ultra-rare
    elif percentage < 0.1:   return 4  # Very rare
    elif percentage < 0.2:   return 2  # Rare
    else:                    return 0  # Common
```

**Factor 3 — Geopolitical** (`calculate_geopolitical_factor`):  
Conflict zones / authoritarian = 3 pts, island nations / landlocked = 2 pts, developing = 1 pt, else 0.

**Factor 4 — Regional** (`calculate_regional_factor`):  
Underrepresented region = 2 pts, emerging region = 1 pt, else 0.

**Weighted Combination**:

```python
rarity_score = (
    (relay_count_factor * 4) +       # weight 4
    (network_percentage_factor * 3) + # weight 3
    (geopolitical_factor * 2) +       # weight 2
    (regional_factor * 1)             # weight 1
)
```

**Tier Assignment** (`assign_rarity_tier`):

```python
if rarity_score >= 15:   return 'legendary'
elif rarity_score >= 10: return 'epic'
elif rarity_score >= 6:  return 'rare'
elif rarity_score >= 3:  return 'emerging'
else:                    return 'common'
```

### Existing Diversity Score (flat)

The current operator-level diversity score in `calculate_diversity_score()`:

```python
diversity_score = 0.0
diversity_score += len(countries) * 2.0       # Geographic
diversity_score += len(platforms) * 1.5        # Platform
diversity_score += unique_as_count * 1.0       # Network (flat — every AS worth 1.0)
```

The problem: every AS contributes the same 1.0 regardless of whether it's a dedicated single-operator AS or OVH with thousands of relays.

### Data Already Available

| Data Point | Location | Description |
|---|---|---|
| `relay['as']` | Per-relay | AS number (e.g., `"AS16276"` for OVH) |
| `relay['as_name']` | Per-relay | Human-readable AS name |
| `sorted['as'][as_number]` | Sorted data | Per-AS aggregated data |
| `sorted['as'][X]['consensus_weight_fraction']` | Sorted data | CW fraction of this AS |
| `sorted['as'][X]['unique_contact_count']` | Sorted data | Distinct contacts (operators) in this AS |
| `contact_data['unique_as_count']` | Per-contact | Unique AS count for an operator |

---

## Test AS Numbers

Values are approximate based on typical Tor network data (~8,000 total relays).

| AS | Name | CW% | Unique Contacts | Character |
|---|---|---|---|---|
| AS16276 | OVH SAS | ~12% | ~350 | Largest hosting provider on Tor |
| AS24940 | Hetzner Online GmbH | ~10% | ~280 | Second-largest hosting provider |
| AS36849 | 1st Amendment Encrypted Openness | ~4% | ~1 | Dedicated single-operator AS |
| AS6939 | Hurricane Electric | ~1.5% | ~40 | Mid-tier transit provider |
| AS9009 | M247 Europe SRL | ~2.5% | ~45 | Mid-tier hosting provider |
| AS205100 | Flokinet Ltd | ~0.03% | ~3 | Small privacy-focused host |
| AS56655 | Terrahost AS | ~0.08% | ~4 | Small Nordic host |

---

## AS Rarity Score: Two Factors, 0-10 Scale

### Concept

Two factors, each returning 0-5, simply added together. No weights, no multiplication. Score range: **0 to 10**.

- **Factor A — AS Consensus Weight**: How much of the network's authority does this AS hold? Lower = more points. This is the core security metric — consensus weight determines how likely relays on this AS are selected for circuits.
- **Factor B — Unique Contact Count**: How many distinct operators (identified by contact info) share this AS? Fewer contacts = the operator made a more unique hosting choice. Contact info is used as the proxy for "operator" since AROI domain adoption is not yet widespread enough.

### Algorithm

```python
def calculate_as_cw_factor(as_cw_fraction):
    """
    Factor A: How much consensus weight does this AS hold?
    Lower CW = higher score = rarer AS from the network's perspective.
    
    Returns: 0-5 points
    """
    cw_percentage = as_cw_fraction * 100
    
    if cw_percentage <= 0:       return 0
    elif cw_percentage < 0.05:   return 5   # Negligible influence
    elif cw_percentage < 0.5:    return 4   # Small influence
    elif cw_percentage < 2.0:    return 3   # Noticeable influence
    elif cw_percentage < 5.0:    return 2   # Significant influence
    elif cw_percentage < 10.0:   return 1   # Major provider
    else:                        return 0   # Dominant (OVH, Hetzner)


def calculate_as_contact_factor(unique_contact_count):
    """
    Factor B: How many distinct operators (by contact info) share this AS?
    Fewer contacts = more unique hosting choice.
    
    Returns: 0-5 points
    """
    if unique_contact_count <= 0:    return 0
    elif unique_contact_count == 1:  return 5   # Sole operator — completely unique
    elif unique_contact_count <= 5:  return 4   # Very few operators
    elif unique_contact_count <= 15: return 3   # Small community
    elif unique_contact_count <= 50: return 2   # Popular provider
    elif unique_contact_count <= 150:return 1   # Very popular
    else:                            return 0   # Mainstream (hundreds of operators)


def calculate_as_rarity_score(as_cw_fraction, unique_contact_count):
    """
    Two-factor AS rarity score. Simply add the two factors.
    
    Score = cw_factor + contact_factor
    Max possible: 5 + 5 = 10
    """
    return calculate_as_cw_factor(as_cw_fraction) + calculate_as_contact_factor(unique_contact_count)


def assign_as_rarity_tier(rarity_score):
    """
    Tier assignment on 0-10 scale.
    """
    if rarity_score >= 8:    return 'legendary'
    elif rarity_score >= 6:  return 'epic'
    elif rarity_score >= 4:  return 'rare'
    elif rarity_score >= 2:  return 'emerging'
    else:                    return 'common'
```

### Applied to Test AS Numbers

| AS | Name | CW% | CW Factor | Contacts | Contact Factor | **Score** | **Tier** |
|---|---|---|---|---|---|---|---|
| AS16276 | OVH SAS | 12% | 0 | 350 | 0 | **0** | common |
| AS24940 | Hetzner Online GmbH | 10% | 0 | 280 | 0 | **0** | common |
| AS36849 | 1st Amend. Encrypted Openness | 4% | 2 | 1 | 5 | **7** | epic |
| AS9009 | M247 Europe SRL | 2.5% | 2 | 45 | 2 | **4** | rare |
| AS6939 | Hurricane Electric | 1.5% | 3 | 40 | 2 | **5** | rare |
| AS56655 | Terrahost AS | 0.08% | 4 | 4 | 4 | **8** | legendary |
| AS205100 | Flokinet Ltd | 0.03% | 5 | 3 | 4 | **9** | legendary |

### What This Tells Us

- **OVH and Hetzner** score 0 — exactly as intended. Dominant CW and hundreds of operators. No diversity bonus.
- **AS36849** scores 7 (epic). The CW factor only gives 2 points (4% is significant), but the sole-operator contact factor gives 5. Running your own AS is the ultimate in network independence and the score reflects that.
- **M247** scores 4 (rare). Mid-tier provider — noticeable CW and ~45 operators sharing it.
- **Hurricane Electric** scores 5 (rare). Lower CW than M247 but similar operator crowding. Slightly better diversity choice.
- **Terrahost** scores 8 (legendary). Small CW and very few operators. Great diversity choice.
- **Flokinet** scores 9 (legendary). Tiniest CW and very few operators. Best possible diversity signal.

---

## Before & After: Contact Page "Network Diversity" (#3)

### Current Code — `intelligence_engine.py` `_layer14_contact_intelligence()`

The rating is based **only on how many unique AS numbers** the operator uses. The sole exception: if an operator has exactly 1 AS and is the only contact on that AS, it gets "Great".

```python
unique_as_count = contact_data.get('unique_as_count', 0)

if unique_as_count == 1:
    # Special case: sole operator on their AS
    if as_data and as_data.get('unique_contact_count', 0) == 1:
        network_rating = "Great"
        portfolio_diversity = f"{network_rating}, 1 AS with 1 operator"
    else:
        network_rating = "Poor"
        portfolio_diversity = f"{network_rating}, {unique_as_count} network"
elif unique_as_count <= 3:
    network_rating = "Okay"
    portfolio_diversity = f"{network_rating}, {unique_as_count} networks"
else:
    network_rating = "Great"
    portfolio_diversity = f"{network_rating}, {unique_as_count} networks"
```

Rendered on the contact page via `_format_intelligence_rating()` as:

```
Network Diversity: Poor, 1 network           (red)
Network Diversity: Okay, 2 networks          (yellow)
Network Diversity: Great, 8 networks         (green)
Network Diversity: Great, 1 AS with 1 operator (green)
```

### Problems with Current Approach

| Operator | AS Numbers | Current Rating | Why It's Wrong |
|---|---|---|---|
| Operator A | 2 AS: OVH + Hetzner | **Okay**, 2 networks | Both are saturated. Should be Poor. |
| Operator B | 2 AS: Flokinet + Terrahost | **Okay**, 2 networks | Both are rare. Should be Great. |
| Operator C | 4 AS: OVH + Hetzner + OVH-US + DigitalOcean | **Great**, 4 networks | All are saturated mainstream providers. Shouldn't be Great. |
| Operator D | 1 AS: AS36849 (sole operator) | **Great**, 1 AS with 1 operator | Correct! But only by special-case logic. |

The rating treats all AS numbers as equal. It cannot distinguish between 2 rare AS and 2 saturated AS.

### Proposed Code — With AS Rarity

Three tiers of rating with a clear hierarchy:
1. **Great** — any operator with at least one rare/epic/legendary AS
2. **Okay** — 4+ AS numbers but all common/emerging (at least they spread across providers)
3. **Poor** — fewer than 4 AS, all common (concentrated on mainstream hosting)

```python
unique_as_count = contact_data.get('unique_as_count', 0)

# Collect AS rarity tiers for this operator's unique AS numbers
operator_as_tiers = []
seen_as = set()
for relay in contact_relays:
    as_number = relay.get('as', '')
    if as_number and as_number not in seen_as:
        seen_as.add(as_number)
        # Inline AS lookup with prefix normalization (same pattern as lines 556-571)
        as_data = None
        if as_number and 'as' in self.sorted_data:
            as_data = self.sorted_data['as'].get(as_number)
            if not as_data:
                if as_number.startswith('AS'):
                    as_data = self.sorted_data['as'].get(as_number[2:])
                else:
                    as_data = self.sorted_data['as'].get(f"AS{as_number}")
        if as_data:
            tier = as_data.get('as_rarity_tier', 'common')
            operator_as_tiers.append(tier)

rare_or_better = sum(1 for t in operator_as_tiers
                     if t in ('legendary', 'epic', 'rare'))

# Rating hierarchy:
#   Great  — has at least one rare/epic/legendary AS (quality choice)
#   Okay   — 4+ AS but all common/emerging (quantity spread across providers)
#   Poor   — <4 AS, all common (concentrated on few mainstream providers)
if rare_or_better > 0:
    network_rating = "Great"
elif unique_as_count >= 4:
    network_rating = "Okay"
else:
    network_rating = "Poor"

# Build description string
if unique_as_count == 1 and operator_as_tiers:
    portfolio_diversity = f"{network_rating}, 1 network ({operator_as_tiers[0]})"
else:
    portfolio_diversity = f"{network_rating}, {unique_as_count} networks ({rare_or_better} rare)"
```

### Before vs After — Side by Side

| Operator | AS Numbers | BEFORE | AFTER | Why |
|---|---|---|---|---|
| 2 AS: OVH + Hetzner | Both common | **Okay**, 2 networks | **Poor**, 2 networks (0 rare) | Worst case: few AS, all mainstream |
| 3 AS: all mainstream | All common | **Okay**, 3 networks | **Poor**, 3 networks (0 rare) | Still <4, all common |
| 4 AS: all mainstream | All common | **Great**, 4 networks | **Okay**, 4 networks (0 rare) | At least spread across 4 providers |
| 5 AS: all mainstream | All common | **Great**, 5 networks | **Okay**, 5 networks (0 rare) | Spread but no rare choices |
| 2 AS: Flokinet + Terrahost | Both legendary | **Okay**, 2 networks | **Great**, 2 networks (2 rare) | Quality over quantity |
| 1 AS: AS36849 (sole op) | epic | **Great**, 1 AS with 1 operator | **Great**, 1 network (epic) | Rare AS, unique choice |
| 3 AS: 1 Flokinet + 2 OVH | 1 legendary + 2 common | **Okay**, 3 networks | **Great**, 3 networks (1 rare) | Has at least 1 rare AS |
| 8 AS: all rare/epic | All score 4+ | **Great**, 8 networks | **Great**, 8 networks (8 rare) | Best case |

The key improvement: **quality of AS choices now matters, not just quantity**. Any operator with even one rare AS gets "Great". Operators who spread across 4+ mainstream providers get "Okay" — better than 2 on OVH+Hetzner, but not as good as choosing rare providers.

### Template Change — `contact.html`

The template itself does not change. The `intelligence.network_diversity` value is already rendered via `{{ intelligence.network_diversity|safe }}`. Only the backend logic in `intelligence_engine.py` changes what string gets produced. The `_format_intelligence_rating()` color-coding function ("Poor"=red, "Okay"=yellow, "Great"=green) continues to work as-is.

---

## Before & After: AROI "Most Diverse" Leaderboard (#1)

### Current Code — `country_utils.py` `calculate_diversity_score()`

```python
def calculate_diversity_score(countries, platforms=None, unique_as_count=None):
    diversity_score = 0.0
    diversity_score += len(countries) * 2.0        # countries x 2.0
    diversity_score += len(platforms) * 1.5         # platforms x 1.5
    diversity_score += unique_as_count * 1.0        # AS count x 1.0 (flat)
    return diversity_score
```

### Problem: Example Rankings Under Current System

Consider 3 hypothetical operators:

| Operator | Countries | Platforms | Unique AS | AS Quality | Current Score |
|---|---|---|---|---|---|
| Alpha | 5 | 1 | 8 | All OVH/Hetzner (common) | 5x2 + 1x1.5 + 8x1 = **19.5** |
| Beta | 3 | 1 | 3 | All rare (Flokinet, Terrahost, etc.) | 3x2 + 1x1.5 + 3x1 = **10.5** |
| Gamma | 4 | 2 | 2 | Both epic (AS36849, Flokinet) | 4x2 + 2x1.5 + 2x1 = **13.0** |

**Alpha ranks #1** despite all 8 AS numbers being saturated mainstream providers. Two problems:
1. The flat `x 1.0` rewards AS quantity regardless of quality.
2. The weights (country=2.0, platform=1.5, AS=1.0) don't reflect the right priority. Country diversity should matter most, AS rarity should be second, platform diversity should be third.

### Proposed Weights: Country > AS > Platform

The new formula reorders the weights so **geographic diversity is the most important factor**, followed by AS rarity, then platform diversity:

| Component | Old Weight | New Weight | Rationale |
|---|---|---|---|
| Country | 2.0 per country | **3.0** per country | Geographic diversity is the primary resilience factor — jurisdictional spread |
| AS (network) | 1.0 per unique AS (flat) | **2.0** per unique AS x avg rarity | AS choice quality matters, not just count. Normalized so it doesn't dominate |
| Platform | 1.5 per platform | **1.0** per platform | Platform matters least — most relays are Linux and that's fine |

The AS component is **normalized**: the average rarity score (0-10) is divided by the max (10) to produce a 0-1 factor, then multiplied by 2.0 per unique AS. This ensures:
- An operator with 3 rare AS (avg rarity 5) gets: 3 x (5/10) x 2.0 = **3.0 points**
- An operator with 8 common AS (avg rarity 0) gets: 8 x (0/10) x 2.0 = **0 points**
- An operator with 2 epic AS (avg rarity 7) gets: 2 x (7/10) x 2.0 = **2.8 points**

This keeps AS contribution in the right range — more than platform (1.0 per unit) but less than country (3.0 per unit).

### Proposed Code — `country_utils.py`

```python
def calculate_diversity_score(countries, platforms=None, unique_as_count=None,
                              as_diversity_score=None):
    """
    Calculate standardized diversity score.
    
    Weights: Country (3.0) > AS rarity (2.0 normalized) > Platform (1.0)
    
    Args:
        countries (list): List of country codes
        platforms (list, optional): List of platform types
        unique_as_count (int, optional): Number of unique ASNs (used for AS calc + fallback)
        as_diversity_score (float, optional): Sum of AS rarity scores across unique AS
    
    Returns:
        float: Weighted diversity score
    """
    diversity_score = 0.0
    
    # Geographic component — highest weight (countries x 3.0)
    if countries:
        diversity_score += len(countries) * 3.0
    
    # Network component — middle weight (normalized AS rarity x 2.0 per AS)
    # avg_rarity / 10 normalizes the 0-10 rarity score to 0-1
    # Then x 2.0 per unique AS keeps it between country (3.0) and platform (1.0)
    if as_diversity_score is not None and unique_as_count and unique_as_count > 0:
        avg_rarity = as_diversity_score / unique_as_count  # 0-10 range
        normalized = avg_rarity / 10.0                     # 0-1 range
        diversity_score += unique_as_count * normalized * 2.0
    elif unique_as_count:
        diversity_score += unique_as_count * 1.0  # flat fallback
    
    # Platform component — lowest weight (platforms x 1.0)
    if platforms:
        diversity_score += len(platforms) * 1.0
    
    return diversity_score
```

### Proposed Code — `aroileaders.py` call site

```python
# Calculate per-operator AS diversity score (sum of rarity scores per unique AS)
from .country_utils import calculate_operator_as_diversity_score

as_diversity_score = calculate_operator_as_diversity_score(
    operator_relays, sorted_as_data
)

diversity_score = calculate_diversity_score(
    countries=list(countries),
    platforms=list(platforms),
    unique_as_count=unique_as_count,
    as_diversity_score=as_diversity_score
)
```

### Proposed Code — `aroileaders.py` tooltip formatting

```python
diversity_breakdown_tooltip = (
    f"Diversity Score: {country_count} countries x 3.0 "
    f"+ {as_count} AS (rarity-weighted) x 2.0 "
    f"+ {platform_count} platforms x 1.0 = {metrics['diversity_score']:.1f}"
)
```

### After: Same 3 Operators Under New System

Using rarity scores from the 0-10 scale (OVH=0, Hetzner=0, Flokinet=9, Terrahost=8, AS36849=7):

| Operator | Countries | Platforms | Unique AS | Avg Rarity | Country Pts | AS Pts | Platform Pts | New Score |
|---|---|---|---|---|---|---|---|---|
| Alpha | 5 | 1 | 8 (all common) | 0 | 5x3 = 15 | 8x(0/10)x2 = 0 | 1x1 = 1 | **16.0** |
| Beta | 3 | 1 | 3 (all rare, ~8.3) | 8.3 | 3x3 = 9 | 3x(8.3/10)x2 = 5.0 | 1x1 = 1 | **15.0** |
| Gamma | 4 | 2 | 2 (both epic, ~8) | 8 | 4x3 = 12 | 2x(8/10)x2 = 3.2 | 2x1 = 2 | **17.2** |

### Before vs After — Ranking Comparison

| Rank | BEFORE (flat) | Score | AFTER (rarity-weighted) | Score |
|---|---|---|---|---|
| #1 | Alpha (5 ctry, 8 common AS) | 19.5 | **Gamma** (4 ctry, 2 epic AS, 2 plat) | **17.2** |
| #2 | Gamma (4 ctry, 2 epic AS) | 13.0 | **Alpha** (5 ctry, 8 common AS) | **16.0** |
| #3 | Beta (3 ctry, 3 rare AS) | 10.5 | **Beta** (3 ctry, 3 rare AS) | **15.0** |

### What Changed in the Rankings

- **Gamma rises to #1** — 4 countries + 2 epic AS + 2 platforms beats Alpha's 5 countries but worthless AS choices.
- **Alpha drops from #1 to #2** — still gets credit for 5 countries (the most important factor), but 8 common AS now contribute 0 instead of 8 points.
- **Beta jumps from 10.5 to 15.0** and nearly ties Alpha — 3 rare AS now contribute 5.0 points instead of 3 points. Only 2 fewer countries keeps it behind.

### Weight Hierarchy Verification

To confirm country > AS > platform ordering, compare one-unit additions from the same base:

| Change from base (3 ctry, 1 plat, 2 common AS) | Score Impact |
|---|---|
| +1 country | **+3.0** |
| +1 epic AS (rarity 7) | **+1.4** |
| +1 platform | **+1.0** |

Adding a country (+3.0) > adding an epic AS (+1.4) > adding a platform (+1.0). The hierarchy holds.

---

## Execution Plan

### Step 1: New functions in `country_utils.py`

Add 5 new functions. No existing functions are modified yet in this step. Zero risk to existing behavior.

| Function | Purpose |
|---|---|
| `calculate_as_cw_factor(as_cw_fraction)` | Returns 0-5 based on CW% thresholds |
| `calculate_as_contact_factor(unique_contact_count)` | Returns 0-5 based on contact count thresholds |
| `calculate_as_rarity_score(as_cw_fraction, unique_contact_count)` | Returns sum of the two factors (0-10) |
| `assign_as_rarity_tier(rarity_score)` | Returns tier string from score |
| `calculate_operator_as_diversity_score(operator_relays, sorted_as_data)` | Sums AS rarity scores across operator's unique AS numbers |

The `calculate_operator_as_diversity_score` function body:

```python
def calculate_operator_as_diversity_score(operator_relays, sorted_as_data):
    """
    Calculate the sum of AS rarity scores across an operator's unique AS numbers.
    
    Args:
        operator_relays (list): List of relay dicts for one operator
        sorted_as_data (dict): The sorted['as'] dict with pre-computed as_rarity_score
        
    Returns:
        float: Sum of AS rarity scores (0 if no data)
    """
    if not operator_relays or not sorted_as_data:
        return 0.0
    
    seen_as = set()
    total_score = 0.0
    
    for relay in operator_relays:
        as_number = relay.get('as', '')
        if not as_number or as_number in seen_as:
            continue
        seen_as.add(as_number)
        
        # Look up pre-computed AS rarity score (keys match relay['as'] format)
        as_entry = sorted_as_data.get(as_number)
        if as_entry:
            total_score += as_entry.get('as_rarity_score', 0)
    
    return total_score
```

**Imports to add in `aroileaders.py`** (line 17, add to existing `from .country_utils import (...)` block):

```python
from .country_utils import (
    count_non_eu_countries, 
    count_frontier_countries_weighted_with_existing_data,
    calculate_diversity_score, 
    calculate_geographic_achievement,
    calculate_operator_as_diversity_score,  # NEW
    EU_POLITICAL_REGION
)
```

**Note on AS prefix normalization**: The `sorted['as']` keys use the same raw format as `relay['as']` (e.g., `"AS16276"`) because both come from `_sort(relay, idx, "as", relay.get("as"), ...)` in `relays.py` line 1722. No prefix normalization is needed in `calculate_operator_as_diversity_score`. However, `intelligence_engine.py` uses defensive prefix normalization (lines 556-571) because it accesses `self.sorted_data['as']` through a different code path — the implementation in Step 5 should reuse that same defensive pattern.

### Step 2: Modify `calculate_diversity_score()` in `country_utils.py`

Add optional `as_diversity_score` parameter. When provided, use normalized rarity-weighted formula. When not provided, fall back to existing flat `unique_as_count * 1.0`. This makes the change backward-compatible — all existing callers continue to work unchanged.

Weight changes: country 2.0 -> **3.0**, platform 1.5 -> **1.0**, AS flat 1.0 -> **normalized rarity x 2.0**.

**Callers to verify**: Only one caller exists — `aroileaders.py` line 646. No other code calls this function.

### Step 3: Pre-compute AS rarity in `relays.py`

In `_finalize_unique_as_counts()` (line 1960), after `unique_as_count` and `unique_contact_count` are finalized for each AS, compute and store `as_rarity_score` and `as_rarity_tier` on each `sorted['as'][as_number]` entry. This is a one-pass addition to an existing loop — no new loops needed.

```python
# After existing unique_contact_count finalization in _finalize_unique_as_counts():
if category == "as":
    cw = data.get("consensus_weight_fraction", 0)
    contacts = data.get("unique_contact_count", 0)
    data["as_rarity_score"] = calculate_as_rarity_score(cw, contacts)
    data["as_rarity_tier"] = assign_as_rarity_tier(data["as_rarity_score"])
```

**Import to add in `relays.py`**: The existing pattern in `relays.py` uses **lazy imports** for `country_utils` (see lines 4741 and 4756). Follow the same pattern — import inside `_finalize_unique_as_counts()`:

```python
# Inside _finalize_unique_as_counts(), before the loop:
from .country_utils import calculate_as_rarity_score, assign_as_rarity_tier
```

### Step 4: Update `aroileaders.py` — diversity score calculation

At line 646, change the `calculate_diversity_score` call to pass the new `as_diversity_score` parameter:

```python
# NEW: Calculate operator-level AS diversity score
as_diversity_score = calculate_operator_as_diversity_score(
    operator_relays, relays_instance.json.get('sorted', {}).get('as', {})
)

diversity_score = calculate_diversity_score(
    countries=list(countries),
    platforms=list(platforms),
    unique_as_count=unique_as_count,
    as_diversity_score=as_diversity_score
)
```

Also update the tooltip formatting at line 1107 to reflect new weights.

Store `as_diversity_score` in the operator metrics dict (after line 766 where `diversity_score` is stored):

```python
'diversity_score': diversity_score,
'as_diversity_score': as_diversity_score,  # NEW: for tooltip/template use
```

### Step 5: Update `intelligence_engine.py` — Network Diversity rating

Replace the existing rating logic at lines 547-585 with the new 3-tier system (full proposed code shown in the "Before & After: Contact Page" section above). Key implementation details:

1. Replace the `if unique_as_count == 1: ... elif ... else:` block (lines 550-585) entirely
2. New code iterates `contact_relays` (available at line 541) collecting each unique AS's `as_rarity_tier`
3. AS lookup uses defensive prefix normalization (reuse existing pattern at lines 556-571)
4. Rating hierarchy: `rare_or_better > 0` → Great, `unique_as_count >= 4` → Okay, else → Poor
5. New description format: `"Great, 4 networks (2 rare)"` or `"Great, 1 network (epic)"`
6. The `_format_intelligence_rating()` function is **not modified** — it continues to color-code based on the first word (Great/Okay/Poor)

### Step 6: Update template tooltip text and scoring documentation

Update all references to the old formula across **3 template files** and **1 Python file**.

**`aroi_macros.html`** — 4 formula tooltip strings (update old weights to new weights):

| Line | Context | Old Text |
|---|---|---|
| 32 | Champion ribbon tooltip | `"Diversity Score: Geographic (countries × 2.0) + Platform (OS types × 1.5) + Network (unique ASNs × 1.0)"` |
| 139 | Top-10 performance column tooltip | Same formula string |
| 256 | Score column tooltip (main ranking table) | Same formula string (inside fallback `else` of `diversity_breakdown_tooltip`) |
| 844 | Score column tooltip (secondary ranking table) | Same formula string (inside fallback `else` of `diversity_breakdown_tooltip`) |

New text: `"Diversity Score: Geographic (countries × 3.0) + Network (AS rarity-weighted × 2.0) + Platform (platforms × 1.0)"`

**`aroi-leaderboards.html`** — 4 locations:

| Line | Context | What to update |
|---|---|---|
| 33 | Nav link tooltip | `"Diversity Score: Calculated by combining geographic spread (countries × 2.0), platform variety (operating systems × 1.5), and network distribution (unique ASNs × 1.0)..."` → update weights |
| 230 | Section h3 title | `"combined geographic, platform, and network diversity scores"` → mention AS rarity weighting |
| 281 | Category list description | `"Geographic, platform, and network diversity score"` → mention AS rarity |
| 365-371 | **Scoring explanation section** — full formula documentation with weights and worked example. **Critical**: contains old weights (countries × 2.0, OS × 1.5, ASNs × 1.0) and an example calculation (5 × 2.0 + 3 × 1.5 + 8 × 1.0 = 22.5) that must all be updated |

**`contact.html`** — 1 location:

| Line | Context | What to update |
|---|---|---|
| 120 | Network Diversity tooltip | `"1 network = Poor (single point of failure), 2-3 networks = Okay (limited redundancy), 4+ networks = Great (excellent resilience)"` → update to reflect new AS rarity-based rating: "Poor = few AS, all common providers; Okay = 4+ AS but all common; Great = at least one rare/epic/legendary AS" |

**`aroileaders.py`** — 2 locations (Python-generated tooltip):

| Line | Context | What to update |
|---|---|---|
| 1100 | Short diversity breakdown | `f"{country_count} Countries, {platform_count} OS, {as_count} AS"` — consider adding rarity info |
| 1107 | Full tooltip with formula | `f"Diversity Score Calculation: {country_count} countries × 2.0 + {platform_count} operating systems × 1.5 + {as_count} unique ASNs × 1.0 = ..."` → update to new weights |

**Total**: 11 locations across 4 files.

---

## Test Plan

### New unit tests: `tests/unit/aroi/test_as_diversity.py`

Tests for the new functions in `country_utils.py`. Follows the existing test pattern from `test_aroi_country_distribution.py` (unittest-based, in `tests/unit/aroi/`).

| Test | What it verifies |
|---|---|
| `test_as_cw_factor_dominant` | CW >= 10% returns 0 (OVH, Hetzner) |
| `test_as_cw_factor_major` | CW 5-10% returns 1 |
| `test_as_cw_factor_significant` | CW 2-5% returns 2 (AS36849, M247) |
| `test_as_cw_factor_noticeable` | CW 0.5-2% returns 3 (Hurricane Electric) |
| `test_as_cw_factor_small` | CW 0.05-0.5% returns 4 (Terrahost) |
| `test_as_cw_factor_negligible` | CW < 0.05% returns 5 (Flokinet) |
| `test_as_cw_factor_zero` | CW = 0 returns 0 |
| `test_as_contact_factor_sole_operator` | 1 contact returns 5 |
| `test_as_contact_factor_few` | 2-5 contacts returns 4 |
| `test_as_contact_factor_small_community` | 6-15 contacts returns 3 |
| `test_as_contact_factor_popular` | 16-50 contacts returns 2 |
| `test_as_contact_factor_very_popular` | 51-150 contacts returns 1 |
| `test_as_contact_factor_mainstream` | 151+ contacts returns 0 |
| `test_as_contact_factor_zero` | 0 contacts returns 0 |
| `test_as_rarity_score_addition` | Score = CW factor + contact factor |
| `test_as_rarity_score_max` | Max score is 10 (5+5) |
| `test_as_rarity_score_ovh` | OVH (12% CW, 350 contacts) = 0 |
| `test_as_rarity_score_as36849` | AS36849 (4% CW, 1 contact) = 7 |
| `test_as_rarity_score_flokinet` | Flokinet (0.03% CW, 3 contacts) = 9 |
| `test_tier_legendary` | Score 8-10 -> 'legendary' |
| `test_tier_epic` | Score 6-7 -> 'epic' |
| `test_tier_rare` | Score 4-5 -> 'rare' |
| `test_tier_emerging` | Score 2-3 -> 'emerging' |
| `test_tier_common` | Score 0-1 -> 'common' |
| `test_operator_as_diversity_score_sums_unique` | Sum across unique AS, skip duplicates |
| `test_operator_as_diversity_score_empty` | Empty relay list returns 0 |
| `test_diversity_score_new_weights` | countries x 3.0 + normalized AS x 2.0 + platforms x 1.0 |
| `test_diversity_score_fallback` | Without `as_diversity_score`, falls back to flat AS count |
| `test_diversity_score_country_beats_as` | +1 country > +1 epic AS > +1 platform |

### Existing test updates

| File | Change needed |
|---|---|
| `tests/unit/relays/test_contact_display.py` | **Update required.** Line 31: mock `'portfolio_diversity': 'Great, 4 networks'` → `'Great, 4 networks (2 rare)'`. Line 100-101: `_format_intelligence_rating('Great, 4 networks')` test — update input/expected for consistency (won't break since `_format_intelligence_rating` doesn't change, but should match new format). Lines 263-264: color assertions — will still pass (checks green color, not exact string). |
| `tests/integration/test_contact_template.py` | **Update required.** Line 87: mock `'network_diversity': '...Great</span>, 4 networks'` → add `(2 rare)`. Line 274: assertion `'Great</span>, 4 networks'` must match the updated mock at line 87. |
| `tests/regression/test_contact_data_integrity.py` | **Optional update.** Line 298: test data `('Great, 4 networks', '#2e7d2e')` tests `_format_intelligence_rating` — won't break (function unchanged). Update input string for consistency. |
| `tests/conftest.py` | No change needed. `diversity_score` fixture values (line 234) are arbitrary numbers not testing the calculation. |
| `tests/helpers/fixtures.py` | No change needed. Same — fixture `diversity_score` values (line 178) are arbitrary. |
| `tests/integration/test_aroi_pagination.py` | No change needed. Same — `diversity_score` fixture values (line 61) are arbitrary. |

### Regression tests: `tests/regression/test_as_diversity_regression.py`

| Test | What it verifies |
|---|---|
| `test_2_common_as_rates_poor` | 2 AS (OVH + Hetzner) -> Poor |
| `test_4_common_as_rates_okay` | 4 mainstream AS -> Okay |
| `test_2_rare_as_rates_great` | 2 rare AS -> Great |
| `test_1_rare_plus_2_common_rates_great` | 1 rare + 2 common -> Great |
| `test_sole_operator_epic_as_rates_great` | AS36849 sole operator -> Great |
| `test_diversity_score_ranking_order` | Alpha (8 common) < Beta (3 rare) < Gamma (2 epic + more countries) |

---

## CI Impact

### Existing CI passes

All 623 existing tests pass (verified). The CI pipeline runs:

1. **Code Quality** — flake8 syntax check. New code must pass `E9,F63,F7,F82` (critical errors). Style warnings are non-blocking.
2. **Unit Tests** — `pytest tests/ -m "not slow"` across Python 3.8-3.11. New tests will be picked up automatically.
3. **Template Validation** — Jinja2 syntax check on `allium/templates/*.html`. The tooltip text changes in `aroi_macros.html` must remain valid Jinja2.
4. **Security Scan** — bandit + safety. No new security concerns expected (no new imports, no external calls).
5. **Integration Tests** — AROI module import check. Unchanged.

### New test file location

```
tests/unit/aroi/test_as_diversity.py         # New: AS rarity scoring unit tests
tests/regression/test_as_diversity_regression.py  # New: before/after scenario tests
```

Both will be automatically collected by pytest (matching `test_*.py` pattern in `tests/`).

### Flake8 compliance

New code must follow existing style: max line length 127, no critical errors. The threshold functions are simple if/elif blocks that naturally comply.

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `calculate_diversity_score` signature change breaks callers | Low | Medium | Only 1 caller (`aroileaders.py`). New param is optional with fallback. |
| Network Diversity string format change breaks tests | Medium | Low | `test_contact_display.py` (line 31) and `test_contact_template.py` (line 87) both hardcode the old format. Update both. |
| AS rarity scores change leaderboard rankings | Certain | Medium | Expected behavior — the whole point. No data loss, just re-ranking. |
| Performance impact of pre-computing AS rarity | Very Low | Very Low | One-pass addition to existing loop. 7 thresholds + 1 addition per AS. |
| Edge case: AS with CW=0 but contacts>0 | Low | Low | `calculate_as_cw_factor` returns 0 for CW<=0. Contact factor still contributes. Score = 0 + contact_factor. Correct behavior. |

---

## Open Questions

1. **How should newly appeared AS numbers be handled?** A brand-new AS with 1 relay would get maximum rarity. This is correct (it IS rare) but could be gamed. Consider requiring minimum relay uptime before scoring.

2. **Should the contact factor weight be higher or lower than CW?** Currently both are equal (0-5 each, just added). If CW is considered more important, the scale could be 0-6 for CW and 0-4 for contacts while keeping a 0-10 max.

---

*This document proposes a 2-factor AS diversity scoring system (consensus weight + unique contacts) on a 0-10 scale for Allium. Feedback welcome before implementation begins.*
