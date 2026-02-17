"""
File: collector_fetcher.py

Fetch and index CollecTor data for per-relay consensus evaluation.
Fetched ONCE per hour, indexed by fingerprint for O(1) lookup.

Data sources:
- CollecTor votes: https://collector.torproject.org/recent/relay-descriptors/votes/
- CollecTor bandwidth files: https://collector.torproject.org/recent/relay-descriptors/bandwidths/
"""

import re
import base64
import urllib.request
import urllib.error
import socket
import concurrent.futures
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging
import time

logger = logging.getLogger(__name__)

# ============================================================================
# FALLBACK AUTHORITY DATA - Only used when Onionoo data is unavailable
# ============================================================================

# V3 identity key fingerprints (signing keys) used in CollecTor vote filenames.
# NOTE: These are DIFFERENT from Onionoo relay fingerprints.
# Only includes the 9 VOTING authorities (Serge has Authority flag but doesn't vote).
_FALLBACK_SIGNING_KEY_TO_NAME = {
    '0232AF901C31A04EE9848595AF9BB7620D4C5B2E': 'dannenberg',
    '23D15D965BC35114467363C165C4F724B64B4F66': 'longclaw',
    '27102BC123E7AF1D4741AE047E160C91ADC76B21': 'bastet',
    '2F3DF9CA0E5D36F2685A2DA67184EB8DCB8CBA8C': 'tor26',
    '49015F787433103580E3B66A1707A00E60F2D15B': 'maatuska',
    '70849B868D606BAECFB6128C5E3D782029AA394F': 'faravahar',
    'E8A9C45EDE6D711294FADF8E7951F4DE6CA56B58': 'dizum',
    'ED03BB616EB2F60BEC80151114BB25CEF515B226': 'gabelmoo',
    'F533C81CEF0BC0267857C99B2F471ADF249FA232': 'moria1',
}

# All 10 directory authorities (includes Serge who has Authority flag but doesn't vote)
# Used as fallback when Onionoo is unavailable
# NOTE: Sorted case-insensitively for consistent display
_FALLBACK_ALL_AUTHORITY_NAMES = sorted([
    'bastet', 'dannenberg', 'dizum', 'faravahar', 'gabelmoo',
    'longclaw', 'maatuska', 'moria1', 'Serge', 'tor26'
], key=str.lower)
_FALLBACK_AUTHORITY_COUNT = len(_FALLBACK_ALL_AUTHORITY_NAMES)  # 10

# Only voting authorities (9) - for consensus-related calculations
_FALLBACK_VOTING_AUTHORITY_NAMES = sorted(_FALLBACK_SIGNING_KEY_TO_NAME.values())
_FALLBACK_VOTING_AUTHORITY_COUNT = len(_FALLBACK_SIGNING_KEY_TO_NAME)  # 9

# Authority country codes (based on known hosting locations)
AUTHORITY_COUNTRIES = {
    'dannenberg': 'DE',    # Germany
    'longclaw': 'US',      # USA
    'bastet': 'US',        # USA
    'tor26': 'AT',         # Austria
    'maatuska': 'SE',      # Sweden
    'faravahar': 'US',     # USA
    'dizum': 'NL',         # Netherlands
    'gabelmoo': 'DE',      # Germany
    'moria1': 'US',        # USA
    'Serge': 'US',         # USA (non-voting authority)
}


# ============================================================================
# DYNAMIC AUTHORITY REGISTRY - Prefers Onionoo data, falls back to hardcoded
# ============================================================================
class AuthorityRegistry:
    """
    Dynamic authority registry that prefers Onionoo-discovered authorities
    over hardcoded fallback data.
    
    Usage:
        registry = AuthorityRegistry()
        registry.update_from_onionoo(relay_list)  # Call when Onionoo data available
        names = registry.get_authority_names()
        count = registry.get_authority_count()
    """
    
    def __init__(self):
        self._discovered_authorities = []  # From Onionoo
        self._authority_names = None  # Cached sorted names
        self._using_fallback = True
    
    def update_from_onionoo(self, relays: list) -> int:
        """
        Update authority data from Onionoo relay list.
        
        Args:
            relays: List of relay dicts from Onionoo details API
            
        Returns:
            Number of authorities discovered
        """
        if not relays:
            return 0
        
        authorities = []
        for r in relays:
            if 'Authority' in r.get('flags', []):
                authorities.append({
                    'fingerprint': r.get('fingerprint', ''),
                    'nickname': r.get('nickname', ''),
                    'address': r.get('or_addresses', [''])[0].split(':')[0] if r.get('or_addresses') else '',
                })
        
        if authorities:
            self._discovered_authorities = authorities
            self._authority_names = sorted([a['nickname'] for a in authorities])
            self._using_fallback = False
            logger.info(f"AuthorityRegistry: Discovered {len(authorities)} authorities from Onionoo")
        
        return len(authorities)
    
    def get_authority_names(self) -> List[str]:
        """Get sorted list of all authority names (Onionoo first, fallback if unavailable)."""
        if self._authority_names:
            return self._authority_names
        return _FALLBACK_ALL_AUTHORITY_NAMES
    
    def get_authority_count(self) -> int:
        """Get number of authorities (Onionoo first, fallback if unavailable)."""
        if self._discovered_authorities:
            return len(self._discovered_authorities)
        return _FALLBACK_AUTHORITY_COUNT
    
    def get_discovered_authorities(self) -> List[dict]:
        """Get list of discovered authority dicts from Onionoo."""
        return self._discovered_authorities
    
    def is_using_fallback(self) -> bool:
        """Check if using fallback data (Onionoo not available)."""
        return self._using_fallback
    
    def get_voting_authority_names(self) -> List[str]:
        """
        Get sorted list of VOTING authority names (9 authorities).
        NOTE: Serge has Authority flag but doesn't vote.
        """
        # If we have Onionoo data, filter out non-voting authorities
        # For now, we use the signing key mapping as source of truth for voters
        return _FALLBACK_VOTING_AUTHORITY_NAMES
    
    def get_voting_authority_count(self) -> int:
        """Get number of voting authorities (9)."""
        return _FALLBACK_VOTING_AUTHORITY_COUNT
    
    def get_signing_key_to_name(self) -> Dict[str, str]:
        """
        Get signing key fingerprint to name mapping.
        NOTE: This always uses the hardcoded mapping because signing key fingerprints
        are different from Onionoo relay fingerprints - we can't discover this dynamically.
        Only includes the 9 voting authorities.
        """
        return _FALLBACK_SIGNING_KEY_TO_NAME


