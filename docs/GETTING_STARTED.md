# 🚀 Getting Started with Allium

Welcome! This guide will help you get Allium running quickly and understand what it does.

## What is Allium?

Allium generates **beautiful, static websites** that show Tor relay statistics and analytics. It downloads data from the Tor network and creates:

- 📊 **Relay statistics** - bandwidth, countries, platforms
- 🏆 **AROI leaderboards** - rankings for relay operators  
- 🌍 **Geographic analysis** - rare country intelligence
- 🔍 **Individual relay pages** - detailed information for each relay

## Quick Start (Recommended)

### Option 1: One-Command Install (Production)
```bash
curl -sSL https://raw.githubusercontent.com/1aeo/allium/master/setup.sh | bash
```

### Option 2: One-Command Install (Developer)
For contributors who want testing tools:
```bash
curl -sSL https://raw.githubusercontent.com/1aeo/allium/master/setup.sh | bash -s -- --dev
```

### Option 3: Manual Install
```bash
# 1. Clone the repository
git clone https://github.com/1aeo/allium.git
cd allium

# 2. Install dependencies
# For production (minimal):
pip3 install -r config/requirements.txt
# OR for development (includes testing tools):
pip3 install -r config/requirements-dev.txt

# 3. Generate your first site
cd allium
python3 allium.py --progress

# 4. View it locally
cd www
python3 -m http.server 8000
# Open http://localhost:8000 in your browser
```

## What Happens During Generation?

When you run `python3 allium.py --progress`, here's what happens:

1. **Downloads data** from Tor's Onionoo API (~20MB)
2. **Processes relay information** for ~7,000 relays
3. **Generates HTML pages** (~500 individual pages)
4. **Creates analytics** and leaderboards
5. **Copies static assets** (CSS, images, flags)

Total time: **1-3 minutes** depending on your connection.

## Understanding the Output

After generation, you'll find these files in `www/`:

```
www/
├── index.html              # Main page with top 500 relays
├── misc/
│   ├── all.html           # All relays listing  
│   ├── aroi-leaderboards.html  # AROI operator rankings
│   ├── countries-cw.html  # Countries by consensus weight
│   └── ...                # Other sorted views
├── relay/
│   └── [fingerprint].html # Individual relay pages
├── country/
│   └── [code].html        # Country-specific pages
├── as/
│   └── [number].html      # AS-specific pages
└── static/               # CSS, images, flags
```

## Common Use Cases

### **Personal Dashboard**
Track specific relays or monitor network changes:
```bash
# Generate fresh data
cd allium && python3 allium.py --progress
```

### **Web Server Deployment**
Deploy to a web server:
```bash
# Generate to web root
python3 allium.py --out /var/www/html/tor-metrics --progress
```

### **Regular Updates**
Set up a cron job for automatic updates:
```bash
# Add to crontab: update every 6 hours
0 */6 * * * cd /path/to/allium && python3 allium.py --out /var/www/tor-metrics
```

## Configuration Options

```bash
# Basic options
python3 allium.py --help

# Common configurations
python3 allium.py --progress                    # Show progress
python3 allium.py --out ./custom-dir            # Custom output
python3 allium.py --display-bandwidth-units bytes  # Use bytes instead of bits
```

## Troubleshooting

### **"Jinja2 not found"**
```bash
pip3 install jinja2
# or
pip3 install -r config/requirements.txt
```

### **"Permission denied"**
```bash
# Use a different output directory
python3 allium.py --out ~/allium-output --progress
```

### **"Python version too old"**
You need Python 3.8+. Check your version:
```bash
python3 --version
```

### **"No module named 'lib'"**
Make sure you're running from the `allium/` subdirectory:
```bash
cd allium
python3 allium.py --progress
```

### **Generation takes too long**
- Normal time: 1-3 minutes
- If longer: check your internet connection
- Use `--progress` to see what's happening

## Understanding AROI Leaderboards

**AROI** = Authenticated Relay Operator Identifier

These leaderboards rank relay operators who provide contact information:

1. **Bandwidth Champions** - Most bandwidth contributed
2. **Consensus Weight Leaders** - Most network authority
3. **Geographic Diversity** - Operating in rare countries
4. **Platform Diversity** - Using non-Linux systems
5. **Network Veterans** - Longest-running operations

## Next Steps

- 📚 **[Main Documentation](../README.md)** - Full feature overview
- 🏗️ **[Architecture](architecture/README.md)** - How allium works
- 🔧 **[Advanced Configuration](ADVANCED.md)** - Custom setups
- 🤝 **[Contributing](../README.md#contributing)** - Help improve allium

## Need Help?

1. Check this guide first
2. Review [common issues](TROUBLESHOOTING.md)  
3. Check the [main README](../README.md)
4. Open an issue on GitHub

---

**Happy exploring the Tor network! 🧅** 