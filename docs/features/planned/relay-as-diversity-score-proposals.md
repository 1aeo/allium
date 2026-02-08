# Relay AS Diversity Score — Implementation Proposals

**Status**: Proposal  
**Created**: February 2026  
**Branch**: `cursor/relay-as-diversity-proposals-719c`  
**Related**: AROI Leaderboards (`aroileaders.py`), Intelligence Engine (`intelligence_engine.py`), Country Diversity (`country_utils.py`)

---

## Problem Statement

The Tor network's resilience depends on relay distribution across many different Autonomous Systems (AS numbers). When a large fraction of relays are concentrated on a few hosting providers (e.g., OVH, Hetzner, DigitalOcean), the network becomes vulnerable to:

- **Single-point censorship**: A hosting provider can be compelled to shut down all relays at once.
- **Traffic correlation attacks**: An adversary controlling an AS can observe traffic entering and leaving the network.
- **Regulatory risk**: A single jurisdiction can affect a disproportionate share of the network.

Currently, Allium tracks AS-level data (relay counts, consensus weight fraction, unique contacts per AS) and has a basic `diversity_score` in `country_utils.py` that weights countries (x2.0), platforms (x1.5), and unique AS count (x1.0). However, there is **no mechanism to award bonus points to relays running on rare or underrepresented AS numbers**, nor to penalize concentration on dominant providers.

**Goal**: A relay on an unknown/rare AS number gets more points. A relay on OVH gets fewer points.

---

## Existing Technique: Country Rarity Scoring

The codebase already has a proven, simple, threshold-based rarity scoring system for **countries** in `country_utils.py`. The AS diversity proposals below are designed to follow the exact same pattern.

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

This is simple, readable, and easy to tune. The AS diversity proposals below reuse this exact structure.

### Existing Diversity Score (flat)

The current operator-level diversity score in `calculate_diversity_score()`:

```python
diversity_score = 0.0
diversity_score += len(countries) * 2.0       # Geographic
diversity_score += len(platforms) * 1.5        # Platform
diversity_score += unique_as_count * 1.0       # Network (flat — every AS worth 1.0)
```

The problem: every AS contributes the same 1.0 regardless of whether it's an unknown hosting provider or OVH with 2,000+ relays.

### Data Already Available

| Data Point | Location | Description |
|---|---|---|
| `relay['as']` | Per-relay | AS number (e.g., `"AS16276"` for OVH) |
| `relay['as_name']` | Per-relay | Human-readable AS name |
| `sorted['as'][as_number]` | Sorted data | Per-AS aggregated data |
| `sorted['as'][X]['consensus_weight_fraction']` | Sorted data | CW fraction of this AS |
| `sorted['as'][X]['unique_contact_count']` | Sorted data | Distinct operators in this AS |
| `contact_data['unique_as_count']` | Per-contact | Unique AS count for an operator |

---

## Proposal A: Threshold-Based AS Rarity Score (Recommended)

### Concept

Apply the **exact same pattern** as the country rarity system. Score each AS across simple threshold-based factors, multiply by weights, sum. No log functions, no complex math — just if/elif thresholds returning small integers.

### Algorithm

