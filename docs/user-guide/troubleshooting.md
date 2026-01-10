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
pip3 install jinja2
# or
pip3 install -r config/requirements.txt
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

**Solution**: Run from the correct directory:
```bash
cd allium  # Must be in the allium/ subdirectory
python3 allium.py --progress
```

## Permission Issues

### "Permission denied creating output directory"

```
❌ Error: Permission denied creating output directory './www'
```

**Solution**: Use a different output directory:
```bash
python3 allium.py --out ~/allium-output --progress
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
python3 allium.py --apis details --progress  # ~400MB instead of ~2.4GB
```

**Solution 2**: Reduce parallel workers:
```bash
python3 allium.py --workers 2 --progress  # Default is 4
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
python3 allium.py --progress  # Shows memory usage
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
python3 allium.py --progress

# Check for proxy requirements
export HTTP_PROXY=http://proxy:port
export HTTPS_PROXY=http://proxy:port
```

### "No onionoo data available"

```
⚠️ No onionoo data available
```

This is often temporary. The generator exits gracefully (exit code 0) in CI environments.

**Solution**: Wait and retry:
```bash
sleep 60 && python3 allium.py --progress
```

## Generation Issues

### "Generation takes too long"

Normal generation time: 2-5 minutes with `--apis all`, 1-2 minutes with `--apis details`.

**If longer**:
1. Check internet connection speed
2. Reduce workers: `--workers 2`
3. Use details-only: `--apis details`

### "Static files already exist, skipping copy"

This is normal behavior, not an error. Static files are only copied once.

**To force refresh**:
```bash
rm -rf www/static
python3 allium.py --progress
```

### "Some pages missing"

If relay or contact pages are missing:

1. Check if relays are filtered by downtime:
   ```bash
   python3 allium.py --filter-downtime 0  # Disable filtering
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
python3 allium.py --base-url "/tor-metrics" --out /var/www/tor-metrics
```

### "Search doesn't work"

Search requires `search-index.json` and server-side function (Cloudflare Pages).

**Verify search index exists**:
```bash
ls -la www/search-index.json
```

## Debug Mode

For detailed debugging:

```bash
# Verbose output
python3 allium.py --progress 2>&1 | tee allium.log

# Check specific API
curl -v https://onionoo.torproject.org/details | head -100
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
