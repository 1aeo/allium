# Tor Relay Uptime Integration Roadmap for Allium

## Executive Summary

This proposal outlines 10 comprehensive ideas for integrating Onionoo API uptime data into the allium Tor relay analytics platform. The integration will provide relay operators with better visibility into their network reliability and help users understand overall Tor network health through detailed uptime analytics.

## Background Analysis

### Current Onionoo Uptime API Structure
- **Endpoint**: `https://onionoo.torproject.org/uptime`
- **Data Format**: Fractional uptime values (0-1) over multiple time periods
- **Time Periods**: 1_month, 6_months, 1_year, 5_years
- **Flag-Specific Uptime**: Running, Guard, Exit, Authority, Fast, Stable
- **Graph History Objects**: Timestamps, intervals, normalized values (0-999)

### Current Allium Uptime Handling
```python
# Basic implementation in aroileaders.py:
running_relays = sum(1 for relay in operator_relays if relay.get('running', False))
uptime_percentage = (running_relays / total_relays * 100) if total_relays > 0 else 0.0
```

## Proposed Uptime Integration Ideas

### 1. Reliability Champions Leaderboard
**Purpose**: New competitive category for most reliable operators

**Technical Implementation**:
```python
# In lib/aroileaders.py - new leaderboard category
def _fetch_uptime_data(self, fingerprints):
    """Fetch uptime data for multiple relays from Onionoo"""
    uptime_url = "https://onionoo.torproject.org/uptime"
    uptime_params = {"lookup": ",".join(fingerprints)}
    
    try:
        response = urllib.request.urlopen(f"{uptime_url}?{urllib.parse.urlencode(uptime_params)}")
        return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Warning: Could not fetch uptime data: {e}")
        return None

def _calculate_reliability_score(self, operator_relays, uptime_data):
    """Calculate comprehensive reliability score"""
    total_weighted_uptime = 0
    total_bandwidth_weight = 0
    
    for relay in operator_relays:
        fingerprint = relay.get('fingerprint', '')
        bandwidth = relay.get('observed_bandwidth', 0)
        
        # Find uptime data for this relay
        relay_uptime = None
        if uptime_data:
            for uptime_relay in uptime_data.get('relays', []):
                if uptime_relay.get('fingerprint') == fingerprint:
                    relay_uptime = uptime_relay
                    break
        
        if relay_uptime and relay_uptime.get('uptime'):
            # Use 6-month uptime as primary metric
            uptime_6m = relay_uptime['uptime'].get('6_months', {})
            if uptime_6m.get('values'):
                # Calculate average uptime from values array
                values = [v for v in uptime_6m['values'] if v is not None]
                if values:
                    avg_uptime = sum(values) / len(values) / 999  # Normalize from 0-999 to 0-1
                    total_weighted_uptime += avg_uptime * bandwidth
                    total_bandwidth_weight += bandwidth
    
    return (total_weighted_uptime / total_bandwidth_weight) if total_bandwidth_weight > 0 else 0

# Add to leaderboards generation:
leaderboards['reliability_champions'] = sorted(
    aroi_operators.items(),
    key=lambda x: x[1]['reliability_score'],
    reverse=True
)[:50]
```

**Template Integration**:
```html
<!-- In aroi-leaderboards.html -->
{{ champion_badge("reliability_champions", relays.json.aroi_leaderboards.leaderboards.reliability_champions, 
   "Reliability Master", "⏰", "panel-success", "aroi-champion-reliability", page_ctx.path_prefix, relays.use_bits) }}

{{ top3_table("Reliability Champions", "⏰", relays.json.aroi_leaderboards.leaderboards.reliability_champions, 
   ["Reliability King", "Reliability Commander", "Reliability Hero"], "reliability_champions", page_ctx, relays.use_bits) }}
```

**Mockup**:
```
┌─────────────────────────────────────────────────────────────┐
│ 🏆 Current World Leaders                                    │
├─────────────────────────────────────────────────────────────┤
│ [Platinum Bandwidth] [Network Authority] [⏰ Reliability Master] │
│                                                             │
│ ⏰ Reliability Master                                        │
│ torworld.example.org                                        │
│ 99.7% Uptime Score                                          │
│ 847 relays • 45.2 Gbit/s                                   │
│ 6-month weighted reliability                                │
└─────────────────────────────────────────────────────────────┘
```

### 2. Individual Relay Uptime History Charts
**Purpose**: Detailed uptime visualization for relay detail pages