```python
# === AS RARITY SCORING SYSTEM ===
# Mirrors the country rarity system in structure and simplicity.

def calculate_as_relay_count_factor(as_relay_count):
    """
    Factor 1: How many relays are on this AS?
    Fewer relays = higher score. Simple threshold brackets.
    
    Returns: 0-6 points
    """
    if as_relay_count == 0:
        return 0
    elif as_relay_count <= 2:
        return 6   # Almost unique
    elif as_relay_count <= 5:
        return 5   # Very rare
    elif as_relay_count <= 10:
        return 4   # Rare
    elif as_relay_count <= 25:
        return 3   # Uncommon
    elif as_relay_count <= 100:
        return 2   # Moderate
    elif as_relay_count <= 500:
        return 1   # Popular
    else:
        return 0   # Saturated (OVH, Hetzner, etc.)


def calculate_as_network_percentage_factor(as_relay_count, total_network_relays):
    """
    Factor 2: What percentage of the network is on this AS?
    Lower share = higher score.
    
    Returns: 0-6 points
    """
    if total_network_relays == 0:
        return 0
    
    percentage = (as_relay_count / total_network_relays) * 100
    
    if percentage < 0.05:    return 6   # Ultra-rare (<0.05% of network)
    elif percentage < 0.1:   return 5   # Very rare
    elif percentage < 0.25:  return 4   # Rare
    elif percentage < 0.5:   return 3   # Uncommon
    elif percentage < 1.0:   return 2   # Moderate
    elif percentage < 3.0:   return 1   # Popular
    else:                    return 0   # Dominant (>3% of network)


def calculate_as_consensus_weight_factor(as_cw_fraction):
    """
    Factor 3: How much consensus weight does this AS hold?
    Lower CW = higher score. Captures actual network influence.
    
    Returns: 0-6 points
    """
    cw_percentage = as_cw_fraction * 100
    
    if cw_percentage <= 0:
        return 0
    elif cw_percentage < 0.01:
        return 6   # Negligible influence
    elif cw_percentage < 0.05:
        return 5   # Tiny influence
    elif cw_percentage < 0.1:
        return 4   # Small influence
    elif cw_percentage < 0.5:
        return 3   # Modest influence
    elif cw_percentage < 1.0:
        return 2   # Noticeable influence
    elif cw_percentage < 5.0:
        return 1   # Significant influence
    else:
        return 0   # Major AS — dominant influence


def calculate_as_operator_factor(unique_contact_count):
    """
    Factor 4: How many distinct operators share this AS?
    Fewer operators = the current operator's choice is more unique.
    An AS with only 1 operator means that operator made a unique hosting choice.
    
    Returns: 0-4 points
    """
    if unique_contact_count <= 0:
        return 0
    elif unique_contact_count == 1:
        return 4   # Sole operator — unique AS choice
    elif unique_contact_count <= 3:
        return 3   # Very few operators
    elif unique_contact_count <= 10:
        return 2   # Small community
    elif unique_contact_count <= 50:
        return 1   # Moderate community
    else:
        return 0   # Heavily shared (many operators chose same provider)


def calculate_as_rarity_score(as_relay_count, total_network_relays,
                               as_cw_fraction, unique_contact_count):
    """
    Calculate the overall AS rarity score using weighted factors.
    
    Same pattern as country rarity:
      score = (factor1 * weight1) + (factor2 * weight2) + ...
    
    Args:
        as_relay_count: Number of relays on this AS
        total_network_relays: Total relays on the network
        as_cw_fraction: Consensus weight fraction of this AS (0.0-1.0)
        unique_contact_count: Number of distinct operators on this AS
    
    Returns:
        int: Weighted rarity score (0-100 range)
    """
    relay_factor = calculate_as_relay_count_factor(as_relay_count)
    network_factor = calculate_as_network_percentage_factor(as_relay_count, total_network_relays)
    cw_factor = calculate_as_consensus_weight_factor(as_cw_fraction)
    operator_factor = calculate_as_operator_factor(unique_contact_count)
    
    return (
        (relay_factor * 4) +       # Relay count: weight 4 (most important)
        (network_factor * 3) +     # Network share: weight 3
        (cw_factor * 3) +          # Consensus weight: weight 3
        (operator_factor * 2)      # Operator uniqueness: weight 2
    )


def assign_as_rarity_tier(rarity_score):
    """
    Assign tier classification. Same tiers as country rarity.
    
    Max possible score: (6*4) + (6*3) + (6*3) + (4*2) = 24+18+18+8 = 68
    """
    if rarity_score >= 50:   return 'legendary'    # Extremely rare AS
    elif rarity_score >= 35: return 'epic'         # Very rare AS
    elif rarity_score >= 20: return 'rare'         # Uncommon AS
    elif rarity_score >= 10: return 'emerging'     # Below-average presence
    else:                    return 'common'        # Well-known provider
```

