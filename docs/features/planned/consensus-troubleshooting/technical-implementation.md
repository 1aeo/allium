# Consensus Troubleshooting - Technical Implementation Guide

**Status**: 📋 Ready for Implementation  
**Dependencies**: Multi-API Architecture (Phase 1 complete)  
**Estimated Effort**: 8-10 weeks

---

## ⏱️ Data Update Frequencies Reference

### Consensus Cycle Timing

The Tor network operates on a **1-hour consensus cycle**:

```
Hour XX:00 UTC
├── XX:00-XX:05  Authorities publish votes
├── XX:05-XX:10  Consensus computed and published
├── XX:10-XX:40  CollecTor collects and publishes files
├── XX:36-XX:40  Bandwidth files published (by those that measure)
└── XX:59        Cycle ends, next consensus begins

Valid-after:  XX:00 UTC
Fresh-until:  XX+1:00 UTC  (1 hour)
Valid-until:  XX+3:00 UTC  (3 hours with warnings)
```

### Data Freshness by Source

| Source | Freshness | Best For |
|--------|-----------|----------|
| **Direct Authority** | Real-time (seconds) | Testing authority reachability |
| **CollecTor** | 5-40 min delay | Production use, bulk data |
| **Consensus Health** | ~15 min delay | Formatted thresholds, quick checks |
| **Onionoo** | ~30-60 min delay | Relay details, uptime |

### Recommended Refresh Intervals for Allium

| Data Type | Refresh Interval | Rationale |
|-----------|------------------|-----------|
| Authority Votes | 1 hour | Matches consensus cycle |
| Bandwidth Files | 1 hour | Matches publication frequency |
| Flag Thresholds | 1 hour | Derived from votes |
| Consensus | 1 hour | Matches validity period |

---

## Architecture Overview

All consensus diagnostics are focused on the **per-relay page** (`relay-info.html`), with CollecTor as the primary data source.

```
┌─────────────────────────────────────────────────────────────────────┐
│             Allium Per-Relay Consensus Diagnostics                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  PRIMARY DATA SOURCE: CollecTor (https://collector.torproject.org) │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────────┐│
│  │                    CollecTor Fetcher                           ││
│  │   /recent/relay-descriptors/votes/       → Authority Votes     ││
│  │   /recent/relay-descriptors/bandwidths/  → BW Measurements     ││
│  │   /recent/relay-descriptors/consensuses/ → Final Consensus     ││
│  └────────────────────────────────────────────────────────────────┘│
│                              │                                      │
│                              ▼                                      │
│  ┌────────────────────────────────────────────────────────────────┐│
│  │                 Consensus Data Manager                         ││
│  │  • Parses all 9 authority votes (from CollecTor)               ││
│  │  • Parses 7 bandwidth files (from CollecTor)                   ││
│  │  • Extracts flag thresholds from votes                         ││
│  │  • Caches data for 1 hour (matches consensus cycle)            ││
│  └────────────────────────────────────────────────────────────────┘│
│                              │                                      │
│                              ▼                                      │
│  ┌────────────────────────────────────────────────────────────────┐│
│  │              Per-Relay Analysis (on relay-info.html)           ││
│  │                                                                ││
│  │  Phase 1: Authority Vote Status                                ││
│  │  ├─ Which authorities voted for this relay?                    ││
│  │  └─ What flags did each authority assign?                      ││
│  │                                                                ││
│  │  Phase 2: Flag Eligibility Analysis                            ││
│  │  ├─ Compare relay metrics against thresholds                   ││
│  │  └─ Explain why flags are missing                              ││
│  │                                                                ││
│  │  Phase 3: Reachability Analysis                                ││
│  │  ├─ IPv4 reachability per authority (presence in vote)         ││
│  │  └─ IPv6 reachability (ReachableIPv6 flag)                     ││
│  │                                                                ││
│  │  Phase 4: Bandwidth Measurements                               ││
│  │  ├─ Per-authority bandwidth values                             ││
│  │  └─ Measurement status and variance                            ││
│  └────────────────────────────────────────────────────────────────┘│
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

Data Flow:
1. Worker pool fetches votes + bandwidth files from CollecTor (hourly)
2. Data is parsed, indexed by relay fingerprint, and cached
3. When generating relay-info.html, lookup relay in cached data
4. Render Phases 1-4 sections with analysis results
```

---

## Data Source Configuration

### Primary Source: Tor Project CollecTor (Recommended)

```python
# lib/consensus/collector.py

"""
CollecTor API configuration for fetching consensus data.

CollecTor is the Tor Project's data aggregation service that collects
and archives all directory authority data in one place.

Benefits:
- Single endpoint for all data
- No load on individual authorities
- Historical data available
- Reliable Tor Project infrastructure
"""

COLLECTOR_CONFIG = {
    'base_url': 'https://collector.torproject.org',
    'recent_path': '/recent/relay-descriptors',
    'archive_path': '/archive/relay-descriptors',
    
    # Data endpoints
    'endpoints': {
        'votes': '/votes/',           # All authority votes
        'consensuses': '/consensuses/', # Merged consensus documents
        'bandwidths': '/bandwidths/',   # Bandwidth authority files
        'server_descriptors': '/server-descriptors/',
        'extra_infos': '/extra-infos/',
    },
    
    # Index endpoint for listing available files
    'index_json': '/index/index.json',
    
    # Timing expectations
    'vote_delay_minutes': 35,      # Votes available ~35 min after XX:00
    'consensus_delay_minutes': 40, # Consensus available ~40 min after XX:00
    'bandwidth_delay_minutes': 45, # BW files available ~45 min after XX:00
    
    # Retention in /recent/
    'recent_retention_hours': 72,  # Files kept for 72 hours
}

def get_latest_votes_url() -> str:
    """Get URL to fetch latest vote files."""
    return f"{COLLECTOR_CONFIG['base_url']}{COLLECTOR_CONFIG['recent_path']}/votes/"

def get_latest_consensus_url() -> str:
    """Get URL to fetch latest consensus."""
    return f"{COLLECTOR_CONFIG['base_url']}{COLLECTOR_CONFIG['recent_path']}/consensuses/"

def get_latest_bandwidth_url() -> str:
    """Get URL to fetch latest bandwidth files."""
    return f"{COLLECTOR_CONFIG['base_url']}{COLLECTOR_CONFIG['recent_path']}/bandwidths/"
```

### Alternative Source: Direct Authority Access

Use direct authority access only when:
- CollecTor is unavailable
- Need data within minutes of publication
- Testing specific authority reachability

```python
# lib/consensus/authorities.py

"""
Directory Authority configuration for direct access.
Use CollecTor (above) for production; use this for fallback/testing.
"""

DIRECTORY_AUTHORITIES = {
    'moria1': {
        'name': 'moria1',
        'ipv4': '128.31.0.39',
        'dir_port': 9231,
        'or_port': 9101,
        'ipv6': '2001:858:2:2:aabb:0:563b:1526',
        'fingerprint': '9695DFC35FFEB861329B9F1AB04C46397020CE31',
        'is_bw_authority': True,
        'operator': 'arma at mit dot edu',
        'country': 'US'
    },
    'tor26': {
        'name': 'tor26',
        'ipv4': '217.196.147.77',
        'dir_port': 80,
        'or_port': 443,
        'ipv6': None,
        'fingerprint': '847B1F850344D7876491A54892F904934E4EB85D',
        'is_bw_authority': True,
        'operator': 'Peter Lundin',
        'country': 'AT'
    },
    'dizum': {
        'name': 'dizum',
        'ipv4': '45.66.35.11',
        'dir_port': 80,
        'or_port': 443,
        'ipv6': '2001:67c:289c::9',
        'fingerprint': '7EA6EAD6FD83083C538F44038BBFA077587DD755',
        'is_bw_authority': False,  # Not a bandwidth authority
        'operator': 'Alex de Joode',
        'country': 'NL'
    },
    'gabelmoo': {
        'name': 'gabelmoo',
        'ipv4': '131.188.40.189',
        'dir_port': 80,
        'or_port': 443,
        'ipv6': '2001:638:a000:4140::ffff:189',
        'fingerprint': 'F2044413DAC2E02E3D6BCF4735A19BCA1DE97281',
        'is_bw_authority': True,
        'operator': 'Sebastian Hahn',
        'country': 'DE'
    },
    'dannenberg': {
        'name': 'dannenberg',
        'ipv4': '193.23.244.244',
        'dir_port': 80,
        'or_port': 443,
        'ipv6': '2001:678:558:1000::244',
        'fingerprint': '7BE683E65D48141321C5ED92F075C55364AC7123',
        'is_bw_authority': False,  # Not a bandwidth authority
        'operator': 'CCC',
        'country': 'DE'
    },
    'maatuska': {
        'name': 'maatuska',
        'ipv4': '171.25.193.9',
        'dir_port': 443,
        'or_port': 80,
        'ipv6': '2001:67c:289c:2::9',
        'fingerprint': 'BD6A829255CB08E66FBE7D3748363586E46B3810',
        'is_bw_authority': True,
        'operator': 'Tomas at Tor Project',
        'country': 'SE'
    },
    'longclaw': {
        'name': 'longclaw',
        'ipv4': '199.58.81.140',
        'dir_port': 80,
        'or_port': 443,
        'ipv6': None,
        'fingerprint': '23D15D965BC35114467363C165C4F724B64B4F66',
        'is_bw_authority': True,
        'operator': 'Riseup',
        'country': 'US'
    },
    'bastet': {
        'name': 'bastet',
        'ipv4': '204.13.164.118',
        'dir_port': 80,
        'or_port': 443,
        'ipv6': '2620:13:4000:6000::1000:118',
        'fingerprint': '27102BC123E7AF1D4741AE047E160C91ADC76B21',
        'is_bw_authority': True,
        'operator': 'stefani at Tor Project',
        'country': 'US'
    },
    'faravahar': {
        'name': 'faravahar',
        'ipv4': '216.218.219.41',
        'dir_port': 80,
        'or_port': 443,
        'ipv6': '2607:8500:154::3',
        'fingerprint': 'CF6D0AAFB385BE71B8E111FC5CFF4B47923733BC',
        'is_bw_authority': True,
        'operator': 'sina at Tor Project',
        'country': 'US'
    }
}

# Authority fingerprint to name mapping (for parsing CollecTor filenames)
AUTHORITY_FINGERPRINTS = {
    '9695DFC35FFEB861329B9F1AB04C46397020CE31': 'moria1',
    '847B1F850344D7876491A54892F904934E4EB85D': 'tor26',
    '7EA6EAD6FD83083C538F44038BBFA077587DD755': 'dizum',
    'F2044413DAC2E02E3D6BCF4735A19BCA1DE97281': 'gabelmoo',
    '7BE683E65D48141321C5ED92F075C55364AC7123': 'dannenberg',
    'BD6A829255CB08E66FBE7D3748363586E46B3810': 'maatuska',
    '23D15D965BC35114467363C165C4F724B64B4F66': 'longclaw',
    '27102BC123E7AF1D4741AE047E160C91ADC76B21': 'bastet',
    'CF6D0AAFB385BE71B8E111FC5CFF4B47923733BC': 'faravahar',
}

# Bandwidth authorities (7 of 9 run sbws bandwidth scanners)
BANDWIDTH_AUTHORITIES = [
    'moria1', 'tor26', 'gabelmoo', 'maatuska', 
    'longclaw', 'bastet', 'faravahar'
]

# Non-bandwidth authorities (do not measure relay bandwidth)
NON_BANDWIDTH_AUTHORITIES = ['dizum', 'dannenberg']

def get_vote_url(authority_name: str) -> str:
    """Get the URL to fetch an authority's current vote."""
    auth = DIRECTORY_AUTHORITIES.get(authority_name)
    if not auth:
        raise ValueError(f"Unknown authority: {authority_name}")
    return f"http://{auth['ipv4']}:{auth['dir_port']}/tor/status-vote/current/authority"

def get_bandwidth_url(authority_name: str) -> str:
    """Get the URL to fetch an authority's bandwidth file."""
    auth = DIRECTORY_AUTHORITIES.get(authority_name)
    if not auth:
        raise ValueError(f"Unknown authority: {authority_name}")
    if not auth['is_bw_authority']:
        return None
    return f"http://{auth['ipv4']}:{auth['dir_port']}/tor/status-vote/next/bandwidth"

def get_bandwidth_authorities() -> list:
    """Get list of bandwidth authorities."""
    return [name for name, auth in DIRECTORY_AUTHORITIES.items() 
            if auth['is_bw_authority']]
```

