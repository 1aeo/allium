# Milestone 2: Directory Authority & Consensus Health

**Timeline**: Q2 2025 (12 weeks)  
**Priority**: High Value  
**Status**: Architecture Planned  
**Lead Feature**: Network Infrastructure Monitoring

---

## 🎯 Milestone Overview

Provide comprehensive monitoring and analysis of Tor's directory authority infrastructure, enabling proactive network health management and transparency into consensus formation processes.

### Success Criteria
- [ ] Real-time directory authority status monitoring
- [ ] Consensus health tracking with historical analysis
- [ ] Authority performance analytics and alerting
- [ ] Integration with existing multi-API architecture
- [ ] <5s data refresh cycles for critical health metrics

---

## 🚀 Top 3 Priority Features

### Feature 2.1: Directory Authority Status Dashboard
**Implementation Priority**: 1 (Critical)  
**Estimated Effort**: 4 weeks  
**Dependencies**: Multi-API implementation (existing), CollecTor integration

#### Visual Mockup
```
┌─────────────────────────────────────────────────────────────┐
│ 🏛️ Directory Authority Health Dashboard                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ │
│ │   Consensus     │ │   Authority     │ │   Network       │ │
│ │   Status        │ │   Voting        │ │   Agreement     │ │
│ │                 │ │                 │ │                 │ │
│ │   ✅ CURRENT    │ │   9/9 ACTIVE    │ │   99.2% SYNC    │ │
│ │   Fresh: 14:32  │ │   Last Vote:    │ │   8.9/9 Auth    │ │
│ │   Next: 15:00   │ │   All Recent    │ │   Agreement     │ │
│ └─────────────────┘ └─────────────────┘ └─────────────────┘ │
│                                                             │
│ Directory Authorities Status:                               │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ moria1        🟢 Online   Vote: ✅  Scan: ✅  DL: 12ms  │ │
│ │ tor26         🟢 Online   Vote: ✅  Scan: ✅  DL: 8ms   │ │
│ │ dizum         🟢 Online   Vote: ✅  Scan: ✅  DL: 15ms  │ │
│ │ gabelmoo      🟢 Online   Vote: ✅  Scan: ✅  DL: 11ms  │ │
│ │ dannenberg    🟢 Online   Vote: ✅  Scan: ✅  DL: 19ms  │ │
│ │ maatuska      🟢 Online   Vote: ✅  Scan: ✅  DL: 7ms   │ │
│ │ faravahar     🟡 Slow     Vote: ✅  Scan: ⚠️   DL: 89ms  │ │
│ │ longclaw      🟢 Online   Vote: ✅  Scan: ✅  DL: 14ms  │ │
│ │ bastet        🟢 Online   Vote: ✅  Scan: ✅  DL: 16ms  │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Recent Consensus Events:                                    │
│ • 14:32 - Consensus published successfully (9/9 authorities)│
│ • 14:31 - Voting round completed in 127 seconds            │
│ • 14:29 - All authorities synchronized                      │
│                                                             │
│ ⚠️  Alerts: faravahar bandwidth scanning slower than usual │
└─────────────────────────────────────────────────────────────┘
```

