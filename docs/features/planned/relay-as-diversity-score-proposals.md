# Relay AS Diversity Score — Implementation Proposals

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

The codebase already has a proven, simple, threshold-based rarity scoring system for **countries** in `country_utils.py`. The AS diversity proposals below follow the same pattern.

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

This is simple, readable, and easy to tune. The AS diversity proposals below reuse this structure.

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

The following real AS numbers are used to evaluate both proposals. Values are approximate based on typical Tor network data (~8,000 total relays).

| AS | Name | Relays | CW% | Unique Contacts | Character |
|---|---|---|---|---|---|
| AS16276 | OVH SAS | ~1,200 | ~12% | ~350 | Largest hosting provider on Tor |
| AS24940 | Hetzner Online GmbH | ~1,100 | ~10% | ~280 | Second-largest hosting provider |
| AS36849 | 1st Amendment Encrypted Openness | ~560 | ~4% | ~1 | Dedicated single-operator AS |
| AS6939 | Hurricane Electric | ~90 | ~1.5% | ~40 | Mid-tier transit provider |
| AS9009 | M247 Europe SRL | ~150 | ~2.5% | ~45 | Mid-tier hosting provider |
| AS205100 | Flokinet Ltd | ~5 | ~0.03% | ~3 | Small privacy-focused host |
| AS56655 | Terrahost AS | ~8 | ~0.08% | ~4 | Small Nordic host |

---

## Option 1: Two-Factor Score — CW + Unique Contacts

### Concept

Two factors, equal weight:

- **Factor A — AS Consensus Weight**: How much of the network's authority does this AS hold? Lower = more points. This is the core security metric — consensus weight determines how likely relays on this AS are selected for circuits.
- **Factor B — Unique Contact Count**: How many distinct operators (identified by contact info) share this AS? Fewer contacts = the operator made a more unique hosting choice. Contact info is used as the proxy for "operator" since AROI domain adoption is not yet widespread enough.

### Algorithm

```python
def calculate_as_cw_factor(as_cw_fraction):
    """
    Factor A: How much consensus weight does this AS hold?
    Lower CW = higher score = rarer AS from the network's perspective.
    
    Returns: 0-6 points
    """
    cw_percentage = as_cw_fraction * 100
    
    if cw_percentage <= 0:       return 0
    elif cw_percentage < 0.01:   return 6   # Negligible influence
    elif cw_percentage < 0.05:   return 5   # Tiny influence
    elif cw_percentage < 0.1:    return 4   # Small influence
    elif cw_percentage < 0.5:    return 3   # Modest influence
    elif cw_percentage < 2.0:    return 2   # Noticeable influence
    elif cw_percentage < 5.0:    return 1   # Significant influence
    else:                        return 0   # Dominant (OVH, Hetzner)


def calculate_as_contact_factor(unique_contact_count):
    """
    Factor B: How many distinct operators (by contact info) share this AS?
    Fewer contacts = more unique hosting choice.
    
    Contact info is a proxy for operator identity. While not perfect
    (some operators use multiple contacts, some share contacts), it is
    the most widely available signal — AROI domain is not yet common enough.
    
    Returns: 0-6 points
    """
    if unique_contact_count <= 0:    return 0
    elif unique_contact_count == 1:  return 6   # Sole operator — completely unique
    elif unique_contact_count <= 3:  return 5   # Very few operators
    elif unique_contact_count <= 10: return 4   # Small community
    elif unique_contact_count <= 25: return 3   # Moderate community
    elif unique_contact_count <= 50: return 2   # Popular provider
    elif unique_contact_count <= 100:return 1   # Very popular
    else:                            return 0   # Mainstream (hundreds of operators)


def calculate_as_rarity_score(as_cw_fraction, unique_contact_count):
    """
    Two-factor AS rarity score.
    
    Score = (cw_factor * 5) + (contact_factor * 5)
    
    Both factors weighted equally at 5.
    Max possible: (6 * 5) + (6 * 5) = 60
    """
    cw_factor = calculate_as_cw_factor(as_cw_fraction)
    contact_factor = calculate_as_contact_factor(unique_contact_count)
    
    return (cw_factor * 5) + (contact_factor * 5)


def assign_as_rarity_tier(rarity_score):
    """
    Tier assignment for 2-factor score.
    Max = 60.
    """
    if rarity_score >= 45:   return 'legendary'
    elif rarity_score >= 30: return 'epic'
    elif rarity_score >= 18: return 'rare'
    elif rarity_score >= 8:  return 'emerging'
    else:                    return 'common'
```