**Technical Implementation**:
```python
# In lib/relays.py - enhance relay detail data
def _fetch_relay_uptime_history(self, fingerprint):
    """Fetch detailed uptime history for a single relay"""
    uptime_url = f"https://onionoo.torproject.org/uptime?lookup={fingerprint}"
    
    try:
        response = urllib.request.urlopen(uptime_url)
        uptime_data = json.loads(response.read().decode('utf-8'))
        
        if uptime_data.get('relays'):
            relay_uptime = uptime_data['relays'][0]
            return self._process_uptime_chart_data(relay_uptime)
    except Exception as e:
        print(f"Warning: Could not fetch uptime for {fingerprint}: {e}")
    
    return None

def _process_uptime_chart_data(self, relay_uptime):
    """Convert Onionoo uptime data to chart-ready format"""
    chart_data = {}
    
    if relay_uptime.get('uptime'):
        for period, data in relay_uptime['uptime'].items():
            if data.get('values') and data.get('first') and data.get('interval'):
                # Convert to Chart.js compatible format
                timestamps = []
                values = []
                
                first_timestamp = data['first']
                interval_seconds = data['interval']
                
                for i, value in enumerate(data['values']):
                    if value is not None:
                        timestamp = first_timestamp + (i * interval_seconds * 1000)  # Convert to milliseconds
                        uptime_percentage = (value / 999) * 100  # Convert 0-999 to 0-100%
                        timestamps.append(timestamp)
                        values.append(uptime_percentage)
                
                chart_data[period] = {
                    'labels': timestamps,
                    'data': values,
                    'period_display': period.replace('_', ' ').title()
                }
    
    return chart_data
```

**Template Integration**:
```html
<!-- In relay-info.html -->
{% if relay.uptime_chart_data %}
<div class="panel panel-default">
    <div class="panel-heading">
        <h4 class="panel-title">⏰ Uptime History</h4>
    </div>
    <div class="panel-body">
        <div class="uptime-chart-controls">
            {% for period, data in relay.uptime_chart_data.items() %}
            <button class="btn btn-sm btn-default uptime-period-btn" data-period="{{ period }}">
                {{ data.period_display }}
            </button>
            {% endfor %}
        </div>
        <canvas id="uptimeChart" width="800" height="300"></canvas>
        <script>
        const uptimeData = {{ relay.uptime_chart_data|tojson }};
        // Chart.js implementation for interactive uptime history
        </script>
    </div>
</div>
{% endif %}
```

**Mockup**:
```
┌─────────────────────────────────────────────────────────────┐
│ ⏰ Uptime History                                            │
├─────────────────────────────────────────────────────────────┤
│ [1 Month] [6 Months] [1 Year] [5 Years]                    │
│                                                             │
│ 100% ┌───────────────────────────────────────────────────┐  │
│  95% │     ████████████████████████████████████████████  │  │
│  90% │                                                   │  │
│  85% │                                                   │  │
│  80% │                                                   │  │
│      └───────────────────────────────────────────────────┘  │
│       Jan    Feb    Mar    Apr    May    Jun               │
│                                                             │
│ Average: 98.7% • Current: Online • Last offline: 3 days ago │
└─────────────────────────────────────────────────────────────┘
```

### 3. Network Health Dashboard
**Purpose**: Aggregate network uptime statistics for general users

**Technical Implementation**:
```python
# In lib/relays.py - network-wide health metrics
def _calculate_network_health_metrics(self):
    """Calculate network-wide uptime and health statistics"""
    total_relays = len(self.json.get('relays', []))
    running_relays = sum(1 for r in self.json['relays'] if r.get('running', False))
    
    # Fetch sample of uptime data for network health estimation
    sample_fingerprints = [r['fingerprint'] for r in self.json['relays'][:100]]  # Sample 100 relays
    uptime_data = self._fetch_uptime_data(sample_fingerprints)
    
    network_health = {
        'current_availability': (running_relays / total_relays * 100) if total_relays > 0 else 0,
        'total_relays': total_relays,
        'running_relays': running_relays,
        'offline_relays': total_relays - running_relays,
    }
    
    if uptime_data:
        # Calculate historical reliability from sample
        sample_uptimes = []
        for relay in uptime_data.get('relays', []):
            if relay.get('uptime', {}).get('1_month', {}).get('values'):
                values = [v for v in relay['uptime']['1_month']['values'] if v is not None]
                if values:
                    avg_uptime = sum(values) / len(values) / 999  # Normalize to 0-1
                    sample_uptimes.append(avg_uptime)
        
        if sample_uptimes:
            network_health.update({
                'avg_monthly_uptime': (sum(sample_uptimes) / len(sample_uptimes)) * 100,
                'reliability_distribution': {
                    'excellent': len([u for u in sample_uptimes if u > 0.95]) / len(sample_uptimes) * 100,
                    'good': len([u for u in sample_uptimes if 0.90 <= u <= 0.95]) / len(sample_uptimes) * 100,
                    'fair': len([u for u in sample_uptimes if 0.80 <= u < 0.90]) / len(sample_uptimes) * 100,
                    'poor': len([u for u in sample_uptimes if u < 0.80]) / len(sample_uptimes) * 100,
                }
            })
    
    return network_health
```

