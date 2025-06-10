# allium: Advanced Tor Relay Analytics & Metrics Platform

A powerful, security-hardened static site generator that creates comprehensive Tor relay metrics, statistics, and operator leaderboards from Onionoo API data.

## 🚀 Key Features

### Core Analytics
- **Complete relay metrics** with advanced sorting and filtering
- **Geographic distribution analysis** with rare country intelligence
- **Platform and AS diversity tracking** across the network
- **Bandwidth and consensus weight analytics** with multiple viewing modes

### AROI Leaderboard System 🏆
- **10 specialized leaderboards** for authenticated relay operators
- **Operator achievement tracking** across multiple dimensions
- **Geographic diversity scoring** with frontier country recognition
- **Platform diversity metrics** highlighting technical leadership

### Security & Performance 🔒
- **XSS-hardened templates** with comprehensive input sanitization
- **Static generation** for maximum performance and security
- **Single API query design** for minimal server load
- **Memory-efficient processing** with real-time monitoring

### Intelligence Features 🧠
- **Dynamic classification system** replacing hardcoded country lists
- **Multi-factor analysis** (relay count, network %, geopolitical factors)
- **Tier-based country rankings** (Legendary, Epic, Rare, Emerging, Common)
- **Geopolitical awareness** in country scoring algorithms

## 📋 Usage

```bash
./allium.py [options]
```

### Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--out` | `./www` | Output directory for generated files |
| `--onionoo-url` | `https://onionoo.torproject.org/details` | Onionoo API endpoint |
| `--display-bandwidth-units` | `bits` | Units for bandwidth display (`bits` or `bytes`) |
| `--progress` | `false` | Show detailed progress with memory usage |

### Examples

```bash
# Generate with progress tracking
./allium.py --progress

# Custom output directory with bytes units
./allium.py --out /var/www/tor-metrics --display-bandwidth-units bytes

# Development with custom API endpoint
./allium.py --onionoo-url http://localhost:8080/details --progress
```

## 🛠️ Installation

### Requirements
- **Python 3.7+**
- **Jinja2 ≥2.11.2**

### Quick Start
```bash
# Clone repository
git clone [repository-url]
cd allium

# Install dependencies
pip install -r requirements.txt

# Generate metrics site
cd allium
./allium.py --progress

# Serve locally (optional)
cd www && python -m http.server 8000
```

## 📊 Generated Content

### Main Pages
- **Index page** with top 500 relays by consensus weight
- **Complete relay listing** with all active relays
- **AROI leaderboards** with 10 specialized categories
- **Geographic analysis** with rare country intelligence

### Categorized Views
- **By Country** - Including rare/frontier country analysis
- **By Platform** - Operating system and version distributions  
- **By AS Number** - Autonomous system diversity tracking
- **By Contact** - Operator family groupings
- **By Bandwidth** - Multiple bandwidth-based sortings
- **By Consensus Weight** - Authority distribution analysis

### Individual Pages
- **Per-relay information** with complete technical details
- **Operator profiles** with achievement metrics
- **Geographic summaries** with diversity scoring
- **Platform statistics** with technical diversity analysis

## 🔒 Security Features

allium implements comprehensive security measures:

- **Global XSS protection** via Jinja2 autoescape
- **Input sanitization** for all external data sources
- **Static generation** eliminating server-side vulnerabilities  
- **No JavaScript dependencies** for maximum security
- **Comprehensive security auditing** with vulnerability tracking

## 🌍 AROI Leaderboards

Ten specialized leaderboards track authenticated operator achievements:

1. **Bandwidth Champions** - Total bandwidth contributed
2. **Consensus Weight Leaders** - Network authority holders
3. **Exit Authority Champions** - Exit traffic facilitators
4. **Exit Gate Keepers** - Number of exit relays operated
5. **Guard Champions** - Number of guard relays operated
6. **Most Diverse Operators** - Geographic, platform, and network diversity scoring
7. **Platform Diversity Heroes** - Non-Linux champions promoting OS diversity
8. **Non-EU Leaders** - Geographic champions expanding Tor outside the EU
9. **Frontier Builders** - Operators in rare or underrepresented countries
10. **Network Veterans** - Longest-serving operators with earliest relay start dates

## 📈 Performance & Monitoring

- **Real-time memory usage tracking** during generation
- **Progress reporting** with timestamp and step tracking
- **Efficient data processing** with minimal API queries
- **Optimized template rendering** with security hardening
- **Scalable architecture** supporting large relay counts

## 🤝 Contributing

allium welcomes contributions in several areas:

- **Security enhancements** and vulnerability reporting
- **Analytics improvements** and new leaderboard categories
- **Geographic intelligence** and country classification updates
- **Performance optimizations** and memory efficiency
- **Template improvements** and UI enhancements

## 📄 License

This project is released under the **UNLICENSE** (public domain).

### Third-Party Assets
- **Country flags** from GoSquared ([license included](licenses/gosquared-flags-license))
- **Relay flags** from The Tor Project ([license included](licenses/tor-flags-license))

## 🔗 References

- [Tor Metrics Project](https://metrics.torproject.org/) - Official tor metrics (inspiration)
- [Onionoo API](https://onionoo.torproject.org/) - Tor relay data source
- [Tor Project](https://www.torproject.org/) - Privacy and anonymity network

## 🏅 Weighted Country Scoring System

Countries are dynamically classified using a sophisticated scoring system with geopolitical awareness:

### Scoring Formula
```
Rarity Score = (Relay Count Factor × 4) + 
               (Network Percentage Factor × 3) + 
               (Geopolitical Factor × 2) + 
               (Regional Factor × 1)
```

### Factor Details

**1. Relay Count Factor (Weight: 4x)**
- 6 points: 0 relays
- 5 points: 1 relay  
- 4 points: 2 relays
- 3 points: 3 relays
- 2 points: 4 relays
- 1 point: 5 relays
- 0 points: 6+ relays

**2. Network Percentage Factor (Weight: 3x)**
- 6 points: <0.05% of network
- 4 points: 0.05-0.1% of network
- 2 points: 0.1-0.2% of network
- 0 points: >0.2% of network

**3. Geopolitical Factor (Weight: 2x)**
- 3 points: Conflict zones (Syria, Yemen, Afghanistan, etc.)
- 3 points: Authoritarian regimes (China, Iran, North Korea, etc.)
- 2 points: Island nations (Malta, Cyprus, Iceland, etc.)
- 2 points: Landlocked developing countries (Kazakhstan, Mongolia, etc.)
- 1 point: General developing countries
- 0 points: Developed countries

**4. Regional Factor (Weight: 1x)**
- 2 points: Underrepresented regions (Africa, Central Asia, Pacific Islands)
- 1 point: Emerging regions (Caribbean, Central America, South Asia)
- 0 points: Well-represented regions

### Country Classifications
- **Legendary (15+ points)** - Ultra-rare countries with critical strategic importance
- **Epic (10-14 points)** - Very rare countries with high geopolitical significance  
- **Rare (6-9 points)** - Uncommon countries worth prioritizing
- **Emerging (3-5 points)** - Countries with potential for growth
- **Common (0-2 points)** - Standard countries with good representation

---

**allium** - Empowering Tor network analysis with intelligence, security, and performance.