#### Sample Implementation
```python
# File: allium/lib/authority_monitor.py

import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class DirectoryAuthorityMonitor:
    """Monitor directory authority health and consensus formation."""
    
    AUTHORITIES = {
        'moria1': {
            'name': 'moria1',
            'address': '128.31.0.34:9131',
            'fingerprint': '9695DFC35FFEB861329B9F1AB04C46397020CE31',
            'operator': 'arma at mit dot edu'
        },
        'tor26': {
            'name': 'tor26', 
            'address': '86.59.21.38:80',
            'fingerprint': '847B1F850344D7876491A54892F904934E4EB85D',
            'operator': 'Peter Lundin'
        },
        'dizum': {
            'name': 'dizum',
            'address': '45.66.33.45:80', 
            'fingerprint': '7EA6EAD6FD83083C538F44038BBFA077587DD755',
            'operator': 'Alex de Joode'
        },
        # ... additional authorities
    }
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.cache_duration = timedelta(minutes=2)
        self._cache = {}
    
    async def get_authority_health_status(self) -> Dict:
        """Get comprehensive directory authority health status."""
        
        # Fetch data from multiple sources in parallel
        consensus_data, authority_votes, network_status = await asyncio.gather(
            self._fetch_current_consensus(),
            self._fetch_authority_votes(),
            self._check_network_connectivity(),
            return_exceptions=True
        )
        
        authority_statuses = await self._check_individual_authorities()
        
        return {
            'summary': {
                'consensus_status': self._analyze_consensus_health(consensus_data),
                'voting_participation': self._analyze_voting_health(authority_votes),
                'network_agreement': self._calculate_network_agreement(authority_votes),
                'last_updated': datetime.utcnow().isoformat()
            },
            'authorities': authority_statuses,
            'consensus_timeline': self._generate_consensus_timeline(consensus_data),
            'alerts': self._generate_health_alerts(authority_statuses, consensus_data)
        }
    
    async def _fetch_current_consensus(self) -> Dict:
        """Fetch current network consensus document."""
        try:
            async with self.session.get(
                'https://collector.torproject.org/recent/relay-descriptors/consensuses/',
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    consensus_text = await response.text()
                    return self._parse_consensus_document(consensus_text)
                return {}
        except Exception as e:
            return {'error': str(e)}
    
    async def _check_individual_authorities(self) -> List[Dict]:
        """Check health status of each directory authority."""
        authority_tasks = []
        
        for auth_id, auth_info in self.AUTHORITIES.items():
            task = self._check_single_authority(auth_id, auth_info)
            authority_tasks.append(task)
        
        results = await asyncio.gather(*authority_tasks, return_exceptions=True)
        
        authority_statuses = []
        for i, result in enumerate(results):
            auth_id = list(self.AUTHORITIES.keys())[i]
            if isinstance(result, Exception):
                status = {
                    'name': auth_id,
                    'status': 'error',
                    'error': str(result),
                    'last_check': datetime.utcnow().isoformat()
                }
            else:
                status = result
            
            authority_statuses.append(status)
        
        return authority_statuses
    
    async def _check_single_authority(self, auth_id: str, auth_info: Dict) -> Dict:
        """Check health status of a single directory authority."""
        start_time = datetime.utcnow()
        
        try:
            # Check directory port connectivity
            dir_url = f"http://{auth_info['address']}/tor/status-vote/current/consensus"
            
            async with self.session.get(
                dir_url,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                status = {
                    'name': auth_id,
                    'display_name': auth_info['name'],
                    'status': 'online' if response.status == 200 else 'degraded',
                    'response_time_ms': round(response_time, 1),
                    'last_check': start_time.isoformat(),
                    'capabilities': {
                        'voting': await self._check_voting_capability(auth_info),
                        'bandwidth_scanning': await self._check_bw_scanning(auth_info),
                        'directory_service': response.status == 200
                    }
                }
                
                # Determine overall health
                if response_time > 1000:  # >1 second is slow
                    status['status'] = 'slow'
                elif not all(status['capabilities'].values()):
                    status['status'] = 'degraded'
                
                return status
                
        except asyncio.TimeoutError:
            return {
                'name': auth_id,
                'display_name': auth_info['name'],
                'status': 'timeout',
                'response_time_ms': None,
                'last_check': start_time.isoformat(),
                'error': 'Connection timeout'
            }
        except Exception as e:
            return {
                'name': auth_id,
                'display_name': auth_info['name'],
                'status': 'offline',
                'response_time_ms': None,
                'last_check': start_time.isoformat(),
                'error': str(e)
            }
    
    def _analyze_consensus_health(self, consensus_data: Dict) -> Dict:
        """Analyze consensus document health."""
        if not consensus_data or 'error' in consensus_data:
            return {
                'status': 'error',
                'message': 'Unable to fetch consensus',
                'freshness': 'unknown'
            }
        
        # Check consensus freshness
        valid_after = consensus_data.get('valid_after')
        fresh_until = consensus_data.get('fresh_until')
        
        now = datetime.utcnow()
        
        if valid_after and fresh_until:
            valid_after_dt = datetime.fromisoformat(valid_after.replace('Z', '+00:00'))
            fresh_until_dt = datetime.fromisoformat(fresh_until.replace('Z', '+00:00'))
            
            if now < valid_after_dt:
                status = 'future'
                message = 'Consensus not yet valid'
            elif now > fresh_until_dt:
                status = 'stale'
                message = 'Consensus is stale'
            else:
                status = 'current'
                message = 'Consensus is current and fresh'
        else:
            status = 'unknown'
            message = 'Unable to determine consensus timing'
        
        return {
            'status': status,
            'message': message,
            'valid_after': valid_after,
            'fresh_until': fresh_until,
            'next_consensus_expected': self._calculate_next_consensus_time(fresh_until)
        }
    
    def _generate_health_alerts(self, authority_statuses: List[Dict], consensus_data: Dict) -> List[Dict]:
        """Generate health alerts based on current status."""
        alerts = []
        
        # Check for offline authorities
        offline_auths = [auth for auth in authority_statuses if auth['status'] in ['offline', 'timeout']]
        if offline_auths:
            alerts.append({
                'level': 'critical' if len(offline_auths) > 2 else 'warning',
                'message': f"{len(offline_auths)} directory authorities are offline: {', '.join([a['name'] for a in offline_auths])}",
                'category': 'authority_connectivity'
            })
        
        # Check for slow authorities
        slow_auths = [auth for auth in authority_statuses if auth['status'] == 'slow']
        if slow_auths:
            alerts.append({
                'level': 'warning',
                'message': f"Slow response from authorities: {', '.join([a['name'] for a in slow_auths])}",
                'category': 'authority_performance'
            })
        
        # Check consensus health
        consensus_health = self._analyze_consensus_health(consensus_data)
        if consensus_health['status'] in ['stale', 'error']:
            alerts.append({
                'level': 'critical',
                'message': f"Consensus issue: {consensus_health['message']}",
                'category': 'consensus_health'
            })
        
        return alerts

# File: allium/lib/consensus_analyzer.py

class ConsensusAnalyzer:
    """Analyze consensus documents for health metrics."""
    
    def __init__(self):
        self.current_consensus = None
        self.consensus_history = []
    
    def analyze_consensus_formation(self, consensus_data: Dict, votes_data: List[Dict]) -> Dict:
        """Analyze the consensus formation process."""
        
        return {
            'formation_metrics': {
                'voting_round_duration': self._calculate_voting_duration(votes_data),
                'authority_agreement': self._calculate_authority_agreement(votes_data),
                'relay_flag_consistency': self._analyze_flag_consistency(votes_data),
                'bandwidth_measurement_variance': self._analyze_bw_variance(votes_data)
            },
            'consensus_quality': {
                'relay_count': consensus_data.get('relay_count', 0),
                'exit_count': len([r for r in consensus_data.get('relays', []) if 'Exit' in r.get('flags', [])]),
                'guard_count': len([r for r in consensus_data.get('relays', []) if 'Guard' in r.get('flags', [])]),
                'consensus_weight_sum': sum(r.get('consensus_weight', 0) for r in consensus_data.get('relays', []))
            },
            'network_health_indicators': {
                'geographic_diversity': self._calculate_geographic_diversity(consensus_data),
                'platform_diversity': self._calculate_platform_diversity(consensus_data),
                'operator_diversity': self._calculate_operator_diversity(consensus_data)
            }
        }
    
    def _calculate_voting_duration(self, votes_data: List[Dict]) -> float:
        """Calculate how long the voting round took."""
        if not votes_data:
            return 0.0
        
        vote_times = [datetime.fromisoformat(vote.get('published', '').replace('Z', '+00:00')) for vote in votes_data if vote.get('published')]
        
        if len(vote_times) < 2:
            return 0.0
        
        return (max(vote_times) - min(vote_times)).total_seconds()
    
    def _calculate_authority_agreement(self, votes_data: List[Dict]) -> float:
        """Calculate how much authorities agree on relay flags."""
        if not votes_data:
            return 0.0
        
        # Simplified agreement calculation
        # In practice, this would compare flags assigned by each authority
        return min(95.0 + len(votes_data), 100.0)  # Placeholder calculation
```

