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

Currently, Allium tracks AS-level data (relay counts, consensus weight fraction, unique contacts per AS) and has a basic `diversity_score` in `country_utils.py` that weights countries (×2.0), platforms (×1.5), and unique AS count (×1.0). However, there is **no mechanism to award bonus points to relays running on rare or underrepresented AS numbers**, nor to penalize concentration on dominant providers.

This proposal outlines several approaches to implement an **AS Diversity Score** that rewards operators who choose less common networks.

---

## Existing Infrastructure

### Data Already Available

From Onionoo API and `relays.py` processing:

| Data Point | Location | Description |
|---|---|---|
| `relay['as']` | Per-relay | AS number (e.g., `"AS16276"` for OVH) |
| `relay['as_name']` | Per-relay | Human-readable AS name |
| `sorted['as'][as_number]` | Sorted data | Per-AS aggregated data (relay count, consensus weight, bandwidth) |
| `sorted['as'][as_number]['consensus_weight_fraction']` | Sorted data | Fraction of total network consensus weight in this AS |
| `sorted['as'][as_number]['unique_contact_count']` | Sorted data | Number of distinct operators in this AS |
| `contact_data['unique_as_count']` | Per-contact | Number of unique AS numbers an operator uses |

### Existing Diversity Scoring (in `country_utils.py`)

```python
def calculate_diversity_score(countries, platforms=None, unique_as_count=None):
    diversity_score = 0.0
    diversity_score += len(countries) * 2.0       # Geographic component
    diversity_score += len(platforms) * 1.5        # Platform component
    diversity_score += unique_as_count * 1.0       # Network component (flat)
    return diversity_score
```

The current AS component is **flat** — each unique AS adds 1.0 point regardless of how rare or common that AS is on the network. This is what we want to improve.

### Existing Rarity Pattern (in `country_utils.py`)

The country rarity system uses a multi-factor weighted scoring model:
- **Relay count factor** — fewer relays in the country = higher score
- **Network percentage factor** — lower network share = higher score
- **Geopolitical factor** — conflict zones, authoritarian regimes = bonus
- **Regional factor** — underrepresented regions = bonus

This established pattern can be adapted for AS diversity scoring.

---

## Proposal A: Inverse Frequency Score (Recommended)

### Concept

Award points inversely proportional to how common an AS is on the network. A relay on an AS with 1 relay gets maximum points; a relay on an AS with 2,000 relays gets minimum points.

### Algorithm

```python
def calculate_as_rarity_score(as_number, sorted_as_data, total_relays):
    """
    Calculate rarity score for a given AS number.
    
    Score = log2(total_relays / as_relay_count)
    
    Examples (assuming ~7,000 total relays):
      - AS with 1 relay:     log2(7000/1)   = 12.77 points
      - AS with 5 relays:    log2(7000/5)   = 10.45 points
      - AS with 50 relays:   log2(7000/50)  =  7.13 points
      - AS with 500 relays:  log2(7000/500) =  3.81 points
      - AS with 2000 relays: log2(7000/2000)=  1.81 points
    """
    import math
    
    as_data = sorted_as_data.get(as_number, {})
    as_relay_count = len(as_data.get('relays', []))
    
    if as_relay_count == 0 or total_relays == 0:
        return 0.0
    
    return math.log2(total_relays / as_relay_count)
```

### Tier Classification

| Tier | Score Range | Description | Example |
|------|------------|-------------|---------|
| Legendary | >= 12 | Unique or nearly unique AS | 1-2 relays in this AS |
| Epic | >= 10 | Very rare AS | 3-7 relays |
| Rare | >= 7 | Uncommon AS | 8-64 relays |
| Common | >= 4 | Moderate presence | 65-500 relays |
| Saturated | < 4 | Heavily used AS | 500+ relays (OVH, Hetzner, etc.) |

### Integration Points

