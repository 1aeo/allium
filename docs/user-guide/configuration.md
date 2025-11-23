# Configuration Guide

This guide covers all configuration options for customizing Allium's behavior and output.

---

## 📋 Command-Line Options

### Basic Usage
```bash
cd allium
python3 allium.py [options]
```

### Available Options

#### Output Configuration
```bash
--out DIRECTORY
```
- **Purpose**: Specify where generated files are saved
- **Default**: `./www`
- **Example**: `--out /var/www/html/tor-metrics`

#### Bandwidth Display Units
```bash
--display-bandwidth-units {bits|bytes}
```
- **Purpose**: Choose bandwidth unit display format
- **Default**: `bits` (Kbit/s, Mbit/s, Gbit/s)
- **Alternative**: `bytes` (KB/s, MB/s, GB/s)
- **Example**: `--display-bandwidth-units bytes`

#### Progress Tracking
```bash
-p, --progress
```
- **Purpose**: Show detailed progress updates with memory usage
- **Default**: Disabled (silent mode)
- **Shows**: Generation stages, memory usage (RSS/Peak), timing per stage
- **Example**: `--progress`

#### API Endpoints
```bash
--onionoo-url URL
```
- **Purpose**: Override default Onionoo Details API endpoint
- **Default**: `https://onionoo.torproject.org/details`
- **Use Case**: Testing, local mirrors, alternative data sources
- **Example**: `--onionoo-url http://localhost:8080/details`

```bash
--onionoo-uptime-url URL
```
- **Purpose**: Override default Onionoo Uptime API endpoint
- **Default**: `https://onionoo.torproject.org/uptime`
- **Use Case**: Local caching, alternative endpoints
- **Example**: `--onionoo-uptime-url http://cache.local/uptime`

```bash
--onionoo-bandwidth-url URL
```
- **Purpose**: Override default Onionoo Bandwidth API endpoint
- **Default**: `https://onionoo.torproject.org/bandwidth`
- **Use Case**: Testing bandwidth features with mock data
- **Example**: `--onionoo-bandwidth-url http://localhost:8080/bandwidth`

#### Caching Configuration
```bash
--bandwidth-cache-hours HOURS
```
- **Purpose**: Set cache duration for bandwidth API data
- **Default**: `12` hours
- **Rationale**: Bandwidth history changes slowly, caching reduces API load
- **Example**: `--bandwidth-cache-hours 24`

---

## 🔧 Common Configuration Scenarios

### Personal Dashboard
Monitor your own relays with frequent updates:
```bash
python3 allium.py \
  --out ~/tor-dashboard \
  --progress
```

### Web Server Deployment
Generate for public web hosting:
```bash
python3 allium.py \
  --out /var/www/html/tor-metrics \
  --display-bandwidth-units bytes \
  --progress
```

### Development/Testing
Use local API mirrors for testing:
```bash
python3 allium.py \
  --out /tmp/test-output \
  --onionoo-url http://localhost:8080/details \
  --onionoo-uptime-url http://localhost:8080/uptime \
  --onionoo-bandwidth-url http://localhost:8080/bandwidth \
  --progress
```

### Low-Memory Systems
Reduce cache time to lower memory usage:
```bash
python3 allium.py \
  --out ./www \
  --bandwidth-cache-hours 6 \
  --progress
```

### Automated Updates
Silent mode for cron jobs (no progress output):
```bash
python3 allium.py --out /var/www/tor-metrics
```

---

## ⏰ Automated Updates (Cron)

### Setup Cron Job

#### Every 6 Hours
```bash
# Edit crontab
crontab -e

# Add this line:
0 */6 * * * cd /path/to/allium && python3 allium.py --out /var/www/tor-metrics
```

#### Daily at 3 AM
```bash
0 3 * * * cd /path/to/allium && python3 allium.py --out /var/www/tor-metrics
```

#### Every 30 Minutes (frequent updates)
```bash
*/30 * * * * cd /path/to/allium && python3 allium.py --out /var/www/tor-metrics
```

### Cron Best Practices

✅ **DO**:
```bash
# Use absolute paths
0 */6 * * * cd /home/user/allium && /usr/bin/python3 allium.py --out /var/www/tor-metrics

# Log output for debugging
0 */6 * * * cd /home/user/allium && python3 allium.py --out /var/www/tor-metrics >> /var/log/allium.log 2>&1

# Set proper environment
0 */6 * * * cd /home/user/allium && source venv/bin/activate && python3 allium.py --out /var/www/tor-metrics
```

❌ **DON'T**:
```bash
# Relative paths (may fail)
0 */6 * * * python3 allium.py

# No logging (can't debug failures)
0 */6 * * * cd /home/user/allium && python3 allium.py --out /var/www/tor-metrics

# Use --progress in cron (creates massive logs)
0 */6 * * * python3 allium.py --progress
```

### Monitoring Cron Jobs

Check cron execution:
```bash
# View cron log
grep CRON /var/log/syslog

# Check allium log (if configured)
tail -f /var/log/allium.log

# Verify last generation time
ls -lh /var/www/tor-metrics/index.html
```