### Feature 2.2: Consensus Health Scraping Integration
**Implementation Priority**: 2 (High)  
**Estimated Effort**: 4 weeks  
**Dependencies**: Consensus health scraping endpoints, caching system

#### Visual Mockup
```
┌─────────────────────────────────────────────────────────────┐
│ 📊 Consensus Health Metrics                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Current Consensus (2025-01-06 15:00:00):                   │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Method: 28              Valid: 15:00-16:00             │ │
│ │ Relays: 8,247           Voting Delay: 300s             │ │
│ │ Authorities: 9/9        Distribution Delay: 300s       │ │
│ │ Bandwidth Sum: 1.2TB/s  Consensus Size: 2.3MB         │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Flag Distribution:                                          │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Running  ████████████████████████████████ 7,234 (87.7%) │ │
│ │ Fast     ████████████████████████████     6,891 (83.6%) │ │
│ │ Stable   ████████████████████████         5,678 (68.9%) │ │
│ │ Guard    ████████████████                 2,845 (34.5%) │ │
│ │ Exit     ███████████                      1,923 (23.3%) │ │
│ │ V2Dir    ████████████████████████████████ 7,156 (86.8%) │ │
│ │ HSDir    ███████████████████████████████  6,987 (84.7%) │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Historical Trends (7 days):                                │
│ Total Relays:     8,247 (+23 from last week)              │
│ Exit Capacity:    847 Gbps (+12.3 Gbps)                   │
│ Guard Capacity:   1.2 Tbps (+45.7 Gbps)                   │
│ Consensus Method: Stable at 28                             │
│                                                             │
│ Quality Indicators:                                         │
│ ✅ Consensus freshness: Excellent                          │
│ ✅ Authority participation: 100%                           │
│ ⚠️  Network diversity: Needs improvement in APAC          │
│ ✅ Exit policy diversity: Good                             │
└─────────────────────────────────────────────────────────────┘
```

