# AROI Leaderboard System

**Autonomous Relay Operator Identification (AROI) Leaderboard** - A comprehensive ranking and analysis system for Tor relay operators.

## 📋 Documents

### [Leaderboard Specification](leaderboard-specification.md)
**Complete specification and design for the Top 10 AROI Operator Leaderboard**

- **Purpose**: Detailed proposal for implementing a comprehensive Tor relay operator leaderboard
- **Content**: Live dashboard mockups, ranking categories, performance metrics, and visual specifications  
- **Audience**: Product owners, developers, and UI/UX designers
- **Size**: ~19KB, comprehensive specification with examples

**Key Features:**
- 🏆 **12 Ranking Categories**: Bandwidth, consensus weight, exit/guard operators, diversity, efficiency
- 📊 **Live Dashboard**: Real-time leaderboard with champion badges and achievements
- 🌍 **Geographic Analysis**: Global diversity tracking and frontier country pioneers
- ⚡ **Performance Metrics**: Efficiency ratios, uptime tracking, and technical excellence
- 🎯 **Operator Focus**: AROI-based grouping for accurate operator representation

### [Data Availability Analysis](data-availability-analysis.md)
**Technical analysis of data requirements and implementation feasibility**

- **Purpose**: Comprehensive analysis of Onionoo API data availability for leaderboard implementation
- **Content**: Data mapping, implementation priorities, and technical feasibility assessment
- **Audience**: Technical leads, backend developers, and data engineers
- **Size**: ~7.7KB, technical analysis with implementation roadmap

**Key Analysis:**
- ✅ **Ready Categories**: 7/12 categories implementable immediately with existing data
- ⚠️ **Calculation Required**: 3/12 categories need new algorithms but data is available
- ❌ **New Data Needed**: 2/12 categories require additional data sources
- 🎯 **Implementation Priority**: Tiered approach with 58% immediate deployment capability

## 🎯 System Overview

The AROI Leaderboard System provides:

### **Operator Identification**
- **AROI Processing**: Automatic operator identification from contact information
- **Contact Grouping**: Relay aggregation by verified operator contacts
- **Duplicate Prevention**: Accurate operator representation without double-counting

### **Performance Ranking**
- **Multi-Category Analysis**: 12 distinct ranking categories covering all aspects of relay operation
- **Real-Time Updates**: Live ranking updates based on current network status
- **Achievement System**: Champion badges and recognition for top performers

### **Geographic & Technical Diversity**
- **Global Coverage**: Geographic diversity tracking and frontier country analysis
- **Platform Diversity**: Recognition for non-Linux operators and BSD technical leaders
- **Infrastructure Analysis**: ASN diversity and network distribution tracking

## 📊 Implementation Status

| Category | Status | Data Available | Implementation |
|----------|--------|----------------|----------------|
| **Bandwidth Leaders** | ✅ Ready | Yes | Immediate |
| **Consensus Weight** | ✅ Ready | Yes | Immediate |
| **Exit Operators** | ✅ Ready | Yes | Immediate |
| **Guard Operators** | ✅ Ready | Yes | Immediate |
| **Platform Diversity** | ✅ Ready | Yes | Immediate |
| **Geographic Champions** | ✅ Ready | Yes | Immediate |
| **BSD Technical Leaders** | ✅ Ready | Yes | Immediate |
| **Efficiency Champions** | ⚠️ Calculation | Yes | Simple Ratio |
| **Frontier Builders** | ⚠️ Calculation | Yes | Rarity Analysis |
| **Diversity Leaders** | ⚠️ Calculation | Yes | Multi-Factor |
| **Network Veterans** | ❌ New Data | Partial | Uptime History |
| **Stability Champions** | ❌ New Data | Limited | Historical Data |

## 🏁 Frontier Builders Rarity Scoring System

The **Frontier Builders** category uses a sophisticated weighted scoring system to identify rare countries where operating Tor relays provides maximum network diversity benefit.

### **Scoring Algorithm**

Countries are evaluated using a **4-factor weighted formula** implemented in `allium/lib/country_utils.py`:

```python
# Lines 404-408, 447-451
rarity_score = (
    (relay_count_factor * 4) +           # Weight: 4x (highest priority)
    (network_percentage_factor * 3) +    # Weight: 3x 
    (geopolitical_factor * 2) +          # Weight: 2x
    (regional_factor * 1)                # Weight: 1x (lowest priority)
)

# Rarity threshold decision (Lines 411, 454)
if rarity_score >= 6:  # Default minimum score
    country_is_rare = True
```

### **Factor Calculations**

