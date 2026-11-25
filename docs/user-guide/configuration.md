# Configuration Guide

**Audience**: Users  
**Scope**: All CLI options, environment variables, and automation

## CLI Reference

Run from the repository root (or `cd allium && python3 allium.py [options]`):

```bash
python3 allium/allium.py [options]
```

### All Options

| Option | Default | Description |
|--------|---------|-------------|
| `--out` | `./www` | Directory to store rendered files |
| `--base-url` | `""` | Public base URL for vanity, canonical, Open Graph, and sitemap URLs (`""` = site-root, `/tor-metrics` = subdirectory preview, `https://...` = absolute canonicals plus `robots.txt` and `sitemap.xml`; bare `/` is rejected) |
| `--display-bandwidth-units` | `bits` | Display bandwidth in `bits` (Kbit/s, Mbit/s, Gbit/s) or `bytes` (KB/s, MB/s, GB/s) |
| `-p, --progress` | `false` | Show progress updates during execution (with memory usage) |
| `--onionoo-details-url` | `https://onionoo.torproject.org/details` | Onionoo details API HTTP URL |
| `--onionoo-uptime-url` | `https://onionoo.torproject.org/uptime` | Onionoo uptime API HTTP URL |
| `--onionoo-bandwidth-url` | `https://onionoo.torproject.org/bandwidth` | Onionoo historical bandwidth API HTTP URL |
| `--aroi-url` | `https://aroivalidator.1aeo.com/latest.json` | AROI validator API HTTP URL |
| `--exit-dns-health-url` | `https://exitdnshealth.1aeo.com/latest.json` | Exit DNS Health API HTTP URL |
| `--bandwidth-cache-hours` | `12` | Hours to cache historical bandwidth data before refreshing |
| `--apis` | `all` | `details` (~400MB memory, details API only) or `all` (~2.4GB memory, all enabled APIs) |
| `--filter-downtime` | `7` | Filter out relays not seen for >N days, even if Onionoo marks them running (`0` disables) |
| `--workers` | `max(4, CPU count)` | Parallel workers for page generation (`0` disables multiprocessing) |
| `--no-charts` | charts on | Skip relay, contact, network, and pressure history charts (charts are drawn only with `--apis all`) |
| `--no-pressure-history` | backfill on | Skip CollecTor pressure-history backfill and use `allium/data/cache/pressure_history.json` |
| `--no-consensus-evaluation` | evaluation on | Skip CollecTor consensus and server-descriptor fetches and per-relay consensus evaluation |
| `--chart-format` | `png` | `png` (shows at Tor Browser's Safest level; falls back to SVG with a notice unless explicitly passed; needs cairocffi, numpy, cairo, and DejaVu Sans) or `svg` (smaller, faster, no extra packages) |
| `--chart-scale` | `2.0` | PNG chart resolution (`1.0`, `1.5`, or `2.0`; default `2.0` is 2160 px wide) |
| `--chart-colors` | `64` | PNG chart colors: `64` (fixed palette, ~1/3 file size) or `full` |
| `--chart-layout` | `beside` | `beside` (writes under `relay/`, `contact/`, `network/`, `pressure/`) or `charts` (writes under `charts/{relay,contact,network,pressure}/`) |

### Environment Variables

| Variable | Who sets it | What it does |
|----------|-------------|--------------|
| `PYTEST_CURRENT_TEST` | `pytest` | Skips the CollecTor pressure-history download during test runs |
| `CI`, `GITHUB_ACTIONS`, `GITLAB_CI` | CI host | `setup.sh` passes `--apis details`; worker failures print tracebacks |
| `ALLIUM_CI_CACHE_FALLBACK` | CI setup job | `setup.sh` seeds fixture API caches and runs once with `--no-pressure-history` (production installs omit it) |
| `ALLIUM_CI_FIXTURE_DIR` | CI setup job | Directory containing CI fixture JSON files when `setup.sh` runs outside the checkout |
| `ALLIUM_CI_CACHE_LIB` | CI setup job | Path to `scripts/ci_cache_fallback.sh` |

## Common Profiles

### Low Memory (~400MB)

```bash
python3 allium/allium.py --apis details --workers 2 --progress --no-pressure-history
```

Disables uptime, bandwidth, AROI validation, Exit DNS Health, CollecTor consensus/descriptor fetches, charts, and the CollecTor pressure-history download (loads cached pressure history only if present).

### Full Analytics (~2.4GB)

```bash
python3 allium/allium.py --apis all --progress
```

Enables all 7 coordinator API workers, daily pressure history, and history charts. Add `--no-pressure-history` on local runs to skip the initial ~90-minute CollecTor archive backfill.

### Subdirectory Hosting

```bash
python3 allium/allium.py --base-url "/tor-metrics" --out /var/www/tor-metrics
```

### Debug Mode

```bash
python3 allium/allium.py --workers 0 --progress
```

Disables multiprocessing for easier debugging.

### Production (Silent)

```bash
python3 allium/allium.py --out /var/www/tor-metrics \
  --base-url https://metrics.example.com
```

No progress output, suitable for cron. An absolute `https://` base URL enables absolute canonical URLs plus `robots.txt` and canonical-only `sitemap.xml` output.

## Virtual Environment

From the repository root:

```bash
cd /path/to/allium
sudo apt install python3-venv libcairo2 fonts-dejavu-core  # Debian/Ubuntu: venv, cairo, chart font
python3 -m venv venv
venv/bin/python3 -m pip install -r config/requirements.txt
venv/bin/python3 allium/allium.py --progress
```

Or run from `allium/` using the repo-root virtualenv (`../venv/bin/python3 allium.py --progress`); avoid mixing `config/requirements.txt` and `allium.py` paths from the wrong directory.

## Automated Updates (Cron)

Production cron jobs must generate into a staging directory, verify `index.html` is non-empty, and `rsync --delete` to the web root only after success — direct-to-docroot runs overwrite or delete live page directories before rebuilding. See [Deployment Guide](deployment.md#automated-updates-cron) for the staged wrapper script.

```bash
# Every 6 hours via staged wrapper script (omit --progress to keep logs compact)
0 */6 * * * /path/to/deploy-allium.sh >> /var/log/allium.log 2>&1
```

Check logs after updates for `⚠️` and `💡` lines: when an optional package for PNG charts is missing, Allium prints the exact install command for the Python interpreter running cron.

## Performance Tuning

| Setting | Impact |
|---------|--------|
| `--apis details` | Reduces memory from ~2.4GB to ~400MB |
| `--workers 2` | Reduces parallel processing overhead |
| `--bandwidth-cache-hours 24` | Reduces Onionoo bandwidth API fetches |
| `--filter-downtime 0` | Includes all relays (more pages) |
| `--no-charts` | Skips relay, contact, network, and pressure chart generation |
| `--no-pressure-history` | Skips CollecTor archive backfill (~90 min on an empty cache) |
| `--no-consensus-evaluation` | Skips CollecTor consensus and descriptor fetches |

## How to Verify

```bash
# Verify CLI options match this guide
python3 allium/allium.py --help
```

## See Also

- [Quick Start](quick-start.md) - First run
- [Deployment](deployment.md) - Web server setup and staged cron publishing
- [Troubleshooting](troubleshooting.md) - Common issues
