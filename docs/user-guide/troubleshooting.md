# Troubleshooting

**Audience**: Users  
**Scope**: Common errors and solutions

## Installation Issues

### "Jinja2 not found"

```
ModuleNotFoundError: No module named 'jinja2'
```

**Solution**:
```bash
# Debian/Ubuntu's own python3 (no virtualenv): pip is missing or refused there (PEP 668)
sudo apt install python3-jinja2
# A virtualenv, from the repository root
venv/bin/python3 -m pip install -r config/requirements.txt
```

### "Python version too old"

```
❌ Error: Python 3.8+ required
```

**Solution**: Upgrade Python or use a virtual environment:
```bash
python3 --version  # Check current version
# Install Python 3.8+ from your package manager or pyenv
```

### "No module named 'lib'"

```
ModuleNotFoundError: No module named 'lib'
```

**Solution**: Invoke `allium.py` directly so `allium/` is on Python's module path (either from the repository root or from `allium/`):
```bash
# From the repository root:
python3 allium/allium.py --progress
# Or from allium/:
cd allium && python3 allium.py --progress
```

### "PNG charts need cairocffi, numpy and the cairo library"

```
⚠️ PNG charts need cairocffi, numpy and the cairo library (No module named 'cairocffi'); writing SVG charts
💡 Install them for /usr/bin/python3: sudo apt install python3-cairocffi python3-numpy libcairo2 fonts-dejavu-core
```

The build goes on with SVG charts (an explicit `--chart-format png` stops instead). The `💡` lines are the
commands for the Python that ran `allium.py`.

**Solution**:

```bash
# Debian/Ubuntu's own python3 (no virtualenv): every package from apt
sudo apt install python3-cairocffi python3-numpy libcairo2 fonts-dejavu-core
# A virtualenv, from the repository root: pip, then what pip cannot install
venv/bin/python3 -m pip install -r config/requirements.txt
sudo apt install libcairo2 fonts-dejavu-core   # Fedora: sudo dnf install cairo dejavu-sans-fonts
```

To keep SVG charts without the notice, run `python3 allium/allium.py --chart-format svg`; `python3 allium/allium.py --no-charts`
builds without charts.

## Permission Issues

### "Permission denied creating output directory"

```
❌ Error: Permission denied creating output directory './www'
```

**Solution**: Use a different output directory:
```bash
python3 allium/allium.py --out ~/allium-output --progress
# or fix permissions
chmod 755 /path/to/parent/directory
```

### "Permission denied writing files"

**Solution**: Check directory ownership:
```bash
ls -la /var/www/
sudo chown -R $USER:$USER /var/www/tor-metrics
```

## Memory Issues

### "Killed" or Out of Memory

Process killed during generation, typically with `--apis all`.

**Solution 1**: Use details-only mode:
```bash
python3 allium/allium.py --apis details --progress  # ~400MB instead of ~2.4GB
```

**Solution 2**: Reduce parallel workers:
```bash
python3 allium/allium.py --workers 2 --progress  # Default is max(4, CPU count)
```

**Solution 3**: Add swap space:
```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Memory monitoring

```bash
# Watch memory during generation
python3 allium/allium.py --progress  # Shows memory usage
# or
watch -n 1 free -h
```

## Network Issues

### "Failed to fetch from Onionoo"

```
❌ Error: Failed to initialize relay data
```

**Causes**:
1. No internet connection
2. Onionoo API temporarily unavailable
3. Firewall blocking requests

**Solutions**:
```bash
# Test connectivity
curl -I https://onionoo.torproject.org/details

# Retry - API may be temporarily slow
python3 allium/allium.py --progress

# Check for proxy requirements
export HTTP_PROXY=http://proxy:port
export HTTPS_PROXY=http://proxy:port
```

### "No onionoo data available"

```
⚠️  No onionoo data available - this might be due to network issues or the service being temporarily unavailable
```

This is often temporary. The generator exits gracefully (exit code 0) when Onionoo details data is unavailable.

**Solution**: Wait and retry:
```bash
sleep 60 && python3 allium/allium.py --progress
```

## Generation Issues

### "Generation takes too long"

Steady-state generation takes 2–5 minutes with `--apis all` (1–2 minutes with `--apis details`). On the very first run with an empty cache, the CollecTor server-descriptor backfill for Network Pressure (`allium/lib/pressure_history.py`) downloads monthly archives and takes ~90 minutes; subsequent runs refresh incrementally.

**If longer**:
1. For fast local runs on an empty cache, skip the backfill: `--no-pressure-history`
2. Check internet connection speed
3. Reduce workers: `--workers 2`
4. Use details-only: `--apis details`
5. Use SVG or disable charts if PNG rasterization is slow on low-CPU hosts: `--chart-format svg` or `--no-charts`

### Static files not updating

`_sync_static_files` syncs new or modified static files incrementally on every run (`Static files: <copied> updated, <skipped> unchanged`). Unchanged files are skipped by size, mtime, and byte comparison (`filecmp.cmp`).

**To force a clean static copy**:
```bash
rm -rf www/static
python3 allium/allium.py --progress --no-pressure-history
```

### "Some pages missing"

If relay or contact pages are missing:

1. Check if relays are filtered by downtime:
   ```bash
   python3 allium/allium.py --filter-downtime 0  # Disable filtering
   ```

2. Verify the relay exists in current Onionoo data

## Output Issues

### "Pages don't display correctly"

**Check**:
1. Static files present: `ls www/static/`
2. Serving from correct directory
3. Base URL matches hosting path

**Fix for subdirectory hosting**:
```bash
python3 allium/allium.py --base-url "/tor-metrics" --out /var/www/tor-metrics
```

### "Search doesn't work"

Search requires `search-index.json` and the server-side function (Cloudflare Pages, deployed via `1aeo/allium-deploy`).

**Verify search index exists**:
```bash
ls -la www/search-index.json
```

## Debug Mode

For detailed debugging (use `--workers 0` to disable multiprocessing):

```bash
# Verbose single-process output
python3 allium/allium.py --workers 0 --progress --no-pressure-history 2>&1 | tee allium.log

# Check specific API
curl -v https://onionoo.torproject.org/details | head -100
```

## How to Verify

```bash
# Run unit tests for optional PNG dependencies and CLI smoke checks
pytest tests/unit/test_optional_deps.py
```

## Getting Help

If issues persist:

1. Check existing issues on GitHub
2. Include in bug report:
   - Python version: `python3 --version`
   - OS: `uname -a`
   - Full error message
   - Command used
   - Output of `--progress` flag