---

## Vote Parser Implementation

### CollecTor Data Fetcher (Primary Implementation)

All consensus troubleshooting data is fetched from CollecTor to minimize load on individual directory authorities and provide a reliable, centralized data source.

```python
# lib/consensus/collector_fetcher.py

"""
Fetch votes and bandwidth files from CollecTor.
This is the PRIMARY data source for all consensus troubleshooting features.

Benefits of CollecTor:
- Single source for all 9 authority votes
- Single source for all 7 bandwidth files  
- No load on individual authorities
- Reliable Tor Project infrastructure
- Files available within 35-45 minutes of consensus
"""

import re
import urllib.request
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

from .collector import COLLECTOR_CONFIG
from .authorities import AUTHORITY_FINGERPRINTS, BANDWIDTH_AUTHORITIES

logger = logging.getLogger(__name__)


class CollectorFetcher:
    """
    Unified fetcher for all CollecTor data needed for per-relay diagnostics.
    
    Fetches:
    - All 9 authority votes (for Phases 1-3)
    - All 7 bandwidth files (for Phase 4)
    """
    
    def __init__(self, cache_dir: str = None):
        self.base_url = COLLECTOR_CONFIG['base_url']
        self.recent_path = COLLECTOR_CONFIG['recent_path']
        self.cache_dir = cache_dir
        
        # Parsed data storage
        self.votes = {}           # authority_name -> parsed vote
        self.bandwidth_files = {} # authority_name -> parsed bandwidth data
        self.relay_index = {}     # fingerprint -> {votes: [], bw: []}
        self.flag_thresholds = {} # authority_name -> thresholds dict
        
    def fetch_all_data(self, timeout: int = 60) -> dict:
        """
        Fetch all data needed for relay diagnostics.
        
        Returns:
            Dict with 'votes', 'bandwidth_files', 'relay_index', 'flag_thresholds'
        """
        # Fetch votes and bandwidth files in sequence (could parallelize)
        self._fetch_votes(timeout)
        self._fetch_bandwidth_files(timeout)
        self._build_relay_index()
        self._extract_flag_thresholds()
        
        return {
            'votes': self.votes,
            'bandwidth_files': self.bandwidth_files,
            'relay_index': self.relay_index,
            'flag_thresholds': self.flag_thresholds,
            'fetched_at': datetime.utcnow().isoformat()
        }
    
    # ═══════════════════════════════════════════════════════════════════
    # VOTES FETCHING (Phase 1-3)
    # ═══════════════════════════════════════════════════════════════════
    
    def _fetch_votes(self, timeout: int) -> None:
        """Fetch all authority votes from CollecTor."""
        votes_url = f"{self.base_url}{self.recent_path}/votes/"
        
        try:
            index_html = self._fetch_url(votes_url, timeout)
            latest_votes = self._find_latest_vote_files(index_html)
            logger.info(f"Found {len(latest_votes)} vote files for latest consensus")
            
            for filename, auth_fingerprint in latest_votes.items():
                auth_name = AUTHORITY_FINGERPRINTS.get(auth_fingerprint, auth_fingerprint[:8])
                try:
                    vote_url = f"{votes_url}{filename}"
                    vote_text = self._fetch_url(vote_url, timeout)
                    self.votes[auth_name] = self._parse_vote(vote_text, auth_name)
                    logger.info(f"Parsed vote from {auth_name}: {self.votes[auth_name]['relay_count']} relays")
                except Exception as e:
                    logger.warning(f"Failed to fetch vote from {auth_name}: {e}")
                    self.votes[auth_name] = {'error': str(e), 'relays': {}}
                    
        except Exception as e:
            logger.error(f"Failed to fetch vote index from CollecTor: {e}")
    
    def _find_latest_vote_files(self, index_html: str) -> Dict[str, str]:
        """
        Parse CollecTor index to find latest vote files.
        
        Vote filename format:
        YYYY-MM-DD-HH-00-00-vote-[AUTHORITY_FINGERPRINT]-[VOTE_DIGEST]
        
        Returns:
            Dict mapping filename to authority fingerprint
        """
        # Pattern: 2025-12-26-04-00-00-vote-FINGERPRINT-DIGEST
        vote_pattern = r'href="(\d{4}-\d{2}-\d{2}-(\d{2})-00-00-vote-([A-F0-9]{40})-[A-F0-9]+)"'
        matches = re.findall(vote_pattern, index_html)
        
        if not matches:
            return {}
        
        # Group by hour, get latest
        votes_by_hour = {}
        for filename, hour, fingerprint in matches:
            if hour not in votes_by_hour:
                votes_by_hour[hour] = {}
            votes_by_hour[hour][filename] = fingerprint
        
        # Return votes from the latest hour
        latest_hour = max(votes_by_hour.keys())
        logger.info(f"Using votes from hour {latest_hour}:00 UTC")
        return votes_by_hour[latest_hour]
    
    def _parse_vote(self, vote_text: str, authority_name: str) -> dict:
        """Parse a vote document into structured data."""
        parsed = {
            'authority': authority_name,
            'published': None,
            'valid_after': None,
            'flag_thresholds': {},
            'known_flags': [],
            'relays': {},  # fingerprint -> relay data
            'relay_count': 0
        }
        
        lines = vote_text.split('\n')
        current_relay = None
        
        for line in lines:
            # Parse header
            if line.startswith('published '):
                parsed['published'] = line.split(' ', 1)[1]
            elif line.startswith('valid-after '):
                parsed['valid_after'] = line.split(' ', 1)[1]
            elif line.startswith('known-flags '):
                parsed['known_flags'] = line.split(' ')[1:]
            elif line.startswith('flag-thresholds '):
                parsed['flag_thresholds'] = self._parse_flag_thresholds(line)
            
            # Parse relay entries
            elif line.startswith('r '):
                parts = line.split(' ')
                if len(parts) >= 8:
                    fingerprint = self._decode_fingerprint(parts[2])
                    current_relay = {
                        'nickname': parts[1],
                        'fingerprint': fingerprint,
                        'ip': parts[5],
                        'or_port': parts[6],
                        'dir_port': parts[7],
                        'flags': [],
                        'bandwidth': None,
                        'measured': False
                    }
                    parsed['relays'][fingerprint] = current_relay
                    parsed['relay_count'] += 1
            
            elif line.startswith('a ') and current_relay:
                # IPv6 address line: a [2001:db8::1]:9001
                current_relay['ipv6'] = line.split(' ', 1)[1] if len(line) > 2 else None
            
            elif line.startswith('s ') and current_relay:
                current_relay['flags'] = line.split(' ')[1:]
            
            elif line.startswith('w ') and current_relay:
                bw_match = re.search(r'Bandwidth=(\d+)', line)
                if bw_match:
                    current_relay['bandwidth'] = int(bw_match.group(1))
                current_relay['measured'] = 'Measured' in line
        
        return parsed
    
    # ═══════════════════════════════════════════════════════════════════
    # BANDWIDTH FILES FETCHING (Phase 4)
    # ═══════════════════════════════════════════════════════════════════
    
    def _fetch_bandwidth_files(self, timeout: int) -> None:
        """Fetch bandwidth files from CollecTor."""
        bw_url = f"{self.base_url}{self.recent_path}/bandwidths/"
        
        try:
            index_html = self._fetch_url(bw_url, timeout)
            latest_bw_files = self._find_latest_bandwidth_files(index_html)
            logger.info(f"Found {len(latest_bw_files)} bandwidth files")
            
            for filename, auth_name in latest_bw_files.items():
                try:
                    file_url = f"{bw_url}{filename}"
                    bw_text = self._fetch_url(file_url, timeout)
                    self.bandwidth_files[auth_name] = self._parse_bandwidth_file(bw_text, auth_name)
                    logger.info(f"Parsed bandwidth file from {auth_name}: {len(self.bandwidth_files[auth_name]['relays'])} relays")
                except Exception as e:
                    logger.warning(f"Failed to fetch bandwidth file from {auth_name}: {e}")
                    self.bandwidth_files[auth_name] = {'error': str(e), 'relays': {}}
                    
        except Exception as e:
            logger.error(f"Failed to fetch bandwidth index from CollecTor: {e}")
    
    def _find_latest_bandwidth_files(self, index_html: str) -> Dict[str, str]:
        """
        Parse CollecTor index to find latest bandwidth files.
        
        Bandwidth filename format:
        YYYY-MM-DD-HH-MM-SS-bandwidth-[SOURCE_NAME]
        
        Returns:
            Dict mapping filename to authority/scanner name
        """
        # Pattern: 2025-12-26-04-36-14-bandwidth-moria1
        bw_pattern = r'href="(\d{4}-\d{2}-\d{2}-(\d{2})-\d{2}-\d{2}-bandwidth-(\w+))"'
        matches = re.findall(bw_pattern, index_html)
        
        if not matches:
            return {}
        
        # Group by hour, get latest for each authority
        bw_by_hour = {}
        for filename, hour, auth_name in matches:
            if hour not in bw_by_hour:
                bw_by_hour[hour] = {}
            # Keep latest file per authority (overwrite if same hour)
            bw_by_hour[hour][filename] = auth_name
        
        # Return bandwidth files from the latest hour
        latest_hour = max(bw_by_hour.keys())
        logger.info(f"Using bandwidth files from hour {latest_hour}:XX UTC")
        return bw_by_hour[latest_hour]
    
    def _parse_bandwidth_file(self, bw_text: str, authority_name: str) -> dict:
        """
        Parse a bandwidth file into structured data.
        
        Format:
        1734567890  # timestamp
        version=1.4.0
        ...
        bw=12345 node_id=$FINGERPRINT nick=RelayName ...
        """
        parsed = {
            'authority': authority_name,
            'timestamp': None,
            'version': None,
            'relays': {},  # fingerprint -> bw value
            'relay_count': 0
        }
        
        for line in bw_text.split('\n'):
            if line.startswith('bw='):
                # Parse bandwidth line
                bw_match = re.search(r'bw=(\d+)', line)
                node_match = re.search(r'node_id=\$([A-F0-9]{40})', line)
                
                if bw_match and node_match:
                    fingerprint = node_match.group(1)
                    parsed['relays'][fingerprint] = {
                        'bandwidth': int(bw_match.group(1)),
                        'authority': authority_name
                    }
                    parsed['relay_count'] += 1
            
            elif line.startswith('version='):
                parsed['version'] = line.split('=', 1)[1]
            elif line.isdigit():
                parsed['timestamp'] = int(line)
        
        return parsed
    
    # ═══════════════════════════════════════════════════════════════════
    # RELAY INDEX & THRESHOLD EXTRACTION
    # ═══════════════════════════════════════════════════════════════════
    
    def _build_relay_index(self) -> None:
        """
        Build index mapping fingerprint -> data from all sources.
        This enables fast per-relay lookups during page generation.
        """
        # Index votes
        for auth_name, vote_data in self.votes.items():
            if 'error' in vote_data:
                continue
            for fingerprint, relay_data in vote_data.get('relays', {}).items():
                if fingerprint not in self.relay_index:
                    self.relay_index[fingerprint] = {'votes': {}, 'bandwidth': {}}
                self.relay_index[fingerprint]['votes'][auth_name] = relay_data
        
        # Index bandwidth measurements
        for auth_name, bw_data in self.bandwidth_files.items():
            if 'error' in bw_data:
                continue
            for fingerprint, bw_info in bw_data.get('relays', {}).items():
                if fingerprint not in self.relay_index:
                    self.relay_index[fingerprint] = {'votes': {}, 'bandwidth': {}}
                self.relay_index[fingerprint]['bandwidth'][auth_name] = bw_info
        
        logger.info(f"Built relay index with {len(self.relay_index)} relays")
    
    def _extract_flag_thresholds(self) -> None:
        """Extract flag thresholds from all authority votes."""
        for auth_name, vote_data in self.votes.items():
            if 'flag_thresholds' in vote_data and vote_data['flag_thresholds']:
                self.flag_thresholds[auth_name] = vote_data['flag_thresholds']
        
        logger.info(f"Extracted thresholds from {len(self.flag_thresholds)} authorities")
    
    # ═══════════════════════════════════════════════════════════════════
    # PER-RELAY ANALYSIS (Called during page generation)
    # ═══════════════════════════════════════════════════════════════════
    
    def get_relay_diagnostics(self, fingerprint: str) -> dict:
        """
        Get complete diagnostics for a single relay.
        Returns data for all 4 phases of the relay page.
        """
        fingerprint = fingerprint.upper()
        
        if fingerprint not in self.relay_index:
            return {
                'error': 'Relay not found in any authority vote',
                'in_consensus': False,
                'phases': {}
            }
        
        relay_data = self.relay_index[fingerprint]
        
        return {
            'fingerprint': fingerprint,
            'in_consensus': len(relay_data['votes']) >= 5,  # Majority
            'phases': {
                'authority_votes': self._analyze_authority_votes(fingerprint, relay_data),
                'flag_eligibility': self._analyze_flag_eligibility(fingerprint, relay_data),
                'reachability': self._analyze_reachability(fingerprint, relay_data),
                'bandwidth': self._analyze_bandwidth(fingerprint, relay_data)
            },
            'analyzed_at': datetime.utcnow().isoformat()
        }
    
    def _analyze_authority_votes(self, fingerprint: str, relay_data: dict) -> dict:
        """Phase 1: Which authorities voted for this relay?"""
        result = {
            'voted_count': len(relay_data['votes']),
            'total_authorities': 9,
            'per_authority': {},
            'issues': []
        }
        
        all_authorities = list(AUTHORITY_FINGERPRINTS.values())
        
        for auth_name in all_authorities:
            if auth_name in relay_data['votes']:
                vote_info = relay_data['votes'][auth_name]
                result['per_authority'][auth_name] = {
                    'voted': True,
                    'flags': vote_info.get('flags', []),
                    'bandwidth': vote_info.get('bandwidth'),
                    'measured': vote_info.get('measured', False)
                }
            else:
                result['per_authority'][auth_name] = {
                    'voted': False,
                    'flags': [],
                    'bandwidth': None,
                    'measured': False
                }
                result['issues'].append(f"{auth_name}: Relay not in vote")
        
        # Detect flag discrepancies
        flag_counts = {}
        for auth_name, info in result['per_authority'].items():
            if info['voted']:
                for flag in info['flags']:
                    flag_counts[flag] = flag_counts.get(flag, 0) + 1
        
        for flag, count in flag_counts.items():
            if 0 < count < result['voted_count']:
                missing = [a for a, i in result['per_authority'].items() 
                          if i['voted'] and flag not in i['flags']]
                if missing:
                    result['issues'].append(f"{', '.join(missing)}: Not assigning {flag} flag")
        
        return result
    
    def _analyze_flag_eligibility(self, fingerprint: str, relay_data: dict) -> dict:
        """Phase 2: Why doesn't relay have certain flags?"""
        # Get median thresholds
        median_thresholds = self._get_median_thresholds()
        
        # Get relay's current flags from majority vote
        current_flags = set()
        for vote_info in relay_data['votes'].values():
            current_flags.update(vote_info.get('flags', []))
        
        return {
            'current_flags': list(current_flags),
            'thresholds': median_thresholds,
            'analysis': {
                'Guard': self._check_flag_requirements('Guard', relay_data, median_thresholds),
                'Stable': self._check_flag_requirements('Stable', relay_data, median_thresholds),
                'Fast': self._check_flag_requirements('Fast', relay_data, median_thresholds),
                'HSDir': self._check_flag_requirements('HSDir', relay_data, median_thresholds)
            }
        }
    
    def _analyze_reachability(self, fingerprint: str, relay_data: dict) -> dict:
        """Phase 3: Can authorities reach this relay?"""
        result = {
            'ipv4': {},
            'ipv6': {},
            'issues': []
        }
        
        all_authorities = list(AUTHORITY_FINGERPRINTS.values())
        ipv6_testing_auths = ['moria1', 'gabelmoo', 'dannenberg', 'maatuska', 'bastet']
        
        for auth_name in all_authorities:
            # IPv4 reachability = presence in vote with Running flag
            if auth_name in relay_data['votes']:
                flags = relay_data['votes'][auth_name].get('flags', [])
                result['ipv4'][auth_name] = {
                    'reachable': 'Running' in flags,
                    'evidence': 'Running flag in vote' if 'Running' in flags else 'In vote but no Running'
                }
                
                # IPv6 reachability
                if auth_name in ipv6_testing_auths:
                    has_ipv6 = 'ReachableIPv6' in flags
                    no_ipv6 = 'NoIPv6Consensus' in flags
                    result['ipv6'][auth_name] = {
                        'reachable': has_ipv6,
                        'evidence': 'ReachableIPv6' if has_ipv6 else ('NoIPv6Consensus' if no_ipv6 else 'No IPv6 flags')
                    }
                    if no_ipv6:
                        result['issues'].append(f"{auth_name}: Cannot reach via IPv6")
                else:
                    result['ipv6'][auth_name] = {'reachable': None, 'evidence': 'Does not test IPv6'}
            else:
                result['ipv4'][auth_name] = {'reachable': False, 'evidence': 'Not in vote'}
                result['ipv6'][auth_name] = {'reachable': False, 'evidence': 'Not in vote'}
                result['issues'].append(f"{auth_name}: Relay not reachable (not in vote)")
        
        return result
    
    def _analyze_bandwidth(self, fingerprint: str, relay_data: dict) -> dict:
        """Phase 4: Bandwidth authority measurements."""
        result = {
            'measured_by': [],
            'not_measured_by': [],
            'per_authority': {},
            'consensus_weight': None,
            'measurement_variance': None
        }
        
        bw_values = []
        
        for auth_name in BANDWIDTH_AUTHORITIES:
            if auth_name in relay_data['bandwidth']:
                bw_info = relay_data['bandwidth'][auth_name]
                bw_value = bw_info.get('bandwidth', 0)
                result['per_authority'][auth_name] = {
                    'measured': True,
                    'value': bw_value
                }
                result['measured_by'].append(auth_name)
                bw_values.append(bw_value)
            else:
                result['per_authority'][auth_name] = {
                    'measured': False,
                    'value': None
                }
                result['not_measured_by'].append(auth_name)
        
        # Calculate statistics
        if bw_values:
            avg = sum(bw_values) / len(bw_values)
            result['average_measurement'] = avg
            if len(bw_values) > 1:
                variance = sum((v - avg) ** 2 for v in bw_values) / len(bw_values)
                result['measurement_variance'] = (variance ** 0.5) / avg * 100  # CV as %
        
        return result
    
    # ═══════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════
    
    def _fetch_url(self, url: str, timeout: int) -> str:
        """Fetch content from URL."""
        req = urllib.request.Request(url, headers={'User-Agent': 'Allium/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8', errors='replace')
    
    def _parse_flag_thresholds(self, line: str) -> dict:
        """Parse flag-thresholds line."""
        thresholds = {}
        parts = line.split(' ')[1:]
        for part in parts:
            if '=' in part:
                key, value = part.split('=', 1)
                try:
                    thresholds[key] = float(value) if '.' in value else int(value)
                except ValueError:
                    thresholds[key] = value
        return thresholds
    
    def _decode_fingerprint(self, b64_fingerprint: str) -> str:
        """Decode base64 fingerprint to hex."""
        import base64
        try:
            decoded = base64.b64decode(b64_fingerprint + '==')
            return decoded.hex().upper()
        except Exception:
            return b64_fingerprint
    
    def _get_median_thresholds(self) -> dict:
        """Calculate median thresholds across all authorities."""
        if not self.flag_thresholds:
            return {}
        
        all_keys = set()
        for thresholds in self.flag_thresholds.values():
            all_keys.update(thresholds.keys())
        
        median_thresholds = {}
        for key in all_keys:
            values = [t[key] for t in self.flag_thresholds.values() if key in t]
            if values:
                values.sort()
                mid = len(values) // 2
                median_thresholds[key] = values[mid] if len(values) % 2 else (values[mid-1] + values[mid]) / 2
        
        return median_thresholds
    
    def _check_flag_requirements(self, flag: str, relay_data: dict, thresholds: dict) -> dict:
        """Check if relay meets requirements for a specific flag."""
        # This would compare relay metrics against thresholds
        # Simplified for now - full implementation in ThresholdAnalyzer
        return {
            'eligible': None,  # Would calculate based on relay metrics
            'requirements': [],
            'missing': []
        }
```