#### Sample Implementation
```python
# File: allium/lib/consensus_health_scraper.py

import re
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import aiohttp

class ConsensusHealthScraper:
    """Scrape and analyze consensus health metrics from various sources."""
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.base_urls = [
            'https://collector.torproject.org/recent/relay-descriptors/consensuses/',
            'https://consensus-health.torproject.org/',
            'https://metrics.torproject.org/rs.html'
        ]
    
    async def scrape_consensus_metrics(self) -> Dict:
        """Scrape comprehensive consensus health metrics."""
        
        # Fetch data from multiple sources
        consensus_doc, health_data, metrics_data = await asyncio.gather(
            self._fetch_latest_consensus(),
            self._fetch_consensus_health_page(),
            self._fetch_metrics_data(),
            return_exceptions=True
        )
        
        # Process and combine data
        processed_metrics = {
            'consensus_info': self._process_consensus_document(consensus_doc),
            'flag_distribution': self._calculate_flag_distribution(consensus_doc),
            'network_metrics': self._process_network_metrics(metrics_data),
            'health_indicators': self._process_health_indicators(health_data),
            'historical_trends': await self._calculate_historical_trends(),
            'quality_assessment': self._assess_consensus_quality(consensus_doc, health_data)
        }
        
        return processed_metrics
    
    async def _fetch_latest_consensus(self) -> Optional[str]:
        """Fetch the most recent consensus document."""
        try:
            # Get list of available consensus files
            async with self.session.get(
                f"{self.base_urls[0]}",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    return None
                
                html_content = await response.text()
                
                # Extract the most recent consensus file
                consensus_files = re.findall(r'href="([^"]*consensus[^"]*)"', html_content)
                if not consensus_files:
                    return None
                
                latest_file = sorted(consensus_files)[-1]
                
                # Fetch the actual consensus document
                async with self.session.get(
                    f"{self.base_urls[0]}{latest_file}",
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as consensus_response:
                    if consensus_response.status == 200:
                        return await consensus_response.text()
                    
        except Exception as e:
            print(f"Error fetching consensus: {e}")
            return None
    
    def _process_consensus_document(self, consensus_text: Optional[str]) -> Dict:
        """Process consensus document and extract key information."""
        if not consensus_text:
            return {'error': 'No consensus document available'}
        
        lines = consensus_text.split('\n')
        consensus_info = {}
        
        for line in lines:
            if line.startswith('network-status-version'):
                consensus_info['version'] = line.split()[1]
            elif line.startswith('vote-status'):
                consensus_info['status'] = line.split()[1]
            elif line.startswith('consensus-method'):
                consensus_info['method'] = int(line.split()[1])
            elif line.startswith('valid-after'):
                consensus_info['valid_after'] = ' '.join(line.split()[1:])
            elif line.startswith('fresh-until'):
                consensus_info['fresh_until'] = ' '.join(line.split()[1:])
            elif line.startswith('valid-until'):
                consensus_info['valid_until'] = ' '.join(line.split()[1:])
            elif line.startswith('voting-delay'):
                delays = line.split()[1:]
                consensus_info['voting_delay'] = int(delays[0])
                consensus_info['dist_delay'] = int(delays[1])
        
        # Count relays and calculate basic metrics
        relay_count = len([line for line in lines if line.startswith('r ')])
        bandwidth_lines = [line for line in lines if line.startswith('w ')]
        
        total_bandwidth = 0
        for bw_line in bandwidth_lines:
            if 'Bandwidth=' in bw_line:
                bw_value = re.search(r'Bandwidth=(\d+)', bw_line)
                if bw_value:
                    total_bandwidth += int(bw_value.group(1))
        
        consensus_info.update({
            'relay_count': relay_count,
            'total_bandwidth': total_bandwidth,
            'consensus_size_bytes': len(consensus_text.encode('utf-8')),
            'parsed_at': datetime.utcnow().isoformat()
        })
        
        return consensus_info
    
    def _calculate_flag_distribution(self, consensus_text: Optional[str]) -> Dict:
        """Calculate distribution of relay flags in consensus."""
        if not consensus_text:
            return {}
        
        flag_counts = {
            'Running': 0, 'Fast': 0, 'Stable': 0, 'Valid': 0,
            'Guard': 0, 'Exit': 0, 'Authority': 0, 'V2Dir': 0,
            'HSDir': 0, 'NoEdConsensus': 0, 'Sybil': 0
        }
        
        lines = consensus_text.split('\n')
        total_relays = 0
        
        for line in lines:
            if line.startswith('s '):  # Status line with flags
                flags = line.split()[1:]  # Skip the 's' part
                total_relays += 1
                
                for flag in flags:
                    if flag in flag_counts:
                        flag_counts[flag] += 1
        
        # Calculate percentages
        flag_distribution = {}
        for flag, count in flag_counts.items():
            percentage = (count / total_relays * 100) if total_relays > 0 else 0
            flag_distribution[flag] = {
                'count': count,
                'percentage': round(percentage, 1)
            }
        
        flag_distribution['total_relays'] = total_relays
        return flag_distribution
    
    def _assess_consensus_quality(self, consensus_doc: Optional[str], health_data: any) -> Dict:
        """Assess overall consensus quality and health."""
        quality_indicators = {}
        
        # Assess consensus freshness
        if consensus_doc:
            consensus_info = self._process_consensus_document(consensus_doc)
            
            if 'fresh_until' in consensus_info:
                try:
                    fresh_until = datetime.strptime(consensus_info['fresh_until'], '%Y-%m-%d %H:%M:%S')
                    now = datetime.utcnow()
                    
                    if now < fresh_until:
                        quality_indicators['freshness'] = {
                            'status': 'excellent',
                            'message': 'Consensus is fresh and current'
                        }
                    else:
                        minutes_stale = (now - fresh_until).total_seconds() / 60
                        if minutes_stale < 10:
                            quality_indicators['freshness'] = {
                                'status': 'good',
                                'message': f'Consensus slightly stale ({minutes_stale:.1f} minutes)'
                            }
                        else:
                            quality_indicators['freshness'] = {
                                'status': 'poor',
                                'message': f'Consensus significantly stale ({minutes_stale:.1f} minutes)'
                            }
                except ValueError:
                    quality_indicators['freshness'] = {
                        'status': 'unknown',
                        'message': 'Unable to parse consensus timing'
                    }
        
        # Add additional quality indicators
        quality_indicators.update({
            'authority_participation': {
                'status': 'excellent',  # Placeholder - would check actual authority participation
                'message': '100% authority participation'
            },
            'network_diversity': {
                'status': 'warning', 
                'message': 'Network diversity needs improvement in APAC region'
            },
            'exit_policy_diversity': {
                'status': 'good',
                'message': 'Good variety of exit policies'
            }
        })
        
        return quality_indicators

# Integration with main allium workflow
# File: allium/lib/workers.py (additions)

async def fetch_consensus_health():
    """Worker function to fetch consensus health data."""
    try:
        async with aiohttp.ClientSession() as session:
            scraper = ConsensusHealthScraper(session)
            health_data = await scraper.scrape_consensus_metrics()
            
            # Cache the data
            _save_cache('consensus_health', health_data)
            _mark_ready('consensus_health')
            
            return health_data
            
    except Exception as e:
        error_msg = f"Consensus health scraping failed: {str(e)}"
        _mark_stale('consensus_health', error_msg)
        return _load_cache('consensus_health')  # Return cached data if available
```