**Mockup**:
```
┌─────────────────────────────────────────────────────────────┐
│ 🏥 Tor Network Health Dashboard                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────┐ │
│ │   97.3%     │ │   94.1%     │ │    8,247    │ │  223    │ │
│ │ Current     │ │ 30-Day Avg  │ │   Online    │ │Offline  │ │
│ │Availability │ │   Uptime    │ │   Relays    │ │ Relays  │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────┘ │
│                                                             │
│ 📊 Network Reliability Distribution                         │
│ ████████████████████████ Excellent (>95%): 67.2%           │
│ ████████████ Good (90-95%): 23.1%                          │
│ ██████ Fair (80-90%): 7.8%                                 │
│ ██ Poor (<80%): 1.9%                                       │
│                                                             │
│ ⚡ Recent Trends: Stability improving (+0.3% vs last week) │
└─────────────────────────────────────────────────────────────┘
```

### 4. Flag-Specific Uptime Analysis
**Purpose**: Show Guard/Exit/Authority uptime separately for network role reliability

**Technical Implementation**:
```python
# In lib/relays.py - flag-specific uptime processing
def _process_flag_uptime_data(self, relay_uptime):
    """Process flag-specific uptime data from Onionoo"""
    flag_uptimes = {}
    
    if relay_uptime.get('flags'):
        for flag_name, flag_data in relay_uptime['flags'].items():
            if flag_data.get('1_month', {}).get('values'):
                values = [v for v in flag_data['1_month']['values'] if v is not None]
                if values:
                    avg_uptime = sum(values) / len(values) / 999  # Normalize to 0-1
                    flag_uptimes[flag_name] = {
                        'monthly_uptime': avg_uptime * 100,
                        'role_description': {
                            'Running': 'Basic operational status',
                            'Guard': 'Entry guard availability',
                            'Exit': 'Exit node availability', 
                            'Authority': 'Directory authority uptime',
                            'Fast': 'High-performance availability',
                            'Stable': 'Long-term reliability indicator'
                        }.get(flag_name, f'{flag_name} flag availability')
                    }
    
    return flag_uptimes
```

**Mockup**:
```
┌─────────────────────────────────────────────────────────────┐
│ 🏷️ Role-Specific Reliability                               │
├─────────────────────────────────────────────────────────────┤
│ [Guard]     ████████████████████ 98.7%  Entry guard avail. │
│ [Exit]      ███████████████████  97.2%  Exit node avail.   │
│ [Running]   ████████████████████ 99.1%  Basic operational  │
│ [Fast]      ███████████████████  96.8%  High-performance   │
│ [Stable]    ████████████████████ 99.3%  Long-term reliab.  │
└─────────────────────────────────────────────────────────────┘
```

### 5. Operator Reliability Portfolio
**Purpose**: Comprehensive uptime dashboard for relay operators

**Technical Implementation**:
```python
# In lib/relays.py - operator-specific reliability dashboard
def _generate_operator_reliability_dashboard(self, contact_hash, operator_relays):
    """Generate comprehensive reliability dashboard for an operator"""
    
    fingerprints = [r['fingerprint'] for r in operator_relays]
    uptime_data = self._fetch_uptime_data(fingerprints)
    
    dashboard = {
        'overall_score': 0,
        'relay_reliability': [],
        'trend_analysis': {},
        'recommendations': [],
        'performance_categories': {
            'excellent': 0, 'good': 0, 'fair': 0, 'poor': 0
        }
    }
    
    total_weighted_score = 0
    total_weight = 0
    
    for relay in operator_relays:
        fingerprint = relay['fingerprint']
        bandwidth = relay.get('observed_bandwidth', 0)
        
        relay_reliability = {
            'fingerprint': fingerprint,
            'nickname': relay.get('nickname', 'Unknown'),
            'bandwidth': bandwidth,
            'current_status': relay.get('running', False),
            'uptime_scores': {},
            'reliability_grade': 'Unknown',
            'issues': []
        }
        
        # Find uptime data for this relay
        if uptime_data:
            for uptime_relay in uptime_data.get('relays', []):
                if uptime_relay.get('fingerprint') == fingerprint:
                    # Process different time periods
                    for period in ['1_month', '6_months', '1_year']:
                        if uptime_relay.get('uptime', {}).get(period, {}).get('values'):
                            values = [v for v in uptime_relay['uptime'][period]['values'] if v is not None]
                            if values:
                                avg_uptime = sum(values) / len(values) / 999 * 100
                                relay_reliability['uptime_scores'][period] = avg_uptime
                    
                    # Calculate reliability grade
                    monthly_uptime = relay_reliability['uptime_scores'].get('1_month', 0)
                    if monthly_uptime >= 98:
                        relay_reliability['reliability_grade'] = 'Excellent'
                        dashboard['performance_categories']['excellent'] += 1
                    elif monthly_uptime >= 95:
                        relay_reliability['reliability_grade'] = 'Good'
                        dashboard['performance_categories']['good'] += 1
                    elif monthly_uptime >= 90:
                        relay_reliability['reliability_grade'] = 'Fair'
                        dashboard['performance_categories']['fair'] += 1
                        relay_reliability['issues'].append('Uptime below 95% - consider infrastructure review')
                    else:
                        relay_reliability['reliability_grade'] = 'Poor'
                        dashboard['performance_categories']['poor'] += 1
                        relay_reliability['issues'].append('Critical uptime issues detected')
                    
                    # Add to weighted score
                    total_weighted_score += monthly_uptime * bandwidth
                    total_weight += bandwidth
        
        dashboard['relay_reliability'].append(relay_reliability)
    
    # Calculate overall score
    dashboard['overall_score'] = (total_weighted_score / total_weight) if total_weight > 0 else 0
    
    # Generate recommendations
    poor_count = dashboard['performance_categories']['poor']
    fair_count = dashboard['performance_categories']['fair']
    
    if poor_count > 0:
        dashboard['recommendations'].append(f'🚨 {poor_count} relays have critical uptime issues - immediate attention needed')
    if fair_count > 0:
        dashboard['recommendations'].append(f'⚠️ {fair_count} relays have suboptimal uptime - consider infrastructure review')
    if dashboard['overall_score'] > 98:
        dashboard['recommendations'].append('🏆 Excellent network reliability! Keep up the great work.')
    
    return dashboard
```

