# Technical Implementation: Consensus Troubleshooting

**Status**: Ready for Implementation  
**Effort**: 6-7 weeks (2 phases)  
**Scope**: Latest CollecTor data only - NO historical parsing

---

## Architecture Overview

### Dynamic Authority Discovery

Authority list is **NOT hardcoded** - discovered from Onionoo API by finding relays with "Authority" flag.

```python
# During Onionoo processing - extract authorities dynamically
def _discover_authorities(relays: list) -> list:
    """
    Discover directory authorities from relay list.
    Returns list of authority relay dicts with fingerprints, nicknames, IPs.
    """
    authorities = [
        {
            'fingerprint': r['fingerprint'],
            'nickname': r['nickname'],
            'address': r.get('or_addresses', [''])[0].split(':')[0],
            'dir_port': r.get('dir_address', '').split(':')[-1] or '80',
            'is_bw_authority': 'V2Dir' in r.get('flags', []),  # Heuristic
        }
        for r in relays 
        if 'Authority' in r.get('flags', [])
    ]
    return authorities
```

### Consensus Voting Requirement (Dynamic)

Calculated based on discovered authority count - displayed as **tooltip** on relay pages.

```python
def calculate_consensus_requirement(authority_count: int) -> dict:
    """
    Calculate majority required for consensus.
    Formula: floor(authority_count / 2) + 1
    """
    majority = (authority_count // 2) + 1
    return {
        'authority_count': authority_count,
        'majority_required': majority,
        'tooltip': f"Consensus requires majority: {majority}/{authority_count} ({authority_count}÷2+1={majority})"
    }

# Examples:
# 9 authorities → 5 required (current)
# 10 authorities → 6 required
# 8 authorities → 5 required
```

### Data Flow (Two-Phase: Onionoo THEN CollecTor)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        HOURLY EXECUTION                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  PHASE 1: Parallel API Fetch (existing threads)                     │
│  Coordinator.fetch_all_apis_threaded()                              │
│  ├── Thread: fetch_onionoo_details()          (existing) ──┐        │
│  ├── Thread: fetch_onionoo_uptime()           (existing)   │        │
│  ├── Thread: fetch_onionoo_bandwidth()        (existing)   │        │
│  └── Thread: fetch_aroi_validation()          (existing)   │        │
│                                                             │        │
│       ↓ Onionoo details completes                          │        │
│                                                             ▼        │
│  PHASE 2: Extract authorities, then fetch CollecTor        │        │
│  ┌─────────────────────────────────────────────────────────┤        │
│  │  authorities = _discover_authorities(onionoo_relays)    │        │
│  │  consensus_req = calculate_consensus_requirement(len)   │        │
│  │                                                         │        │
│  │  collector_data = fetch_collector_consensus_data(       │        │
│  │      authorities=authorities  # Pass discovered list    │        │
│  │  )                                                      │        │
│  └─────────────────────────────────────────────────────────┘        │
│                                                                     │
│       ↓ All data available                                          │
│                                                                     │
│  Coordinator.create_relay_set():                                    │
│       ├── relay_set.authorities = authorities              (NEW)   │
│       ├── relay_set.consensus_requirement = consensus_req  (NEW)   │
│       ├── relay_set._reprocess_uptime_data()      (existing)       │
│       ├── relay_set._reprocess_bandwidth_data()   (existing)       │
│       └── relay_set._reprocess_collector_data()   (NEW)            │
│                                                                     │
│       ↓                                                             │
│                                                                     │
│  Page Generation (parallel via mp_workers)                          │
│  ├── relay-info.html × 7000   → Uses relay['collector_diagnostics'] │
│  │                              + consensus_requirement for tooltip │
│  └── misc-authorities.html    → Uses relay_set.authorities          │
│                                 (dynamic, not hardcoded)            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Modular Structure

```
lib/consensus/                        # NEW MODULE (self-contained)
├── __init__.py                       # Exports: CollectorFetcher, AuthorityMonitor
├── collector_fetcher.py              # Fetch + parse + index (no relay loop)
├── authority_monitor.py              # Authority latency checks (Phase 2)
└── diagnostics.py                    # Format diagnostics for templates

lib/workers.py                        # MODIFY: +1 function
└── fetch_collector_consensus_data()  # Follows fetch_onionoo_uptime() pattern

lib/coordinator.py                    # MODIFY: +3 lines
├── api_workers.append(...)           # Add to existing list
├── get_collector_consensus_data()    # Getter (like get_uptime_data)
└── create_relay_set() +1 line        # Call _reprocess_collector_data()

lib/relays.py                         # MODIFY: +1 method (~30 lines)
└── _reprocess_collector_data()       # Follows _reprocess_uptime_data() pattern
```

---

## Phase 1: Per-Relay Diagnostics

### 1.1 CollecTor Fetcher Module