# Global registry instance - can be updated when Onionoo data is loaded
_authority_registry = AuthorityRegistry()


def get_authority_registry() -> AuthorityRegistry:
    """Get the global authority registry instance."""
    return _authority_registry


# ============================================================================
# BACKWARD COMPATIBILITY - Expose commonly used values
# ============================================================================
# These use the registry which prefers Onionoo data over fallback
def get_authority_names() -> List[str]:
    """Get sorted list of ALL authority names (dynamic from Onionoo when available)."""
    return _authority_registry.get_authority_names()


def get_authority_count() -> int:
    """Get total authority count (dynamic from Onionoo when available)."""
    return _authority_registry.get_authority_count()


def get_voting_authority_names() -> List[str]:
    """Get sorted list of VOTING authority names (9 authorities that produce votes)."""
    return _authority_registry.get_voting_authority_names()


def get_voting_authority_count() -> int:
    """Get voting authority count (9 - excludes non-voting authorities like Serge)."""
    return _authority_registry.get_voting_authority_count()


# Signing key mapping - always hardcoded (different from relay fingerprints)
AUTHORITIES = _FALLBACK_SIGNING_KEY_TO_NAME  # For backward compatibility
AUTHORITIES_BY_NAME = {name: fp for fp, name in _FALLBACK_SIGNING_KEY_TO_NAME.items()}

# Default values - use functions for dynamic behavior, these are fallback values
DEFAULT_AUTHORITY_COUNT = _FALLBACK_VOTING_AUTHORITY_COUNT  # 9 voting authorities
AUTHORITY_NAMES = _FALLBACK_VOTING_AUTHORITY_NAMES  # Backward compat for voting authorities

# Import flag threshold constants from centralized module (DRY)
from .flag_thresholds import (
    SECONDS_PER_DAY,
    GUARD_BW_GUARANTEE as AUTH_DIR_GUARD_BW_GUARANTEE,  # Backward compat alias
    GUARD_TK_DEFAULT,
    GUARD_WFU_DEFAULT,
    HSDIR_TK_DEFAULT,
    HSDIR_WFU_DEFAULT,
    FAST_BW_GUARANTEE,
    parse_wfu_threshold,
    format_time_as_days,
    check_guard_eligibility,
    check_hsdir_eligibility,
    check_fast_eligibility,
    check_stable_eligibility,
)

COLLECTOR_BASE = 'https://collector.torproject.org'
VOTES_PATH = '/recent/relay-descriptors/votes/'
BANDWIDTH_PATH = '/recent/relay-descriptors/bandwidths/'

# Maximum response size to prevent DoS
MAX_RESPONSE_SIZE = 100 * 1024 * 1024  # 100MB limit

# Pre-compiled regex patterns for bandwidth file parsing (compiled once, used many times)
_BW_NODE_ID_PATTERN = re.compile(r'node_id=\$([A-F0-9]+)', re.IGNORECASE)
_BW_VALUE_PATTERN = re.compile(r'bw=(\d+)')


