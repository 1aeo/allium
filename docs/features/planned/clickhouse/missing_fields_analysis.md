# ClickHouse Schema Missing Fields Analysis

**Created**: 2025-01-27  
**Status**: Under Review  
**Purpose**: Analyze missing fields across all Tor data sources and provide implementation recommendations

---

## Overview

This document analyzes potentially missing fields from our ClickHouse schema across all 5-6 input file types:
- Consensus documents
- Authority votes  
- Server descriptors
- Extra-info descriptors
- Bandwidth files
- (Bridge data - excluded per requirements)

Each item includes thorough analysis, recommendation, pros/cons, and schema changes where applicable.

---

## 🔍 ANALYSIS BY CATEGORY

### **1. CONSENSUS METADATA & PARAMETERS**

#### **1.1 Consensus Parameters (`params` line)**
**Source**: Consensus documents (`params` line)  
**Description**: Network-wide parameters that affect Tor behavior (e.g., `circuitPriorityHalflifeMsec=30000`)  
**Current Schema**: ❌ Not captured  

**Recommendation**: ✅ **ADD** - High Priority  

**Pros**:
- Critical for understanding network behavior changes over time
- Essential for research into parameter impact on performance
- Relatively small data footprint (key-value pairs)
- Direct impact on relay selection and circuit building

**Cons**:
- Adds complexity with nested/map structure
- May change over time requiring schema flexibility

**Most Similar Existing Field**: `consensus_protocols Map(String, String)`

**Before/After Schema**:
```sql
-- BEFORE: Missing consensus parameters

-- AFTER: Add consensus parameters
consensus_parameters Map(String, String) CODEC(ZSTD)
  COMMENT 'Consensus parameters | params | 2025-06-28-20-00-00-consensus',
```

---

#### **1.2 Bandwidth Weights (`bandwidth-weights` line)**
**Source**: Consensus documents (`bandwidth-weights` line)  
**Description**: Path selection weights (Wgg, Wgd, Wee, Wed, Wmg, Wmd, Wme, Wmt, etc.)  
**Current Schema**: ❌ Not captured  

**Recommendation**: ✅ **ADD** - High Priority  

**Pros**:
- Fundamental to understanding Tor's path selection algorithm
- Critical for bandwidth allocation research
- Stable set of ~10-12 weight values
- Essential for replicating Tor's relay selection behavior

**Cons**:
- Adds 10-12 columns to already wide table
- Values may be correlated

**Most Similar Existing Field**: `consensus_bandwidth UInt32`

**Before/After Schema**:
```sql
-- BEFORE: Missing bandwidth weights

-- AFTER: Add bandwidth weights  
bandwidth_weight_Wgg UInt32 COMMENT 'Guard-Guard weight | Wgg | consensus',
bandwidth_weight_Wgd UInt32 COMMENT 'Guard-non-Guard weight | Wgd | consensus', 
bandwidth_weight_Wmg UInt32 COMMENT 'Middle-Guard weight | Wmg | consensus',
bandwidth_weight_Wmd UInt32 COMMENT 'Middle-non-Guard weight | Wmd | consensus',
bandwidth_weight_Wee UInt32 COMMENT 'Exit-Exit weight | Wee | consensus',
bandwidth_weight_Wed UInt32 COMMENT 'Exit-non-Exit weight | Wed | consensus',
bandwidth_weight_Wme UInt32 COMMENT 'Middle-Exit weight | Wme | consensus',
bandwidth_weight_Wmt UInt32 COMMENT 'Middle weight | Wmt | consensus',
```

---

#### **1.3 Software Package Hashes (`package` lines)**
**Source**: Consensus documents (`package` lines) - Legacy  
**Description**: Software distribution verification hashes (mostly historical)  
**Current Schema**: ❌ Not captured  

**Recommendation**: ❌ **SKIP** - Low Priority  

**Pros**:
- Historical completeness
- Software verification tracking

**Cons**:
- Legacy feature, rarely used in modern consensus
- High storage overhead for minimal research value
- Complex nested structure for rarely-populated data
- Focus should be on relay behavior, not software distribution

**Most Similar Existing Field**: N/A (would be new nested structure)

---

### **2. RELAY ADDRESSING & CONNECTIVITY**

#### **2.1 Alternative OR Addresses (`or-address` lines)**
**Source**: Server descriptors (`or-address` lines)  
**Description**: Additional IPv4/IPv6 addresses and ports beyond primary OR address  
**Current Schema**: ⚠️ Partial (only primary IPv4/IPv6 captured)  