1. **Per-relay display** (`relay-info.html`): Show AS rarity tier badge next to AS name
2. **AROI Leaderboards** (`aroileaders.py`): New "AS Diversity Champions" category ranking operators by average AS rarity across their relays
3. **Intelligence Engine** (`intelligence_engine.py`): Add AS rarity to contact intelligence (Layer 14)
4. **Existing diversity_score** (`country_utils.py`): Replace flat `unique_as_count * 1.0` with sum of per-AS rarity scores
5. **Network Health Dashboard**: Show AS concentration risk metrics

### Implementation Changes

**File: `allium/lib/country_utils.py`** — Add new functions:

```python
import math

def calculate_as_rarity_score(as_relay_count, total_relays):
    """Calculate log-based rarity score for an AS."""
    if as_relay_count <= 0 or total_relays <= 0:
        return 0.0
    return math.log2(total_relays / as_relay_count)

def assign_as_rarity_tier(rarity_score):
    """Assign tier classification based on AS rarity score."""
    if rarity_score >= 12:  return 'legendary'
    elif rarity_score >= 10: return 'epic'
    elif rarity_score >= 7:  return 'rare'
    elif rarity_score >= 4:  return 'common'
    else:                    return 'saturated'

def calculate_operator_as_diversity_score(operator_relays, sorted_as_data, total_relays):
    """
    Calculate AS diversity score for an operator.
    Sum of rarity scores across all unique AS numbers used by the operator.
    """
    unique_as_numbers = set(
        relay.get('as', '') for relay in operator_relays if relay.get('as')
    )
    
    total_score = 0.0
    for as_number in unique_as_numbers:
        as_data = sorted_as_data.get(as_number, {})
        as_relay_count = len(as_data.get('relays', []))
        total_score += calculate_as_rarity_score(as_relay_count, total_relays)
    
    return total_score
```

**File: `allium/lib/country_utils.py`** — Modify `calculate_diversity_score`:

```python
def calculate_diversity_score(countries, platforms=None, unique_as_count=None,
                              as_rarity_score=None):
    """Enhanced diversity score with AS rarity weighting."""
    diversity_score = 0.0
    
    if countries:
        diversity_score += len(countries) * 2.0
    if platforms:
        diversity_score += len(platforms) * 1.5
    
    # Use AS rarity score if available, otherwise fall back to flat count
    if as_rarity_score is not None:
        diversity_score += as_rarity_score
    elif unique_as_count:
        diversity_score += unique_as_count * 1.0
    
    return diversity_score
```

**File: `allium/lib/aroileaders.py`** — New leaderboard category:

```python
# 19. AS Diversity Champions - Operators with highest AS rarity scores
leaderboards['as_diversity'] = sorted(
    aroi_operators.items(),
    key=lambda x: x[1]['as_diversity_score'],
    reverse=True
)[:50]
```

### Pros

- Mathematically elegant — logarithmic scaling provides smooth differentiation
- Self-adjusting — automatically adapts as AS distribution changes
- Follows established rarity pattern from country scoring
- Low computational cost — single pass through AS data

### Cons

- Pure relay count doesn't capture consensus weight concentration
- A "rare" AS could still have high consensus weight if it hosts high-bandwidth relays
- Log scale may compress differences at the extreme ends

---

## Proposal B: Consensus Weight-Based Inverse Score

### Concept

Instead of using relay counts, use the **consensus weight fraction** of each AS. This captures actual network influence more accurately — an AS with 10 relays holding 15% of consensus weight is more of a risk than one with 100 relays holding 0.5%.

### Algorithm

```python
def calculate_as_diversity_score_cw(as_number, sorted_as_data):
    """
    Score based on inverse of consensus weight fraction.
    
    Score = -log10(cw_fraction) * scaling_factor
    
    Examples:
      - AS with 0.001% CW: -log10(0.00001) * 2 = 10.0 points
      - AS with 0.1% CW:   -log10(0.001)   * 2 =  6.0 points
      - AS with 1% CW:     -log10(0.01)    * 2 =  4.0 points
      - AS with 5% CW:     -log10(0.05)    * 2 =  2.6 points
      - AS with 15% CW:    -log10(0.15)    * 2 =  1.6 points
    """
    import math
    
    as_data = sorted_as_data.get(as_number, {})
    cw_fraction = as_data.get('consensus_weight_fraction', 0)
    
    if cw_fraction <= 0:
        return 0.0
    
    # Cap minimum fraction to avoid infinite scores
    cw_fraction = max(cw_fraction, 1e-8)
    
    SCALING_FACTOR = 2.0
    return -math.log10(cw_fraction) * SCALING_FACTOR
```

