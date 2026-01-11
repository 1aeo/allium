# Allium

[![CI/CD Pipeline](https://github.com/1aeo/allium/workflows/Allium%20CI/CD%20Pipeline/badge.svg)](https://github.com/1aeo/allium/actions)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: Unlicense](https://img.shields.io/badge/license-Public%20Domain-blue.svg)](https://unlicense.org/)

**Advanced Tor Relay Analytics & Metrics Platform** — a security-hardened static site generator that produces a browsable Tor relay analytics site from Onionoo API data.

### What You Get

- **Static site output** in `allium/www/` — serve locally or deploy anywhere static files can be hosted
- **Relay + operator analytics** — bandwidth, consensus weight, diversity views, uptime/reliability, and more
- **AROI leaderboards** — 18 specialized categories recognizing authenticated relay operators

### Why Allium?

- **Privacy-First** — Generates static HTML requiring no server-side processing or JavaScript dependencies
- **Security-Hardened** — Input sanitization, XSS protection, and dependency scanning built-in
- **Deep Intelligence** — Goes beyond basic metrics with operator leaderboards and 6-layer analytics engine

*Originally forked from [allium](https://git.jordan.im/allium), this version adds extensive analytics, operator leaderboards, and intelligence features.*

![AROI Leaderboard Preview](docs/screenshots/aroi-leaderboard-top3-top6.png)

## Quick Start

### One-command setup (recommended)

```bash
curl -sSL https://raw.githubusercontent.com/1aeo/allium/master/setup.sh | bash
```

### Safer install (inspect script first)

```bash
curl -fsSL https://raw.githubusercontent.com/1aeo/allium/master/setup.sh -o setup.sh
less setup.sh
bash setup.sh
```

### Manual installation

```bash
git clone https://github.com/1aeo/allium.git && cd allium

# Create and activate virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install -r config/requirements.txt
cd allium && python3 allium.py --progress
cd www && python3 -m http.server 8000
# Visit http://localhost:8000
```

### Common Tasks

| Task | Command |
|------|---------|
| Generate site | `cd allium && python3 allium.py --progress` |
| Serve output | `cd allium/www && python3 -m http.server 8000` |
| Custom output dir | `python3 allium.py --out /path/to/site` |
| Minimal memory mode | `python3 allium.py --apis details --progress` |

### Resource Notes

- **Memory**: Plan for **~3GB RAM** available (the uptime dataset alone peaks around ~2GB)
- **Time**: Full generation takes ~2-5 minutes producing ~21,700 HTML pages
- **Disk**: Output is approximately ~500MB

## Table of Contents

- [Key Features](#key-features)
- [API Data Sources](#api-data-sources)
- [Usage & Configuration](#usage--configuration)
- [Generated Content](#generated-content)
- [AROI Leaderboards](#aroi-leaderboards)
- [Security & Performance](#security--performance)
- [Requirements](#requirements)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [Screenshots](#screenshots)
- [License](#license)
- [References](#references)

## Key Features

<details>
<summary><strong>Core Analytics</strong></summary>

- **Complete relay metrics** with advanced sorting and filtering
- **Geographic distribution analysis** with rare country intelligence
- **Platform and AS diversity tracking** across the network
- **Bandwidth and consensus weight analytics** with multiple viewing modes

</details>

<details>
<summary><strong>Uptime Intelligence System ⏰</strong></summary>

- **Reliability Champions Leaderboard** with "Reliability Masters" (6-month) & "Legacy Titans" (5-year) categories
- **Comprehensive operator reliability portfolios** with multi-period analysis and network percentile positioning
- **Flag-specific uptime tracking** with intelligent priority system (Exit > Guard > Fast > Running)
- **Statistical outlier detection** identifying performance anomalies (≥2σ deviations)
- **Network Health Dashboard** with real-time uptime metrics and concentration risk analysis
- **Individual relay uptime display** with flag analysis and network context

</details>

<details>
<summary><strong>Enhanced User Interface 🎨</strong></summary>

- **Optimized contact pages** with streamlined reliability metrics and comprehensive analysis
- **Enhanced family pages** with AROI and Contact navigation
- **Country display improvements** with full country names and tooltips
- **Responsive design** with mobile-friendly layouts
- **JavaScript-free pagination** for AROI leaderboards with independent category navigation

</details>

<details>
<summary><strong>AROI Leaderboard System 🏆</strong></summary>

- **18 specialized leaderboards** for authenticated relay operators across all performance dimensions
- **Champion badge system** with elite performer recognition across categories
- **Paginated rankings** with 1-10, 11-20, 21-25 views per category
- **Independent pagination** — each category manages its own page state with CSS-only navigation
- **Reliability scoring system** with 6-month and 5-year average uptime analysis
- **Bandwidth served analysis** with historical performance tracking
- **25+ relay eligibility filter** ensuring statistical significance for reliability categories
- **Multi-dimensional scoring** across capacity, diversity, reliability, and innovation
- **Geographic diversity scoring** with frontier country recognition and non-EU leadership
- **Platform diversity metrics** highlighting technical leadership beyond Linux
- **Network address diversity** with IPv4/IPv6 unique address distribution tracking
- **Veteran recognition** with scale-weighted tenure analysis

</details>

<details>
<summary><strong>Network Health Dashboard 📊</strong></summary>

- **Comprehensive network monitoring** with 10-card dashboard layout
- **Real-time network metrics** including relay counts, bandwidth stats, uptime analysis
- **IPv6 adoption tracking** at relay, operator, and network levels
- **Geographic and provider diversity** with concentration risk analysis
- **Performance analytics** with CW/BW ratio calculations and percentile rankings

</details>

<details>
<summary><strong>Directory Authorities Monitoring 🏛️</strong></summary>

- **Authority health tracking** with uptime statistics and Z-score outlier detection
- **Network consensus monitoring** displaying authority status, geographic distribution, and performance metrics

</details>

<details>
<summary><strong>Intelligence Engine 🧠</strong></summary>

- **6-layer intelligence engine** with sub-millisecond analysis performance
- **Context analysis** with automatic relationship mapping and pattern detection
- **Performance correlation analysis** with CW/BW ratio intelligence and network benchmarking
- **Geographic intelligence** with concentration risk analysis and jurisdiction mapping
- **Infrastructure intelligence** with AS concentration and provider diversity assessment
- **Statistical intelligence** with network percentiles and outlier detection
- **22 template integration points** across contact pages, health dashboard, and relay info
- **Dynamic classification system** with tier-based country rankings
- **Underutilized relay detection** identifying optimization opportunities for operators

</details>

<details>
<summary><strong>Security & Performance 🔒</strong></summary>

- **XSS-hardened templates** with comprehensive input sanitization
- **Static generation** for maximum performance and security
- **Memory-efficient processing** with real-time monitoring
- **Parallel API fetching** (27s vs 31s sequential)
- **Template optimization** with logic moved from Jinja2 to Python for better performance
- **Pre-computed display data** reducing template rendering complexity

</details>

## API Data Sources

Allium integrates with multiple Tor Project APIs:

### Onionoo Details API

- **URL**: `https://onionoo.torproject.org/details`
- **Purpose**: Core relay information (bandwidth, flags, location, technical details)
- **Memory**: ~400MB during processing

<details>
<summary>Sample response</summary>

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

</details>

### Onionoo Uptime API

- **URL**: `https://onionoo.torproject.org/uptime`
- **Purpose**: Historical uptime statistics and flag history for reliability analysis
- **Memory**: ~2GB during processing (large historical dataset)

<details>
<summary>Sample response</summary>

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

</details>

### Onionoo Bandwidth API

- **URL**: `https://onionoo.torproject.org/bandwidth`
- **Purpose**: Historical bandwidth statistics for trend analysis
- **Cache**: Configurable (default: 12 hours)

**Performance Features**: Parallel API fetching, HTTP conditional requests, graceful fallback to cached data

## Usage & Configuration

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
| `--apis` | `all` | API sources to fetch (`all`, `details`, etc.) |

**Examples**:

```bash
# Generate with progress tracking
./allium.py --progress

# Custom output with bytes units
./allium.py --out /var/www/tor-metrics --display-bandwidth-units bytes

# Minimal memory mode (~400MB instead of ~2.4GB)
./allium.py --apis details --progress
```

## Generated Content

### Main Analytics

- **Index page** — Top 500 relays by consensus weight
- **Complete relay listing** — All active relays with filtering
- **AROI leaderboards** — 18 specialized operator categories
- **Network Health Dashboard** — Real-time network monitoring

### Categorized Views

- **By Country** — Rare/frontier country analysis
- **By Platform** — OS and version distributions
- **By AS Number** — Autonomous system diversity
- **By Contact** — Operator family groupings

### Individual Pages

- **Per-relay details** — Complete technical specifications
- **Operator profiles** — Achievement metrics and diversity scoring
- **Geographic summaries** — Country-level statistics
- **Directory Authorities** — Consensus health with uptime analysis

## AROI Leaderboards

Eighteen specialized categories tracking authenticated operator achievements:

<details>
<summary><strong>🚀 Capacity & Performance</strong></summary>

1. **Bandwidth Contributed** — Total observed bandwidth capacity
2. **Consensus Weight Authority** — Network routing control influence

</details>

<details>
<summary><strong>🛡️ Network Role Specialization</strong></summary>

3. **Exit Authority Champions** — Exit consensus weight control
4. **Guard Authority Champions** — Guard consensus weight control
5. **Exit Operators** — Exit relay infrastructure providers
6. **Guard Operators** — Guard relay infrastructure providers

</details>

<details>
<summary><strong>⏰ Reliability Excellence</strong> (25+ relays required)</summary>

7. **Reliability Masters** — 6-month average uptime
8. **Legacy Titans** — 5-year average uptime
9. **Bandwidth Served Masters** — 6-month bandwidth performance
10. **Bandwidth Served Legends** — 5-year bandwidth performance

</details>

<details>
<summary><strong>🌍 Diversity & Geographic Leadership</strong></summary>

11. **Most Diverse Operators** — Multi-factor diversity scoring
12. **Platform Diversity Heroes** — Non-Linux operational excellence
13. **Non-EU Leaders** — Geographic expansion beyond EU
14. **Frontier Builders** — Operations in underrepresented countries

</details>

<details>
<summary><strong>🏆 Innovation & Leadership</strong></summary>

15. **Network Veterans** — Scale-weighted operational tenure
16. **IPv4 Address Leaders** — Unique IPv4 address diversity
17. **IPv6 Address Leaders** — Unique IPv6 address diversity
18. **AROI Validation Champions** — Verified identity count

</details>

## Security & Performance

- **Global XSS protection** via Jinja2 autoescape
- **Input sanitization** for all external data sources
- **Static generation** eliminating server-side vulnerabilities
- **No JavaScript dependencies** for maximum security
- **Real-time memory usage tracking** during generation
- **Scalable architecture** supporting large relay counts

## Requirements

### Production (Minimal)

- **Python 3.8+**
- **Jinja2 ≥2.11.2**

### Development (Additional)

- **pytest ≥6.0.0** — Unit testing framework
- **pytest-cov ≥2.10.0** — Coverage reporting
- **flake8 ≥3.8.0** — Code style checker
- **bandit ≥1.7.0** — Security vulnerability scanner
- **safety ≥1.10.0** — Dependency vulnerability checker
- **djlint ≥1.0.0** — HTML/template linter
- **memory-profiler ≥0.60.0** — Memory usage profiling

## Documentation

Comprehensive documentation in [`docs/`](docs/):

### For Users

- **[Quick Start Guide](docs/user-guide/quick-start.md)** — Get running in 5 minutes
- **[Configuration Guide](docs/user-guide/configuration.md)** — All options and automation setup
- **[Deployment Guide](docs/user-guide/deployment.md)** — Web server setup
- **[Troubleshooting](docs/user-guide/troubleshooting.md)** — Common issues and solutions

### For Developers

- **[Architecture Overview](docs/architecture/overview.md)** — System design and data flow
- **[Testing Standards](docs/development/testing.md)** — Test naming and organization
- **[Security Guide](docs/development/security.md)** — Security best practices

### Additional Resources

- **[Documentation Index](docs/README.md)** — Full navigation
- **[Roadmap 2025-2026](docs/features/planned/allium-roadmap-2025.md)** — Future plans
- **[Current Capabilities](docs/reference/current-capabilities.md)** — All working features
- **[Planned Features](docs/features/planned/)** — What's coming next

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed instructions.

### Developer Setup

```bash
# Quick setup with dev dependencies
curl -sSL https://raw.githubusercontent.com/1aeo/allium/master/setup.sh | bash -s -- --dev

# Or manually:
git clone https://github.com/1aeo/allium.git && cd allium
python3 -m venv venv && source venv/bin/activate
pip install -r config/requirements-dev.txt
```

**Run tests**: `pytest` • **Lint**: `flake8 .` • **Security scan**: `bandit -r .`

### Contributing Areas

- Security enhancements and vulnerability reporting
- Analytics improvements and new leaderboard categories
- Geographic intelligence and country classification updates
- Performance optimizations and memory efficiency
- Template improvements and UI enhancements

## Screenshots

### AROI Leaderboard — Top 3 and Top 6 Champions

![AROI Leaderboard Top 3 and Top 6](docs/screenshots/aroi-leaderboard-top3-top6.png)

Main AROI leaderboard showing top operators across categories with expandable views.

### AROI Leaderboard — Top 25 Bandwidth Champions

![AROI Leaderboard Top 25 Bandwidth](docs/screenshots/aroi-leaderboard-top25-bandwidth.png)

Detailed ranking of top bandwidth contributors with network impact metrics.

### AROI Leaderboard — Champions Badges

![AROI Leaderboard Champions Badges](docs/screenshots/aroi-leaderboard-champions-badges.png)

Achievement badge system displaying operator accomplishments.

### Browse by Contact

![Browse by Contact](docs/screenshots/browse-by-contact.png)

Contact-based interface for exploring relay operators grouped by contact information.

### Browse by Contact — 1aeo Example

![Browse by Contact 1aeo](docs/screenshots/browse-by-contact-1aeo.png)

Individual operator profile showing relay family details and geographic distribution.

## License

**UNLICENSE** (public domain)

**Third-Party Assets**: Country flags (GoSquared), Relay flags (The Tor Project)

## References

- [Original allium](https://git.jordan.im/allium) — Fork source
- [Tor Metrics Project](https://metrics.torproject.org/) — Official metrics (inspiration)
- [Onionoo API](https://onionoo.torproject.org/) — Tor relay data source
- [Tor Project](https://www.torproject.org/) — Privacy and anonymity network

---

**allium** — Empowering Tor network analysis with intelligence, security, and performance.