### Applied to Test AS Numbers

| AS | Name | CW% | CW Factor | Contacts | Contact Factor | Score | Tier |
|---|---|---|---|---|---|---|---|
| AS16276 | OVH SAS | 12% | 0 | 350 | 0 | **(0 x 5) + (0 x 5) = 0** | common |
| AS24940 | Hetzner Online GmbH | 10% | 0 | 280 | 0 | **(0 x 5) + (0 x 5) = 0** | common |
| AS36849 | 1st Amend. Encrypted Openness | 4% | 1 | 1 | 6 | **(1 x 5) + (6 x 5) = 35** | epic |
| AS9009 | M247 Europe SRL | 2.5% | 1 | 45 | 2 | **(1 x 5) + (2 x 5) = 15** | emerging |
| AS6939 | Hurricane Electric | 1.5% | 2 | 40 | 2 | **(2 x 5) + (2 x 5) = 20** | rare |
| AS56655 | Terrahost AS | 0.08% | 4 | 4 | 4 | **(4 x 5) + (4 x 5) = 40** | epic |
| AS205100 | Flokinet Ltd | 0.03% | 5 | 3 | 5 | **(5 x 5) + (5 x 5) = 50** | legendary |

### What This Tells Us

- **OVH and Hetzner** score 0 — exactly as intended. They dominate the network in both CW and operator count. No diversity bonus.
- **AS36849** scores 35 (epic). Even though it holds ~4% CW (which alone only gives 1 point), the fact that only 1 unique contact operates on this AS means it is a completely unique hosting choice. The contact factor rewards this. Running your own AS is the ultimate in network independence.
- **M247** scores 15 (emerging). Mid-tier provider — modest CW and ~45 operators sharing it. Not rare, but not saturated either.
- **Hurricane Electric** scores 20 (rare). Lower CW than M247 but similar operator crowding. Slightly better diversity choice.
- **Terrahost** scores 40 (epic). Small Nordic host with very few operators. Good diversity choice.
- **Flokinet** scores 50 (legendary). Tiny CW and very few operators. Best possible diversity signal.

### Pros

- **Two meaningful dimensions** — CW captures network influence, contact count captures hosting choice uniqueness
- **Correctly rewards dedicated operator AS** — AS36849 gets a high score because running your own AS IS a unique contribution to diversity, even if you have many relays
- **Correctly penalizes mainstream hosting** — OVH and Hetzner score 0 on both factors
- **Contact info is widely available** — unlike AROI domain, nearly every relay has contact info already tracked via `unique_contact_count` in sorted AS data
- **Simple** — same if/elif pattern as country rarity, no imports

### Cons

- Contact info is an imperfect proxy for operators (some operators have multiple contacts, some share contacts)
- Does not directly measure relay count — but relay count strongly correlates with both CW and contact count anyway

---

## Option 2: Single-Factor Score — CW Only

### Concept

The absolute simplest version. One factor: what fraction of the network's consensus weight does this AS hold? That single number determines the score. Nothing else.

Consensus weight is chosen over relay count because it measures actual network influence — an AS with 10 high-bandwidth relays holding 5% CW is a bigger concentration risk than an AS with 100 low-bandwidth relays holding 0.1% CW.

### Algorithm

```python
def calculate_as_cw_factor(as_cw_fraction):
    """
    Single-factor AS rarity score based on consensus weight.
    
    Returns: 0-6 points
    """
    cw_percentage = as_cw_fraction * 100
    
    if cw_percentage <= 0:       return 0
    elif cw_percentage < 0.01:   return 6   # Negligible influence
    elif cw_percentage < 0.05:   return 5   # Tiny influence
    elif cw_percentage < 0.1:    return 4   # Small influence
    elif cw_percentage < 0.5:    return 3   # Modest influence
    elif cw_percentage < 2.0:    return 2   # Noticeable influence
    elif cw_percentage < 5.0:    return 1   # Significant influence
    else:                        return 0   # Dominant (OVH, Hetzner)


def calculate_as_rarity_score(as_cw_fraction):
    """
    Single-factor AS rarity score.
    
    Score = cw_factor * 10
    
    Max possible: 6 * 10 = 60
    Scaling by 10 to get a comparable range to Option 1.
    """
    return calculate_as_cw_factor(as_cw_fraction) * 10


def assign_as_rarity_tier(rarity_score):
    """
    Tier assignment for 1-factor score.
    Max = 60.
    """
    if rarity_score >= 45:   return 'legendary'
    elif rarity_score >= 30: return 'epic'
    elif rarity_score >= 18: return 'rare'
    elif rarity_score >= 8:  return 'emerging'
    else:                    return 'common'
```

