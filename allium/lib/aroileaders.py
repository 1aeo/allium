"""
File: aroileaders.py

AROI (Authenticated Relay Operator Identifier) Leaderboard calculations
Processes operator rankings based on Onionoo API data grouped by contact information
"""

import hashlib
from collections import defaultdict
import re


def _calculate_aroi_leaderboards(relays_instance):
    """
    Calculate AROI operator leaderboards using current live relay data.
    
    Leverages existing contact-based aggregation from relays.py to generate
    11 core ranking categories with efficient preprocessing for template rendering.
    
    Args:
        relays_instance: Relays object with processed json data including sorted contacts
        
    Returns:
        dict: Leaderboard data optimized for template rendering
    """
    
    if not relays_instance.json or 'sorted' not in relays_instance.json:
        return {}
    
    # Get existing contact-based aggregations (already calculated)
    contacts = relays_instance.json.get('sorted', {}).get('contact', {})
    all_relays = relays_instance.json.get('relays', [])
    
    if not contacts or not all_relays:
        return {}
    
    # Build AROI operator data by processing contacts
    aroi_operators = {}
    
    for contact_hash, contact_data in contacts.items():
        # Get AROI domain and contact info from first relay in this contact group
        relay_indices = contact_data.get('relays', [])
        if not relay_indices:
            continue
            
        first_relay = all_relays[relay_indices[0]]
        aroi_domain = first_relay.get('aroi_domain', 'none')
        contact_info = first_relay.get('contact', '')
        
        # Skip operators without contact information (AROI requires contact info)
        if not contact_info or contact_info.strip() == '':
            continue
        if aroi_domain == 'none' and not contact_info:
            continue
            
        # Use AROI domain as key if available, otherwise use contact hash
        if aroi_domain and aroi_domain != 'none':
            operator_key = aroi_domain
        else:
            operator_key = f"contact_{contact_hash[:8]}"
        
        # Collect relay data for this operator
        operator_relays = [all_relays[i] for i in relay_indices]
        
        # Calculate comprehensive operator metrics
        total_bandwidth = contact_data.get('bandwidth', 0)
        total_consensus_weight = contact_data.get('consensus_weight_fraction', 0.0)
        guard_count = contact_data.get('guard_count', 0)
        exit_count = contact_data.get('exit_count', 0)
        middle_count = contact_data.get('middle_count', 0)
        total_relays = len(operator_relays)
        unique_as_count = contact_data.get('unique_as_count', 0)
        measured_count = contact_data.get('measured_count', 0)
        first_seen = contact_data.get('first_seen', '')
        
        # Calculate geographic and platform diversity
        countries = set(relay.get('country', '') for relay in operator_relays if relay.get('country'))
        platforms = set(relay.get('platform', '') for relay in operator_relays if relay.get('platform'))
        
        # Non-Linux platform detection
        non_linux_relays = [relay for relay in operator_relays 
                          if relay.get('platform') and not relay.get('platform', '').startswith('Linux')]
        
        # BSD platform detection  
        bsd_relays = [relay for relay in operator_relays
                     if relay.get('platform') and any(bsd in relay.get('platform', '') 
                     for bsd in ['BSD', 'FreeBSD', 'OpenBSD', 'NetBSD', 'DragonFly'])]
        
        # Non-EU country detection (simplified)
        eu_countries = {'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 
                       'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 
                       'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'}
        non_eu_relays = [relay for relay in operator_relays 
                        if relay.get('country') and relay.get('country').upper() not in eu_countries]
        
        # Rare/frontier countries (simplified list)
        rare_countries = {'MN', 'TN', 'UY', 'KZ', 'MD', 'LK', 'MK', 'MT', 'EE', 'LV'}
        rare_country_relays = [relay for relay in operator_relays
                              if relay.get('country') and relay.get('country').upper() in rare_countries]
        
        # Calculate diversity score (simplified version)
        diversity_score = 0.0
        if countries:
            diversity_score += len(countries) * 2.0  # Geographic component
        if platforms:
            diversity_score += len(platforms) * 1.5  # Platform component  
        if unique_as_count:
            diversity_score += unique_as_count * 1.0  # Network component
        
        # Calculate uptime approximation (from running status)
        running_relays = sum(1 for relay in operator_relays if relay.get('running', False))
        uptime_percentage = (running_relays / total_relays * 100) if total_relays > 0 else 0.0
        
        # Calculate efficiency ratio (consensus weight to bandwidth)
        efficiency_ratio = 0.0
        if total_bandwidth > 0:
            # Convert bandwidth to approximate consensus weight scale for ratio
            bandwidth_gb = total_bandwidth / (1024 * 1024 * 1024)  # Convert to GB/s
            if bandwidth_gb > 0:
                efficiency_ratio = (total_consensus_weight * 100) / bandwidth_gb
        
        # Store operator data
        aroi_operators[operator_key] = {
            'aroi_domain': aroi_domain,
            'contact_hash': contact_hash,
            'contact_info': contact_info,
            'total_relays': total_relays,
            'total_bandwidth': total_bandwidth,
            'total_consensus_weight': total_consensus_weight,
            'guard_count': guard_count,
            'exit_count': exit_count,
            'middle_count': middle_count,
            'measured_count': measured_count,
            'unique_as_count': unique_as_count,
            'countries': list(countries),
            'country_count': len(countries),
            'platforms': list(platforms),
            'platform_count': len(platforms),
            'non_linux_count': len(non_linux_relays),
            'bsd_count': len(bsd_relays),
            'non_eu_count': len(non_eu_relays),
            'rare_country_count': len(rare_country_relays),
            'diversity_score': diversity_score,
            'uptime_percentage': uptime_percentage,
            'efficiency_ratio': efficiency_ratio,
            'first_seen': first_seen,
            'relays': operator_relays
        }
    
    # Generate 11 core leaderboard categories
    leaderboards = {}
    
    # 1. Bandwidth Contributed
    leaderboards['bandwidth'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['total_bandwidth'],
        reverse=True
    )[:50]  # Top 50 for each category
    
    # 2. Consensus Weight
    leaderboards['consensus_weight'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['total_consensus_weight'],
        reverse=True
    )[:50]
    
    # 3. Exit Operators
    leaderboards['exit_operators'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['exit_count'],
        reverse=True
    )[:50]
    
    # 4. Guard Operators
    leaderboards['guard_operators'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['guard_count'],
        reverse=True
    )[:50]
    
    # 5. Most Diverse Operators
    leaderboards['most_diverse'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['diversity_score'],
        reverse=True
    )[:50]
    
    # 6. Platform Diversity (Non-Linux Heroes)
    leaderboards['platform_diversity'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['non_linux_count'],
        reverse=True
    )[:50]
    
    # 7. Technical Leaders (BSD Operators)
    leaderboards['bsd_operators'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['bsd_count'],
        reverse=True
    )[:50]
    
    # 8. Geographic Champions (Non-EU Leaders)
    leaderboards['non_eu_leaders'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['non_eu_count'],
        reverse=True
    )[:50]
    
    # 9. Frontier Builders (Rare Countries)
    leaderboards['frontier_builders'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['rare_country_count'],
        reverse=True
    )[:50]
    
    # 10. Network Veterans (Most Reliable) 
    leaderboards['network_veterans'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['uptime_percentage'],
        reverse=True
    )[:50]
    
    # 11. Efficiency Champions
    leaderboards['efficiency_champions'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['efficiency_ratio'],
        reverse=True
    )[:50]
    
    # Format data for template rendering with bandwidth units
    formatted_leaderboards = {}
    for category, data in leaderboards.items():
        formatted_data = []
        for rank, (operator_key, metrics) in enumerate(data, 1):
            # Format bandwidth using existing relay formatting methods
            bandwidth_unit = relays_instance._determine_unit(metrics['total_bandwidth'])
            formatted_bandwidth = relays_instance._format_bandwidth_with_unit(
                metrics['total_bandwidth'], bandwidth_unit
            )
            
            formatted_entry = {
                'rank': rank,
                'operator_key': operator_key,
                'aroi_domain': metrics['aroi_domain'],
                'contact_hash': metrics['contact_hash'],
                'contact_info': metrics['contact_info'],
                'total_relays': metrics['total_relays'],
                'total_bandwidth': formatted_bandwidth,
                'bandwidth_unit': bandwidth_unit,
                'total_consensus_weight_pct': f"{metrics['total_consensus_weight'] * 100:.2f}%",
                'guard_count': metrics['guard_count'],
                'exit_count': metrics['exit_count'],
                'middle_count': metrics['middle_count'],
                'measured_count': metrics['measured_count'],
                'unique_as_count': metrics['unique_as_count'],
                'country_count': metrics['country_count'],
                'countries': metrics['countries'][:5],  # Top 5 countries for display
                'platform_count': metrics['platform_count'],
                'platforms': metrics['platforms'][:3],  # Top 3 platforms for display
                'non_linux_count': metrics['non_linux_count'],
                'bsd_count': metrics['bsd_count'],
                'non_eu_count': metrics['non_eu_count'],
                'rare_country_count': metrics['rare_country_count'],
                'diversity_score': f"{metrics['diversity_score']:.1f}",
                'uptime_percentage': f"{metrics['uptime_percentage']:.1f}%",
                'efficiency_ratio': f"{metrics['efficiency_ratio']:.1f}x",
                'first_seen_date': metrics['first_seen'].split(' ')[0] if metrics['first_seen'] else 'Unknown'
            }
            formatted_data.append(formatted_entry)
        
        formatted_leaderboards[category] = formatted_data
    
    # Generate summary statistics
    total_operators = len(aroi_operators)
    total_bandwidth_all = sum(op['total_bandwidth'] for op in aroi_operators.values())
    total_cw_all = sum(op['total_consensus_weight'] for op in aroi_operators.values())
    
    # Format summary bandwidth with unit
    summary_bandwidth_unit = relays_instance._determine_unit(total_bandwidth_all)
    summary_bandwidth_value = relays_instance._format_bandwidth_with_unit(
        total_bandwidth_all, summary_bandwidth_unit
    )
    
    summary_stats = {
        'total_operators': total_operators,
        'total_bandwidth_formatted': f"{summary_bandwidth_value} {summary_bandwidth_unit}",
        'total_consensus_weight_pct': f"{total_cw_all * 100:.1f}%",
        'update_timestamp': relays_instance.timestamp if hasattr(relays_instance, 'timestamp') else 'Unknown',
        'categories': {
            'bandwidth': 'Bandwidth Contributed',
            'consensus_weight': 'Consensus Weight',
            'exit_operators': 'Exit Operators',
            'guard_operators': 'Guard Operators', 
            'most_diverse': 'Most Diverse Operators',
            'platform_diversity': 'Platform Diversity (Non-Linux Heroes)',
            'bsd_operators': 'Technical Leaders (BSD Operators)',
            'non_eu_leaders': 'Geographic Champions (Non-EU Leaders)',
            'frontier_builders': 'Frontier Builders (Rare Countries)',
            'network_veterans': 'Network Veterans (Most Reliable)',
            'efficiency_champions': 'Efficiency Champions'
        }
    }
    
    return {
        'leaderboards': formatted_leaderboards,
        'summary': summary_stats,
        'raw_operators': aroi_operators  # For potential future use
    } 