### Worked Examples

Assuming ~7,000 total relays on the network:

**AS205100 (Flokinet) — 5 relays, 0.03% CW, 2 operators**:
- Relay count: 5 relays -> 5 pts
- Network %: 5/7000 = 0.07% -> 5 pts
- CW: 0.03% -> 5 pts
- Operators: 2 -> 3 pts
- Score = (5 * 4) + (5 * 3) + (5 * 3) + (3 * 2) = 20 + 15 + 15 + 6 = **56 (legendary)**

**AS24940 (Hetzner) — 800 relays, 8% CW, 200 operators**:
- Relay count: 800 relays -> 0 pts
- Network %: 800/7000 = 11.4% -> 0 pts
- CW: 8% -> 0 pts
- Operators: 200 -> 0 pts
- Score = 0 + 0 + 0 + 0 = **0 (common)**

**AS9009 (M247) — 40 relays, 0.4% CW, 15 operators**:
- Relay count: 40 relays -> 2 pts
- Network %: 40/7000 = 0.57% -> 2 pts
- CW: 0.4% -> 3 pts
- Operators: 15 -> 1 pt
- Score = (2 * 4) + (2 * 3) + (3 * 3) + (1 * 2) = 8 + 6 + 9 + 2 = **25 (rare)**

### Operator-Level Scoring

```python
def calculate_operator_as_diversity_score(operator_relays, sorted_as_data, total_relays):
    """
    Calculate total AS diversity score for an operator.
    Sum of rarity scores for each unique AS the operator uses.
    
    An operator with 3 relays all on OVH scores ~0.
    An operator with 3 relays each on a different rare AS scores ~150+.
    """
    seen_as = set()
    total_score = 0
    
    for relay in operator_relays:
        as_number = relay.get('as', '')
        if not as_number or as_number in seen_as:
            continue
        seen_as.add(as_number)
        
        as_data = sorted_as_data.get(as_number, {})
        as_relay_count = len(as_data.get('relays', []))
        as_cw_fraction = as_data.get('consensus_weight_fraction', 0)
        unique_contacts = as_data.get('unique_contact_count', 0)
        
        total_score += calculate_as_rarity_score(
            as_relay_count, total_relays, as_cw_fraction, unique_contacts
        )
    
    return total_score
```

### Pros

- **Identical pattern** to existing country rarity — easy to review, test, maintain
- **No math imports** — just if/elif and integer arithmetic
- **All 4 factors** capture different aspects (count, share, influence, crowding)
- **Easy to tune** — adjust any threshold or weight independently
- **Deterministic** — same input always produces same output, no floating-point surprises

### Cons

- Threshold brackets are manually chosen (but same is true for country rarity)
- Relay count and network percentage overlap somewhat (both measure AS size)

---

## Proposal B: Two-Factor Simplified Score

### Concept

If Proposal A feels like too many factors, strip it down to the **two most important dimensions**: how many relays are on the AS, and how much consensus weight it holds. Two factors, same threshold pattern.

### Algorithm