**Recommendation**: ✅ **ADD** - Medium Priority  

**Pros**:
- Complete picture of relay connectivity options
- Important for IPv6 transition analysis
- Relatively common in modern relays
- Supports multi-homed relay research

**Cons**:
- Nested array structure adds complexity
- Most relays have only 1-2 additional addresses

**Most Similar Existing Field**: `consensus_ipv4_address`, `consensus_ipv6_address`

**Before/After Schema**:
```sql
-- BEFORE: Only primary addresses
consensus_ipv4_address Nullable(IPv4) COMMENT 'IPv4 address | r <IP> | consensus',
consensus_ipv6_address Nullable(IPv6) COMMENT 'IPv6 address | r <IP6> | consensus',

-- AFTER: Add additional addresses
additional_or_addresses Array(Tuple(
    address IPv6,  -- Supports both IPv4 and IPv6
    port UInt16
)) COMMENT 'Additional OR addresses | or-address | server-descriptors',
```

---

#### **2.2 Overload Information (`overload-general`)**
**Source**: Server descriptors (`overload-general` line)  
**Description**: General overload indicators when relay is under stress  
**Current Schema**: ❌ Not captured  

**Recommendation**: ✅ **ADD** - Medium Priority  

**Pros**:
- Important for network health monitoring
- Indicates relay performance issues
- Helps identify capacity problems
- Lightweight single field

**Cons**:
- Not present in all descriptors
- Binary indicator with limited granularity

**Most Similar Existing Field**: `descriptor_uptime_seconds UInt32`

**Before/After Schema**:
```sql
-- BEFORE: Missing overload tracking

-- AFTER: Add overload indicator
descriptor_overload_general UInt8 DEFAULT 0
  COMMENT 'General overload flag | overload-general | server-descriptors',
```

---

### **3. FAMILY & TRUST RELATIONSHIPS**

#### **3.1 Family Certificates (`family-cert`)**
**Source**: Server descriptors (`family-cert` lines)  
**Description**: Cryptographic certificates proving family relationships (future replacement for `family` field)  
**Current Schema**: ❌ Not captured  

**Recommendation**: ✅ **ADD** - High Priority (Future-Proofing)  

**Storage Research**: Family certificates use Ed25519 certificate format (type `[0C]` FAMILY_V_IDENTITY) with ~104 bytes per certificate plus minimal extensions. Much more efficient than storing full certificate strings.

**Pros**:
- Future-proofs schema for upcoming Tor features
- More secure than current `family` declarations
- Essential for family-based analysis in future network
- Cryptographically verifiable relationships
- Efficient structured storage vs full certificate strings
- O(N) storage complexity vs O(N²) for current family system

**Cons**:
- Not yet widely deployed
- Complex parsing required
- Transition period requires both formats

**Most Similar Existing Field**: `descriptor_declared_family_list Array(FixedString(20))`

**Before/After Schema**:
```sql
-- BEFORE: Only declared family
descriptor_declared_family_list Array(FixedString(20))
  COMMENT 'Declared family | family | server-descriptors',

-- AFTER: Add both for compatibility during transition (keep past 20 years + future)
descriptor_declared_family_list Array(FixedString(20))
  COMMENT 'Declared family | family | server-descriptors',

-- EFFICIENT: Structured certificate storage instead of full certificate strings
family_certificates Array(Tuple(
    cert_type UInt8,           -- Certificate type (0C for family)
    expiration_date UInt32,    -- Hours since epoch 
    family_key FixedString(32),-- Ed25519 family signing key
    signature FixedString(64)  -- Ed25519 signature
)) CODEC(ZSTD) COMMENT 'Family certificates | family-cert | server-descriptors',
```

**Implementation Note**: Store parsed certificate components rather than full certificate strings for 75% space savings and better query performance.

---

### **4. GEOGRAPHIC & DATABASE METADATA**

#### **4.1 GeoIP Database Versions**
**Source**: System metadata (GeoIP database info)  
**Description**: Version/date of GeoIP databases used for country/ASN resolution  
**Current Schema**: ❌ Not captured  

**Recommendation**: ✅ **ADD** - Medium Priority  

**Pros**:
- Essential for data quality tracking
- Explains changes in geo assignments over time
- Relatively small metadata overhead
- Important for reproducible research

**Cons**:
- System metadata, not directly from Tor files
- Requires coordination with ingestion process

**Most Similar Existing Field**: `geo_country_code FixedString(2)`

