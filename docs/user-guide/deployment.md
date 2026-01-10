# Deployment Guide

**Audience**: Users  
**Scope**: Web server setup and hosting options

## Quick Deploy

```bash
# Generate site
cd allium && python3 allium.py --out /var/www/tor-metrics --progress

# Serve (development)
cd /var/www/tor-metrics && python3 -m http.server 8000
```

## Subdirectory Hosting

Use `--base-url` when hosting under a subdirectory:

```bash
# Hosting at https://example.com/tor-metrics/
python3 allium.py --out /var/www/tor-metrics --base-url "/tor-metrics"
```

This ensures all internal links use the correct path prefix.

## nginx Configuration

```nginx
server {
    listen 80;
    server_name tor-metrics.example.com;
    root /var/www/tor-metrics;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    # Optional: Enable gzip
    gzip on;
    gzip_types text/html text/css application/json;

    # Optional: Cache static assets
    location /static/ {
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
```

## Apache Configuration

```apache
<VirtualHost *:80>
    ServerName tor-metrics.example.com
    DocumentRoot /var/www/tor-metrics
    
    <Directory /var/www/tor-metrics>
        Options Indexes FollowSymLinks
        AllowOverride None
        Require all granted
    </Directory>

    # Optional: Enable compression
    <IfModule mod_deflate.c>
        AddOutputFilterByType DEFLATE text/html text/css application/json
    </IfModule>
</VirtualHost>
```

## GitHub Pages

1. Generate to `docs/` or a `gh-pages` branch
2. Enable GitHub Pages in repository settings
3. Set source to the appropriate branch/folder

```bash
# Generate for GitHub Pages
python3 allium.py --out ./docs --base-url "/repository-name"
git add docs/
git commit -m "Update metrics"
git push
```

## Cloudflare Pages

### Basic Setup

1. Connect repository to Cloudflare Pages
2. Set build command: `cd allium && python3 allium.py --out ../public`
3. Set output directory: `public`

### Search Function

Allium generates `search-index.json` for use with Cloudflare Pages Functions:

1. Create `functions/search.js`:

```javascript
export async function onRequest(context) {
    const url = new URL(context.request.url);
    const query = url.searchParams.get('q');
    
    if (!query) {
        return new Response(JSON.stringify({error: 'Missing query'}), {
            status: 400,
            headers: {'Content-Type': 'application/json'}
        });
    }
    
    // Fetch search index
    const indexUrl = new URL('/search-index.json', url.origin);
    const response = await fetch(indexUrl);
    const index = await response.json();
    
    // Search logic
    const results = index.relays.filter(r => 
        r.nickname.toLowerCase().includes(query.toLowerCase()) ||
        r.fingerprint.toLowerCase().includes(query.toLowerCase())
    ).slice(0, 20);
    
    return new Response(JSON.stringify(results), {
        headers: {'Content-Type': 'application/json'}
    });
}
```

2. Deploy - Cloudflare automatically picks up the function

## Automated Updates (Cron)

```bash
# Update every 6 hours
0 */6 * * * cd /path/to/allium && python3 allium.py --out /var/www/tor-metrics >> /var/log/allium.log 2>&1

# Update daily at 3 AM
0 3 * * * cd /path/to/allium && python3 allium.py --out /var/www/tor-metrics
```

### Memory Considerations

For cron jobs on memory-constrained systems:

```bash
# Low memory mode (~400MB)
0 */6 * * * cd /path/to/allium && python3 allium.py --apis details --out /var/www/tor-metrics
```

## Disk Space

Typical output size: ~500MB

Ensure sufficient disk space before generation. Old files are overwritten, not accumulated.

## How to Verify

```bash
# Test local deployment
python3 -m http.server 8000 --directory /var/www/tor-metrics

# Verify pages load
curl -I http://localhost:8000/
curl -I http://localhost:8000/top500.html
curl -I http://localhost:8000/network-health.html
```
