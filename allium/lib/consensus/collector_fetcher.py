"""
File: collector_fetcher.py

Fetch and index CollecTor data for per-relay diagnostics.
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

# Directory Authority fingerprint → name mapping (fallback - should be discovered dynamically)
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

COLLECTOR_BASE = 'https://collector.torproject.org'
VOTES_PATH = '/recent/relay-descriptors/votes/'
BANDWIDTH_PATH = '/recent/relay-descriptors/bandwidths/'

# Maximum response size to prevent DoS
MAX_RESPONSE_SIZE = 100 * 1024 * 1024  # 100MB limit


class CollectorFetcher:
    """
    Fetch and index CollecTor data.
    
    Usage:
        fetcher = CollectorFetcher()
        data = fetcher.fetch_all()
        diagnostics = fetcher.get_relay_diagnostics('FINGERPRINT')
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
            'fetched_at': datetime.utcnow().isoformat(),
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
                self._build_relay_index()
                result['relay_index'] = self.relay_index
            except Exception as e:
                logger.error(f"Failed to build relay index: {e}")
                result['errors'].append(f"relay_index: {e}")
            
            try:
                self._extract_flag_thresholds()
                result['flag_thresholds'] = self.flag_thresholds
            except Exception as e:
                logger.error(f"Failed to extract flag thresholds: {e}")
                result['errors'].append(f"flag_thresholds: {e}")
            
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
    
    def get_relay_diagnostics(self, fingerprint: str, authority_count: int = 9) -> dict:
        """
        Get diagnostics for a single relay.
        O(1) lookup after index is built.
        
        Args:
            fingerprint: Relay fingerprint (40 hex chars)
            authority_count: Total number of authorities (for consensus calculation)
        
        Returns:
            dict: Diagnostic information for the relay
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
            vote_files: List of vote file names
            
        Returns:
            dict: Authority fingerprint → latest vote filename
        """
        latest_votes = {}
        
        for filename in vote_files:
            # Extract authority fingerprint from filename
            # Format: YYYY-MM-DD-HH-MM-SS-vote-FINGERPRINT-...
            match = re.match(r'[0-9-]+-vote-([A-F0-9]+)-', filename, re.IGNORECASE)
            if match:
                auth_fp = match.group(1).upper()
                # Keep the latest (files are typically sorted, but we check timestamp)
                if auth_fp not in latest_votes or filename > latest_votes[auth_fp]:
                    latest_votes[auth_fp] = filename
        
        return latest_votes
    
    def _fetch_all_votes(self) -> Dict[str, dict]:
        """
        Fetch and parse all latest authority votes.
        
        Returns:
            dict: Authority name → parsed vote data
        """
        vote_files = self._fetch_vote_listing()
        if not vote_files:
            logger.warning("No vote files found")
            return {}
        
        latest_votes = self._get_latest_votes(vote_files)
        logger.info(f"Found {len(latest_votes)} authority votes")
        
        votes = {}
        
        # Fetch votes in parallel
        def fetch_vote(auth_fp_filename):
            auth_fp, filename = auth_fp_filename
            try:
                url = f"{COLLECTOR_BASE}{VOTES_PATH}{filename}"
                content = self._fetch_url(url)
                parsed = self._parse_vote(content, auth_fp)
                if parsed:
                    return (auth_fp, parsed)
            except Exception as e:
                logger.warning(f"Failed to fetch vote for {auth_fp}: {e}")
            return None
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=9) as executor:
            results = list(executor.map(fetch_vote, latest_votes.items()))
        
        for result in results:
            if result:
                auth_fp, parsed = result
                auth_name = AUTHORITIES.get(auth_fp, auth_fp[:8])
                votes[auth_name] = parsed
                
                # Detect if this authority runs a bandwidth scanner
                if parsed.get('has_bandwidth_file_headers'):
                    self.bw_authorities.add(auth_name)
        
        logger.info(f"Successfully parsed {len(votes)} authority votes")
        return votes
    
    def _parse_vote(self, content: str, auth_fp: str) -> Optional[dict]:
        """
        Parse a vote file and extract relay information.
        
        Args:
            content: Raw vote file content
            auth_fp: Authority fingerprint
            
        Returns:
            dict: Parsed vote data or None if parsing fails
        """
        if not content:
            return None
        
        result = {
            'authority_fingerprint': auth_fp,
            'authority_name': AUTHORITIES.get(auth_fp, auth_fp[:8]),
            'relays': {},
            'flag_thresholds': {},
            'has_bandwidth_file_headers': False,
            'params': {},
        }
        
        lines = content.split('\n')
        current_relay = None
        in_router_section = False
        
        for line in lines:
            # Detect bandwidth-file-headers (indicates BW authority)
            if line.startswith('bandwidth-file-headers'):
                result['has_bandwidth_file_headers'] = True
                continue
            
            # Parse flag-thresholds line
            if line.startswith('flag-thresholds'):
                result['flag_thresholds'] = self._parse_flag_thresholds(line)
                continue
            
            # Parse router status entry (r line)
            if line.startswith('r '):
                in_router_section = True
                parts = line.split()
                if len(parts) >= 9:
                    nickname = parts[1]
                    # Decode base64 fingerprint (parts[2] is identity)
                    try:
                        fp_bytes = base64.b64decode(parts[2] + '==')
                        fingerprint = fp_bytes.hex().upper()
                    except Exception:
                        fingerprint = parts[2]
                    
                    # Parse IP address and ports
                    # r line: r nickname identity digest date time IP ORPort DirPort
                    ip_address = parts[6] if len(parts) > 6 else ''
                    or_port = parts[7] if len(parts) > 7 else ''
                    dir_port = parts[8] if len(parts) > 8 else ''
                    
                    current_relay = {
                        'nickname': nickname,
                        'fingerprint': fingerprint,
                        'ipv4_address': ip_address,
                        'or_port': or_port,
                        'dir_port': dir_port,
                        'flags': [],
                        'bandwidth': None,
                        'measured': None,
                        'ipv6_address': None,
                        'ipv6_reachable': None,
                        'wfu': None,
                        'tk': None,
                        'mtbf': None,
                    }
                    result['relays'][fingerprint] = current_relay
                continue
            
            # Parse 'a' line (IPv6 address)
            if line.startswith('a ') and current_relay:
                # a [IPv6]:port
                ipv6_match = re.match(r'a \[([^\]]+)\]:(\d+)', line)
                if ipv6_match:
                    current_relay['ipv6_address'] = ipv6_match.group(1)
                    current_relay['ipv6_reachable'] = True
                    self.ipv6_testing_authorities.add(result['authority_name'])
                continue
            
            # Parse 's' line (flags)
            if line.startswith('s ') and current_relay:
                flags = line[2:].split()
                current_relay['flags'] = flags
                continue
            
            # Parse 'w' line (bandwidth)
            if line.startswith('w ') and current_relay:
                # w Bandwidth=XXX [Measured=YYY] [Unmeasured=1]
                bw_match = re.search(r'Bandwidth=(\d+)', line)
                if bw_match:
                    current_relay['bandwidth'] = int(bw_match.group(1))
                
                measured_match = re.search(r'Measured=(\d+)', line)
                if measured_match:
                    current_relay['measured'] = int(measured_match.group(1))
                
                unmeasured_match = re.search(r'Unmeasured=1', line)
                if unmeasured_match:
                    current_relay['measured'] = None  # Explicitly unmeasured
                continue
            
            # Parse stats line (wfu, tk, mtbf)
            if line.startswith('stats ') and current_relay:
                # stats wfu=0.999 tk=86400 mtbf=123456
                wfu_match = re.search(r'wfu=([0-9.]+)', line)
                if wfu_match:
                    current_relay['wfu'] = float(wfu_match.group(1))
                
                tk_match = re.search(r'tk=(\d+)', line)
                if tk_match:
                    current_relay['tk'] = int(tk_match.group(1))
                
                mtbf_match = re.search(r'mtbf=(\d+)', line)
                if mtbf_match:
                    current_relay['mtbf'] = int(mtbf_match.group(1))
                continue
            
            # End of router section markers
            if line.startswith('directory-footer') or line.startswith('directory-signature'):
                in_router_section = False
                current_relay = None
        
        return result
    
    def _parse_flag_thresholds(self, line: str) -> dict:
        """
        Parse flag-thresholds line from vote.
        
        Format: flag-thresholds stable-uptime=X stable-mtbf=Y fast-speed=Z guard-wfu=W guard-tk=T guard-bw-inc-exits=B guard-bw-exc-exits=C ...
        """
        thresholds = {}
        
        # Remove 'flag-thresholds ' prefix
        content = line.replace('flag-thresholds ', '').strip()
        
        # Parse key=value pairs
        for pair in content.split():
            if '=' in pair:
                key, value = pair.split('=', 1)
                try:
                    # Try to parse as number
                    if '.' in value or '%' in value.replace('%', ''):
                        thresholds[key] = float(value.replace('%', ''))
                    else:
                        thresholds[key] = int(value)
                except ValueError:
                    thresholds[key] = value
        
        return thresholds
    
    def _fetch_all_bandwidth_files(self) -> Dict[str, dict]:
        """
        Fetch and parse bandwidth measurement files.
        
        Returns:
            dict: Authority name → bandwidth data
        """
        bw_files = self._fetch_bandwidth_listing()
        if not bw_files:
            logger.info("No bandwidth files found (normal for non-BW authorities)")
            return {}
        
        # Get latest bandwidth file for each authority
        latest_bw = {}
        for filename in bw_files:
            # Extract authority from filename
            match = re.match(r'[0-9-]+-bandwidth-([^.]+)', filename, re.IGNORECASE)
            if match:
                auth_id = match.group(1)
                if auth_id not in latest_bw or filename > latest_bw[auth_id]:
                    latest_bw[auth_id] = filename
        
        bandwidth_data = {}
        
        for auth_id, filename in latest_bw.items():
            try:
                url = f"{COLLECTOR_BASE}{BANDWIDTH_PATH}{filename}"
                content = self._fetch_url(url)
                parsed = self._parse_bandwidth_file(content)
                if parsed:
                    bandwidth_data[auth_id] = parsed
            except Exception as e:
                logger.warning(f"Failed to fetch bandwidth file {filename}: {e}")
        
        logger.info(f"Parsed {len(bandwidth_data)} bandwidth files")
        return bandwidth_data
    
    def _parse_bandwidth_file(self, content: str) -> Optional[dict]:
        """
        Parse a bandwidth measurement file.
        
        Returns:
            dict: Fingerprint → measured bandwidth
        """
        if not content:
            return None
        
        result = {
            'relays': {},
            'timestamp': None,
        }
        
        for line in content.split('\n'):
            # Skip header lines and empty lines
            if not line or line.startswith('#') or '=' not in line:
                continue
            
            # Format: bw=XXX node_id=FINGERPRINT ...
            bw_match = re.search(r'bw=(\d+)', line)
            fp_match = re.search(r'node_id=\$?([A-F0-9]{40})', line, re.IGNORECASE)
            
            if bw_match and fp_match:
                fingerprint = fp_match.group(1).upper()
                bandwidth = int(bw_match.group(1))
                result['relays'][fingerprint] = bandwidth
        
        return result
    
    def _build_relay_index(self):
        """
        Build indexed relay data from parsed votes.
        Creates O(1) lookup structure for relay diagnostics.
        """
        self.relay_index = {}
        
        for auth_name, vote_data in self.votes.items():
            if not vote_data or 'relays' not in vote_data:
                continue
            
            for fingerprint, relay_data in vote_data['relays'].items():
                if not self._validate_fingerprint(fingerprint):
                    continue
                
                if fingerprint not in self.relay_index:
                    self.relay_index[fingerprint] = {
                        'fingerprint': fingerprint,
                        'nickname': relay_data.get('nickname', 'Unknown'),
                        'votes': {},
                        'bandwidth_measurements': {},
                    }
                
                # Store vote data from this authority
                self.relay_index[fingerprint]['votes'][auth_name] = {
                    'flags': relay_data.get('flags', []),
                    'bandwidth': relay_data.get('bandwidth'),
                    'measured': relay_data.get('measured'),
                    'wfu': relay_data.get('wfu'),
                    'tk': relay_data.get('tk'),
                    'mtbf': relay_data.get('mtbf'),
                    'ipv4_address': relay_data.get('ipv4_address'),
                    'ipv6_address': relay_data.get('ipv6_address'),
                    'ipv6_reachable': relay_data.get('ipv6_reachable'),
                }
        
        # Add bandwidth measurements from bandwidth files
        for auth_id, bw_data in self.bandwidth_files.items():
            if not bw_data or 'relays' not in bw_data:
                continue
            
            for fingerprint, bandwidth in bw_data['relays'].items():
                if fingerprint in self.relay_index:
                    self.relay_index[fingerprint]['bandwidth_measurements'][auth_id] = bandwidth
        
        logger.info(f"Indexed {len(self.relay_index)} relays from votes")
    
    def _extract_flag_thresholds(self):
        """
        Extract flag thresholds from all authority votes.
        """
        self.flag_thresholds = {}
        
        for auth_name, vote_data in self.votes.items():
            if vote_data and 'flag_thresholds' in vote_data:
                self.flag_thresholds[auth_name] = vote_data['flag_thresholds']
        
        logger.info(f"Extracted flag thresholds from {len(self.flag_thresholds)} authorities")
    
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
        """
        authority_votes = []
        
        for auth_name in sorted(AUTHORITIES.values()):
            vote_info = relay.get('votes', {}).get(auth_name, {})
            
            voted = bool(vote_info)
            flags = vote_info.get('flags', []) if voted else []
            
            authority_votes.append({
                'authority': auth_name,
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
            })
        
        return authority_votes
    
    def _format_time_known(self, seconds: Optional[int]) -> str:
        """Format time known in human-readable format."""
        if seconds is None:
            return 'N/A'
        
        days = seconds / 86400
        if days >= 1:
            return f"{days:.1f} days"
        
        hours = seconds / 3600
        if hours >= 1:
            return f"{hours:.1f} hours"
        
        return f"{seconds} seconds"
    
    def _analyze_flag_eligibility(self, relay: dict) -> dict:
        """
        Analyze flag eligibility across all authorities.
        """
        eligibility = {
            'guard': {'eligible_count': 0, 'details': []},
            'stable': {'eligible_count': 0, 'details': []},
            'fast': {'eligible_count': 0, 'details': []},
            'hsdir': {'eligible_count': 0, 'details': []},
        }
        
        for auth_name, thresholds in self.flag_thresholds.items():
            vote_info = relay.get('votes', {}).get(auth_name, {})
            if not vote_info:
                continue
            
            # Guard flag eligibility
            guard_wfu_threshold = thresholds.get('guard-wfu', 0.98)
            guard_tk_threshold = thresholds.get('guard-tk', 691200)  # 8 days default
            guard_bw_threshold = thresholds.get('guard-bw-inc-exits', 0)
            
            relay_wfu = vote_info.get('wfu', 0)
            relay_tk = vote_info.get('tk', 0)
            relay_bw = vote_info.get('bandwidth', 0)
            
            guard_eligible = (
                relay_wfu >= guard_wfu_threshold and
                relay_tk >= guard_tk_threshold and
                relay_bw >= guard_bw_threshold
            )
            
            if guard_eligible:
                eligibility['guard']['eligible_count'] += 1
            
            eligibility['guard']['details'].append({
                'authority': auth_name,
                'eligible': guard_eligible,
                'wfu_threshold': guard_wfu_threshold,
                'wfu_value': relay_wfu,
                'wfu_met': relay_wfu >= guard_wfu_threshold,
                'tk_threshold': guard_tk_threshold,
                'tk_value': relay_tk,
                'tk_met': relay_tk >= guard_tk_threshold,
                'bw_threshold': guard_bw_threshold,
                'bw_value': relay_bw,
                'bw_met': relay_bw >= guard_bw_threshold,
            })
            
            # Stable flag eligibility
            stable_uptime = thresholds.get('stable-uptime', 0)
            stable_mtbf = thresholds.get('stable-mtbf', 0)
            relay_mtbf = vote_info.get('mtbf', 0)
            
            stable_eligible = relay_mtbf >= stable_mtbf if stable_mtbf > 0 else True
            if stable_eligible:
                eligibility['stable']['eligible_count'] += 1
            
            eligibility['stable']['details'].append({
                'authority': auth_name,
                'eligible': stable_eligible,
                'mtbf_threshold': stable_mtbf,
                'mtbf_value': relay_mtbf,
            })
            
            # Fast flag eligibility
            fast_speed = thresholds.get('fast-speed', 0)
            fast_eligible = relay_bw >= fast_speed
            if fast_eligible:
                eligibility['fast']['eligible_count'] += 1
            
            eligibility['fast']['details'].append({
                'authority': auth_name,
                'eligible': fast_eligible,
                'speed_threshold': fast_speed,
                'speed_value': relay_bw,
            })
            
            # HSDir flag eligibility
            hsdir_wfu = thresholds.get('hsdir-wfu', 0.98)
            hsdir_tk = thresholds.get('hsdir-tk', 691200)
            
            hsdir_eligible = relay_wfu >= hsdir_wfu and relay_tk >= hsdir_tk
            if hsdir_eligible:
                eligibility['hsdir']['eligible_count'] += 1
            
            eligibility['hsdir']['details'].append({
                'authority': auth_name,
                'eligible': hsdir_eligible,
                'wfu_threshold': hsdir_wfu,
                'tk_threshold': hsdir_tk,
            })
        
        return eligibility
    
    def _format_bandwidth(self, relay: dict) -> dict:
        """
        Format bandwidth information from all sources.
        """
        votes = relay.get('votes', {})
        measurements = relay.get('bandwidth_measurements', {})
        
        bandwidth_values = []
        for auth_name, vote in votes.items():
            if vote.get('measured') is not None:
                bandwidth_values.append(vote['measured'])
            elif vote.get('bandwidth') is not None:
                bandwidth_values.append(vote['bandwidth'])
        
        # Add measurements from bandwidth files
        bandwidth_values.extend(measurements.values())
        
        if not bandwidth_values:
            return {'average': None, 'min': None, 'max': None, 'deviation': None}
        
        avg = sum(bandwidth_values) / len(bandwidth_values)
        return {
            'average': avg,
            'min': min(bandwidth_values),
            'max': max(bandwidth_values),
            'deviation': max(bandwidth_values) - min(bandwidth_values) if len(bandwidth_values) > 1 else 0,
            'measurement_count': len(bandwidth_values),
        }
    
    def _format_reachability(self, relay: dict) -> dict:
        """
        Format reachability information across authorities.
        """
        votes = relay.get('votes', {})
        
        ipv4_reachable = []
        ipv6_reachable = []
        ipv6_not_tested = []
        
        for auth_name in sorted(AUTHORITIES.values()):
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
            'total_authorities': len(AUTHORITIES),
        }


def discover_authorities(relays: list) -> list:
    """
    Discover directory authorities from relay list.
    Returns list of authority relay dicts with fingerprints, nicknames, IPs.
    
    Args:
        relays: List of relay dicts from Onionoo
        
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
