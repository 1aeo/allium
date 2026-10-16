# Configuration Guide

**Audience**: Users  
**Scope**: All CLI options and automation

## CLI Reference

```bash
cd allium
python3 allium.py [options]
```

### All Options

| Option | Default | Description |
|--------|---------|-------------|
| `--out` | `./www` | Output directory |
| `--base-url` | `""` | Public SEO base URL (e.g., `https://metrics.example.com`); root-relative values are for previews/subdirectory hosting |
| `--display-bandwidth-units` | `bits` | `bits` (Kbit/s) or `bytes` (KB/s) |
| `-p, --progress` | false | Show progress with memory usage |
| `--onionoo-details-url` | `https://onionoo.torproject.org/details` | Details API endpoint |
| `--onionoo-uptime-url` | `https://onionoo.torproject.org/uptime` | Uptime API endpoint |
| `--onionoo-bandwidth-url` | `https://onionoo.torproject.org/bandwidth` | Bandwidth API endpoint |
| `--aroi-url` | `https://aroivalidator.1aeo.com/latest.json` | AROI validator endpoint |
| `--bandwidth-cache-hours` | `12` | Hours to cache bandwidth data |
| `--apis` | `all` | `details` (~400MB) or `all` (~2.4GB) |
| `--filter-downtime` | `7` | Filter relays not seen for >N days, even if Onionoo still marks them running (0=disable) |
| `--workers` | `4` | Parallel workers (0=disable multiprocessing) |
| `--no-charts` | charts on | Skip the relay and contact history charts (drawn only with `--apis all`) |
| `--chart-format` | `png` | `png` (needs cairocffi, numpy and the cairo library, see the README's PNG charts section: without them the default writes SVG with a notice naming the install commands, and an explicit `png` stops; DejaVu Sans keeps the chart font) or `svg` |
| `--chart-scale` | `2` | PNG resolution: `2`, `1.5` or `1` |
| `--chart-colors` | `64` | PNG colors: `64` (fixed palette, about a third the size) or `full` |
| `--chart-layout` | `beside` | `beside` (next to each relay and contact page) or `charts` (`charts/relay/<fingerprint>/` and `charts/contact/<hash>/`, to serve them apart from the pages) |

## Common Profiles

### Low Memory (~400MB)

```bash
python3 allium.py --apis details --workers 2 --progress
```

Disables uptime/bandwidth APIs. Reliability features unavailable.

### Full Analytics (~2.4GB)

```bash
python3 allium.py --apis all --progress
```

All features enabled including reliability analysis.

### Subdirectory Hosting

```bash
python3 allium.py --base-url "/tor-metrics" --out /var/www/tor-metrics
```

### Debug Mode

```bash
python3 allium.py --workers 0 --progress
```

Disables multiprocessing for easier debugging.

### Production (Silent)

```bash
python3 allium.py --out /var/www/tor-metrics \
  --base-url https://metrics.example.com
```

No progress output, suitable for cron. An absolute HTTP(S) base URL enables an
absolute canonical on every page plus canonical-only `sitemap.xml` output.

## Automated Updates (Cron)

### Every 6 Hours

```bash
crontab -e
# Add:
0 */6 * * * cd /path/to/allium && python3 allium.py --out /var/www/tor-metrics >> /var/log/allium.log 2>&1
```

### Daily at 3 AM

```bash
0 3 * * * cd /path/to/allium && python3 allium.py --out /var/www/tor-metrics
```

### Low Memory Cron

```bash
0 */6 * * * cd /path/to/allium && python3 allium.py --apis details --out /var/www/tor-metrics
```

### Cron Tips

- Use absolute paths
- Log output for debugging
- Don't use `--progress` (creates large logs)
- Run as non-root user
- After updating allium, check the next run's log for `⚠️` and `💡` lines: when an optional feature such as PNG charts lacks a package, they name it and the command that installs it for the Python cron runs (they print without `--progress` too)

## Virtual Environment

```bash
cd allium
sudo apt install python3-venv libcairo2 fonts-dejavu-core  # Debian/Ubuntu: venv support, then PNG charts
python3 -m venv venv
source venv/bin/activate
pip install -r config/requirements.txt
python3 allium.py --progress
```

For cron with venv:

```bash
0 */6 * * * cd /path/to/allium && source venv/bin/activate && python3 allium.py --out /var/www/tor-metrics
```

## Performance Tuning

| Setting | Impact |
|---------|--------|
| `--apis details` | Reduces memory from ~2.4GB to ~400MB |
| `--workers 2` | Reduces parallel processing overhead |
| `--bandwidth-cache-hours 24` | Reduces API fetches |
| `--filter-downtime 0` | Includes all relays (more pages) |

## How to Verify

```bash
# Check current CLI options match this doc
python3 allium/allium.py --help
```

## See Also

- [Quick Start](quick-start.md) - First run
- [Deployment](deployment.md) - Web server setup
- [Troubleshooting](troubleshooting.md) - Common issues
