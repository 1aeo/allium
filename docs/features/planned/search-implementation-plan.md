# Allium Search Implementation Plan

**Status**: 📋 Planned  
**Created**: December 2024  
**Priority**: High Value  
**Estimated Effort**: 3 days  
**Dependencies**: Cloudflare Pages Functions (existing infrastructure)

---

## Executive Summary

### Overview

Implement server-side search functionality for Tor relay metrics without client-side JavaScript, using Cloudflare Pages Functions. Users can search by relay fingerprint, nickname, operator (AROI domain), AS number, country, IP address, and family—with intelligent disambiguation when multiple results match.

### Key Benefits

| Benefit | Description |
|---------|-------------|
| **Zero JavaScript** | Works with JS disabled; pure HTML form + server redirect |
| **Fast** | Edge-computed at 300+ Cloudflare locations worldwide |
| **Free** | Well within Cloudflare's 100K requests/day free tier |
| **Simple** | Single static JSON file + one function; deploys with site |
| **Smart** | Auto-detects families, suggests related results |
| **Secure** | Input validation, XSS prevention, safe redirects, CSP headers |

### Search Capabilities

| Query Type | Example | Result |
|------------|---------|--------|
| Fingerprint (full/partial) | `ABCD1234...` | Direct to relay page |
| Nickname | `MyTorRelay` | Direct to relay (or family if shared) |
| AROI Domain | `torworld.org` | Direct to contact page |
| AS Number | `AS24940` or `24940` | Direct to AS page |
| Country | `Germany` or `de` | Direct to country page |
| IP Address | `1.2.3.4` | Direct to relay page |
| Family Prefix | `emerald` | Direct to family page |
| Platform/Flag | `linux`, `exit` | Direct to category page |

### Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  HTML Form  │────▶│  /search?q=...   │────▶│  Pages Function │
│  (any page) │     │  (GET request)   │     │  (search.js)    │
└─────────────┘     └──────────────────┘     └────────┬────────┘
                                                      │
                    ┌──────────────────┐              │
                    │ search-index.json│◀─────────────┘
                    │ (static file)    │   fetch + cache
                    └──────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  302 Redirect    │
                    │  /relay/[fp]/    │
                    └──────────────────┘
