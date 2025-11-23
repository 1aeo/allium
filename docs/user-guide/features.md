# Features Guide

Complete guide to understanding Allium's features and generated content.

---

## 📊 Overview

Allium generates a comprehensive static website with multiple views of Tor network data. All content is generated from the Onionoo API and updated whenever you run the generation command.

---

## 🏠 Main Pages

### Index Page (`index.html`)
**Top 500 Relays by Consensus Weight**

Shows the most influential relays on the Tor network:
- Sorted by consensus weight (network voting power)
- Displays bandwidth, flags, country, platform
- Links to detailed relay pages
- Updated every generation

**Use Case**: Quick overview of network's most important relays

### All Relays (`misc/all.html`)
**Complete Relay Listing**

Every active relay on the network:
- Alphabetically sorted
- Full technical details
- Search-friendly format
- Thousands of relays

**Use Case**: Finding specific relays, comprehensive analysis

### Network Health Dashboard (`network-health.html`)
**Real-Time Network Monitoring**

Comprehensive network metrics across 10 categories:
- **Network Overview**: Total relays, bandwidth, consensus weight
- **Relay Statistics**: Exit/Guard/Running counts and percentages
- **Bandwidth Analysis**: Total observed bandwidth, consensus weight distribution
- **Uptime & Reliability**: Network-wide uptime statistics, reliability metrics
- **IPv6 Adoption**: Relay and operator IPv6 support tracking
- **Geographic Diversity**: Country distribution, concentration risks
- **Provider Diversity**: AS distribution, infrastructure diversity
- **Performance Metrics**: CW/BW ratios, efficiency analysis
- **Authority Health**: Directory authority status and performance
- **Operator Statistics**: Total operators, AROI leaderboard participants

**Use Case**: Understanding overall network health and trends

---

## 🏆 AROI Leaderboards (`misc/aroi-leaderboards.html`)

**Authenticated Relay Operator Identifier** rankings across 17 specialized categories.

### What is AROI?

AROI identifies relay operators who provide contact information, enabling:
- Operator-level (not just relay-level) analysis
- Recognition for collective contributions
- Multi-relay family tracking
- Community building

### The 17 Categories

#### 🚀 Capacity & Performance (2 categories)

**1. Bandwidth Contributed**
- **Metric**: Total observed bandwidth capacity
- **Purpose**: Recognize raw capacity contribution
- **Display**: Gbit/s or GB/s

**2. Consensus Weight Authority**
- **Metric**: Network routing control influence
- **Purpose**: Measure network decision-making power
- **Display**: Percentage of total consensus weight

#### 🛡️ Network Role Specialization (4 categories)

**3. Exit Authority Champions**
- **Metric**: Exit consensus weight control
- **Purpose**: Recognize exit relay operators
- **Importance**: Exit nodes enable internet access

**4. Guard Authority Champions**
- **Metric**: Guard consensus weight control
- **Purpose**: Recognize guard relay operators
- **Importance**: Guard nodes are entry points to Tor

**5. Exit Operators**
- **Metric**: Number of exit relays operated
- **Purpose**: Track exit relay infrastructure providers
- **Note**: Weighted by relay importance

**6. Guard Operators**
- **Metric**: Number of guard relays operated
- **Purpose**: Track guard relay infrastructure providers
- **Note**: Weighted by relay importance

#### ⏰ Reliability & Performance Excellence (4 categories)

**7. Reliability Masters (6-month)**
- **Metric**: 6-month average uptime
- **Eligibility**: 25+ relays minimum
- **Purpose**: Recent reliability excellence
- **Statistical Significance**: Large relay count requirement

**8. Legacy Titans (5-year)**
- **Metric**: 5-year average uptime
- **Eligibility**: 25+ relays minimum
- **Purpose**: Long-term reliability
- **Prestige**: Highest difficulty category

**9. Bandwidth Served Masters (6-month)**
- **Metric**: 6-month bandwidth performance
- **Eligibility**: 25+ relays minimum
- **Purpose**: Recent bandwidth serving excellence

