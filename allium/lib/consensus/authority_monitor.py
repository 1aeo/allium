"""
File: authority_monitor.py

Monitor directory authority health and status.
Provides latency checks and voting participation metrics.
"""

import urllib.request
import urllib.error
import socket
import time
import concurrent.futures
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Default authority endpoints for latency checks
# Note: These are fallbacks - authorities should be discovered dynamically
DEFAULT_AUTHORITY_ENDPOINTS = {
    'moria1': 'http://128.31.0.39:9131',
    'tor26': 'http://86.59.21.38:80',
    'dizum': 'http://45.66.33.45:80',
    'gabelmoo': 'http://131.188.40.189:80',
    'bastet': 'http://204.13.164.118:80',
    'dannenberg': 'http://193.23.244.244:80',
    'maatuska': 'http://171.25.193.9:443',
    'longclaw': 'http://199.58.81.140:80',
    'faravahar': 'http://154.35.175.225:80',
}


class AuthorityMonitor:
    """
    Monitor directory authority health.
    
    Usage:
        monitor = AuthorityMonitor()
        status = monitor.check_all_authorities()
    """
    
    def __init__(self, timeout: int = 10, authorities: Optional[List[Dict]] = None):
        """
        Initialize AuthorityMonitor.
        
        Args:
            timeout: HTTP request timeout in seconds
            authorities: Optional list of authority dicts with endpoints
        """
        self.timeout = timeout
        self.authorities = authorities or []
        self._last_check = None
        self._cached_status = None
    
    def check_all_authorities(self, force: bool = False) -> Dict[str, dict]:
        """
        Check health of all directory authorities.
        
        Args:
            force: Force fresh check even if cached data is recent
            
        Returns:
            dict: Authority name → health status
        """
        # Use cached data if recent (within 5 minutes)
        if not force and self._cached_status and self._last_check:
            cache_age = (datetime.utcnow() - self._last_check).total_seconds()
            if cache_age < 300:  # 5 minutes
                return self._cached_status
        
        status = {}
        
        # Build endpoint list from authorities or use defaults
        endpoints = self._get_authority_endpoints()
        
        # Check authorities in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=9) as executor:
            future_to_auth = {
                executor.submit(self._check_authority, name, endpoint): name
                for name, endpoint in endpoints.items()
            }
            
            for future in concurrent.futures.as_completed(future_to_auth):
                auth_name = future_to_auth[future]
                try:
                    result = future.result()
                    status[auth_name] = result
                except Exception as e:
                    logger.warning(f"Failed to check {auth_name}: {e}")
                    status[auth_name] = {
                        'online': False,
                        'latency_ms': None,
                        'error': str(e),
                        'checked_at': datetime.utcnow().isoformat(),
                    }
        
        self._cached_status = status
        self._last_check = datetime.utcnow()
        
        return status
    
    def _get_authority_endpoints(self) -> Dict[str, str]:
        """
        Get authority endpoints from discovered authorities or defaults.
        """
        if self.authorities:
            endpoints = {}
            for auth in self.authorities:
                name = auth.get('nickname', '')
                address = auth.get('address', '')
                dir_port = auth.get('dir_port', '80')
                if name and address:
                    endpoints[name] = f"http://{address}:{dir_port}"
            if endpoints:
                return endpoints
        
        return DEFAULT_AUTHORITY_ENDPOINTS
    
    def _check_authority(self, name: str, endpoint: str) -> dict:
        """
        Check a single authority's responsiveness.
        
        Args:
            name: Authority name
            endpoint: Authority endpoint URL
            
        Returns:
            dict: Health status for this authority
        """
        start_time = time.time()
        
        try:
            req = urllib.request.Request(
                f"{endpoint}/tor/status-vote/current/consensus-microdesc",
                headers={'User-Agent': 'Allium/1.0'},
                method='HEAD'  # Only check if reachable, don't download
            )
            
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                latency_ms = (time.time() - start_time) * 1000
                
                return {
                    'online': True,
                    'latency_ms': round(latency_ms, 1),
                    'status_code': response.status,
                    'error': None,
                    'checked_at': datetime.utcnow().isoformat(),
                }
                
        except urllib.error.HTTPError as e:
            latency_ms = (time.time() - start_time) * 1000
            return {
                'online': False,
                'latency_ms': round(latency_ms, 1),
                'status_code': e.code,
                'error': f"HTTP {e.code}",
                'checked_at': datetime.utcnow().isoformat(),
            }
            
        except (urllib.error.URLError, socket.timeout) as e:
            return {
                'online': False,
                'latency_ms': None,
                'status_code': None,
                'error': str(e.reason) if hasattr(e, 'reason') else str(e),
                'checked_at': datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            return {
                'online': False,
                'latency_ms': None,
                'status_code': None,
                'error': str(e),
                'checked_at': datetime.utcnow().isoformat(),
            }
    
    def get_summary(self, status: Optional[Dict[str, dict]] = None) -> dict:
        """
        Get summary of authority health.
        
        Args:
            status: Authority status dict (uses cached if not provided)
            
        Returns:
            dict: Summary statistics
        """
        if status is None:
            status = self._cached_status or self.check_all_authorities()
        
        online_count = sum(1 for s in status.values() if s.get('online'))
        latencies = [s['latency_ms'] for s in status.values() if s.get('latency_ms') is not None]
        
        return {
            'total_authorities': len(status),
            'online_count': online_count,
            'offline_count': len(status) - online_count,
            'average_latency_ms': round(sum(latencies) / len(latencies), 1) if latencies else None,
            'max_latency_ms': max(latencies) if latencies else None,
            'min_latency_ms': min(latencies) if latencies else None,
            'slow_authorities': [
                name for name, s in status.items()
                if s.get('latency_ms') and s['latency_ms'] > 500
            ],
            'offline_authorities': [
                name for name, s in status.items()
                if not s.get('online')
            ],
            'checked_at': self._last_check.isoformat() if self._last_check else None,
        }
    
    def get_alerts(self, status: Optional[Dict[str, dict]] = None) -> List[dict]:
        """
        Get alerts for authority issues.
        
        Args:
            status: Authority status dict (uses cached if not provided)
            
        Returns:
            list: Alert messages
        """
        if status is None:
            status = self._cached_status or self.check_all_authorities()
        
        alerts = []
        
        for name, s in status.items():
            if not s.get('online'):
                alerts.append({
                    'severity': 'error',
                    'authority': name,
                    'message': f"{name} is offline",
                    'details': s.get('error', 'Unknown error'),
                })
            elif s.get('latency_ms') and s['latency_ms'] > 1000:
                alerts.append({
                    'severity': 'warning',
                    'authority': name,
                    'message': f"{name} responding slowly ({s['latency_ms']}ms)",
                    'details': 'Latency exceeds 1000ms threshold',
                })
        
        # Check if too many authorities are down
        offline_count = sum(1 for s in status.values() if not s.get('online'))
        if offline_count >= 3:
            alerts.insert(0, {
                'severity': 'critical',
                'authority': None,
                'message': f"{offline_count}/{len(status)} authorities are offline",
                'details': 'Network consensus may be affected',
            })
        
        return alerts
