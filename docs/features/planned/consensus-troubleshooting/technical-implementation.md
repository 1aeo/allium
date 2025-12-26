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

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Allium Consensus Troubleshooting                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │
│  │  Authority  │  │  Bandwidth  │  │  Consensus  │                │
│  │   Votes     │  │    Files    │  │   Health    │                │
│  │   Parser    │  │   Parser    │  │   Scraper   │                │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                │
│         │                │                │                        │
│         └────────────────┼────────────────┘                        │
│                          │                                          │
│                          ▼                                          │
│               ┌─────────────────────┐                              │
│               │   Consensus Data    │                              │
│               │      Manager        │                              │
│               │  (lib/consensus/)   │                              │
│               └──────────┬──────────┘                              │
│                          │                                          │
│         ┌────────────────┼────────────────┐                        │
│         ▼                ▼                ▼                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │
│  │ relay-info  │  │ authorities │  │troubleshoot │                │
│  │   .html     │  │   .html     │  │    .html    │                │
│  │ (enhanced)  │  │ (enhanced)  │  │   (new)     │                │
│  └─────────────┘  └─────────────┘  └─────────────┘                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
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

### CollecTor-Based Vote Fetcher (Recommended)

```python
# lib/consensus/collector_fetcher.py

"""
Fetch and parse votes from CollecTor (centralized Tor Project archive).
This is the recommended approach - single source, no authority load.
"""

import re
import urllib.request
from typing import Dict, List, Optional
from datetime import datetime
import logging

from .collector import COLLECTOR_CONFIG, get_latest_votes_url
from .authorities import AUTHORITY_FINGERPRINTS

logger = logging.getLogger(__name__)


class CollectorVoteFetcher:
    """Fetch authority votes from CollecTor."""
    
    def __init__(self, cache_manager=None):
        self.cache_manager = cache_manager
        self.base_url = f"{COLLECTOR_CONFIG['base_url']}{COLLECTOR_CONFIG['recent_path']}"
    
    def fetch_latest_votes(self, timeout: int = 60) -> Dict[str, dict]:
        """
        Fetch all authority votes for the most recent consensus period.
        
        Returns:
            Dict mapping authority names to parsed vote data
        """
        # Step 1: Get directory listing of vote files
        votes_url = f"{self.base_url}/votes/"
        index_html = self._fetch_url(votes_url, timeout)
        
        # Step 2: Parse filenames to find latest votes
        latest_votes = self._find_latest_vote_files(index_html)
        logger.info(f"Found {len(latest_votes)} vote files for latest consensus")
        
        # Step 3: Fetch and parse each vote
        votes = {}
        for filename, auth_fingerprint in latest_votes.items():
            auth_name = AUTHORITY_FINGERPRINTS.get(auth_fingerprint, auth_fingerprint[:8])
            try:
                vote_url = f"{votes_url}{filename}"
                vote_text = self._fetch_url(vote_url, timeout)
                votes[auth_name] = self._parse_vote(vote_text, auth_name)
                logger.info(f"Parsed vote from {auth_name}")
            except Exception as e:
                logger.warning(f"Failed to fetch vote from {auth_name}: {e}")
                votes[auth_name] = {'error': str(e), 'relays': {}}
        
        return votes
    
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
    
    def _fetch_url(self, url: str, timeout: int) -> str:
        """Fetch content from URL."""
        req = urllib.request.Request(url, headers={'User-Agent': 'Allium/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8', errors='replace')
    
    def _parse_vote(self, vote_text: str, authority_name: str) -> dict:
        """Parse vote document - delegates to VoteParser."""
        from .vote_parser import VoteParser
        parser = VoteParser()
        return parser._parse_vote(vote_text, authority_name)
```

### Core Vote Parser

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