### Feature 2.3: Authority Performance Analytics
**Implementation Priority**: 3 (High)  
**Estimated Effort**: 4 weeks  
**Dependencies**: Historical data collection, performance monitoring

#### Visual Mockup
```
┌─────────────────────────────────────────────────────────────┐
│ 📈 Authority Performance Analytics                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Authority Performance Scorecard (30 days):                 │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Authority    Uptime  Votes  BW-Scan  Consensus  Score   │ │
│ │ moria1       99.8%   100%   98.2%    99.1%     ⭐⭐⭐⭐⭐ │ │
│ │ tor26        99.9%   100%   97.8%    99.3%     ⭐⭐⭐⭐⭐ │ │
│ │ dizum        99.4%   99.7%  96.1%    98.9%     ⭐⭐⭐⭐   │ │
│ │ gabelmoo     99.7%   100%   98.9%    99.2%     ⭐⭐⭐⭐⭐ │ │
│ │ dannenberg   99.2%   99.8%  94.3%    98.6%     ⭐⭐⭐⭐   │ │
│ │ maatuska     99.9%   100%   99.1%    99.4%     ⭐⭐⭐⭐⭐ │ │
│ │ faravahar    97.8%   98.9%  89.2%    97.1%     ⭐⭐⭐     │ │
│ │ longclaw     99.5%   100%   97.4%    99.0%     ⭐⭐⭐⭐   │ │
│ │ bastet       99.6%   99.9%  98.7%    99.3%     ⭐⭐⭐⭐⭐ │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Network Impact Analysis:                                    │
│ • Consensus Reliability: 99.4% (Excellent)                │
│ • Authority Redundancy: 9 active authorities (Optimal)     │
│ • Single Point of Failure Risk: Low                        │
│ • Geographic Distribution: 6 countries, 3 continents       │
│                                                             │
│ Performance Trends (7 days):                               │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │    Consensus Success Rate                               │ │
│ │ 100%┌─────────────────────────────────────────────────┐ │ │
│ │  95%│ ████████████████████████████████████████████████│ │ │
│ │  90%│                                                 │ │ │
│ │     └─────────────────────────────────────────────────┘ │ │
│ │      Mon  Tue  Wed  Thu  Fri  Sat  Sun                 │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Recent Events:                                              │
│ • 2025-01-05: faravahar bandwidth scanning performance drop │
│ • 2025-01-03: All authorities synchronized for 48h straight │
│ • 2025-01-01: New Year consensus formation: 127s (Normal)   │
└─────────────────────────────────────────────────────────────┘
```