### Applied to Test AS Numbers

| AS | Name | CW% | CW Factor | Score | Tier |
|---|---|---|---|---|---|
| AS16276 | OVH SAS | 12% | 0 | **0 x 10 = 0** | common |
| AS24940 | Hetzner Online GmbH | 10% | 0 | **0 x 10 = 0** | common |
| AS36849 | 1st Amend. Encrypted Openness | 4% | 1 | **1 x 10 = 10** | emerging |
| AS9009 | M247 Europe SRL | 2.5% | 1 | **1 x 10 = 10** | emerging |
| AS6939 | Hurricane Electric | 1.5% | 2 | **2 x 10 = 20** | rare |
| AS56655 | Terrahost AS | 0.08% | 4 | **4 x 10 = 40** | epic |
| AS205100 | Flokinet Ltd | 0.03% | 5 | **5 x 10 = 50** | legendary |

### What This Tells Us

- **OVH and Hetzner** still correctly score 0 — dominant CW means no diversity bonus.
- **AS36849 scores the same as M247** (both 10, emerging). This is the key difference from Option 1. With CW only, we cannot distinguish between AS36849 (a dedicated single-operator AS — unique hosting choice) and M247 (a shared hosting provider with ~45 different operators). Both sit in the 2-5% CW band so they score identically.
- **Terrahost and Flokinet** score well — small CW correctly identified as rare.
- **Hurricane Electric** in the middle — moderate CW gives a moderate score.

### Pros

- **Absolute minimum complexity** — one threshold table, one multiplication
- **CW is the most meaningful security metric** — captures actual network influence regardless of relay count
- **Trivial to implement** — reuses the exact same `calculate_as_cw_factor` from Option 1
- **No dependency on contact data quality** — purely based on network measurements

### Cons

- **Cannot distinguish hosting choice uniqueness** — AS36849 (1 operator, dedicated AS) scores the same as M247 (45 operators, shared hosting). The fact that someone chose to run on their own AS — the ultimate diversity contribution — is invisible.
- **Cannot differentiate providers in the same CW band** — any two AS numbers with similar CW% get the same score regardless of how many operators share them.

---

## Side-by-Side Comparison

### Score Comparison Table

| AS | Name | Option 1 (CW + Contacts) | | Option 2 (CW Only) | |
|---|---|---|---|---|---|
| | | **Score** | **Tier** | **Score** | **Tier** |
| AS16276 | OVH SAS | 0 | common | 0 | common |
| AS24940 | Hetzner Online GmbH | 0 | common | 0 | common |
| AS36849 | 1st Amend. Encrypted Openness | **35** | **epic** | 10 | emerging |
| AS9009 | M247 Europe SRL | 15 | emerging | 10 | emerging |
| AS6939 | Hurricane Electric | 20 | rare | 20 | rare |
| AS56655 | Terrahost AS | 40 | epic | 40 | epic |
| AS205100 | Flokinet Ltd | 50 | legendary | 50 | legendary |

### Key Differences

The two options agree on 5 of 7 test AS numbers. They diverge on:

1. **AS36849** — Option 1 scores it 35 (epic) vs Option 2 scores it 10 (emerging). This is the biggest difference. Option 1 recognizes that being the sole operator on an AS is a unique and valuable diversity contribution. Option 2 only sees the 4% CW and treats it the same as any other mid-tier provider.

2. **AS9009 (M247)** — Option 1 scores it 15 (emerging) vs Option 2 scores it 10 (emerging). Same tier, but Option 1 gives slightly more credit because M247 has ~45 contacts vs OVH's ~350 — it's less crowded.

For the very small (Flokinet, Terrahost) and very large (OVH, Hetzner) AS numbers, both options produce the same result. The difference matters most for mid-range AS numbers where operator crowding varies significantly.

### Decision Matrix