```python
# lib/workers.py additions

"""
Add consensus troubleshooting workers to existing multi-API architecture.
"""

import threading
from lib.consensus.vote_parser import VoteParser
from lib.consensus.threshold_analyzer import ThresholdAnalyzer
from lib.consensus.authorities import DIRECTORY_AUTHORITIES

# Global parser instances
_vote_parser = None
_threshold_analyzer = None


def fetch_authority_votes():
    """
    Worker function to fetch votes from all directory authorities.
    Runs as part of the multi-API worker pool.
    """
    global _vote_parser
    
    try:
        progress_logger.log("Fetching directory authority votes...")
        
        _vote_parser = VoteParser()
        votes = _vote_parser.fetch_all_votes(timeout=30)
        
        # Cache the parsed votes
        _save_cache('authority_votes', {
            'votes': {name: _serialize_vote(vote) for name, vote in votes.items()},
            'fetched_at': datetime.utcnow().isoformat()
        })
        _mark_ready('authority_votes')
        
        successful = sum(1 for v in votes.values() if 'error' not in v)
        progress_logger.log(f"Fetched votes from {successful}/{len(DIRECTORY_AUTHORITIES)} authorities")
        
        return votes
        
    except Exception as e:
        error_msg = f"Failed to fetch authority votes: {str(e)}"
        progress_logger.log(error_msg)
        _mark_stale('authority_votes', error_msg)
        return _load_cache('authority_votes')


def fetch_flag_thresholds():
    """
    Worker function to fetch and parse flag thresholds.
    Uses the cached vote data to extract thresholds.
    """
    global _threshold_analyzer
    
    try:
        progress_logger.log("Extracting flag thresholds from votes...")
        
        # Load cached votes
        votes_cache = _load_cache('authority_votes')
        if not votes_cache:
            raise ValueError("Authority votes not available")
        
        # Extract thresholds from each authority's vote
        authority_thresholds = {}
        for auth_name, vote_data in votes_cache.get('votes', {}).items():
            if 'flag_thresholds' in vote_data:
                authority_thresholds[auth_name] = vote_data['flag_thresholds']
        
        _threshold_analyzer = ThresholdAnalyzer(authority_thresholds)
        network_thresholds = _threshold_analyzer.get_network_thresholds()
        
        _save_cache('flag_thresholds', {
            'per_authority': authority_thresholds,
            'network_median': network_thresholds,
            'fetched_at': datetime.utcnow().isoformat()
        })
        _mark_ready('flag_thresholds')
        
        progress_logger.log(f"Extracted thresholds from {len(authority_thresholds)} authorities")
        
        return network_thresholds
        
    except Exception as e:
        error_msg = f"Failed to extract flag thresholds: {str(e)}"
        progress_logger.log(error_msg)
        _mark_stale('flag_thresholds', error_msg)
        return _load_cache('flag_thresholds')


def _serialize_vote(vote_data: dict) -> dict:
    """Serialize vote data for caching (without full relay list)."""
    return {
        'authority': vote_data.get('authority'),
        'published': vote_data.get('published'),
        'valid_after': vote_data.get('valid_after'),
        'flag_thresholds': vote_data.get('flag_thresholds'),
        'known_flags': vote_data.get('known_flags'),
        'relay_count': vote_data.get('relay_count'),
        # Don't serialize full relay list - too large
        # Keep fingerprint index for lookups
        'relay_fingerprints': list(vote_data.get('relays', {}).keys())
    }


def get_relay_consensus_analysis(fingerprint: str) -> dict:
    """
    Get consensus analysis for a specific relay.
    Called from template rendering.
    """
    global _vote_parser
    
    if _vote_parser is None:
        # Try to initialize from cache
        votes_cache = _load_cache('authority_votes')
        if votes_cache:
            _vote_parser = VoteParser()
            # Would need to re-fetch or use cached fingerprint lists
    
    if _vote_parser:
        return _vote_parser.analyze_relay_consensus_status(fingerprint)
    
    return {'error': 'Vote data not available'}


def get_relay_flag_eligibility(relay_data: dict) -> dict:
    """
    Get flag eligibility analysis for a relay.
    Called from template rendering.
    """
    global _threshold_analyzer
    
    if _threshold_analyzer is None:
        thresholds_cache = _load_cache('flag_thresholds')
        if thresholds_cache:
            _threshold_analyzer = ThresholdAnalyzer(
                thresholds_cache.get('per_authority', {})
            )
    
    if _threshold_analyzer:
        return _threshold_analyzer.generate_full_eligibility_report(relay_data)
    
    return {'error': 'Threshold data not available'}
```

---

## Template Integration

### relay-info.html Additions

