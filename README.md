# Allium

[![CI/CD Pipeline](https://github.com/1aeo/allium/workflows/Allium%20CI/CD%20Pipeline/badge.svg)](https://github.com/1aeo/allium/actions)

**Advanced Tor Relay Analytics & Metrics Platform** - A powerful, security-hardened static site generator that creates comprehensive Tor relay metrics, statistics, and operator leaderboards from Onionoo API data.

## 🚀 Quick Start
**One-command setup** (recommended):
```bash
curl -sSL https://raw.githubusercontent.com/1aeo/allium/master/setup.sh | bash
```

**Manual installation**:
```bash
git clone https://github.com/1aeo/allium.git && cd allium
pip3 install -r config/requirements.txt
cd allium && python3 allium.py --progress
cd www && python3 -m http.server 8000
# Visit http://localhost:8000
```

**⚡ Update data**: `cd allium && python3 allium.py --progress`

## 📋 Table of Contents

- [🚀 Key Features](#-key-features)
- [🌐 API Data Sources](#-api-data-sources)  
- [📋 Usage & Configuration](#-usage--configuration)
- [📊 Generated Content](#-generated-content)
- [🌍 AROI Leaderboards](#-aroi-leaderboards)
- [🔒 Security & Performance](#-security--performance)
- [🛠️ Requirements](#️-requirements)
- [🤝 Contributing](#-contributing)
- [📷 Screenshots](#-screenshots)
- [📄 License](#-license)

## 🚀 Key Features

### Core Analytics
- **Complete relay metrics** with advanced sorting and filtering
- **Geographic distribution analysis** with rare country intelligence
- **Platform and AS diversity tracking** across the network
- **Bandwidth and consensus weight analytics** with multiple viewing modes

### Enhanced User Interface 🎨
- **Optimized contact pages** with efficient two-column layout (50% space reduction)
- **Enhanced operator profiles** with streamlined reliability metrics and network uptime percentiles
- **Network uptime percentile analysis** showing operator positioning within network performance distribution
- **Enhanced family pages** with AROI and Contact bullets for better navigation
- **Country display improvements** with full country names and tooltips
- **Improved information density** while preserving all analytical data
- **Responsive design** with mobile-friendly layouts
- **JavaScript-free pagination** for AROI leaderboards with independent category navigation

### AROI Leaderboard System 🏆
- **15 specialized leaderboards** for authenticated relay operators (includes Guard/Exit Authority, IPv4/IPv6 unique address categories)
- **Paginated rankings** with 1-10, 11-20, 21-25 views per category for improved navigation
- **Independent pagination** - each category manages its own page state
- **CSS-only navigation** using `:target` selectors for maximum security and performance
- **Reliability scoring system** with 6-month and 5-year average uptime analysis
- **Simplified reliability scoring** using average uptime (no bandwidth weighting)
- **25+ relay eligibility filter** ensuring statistical significance for reliability categories
- **Operator achievement tracking** across multiple dimensions
- **Geographic diversity scoring** with frontier country recognition
- **Platform diversity metrics** highlighting technical leadership
- **Network address diversity** with IPv4/IPv6 unique address leaderboards

### Security & Performance 🔒
- **XSS-hardened templates** with comprehensive input sanitization
- **Static generation** for maximum performance and security
- **Memory-efficient processing** with real-time monitoring
- **Parallel API fetching** (27s vs 31s sequential)
- **Template optimization** with logic moved from Jinja2 to Python for better performance
- **Pre-computed display data** reducing template rendering complexity

### Network Health Dashboard 📊
- **Comprehensive network monitoring** with 10-card dashboard layout
- **Real-time network metrics** including relay counts, bandwidth stats, uptime analysis
- **IPv6 adoption tracking** at relay, operator, and network levels
- **Geographic and provider diversity** with concentration risk analysis
- **Performance analytics** with CW/BW ratio calculations and percentile rankings

### Directory Authorities Monitoring 🏛️
- **Authority health tracking** with uptime statistics and Z-score outlier detection
- **Network consensus monitoring** displaying authority status, geographic distribution, and performance metrics

### Intelligence Features 🧠
- **Dynamic classification system** replacing hardcoded country lists
- **Multi-factor analysis** (relay count, network %, geopolitical factors)
- **Tier-based country rankings** (Legendary, Epic, Rare, Emerging, Common)
- **Geopolitical awareness** in country scoring algorithms
- **Performance efficiency analysis** with CW/BW ratio calculations, network comparisons, and percentile rankings
- **Underutilized relay detection** identifying optimization opportunities for operators

## 🌐 API Data Sources

allium integrates with multiple Tor Project APIs:

### Onionoo Details API
- **URL**: `https://onionoo.torproject.org/details`
- **Purpose**: Core relay information (bandwidth, flags, location, technical details)
- **Memory Usage**: ~400MB during processing
- **Usage**: Primary data source for relay listings, geographic analysis, operator metrics

**Sample Data**:
```json
{
  "relays": [{
    "fingerprint": "9695DFC35FFEB861329B9F1AB04C46397020CE31",
    "nickname": "moria1",
    "running": true,
    "flags": ["Authority", "Fast", "Running", "Stable"],
    "consensus_weight": 27,
    "country": "us",
    "platform": "Tor 0.4.8.7 on Linux",
    "observed_bandwidth": 20971520
  }]
}
```

### Onionoo Uptime API  
- **URL**: `https://onionoo.torproject.org/uptime`
- **Purpose**: Historical uptime statistics and flag history for reliability analysis
- **Memory Usage**: ~2GB during processing (large historical dataset)
- **Usage**: Enhanced relay reliability metrics and performance analysis

### Onionoo Bandwidth API
- **URL**: `https://onionoo.torproject.org/bandwidth`
- **Purpose**: Historical bandwidth statistics for trend analysis and optimization
- **Cache**: Configurable cache time (default: 12 hours)
- **Usage**: Historical bandwidth data for performance tracking and analysis

**Sample Data**:
```json
{
  "relays": [{
    "fingerprint": "9695DFC35FFEB861329B9F1AB04C46397020CE31",
    "uptime": {
      "1_month": "978",
      "1_year": "945"
    },
    "flags": {
      "Running": {"1_month": "987", "1_year": "954"},
      "Guard": {"1_month": "974", "1_year": "943"}
    }
  }]
}
```

**Performance Features**: Parallel API fetching, HTTP conditional requests, graceful fallback to cached data

## 📋 Usage & Configuration

```bash
./allium.py [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--out` | `./www` | Output directory for generated files |
| `--onionoo-url` | `https://onionoo.torproject.org/details` | Onionoo API endpoint |
| `--onionoo-bandwidth-url` | `https://onionoo.torproject.org/bandwidth` | Historical bandwidth API endpoint |
| `--bandwidth-cache-hours` | `12` | Cache time for historical bandwidth data (hours) |
| `--display-bandwidth-units` | `bits` | Units for bandwidth display (`bits` or `bytes`) |
| `--progress` | `false` | Show detailed progress with memory usage |

**Examples**:
```bash
# Generate with progress tracking
./allium.py --progress

# Custom output with bytes units
./allium.py --out /var/www/tor-metrics --display-bandwidth-units bytes
```

## 📊 Generated Content

### Main Analytics
- **Index page** - Top 500 relays by consensus weight
- **Complete relay listing** - All active relays with filtering
- **AROI leaderboards** - 12 specialized operator categories
- **Geographic analysis** - Rare country intelligence

### Categorized Views
- **By Country** - Rare/frontier country analysis
- **By Platform** - OS and version distributions  
- **By AS Number** - Autonomous system diversity
- **By Contact** - Operator family groupings
- **By Bandwidth/Weight** - Multiple sorting options

### Individual Pages
- **Per-relay details** - Complete technical specifications
- **Operator profiles** - Achievement metrics and diversity scoring
- **Geographic summaries** - Country-level statistics
- **Network Health Dashboard** - Real-time network monitoring and analysis
- **Directory Authorities** - Consensus health tracking with uptime analysis and version compliance monitoring

## 🌍 AROI Leaderboards

Fifteen specialized categories tracking authenticated operator achievements:

1. **Bandwidth Capacity Champions** - Total bandwidth contributed
2. **Consensus Weight Leaders** - Network authority holders
3. **Exit Authority Champions** - Exit traffic facilitators
4. **Guard Authority Champions** - Guard traffic facilitators
5. **Exit Gate Keepers** - Number of exit relays operated
6. **Guard Champions** - Number of guard relays operated
7. **Most Diverse Operators** - Geographic, platform, and network diversity
8. **Platform Diversity Heroes** - Non-Linux champions promoting OS diversity
9. **Non-EU Leaders** - Geographic champions expanding Tor outside EU
10. **Frontier Builders** - Operators in rare/underrepresented countries
11. **Network Veterans** - Longest-serving operators
12. **Reliability Masters** - 6-month average uptime champions (25+ relays)
13. **Legacy Titans** - 5-year average uptime champions (25+ relays)
14. **IPv4 Address Diversity** - Unique IPv4 address distribution leaders
15. **IPv6 Address Diversity** - Unique IPv6 address distribution leaders

## 🔒 Security & Performance

- **Global XSS protection** via Jinja2 autoescape
- **Input sanitization** for all external data sources
- **Static generation** eliminating server-side vulnerabilities  
- **No JavaScript dependencies** for maximum security
- **Real-time memory usage tracking** during generation
- **Optimized template rendering** with security hardening
- **Scalable architecture** supporting large relay counts

## 🛠️ Requirements

### Production (Minimal)
- **Python 3.8+**
- **Jinja2 ≥2.11.2**

### Development (Additional)
- **pytest ≥6.0.0** - Unit testing framework
- **pytest-cov ≥2.10.0** - Coverage reporting
- **flake8 ≥3.8.0** - Code style checker
- **bandit ≥1.7.0** - Security vulnerability scanner
- **safety ≥1.10.0** - Dependency vulnerability checker
- **djlint ≥1.0.0** - HTML/template linter
- **memory-profiler ≥0.60.0** - Memory usage profiling

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed setup instructions.

### 🧪 Developer Setup

**Quick developer setup** (includes testing and linting tools):
```bash
curl -sSL https://raw.githubusercontent.com/1aeo/allium/master/setup.sh | bash -s -- --dev
```

**Manual developer setup**:
```bash
git clone https://github.com/1aeo/allium.git && cd allium
python3 -m venv venv && source venv/bin/activate
pip install -r config/requirements-dev.txt
cd allium && python3 allium.py --progress
```

**Run tests**: `pytest` • **Lint code**: `flake8 .` • **Security scan**: `bandit -r .`

### 🎯 Contributing Areas

Areas where contributions are particularly welcome:
- Security enhancements and vulnerability reporting
- Analytics improvements and new leaderboard categories
- Geographic intelligence and country classification updates
- Performance optimizations and memory efficiency
- Template improvements and UI enhancements

## 📷 Screenshots

### AROI Leaderboard - Top 3 and Top 6 Champions
![AROI Leaderboard Top 3 and Top 6](docs/screenshots/aroi-leaderboard-top3-top6.png)

Main AROI leaderboard showing top operators across categories with expandable views highlighting achievements in bandwidth, consensus weight, and network diversity.

### AROI Leaderboard - Top 25 Bandwidth Capacity Champions
![AROI Leaderboard Top 25 Bandwidth](docs/screenshots/aroi-leaderboard-top25-bandwidth.png)

Detailed ranking of the top 25 bandwidth contributors showing authenticated relay operators with precise measurements and network impact metrics.

### AROI Leaderboard - Champions Badges
![AROI Leaderboard Champions Badges](docs/screenshots/aroi-leaderboard-champions-badges.png)

Achievement badge system displaying operator accomplishments including geographic diversity, platform diversity, frontier building, and network veteran status.

### Browse by Contact
![Browse by Contact](docs/screenshots/browse-by-contact.png)

Contact-based interface for exploring relay operators grouped by contact information, enabling easy navigation of operator families and collective contributions.

### Browse by Contact - 1aeo Example
![Browse by Contact 1aeo](docs/screenshots/browse-by-contact-1aeo.png.jpg)

Individual operator profile showing relay family details, geographic distribution, and technical specifications across their network infrastructure.

## 📄 License

**UNLICENSE** (public domain)

**Third-Party Assets**: Country flags (GoSquared), Relay flags (The Tor Project)

## 🔗 References

- [Original allium](https://git.jordan.im/allium) - Fork source
- [Tor Metrics Project](https://metrics.torproject.org/) - Official metrics (inspiration)
- [Onionoo API](https://onionoo.torproject.org/) - Tor relay data source
- [Tor Project](https://www.torproject.org/) - Privacy and anonymity network

---

**allium** - Empowering Tor network analysis with intelligence, security, and performance.