**10. Bandwidth Served Legends (5-year)**
- **Metric**: 5-year bandwidth performance
- **Eligibility**: 25+ relays minimum
- **Purpose**: Long-term bandwidth excellence

#### 🌍 Diversity & Geographic Leadership (4 categories)

**11. Most Diverse Operators**
- **Metric**: Multi-factor diversity score
- **Factors**: Geographic, AS, platform diversity
- **Purpose**: Recognize well-distributed operations

**12. Platform Diversity Heroes**
- **Metric**: Non-Linux operational excellence
- **Purpose**: Encourage platform diversity
- **Importance**: Reduces monoculture risk

**13. Non-EU Leaders**
- **Metric**: Operations outside European Union
- **Purpose**: Geographic decentralization
- **Importance**: Jurisdiction diversity

**14. Frontier Builders**
- **Metric**: Operations in rare/underrepresented countries
- **Purpose**: Expand network geographic reach
- **Intelligence**: Uses rare country classification

#### 🏆 Innovation & Leadership (3 categories)

**15. Network Veterans**
- **Metric**: Scale-weighted operational tenure
- **Purpose**: Recognize long-term commitment
- **Calculation**: Time * relay importance

**16. IPv4 Address Leaders**
- **Metric**: Unique IPv4 address diversity
- **Purpose**: IP address distribution
- **Importance**: Resistance to blocking

**17. IPv6 Address Leaders**
- **Metric**: Unique IPv6 address diversity
- **Purpose**: IPv6 adoption leadership
- **Future**: Growing importance

### Leaderboard Features

**Pagination System**:
- Top 1-10 (primary view)
- Top 11-20 (secondary view)
- Top 21-25 (tertiary view)
- Independent per category
- JavaScript-free navigation

**Champion Badges**:
- Displayed on operator pages
- Multiple badges possible
- Visual recognition system
- Links back to leaderboards

---

## 🌍 Geographic Views

### Countries by Consensus Weight (`misc/countries-cw.html`)
Ranked by network influence per country:
- Shows relay count per country
- Consensus weight percentage
- Country flags
- Links to country pages

### Countries by Bandwidth (`misc/countries-bw.html`)
Ranked by bandwidth capacity per country:
- Total observed bandwidth
- Relay distribution
- Geographic intelligence

### Individual Country Pages (`country/[code]/`)
Per-country relay listing:
- All relays in specific country
- Country-level statistics
- Rare country classification (if applicable)

**Example**: `country/us/` (United States relays)

---

## 🔧 Platform & Infrastructure

### Platforms (`misc/platforms-bw.html`, etc.)
Relay distribution by operating system:
- Linux variants (most common)
- BSD variants
- Windows
- Other platforms

**Why it matters**: Platform diversity reduces vulnerability to OS-specific exploits.

### AS Numbers (`misc/as-bw.html`, etc.)
Relay distribution by Autonomous System:
- ISP/hosting provider diversity
- Concentration risk analysis
- Infrastructure redundancy

**Why it matters**: AS diversity prevents single points of failure.

---

## 📄 Individual Pages

### Relay Pages (`relay/[fingerprint].html`)
Complete technical specifications for each relay:

**Basic Information**:
- Nickname, fingerprint
- Running status, flags
- IP addresses (IPv4/IPv6)
- OR/Dir ports

**Performance Metrics**:
- Observed bandwidth
- Consensus weight
- Advertised bandwidth

**Uptime & Reliability**:
- Current uptime
- Historical uptime (1-month, 3-month, 6-month, 1-year, 5-year)
- Flag-specific uptime (Exit, Guard, Fast, Running)
- Statistical outlier detection
- Network percentile ranking

**Network Context**:
- First seen date
- Last restarted date
- Directory authorities recommending flags
- Country, platform, contact info
- Family relationships (if applicable)

**Intelligence Insights**:
- Performance correlation analysis
- Geographic intelligence
- Infrastructure analysis
- Optimization recommendations (if applicable)

### Operator/Contact Pages (`contact/[hash]/`)
Aggregated view of all relays by operator:

**Operator Statistics**:
- Total relay count
- Combined bandwidth
- Combined consensus weight
- Geographic distribution

