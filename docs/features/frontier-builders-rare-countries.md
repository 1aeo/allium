# Frontier Builders: Rare Country Calculation System

## Overview

The **Frontier Builders** leaderboard recognizes Tor relay operators who contribute to network diversity by operating relays in rare, underrepresented, or strategically important countries. This document explains the sophisticated 4-step weighted scoring algorithm used to determine which countries qualify as "rare" for the purposes of this leaderboard.

## Algorithm Overview

Countries are evaluated using a **4-factor weighted formula** implemented in [`allium/lib/country_utils.py`](../../allium/lib/country_utils.py):

```python
# Lines 395-401 in allium/lib/country_utils.py
rarity_score = (
    (relay_count_factor * 4) +           # Weight: 4x (highest priority)
    (network_percentage_factor * 3) +    # Weight: 3x 
    (geopolitical_factor * 2) +          # Weight: 2x
    (regional_factor * 1)                # Weight: 1x (lowest priority)
)

# A country becomes "rare" if rarity_score >= 6 (default minimum score)
```

**Maximum Possible Score**: 6×4 + 6×3 + 3×2 + 2×1 = **44 points**

---

## Step 1: Relay Count Factor (4x Weight)

**Purpose**: Prioritize countries with very few active Tor relays

**Implementation**: [`lines 262-276`](../../allium/lib/country_utils.py#L262-L276) in `allium/lib/country_utils.py`

```python
def calculate_relay_count_factor(country_relay_count):
    if country_relay_count == 0:
        return 0
    return max(7 - country_relay_count, 0)
```

### Scoring Table

| Relay Count | Points | Weight | Total Contribution |
|-------------|--------|--------|--------------------|
| 1 relay     | 6      | ×4     | **24 points**      |
| 2 relays    | 5      | ×4     | **20 points**      |
| 3 relays    | 4      | ×4     | **16 points**      |
| 4 relays    | 3      | ×4     | **12 points**      |
| 5 relays    | 2      | ×4     | **8 points**       |
| 6 relays    | 1      | ×4     | **4 points**       |
| 7+ relays   | 0      | ×4     | **0 points**       |

**Rationale**: Countries with fewer than 7 relays are considered underrepresented. This dynamic factor ensures that popular countries (US, DE, FR) with hundreds of relays receive 0 points, while countries with just 1-6 relays get significant scoring boosts.

---

## Step 2: Network Percentage Factor (3x Weight)

**Purpose**: Identify countries representing tiny fractions of the total Tor network

**Implementation**: [`lines 280-296`](../../allium/lib/country_utils.py#L280-L296) in `allium/lib/country_utils.py`

```python
def calculate_network_percentage_factor(country_relays, total_network_relays):
    if total_network_relays == 0:
        return 0
    
    percentage = (country_relays / total_network_relays) * 100
    
    if percentage < 0.05:    return 6  # Ultra-rare (<0.05%)
    elif percentage < 0.1:   return 4  # Very rare (0.05-0.1%)
    elif percentage < 0.2:   return 2  # Rare (0.1-0.2%)
    else:                    return 0  # Common (>0.2%)
```

### Scoring Table

| Network Percentage | Classification | Points | Weight | Total Contribution |
|-------------------|----------------|--------|--------|--------------------|
| < 0.05%           | Ultra-rare     | 6      | ×3     | **18 points**      |
| 0.05% - 0.1%      | Very rare      | 4      | ×3     | **12 points**      |
| 0.1% - 0.2%       | Rare           | 2      | ×3     | **6 points**       |
| > 0.2%            | Common         | 0      | ×3     | **0 points**       |

**Rationale**: Countries representing more than 0.2% of the network (like US ~15%, DE ~12%, FR ~8%) are considered common and receive 0 points. Countries with minimal network presence get higher scores.

---

## Step 3: Geopolitical Factor (2x Weight)

**Purpose**: Recognize strategic importance of operating relays in geopolitically significant countries

**Implementation**: [`lines 301-318`](../../allium/lib/country_utils.py#L301-L318) in `allium/lib/country_utils.py`

### Category A: Conflict Zones (3 points × 2 = 6 points)

**Definition**: [`lines 39-43`](../../allium/lib/country_utils.py#L39-L43) - Active conflicts, post-conflict zones

| Code | Country | Flag |
|------|---------|------|
| `sy` | Syria | 🇸🇾 |
| `ye` | Yemen | 🇾🇪 |
| `af` | Afghanistan | 🇦🇫 |
| `mm` | Myanmar | 🇲🇲 |
| `sd` | Sudan | 🇸🇩 |
| `so` | Somalia | 🇸🇴 |
| `ly` | Libya | 🇱🇾 |
| `iq` | Iraq | 🇮🇶 |
| `ml` | Mali | 🇲🇱 |
| `cf` | Central African Republic | 🇨🇫 |
| `ss` | South Sudan | 🇸🇸 |
| `td` | Chad | 🇹🇩 |
| `ni` | Nicaragua | 🇳🇮 |
| `ht` | Haiti | 🇭🇹 |
| `pk` | Pakistan | 🇵🇰 |
| `ng` | Nigeria | 🇳🇬 |

### Category B: Authoritarian Regimes (3 points × 2 = 6 points)

**Definition**: [`lines 46-49`](../../allium/lib/country_utils.py#L46-L49) - Freedom House "Not Free" countries

| Code | Country | Flag |
|------|---------|------|
| `cn` | China | 🇨🇳 |
| `ir` | Iran | 🇮🇷 |
| `kp` | North Korea | 🇰🇵 |
| `sa` | Saudi Arabia | 🇸🇦 |
| `by` | Belarus | 🇧🇾 |
| `tm` | Turkmenistan | 🇹🇲 |
| `uz` | Uzbekistan | 🇺🇿 |
| `la` | Laos | 🇱🇦 |
| `vn` | Vietnam | 🇻🇳 |
| `cu` | Cuba | 🇨🇺 |
| `er` | Eritrea | 🇪🇷 |
| `az` | Azerbaijan | 🇦🇿 |
| `bh` | Bahrain | 🇧🇭 |
| `cm` | Cameroon | 🇨🇲 |
| `dj` | Djibouti | 🇩🇯 |
| `gq` | Equatorial Guinea | 🇬🇶 |
| `tj` | Tajikistan | 🇹🇯 |
| `eg` | Egypt | 🇪🇬 |

### Category C: Island Nations (2 points × 2 = 4 points)

**Definition**: [`lines 52-56`](../../allium/lib/country_utils.py#L52-L56) - Strategic geographic positions

| Code | Country | Flag |
|------|---------|------|
| `mt` | Malta | 🇲🇹 |
| `cy` | Cyprus | 🇨🇾 |
| `is` | Iceland | 🇮🇸 |
| `mv` | Maldives | 🇲🇻 |
| `fj` | Fiji | 🇫🇯 |
| `mg` | Madagascar | 🇲🇬 |
| `mu` | Mauritius | 🇲🇺 |
| `sc` | Seychelles | 🇸🇨 |
| `bb` | Barbados | 🇧🇧 |
| `jm` | Jamaica | 🇯🇲 |
| `tt` | Trinidad and Tobago | 🇹🇹 |
| `bh` | Bahrain | 🇧🇭 |
| `bn` | Brunei | 🇧🇳 |
| `ki` | Kiribati | 🇰🇮 |
| `tv` | Tuvalu | 🇹🇻 |
| `to` | Tonga | 🇹🇴 |
| `ws` | Samoa | 🇼🇸 |
| `vu` | Vanuatu | 🇻🇺 |
| `sb` | Solomon Islands | 🇸🇧 |
| `pw` | Palau | 🇵🇼 |
| `fm` | Micronesia | 🇫🇲 |
| `mh` | Marshall Islands | 🇲🇭 |
| `nr` | Nauru | 🇳🇷 |
| `ag` | Antigua and Barbuda | 🇦🇬 |
| `bs` | Bahamas | 🇧🇸 |
| `dm` | Dominica | 🇩🇲 |
| `gd` | Grenada | 🇬🇩 |
| `kn` | Saint Kitts and Nevis | 🇰🇳 |
| `lc` | Saint Lucia | 🇱🇨 |
| `vc` | Saint Vincent and the Grenadines | 🇻🇨 |
| `cv` | Cape Verde | 🇨🇻 |

### Category D: Landlocked Developing (2 points × 2 = 4 points)

**Definition**: [`lines 59-63`](../../allium/lib/country_utils.py#L59-L63) - UN LDC + landlocked countries

| Code | Country | Flag |
|------|---------|------|
| `af` | Afghanistan | 🇦🇫 |
| `bf` | Burkina Faso | 🇧🇫 |
| `bi` | Burundi | 🇧🇮 |
| `cf` | Central African Republic | 🇨🇫 |
| `td` | Chad | 🇹🇩 |
| `kz` | Kazakhstan | 🇰🇿 |
| `kg` | Kyrgyzstan | 🇰🇬 |
| `tj` | Tajikistan | 🇹🇯 |
| `tm` | Turkmenistan | 🇹🇲 |
| `uz` | Uzbekistan | 🇺🇿 |
| `bt` | Bhutan | 🇧🇹 |
| `np` | Nepal | 🇳🇵 |
| `py` | Paraguay | 🇵🇾 |
| `bo` | Bolivia | 🇧🇴 |
| `ml` | Mali | 🇲🇱 |
| `ne` | Niger | 🇳🇪 |
| `rw` | Rwanda | 🇷🇼 |
| `ug` | Uganda | 🇺🇬 |
| `zm` | Zambia | 🇿🇲 |
| `zw` | Zimbabwe | 🇿🇼 |
| `mw` | Malawi | 🇲🇼 |
| `ls` | Lesotho | 🇱🇸 |
| `sz` | Eswatini | 🇸🇿 |
| `aw` | Aruba | 🇦🇼 |

### Category E: General Developing (1 point × 2 = 2 points)

**Definition**: [`lines 66-78`](../../allium/lib/country_utils.py#L66-L78) - World Bank Lower/Lower-middle income

#### Africa
| Code | Country | Flag |
|------|---------|------|
| `dz` | Algeria | 🇩🇿 |
| `ao` | Angola | 🇦🇴 |
| `bj` | Benin | 🇧🇯 |
| `bw` | Botswana | 🇧🇼 |
| `cm` | Cameroon | 🇨🇲 |
| `cg` | Republic of the Congo | 🇨🇬 |
| `ci` | Côte d'Ivoire | 🇨🇮 |
| `eg` | Egypt | 🇪🇬 |
| `et` | Ethiopia | 🇪🇹 |
| `ga` | Gabon | 🇬🇦 |
| `gh` | Ghana | 🇬🇭 |
| `gn` | Guinea | 🇬🇳 |
| `ke` | Kenya | 🇰🇪 |
| `lr` | Liberia | 🇱🇷 |
| `ly` | Libya | 🇱🇾 |
| `ma` | Morocco | 🇲🇦 |
| `mz` | Mozambique | 🇲🇿 |
| `na` | Namibia | 🇳🇦 |
| `ng` | Nigeria | 🇳🇬 |
| `sn` | Senegal | 🇸🇳 |
| `sl` | Sierra Leone | 🇸🇱 |
| `tz` | Tanzania | 🇹🇿 |
| `tn` | Tunisia | 🇹🇳 |
| `za` | South Africa | 🇿🇦 |
| `zm` | Zambia | 🇿🇲 |
| `zw` | Zimbabwe | 🇿🇼 |

#### Asia
| Code | Country | Flag |
|------|---------|------|
| `bd` | Bangladesh | 🇧🇩 |
| `in` | India | 🇮🇳 |
| `id` | Indonesia | 🇮🇩 |
| `lk` | Sri Lanka | 🇱🇰 |
| `mn` | Mongolia | 🇲🇳 |
| `pk` | Pakistan | 🇵🇰 |
| `ph` | Philippines | 🇵🇭 |
| `th` | Thailand | 🇹🇭 |
| `vn` | Vietnam | 🇻🇳 |

#### Latin America
| Code | Country | Flag |
|------|---------|------|
| `ar` | Argentina | 🇦🇷 |
| `br` | Brazil | 🇧🇷 |
| `cl` | Chile | 🇨🇱 |
| `co` | Colombia | 🇨🇴 |
| `ec` | Ecuador | 🇪🇨 |
| `pe` | Peru | 🇵🇪 |
| `uy` | Uruguay | 🇺🇾 |
| `ve` | Venezuela | 🇻🇪 |
| `mx` | Mexico | 🇲🇽 |
| `gt` | Guatemala | 🇬🇹 |
| `hn` | Honduras | 🇭🇳 |
| `sv` | El Salvador | 🇸🇻 |
| `cr` | Costa Rica | 🇨🇷 |
| `pa` | Panama | 🇵🇦 |
| `do` | Dominican Republic | 🇩🇴 |
| `jm` | Jamaica | 🇯🇲 |

#### Eastern Europe
| Code | Country | Flag |
|------|---------|------|
| `al` | Albania | 🇦🇱 |
| `ba` | Bosnia and Herzegovina | 🇧🇦 |
| `mk` | North Macedonia | 🇲🇰 |
| `md` | Moldova | 🇲🇩 |
| `me` | Montenegro | 🇲🇪 |

---

## Step 4: Regional Factor (1x Weight)

**Purpose**: Boost countries from regions historically underrepresented in the Tor network

**Implementation**: [`lines 326-340`](../../allium/lib/country_utils.py#L326-L340) in `allium/lib/country_utils.py`

### Category A: Underrepresented Regions (2 points × 1 = 2 points)

**Definition**: [`lines 84-99`](../../allium/lib/country_utils.py#L84-L99) - Regions with typically low relay counts

#### Africa (All 54 countries)
| Code | Country | Flag |
|------|---------|------|
| `dz` | Algeria | 🇩🇿 |
| `ao` | Angola | 🇦🇴 |
| `bj` | Benin | 🇧🇯 |
| `bw` | Botswana | 🇧🇼 |
| `bf` | Burkina Faso | 🇧🇫 |
| `bi` | Burundi | 🇧🇮 |
| `cm` | Cameroon | 🇨🇲 |
| `cv` | Cape Verde | 🇨🇻 |
| `cf` | Central African Republic | 🇨🇫 |
| `td` | Chad | 🇹🇩 |
| `km` | Comoros | 🇰🇲 |
| `cg` | Republic of the Congo | 🇨🇬 |
| `ci` | Côte d'Ivoire | 🇨🇮 |
| `dj` | Djibouti | 🇩🇯 |
| `eg` | Egypt | 🇪🇬 |
| `gq` | Equatorial Guinea | 🇬🇶 |
| `er` | Eritrea | 🇪🇷 |
| `et` | Ethiopia | 🇪🇹 |
| `ga` | Gabon | 🇬🇦 |
| `gm` | Gambia | 🇬🇲 |
| `gh` | Ghana | 🇬🇭 |
| `gn` | Guinea | 🇬🇳 |
| `gw` | Guinea-Bissau | 🇬🇼 |
| `ke` | Kenya | 🇰🇪 |
| `ls` | Lesotho | 🇱🇸 |
| `lr` | Liberia | 🇱🇷 |
| `ly` | Libya | 🇱🇾 |
| `mg` | Madagascar | 🇲🇬 |
| `mw` | Malawi | 🇲🇼 |
| `ml` | Mali | 🇲🇱 |
| `mr` | Mauritania | 🇲🇷 |
| `mu` | Mauritius | 🇲🇺 |
| `ma` | Morocco | 🇲🇦 |
| `mz` | Mozambique | 🇲🇿 |
| `na` | Namibia | 🇳🇦 |
| `ne` | Niger | 🇳🇪 |
| `ng` | Nigeria | 🇳🇬 |
| `rw` | Rwanda | 🇷🇼 |
| `st` | São Tomé and Príncipe | 🇸🇹 |
| `sn` | Senegal | 🇸🇳 |
| `sc` | Seychelles | 🇸🇨 |
| `sl` | Sierra Leone | 🇸🇱 |
| `so` | Somalia | 🇸🇴 |
| `za` | South Africa | 🇿🇦 |
| `ss` | South Sudan | 🇸🇸 |
| `sd` | Sudan | 🇸🇩 |
| `sz` | Eswatini | 🇸🇿 |
| `tz` | Tanzania | 🇹🇿 |
| `tg` | Togo | 🇹🇬 |
| `tn` | Tunisia | 🇹🇳 |
| `ug` | Uganda | 🇺🇬 |
| `zm` | Zambia | 🇿🇲 |
| `zw` | Zimbabwe | 🇿🇼 |

#### Central Asia (5 countries)
| Code | Country | Flag |
|------|---------|------|
| `kz` | Kazakhstan | 🇰🇿 |
| `kg` | Kyrgyzstan | 🇰🇬 |
| `tj` | Tajikistan | 🇹🇯 |
| `tm` | Turkmenistan | 🇹🇲 |
| `uz` | Uzbekistan | 🇺🇿 |

#### Pacific Islands (12 countries)
| Code | Country | Flag |
|------|---------|------|
| `fj` | Fiji | 🇫🇯 |
| `ki` | Kiribati | 🇰🇮 |
| `mh` | Marshall Islands | 🇲🇭 |
| `fm` | Micronesia | 🇫🇲 |
| `nr` | Nauru | 🇳🇷 |
| `pw` | Palau | 🇵🇼 |
| `pg` | Papua New Guinea | 🇵🇬 |
| `ws` | Samoa | 🇼🇸 |
| `sb` | Solomon Islands | 🇸🇧 |
| `to` | Tonga | 🇹🇴 |
| `tv` | Tuvalu | 🇹🇻 |
| `vu` | Vanuatu | 🇻🇺 |

### Category B: Emerging Regions (1 point × 1 = 1 point)

**Definition**: [`lines 101-115`](../../allium/lib/country_utils.py#L101-L115) - Growing but still underrepresented

#### Caribbean (15 countries)
| Code | Country | Flag |
|------|---------|------|
| `ag` | Antigua and Barbuda | 🇦🇬 |
| `bs` | Bahamas | 🇧🇸 |
| `bb` | Barbados | 🇧🇧 |
| `bz` | Belize | 🇧🇿 |
| `dm` | Dominica | 🇩🇲 |
| `do` | Dominican Republic | 🇩🇴 |
| `gd` | Grenada | 🇬🇩 |
| `gy` | Guyana | 🇬🇾 |
| `ht` | Haiti | 🇭🇹 |
| `jm` | Jamaica | 🇯🇲 |
| `kn` | Saint Kitts and Nevis | 🇰🇳 |
| `lc` | Saint Lucia | 🇱🇨 |
| `vc` | Saint Vincent and the Grenadines | 🇻🇨 |
| `sr` | Suriname | 🇸🇷 |
| `tt` | Trinidad and Tobago | 🇹🇹 |

#### Central America (6 countries)
| Code | Country | Flag |
|------|---------|------|
| `cr` | Costa Rica | 🇨🇷 |
| `sv` | El Salvador | 🇸🇻 |
| `gt` | Guatemala | 🇬🇹 |
| `hn` | Honduras | 🇭🇳 |
| `ni` | Nicaragua | 🇳🇮 |
| `pa` | Panama | 🇵🇦 |

#### South Asia (5 countries)
| Code | Country | Flag |
|------|---------|------|
| `bd` | Bangladesh | 🇧🇩 |
| `bt` | Bhutan | 🇧🇹 |
| `mv` | Maldives | 🇲🇻 |
| `np` | Nepal | 🇳🇵 |
| `lk` | Sri Lanka | 🇱🇰 |

#### Southeast Asia Emerging (5 countries)
| Code | Country | Flag |
|------|---------|------|
| `bn` | Brunei | 🇧🇳 |
| `kh` | Cambodia | 🇰🇭 |
| `la` | Laos | 🇱🇦 |
| `mm` | Myanmar | 🇲🇲 |
| `tl` | East Timor | 🇹🇱 |

---

## Static Frontier Countries

**Definition**: [`lines 30-32`](../../allium/lib/country_utils.py#L30-L32) - Predefined list of strategically important countries

**Note**: Estonia (ee) and Latvia (lv) were removed as they are EU member states with strong infrastructure.

| Code | Country | Flag | Justification |
|------|---------|------|---------------|
| `mn` | Mongolia | 🇲🇳 | Landlocked Asian country, strategic location |
| `tn` | Tunisia | 🇹🇳 | North African, post-Arab Spring democracy |
| `uy` | Uruguay | 🇺🇾 | Small South American country |
| `kz` | Kazakhstan | 🇰🇿 | Largest landlocked country, Central Asia |
| `md` | Moldova | 🇲🇩 | Non-EU Eastern European country |
| `lk` | Sri Lanka | 🇱🇰 | Island nation in South Asia |
| `mk` | North Macedonia | 🇲🇰 | Balkan country, recent NATO member |
| `mt` | Malta | 🇲🇹 | Strategic Mediterranean island |

---

## Real-World Examples

### Example 1: Armenia (AM) - **RARE Country**
*Network data: 4 relays out of 9,570 total*

| Factor | Calculation | Points | Weight | Contribution |
|--------|-------------|--------|--------|--------------|
| **Relay Count** | `max(7-4, 0) = 3` | 3 | ×4 | **12** |
| **Network %** | `4/9570 = 0.04%` (ultra-rare) | 6 | ×3 | **18** |
| **Geopolitical** | Developing country | 1 | ×2 | **2** |
| **Regional** | Not classified | 0 | ×1 | **0** |
| **Total Score** | | | | **32 points** |

**Result**: `32 >= 6` → **Armenia qualifies as RARE** ✅

### Example 2: France (FR) - **COMMON Country**
*Network data: ~800 relays out of 9,570 total*

| Factor | Calculation | Points | Weight | Contribution |
|--------|-------------|--------|--------|--------------|
| **Relay Count** | `max(7-800, 0) = 0` | 0 | ×4 | **0** |
| **Network %** | `800/9570 = 8.4%` (common) | 0 | ×3 | **0** |
| **Geopolitical** | Major EU country | 0 | ×2 | **0** |
| **Regional** | Not underrepresented | 0 | ×1 | **0** |
| **Total Score** | | | | **0 points** |

**Result**: `0 < 6` → **France does NOT qualify as rare** ❌

---

## Implementation Details

### Code Location
The complete implementation is in [`allium/lib/country_utils.py`](../../allium/lib/country_utils.py) with the main function:

```python
# Lines 417-478
def get_rare_countries_weighted_with_existing_data(country_data, total_relays, min_score=6):
    """
    Ultra-optimized version that uses pre-calculated country data from relays.py.
    
    This is the most efficient implementation for getting all rare countries in the network
    as it leverages existing work from relays.py categorization.
    """
```

### Usage in AROI Leaderboards
The system is used in [`allium/lib/aroileaders.py`](../../allium/lib/aroileaders.py):

```python
# Lines 169-172
country_data = relays_instance.json.get('sorted', {}).get('country', {})
from .country_utils import get_rare_countries_weighted_with_existing_data
all_rare_countries = get_rare_countries_weighted_with_existing_data(country_data, len(all_relays))
valid_rare_countries = {country for country in all_rare_countries if len(country) == 2 and country.isalpha()}
```

### Performance Optimization
The system calculates rare countries **once** globally and reuses the list for all operators, avoiding expensive per-operator calculations and improving performance by ~95%.

---

## Rarity Tiers

Countries are classified into tiers based on their total score:

| Score Range | Tier | Symbol | Description |
|-------------|------|--------|-------------|
| 15+ points | Legendary | 🏆 | Extremely rare, maximum strategic value |
| 10-14 points | Epic | ⭐ | Very rare, high strategic importance |
| 6-9 points | Rare | 🎖️ | Rare, qualifies for Frontier Builders |
| 3-5 points | Emerging | 📍 | Somewhat rare, developing importance |
| 0-2 points | Common | - | Common, well-represented |

Only countries scoring **6+ points** appear as "rare" in the Frontier Builders leaderboard, ensuring focus on truly underrepresented regions where Tor relay operations provide maximum network diversity benefit. 