---

## 🌐 Environment Configuration

### Python Virtual Environment (Recommended)

**Create and activate**:
```bash
cd allium
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows
```

**Install dependencies**:
```bash
pip install -r config/requirements.txt
```

**Deactivate when done**:
```bash
deactivate
```

### System-Wide Installation

**Not recommended**, but possible:
```bash
sudo pip3 install -r config/requirements.txt
```

---

## 📊 Output Directory Structure

Generated output follows this structure:
```
www/
├── index.html              # Top 500 relays by consensus weight
├── network-health.html     # Network health dashboard
├── misc/
│   ├── all.html           # All relays
│   ├── aroi-leaderboards.html  # AROI rankings
│   ├── authorities.html   # Directory authorities
│   ├── countries-cw.html  # Countries by consensus weight
│   ├── countries-bw.html  # Countries by bandwidth
│   └── ...                # Other sorted views
├── relay/
│   └── [fingerprint].html # Individual relay pages
├── country/
│   └── [code]/
│       └── index.html     # Country-specific pages
├── as/
│   └── [number]/
│       └── index.html     # AS-specific pages
├── contact/
│   └── [hash]/
│       └── index.html     # Operator contact pages
├── family/
│   └── [hash]/
│       └── index.html     # Family pages
├── platform/
│   └── [name]/
│       └── index.html     # Platform pages
├── first_seen/
│   └── [date]/
│       └── index.html     # First seen pages
└── static/                # CSS, images, flags
```

---

## 🔧 Advanced Configuration

### Custom Templates

To customize the look and feel, modify templates in:
```
allium/templates/
├── base.html          # Base template (header/footer)
├── index.html         # Main page
├── relay.html         # Individual relay pages
├── contact.html       # Operator pages
└── ...
```

**After modification**, regenerate:
```bash
python3 allium.py --out ./www --progress
```

### Custom Static Assets

Modify CSS and images:
```
allium/static/
├── css/
│   └── custom.css     # Add custom styles here
└── images/
    └── ...            # Replace images
```

Static files are automatically copied during generation.

---

## ⚙️ Performance Tuning

### Memory Usage

**Current**: Peak ~3.1GB during generation

**Reduce memory** (if needed):
- Lower bandwidth cache: `--bandwidth-cache-hours 6`
- Generate more frequently (less cached data)
- Use 64-bit Python (handles memory better)

### Generation Speed

**Current**: ~5 minutes for 10,000 relays

**Improve speed**:
- Use faster storage (SSD preferred)
- Ensure good network connection for API calls
- Run on systems with available RAM (no swapping)

### Caching Strategy

**API data caching**:
- Details API: Fetched every generation
- Uptime API: Fetched every generation
- Bandwidth API: Cached for 12 hours (configurable)

**Rationale**: Bandwidth history is relatively stable, caching reduces load on Onionoo API.

---

## 🛡️ Security Considerations

### File Permissions

Set appropriate permissions for output:
```bash
# Web server directory
chmod 755 /var/www/html/tor-metrics
chmod 644 /var/www/html/tor-metrics/*.html
```

### Cron User

Run cron as non-root user:
```bash
# User crontab (recommended)
crontab -e

# Not root crontab
# sudo crontab -e  # DON'T DO THIS
```

### API Endpoints

**Use HTTPS** for all Onionoo API endpoints:
- ✅ `https://onionoo.torproject.org/details`
- ❌ `http://onionoo.torproject.org/details`

---

## 📝 Configuration Checklist

Before deploying to production:

- [ ] Choose appropriate output directory
- [ ] Set bandwidth display units (bits vs bytes)
- [ ] Configure cron schedule for updates
- [ ] Set up logging for cron jobs
- [ ] Verify file permissions
- [ ] Test generation with `--progress` first
- [ ] Monitor first few automated runs
- [ ] Set up monitoring alerts (optional)

---

## 🔍 Troubleshooting

### "Permission denied" on output directory
```bash
# Use a directory you own
python3 allium.py --out ~/allium-output --progress

# Or fix permissions
sudo chown -R $USER:$USER /var/www/html/tor-metrics
```

### "API request failed"
```bash
# Check network connectivity
curl -I https://onionoo.torproject.org/details

# Verify Onionoo status
# Visit https://metrics.torproject.org/
```

### "Out of memory"
```bash
# Reduce cache time
python3 allium.py --bandwidth-cache-hours 6 --progress

# Check available memory
free -h
```

### Generation hangs/stalls
```bash
# Run with progress to see where it hangs
python3 allium.py --progress

# Check network latency to Onionoo
ping onionoo.torproject.org
```

---

## 📚 Related Documentation

- **[Quick Start Guide](quick-start.md)** - Installation and first run
- **[Features Guide](features.md)** - Understanding generated content
- **[Updating Guide](updating.md)** - Keeping Allium current
- **[Development Guide](../development/README.md)** - Contributing and testing

---

**Last Updated**: 2025-11-23  
**Applies to**: Allium v2.0+
