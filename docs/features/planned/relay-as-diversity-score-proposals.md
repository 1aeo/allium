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

## Integration Points

Both options integrate the same way. The only difference is which function gets called.

### 1. `country_utils.py` — Add AS rarity functions

```python
# Option 1: both functions
# Option 2: only calculate_as_cw_factor

def calculate_as_cw_factor(as_cw_fraction):
    ...

def calculate_as_contact_factor(unique_contact_count):  # Option 1 only
    ...

def calculate_as_rarity_score(...):
    ...

def assign_as_rarity_tier(rarity_score):
    ...
```

### 2. `relays.py` — Pre-compute AS rarity during `_categorize()`

After `sorted['as']` is built, compute rarity score for each AS in one pass:

```python
# In _categorize(), after AS data is assembled:
for as_number, as_data in self.json['sorted']['as'].items():
    as_cw = as_data.get('consensus_weight_fraction', 0)
    unique_contacts = as_data.get('unique_contact_count', 0)
    
    # Option 1:
    as_data['as_rarity_score'] = calculate_as_rarity_score(as_cw, unique_contacts)
    # Option 2:
    # as_data['as_rarity_score'] = calculate_as_rarity_score(as_cw)
    
    as_data['as_rarity_tier'] = assign_as_rarity_tier(as_data['as_rarity_score'])
```

### 3. `aroileaders.py` — Operator-level scoring + new leaderboard

```python
def calculate_operator_as_diversity_score(operator_relays, sorted_as_data):
    """Sum of AS rarity scores across each unique AS the operator uses."""
    seen_as = set()
    total_score = 0
    
    for relay in operator_relays:
        as_number = relay.get('as', '')
        if not as_number or as_number in seen_as:
            continue
        seen_as.add(as_number)
        
        as_data = sorted_as_data.get(as_number, {})
        total_score += as_data.get('as_rarity_score', 0)
    
    return total_score

# New leaderboard: AS Diversity Champions
leaderboards['as_diversity'] = sorted(
    aroi_operators.items(),
    key=lambda x: x[1]['as_diversity_score'],
    reverse=True
)[:50]
```

### 4. `calculate_diversity_score()` — Replace flat AS component

```python
# Replace: unique_as_count * 1.0
# With:    sum of rarity scores per unique AS
if as_rarity_score is not None:
    diversity_score += as_rarity_score
elif unique_as_count:
    diversity_score += unique_as_count * 1.0  # backward-compatible fallback
```

### 5. `intelligence_engine.py` — Layer 14 contact intelligence

```python
# In _layer14_contact_intelligence():
rare_as_count = sum(
    1 for as_num in unique_as_set
    if sorted_as_data.get(as_num, {}).get('as_rarity_tier') in ('legendary', 'epic', 'rare')
)
```

### 6. Templates — Display AS rarity badge

```html
<!-- relay-info.html -->
<td>{{ relay.as_name }}
  <span class="badge badge-{{ relay.as_rarity_tier }}">{{ relay.as_rarity_tier }}</span>
</td>
```

---

## Open Questions

1. **Should the AS diversity score replace the flat `unique_as_count * 1.0` in the existing "Most Diverse Operators" leaderboard?** Recommended: yes, with backward-compatible fallback.

2. **Should this become a 19th AROI leaderboard category?** Adding "AS Diversity Champions" would be consistent with the existing 18 categories.

3. **How should newly appeared AS numbers be handled?** A brand-new AS with 1 relay would get maximum rarity. This is correct (it IS rare) but could be gamed. Consider requiring minimum relay uptime before scoring.

4. **Should the contact factor weight be higher or lower than CW?** Currently both are weighted at 5. If CW is considered more important, it could be weighted at 6 vs contact at 4.

---

*This document proposes two implementation options for AS diversity scoring in Allium. Both follow the existing threshold-based scoring pattern from `country_utils.py`. Feedback welcome before implementation begins.*
