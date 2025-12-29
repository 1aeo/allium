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
 */

// =============================================================================
// PRECOMPILED PATTERNS
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
    throw new Error(`Failed to load search index: ${response.status}`);
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

function redirect(path) {
  return Response.redirect(path, 302);
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
// RESPONSE HANDLERS
// =============================================================================

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

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

  if (suggestedFamily) {
    html += `
  <div class="suggestion">
    <strong>💡 These relays appear to be in the same family:</strong><br>
    <a href="/family/${suggestedFamily}/">View Family</a>
  </div>`;
  }

  if (relays.length > 0) {
    html += `
  <h3>Relays (${relays.length})</h3>
  <table>
    <tr><th>Nickname</th><th>Fingerprint</th><th>Country</th><th>Family</th></tr>`;
    for (const r of relays) {
      const familyLink = r.fam ? `<a href="/family/${r.fam}/">View</a>` : '-';
      html += `
    <tr>
      <td><a href="/relay/${r.f}/">${escapeHtml(r.n)}</a></td>
      <td><code>${r.f.substring(0, 8)}...</code></td>
      <td>${r.cc ? r.cc.toUpperCase() : '?'}</td>
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
      const label = f.a || f.px || f.id.substring(0, 8);
      html += `
    <tr>
      <td><a href="/family/${f.id}/">${escapeHtml(label)}</a></td>
      <td>${f.sz} relays</td>
      <td>${f.a || '-'}</td>
    </tr>`;
    }
    html += '</table>';
  }

  html += `
  <p><a href="/">← Back to home</a></p>
</body>
</html>`;

  return new Response(html, {
    headers: { 'Content-Type': 'text/html; charset=utf-8' }
  });
}

function renderNotFoundPage(query) {
  return new Response(`<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Not Found - ${escapeHtml(query)}</title>
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
      <input type="text" name="q" placeholder="Search again..." value="${escapeHtml(query)}">
      <br><button type="submit">Search</button>
    </form>
  </div>
  <p><a href="/">← Back to home</a></p>
</body>
</html>`, {
    status: 404,
    headers: { 'Content-Type': 'text/html; charset=utf-8' }
  });
}

// =============================================================================
// REQUEST HANDLER
// =============================================================================

export async function onRequestGet(context) {
  const { request } = context;
  const url = new URL(request.url);
  const query = url.searchParams.get('q');
  
  if (!query || !query.trim()) {
    return redirect(url.origin + '/');
  }
  
  try {
    const index = await loadIndex(url.origin);
    const result = search(query, index);
    
    switch (result.type) {
      case 'relay':
        return redirect(`${url.origin}/relay/${result.fingerprint}/`);
      case 'family':
        return redirect(`${url.origin}/family/${result.familyId}/`);
      case 'contact':
        return redirect(`${url.origin}/contact/${result.contactMd5}/`);
      case 'as':
        return redirect(`${url.origin}/as/${result.asNumber}/`);
      case 'country':
        return redirect(`${url.origin}/country/${result.countryCode}/`);
      case 'platform':
        return redirect(`${url.origin}/platform/${result.platform}/`);
      case 'flag':
        return redirect(`${url.origin}/flag/${result.flag}/`);
      case 'multiple':
        return renderDisambiguationPage(result.matches, query, result.hint);
      case 'not_found':
      default:
        return renderNotFoundPage(query);
    }
  } catch (error) {
    console.error('Search error:', error);
    return new Response(`Search error: ${error.message}`, { status: 500 });
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
         autocomplete="off"
         autocapitalize="off"
         spellcheck="false">
  <button type="submit" 
          style="padding: 4px 12px; background: #007bff; color: white; border: none; border-radius: 3px; cursor: pointer;">
    Search
  </button>
</form>
```

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

# 3. Test search
curl "http://localhost:8788/search?q=torworld"
curl "http://localhost:8788/search?q=ABCD1234"

# 4. Deploy
git add functions/search.js
git commit -m "Add server-side search function"
git push
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
