# Directory Authorities Implementation

This document describes the implementation of the Directory Authorities page for the Allium project.

## Overview

The Directory Authorities page provides comprehensive monitoring of Tor directory authorities, including:
- Health metrics and consensus participation
- Uptime statistics with z-score analysis
- Network and geographical information

**Note:** Version compliance monitoring is commented out until real consensus-health API data is available.

## Files Created/Modified

### Core Implementation
- `lib/relays.py` - Added directory authority processing methods and general uptime data fetching
- `templates/misc-authorities.html` - Main template for the authorities page with ch? placeholders for version compliance
- `templates/macros.html` - Updated navigation to include authorities page
- `allium.py` - Added call to generate authorities page

### Testing
- `test_authorities.py` - Comprehensive test suite for authority functionality (version compliance test disabled)
- `test_template_rendering.py` - Template rendering and edge case tests updated for new attribute structure

## Data Sources

### Real-Time Data (Onionoo API)
- **Authority Details**: Extracted from main relay data (`self.json['relays']`) by filtering for "Authority" flag
  - Basic information: nickname, fingerprint, running status
  - Network details: AS number, country, platform, version
  - Contact information and timestamps
  
- **Uptime Data**: `https://onionoo.torproject.org/uptime` - **Fetched for ALL relays during initialization**
  - Historical uptime data for 1 month, 6 months, 1 year, 5 years
  - Merged into each relay object as `uptime_data` field
  - Used for directory authority uptime analysis and z-score computation
  - **Available for future relay uptime features**

### Placeholder Data (Future Implementation)
- **CollecTor API** (`ct?` prefix in template): 
  - Last vote timestamps from consensus documents
  - Bandwidth measurement data from bandwidth files
  
- **Consensus Health** (`ch?` prefix in template):
  - Real-time consensus metrics
  - Relay coverage statistics per authority
  - Consensus age and failure rates
  - **Version compliance tracking** (currently shows placeholders)

## Key Features

### Health Metrics Summary
- ~~Version compliance tracking~~ (replaced with ch? placeholders until real data available)
- Uptime analysis with statistical outlier detection
- Overall network health indicators

### Authority Table
- **Status Monitoring**: Online/offline status with last seen timestamps
- **Network Info**: AS number, provider name, country with flag icons
- **Performance**: Multi-period uptime with color-coded z-scores
- **~~Compliance~~**: Version checking with ch? placeholders
- **History**: First seen and last restarted dates

### Visual Indicators
- **Color-coded z-scores**: Green (good), yellow (normal), red (problematic)
- **Problem highlighting**: Authorities with issues shown in red (based on uptime and running status)
- **Status icons**: Online (🟢) / Offline (🔴) indicators

## Implementation Details

### Data Processing (`lib/relays.py`)

#### Enhanced Initialization Flow
1. **`_fetch_onionoo_details()`** - Fetches relay details for all relays
2. **`_fetch_onionoo_uptime()`** - **NEW: Fetches uptime data for ALL relays and merges into relay objects**
3. **Processing methods** - Work with the complete dataset (details + uptime)

#### `_fetch_onionoo_uptime()`
- **Architectural improvement**: Fetches uptime data for all ~7000 relays upfront
- Merges uptime data into each relay object as `uptime_data` field
- Provides foundation for future relay uptime analysis features
- Handles network errors gracefully with empty uptime data fallback
- **Performance**: Single uptime API call instead of targeted calls

#### `_process_directory_authorities()`
- Filters directory authorities from already-fetched relay data
- **Uses stored uptime data** from `relay['uptime_data']` instead of making separate API calls
- Calculates average uptime percentages for multiple periods
- Computes z-scores for uptime comparison
- Sorts authorities alphabetically for consistent display
- **Cleaned up**: Only includes fields actually used in template (removed unused or_addresses, dir_address)
- **Version compliance**: Commented out until real consensus-health data available

#### `_calculate_average_uptime(uptime_data)`
- Processes Onionoo uptime data format
- Handles missing values and converts to percentages
- Returns None for invalid/missing data

#### `write_misc()` - Directory Authorities Integration
- **Detects `misc-authorities.html` template** and automatically processes directory authorities
- **No separate function needed**: Directory authorities processing integrated directly into standard workflow
- Stores authority data and summary as class attributes for template access
- Calculates summary statistics for uptime analysis (version compliance disabled)
- **Consistent with other misc pages**: Uses same rendering pipeline as families, networks, contacts, etc.

### Template Structure (`templates/misc-authorities.html`)

#### Summary Section
- Consensus health overview (with `ch?` placeholders)
- Directory authority metrics summary
- **Version compliance**: ch? placeholders instead of real data
- Uptime analysis with real z-score data