### Core Vote Parser (Alternative - Direct Authority Access)

```python
# lib/consensus/vote_parser.py

"""
Parse directory authority votes to determine relay voting status.
"""

import re
import urllib.request
from typing import Dict, List, Optional
from datetime import datetime
import logging

from .authorities import DIRECTORY_AUTHORITIES, get_vote_url

logger = logging.getLogger(__name__)


class VoteParser:
    """Parse and analyze directory authority votes."""
    
    def __init__(self, cache_manager=None):
        self.cache_manager = cache_manager
        self.votes = {}  # authority_name -> parsed vote data
        
    def fetch_all_votes(self, timeout: int = 30) -> Dict[str, dict]:
        """
        Fetch votes from all directory authorities.
        
        Returns:
            Dict mapping authority names to parsed vote data
        """
        for auth_name in DIRECTORY_AUTHORITIES:
            try:
                vote_url = get_vote_url(auth_name)
                vote_text = self._fetch_vote(vote_url, timeout)
                self.votes[auth_name] = self._parse_vote(vote_text, auth_name)
                logger.info(f"Successfully fetched vote from {auth_name}")
            except Exception as e:
                logger.warning(f"Failed to fetch vote from {auth_name}: {e}")
                self.votes[auth_name] = {'error': str(e), 'relays': {}}
        
        return self.votes
    
    def _fetch_vote(self, url: str, timeout: int) -> str:
        """Fetch vote document from URL."""
        req = urllib.request.Request(url, headers={'User-Agent': 'Allium/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8', errors='replace')
    
    def _parse_vote(self, vote_text: str, authority_name: str) -> dict:
        """
        Parse a vote document and extract relay information.
        
        Vote format (simplified):
        r nickname fingerprint publication-date ip or-port dir-port
        s Flag1 Flag2 Flag3
        w Bandwidth=12345
        """
        parsed = {
            'authority': authority_name,
            'published': None,
            'valid_after': None,
            'flag_thresholds': {},
            'known_flags': [],
            'relays': {},  # fingerprint -> relay data
            'relay_count': 0
        }
        
        lines = vote_text.split('\n')
        current_relay = None
        
        for line in lines:
            # Parse header information
            if line.startswith('published '):
                parsed['published'] = line.split(' ', 1)[1]
            elif line.startswith('valid-after '):
                parsed['valid_after'] = line.split(' ', 1)[1]
            elif line.startswith('known-flags '):
                parsed['known_flags'] = line.split(' ')[1:]
            elif line.startswith('flag-thresholds '):
                parsed['flag_thresholds'] = self._parse_flag_thresholds(line)
            
            # Parse relay entries
            elif line.startswith('r '):
                # r nickname fingerprint_base64 date time ip or_port dir_port
                parts = line.split(' ')
                if len(parts) >= 8:
                    nickname = parts[1]
                    fingerprint_b64 = parts[2]
                    fingerprint = self._decode_fingerprint(fingerprint_b64)
                    ip = parts[5]
                    or_port = parts[6]
                    dir_port = parts[7]
                    
                    current_relay = {
                        'nickname': nickname,
                        'fingerprint': fingerprint,
                        'ip': ip,
                        'or_port': or_port,
                        'dir_port': dir_port,
                        'flags': [],
                        'bandwidth': None,
                        'measured': False
                    }
                    parsed['relays'][fingerprint] = current_relay
                    parsed['relay_count'] += 1
            
            elif line.startswith('s ') and current_relay:
                # s Flag1 Flag2 Flag3
                current_relay['flags'] = line.split(' ')[1:]
            
            elif line.startswith('w ') and current_relay:
                # w Bandwidth=12345 Measured=1
                bw_match = re.search(r'Bandwidth=(\d+)', line)
                if bw_match:
                    current_relay['bandwidth'] = int(bw_match.group(1))
                current_relay['measured'] = 'Measured' in line
        
        return parsed
    
    def _parse_flag_thresholds(self, line: str) -> dict:
        """Parse flag-thresholds line into structured dict."""
        thresholds = {}
        # Example: flag-thresholds stable-uptime=1749590 stable-mtbf=31256159 ...
        parts = line.split(' ')[1:]  # Skip 'flag-thresholds'
        for part in parts:
            if '=' in part:
                key, value = part.split('=', 1)
                try:
                    thresholds[key] = int(value) if '.' not in value else float(value)
                except ValueError:
                    thresholds[key] = value
        return thresholds
    
    def _decode_fingerprint(self, b64_fingerprint: str) -> str:
        """Decode base64 fingerprint to hex format."""
        import base64
        try:
            decoded = base64.b64decode(b64_fingerprint + '==')
            return decoded.hex().upper()
        except Exception:
            return b64_fingerprint
    
    def get_relay_vote_status(self, fingerprint: str) -> Dict[str, dict]:
        """
        Get voting status for a specific relay from all authorities.
        
        Args:
            fingerprint: Relay fingerprint (hex format)
            
        Returns:
            Dict mapping authority names to relay status
        """
        fingerprint = fingerprint.upper()
        result = {}
        
        for auth_name, vote_data in self.votes.items():
            if 'error' in vote_data:
                result[auth_name] = {
                    'voted': False,
                    'error': vote_data['error'],
                    'flags': [],
                    'bandwidth': None,
                    'measured': False
                }
            elif fingerprint in vote_data['relays']:
                relay = vote_data['relays'][fingerprint]
                result[auth_name] = {
                    'voted': True,
                    'flags': relay['flags'],
                    'bandwidth': relay['bandwidth'],
                    'measured': relay['measured'],
                    'nickname': relay['nickname']
                }
            else:
                result[auth_name] = {
                    'voted': False,
                    'error': 'Not in vote',
                    'flags': [],
                    'bandwidth': None,
                    'measured': False
                }
        
        return result
    
    def analyze_relay_consensus_status(self, fingerprint: str) -> dict:
        """
        Comprehensive analysis of a relay's consensus status.
        
        Returns analysis with:
        - Overall consensus status
        - Per-authority voting details
        - Flag discrepancies
        - Bandwidth measurement analysis
        - Troubleshooting recommendations
        """
        vote_status = self.get_relay_vote_status(fingerprint)
        
        # Count how many authorities voted for this relay
        voted_count = sum(1 for v in vote_status.values() if v.get('voted'))
        total_authorities = len(DIRECTORY_AUTHORITIES)
        
        # Analyze flag discrepancies
        flag_sets = {}
        for auth_name, status in vote_status.items():
            if status.get('voted'):
                flag_tuple = tuple(sorted(status['flags']))
                if flag_tuple not in flag_sets:
                    flag_sets[flag_tuple] = []
                flag_sets[flag_tuple].append(auth_name)
        
        # Find missing flags compared to majority
        all_flags = set()
        for status in vote_status.values():
            if status.get('voted'):
                all_flags.update(status['flags'])
        
        flag_analysis = {}
        for flag in all_flags:
            has_flag = [auth for auth, status in vote_status.items() 
                       if status.get('voted') and flag in status['flags']]
            missing_flag = [auth for auth, status in vote_status.items() 
                          if status.get('voted') and flag not in status['flags']]
            flag_analysis[flag] = {
                'authorities_assigning': has_flag,
                'authorities_not_assigning': missing_flag,
                'assignment_rate': len(has_flag) / voted_count if voted_count > 0 else 0
            }
        
        # Analyze bandwidth measurements
        bandwidth_measurements = {}
        for auth_name, status in vote_status.items():
            if status.get('voted') and status.get('bandwidth') is not None:
                bandwidth_measurements[auth_name] = {
                    'value': status['bandwidth'],
                    'measured': status['measured']
                }
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            vote_status, voted_count, total_authorities, flag_analysis
        )
        
        return {
            'fingerprint': fingerprint,
            'in_consensus': voted_count >= (total_authorities // 2 + 1),  # Majority
            'voted_count': voted_count,
            'total_authorities': total_authorities,
            'per_authority_status': vote_status,
            'flag_analysis': flag_analysis,
            'bandwidth_measurements': bandwidth_measurements,
            'recommendations': recommendations,
            'analyzed_at': datetime.utcnow().isoformat()
        }
    
    def _generate_recommendations(self, vote_status: dict, voted_count: int, 
                                   total: int, flag_analysis: dict) -> List[str]:
        """Generate troubleshooting recommendations based on analysis."""
        recommendations = []
        
        # Check if missing from consensus entirely
        if voted_count == 0:
            recommendations.append(
                "⚠️ CRITICAL: Relay is not in ANY authority's vote. "
                "Check that your relay is running and ORPort is reachable."
            )
            recommendations.append(
                "Run: `tor --verify-config` to check your configuration."
            )
            return recommendations
        
        # Check if missing from some authorities
        missing_from = [auth for auth, status in vote_status.items() 
                       if not status.get('voted')]
        if missing_from:
            recommendations.append(
                f"⚠️ Relay missing from {len(missing_from)} authority votes: "
                f"{', '.join(missing_from)}. Check network connectivity to these authorities."
            )
        
        # Check for Guard flag issues
        if 'Guard' in flag_analysis:
            guard_info = flag_analysis['Guard']
            if guard_info['assignment_rate'] < 1.0 and guard_info['assignment_rate'] > 0:
                not_assigning = guard_info['authorities_not_assigning']
                recommendations.append(
                    f"ℹ️ Guard flag not assigned by: {', '.join(not_assigning)}. "
                    "Check if your relay meets WFU (≥98%) and bandwidth thresholds."
                )
        
        # Check for Stable flag issues
        if 'Stable' in flag_analysis:
            stable_info = flag_analysis['Stable']
            if stable_info['assignment_rate'] < 1.0:
                recommendations.append(
                    "ℹ️ Stable flag not assigned by all authorities. "
                    "Ensure uptime and MTBF meet median thresholds."
                )
        
        return recommendations
```

