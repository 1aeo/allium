"""
File: aroileaders.py

AROI (Authenticated Relay Operator Identifier) Leaderboard calculations
Processes operator rankings based on Onionoo API data grouped by contact information
Reuses existing contact calculations and only computes new metrics not already available
"""

import hashlib
from collections import defaultdict
import re
import html

# Import centralized country utilities
from .country_utils import (
    count_non_eu_countries, 
    count_frontier_countries_weighted_with_existing_data,
    calculate_diversity_score, 
    calculate_geographic_achievement
)


def _format_breakdown_details(breakdown_items, max_chars, formatter_func=None):
    """
    Reusable helper function to format country/item breakdowns with truncation.
    
    Args:
        breakdown_items (list): List of (country, count) tuples, pre-sorted
        max_chars (int): Maximum characters allowed before truncation
        formatter_func (callable): Custom function to format each (count, country) pair
        
    Returns:
        tuple: (formatted_details, tooltip_text)
    """
    if not breakdown_items:
        return "", ""
    
    # Default formatter if none provided
    if formatter_func is None:
        formatter_func = lambda count, country: f"{count} in {country}"
    
    # Create full breakdown for tooltip and short breakdown for display
    full_breakdown = []
    short_breakdown = []
    
    for country, count in breakdown_items:
        detail = formatter_func(count, country)
        full_breakdown.append(detail)
        short_breakdown.append(detail)
    
    tooltip_text = ", ".join(full_breakdown)
    
    # Create short version with truncation
    short_text = ", ".join(short_breakdown)
    if len(short_text) > max_chars:
        # Find the last complete entry that fits
        chars_used = 0
        for i, detail in enumerate(short_breakdown):
            if i > 0:
                chars_used += 2  # for ", "
            if chars_used + len(detail) <= max_chars - 3:  # leave 3 chars for "..."
                chars_used += len(detail)
            else:
                short_breakdown = short_breakdown[:i]
                break
        details_text = ", ".join(short_breakdown) + "..."
    else:
        details_text = short_text
    
    return details_text, tooltip_text