**Mockup**:
```
┌─────────────────────────────────────────────────────────────┐
│ 📊 Reliability Dashboard - torworld.example.org            │
├─────────────────────────────────────────────────────────────┤
│                    98.7%                                    │
│           Overall Network Reliability Score                 │
│         Bandwidth-weighted average across all relays        │
│                                                             │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐             │
│ │   43    │ │   12    │ │    3    │ │    1    │             │
│ │Excellent│ │  Good   │ │  Fair   │ │  Poor   │             │
│ └─────────┘ └─────────┘ └─────────┘ └─────────┘             │
│                                                             │
│ 🔍 Individual Relay Analysis:                               │
│ relay01  [Online]  98.7%  97.2%  Excellent  ✓              │
│ relay02  [Online]  97.1%  96.8%  Good      ✓               │
│ relay03  [Offline] 89.2%  91.5%  Fair      ⚠️ Review needed │
│                                                             │
│ 🏆 Recommendations:                                         │
│ ⚠️ 1 relay has suboptimal uptime - consider review         │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Details & Remaining Ideas

*[Content continues with remaining 5 ideas...]* # Uptime Integration Ideas - Part 2 (Ideas 6-10)

## 6. Historical Network Stability Trends
**Purpose**: Long-term trend analysis for understanding network evolution

**Technical Implementation**:
```python
# In lib/relays.py - historical trend analysis
def _analyze_network_stability_trends(self):
    """Analyze long-term network stability trends"""
    
    # Sample relays for trend analysis (top 200 by consensus weight)
    sorted_relays = sorted(self.json['relays'], key=lambda r: r.get('consensus_weight', 0), reverse=True)
    sample_relays = sorted_relays[:200]
    
    fingerprints = [r['fingerprint'] for r in sample_relays]
    uptime_data = self._fetch_uptime_data(fingerprints)
    
    trends = {
        'periods': ['1_month', '6_months', '1_year', '5_years'],
        'network_stability': {},
        'consensus_weight_reliability': {},
        'improvement_declining_relays': {'improving': [], 'declining': []},
        'stability_distribution': {}
    }
    
    if not uptime_data:
        return trends
    
    for period in trends['periods']:
        period_uptimes = []
        weighted_uptimes = []
        total_consensus_weight = 0
        
        for relay in sample_relays:
            fingerprint = relay['fingerprint']
            consensus_weight = relay.get('consensus_weight', 0)
            
            # Find uptime data
            for uptime_relay in uptime_data.get('relays', []):
                if uptime_relay.get('fingerprint') == fingerprint:
                    if uptime_relay.get('uptime', {}).get(period, {}).get('values'):
                        values = [v for v in uptime_relay['uptime'][period]['values'] if v is not None]
                        if values:
                            avg_uptime = sum(values) / len(values) / 999
                            period_uptimes.append(avg_uptime)
                            weighted_uptimes.append(avg_uptime * consensus_weight)
                            total_consensus_weight += consensus_weight
        
        if period_uptimes:
            trends['network_stability'][period] = {
                'average_uptime': (sum(period_uptimes) / len(period_uptimes)) * 100,
                'weighted_average': (sum(weighted_uptimes) / total_consensus_weight) * 100 if total_consensus_weight > 0 else 0,
                'relay_count': len(period_uptimes),
                'std_deviation': _calculate_standard_deviation(period_uptimes) * 100
            }
    
    return trends