**Before/After Schema**:
```sql
-- BEFORE: Geo fields without version tracking
geo_country_code FixedString(2) COMMENT 'Country code | GeoLite2 country_iso_code | GeoLite2 DB',
geo_as_number UInt32 COMMENT 'ASN number | GeoLite2 autonomous_system_number | GeoLite2 DB',

-- AFTER: Add database version tracking
geo_database_version LowCardinality(String)
  COMMENT 'GeoIP database version | system | GeoLite2 DB metadata',
geo_database_date Date
  COMMENT 'GeoIP database date | system | GeoLite2 DB metadata',
```

---

### **5. OPERATING SYSTEM & SOFTWARE DETAILED TRACKING**

#### **5.1 Detailed Platform Information**
**Source**: Server descriptors (`platform` line) - Enhanced parsing  
**Description**: Structured OS, version, and architecture information extracted from platform string  
**Current Schema**: ⚠️ Raw only (`descriptor_platform_raw String`)  

**Recommendation**: ✅ **ADD** - Medium Priority  

**Pros**:
- Better analysis of OS distribution in Tor network
- Structured data enables OS-specific research
- Platform security analysis capabilities
- Relatively easy to parse from existing data

**Cons**:
- Parsing complexity and potential errors
- Platform strings are inconsistent across relays
- Additional storage for parsed fields

**Most Similar Existing Field**: `descriptor_platform_raw String`, `descriptor_tor_version String`

**Before/After Schema**:
```sql
-- BEFORE: Only raw platform string
descriptor_platform_raw String CODEC(ZSTD) COMMENT 'Platform string | platform | server-descriptors',

-- AFTER: Add parsed platform fields
descriptor_os_name LowCardinality(String)
  COMMENT 'Operating system | parsed from platform | server-descriptors',
descriptor_os_version LowCardinality(String)  
  COMMENT 'OS version | parsed from platform | server-descriptors',
descriptor_architecture LowCardinality(String)
  COMMENT 'CPU architecture | parsed from platform | server-descriptors',
```

---

### **6. ADVANCED PROTOCOL FEATURES**

#### **6.1 Extended Protocol Information**
**Source**: Server descriptors (various protocol-related lines)  
**Description**: Additional protocol capabilities like `eventdns`, `caches-extra-info`, etc.  
**Current Schema**: ⚠️ Partial (`consensus_protocols Map(String, String)`)  

**Recommendation**: ❌ **SKIP** - Low Priority  

**Pros**:
- Complete protocol capability tracking
- Research into feature adoption

**Cons**:
- Most capabilities already captured in protocols map
- Limited research value for detailed protocol flags
- High complexity for marginal benefit
- Focus should be on high-level protocol versions

**Most Similar Existing Field**: `consensus_protocols Map(String, String)`

---

## 📊 IMPLEMENTATION PRIORITY SUMMARY

### **🔴 HIGH PRIORITY (Recommend Implementation)**
1. **Consensus Parameters** - Critical for network behavior analysis
2. **Bandwidth Weights** - Essential for path selection research  
3. **Family Certificates** - Future-proofing for upcoming Tor features

### **🟡 MEDIUM PRIORITY (Consider Implementation)**
4. **Alternative OR Addresses** - Complete connectivity picture
5. **Overload Indicators** - Network health monitoring
6. **GeoIP Database Versions** - Data quality tracking
7. **Parsed Platform Information** - Structured OS analysis

### **🟢 LOW PRIORITY (Skip for Now)**
8. **Package Lines** - Legacy feature, minimal research value
9. **Extended Protocol Flags** - Already captured in protocols map

---

## 🎯 RECOMMENDED NEXT STEPS

1. **Implement High Priority items first** (consensus parameters, bandwidth weights, family certificates)
2. **Research actual data prevalence** for medium priority items
3. **Validate storage impact** for proposed changes
4. **Consider implementation in phases** rather than all at once

---

## 📝 APPROVAL CHECKLIST

- [ ] **Section 1**: Consensus Parameters (`params`) - HIGH PRIORITY
- [ ] **Section 2**: Bandwidth Weights (`bandwidth-weights`) - HIGH PRIORITY  
- [ ] **Section 3**: Family Certificates (`family-cert`) - HIGH PRIORITY
- [ ] **Section 4**: Alternative OR Addresses (`or-address`) - MEDIUM PRIORITY
- [ ] **Section 5**: Overload Indicators (`overload-general`) - MEDIUM PRIORITY
- [ ] **Section 6**: GeoIP Database Versions - MEDIUM PRIORITY
- [ ] **Section 7**: Parsed Platform Information - MEDIUM PRIORITY

**Note**: Sections 8-9 are recommended to be skipped based on analysis. 