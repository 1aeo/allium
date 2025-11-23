# Directory Authorities Proposals & Documentation

This directory contains all proposal work, documentation, and mockups related to Tor Directory Authorities monitoring in Allium.

## Contents

### Mockups
- **`authorities-page-mockup.html`** - Generated HTML page showing current directory authorities monitoring
  - Real output from allium.py showing actual authority data and layout
  - Includes working uptime statistics and basic functionality
  - Contains placeholders for future data integration (consensus-health API, CollecTor API)
  - Shows current implementation status and design for monitoring directory authority health

### Documentation
- **`directory-authorities-monitoring.md`** - Comprehensive implementation documentation
  - Technical details of the directory authorities page implementation
  - Data sources and API integration plans
  - Testing strategy and architectural benefits
  - Future enhancement roadmap

## Purpose

The Directory Authorities page provides comprehensive monitoring of Tor directory authorities, including:

- **Health Metrics**: Consensus participation and network status
- **Uptime Analysis**: Statistical analysis with z-score outlier detection  
- **Version Compliance**: Tracking authorities on recommended Tor versions
- **Network Information**: AS numbers, geographical distribution
- **Performance Monitoring**: Bandwidth measurements and vote tracking

## Implementation Status

- ✅ **Core Template**: HTML mockup with complete layout and styling
- ✅ **Uptime Integration**: Real-time uptime data from Onionoo API
- ✅ **Statistical Analysis**: Z-score calculation for uptime outliers
- 🚧 **Version Compliance**: Placeholder data (pending consensus-health API)
- 🚧 **Vote Tracking**: Placeholder data (pending CollecTor API integration)
- 🚧 **Bandwidth Measurements**: Placeholder data (pending CollecTor API)

## Data Sources

### Current (Real Data)
- **Onionoo API**: Authority details, uptime statistics, network information

### Planned (Placeholder Data)
- **Consensus-Health API**: Version compliance, consensus metrics, relay coverage
- **CollecTor API**: Vote timestamps, bandwidth measurements

## Navigation

This feature is accessible via the "Directory Authorities" menu item in the main Allium navigation and generates to `www/misc/authorities.html`.

## Related Work

See also:
- `docs/features/multi-api-implementation-plan.md` - Overall API integration strategy
- `docs/proposals/network_health_dashboard_mockups.md` - Related network monitoring proposals
- `tests/test_authorities.py` - Test suite for directory authorities functionality 