```html
{# Add after existing relay information sections #}

{% if relay.consensus_analysis %}
<div id="consensus-votes" class="section">
    <h3>
        <a href="#consensus-votes" class="anchor-link">🗳️ Directory Authority Votes</a>
    </h3>
    
    <div class="consensus-summary">
        {% set analysis = relay.consensus_analysis %}
        {% if analysis.in_consensus %}
            <span class="status-good">✅ In Consensus</span>
            ({{ analysis.voted_count }}/{{ analysis.total_authorities }} authorities)
        {% else %}
            <span class="status-bad">❌ Not in Consensus</span>
            ({{ analysis.voted_count }}/{{ analysis.total_authorities }} authorities)
        {% endif %}
    </div>
    
    <table class="table table-condensed authority-votes-table">
        <thead>
            <tr>
                <th>Authority</th>
                <th>Voted</th>
                <th>Flags Assigned</th>
                <th>Bandwidth</th>
                <th>Issue</th>
            </tr>
        </thead>
        <tbody>
        {% for auth_name, status in analysis.per_authority_status.items() %}
            <tr>
                <td>{{ auth_name }}</td>
                <td>
                    {% if status.voted %}
                        <span class="status-good">✅</span>
                    {% else %}
                        <span class="status-bad">❌</span>
                    {% endif %}
                </td>
                <td>{{ status.flags|join(' ') if status.flags else 'N/A' }}</td>
                <td>{{ status.bandwidth if status.bandwidth else 'N/A' }}</td>
                <td>
                    {% if not status.voted %}
                        <span class="issue-warning">⚠️ {{ status.error }}</span>
                    {% endif %}
                </td>
            </tr>
        {% endfor %}
        </tbody>
    </table>
    
    {% if analysis.recommendations %}
    <div class="recommendations">
        <h4>💡 Troubleshooting Recommendations</h4>
        <ul>
        {% for rec in analysis.recommendations %}
            <li>{{ rec }}</li>
        {% endfor %}
        </ul>
    </div>
    {% endif %}
</div>
{% endif %}

{% if relay.flag_eligibility %}
<div id="flag-eligibility" class="section">
    <h3>
        <a href="#flag-eligibility" class="anchor-link">🎯 Flag Eligibility Analysis</a>
    </h3>
    
    {% set eligibility = relay.flag_eligibility %}
    
    <div class="current-flags">
        <strong>Current Flags:</strong> {{ eligibility.current_flags|join(', ') }}
    </div>
    
    {% for flag, analysis in eligibility.flag_eligibility.items() %}
    <div class="flag-analysis">
        <h4>
            {{ flag }}
            {% if flag in eligibility.current_flags %}
                <span class="has-flag">✅ Has Flag</span>
            {% elif analysis.eligible %}
                <span class="eligible">🟡 Eligible</span>
            {% else %}
                <span class="not-eligible">❌ Not Eligible</span>
            {% endif %}
        </h4>
        
        <table class="table table-condensed requirements-table">
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
                <tr class="{% if req.met %}req-met{% else %}req-not-met{% endif %}">
                    <td>{{ req.description }}</td>
                    <td>{{ req.relay_value|format_threshold_value(req.unit) }}</td>
                    <td>{{ req.threshold|format_threshold_value(req.unit) }}</td>
                    <td>
                        {% if req.met %}
                            ✅ Met
                        {% elif req.met is none %}
                            ❓ Unknown
                        {% else %}
                            ❌ Below
                        {% endif %}
                    </td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
        
        {% if analysis.recommendations %}
        <div class="flag-recommendations">
            <small>
            {% for rec in analysis.recommendations %}
                • {{ rec }}<br>
            {% endfor %}
            </small>
        </div>
        {% endif %}
    </div>
    {% endfor %}
</div>
{% endif %}
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

- [ ] Create `lib/consensus/` directory structure
- [ ] Implement `authorities.py` with endpoint configuration
- [ ] Implement `vote_parser.py` with parsing logic
- [ ] Implement `threshold_analyzer.py` with eligibility analysis
- [ ] Add worker functions to `lib/workers.py`
- [ ] Update `relay-info.html` template
- [ ] Update `misc-authorities.html` template
- [ ] Create `misc-troubleshooter.html` template
- [ ] Add unit tests
- [ ] Add integration tests
- [ ] Update documentation
- [ ] Performance testing with production data

---

**Document Status**: Technical specification complete  
**Next Steps**: Implementation review and Phase 1 kickoff