---

## Flag Threshold Analyzer

```python
# lib/consensus/threshold_analyzer.py

"""
Analyze relay flag eligibility against current thresholds.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta


class ThresholdAnalyzer:
    """Analyze relay flag eligibility against network thresholds."""
    
    # Flag threshold definitions
    FLAG_REQUIREMENTS = {
        'Guard': {
            'wfu': {
                'description': 'Weighted Fractional Uptime',
                'threshold_key': 'guard-wfu',
                'default': 0.98,
                'comparison': 'gte'
            },
            'time_known': {
                'description': 'Time Known to Network',
                'threshold_key': 'guard-tk',
                'default': 691200,  # 8 days in seconds
                'comparison': 'gte',
                'unit': 'seconds'
            },
            'bandwidth_with_exits': {
                'description': 'Bandwidth (including exits)',
                'threshold_key': 'guard-bw-inc-exits',
                'default': 29000000,
                'comparison': 'gte',
                'unit': 'bytes'
            },
            'bandwidth_without_exits': {
                'description': 'Bandwidth (excluding exits)',
                'threshold_key': 'guard-bw-exc-exits',
                'default': 28000000,
                'comparison': 'gte',
                'unit': 'bytes'
            }
        },
        'Stable': {
            'uptime': {
                'description': 'Stable Uptime',
                'threshold_key': 'stable-uptime',
                'default': 1749590,
                'comparison': 'gte',
                'unit': 'seconds'
            },
            'mtbf': {
                'description': 'Mean Time Between Failures',
                'threshold_key': 'stable-mtbf',
                'default': 31256159,
                'comparison': 'gte',
                'unit': 'seconds'
            }
        },
        'Fast': {
            'bandwidth': {
                'description': 'Minimum Bandwidth',
                'threshold_key': 'fast-speed',
                'default': 102000,
                'comparison': 'gte',
                'unit': 'bytes'
            }
        },
        'HSDir': {
            'wfu': {
                'description': 'Weighted Fractional Uptime',
                'threshold_key': 'hsdir-wfu',
                'default': 0.98,
                'comparison': 'gte'
            },
            'time_known': {
                'description': 'Time Known to Network',
                'threshold_key': 'hsdir-tk',
                'default': 852226,
                'comparison': 'gte',
                'unit': 'seconds'
            }
        }
    }
    
    def __init__(self, authority_thresholds: Dict[str, dict] = None):
        """
        Initialize with authority threshold data.
        
        Args:
            authority_thresholds: Dict mapping authority names to their thresholds
        """
        self.authority_thresholds = authority_thresholds or {}
    
    def get_network_thresholds(self) -> dict:
        """
        Get aggregated network thresholds (median across authorities).
        """
        aggregated = {}
        
        # Collect all threshold values per key
        threshold_values = {}
        for auth_name, thresholds in self.authority_thresholds.items():
            for key, value in thresholds.items():
                if key not in threshold_values:
                    threshold_values[key] = []
                threshold_values[key].append(value)
        
        # Calculate median for each threshold
        for key, values in threshold_values.items():
            sorted_values = sorted(values)
            mid = len(sorted_values) // 2
            if len(sorted_values) % 2 == 0:
                aggregated[key] = (sorted_values[mid - 1] + sorted_values[mid]) / 2
            else:
                aggregated[key] = sorted_values[mid]
        
        return aggregated
    
    def analyze_flag_eligibility(self, relay_data: dict, 
                                  flag: str) -> dict:
        """
        Analyze whether a relay meets requirements for a specific flag.
        
        Args:
            relay_data: Dict containing relay metrics
            flag: Flag name to check (e.g., 'Guard', 'Stable')
            
        Returns:
            Dict with eligibility analysis
        """
        if flag not in self.FLAG_REQUIREMENTS:
            return {'error': f'Unknown flag: {flag}'}
        
        requirements = self.FLAG_REQUIREMENTS[flag]
        network_thresholds = self.get_network_thresholds()
        
        analysis = {
            'flag': flag,
            'eligible': True,
            'requirements': [],
            'recommendations': []
        }
        
        for req_name, req_config in requirements.items():
            threshold_key = req_config['threshold_key']
            default_threshold = req_config['default']
            threshold = network_thresholds.get(threshold_key, default_threshold)
            
            # Get relay's value for this requirement
            relay_value = self._get_relay_metric(relay_data, req_name, flag)
            
            requirement_result = {
                'name': req_name,
                'description': req_config['description'],
                'threshold': threshold,
                'relay_value': relay_value,
                'unit': req_config.get('unit', ''),
                'met': False
            }
            
            if relay_value is not None:
                if req_config['comparison'] == 'gte':
                    requirement_result['met'] = relay_value >= threshold
                elif req_config['comparison'] == 'lte':
                    requirement_result['met'] = relay_value <= threshold
                
                if not requirement_result['met']:
                    analysis['eligible'] = False
                    deficit = abs(threshold - relay_value)
                    deficit_pct = (deficit / threshold * 100) if threshold > 0 else 0
                    analysis['recommendations'].append(
                        f"Increase {req_config['description']} from "
                        f"{self._format_value(relay_value, req_config.get('unit'))} to "
                        f"{self._format_value(threshold, req_config.get('unit'))} "
                        f"({deficit_pct:.1f}% below threshold)"
                    )
            else:
                requirement_result['met'] = None
                analysis['recommendations'].append(
                    f"Unable to determine {req_config['description']} - data unavailable"
                )
            
            analysis['requirements'].append(requirement_result)
        
        return analysis
    
    def _get_relay_metric(self, relay_data: dict, metric_name: str, 
                          flag: str) -> Optional[float]:
        """
        Extract relay metric value from relay data.
        
        Maps generic metric names to actual relay data fields.
        """
        metric_mapping = {
            'wfu': ['weighted_fractional_uptime', 'wfu', 
                   ('uptime_percentages', '1_month', lambda x: x / 100)],
            'time_known': ['time_known', 
                          ('first_seen', lambda x: self._calculate_time_known(x))],
            'bandwidth_with_exits': ['observed_bandwidth', 'bandwidth'],
            'bandwidth_without_exits': ['observed_bandwidth', 'bandwidth'],
            'uptime': ['uptime_seconds', 
                      ('last_restarted', lambda x: self._calculate_uptime(x))],
            'mtbf': ['mtbf', 'mean_time_between_failures'],
            'bandwidth': ['observed_bandwidth', 'bandwidth']
        }
        
        possible_keys = metric_mapping.get(metric_name, [metric_name])
        
        for key in possible_keys:
            if isinstance(key, tuple):
                # Complex mapping with nested access or transformation
                if len(key) == 2 and callable(key[1]):
                    field_name, transform = key
                    if field_name in relay_data:
                        return transform(relay_data[field_name])
                elif len(key) == 3:
                    field1, field2, transform = key
                    if field1 in relay_data and isinstance(relay_data[field1], dict):
                        if field2 in relay_data[field1]:
                            return transform(relay_data[field1][field2])
            elif key in relay_data:
                return relay_data[key]
        
        return None
    
    def _calculate_time_known(self, first_seen: str) -> float:
        """Calculate time known from first_seen timestamp."""
        try:
            first_seen_dt = datetime.fromisoformat(first_seen.replace('Z', '+00:00'))
            delta = datetime.now(first_seen_dt.tzinfo) - first_seen_dt
            return delta.total_seconds()
        except Exception:
            return None
    
    def _calculate_uptime(self, last_restarted: str) -> float:
        """Calculate uptime from last_restarted timestamp."""
        try:
            restart_dt = datetime.fromisoformat(last_restarted.replace('Z', '+00:00'))
            delta = datetime.now(restart_dt.tzinfo) - restart_dt
            return delta.total_seconds()
        except Exception:
            return None
    
    def _format_value(self, value: float, unit: str) -> str:
        """Format value with appropriate unit."""
        if unit == 'seconds':
            if value >= 86400:
                return f"{value / 86400:.1f} days"
            elif value >= 3600:
                return f"{value / 3600:.1f} hours"
            else:
                return f"{value:.0f} seconds"
        elif unit == 'bytes':
            if value >= 1000000000:
                return f"{value / 1000000000:.1f} GB/s"
            elif value >= 1000000:
                return f"{value / 1000000:.1f} MB/s"
            elif value >= 1000:
                return f"{value / 1000:.1f} KB/s"
            else:
                return f"{value:.0f} B/s"
        elif value < 1:
            return f"{value * 100:.1f}%"
        else:
            return f"{value:.2f}"
    
    def generate_full_eligibility_report(self, relay_data: dict) -> dict:
        """
        Generate comprehensive flag eligibility report for a relay.
        """
        report = {
            'relay_fingerprint': relay_data.get('fingerprint'),
            'relay_nickname': relay_data.get('nickname'),
            'current_flags': relay_data.get('flags', []),
            'flag_eligibility': {},
            'summary': {
                'eligible_flags': [],
                'ineligible_flags': [],
                'unknown_eligibility': []
            },
            'generated_at': datetime.utcnow().isoformat()
        }
        
        for flag in self.FLAG_REQUIREMENTS:
            eligibility = self.analyze_flag_eligibility(relay_data, flag)
            report['flag_eligibility'][flag] = eligibility
            
            if eligibility.get('eligible') is True:
                report['summary']['eligible_flags'].append(flag)
            elif eligibility.get('eligible') is False:
                report['summary']['ineligible_flags'].append(flag)
            else:
                report['summary']['unknown_eligibility'].append(flag)
        
        return report
```

