# Top 10 AROI Operator Leaderboard - Data Availability Analysis

## Executive Summary

This document analyzes the data requirements for implementing the Top 10 AROI Operator Leaderboard by comparing the proposed categories against available Onionoo API data and current allium processing capabilities.

## Methodology

Analysis based on:
- **Onionoo API Documentation**: Official Tor Project API specification
- **Current Allium Codebase**: Existing data processing and aggregation capabilities
- **AROI Processing**: Current contact-based operator grouping functionality

## Categories Analysis

### **FULLY SUPPORTED (Ready to Implement)**

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

#### 6. **Technical Leaders (BSD Operators)** ✅
- **Data Available**: `platform` field with BSD variant detection
- **Aggregation**: BSD platform detection already implemented (FreeBSD, OpenBSD, NetBSD)
- **AROI Grouping**: Can group by contact and count BSD platforms
- **Implementation**: Count relays per AROI where `platform` contains BSD variants

#### 7. **Geographic Champions (Non-EU Leaders)** ✅
- **Data Available**: `country` and `country_name` fields from Onionoo
- **Aggregation**: Country-based grouping already implemented
- **AROI Grouping**: Can group by contact and identify primary countries
- **Implementation**: Group by AROI contact, identify non-EU countries per operator

### **PARTIALLY SUPPORTED (Requires New Calculations)**

#### 8. **Efficiency Champions (High CW/Bandwidth Ratio)** ⚠️
- **Data Available**: Both `consensus_weight_fraction` and `observed_bandwidth` available
- **Calculation Needed**: New ratio calculation (CW/BW ratio per AROI)
- **AROI Grouping**: Functional via contact hash grouping
- **Implementation**: Calculate efficiency ratio = total_consensus_weight / total_bandwidth per AROI

#### 9. **Frontier Builders (Rare Countries)** ⚠️
- **Data Available**: `country` field available from Onionoo
- **Calculation Needed**: "Rarity scoring" algorithm for countries (frequency analysis)
- **AROI Grouping**: Functional via contact hash grouping
- **Implementation**: Analyze country frequency across all relays, score operators in rare countries

#### 10. **Most Diverse Operators** ⚠️
- **Data Available**: `country`, `platform`, `as` (AS number) fields available
- **Calculation Needed**: Complex diversity scoring algorithm (30% geo, 25% platform, 20% ASN, 25% underrepresented)
- **AROI Grouping**: Functional via contact hash grouping
- **Implementation**: Multi-factor diversity calculation per AROI operator

### **REQUIRES NEW DATA/CALCULATIONS**

#### 11. **Network Veterans (Longest Operating)** ❌
- **Data Available**: `first_seen` field available from Onionoo
- **Current Issue**: Need historical data analysis or "longest operating" definition
- **AROI Grouping**: Functional via contact hash grouping
- **Gap**: Need to define "longest operating" vs "earliest first_seen" vs "consistent operation"
- **Implementation**: Use `first_seen` dates per AROI, but may need uptime consistency analysis

#### 12. **Diamond Stability (Highest Uptime)** ❌
- **Data Limited**: Onionoo provides `running` status but no historical uptime percentage
- **Missing Data**: No access to uptime history documents in current implementation
- **AROI Grouping**: Functional via contact hash grouping
- **Gap**: Would need Onionoo uptime documents (`/uptime` endpoint) integration
- **Implementation**: Requires new data source or approximation using `running` status

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
6. **Technical Leaders (BSD Operators)** - Direct data available
7. **Geographic Champions (Non-EU Leaders)** - Direct data available

### **Tier 2: Quick Implementation (Simple Calculations)**
8. **Efficiency Champions** - Simple ratio calculation
9. **Frontier Builders** - Country frequency analysis required
10. **Most Diverse Operators** - Complex multi-factor scoring required

### **Tier 3: Requires New Data Integration**
11. **Network Veterans** - May work with `first_seen` approximation
12. **Diamond Stability** - Requires Onionoo uptime documents integration

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

- **High Confidence (Tier 1)**: 7/12 categories ready for immediate deployment
- **Medium Confidence (Tier 2)**: 3/12 categories require calculations but data available  
- **Low Confidence (Tier 3)**: 2/12 categories may require new data sources

## Conclusion

**58% of leaderboard categories (7/12)** can be implemented immediately with existing data and processing capabilities. The AROI operator grouping system is fully functional and ready for leaderboard implementation.

Priority should focus on deploying the 7 ready categories first, then iteratively adding the calculation-required categories, and finally investigating uptime data integration for completeness. 