**Reliability Portfolio**:
- Average uptime across all relays
- Multi-period analysis (1-month to 5-year)
- Network percentile positioning
- Statistical outliers identification

**AROI Achievements**:
- Champion badges earned
- Category rankings
- Diversity scores

**Relay Listing**:
- All relays operated
- Individual relay metrics
- Links to relay pages

### Family Pages (`family/[hash]/`)
Relay families (explicitly configured):
- Family member listing
- Collective statistics
- AROI and Contact navigation links
- Combined metrics

---

## 🏛️ Directory Authorities (`misc/authorities.html`)

**Tor Network Consensus Coordinators**

Monitors the 9-10 directory authorities that coordinate the Tor network:

**Authority Information**:
- Nickname and identity
- IP address and ports
- Geographic location
- Software version

**Health Metrics**:
- Uptime statistics
- Consensus participation
- Version compliance
- Z-score outlier detection

**Purpose**: Transparency into network governance infrastructure

---

## 📈 Sorted Views

Multiple views of the same data, sorted differently:

### By Bandwidth
- `misc/bandwidth-bw.html` - Relays by observed bandwidth
- `misc/countries-bw.html` - Countries by bandwidth
- `misc/as-bw.html` - AS numbers by bandwidth

### By Consensus Weight
- `misc/bandwidth-cw.html` - Relays by consensus weight
- `misc/countries-cw.html` - Countries by consensus weight
- `misc/as-cw.html` - AS numbers by consensus weight

### By First Seen
- `first_seen/[date]/` - Relays by join date
- Shows network growth over time
- Historical analysis

**Use Case**: Different perspectives on same data for various analysis needs

---

## 🔍 Search & Discovery

### Finding Relays

**By Fingerprint**: Direct URL
```
relay/[FULL_FINGERPRINT].html
```

**By Operator**: Contact pages
```
contact/[HASH]/
```

**By Country**: Country pages
```
country/[CODE]/
```

**By AS**: AS pages
```
as/[NUMBER]/
```

### Finding Operators

**Browse by Contact**: 
- Navigate to `misc/all.html`
- Find relay with desired contact
- Click contact link

**AROI Leaderboards**:
- Top operators visible immediately
- Multiple categories to explore

---

## 📊 Understanding Metrics

### Bandwidth
- **Observed Bandwidth**: What relay reports
- **Advertised Bandwidth**: What relay can handle
- **Display**: Can be Gbit/s (bits) or GB/s (bytes)

### Consensus Weight
- **Purpose**: Voting power in network
- **Range**: 0-100% of network total
- **Higher**: More client traffic routed through relay

### Uptime
- **Calculation**: Percentage of time relay was reachable
- **Periods**: 1-month, 3-month, 6-month, 1-year, 5-year
- **Purpose**: Reliability assessment

### Flags
- **Authority**: Directory authority
- **Exit**: Allows exit to internet
- **Guard**: Eligible to be entry guard
- **Fast**: Meets bandwidth threshold
- **Running**: Currently reachable
- **Stable**: Long uptime history
- **V2Dir**: Directory cache

---

## 🎯 Use Cases

### Relay Operators
- Monitor your relays
- Track performance metrics
- View uptime history
- Check AROI rankings
- Identify optimization opportunities

### Researchers
- Network analysis
- Geographic distribution studies
- Performance correlation research
- Operator behavior patterns
- Diversity assessments

### Tor Users
- Understand network composition
- See geographic distribution
- Check network health
- Learn about relay operators

### Network Monitors
- Track network changes
- Identify concentration risks
- Monitor authority health
- Analyze trends over time

---

## 🔧 Customization

All features are generated from templates in `allium/templates/`. See **[Development Guide](../development/README.md)** for customization.

---

## 📚 Related Documentation

- **[Quick Start](quick-start.md)** - Getting started
- **[Configuration](configuration.md)** - Customizing output
- **[Updating](updating.md)** - Keeping data fresh
- **[API Documentation](../api/README.md)** - Data sources

---

**Last Updated**: 2025-11-23  
**Feature Count**: 17 AROI categories + 10 health dashboard cards + comprehensive relay analysis
