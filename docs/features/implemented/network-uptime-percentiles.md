# Network Uptime Percentiles

## Overview
Contact pages now display network-wide uptime percentiles, showing where each operator's reliability ranks within the entire Tor network distribution.

## What You'll See

On contact detail pages, under **Relay Reliability**, you'll find:

```
Network Uptime (6mo): 5th Pct: 85%, 25th Pct: 95%, 50th Pct: 98%, Operator: 99%, 75th Pct: 99%
```

## Understanding the Display

- **Percentiles**: Show network-wide performance distribution
- **Operator position**: Your operator's ranking within the network
- **Color coding**: 
  - 🟢 **Green**: Above 50th percentile (better than median)
  - 🟡 **Yellow**: Below median but above 5th percentile
  - 🔴 **Red**: Below 5th percentile

## Data Source

- **Period**: 6-month rolling window
- **Calculation**: Daily uptime averages from Onionoo API
- **Network scope**: All active relays with operational data
- **Update frequency**: Refreshed with each site generation

## Implementation Details

- **Performance optimized**: Network percentiles calculated once and cached
- **Mathematically robust**: Uses median-based statistics for accuracy
- **Inclusive approach**: Includes all operational relays (>1% uptime) for honest network representation
- **Quality filtering**: Requires minimum 30 data points for statistical reliability

## Benefits for Operators

1. **Benchmarking**: Compare your reliability against network standards
2. **Performance goals**: Understand what constitutes good/excellent uptime
3. **Network context**: See your contribution to overall network health
4. **Improvement guidance**: Clear targets for reliability enhancement

---

*This feature provides transparent, data-driven insights into relay performance within the broader Tor network ecosystem.* 