```python
def calculate_as_rarity_score_simple(as_relay_count, total_network_relays, as_cw_fraction):
    """
    Simplified 2-factor AS rarity score.
    
    Factor 1: Relay count (0-6 pts, weight 5)
    Factor 2: Consensus weight (0-6 pts, weight 5)
    
    Max score: (6*5) + (6*5) = 60
    """
    # Factor 1: Relay count
    if as_relay_count == 0:       relay_factor = 0
    elif as_relay_count <= 2:     relay_factor = 6
    elif as_relay_count <= 5:     relay_factor = 5
    elif as_relay_count <= 15:    relay_factor = 4
    elif as_relay_count <= 50:    relay_factor = 3
    elif as_relay_count <= 200:   relay_factor = 2
    elif as_relay_count <= 500:   relay_factor = 1
    else:                         relay_factor = 0
    
    # Factor 2: Consensus weight
    cw_percentage = as_cw_fraction * 100
    if cw_percentage <= 0:        cw_factor = 0
    elif cw_percentage < 0.01:    cw_factor = 6
    elif cw_percentage < 0.05:    cw_factor = 5
    elif cw_percentage < 0.1:     cw_factor = 4
    elif cw_percentage < 0.5:     cw_factor = 3
    elif cw_percentage < 2.0:     cw_factor = 2
    elif cw_percentage < 5.0:     cw_factor = 1
    else:                         cw_factor = 0
    
    return (relay_factor * 5) + (cw_factor * 5)


def assign_as_rarity_tier_simple(rarity_score):
    """Tier assignment for 2-factor score. Max = 60."""
    if rarity_score >= 45:   return 'legendary'
    elif rarity_score >= 30: return 'epic'
    elif rarity_score >= 18: return 'rare'
    elif rarity_score >= 8:  return 'emerging'
    else:                    return 'common'
```

### Worked Examples

**Flokinet (5 relays, 0.03% CW)**: (5 * 5) + (5 * 5) = **50 (legendary)**  
**Hetzner (800 relays, 8% CW)**: (0 * 5) + (0 * 5) = **0 (common)**  
**M247 (40 relays, 0.4% CW)**: (3 * 5) + (3 * 5) = **30 (epic)**

### Pros

- Simplest possible meaningful implementation
- Only 2 factors to understand and tune
- Covers both relay count and actual network influence

### Cons

- Doesn't capture operator crowding (unique_contact_count)
- Doesn't distinguish between "small AS with 1 operator" vs "small AS with 10 operators"

---

## Proposal C: Network-Share-Only Score

### Concept

The absolute simplest approach. One factor: what percentage of the network's relays are on this AS? That single number determines the score. Nothing else.

### Algorithm

```python
def calculate_as_rarity_score_minimal(as_relay_count, total_network_relays):
    """
    Single-factor AS rarity score based on network share.
    
    Returns: 0-6 points (can be used directly or multiplied by a weight)
    
    The idea: an AS hosting <0.05% of the network is ultra-rare.
    An AS hosting >5% of the network is saturated.
    """
    if total_network_relays == 0 or as_relay_count == 0:
        return 0
    
    percentage = (as_relay_count / total_network_relays) * 100
    
    if percentage < 0.05:    return 6   # Ultra-rare
    elif percentage < 0.1:   return 5   # Very rare
    elif percentage < 0.25:  return 4   # Rare
    elif percentage < 0.5:   return 3   # Uncommon
    elif percentage < 1.0:   return 2   # Moderate
    elif percentage < 3.0:   return 1   # Popular
    else:                    return 0   # Saturated
```

This is literally the same function as `calculate_network_percentage_factor` for countries but applied to AS data. To use it in the operator-level diversity score:

```python
def calculate_diversity_score(countries, platforms=None, unique_as_count=None,
                              operator_relays=None, sorted_as_data=None,
                              total_network_relays=None):
    """Enhanced diversity score — rare AS worth more than common AS."""
    diversity_score = 0.0
    
    if countries:
        diversity_score += len(countries) * 2.0
    if platforms:
        diversity_score += len(platforms) * 1.5
    
    # AS component: rarity-weighted instead of flat count
    if operator_relays and sorted_as_data and total_network_relays:
        seen_as = set()
        for relay in operator_relays:
            as_number = relay.get('as', '')
            if as_number and as_number not in seen_as:
                seen_as.add(as_number)
                as_data = sorted_as_data.get(as_number, {})
                as_relay_count = len(as_data.get('relays', []))
                rarity = calculate_as_rarity_score_minimal(as_relay_count, total_network_relays)
                diversity_score += rarity  # 0-6 per unique AS instead of flat 1.0
    elif unique_as_count:
        diversity_score += unique_as_count * 1.0  # Fallback to flat
    
    return diversity_score
```