```

### Deliverables

1. **Search Index Generator** (`allium/lib/search_index.py`) - Python module for Allium
2. **Search Function** (`functions/search.js`) - Cloudflare Pages Function for allium-deploy
3. **Search Form** - HTML addition to `skeleton.html` template
4. **Disambiguation Page** - HTML template for multiple results

### Timeline

| Phase | Effort | Description |
|-------|--------|-------------|
| Index Generator | 1 day | Python module + integration |
| Search Function | 1 day | Cloudflare function + tests |
| UI Integration | 0.5 day | Form + disambiguation template |
| Testing | 0.5 day | End-to-end validation |
| **Total** | **3 days** | |

### Resource Requirements

| Resource | Estimate |
|----------|----------|
| Index file size | ~250 KB (gzip) |
| Function memory | <10 MB |
| Latency | <50ms (cached) |
| Cost | $0 (free tier) |

### Security Summary

| Protection | Implementation |
|------------|----------------|
| **Input Validation** | Query length limit (100 chars), character allowlist |
| **XSS Prevention** | All output HTML-escaped, CSP blocks inline scripts |
| **Open Redirect** | Path allowlist validation before redirect |
| **DoS Mitigation** | Query limits, Cloudflare rate limiting |
| **Error Handling** | Generic messages to users, detailed server logs |
| **Security Headers** | X-Frame-Options, CSP, X-Content-Type-Options |

---

## Backend Options Considered

### Why Cloudflare Pages Functions (Option 4B)

We evaluated multiple backend options for handling the search form submission:

| Option | Infrastructure | Complexity | Vendor Lock-in | Cost | Decision |
|--------|---------------|------------|----------------|------|----------|
| **4A: Cloudflare Workers (Standalone)** | Separate deployment | Medium | Medium | Free | ❌ More complex |
| **4B: Cloudflare Pages Functions** | Integrated | Low | Medium | Free | ✅ **Selected** |
| **4C: Vercel Edge Functions** | Migration required | Medium | Medium | Free | ❌ Migration needed |
| **4D: Netlify Edge Functions** | Migration required | Medium | Medium | Free | ❌ Migration needed |

**Cloudflare Pages Functions was selected because:**

1. **Already deployed** - allium-deploy uses Cloudflare Pages
2. **Single deployment** - Function deploys with static site automatically
3. **Automatic routing** - `functions/search.js` handles `/search` automatically
4. **Best free tier** - 100K requests/day (3M/month) vs 100K/month for alternatives
5. **Zero additional configuration** - No separate wrangler.toml needed

### Storage Decision: Static File vs R2

We chose to store `search-index.json` as a **static Pages file** rather than in R2:

| Aspect | R2 Binding | Static File |
|--------|------------|-------------|
| Deployment | Separate upload | ✅ Automatic |
| Sync with site | Manual | ✅ Always |
| Configuration | Required | ✅ None |
| Performance | ~0.5ms | ~2ms (cached) |
| Complexity | Higher | ✅ Lower |

The ~1.5ms difference is negligible for a search redirect.

---

## Search Index Specification

### Searchable Fields

#### Tier 1: Primary Search Targets (Essential)

| Field | Source | Example | Redirects To |
|-------|--------|---------|--------------|
| **Fingerprint** | `relay['fingerprint']` | `ABCD1234...` (40 hex) | `/relay/ABCD1234.../` |
| **Nickname** | `relay['nickname']` | `MyTorRelay` | `/relay/[fingerprint]/` |
| **AROI Domain** | `relay['aroi_domain']` | `torworld.org` | `/contact/[md5]/` |
| **Contact Hash** | `relay['contact_md5']` | `a1b2c3d4...` (32 hex) | `/contact/[md5]/` |

#### Tier 2: Secondary Search Targets (High Value)

| Field | Source | Example | Redirects To |
|-------|--------|---------|--------------|
| **AS Number** | `relay['as']` | `AS24940` | `/as/AS24940/` |
| **AS Name** | `relay['as_name']` | `Hetzner` | `/as/[as_number]/` |
| **Country Code** | `relay['country']` | `DE`, `US` | `/country/de/` |
| **Country Name** | `relay['country_name']` | `Germany` | `/country/de/` |
| **IP Address** | `relay['or_addresses']` | `1.2.3.4` | `/relay/[fingerprint]/` |

#### Tier 3: Convenience Search Targets

| Field | Source | Example | Redirects To |
|-------|--------|---------|--------------|
| **Platform** | `relay['platform']` | `linux`, `freebsd` | `/platform/linux/` |
| **Flag** | `relay['flags']` | `Exit`, `Guard` | `/flag/exit/` |
| **Family** | `relay['effective_family'][0]` | `ABCD1234...` | `/family/ABCD.../` |

### Family-Specific Search Fields

For families without AROI domain or matching contacts:

| Field | Description | Example Query |
|-------|-------------|---------------|
| **Family fingerprint** | Full or partial | `ABCD1234` |
| **Nickname prefix** | Auto-detected pattern | `emerald`, `calyx` |
| **Any member nickname** | Exact or partial | `relay2`, `exit-de` |
| **Any member fingerprint** | Full fingerprint | `EFGH5678...` |
| **AS numbers** | Networks in family | `AS24940` |
| **Countries** | Country codes | `de` |

### Index JSON Structure

```json
{
  "meta": {
    "generated_at": "2025-01-06T12:00:00Z",
    "relay_count": 7234,
    "family_count": 1847,
    "version": "1.0"
  },
  
  "relays": [
    {
      "f": "ABCD1234567890ABCD1234567890ABCD12345678",
      "n": "MyTorRelay",
      "a": "torworld.org",
      "c": "a1b2c3d4e5f6...",
      "as": "AS24940",
      "cc": "de",
      "ip": ["1.2.3.4", "2001:db8::1"],
      "fam": "ABCD1234..."
    }
  ],
  
  "families": [
    {
      "id": "ABCD1234567890ABCD1234567890ABCD12345678",
      "sz": 12,
      "nn": ["relay1", "relay2", "exit-de", "exit-us"],
      "px": "relay",
      "pxg": true,
      "a": "torworld.org",
      "c": ["a1b2c3...", "e5f6g7..."],
      "as": ["AS24940", "AS16276"],
      "cc": ["de", "us", "nl"],
      "fs": "2020-03-15"
    }
  ],
  
  "lookups": {
    "as_names": {
      "AS24940": "Hetzner Online GmbH",
      "AS16276": "OVH SAS"
    },
    "country_names": {
      "de": "Germany",
      "us": "United States"
    },
    "platforms": ["linux", "freebsd", "windows", "darwin"],
    "flags": ["exit", "guard", "stable", "fast", "hsdir", "v2dir"]
  }
}
```

**Key legend:**
- `f`: fingerprint
- `n`: nickname
- `a`: aroi_domain
- `c`: contact_md5 (or array for families)
- `as`: AS number(s)
- `cc`: country_code(s)
- `ip`: IP addresses
- `fam`: family_id (for relays in families)
- `sz`: size (relay count)
- `nn`: nicknames (all member nicknames)
- `px`: prefix (detected naming pattern)
- `pxg`: prefix_generic (boolean)
- `fs`: first_seen

### Size Estimates

| Component | Uncompressed | Gzip |
|-----------|-------------|------|
| Relays (~7,000) | ~800 KB | ~150 KB |
| Families (~2,000) | ~400 KB | ~80 KB |
| Lookups (AS, countries, etc.) | ~50 KB | ~15 KB |
| **Total** | **~1.25 MB** | **~250 KB** |

---

## Search Logic

### Decision Flowchart

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER QUERY                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. Is it a 40-char hex fingerprint?                             │
│    YES → Is it a relay fingerprint?                             │
│          YES → REDIRECT to /relay/[fp]/                         │
│          NO  → Is it a family fingerprint?                      │
│                YES → REDIRECT to /family/[fp]/                  │
│                NO  → NOT FOUND                                  │
└─────────────────────────────────────────────────────────────────┘
                              │ NO
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Is it a partial hex fingerprint (6-39 chars)?                │
│    YES → Find matching relays AND families                      │
│          1 relay match  → REDIRECT to /relay/[fp]/              │
│          1 family match → REDIRECT to /family/[fp]/             │
│          Multiple       → SHOW disambiguation page              │
└─────────────────────────────────────────────────────────────────┘
                              │ NO
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Is it an exact nickname match?                               │
│    YES → How many relays match?                                 │
│          1 relay  → REDIRECT to /relay/[fp]/                    │
│          Multiple → Are they in the SAME family?                │
│                     YES → REDIRECT to /family/[fp]/             │
│                     NO  → SHOW disambiguation page              │
└─────────────────────────────────────────────────────────────────┘
                              │ NO
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Is it a family nickname prefix?                              │
│    YES → REDIRECT to /family/[fp]/                              │
└─────────────────────────────────────────────────────────────────┘
                              │ NO
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. Is it an AROI domain?                                        │
│    YES → REDIRECT to /contact/[md5]/                            │
└─────────────────────────────────────────────────────────────────┘
                              │ NO
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. Is it an AS number? (AS12345 or just 12345)                  │
│    YES → REDIRECT to /as/AS12345/                               │
└─────────────────────────────────────────────────────────────────┘
                              │ NO
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. Is it a country code or name?                                │
│    YES → REDIRECT to /country/[code]/                           │
└─────────────────────────────────────────────────────────────────┘
                              │ NO
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. Is it an IP address?                                         │
│    YES → Find relay with this IP                                │
│          → REDIRECT to /relay/[fp]/                             │
└─────────────────────────────────────────────────────────────────┘
                              │ NO
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 9. Is it a platform or flag?                                    │
│    YES → REDIRECT to /platform/[name]/ or /flag/[name]/         │
└─────────────────────────────────────────────────────────────────┘
                              │ NO
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 10. Fuzzy nickname search (contains)                            │
│     1 match    → REDIRECT to /relay/[fp]/                       │
│     Multiple   → Check if same family, else SHOW list           │
│     0 matches  → Continue to step 11                            │
└─────────────────────────────────────────────────────────────────┘
                              │ NO
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 11. Family nickname search (any member contains query)          │
│     1 match   → REDIRECT to /family/[fp]/                       │
│     Multiple  → SHOW disambiguation                             │
│     0 matches → NOT FOUND                                       │
└─────────────────────────────────────────────────────────────────┘
```

### Family vs Relay Detection

| Query Type | Detection Method | Result |
|-------------|------------------|--------|
| **Relay** | Exact fingerprint, unique nickname, IP match | → `/relay/[fp]/` |
| **Family** | Family fingerprint, prefix pattern, all-same-family nicknames | → `/family/[fp]/` |
| **Contact** | AROI domain | → `/contact/[md5]/` |
| **Ambiguous** | Multiple relays in different families | → Disambiguation page |
| **Ambiguous (same family)** | Multiple relays, same family | → Show family suggestion |

**Key insight:** If multiple relays match and they share the same family, promote the family page.

---

## Technical Implementation

### 1. Search Index Generator

#### File: `allium/lib/search_index.py`

