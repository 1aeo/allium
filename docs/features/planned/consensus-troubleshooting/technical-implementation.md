# Technical Implementation: Consensus Troubleshooting

**Status**: Ready for Implementation  
**Effort**: 6-7 weeks (2 phases)  
**Scope**: Latest CollecTor data only - NO historical parsing

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        HOURLY EXECUTION                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Coordinator.fetch_all_apis_threaded()                              │
│  ├── Thread: fetch_onionoo_details()     (existing)                 │
│  ├── Thread: fetch_onionoo_uptime()      (existing)                 │
│  ├── Thread: fetch_onionoo_bandwidth()   (existing)                 │
│  ├── Thread: fetch_aroi_validation()     (existing)                 │
│  └── Thread: fetch_collector_consensus() (NEW - this feature)       │
│                                                                     │
│       All threads complete (~60 seconds total)                      │
│       ↓                                                             │
│                                                                     │
│  relay_set = Coordinator.create_relay_set()                         │
│       │                                                             │
│       ├── relay_set.collector_data = {...}  # Indexed by fingerprint│
│       │                                                             │
│       ↓                                                             │
│                                                                     │
│  Page Generation (parallel via mp_workers)                          │
│  ├── relay-info.html × 7000   → O(1) lookup per relay              │
│  └── misc-authorities.html    → Authority dashboard                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
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
        """
        fingerprint = fingerprint.upper()
        if fingerprint not in self.relay_index:
            return {'error': 'Relay not found', 'in_consensus': False}
        
        relay = self.relay_index[fingerprint]
        vote_count = len(relay['votes'])
        
        return {
            'fingerprint': fingerprint,
            'in_consensus': vote_count >= 5,  # Majority required
            'vote_count': vote_count,
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
# lib/coordinator.py - MODIFY __init__

# Add to api_workers list (around line 66-72)
if self.enabled_apis == 'all':
    self.api_workers.append(("onionoo_uptime", fetch_onionoo_uptime, [self.onionoo_uptime_url, self._log_progress]))
    self.api_workers.append(("onionoo_bandwidth", fetch_onionoo_bandwidth, [self.onionoo_bandwidth_url, self.bandwidth_cache_hours, self._log_progress]))
    self.api_workers.append(("aroi_validation", fetch_aroi_validation, [self.aroi_url, self._log_progress]))
    # NEW: CollecTor consensus data for per-relay diagnostics
    self.api_workers.append(("collector_consensus", fetch_collector_consensus_data, [self._log_progress]))

# lib/coordinator.py - MODIFY create_relay_set (around line 268-269)

# After attaching other data:
setattr(relay_set, 'collector_data', self.get_collector_consensus_data())

# Add getter method:
def get_collector_consensus_data(self):
    """Get CollecTor consensus data if available."""
    return self.worker_data.get('collector_consensus')
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
  
  {# Authority Votes & Reachability #}
  <h4>Authority Votes & Reachability</h4>
  <p>
    {% if relay.collector_diagnostics.in_consensus %}
      <span class="status-ok">✅ IN CONSENSUS</span>
    {% else %}
      <span class="status-warn">⚠️ NOT IN CONSENSUS</span>
    {% endif %}
    ({{ relay.collector_diagnostics.vote_count }}/9 authorities)
  </p>
  
  <table class="authority-votes">
    <thead>
      <tr>
        <th>Authority</th>
        <th>IPv4</th>
        <th>IPv6</th>
        <th>Vote</th>
        <th>Flags</th>
        <th>Bandwidth</th>
      </tr>
    </thead>
    <tbody>
    {% for auth in relay.collector_diagnostics.authority_votes %}
      <tr>
        <td>{{ auth.authority }}</td>
        <td>{% if auth.ipv4_reachable %}✅{% else %}❌{% endif %}</td>
        <td>
          {% if auth.ipv6_reachable is none %}⚪{% elif auth.ipv6_reachable %}✅{% else %}❌{% endif %}
        </td>
        <td>{% if auth.voted %}✅{% else %}❌{% endif %}</td>
        <td>{{ auth.flags | join(' ') }}</td>
        <td>{{ auth.bandwidth | format_bandwidth if auth.bandwidth else '—' }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  
  {# Bandwidth Measurements #}
  {% if relay.collector_diagnostics.bandwidth %}
  <h4>Bandwidth Measurements</h4>
  <p>
    Measured by: {{ relay.collector_diagnostics.bandwidth.measured_count }}/{{ relay.collector_diagnostics.bandwidth.total_authorities }} bandwidth authorities
  </p>
  
  <table class="bandwidth-measurements">
    <thead>
      <tr>
        <th>BW Authority</th>
        <th>Measured</th>
        <th>Value</th>
        <th title="Values outside ±5% shown in red">Deviation</th>
      </tr>
    </thead>
    <tbody>
    {% for m in relay.collector_diagnostics.bandwidth.measurements %}
      <tr>
        <td>{{ m.authority }}</td>
        <td>{% if m.measured %}✅{% else %}❌{% endif %}</td>
        <td>{{ m.value | format_bandwidth if m.value else '—' }}</td>
        <td class="{% if m.deviation_warning %}deviation-warning{% endif %}">
          {% if m.deviation is not none %}
            {{ '%+.1f' % m.deviation }}%
          {% else %}
            —
          {% endif %}
        </td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
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

.authority-votes, .bandwidth-measurements {
  width: 100%;
  border-collapse: collapse;
}

.authority-votes th, .authority-votes td,
.bandwidth-measurements th, .bandwidth-measurements td {
  padding: 0.5em;
  border: 1px solid #ddd;
  text-align: left;
}

.deviation-warning {
  color: #c00;
  font-weight: bold;
}

.status-ok { color: #080; }
.status-warn { color: #c80; }

.data-freshness {
  font-size: 0.9em;
  color: #666;
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

### 2.2 Worker for Authority Health

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

## Testing Checklist

### Phase 1
- [ ] `CollectorFetcher.fetch_all()` returns valid data
- [ ] `CollectorFetcher.get_relay_diagnostics()` returns correct format
- [ ] Worker integrates with Coordinator
- [ ] Cache respects 1-hour freshness
- [ ] Template renders correctly for relays with/without data

### Phase 2
- [ ] Authority latency checks complete in < 15s
- [ ] Dashboard shows all 9 authorities
- [ ] Flag thresholds display correctly
- [ ] Alerts appear for slow/offline authorities

---

**Implementation Ready**: Follow existing patterns in `lib/workers.py` and `lib/coordinator.py`