class CollectorFetcher:
    """
    Fetch and index CollecTor data.
    
    Usage:
        fetcher = CollectorFetcher()
        data = fetcher.fetch_all()
        consensus_evaluation = fetcher.get_relay_consensus_evaluation('FINGERPRINT')
    """
    
    def __init__(self, timeout: int = 30, authorities: Optional[List[Dict]] = None):
        """
        Initialize CollectorFetcher.
        
        Args:
            timeout: HTTP request timeout in seconds
            authorities: Optional list of authority dicts discovered from Onionoo
        """
        self.timeout = timeout
        self.authorities = authorities or []
        self.votes = {}
        self.bandwidth_files = {}
        self.relay_index = {}
        self.flag_thresholds = {}
        self.bw_authorities = set()  # Authorities that run bandwidth scanners
        self.ipv6_testing_authorities = set()  # Authorities that test IPv6
        self._timings = {}
    
    def fetch_all(self) -> dict:
        """
        Fetch all data from CollecTor with comprehensive error handling.
        NEVER let exceptions propagate - always return usable data or empty fallback.
        
        Returns:
            dict: Collected data with votes, bandwidth files, relay index, and flag thresholds
        """
        result = {
            'votes': {},
            'bandwidth_files': {},
            'relay_index': {},
            'flag_thresholds': {},
            'bw_authorities': [],
            'ipv6_testing_authorities': [],
            'fetched_at': datetime.utcnow().isoformat(),  # Note: uses UTC for consistency
            'errors': [],
            'timings': {},
        }
        
        # Fetch votes and bandwidth files in parallel
        start_time = time.time()
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                votes_future = executor.submit(self._fetch_all_votes)
                bw_future = executor.submit(self._fetch_all_bandwidth_files)
                
                try:
                    self.votes = votes_future.result(timeout=120)
                    result['votes'] = self.votes
                except Exception as e:
                    logger.error(f"Failed to fetch votes: {e}")
                    result['errors'].append(f"votes: {e}")
                    self.votes = {}
                
                try:
                    self.bandwidth_files = bw_future.result(timeout=120)
                    result['bandwidth_files'] = self.bandwidth_files
                except Exception as e:
                    logger.error(f"Failed to fetch bandwidth: {e}")
                    result['errors'].append(f"bandwidth: {e}")
                    self.bandwidth_files = {}
                    
        except Exception as e:
            logger.error(f"Failed to execute parallel fetches: {e}")
            result['errors'].append(f"parallel_fetch: {e}")
        
        self._timings['fetch'] = time.time() - start_time
        
        # Build index only if we have some data
        if self.votes or self.bandwidth_files:
            start_time = time.time()
            try:
                # _build_relay_index() now also extracts flag_thresholds in single pass
                self._build_relay_index()
                result['relay_index'] = self.relay_index
                result['flag_thresholds'] = self.flag_thresholds
            except Exception as e:
                logger.error(f"Failed to build relay index: {e}")
                result['errors'].append(f"relay_index: {e}")
            
            self._timings['index'] = time.time() - start_time
        
        result['bw_authorities'] = list(self.bw_authorities)
        result['ipv6_testing_authorities'] = list(self.ipv6_testing_authorities)
        result['timings'] = self._timings
        
        # Log performance metrics
        total = sum(self._timings.values())
        logger.info(f"CollecTor fetch complete in {total:.1f}s")
        if total > 60:
            logger.warning(f"CollecTor fetch took {total:.1f}s (>60s threshold)")
        
        return result
    
    def get_relay_consensus_evaluation(self, fingerprint: str, authority_count: int = DEFAULT_AUTHORITY_COUNT) -> dict:
        """
        Get consensus evaluation for a single relay.
        O(1) lookup after index is built.
        
        Args:
            fingerprint: Relay fingerprint (40 hex chars)
            authority_count: Total number of authorities (for consensus calculation)
        
        Returns:
            dict: Consensus evaluation information for the relay
        """
        fingerprint = fingerprint.upper()
        if not self._validate_fingerprint(fingerprint):
            return {'error': 'Invalid fingerprint', 'in_consensus': False}
            
        if fingerprint not in self.relay_index:
            return {'error': 'Relay not found in votes', 'in_consensus': False, 'vote_count': 0}
        
        relay = self.relay_index[fingerprint]
        vote_count = len(relay.get('votes', {}))
        
        # Tor consensus requires MAJORITY of authorities
        # Per dir-spec: relay appears in consensus if > half of authorities vote for it
        majority_required = (authority_count // 2) + 1
        in_consensus = vote_count >= majority_required
        
        return {
            'fingerprint': fingerprint,
            'in_consensus': in_consensus,
            'vote_count': vote_count,
            'total_authorities': authority_count,
            'majority_required': majority_required,
            'authority_votes': self._format_authority_votes(relay),
            'flag_eligibility': self._analyze_flag_eligibility(relay),
            'bandwidth': self._format_bandwidth(relay),
            'reachability': self._format_reachability(relay),
        }
    
    def _fetch_url(self, url: str) -> str:
        """Fetch URL with timeout, size limit, and error handling."""
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
    
    def _fetch_vote_listing(self) -> List[str]:
        """Fetch list of available vote files from CollecTor."""
        try:
            html = self._fetch_url(f"{COLLECTOR_BASE}{VOTES_PATH}")
            # Parse HTML listing for vote file links
            # Files match pattern: YYYY-MM-DD-HH-MM-SS-vote-FINGERPRINT-...
            pattern = r'href="([0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}-vote-[A-F0-9]+-[^"]+)"'
            matches = re.findall(pattern, html, re.IGNORECASE)
            return matches
        except Exception as e:
            logger.error(f"Failed to fetch vote listing: {e}")
            return []
    
    def _fetch_bandwidth_listing(self) -> List[str]:
        """Fetch list of available bandwidth files from CollecTor."""
        try:
            html = self._fetch_url(f"{COLLECTOR_BASE}{BANDWIDTH_PATH}")
            # Parse HTML listing for bandwidth file links
            pattern = r'href="([0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}-bandwidth-[^"]+)"'
            matches = re.findall(pattern, html, re.IGNORECASE)
            return matches
        except Exception as e:
            logger.error(f"Failed to fetch bandwidth listing: {e}")
            return []
    
    def _get_latest_votes(self, vote_files: List[str]) -> Dict[str, str]:
        """
        Get the most recent vote file for each authority.
        
        Args:
            vote_files: List of vote filenames
            
        Returns:
            dict: Authority fingerprint → latest filename
        """
        # Group by authority fingerprint
        by_authority = {}
        for filename in vote_files:
            # Extract authority fingerprint from filename
            # Format: YYYY-MM-DD-HH-MM-SS-vote-FINGERPRINT-...
            match = re.search(r'vote-([A-F0-9]+)-', filename, re.IGNORECASE)
            if match:
                auth_fp = match.group(1).upper()
                if auth_fp not in by_authority or filename > by_authority[auth_fp]:
                    by_authority[auth_fp] = filename
        
        return by_authority
    
    def _fetch_all_votes(self) -> Dict[str, dict]:
        """Fetch and parse all authority votes."""
        votes = {}
        
        # Get listing of available votes
        vote_files = self._fetch_vote_listing()
        if not vote_files:
            logger.warning("No vote files found")
            return votes
        
        # Get latest vote for each authority
        latest_votes = self._get_latest_votes(vote_files)
        
        # Fetch each vote in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=9) as executor:
            future_to_auth = {}
            for auth_fp, filename in latest_votes.items():
                url = f"{COLLECTOR_BASE}{VOTES_PATH}{filename}"
                future = executor.submit(self._fetch_and_parse_vote, url, auth_fp)
                future_to_auth[future] = auth_fp
            
            for future in concurrent.futures.as_completed(future_to_auth):
                auth_fp = future_to_auth[future]
                try:
                    vote_data = future.result()
                    if vote_data:
                        auth_name = AUTHORITIES.get(auth_fp, auth_fp[:8])
                        votes[auth_name] = vote_data
                        
                        # Track if this authority runs a bandwidth scanner
                        if vote_data.get('has_bandwidth_file_headers'):
                            self.bw_authorities.add(auth_name)
                except Exception as e:
                    logger.warning(f"Failed to fetch vote for {auth_fp}: {e}")
        
        logger.info(f"Fetched {len(votes)} authority votes")
        return votes
    
    def _fetch_and_parse_vote(self, url: str, auth_fp: str) -> Optional[dict]:
        """Fetch and parse a single vote file."""
        try:
            content = self._fetch_url(url)
            return self._parse_vote(content, auth_fp)
        except Exception as e:
            logger.warning(f"Failed to fetch/parse vote from {url}: {e}")
            return None
    
    def _parse_vote(self, content: str, auth_fp: str) -> dict:
        """
        Parse a vote file content.
        
        Args:
            content: Raw vote file content
            auth_fp: Authority fingerprint
            
        Returns:
            dict: Parsed vote data
        """
        vote = {
            'authority_fingerprint': auth_fp,
            'relays': {},
            'flag_thresholds': {},
            'has_bandwidth_file_headers': False,
        }
        
        lines = content.split('\n')
        current_relay = None
        
        for line in lines:
            line = line.strip()
            
            # Parse flag-thresholds line
            if line.startswith('flag-thresholds '):
                vote['flag_thresholds'] = self._parse_flag_thresholds(line)
            
            # Check for bandwidth-file-headers (indicates bandwidth authority)
            elif line.startswith('bandwidth-file-headers'):
                vote['has_bandwidth_file_headers'] = True
            
            # Parse relay entry (r line)
            elif line.startswith('r '):
                if current_relay and current_relay.get('fingerprint'):
                    vote['relays'][current_relay['fingerprint']] = current_relay
                current_relay = self._parse_relay_r_line(line)
                if current_relay is None:
                    continue  # Skip malformed relay entries
            
            # Parse additional relay lines
            elif current_relay:
                if line.startswith('s '):
                    # Flags line
                    current_relay['flags'] = line[2:].split()
                elif line.startswith('w '):
                    # Bandwidth line
                    current_relay.update(self._parse_w_line(line))
                elif line.startswith('a '):
                    # IPv6 address line
                    current_relay['ipv6_address'] = line[2:]
                    current_relay['ipv6_reachable'] = True
                elif line.startswith('stats '):
                    # Stats line: stats wfu=X.XX tk=XXXX mtbf=XXXX
                    current_relay.update(self._parse_stats_line(line))
        
        # Don't forget the last relay
        if current_relay and current_relay.get('fingerprint'):
            vote['relays'][current_relay['fingerprint']] = current_relay
        
        return vote
    
    def _parse_relay_r_line(self, line: str) -> Optional[dict]:
        """Parse an 'r' line from a vote (relay entry)."""
        # r <nickname> <identity> <digest> <publication_date> <publication_time> <IP> <ORPort> <DirPort>
        # Example: r lisdex AAAErLudKby6FyVrs1ko3b/Iq6k YpRTARWdwmwEVbePGq0/dy8d3I4 2025-12-27 11:01:03 152.53.144.50 8443 0
        parts = line.split()
        if len(parts) < 9:  # Need at least 9 parts (r + 8 fields)
            return None
        
        try:
            # Identity is base64-encoded, need to decode to get fingerprint
            identity_b64 = parts[2]
            # Pad base64 if needed
            padding = 4 - len(identity_b64) % 4
            if padding != 4:
                identity_b64 += '=' * padding
            identity_bytes = base64.b64decode(identity_b64)
            fingerprint = identity_bytes.hex().upper()
            
            # Note: parts[4] is date, parts[5] is time, parts[6] is IP
            # Parse descriptor published timestamp
            descriptor_published = None
            try:
                descriptor_published = f"{parts[4]} {parts[5]}"  # e.g., "2025-12-27 11:01:03"
            except:
                pass
            
            return {
                'nickname': parts[1],
                'fingerprint': fingerprint,
                'ip': parts[6],
                'or_port': int(parts[7]),
                'dir_port': int(parts[8]),
                'descriptor_published': descriptor_published,  # When relay's descriptor was published
                'flags': [],
                'bandwidth': None,
                'measured': None,
                'wfu': None,
                'tk': None,
                'mtbf': None,
            }
        except Exception as e:
            logger.debug(f"Failed to parse r line: {e}")
            return None
    
    def _parse_w_line(self, line: str) -> dict:
        """Parse a 'w' line (bandwidth weights)."""
        result = {}
        parts = line[2:].split()
        
        for part in parts:
            if '=' in part:
                key, value = part.split('=', 1)
                try:
                    if key == 'Bandwidth':
                        result['bandwidth'] = int(value)
                    elif key == 'Measured':
                        result['measured'] = int(value)
                except ValueError:
                    pass
        
        return result
    
    def _parse_stats_line(self, line: str) -> dict:
        """Parse a 'stats' line (wfu, tk, mtbf values)."""
        result = {}
        # stats wfu=0.987654 tk=1234567 mtbf=7654321
        parts = line[6:].split()  # Skip 'stats '
        
        for part in parts:
            if '=' in part:
                key, value = part.split('=', 1)
                try:
                    if key == 'wfu':
                        result['wfu'] = float(value)
                    elif key == 'tk':
                        result['tk'] = int(value)
                    elif key == 'mtbf':
                        result['mtbf'] = int(value)
                except ValueError:
                    pass
        
        return result
    
    def _parse_flag_thresholds(self, line: str) -> dict:
        """Parse flag-thresholds line from vote."""
        thresholds = {}
        # flag-thresholds stable-uptime=... stable-mtbf=... ...
        parts = line.split()[1:]  # Skip 'flag-thresholds'
        
        for part in parts:
            if '=' in part:
                key, value = part.split('=', 1)
                try:
                    # Handle percentage values
                    if value.endswith('%'):
                        thresholds[key] = float(value[:-1]) / 100
                    else:
                        thresholds[key] = float(value)
                except ValueError:
                    thresholds[key] = value
        
        return thresholds
    
    def _fetch_all_bandwidth_files(self) -> Dict[str, dict]:
        """Fetch and parse bandwidth measurement files."""
        bandwidth_files = {}
        
        # Get listing of available bandwidth files
        bw_files = self._fetch_bandwidth_listing()
        if not bw_files:
            logger.info("No bandwidth files found")
            return bandwidth_files
        
        # Get the most recent bandwidth file
        if bw_files:
            latest_file = max(bw_files)
            url = f"{COLLECTOR_BASE}{BANDWIDTH_PATH}{latest_file}"
            
            try:
                content = self._fetch_url(url)
                bandwidth_files = self._parse_bandwidth_file(content)
            except Exception as e:
                logger.warning(f"Failed to fetch bandwidth file: {e}")
        
        return bandwidth_files
    
    def _parse_bandwidth_file(self, content: str) -> Dict[str, dict]:
        """Parse a bandwidth measurement file using pre-compiled regex patterns."""
        measurements = {}
        
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('@') or line.startswith('#'):
                continue
            
            # Format: bw=<value> node_id=$<fingerprint> ...
            if 'node_id=$' in line:
                try:
                    # Use pre-compiled patterns for better performance
                    fp_match = _BW_NODE_ID_PATTERN.search(line)
                    bw_match = _BW_VALUE_PATTERN.search(line)
                    
                    if fp_match and bw_match:
                        fingerprint = fp_match.group(1).upper()
                        bandwidth = int(bw_match.group(1))
                        measurements[fingerprint] = {'bw': bandwidth}
                except Exception:
                    continue
        
        return measurements
    
    def _build_relay_index(self):
        """
        Build index of relay data from all votes and extract flag thresholds in single pass.
        Indexed by fingerprint for O(1) lookup.
        
        Optimization: Combined with _extract_flag_thresholds to avoid iterating self.votes twice.
        """
        self.relay_index = {}
        self.flag_thresholds = {}  # Extract thresholds in same loop
        
        for auth_name, vote_data in self.votes.items():
            if not vote_data:
                continue
            
            # Extract flag thresholds (previously in separate _extract_flag_thresholds method)
            if 'flag_thresholds' in vote_data:
                self.flag_thresholds[auth_name] = vote_data['flag_thresholds']
            
            # Build relay index
            relays = vote_data.get('relays')
            if not relays:
                continue
            
            for fingerprint, relay_data in relays.items():
                if fingerprint not in self.relay_index:
                    self.relay_index[fingerprint] = {
                        'fingerprint': fingerprint,
                        'nickname': relay_data.get('nickname', ''),
                        'votes': {},
                        'bandwidth_measurements': {},
                    }
                
                # Add vote data for this authority
                self.relay_index[fingerprint]['votes'][auth_name] = {
                    'flags': relay_data.get('flags', []),
                    'bandwidth': relay_data.get('bandwidth'),
                    'measured': relay_data.get('measured'),
                    'wfu': relay_data.get('wfu'),
                    'tk': relay_data.get('tk'),
                    'mtbf': relay_data.get('mtbf'),
                    'ipv6_reachable': relay_data.get('ipv6_reachable'),
                    'ipv6_address': relay_data.get('ipv6_address'),
                    'descriptor_published': relay_data.get('descriptor_published'),
                }
        
        # Add bandwidth measurements from bandwidth files
        for fingerprint, bw_data in self.bandwidth_files.items():
            if fingerprint in self.relay_index:
                self.relay_index[fingerprint]['bandwidth_measurements'] = bw_data
        
        logger.info(f"Indexed {len(self.relay_index)} relays from votes, {len(self.flag_thresholds)} authority thresholds")
    
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
    
    def _format_authority_votes(self, relay: dict) -> List[dict]:
        """
        Format per-authority vote information for display.
        Only includes voting authorities (9) - excludes non-voting authorities like Serge.
        """
        authority_votes = []
        relay_votes = relay.get('votes', {})
        
        for auth_name in get_voting_authority_names():  # Only voting authorities (9)
            vote_info = relay_votes.get(auth_name, {})
            
            voted = bool(vote_info)
            flags = vote_info.get('flags', []) if voted else []
            
            authority_votes.append({
                'authority': auth_name,
                'fingerprint': AUTHORITIES_BY_NAME.get(auth_name, ''),  # Use pre-computed lookup
                'voted': voted,
                'flags': flags,
                'bandwidth': vote_info.get('bandwidth'),
                'measured': vote_info.get('measured'),
                'wfu': vote_info.get('wfu'),
                'wfu_display': f"{vote_info.get('wfu', 0) * 100:.1f}%" if vote_info.get('wfu') else 'N/A',
                'tk': vote_info.get('tk'),
                'tk_display': self._format_time_known(vote_info.get('tk')),
                'mtbf': vote_info.get('mtbf'),
                'ipv4_reachable': voted,  # If voted, authority could reach relay
                'ipv6_reachable': vote_info.get('ipv6_reachable'),
                'ipv6_address': vote_info.get('ipv6_address'),
                'is_bw_authority': auth_name in self.bw_authorities,
                'descriptor_published': vote_info.get('descriptor_published'),  # Timestamp of relay's descriptor
            })
        
        return authority_votes
    
    def _format_time_known(self, seconds: Optional[int]) -> str:
        """Format time known in human-readable format."""
        if seconds is None:
            return 'N/A'
        
        days = seconds / SECONDS_PER_DAY
        if days >= 1:
            return f"{days:.1f} days"
        
        hours = seconds / 3600
        if hours >= 1:
            return f"{hours:.1f} hours"
        
        return f"{seconds} seconds"
    
    def _analyze_flag_eligibility(self, relay: dict) -> dict:
        """
        Analyze flag eligibility across all authorities.
        
        Guard flag requirements per Tor dir-spec:
        1. Must be Fast
        2. Must be Stable
        3. WFU >= guard-wfu threshold
        4. TK >= guard-tk threshold (makes relay "familiar")
        5. Bandwidth >= AuthDirGuardBWGuarantee (2 MB/s default) OR in top 25% (>= guard-bw-inc-exits)
        6. Must have V2Dir flag
        """
        eligibility = {
            'guard': {'eligible_count': 0, 'assigned_count': 0, 'details': []},
            'stable': {'eligible_count': 0, 'assigned_count': 0, 'details': []},
            'fast': {'eligible_count': 0, 'assigned_count': 0, 'details': []},
            'hsdir': {'eligible_count': 0, 'assigned_count': 0, 'details': []},
            'exit': {'eligible_count': 0, 'assigned_count': 0, 'details': []},
            'middleonly': {'eligible_count': 0, 'assigned_count': 0, 'details': []},
            'badexit': {'eligible_count': 0, 'assigned_count': 0, 'details': []},
        }
        
        for auth_name, thresholds in self.flag_thresholds.items():
            vote_info = relay.get('votes', {}).get(auth_name, {})
            if not vote_info:
                continue
            
            # Get flags assigned by this authority
            auth_flags = vote_info.get('flags', [])
            
            # Guard flag eligibility
            guard_wfu_threshold = thresholds.get('guard-wfu', 0.98)
            guard_tk_threshold = thresholds.get('guard-tk', GUARD_TK_DEFAULT)
            guard_bw_top25_threshold = thresholds.get('guard-bw-inc-exits', 0)  # Top 25% cutoff
            
            relay_wfu = vote_info.get('wfu', 0)
            relay_tk = vote_info.get('tk', 0)
            # Use measured bandwidth (from sbws) for Guard eligibility, fall back to self-reported
            relay_measured_bw = vote_info.get('measured') or vote_info.get('bandwidth', 0)
            
            # Guard BW check: bandwidth >= 2 MB/s (guarantee) OR in top 25% (>= guard-bw-inc-exits)
            # Per Tor dir-spec: "bandwidth is at least AuthDirGuardBWGuarantee (2 MB by default), 
            # OR its bandwidth is among the 25% fastest relays"
            guard_bw_meets_guarantee = relay_measured_bw >= AUTH_DIR_GUARD_BW_GUARANTEE  # Use module constant
            guard_bw_in_top25 = relay_measured_bw >= guard_bw_top25_threshold
            guard_bw_eligible = guard_bw_meets_guarantee or guard_bw_in_top25
            
            # Guard flag prerequisites: must have Fast, Stable, and V2Dir flags from this authority
            # Per Tor dir-spec Section 3.4.2: Guard requires Fast, Stable, and V2Dir
            has_fast = 'Fast' in auth_flags
            has_stable = 'Stable' in auth_flags
            has_v2dir = 'V2Dir' in auth_flags
            guard_prereqs_met = has_fast and has_stable and has_v2dir
            
            guard_eligible = (
                guard_prereqs_met and
                relay_wfu >= guard_wfu_threshold and
                relay_tk >= guard_tk_threshold and
                guard_bw_eligible
            )
            
            if guard_eligible:
                eligibility['guard']['eligible_count'] += 1
            
            # Count actual Guard flag assignment by this authority
            has_guard_flag = 'Guard' in auth_flags
            if has_guard_flag:
                eligibility['guard']['assigned_count'] += 1
            
            eligibility['guard']['details'].append({
                'authority': auth_name,
                'eligible': guard_eligible,
                'assigned': has_guard_flag,  # Whether authority actually assigned Guard flag
                # Prerequisite flags (per Tor dir-spec: Guard requires Fast, Stable, V2Dir)
                'has_fast': has_fast,
                'has_stable': has_stable,
                'has_v2dir': has_v2dir,
                'prereqs_met': guard_prereqs_met,
                # WFU requirement
                'wfu_threshold': guard_wfu_threshold,
                'wfu_value': relay_wfu,
                'wfu_met': relay_wfu >= guard_wfu_threshold,
                # TK requirement
                'tk_threshold': guard_tk_threshold,
                'tk_value': relay_tk,
                'tk_met': relay_tk >= guard_tk_threshold,
                # BW requirement
                'bw_guarantee': AUTH_DIR_GUARD_BW_GUARANTEE,  # 2 MB/s minimum
                'bw_top25_threshold': guard_bw_top25_threshold,  # Top 25% cutoff
                'bw_value': relay_measured_bw,
                'bw_meets_guarantee': guard_bw_meets_guarantee,
                'bw_in_top25': guard_bw_in_top25,
                'bw_met': guard_bw_eligible,
            })
            
            # Stable flag eligibility
            stable_uptime = thresholds.get('stable-uptime', 0)
            stable_mtbf = thresholds.get('stable-mtbf', 0)
            relay_mtbf = vote_info.get('mtbf', 0)
            
            stable_eligible = relay_mtbf >= stable_mtbf if stable_mtbf > 0 else True
            if stable_eligible:
                eligibility['stable']['eligible_count'] += 1
            
            # Count actual Stable flag assignment by this authority
            has_stable_flag = 'Stable' in auth_flags
            if has_stable_flag:
                eligibility['stable']['assigned_count'] += 1
            
            eligibility['stable']['details'].append({
                'authority': auth_name,
                'eligible': stable_eligible,
                'assigned': has_stable_flag,  # Whether authority actually assigned Stable flag
                'mtbf_threshold': stable_mtbf,
                'mtbf_value': relay_mtbf,
            })
            
            # Fast flag eligibility - use measured bandwidth
            fast_speed = thresholds.get('fast-speed', 0)
            fast_eligible = relay_measured_bw >= fast_speed
            if fast_eligible:
                eligibility['fast']['eligible_count'] += 1
            
            # Count actual Fast flag assignment by this authority
            # Note: has_fast already calculated above for Guard prereq check
            if has_fast:
                eligibility['fast']['assigned_count'] += 1
            
            eligibility['fast']['details'].append({
                'authority': auth_name,
                'eligible': fast_eligible,
                'assigned': has_fast,  # Whether authority actually assigned Fast flag
                'speed_threshold': fast_speed,
                'speed_value': relay_measured_bw,
            })
            
            # HSDir flag eligibility
            hsdir_wfu = thresholds.get('hsdir-wfu', 0.98)
            hsdir_tk = thresholds.get('hsdir-tk', HSDIR_TK_DEFAULT)
            
            hsdir_eligible = relay_wfu >= hsdir_wfu and relay_tk >= hsdir_tk
            if hsdir_eligible:
                eligibility['hsdir']['eligible_count'] += 1
            
            # Count actual HSDir flag assignment by this authority
            has_hsdir_flag = 'HSDir' in auth_flags
            if has_hsdir_flag:
                eligibility['hsdir']['assigned_count'] += 1
            
            eligibility['hsdir']['details'].append({
                'authority': auth_name,
                'eligible': hsdir_eligible,
                'assigned': has_hsdir_flag,  # Whether authority actually assigned HSDir flag
                'wfu_threshold': hsdir_wfu,
                'tk_threshold': hsdir_tk,
            })
            
            # Simple flag tracking: Exit, MiddleOnly, BadExit
            # These flags have no numeric thresholds — purely presence-based.
            # Exit: policy-based (ports 80+443); MiddleOnly: authority discretion;
            # BadExit: misbehavior detection (also auto-added with MiddleOnly).
            for flag_consensus, flag_key in (('Exit', 'exit'), ('MiddleOnly', 'middleonly'), ('BadExit', 'badexit')):
                has_flag = flag_consensus in auth_flags
                if has_flag:
                    eligibility[flag_key]['eligible_count'] += 1
                    eligibility[flag_key]['assigned_count'] += 1
                eligibility[flag_key]['details'].append({
                    'authority': auth_name,
                    'eligible': has_flag,
                    'assigned': has_flag,
                })
        
        return eligibility
    
    def _format_bandwidth(self, relay: dict) -> dict:
        """
        Format bandwidth information from all sources.
        
        Tracks:
        - bw_auth_measured_count: How many BW authorities actually measured this relay
        - bw_auth_total: Total number of BW authorities (denominator)
        - measurement_count: Total bandwidth values (from all sources)
        """
        votes = relay.get('votes', {})
        measurements = relay.get('bandwidth_measurements', {})
        
        bandwidth_values = []
        bw_auth_measured_count = 0  # BW authorities that measured THIS relay
        bw_auth_measured_set = set()  # Track names only for "not measured" display
        
        for auth_name, vote in votes.items():
            if vote.get('measured') is not None:
                bandwidth_values.append(vote['measured'])
                if auth_name in self.bw_authorities:
                    bw_auth_measured_count += 1
                    bw_auth_measured_set.add(auth_name)
            elif vote.get('bandwidth') is not None:
                bandwidth_values.append(vote['bandwidth'])
        
        # Add measurements from bandwidth files
        bandwidth_values.extend(measurements.values())
        
        bw_auth_total = len(self.bw_authorities)
        # Only compute missing names when not all BW authorities measured (template only uses this case)
        bw_auth_not_measured = (sorted(self.bw_authorities - bw_auth_measured_set)
                                if bw_auth_measured_count < bw_auth_total else [])
        
        if not bandwidth_values:
            return {
                'median': None, 'average': None, 'min': None, 'max': None, 
                'deviation': None, 'measurement_count': 0,
                'bw_auth_measured_count': 0,
                'bw_auth_total': bw_auth_total,
                'bw_auth_not_measured_names': sorted(self.bw_authorities),
            }
        
        # Calculate median (what Tor consensus actually uses)
        sorted_values = sorted(bandwidth_values)
        n = len(sorted_values)
        if n % 2 == 0:
            median = (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2
        else:
            median = sorted_values[n // 2]
        
        avg = sum(bandwidth_values) / len(bandwidth_values)
        return {
            'median': median,  # Tor consensus uses median
            'average': avg,    # For reference
            'min': min(bandwidth_values),
            'max': max(bandwidth_values),
            'deviation': max(bandwidth_values) - min(bandwidth_values) if len(bandwidth_values) > 1 else 0,
            'measurement_count': len(bandwidth_values),
            'bw_auth_measured_count': bw_auth_measured_count,
            'bw_auth_total': bw_auth_total,
            'bw_auth_not_measured_names': bw_auth_not_measured,
        }
    
    def _format_reachability(self, relay: dict) -> dict:
        """
        Format reachability information across authorities.
        Only includes voting authorities (9) - reachability is only tested by voters.
        """
        votes = relay.get('votes', {})
        
        ipv4_reachable = []
        ipv6_reachable = []
        ipv6_not_tested = []
        
        for auth_name in get_voting_authority_names():  # Only voting authorities (9)
            vote = votes.get(auth_name, {})
            
            if vote:
                ipv4_reachable.append(auth_name)
                if vote.get('ipv6_reachable'):
                    ipv6_reachable.append(auth_name)
                elif auth_name not in self.ipv6_testing_authorities:
                    ipv6_not_tested.append(auth_name)
        
        return {
            'ipv4_reachable_count': len(ipv4_reachable),
            'ipv4_reachable_authorities': ipv4_reachable,
            'ipv6_reachable_count': len(ipv6_reachable),
            'ipv6_reachable_authorities': ipv6_reachable,
            'ipv6_not_tested_authorities': ipv6_not_tested,
            'total_authorities': get_voting_authority_count(),  # Use voting authorities (9) for consensus
        }


def discover_authorities(relays: list, update_registry: bool = True) -> list:
    """
    Discover directory authorities from relay list (Onionoo details API).
    Returns list of authority relay dicts with fingerprints, nicknames, IPs.
    
    This function prefers dynamic discovery from Onionoo over hardcoded fallback.
    When authorities are discovered, it updates the global registry so other
    functions automatically use the discovered values.
    
    Args:
        relays: List of relay dicts from Onionoo
        update_registry: If True, updates global AuthorityRegistry with discovered data
        
    Returns:
        List of authority dicts
    """
    authorities = []
    
    for r in relays:
        if 'Authority' in r.get('flags', []):
            authorities.append({
                'fingerprint': r.get('fingerprint', ''),
                'nickname': r.get('nickname', ''),
                'address': r.get('or_addresses', [''])[0].split(':')[0] if r.get('or_addresses') else '',
                'dir_port': r.get('dir_address', '').split(':')[-1] or '80',
                'contact': r.get('contact', ''),
            })
    
    # Update global registry with discovered authorities
    if update_registry and authorities:
        _authority_registry.update_from_onionoo(relays)
        logger.info(f"discover_authorities: Found {len(authorities)} authorities from Onionoo")
    
    return authorities


def calculate_consensus_requirement(authority_count: int) -> dict:
    """
    Calculate majority required for consensus.
    Formula: floor(authority_count / 2) + 1
    
    Args:
        authority_count: Number of directory authorities
        
    Returns:
        dict: Consensus requirement info
    """
    majority = (authority_count // 2) + 1
    return {
        'authority_count': authority_count,
        'majority_required': majority,
        'tooltip': f"Consensus requires majority: {majority}/{authority_count} ({authority_count}÷2+1={majority})"
    }