### Pros

- Captures actual network influence rather than just relay count
- Better security metric — consensus weight determines path selection probability
- An AS with few but high-bandwidth relays correctly gets lower diversity score

### Cons

- More volatile — consensus weight fluctuates with relay bandwidth changes
- Harder to explain to operators ("why did my score change?")
- Newly joined relays with low consensus weight could inflate scores temporarily

---

## Proposal C: Multi-Factor Weighted Score (Comprehensive)

### Concept

Combine multiple factors into a weighted score, similar to the existing country rarity system. This provides the most nuanced assessment.

### Algorithm

```python
def calculate_as_diversity_multifactor(as_number, sorted_as_data, total_relays):
    """
    Multi-factor AS diversity score.
    
    Factors:
      1. Relay count factor (weight: 4) — fewer relays = higher score
      2. Consensus weight factor (weight: 3) — lower CW fraction = higher score
      3. Operator diversity factor (weight: 2) — more unique operators = higher score
      4. Geographic factor (weight: 1) — AS in underrepresented country = bonus
    """
    as_data = sorted_as_data.get(as_number, {})
    as_relay_count = len(as_data.get('relays', []))
    cw_fraction = as_data.get('consensus_weight_fraction', 0)
    unique_contacts = as_data.get('unique_contact_count', 0)
    
    # Factor 1: Relay count (0-6 points)
    if as_relay_count == 0:
        relay_factor = 0
    elif as_relay_count <= 2:
        relay_factor = 6
    elif as_relay_count <= 5:
        relay_factor = 5
    elif as_relay_count <= 10:
        relay_factor = 4
    elif as_relay_count <= 50:
        relay_factor = 3
    elif as_relay_count <= 200:
        relay_factor = 2
    elif as_relay_count <= 500:
        relay_factor = 1
    else:
        relay_factor = 0
    
    # Factor 2: Consensus weight (0-6 points)
    cw_percentage = cw_fraction * 100
    if cw_percentage < 0.01:
        cw_factor = 6
    elif cw_percentage < 0.05:
        cw_factor = 5
    elif cw_percentage < 0.1:
        cw_factor = 4
    elif cw_percentage < 0.5:
        cw_factor = 3
    elif cw_percentage < 1.0:
        cw_factor = 2
    elif cw_percentage < 5.0:
        cw_factor = 1
    else:
        cw_factor = 0  # Major AS (OVH, Hetzner)
    
    # Factor 3: Operator diversity (0-4 points)
    # Single-operator AS = more risk, but also means the operator
    # has sole presence = more diversity contribution
    if unique_contacts == 1:
        operator_factor = 4  # Sole operator in AS — unique contribution
    elif unique_contacts <= 3:
        operator_factor = 3
    elif unique_contacts <= 10:
        operator_factor = 2
    elif unique_contacts <= 50:
        operator_factor = 1
    else:
        operator_factor = 0  # Heavily shared AS
    
    # Factor 4: Network percentage (0-6 points) — reuse existing pattern
    if total_relays > 0:
        percentage = (as_relay_count / total_relays) * 100
        if percentage < 0.02:
            network_factor = 6
        elif percentage < 0.05:
            network_factor = 4
        elif percentage < 0.1:
            network_factor = 3
        elif percentage < 0.5:
            network_factor = 2
        elif percentage < 1.0:
            network_factor = 1
        else:
            network_factor = 0
    else:
        network_factor = 0
    
    # Weighted combination
    score = (
        (relay_factor * 4) +       # Relay count: weight 4
        (cw_factor * 3) +          # Consensus weight: weight 3
        (operator_factor * 2) +    # Operator diversity: weight 2
        (network_factor * 1)       # Network percentage: weight 1
    )
    
    return score
```