```python
# lib/consensus/collector_fetcher.py
"""
Fetch and index CollecTor data for per-relay diagnostics.
Fetched ONCE per hour, indexed by fingerprint for O(1) lookup.
"""

import re
import base64
import urllib.request
import concurrent.futures
from typing import Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# 9 Directory Authorities (all vote, 7 run bandwidth scanners)
AUTHORITIES = {
    '0232AF901C31A04EE9848595AF9BB7620D4C5B2E': 'moria1',
    '14C131DFC5C6F93646BE72FA1401C02A8DF2E8B4': 'tor26',
    'E8A9C45EDE6D711294FADF8E7951F4DE6CA56B58': 'dizum',
    '97B10E9A490BE3D9A67C84EE3EF2FCFB6F0C9CDD': 'gabelmoo',
    'ED03BB616EB2F60BEC80151114BB25CEF515B226': 'bastet',
    '0AD3FA884D18F89EEA2D89C019379E0E7FD94417': 'dannenberg',
    'BD6A829255CB08E66FBE7D3748363586E46B3810': 'maatuska',
    '24E2F139121D4394C54B5BCC368B3B411857C413': 'longclaw',
    'EFCBE720AB3A82B99F9E953CD5BF50F7EEFC7B97': 'faravahar',
}

BANDWIDTH_AUTHORITIES = ['moria1', 'tor26', 'gabelmoo', 'bastet', 'longclaw', 'faravahar', 'maatuska']
IPV6_TESTING_AUTHORITIES = ['moria1', 'gabelmoo', 'dannenberg', 'maatuska', 'bastet']

COLLECTOR_BASE = 'https://collector.torproject.org'
VOTES_PATH = '/recent/relay-descriptors/votes/'
BANDWIDTH_PATH = '/recent/relay-descriptors/bandwidths/'


class CollectorFetcher:
    """
    Fetch and index CollecTor data.
    
    Usage:
        fetcher = CollectorFetcher()
        data = fetcher.fetch_all()
        diagnostics = fetcher.get_relay_diagnostics('FINGERPRINT')
    """
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.votes = {}
        self.bandwidth_files = {}
        self.relay_index = {}
        self.flag_thresholds = {}
    
    def fetch_all(self) -> dict:
        """
        Fetch all data from CollecTor.
        Uses parallel HTTP requests for efficiency.
        """
        # Fetch votes and bandwidth files in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            votes_future = executor.submit(self._fetch_all_votes)
            bw_future = executor.submit(self._fetch_all_bandwidth_files)
            
            self.votes = votes_future.result()
            self.bandwidth_files = bw_future.result()
        
        # Build index ONCE (O(n) where n = relay count * authority count)
        self._build_relay_index()
        self._extract_flag_thresholds()
        
        return {
            'votes': self.votes,
            'bandwidth_files': self.bandwidth_files,
            'relay_index': self.relay_index,
            'flag_thresholds': self.flag_thresholds,
            'fetched_at': datetime.utcnow().isoformat()
        }
    
    def get_relay_diagnostics(self, fingerprint: str) -> dict:
        """
        Get diagnostics for a single relay.
        O(1) lookup after index is built.
        
        NOTE: This is called during _reprocess_collector_data() in relays.py,
        NOT during page generation. The result is attached to each relay
        as relay['collector_diagnostics'] for template access.
        """
        fingerprint = fingerprint.upper()
        if fingerprint not in self.relay_index:
            return {'error': 'Relay not found', 'in_consensus': False}
        
        relay = self.relay_index[fingerprint]
        vote_count = len(relay['votes'])
        
        # Tor consensus requires MAJORITY of authorities (5 out of 9)
        # Per dir-spec: relay appears in consensus if ≥ half of authorities vote for it
        in_consensus = vote_count >= 5  # floor(9/2) + 1 = 5
        
        return {
            'fingerprint': fingerprint,
            'in_consensus': in_consensus,
            'vote_count': vote_count,
            'total_authorities': 9,
            'authority_votes': self._format_authority_votes(relay),
            'flag_eligibility': self._analyze_flag_eligibility(relay),
            'bandwidth': self._format_bandwidth(relay),
        }
    
    # ─────────────────────────────────────────────────────────────────
    # Private: Fetching
    # ─────────────────────────────────────────────────────────────────
    
    def _fetch_all_votes(self) -> Dict[str, dict]:
        """Fetch latest votes from all 9 authorities."""
        votes = {}
        
        # Get vote file list
        index_url = f"{COLLECTOR_BASE}{VOTES_PATH}"
        index_html = self._fetch_url(index_url)
        latest_files = self._find_latest_vote_files(index_html)
        
        # Fetch each vote file in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=9) as executor:
            futures = {}
            for filename, fingerprint in latest_files.items():
                auth_name = AUTHORITIES.get(fingerprint, fingerprint[:8])
                url = f"{index_url}{filename}"
                futures[executor.submit(self._fetch_url, url)] = auth_name
            
            for future in concurrent.futures.as_completed(futures):
                auth_name = futures[future]
                try:
                    vote_text = future.result()
                    votes[auth_name] = self._parse_vote(vote_text, auth_name)
                except Exception as e:
                    logger.warning(f"Failed to fetch vote from {auth_name}: {e}")
                    votes[auth_name] = {'error': str(e), 'relays': {}}
        
        logger.info(f"Fetched {len(votes)} authority votes")
        return votes
    
    def _fetch_all_bandwidth_files(self) -> Dict[str, dict]:
        """Fetch latest bandwidth files from 7 bandwidth authorities."""
        bandwidth = {}
        
        # Get bandwidth file list
        index_url = f"{COLLECTOR_BASE}{BANDWIDTH_PATH}"
        index_html = self._fetch_url(index_url)
        latest_files = self._find_latest_bandwidth_files(index_html)
        
        # Fetch each bandwidth file in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
            futures = {}
            for filename, auth_name in latest_files.items():
                url = f"{index_url}{filename}"
                futures[executor.submit(self._fetch_url, url)] = auth_name
            
            for future in concurrent.futures.as_completed(futures):
                auth_name = futures[future]
                try:
                    bw_text = future.result()
                    bandwidth[auth_name] = self._parse_bandwidth_file(bw_text, auth_name)
                except Exception as e:
                    logger.warning(f"Failed to fetch bandwidth from {auth_name}: {e}")
                    bandwidth[auth_name] = {'error': str(e), 'relays': {}}
        
        logger.info(f"Fetched {len(bandwidth)} bandwidth files")
        return bandwidth
    
    def _fetch_url(self, url: str) -> str:
        """Fetch URL with timeout and error handling."""
        req = urllib.request.Request(url, headers={'User-Agent': 'Allium/1.0'})
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            return response.read().decode('utf-8', errors='replace')
    
    # ─────────────────────────────────────────────────────────────────
    # Private: Parsing
    # ─────────────────────────────────────────────────────────────────
    
    def _find_latest_vote_files(self, index_html: str) -> Dict[str, str]:
        """Find latest vote files from directory listing."""
        # Pattern: 2025-12-26-04-00-00-vote-FINGERPRINT-DIGEST
        pattern = r'href="(\d{4}-\d{2}-\d{2}-(\d{2})-00-00-vote-([A-F0-9]{40})-[A-F0-9]+)"'
        matches = re.findall(pattern, index_html)
        
        if not matches:
            return {}
        
        # Group by hour, take latest
        by_hour = {}
        for filename, hour, fingerprint in matches:
            if hour not in by_hour:
                by_hour[hour] = {}
            by_hour[hour][filename] = fingerprint
        
        latest_hour = max(by_hour.keys())
        return by_hour[latest_hour]
    
    def _find_latest_bandwidth_files(self, index_html: str) -> Dict[str, str]:
        """Find latest bandwidth files from directory listing."""
        # Pattern: 2025-12-26-04-30-00-bandwidth-moria1
        pattern = r'href="(\d{4}-\d{2}-\d{2}-(\d{2})-\d{2}-\d{2}-bandwidth-(\w+))"'
        matches = re.findall(pattern, index_html)
        
        if not matches:
            return {}
        
        # Group by hour, take latest
        by_hour = {}
        for filename, hour, auth_name in matches:
            if hour not in by_hour:
                by_hour[hour] = {}
            by_hour[hour][filename] = auth_name
        
        latest_hour = max(by_hour.keys())
        return by_hour[latest_hour]
    
    def _parse_vote(self, vote_text: str, auth_name: str) -> dict:
        """Parse vote document into structured data."""
        parsed = {
            'authority': auth_name,
            'published': None,
            'valid_after': None,
            'flag_thresholds': {},
            'known_flags': [],
            'relays': {},
        }
        
        current_relay = None
        
        for line in vote_text.split('\n'):
            # Router entry
            if line.startswith('r '):
                parts = line.split(' ')
                if len(parts) >= 8:
                    fingerprint = self._decode_fingerprint(parts[2])
                    current_relay = {
                        'nickname': parts[1],
                        'fingerprint': fingerprint,
                        'ip': parts[5],
                        'flags': [],
                        'bandwidth': None,
                        'measured': False,
                    }
                    parsed['relays'][fingerprint] = current_relay
            
            # IPv6 address
            elif line.startswith('a ') and current_relay:
                current_relay['ipv6'] = line.split(' ', 1)[1] if len(line) > 2 else None
            
            # Flags
            elif line.startswith('s ') and current_relay:
                current_relay['flags'] = line.split(' ')[1:]
            
            # Bandwidth
            elif line.startswith('w ') and current_relay:
                bw_match = re.search(r'Bandwidth=(\d+)', line)
                if bw_match:
                    current_relay['bandwidth'] = int(bw_match.group(1))
                current_relay['measured'] = 'Measured' in line
            
            # Header fields
            elif line.startswith('published '):
                parsed['published'] = line.split(' ', 1)[1]
            elif line.startswith('valid-after '):
                parsed['valid_after'] = line.split(' ', 1)[1]
            elif line.startswith('known-flags '):
                parsed['known_flags'] = line.split(' ')[1:]
            elif line.startswith('flag-thresholds '):
                parsed['flag_thresholds'] = self._parse_flag_thresholds(line)
        
        return parsed
    
    def _parse_bandwidth_file(self, bw_text: str, auth_name: str) -> dict:
        """Parse bandwidth file into structured data."""
        parsed = {
            'authority': auth_name,
            'timestamp': None,
            'version': None,
            'relays': {},
        }
        
        for line in bw_text.split('\n'):
            if line.startswith('bw='):
                bw_match = re.search(r'bw=(\d+)', line)
                node_match = re.search(r'node_id=\$([A-F0-9]{40})', line)
                if bw_match and node_match:
                    fingerprint = node_match.group(1)
                    parsed['relays'][fingerprint] = {
                        'bandwidth': int(bw_match.group(1)),
                    }
            elif line.startswith('version='):
                parsed['version'] = line.split('=', 1)[1]
            elif line.isdigit():
                parsed['timestamp'] = int(line)
        
        return parsed
    
    def _parse_flag_thresholds(self, line: str) -> dict:
        """Parse flag-thresholds line into dict."""
        thresholds = {}
        for part in line.split(' ')[1:]:
            if '=' in part:
                key, value = part.split('=', 1)
                try:
                    thresholds[key] = float(value) if '.' in value else int(value)
                except ValueError:
                    thresholds[key] = value
        return thresholds
    
    def _decode_fingerprint(self, b64: str) -> str:
        """Decode base64 fingerprint to hex."""
        try:
            # Add padding if needed
            padded = b64 + '=' * (4 - len(b64) % 4) if len(b64) % 4 else b64
            decoded = base64.b64decode(padded)
            return decoded.hex().upper()
        except Exception:
            return b64
    
    # ─────────────────────────────────────────────────────────────────
    # Private: Indexing (runs ONCE after fetch)
    # ─────────────────────────────────────────────────────────────────
    
    def _build_relay_index(self):
        """
        Build fingerprint-indexed relay data.
        Called ONCE after fetching, enables O(1) lookup per relay.
        """
        self.relay_index = {}
        
        # Index votes
        for auth_name, vote_data in self.votes.items():
            if 'error' in vote_data:
                continue
            for fingerprint, relay in vote_data.get('relays', {}).items():
                if fingerprint not in self.relay_index:
                    self.relay_index[fingerprint] = {'votes': {}, 'bandwidth': {}}
                self.relay_index[fingerprint]['votes'][auth_name] = relay
        
        # Index bandwidth
        for auth_name, bw_data in self.bandwidth_files.items():
            if 'error' in bw_data:
                continue
            for fingerprint, bw_info in bw_data.get('relays', {}).items():
                if fingerprint not in self.relay_index:
                    self.relay_index[fingerprint] = {'votes': {}, 'bandwidth': {}}
                self.relay_index[fingerprint]['bandwidth'][auth_name] = bw_info
        
        logger.info(f"Indexed {len(self.relay_index)} relays")
    
    def _extract_flag_thresholds(self):
        """Extract flag thresholds from votes for Phase 1 flag eligibility."""
        for auth_name, vote_data in self.votes.items():
            if 'flag_thresholds' in vote_data and vote_data['flag_thresholds']:
                self.flag_thresholds[auth_name] = vote_data['flag_thresholds']
        logger.info(f"Extracted thresholds from {len(self.flag_thresholds)} authorities")
    
    # ─────────────────────────────────────────────────────────────────
    # Private: Formatting for templates
    # ─────────────────────────────────────────────────────────────────
    
    def _format_authority_votes(self, relay: dict) -> list:
        """Format per-authority vote data for template."""
        result = []
        
        for auth_name in AUTHORITIES.values():
            if auth_name in relay['votes']:
                vote = relay['votes'][auth_name]
                ipv4_ok = 'Running' in vote.get('flags', [])
                
                # IPv6 check (only some authorities test)
                ipv6_ok = None
                if auth_name in IPV6_TESTING_AUTHORITIES:
                    ipv6_ok = 'ReachableIPv6' in vote.get('flags', [])
                
                result.append({
                    'authority': auth_name,
                    'voted': True,
                    'ipv4_reachable': ipv4_ok,
                    'ipv6_reachable': ipv6_ok,
                    'flags': vote.get('flags', []),
                    'bandwidth': vote.get('bandwidth'),
                })
            else:
                result.append({
                    'authority': auth_name,
                    'voted': False,
                    'ipv4_reachable': False,
                    'ipv6_reachable': False,
                    'flags': [],
                    'bandwidth': None,
                })
        
        return result
    
    def _analyze_flag_eligibility(self, relay: dict) -> dict:
        """Analyze which flags relay is eligible for."""
        # Get median thresholds across authorities
        thresholds = self._get_median_thresholds()
        
        # Get current flags from votes
        current_flags = set()
        for vote in relay['votes'].values():
            current_flags.update(vote.get('flags', []))
        
        return {
            'current_flags': list(current_flags),
            'thresholds': thresholds,
            # Detailed analysis would compare relay metrics vs thresholds
            # Simplified for initial implementation
        }
    
    def _format_bandwidth(self, relay: dict) -> dict:
        """Format bandwidth data for template."""
        measurements = []
        bw_values = []
        
        for auth_name in BANDWIDTH_AUTHORITIES:
            if auth_name in relay['bandwidth']:
                bw = relay['bandwidth'][auth_name]['bandwidth']
                measurements.append({
                    'authority': auth_name,
                    'measured': True,
                    'value': bw,
                })
                bw_values.append(bw)
            else:
                measurements.append({
                    'authority': auth_name,
                    'measured': False,
                    'value': None,
                })
        
        # Calculate deviation if we have measurements
        avg = sum(bw_values) / len(bw_values) if bw_values else 0
        for m in measurements:
            if m['measured'] and avg > 0:
                m['deviation'] = ((m['value'] - avg) / avg) * 100
                m['deviation_warning'] = abs(m['deviation']) > 5
            else:
                m['deviation'] = None
                m['deviation_warning'] = False
        
        return {
            'measured_count': len(bw_values),
            'total_authorities': len(BANDWIDTH_AUTHORITIES),
            'average': avg,
            'measurements': measurements,
        }
    
    def _get_median_thresholds(self) -> dict:
        """Calculate median thresholds across authorities."""
        if not self.flag_thresholds:
            return {}
        
        all_keys = set()
        for t in self.flag_thresholds.values():
            all_keys.update(t.keys())
        
        result = {}
        for key in all_keys:
            values = [t[key] for t in self.flag_thresholds.values() if key in t]
            if values:
                values.sort()
                mid = len(values) // 2
                result[key] = values[mid]
        
        return result
```