#### Main Table
- Comprehensive authority information using real Onionoo data
- **Version compliance column**: ch? placeholder instead of computed values
- Placeholder columns for future CollecTor/consensus-health data

#### Template Access Pattern
- Uses `relays.authorities_data` instead of separate `authorities` variable
- Uses `relays.authorities_summary` for summary statistics
- Consistent with other Allium template patterns via `write_misc()`

### Statistical Analysis

#### Z-Score Calculation
- Based on 1-month uptime compared to all authorities
- Used to identify outliers and problematic authorities
- Thresholds:
  - Above +0.3: Above average (green)
  - -0.5 to +0.3: Normal range (yellow)
  - Below -2.0: Problematic (red)

#### ~~Version Compliance~~ (Disabled)
- ~~Compares authority versions against recommended version~~
- **Replaced with ch? placeholders** until consensus-health integration
- Will use real recommended version data when available

## Architectural Benefits

### Current Improvements
- **Reduced API calls**: Single uptime call for all relays vs. targeted authority calls
- **Better performance**: One network request instead of multiple
- **Data consistency**: All relay data fetched at same time
- **Cleaner code**: Uses standard `write_misc()` method, no custom template handling
- **Optimized data**: Only stores fields actually used in template
- **Better separation**: Real data vs. placeholder data clearly marked

### Future Extensibility
The comprehensive uptime dataset enables future features:
- **Relay uptime analysis pages**: Compare uptime across relay types
- **Uptime-based sorting/filtering**: Sort relays by reliability
- **Network health metrics**: Overall network uptime statistics
- **Relay comparison tools**: Side-by-side uptime comparisons
- **Historical trend analysis**: Uptime changes over time

## Testing

### Unit Tests (`test_authorities.py`)
- **Data Processing**: Uptime calculation and z-score computation
- **Network Handling**: Sequential API calls (details + uptime) and error scenarios
- **Integration**: Full workflow testing with merged uptime data and write_misc usage
- **Edge Cases**: Missing uptime data and invalid responses
- **Version Compliance**: Test disabled (commented out) until real data available

### Template Tests (`test_template_rendering.py`)
- **Compilation**: Template syntax validation
- **Rendering**: Output with new attribute structure (`relays.authorities_data`, `relays.authorities_summary`)
- **Edge Cases**: Empty data and None values
- **Structure**: HTML validity and content checks

## Usage

### Generation
The authorities page is automatically generated when running allium.py:

```bash
python3 allium.py --out ./www --onionoo-url https://onionoo.torproject.org/details
```

### Output
- File: `./www/misc/authorities.html`
- Navigation: Accessible via "Directory Authorities" menu item
- Updates: Refreshes every 30 minutes with new Onionoo data

## Future Enhancements

### Data Integration
1. **Consensus-Health Integration**:
   - Replace `ch?` placeholders with real API data
   - Add real version compliance monitoring
   - Include relay coverage statistics per authority
   - Add consensus failure metrics

2. **CollecTor API Integration**:
   - Parse consensus documents for vote timestamps
   - Extract bandwidth measurements from bandwidth files
   - Add real-time voting status

### New Features Enabled by Uptime Data
1. **Relay Uptime Analysis**:
   - Dedicated relay uptime comparison pages
   - Uptime trend visualization
   - Reliability rankings

2. **Network Health Dashboard**:
   - Overall network uptime statistics
   - Uptime distribution analysis
   - Historical reliability trends

3. **Enhanced Monitoring**:
   - Email alerts for relay downtime
   - Performance degradation detection
   - Geographic uptime analysis

## Dependencies

### Python Packages
- `statistics` - For z-score calculation
- `urllib.request` - For API calls
- `json` - For data parsing
- `jinja2` - For template rendering

### External APIs
- **Onionoo API** - Real-time relay and authority data (details + uptime for all relays)
- **CollecTor API** - Historical consensus and bandwidth data (future)
- **Consensus-Health** - Processed health metrics and version compliance (future)

## Error Handling

### Network Failures
- Graceful degradation when APIs are unavailable
- Error logging for debugging
- Fallback to cached data when possible

### Data Validation
- Handles missing or malformed API responses
- Validates uptime data format and ranges
- Filters out invalid authority entries

### Template Safety
- Safe handling of None values
- Conditional rendering for missing data
- Default values for incomplete information
- ch? placeholders for unavailable external data

This implementation provides a solid foundation for monitoring Tor directory authority health while establishing the infrastructure for comprehensive relay uptime analysis across the entire network. The separation of real data (Onionoo) from placeholder data (ch?, ct?) makes it clear what functionality is available now vs. future enhancements. 