### Tier Classification

| Tier | Score Range | Description |
|------|------------|-------------|
| Legendary | >= 80 | Extremely rare AS — almost no other relays |
| Epic | >= 60 | Very rare AS — minimal network presence |
| Rare | >= 40 | Uncommon AS — below-average relay count |
| Emerging | >= 20 | Moderately used AS |
| Common | >= 10 | Well-populated AS |
| Saturated | < 10 | Major hosting provider (OVH, Hetzner, DigitalOcean) |

### Pros

- Most comprehensive assessment
- Follows proven pattern from `country_utils.py` rarity scoring
- Each factor is independently tunable
- Captures both relay concentration and consensus weight

### Cons

- Most complex to implement and maintain
- Multiple factors may be partially redundant (relay count correlates with CW fraction)
- Harder to explain to operators

---

## Proposal D: Percentile Rank Score (Simple & Effective)

### Concept

Rank all AS numbers by their relay count, then assign a percentile-based score. This is the simplest approach and is self-normalizing.

### Algorithm

```python
def calculate_as_percentile_score(as_number, sorted_as_data):
    """
    Score = percentile rank of AS (inverted, so rare AS gets higher score).
    
    If there are 1,000 unique AS numbers:
      - Rarest AS (rank 1):     score = 100.0
      - Median AS (rank 500):   score = 50.0
      - Most common AS (rank 1000): score = 0.0
    """
    # Collect all AS relay counts
    as_relay_counts = {}
    for as_num, as_data in sorted_as_data.items():
        as_relay_counts[as_num] = len(as_data.get('relays', []))
    
    if not as_relay_counts or as_number not in as_relay_counts:
        return 0.0
    
    # Sort AS numbers by relay count (ascending = rare first)
    sorted_as = sorted(as_relay_counts.items(), key=lambda x: x[1])
    total_as = len(sorted_as)
    
    # Find rank of this AS
    for rank, (as_num, _) in enumerate(sorted_as):
        if as_num == as_number:
            # Invert: rank 0 (rarest) gets 100, last rank gets 0
            return ((total_as - rank - 1) / (total_as - 1)) * 100 if total_as > 1 else 50.0
    
    return 0.0
```

### Optimized Implementation

For batch processing (to avoid re-sorting per relay):

```python
def precompute_as_percentile_scores(sorted_as_data):
    """Pre-compute percentile scores for all AS numbers in one pass."""
    as_relay_counts = {
        as_num: len(as_data.get('relays', []))
        for as_num, as_data in sorted_as_data.items()
    }
    
    sorted_as = sorted(as_relay_counts.items(), key=lambda x: x[1])
    total_as = len(sorted_as)
    
    scores = {}
    for rank, (as_num, _) in enumerate(sorted_as):
        scores[as_num] = ((total_as - rank - 1) / (total_as - 1)) * 100 if total_as > 1 else 50.0
    
    return scores
```

### Pros

- Simplest to implement and understand
- Self-normalizing — always produces 0-100 range
- No tuning parameters needed
- Easy to explain to operators: "Your AS is in the top X% rarest"

### Cons

- Treats all gaps equally — the difference between rank 1 and rank 2 may be huge in absolute terms
- Doesn't capture consensus weight
- Equal-relay-count AS numbers get different scores based on sort order

---

## Comparison Matrix

| Criterion | Proposal A (Log) | Proposal B (CW) | Proposal C (Multi) | Proposal D (Percentile) |
|---|---|---|---|---|
| **Complexity** | Low | Low | High | Very Low |
| **Accuracy** | Good | Better for security | Best | Fair |
| **Performance** | O(1) per relay | O(1) per relay | O(1) per relay | O(n log n) precompute, O(1) per relay |
| **Explainability** | Good | Moderate | Moderate | Excellent |
| **Self-adjusting** | Yes | Yes | Yes | Yes |
| **Captures CW** | No | Yes | Yes | No |
| **Follows existing patterns** | Partially | No | Yes (mirrors country rarity) | No |
| **Implementation effort** | ~2 hours | ~2 hours | ~4 hours | ~1 hour |