---

## Worker Integration

The worker fetches all data from CollecTor once per hour and caches it. Per-relay lookups are then done from the cached data during page generation.

```python
# lib/workers.py additions

"""
Consensus troubleshooting worker using CollecTor as the primary data source.
"""

import json
import os
from datetime import datetime
from typing import Optional

from lib.consensus.collector_fetcher import CollectorFetcher

# Global fetcher instance (persists between page generations)
_collector_fetcher: Optional[CollectorFetcher] = None
_last_fetch_time: Optional[datetime] = None
_cache_dir = 'cache/consensus'


def fetch_collector_data() -> dict:
    """
    Worker function to fetch all consensus data from CollecTor.
    
    This single worker replaces multiple individual fetchers because
    CollecTor provides ALL data from a single source:
    - All 9 authority votes
    - All 7 bandwidth files
    - Flag thresholds (extracted from votes)
    
    Called once per hour by the multi-API worker pool.
    """
    global _collector_fetcher, _last_fetch_time
    
    try:
        progress_logger.log("Fetching consensus data from CollecTor...")
        
        _collector_fetcher = CollectorFetcher(cache_dir=_cache_dir)
        data = _collector_fetcher.fetch_all_data(timeout=120)  # 2 min timeout for all files
        
        # Log results
        vote_count = len([v for v in data['votes'].values() if 'error' not in v])
        bw_count = len([b for b in data['bandwidth_files'].values() if 'error' not in b])
        relay_count = len(data['relay_index'])
        
        progress_logger.log(
            f"CollecTor fetch complete: {vote_count}/9 votes, "
            f"{bw_count}/7 bandwidth files, {relay_count} relays indexed"
        )
        
        # Save to cache for graceful degradation
        _save_collector_cache(data)
        _mark_ready('collector_data')
        _last_fetch_time = datetime.utcnow()
        
        return data
        
    except Exception as e:
        error_msg = f"Failed to fetch CollecTor data: {str(e)}"
        progress_logger.log(error_msg)
        _mark_stale('collector_data', error_msg)
        
        # Try to load from cache
        cached = _load_collector_cache()
        if cached:
            progress_logger.log("Using cached CollecTor data")
            _collector_fetcher = CollectorFetcher(cache_dir=_cache_dir)
            _collector_fetcher.votes = cached.get('votes', {})
            _collector_fetcher.bandwidth_files = cached.get('bandwidth_files', {})
            _collector_fetcher.relay_index = cached.get('relay_index', {})
            _collector_fetcher.flag_thresholds = cached.get('flag_thresholds', {})
            return cached
        
        return {'error': error_msg}


def get_relay_diagnostics(fingerprint: str) -> dict:
    """
    Get complete diagnostics for a relay (Phases 1-4).
    Called during relay-info.html generation.
    
    Args:
        fingerprint: Relay fingerprint (hex, 40 chars)
        
    Returns:
        Dict with all diagnostic data for the relay page
    """
    global _collector_fetcher
    
    # Ensure fetcher is initialized
    if _collector_fetcher is None:
        cached = _load_collector_cache()
        if cached:
            _collector_fetcher = CollectorFetcher(cache_dir=_cache_dir)
            _collector_fetcher.votes = cached.get('votes', {})
            _collector_fetcher.bandwidth_files = cached.get('bandwidth_files', {})
            _collector_fetcher.relay_index = cached.get('relay_index', {})
            _collector_fetcher.flag_thresholds = cached.get('flag_thresholds', {})
        else:
            return {'error': 'CollecTor data not available'}
    
    return _collector_fetcher.get_relay_diagnostics(fingerprint)


def get_network_flag_thresholds() -> dict:
    """
    Get current network flag thresholds (median across authorities).
    Useful for the Directory Authorities page and troubleshooting wizard.
    """
    global _collector_fetcher
    
    if _collector_fetcher is None:
        cached = _load_collector_cache()
        if cached:
            return {
                'per_authority': cached.get('flag_thresholds', {}),
                'median': _calculate_median_thresholds(cached.get('flag_thresholds', {}))
            }
        return {'error': 'Threshold data not available'}
    
    return {
        'per_authority': _collector_fetcher.flag_thresholds,
        'median': _collector_fetcher._get_median_thresholds()
    }


def _save_collector_cache(data: dict) -> None:
    """Save CollecTor data to cache file."""
    os.makedirs(_cache_dir, exist_ok=True)
    cache_file = os.path.join(_cache_dir, 'collector_data.json')
    
    # Don't cache full relay data (too large) - just index and metadata
    cache_data = {
        'fetched_at': data.get('fetched_at'),
        'votes': {
            name: {
                'authority': v.get('authority'),
                'published': v.get('published'),
                'valid_after': v.get('valid_after'),
                'flag_thresholds': v.get('flag_thresholds'),
                'relay_count': v.get('relay_count'),
                # Store relays dict for lookups
                'relays': v.get('relays', {})
            } for name, v in data.get('votes', {}).items()
        },
        'bandwidth_files': {
            name: {
                'authority': b.get('authority'),
                'timestamp': b.get('timestamp'),
                'relay_count': b.get('relay_count'),
                'relays': b.get('relays', {})
            } for name, b in data.get('bandwidth_files', {}).items()
        },
        'flag_thresholds': data.get('flag_thresholds', {}),
        'relay_index': data.get('relay_index', {})
    }
    
    with open(cache_file, 'w') as f:
        json.dump(cache_data, f)


def _load_collector_cache() -> Optional[dict]:
    """Load CollecTor data from cache file."""
    cache_file = os.path.join(_cache_dir, 'collector_data.json')
    if os.path.exists(cache_file):
        try:
            with open(cache_file) as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _calculate_median_thresholds(per_authority: dict) -> dict:
    """Calculate median thresholds from per-authority data."""
    if not per_authority:
        return {}
    
    all_keys = set()
    for thresholds in per_authority.values():
        all_keys.update(thresholds.keys())
    
    median_thresholds = {}
    for key in all_keys:
        values = [t[key] for t in per_authority.values() if key in t]
        if values:
            values.sort()
            mid = len(values) // 2
            median_thresholds[key] = values[mid] if len(values) % 2 else (values[mid-1] + values[mid]) / 2
    
    return median_thresholds
```