```python
"""
File: allium/lib/search_index.py

Search index generator for Cloudflare Pages Function search.
Generates a compact JSON index of relays and families for server-side search.

Design principles:
- Compute-efficient: All processing done at build time
- Compact output: Short keys, minimal redundancy
- DRY: Reusable helper functions
"""

import json
import os
from typing import Any, Dict, List, Optional, Set


# =============================================================================
# CONSTANTS
# =============================================================================

MIN_PREFIX_LENGTH = 3
PREFIX_STRIP_CHARS = '-_0123456789'
GENERIC_PREFIXES = frozenset({
    'relay', 'tor', 'exit', 'guard', 'node', 'server', 
    'unnamed', 'default', 'test', 'my'
})


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def extract_ip_from_or_address(or_address: str) -> Optional[str]:
    """
    Extract IP address from OR address string.
    Handles IPv4 "1.2.3.4:9001" and IPv6 "[2001:db8::1]:9001".
    """
    if not or_address:
        return None
    
    if or_address.startswith('['):
        bracket_end = or_address.find(']')
        if bracket_end > 1:
            return or_address[1:bracket_end]
    else:
        colon_pos = or_address.rfind(':')
        if colon_pos > 0:
            return or_address[:colon_pos]
        return or_address
    
    return None


def extract_common_prefix(nicknames: List[str]) -> Optional[str]:
    """
    Find the longest common prefix among a list of nicknames.
    Used to detect operator naming patterns.
    """
    if not nicknames or len(nicknames) < 2:
        return None
    
    valid_names = [n for n in nicknames if n]
    if len(valid_names) < 2:
        return None
    
    sorted_names = sorted(valid_names, key=str.lower)
    first = sorted_names[0].lower()
    last = sorted_names[-1].lower()
    
    prefix_len = 0
    for i, char in enumerate(first):
        if i < len(last) and first[i] == last[i]:
            prefix_len += 1
        else:
            break
    
    if prefix_len < MIN_PREFIX_LENGTH:
        return None
    
    prefix = sorted_names[0][:prefix_len].rstrip(PREFIX_STRIP_CHARS)
    
    if len(prefix) < MIN_PREFIX_LENGTH:
        return None
    
    return prefix


def is_generic_prefix(prefix: str) -> bool:
    """Check if a prefix is generic/common."""
    return prefix.lower() in GENERIC_PREFIXES


def compact_relay_entry(relay: Dict[str, Any], family_id: Optional[str]) -> Dict[str, Any]:
    """Create a compact relay entry for the search index."""
    entry = {
        'f': relay['fingerprint'],
        'n': relay.get('nickname', ''),
    }
    
    aroi = relay.get('aroi_domain')
    if aroi and aroi != 'none':
        entry['a'] = aroi
    
    contact_md5 = relay.get('contact_md5')
    if contact_md5:
        entry['c'] = contact_md5
    
    as_number = relay.get('as')
    if as_number:
        entry['as'] = as_number
    
    country = relay.get('country')
    if country:
        entry['cc'] = country.lower()
    
    ips = []
    for addr in relay.get('or_addresses', []):
        ip = extract_ip_from_or_address(addr)
        if ip:
            ips.append(ip)
    if ips:
        entry['ip'] = ips
    
    if family_id:
        entry['fam'] = family_id
    
    return entry


def compact_family_entry(
    family_id: str,
    family_data: Dict[str, Any],
    relays: List[Dict[str, Any]],
    relay_indices: List[int]
) -> Dict[str, Any]:
    """Create a compact family entry for the search index."""
    members = [relays[idx] for idx in relay_indices]
    
    nicknames = [m.get('nickname', '') for m in members if m.get('nickname')]
    prefix = extract_common_prefix(nicknames)
    
    as_numbers = sorted(set(m.get('as') for m in members if m.get('as')))
    countries = sorted(set(m.get('country', '').lower() for m in members if m.get('country')))
    contact_hashes = sorted(set(m.get('contact_md5') for m in members if m.get('contact_md5')))
    
    entry = {
        'id': family_id,
        'sz': len(members),
        'nn': nicknames,
    }
    
    if prefix:
        entry['px'] = prefix
        entry['pxg'] = is_generic_prefix(prefix)
    
    aroi = family_data.get('aroi_domain')
    if aroi and aroi != 'none':
        entry['a'] = aroi
    
    if contact_hashes:
        entry['c'] = contact_hashes
    
    if as_numbers:
        entry['as'] = as_numbers
    
    if countries:
        entry['cc'] = countries
    
    first_seen = family_data.get('first_seen', '')
    if first_seen:
        entry['fs'] = first_seen.split(' ')[0]
    
    return entry


# =============================================================================
# MAIN GENERATOR
# =============================================================================

def generate_search_index(relays_data: Dict[str, Any], output_path: str) -> Dict[str, int]:
    """
    Generate a compact search index for the Cloudflare Pages Function.
    """
    relays = relays_data.get('relays', [])
    sorted_data = relays_data.get('sorted', {})
    family_data = sorted_data.get('family', {})
    
    # Build family membership map
    family_membership: Dict[str, str] = {}
    for family_id, fdata in family_data.items():
        for idx in fdata.get('relays', []):
            relay_fp = relays[idx]['fingerprint']
            family_membership[relay_fp] = family_id
    
    index = {
        'meta': {
            'generated_at': relays_data.get('relays_published', ''),
            'relay_count': len(relays),
            'family_count': len(family_data),
            'version': '1.0'
        },
        'relays': [],
        'families': [],
        'lookups': {
            'as_names': {},
            'country_names': {},
            'platforms': set(),
            'flags': set()
        }
    }
    
    # Process relays
    for relay in relays:
        fp = relay['fingerprint']
        family_id = family_membership.get(fp)
        
        if family_id and len(family_data.get(family_id, {}).get('relays', [])) < 2:
            family_id = None
        
        entry = compact_relay_entry(relay, family_id)
        index['relays'].append(entry)
        
        if relay.get('as') and relay.get('as_name'):
            index['lookups']['as_names'][relay['as']] = relay['as_name']
        
        if relay.get('country') and relay.get('country_name'):
            index['lookups']['country_names'][relay['country'].lower()] = relay['country_name']
        
        if relay.get('platform'):
            index['lookups']['platforms'].add(relay['platform'].lower())
        
        for flag in relay.get('flags', []):
            index['lookups']['flags'].add(flag.lower())
    
    # Process families
    for family_id, fdata in family_data.items():
        relay_indices = fdata.get('relays', [])
        if len(relay_indices) < 2:
            continue
        
        entry = compact_family_entry(family_id, fdata, relays, relay_indices)
        index['families'].append(entry)
    
    # Convert sets to sorted lists
    index['lookups']['platforms'] = sorted(index['lookups']['platforms'])
    index['lookups']['flags'] = sorted(index['lookups']['flags'])
    
    # Write minified JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, separators=(',', ':'), ensure_ascii=False)
    
    file_size = os.path.getsize(output_path)
    
    return {
        'relay_count': len(index['relays']),
        'family_count': len(index['families']),
        'as_count': len(index['lookups']['as_names']),
        'country_count': len(index['lookups']['country_names']),
        'file_size_bytes': file_size,
        'file_size_kb': round(file_size / 1024, 1)
    }
```

#### Integration with `allium.py`

Add after page generation, before completion message:

```python
# Generate search index
from lib.search_index import generate_search_index

progress_logger.log("Generating search index...")
search_index_path = os.path.join(args.output_dir, "search-index.json")
search_stats = generate_search_index(RELAY_SET.json, search_index_path)
progress_logger.log(
    f"Generated search index: {search_stats['relay_count']} relays, "
    f"{search_stats['family_count']} families, {search_stats['file_size_kb']} KB"
)
```

---

### 2. Cloudflare Pages Function

#### File: `functions/search.js` (for allium-deploy repository)

