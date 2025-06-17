# Flag Uptime System

## Overview

The Flag Uptime System provides specialized uptime monitoring for Tor relays based on their active network roles. Unlike general uptime statistics that track when a relay is simply online, flag uptime tracks reliability specifically when a relay is performing its primary network function (Exit, Guard, Fast, or Running).

This system was implemented to give operators and users better insight into relay performance in their actual network roles, helping identify relays that may be online but not effectively contributing to the Tor network in their designated capacity.

## Core Concepts

### Flag Priority System

Flag uptime follows a strict priority hierarchy to avoid displaying redundant information:

1. **Exit** (Highest Priority) - Relay allows exit traffic to the internet
2. **Guard** - Relay is suitable for use as an entry guard
3. **Fast** - Relay has sufficient bandwidth for general use
4. **Running** (Lowest Priority) - Relay is currently running and reachable

Only the highest priority flag's uptime data is displayed for each relay. This prevents cluttering the interface with multiple overlapping statistics.

### Calculation Methodology

Flag uptime is calculated using Onionoo API data with the following process:

1. **Data Collection**: Flag-specific uptime data is fetched from Onionoo for multiple time periods (1M, 6M, 1Y, 5Y)
2. **Normalization**: Raw Onionoo values (0-999 scale) are converted to percentages (0-100%)
3. **Averaging**: Multiple data points within each period are averaged
4. **Filtering**: Only periods with actual data are displayed
5. **Comparison**: Flag uptime is compared against overall relay uptime

### Display Logic

The system uses intelligent display logic to reduce visual clutter:

- **Match Overall Uptime**: When flag uptime matches overall uptime (within 0.1%), display shows "Match Overall Uptime" with actual percentages
- **Different Values**: When flag uptime differs significantly from overall uptime, show the specific flag uptime percentages
- **Clean Format**: Percentages are displayed without prefixes (removed G/F/E/R prefixes for cleaner presentation)

## Color Coding System

Flag uptime values use consistent color coding across the application:

- **Green**: High reliability (typically ≥95%)
- **Yellow**: Moderate reliability (typically 80-94%)
- **Red**: Low reliability (typically <80%)

The exact thresholds are calculated using statistical analysis of network-wide data to identify outliers and standard performance ranges.

## Integration Points

### Relay Detail Pages

Flag uptime is displayed in the relay information section with:
- Tooltip showing flag priority and calculation details
- Period-specific data (1M/6M/1Y/5Y) where available
- Color coding for quick visual assessment
- "Match Overall Uptime" logic for clean presentation

### Contact Operator Pages

Flag uptime integrates with operator reliability analysis:
- Aggregated flag reliability statistics across all operator relays
- Only includes flag data for flags the relay currently holds
- Prevents historical flag data from skewing current reliability calculations
- Consistent color coding with individual relay displays

### Leaderboard Integration

Flag uptime data supports AROI (Autonomous Relay Operator Identifier) leaderboard calculations:
- Contributes to operator reliability scoring
- Helps identify consistently high-performing operators
- Factors into diversity and reliability rankings

## Technical Implementation

### Data Processing

Flag uptime processing is optimized for performance:

1. **Single-Pass Processing**: All uptime calculations are performed in one pass through the data
2. **Shared Utilities**: Common calculations use the `uptime_utils.py` module to avoid duplication
3. **Template Optimization**: Pre-computed values are cached to reduce template rendering time
4. **Memory Efficiency**: Large datasets are processed incrementally to manage memory usage

### Statistical Analysis

The system includes sophisticated statistical analysis:

- **Outlier Detection**: Identifies relays with unusually high or low flag uptime
- **Network Baselines**: Calculates network-wide statistics for comparison
- **Threshold Calculation**: Dynamic thresholds based on network performance distribution
- **Confidence Intervals**: Statistical confidence measures for reliability ratings

## Configuration

### Display Periods

The system supports multiple time periods with dynamic display:
- **1M**: 1 month uptime data
- **6M**: 6 month uptime data  
- **1Y**: 1 year uptime data
- **5Y**: 5 year uptime data

Only periods with available data are shown, preventing empty or misleading displays.

### Thresholds

Color coding thresholds are configurable but default to:
- **Green Threshold**: ≥95% uptime
- **Yellow Threshold**: 80-94% uptime
- **Red Threshold**: <80% uptime

These can be adjusted based on network conditions and performance standards.

## Usage Examples

### Individual Relay Display

```
Flag Uptime (1M/6M/1Y/5Y): 98.5% / 97.2% / 96.8% / 95.1%
```

### Match Overall Uptime Display

```
Flag Uptime (1M/6M/1Y/5Y): Match Overall Uptime (98.5% / 97.2% / 96.8% / 95.1%)
```

### Operator Aggregate Display

```
Exit Flag Reliability: 96.2% (High) - 15 relays
Guard Flag Reliability: 94.1% (Good) - 8 relays
```

## Benefits

### For Relay Operators

- **Performance Insight**: Understand how effectively relays serve their intended network role
- **Troubleshooting**: Identify relays that are online but not functioning optimally in their role
- **Optimization**: Focus improvement efforts on relays with poor flag-specific performance

### For Network Users

- **Reliability Assessment**: Better understand which relays consistently perform their network functions
- **Selection Criteria**: Make informed decisions about relay selection based on role-specific performance
- **Network Health**: Gain insight into overall network reliability in key functions

### For Network Analysis

- **Performance Metrics**: Detailed statistics on network function performance
- **Trend Analysis**: Track performance changes over time across different relay roles
- **Capacity Planning**: Identify areas where network capacity or reliability needs improvement

## Future Enhancements

Potential future improvements to the flag uptime system:

- **Historical Trending**: Graphical displays of flag uptime trends over time
- **Predictive Analysis**: Machine learning models to predict flag reliability issues
- **Alert Systems**: Automated notifications for significant flag uptime degradation
- **Comparative Analysis**: Benchmarking against similar relays or network segments
- **Integration with Monitoring**: Automated monitoring system integration for proactive management

## Related Documentation

- [Relay Detail Page Layout Changes](relay-detail-page-layout-changes.md)
- [Contact Operator Page Enhancements](contact-operator-page-enhancements.md)
- [Uptime Processing Architecture](../architecture/uptime-processing-architecture.md)
- [AROI Leaderboard Integration](aroi-leaderboard/README.md) 