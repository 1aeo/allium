# AROI Leaderboard Enhancement Proposals

## Implementation Status

✅ **IMPLEMENTED**: The core AROI leaderboard system with 17 competitive categories is fully operational. This document now focuses on advanced enhancements and additional features.

## Current Implementation

**17 Live Categories**:
- All basic capacity, authority, and diversity metrics are implemented
- Reliability scoring (6-month and 5-year) is operational  
- Platform diversity and geographic leadership tracking is active
- IPv4/IPv6 address diversity leaderboards are functional

## Enhancement Opportunities

### **Advanced Analytics Integration**

#### 1. **Bandwidth Contributed** ✅
- **Data Available**: `observed_bandwidth` per relay from Onionoo
- **Aggregation**: Already implemented in `relays.py` - contact-based bandwidth totals
- **AROI Grouping**: Functional via contact hash grouping (`contact_md5`)
- **Implementation**: Sum `observed_bandwidth` for all relays per AROI contact

#### 2. **Consensus Weight** ✅
- **Data Available**: `consensus_weight_fraction` per relay from Onionoo
- **Aggregation**: Already implemented - contact-based consensus weight totals
- **AROI Grouping**: Functional via contact hash grouping
- **Implementation**: Sum `consensus_weight_fraction` for all relays per AROI contact

#### 3. **Exit Operators** ✅
- **Data Available**: Exit flag detection via `flags` array containing "Exit"
- **Aggregation**: Already implemented - exit relay counts and bandwidth per contact
- **AROI Grouping**: Functional via contact hash grouping
- **Implementation**: Count relays with "Exit" flag per AROI contact

#### 4. **Guard Operators** ✅
- **Data Available**: Guard flag detection via `flags` array containing "Guard"
- **Aggregation**: Already implemented - guard relay counts and bandwidth per contact
- **AROI Grouping**: Functional via contact hash grouping
- **Implementation**: Count relays with "Guard" flag per AROI contact

#### 5. **Platform Diversity (Non-Linux Heroes)** ✅
- **Data Available**: `platform` field from Onionoo (parsed and cleaned in `_trim_platform()`)
- **Aggregation**: Platform detection already implemented (FreeBSD, OpenBSD, Windows, etc.)
- **AROI Grouping**: Can group by contact and count non-Linux platforms
- **Implementation**: Count relays per AROI where `platform != "Linux"`

#### 6. **Exit Authority Champions** ✅
- **Data Available**: Exit consensus weight calculation via `exit_consensus_weight_fraction`
- **Aggregation**: Exit authority weight already implemented in contact aggregations
- **AROI Grouping**: Functional via contact hash grouping
- **Implementation**: Sum exit consensus weight for all relays per AROI contact

#### 7. **Most Diverse Operators** ✅
- **Data Available**: `country`, `platform`, `as` (AS number) fields available
- **Aggregation**: Multi-factor diversity scoring already implemented
- **AROI Grouping**: Functional via contact hash grouping
- **Implementation**: Multi-factor diversity calculation per AROI operator

### **PARTIALLY SUPPORTED (Requires New Calculations)**

#### 8. **Frontier Builders (Rare Countries)** ⚠️
- **Data Available**: `country` field available from Onionoo
- **Calculation Needed**: "Rarity scoring" algorithm for countries (frequency analysis)
- **AROI Grouping**: Functional via contact hash grouping
- **Implementation**: Analyze country frequency across all relays, score operators in rare countries

#### 9. **Geographic Champions (Non-EU Leaders)** ⚠️
- **Data Available**: `country` and `country_name` fields from Onionoo
- **Calculation Needed**: Non-EU country identification and counting
- **AROI Grouping**: Functional via contact hash grouping
- **Implementation**: Group by AROI contact, identify and count non-EU countries per operator

#### 10. **Network Veterans (Longest Operating)** ⚠️
- **Data Available**: `first_seen` field available from Onionoo
- **Calculation Needed**: Earliest first seen time calculation with relay scale weighting
- **AROI Grouping**: Functional via contact hash grouping
- **Implementation**: Use `first_seen` dates per AROI with veteran scoring algorithm

## AROI Processing Status ✅

**Current Capability**: Fully functional AROI operator identification and grouping
- **Contact Processing**: `_process_aroi_contacts()` extracts AROI domains from contact info
- **Contact Grouping**: Operators grouped by `contact_md5` hash
- **Display Format**: AROI domain extraction following ContactInfo-Information-Sharing-Specification
- **Aggregation**: All bandwidth, consensus weight, and relay counts already aggregated by contact/AROI

## Implementation Priority Stack Rank

### **Tier 1: Immediate Implementation (Ready Now)**
1. **Bandwidth Contributed** - Direct data available
2. **Consensus Weight** - Direct data available  
3. **Exit Operators** - Direct data available
4. **Guard Operators** - Direct data available
5. **Platform Diversity (Non-Linux Heroes)** - Direct data available
6. **Exit Authority Champions** - Direct data available
7. **Most Diverse Operators** - Direct data available

### **Tier 2: Quick Implementation (Simple Calculations)**
8. **Frontier Builders** - Country frequency analysis required
9. **Geographic Champions (Non-EU Leaders)** - Geographic analysis required
10. **Network Veterans** - Veteran scoring algorithm required

## Recommendations

### **Phase 1: Quick Win Implementation**
- Deploy Tier 1 categories immediately using existing data
- Implement basic AROI leaderboard infrastructure  
- Focus on 7 categories that require zero additional calculations

### **Phase 2: Enhanced Calculations** 
- Add Tier 2 categories with new calculation algorithms
- Implement diversity scoring system
- Add country rarity analysis

### **Phase 3: Data Integration**
- Investigate Onionoo uptime documents integration for stability metrics
- Define and implement "network veteran" criteria
- Consider proxy metrics for uptime if direct data unavailable

## Data Confidence Assessment

- **High Confidence (Tier 1)**: 7/10 categories ready for immediate deployment
- **Medium Confidence (Tier 2)**: 3/10 categories require calculations but data is available

## Conclusion

**70% of leaderboard categories (7/10)** can be implemented immediately with existing data and processing capabilities. The AROI operator grouping system is fully functional and ready for leaderboard implementation.

Priority should focus on deploying the 7 ready categories first, then iteratively adding the calculation-required categories for full implementation. 