```

**Mockup**:
```
┌─────────────────────────────────────────────────────────────┐
│ 📈 Historical Network Stability Trends                     │
├─────────────────────────────────────────────────────────────┤
│ Time Period    Avg Uptime  Weighted  Sample   Variability   │
│ 1 Month        97.8%       98.1%     198      ±2.3%        │
│ 6 Months       96.9%       97.4%     187      ±3.1%        │
│ 1 Year         95.7%       96.8%     156      ±4.2%        │
│ 5 Years        93.2%       94.5%     89       ±6.7%        │
│                                                             │
│ ✅ Trend: Network reliability improving (+1.2% vs 6mo)      │
└─────────────────────────────────────────────────────────────┘
```

## 7. Uptime-Based Relay Recommendations
**Purpose**: Smart relay selection recommendations based on reliability

**Technical Implementation**:
```python
# In lib/relays.py - intelligent relay recommendations
def _generate_reliability_recommendations(self):
    """Generate relay recommendations based on uptime and performance"""
    
    # Get uptime data for top relays by consensus weight
    top_relays = sorted(self.json['relays'], key=lambda r: r.get('consensus_weight', 0), reverse=True)[:500]
    fingerprints = [r['fingerprint'] for r in top_relays]
    uptime_data = self._fetch_uptime_data(fingerprints)
    
    recommendations = {
        'most_reliable_guards': [],
        'most_reliable_exits': [],
        'rising_stars': [],  # Good uptime + newer relays
        'stability_champions': [],  # Excellent long-term uptime
        'recommendations_summary': {}
    }
    
    if not uptime_data:
        return recommendations
    
    relay_reliability_scores = []
    
    for relay in top_relays:
        fingerprint = relay['fingerprint']
        flags = relay.get('flags', [])
        consensus_weight = relay.get('consensus_weight', 0)
        
        # Find uptime data
        reliability_score = None
        long_term_stability = None
        
        for uptime_relay in uptime_data.get('relays', []):
            if uptime_relay.get('fingerprint') == fingerprint:
                # Calculate 1-month reliability score
                if uptime_relay.get('uptime', {}).get('1_month', {}).get('values'):
                    monthly_values = [v for v in uptime_relay['uptime']['1_month']['values'] if v is not None]
                    if monthly_values:
                        reliability_score = sum(monthly_values) / len(monthly_values) / 999
                
                # Calculate long-term stability (1-year if available)
                if uptime_relay.get('uptime', {}).get('1_year', {}).get('values'):
                    yearly_values = [v for v in uptime_relay['uptime']['1_year']['values'] if v is not None]
                    if yearly_values:
                        long_term_stability = sum(yearly_values) / len(yearly_values) / 999
                break
        
        if reliability_score is not None:
            relay_analysis = {
                'relay': relay,
                'reliability_score': reliability_score,
                'long_term_stability': long_term_stability,
                'consensus_weight': consensus_weight,
                'flags': flags
            }
            relay_reliability_scores.append(relay_analysis)
    
    # Sort by reliability score
    relay_reliability_scores.sort(key=lambda r: r['reliability_score'], reverse=True)
    
    # Generate category-specific recommendations
    for relay_data in relay_reliability_scores:
        relay = relay_data['relay']
        score = relay_data['reliability_score']
        flags = relay_data['flags']
        
        if score > 0.98:  # 98%+ uptime
            # Most reliable guards
            if 'Guard' in flags and len(recommendations['most_reliable_guards']) < 20:
                recommendations['most_reliable_guards'].append({
                    'fingerprint': relay['fingerprint'],
                    'nickname': relay.get('nickname', 'Unknown'),
                    'uptime': score * 100,
                    'consensus_weight': relay.get('consensus_weight', 0),
                    'country': relay.get('country', 'Unknown')
                })
            
            # Most reliable exits
            if 'Exit' in flags and len(recommendations['most_reliable_exits']) < 20:
                recommendations['most_reliable_exits'].append({
                    'fingerprint': relay['fingerprint'],
                    'nickname': relay.get('nickname', 'Unknown'),
                    'uptime': score * 100,
                    'consensus_weight': relay.get('consensus_weight', 0),
                    'country': relay.get('country', 'Unknown')
                })
    
    return recommendations