---

## Template Integration

### relay-info.html - Complete Consensus Diagnostics Section

All 4 phases are rendered as a unified "Consensus Diagnostics" section on the relay detail page.

```html
{# ═══════════════════════════════════════════════════════════════════════════
   CONSENSUS DIAGNOSTICS SECTION
   Add this after existing relay information sections in relay-info.html
   
   Data source: relay.diagnostics (from get_relay_diagnostics() in workers.py)
   ═══════════════════════════════════════════════════════════════════════════ #}

{% if relay.diagnostics and not relay.diagnostics.error %}
{% set diag = relay.diagnostics %}

<div id="consensus-diagnostics" class="section">
    <h2>
        <a href="#consensus-diagnostics" class="anchor-link">🔍 Consensus Diagnostics</a>
    </h2>
    
    <div class="diagnostics-summary">
        {% if diag.in_consensus %}
            <span class="status-good">✅ IN CONSENSUS</span>
        {% else %}
            <span class="status-bad">❌ NOT IN CONSENSUS</span>
        {% endif %}
        <small>(Data from CollecTor, analyzed {{ diag.analyzed_at|timeago }})</small>
    </div>

    {# ════════════════════════════════════════════════════════════════════════
       PHASE 1: Authority Votes
       ════════════════════════════════════════════════════════════════════════ #}
    
    <div id="authority-votes" class="diagnostic-phase">
        <h3>
            <a href="#authority-votes" class="anchor-link">🗳️ Phase 1: Directory Authority Votes</a>
        </h3>
        
        {% set votes = diag.phases.authority_votes %}
        <p class="phase-summary">
            Voted by <strong>{{ votes.voted_count }}/{{ votes.total_authorities }}</strong> authorities
        </p>
        
        <table class="table table-condensed">
            <thead>
                <tr>
                    <th>Authority</th>
                    <th>Voted</th>
                    <th>Flags Assigned</th>
                    <th>Bandwidth</th>
                </tr>
            </thead>
            <tbody>
            {% for auth_name, status in votes.per_authority.items()|sort %}
                <tr class="{% if not status.voted %}row-warning{% endif %}">
                    <td>{{ auth_name }}</td>
                    <td>
                        {% if status.voted %}✅{% else %}❌{% endif %}
                    </td>
                    <td>
                        {% if status.voted %}
                            {{ status.flags|join(' ') or 'No flags' }}
                        {% else %}
                            <span class="text-muted">Not in vote</span>
                        {% endif %}
                    </td>
                    <td>
                        {% if status.bandwidth %}
                            {{ status.bandwidth|format_bandwidth }}
                            {% if status.measured %}<span class="badge">Measured</span>{% endif %}
                        {% else %}
                            <span class="text-muted">N/A</span>
                        {% endif %}
                    </td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
        
        {% if votes.issues %}
        <div class="issues-box">
            <strong>⚠️ Issues Detected:</strong>
            <ul>
            {% for issue in votes.issues %}
                <li>{{ issue }}</li>
            {% endfor %}
            </ul>
        </div>
        {% endif %}
    </div>

    {# ════════════════════════════════════════════════════════════════════════
       PHASE 2: Flag Eligibility
       ════════════════════════════════════════════════════════════════════════ #}
    
    <div id="flag-eligibility" class="diagnostic-phase">
        <h3>
            <a href="#flag-eligibility" class="anchor-link">🎯 Phase 2: Flag Eligibility Analysis</a>
        </h3>
        
        {% set flags = diag.phases.flag_eligibility %}
        <p class="phase-summary">
            Current flags: <strong>{{ flags.current_flags|join(', ') or 'None' }}</strong>
        </p>
        
        {% for flag_name, analysis in flags.analysis.items() %}
        <div class="flag-card">
            <h4>
                {{ flag_name }}
                {% if flag_name in flags.current_flags %}
                    <span class="badge badge-success">✅ Has Flag</span>
                {% elif analysis.eligible %}
                    <span class="badge badge-warning">🟡 Eligible</span>
                {% else %}
                    <span class="badge badge-danger">❌ Not Eligible</span>
                {% endif %}
            </h4>
            
            {% if analysis.requirements %}
            <table class="table table-sm">
                <thead>
                    <tr>
                        <th>Requirement</th>
                        <th>Your Value</th>
                        <th>Threshold</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                {% for req in analysis.requirements %}
                    <tr class="{% if not req.met %}row-danger{% endif %}">
                        <td>{{ req.description }}</td>
                        <td>{{ req.relay_value|format_metric(req.unit) }}</td>
                        <td>{{ req.threshold|format_metric(req.unit) }}</td>
                        <td>
                            {% if req.met %}✅ Met{% elif req.met is none %}❓{% else %}❌ Below{% endif %}
                        </td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
            {% endif %}
            
            {% if analysis.missing %}
            <p class="recommendation">
                💡 To gain {{ flag_name }}: {{ analysis.missing|join(', ') }}
            </p>
            {% endif %}
        </div>
        {% endfor %}
    </div>

    {# ════════════════════════════════════════════════════════════════════════
       PHASE 3: Reachability Analysis
       ════════════════════════════════════════════════════════════════════════ #}
    
    <div id="reachability" class="diagnostic-phase">
        <h3>
            <a href="#reachability" class="anchor-link">🌐 Phase 3: Authority Reachability</a>
        </h3>
        
        {% set reach = diag.phases.reachability %}
        
        <div class="row">
            <div class="col-md-6">
                <h4>IPv4 Reachability ({{ relay.or_addresses[0] if relay.or_addresses else 'N/A' }})</h4>
                <table class="table table-sm">
                    <thead>
                        <tr><th>Authority</th><th>Status</th><th>Evidence</th></tr>
                    </thead>
                    <tbody>
                    {% for auth_name, status in reach.ipv4.items()|sort %}
                        <tr class="{% if not status.reachable %}row-warning{% endif %}">
                            <td>{{ auth_name }}</td>
                            <td>{% if status.reachable %}✅{% else %}❌{% endif %}</td>
                            <td><small>{{ status.evidence }}</small></td>
                        </tr>
                    {% endfor %}
                    </tbody>
                </table>
            </div>
            
            <div class="col-md-6">
                <h4>IPv6 Reachability</h4>
                <table class="table table-sm">
                    <thead>
                        <tr><th>Authority</th><th>Status</th><th>Evidence</th></tr>
                    </thead>
                    <tbody>
                    {% for auth_name, status in reach.ipv6.items()|sort %}
                        <tr class="{% if status.reachable == false %}row-warning{% endif %}">
                            <td>{{ auth_name }}</td>
                            <td>
                                {% if status.reachable is none %}⚪{% elif status.reachable %}✅{% else %}❌{% endif %}
                            </td>
                            <td><small>{{ status.evidence }}</small></td>
                        </tr>
                    {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        
        {% if reach.issues %}
        <div class="issues-box">
            <strong>⚠️ Reachability Issues:</strong>
            <ul>
            {% for issue in reach.issues %}
                <li>{{ issue }}</li>
            {% endfor %}
            </ul>
        </div>
        {% endif %}
    </div>

    {# ════════════════════════════════════════════════════════════════════════
       PHASE 4: Bandwidth Measurements
       ════════════════════════════════════════════════════════════════════════ #}
    
    <div id="bandwidth-measurements" class="diagnostic-phase">
        <h3>
            <a href="#bandwidth-measurements" class="anchor-link">📊 Phase 4: Bandwidth Authority Measurements</a>
        </h3>
        
        {% set bw = diag.phases.bandwidth %}
        <p class="phase-summary">
            Measured by <strong>{{ bw.measured_by|length }}/7</strong> bandwidth authorities
            {% if bw.measurement_variance %}
                (variance: {{ bw.measurement_variance|round(1) }}%)
            {% endif %}
        </p>
        
        <table class="table table-condensed">
            <thead>
                <tr>
                    <th>BW Authority</th>
                    <th>Measured</th>
                    <th>Value</th>
                    <th>Deviation</th>
                </tr>
            </thead>
            <tbody>
            {% for auth_name, status in bw.per_authority.items()|sort %}
                <tr class="{% if not status.measured %}row-muted{% endif %}">
                    <td>{{ auth_name }}</td>
                    <td>{% if status.measured %}✅{% else %}❌{% endif %}</td>
                    <td>
                        {% if status.value %}
                            {{ status.value|format_bandwidth }}
                        {% else %}
                            <span class="text-muted">N/A</span>
                        {% endif %}
                    </td>
                    <td>
                        {% if status.value and bw.average_measurement %}
                            {% set deviation = ((status.value - bw.average_measurement) / bw.average_measurement * 100) %}
                            <span class="{% if deviation > 10 or deviation < -10 %}text-warning{% endif %}">
                                {{ '%+.1f'|format(deviation) }}%
                            </span>
                        {% else %}
                            -
                        {% endif %}
                    </td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
        
        {% if bw.not_measured_by %}
        <div class="info-box">
            <strong>ℹ️ Not measured by:</strong> {{ bw.not_measured_by|join(', ') }}
            <br><small>Note: dizum and dannenberg do not run bandwidth scanners.</small>
        </div>
        {% endif %}
        
        {% if bw.measured_by|length < 3 %}
        <div class="warning-box">
            <strong>⚠️ Unmeasured Status</strong>
            <p>This relay is measured by fewer than 3 bandwidth authorities, which may result in "Unmeasured" status in consensus.</p>
            <ul>
                <li>New relays may take 1-2 weeks to be fully measured</li>
                <li>Check reachability to bandwidth authorities above</li>
                <li>Ensure relay has stable connectivity</li>
            </ul>
        </div>
        {% endif %}
    </div>

</div>
{% endif %}

{# Show error message if diagnostics failed #}
{% if relay.diagnostics and relay.diagnostics.error %}
<div id="consensus-diagnostics" class="section">
    <h2>🔍 Consensus Diagnostics</h2>
    <div class="error-box">
        <strong>⚠️ Diagnostics Unavailable</strong>
        <p>{{ relay.diagnostics.error }}</p>
        <p>This may indicate the relay is not currently in consensus, or data is being refreshed.</p>
    </div>
</div>
{% endif %}
```