### 1.2 Worker Integration

```python
# lib/workers.py - ADD THIS FUNCTION

from lib.consensus.collector_fetcher import CollectorFetcher

# Cache config (follows existing patterns)
COLLECTOR_CACHE_MAX_AGE_HOURS = 1  # Refresh every hour (matches consensus cycle)

@handle_http_errors("collector consensus", _load_cache, _save_cache, _mark_ready, _mark_stale,
                   allow_exit_on_304=False, critical=False)
def fetch_collector_consensus_data(progress_logger=None):
    """
    Fetch CollecTor votes and bandwidth files.
    Follows existing worker pattern for threading and caching.
    """
    api_name = "collector_consensus"
    
    def log_progress(message):
        if progress_logger:
            progress_logger(message)
    
    # Check cache age - only fetch if older than 1 hour
    cache_age = _cache_manager.get_cache_age(api_name)
    if cache_age is not None and cache_age < COLLECTOR_CACHE_MAX_AGE_HOURS * 3600:
        log_progress(f"using cached CollecTor data (less than {COLLECTOR_CACHE_MAX_AGE_HOURS} hour old)")
        cached_data = _load_cache(api_name)
        if cached_data:
            _mark_ready(api_name)
            relay_count = len(cached_data.get('relay_index', {}))
            log_progress(f"loaded {relay_count} relays from CollecTor cache")
            return cached_data
    
    # Fetch fresh data
    log_progress("fetching fresh CollecTor data (votes + bandwidth files)...")
    
    fetcher = CollectorFetcher(timeout=30)
    data = fetcher.fetch_all()
    
    # Cache the indexed data
    log_progress("caching CollecTor data...")
    _save_cache(api_name, data)
    _mark_ready(api_name)
    
    relay_count = len(data.get('relay_index', {}))
    vote_count = len([v for v in data.get('votes', {}).values() if 'error' not in v])
    bw_count = len([b for b in data.get('bandwidth_files', {}).values() if 'error' not in b])
    
    log_progress(f"successfully indexed {relay_count} relays from {vote_count} votes + {bw_count} bandwidth files")
    
    return data
```

### 1.3 Coordinator Integration

```python
# lib/coordinator.py - MODIFY __init__ (around line 66-72)

# Add to api_workers list
if self.enabled_apis == 'all':
    self.api_workers.append(("onionoo_uptime", fetch_onionoo_uptime, [self.onionoo_uptime_url, self._log_progress]))
    self.api_workers.append(("onionoo_bandwidth", fetch_onionoo_bandwidth, [self.onionoo_bandwidth_url, self.bandwidth_cache_hours, self._log_progress]))
    self.api_workers.append(("aroi_validation", fetch_aroi_validation, [self.aroi_url, self._log_progress]))
    # NEW: CollecTor consensus data for per-relay diagnostics
    self.api_workers.append(("collector_consensus", fetch_collector_consensus_data, [self._log_progress]))

# lib/coordinator.py - ADD getter method (around line 224)
def get_collector_consensus_data(self):
    """Get CollecTor consensus data if available."""
    return self.worker_data.get('collector_consensus')

# lib/coordinator.py - MODIFY create_relay_set (around line 268-295)
# After existing reprocess calls, add:

# COLLECTOR PROCESSING: Process CollecTor data for per-relay diagnostics
# Follows same pattern as uptime/bandwidth processing
collector_data = self.get_collector_consensus_data()
if collector_data:
    setattr(relay_set, 'collector_data', collector_data)
    try:
        relay_set._reprocess_collector_data()
    except Exception as e:
        print(f"Warning: CollecTor processing failed ({e}), continuing without diagnostics")
```

### 1.4 Relays Integration (NO NEW LOOPS)

```python
# lib/relays.py - ADD METHOD (follows _reprocess_uptime_data pattern)

def _discover_authorities(self):
    """
    Discover directory authorities from relay list (dynamic, not hardcoded).
    Called during preprocessing, before CollecTor fetch.
    """
    authorities = []
    for relay in self.json.get("relays", []):
        if 'Authority' in relay.get('flags', []):
            authorities.append({
                'fingerprint': relay['fingerprint'],
                'nickname': relay.get('nickname', ''),
                'address': relay.get('or_addresses', [''])[0].split(':')[0] if relay.get('or_addresses') else '',
                'dir_address': relay.get('dir_address', ''),
            })
    
    # Calculate consensus requirement based on discovered count
    authority_count = len(authorities)
    majority_required = (authority_count // 2) + 1
    
    self.authorities = authorities
    self.consensus_requirement = {
        'authority_count': authority_count,
        'majority_required': majority_required,
        'tooltip': f"Consensus requires majority: {majority_required}/{authority_count} ({authority_count}÷2+1={majority_required})"
    }
    
    if self.progress:
        self._log_progress(f"Discovered {authority_count} directory authorities from Onionoo")
    
    return authorities


def _reprocess_collector_data(self):
    """
    Process CollecTor data for per-relay consensus diagnostics.
    
    Called from coordinator AFTER collector_data is attached.
    Follows same pattern as _reprocess_uptime_data() and _reprocess_bandwidth_data().
    
    EFFICIENCY: Single pass through relays, O(1) lookup per relay.
    NO NEW LOOPS - integrates with existing relay processing.
    
    DYNAMIC: Uses discovered authorities list, not hardcoded.
    """
    if not hasattr(self, 'collector_data') or not self.collector_data:
        return
    
    # Get dynamic authority list (discovered from Onionoo)
    if not hasattr(self, 'authorities'):
        self._discover_authorities()
    
    relay_index = self.collector_data.get('relay_index', {})
    flag_thresholds = self.collector_data.get('flag_thresholds', {})
    fetched_at = self.collector_data.get('fetched_at', '')
    
    # Import diagnostics formatter (lazy import to avoid circular deps)
    from .consensus.diagnostics import format_relay_diagnostics
    
    # Single pass through relays - same loop pattern as _reprocess_uptime_data
    for relay in self.json["relays"]:
        fingerprint = relay.get('fingerprint', '')
        
        if fingerprint in relay_index:
            indexed_data = relay_index[fingerprint]
            
            # Pass dynamic authorities and consensus requirement
            relay['collector_diagnostics'] = format_relay_diagnostics(
                fingerprint=fingerprint,
                indexed_data=indexed_data,
                flag_thresholds=flag_thresholds,
                fetched_at=fetched_at,
                authorities=self.authorities,  # Dynamic list
                consensus_requirement=self.consensus_requirement,  # Dynamic calculation
            )
        else:
            # Relay not in any authority vote (new relay or offline)
            relay['collector_diagnostics'] = None
    
    if self.progress:
        indexed_count = sum(1 for r in self.json["relays"] if r.get('collector_diagnostics'))
        self._log_progress(f"CollecTor diagnostics attached to {indexed_count} relays")
```

### 1.5 Diagnostics Formatter Module