#### **1. Relay Count Factor** (Lines 262-276)
```python
def calculate_relay_count_factor(country_relay_count):
    if country_relay_count == 0:
        return 0
    return max(7 - country_relay_count, 0)
```

**Scoring:**
- **1 relay** = 6 points
- **2 relays** = 5 points
- **3 relays** = 4 points
- **7+ relays** = 0 points

#### **2. Network Percentage Factor** (Lines 278-296)
```python
percentage = (country_relays / total_network_relays) * 100

if percentage < 0.05:    return 6  # Ultra-rare (<0.05%)
elif percentage < 0.1:   return 4  # Very rare (0.05-0.1%)
elif percentage < 0.2:   return 2  # Rare (0.1-0.2%)
else:                    return 0  # Common (>0.2%)
```

#### **3. Geopolitical Factor** (Lines 298-318)
```python
if country_lower in GEOPOLITICAL_CLASSIFICATIONS['conflict_zones']:
    return 3
elif country_lower in GEOPOLITICAL_CLASSIFICATIONS['authoritarian']:
    return 3
elif country_lower in GEOPOLITICAL_CLASSIFICATIONS['island_nations']:
    return 2
elif country_lower in GEOPOLITICAL_CLASSIFICATIONS['landlocked_developing']:
    return 2
elif country_lower in GEOPOLITICAL_CLASSIFICATIONS['developing']:
    return 1
else:
    return 0
```

#### **4. Regional Factor** (Lines 320-335)
```python
if country_lower in REGIONAL_CLASSIFICATIONS['underrepresented']:
    return 2
elif country_lower in REGIONAL_CLASSIFICATIONS['emerging']:
    return 1
else:
    return 0
```

### **Rarity Classification Tiers** (Lines 346-362)

```python
def assign_rarity_tier(rarity_score):
    if rarity_score >= 15:   return 'legendary'    # 🏆
    elif rarity_score >= 10: return 'epic'         # ⭐
    elif rarity_score >= 6:  return 'rare'         # 🎖️
    elif rarity_score >= 3:  return 'emerging'     # 📍
    else:                    return 'common'       # Standard
```

### **Real-World Examples**

#### **🇦🇲 Armenia (AM) - RARE Country**
*Network data: 4 relays out of 9,570 total*

| Factor | Calculation | Points | Weighted |
|--------|-------------|--------|----------|
| **Relay Count** | `max(7-4, 0) = 3` | 3 | 3 × 4 = **12** |
| **Network %** | `4/9570 = 0.04%` (ultra-rare) | 6 | 6 × 3 = **18** |
| **Geopolitical** | Developing country | 1 | 1 × 2 = **2** |
| **Regional** | Not classified | 0 | 0 × 1 = **0** |
| **Total Score** | | | **32 points** |

**Result:** `32 >= 6` → **Armenia qualifies as RARE** ✅

#### **🇫🇷 France (FR) - COMMON Country**
*Network data: ~800 relays out of 9,570 total*

| Factor | Calculation | Points | Weighted |
|--------|-------------|--------|----------|
| **Relay Count** | `max(7-800, 0) = 0` | 0 | 0 × 4 = **0** |
| **Network %** | `800/9570 = 8.4%` (common) | 0 | 0 × 3 = **0** |
| **Geopolitical** | Major EU country | 0 | 0 × 2 = **0** |
| **Regional** | Not underrepresented | 0 | 0 × 1 = **0** |
| **Total Score** | | | **0 points** |

**Result:** `0 < 6` → **France does NOT qualify as rare** ❌

### **Frontier Builders Display**

The leaderboard shows operators by their actual relays in rare countries:

- **prsv.ch**: `6 relays in 6 rare countries` (6 relays in Armenia, Albania, etc.)
- **BMTY90**: `4 relays in 4 rare countries` 
- **your@e-mail**: `3 relays in 3 rare countries`

This ensures accurate representation - operators are ranked by their **actual contribution to network diversity** in underrepresented regions, not by total relay count.

## 🏆 Network Veterans Scoring System

The **Network Veterans** category recognizes operators with the longest continuous service to the Tor network, emphasizing early adoption while considering operational scale.

### **Scoring Algorithm**

Veteran scoring uses an **earliest first seen time** approach with **relay scale weighting** implemented in `allium/lib/aroileaders.py`:

```python
# Lines 179-209
# Find earliest first_seen date among all operator's relays
earliest_first_seen = None
for relay in operator_relays:
    relay_first_seen = datetime.strptime(relay.get('first_seen'), '%Y-%m-%d %H:%M:%S')
    if earliest_first_seen is None or relay_first_seen < earliest_first_seen:
        earliest_first_seen = relay_first_seen

# Calculate veteran score
veteran_days = (current_date - earliest_first_seen).days
veteran_score = veteran_days * veteran_relay_scaling_factor
```