| Criterion | Option 1 (CW + Contacts) | Option 2 (CW Only) |
|---|---|---|
| **Complexity** | Low (2 threshold tables) | Very Low (1 threshold table) |
| **Captures network influence** | Yes | Yes |
| **Captures hosting choice uniqueness** | Yes | No |
| **Rewards dedicated operator AS** | Yes (AS36849 → epic) | No (AS36849 → emerging) |
| **Distinguishes same-CW providers** | Yes | No |
| **Depends on contact data quality** | Partially | No |
| **Implementation effort** | ~2 hours | ~1 hour |
| **Mirrors country rarity pattern** | Yes (multi-factor weighted sum) | Partially (single factor) |

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

# Collect AS rarity scores for this operator's unique AS numbers
operator_as_scores = []
seen_as = set()
for relay in contact_relays:
    as_number = relay.get('as', '')
    if as_number and as_number not in seen_as:
        seen_as.add(as_number)
        as_info = self._lookup_as_data(as_number)  # existing helper
        if as_info:
            score = as_info.get('as_rarity_score', 0)
            tier = as_info.get('as_rarity_tier', 'common')
            operator_as_scores.append((as_number, score, tier))

rare_or_better = sum(1 for _, _, t in operator_as_scores
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
if unique_as_count == 1 and operator_as_scores:
    _, score, tier = operator_as_scores[0]
    portfolio_diversity = f"{network_rating}, 1 network ({tier})"
else:
    portfolio_diversity = f"{network_rating}, {unique_as_count} networks ({rare_or_better} rare)"
```

### After — What the Contact Page Shows

```
Network Diversity: Poor, 2 networks (0 rare)              (red)    — OVH + Hetzner
Network Diversity: Great, 2 networks (2 rare)             (green)  — Flokinet + Terrahost
Network Diversity: Okay, 4 networks (0 rare)              (yellow) — 4x mainstream providers
Network Diversity: Great, 1 network (epic)                (green)  — AS36849 sole operator
Network Diversity: Great, 3 networks (1 rare)             (green)  — 1 rare + 2 common
Network Diversity: Poor, 3 networks (0 rare)              (red)    — 3x mainstream providers
```

### Before vs After — Side by Side

| Operator | AS Numbers | BEFORE | AFTER | Why |
|---|---|---|---|---|
| 2 AS: OVH + Hetzner | Both common | **Okay**, 2 networks | **Poor**, 2 networks (0 rare) | Worst case: few AS, all mainstream |
| 3 AS: all mainstream | All common | **Okay**, 3 networks | **Poor**, 3 networks (0 rare) | Still <4, all common |
| 4 AS: all mainstream | All common | **Great**, 4 networks | **Okay**, 4 networks (0 rare) | At least spread across 4 providers |
| 5 AS: all mainstream | All common | **Great**, 5 networks | **Okay**, 5 networks (0 rare) | Spread but no rare choices |
| 2 AS: Flokinet + Terrahost | Both epic | **Okay**, 2 networks | **Great**, 2 networks (2 rare) | Quality over quantity |
| 1 AS: AS36849 (sole op) | Score 35 (epic) | **Great**, 1 AS with 1 operator | **Great**, 1 network (epic) | Rare AS, unique choice |
| 3 AS: 1 Flokinet + 2 OVH | 1 rare + 2 common | **Okay**, 3 networks | **Great**, 3 networks (1 rare) | Has at least 1 rare AS |
| 8 AS: all rare/epic | All score 30+ | **Great**, 8 networks | **Great**, 8 networks (8 rare) | Best case |

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

### Current Code — `aroileaders.py` call site

```python
diversity_score = calculate_diversity_score(
    countries=list(countries),
    platforms=list(platforms),
    unique_as_count=unique_as_count
)
```

### Current Code — `aroileaders.py` tooltip formatting

```python
diversity_breakdown_tooltip = (
    f"Diversity Score Calculation: {country_count} countries × 2.0 "
    f"+ {platform_count} operating systems × 1.5 "
    f"+ {as_count} unique ASNs × 1.0 = {metrics['diversity_score']}"
)
```

### Current Code — `aroi_macros.html` template rendering

Champion card:
```html
<span title="Diversity Score: Geographic (countries × 2.0) + Platform (OS types × 1.5)
 + Network (unique ASNs × 1.0)">{{ champion.diversity_score }} diversity</span>
```

Table row — Key Metric column:
```html
<span title="{{ entry.diversity_breakdown_tooltip }}">{{ entry.diversity_score }}</span>
```

Table row — last column header + cell:
```html
<th title="Number of unique Autonomous Systems (ASNs) used for network diversity">Unique AS</th>
...
<td>{{ entry.unique_as_count }}</td>
```

### Problem: Example Rankings Under Current System

Consider 3 hypothetical operators:

| Operator | Countries | Platforms | Unique AS | AS Quality | Current Score |
|---|---|---|---|---|---|
| Alpha | 5 | 1 | 8 | All OVH/Hetzner (common) | 5×2 + 1×1.5 + 8×1 = **19.5** |
| Beta | 3 | 1 | 3 | All rare (Flokinet, Terrahost, etc.) | 3×2 + 1×1.5 + 3×1 = **10.5** |
| Gamma | 4 | 2 | 2 | Both epic (AS36849, Flokinet) | 4×2 + 2×1.5 + 2×1 = **13.0** |

**Alpha ranks #1** despite all 8 AS numbers being saturated mainstream providers. Two problems:
1. The flat `× 1.0` rewards AS quantity regardless of quality.
2. The weights (country=2.0, platform=1.5, AS=1.0) don't reflect the right priority. Country diversity should matter most, AS rarity should be second, platform diversity should be third.

### Proposed Weights: Country > AS > Platform

The new formula reorders the weights so **geographic diversity is the most important factor**, followed by AS rarity, then platform diversity:

| Component | Old Weight | New Weight | Rationale |
|---|---|---|---|
| Country | 2.0 per country | **3.0** per country | Geographic diversity is the primary resilience factor — jurisdictional spread |
| AS (network) | 1.0 per unique AS (flat) | **2.0** per unique AS × avg rarity | AS choice quality matters, not just count. Normalized so it doesn't dominate |
| Platform | 1.5 per platform | **1.0** per platform | Platform matters least — most relays are Linux and that's fine |

The AS component is **normalized**: the average rarity score (0-60) is divided by the max (60) to produce a 0-1 factor, then multiplied by 2.0 per unique AS. This ensures:
- An operator with 3 rare AS (avg rarity 45) gets: 3 × (45/60) × 2.0 = **4.5 points**
- An operator with 8 common AS (avg rarity 0) gets: 8 × (0/60) × 2.0 = **0 points**
- An operator with 2 epic AS (avg rarity 42) gets: 2 × (42/60) × 2.0 = **2.8 points**

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
    
    # Geographic component — highest weight (countries × 3.0)
    if countries:
        diversity_score += len(countries) * 3.0
    
    # Network component — middle weight (normalized AS rarity × 2.0 per AS)
    # avg_rarity / 60 normalizes the 0-60 rarity score to 0-1
    # Then × 2.0 per unique AS keeps it between country (3.0) and platform (1.0)
    if as_diversity_score is not None and unique_as_count and unique_as_count > 0:
        avg_rarity = as_diversity_score / unique_as_count  # 0-60 range
        normalized = avg_rarity / 60.0                     # 0-1 range
        diversity_score += unique_as_count * normalized * 2.0
    elif unique_as_count:
        diversity_score += unique_as_count * 1.0  # flat fallback
    
    # Platform component — lowest weight (platforms × 1.0)
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

`calculate_operator_as_diversity_score` iterates the operator's unique AS numbers, looks up each one's pre-computed `as_rarity_score` from `sorted['as']`, and sums them.

### Proposed Code — `aroileaders.py` tooltip formatting

```python
diversity_breakdown_tooltip = (
    f"Diversity Score: {country_count} countries × 3.0 "
    f"+ {as_count} AS (rarity-weighted) × 2.0 "
    f"+ {platform_count} platforms × 1.0 = {metrics['diversity_score']:.1f}"
)
```

### Proposed Code — `aroi_macros.html` template changes

Champion card — update tooltip only:
```html
<span title="Diversity Score: Geographic (countries × 3.0) + Network (AS rarity × 2.0)
 + Platform (OS types × 1.0)">{{ champion.diversity_score }} diversity</span>
```

Table row — Key Metric column: no change (still shows `{{ entry.diversity_score }}`).

Table row — Unique AS column: keep it, optionally add AS diversity sub-score:
```html
<th title="Unique AS count and AS diversity score (rarity-weighted)">Unique AS</th>
...
<td title="AS diversity score: {{ entry.as_diversity_score }}">{{ entry.unique_as_count }}</td>
```

### After: Same 3 Operators Under New System

Using rarity scores from the proposal (OVH=0, Hetzner=0, Flokinet=50, Terrahost=40, AS36849=35):

| Operator | Countries | Platforms | Unique AS | Avg Rarity | Country Pts | AS Pts | Platform Pts | New Score |
|---|---|---|---|---|---|---|---|---|
| Alpha | 5 | 1 | 8 (all common) | 0 | 5×3.0 = 15 | 8×(0/60)×2 = 0 | 1×1.0 = 1 | **16.0** |
| Beta | 3 | 1 | 3 (all rare, ~45) | 45 | 3×3.0 = 9 | 3×(45/60)×2 = 4.5 | 1×1.0 = 1 | **14.5** |
| Gamma | 4 | 2 | 2 (both epic, ~42) | 42.5 | 4×3.0 = 12 | 2×(42.5/60)×2 = 2.8 | 2×1.0 = 2 | **16.8** |

### Before vs After — Ranking Comparison

| Rank | BEFORE (flat) | Score | AFTER (rarity-weighted) | Score |
|---|---|---|---|---|
| #1 | Alpha (5 ctry, 8 common AS) | 19.5 | **Gamma** (4 ctry, 2 epic AS, 2 plat) | **16.8** |
| #2 | Gamma (4 ctry, 2 epic AS) | 13.0 | **Alpha** (5 ctry, 8 common AS) | **16.0** |
| #3 | Beta (3 ctry, 3 rare AS) | 10.5 | **Beta** (3 ctry, 3 rare AS) | **14.5** |

### What Changed in the Rankings

- **Gamma rises to #1** — 4 countries + 2 epic AS + 2 platforms beats Alpha's 5 countries but worthless AS choices.
- **Alpha drops from #1 to #2** — still gets credit for 5 countries (the most important factor), but 8 common AS now contribute 0 instead of 8 points. It almost ties with Gamma because country weight (3.0) is the dominant factor.
- **Beta stays #3** — only 3 countries holds it back. But its 3 rare AS now contribute 4.5 points instead of 3 points, narrowing the gap significantly (14.5 vs 16.0 instead of 10.5 vs 19.5).

### Weight Hierarchy in Action

To verify country > AS > platform ordering, compare same-base operators:

| Operator | Change | Score Impact |
|---|---|---|
| Base: 3 ctry, 1 plat, 2 common AS | — | 3×3 + 0 + 1 = **10.0** |
| +1 country | +3.0 | **13.0** (+3.0) |
| +1 epic AS (rarity 42) | +1.4 | **11.4** (+1.4) |
| +1 platform | +1.0 | **11.0** (+1.0) |

Adding a country (+3.0) is worth more than adding an epic AS (+1.4), which is worth more than adding a platform (+1.0). The hierarchy **country > AS > platform** holds at every level.

---

## User-Facing Locations Audit

A full audit of every place in the codebase where diversity or AS data appears in user-facing output. These are the locations where the new AS rarity score could be surfaced or where existing diversity calculations would change.

---

### 1. AROI Leaderboard — "Most Diverse Operators" (existing)

**Files**: `aroileaders.py` (lines 644-650, 894-899), `aroi_macros.html`, `aroi-leaderboards.html`

This is the primary diversity leaderboard today. Currently ranked by `diversity_score` which uses the **flat** formula:

```
diversity_score = countries * 2.0 + platforms * 1.5 + unique_as_count * 1.0
```

The template shows:
- Champion card: `{{ champion.diversity_score }} diversity` with tooltip "Diversity Score: Geographic (countries x 2.0) + Platform (OS types x 1.5) + Network (unique ASNs x 1.0)"
- Table rows: `{{ entry.diversity_score }}` as primary metric, `{{ entry.country_count }} countries`, `{{ entry.unique_as_count }}` in a Unique AS column
- Achievement titles: "Diversity Legend", "Diversity Master", "Diversity Champion"
- Breakdown tooltip: "Diversity Score Calculation: X countries x 2.0 + Y operating systems x 1.5 + Z unique ASNs x 1.0 = score"

**Change needed**: Replace `unique_as_count * 1.0` with sum of AS rarity scores per unique AS. Update tooltip text to reflect new formula. The `unique_as_count` column stays (it's still useful info) but the score calculation changes.

---

### 2. AROI Leaderboard — New "AS Diversity Champions" category

**Files**: `aroileaders.py`, `aroi_macros.html`, `aroi-leaderboards.html`

**New addition**: A 19th leaderboard category ranked purely by operator-level AS diversity score (sum of AS rarity scores across each unique AS the operator uses). Separate from "Most Diverse" which combines country + platform + AS.

**Nav link in** `aroi-leaderboards.html` (line 33) would add a new entry alongside the existing:

```html
<a href="#most_diverse" ...>Most Diverse</a>
<!-- NEW -->
<a href="#as_diversity" ...>AS Diversity</a>
```

---

### 3. Contact Page — Operator Intelligence: "Network Diversity"

**Files**: `intelligence_engine.py` (lines 547-585), `relays.py` (lines 3644-3647), `contact.html` (lines 119-121)

The Intelligence Engine Layer 14 computes `portfolio_diversity` per contact, displayed as "Network Diversity" on each contact page. Current logic:

```python
# 1 unique AS = "Poor" (unless sole operator on that AS → "Great")
# 2-3 unique AS = "Okay"
# 4+ unique AS = "Great"
```

Displayed as:
```html
<li><strong>Network Diversity:</strong> Great, 8 networks</li>
```

**Change needed**: Incorporate AS rarity into the rating. An operator with 2 AS numbers that are both rare could be rated higher than an operator with 4 AS numbers that are all OVH/Hetzner. Could show: "Great, 3 networks (2 rare, 1 common)" or include the AS rarity score.

---

### 4. Contact Page — Operator Intelligence: "Infrastructure Diversity"

**Files**: `intelligence_engine.py` (lines 653-683), `relays.py` (lines 3654-3655), `contact.html` (lines 127-129)

Currently measures **platform** diversity (OS types). Not directly AS-related, but it's a sibling metric in the same intelligence section.

```html
<li><strong>Infrastructure Diversity:</strong> Great, 2 platforms</li>
```

**No change needed** — this is platform-specific. Mentioned for context only.

---

### 5. Relay Info Page — AS Number & AS Name

**Files**: `relay-info.html` (lines 431-446 in Section 2, lines 821-835 in legacy section)

Each relay's detail page shows the AS number and AS name in two places:

```html
<!-- Section 2: Network Details -->
<dt>AS Number</dt>
<dd><a href="...">AS36849</a></dd>
<dt>AS Name</dt>
<dd>1st Amendment Encrypted Openness LLC (BGP.tools)</dd>

<!-- Legacy section at bottom -->
<a href='...' title="AS Number">AS36849</a> |
<span title="AS Name">1st Amendment Encrypted Openness LLC</span>
```

**Change needed**: Add AS rarity tier badge next to AS name. E.g.: `1st Amendment Encrypted Openness LLC [epic]`

---

### 6. AS Detail Page — Per-AS Summary

**Files**: `as.html`, `relay-list.html` (shared base), `macros.html` (detail_summary macro)

Each AS gets its own page (e.g., `/as/AS36849/`) showing relay list and summary stats (bandwidth, consensus weight, guard/middle/exit counts, unique AROI operators, unique contacts).

```html
{% block title %}Tor Relays :: {{ as_name }} ({{ as_number }}){% endblock %}
{{ detail_summary(bandwidth, ..., unique_contact_count=unique_contact_count, ...) }}
```

**Change needed**: Add AS rarity score and tier to the AS detail page summary. This is the most natural place to show "This AS is rated epic (score: 35)".

---

### 7. Browse by Network (misc-networks.html) — AS Listing Table

**Files**: `misc-networks.html` (lines 42-49, 127-131)

Lists all AS numbers with relay counts, bandwidth, consensus weight. Also shows intelligence context:

```html
<li><strong>Infrastructure Dependency</strong>:
    {{ networks_top_3_percentage }}% in top 3 ASes,
    {{ critical_as_count }} critical ({{ critical_as_list|join(', ') }})
</li>
```

The table rows show AS number, AS name, relay count, bandwidth, CW%.

**Change needed**: Add AS rarity tier column to the table. Add rarity distribution to the intelligence context (e.g., "X legendary, Y epic, Z rare, W common AS numbers").

---

### 8. Browse by Contact (misc-contacts.html) — Contact Table

**Files**: `misc-contacts.html` (lines 106-153)

Each contact row shows a "Unique AS" column:

```html
<th title="Number of different autonomous systems">Unique AS</th>
...
<td>{{ v['unique_as_count'] }}</td>
```

**Change needed**: Could add an "AS Diversity Score" column alongside or replace "Unique AS" count with the rarity-weighted score. Or keep both: "3 AS (score: 85)".

---

### 9. Network Health Dashboard — AS Concentration Metrics

**Files**: `network-health-dashboard.html` (lines 498-519), `relays.py` (network health computation)

Shows top-3 AS by CW, top-5 and top-10 AS concentration percentages:

```html
<span class="metric-value">{{ top_3_as_concentration }}%</span>
<span class="metric-label">Top 3 AS CW Share</span>
```

Also shows top AS for IPv4/IPv6.

**Change needed**: Could add a "Network AS Diversity" metric showing distribution of AS rarity tiers across the network (e.g., "650 common, 200 emerging, 80 rare, 20 epic, 5 legendary").

---

### 10. Relay List Tables — AS Name Column

**Files**: `relay-list.html` (lines 131-139), `contact-relay-list.html` (lines 182-189)

Every relay list table shows AS name as a clickable column:

```html
<td>
    <a href="https://bgp.tools/{{ relay['as'] }}"
       title="{{ relay['as_name'] }}">{{ relay['as_name']|truncate(20) }}</a>
</td>
```

**No change needed** unless we want to add a small rarity indicator (e.g., colored dot) inline. Low priority.

---

### 11. Directory Authorities Page

**Files**: `misc-authorities.html` (lines 122-201)

Shows AS number and AS name for each directory authority:

```html
<th>AS Number</th>
<th>AS Name</th>
...
<td><a href="...">{{ authority.as }}</a></td>
<td>{{ authority.as_name|truncate(20) }}</td>
```

**No change needed** — directory authorities are a special case, not scored for diversity.

---

### 12. Intelligence Engine — Layer 10: Infrastructure Dependency

**Files**: `intelligence_engine.py` (lines 304-337)

Identifies "critical AS" (those holding >5% of network CW):

```python
critical_as = []
for as_number, as_data in self.sorted_data['as'].items():
    if as_data.get('consensus_weight_fraction', 0) > 0.05:
        critical_as.append(as_number)
```

Displayed in `misc-networks.html` as intelligence context.

**Change needed**: Could complement critical AS detection with rarity data — "X critical AS (all common tier), Y rare or better AS available as alternatives".

---

## Summary: Recommended Changes by Priority

| Priority | Location | Change | File(s) |
|---|---|---|---|
| **P0** | `country_utils.py` | Add `calculate_as_cw_factor`, `calculate_as_contact_factor`, `calculate_as_rarity_score`, `assign_as_rarity_tier` | `country_utils.py` |
| **P0** | `relays.py` | Pre-compute AS rarity score and tier during `_categorize()` | `relays.py` |
| **P1** | AROI "Most Diverse" leaderboard | Replace flat `unique_as_count * 1.0` with rarity-weighted AS score in `calculate_diversity_score()` | `country_utils.py`, `aroileaders.py` |
| **P1** | AROI "Most Diverse" template | Update tooltip formula text, keep Unique AS column | `aroi_macros.html` |
| **P1** | Contact Operator Intelligence | Incorporate AS rarity into "Network Diversity" rating logic | `intelligence_engine.py` |
| **P2** | AS detail page | Show AS rarity score and tier in page summary | `as.html`, `macros.html` |
| **P2** | Relay info page | Add AS rarity tier badge next to AS name | `relay-info.html` |
| **P2** | New AROI leaderboard | Add 19th category "AS Diversity Champions" | `aroileaders.py`, `aroi_macros.html`, `aroi-leaderboards.html` |
| **P3** | Browse by Network | Add rarity tier column to AS table, rarity distribution to intelligence context | `misc-networks.html` |
| **P3** | Browse by Contact | Add AS diversity score alongside unique AS count | `misc-contacts.html` |
| **P3** | Network Health Dashboard | Add network-wide AS rarity distribution metric | `network-health-dashboard.html`, `relays.py` |
| **P3** | Intelligence Layer 10 | Complement critical AS detection with rarity context | `intelligence_engine.py` |

---

## Open Questions

1. **Should the contact factor weight be higher or lower than CW?** Currently both are weighted at 5. If CW is considered more important, it could be weighted at 6 vs contact at 4.

2. **How should newly appeared AS numbers be handled?** A brand-new AS with 1 relay would get maximum rarity. This is correct (it IS rare) but could be gamed. Consider requiring minimum relay uptime before scoring.

3. **Should the new "AS Diversity Champions" leaderboard (P2) be added in the same release as the score calculation (P0/P1)?** Could be phased separately.

---

*This document proposes a 2-factor AS diversity scoring system (consensus weight + unique contacts) for Allium. All user-facing locations where the score could appear have been audited above. Feedback welcome before implementation begins.*