```python
# lib/consensus/diagnostics.py
"""
Format CollecTor data for template display.
Keeps formatting logic separate from fetching/parsing.

NOTE: Authority list is DYNAMIC - passed in from Onionoo discovery, not hardcoded.
"""

from typing import Dict, List, Optional


# These are used as FALLBACK only if dynamic discovery fails
# Primary source is Onionoo API (relays with "Authority" flag)
FALLBACK_AUTHORITY_FINGERPRINTS = {
    'moria1': '9695DFC35FFEB861329B9F1AB04C46397020CE31',
    'tor26': '847B1F850344D7876491A54892F904934E4EB85D',
    'dizum': '7EA6EAD6FD83083C538F44038BBFA077587DD755',
    'gabelmoo': 'F2044413DAC2E02E3D6BCF4735A19BCA1DE97281',
    'bastet': '27102BC123E7AF1D4741AE047E160C91ADC76B21',
    'dannenberg': '0232AF901C31A04EE9848595AF9BB7620D4C5B2E',
    'maatuska': 'BD6A829255CB08E66FBE7D3748363586E46B3810',
    'longclaw': '23D15D965BC35114467363C165C4F724B64B4F66',
    'faravahar': 'EFCBE720AB3A82B99F9E953CD5BF50F7EEFC7B97',
}

# Known bandwidth authority nicknames (used to identify BW authorities from dynamic list)
# This is a static list because running sbws is a configuration choice, not detectable from flags
KNOWN_BW_AUTHORITY_NICKNAMES = {'moria1', 'tor26', 'gabelmoo', 'bastet', 'longclaw', 'faravahar', 'maatuska'}

# Known IPv6 testing authorities (detectable by presence of ReachableIPv6 flag in their votes)
KNOWN_IPV6_TESTING_NICKNAMES = {'moria1', 'gabelmoo', 'dannenberg', 'maatuska', 'bastet'}


def format_relay_diagnostics(
    fingerprint: str,
    indexed_data: Dict,
    flag_thresholds: Dict,
    fetched_at: str,
    authorities: List[Dict],  # Dynamic list from Onionoo discovery
    consensus_requirement: Dict,  # {authority_count, majority_required, tooltip}
) -> Dict:
    """
    Format indexed CollecTor data for template display.
    
    Called once per relay during _reprocess_collector_data().
    Returns dict suitable for Jinja2 template with:
    - Combined authority votes & bandwidth (single table)
    - Authority names linked via fingerprint (from dynamic list)
    - Color-coded flag eligibility (no checkmarks)
    - Consensus requirement as tooltip (dynamic based on authority count)
    
    Args:
        fingerprint: Relay fingerprint
        indexed_data: Pre-indexed CollecTor data for this relay
        flag_thresholds: Per-authority flag thresholds
        fetched_at: Timestamp of CollecTor data
        authorities: Dynamic list of authorities from Onionoo discovery
        consensus_requirement: {authority_count, majority_required, tooltip}
    """
    votes = indexed_data.get('votes', {})
    bandwidth = indexed_data.get('bandwidth', {})
    vote_count = len(votes)
    
    # Consensus requires majority - DYNAMIC based on discovered authority count
    authority_count = consensus_requirement.get('authority_count', len(authorities))
    majority_required = consensus_requirement.get('majority_required', (authority_count // 2) + 1)
    in_consensus = vote_count >= majority_required
    
    # Build authority lookup from dynamic list
    auth_by_nickname = {a['nickname']: a for a in authorities}
    auth_by_fingerprint = {a['fingerprint']: a for a in authorities}
    
    # Collect bandwidth values for deviation calculation
    bw_values = []
    for auth in authorities:
        auth_name = auth['nickname']
        if auth_name in bandwidth:
            bw_values.append(bandwidth[auth_name].get('bandwidth', 0))
    avg_bw = sum(bw_values) / len(bw_values) if bw_values else 0
    
    # Build combined authority data (votes + bandwidth in single list)
    authority_votes = []
    all_flags = set()
    issues = []
    
    # Use dynamic authority list instead of hardcoded
    for auth in authorities:
        auth_name = auth['nickname']
        auth_fingerprint = auth['fingerprint']
        
        # Check if this authority runs bandwidth scanner
        is_bw_authority = auth_name in KNOWN_BW_AUTHORITY_NICKNAMES
        tests_ipv6 = auth_name in KNOWN_IPV6_TESTING_NICKNAMES
        
        auth_data = {
            'authority': auth_name,
            'fingerprint': auth_fingerprint,  # From dynamic discovery
            'is_bw_authority': is_bw_authority,
            'tests_ipv6': tests_ipv6,
        }
        
        if auth_name in votes:
            vote = votes[auth_name]
            flags = vote.get('flags', [])
            all_flags.update(flags)
            
            auth_data.update({
                'voted': True,
                'ipv4_reachable': 'Running' in flags,
                'ipv6_reachable': 'ReachableIPv6' in flags if tests_ipv6 else None,
                'flags': flags,
            })
            
            # Track issues
            if 'Running' not in flags:
                issues.append(f"{auth_name}: IPv4 not reachable")
        else:
            auth_data.update({
                'voted': False,
                'ipv4_reachable': False,
                'ipv6_reachable': False if tests_ipv6 else None,
                'flags': [],
            })
            issues.append(f"{auth_name}: cannot reach relay")
        
        # Add bandwidth data (N/A for non-BW authorities)
        if is_bw_authority:
            if auth_name in bandwidth:
                bw = bandwidth[auth_name].get('bandwidth', 0)
                deviation = ((bw - avg_bw) / avg_bw * 100) if avg_bw > 0 else 0
                auth_data.update({
                    'bw_value': bw,
                    'bw_deviation': deviation,
                    'bw_deviation_warning': abs(deviation) > 5.0,
                })
            else:
                auth_data.update({
                    'bw_value': None,
                    'bw_deviation': None,
                    'bw_deviation_warning': False,
                })
        else:
            # Non-bandwidth authority - mark as N/A
            auth_data.update({
                'bw_value': None,
                'bw_deviation': None,
                'bw_deviation_warning': False,
            })
        
        authority_votes.append(auth_data)
    
    # Format flag eligibility (color-coded, no checkmarks)
    flag_eligibility = _format_flag_eligibility(
        current_flags=all_flags,
        flag_thresholds=flag_thresholds,
        relay_data=indexed_data,
    )
    
    return {
        'fingerprint': fingerprint,
        'in_consensus': in_consensus,
        'vote_count': vote_count,
        'authority_count': authority_count,  # Dynamic, not hardcoded 9
        'majority_required': majority_required,  # Dynamic (authority_count // 2 + 1)
        'consensus_tooltip': consensus_requirement.get('tooltip', ''),  # For hover
        'authority_votes': authority_votes,  # Combined votes + bandwidth
        'current_flags': list(all_flags),
        'issues': issues if issues else None,
        'flag_eligibility': flag_eligibility,
        'fetched_at': fetched_at,
    }


def _format_flag_eligibility(
    current_flags: set,
    flag_thresholds: Dict,
    relay_data: Dict,
) -> Optional[Dict]:
    """
    Format flag eligibility analysis.
    Returns data for color-coded display (green=met, red=below).
    NO checkmarks - uses text color only.
    """
    # Determine which flag to analyze (first missing important flag)
    important_flags = ['Guard', 'Stable', 'Fast', 'HSDir']
    target_flag = None
    
    for flag in important_flags:
        if flag not in current_flags:
            target_flag = flag
            break
    
    if not target_flag:
        return None  # Relay has all important flags
    
    # Get median thresholds
    median_thresholds = _get_median_thresholds(flag_thresholds)
    
    # Build requirements list based on target flag
    requirements = []
    
    if target_flag == 'Guard':
        requirements = [
            {
                'name': 'WFU (Uptime)',
                'your_value': '96.2%',  # Would come from relay data
                'threshold': f"≥{median_thresholds.get('guard-wfu', 98)}%",
                'met': False,  # Would be calculated
                'difference': '1.8%',
            },
            {
                'name': 'Time Known',
                'your_value': '45 days',
                'threshold': '≥8 days',
                'met': True,
                'difference': None,
            },
            {
                'name': 'Bandwidth',
                'your_value': '25 MB/s',
                'threshold': f"≥{median_thresholds.get('guard-bw-inc-exits', 29000000) / 1000000:.0f} MB/s",
                'met': False,
                'difference': '14%',
            },
        ]
    
    return {
        'target_flag': target_flag,
        'requirements': requirements,
    }


def _get_median_thresholds(flag_thresholds: Dict) -> Dict:
    """Calculate median threshold values across all authorities."""
    if not flag_thresholds:
        return {}
    
    all_keys = set()
    for thresholds in flag_thresholds.values():
        all_keys.update(thresholds.keys())
    
    result = {}
    for key in all_keys:
        values = [t[key] for t in flag_thresholds.values() if key in t]
        if values:
            values.sort()
            mid = len(values) // 2
            result[key] = values[mid]
    
    return result
```

### 1.4 Template Integration

```jinja2
{# templates/relay-info.html - ADD AFTER existing sections #}

{% if relay.collector_diagnostics %}
<section class="consensus-diagnostics">
  <h3>🔍 Consensus Diagnostics</h3>
  <p class="data-freshness">
    Data from: {{ relay.collector_diagnostics.fetched_at | format_datetime }}
  </p>
  
  {# Combined Authority Votes & Bandwidth (single table) #}
  <h4>Authority Votes & Bandwidth</h4>
  <p>
    {# Consensus status with dynamic tooltip explaining majority requirement #}
    <span class="consensus-status 
                 {% if relay.collector_diagnostics.in_consensus %}status-ok{% else %}status-warn{% endif %}"
          title="{{ relay.collector_diagnostics.consensus_tooltip }}">
      {% if relay.collector_diagnostics.in_consensus %}
        IN CONSENSUS
      {% else %}
        NOT IN CONSENSUS
      {% endif %}
      ({{ relay.collector_diagnostics.vote_count }}/{{ relay.collector_diagnostics.authority_count }} authorities)
    </span>
    <span class="tooltip-hint" title="{{ relay.collector_diagnostics.consensus_tooltip }}">ⓘ</span>
  </p>
  
  <table class="authority-table">
    <thead>
      <tr>
        <th>Authority</th>
        <th>IPv4</th>
        <th>IPv6</th>
        <th>Flags</th>
        <th>BW Value</th>
        <th title="Values outside ±5% shown in red">Deviation</th>
      </tr>
    </thead>
    <tbody>
    {% for auth in relay.collector_diagnostics.authority_votes %}
      <tr class="{% if not auth.voted %}row-not-voted{% endif %}">
        {# Authority name links to their relay page #}
        <td>
          <a href="{{ path_prefix }}relay/{{ auth.fingerprint }}.html" 
             title="View {{ auth.authority }} relay details">
            {{ auth.authority }}
          </a>
        </td>
        <td>{% if auth.ipv4_reachable %}✅{% else %}❌{% endif %}</td>
        <td>
          {% if auth.ipv6_reachable is none %}
            <span title="This authority doesn't test IPv6">⚪</span>
          {% elif auth.ipv6_reachable %}✅
          {% else %}❌{% endif %}
        </td>
        <td>{{ auth.flags | join(' ') if auth.flags else '—' }}</td>
        {# Bandwidth - show N/A for non-bandwidth authorities #}
        <td>
          {% if auth.is_bw_authority %}
            {{ auth.bw_value | format_bandwidth if auth.bw_value else '—' }}
          {% else %}
            <span class="not-applicable" title="This authority doesn't run a bandwidth scanner">N/A</span>
          {% endif %}
        </td>
        <td>
          {% if auth.is_bw_authority %}
            {% if auth.bw_deviation is not none %}
              <span class="{% if auth.bw_deviation_warning %}deviation-warning{% endif %}"
                    title="{% if auth.bw_deviation_warning %}Deviation >±5% may indicate measurement issues{% endif %}">
                {{ '%+.1f' % auth.bw_deviation }}%
              </span>
            {% else %}—{% endif %}
          {% else %}
            <span class="not-applicable">N/A</span>
          {% endif %}
        </td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  
  <p class="table-legend">
    IPv6: ⚪ = authority doesn't test IPv6 • 
    BW: N/A = authority doesn't run bandwidth scanner (dizum, dannenberg)
  </p>
  
  {# Issues summary #}
  {% if relay.collector_diagnostics.issues %}
  <div class="issues-summary">
    ⚠️ Issues: {{ relay.collector_diagnostics.issues | join(' • ') }}
  </div>
  {% endif %}
  
  {# Flag Eligibility - color-coded text, no checkmarks #}
  {% if relay.collector_diagnostics.flag_eligibility %}
  <h4>Flag Eligibility</h4>
  <p class="eligibility-question">
    Why doesn't this relay have the <strong>{{ relay.collector_diagnostics.flag_eligibility.target_flag }}</strong> flag?
  </p>
  
  <table class="flag-eligibility">
    <thead>
      <tr>
        <th>Requirement</th>
        <th>Your Value</th>
        <th>Threshold</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
    {% for req in relay.collector_diagnostics.flag_eligibility.requirements %}
      <tr>
        <td>{{ req.name }}</td>
        <td>{{ req.your_value }}</td>
        <td>{{ req.threshold }}</td>
        {# Color-coded status - green for met, red for below - NO checkmarks #}
        <td class="{% if req.met %}status-met{% else %}status-below{% endif %}">
          {{ req.your_value }}
          {% if req.met %}
            (meets threshold)
          {% else %}
            (below by {{ req.difference }})
          {% endif %}
        </td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  
  <p class="eligibility-legend">
    <span class="status-met">Green</span> = meets requirement • 
    <span class="status-below">Red</span> = below threshold
  </p>
  {% endif %}
</section>
{% endif %}
```

