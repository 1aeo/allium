# Quick Start

**Audience**: Users  
**Scope**: Installation and first run

## What is Allium?

Allium generates static HTML websites showing Tor relay statistics:
- AROI leaderboards ranking authenticated operators (21 categories)
- Network health dashboard and network pressure page
- Individual pages for ~7,000 relays
- Geographic, AS, family, platform, and flag analysis

## Installation

### One-Command (Recommended)

```bash
curl -sSL https://raw.githubusercontent.com/1aeo/allium/master/setup.sh | bash
```

### Manual

```bash
git clone https://github.com/1aeo/allium.git
cd allium
sudo apt install python3-venv libcairo2 fonts-dejavu-core  # Debian/Ubuntu: venv, cairo, chart font
python3 -m venv venv && source venv/bin/activate
pip install -r config/requirements.txt
python3 allium/allium.py --progress --no-pressure-history
```

## First Run

From the repository root (outputs to `./www/`):

```bash
python3 allium/allium.py --progress --no-pressure-history
```

Running inside `allium/` (`cd allium && python3 allium.py --progress --no-pressure-history`) writes output to `allium/www/` instead.

- **Fast local run (`--no-pressure-history`)**: Takes 2–5 minutes (omits CollecTor pressure-history backfill).
- **Full run (no `--no-pressure-history`)**: The first run on an empty cache takes ~90 minutes to backfill the CollecTor server-descriptor archive; subsequent runs refresh incrementally in 2–5 minutes.

### View Locally

```bash
cd www
python3 -m http.server 8000
# Open http://localhost:8000
```

## Output Structure

```
www/
├── index.html                      # AROI leaderboards (main page)
├── top500.html                     # Top 500 relays by consensus weight
├── network-health.html             # Network health dashboard
├── network-pressure.html           # Daily network pressure charts
├── search-index.json               # Search data
├── metrics                         # Prometheus v2 exposition metrics
├── misc/
│   ├── all.html                    # All relays
│   ├── aroi-leaderboards.html      # AROI leaderboards
│   ├── authorities.html            # Directory authorities
│   ├── diagnostics.html            # API health & freshness diagnostics
│   └── ...                         # Sorted listings
├── relay/<fingerprint>/index.html  # Individual relay pages
├── contact/<hash>/index.html       # Operator pages
├── country/<code>/index.html       # Country pages
└── static/                         # CSS, images, flags
```

## Common Options

```bash
# Show progress
python3 allium/allium.py --progress

# Custom output directory
python3 allium/allium.py --out /var/www/tor-metrics

# Low memory mode (~400MB instead of ~2.4GB, skipping archive backfill)
python3 allium/allium.py --apis details --no-pressure-history

# All options
python3 allium/allium.py --help
```

## Quick Troubleshooting

| Error | Solution |
|-------|----------|
| "Jinja2 not found" | `sudo apt install python3-jinja2` for Debian/Ubuntu's own python3; in a virtualenv, `pip install -r config/requirements.txt` from the repository root |
| "Permission denied" | `python3 allium/allium.py --out ~/allium-output` |
| "No module named 'lib'" | Run `python3 allium/allium.py` from the repository root or `cd allium && python3 allium.py` |
| Out of memory | `python3 allium/allium.py --apis details --no-pressure-history` |
| "PNG charts need cairocffi, numpy and the cairo library" | Run the `💡` commands printed after it, or add `--chart-format svg` |

## How to Verify

```bash
ls www/index.html www/network-health.html www/network-pressure.html www/misc/diagnostics.html www/metrics
```

## Next Steps

- [Configuration](configuration.md) - All CLI options
- [Deployment](deployment.md) - Web server setup
- [Troubleshooting](troubleshooting.md) - Common issues
- [Current Capabilities](../reference/current-capabilities.md) - All features