#### Sample Implementation
```python
# File: allium/lib/authority_analytics.py

from datetime import datetime, timedelta
from typing import Dict, List
import statistics

class AuthorityPerformanceAnalytics:
    """Analyze directory authority performance over time."""
    
    def __init__(self, historical_data: List[Dict]):
        self.historical_data = historical_data
        self.performance_periods = {
            '24h': timedelta(days=1),
            '7d': timedelta(days=7),
            '30d': timedelta(days=30),
            '90d': timedelta(days=90)
        }
    
    def calculate_performance_scorecard(self, period: str = '30d') -> Dict:
        """Calculate comprehensive performance scorecard for all authorities."""
        
        cutoff_date = datetime.utcnow() - self.performance_periods[period]
        relevant_data = [
            record for record in self.historical_data 
            if datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00')) >= cutoff_date
        ]
        
        authority_metrics = {}
        
        for auth_name in self._get_authority_names():
            authority_metrics[auth_name] = self._calculate_authority_metrics(
                auth_name, relevant_data
            )
        
        return {
            'period': period,
            'scorecard': authority_metrics,
            'network_analysis': self._analyze_network_impact(authority_metrics),
            'performance_trends': self._calculate_performance_trends(relevant_data),
            'events': self._extract_notable_events(relevant_data),
            'generated_at': datetime.utcnow().isoformat()
        }
    
    def _calculate_authority_metrics(self, auth_name: str, data: List[Dict]) -> Dict:
        """Calculate performance metrics for a single authority."""
        
        auth_records = [
            record for record in data 
            if record.get('authorities', {}).get(auth_name)
        ]
        
        if not auth_records:
            return {
                'uptime_percentage': 0,
                'vote_participation': 0,
                'bandwidth_scan_success': 0,
                'consensus_agreement': 0,
                'performance_score': 0,
                'status': 'no_data'
            }
        
        # Calculate uptime percentage
        online_count = len([
            r for r in auth_records 
            if r['authorities'][auth_name].get('status') == 'online'
        ])
        uptime_percentage = (online_count / len(auth_records)) * 100
        
        # Calculate vote participation
        voting_records = [
            r for r in auth_records 
            if 'voting' in r['authorities'][auth_name].get('capabilities', {})
        ]
        vote_success = len([
            r for r in voting_records 
            if r['authorities'][auth_name]['capabilities']['voting'] == True
        ])
        vote_participation = (vote_success / len(voting_records)) * 100 if voting_records else 0
        
        # Calculate bandwidth scanning success
        bw_scan_records = [
            r for r in auth_records 
            if 'bandwidth_scanning' in r['authorities'][auth_name].get('capabilities', {})
        ]
        bw_scan_success_count = len([
            r for r in bw_scan_records 
            if r['authorities'][auth_name]['capabilities']['bandwidth_scanning'] == True
        ])
        bw_scan_success = (bw_scan_success_count / len(bw_scan_records)) * 100 if bw_scan_records else 0
        
        # Calculate consensus agreement rate (simplified)
        consensus_agreement = min(95 + uptime_percentage * 0.04, 100)  # Simplified calculation
        
        # Calculate overall performance score
        performance_score = self._calculate_performance_score(
            uptime_percentage, vote_participation, bw_scan_success, consensus_agreement
        )
        
        return {
            'uptime_percentage': round(uptime_percentage, 1),
            'vote_participation': round(vote_participation, 1),
            'bandwidth_scan_success': round(bw_scan_success, 1),
            'consensus_agreement': round(consensus_agreement, 1),
            'performance_score': performance_score,
            'star_rating': self._convert_to_star_rating(performance_score),
            'response_time_avg': self._calculate_avg_response_time(auth_name, auth_records),
            'status': self._determine_overall_status(performance_score)
        }
    
    def _calculate_performance_score(self, uptime: float, voting: float, bw_scan: float, consensus: float) -> int:
        """Calculate weighted performance score (0-100)."""
        
        # Weights for different metrics
        weights = {
            'uptime': 0.30,      # 30% - Core availability
            'voting': 0.25,      # 25% - Consensus participation
            'bw_scan': 0.20,     # 20% - Bandwidth measurement
            'consensus': 0.25    # 25% - Network agreement
        }
        
        weighted_score = (
            uptime * weights['uptime'] +
            voting * weights['voting'] +
            bw_scan * weights['bw_scan'] +
            consensus * weights['consensus']
        )
        
        return round(weighted_score)
    
    def _convert_to_star_rating(self, score: int) -> str:
        """Convert numerical score to star rating."""
        if score >= 98:
            return '⭐⭐⭐⭐⭐'
        elif score >= 95:
            return '⭐⭐⭐⭐'
        elif score >= 90:
            return '⭐⭐⭐'
        elif score >= 80:
            return '⭐⭐'
        else:
            return '⭐'
    
    def _analyze_network_impact(self, authority_metrics: Dict) -> Dict:
        """Analyze overall network impact and health."""
        
        all_scores = [metrics['performance_score'] for metrics in authority_metrics.values()]
        
        # Calculate network reliability
        network_reliability = statistics.mean(all_scores)
        
        # Count active authorities
        active_authorities = len([
            name for name, metrics in authority_metrics.items()
            if metrics['status'] != 'no_data'
        ])
        
        # Assess redundancy
        if active_authorities >= 7:
            redundancy_status = 'excellent'
        elif active_authorities >= 5:
            redundancy_status = 'good'
        else:
            redundancy_status = 'concerning'
        
        # Calculate failure risk
        low_performing = len([
            name for name, metrics in authority_metrics.items()
            if metrics['performance_score'] < 90
        ])
        
        if low_performing == 0:
            failure_risk = 'low'
        elif low_performing <= 2:
            failure_risk = 'moderate'
        else:
            failure_risk = 'high'
        
        return {
            'network_reliability': round(network_reliability, 1),
            'reliability_status': self._get_reliability_status(network_reliability),
            'active_authorities': active_authorities,
            'redundancy_status': redundancy_status,
            'failure_risk': failure_risk,
            'geographic_distribution': self._analyze_geographic_distribution()
        }

    def _get_reliability_status(self, score: float) -> str:
        """Get textual reliability status."""
        if score >= 98:
            return 'Excellent'
        elif score >= 95:
            return 'Very Good'
        elif score >= 90:
            return 'Good'
        elif score >= 80:
            return 'Fair'
        else:
            return 'Poor'
```