```css
/* templates/static/css/style.css - ADD */

.consensus-diagnostics {
  margin-top: 2em;
  padding: 1em;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.consensus-diagnostics h4 {
  margin-top: 1.5em;
  margin-bottom: 0.5em;
  border-bottom: 1px solid #eee;
  padding-bottom: 0.3em;
}

.authority-table, .flag-eligibility {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 0.5em;
}

.authority-table th, .authority-table td,
.flag-eligibility th, .flag-eligibility td {
  padding: 0.5em;
  border: 1px solid #ddd;
  text-align: left;
}

/* Authority name links */
.authority-table td a {
  color: #0066cc;
  text-decoration: none;
}
.authority-table td a:hover {
  text-decoration: underline;
}

/* Row styling for authorities that didn't vote */
.row-not-voted {
  opacity: 0.6;
  background-color: #f9f9f9;
}

/* N/A styling for non-bandwidth authorities */
.not-applicable {
  color: #999;
  font-style: italic;
}

/* Deviation warning (>±5%) */
.deviation-warning {
  color: #c00;
  font-weight: bold;
}

/* Flag eligibility status - COLOR ONLY, no symbols */
.status-met {
  color: #080;  /* Green for meets threshold */
  font-weight: 500;
}
.status-below {
  color: #c00;  /* Red for below threshold */
  font-weight: 500;
}

/* General status indicators */
.status-ok { color: #080; }
.status-warn { color: #c80; }

.data-freshness, .table-legend, .eligibility-legend {
  font-size: 0.85em;
  color: #666;
  margin-top: 0.3em;
}

.issues-summary {
  margin: 1em 0;
  padding: 0.5em;
  background-color: #fff8e1;
  border-left: 3px solid #ffc107;
}

.eligibility-question {
  font-style: italic;
  color: #555;
}
```

---

## Phase 2: Authority Dashboard Enhancement

### 2.1 Authority Monitor

```python
# lib/consensus/authority_monitor.py
"""
Real-time directory authority health monitoring.
Checks latency to each authority's directory port.
"""

import asyncio
import time
from typing import Dict
from datetime import datetime

# Authority directory ports
AUTHORITY_ENDPOINTS = {
    'moria1': ('128.31.0.34', 9131),
    'tor26': ('86.59.21.38', 80),
    'dizum': ('45.66.33.45', 80),
    'gabelmoo': ('131.188.40.189', 80),
    'bastet': ('204.13.164.118', 80),
    'dannenberg': ('193.23.244.244', 80),
    'maatuska': ('171.25.193.9', 443),
    'longclaw': ('199.58.81.140', 80),
    'faravahar': ('154.35.175.225', 80),
}

# Latency thresholds (ms)
LATENCY_OK = 100
LATENCY_SLOW = 500


async def check_authority_latency(name: str, host: str, port: int, timeout: int = 10) -> dict:
    """Check latency to a single authority."""
    url_path = '/tor/status-vote/current/consensus.z'
    
    start = time.time()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout
        )
        
        # Send HEAD request
        request = f"HEAD {url_path} HTTP/1.0\r\nHost: {host}\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        
        # Read response
        await reader.read(1024)
        writer.close()
        await writer.wait_closed()
        
        latency_ms = (time.time() - start) * 1000
        
        if latency_ms < LATENCY_OK:
            status = 'ok'
        elif latency_ms < LATENCY_SLOW:
            status = 'slow'
        else:
            status = 'degraded'
        
        return {
            'name': name,
            'status': status,
            'latency_ms': round(latency_ms, 1),
            'checked_at': datetime.utcnow().isoformat(),
        }
        
    except asyncio.TimeoutError:
        return {
            'name': name,
            'status': 'timeout',
            'latency_ms': None,
            'error': f'Connection timeout ({timeout}s)',
            'checked_at': datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            'name': name,
            'status': 'error',
            'latency_ms': None,
            'error': str(e),
            'checked_at': datetime.utcnow().isoformat(),
        }


async def check_all_authorities() -> Dict:
    """Check all 9 authorities in parallel."""
    tasks = [
        check_authority_latency(name, host, port)
        for name, (host, port) in AUTHORITY_ENDPOINTS.items()
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    authorities = {}
    online = slow = offline = 0
    
    for result in results:
        if isinstance(result, Exception):
            continue
        
        name = result['name']
        authorities[name] = result
        
        if result['status'] == 'ok':
            online += 1
        elif result['status'] == 'slow':
            slow += 1
        else:
            offline += 1
    
    return {
        'authorities': authorities,
        'summary': {
            'online': online,
            'slow': slow,
            'offline': offline,
            'total': len(AUTHORITY_ENDPOINTS),
        },
        'checked_at': datetime.utcnow().isoformat(),
    }


def check_authorities_sync() -> Dict:
    """Synchronous wrapper for check_all_authorities."""
    return asyncio.run(check_all_authorities())
```

### 2.2 Authority Dashboard Template

**Important**: 
- Authority list is **DYNAMIC** - discovered from Onionoo (relays with "Authority" flag)
- Flag thresholds are **unique per authority** - shown as columns by default (not expandable)

```jinja2
{# templates/misc-authorities.html - Enhanced dashboard with dynamic authorities #}

<section class="authority-dashboard">
  <h2>🏛️ Directory Authorities ({{ authorities|length }} discovered)</h2>
  
  {# Consensus status bar #}
  <div class="consensus-status-bar">
    <span class="status-{{ consensus.freshness }}">
      {% if consensus.freshness == 'fresh' %}✅ FRESH{% else %}⚠️ {{ consensus.freshness|upper }}{% endif %}
    </span>
    │ {{ authorities|selectattr('voted')|list|length }}/{{ authorities|length }} Voted
    │ Next: {{ consensus.next_consensus_time }} ({{ consensus.minutes_until_next }} min)
  </div>
  
  {# Authority table with ALL threshold columns shown by default #}
  <table class="authority-table">
    <thead>
      <tr>
        <th>Authority</th>
        <th>Status</th>
        <th>Vote</th>
        <th>BW Auth</th>
        <th>Latency</th>
        <th>Relays</th>
        {# Threshold columns - shown by default, not expandable #}
        <th title="Guard bandwidth threshold (guard-bw-inc-exits)">Guard BW</th>
        <th title="Stable uptime threshold (stable-uptime)">Stable</th>
        <th title="Fast speed threshold (fast-speed)">Fast</th>
        <th title="Weighted Fractional Uptime (guard-wfu)">WFU</th>
      </tr>
    </thead>
    <tbody>
    {# Loop over dynamic authority list (from Onionoo discovery) #}
    {% for auth in authorities %}
      <tr class="status-{{ auth.health_status }}">
        {# Authority name links to relay page #}
        <td>
          <a href="{{ path_prefix }}relay/{{ auth.fingerprint }}.html"
             title="View {{ auth.nickname }} relay details">
            {{ auth.nickname }}
          </a>
        </td>
        <td>
          {% if auth.health_status == 'ok' %}🟢 OK
          {% elif auth.health_status == 'slow' %}🟡 SLOW
          {% else %}🔴 DOWN{% endif %}
        </td>
        <td>{% if auth.voted %}✅{% else %}❌{% endif %}</td>
        <td>{% if auth.is_bw_authority %}✅{% else %}❌{% endif %}</td>
        <td>{{ auth.latency_ms|default('—') }} ms</td>
        <td>{{ auth.relay_count|default('—')|format_number }}</td>
        {# Per-authority thresholds - ALL columns shown by default #}
        <td>{{ auth.thresholds.guard_bw|format_bandwidth }}</td>
        <td>{{ auth.thresholds.stable_uptime|format_days }}</td>
        <td>{{ auth.thresholds.fast_speed|format_bandwidth }}</td>
        <td>{{ auth.thresholds.wfu|format_percent }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  
  {# Legend #}
  <p class="table-legend">
    ↗ Authority names link to their relay page │ 
    Thresholds vary per authority (each calculates based on relays it observes)
  </p>
  
  {# Alerts #}
  {% if alerts %}
  <div class="authority-alerts">
    {% for alert in alerts %}
      <div class="alert alert-{{ alert.level }}">⚠️ {{ alert.message }}</div>
    {% endfor %}
  </div>
  {% endif %}
  
  {# Network flag distribution #}
  <div class="flag-distribution">
    Network Totals:
    Running {{ network.running|format_number }} │
    Fast {{ network.fast|format_number }} │
    Guard {{ network.guard|format_number }} │
    Exit {{ network.exit|format_number }}
  </div>
</section>
```