```javascript
/**
 * File: functions/search.js
 * 
 * Cloudflare Pages Function for server-side relay search.
 * 
 * Design principles:
 * - Compute-efficient: Precompiled regex, early returns
 * - DRY: Reusable search helpers
 * - Cache-optimized: In-memory index caching per worker instance
 * - Security-first: Input validation, XSS prevention, safe redirects
 */

// =============================================================================
// SECURITY CONSTANTS
// =============================================================================

const SECURITY = {
  // Maximum query length to prevent DoS
  MAX_QUERY_LENGTH: 100,
  
  // Allowed characters in search queries (alphanumeric, common punctuation)
  ALLOWED_QUERY_PATTERN: /^[A-Za-z0-9\s\-_.@:]+$/,
  
  // Valid path segments (alphanumeric, hyphen, underscore)
  SAFE_PATH_PATTERN: /^[A-Za-z0-9\-_]+$/,
};

// Valid redirect path prefixes (allowlist)
const SAFE_REDIRECT_PREFIXES = [
  '/relay/',
  '/family/',
  '/contact/',
  '/as/',
  '/country/',
  '/platform/',
  '/flag/',
  '/first_seen/',
  '/'  // Homepage only (exact match)
];

// Security headers for HTML responses
const SECURITY_HEADERS = {
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
  'X-XSS-Protection': '1; mode=block',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Content-Security-Policy': [
    "default-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "script-src 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
    "base-uri 'self'"
  ].join('; ')
};

// =============================================================================
// PRECOMPILED PATTERNS (ReDoS-safe: simple, non-backtracking)
// =============================================================================

const PATTERNS = {
  FULL_FINGERPRINT: /^[A-Fa-f0-9]{40}$/,
  PARTIAL_FINGERPRINT: /^[A-Fa-f0-9]{6,39}$/,
  IP_ADDRESS: /^[\d.:a-fA-F]+$/,
  AS_NUMBER: /^(?:AS)?(\d+)$/i,
};

// =============================================================================
// CACHE
// =============================================================================

let cachedIndex = null;
let cacheTimestamp = 0;
const CACHE_TTL_MS = 300000; // 5 minutes

// =============================================================================
// SECURITY HELPERS
// =============================================================================

/**
 * Sanitize and validate user query input.
 */
function sanitizeQuery(query) {
  if (!query) {
    return { valid: false, sanitized: '', error: 'Empty query' };
  }
  
  const str = String(query);
  
  if (str.length > SECURITY.MAX_QUERY_LENGTH) {
    return { 
      valid: false, 
      sanitized: '', 
      error: `Query too long (max ${SECURITY.MAX_QUERY_LENGTH} characters)` 
    };
  }
  
  const trimmed = str.trim();
  
  if (!trimmed) {
    return { valid: false, sanitized: '', error: 'Empty query' };
  }
  
  if (!SECURITY.ALLOWED_QUERY_PATTERN.test(trimmed)) {
    return { 
      valid: false, 
      sanitized: '', 
      error: 'Query contains invalid characters' 
    };
  }
  
  return { valid: true, sanitized: trimmed, error: null };
}

/**
 * Validate a value is safe for use in URL paths.
 */
function isSafePathSegment(value) {
  if (!value || typeof value !== 'string') return false;
  if (value.includes('..')) return false;
  if (value.includes('/')) return false;
  if (value.includes('\\')) return false;
  return SECURITY.SAFE_PATH_PATTERN.test(value);
}

/**
 * Escape HTML special characters to prevent XSS.
 */
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/`/g, '&#96;')
    .replace(/\//g, '&#x2F;');
}

/**
 * Create a safe redirect response with path validation.
 */
function safeRedirect(origin, path) {
  const isAllowed = SAFE_REDIRECT_PREFIXES.some(prefix => {
    if (prefix === '/') return path === '/';
    return path.startsWith(prefix);
  });
  
  if (!isAllowed) {
    console.error(`Blocked unsafe redirect: ${path}`);
    return secureResponse('Invalid redirect target', 400);
  }
  
  if (path.includes('://') || path.startsWith('//')) {
    console.error(`Blocked protocol in redirect: ${path}`);
    return secureResponse('Invalid redirect target', 400);
  }
  
  const fullUrl = new URL(path, origin).toString();
  return Response.redirect(fullUrl, 302);
}

/**
 * Create a response with security headers.
 */
function secureResponse(body, status = 200, additionalHeaders = {}) {
  return new Response(body, {
    status,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      ...SECURITY_HEADERS,
      ...additionalHeaders
    }
  });
}

/**
 * Handle errors securely without exposing internal details.
 */
function handleError(error, query) {
  console.error('Search error:', {
    message: error.message,
    stack: error.stack,
    query: query?.substring(0, 50)
  });
  
  return secureResponse(`
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Search Error</title>
      <link rel="stylesheet" href="/static/css/bootstrap.min.css">
    </head>
    <body style="padding: 40px; text-align: center;">
      <h2>Search Temporarily Unavailable</h2>
      <p>Please try again in a few moments.</p>
      <p><a href="/">← Back to home</a></p>
    </body>
    </html>
  `, 503);
}

// =============================================================================
// INDEX LOADER
// =============================================================================

async function loadIndex(originUrl) {
  const now = Date.now();
  
  if (cachedIndex && (now - cacheTimestamp) < CACHE_TTL_MS) {
    return cachedIndex;
  }
  
  const response = await fetch(new URL('/search-index.json', originUrl), {
    cf: { cacheEverything: true, cacheTtl: 1800 }
  });
  
  if (!response.ok) {
    throw new Error(`Index load failed: ${response.status}`);
  }
  
  cachedIndex = await response.json();
  cacheTimestamp = now;
  
  return cachedIndex;
}

// =============================================================================
// SEARCH HELPERS
// =============================================================================

function findRelays(relays, predicate, limit = 20) {
  const results = [];
  for (const relay of relays) {
    if (predicate(relay)) {
      results.push(relay);
      if (results.length >= limit) break;
    }
  }
  return results;
}

function findFamilies(families, predicate, limit = 10) {
  const results = [];
  for (const family of families) {
    if (predicate(family)) {
      results.push(family);
      if (results.length >= limit) break;
    }
  }
  return results;
}

function getSharedFamily(relays) {
  if (!relays || relays.length === 0) return null;
  
  const familyIds = new Set();
  for (const relay of relays) {
    if (relay.fam) familyIds.add(relay.fam);
  }
  
  return familyIds.size === 1 ? [...familyIds][0] : null;
}

const Result = {
  relay: (fingerprint) => ({ type: 'relay', fingerprint }),
  family: (familyId) => ({ type: 'family', familyId }),
  contact: (contactMd5) => ({ type: 'contact', contactMd5 }),
  as: (asNumber) => ({ type: 'as', asNumber }),
  country: (countryCode) => ({ type: 'country', countryCode }),
  platform: (platform) => ({ type: 'platform', platform }),
  flag: (flag) => ({ type: 'flag', flag }),
  multiple: (matches, hint) => ({ type: 'multiple', matches, hint }),
  notFound: (query) => ({ type: 'not_found', query })
};

// =============================================================================
// MAIN SEARCH
// =============================================================================

