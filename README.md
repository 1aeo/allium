# Allium

[![CI/CD Pipeline](https://github.com/1aeo/allium/workflows/Allium%20CI/CD%20Pipeline/badge.svg)](https://github.com/1aeo/allium/actions)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: Unlicense](https://img.shields.io/badge/license-Unlicense-green.svg)](https://unlicense.org/)
[![Status: Active](https://img.shields.io/badge/status-active-brightgreen.svg)]()

**Advanced Tor Relay Analytics & Metrics Platform** — A powerful, security-hardened static site generator that creates comprehensive Tor relay metrics, statistics, and operator leaderboards from Onionoo API data.

## Why Allium?

Allium transforms raw Tor network data into actionable intelligence. Unlike basic relay listings, Allium provides:

- **Operator Recognition** — AROI leaderboards celebrating authenticated relay operators across 18 performance categories
- **Network Health Insights** — Real-time monitoring with concentration risk analysis and geographic diversity tracking
- **Reliability Analytics** — Multi-period uptime analysis with statistical outlier detection
- **Security-First Design** — XSS-hardened templates with zero JavaScript dependencies

*Originally forked from [allium](https://git.jordan.im/allium), this version adds extensive analytics, operator leaderboards, and intelligence features.*

## 🚀 Quick Start

> ⚠️ **Security Note**: Before running scripts from the internet, review them first: `curl -sSL https://raw.githubusercontent.com/1aeo/allium/master/setup.sh | less`

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

- [🛠️ Requirements](#️-requirements)
- [📋 Usage & Configuration](#-usage--configuration)
- [🚀 Key Features](#-key-features)
- [🌐 API Data Sources](#-api-data-sources)
- [📊 Generated Content](#-generated-content)
- [🌍 AROI Leaderboards](#-aroi-leaderboards)
- [🔒 Security & Performance](#-security--performance)
- [📚 Documentation](#-documentation)
- [🤝 Contributing](#-contributing)
- [📷 Screenshots](#-screenshots)
- [📄 License](#-license)
- [🔗 References](#-references)

## 🛠️ Requirements

### Prerequisites Check

```bash
# Verify Python version (3.8+ required)
python3 --version

# Verify pip is available
pip3 --version
```

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
# Generate with progress tracking (~2-5 minutes, ~2.4GB peak memory)
./allium.py --progress

# Custom output with bytes units
./allium.py --out /var/www/tor-metrics --display-bandwidth-units bytes

# Minimal memory mode (~400MB)
./allium.py --apis details --progress
```

**Typical Generation**: ~21,700 HTML pages in 2-5 minutes

## 🚀 Key Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **Complete Relay Metrics** | Advanced sorting, filtering, and analysis for all active relays |
| **AROI Leaderboards** | 18 specialized categories recognizing authenticated operators |
| **Network Health Dashboard** | 10-card monitoring with real-time metrics and risk analysis |
| **Reliability System** | Multi-period uptime tracking with statistical outlier detection |
| **Intelligence Engine** | 6-layer analysis providing smart context across templates |
| **Directory Authorities** | Health tracking with uptime statistics and Z-score analysis |

### Detailed Feature Documentation

For comprehensive feature documentation, see:
- **[Current Capabilities](docs/reference/current-capabilities.md)** — Complete list of all working features
- **[Architecture Overview](docs/architecture/overview.md)** — System design and data flow

## 🌐 API Data Sources

Allium integrates with multiple Tor Project APIs:

### Onionoo Details API

- **URL**: `https://onionoo.torproject.org/details`
- **Purpose**: Core relay information (bandwidth, flags, location, technical details)
- **Memory Usage**: ~400MB during processing

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

### Onionoo Bandwidth API

- **URL**: `https://onionoo.torproject.org/bandwidth`
- **Purpose**: Historical bandwidth statistics for trend analysis and optimization
- **Cache**: Configurable cache time (default: 12 hours)

**Performance Features**: Parallel API fetching, HTTP conditional requests, graceful fallback to cached data

## 📊 Generated Content

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

## 🌍 AROI Leaderboards

Eighteen specialized categories tracking authenticated operator achievements across five core dimensions:

**🚀 Capacity & Performance**
1. **Bandwidth Contributed** — Total observed bandwidth capacity
2. **Consensus Weight Authority** — Network routing control influence

**🛡️ Network Role Specialization**
3. **Exit Authority Champions** — Exit consensus weight control
4. **Guard Authority Champions** — Guard consensus weight control
5. **Exit Operators** — Exit relay infrastructure providers
6. **Guard Operators** — Guard relay infrastructure providers

**⏰ Reliability & Performance Excellence** *(25+ relays required)*
7. **Reliability Masters** — 6-month average uptime
8. **Legacy Titans** — 5-year average uptime
9. **Bandwidth Served Masters** — 6-month bandwidth performance
10. **Bandwidth Served Legends** — 5-year bandwidth performance

**🌍 Diversity & Geographic Leadership**
11. **Most Diverse Operators** — Multi-factor diversity scoring
12. **Platform Diversity Heroes** — Non-Linux operational excellence
13. **Non-EU Leaders** — Geographic expansion beyond EU
14. **Frontier Builders** — Operations in underrepresented countries

**🏆 Innovation & Leadership**
15. **Network Veterans** — Scale-weighted operational tenure
16. **IPv4 Address Leaders** — Unique IPv4 address diversity
17. **IPv6 Address Leaders** — Unique IPv6 address diversity
18. **AROI Validation Champions** — Verified identity count

## 🔒 Security & Performance

- **Global XSS protection** via Jinja2 autoescape
- **Input sanitization** for all external data sources
- **Static generation** eliminating server-side vulnerabilities
- **No JavaScript dependencies** for maximum security
- **Real-time memory usage tracking** during generation
- **Scalable architecture** supporting large relay counts

## 📚 Documentation

Comprehensive documentation is available in the [`docs/`](docs/) directory:

### 👥 For Users

- **[Quick Start Guide](docs/user-guide/quick-start.md)** — Get running in 5 minutes
- **[Configuration Guide](docs/user-guide/configuration.md)** — All options and automation setup
- **[Deployment Guide](docs/user-guide/deployment.md)** — Web server setup
- **[Troubleshooting](docs/user-guide/troubleshooting.md)** — Common issues and solutions

### 👨‍💻 For Developers

- **[Architecture Overview](docs/architecture/overview.md)** — System design and data flow
- **[Testing Standards](docs/development/testing.md)** — Test naming and organization
- **[Security Guide](docs/development/security.md)** — Security best practices

### 📖 Additional Resources

- **[Complete Documentation Index](docs/README.md)** — Full documentation navigation
- **[Roadmap 2025-2026](docs/features/planned/allium-roadmap-2025.md)** — Future plans and milestones
- **[Current Capabilities](docs/reference/current-capabilities.md)** — All working features
- **[Planned Features](docs/features/planned/)** — What's coming next

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed setup instructions.

### Quick Developer Setup

```bash
# Clone and setup with dev dependencies
git clone https://github.com/1aeo/allium.git && cd allium
curl -sSL https://raw.githubusercontent.com/1aeo/allium/master/setup.sh | bash -s -- --dev

# Or manually:
python3 -m venv venv && source venv/bin/activate
pip install -r config/requirements-dev.txt
```

**Run tests**: `pytest` • **Lint code**: `flake8 .` • **Security scan**: `bandit -r .`

### Contributing Areas

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

![Browse by Contact 1aeo](docs/screenshots/browse-by-contact-1aeo.png)

Individual operator profile showing relay family details, geographic distribution, and technical specifications across their network infrastructure.

## 📄 License

**UNLICENSE** (public domain)

**Third-Party Assets**: Country flags (GoSquared), Relay flags (The Tor Project)

## 🔗 References

- [Original allium](https://git.jordan.im/allium) — Fork source
- [Tor Metrics Project](https://metrics.torproject.org/) — Official metrics (inspiration)
- [Onionoo API](https://onionoo.torproject.org/) — Tor relay data source
- [Tor Project](https://www.torproject.org/) — Privacy and anonymity network

---

**allium** — Empowering Tor network analysis with intelligence, security, and performance.
