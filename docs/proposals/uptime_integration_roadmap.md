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

*[Content continues with remaining 5 ideas...]* 