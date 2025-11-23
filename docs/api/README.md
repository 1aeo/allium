# API Documentation

Documentation for the Tor Project APIs that Allium integrates with.

## 🌐 Onionoo APIs

Allium integrates with three Onionoo API endpoints:

### 1. [Details API](onionoo-details.md)
**Endpoint**: `https://onionoo.torproject.org/details`  
**Purpose**: Core relay information (bandwidth, flags, location, technical details)  
**Memory**: ~400MB during processing  
**Update Frequency**: Hourly

### 2. [Uptime API](onionoo-uptime.md)
**Endpoint**: `https://onionoo.torproject.org/uptime`  
**Purpose**: Historical uptime statistics and flag history  
**Memory**: ~2GB during processing  
**Update Frequency**: Daily

### 3. [Bandwidth API](onionoo-bandwidth.md)
**Endpoint**: `https://onionoo.torproject.org/bandwidth`  
**Purpose**: Historical bandwidth statistics  
**Memory**: ~500MB during processing  
**Update Frequency**: Configurable (default: 12 hours)

## 🔧 Configuration

See [User Guide - Configuration](../user-guide/configuration.md) for API configuration options.

## 📚 External Resources

- **[Official Onionoo Documentation](https://metrics.torproject.org/onionoo.html)** - Complete API reference
- **[Tor Metrics](https://metrics.torproject.org/)** - Official Tor Project metrics
- **[CollecTor](https://collector.torproject.org/)** - Raw Tor network data

## 🎯 Quick Reference

| API | Size | Update | Primary Use |
|-----|------|--------|-------------|
| Details | ~20MB | Hourly | Relay listings, operator pages |
| Uptime | ~2GB | Daily | Reliability analysis, uptime metrics |
| Bandwidth | ~500MB | Configurable | Historical bandwidth, trends |

---

For implementation details, see [Architecture](../architecture/data-pipeline.md)