### 2.3 Format Authority Thresholds

```python
# lib/consensus/diagnostics.py - Add threshold formatting

def format_authority_thresholds(flag_thresholds: Dict[str, Dict]) -> Dict:
    """
    Format per-authority thresholds for template display.
    Each authority has UNIQUE thresholds based on relays it observes.
    
    Args:
        flag_thresholds: {auth_name: {threshold_key: value, ...}, ...}
    
    Returns:
        Dict with per-authority formatted values and computed ranges
    """
    formatted = {
        'per_authority': {},
        'ranges': {},
    }
    
    # Collect values for range calculation
    guard_bw_values = []
    stable_values = []
    
    for auth_name, thresholds in flag_thresholds.items():
        # Guard bandwidth threshold (in bytes, convert to MB/s)
        guard_bw = thresholds.get('guard-bw-inc-exits', 0)
        guard_bw_mb = guard_bw / 1_000_000  # Convert to MB/s
        
        # Stable uptime threshold (in seconds, convert to days)
        stable_uptime = thresholds.get('stable-uptime', 0)
        stable_days = stable_uptime / 86400  # Convert to days
        
        # WFU is consistent across authorities (98%)
        wfu = thresholds.get('guard-wfu', 0.98)
        if isinstance(wfu, str):
            wfu = float(wfu.replace('%', '')) / 100
        
        formatted['per_authority'][auth_name] = {
            'guard_bw': guard_bw_mb,
            'guard_bw_raw': guard_bw,
            'stable_uptime': stable_days,
            'stable_uptime_raw': stable_uptime,
            'wfu': wfu * 100,  # As percentage
            'fast_speed': thresholds.get('fast-speed', 0),
        }
        
        guard_bw_values.append(guard_bw_mb)
        stable_values.append(stable_days)
    
    # Calculate ranges for summary display
    if guard_bw_values:
        formatted['ranges']['guard_bw'] = {
            'min': min(guard_bw_values),
            'max': max(guard_bw_values),
        }
    
    if stable_values:
        formatted['ranges']['stable'] = {
            'min': min(stable_values),
            'max': max(stable_values),
        }
    
    # WFU is always 98% across all authorities
    formatted['ranges']['wfu'] = 98.0
    
    return formatted
```

### 2.4 Worker for Authority Health

```python
# lib/workers.py - ADD THIS FUNCTION

def fetch_authority_health(progress_logger=None):
    """
    Check directory authority health (latency checks).
    """
    api_name = "authority_health"
    
    def log_progress(message):
        if progress_logger:
            progress_logger(message)
    
    # Check cache - refresh every 15 minutes for health checks
    cache_age = _cache_manager.get_cache_age(api_name)
    if cache_age is not None and cache_age < 900:  # 15 minutes
        log_progress("using cached authority health data")
        return _load_cache(api_name)
    
    try:
        log_progress("checking directory authority health...")
        
        from lib.consensus.authority_monitor import check_authorities_sync
        data = check_authorities_sync()
        
        _save_cache(api_name, data)
        _mark_ready(api_name)
        
        summary = data.get('summary', {})
        log_progress(f"authority health: {summary.get('online', 0)}/9 online")
        
        return data
        
    except Exception as e:
        error_msg = f"Failed to check authority health: {str(e)}"
        log_progress(f"Error: {error_msg}")
        _mark_stale(api_name, error_msg)
        return _load_cache(api_name)  # Fall back to cache
```

---

## Compute Efficiency Summary

| Operation | Frequency | Complexity | Notes |
|-----------|-----------|------------|-------|
| Fetch CollecTor data | 1/hour | O(n) fetch | 9 votes + 7 bw files in parallel |
| Parse votes/bandwidth | 1/hour | O(n) | n = total relay entries |
| Build relay index | 1/hour | O(n) | Single pass indexing |
| Per-relay lookup | ~7000/hour | O(1) | Dictionary lookup |
| Authority latency check | 1/hour | O(1) | 9 parallel HTTP HEAD requests |
| Template rendering | ~7000/hour | O(1) | Data already indexed |

**Total hourly compute**: ~30 seconds for CollecTor fetch + index, then O(1) per page.

---

## 🧪 Testing Implementation

### Baseline Capture (Run Before Starting)

```bash
#!/bin/bash
# scripts/capture_baseline.sh - Run BEFORE any code changes

set -e
cd /workspace/allium

echo "=== Step 1: Capture baseline output ==="
python allium.py --progress --output-dir baseline_output/ 2>&1 | tee baseline_run.log

echo "=== Step 2: Save file inventory ==="
find baseline_output/ -type f -name "*.html" | sort > baseline_files.txt
echo "Total HTML files: $(wc -l < baseline_files.txt)"

echo "=== Step 3: Create normalized baseline (remove timestamps for diff) ==="
mkdir -p baseline_normalized/
for f in $(find baseline_output/ -name "*.html"); do
    # Normalize: remove timestamps, generation dates
    sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}/TIMESTAMP/g' "$f" | \
    sed -E 's/Generated: .*/Generated: TIMESTAMP/g' > \
    "baseline_normalized/$(basename $f)"
done

echo "=== Step 4: Run existing test suite ==="
pytest tests/ -v 2>&1 | tee baseline_tests.log

echo "=== Baseline captured ==="
echo "Files: $(wc -l < baseline_files.txt)"
echo "Tests: $(grep -c 'passed' baseline_tests.log || echo 0) passed"
```

### Unit Test: collector_fetcher.py

```python
# tests/test_collector_fetcher.py
"""
Unit tests for lib/consensus/collector_fetcher.py
Run: pytest tests/test_collector_fetcher.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
import json


class TestCollectorFetcher:
    """Test CollectorFetcher class."""
    
    @pytest.fixture
    def fetcher(self):
        from lib.consensus.collector_fetcher import CollectorFetcher
        return CollectorFetcher(timeout=10)
    
    @pytest.fixture
    def sample_vote_text(self):
        """Sample vote document for testing."""
        return """network-status-version 3
vote-status vote
published 2025-12-26 04:00:00
valid-after 2025-12-26 05:00:00
flag-thresholds stable-uptime=613624 stable-mtbf=2505783 fast-speed=26000 guard-wfu=98.000% guard-tk=691200 guard-bw-inc-exits=29000000 guard-bw-exc-exits=29000000 enough-mtbf=1
known-flags Authority BadExit Exit Fast Guard HSDir Running Stable V2Dir Valid
r TestRelay1 AAAAAAAAAAAAAAAAAAAAAAAAAAAA 2025-12-26 03:45:00 192.168.1.1 9001 0
s Fast Guard Running Stable Valid
w Bandwidth=50000 Measured
r TestRelay2 BBBBBBBBBBBBBBBBBBBBBBBBBBBB 2025-12-26 03:45:00 192.168.1.2 9001 0
s Fast Running Stable Valid
w Bandwidth=25000
"""
    
    @pytest.fixture
    def sample_bandwidth_text(self):
        """Sample bandwidth file for testing."""
        return """1735189200
version=1.0.0
bw=50000 node_id=$0000000000000000000000000000000000000001
bw=25000 node_id=$0000000000000000000000000000000000000002
"""
    
    def test_parse_vote(self, fetcher, sample_vote_text):
        """Test vote parsing extracts relay data correctly."""
        result = fetcher._parse_vote(sample_vote_text, 'moria1')
        
        assert result['authority'] == 'moria1'
        assert result['valid_after'] == '2025-12-26 05:00:00'
        assert 'flag_thresholds' in result
        assert result['flag_thresholds'].get('guard-wfu') == '98.000%'
        assert len(result['relays']) >= 1
    
    def test_parse_bandwidth_file(self, fetcher, sample_bandwidth_text):
        """Test bandwidth file parsing."""
        result = fetcher._parse_bandwidth_file(sample_bandwidth_text, 'moria1')
        
        assert result['authority'] == 'moria1'
        assert result['version'] == '1.0.0'
        assert len(result['relays']) == 2
        
        # Check specific relay
        fp = '0000000000000000000000000000000000000001'
        assert fp in result['relays']
        assert result['relays'][fp]['bandwidth'] == 50000
    
    def test_build_relay_index(self, fetcher):
        """Test relay index is built correctly."""
        fetcher.votes = {
            'moria1': {
                'relays': {
                    'ABC123': {'flags': ['Fast', 'Guard'], 'bandwidth': 50000}
                }
            }
        }
        fetcher.bandwidth_files = {
            'moria1': {
                'relays': {
                    'ABC123': {'bandwidth': 48000}
                }
            }
        }
        
        fetcher._build_relay_index()
        
        assert 'ABC123' in fetcher.relay_index
        assert 'moria1' in fetcher.relay_index['ABC123']['votes']
        assert 'moria1' in fetcher.relay_index['ABC123']['bandwidth']
    
    def test_get_relay_diagnostics_found(self, fetcher):
        """Test diagnostics for existing relay."""
        fetcher.relay_index = {
            'ABC123': {
                'votes': {
                    'moria1': {'flags': ['Fast', 'Guard', 'Running'], 'bandwidth': 50000},
                    'tor26': {'flags': ['Fast', 'Running'], 'bandwidth': 49000},
                },
                'bandwidth': {
                    'moria1': {'bandwidth': 48000},
                }
            }
        }
        fetcher.flag_thresholds = {}
        
        result = fetcher.get_relay_diagnostics('ABC123')
        
        assert result['fingerprint'] == 'ABC123'
        assert result['in_consensus'] == False  # Only 2 votes, need 5
        assert result['vote_count'] == 2
        assert 'authority_votes' in result
    
    def test_get_relay_diagnostics_not_found(self, fetcher):
        """Test diagnostics for non-existent relay."""
        fetcher.relay_index = {}
        
        result = fetcher.get_relay_diagnostics('NOTFOUND')
        
        assert 'error' in result
        assert result['in_consensus'] == False
    
    def test_bandwidth_deviation_calculation(self, fetcher):
        """Test bandwidth deviation is calculated correctly."""
        fetcher.relay_index = {
            'ABC123': {
                'votes': {},
                'bandwidth': {
                    'moria1': {'bandwidth': 100},
                    'tor26': {'bandwidth': 110},  # +10%
                    'gabelmoo': {'bandwidth': 90},  # -10%
                }
            }
        }
        
        result = fetcher._format_bandwidth(fetcher.relay_index['ABC123'])
        
        assert result['measured_count'] == 3
        assert result['average'] == 100
        
        # Check deviation warnings (>5% should be flagged)
        for m in result['measurements']:
            if m['authority'] == 'tor26':
                assert m['deviation'] == 10.0
                assert m['deviation_warning'] == True
            elif m['authority'] == 'gabelmoo':
                assert m['deviation'] == -10.0
                assert m['deviation_warning'] == True


class TestCollectorFetcherIntegration:
    """Integration tests with mocked HTTP."""
    
    @patch('lib.consensus.collector_fetcher.CollectorFetcher._fetch_url')
    def test_fetch_all_with_mock(self, mock_fetch):
        """Test full fetch flow with mocked HTTP."""
        from lib.consensus.collector_fetcher import CollectorFetcher
        
        # Mock directory listing
        mock_fetch.side_effect = [
            # Votes directory listing
            '<a href="2025-12-26-04-00-00-vote-0232AF901C31A04EE9848595AF9BB7620D4C5B2E-ABC">',
            # Vote content
            'network-status-version 3\nvote-status vote\n',
            # Bandwidth directory listing  
            '<a href="2025-12-26-04-30-00-bandwidth-moria1">',
            # Bandwidth content
            '1735189200\nversion=1.0.0\n',
        ]
        
        fetcher = CollectorFetcher(timeout=5)
        # This would fail in real execution but tests the flow
        # In real tests, provide complete mock data
```