```

**Mockup**:
```
┌─────────────────────────────────────────────────────────────┐
│ 🎯 Reliable Relay Recommendations                           │
├─────────────────────────────────────────────────────────────┤
│ Analysis: 500 top relays analyzed. 87 relays (17.4%)       │
│ maintain excellent reliability (98%+ uptime).               │
│                                                             │
│ 🛡️ Most Reliable Guard Relays                              │
│ RelayGuard01    99.3%  12,547  DE  4A3B...                 │
│ StableEntry     99.1%  9,823   US  7F2C...                 │
│ GuardianNode    98.9%  8,745   NL  A1B2...                 │
│                                                             │
│ 🚪 Most Reliable Exit Relays                               │
│ ExitGate01      99.2%  15,234  SE  3D4E...                 │
│ SafeExit        98.8%  11,456  CH  B5C6...                 │
│ TorExit03       98.7%  9,876   CA  E7F8...                 │
└─────────────────────────────────────────────────────────────┘
```

## 8. Real-time Downtime Alerts Dashboard
**Purpose**: Monitor and display recently offline high-impact relays

**Technical Implementation**:
```python
# In lib/relays.py - downtime monitoring
def _detect_critical_downtimes(self):
    """Detect and analyze critical relay downtimes"""
    
    # Focus on high-impact relays (top 10% by consensus weight)
    total_relays = len(self.json['relays'])
    top_relay_count = max(50, total_relays // 10)  # At least 50, or top 10%
    
    high_impact_relays = sorted(
        self.json['relays'], 
        key=lambda r: r.get('consensus_weight', 0), 
        reverse=True
    )[:top_relay_count]
    
    downtime_alerts = {
        'critical_offline': [],  # High consensus weight relays offline
        'guard_outages': [],     # Important guard relays offline
        'exit_outages': [],      # Important exit relays offline
        'recent_instability': [], # Relays with recent uptime issues
        'impact_analysis': {}
    }
    
    total_offline_consensus_weight = 0
    total_consensus_weight = sum(r.get('consensus_weight', 0) for r in self.json['relays'])
    
    # Analyze current outages
    for relay in high_impact_relays:
        if not relay.get('running', False):
            consensus_weight = relay.get('consensus_weight', 0)
            flags = relay.get('flags', [])
            
            outage_info = {
                'fingerprint': relay['fingerprint'],
                'nickname': relay.get('nickname', 'Unknown'),
                'consensus_weight': consensus_weight,
                'consensus_weight_pct': (consensus_weight / total_consensus_weight * 100) if total_consensus_weight > 0 else 0,
                'flags': flags,
                'last_seen': relay.get('last_seen', 'Unknown'),
                'country': relay.get('country', 'Unknown'),
                'contact': relay.get('contact', 'No contact info')
            }
            
            # Categorize the outage
            if consensus_weight > 1000:  # High-impact threshold
                downtime_alerts['critical_offline'].append(outage_info)
                total_offline_consensus_weight += consensus_weight
            
            if 'Guard' in flags:
                downtime_alerts['guard_outages'].append(outage_info)
            
            if 'Exit' in flags:
                downtime_alerts['exit_outages'].append(outage_info)
    
    # Calculate network impact
    downtime_alerts['impact_analysis'] = {
        'offline_consensus_weight_pct': (total_offline_consensus_weight / total_consensus_weight * 100) if total_consensus_weight > 0 else 0,
        'critical_relays_offline': len(downtime_alerts['critical_offline']),
        'guards_affected': len(downtime_alerts['guard_outages']),
        'exits_affected': len(downtime_alerts['exit_outages']),
        'severity_level': 'critical' if total_offline_consensus_weight / total_consensus_weight > 0.05 else 'moderate' if total_offline_consensus_weight / total_consensus_weight > 0.02 else 'low'
    }
    
    return downtime_alerts
```

**Mockup**:
```
┌─────────────────────────────────────────────────────────────┐
│ 🚨 Network Downtime Alerts                    [LOW IMPACT] │
├─────────────────────────────────────────────────────────────┤
│ Critical Offline: 3  Lost Weight: 1.7%  Guards: 2  Exits: 1│
│                                                             │
│ 🚨 Critical Relays Offline:                                │
│ BigRelay01   [G][E] 2.3% weight  Last seen: 2h ago         │
│ MajorExit    [E]    1.8% weight  Last seen: 6h ago         │
│ GuardNode    [G]    1.1% weight  Last seen: 4h ago         │
│                                                             │
│ 📧 Operator Contacts:                                       │
│ admin@relay01.org (BigRelay01) - Notified 1h ago          │
│ contact@majorexit.net (MajorExit) - No response            │
└─────────────────────────────────────────────────────────────┘
```

## 9. Comparative Uptime Analysis
**Purpose**: Benchmark operator performance against network averages and peers

**Technical Implementation**:
```python
# In lib/relays.py - comparative analysis
def _generate_uptime_benchmarks(self, operator_relays, operator_metrics):
    """Generate benchmarking data for operator performance"""
    
    # Get network-wide benchmark data
    all_relays_sample = self.json['relays'][:500]  # Sample for performance
    fingerprints = [r['fingerprint'] for r in all_relays_sample]
    network_uptime_data = self._fetch_uptime_data(fingerprints)
    
    # Calculate network benchmarks
    network_benchmarks = {
        'percentiles': {'25th': 0, '50th': 0, '75th': 0, '90th': 0, '95th': 0},
        'by_consensus_weight': {'low': 0, 'medium': 0, 'high': 0},
        'by_geography': {},
        'by_flags': {'Guard': 0, 'Exit': 0, 'Middle': 0}
    }
    
    if network_uptime_data:
        # Calculate network uptime percentiles
        network_uptimes = []
        for relay in network_uptime_data.get('relays', []):
            if relay.get('uptime', {}).get('1_month', {}).get('values'):
                values = [v for v in relay['uptime']['1_month']['values'] if v is not None]
                if values:
                    avg_uptime = sum(values) / len(values) / 999
                    network_uptimes.append(avg_uptime)
        
        if network_uptimes:
            sorted_uptimes = sorted(network_uptimes)
            network_benchmarks['percentiles'] = {
                '25th': sorted_uptimes[len(sorted_uptimes) // 4] * 100,
                '50th': sorted_uptimes[len(sorted_uptimes) // 2] * 100,
                '75th': sorted_uptimes[3 * len(sorted_uptimes) // 4] * 100,
                '90th': sorted_uptimes[9 * len(sorted_uptimes) // 10] * 100,
                '95th': sorted_uptimes[19 * len(sorted_uptimes) // 20] * 100
            }
    
    # Calculate operator-specific benchmarks
    operator_fingerprints = [r['fingerprint'] for r in operator_relays]
    operator_uptime_data = self._fetch_uptime_data(operator_fingerprints)
    
    operator_benchmarks = {
        'overall_score': operator_metrics.get('reliability_score', 0) * 100,
        'percentile_ranking': 0,
        'compared_to_network': 'average',
        'improvement_areas': [],
        'strengths': []
    }
    
    # Calculate where operator ranks
    if operator_benchmarks['overall_score'] > network_benchmarks['percentiles']['95th']:
        operator_benchmarks['percentile_ranking'] = 95
        operator_benchmarks['compared_to_network'] = 'exceptional'
        operator_benchmarks['strengths'].append('Top 5% network reliability')
    elif operator_benchmarks['overall_score'] > network_benchmarks['percentiles']['90th']:
        operator_benchmarks['percentile_ranking'] = 90
        operator_benchmarks['compared_to_network'] = 'excellent'
        operator_benchmarks['strengths'].append('Top 10% network reliability')
    elif operator_benchmarks['overall_score'] > network_benchmarks['percentiles']['75th']:
        operator_benchmarks['percentile_ranking'] = 75
        operator_benchmarks['compared_to_network'] = 'above_average'
        operator_benchmarks['strengths'].append('Above average reliability')
    elif operator_benchmarks['overall_score'] > network_benchmarks['percentiles']['50th']:
        operator_benchmarks['percentile_ranking'] = 50
        operator_benchmarks['compared_to_network'] = 'average'
    else:
        operator_benchmarks['compared_to_network'] = 'below_average'
        operator_benchmarks['improvement_areas'].append('Reliability below network median')
    
    return {
        'network_benchmarks': network_benchmarks,
        'operator_benchmarks': operator_benchmarks
    }
```

**Mockup**:
```
┌─────────────────────────────────────────────────────────────┐
│ 📊 Uptime Benchmarking - torworld.example.org              │
├─────────────────────────────────────────────────────────────┤
│ Your Score: 98.7%  Network Ranking: 92nd Percentile        │
│                                                             │
│ Network Comparison:                                         │
│ 95th Percentile: 99.1% ████████████████████ ↑ 0.4%        │
│ 90th Percentile: 98.3% ████████████████████ ✓ You         │
│ 75th Percentile: 96.8% ████████████████████ ↓ 1.9%        │
│ 50th Percentile: 94.2% ████████████████████ ↓ 4.5%        │
│ 25th Percentile: 91.7% ████████████████████ ↓ 7.0%        │
│                                                             │
│ 🏆 Strengths:                                               │
│ • Top 10% network reliability                               │
│ • Consistent performance across all relays                  │
│                                                             │
│ 📈 Improvement Opportunities:                               │
│ • Target 99%+ uptime to reach top 5%                       │
│ • 3 relays below 95% threshold                             │
└─────────────────────────────────────────────────────────────┘
```

## 10. Uptime Prediction Modeling
**Purpose**: Predictive analytics for relay stability and maintenance planning

**Technical Implementation**:
```python
# In lib/relays.py - predictive modeling
def _generate_uptime_predictions(self, operator_relays):
    """Generate uptime predictions and maintenance recommendations"""
    
    fingerprints = [r['fingerprint'] for r in operator_relays]
    uptime_data = self._fetch_uptime_data(fingerprints)
    
    predictions = {
        'relay_predictions': [],
        'maintenance_recommendations': [],
        'risk_assessment': {
            'high_risk_relays': [],
            'trending_down': [],
            'stability_score': 0
        }
    }
    
    if not uptime_data:
        return predictions
    
    for relay in operator_relays:
        fingerprint = relay['fingerprint']
        
        # Find uptime data for this relay
        for uptime_relay in uptime_data.get('relays', []):
            if uptime_relay.get('fingerprint') == fingerprint:
                # Analyze uptime trends
                uptime_trend = self._analyze_uptime_trend(uptime_relay)
                
                relay_prediction = {
                    'fingerprint': fingerprint,
                    'nickname': relay.get('nickname', 'Unknown'),
                    'current_uptime': uptime_trend.get('current_uptime', 0),
                    'trend_direction': uptime_trend.get('trend', 'stable'),
                    'predicted_30day': uptime_trend.get('predicted_30day', 0),
                    'risk_level': uptime_trend.get('risk_level', 'low'),
                    'maintenance_window': uptime_trend.get('maintenance_window', 'none'),
                    'recommendations': uptime_trend.get('recommendations', [])
                }
                
                predictions['relay_predictions'].append(relay_prediction)
                
                # Risk assessment
                if relay_prediction['risk_level'] == 'high':
                    predictions['risk_assessment']['high_risk_relays'].append(relay_prediction)
                elif relay_prediction['trend_direction'] == 'declining':
                    predictions['risk_assessment']['trending_down'].append(relay_prediction)
                
                break
    
    # Generate maintenance recommendations
    predictions['maintenance_recommendations'] = self._generate_maintenance_schedule(predictions['relay_predictions'])
    
    return predictions

def _analyze_uptime_trend(self, uptime_relay):
    """Analyze uptime trend for a single relay"""
    if not uptime_relay.get('uptime', {}).get('1_month', {}).get('values'):
        return {'trend': 'unknown', 'current_uptime': 0}
    
    values = [v for v in uptime_relay['uptime']['1_month']['values'] if v is not None]
    if len(values) < 10:  # Need sufficient data
        return {'trend': 'insufficient_data', 'current_uptime': 0}
    
    # Simple trend analysis
    recent_values = values[-7:]  # Last week
    older_values = values[-21:-14] if len(values) >= 21 else values[:-7]  # Previous week
    
    recent_avg = sum(recent_values) / len(recent_values) / 999 * 100
    older_avg = sum(older_values) / len(older_values) / 999 * 100 if older_values else recent_avg
    
    trend_change = recent_avg - older_avg
    
    trend_analysis = {
        'current_uptime': recent_avg,
        'trend': 'improving' if trend_change > 2 else 'declining' if trend_change < -2 else 'stable',
        'predicted_30day': max(0, min(100, recent_avg + (trend_change * 2))),  # Extrapolate trend
        'risk_level': 'high' if recent_avg < 90 or trend_change < -5 else 'medium' if recent_avg < 95 or trend_change < -2 else 'low',
        'recommendations': []
    }
    
    # Generate recommendations
    if trend_analysis['risk_level'] == 'high':
        trend_analysis['recommendations'].append('Immediate attention required - critical reliability issues')
        trend_analysis['maintenance_window'] = 'urgent'
    elif trend_analysis['trend'] == 'declining':
        trend_analysis['recommendations'].append('Schedule preventive maintenance')
        trend_analysis['maintenance_window'] = 'within_week'
    else:
        trend_analysis['maintenance_window'] = 'normal_schedule'
    
    return trend_analysis
```

**Mockup**:
```
┌─────────────────────────────────────────────────────────────┐
│ 🔮 Uptime Predictions & Maintenance Planning               │
├─────────────────────────────────────────────────────────────┤
│ 📈 Trend Analysis (Next 30 Days):                          │
│                                                             │
│ relay01  98.7% → 98.9% ↗️ [Stable]     Low Risk           │
│ relay02  96.2% → 95.1% ↘️ [Declining]  Medium Risk         │
│ relay03  89.1% → 85.3% ↘️ [Critical]   High Risk           │
│                                                             │
│ 🚨 Risk Assessment:                                         │
│ • 1 relay at high risk (relay03)                           │
│ • 1 relay trending down (relay02)                          │
│ • Overall stability score: 87/100                          │
│                                                             │
│ 🔧 Maintenance Recommendations:                             │
│ • relay03: Urgent attention required                       │
│ • relay02: Schedule maintenance within 1 week              │
│ • relay01: Normal maintenance schedule                      │
│                                                             │
│ 📅 Suggested Maintenance Windows:                           │
│ • This weekend: relay02 (preventive)                       │
│ • ASAP: relay03 (critical)                                 │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Priority & Next Steps

### Phase 1: Foundation (Weeks 1-2)
1. **Reliability Champions Leaderboard** - Core infrastructure
2. **Network Health Dashboard** - Public visibility

### Phase 2: Operator Tools (Weeks 3-4)  
3. **Individual Relay Uptime Charts** - Detailed visibility
4. **Operator Reliability Portfolio** - Operator management

### Phase 3: Advanced Analytics (Weeks 5-6)
5. **Flag-Specific Uptime Analysis** - Role-based insights
6. **Historical Network Stability Trends** - Long-term analysis

### Phase 4: Intelligence Features (Weeks 7-8)
7. **Uptime-Based Relay Recommendations** - User guidance
8. **Real-time Downtime Alerts** - Network monitoring

### Phase 5: Future Features
9. **Comparative Uptime Analysis** - Benchmarking
10. **Uptime Prediction Modeling** - Predictive analytics

## Technical Requirements

### Dependencies
- Enhanced Onionoo API integration
- Chart.js for visualization  
- Additional database fields for caching
- Background processing for data collection

### Performance Considerations
- Cache uptime data to reduce API calls
- Implement progressive loading for large datasets
- Use sampling for network-wide statistics
- Background processing for complex calculations 