---

## Recommendation

**Proposal A (Inverse Frequency Score)** is recommended as the primary implementation for the following reasons:

1. **Best balance of simplicity and accuracy** — logarithmic scaling provides meaningful differentiation without over-engineering.
2. **Low implementation risk** — simple math, easy to test, easy to explain.
3. **Extensible** — can later be enhanced with CW weighting (evolve toward Proposal C) if needed.
4. **Consistent with existing patterns** — the rarity tier system (`legendary`/`epic`/`rare`/`common`) already exists for countries.

**Proposal C (Multi-Factor)** is recommended as a future enhancement once Proposal A is validated in production. It provides the most comprehensive view and mirrors the proven `country_utils.py` weighted scoring system.

---

## Integration Roadmap

### Phase 1: Core Scoring (Proposal A)

1. Add `calculate_as_rarity_score()` and `assign_as_rarity_tier()` to `country_utils.py`
2. Pre-compute AS rarity scores in `relays.py` during `_categorize()` (single pass over sorted AS data)
3. Store `as_rarity_score` and `as_rarity_tier` on each relay for template access
4. Display AS rarity tier badge on `relay-info.html` pages

### Phase 2: Operator Scoring

5. Add `calculate_operator_as_diversity_score()` to `country_utils.py`
6. Integrate into `aroileaders.py` — compute operator-level AS diversity score
7. Enhance `calculate_diversity_score()` to use rarity-weighted AS component
8. Add new AROI leaderboard category: "AS Diversity Champions"

### Phase 3: Intelligence & Dashboard

9. Add AS rarity analysis to Intelligence Engine Layer 10 (Infrastructure Dependency)
10. Add AS concentration risk indicator to Network Health Dashboard
11. Enhance contact intelligence (Layer 14) with per-operator AS rarity assessment

### Phase 4: Enhancement to Multi-Factor (Proposal C)

12. Evolve scoring to include consensus weight factor
13. Add operator diversity factor
14. Add network percentage factor
15. Tune weights based on real-world data

---

## Example Output

### Relay Info Page

```
AS Number: AS205100 (Flokinet Ltd)
AS Rarity:  Epic (score: 10.8)
           Only 5 relays on this AS network-wide
```

### AROI Leaderboard — AS Diversity Champions

| Rank | Operator | AS Diversity Score | Unique AS | Avg Rarity | Top Rare AS |
|------|----------|--------------------|-----------|------------|-------------|
| 1 | diverse-ops.org | 87.3 | 12 | Epic | AS205100, AS60729 |
| 2 | global-tor.net | 72.1 | 8 | Rare | AS131284, AS9009 |
| 3 | privacy-relay.io | 65.4 | 15 | Common | AS16276 (OVH) |

### Intelligence Engine — Contact Page

```
Network Diversity: Great, 8 networks
AS Rarity Assessment: Above Average — 5 of 8 AS numbers are rare or better
  - AS205100 (Flokinet): Epic (10.8 pts)
  - AS60729 (Leaseweb DE): Rare (7.2 pts)
  - AS24940 (Hetzner): Common (3.1 pts)
```

---

## Open Questions

1. **Should the AS diversity score affect the existing `diversity_score` used in the "Most Diverse Operators" leaderboard?** Proposal A recommends yes — replace the flat `unique_as_count * 1.0` with the sum of rarity scores.

2. **Should we have a negative/penalty component for saturated AS?** Currently all proposals score down to 0 but never go negative. A penalty would actively discourage further relay deployment on already-saturated AS numbers.

3. **How should newly appeared AS numbers be handled?** A brand-new AS with 1 relay would get maximum rarity score. This is technically correct (it IS rare) but could be gamed. Consider requiring minimum relay uptime before scoring.

4. **Should consensus weight be used instead of relay count?** Proposal B argues yes. The recommended approach is to start with relay count (Proposal A) and evolve to multi-factor (Proposal C) which includes both.

---

*This document proposes implementation strategies for AS diversity scoring in Allium. Feedback and discussion are welcome before implementation begins.*