### **Scaling Factor Calculation**

Relay count determines scaling factor based on network maximums (360 max relays):

```python
# Lines 185-197
if total_relays >= 300:      # Top tier operators (83%+ of max)
    veteran_relay_scaling_factor = 1.3
elif total_relays >= 200:    # Large operators (56%+ of max)  
    veteran_relay_scaling_factor = 1.25
elif total_relays >= 100:    # Medium-large operators (28%+ of max)
    veteran_relay_scaling_factor = 1.2
elif total_relays >= 50:     # Medium operators (14%+ of max)
    veteran_relay_scaling_factor = 1.15
elif total_relays >= 20:     # Small-medium operators (6%+ of max)
    veteran_relay_scaling_factor = 1.1
elif total_relays >= 10:     # Small operators (3%+ of max)
    veteran_relay_scaling_factor = 1.05
else:                        # Micro operators (1-9 relays)
    veteran_relay_scaling_factor = 1.0
```

### **Scoring Criteria**

#### **1. Primary Factor: Earliest First Seen Time**
- **Purpose**: Identify true network pioneers who started operating relays earliest
- **Calculation**: Days between earliest relay's `first_seen` date and current date
- **Weight**: Primary ranking factor (base score)

#### **2. Secondary Factor: Relay Scale Multiplier**
- **Purpose**: Differentiate between operators with similar start dates based on commitment level
- **Calculation**: Tiered multiplier from 1.0x to 1.3x based on total relay count
- **Weight**: Tiebreaker factor (small influence)

#### **3. Operator Perspective Benefits**
- **Early Adoption Recognition**: Veterans with longest service get primary recognition
- **Scale Consideration**: Among equal veterans, larger operations rank higher
- **Commitment Weighting**: Sustained large-scale operations receive bonus points

### **Real-World Examples**

#### **🥇 Top Veteran (TOR Operator &lt;tor@insc.de&gt;)**
*Operating since ~2007 with 1 relay*

| Metric | Value | Calculation |
|--------|-------|-------------|
| **Earliest First Seen** | ~6,435 days ago | Single relay operation since 2007 |
| **Total Relays** | 1 relay | Micro operator (1-9 relays) |
| **Scaling Factor** | 1.0x | No scale bonus for small operations |
| **Veteran Score** | 6,435.0 | `6,435 days × 1.0 = 6,435` |

**Display:** `"6435 days * 1 relays"` with tooltip `"6435 days * 1.0 (1 relays)"`

#### **🥈 Second Place Veteran**
*Operating since ~2009 with 1 relay*

| Metric | Value | Calculation |
|--------|-------|-------------|
| **Earliest First Seen** | ~5,453 days ago | Single relay operation since 2009 |
| **Total Relays** | 1 relay | Micro operator (1-9 relays) |
| **Scaling Factor** | 1.0x | No scale bonus for small operations |
| **Veteran Score** | 5,453.0 | `5,453 days × 1.0 = 5,453` |

#### **Hypothetical Large Veteran Example**
*Operating since 2010 with 150 relays*

| Metric | Value | Calculation |
|--------|-------|-------------|
| **Earliest First Seen** | ~5,000 days ago | Started relay operations in 2010 |
| **Total Relays** | 150 relays | Medium-large operator (100+ relays) |
| **Scaling Factor** | 1.2x | 20% bonus for substantial scale |
| **Veteran Score** | 6,000.0 | `5,000 days × 1.2 = 6,000` |

**Result:** Large operator with slightly later start (5,000 days) scores 6,000, beating smaller veteran (5,453 days) due to scale bonus.

### **Veteran Rankings Display**

The leaderboard emphasizes both veteran status and commitment level:

- **Top 3 Performance**: `"6435 days * 1 relays"` (earliest time × relay count)
- **Top 25 Specialization**: `"6435 days * 1.0..."` (calculation details, truncated)
- **Tooltip Details**: `"6435 days * 1.0 (1 relays)"` (complete scoring breakdown)

This ensures **true network pioneers** receive primary recognition while **sustained large-scale commitment** serves as meaningful tiebreaker for operators with similar veteran status.

## 🔗 Related Documentation

- **[Performance](../../performance/aroi-leaderboard-ultra-optimization.md)** - Ultra-optimization implementation report
- **[Geographic Processing](../geographic-processing.md)** - Country harmonization and geographic analysis
- **[Architecture](../../architecture/)** - System architecture and design principles