---

## 📋 Stack-Ranked Additional Features

### Priority 4: Authority Geolocation Tracking
**Effort**: 2 weeks  
**Impact**: Medium - Geographic distribution visibility
- Map visualization of authority locations
- Geographic diversity analysis
- Regional failure risk assessment

### Priority 5: Consensus Formation Timeline
**Effort**: 3 weeks  
**Impact**: High - Deep consensus process insights
- Step-by-step consensus creation visualization
- Voting round timing analysis
- Authority synchronization tracking

### Priority 6: Authority Communication Analysis
**Effort**: 3 weeks  
**Impact**: Medium - Network partition detection
- Inter-authority communication patterns
- Network partition detection
- Consensus agreement correlation

### Priority 7: Bandwidth Measurement Accuracy Analysis
**Effort**: 2 weeks  
**Impact**: Medium - Network measurement quality
- Authority bandwidth scanning comparison
- Measurement accuracy assessment
- Discrepancy identification and alerts

### Priority 8: Consensus Diff Analysis
**Effort**: 2 weeks  
**Impact**: Low - Change tracking
- Changes between consensus periods
- Relay addition/removal tracking
- Flag change analysis

### Priority 9: Authority Load Balancing Analytics
**Effort**: 2 weeks  
**Impact**: Low - Operational insights
- Request distribution across authorities
- Load balancing effectiveness
- Performance impact analysis

### Priority 10: Historical Authority Events Timeline
**Effort**: 3 weeks  
**Impact**: Medium - Historical perspective
- Timeline of authority changes and incidents
- Major network events correlation
- Long-term trend analysis

### Priority 11: Consensus Validation Tools
**Effort**: 4 weeks  
**Impact**: High - Security and integrity
- Tools for verifying consensus integrity
- Cryptographic signature validation
- Tamper detection capabilities

---

## 🛠️ Technical Implementation Plan

### Week 1-3: Multi-API Integration Foundation
- Integrate with existing multi-API architecture
- Set up CollecTor API connections
- Implement basic authority monitoring

### Week 4-6: Directory Authority Dashboard
- Complete authority status monitoring
- Implement real-time health checks
- Add authority performance tracking

### Week 7-9: Consensus Health Integration
- Build consensus health scraping system
- Implement metrics calculation and analysis
- Add historical trend tracking

### Week 10-12: Performance Analytics & Polish
- Complete authority performance analytics
- Add visualization and reporting features
- Integration testing and optimization

---

*This milestone provides critical infrastructure monitoring capabilities that enable proactive network health management and transparency into Tor's consensus formation process.*