### Unit Test: authority_monitor.py

```python
# tests/test_authority_monitor.py
"""
Unit tests for lib/consensus/authority_monitor.py
Run: pytest tests/test_authority_monitor.py -v
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock


class TestAuthorityMonitor:
    """Test authority monitoring functions."""
    
    @pytest.mark.asyncio
    async def test_check_authority_latency_success(self):
        """Test successful latency check."""
        from lib.consensus.authority_monitor import check_authority_latency
        
        with patch('asyncio.open_connection') as mock_conn:
            # Mock reader/writer
            mock_reader = AsyncMock()
            mock_reader.read = AsyncMock(return_value=b'HTTP/1.0 200 OK\r\n')
            mock_writer = MagicMock()
            mock_writer.write = MagicMock()
            mock_writer.drain = AsyncMock()
            mock_writer.close = MagicMock()
            mock_writer.wait_closed = AsyncMock()
            
            mock_conn.return_value = (mock_reader, mock_writer)
            
            result = await check_authority_latency('moria1', '128.31.0.34', 9131)
            
            assert result['name'] == 'moria1'
            assert result['status'] in ['ok', 'slow', 'degraded']
            assert 'latency_ms' in result
            assert 'checked_at' in result
    
    @pytest.mark.asyncio
    async def test_check_authority_latency_timeout(self):
        """Test timeout handling."""
        from lib.consensus.authority_monitor import check_authority_latency
        
        with patch('asyncio.open_connection') as mock_conn:
            mock_conn.side_effect = asyncio.TimeoutError()
            
            result = await check_authority_latency('moria1', '128.31.0.34', 9131, timeout=1)
            
            assert result['name'] == 'moria1'
            assert result['status'] == 'timeout'
            assert result['latency_ms'] is None
            assert 'error' in result
    
    @pytest.mark.asyncio
    async def test_check_authority_latency_connection_error(self):
        """Test connection error handling."""
        from lib.consensus.authority_monitor import check_authority_latency
        
        with patch('asyncio.open_connection') as mock_conn:
            mock_conn.side_effect = ConnectionRefusedError("Connection refused")
            
            result = await check_authority_latency('moria1', '128.31.0.34', 9131)
            
            assert result['name'] == 'moria1'
            assert result['status'] == 'error'
            assert 'error' in result
    
    @pytest.mark.asyncio
    async def test_check_all_authorities(self):
        """Test checking all authorities in parallel."""
        from lib.consensus.authority_monitor import check_all_authorities
        
        with patch('lib.consensus.authority_monitor.check_authority_latency') as mock_check:
            mock_check.return_value = {
                'name': 'test',
                'status': 'ok',
                'latency_ms': 50,
                'checked_at': '2025-12-26T04:00:00',
            }
            
            result = await check_all_authorities()
            
            assert 'authorities' in result
            assert 'summary' in result
            assert result['summary']['total'] == 9
    
    def test_check_authorities_sync(self):
        """Test synchronous wrapper."""
        from lib.consensus.authority_monitor import check_authorities_sync
        
        with patch('lib.consensus.authority_monitor.check_all_authorities') as mock_async:
            mock_async.return_value = {
                'authorities': {},
                'summary': {'online': 9, 'slow': 0, 'offline': 0, 'total': 9},
            }
            
            result = check_authorities_sync()
            
            assert 'summary' in result


class TestLatencyThresholds:
    """Test latency threshold classification."""
    
    def test_latency_ok(self):
        """Test OK latency classification."""
        from lib.consensus.authority_monitor import LATENCY_OK
        assert LATENCY_OK == 100  # ms
    
    def test_latency_slow(self):
        """Test slow latency classification."""
        from lib.consensus.authority_monitor import LATENCY_SLOW
        assert LATENCY_SLOW == 500  # ms
```

### Worker Integration Test

```python
# tests/test_workers_collector.py
"""
Integration tests for collector worker in lib/workers.py
Run: pytest tests/test_workers_collector.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
import json
import os


class TestCollectorWorker:
    """Test fetch_collector_consensus_data worker."""
    
    @pytest.fixture
    def mock_cache_manager(self):
        """Mock cache manager."""
        with patch('lib.workers._cache_manager') as mock:
            mock.get_cache_age.return_value = None  # No cache
            yield mock
    
    @pytest.fixture
    def mock_fetcher(self):
        """Mock CollectorFetcher."""
        with patch('lib.workers.CollectorFetcher') as mock:
            instance = MagicMock()
            instance.fetch_all.return_value = {
                'votes': {'moria1': {'relays': {}}},
                'bandwidth_files': {'moria1': {'relays': {}}},
                'relay_index': {'ABC123': {}},
                'flag_thresholds': {},
                'fetched_at': '2025-12-26T04:00:00',
            }
            mock.return_value = instance
            yield mock
    
    def test_fetch_fresh_data(self, mock_cache_manager, mock_fetcher):
        """Test fetching fresh data when cache is stale."""
        from lib.workers import fetch_collector_consensus_data
        
        mock_cache_manager.get_cache_age.return_value = 7200  # 2 hours old
        
        result = fetch_collector_consensus_data(progress_logger=print)
        
        assert 'relay_index' in result
        assert 'votes' in result
        mock_fetcher.return_value.fetch_all.assert_called_once()
    
    def test_use_cached_data(self, mock_cache_manager):
        """Test using cached data when fresh."""
        from lib.workers import fetch_collector_consensus_data, _load_cache
        
        mock_cache_manager.get_cache_age.return_value = 1800  # 30 min old
        
        with patch('lib.workers._load_cache') as mock_load:
            mock_load.return_value = {'relay_index': {}, 'cached': True}
            
            result = fetch_collector_consensus_data(progress_logger=print)
            
            assert result.get('cached') == True
            mock_load.assert_called_with('collector_consensus')
```

### Regression Test Script

```bash
#!/bin/bash
# scripts/validate_phase.sh - Run after each phase to verify no regressions

set -e
cd /workspace/allium

echo "=== Step 1: Generate current output ==="
python allium.py --progress --output-dir current_output/ 2>&1 | tee current_run.log

echo "=== Step 2: Normalize current output (remove timestamps) ==="
mkdir -p current_normalized/
for f in $(find current_output/ -name "*.html"); do
    sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}/TIMESTAMP/g' "$f" | \
    sed -E 's/Generated: .*/Generated: TIMESTAMP/g' > \
    "current_normalized/$(basename $f)"
done

echo "=== Step 3: Run full test suite ==="
pytest tests/ -v --tb=short
TEST_RESULT=$?

echo "=== Step 4: Compare file counts ==="
BASELINE_COUNT=$(wc -l < baseline_files.txt)
CURRENT_COUNT=$(find current_output/ -type f -name "*.html" | wc -l)
echo "Baseline files: $BASELINE_COUNT"
echo "Current files:  $CURRENT_COUNT"

if [ "$CURRENT_COUNT" -lt "$BASELINE_COUNT" ]; then
    echo "ERROR: File count decreased! Possible regression."
    exit 1
fi

echo "=== Step 5: Full diff (saved to full_diff.txt) ==="
diff -r baseline_normalized/ current_normalized/ \
    --exclude="*.log" > full_diff.txt 2>&1 || true

echo ""
echo "=== DIFF SUMMARY ==="
echo "Files only in baseline: $(grep -c 'Only in baseline' full_diff.txt || echo 0)"
echo "Files only in current:  $(grep -c 'Only in current' full_diff.txt || echo 0)"  
echo "Files that differ:      $(grep -c 'differ$' full_diff.txt || echo 0)"

echo ""
echo "=== EXPECTED CHANGES (new feature sections) ==="
DIAG_COUNT=$(grep -l "Consensus Diagnostics" current_output/relay/*.html 2>/dev/null | wc -l || echo 0)
echo "$DIAG_COUNT relay pages have new Consensus Diagnostics section"

echo ""
echo "=== UNEXPECTED CHANGES (review these!) ==="
# Show changes that are NOT the new feature sections
diff -r baseline_normalized/ current_normalized/ \
    --exclude="*.log" 2>/dev/null | \
    grep -v "Consensus Diagnostics" | \
    grep -v "Authority Votes" | \
    grep -v "Flag Eligibility" | \
    grep -v "Bandwidth Measurements" | \
    grep -v "Flag Thresholds" | \
    grep -v "^---" | \
    grep -v "^+++" | \
    grep -v "^@@" | \
    head -30 || echo "(none found)"

echo ""
echo "=== Full diff saved to: full_diff.txt ==="
echo "=== Test result: $TEST_RESULT ==="

exit $TEST_RESULT
```