function search(query, index) {
  const q = query.trim();
  if (!q) return Result.notFound('');
  
  const qLower = q.toLowerCase();
  const qUpper = q.toUpperCase();
  const { relays, families, lookups } = index;
  
  // Step 1: Full fingerprint
  if (PATTERNS.FULL_FINGERPRINT.test(q)) {
    const relay = relays.find(r => r.f.toUpperCase() === qUpper);
    if (relay) return Result.relay(relay.f);
    
    const family = families.find(f => f.id.toUpperCase() === qUpper);
    if (family) return Result.family(family.id);
    
    return Result.notFound(q);
  }
  
  // Step 2: Partial fingerprint
  if (PATTERNS.PARTIAL_FINGERPRINT.test(q)) {
    const relayMatches = findRelays(relays, r => r.f.toUpperCase().startsWith(qUpper), 10);
    const familyMatches = findFamilies(families, f => f.id.toUpperCase().startsWith(qUpper), 5);
    
    if (relayMatches.length === 1 && familyMatches.length === 0) {
      return Result.relay(relayMatches[0].f);
    }
    if (familyMatches.length === 1 && relayMatches.length === 0) {
      return Result.family(familyMatches[0].id);
    }
    if (relayMatches.length > 0 || familyMatches.length > 0) {
      return Result.multiple({ relays: relayMatches, families: familyMatches }, 'fingerprint');
    }
  }
  
  // Step 3: Exact nickname
  const exactNicknameMatches = findRelays(relays, r => r.n.toLowerCase() === qLower, 50);
  
  if (exactNicknameMatches.length === 1) {
    return Result.relay(exactNicknameMatches[0].f);
  }
  if (exactNicknameMatches.length > 1) {
    const sharedFamily = getSharedFamily(exactNicknameMatches);
    if (sharedFamily) return Result.family(sharedFamily);
    return Result.multiple({ relays: exactNicknameMatches }, 'nickname');
  }
  
  // Step 4: Family prefix
  let prefixMatch = families.find(f => f.px && f.px.toLowerCase() === qLower && !f.pxg);
  if (!prefixMatch) {
    prefixMatch = families.find(f => f.px && f.px.toLowerCase() === qLower);
  }
  if (prefixMatch) return Result.family(prefixMatch.id);
  
  // Step 5: AROI domain
  const aroiRelay = relays.find(r => r.a && r.a.toLowerCase() === qLower);
  if (aroiRelay && aroiRelay.c) return Result.contact(aroiRelay.c);
  
  const aroiFamily = families.find(f => f.a && f.a.toLowerCase() === qLower);
  if (aroiFamily) return Result.family(aroiFamily.id);
  
  // Step 6: AS number
  const asMatch = PATTERNS.AS_NUMBER.exec(q);
  if (asMatch && lookups.as_names[`AS${asMatch[1]}`]) {
    return Result.as(`AS${asMatch[1]}`);
  }
  
  const asNameEntry = Object.entries(lookups.as_names).find(
    ([, name]) => name.toLowerCase().includes(qLower)
  );
  if (asNameEntry) return Result.as(asNameEntry[0]);
  
  // Step 7: Country
  if (lookups.country_names[qLower]) return Result.country(qLower);
  
  const countryByName = Object.entries(lookups.country_names).find(
    ([, name]) => name.toLowerCase() === qLower
  );
  if (countryByName) return Result.country(countryByName[0]);
  
  // Step 8: IP address
  if (PATTERNS.IP_ADDRESS.test(q) && (q.includes('.') || q.includes(':'))) {
    const ipMatch = relays.find(r => r.ip && r.ip.includes(q));
    if (ipMatch) return Result.relay(ipMatch.f);
  }
  
  // Step 9: Platform or flag
  if (lookups.platforms.includes(qLower)) return Result.platform(qLower);
  if (lookups.flags.includes(qLower)) return Result.flag(qLower);
  
  // Step 10: Fuzzy nickname
  const fuzzyMatches = findRelays(relays, r => r.n.toLowerCase().includes(qLower), 30);
  
  if (fuzzyMatches.length === 1) return Result.relay(fuzzyMatches[0].f);
  if (fuzzyMatches.length > 1) {
    const sharedFamily = getSharedFamily(fuzzyMatches);
    return Result.multiple(
      { relays: fuzzyMatches.slice(0, 20), suggestedFamily: sharedFamily },
      'fuzzy_nickname'
    );
  }
  
  // Step 11: Family nickname search
  const familyNicknameMatches = findFamilies(families,
    f => f.nn.some(n => n.toLowerCase().includes(qLower)), 10);
  
  if (familyNicknameMatches.length === 1) return Result.family(familyNicknameMatches[0].id);
  if (familyNicknameMatches.length > 1) {
    return Result.multiple({ families: familyNicknameMatches }, 'family_nickname');
  }
  
  return Result.notFound(q);
}

// =============================================================================
// RESPONSE RENDERERS
// =============================================================================

