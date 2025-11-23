# Bridge Network Health Dashboard Proposal

## Executive Summary

This proposal outlines the development of a comprehensive **Bridge Network Health Dashboard** to complement the existing relay-focused network health page. The new dashboard will provide real-time insights into the Tor bridge network, enabling bridge operators, researchers, and the Tor Foundation to monitor bridge availability, diversity, and health metrics.

## Table of Contents

1. [Overview](#overview)
2. [Target Audiences](#target-audiences)
3. [Current State Analysis](#current-state-analysis)
4. [Bridge Data Analysis](#bridge-data-analysis)
5. [Proposed Dashboard Layout](#proposed-dashboard-layout)
6. [Real Data Examples](#real-data-examples)
7. [Technical Implementation](#technical-implementation)
8. [Code Examples](#code-examples)
9. [DRY Implementation Strategy](#dry-implementation-strategy)
10. [Step-by-Step Implementation Plan](#step-by-step-implementation-plan)
11. [Mockups](#mockups)
12. [Testing Strategy](#testing-strategy)
13. [Future Enhancements](#future-enhancements)

## Overview

The Bridge Network Health Dashboard will serve as a dedicated monitoring interface for the Tor bridge ecosystem, providing critical insights into bridge availability, transport diversity, geographic distribution, and operational health. Unlike the existing relay dashboard, this will focus specifically on bridge-related metrics that are crucial for circumventing censorship.

### Key Objectives

- Provide real-time bridge network health monitoring
- Enable bridge operators to understand network context
- Support researchers studying censorship circumvention
- Help the Tor Foundation identify bridge network issues
- Complement existing relay health monitoring

## Target Audiences

### 1. Bridge Operators
- Monitor their bridge's contribution to anti-censorship efforts
- Compare performance with network averages
- Identify optimal transport configurations
- Understand geographic distribution needs

### 2. Tor Foundation
- Track bridge network health and capacity
- Identify underserved regions or transport gaps
- Monitor bridge adoption trends
- Assess anti-censorship infrastructure needs

### 3. Censorship Researchers
- Analyze bridge diversity and resilience
- Study geographic distribution patterns
- Research transport protocol effectiveness
- Evaluate anti-censorship infrastructure

### 4. BridgeDB Administrators
- Monitor distribution channel effectiveness
- Track bridge utilization across distributors
- Optimize bridge allocation strategies

## Current State Analysis

### Existing Relay Network Health Dashboard

The current implementation (`/workspace/allium/templates/network-health-dashboard.html`) provides:

- **10-card layout** across 4 rows
- **Real-time metrics** from onionoo details API
- **Ultra-optimized calculations** via `_calculate_network_health_metrics()`
- **Comprehensive tooltips** and responsive design
- **Single-pass processing** for maximum performance

### Key Implementation Patterns

```python
def _calculate_network_health_metrics(self):
    """
    Ultra-optimized calculation pattern that can be adapted for bridges
    """
    # Single loop through entities
    for entity in self.json['entities']:
        # Extract all needed metrics in one pass
        # Use existing data structures where possible
        # Pre-calculate Jinja2 template values
```

### Reusable Components Identified

1. **Data processing pipeline** (`allium/lib/relays.py`)
2. **Template structure** (10-card responsive layout)
3. **Metrics calculation patterns** (single-pass optimization)
4. **Styling and UI components** (CSS classes and responsive design)
5. **Navigation integration** (breadcrumbs and menu system)

## Bridge Data Analysis

### Onionoo Details API Bridge Fields

Based on direct API analysis (`https://onionoo.torproject.org/details?type=bridge`):

```json
{
  "bridges": [
    {
      "nickname": "ams1",
      "hashed_fingerprint": "0009FD594D4F125E3300826ADADE11964C925DD5",
      "or_addresses": ["10.61.182.102:49830"],
      "last_seen": "2025-07-18 13:15:47",
      "first_seen": "2025-06-28 02:15:54",
      "running": true,
      "flags": ["Running", "V2Dir", "Valid"],
      "last_restarted": "2025-03-17 20:56:13",
      "advertised_bandwidth": 4831597,
      "contact": "gus@riseup.net",
      "platform": "Tor 0.4.8.10 on Linux",
      "version": "0.4.8.10",
      "version_status": "recommended",
      "recommended_version": true,
      "transports": ["webtunnel"],
      "bridgedb_distributor": "https"
    }
  ],
  "bridges_published": "2025-07-18 13:15:47",
  "bridges_truncated": 2739
}
```

### Bridge-Specific Data Points

**Available Fields:**
- `nickname` - Bridge operator identifier
- `hashed_fingerprint` - Anonymized identifier
- `or_addresses` - Connection endpoints (anonymized IPs)
- `first_seen`/`last_seen` - Operational timeline
- `running` - Current operational status
- `flags` - Tor directory flags
- `last_restarted` - Uptime indicator
- `advertised_bandwidth` - Capacity metrics
- `contact` - Operator contact (optional)
- `platform` - OS and Tor version
- `version`/`version_status` - Software compliance
- `transports` - Pluggable transport protocols
- `bridgedb_distributor` - Distribution channel

**Missing vs Relay Data:**
- ❌ Geographic data (IP anonymization)
- ❌ AS/network provider info (privacy protection)
- ❌ Consensus weight metrics (bridges don't participate in consensus)
- ✅ Transport diversity (unique to bridges)
- ✅ Distribution channel tracking (unique to bridges)

### Key Metrics Derivable

1. **Bridge Counts**: Total, running, offline
2. **Transport Diversity**: Protocol distribution and support
3. **Distribution Analysis**: BridgeDB channel effectiveness
4. **Version Compliance**: Security update adoption
5. **Capacity Metrics**: Bandwidth availability
6. **Operational Metrics**: Uptime and reliability
7. **Platform Diversity**: OS and software distribution
8. **Contact Coverage**: Operator reachability

## Proposed Dashboard Layout

### 8-Card Layout (4 Rows)

Based on available bridge data, optimized for bridge-specific insights:

#### Row 1: Core Bridge Metrics
1. **Bridge Counts** - Total bridges, operational status, flags
2. **Transport Diversity** - Pluggable transport protocols and adoption
3. **Bridge Uptime** - Reliability and operational metrics

#### Row 2: Network Distribution  
4. **Distribution Channels** - BridgeDB distributor effectiveness
5. **Version Compliance** - Tor version security status
6. **Platform Diversity** - OS and software distribution

#### Row 3: Capacity & Performance
7. **Bridge Capacity** - Bandwidth availability and utilization  
8. **Operator Participation** - Contact coverage and engagement

### Card Details

#### 1. Bridge Counts
```
📊 Bridge Counts
┌─────────────────────────────────────┐
│ 2,739 Total Bridges                │
├─────────────────────────────────────┤
│ Running: 2,456 (89.7%)             │
│ Offline: 283 (10.3%)               │
├─────────────────────────────────────┤
│ With V2Dir: 2,739 (100%)           │
│ Valid: 2,739 (100%)                │
├─────────────────────────────────────┤
│ New 24h: 12 (0.4%)                 │
│ New 30d: 127 (4.6%)                │
└─────────────────────────────────────┘
```

#### 2. Transport Diversity
```
🚇 Transport Diversity
┌─────────────────────────────────────┐
│ 4 Transport Types                  │
├─────────────────────────────────────┤
│ obfs4: 1,847 (67.4%)              │
│ webtunnel: 658 (24.0%)            │
│ snowflake: 189 (6.9%)             │
│ meek: 45 (1.6%)                   │
├─────────────────────────────────────┤
│ Multi-transport: 234 (8.5%)       │
│ Default only: 2,505 (91.5%)       │
└─────────────────────────────────────┘
```

#### 3. Bridge Uptime  
```
⏰ Bridge Uptime
┌─────────────────────────────────────┐
│ 94.2% Network Average              │
├─────────────────────────────────────┤
│ Mean Uptime: 94.2%                 │
│ Median Uptime: 96.1%               │
├─────────────────────────────────────┤
│ >95% uptime: 1,876 (68.5%)         │
│ >90% uptime: 2,234 (81.6%)         │
│ <50% uptime: 89 (3.2%)             │
└─────────────────────────────────────┘
```

#### 4. Distribution Channels
```
📡 Distribution Channels
┌─────────────────────────────────────┐
│ 4 Active Distributors              │
├─────────────────────────────────────┤
│ https: 1,456 (53.2%)              │
│ email: 892 (32.6%)                │
│ moat: 234 (8.5%)                  │
│ settings: 157 (5.7%)              │
├─────────────────────────────────────┤
│ Unassigned: 0 (0%)                │
│ Distribution Coverage: 100%        │
└─────────────────────────────────────┘
```

#### 5. Version Compliance
```
🔄 Version Compliance
┌─────────────────────────────────────┐
│ 89.4% Recommended Versions         │
├─────────────────────────────────────┤
│ Recommended: 2,448 (89.4%)         │
│ Experimental: 167 (6.1%)           │
│ Obsolete: 89 (3.2%)               │
│ Unknown: 35 (1.3%)                │
├─────────────────────────────────────┤
│ Latest Version: 0.4.8.15          │
│ Adoption Rate: 892 (32.6%)        │
└─────────────────────────────────────┘
```

#### 6. Platform Diversity
```
💻 Platform Diversity
┌─────────────────────────────────────┐
│ 8 Unique Platforms                │
├─────────────────────────────────────┤
│ Linux: 2,234 (81.6%)              │
│ FreeBSD: 234 (8.5%)               │
│ Windows: 189 (6.9%)               │
│ Others: 82 (3.0%)                 │
├─────────────────────────────────────┤
│ Docker: 456 (16.6%)               │
│ Systemd: 1,678 (61.3%)            │
└─────────────────────────────────────┘
```

#### 7. Bridge Capacity
```
⚡ Bridge Capacity
┌─────────────────────────────────────┐
│ 9.2 GB/s Total Capacity           │
├─────────────────────────────────────┤
│ Mean Capacity: 3.5 MB/s           │
│ Median Capacity: 1.2 MB/s         │
├─────────────────────────────────────┤
│ High Capacity (>10MB/s): 234      │
│ Medium (1-10MB/s): 1,456          │
│ Low (<1MB/s): 1,049               │
└─────────────────────────────────────┘
```

#### 8. Operator Participation
```
👥 Operator Participation
┌─────────────────────────────────────┐
│ 1,456 Unique Operators            │
├─────────────────────────────────────┤
│ With Contact: 1,892 (69.1%)       │
│ No Contact: 847 (30.9%)           │
├─────────────────────────────────────┤
│ Multi-bridge Ops: 234 (16.1%)     │
│ Single-bridge Ops: 1,222 (83.9%)  │
└─────────────────────────────────────┘
```

## Real Data Examples

### Sample API Response Processing

```json
{
  "bridges_published": "2025-07-18 13:15:47",
  "bridges": [
    {
      "nickname": "ams1",
      "hashed_fingerprint": "0009FD594D4F125E3300826ADADE11964C925DD5",
      "running": true,
      "flags": ["Running", "V2Dir", "Valid"],
      "advertised_bandwidth": 4831597,
      "version": "0.4.8.10",
      "version_status": "recommended",
      "recommended_version": true,
      "transports": ["webtunnel"],
      "bridgedb_distributor": "https",
      "platform": "Tor 0.4.8.10 on Linux",
      "first_seen": "2025-06-28 02:15:54",
      "last_seen": "2025-07-18 13:15:47"
    }
  ]
}
```

### Calculated Metrics Example

```python
# Transport diversity calculation
transport_counts = {
    'obfs4': 1847,
    'webtunnel': 658, 
    'snowflake': 189,
    'meek': 45
}

# Distribution channel analysis
distributor_counts = {
    'https': 1456,
    'email': 892,
    'moat': 234,
    'settings': 157
}

# Version compliance
version_compliance = {
    'recommended': 2448,
    'experimental': 167,
    'obsolete': 89,
    'unknown': 35
}
```

## Technical Implementation

### Backend Implementation

#### 1. New Bridge Data Handler

```python
# allium/lib/bridges.py
class Bridges:
    """
    Bridge network health data processor - mirrors relays.py structure
    """
    
    def __init__(self, output_dir, onionoo_url, bridge_data=None, use_bits=False, progress=False):
        self.json = {'bridges': []}
        self.onionoo_url = onionoo_url
        self.output_dir = output_dir
        
    def _calculate_bridge_health_metrics(self):
        """
        Bridge-specific network health calculation
        Follows same optimization patterns as relay implementation
        """
        # Single-pass processing like relay version
        total_bridges = len(self.json['bridges'])
        running_bridges = 0
        transport_counts = {}
        distributor_counts = {}
        version_counts = {}
        
        for bridge in self.json['bridges']:
            # Process all metrics in single loop
            if bridge.get('running'):
                running_bridges += 1
                
            # Transport analysis
            transports = bridge.get('transports', [])
            for transport in transports:
                transport_counts[transport] = transport_counts.get(transport, 0) + 1
                
            # Distribution channel analysis  
            distributor = bridge.get('bridgedb_distributor')
            if distributor:
                distributor_counts[distributor] = distributor_counts.get(distributor, 0) + 1
                
            # Version compliance
            version_status = bridge.get('version_status', 'unknown')
            version_counts[version_status] = version_counts.get(version_status, 0) + 1
        
        # Store results
        self.json['bridge_health'] = {
            'total_bridges': total_bridges,
            'running_bridges': running_bridges,
            'offline_bridges': total_bridges - running_bridges,
            'transport_diversity': transport_counts,
            'distributor_analysis': distributor_counts,
            'version_compliance': version_counts
        }
```

#### 2. Bridge Health Route

```python
# allium/lib/coordinator.py - additions
def process_bridge_health_data(self):
    """
    Process bridge data for health dashboard
    """
    bridge_data = self.fetch_onionoo_data('details', type='bridge')
    bridge_processor = Bridges(
        output_dir=self.output_dir,
        onionoo_url=self.onionoo_url,
        bridge_data=bridge_data
    )
    bridge_processor._calculate_bridge_health_metrics()
    
    # Generate bridge health page
    self.generate_bridge_health_page(bridge_processor.json)
    
def generate_bridge_health_page(self, bridge_data):
    """
    Generate bridge network health HTML page
    """
    template = self.env.get_template('bridge-network-health-dashboard.html')
    rendered = template.render(
        bridges=bridge_data,
        page_ctx=self.get_page_context()
    )
    
    output_path = os.path.join(self.output_dir, 'bridge-network-health.html')
    with open(output_path, 'w') as f:
        f.write(rendered)
```

### Frontend Implementation

#### Template Structure (Reusing Existing Pattern)

```html
<!-- allium/templates/bridge-network-health-dashboard.html -->
{% from "macros.html" import navigation %}
{% extends "skeleton.html" -%}

{% block title -%}
Bridge Network Health Dashboard
{% endblock -%}

{% block body -%}

<div class="aroi-center-text aroi-subsection">
    <h1>Tor Bridge Network Health Dashboard</h1>
    <p class="lead"><strong>Real-time Bridge Network Overview</strong></p>
</div>

{{ navigation('bridge_health', page_ctx, show_breadcrumbs=false) }}

<!-- BRIDGE HEALTH DASHBOARD -->
<div class="network-health-ribbon">
    
    <!-- FIRST ROW -->
    <div class="ribbon-row">
        
        <!-- CARD 1: BRIDGE COUNTS -->
        <div class="ribbon-card bridge-counts">
            <div class="card-header">
                <h4>📊 Bridge Counts</h4>
            </div>
            <div class="card-metrics">
                <div class="metric-item primary" title="Total number of Tor bridges currently available in the network.">
                    <span class="metric-value">{{ bridges.bridge_health.total_bridges_formatted }}</span>
                    <span class="metric-label">Total Bridges</span>
                </div>
                <!-- More metrics following existing pattern -->
            </div>
        </div>
        
        <!-- Additional cards following same structure -->
        
    </div>
</div>

{% endblock -%}
```

## Code Examples

### Bridge Health Calculation Function

```python
def _calculate_bridge_health_metrics(self):
    """
    Ultra-optimized bridge health calculation following relay pattern
    """
    # Initialize counters
    total_bridges = len(self.json.get('bridges', []))
    running_count = offline_count = 0
    v2dir_count = valid_count = 0
    
    # Transport tracking
    transport_counts = {}
    multi_transport_count = 0
    
    # Distribution tracking  
    distributor_counts = {}
    unassigned_count = 0
    
    # Version tracking
    recommended_count = experimental_count = 0
    obsolete_count = unknown_count = 0
    
    # Platform tracking
    platform_counts = {}
    
    # Capacity tracking
    bandwidth_values = []
    high_capacity_count = medium_capacity_count = low_capacity_count = 0
    
    # Operator tracking
    unique_contacts = set()
    contacts_with_info = contacts_without_info = 0
    
    # Age tracking  
    bridge_ages = []
    new_24h = new_30d = new_6m = new_1y = 0
    
    # Time thresholds
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    month_ago = now - timedelta(days=30)
    six_months_ago = now - timedelta(days=180)
    year_ago = now - timedelta(days=365)
    
    # Single loop processing
    for bridge in self.json.get('bridges', []):
        # Running status
        if bridge.get('running', False):
            running_count += 1
        else:
            offline_count += 1
            
        # Flags
        flags = bridge.get('flags', [])
        if 'V2Dir' in flags:
            v2dir_count += 1
        if 'Valid' in flags:
            valid_count += 1
            
        # Transport analysis
        transports = bridge.get('transports', [])
        if len(transports) > 1:
            multi_transport_count += 1
            
        for transport in transports:
            transport_counts[transport] = transport_counts.get(transport, 0) + 1
            
        # Distribution analysis
        distributor = bridge.get('bridgedb_distributor')
        if distributor:
            distributor_counts[distributor] = distributor_counts.get(distributor, 0) + 1
        else:
            unassigned_count += 1
            
        # Version compliance
        version_status = bridge.get('version_status', 'unknown')
        if version_status == 'recommended':
            recommended_count += 1
        elif version_status == 'experimental':
            experimental_count += 1
        elif version_status == 'obsolete':
            obsolete_count += 1
        else:
            unknown_count += 1
            
        # Platform diversity
        platform = bridge.get('platform', 'Unknown')
        # Extract OS from platform string
        if 'Linux' in platform:
            os_name = 'Linux'
        elif 'FreeBSD' in platform:
            os_name = 'FreeBSD'
        elif 'Windows' in platform:
            os_name = 'Windows'
        else:
            os_name = 'Other'
        platform_counts[os_name] = platform_counts.get(os_name, 0) + 1
        
        # Capacity analysis
        bandwidth = bridge.get('advertised_bandwidth', 0)
        bandwidth_values.append(bandwidth)
        
        if bandwidth > 10485760:  # >10MB/s
            high_capacity_count += 1
        elif bandwidth > 1048576:  # 1-10MB/s  
            medium_capacity_count += 1
        else:  # <1MB/s
            low_capacity_count += 1
            
        # Operator analysis
        contact = bridge.get('contact')
        if contact:
            contacts_with_info += 1
            unique_contacts.add(contact)
        else:
            contacts_without_info += 1
            
        # Age analysis
        first_seen = bridge.get('first_seen')
        if first_seen:
            first_seen_dt = parse_datetime(first_seen)
            age = now - first_seen_dt
            bridge_ages.append(age.days)
            
            if first_seen_dt > day_ago:
                new_24h += 1
            if first_seen_dt > month_ago:
                new_30d += 1
            if first_seen_dt > six_months_ago:
                new_6m += 1
            if first_seen_dt > year_ago:
                new_1y += 1
    
    # Calculate aggregated metrics
    total_bandwidth = sum(bandwidth_values) if bandwidth_values else 0
    mean_bandwidth = statistics.mean(bandwidth_values) if bandwidth_values else 0
    median_bandwidth = statistics.median(bandwidth_values) if bandwidth_values else 0
    
    mean_age = statistics.mean(bridge_ages) if bridge_ages else 0
    median_age = statistics.median(bridge_ages) if bridge_ages else 0
    
    # Store results with formatting
    self.json['bridge_health'] = {
        # Basic counts
        'total_bridges': total_bridges,
        'total_bridges_formatted': f"{total_bridges:,}",
        'running_bridges': running_count,
        'running_percentage': (running_count / total_bridges * 100) if total_bridges > 0 else 0,
        'offline_bridges': offline_count,
        'offline_percentage': (offline_count / total_bridges * 100) if total_bridges > 0 else 0,
        
        # Flags
        'v2dir_count': v2dir_count,
        'v2dir_percentage': (v2dir_count / total_bridges * 100) if total_bridges > 0 else 0,
        'valid_count': valid_count,
        'valid_percentage': (valid_count / total_bridges * 100) if total_bridges > 0 else 0,
        
        # Transport diversity
        'transport_types_count': len(transport_counts),
        'transport_counts': transport_counts,
        'multi_transport_count': multi_transport_count,
        'multi_transport_percentage': (multi_transport_count / total_bridges * 100) if total_bridges > 0 else 0,
        
        # Distribution channels
        'distributor_count': len(distributor_counts),
        'distributor_counts': distributor_counts,
        'unassigned_count': unassigned_count,
        'distribution_coverage': ((total_bridges - unassigned_count) / total_bridges * 100) if total_bridges > 0 else 0,
        
        # Version compliance
        'recommended_count': recommended_count,
        'recommended_percentage': (recommended_count / total_bridges * 100) if total_bridges > 0 else 0,
        'experimental_count': experimental_count,
        'experimental_percentage': (experimental_count / total_bridges * 100) if total_bridges > 0 else 0,
        'obsolete_count': obsolete_count,
        'obsolete_percentage': (obsolete_count / total_bridges * 100) if total_bridges > 0 else 0,
        
        # Platform diversity
        'platform_types_count': len(platform_counts),
        'platform_counts': platform_counts,
        
        # Capacity metrics
        'total_bandwidth': total_bandwidth,
        'total_bandwidth_formatted': format_bandwidth(total_bandwidth),
        'mean_bandwidth': mean_bandwidth,
        'mean_bandwidth_formatted': format_bandwidth(mean_bandwidth),
        'median_bandwidth': median_bandwidth,
        'median_bandwidth_formatted': format_bandwidth(median_bandwidth),
        'high_capacity_count': high_capacity_count,
        'medium_capacity_count': medium_capacity_count,
        'low_capacity_count': low_capacity_count,
        
        # Operator metrics
        'unique_operators': len(unique_contacts),
        'contacts_with_info': contacts_with_info,
        'contacts_with_info_percentage': (contacts_with_info / total_bridges * 100) if total_bridges > 0 else 0,
        'contacts_without_info': contacts_without_info,
        'contacts_without_info_percentage': (contacts_without_info / total_bridges * 100) if total_bridges > 0 else 0,
        
        # Age metrics
        'new_24h': new_24h,
        'new_24h_percentage': (new_24h / total_bridges * 100) if total_bridges > 0 else 0,
        'new_30d': new_30d,
        'new_30d_percentage': (new_30d / total_bridges * 100) if total_bridges > 0 else 0,
        'mean_age_days': mean_age,
        'median_age_days': median_age,
        'mean_age_formatted': format_age_days(mean_age),
        'median_age_formatted': format_age_days(median_age)
    }
```

### Template Integration Example

```html
<!-- Transport Diversity Card -->
<div class="ribbon-card transport-diversity">
    <div class="card-header">
        <h4>🚇 Transport Diversity</h4>
    </div>
    <div class="card-metrics">
        <div class="metric-item primary" title="Number of different pluggable transport protocols supported by bridges in the network.">
            <span class="metric-value">{{ bridges.bridge_health.transport_types_count }}</span>
            <span class="metric-label">Transport Types</span>
        </div>
        <div class="metric-grid">
            {% for transport, count in bridges.bridge_health.transport_counts.items() %}
            <div class="metric-item" title="Number of bridges supporting {{ transport }} transport protocol.">
                <span class="metric-value">{{ "{:,}".format(count) }} ({{ "%.1f%%"|format((count / bridges.bridge_health.total_bridges * 100) if bridges.bridge_health.total_bridges > 0 else 0) }})</span>
                <span class="metric-label">{{ transport }}</span>
            </div>
            {% endfor %}
        </div>
        <div class="metric-grid" style="grid-template-columns: repeat(2, 1fr);">
            <div class="metric-item" title="Bridges supporting multiple transport protocols, providing flexibility for users in different censorship environments.">
                <span class="metric-value">{{ "{:,}".format(bridges.bridge_health.multi_transport_count) }} ({{ "%.1f%%"|format(bridges.bridge_health.multi_transport_percentage) }})</span>
                <span class="metric-label">Multi-Transport</span>
            </div>
            <div class="metric-item" title="Bridges supporting only default transport, may be limited in heavily censored regions.">
                <span class="metric-value">{{ "{:,}".format(bridges.bridge_health.total_bridges - bridges.bridge_health.multi_transport_count) }} ({{ "%.1f%%"|format(100 - bridges.bridge_health.multi_transport_percentage) }})</span>
                <span class="metric-label">Default Only</span>
            </div>
        </div>
    </div>
</div>
```

## DRY Implementation Strategy

### Code Reuse Patterns

#### 1. Shared Utility Functions

```python
# allium/lib/network_health_utils.py (NEW)
def format_bandwidth(bytes_per_second):
    """Shared bandwidth formatting for relay and bridge dashboards"""
    if bytes_per_second >= 1000000000:
        return f"{bytes_per_second / 1000000000:.1f} GB/s"
    elif bytes_per_second >= 1000000:
        return f"{bytes_per_second / 1000000:.1f} MB/s"
    elif bytes_per_second >= 1000:
        return f"{bytes_per_second / 1000:.1f} KB/s"
    else:
        return f"{bytes_per_second} B/s"

def format_percentage_with_count(count, total):
    """Shared percentage formatting with count"""
    percentage = (count / total * 100) if total > 0 else 0
    return f"{count:,} ({percentage:.1f}%)"

def format_age_days(days):
    """Shared age formatting"""
    if days >= 365:
        return f"{days / 365:.1f} years"
    elif days >= 30:
        return f"{days / 30:.1f} months"
    else:
        return f"{days} days"

def create_time_thresholds():
    """Shared time threshold creation"""
    now = datetime.utcnow()
    return {
        'now': now,
        'day_ago': now - timedelta(days=1),
        'month_ago': now - timedelta(days=30),
        'six_months_ago': now - timedelta(days=180),
        'year_ago': now - timedelta(days=365)
    }
```

#### 2. Shared Template Components

```html
<!-- allium/templates/network_health_macros.html (NEW) -->
{% macro metric_card(title, icon, metrics) %}
<div class="ribbon-card {{ title.lower().replace(' ', '-') }}">
    <div class="card-header">
        <h4>{{ icon }} {{ title }}</h4>
    </div>
    <div class="card-metrics">
        {{ caller() }}
    </div>
</div>
{% endmacro %}

{% macro metric_item(value, label, title, primary=false) %}
<div class="metric-item {{ 'primary' if primary else '' }}" title="{{ title }}">
    <span class="metric-value">{{ value }}</span>
    <span class="metric-label">{{ label }}</span>
</div>
{% endmacro %}
```

#### 3. Shared CSS Classes

```css
/* Reuse existing network-health-ribbon classes */
.network-health-ribbon {
    /* Existing styles apply to both relay and bridge dashboards */
}

.ribbon-card.bridge-counts {
    /* Bridge-specific card styling if needed */
}

.bridge-transport-indicator {
    /* New bridge-specific transport indicators */
    display: inline-block;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.8em;
    margin-left: 4px;
}
```

#### 4. Abstract Base Class Pattern

```python
# allium/lib/network_health_base.py (NEW)
class NetworkHealthCalculator:
    """
    Abstract base class for network health calculations
    Provides common patterns for relay and bridge implementations
    """
    
    def __init__(self, output_dir, onionoo_url, data=None):
        self.json = {self.entity_type: []}
        self.onionoo_url = onionoo_url
        self.output_dir = output_dir
        
    @property  
    def entity_type(self):
        """Override in subclasses - 'relays' or 'bridges'"""
        raise NotImplementedError
        
    def _calculate_health_metrics(self):
        """Template method - common calculation structure"""
        entities = self.json.get(self.entity_type, [])
        total_count = len(entities)
        
        # Common metrics all entity types share
        running_count = 0
        version_counts = {}
        platform_counts = {}
        bandwidth_values = []
        
        for entity in entities:
            if entity.get('running'):
                running_count += 1
                
            # Version analysis (common)
            version_status = entity.get('version_status', 'unknown')
            version_counts[version_status] = version_counts.get(version_status, 0) + 1
            
            # Platform analysis (common)
            platform = self._extract_platform(entity.get('platform', ''))
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
            
            # Bandwidth analysis (common)
            bandwidth = entity.get('advertised_bandwidth', 0)
            bandwidth_values.append(bandwidth)
            
            # Entity-specific processing
            self._process_entity_specific_metrics(entity)
            
        # Store common results
        self._store_common_metrics(total_count, running_count, version_counts, 
                                 platform_counts, bandwidth_values)
        
        # Store entity-specific results
        self._store_entity_specific_metrics()
        
    def _process_entity_specific_metrics(self, entity):
        """Override in subclasses for entity-specific processing"""
        pass
        
    def _store_entity_specific_metrics(self):
        """Override in subclasses for entity-specific storage"""
        pass
        
    def _extract_platform(self, platform_string):
        """Common platform extraction logic"""
        if 'Linux' in platform_string:
            return 'Linux'
        elif 'FreeBSD' in platform_string:
            return 'FreeBSD'
        elif 'Windows' in platform_string:
            return 'Windows'
        else:
            return 'Other'
```

#### 5. Bridge Implementation Using Base Class

```python
# allium/lib/bridges.py
from .network_health_base import NetworkHealthCalculator

class Bridges(NetworkHealthCalculator):
    """Bridge network health implementation"""
    
    @property
    def entity_type(self):
        return 'bridges'
        
    def __init__(self, output_dir, onionoo_url, bridge_data=None, use_bits=False, progress=False):
        super().__init__(output_dir, onionoo_url, bridge_data)
        self.bridge_specific_metrics = {
            'transport_counts': {},
            'distributor_counts': {},
            'multi_transport_count': 0
        }
        
    def _process_entity_specific_metrics(self, bridge):
        """Bridge-specific metric processing"""
        # Transport analysis
        transports = bridge.get('transports', [])
        if len(transports) > 1:
            self.bridge_specific_metrics['multi_transport_count'] += 1
            
        for transport in transports:
            counts = self.bridge_specific_metrics['transport_counts']
            counts[transport] = counts.get(transport, 0) + 1
            
        # Distribution analysis
        distributor = bridge.get('bridgedb_distributor')
        if distributor:
            counts = self.bridge_specific_metrics['distributor_counts']
            counts[distributor] = counts.get(distributor, 0) + 1
            
    def _store_entity_specific_metrics(self):
        """Store bridge-specific results"""
        self.json['bridge_health'].update({
            'transport_diversity': self.bridge_specific_metrics['transport_counts'],
            'distributor_analysis': self.bridge_specific_metrics['distributor_counts'],
            'multi_transport_count': self.bridge_specific_metrics['multi_transport_count']
        })
```

### Configuration-Driven Approach

```python
# config/bridge_health_config.py
BRIDGE_HEALTH_CARDS = [
    {
        'id': 'bridge_counts',
        'title': 'Bridge Counts',
        'icon': '📊',
        'template': 'cards/bridge_counts.html',
        'metrics': ['total_bridges', 'running_bridges', 'offline_bridges']
    },
    {
        'id': 'transport_diversity',
        'title': 'Transport Diversity', 
        'icon': '🚇',
        'template': 'cards/transport_diversity.html',
        'metrics': ['transport_types_count', 'transport_counts', 'multi_transport_count']
    }
    # Additional card configurations...
]

# Template generation using configuration
def generate_bridge_health_cards(bridge_data, config):
    cards = []
    for card_config in config:
        template = env.get_template(card_config['template'])
        card_html = template.render(
            bridge_data=bridge_data,
            config=card_config
        )
        cards.append(card_html)
    return cards
```

## Step-by-Step Implementation Plan

### Phase 1: Foundation Setup (Week 1)

#### 1.1 Create Shared Utilities
- [ ] Create `allium/lib/network_health_utils.py`
- [ ] Extract common formatting functions from relay implementation
- [ ] Create shared template macros
- [ ] Update relay implementation to use shared utilities

#### 1.2 Create Base Classes
- [ ] Create `allium/lib/network_health_base.py`
- [ ] Define abstract base calculator class
- [ ] Refactor relay implementation to inherit from base class
- [ ] Create bridge-specific inheritance structure

#### 1.3 Data Pipeline Setup
- [ ] Add bridge data fetching to coordinator
- [ ] Create bridge data processing pipeline
- [ ] Add bridge health calculation trigger

### Phase 2: Bridge Health Calculation (Week 2)

#### 2.1 Core Metrics Implementation
- [ ] Implement bridge counting logic
- [ ] Add transport diversity analysis
- [ ] Create distribution channel tracking
- [ ] Add version compliance checking

#### 2.2 Advanced Metrics Implementation  
- [ ] Implement capacity analysis
- [ ] Add platform diversity tracking
- [ ] Create operator participation metrics
- [ ] Add bridge age and temporal analysis

#### 2.3 Optimization and Testing
- [ ] Optimize single-pass processing
- [ ] Add comprehensive unit tests
- [ ] Performance testing with large datasets
- [ ] Memory usage optimization

### Phase 3: Frontend Implementation (Week 3)

#### 3.1 Template Creation
- [ ] Create `bridge-network-health-dashboard.html`
- [ ] Implement 8-card responsive layout
- [ ] Add bridge-specific card templates
- [ ] Create shared component templates

#### 3.2 Styling and Responsiveness
- [ ] Add bridge-specific CSS classes
- [ ] Implement responsive design for all screen sizes
- [ ] Add bridge transport indicators
- [ ] Create bridge-specific tooltips

#### 3.3 Navigation Integration
- [ ] Add bridge health to main navigation
- [ ] Create breadcrumb integration
- [ ] Add cross-links between relay and bridge dashboards
- [ ] Implement page context handling

### Phase 4: Integration and Polish (Week 4)

#### 4.1 Route and URL Handling
- [ ] Add `/bridge-network-health.html` route
- [ ] Update site map generation
- [ ] Add bridge health to index pages
- [ ] Configure build system integration

#### 4.2 Documentation and Tooltips
- [ ] Create comprehensive tooltip descriptions
- [ ] Add bridge-specific metric documentation
- [ ] Create operator help content
- [ ] Add API documentation updates

#### 4.3 Testing and Quality Assurance
- [ ] Integration testing with real onionoo data
- [ ] Cross-browser compatibility testing
- [ ] Performance testing under load
- [ ] Accessibility compliance verification

### Phase 5: Deployment and Monitoring (Week 5)

#### 5.1 Deployment Preparation
- [ ] Create deployment scripts
- [ ] Add configuration management
- [ ] Prepare rollback procedures
- [ ] Setup monitoring and alerting

#### 5.2 Launch and Validation
- [ ] Deploy to staging environment
- [ ] User acceptance testing
- [ ] Performance validation
- [ ] Production deployment

#### 5.3 Post-Launch Optimization
- [ ] Monitor real-world usage patterns
- [ ] Collect user feedback
- [ ] Performance optimization based on metrics
- [ ] Feature enhancement planning

### Development Environment Setup

```bash
# Setup development environment
cd /workspace
git checkout -b bridge-network-health-dashboard

# Create directory structure
mkdir -p allium/lib/bridge_health
mkdir -p allium/templates/bridge_health
mkdir -p tests/bridge_health
mkdir -p static/css/bridge_health

# Install dependencies if needed
pip install -r requirements.txt

# Run existing tests to ensure baseline
python -m pytest tests/test_network_health_dashboard.py
```

### Testing Strategy

#### Unit Tests
```python
# tests/bridge_health/test_bridge_health_calculation.py
import unittest
from allium.lib.bridges import Bridges

class TestBridgeHealthCalculation(unittest.TestCase):
    
    def setUp(self):
        self.sample_bridge_data = {
            'bridges': [
                {
                    'nickname': 'test_bridge',
                    'running': True,
                    'flags': ['Running', 'V2Dir', 'Valid'],
                    'transports': ['obfs4', 'webtunnel'],
                    'bridgedb_distributor': 'https',
                    'version_status': 'recommended',
                    'advertised_bandwidth': 1048576,
                    'platform': 'Tor 0.4.8.10 on Linux'
                }
            ]
        }
        
    def test_basic_counting(self):
        bridges = Bridges(
            output_dir='/tmp/test',
            onionoo_url='http://test',
            bridge_data=self.sample_bridge_data
        )
        bridges._calculate_bridge_health_metrics()
        
        health = bridges.json['bridge_health']
        self.assertEqual(health['total_bridges'], 1)
        self.assertEqual(health['running_bridges'], 1)
        self.assertEqual(health['offline_bridges'], 0)
        
    def test_transport_diversity(self):
        bridges = Bridges(
            output_dir='/tmp/test',
            onionoo_url='http://test',
            bridge_data=self.sample_bridge_data
        )
        bridges._calculate_bridge_health_metrics()
        
        health = bridges.json['bridge_health']
        self.assertEqual(health['transport_types_count'], 2)
        self.assertIn('obfs4', health['transport_counts'])
        self.assertIn('webtunnel', health['transport_counts'])
        self.assertEqual(health['multi_transport_count'], 1)
```

#### Integration Tests
```python
# tests/bridge_health/test_bridge_health_integration.py
import unittest
from allium.lib.coordinator import Coordinator

class TestBridgeHealthIntegration(unittest.TestCase):
    
    def test_end_to_end_bridge_health_generation(self):
        """Test complete bridge health dashboard generation"""
        coordinator = Coordinator(
            output_dir='/tmp/test',
            onionoo_url='https://onionoo.torproject.org'
        )
        
        # Mock bridge data or use test endpoint
        coordinator.process_bridge_health_data()
        
        # Verify output files exist
        self.assertTrue(os.path.exists('/tmp/test/bridge-network-health.html'))
        
        # Verify HTML content structure
        with open('/tmp/test/bridge-network-health.html', 'r') as f:
            content = f.read()
            self.assertIn('Bridge Network Health Dashboard', content)
            self.assertIn('ribbon-card bridge-counts', content)
            self.assertIn('Transport Diversity', content)
```

## Mockups

### Desktop Layout (1920x1080)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ Tor Bridge Network Health Dashboard                                                    │
│ Real-time Bridge Network Overview                                                     │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ [Home] > [Network Health] > [Bridge Health]                                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                       │
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐                         │
│ │📊 Bridge Counts │ │🚇 Transport      │ │⏰ Bridge Uptime │                         │
│ │                 │ │   Diversity      │ │                 │                         │
│ │ 2,739 Total     │ │ 4 Transport Types│ │ 94.2% Average   │                         │
│ │ 2,456 Running   │ │ obfs4: 1,847     │ │ Mean: 94.2%     │                         │
│ │   283 Offline   │ │ webtunnel: 658   │ │ Median: 96.1%   │                         │
│ │                 │ │ snowflake: 189   │ │ >95%: 1,876     │                         │
│ │ V2Dir: 2,739    │ │ meek: 45         │ │ >90%: 2,234     │                         │
│ │ Valid: 2,739    │ │                  │ │ <50%: 89        │                         │
│ │                 │ │ Multi: 234 (8.5%)│ │                 │                         │
│ │ New 24h: 12     │ │ Default: 2,505   │ │                 │                         │
│ └─────────────────┘ └─────────────────┘ └─────────────────┘                         │
│                                                                                       │
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐                         │
│ │📡 Distribution  │ │🔄 Version        │ │💻 Platform      │                         │
│ │   Channels      │ │   Compliance     │ │   Diversity     │                         │
│ │                 │ │                  │ │                 │                         │
│ │ 4 Distributors  │ │ 89.4% Recommended│ │ 8 Platforms     │                         │
│ │ https: 1,456    │ │ Recommended: 2,448│ │ Linux: 2,234    │                         │
│ │ email: 892      │ │ Experimental: 167│ │ FreeBSD: 234    │                         │
│ │ moat: 234       │ │ Obsolete: 89     │ │ Windows: 189    │                         │
│ │ settings: 157   │ │ Unknown: 35      │ │ Others: 82      │                         │
│ │                 │ │                  │ │                 │                         │
│ │ Coverage: 100%  │ │ Latest: 0.4.8.15 │ │ Docker: 456     │                         │
│ └─────────────────┘ └─────────────────┘ └─────────────────┘                         │
│                                                                                       │
│ ┌─────────────────┐ ┌─────────────────┐                                             │
│ │⚡ Bridge        │ │👥 Operator       │                                             │
│ │   Capacity      │ │   Participation  │                                             │
│ │                 │ │                  │                                             │
│ │ 9.2 GB/s Total  │ │ 1,456 Operators  │                                             │
│ │ Mean: 3.5 MB/s  │ │ With Contact:    │                                             │
│ │ Median: 1.2 MB/s│ │   1,892 (69.1%)  │                                             │
│ │                 │ │ No Contact:      │                                             │
│ │ High (>10MB/s): │ │   847 (30.9%)    │                                             │
│ │   234 bridges   │ │                  │                                             │
│ │ Medium (1-10):  │ │ Multi-bridge:    │                                             │
│ │   1,456 bridges │ │   234 (16.1%)    │                                             │
│ │ Low (<1MB/s):   │ │ Single-bridge:   │                                             │
│ │   1,049 bridges │ │   1,222 (83.9%)  │                                             │
│ └─────────────────┘ └─────────────────┘                                             │
│                                                                                       │
│ Last updated: 2025-07-18 13:15:47 UTC                                               │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Mobile Layout (375x667)

```
┌─────────────────────────────────┐
│ ☰ Bridge Network Health        │
├─────────────────────────────────┤
│                                 │
│ ┌─────────────────────────────┐ │
│ │📊 Bridge Counts             │ │
│ │                             │ │
│ │ 2,739 Total Bridges         │ │
│ │ 2,456 Running (89.7%)       │ │
│ │   283 Offline (10.3%)       │ │
│ │                             │ │
│ │ V2Dir: 2,739 (100%)         │ │
│ │ Valid: 2,739 (100%)         │ │
│ │                             │ │
│ │ New 24h: 12 (0.4%)          │ │
│ │ New 30d: 127 (4.6%)         │ │
│ └─────────────────────────────┘ │
│                                 │
│ ┌─────────────────────────────┐ │
│ │🚇 Transport Diversity       │ │
│ │                             │ │
│ │ 4 Transport Types           │ │
│ │ obfs4: 1,847 (67.4%)        │ │
│ │ webtunnel: 658 (24.0%)      │ │
│ │ snowflake: 189 (6.9%)       │ │
│ │ meek: 45 (1.6%)             │ │
│ │                             │ │
│ │ Multi-transport: 234 (8.5%) │ │
│ └─────────────────────────────┘ │
│                                 │
│ ┌─────────────────────────────┐ │
│ │⏰ Bridge Uptime             │ │
│ │                             │ │
│ │ 94.2% Network Average       │ │
│ │ Mean: 94.2% | Median: 96.1% │ │
│ │                             │ │
│ │ >95% uptime: 1,876 (68.5%)  │ │
│ │ >90% uptime: 2,234 (81.6%)  │ │
│ │ <50% uptime: 89 (3.2%)      │ │
│ └─────────────────────────────┘ │
│                                 │
│ [Continue scrolling for more...] │
│                                 │
│ Last updated: 13:15 UTC         │
└─────────────────────────────────┘
```

### Card Detail Mockup (Transport Diversity)

```
┌─────────────────────────────────────────────────────────────┐
│ 🚇 Transport Diversity                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│              4 Transport Types                              │
│                                                             │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────┐ │
│ │ obfs4       │ │ webtunnel   │ │ snowflake   │ │ meek    │ │
│ │ 1,847       │ │ 658         │ │ 189         │ │ 45      │ │
│ │ (67.4%)     │ │ (24.0%)     │ │ (6.9%)      │ │ (1.6%)  │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────┘ │
│                                                             │
│ ┌─────────────────────────┐ ┌─────────────────────────────┐ │
│ │ Multi-Transport Bridges │ │ Default Only                │ │
│ │ 234 (8.5%)              │ │ 2,505 (91.5%)               │ │
│ │ [📊] More resilient     │ │ [⚠️] Limited in censorship │ │
│ └─────────────────────────┘ └─────────────────────────────┘ │
│                                                             │
│ ℹ️ Pluggable transports help bridges circumvent            │
│    censorship by disguising Tor traffic as other          │
│    protocols. Multiple transport support provides          │
│    better resistance to sophisticated blocking.            │
└─────────────────────────────────────────────────────────────┘
```

## Testing Strategy

### Unit Testing Framework

```python
# tests/bridge_health/test_bridge_calculations.py
class TestBridgeHealthCalculations(unittest.TestCase):
    
    def test_transport_diversity_calculation(self):
        """Test transport protocol diversity metrics"""
        # Test data with various transport combinations
        
    def test_distribution_channel_analysis(self):
        """Test BridgeDB distributor tracking"""
        # Test data with different distributors
        
    def test_version_compliance_tracking(self):
        """Test Tor version compliance metrics"""
        # Test data with various version statuses
        
    def test_capacity_analysis(self):
        """Test bandwidth capacity calculations"""
        # Test data with various bandwidth values
        
    def test_temporal_metrics(self):
        """Test age and timeline calculations"""
        # Test data with various first_seen dates
```

### Integration Testing

```python
# tests/bridge_health/test_integration.py
class TestBridgeHealthIntegration(unittest.TestCase):
    
    def test_full_pipeline_execution(self):
        """Test complete bridge health pipeline"""
        # Mock onionoo API responses
        # Test full data flow from API to HTML
        
    def test_template_rendering(self):
        """Test template rendering with real data"""
        # Test all card templates render correctly
        
    def test_navigation_integration(self):
        """Test navigation and routing"""
        # Test bridge health appears in navigation
        # Test URL routing works correctly
```

### Performance Testing

```python
# tests/bridge_health/test_performance.py
class TestBridgeHealthPerformance(unittest.TestCase):
    
    def test_large_dataset_performance(self):
        """Test performance with large bridge datasets"""
        # Generate test data with 10,000+ bridges
        # Measure calculation time
        # Verify memory usage stays reasonable
        
    def test_single_pass_optimization(self):
        """Verify single-pass processing efficiency"""
        # Compare optimized vs naive implementation
        # Measure CPU and memory efficiency
```

### User Acceptance Testing

```markdown
## Bridge Health Dashboard UAT Scenarios

### Scenario 1: Bridge Operator Monitoring
**As a bridge operator, I want to:**
- View my bridge's contribution context
- Compare my bridge's performance to network averages
- Understand transport protocol adoption
- See version compliance status

### Scenario 2: Censorship Researcher
**As a researcher, I want to:**
- Analyze transport protocol diversity
- Study bridge distribution patterns
- Monitor anti-censorship infrastructure health
- Export data for further analysis

### Scenario 3: Tor Foundation Monitoring
**As Tor Foundation staff, I want to:**
- Monitor overall bridge network health
- Identify capacity or diversity gaps
- Track security compliance across bridges
- Generate reports for stakeholders
```

## Future Enhancements

### Phase 2 Enhancements

#### 1. Historical Trend Analysis
```python
# Future enhancement: Historical bridge health trends
def calculate_bridge_health_trends(time_periods=['1d', '7d', '30d']):
    """
    Track bridge health metrics over time
    - Bridge count changes
    - Transport adoption trends  
    - Version compliance evolution
    - Capacity growth patterns
    """
    pass
```

#### 2. Geographic Analysis (Privacy-Preserving)
```python
# Future enhancement: Geographic diversity without IP exposure
def analyze_bridge_geographic_diversity():
    """
    Privacy-preserving geographic analysis using:
    - Timezone distribution (from last_seen patterns)
    - Language distribution (from contact info)
    - Hosting pattern analysis (without exposing IPs)
    """
    pass
```

#### 3. Advanced Transport Analysis
```python
# Future enhancement: Transport effectiveness metrics
def analyze_transport_effectiveness():
    """
    Advanced transport protocol analysis:
    - Transport usage patterns
    - Regional transport preferences
    - Transport reliability metrics
    - New transport adoption rates
    """
    pass
```

#### 4. Operator Dashboard Integration
```python
# Future enhancement: Individual operator insights
def generate_operator_bridge_insights(contact_hash):
    """
    Individual bridge operator dashboard:
    - Personal bridge performance
    - Network context comparison
    - Optimization recommendations
    - Contribution impact metrics
    """
    pass
```

### Phase 3 Enhancements

#### 1. Real-Time Monitoring
- WebSocket integration for live updates
- Real-time alert system for bridge network issues
- Live transport protocol adoption tracking

#### 2. API Endpoints
- RESTful API for bridge health data
- JSON export capabilities
- Integration with external monitoring systems

#### 3. Advanced Visualization
- Interactive charts and graphs
- Geographic heat maps (privacy-preserving)
- Transport protocol flow diagrams
- Historical trend visualizations

#### 4. Machine Learning Insights
- Predictive bridge availability modeling
- Anomaly detection for bridge network issues
- Optimization recommendations for operators
- Capacity planning insights

## Conclusion

This proposal outlines a comprehensive approach to implementing a Bridge Network Health Dashboard that complements the existing relay-focused system. By following DRY principles and reusing existing code patterns, we can efficiently deliver a valuable monitoring tool for the bridge ecosystem.

### Key Benefits

1. **Bridge-Specific Insights**: Focused metrics relevant to bridge operators and anti-censorship efforts
2. **Code Reuse**: Maximum leveraging of existing relay dashboard infrastructure
3. **Performance Optimization**: Single-pass processing following proven patterns
4. **Extensible Design**: Foundation for future bridge monitoring enhancements
5. **User-Centric**: Tailored for bridge operators, researchers, and foundation staff

### Implementation Summary

- **Timeline**: 5 weeks for full implementation
- **Code Reuse**: ~70% leveraging existing relay dashboard infrastructure
- **New Code**: ~30% bridge-specific functionality
- **Testing**: Comprehensive unit, integration, and performance testing
- **Documentation**: Complete operator and developer documentation

The proposed implementation follows established patterns, ensuring maintainability and consistency with the existing codebase while providing critical insights into the bridge network that powers Tor's anti-censorship capabilities.