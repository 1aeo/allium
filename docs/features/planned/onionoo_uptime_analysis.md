# Onionoo Uptime Endpoint Analysis

## Overview

The Onionoo protocol is a web service developed by the Tor Project for querying information about Tor relays and bridges. This analysis focuses specifically on the uptime endpoint, which provides historical uptime statistics for Tor relays.

## Endpoint Details

**URL:** `https://onionoo.torproject.org/uptime`
**Method:** GET
**Response Format:** JSON

## Data Structure

The uptime endpoint returns a JSON response containing an array of relay objects. Each relay object has the following structure:

### Relay Object Fields

- **fingerprint**: Unique identifier for the relay (40-character hexadecimal string)
- **uptime**: Object containing uptime statistics across different time periods
- **flags**: Object containing flag history across different time periods

### Time Periods

The endpoint provides data for the following time periods:
- `1_month`: Last 30 days
- `6_months`: Last 180 days  
- `1_year`: Last 365 days
- `5_years`: Last 1,825 days

### Time Period Data Structure

Each time period contains:
- **first**: Timestamp of the first data point (Unix timestamp in seconds)
- **last**: Timestamp of the last data point (Unix timestamp in seconds)
- **interval**: Time interval between data points in seconds
- **factor**: Calculation factor for converting raw values
- **count**: Number of data points in the series
- **values**: Array of integer values representing the actual data

## Uptime Values

### Encoding
- Uptime values are encoded as integers
- **999** = 99.9% uptime
- **0** = 0% uptime
- Values represent uptime percentages over time intervals
- Scale: 0-999 (where 999 = 99.9%)

### Interpretation
- Most active relays consistently show 999 values (high uptime)
- Periods of 0 values indicate downtime or relay unavailability
- Historical data allows tracking of relay reliability over time

## Flag Categories

The flags section tracks when relays had specific capabilities or statuses:

### Flag Types
- **Exit**: Relay allows exit traffic
- **Fast**: Relay has sufficient bandwidth
- **Guard**: Relay is suitable as a guard node
- **HSDir**: Relay serves as a hidden service directory
- **Running**: Relay is currently running
- **Stable**: Relay has been stable over time
- **StaleDesc**: Relay descriptor is stale
- **V2Dir**: Relay serves as a directory server
- **Valid**: Relay has a valid descriptor

### Flag Data Structure
Each flag category uses the same time period structure as uptime data, allowing historical analysis of relay capabilities.

## Example Data Points

### Sample Relay Fingerprints
- `0077BCBA7244DB3E6A5ED2746E86170066684887`
- `009C86B4155629A8E4040A1DBA81CAD3C0E48A7B`
- `00A8E8D889C2A5A4F0F52999A6B86BF5A1A87F56`

### Typical Data Patterns
- **New relays**: Show consistent 999 values for recent periods
- **Established relays**: Have historical data spanning multiple years
- **Intermittent relays**: Show patterns of 0 and 999 values indicating periods of downtime

## API Response Characteristics

### Data Volume
- The endpoint returns data for thousands of relays
- Response size can be substantial due to historical data
- Data is efficiently encoded using integer arrays

### Update Frequency
- Data appears to be updated regularly
- Historical data is preserved for long-term analysis
- Recent data points are more frequent than historical ones

## Use Cases

### Network Analysis
- Monitor overall Tor network health
- Identify reliable long-running relays
- Analyze network stability trends

### Relay Operator Insights
- Track individual relay performance
- Compare relay uptime across different time periods
- Monitor flag status changes over time

### Research Applications
- Study Tor network evolution
- Analyze relay churn patterns
- Investigate correlation between uptime and relay flags

## Technical Implementation Notes

### Data Access
- No authentication required for public endpoint
- Standard HTTP GET request
- JSON response format for easy parsing

### Performance Considerations
- Large response payload
- Consider pagination or filtering if available
- Implement appropriate caching strategies

## Limitations and Considerations

### Data Accuracy
- Uptime measurements based on Tor directory authority observations
- May not reflect actual relay availability from user perspective
- Network connectivity issues could affect measurements

### Historical Data
- Older data may have different granularity
- Some relays may have incomplete historical records
- Data retention policies may limit historical depth

## Related Endpoints

The Onionoo service provides additional endpoints for comprehensive relay analysis:
- `/summary`: Basic relay information
- `/details`: Detailed relay information
- `/bandwidth`: Bandwidth statistics
- `/weights`: Relay weight information
- `/clients`: Client statistics

## Conclusion

The Onionoo uptime endpoint provides valuable insights into Tor network reliability and relay performance. The structured historical data enables both real-time monitoring and long-term trend analysis, making it an essential resource for network operators, researchers, and anyone interested in Tor network health.

---

*Analysis conducted on the Onionoo uptime endpoint: https://onionoo.torproject.org/uptime*
*Documentation created as part of Tor network research and analysis*