def _calculate_aroi_leaderboards(relays_instance):
    """
    Calculate AROI operator leaderboards using current live relay data.
    
    Leverages existing contact-based aggregations from relays.py to minimize
    duplicate calculations. Only computes new metrics not already available.
    
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
    
    # PERFORMANCE OPTIMIZATION: Pre-calculate rare countries once instead of per-operator
    # This eliminates O(n²) performance where rare countries were calculated 3,123 times
    # Now calculated once and reused, improving performance by ~95%
    country_data = relays_instance.json.get('sorted', {}).get('country', {})
    from .country_utils import get_rare_countries_weighted_with_existing_data
    all_rare_countries = get_rare_countries_weighted_with_existing_data(country_data, len(all_relays))
    valid_rare_countries = {country for country in all_rare_countries if len(country) == 2 and country.isalpha()}
    
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
            
        # Additional validation: skip if contact is just whitespace or very short
        if len(contact_info.strip()) < 3:
            continue
            
        # Use AROI domain as key if available, otherwise use first 10 chars of contact_info
        if aroi_domain and aroi_domain != 'none':
            operator_key = aroi_domain
        else:
            # Use first 16 characters of contact info for better readability
            if contact_info and len(contact_info.strip()) > 0:
                clean_contact = contact_info.strip()
                if len(clean_contact) > 16:
                    operator_key = clean_contact[:16] + '...'
                else:
                    operator_key = clean_contact
            else:
                # Fallback to contact hash only if no contact info available
                operator_key = f"contact_{contact_hash[:8]}"
        
        # === USE EXISTING CALCULATIONS (NO DUPLICATION) ===
        # All basic metrics are already computed in contact_data
        total_bandwidth = contact_data.get('bandwidth', 0)
        total_consensus_weight = contact_data.get('consensus_weight_fraction', 0.0)
        guard_count = contact_data.get('guard_count', 0)
        exit_count = contact_data.get('exit_count', 0)
        middle_count = contact_data.get('middle_count', 0)
        unique_as_count = contact_data.get('unique_as_count', 0)
        measured_count = contact_data.get('measured_count', 0)
        first_seen = contact_data.get('first_seen', '')
        total_relays = len(relay_indices)  # Use existing relay list length
        
        # === CALCULATE ONLY NEW METRICS NOT ALREADY AVAILABLE ===
        # Get relay data for new calculations only
        operator_relays = [all_relays[i] for i in relay_indices]
        
        # Geographic and platform diversity (minimal calculation)
        countries = set(relay.get('country', '') for relay in operator_relays if relay.get('country'))
        platforms = set(relay.get('platform', '') for relay in operator_relays if relay.get('platform'))
        
        # Specialized platform/geographic counts (new calculations)
        non_linux_count = sum(1 for relay in operator_relays 
                             if relay.get('platform') and not relay.get('platform', '').startswith('Linux'))
        

        
        # Non-EU country detection (using centralized utilities)
        operator_countries = [relay.get('country') for relay in operator_relays if relay.get('country')]
        non_eu_count = count_non_eu_countries(operator_countries, use_political=True)
        
        # Rare/frontier countries (using pre-calculated rare countries from above)
        # Use unique countries for rare country calculation (not per-relay count)
        unique_operator_countries = list(set(operator_countries))
        
        # Find which of the operator's countries are rare
        operator_rare_countries = set()
        for country in unique_operator_countries:
            if country and country.lower() in valid_rare_countries:
                operator_rare_countries.add(country.upper())
        
        # Calculate rare country count by counting how many rare countries operator actually operates in
        rare_country_count = len(operator_rare_countries)
        
        relays_in_rare_countries = sum(1 for relay in operator_relays 
                                     if relay.get('country', '').upper() in operator_rare_countries)
        
        # Calculate breakdown of relays per rare country for tooltips and specialization
        rare_country_breakdown = {}
        for relay in operator_relays:
            country = relay.get('country', '').upper()
            if country in operator_rare_countries:
                rare_country_breakdown[country] = rare_country_breakdown.get(country, 0) + 1
        
        # Sort by relay count (descending) then by country name for consistent display
        sorted_rare_breakdown = sorted(rare_country_breakdown.items(), 
                                     key=lambda x: (-x[1], x[0]))
        
        # Calculate general country breakdown for reuse (all countries, not just rare ones)
        all_country_breakdown = {}
        for relay in operator_relays:
            country = relay.get('country', '').upper()
            if country:
                all_country_breakdown[country] = all_country_breakdown.get(country, 0) + 1
        
        # Sort by relay count (descending) then by country name for consistent display
        sorted_all_country_breakdown = sorted(all_country_breakdown.items(), 
                                     key=lambda x: (-x[1], x[0]))
        

        

        
        # Diversity score (using centralized calculation)
        diversity_score = calculate_diversity_score(
            countries=list(countries), 
            platforms=list(platforms), 
            unique_as_count=unique_as_count
        )
        
        # Uptime approximation (new calculation - from running status)
        running_relays = sum(1 for relay in operator_relays if relay.get('running', False))
        uptime_percentage = (running_relays / total_relays * 100) if total_relays > 0 else 0.0
        

        
        # Exit Authority - reuse existing calculation from relays.py
        exit_consensus_weight = contact_data.get('exit_consensus_weight_fraction', 0.0)
        
        # Veteran Score - earliest first seen time weighted by relay scale
        veteran_score = 0.0
        veteran_days = 0
        veteran_relay_scaling_factor = 1.0
        veteran_details = ""
        
        if operator_relays:
            from datetime import datetime
            current_date = datetime.now()
            
            # Find earliest first_seen date among all relays
            earliest_first_seen = None
            for relay in operator_relays:
                relay_first_seen_str = relay.get('first_seen', '')
                if relay_first_seen_str:
                    try:
                        relay_first_seen = datetime.strptime(relay_first_seen_str, '%Y-%m-%d %H:%M:%S')
                        if earliest_first_seen is None or relay_first_seen < earliest_first_seen:
                            earliest_first_seen = relay_first_seen
                    except (ValueError, TypeError):
                        continue
            
            if earliest_first_seen:
                # Calculate days since earliest relay
                veteran_days = (current_date - earliest_first_seen).days
                
                # Realistic scaling based on 360 max relays
                if total_relays >= 300:      # Top tier operators (83%+ of max)
                    veteran_relay_scaling_factor = 1.3
                elif total_relays >= 200:    # Large operators (56%+ of max)  
                    veteran_relay_scaling_factor = 1.25
                elif total_relays >= 100:    # Medium-large operators (28%+ of max)
                    veteran_relay_scaling_factor = 1.2
                elif total_relays >= 50:     # Medium operators (14%+ of max)
                    veteran_relay_scaling_factor = 1.15
                elif total_relays >= 20:     # Small-medium operators (6%+ of max)
                    veteran_relay_scaling_factor = 1.1
                elif total_relays >= 10:     # Small operators (3%+ of max)
                    veteran_relay_scaling_factor = 1.05
                else:                        # Micro operators (1-9 relays)
                    veteran_relay_scaling_factor = 1.0
                
                veteran_score = veteran_days * veteran_relay_scaling_factor
                veteran_details = f"Online and serving traffic since first day: {veteran_days} days * {veteran_relay_scaling_factor} ({total_relays} relays)"
        
        # Store operator data (mix of existing + new calculations)
        aroi_operators[operator_key] = {
            # === EXISTING CALCULATIONS (REUSED) ===
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
            'first_seen': first_seen,
            
            # === NEW CALCULATIONS (ONLY WHAT'S NEEDED) ===
            'countries': list(countries),
            'country_count': len(countries),
            'platforms': list(platforms),
            'platform_count': len(platforms),
            'non_linux_count': non_linux_count,
            'non_eu_count': non_eu_count,
            'rare_country_count': rare_country_count,
            'relays_in_rare_countries': relays_in_rare_countries,
            'rare_country_breakdown': sorted_rare_breakdown,
            'all_country_breakdown': sorted_all_country_breakdown,  # Reusable country breakdown
            'diversity_score': diversity_score,
            'uptime_percentage': uptime_percentage,
            'exit_consensus_weight': exit_consensus_weight,
            'veteran_score': veteran_score,
            'veteran_days': veteran_days,
            'veteran_relay_scaling_factor': veteran_relay_scaling_factor,
            'veteran_details': veteran_details,
            
            # Keep minimal relay data for potential future use
            'relays': operator_relays
        }
    
    # Generate 11 core leaderboard categories
    leaderboards = {}
    
    # 1. Bandwidth Contributed (use existing calculation)
    leaderboards['bandwidth'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['total_bandwidth'],
        reverse=True
    )[:50]  # Top 50 for each category
    
    # 2. Consensus Weight (use existing calculation)
    leaderboards['consensus_weight'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['total_consensus_weight'],
        reverse=True
    )[:50]
    
    # 3. Exit Authority Champions (new calculation)
    leaderboards['exit_authority'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['exit_consensus_weight'],
        reverse=True
    )[:50]
    
    # 4. Exit Operators (use existing calculation)
    leaderboards['exit_operators'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['exit_count'],
        reverse=True
    )[:50]
    
    # 5. Guard Operators (use existing calculation)
    leaderboards['guard_operators'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['guard_count'],
        reverse=True
    )[:50]
    
    # 6. Most Diverse Operators (new calculation)
    leaderboards['most_diverse'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['diversity_score'],
        reverse=True
    )[:50]
    
    # 7. Platform Diversity - Non-Linux Heroes (new calculation)
    leaderboards['platform_diversity'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['non_linux_count'],
        reverse=True
    )[:50]
    

    
    # 8. Geographic Champions - Non-EU Leaders (new calculation)
    leaderboards['non_eu_leaders'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['non_eu_count'],
        reverse=True
    )[:50]
    
    # 9. Frontier Builders - Rare Countries (new calculation)
    leaderboards['frontier_builders'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['rare_country_count'],
        reverse=True
    )[:50]
    
    # 10. Network Veterans - Earliest First Seen + Relay Scale (new calculation)
    leaderboards['network_veterans'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['veteran_score'],
        reverse=True
    )[:50]
    

    
    # Format data for template rendering with bandwidth units (reuse existing formatters)
    formatted_leaderboards = {}
    for category, data in leaderboards.items():
        formatted_data = []
        for rank, (operator_key, metrics) in enumerate(data, 1):
            # Use existing bandwidth formatting methods (top10 specific formatting)
            bandwidth_unit = relays_instance._determine_unit(metrics['total_bandwidth'])
            formatted_bandwidth = relays_instance._format_bandwidth_with_unit(
                metrics['total_bandwidth'], bandwidth_unit, decimal_places=1
            )
            
            # Calculate geographic achievement for non_eu_leaders category
            geographic_achievement = ""
            geographic_breakdown_details = ""
            geographic_breakdown_tooltip = ""
            if category == 'non_eu_leaders':
                geographic_achievement = calculate_geographic_achievement(metrics['countries'])
                # Reuse pre-calculated country breakdown data instead of recalculating
                geographic_breakdown_details, geographic_breakdown_tooltip = _format_breakdown_details(
                    metrics['all_country_breakdown'], 36
                )
            
            # Format rare country breakdown for frontier_builders category
            rare_country_details = ""
            rare_country_tooltip = ""
            frontier_achievement_title = ""
            platform_hero_title = ""
            diversity_master_title = ""
            
            if category == 'frontier_builders' and metrics['rare_country_breakdown']:
                # Use helper function with custom formatter for rare countries (includes "relay/relays")
                rare_country_details, rare_country_tooltip = _format_breakdown_details(
                    metrics['rare_country_breakdown'], 34,
                    lambda count, country: f"{count} relay{'s' if count != 1 else ''} in {country}"
                )
                
                # Add achievement titles for top 3 frontier builders
                if rank == 1:
                    frontier_achievement_title = "🌟 Frontier Legend"
                elif rank == 2:
                    frontier_achievement_title = "⭐ Frontier Master"
                elif rank == 3:
                    frontier_achievement_title = "✨ Frontier Champion"
            
            # Add achievement titles for top 3 platform diversity heroes
            platform_breakdown_details = ""
            platform_breakdown_tooltip = ""
            if category == 'platform_diversity':
                if rank == 1:
                    platform_hero_title = "🏆 Platform Legend"
                elif rank == 2:
                    platform_hero_title = "💻 Platform Master"
                elif rank == 3:
                    platform_hero_title = "🖥️ Platform Champion"
                
                # Format platform breakdown for specialization column (non-Linux only)
                platform_breakdown = {}
                for relay in operator_relays:
                    platform = relay.get('platform', 'Unknown')
                    if platform and not platform.lower().startswith('linux'):
                        # Extract short platform name (before first space or version number)
                        short_platform = platform.split()[0] if platform else 'Unknown'
                        # Map common platform names to shorter versions
                        if short_platform.lower().startswith('win'):
                            short_platform = 'Win'
                        elif short_platform.lower().startswith('mac') or short_platform.lower().startswith('darwin'):
                            short_platform = 'Mac'
                        elif short_platform.lower().startswith('freebsd'):
                            short_platform = 'FreeBSD'
                        elif short_platform.lower().startswith('openbsd'):
                            short_platform = 'OpenBSD'
                        elif short_platform.lower().startswith('netbsd'):
                            short_platform = 'NetBSD'
                        platform_breakdown[short_platform] = platform_breakdown.get(short_platform, 0) + 1
                
                # Sort by relay count (descending) then by platform name
                sorted_platform_breakdown = sorted(platform_breakdown.items(), 
                                                  key=lambda x: (-x[1], x[0]))
                
                # Create short format (max 12 chars): "Win:5,Mac:3"
                platform_parts = []
                for platform, count in sorted_platform_breakdown:
                    platform_parts.append(f"{platform}:{count}")
                
                platform_breakdown_full = ",".join(platform_parts)
                if len(platform_breakdown_full) > 12:
                    platform_breakdown_details = platform_breakdown_full[:9] + "..."
                else:
                    platform_breakdown_details = platform_breakdown_full
                
                # Create full tooltip with platform details and countries
                platform_tooltip_parts = []
                for platform, count in sorted_platform_breakdown:
                    platform_tooltip_parts.append(f"{count} {platform} relays")
                platform_tooltip_text = ", ".join(platform_tooltip_parts)
                
                # Add countries to tooltip
                countries_text = ", ".join(sorted(metrics['countries']))
                platform_breakdown_tooltip = f"Platform Distribution: {platform_tooltip_text}. Countries: {countries_text}"
            
            # Add achievement titles for top 3 diversity masters
            diversity_breakdown_details = ""
            diversity_breakdown_tooltip = ""
            if category == 'most_diverse':
                if rank == 1:
                    diversity_master_title = "🌍 Diversity Legend"
                elif rank == 2:
                    diversity_master_title = "🌟 Diversity Master"
                elif rank == 3:
                    diversity_master_title = "🌐 Diversity Champion"
                
                # Format diversity calculation breakdown
                country_count = metrics['country_count']
                platform_count = metrics['platform_count']
                as_count = metrics['unique_as_count']
                
                # Create short format (max 20 chars): "5 Countries, 3 OS, 8 AS"
                diversity_breakdown_full = f"{country_count} Countries, {platform_count} OS, {as_count} AS"
                if len(diversity_breakdown_full) > 20:
                    diversity_breakdown_details = diversity_breakdown_full[:17] + "..."
                else:
                    diversity_breakdown_details = diversity_breakdown_full
                
                # Create full tooltip with calculation details
                diversity_breakdown_tooltip = f"Diversity Score Calculation: {country_count} countries × 2.0 + {platform_count} operating systems × 1.5 + {as_count} unique ASNs × 1.0 = {metrics['diversity_score']}"
            
            # Format veteran details for network_veterans category
            veteran_details_short = ""
            veteran_tooltip = ""
            if category == 'network_veterans' and metrics['veteran_details']:
                veteran_tooltip = metrics['veteran_details']
                
                # Create short version (max 20 chars for table)
                if len(veteran_tooltip) > 20:
                    # Extract just the days and scaling factor for short display
                    days_part = f"{metrics['veteran_days']} days * {metrics['veteran_relay_scaling_factor']}"
                    if len(days_part) > 17:  # leave room for "..."
                        veteran_details_short = f"{metrics['veteran_days']} days..."
                    else:
                        veteran_details_short = days_part + "..."
                else:
                    veteran_details_short = veteran_tooltip

            
            display_name = metrics['aroi_domain'] if metrics['aroi_domain'] and metrics['aroi_domain'] != 'none' else operator_key

            # Calculate percentages for guard and exit relay ratios
            guard_percentage = (metrics['guard_count'] / metrics['total_relays'] * 100) if metrics['total_relays'] > 0 else 0
            exit_percentage = (metrics['exit_count'] / metrics['total_relays'] * 100) if metrics['total_relays'] > 0 else 0

            formatted_entry = {
                'rank': rank,
                'operator_key': operator_key,
                'display_name': display_name,
                'aroi_domain': metrics['aroi_domain'],
                'contact_hash': metrics['contact_hash'],
                'contact_info': metrics['contact_info'],
                'contact_info_escaped': html.escape(metrics['contact_info']),
                'total_relays': metrics['total_relays'],
                'total_bandwidth': formatted_bandwidth,
                'bandwidth_unit': bandwidth_unit,
                'total_consensus_weight_pct': f"{metrics['total_consensus_weight'] * 100:.2f}%",
                'exit_consensus_weight_pct': f"{metrics['exit_consensus_weight'] * 100:.2f}%",
                'guard_count': metrics['guard_count'],
                'exit_count': metrics['exit_count'],
                'guard_percentage': f"{guard_percentage:.0f}%",
                'exit_percentage': f"{exit_percentage:.0f}%",
                'middle_count': metrics['middle_count'],
                'measured_count': metrics['measured_count'],
                'unique_as_count': metrics['unique_as_count'],
                'country_count': metrics['country_count'],
                'countries': metrics['countries'][:5],  # Top 5 countries for display
                'platform_count': metrics['platform_count'],
                'platforms': metrics['platforms'][:3],  # Top 3 platforms for display
                'non_linux_count': metrics['non_linux_count'],
                'non_eu_count': metrics['non_eu_count'],
                'rare_country_count': metrics['rare_country_count'],
                'relays_in_rare_countries': metrics['relays_in_rare_countries'],
                'rare_country_details': rare_country_details,
                'rare_country_tooltip': rare_country_tooltip,
                'frontier_achievement_title': frontier_achievement_title,
                'platform_hero_title': platform_hero_title,
                'platform_breakdown_details': platform_breakdown_details,
                'platform_breakdown_tooltip': platform_breakdown_tooltip,
                'diversity_master_title': diversity_master_title,
                'diversity_breakdown_details': diversity_breakdown_details,
                'diversity_breakdown_tooltip': diversity_breakdown_tooltip,
                'diversity_score': f"{metrics['diversity_score']:.1f}",
                'uptime_percentage': f"{metrics['uptime_percentage']:.1f}%",
                'veteran_score': f"{metrics['veteran_score']:.0f}",
                'veteran_days': metrics['veteran_days'],
                'veteran_relay_scaling_factor': metrics['veteran_relay_scaling_factor'],
                'veteran_details_short': veteran_details_short,
                'veteran_tooltip': veteran_tooltip,
                'first_seen_date': metrics['first_seen'].split(' ')[0] if metrics['first_seen'] else 'Unknown',
                'geographic_achievement': geographic_achievement,  # Add dynamic achievement
                'geographic_breakdown_details': geographic_breakdown_details,  # Add geographic breakdown
                'geographic_breakdown_tooltip': geographic_breakdown_tooltip  # Add geographic tooltip
            }
            formatted_data.append(formatted_entry)
        
        formatted_leaderboards[category] = formatted_data
    
    # Generate summary statistics (reuse existing calculations)
    total_operators = len(aroi_operators)
    total_bandwidth_all = sum(op['total_bandwidth'] for op in aroi_operators.values())
    total_cw_all = sum(op['total_consensus_weight'] for op in aroi_operators.values())
    
    # Validation: consensus weight should be reasonable (≤ 100% of network)
    if total_cw_all > 1.0:
        print(f"⚠️  WARNING: AROI consensus weight sum ({total_cw_all:.3f}) exceeds 100% - check calculation logic")
    
    # The total_cw_all represents the fraction of network consensus weight held by AROI operators
    # This should be displayed as the percentage of network authority they represent
    
    # Format summary bandwidth with unit (reuse existing formatters with top10 formatting)
    summary_bandwidth_unit = relays_instance._determine_unit(total_bandwidth_all)
    summary_bandwidth_value = relays_instance._format_bandwidth_with_unit(
        total_bandwidth_all, summary_bandwidth_unit, decimal_places=1
    )
    
    summary_stats = {
        'total_operators': total_operators,
        'total_bandwidth_formatted': f"{summary_bandwidth_value} {summary_bandwidth_unit}",
        'total_consensus_weight_pct': f"{total_cw_all * 100:.1f}%",
        'live_categories_count': len(formatted_leaderboards),  # Dynamic count of actual leaderboards
        'update_timestamp': relays_instance.timestamp if hasattr(relays_instance, 'timestamp') else 'Unknown',
        'categories': {
            'bandwidth': 'Bandwidth Contributed',
            'consensus_weight': 'Consensus Weight',
            'exit_authority': 'Exit Authority Champions',
            'exit_operators': 'Exit Operators',
            'guard_operators': 'Guard Operators', 
            'most_diverse': 'Most Diverse Operators',
            'platform_diversity': 'Platform Diversity (Non-Linux Heroes)',

            'non_eu_leaders': 'Geographic Champions (Non-EU Leaders)',
            'frontier_builders': 'Frontier Builders (Rare Countries)',
            'network_veterans': 'Network Veterans'
        }
    }
    
    return {
        'leaderboards': formatted_leaderboards,
        'summary': summary_stats,
        'raw_operators': aroi_operators  # For potential future use
    }

 