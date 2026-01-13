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
<summary><strong>Data Processing</strong></summary>

- Multi-threaded API fetching from 5 sources: Onionoo Details/Uptime/Bandwidth, AROI Validation, CollecTor Consensus
- Multiprocessing page generation (CPU count workers, min 4, configurable via `--workers`)
- Memory modes: `--apis details` (~400MB) or `--apis all` (~2.4GB)
- Downtime filtering: excludes relays offline >7 days (configurable via `--filter-downtime`)
- Generates ~21,700 HTML pages including relay, contact, country, AS, family, platform, and flag pages

</details>

<details>
<summary><strong>AROI Leaderboards (18 Categories)</strong></summary>

Authenticated Relay Operator Identification system ranking verified operators:

**Capacity**: Bandwidth Contributed, Consensus Weight Leaders  
**Roles**: Exit/Guard Authority Champions, Exit/Guard Operators  
**Reliability** (>25 relays required): Reliability Masters (6mo), Legacy Titans (5yr), Bandwidth Served Masters (6mo), Bandwidth Served Legends (5yr)  
**Diversity**: Most Diverse, Platform Diversity (non-Linux), Non-EU Leaders, Frontier Builders (rare countries)  
**Infrastructure**: Network Veterans (tenure), IPv4/IPv6 Address Leaders, AROI Validation Champions

- Paginated rankings (Top 10, 11-20, 21-25) with CSS-only navigation
- Champion badge system for top performers

</details>

<details>
<summary><strong>Reliability System</strong></summary>

- Multi-period uptime tracking: 1-month, 6-month, 1-year, 5-year
- Flag-specific uptime with priority: Exit > Guard > Fast > Running
- Network percentile positioning (5th, 25th, 50th, 75th, 90th, 95th, 99th)
- Statistical outlier detection using ≥2σ standard deviation threshold
- Uptime normalization from Onionoo 0-999 scale to 0-100%
- Minimum 30 data points required for valid calculations

</details>

<details>
<summary><strong>Network Health Dashboard</strong></summary>

Real-time metrics at `network-health.html`:

- Relay counts by role (exit/guard/middle) with percentages
- Bandwidth distribution (total, by role, mean/median per category)
- Uptime statistics (1mo mean/median by role, multi-period series)
- AROI validation status (validated/invalid/unconfigured counts)
- IPv4/IPv6 adoption rates
- Flag distribution (Fast, Stable, HSDir, V2Dir, Authority)
- New relay tracking (24h, 30d, 6mo, 1yr)

</details>

<details>
<summary><strong>Intelligence Engine (6 Layers)</strong></summary>

Pre-computed analysis attached to contact pages:

1. **Basic Relationships** — total countries, networks, operators, families, platforms
2. **Concentration Patterns** — top-3 country/AS weight, Five Eyes percentage, no-contact percentage
3. **Performance Correlation** — measured percentage, underutilized relay detection, CW/BW efficiency ratio
4. **Infrastructure Dependency** — unique Tor versions, critical AS identification (>5% weight), sync risk assessment
5. **Geographic Clustering** — Five/Fourteen Eyes influence, regional HHI concentration index
6. **Capacity Distribution** — Gini coefficient, guard/exit capacity percentages

</details>

<details>
<summary><strong>Directory Authorities</strong></summary>

`misc/authorities.html` provides:

- Authority uptime statistics with Z-score outlier detection
- Version compliance tracking
- Consensus participation monitoring
- Geographic distribution

</details>

<details>
<summary><strong>Security</strong></summary>

- Jinja2 autoescape enabled globally for XSS protection
- IP address validation via Python `ipaddress` module
- HTML entity escaping for all user-controlled data
- No JavaScript dependencies in generated output
- Static HTML eliminates server-side attack surface

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
| `--apis` | `all` | API sources: `all` (~2.4GB) or `details` (~400MB) |
| `--filter-downtime` | `7` | Exclude relays offline >N days (0 to disable) |
| `--workers` | CPU count (min 4) | Parallel workers for page generation |

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