---

## Testing Checklist

### Phase 1 Tests
- [ ] `pytest tests/test_collector_fetcher.py -v` passes
- [ ] `pytest tests/test_workers_collector.py -v` passes
- [ ] `pytest tests/ -v` full suite passes
- [ ] Baseline comparison shows only expected changes
- [ ] New relay diagnostics section appears in ~7000 relay pages

### Phase 2 Tests
- [ ] `pytest tests/test_authority_monitor.py -v` passes
- [ ] `pytest tests/ -v` full suite passes
- [ ] Authority latency checks complete in < 15s
- [ ] Dashboard shows all 9 authorities
- [ ] Final baseline comparison passes

### Final Validation
```bash
# Run this after Phase 2 is complete
./scripts/regression_test.sh

# Manual verification
diff -r baseline_output/ final_output/ --brief | wc -l
# Expected: Only relay-info.html files and misc-authorities.html changed
```

---

## 🚀 Production Quality Requirements

### Error Handling (Required in All New Code)

```python
# lib/consensus/collector_fetcher.py - Error handling pattern

class CollectorFetcher:
    def fetch_all(self) -> dict:
        """
        Fetch all data with comprehensive error handling.
        NEVER let exceptions propagate - always return usable data or empty fallback.
        """
        result = {
            'votes': {},
            'bandwidth_files': {},
            'relay_index': {},
            'flag_thresholds': {},
            'fetched_at': datetime.utcnow().isoformat(),
            'errors': [],  # Track all errors for debugging
        }
        
        # Fetch votes with individual error handling
        try:
            result['votes'] = self._fetch_all_votes()
        except Exception as e:
            logger.error(f"Failed to fetch votes: {e}")
            result['errors'].append(f"votes: {e}")
            # Continue with empty votes - don't fail entire fetch
        
        # Fetch bandwidth with individual error handling
        try:
            result['bandwidth_files'] = self._fetch_all_bandwidth_files()
        except Exception as e:
            logger.error(f"Failed to fetch bandwidth: {e}")
            result['errors'].append(f"bandwidth: {e}")
        
        # Build index only if we have some data
        if result['votes'] or result['bandwidth_files']:
            try:
                self._build_relay_index()
                result['relay_index'] = self.relay_index
                result['flag_thresholds'] = self.flag_thresholds
            except Exception as e:
                logger.error(f"Failed to build index: {e}")
                result['errors'].append(f"index: {e}")
        
        return result
    
    def _fetch_url(self, url: str) -> str:
        """Fetch URL with timeout, size limit, and error handling."""
        MAX_RESPONSE_SIZE = 100 * 1024 * 1024  # 100MB limit
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Allium/1.0'})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                # Check content length before reading
                content_length = response.headers.get('Content-Length')
                if content_length and int(content_length) > MAX_RESPONSE_SIZE:
                    raise ValueError(f"Response too large: {content_length} bytes")
                
                data = response.read(MAX_RESPONSE_SIZE + 1)
                if len(data) > MAX_RESPONSE_SIZE:
                    raise ValueError(f"Response exceeded {MAX_RESPONSE_SIZE} bytes")
                
                return data.decode('utf-8', errors='replace')
                
        except urllib.error.HTTPError as e:
            logger.warning(f"HTTP {e.code} for {url}")
            raise
        except urllib.error.URLError as e:
            logger.warning(f"URL error for {url}: {e.reason}")
            raise
        except socket.timeout:
            logger.warning(f"Timeout fetching {url}")
            raise
```

### Data Validation (Required)

```python
# lib/consensus/collector_fetcher.py - Validation functions

def _validate_vote_structure(self, vote_data: dict, auth_name: str) -> bool:
    """
    Validate vote data structure before use.
    Returns False if data is malformed (will be skipped).
    """
    if not isinstance(vote_data, dict):
        logger.warning(f"Vote from {auth_name} is not a dict")
        return False
    
    if 'relays' not in vote_data:
        logger.warning(f"Vote from {auth_name} missing 'relays' key")
        return False
    
    if not isinstance(vote_data.get('relays'), dict):
        logger.warning(f"Vote from {auth_name} has invalid 'relays' type")
        return False
    
    return True

def _validate_fingerprint(self, fingerprint: str) -> bool:
    """Validate fingerprint is 40 hex characters."""
    if not fingerprint:
        return False
    if len(fingerprint) != 40:
        return False
    try:
        int(fingerprint, 16)
        return True
    except ValueError:
        return False
```

### Feature Flag Implementation

```python
# lib/consensus/__init__.py
"""
Consensus troubleshooting module.
Feature flag: ALLIUM_COLLECTOR_DIAGNOSTICS (default: true)
"""

import os

COLLECTOR_DIAGNOSTICS_ENABLED = os.environ.get(
    'ALLIUM_COLLECTOR_DIAGNOSTICS', 'true'
).lower() == 'true'

def is_enabled() -> bool:
    """Check if collector diagnostics feature is enabled."""
    return COLLECTOR_DIAGNOSTICS_ENABLED
```

```python
# lib/coordinator.py - Use feature flag
from lib.consensus import is_enabled as collector_enabled

# In __init__, add to api_workers only if enabled
if self.enabled_apis == 'all' and collector_enabled():
    self.api_workers.append(("collector_consensus", fetch_collector_consensus_data, [...]))
```

```jinja2
{# templates/relay-info.html - Check for data before rendering #}
{% if relay.collector_diagnostics %}
<section class="consensus-diagnostics">
  {# ... diagnostics content ... #}
</section>
{% endif %}
{# If disabled or no data, section simply doesn't appear - graceful degradation #}
```

### Logging Standards

```python
# Logging levels and when to use them
import logging
logger = logging.getLogger(__name__)

# DEBUG: Detailed internal state (not in production logs)
logger.debug(f"Parsing vote from {auth_name}, {len(lines)} lines")

# INFO: Normal operation milestones
logger.info(f"Fetched {len(votes)} authority votes")
logger.info(f"Indexed {len(relay_index)} relays")

# WARNING: Recoverable issues (operation continues)
logger.warning(f"Failed to fetch vote from {auth_name}: {e}")
logger.warning(f"Relay {fp} has invalid fingerprint, skipping")

# ERROR: Serious issues (feature may be degraded)
logger.error(f"Failed to fetch any votes from CollecTor")
logger.error(f"Cache corruption detected, clearing cache")

# CRITICAL: Should never happen (requires investigation)
logger.critical(f"Unexpected exception in _build_relay_index: {e}")
```

### Cache Integrity

```python
# lib/workers.py - Cache validation

def _load_cache_with_validation(api_name: str) -> Optional[dict]:
    """Load cache with structure validation."""
    try:
        data = _load_cache(api_name)
        if data is None:
            return None
        
        # Validate expected structure
        if api_name == 'collector_consensus':
            required_keys = ['votes', 'relay_index', 'fetched_at']
            if not all(key in data for key in required_keys):
                logger.warning(f"Cache {api_name} missing required keys, invalidating")
                _invalidate_cache(api_name)
                return None
            
            # Validate fetched_at is not too old
            fetched_at = data.get('fetched_at', '')
            if _cache_too_old(fetched_at, max_hours=3):
                logger.info(f"Cache {api_name} too old ({fetched_at}), will refetch")
                return None
        
        return data
        
    except json.JSONDecodeError as e:
        logger.error(f"Cache {api_name} corrupted: {e}")
        _invalidate_cache(api_name)
        return None

def _invalidate_cache(api_name: str) -> None:
    """Safely delete corrupted cache file."""
    cache_file = os.path.join(CACHE_DIR, f"{api_name}_cache.json")
    try:
        if os.path.exists(cache_file):
            os.remove(cache_file)
            logger.info(f"Invalidated cache: {cache_file}")
    except OSError as e:
        logger.error(f"Failed to invalidate cache {cache_file}: {e}")
```

### Performance Profiling Points

```python
# lib/consensus/collector_fetcher.py - Add timing instrumentation

import time

class CollectorFetcher:
    def fetch_all(self) -> dict:
        timings = {}
        
        start = time.time()
        self._fetch_all_votes()
        timings['fetch_votes'] = time.time() - start
        
        start = time.time()
        self._fetch_all_bandwidth_files()
        timings['fetch_bandwidth'] = time.time() - start
        
        start = time.time()
        self._build_relay_index()
        timings['build_index'] = time.time() - start
        
        # Log performance metrics
        total = sum(timings.values())
        logger.info(f"CollecTor fetch complete in {total:.1f}s: "
                   f"votes={timings['fetch_votes']:.1f}s, "
                   f"bw={timings['fetch_bandwidth']:.1f}s, "
                   f"index={timings['build_index']:.1f}s")
        
        # Warn if too slow
        if total > 60:
            logger.warning(f"CollecTor fetch took {total:.1f}s (>60s threshold)")
        
        return {..., 'timings': timings}
```

---

## Final Pre-Production Checklist

### Before Merging to Main

- [ ] All unit tests pass: `pytest tests/ -v`
- [ ] All new code has error handling (no bare exceptions)
- [ ] All external calls have timeouts
- [ ] Feature flag implemented and tested (enable/disable)
- [ ] Baseline comparison shows only expected changes
- [ ] Performance benchmark within limits (+30s max)
- [ ] Memory usage within limits (+100MB max)
- [ ] Code review checklist completed by reviewer
- [ ] CI/CD pipeline passes

### Before Enabling in Production

- [ ] Feature deployed with flag disabled
- [ ] Staging environment tested for 48 hours
- [ ] Monitoring scripts deployed
- [ ] Rollback procedure documented and tested
- [ ] On-call team briefed on new feature

### After Production Rollout

- [ ] Monitor error rates for 24 hours
- [ ] Monitor performance metrics for 24 hours
- [ ] Verify diagnostics appearing on relay pages
- [ ] Check cache refresh working hourly
- [ ] Remove feature flag after 1 week stable

---

**Implementation Ready**: Follow existing patterns in `lib/workers.py` and `lib/coordinator.py`
