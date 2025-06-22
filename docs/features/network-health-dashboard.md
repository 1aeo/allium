# Network Health Dashboard

## Overview

The Network Health Dashboard provides a comprehensive real-time overview of the Tor network's operational status and health metrics through a 10-card dashboard layout.

## Target Audiences

- **Relay Operators**: Monitor network context for their relays and identify optimization opportunities
- **Tor Foundation**: Track network health trends and identify areas needing attention
- **Researchers**: Access comprehensive network statistics and diversity metrics

## Dashboard Layout

The dashboard consists of 10 specialized cards organized across 4 rows:

### Row 1: Core Network Metrics
1. **Relay Counts** - Total relays, flags (Exit/Guard/Middle), and technical classifications
2. **Bandwidth Availability** - Network capacity and bandwidth distribution by relay role
3. **Relay Uptime** - Network reliability metrics across multiple time periods

### Row 2: Network Participation
4. **Operator Participation** - AROI operator counts, contact info, and family configuration
5. **Geographic Participation** - Country diversity, consensus weight distribution, jurisdiction analysis
6. **Provider Participation** - AS diversity, concentration metrics, and infrastructure distribution

### Row 3: Performance & Compliance
7. **Bandwidth Utilization** - CW/BW ratio analysis and performance efficiency metrics
8. **Version Compliance** - Tor version distribution and security compliance status
9. **Platform Distribution** - Operating system diversity across the network

### Row 4: Network Policies
10. **Exit Policies** - Exit relay restrictions and traffic allowance analysis

## Key Features

### IPv6 Adoption Tracking
- Relay-level IPv6 support (dual-stack vs IPv4-only)
- Operator-level IPv6 adoption metrics
- Bandwidth distribution by IP protocol support

### Performance Analytics
- CW/BW ratio calculations with network comparisons
- Statistical analysis (mean/median) for all bandwidth metrics
- Geographic and AS-level performance benchmarks

### Concentration Risk Analysis
- Geographic consensus weight distribution
- AS concentration with top provider analysis
- Intelligence alliance influence tracking (Five Eyes, Fourteen Eyes)

## Navigation

Access the dashboard at `/network-health.html` or through the main navigation menu.

## Technical Implementation

- **Ultra-optimized calculations** with single-pass relay processing
- **Real-time metrics** updated with each data refresh
- **Comprehensive tooltips** explaining all metrics and calculations
- **Responsive design** for various screen sizes 