### CSS Additions for Diagnostics

```css
/* Add to allium.css */

/* Diagnostics Section */
#consensus-diagnostics {
    margin-top: 2rem;
    border-top: 2px solid #e0e0e0;
    padding-top: 1rem;
}

.diagnostics-summary {
    font-size: 1.2rem;
    margin-bottom: 1rem;
    padding: 0.5rem 1rem;
    background: #f8f9fa;
    border-radius: 4px;
}

.diagnostic-phase {
    margin-top: 1.5rem;
    padding: 1rem;
    border: 1px solid #dee2e6;
    border-radius: 4px;
}

.diagnostic-phase h3 {
    margin-top: 0;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #eee;
}

.phase-summary {
    margin-bottom: 1rem;
    color: #555;
}

/* Status indicators */
.status-good { color: #28a745; font-weight: bold; }
.status-bad { color: #dc3545; font-weight: bold; }

/* Issue boxes */
.issues-box, .warning-box {
    margin-top: 1rem;
    padding: 0.75rem 1rem;
    background: #fff3cd;
    border: 1px solid #ffc107;
    border-radius: 4px;
}

.info-box {
    margin-top: 1rem;
    padding: 0.75rem 1rem;
    background: #e7f3ff;
    border: 1px solid #007bff;
    border-radius: 4px;
}

.error-box {
    padding: 1rem;
    background: #f8d7da;
    border: 1px solid #dc3545;
    border-radius: 4px;
}

/* Table row states */
.row-warning { background: #fff3cd; }
.row-danger { background: #f8d7da; }
.row-muted { color: #6c757d; }

/* Flag cards */
.flag-card {
    margin-bottom: 1rem;
    padding: 0.75rem;
    border: 1px solid #ddd;
    border-radius: 4px;
}

.flag-card h4 {
    margin: 0 0 0.5rem 0;
}

/* Badges */
.badge { 
    padding: 0.25rem 0.5rem; 
    border-radius: 3px; 
    font-size: 0.8rem;
}
.badge-success { background: #28a745; color: white; }
.badge-warning { background: #ffc107; color: black; }
.badge-danger { background: #dc3545; color: white; }
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_vote_parser.py

import pytest
from lib.consensus.vote_parser import VoteParser

class TestVoteParser:
    
    def test_parse_flag_thresholds(self):
        parser = VoteParser()
        line = "flag-thresholds stable-uptime=1749590 stable-mtbf=31256159 fast-speed=1048000"
        result = parser._parse_flag_thresholds(line)
        
        assert result['stable-uptime'] == 1749590
        assert result['stable-mtbf'] == 31256159
        assert result['fast-speed'] == 1048000
    
    def test_decode_fingerprint(self):
        parser = VoteParser()
        # Base64 encoded fingerprint example
        b64 = "lpXfwYX/64YTKb8flATdRjcgDjE"
        result = parser._decode_fingerprint(b64)
        assert len(result) == 40  # Hex fingerprint length
    
    def test_get_relay_vote_status_missing_relay(self):
        parser = VoteParser()
        parser.votes = {
            'moria1': {'relays': {}, 'error': None},
            'tor26': {'relays': {}, 'error': None}
        }
        
        result = parser.get_relay_vote_status('ABCD1234')
        
        assert result['moria1']['voted'] is False
        assert result['tor26']['voted'] is False


# tests/test_threshold_analyzer.py

import pytest
from lib.consensus.threshold_analyzer import ThresholdAnalyzer

class TestThresholdAnalyzer:
    
    def test_guard_flag_eligibility_met(self):
        thresholds = {
            'moria1': {
                'guard-wfu': 0.98,
                'guard-tk': 691200,
                'guard-bw-inc-exits': 29000000
            }
        }
        analyzer = ThresholdAnalyzer(thresholds)
        
        relay_data = {
            'weighted_fractional_uptime': 0.99,
            'time_known': 1000000,
            'observed_bandwidth': 50000000
        }
        
        result = analyzer.analyze_flag_eligibility(relay_data, 'Guard')
        assert result['eligible'] is True
    
    def test_guard_flag_eligibility_not_met(self):
        thresholds = {
            'moria1': {
                'guard-wfu': 0.98,
                'guard-tk': 691200,
                'guard-bw-inc-exits': 29000000
            }
        }
        analyzer = ThresholdAnalyzer(thresholds)
        
        relay_data = {
            'weighted_fractional_uptime': 0.95,  # Below threshold
            'time_known': 1000000,
            'observed_bandwidth': 50000000
        }
        
        result = analyzer.analyze_flag_eligibility(relay_data, 'Guard')
        assert result['eligible'] is False
        assert len(result['recommendations']) > 0
```