function renderDisambiguationPage(matches, query, hint) {
  const relays = matches.relays || [];
  const families = matches.families || [];
  const suggestedFamily = matches.suggestedFamily;
  
  let html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Search Results - ${escapeHtml(query)}</title>
  <link rel="stylesheet" href="/static/css/bootstrap.min.css">
  <style>
    body { padding: 20px; font-family: sans-serif; }
    .suggestion { background: #e7f3ff; padding: 15px; border-radius: 5px; margin: 15px 0; }
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
    th { background: #f5f5f5; }
    code { background: #f0f0f0; padding: 2px 5px; border-radius: 3px; font-size: 12px; }
  </style>
</head>
<body>
  <h2>Search Results for "${escapeHtml(query)}"</h2>`;

  if (suggestedFamily && isSafePathSegment(suggestedFamily)) {
    html += `
  <div class="suggestion">
    <strong>💡 These relays appear to be in the same family:</strong><br>
    <a href="/family/${escapeHtml(suggestedFamily)}/">View Family</a>
  </div>`;
  }

  if (relays.length > 0) {
    html += `
  <h3>Relays (${relays.length})</h3>
  <table>
    <tr><th>Nickname</th><th>Fingerprint</th><th>Country</th><th>Family</th></tr>`;
    for (const r of relays) {
      if (!isSafePathSegment(r.f)) continue; // Skip invalid fingerprints
      const familyLink = (r.fam && isSafePathSegment(r.fam)) 
        ? `<a href="/family/${escapeHtml(r.fam)}/">View</a>` 
        : '-';
      html += `
    <tr>
      <td><a href="/relay/${escapeHtml(r.f)}/">${escapeHtml(r.n)}</a></td>
      <td><code>${escapeHtml(r.f.substring(0, 8))}...</code></td>
      <td>${r.cc ? escapeHtml(r.cc.toUpperCase()) : '?'}</td>
      <td>${familyLink}</td>
    </tr>`;
    }
    html += '</table>';
  }

  if (families.length > 0) {
    html += `
  <h3>Families (${families.length})</h3>
  <table>
    <tr><th>Family</th><th>Size</th><th>AROI</th></tr>`;
    for (const f of families) {
      if (!isSafePathSegment(f.id)) continue; // Skip invalid family IDs
      const label = f.a || f.px || f.id.substring(0, 8);
      html += `
    <tr>
      <td><a href="/family/${escapeHtml(f.id)}/">${escapeHtml(label)}</a></td>
      <td>${parseInt(f.sz, 10) || 0} relays</td>
      <td>${escapeHtml(f.a) || '-'}</td>
    </tr>`;
    }
    html += '</table>';
  }

  html += `
  <p><a href="/">← Back to home</a></p>
</body>
</html>`;

  return secureResponse(html, 200);
}

function renderNotFoundPage(query) {
  return secureResponse(`<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Not Found</title>
  <link rel="stylesheet" href="/static/css/bootstrap.min.css">
  <style>
    body { padding: 40px; font-family: sans-serif; text-align: center; }
    .search-box { margin: 30px auto; max-width: 400px; }
    input[type="text"] { width: 100%; padding: 10px; font-size: 16px; }
  </style>
</head>
<body>
  <h2>No results found for "${escapeHtml(query)}"</h2>
  <p>Try searching for:</p>
  <ul style="text-align: left; max-width: 400px; margin: 0 auto;">
    <li>Relay fingerprint (full or partial)</li>
    <li>Relay nickname</li>
    <li>Operator domain (AROI)</li>
    <li>AS number (e.g., AS24940)</li>
    <li>Country name or code</li>
  </ul>
  <div class="search-box">
    <form action="/search" method="GET">
      <input type="text" name="q" placeholder="Search again..." 
             value="${escapeHtml(query)}" maxlength="100"
             autocomplete="off" autocapitalize="off" spellcheck="false">
      <br><button type="submit">Search</button>
    </form>
  </div>
  <p><a href="/">← Back to home</a></p>
</body>
</html>`, 404);
}

function renderInvalidQueryPage(error) {
  return secureResponse(`<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Invalid Search</title>
  <link rel="stylesheet" href="/static/css/bootstrap.min.css">
</head>
<body style="padding: 40px; text-align: center;">
  <h2>Invalid Search Query</h2>
  <p>${escapeHtml(error)}</p>
  <p><a href="/">← Back to home</a></p>
</body>
</html>`, 400);
}

// =============================================================================
// REQUEST HANDLER
// =============================================================================

export async function onRequestGet(context) {
  const { request } = context;
  const url = new URL(request.url);
  const rawQuery = url.searchParams.get('q');
  
  // Input validation
  const { valid, sanitized, error } = sanitizeQuery(rawQuery);
  
  if (!valid) {
    if (!rawQuery || !rawQuery.trim()) {
      return safeRedirect(url.origin, '/');
    }
    return renderInvalidQueryPage(error);
  }
  
  try {
    const index = await loadIndex(url.origin);
    const result = search(sanitized, index);
    
    switch (result.type) {
      case 'relay':
        if (!isSafePathSegment(result.fingerprint)) {
          return handleError(new Error('Invalid fingerprint format'), sanitized);
        }
        return safeRedirect(url.origin, `/relay/${result.fingerprint}/`);
      
      case 'family':
        if (!isSafePathSegment(result.familyId)) {
          return handleError(new Error('Invalid family ID format'), sanitized);
        }
        return safeRedirect(url.origin, `/family/${result.familyId}/`);
      
      case 'contact':
        if (!isSafePathSegment(result.contactMd5)) {
          return handleError(new Error('Invalid contact hash format'), sanitized);
        }
        return safeRedirect(url.origin, `/contact/${result.contactMd5}/`);
      
      case 'as':
        if (!isSafePathSegment(result.asNumber)) {
          return handleError(new Error('Invalid AS number format'), sanitized);
        }
        return safeRedirect(url.origin, `/as/${result.asNumber}/`);
      
      case 'country':
        if (!isSafePathSegment(result.countryCode)) {
          return handleError(new Error('Invalid country code format'), sanitized);
        }
        return safeRedirect(url.origin, `/country/${result.countryCode}/`);
      
      case 'platform':
        if (!isSafePathSegment(result.platform)) {
          return handleError(new Error('Invalid platform format'), sanitized);
        }
        return safeRedirect(url.origin, `/platform/${result.platform}/`);
      
      case 'flag':
        if (!isSafePathSegment(result.flag)) {
          return handleError(new Error('Invalid flag format'), sanitized);
        }
        return safeRedirect(url.origin, `/flag/${result.flag}/`);
      
      case 'multiple':
        return renderDisambiguationPage(result.matches, sanitized, result.hint);
      
      case 'not_found':
      default:
        return renderNotFoundPage(sanitized);
    }
  } catch (error) {
    return handleError(error, sanitized);
  }
}
```

---

### 3. HTML Search Form

Add to `allium/templates/skeleton.html` in the navigation area:

```html
<form action="{{ page_ctx.path_prefix }}search" method="GET" 
      style="display: inline-block; margin-left: 15px;">
  <input type="text" 
         name="q" 
         placeholder="Search relays, families, AS..." 
         title="Search by fingerprint, nickname, AROI, AS number, country, or IP"
         style="padding: 4px 8px; width: 200px; border: 1px solid #ccc; border-radius: 3px;"
         maxlength="100"
         pattern="[A-Za-z0-9\s\-_.@:]+"
         autocomplete="off"
         autocapitalize="off"
         spellcheck="false">
  <button type="submit" 
          style="padding: 4px 12px; background: #007bff; color: white; border: none; border-radius: 3px; cursor: pointer;">
    Search
  </button>
</form>
```

**Security attributes:**
- `maxlength="100"` - Client-side limit matching server-side validation
- `pattern="[A-Za-z0-9\s\-_.@:]+"` - Client-side character validation (defense-in-depth)
- `autocomplete="off"` - Prevent sensitive data leakage from form history

---

## Deployment Checklist

### Allium Repository

```bash
# 1. Add search index generator
# Copy search_index.py to allium/lib/

# 2. Update allium.py to generate index
# Add integration code after page generation

# 3. Test locally
python3 allium/allium.py --out ./www --progress

# 4. Verify index created
ls -la www/search-index.json
```

### Allium-Deploy Repository

```bash
# 1. Add search function
mkdir -p functions
# Copy search.js to functions/

# 2. Test locally with Wrangler
npx wrangler pages dev ./public --local

# 3. Test search functionality
curl "http://localhost:8788/search?q=torworld"
curl "http://localhost:8788/search?q=ABCD1234"

# 4. Security tests (run before deployment)
# Test input validation
curl "http://localhost:8788/search?q="                                    # Empty - should redirect
curl "http://localhost:8788/search?q=$(python3 -c 'print("a"*200)')"      # Too long - should reject
curl "http://localhost:8788/search?q=<script>alert(1)</script>"           # XSS - should sanitize/reject
curl "http://localhost:8788/search?q=../../../etc/passwd"                 # Path traversal - should reject
curl -I "http://localhost:8788/search?q=test"                             # Check security headers

# 5. Verify security headers in response
# Expected headers:
# - X-Content-Type-Options: nosniff
# - X-Frame-Options: DENY
# - X-XSS-Protection: 1; mode=block
# - Content-Security-Policy: script-src 'none'

# 6. Deploy
git add functions/search.js
git commit -m "Add server-side search function with security hardening"
git push
```

### Post-Deployment Security Verification

```bash
# 1. Configure Cloudflare Rate Limiting (Dashboard > Security > WAF)
# Rule: URI path equals "/search"
# Threshold: 60 requests per minute per IP
# Action: Challenge

# 2. Verify CSP is working (browser dev tools)
# - Open search results page
# - Check Console for CSP violations
# - Should block any inline scripts

# 3. Test from external tool
curl -H "User-Agent: SecurityTest" "https://your-site.com/search?q=test"
# Verify response includes all security headers
```

---

## Performance Characteristics

| Metric | Value |
|--------|-------|
| Index parse time | ~5-10ms |
| Search execution | <1ms (cached index) |
| Total latency | ~10-50ms |
| Memory per worker | ~2-5 MB |
| Cache hit rate | >95% |

### Compute Efficiency Features

| Feature | Implementation |
|---------|----------------|
| Precompiled regex | `PATTERNS` object at module level |
| Early returns | Each search step returns immediately on match |
| Lazy loading | Index loaded on first request, cached after |
| Bounded loops | `findRelays()` and `findFamilies()` have limits |
| Short-circuit evaluation | `&&` and `||` for conditional checks |
| Minimal allocations | Reuse result objects via `Result` factory |

### DRY Principles Applied

| Pattern | Implementation |
|---------|----------------|
| Result objects | `Result` factory creates consistent return types |
| Search helpers | `findRelays()`, `findFamilies()`, `getSharedFamily()` |
| HTML escaping | Single `escapeHtml()` function |
| Index loading | Single `loadIndex()` with caching |
| Redirect helper | Single `redirect()` function |

---

## Security Best Practices

### Security Threat Model

| Threat | Risk Level | Mitigation |
|--------|------------|------------|
| **XSS (Cross-Site Scripting)** | High | HTML escaping all user input |
| **Open Redirect** | Medium | Validate redirect targets against allowlist |
| **DoS via Long Queries** | Medium | Query length limits |
| **ReDoS (Regex DoS)** | Low | Simple, non-backtracking regex patterns |
| **Path Traversal** | Low | Validate fingerprints/IDs are alphanumeric |
| **Information Disclosure** | Low | Generic error messages |
| **Cache Poisoning** | Low | Validate cache keys |

### Input Validation

All user input is validated before processing:

```javascript
// =============================================================================
// SECURITY CONSTANTS
// =============================================================================

const SECURITY = {
  // Maximum query length to prevent DoS
  MAX_QUERY_LENGTH: 100,
  
  // Allowed characters in search queries (alphanumeric, common punctuation)
  ALLOWED_QUERY_PATTERN: /^[A-Za-z0-9\s\-_.@:]+$/,
  
  // Valid fingerprint pattern (strict hex)
  FINGERPRINT_PATTERN: /^[A-Fa-f0-9]+$/,
  
  // Valid path segments (alphanumeric, hyphen, underscore)
  SAFE_PATH_PATTERN: /^[A-Za-z0-9\-_]+$/,
};

// =============================================================================
// INPUT SANITIZATION
// =============================================================================

/**
 * Sanitize and validate user query input.
 * 
 * @param {string} query - Raw user input
 * @returns {object} { valid: boolean, sanitized: string, error: string }
 */
function sanitizeQuery(query) {
  // Null/undefined check
  if (!query) {
    return { valid: false, sanitized: '', error: 'Empty query' };
  }
  
  // Type coercion safety
  const str = String(query);
  
  // Length check (prevent DoS)
  if (str.length > SECURITY.MAX_QUERY_LENGTH) {
    return { 
      valid: false, 
      sanitized: '', 
      error: `Query too long (max ${SECURITY.MAX_QUERY_LENGTH} chars)` 
    };
  }
  
  // Trim whitespace
  const trimmed = str.trim();
  
  if (!trimmed) {
    return { valid: false, sanitized: '', error: 'Empty query after trim' };
  }
  
  // Character allowlist validation
  if (!SECURITY.ALLOWED_QUERY_PATTERN.test(trimmed)) {
    return { 
      valid: false, 
      sanitized: '', 
      error: 'Invalid characters in query' 
    };
  }
  
  return { valid: true, sanitized: trimmed, error: null };
}

/**
 * Validate a value is safe for use in URL paths.
 * Prevents path traversal attacks.
 * 
 * @param {string} value - Value to validate
 * @returns {boolean} True if safe for path use
 */
function isSafePathSegment(value) {
  if (!value || typeof value !== 'string') return false;
  if (value.includes('..')) return false;  // Path traversal
  if (value.includes('/')) return false;   // Path separator
  if (value.includes('\\')) return false;  // Windows path separator
  return SECURITY.SAFE_PATH_PATTERN.test(value);
}
```

### XSS Prevention

All output is escaped before rendering:

```javascript
/**
 * Escape HTML special characters to prevent XSS.
 * Uses a comprehensive character map for security.
 * 
 * @param {string} str - String to escape
 * @returns {string} HTML-safe string
 */
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  
  return String(str)
    .replace(/&/g, '&amp;')   // Must be first
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/`/g, '&#96;')   // Template literal protection
    .replace(/\//g, '&#x2F;'); // Forward slash for extra safety
}

/**
 * Escape string for use in HTML attributes.
 * More restrictive than general HTML escaping.
 * 
 * @param {string} str - String to escape
 * @returns {string} Attribute-safe string
 */
function escapeAttr(str) {
  if (str === null || str === undefined) return '';
  
  // First apply HTML escaping
  let escaped = escapeHtml(str);
  
  // Additional attribute-specific escaping
  escaped = escaped
    .replace(/=/g, '&#x3D;')
    .replace(/\(/g, '&#x28;')
    .replace(/\)/g, '&#x29;');
  
  return escaped;
}
```

### Open Redirect Prevention

Redirect targets are validated against known-safe paths:

```javascript
// =============================================================================
// REDIRECT SAFETY
// =============================================================================

/**
 * Valid redirect path prefixes (allowlist).
 */
const SAFE_REDIRECT_PREFIXES = [
  '/relay/',
  '/family/',
  '/contact/',
  '/as/',
  '/country/',
  '/platform/',
  '/flag/',
  '/first_seen/',
  '/'  // Homepage only (exact match)
];

/**
 * Create a safe redirect response.
 * Validates the path against an allowlist to prevent open redirects.
 * 
 * @param {string} origin - Request origin URL
 * @param {string} path - Redirect path
 * @returns {Response} Redirect response or error
 */
function safeRedirect(origin, path) {
  // Validate path starts with allowed prefix
  const isAllowed = SAFE_REDIRECT_PREFIXES.some(prefix => {
    if (prefix === '/') {
      return path === '/';
    }
    return path.startsWith(prefix);
  });
  
  if (!isAllowed) {
    console.error(`Blocked unsafe redirect: ${path}`);
    return new Response('Invalid redirect', { status: 400 });
  }
  
  // Ensure path doesn't contain protocol (prevent //evil.com)
  if (path.includes('://') || path.startsWith('//')) {
    console.error(`Blocked protocol in redirect: ${path}`);
    return new Response('Invalid redirect', { status: 400 });
  }
  
  // Construct full URL with validated origin
  const fullUrl = new URL(path, origin).toString();
  
  return Response.redirect(fullUrl, 302);
}
```

### Security Headers

Response headers for defense-in-depth:

```javascript
/**
 * Security headers for HTML responses.
 */
const SECURITY_HEADERS = {
  // Prevent MIME type sniffing
  'X-Content-Type-Options': 'nosniff',
  
  // Prevent clickjacking
  'X-Frame-Options': 'DENY',
  
  // XSS protection (legacy browsers)
  'X-XSS-Protection': '1; mode=block',
  
  // Referrer policy
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  
  // Content Security Policy
  'Content-Security-Policy': [
    "default-src 'self'",
    "style-src 'self' 'unsafe-inline'",  // For inline styles
    "img-src 'self' data:",
    "script-src 'none'",                  // No JavaScript
    "frame-ancestors 'none'",
    "form-action 'self'",
    "base-uri 'self'"
  ].join('; ')
};

/**
 * Create a response with security headers.
 * 
 * @param {string} body - Response body
 * @param {number} status - HTTP status code
 * @param {object} additionalHeaders - Additional headers to merge
 * @returns {Response} Response with security headers
 */
function secureResponse(body, status = 200, additionalHeaders = {}) {
  return new Response(body, {
    status,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      ...SECURITY_HEADERS,
      ...additionalHeaders
    }
  });
}
```

### Error Handling

Errors are logged server-side but not exposed to users:

```javascript
/**
 * Handle errors securely without exposing internal details.
 * 
 * @param {Error} error - The caught error
 * @param {string} query - The user's query (for logging)
 * @returns {Response} User-safe error response
 */
function handleError(error, query) {
  // Log full error server-side for debugging
  console.error('Search error:', {
    message: error.message,
    stack: error.stack,
    query: query?.substring(0, 50)  // Truncate for log safety
  });
  
  // Return generic message to user (no internal details)
  return secureResponse(`
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Search Error</title>
      <link rel="stylesheet" href="/static/css/bootstrap.min.css">
    </head>
    <body style="padding: 40px; text-align: center;">
      <h2>Search Temporarily Unavailable</h2>
      <p>Please try again in a few moments.</p>
      <p><a href="/">← Back to home</a></p>
    </body>
    </html>
  `, 503);
}
```

### Rate Limiting

Cloudflare provides built-in DDoS protection, but additional application-level considerations:

```javascript
/**
 * Rate limiting is handled by Cloudflare's infrastructure:
 * 
 * 1. **Cloudflare DDoS Protection** (automatic)
 *    - Layer 7 attack mitigation
 *    - Bot detection
 *    - Challenge pages for suspicious traffic
 * 
 * 2. **Cloudflare Rate Limiting** (configurable in dashboard)
 *    - Set rules like: 100 requests per minute per IP to /search
 *    - Action: Challenge or Block
 * 
 * 3. **Workers Limits** (platform enforced)
 *    - 100,000 requests/day on free tier
 *    - 10ms CPU time per request (free tier)
 *    - Automatic rejection when limits exceeded
 * 
 * Application-level rate limiting is NOT implemented in the function
 * because Cloudflare handles this more efficiently at the edge.
 * 
 * To configure Cloudflare Rate Limiting:
 * 1. Go to Cloudflare Dashboard > Security > WAF > Rate limiting rules
 * 2. Create rule: If URI path equals "/search" 
 * 3. Set threshold: 60 requests per minute
 * 4. Action: Challenge
 */
```

### ReDoS Prevention

All regex patterns are designed to be safe:

```javascript
/**
 * PATTERNS object uses only simple, non-backtracking patterns.
 * 
 * Safe patterns avoid:
 * - Nested quantifiers: (a+)+
 * - Overlapping alternations: (a|a)+
 * - Unbounded repetition with ambiguity
 * 
 * All patterns below are O(n) where n = input length.
 */
const PATTERNS = {
  // Simple character class with fixed length - O(n)
  FULL_FINGERPRINT: /^[A-Fa-f0-9]{40}$/,
  
  // Simple character class with bounded length - O(n)
  PARTIAL_FINGERPRINT: /^[A-Fa-f0-9]{6,39}$/,
  
  // Simple character class - O(n)
  IP_ADDRESS: /^[\d.:a-fA-F]+$/,
  
  // Simple optional prefix with capture - O(n)
  AS_NUMBER: /^(?:AS)?(\d+)$/i,
};

// These patterns are verified safe using tools like:
// - https://devina.io/redos-checker
// - npm package 'safe-regex'
```

### Security Checklist

Before deployment, verify:

- [ ] All user input is sanitized via `sanitizeQuery()`
- [ ] All HTML output uses `escapeHtml()` or `escapeAttr()`
- [ ] All redirects use `safeRedirect()` with path validation
- [ ] Security headers are included in all HTML responses
- [ ] Error messages don't expose internal details
- [ ] Regex patterns are ReDoS-safe
- [ ] Query length is limited (100 chars max)
- [ ] Fingerprints/IDs are validated as alphanumeric
- [ ] Cloudflare rate limiting rules are configured
- [ ] CSP header blocks inline scripts

### Updated Request Handler with Security

```javascript
export async function onRequestGet(context) {
  const { request } = context;
  const url = new URL(request.url);
  const rawQuery = url.searchParams.get('q');
  
  // Input validation
  const { valid, sanitized, error } = sanitizeQuery(rawQuery);
  
  if (!valid) {
    if (!rawQuery || !rawQuery.trim()) {
      // Empty query - redirect home
      return safeRedirect(url.origin, '/');
    }
    // Invalid query - show error
    return secureResponse(`
      <!DOCTYPE html>
      <html>
      <head><meta charset="utf-8"><title>Invalid Search</title></head>
      <body style="padding: 40px; text-align: center;">
        <h2>Invalid Search Query</h2>
        <p>${escapeHtml(error)}</p>
        <p><a href="/">← Back to home</a></p>
      </body>
      </html>
    `, 400);
  }
  
  try {
    const index = await loadIndex(url.origin);
    const result = search(sanitized, index);
    
    switch (result.type) {
      case 'relay':
        if (!isSafePathSegment(result.fingerprint)) {
          return handleError(new Error('Invalid fingerprint'), sanitized);
        }
        return safeRedirect(url.origin, `/relay/${result.fingerprint}/`);
      
      case 'family':
        if (!isSafePathSegment(result.familyId)) {
          return handleError(new Error('Invalid family ID'), sanitized);
        }
        return safeRedirect(url.origin, `/family/${result.familyId}/`);
      
      case 'contact':
        if (!isSafePathSegment(result.contactMd5)) {
          return handleError(new Error('Invalid contact hash'), sanitized);
        }
        return safeRedirect(url.origin, `/contact/${result.contactMd5}/`);
      
      case 'as':
        if (!isSafePathSegment(result.asNumber)) {
          return handleError(new Error('Invalid AS number'), sanitized);
        }
        return safeRedirect(url.origin, `/as/${result.asNumber}/`);
      
      case 'country':
        if (!isSafePathSegment(result.countryCode)) {
          return handleError(new Error('Invalid country code'), sanitized);
        }
        return safeRedirect(url.origin, `/country/${result.countryCode}/`);
      
      case 'platform':
        if (!isSafePathSegment(result.platform)) {
          return handleError(new Error('Invalid platform'), sanitized);
        }
        return safeRedirect(url.origin, `/platform/${result.platform}/`);
      
      case 'flag':
        if (!isSafePathSegment(result.flag)) {
          return handleError(new Error('Invalid flag'), sanitized);
        }
        return safeRedirect(url.origin, `/flag/${result.flag}/`);
      
      case 'multiple':
        return renderDisambiguationPage(result.matches, sanitized, result.hint);
      
      case 'not_found':
      default:
        return renderNotFoundPage(sanitized);
    }
  } catch (error) {
    return handleError(error, sanitized);
  }
}
```

---

## Future Enhancements

1. **Search analytics** - Track popular queries for insights
2. **Autocomplete** - Suggest completions as user types (would require JS)
3. **Search history** - Browser localStorage for recent searches
4. **Advanced syntax** - Support `country:de AND flag:exit` queries
5. **Relevance scoring** - Rank results by importance/bandwidth

---

## Related Documentation

- [Allium Roadmap 2025](allium-roadmap-2025.md) - Overall project roadmap
- [Milestone 5: Community Tools](milestone-5-community-tools.md) - API planning
- [User Guide: Features](../../user-guide/features.md) - Current search capabilities

---

**Last Updated**: December 2024  
**Document Status**: Implementation Ready  
**Security Review**: Included (see Security Best Practices section)
