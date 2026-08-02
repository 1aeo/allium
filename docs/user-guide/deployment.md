# Deployment Guide

**Audience**: Users  
**Scope**: Web server setup and hosting options

## Quick Deploy

```bash
# Generate into staging, then publish only after a successful exit.
cd allium
(
  set -eu
  staging_dir="$(mktemp -d)"
  trap 'rm -rf -- "$staging_dir"' EXIT
  python3 allium.py --out "$staging_dir" \
    --base-url https://metrics.example.com --progress
  rsync -a --delete "$staging_dir"/ /var/www/tor-metrics/
)

# Serve (development)
cd /var/www/tor-metrics && python3 -m http.server 8000
```

The generator exits non-zero when generation fails, including when the final
crawl-size guard finds an oversized page. Keep generation and publication as
separate steps: only synchronize the staging directory after the generator
returns zero. This leaves the currently published site untouched on failure.

## Subdirectory Hosting

Use an absolute `--base-url` in production. It is the origin for canonical and
Open Graph URLs and enables `sitemap.xml` generation:

```bash
python3 allium.py --out /var/www/tor-metrics \
  --base-url "https://example.com/tor-metrics"
```

A root-relative value still supports local or subdirectory previews, but only
root-relative canonicals are emitted and the public sitemap is skipped:

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
        try_files $uri $uri/ $uri.html =404;
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
python3 allium.py --out ./docs --base-url "/repository-name" && \
  git add docs/ && \
  git commit -m "Update metrics" && \
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
            headers: {
                'Content-Type': 'application/json',
                'X-Robots-Tag': 'noindex, follow'
            }
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

Put the staged generation and `rsync` sequence from Quick Deploy in an
executable `/path/to/deploy-allium.sh`. The script must use `set -e` (or an
explicit exit-status check) so a generator failure prevents `rsync`.

```bash
# Update every 6 hours
0 */6 * * * /path/to/deploy-allium.sh >> /var/log/allium.log 2>&1

# Update daily at 3 AM
0 3 * * * /path/to/deploy-allium.sh
```

### Memory Considerations

For cron jobs on memory-constrained systems:

```bash
# Low memory mode (~400MB): add --apis details to the generator command in
# deploy-allium.sh, then keep the same failure-gated cron entry.
0 */6 * * * /path/to/deploy-allium.sh
```

## Disk Space

Full-API output can require several gigabytes. Pagination keeps every generated
HTML page below Allium's 1,900,000-byte crawler guard.

Ensure sufficient disk space before generation. Old files are overwritten, not accumulated.

## How to Verify

```bash
# Test local deployment
python3 -m http.server 8000 --directory /var/www/tor-metrics

# Verify pages load
curl -I http://localhost:8000/
curl -I http://localhost:8000/top500.html
curl -I http://localhost:8000/network-health.html

# After production deployment, purge stale crawler-discovery cache keys and verify
curl -fsS https://metrics.example.com/robots.txt
curl -fsS https://metrics.example.com/sitemap.xml | head
curl -fsS https://metrics.example.com/ | grep -E 'canonical|site-verification'
```

Production automation should explicitly purge `/robots.txt` and `/sitemap.xml`
after publishing. Search result/disambiguation HTML should return
`X-Robots-Tag: noindex, follow`; direct search matches may remain redirects.