### Worked Examples (7,000 total relays)

**Operator with 3 relays on 3 rare AS (5, 8, 3 relays each)**:
- AS with 5 relays: 0.07% -> 5 pts
- AS with 8 relays: 0.11% -> 4 pts
- AS with 3 relays: 0.04% -> 6 pts
- AS component = 15 pts (vs. 3 pts with flat scoring)

**Operator with 3 relays all on OVH (2,000 relays)**:
- AS with 2,000 relays: 28.6% -> 0 pts
- AS component = 0 pts (vs. 1 pt with flat scoring)

### Pros

- **Absolute minimum complexity** — one function, one threshold table
- Identical to existing `calculate_network_percentage_factor` — just reused for AS
- Trivial to implement, test, and explain
- Already proven to work for countries

### Cons

- Doesn't capture consensus weight — an AS with 5 relays but 10% CW scores the same as one with 5 relays and 0.01% CW
- Doesn't capture operator crowding

---

## Comparison Matrix

| Criterion | Proposal A (4-Factor) | Proposal B (2-Factor) | Proposal C (1-Factor) |
|---|---|---|---|
| **Complexity** | Moderate | Low | Very Low |
| **Factors** | Relay count + Network % + CW + Operators | Relay count + CW | Network % only |
| **Max Score per AS** | 68 | 60 | 6 |
| **Captures CW** | Yes | Yes | No |
| **Captures operator crowding** | Yes | No | No |
| **Mirrors country rarity pattern** | Exactly | Partially | Exactly (single factor) |
| **Implementation effort** | ~3 hours | ~2 hours | ~1 hour |
| **Tuning complexity** | 4 threshold tables + 4 weights | 2 threshold tables + 2 weights | 1 threshold table |
| **Explainability** | Good (familiar pattern) | Good | Excellent |

---

## Recommendation

**Proposal A (Threshold-Based 4-Factor)** is recommended because:

1. **Mirrors the proven country rarity pattern exactly** — same structure, same style, same kind of threshold tables. Anyone who understands `calculate_relay_count_factor` + `calculate_network_percentage_factor` + `calculate_geopolitical_factor` + `calculate_regional_factor` will immediately understand the AS version.

2. **Captures what matters** — a rare AS is not just one with few relays. It's one with low relay count AND low consensus weight AND few other operators. Proposal A is the only one that captures all dimensions.

3. **Still simple** — no log functions, no floating-point math beyond basic division, no imports. Just if/elif thresholds and integer multiplication. Same level of complexity as the existing country system.

**Proposal C (1-Factor)** is a good fallback if minimal implementation time is preferred. It can be implemented in under an hour by literally reusing the existing `calculate_network_percentage_factor` function.

**Proposal B (2-Factor)** is the middle ground — captures both relay count and consensus weight without the operator crowding dimension.

---

## Integration Points

Regardless of which proposal is chosen, the integration follows the same pattern:

### 1. `country_utils.py` — Add AS rarity functions

New functions following the existing naming pattern:
- `calculate_as_relay_count_factor()`
- `calculate_as_network_percentage_factor()`
- `calculate_as_consensus_weight_factor()` (Proposal A/B only)
- `calculate_as_operator_factor()` (Proposal A only)
- `calculate_as_rarity_score()`
- `assign_as_rarity_tier()`

### 2. `relays.py` — Pre-compute AS rarity during `_categorize()`

After `sorted['as']` is built, compute rarity score for each AS in one pass:

```python
# In _categorize(), after AS data is assembled:
total_relays = len(all_relays)
for as_number, as_data in self.json['sorted']['as'].items():
    as_relay_count = len(as_data.get('relays', []))
    as_cw = as_data.get('consensus_weight_fraction', 0)
    unique_contacts = as_data.get('unique_contact_count', 0)
    as_data['as_rarity_score'] = calculate_as_rarity_score(
        as_relay_count, total_relays, as_cw, unique_contacts
    )
    as_data['as_rarity_tier'] = assign_as_rarity_tier(as_data['as_rarity_score'])
```

### 3. `aroileaders.py` — New leaderboard + enhanced diversity score

```python
# Per-operator AS diversity score (sum of AS rarity scores for each unique AS)
as_diversity_score = calculate_operator_as_diversity_score(
    operator_relays, sorted_as_data, total_relays
)

# New leaderboard: AS Diversity Champions
leaderboards['as_diversity'] = sorted(
    aroi_operators.items(),
    key=lambda x: x[1]['as_diversity_score'],
    reverse=True
)[:50]
```

### 4. `intelligence_engine.py` — Layer 14 contact intelligence

Add AS rarity assessment to contact pages:

```python
# In _layer14_contact_intelligence():
as_rarity_assessment = "Above Average"  # or "Below Average", "Excellent", etc.
rare_as_count = sum(1 for as_num in unique_as_set
                    if sorted_as_data.get(as_num, {}).get('as_rarity_tier') in ('legendary', 'epic', 'rare'))
```

### 5. `relay-info.html` — Display AS rarity badge

```html
<td>{{ relay.as_name }}
  <span class="badge badge-{{ relay.as_rarity_tier }}">{{ relay.as_rarity_tier }}</span>
</td>
```

### 6. `calculate_diversity_score()` — Replace flat AS component

```python
# Replace: unique_as_count * 1.0
# With:    sum of rarity scores per unique AS
if as_rarity_score is not None:
    diversity_score += as_rarity_score
elif unique_as_count:
    diversity_score += unique_as_count * 1.0  # backward-compatible fallback
```

---

## Example Output

### Relay Info Page

```
AS Number: AS205100 (Flokinet Ltd)
AS Rarity: legendary (score: 56)
           Only 5 relays on this AS network-wide
```

### AROI Leaderboard — AS Diversity Champions

| Rank | Operator | AS Diversity Score | Unique AS | Best AS Tier | Specialization |
|------|----------|--------------------|-----------|--------------|----------------|
| 1 | diverse-ops.org | 187 | 12 | legendary | 4 legendary, 5 epic, 3 rare |
| 2 | global-tor.net | 142 | 8 | epic | 2 legendary, 4 epic, 2 rare |
| 3 | privacy-relay.io | 23 | 15 | common | 0 legendary, 1 rare, 14 common |

### Intelligence Engine — Contact Page

```
Network Diversity: Great, 8 networks
AS Rarity: Above Average — 5 of 8 AS numbers are rare or better
  - AS205100 (Flokinet): legendary (56 pts)
  - AS60729 (Leaseweb DE): rare (25 pts)
  - AS24940 (Hetzner): common (0 pts)
```

---

## Open Questions

1. **Should the AS diversity score replace the flat `unique_as_count * 1.0` in the existing "Most Diverse Operators" leaderboard?** Recommended: yes, with backward-compatible fallback.

2. **Should there be a negative/penalty component for saturated AS?** Currently all proposals score down to 0 but never go negative. A penalty could be considered if we want to actively discourage OVH/Hetzner concentration.

3. **How should newly appeared AS numbers be handled?** A new AS with 1 relay would get maximum rarity. This is correct (it IS rare) but could be gamed. Consider requiring minimum relay uptime before scoring.

4. **Should this become a 19th AROI leaderboard category?** Adding "AS Diversity Champions" would be consistent with the existing 18 categories.

---

*This document proposes implementation strategies for AS diversity scoring in Allium. All proposals follow the existing threshold-based scoring pattern from `country_utils.py`. Feedback welcome before implementation begins.*
