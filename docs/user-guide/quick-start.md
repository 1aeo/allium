# Quick Start

**Audience**: Users  
**Scope**: Installation and first run

## What is Allium?

Allium generates static HTML websites showing Tor relay statistics:
- AROI leaderboards ranking authenticated operators (18 categories)
- Network health dashboard
- Individual pages for ~7,000 relays
- Geographic and platform analysis

## Installation

### Prerequisites

- Python **3.8+**
- `pip` (usually included with Python on most platforms)
- Virtualenv support (`python3 -m venv`)
  - On Debian/Ubuntu, you may need:
    - `sudo apt-get update && sudo apt-get install -y python3-venv`

### One-Command (Recommended)

```bash
curl -sSL https://raw.githubusercontent.com/1aeo/allium/master/setup.sh | bash
```

### Manual

```bash
git clone https://github.com/1aeo/allium.git
cd allium
python3 -m venv venv
source venv/bin/activate
python -m pip install -r config/requirements.txt

# First run (recommended on low-memory systems)
python3 allium/allium.py --progress --apis details
```

## First Run

```bash
# From the repository root:
source venv/bin/activate
python3 allium/allium.py --progress
```

Generation takes 2-5 minutes. Output goes to `www/`.

If you run out of memory, use details-only mode:

```bash
python3 allium/allium.py --progress --apis details
```

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
├── search-index.json               # Search data
├── misc/
│   ├── all.html                    # All relays
│   ├── aroi-leaderboards.html      # AROI leaderboards
│   ├── authorities.html            # Directory authorities
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

# Low memory mode (~400MB instead of ~2.4GB)
python3 allium/allium.py --apis details

# All options
python3 allium/allium.py --help
```

## Quick Troubleshooting

| Error | Solution |
|-------|----------|
| "Jinja2 not found" | `python3 -m pip install -r config/requirements.txt` |
| "Permission denied" | `python3 allium/allium.py --out ~/allium-output` |
| "No module named 'lib'" | Run `python3 allium/allium.py ...` from the repository root |
| Out of memory | `python3 allium/allium.py --apis details` |

## Next Steps

- [Configuration](configuration.md) - All CLI options
- [Deployment](deployment.md) - Web server setup
- [Troubleshooting](troubleshooting.md) - Common issues
- [Current Capabilities](../reference/current-capabilities.md) - All features