---

## Performance Considerations

### Caching Strategy

1. **Authority Votes**: Cache for 1 hour (consensus period)
2. **Flag Thresholds**: Cache for 1 hour (extracted from votes)
3. **Per-Relay Analysis**: Compute on-demand, cache for 15 minutes

### Memory Optimization

- Don't store full relay lists from votes (only fingerprint index)
- Lazy-load relay-specific data when requested
- Use compressed JSON for large cached datasets

### Network Optimization

- Fetch votes in parallel from all authorities
- Implement timeouts and retries for unreliable authorities
- Fall back to cached data if fetch fails

---

## Deployment Checklist

### Phase 1: Core Infrastructure
- [ ] Create `lib/consensus/` directory structure
- [ ] Implement `collector.py` - CollecTor configuration
- [ ] Implement `authorities.py` - Authority configuration and fingerprint mapping
- [ ] Implement `collector_fetcher.py` - Main data fetcher from CollecTor

### Phase 2: Worker Integration  
- [ ] Add `fetch_collector_data()` to `lib/workers.py`
- [ ] Add `get_relay_diagnostics()` lookup function
- [ ] Implement caching strategy for CollecTor data
- [ ] Test worker with multi-API coordinator

### Phase 3: Template Updates
- [ ] Update `relay-info.html` with Consensus Diagnostics section
- [ ] Add CSS styles for diagnostic components
- [ ] Add Jinja2 filters for formatting (`format_bandwidth`, `format_metric`, `timeago`)
- [ ] Test rendering with sample relay data

### Phase 4: Testing
- [ ] Unit tests for `CollectorFetcher` parsing
- [ ] Unit tests for per-relay analysis functions
- [ ] Integration test with real CollecTor data
- [ ] Performance testing (7000+ relays)

### Phase 5: Documentation
- [ ] Update README with new features
- [ ] Document CollecTor data dependencies
- [ ] Add troubleshooting FAQ for operators

---

## Performance Considerations

### Data Size Estimates
| Data | Estimated Size | Parse Time |
|------|----------------|------------|
| 9 Authority Votes | ~50 MB total | ~5-10 sec |
| 7 Bandwidth Files | ~50 MB total | ~3-5 sec |
| Relay Index (7000 relays) | ~10 MB in memory | Instant |
| Per-relay lookup | <1 KB | <1 ms |

### Caching Strategy
1. **CollecTor data**: Cache for 1 hour (matches consensus cycle)
2. **Relay index**: Keep in memory for fast lookups during page generation
3. **Per-relay diagnostics**: Compute on-demand (already indexed)

### Graceful Degradation
- If CollecTor fetch fails, use cached data (may be up to 3 hours old)
- Show "Data may be stale" warning when using cached data
- Individual phase sections can be hidden if data unavailable

---

**Document Status**: Technical specification complete  
**Primary Data Source**: Tor Project CollecTor (https://collector.torproject.org)  
**Target Location**: Per-relay detail pages (`relay-info.html`)  
**Next Steps**: Implementation review and core infrastructure development
