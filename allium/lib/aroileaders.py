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
import ipaddress

# Import centralized country utilities
from .country_utils import (
    count_non_eu_countries, 
    count_frontier_countries_weighted_with_existing_data,
    calculate_diversity_score, 
    calculate_geographic_achievement,
    EU_POLITICAL_REGION  # Add this import
)

# Import HTML escaping utility
from .string_utils import safe_html_escape



def _calculate_reliability_score(operator_relays, uptime_data, time_period):
    """
    Calculate reliability score using simple average uptime (no weighting).
    
    Formula: Score = Average uptime percentage across all relays
    Uses shared uptime utilities to avoid code duplication with relays.py.
    
    Args:
        operator_relays (list): List of relay objects for this operator
        uptime_data (dict): Uptime data from Onionoo API (attached to relays_instance)
        time_period (str): Time period to use ('6_months' or '5_years')
        
    Returns:
        dict: Reliability metrics including score, average uptime, relay count, etc.
    """
    if not operator_relays or not uptime_data:
        return {
            'score': 0.0,
            'average_uptime': 0.0,
            'relay_count': 0,
            'weight': 1.0,  # Always 1.0 since no weighting is applied
            'valid_relays': 0,
            'breakdown': {}
        }
    
    from .uptime_utils import extract_relay_uptime_for_period
    
    # Extract uptime data for this period using shared utility
    period_result = extract_relay_uptime_for_period(operator_relays, uptime_data, time_period)
    
    # Calculate metrics
    relay_count = len(operator_relays)
    valid_relays = len(period_result['uptime_values'])
    
    if not period_result['uptime_values']:
        return {
            'score': 0.0,
            'average_uptime': 0.0,
            'relay_count': relay_count,
            'weight': 1.0,  # Always 1.0 since no weighting is applied
            'valid_relays': 0,
            'breakdown': {}
        }
    
    # Calculate simple average uptime across all relays (no weighting)
    average_uptime = sum(period_result['uptime_values']) / len(period_result['uptime_values'])
    
    # Score is simply the average uptime (no weight multiplier)
    score = average_uptime
    
    # Convert relay_breakdown format for compatibility
    breakdown = {}
    for fingerprint, relay_data in period_result['relay_breakdown'].items():
        breakdown[relay_data['nickname']] = {
            'fingerprint': fingerprint,
            'uptime': relay_data['uptime'],
            'data_points': relay_data.get('data_points', 0)
        }
    
    return {
        'score': score,
        'average_uptime': average_uptime,
        'relay_count': relay_count,
        'weight': 1.0,  # Always 1.0 since no weighting is applied
        'valid_relays': valid_relays,
        'breakdown': breakdown
    }


def _safe_parse_ip_address(address_string):
    """
    Safely parse IP address from or_addresses string with validation.
    Returns tuple (ip_address, ip_version) or (None, None) if invalid.
    
    Security: Validates all input against Python's ipaddress module to prevent
    injection attacks through malformed address strings.
    """
    if not address_string or not isinstance(address_string, str):
        return None, None
    
    try:
        # Handle IPv6 with brackets like [2001:db8::1]:9001
        if address_string.startswith('[') and ']:' in address_string:
            ip_part = address_string.split(']:')[0][1:]  # Remove brackets and port
            parsed_ip = ipaddress.ip_address(ip_part)
            return str(parsed_ip), 6 if isinstance(parsed_ip, ipaddress.IPv6Address) else 4
        
        # Handle addresses with colons (could be IPv4:port or IPv6)
        elif ':' in address_string:
            # Try parsing as IPv6 first (since IPv6 has multiple colons)
            try:
                parsed_ip = ipaddress.ip_address(address_string)
                return str(parsed_ip), 6 if isinstance(parsed_ip, ipaddress.IPv6Address) else 4
            except (ValueError, ipaddress.AddressValueError):
                # Not a bare IPv6, try as IPv4:port
                ip_part = address_string.split(':')[0]
                parsed_ip = ipaddress.ip_address(ip_part)
                return str(parsed_ip), 6 if isinstance(parsed_ip, ipaddress.IPv6Address) else 4
        
        # Handle bare IP address without port
        else:
            parsed_ip = ipaddress.ip_address(address_string)
            return str(parsed_ip), 6 if isinstance(parsed_ip, ipaddress.IPv6Address) else 4
            
    except (ValueError, ipaddress.AddressValueError):
        # Invalid IP address format - silently skip
        return None, None

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
            
        # Use AROI domain as key if available, otherwise use first 24 chars of contact_info
        if aroi_domain and aroi_domain != 'none':
            operator_key = aroi_domain
        else:
            # Use first 30 characters of contact info for better readability (extended from 24)
            if contact_info and len(contact_info.strip()) > 0:
                clean_contact = contact_info.strip()
                if len(clean_contact) > 30:
                    operator_key = clean_contact[:30] + '...'
                else:
                    operator_key = clean_contact
            else:
                # Fallback to contact hash only if no contact info available
                operator_key = f"contact_{contact_hash[:8]}"
        
        # === USE EXISTING CALCULATIONS (NO DUPLICATION) ===
        # All basic metrics are already computed in contact_data
        total_bandwidth = contact_data.get('bandwidth', 0)
        exit_bandwidth = contact_data.get('exit_bandwidth', 0)
        guard_bandwidth = contact_data.get('guard_bandwidth', 0)
        middle_bandwidth = contact_data.get('middle_bandwidth', 0)
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
        
        # === IPv4/IPv6 UNIQUE ADDRESS CALCULATIONS (NEW) ===
        # Extract unique IPv4 and IPv6 addresses from all operator relays
        unique_ipv4_addresses = set()
        unique_ipv6_addresses = set()
        ipv4_relay_count = 0
        ipv6_relay_count = 0
        ipv4_total_bandwidth = 0
        ipv6_total_bandwidth = 0
        ipv4_total_consensus_weight = 0.0
        ipv6_total_consensus_weight = 0.0
        ipv4_guard_count = 0
        ipv4_exit_count = 0
        ipv4_middle_count = 0
        ipv6_guard_count = 0
        ipv6_exit_count = 0
        ipv6_middle_count = 0
        
        for relay in operator_relays:
            or_addresses = relay.get('or_addresses', [])
            relay_bandwidth = relay.get('observed_bandwidth', 0)
            relay_consensus_weight = relay.get('consensus_weight_fraction', 0)
            relay_flags = relay.get('flags', [])
            
            has_ipv4 = False
            has_ipv6 = False
            
            for address in or_addresses:
                # Safely parse IP address with validation to prevent injection attacks
                parsed_ip, ip_version = _safe_parse_ip_address(address)
                if parsed_ip and ip_version:
                    if ip_version == 4:
                        unique_ipv4_addresses.add(parsed_ip)
                        has_ipv4 = True
                    elif ip_version == 6:
                        unique_ipv6_addresses.add(parsed_ip)
                        has_ipv6 = True
            
            # Count relays and aggregate metrics by IP type
            # Use Exit > Guard > Middle priority logic (consistent with relays.py)
            if has_ipv4:
                ipv4_relay_count += 1
                ipv4_total_bandwidth += relay_bandwidth
                ipv4_total_consensus_weight += relay_consensus_weight
                # Primary role assignment (Exit > Guard > Middle priority)
                if 'Exit' in relay_flags:
                    ipv4_exit_count += 1
                elif 'Guard' in relay_flags:
                    ipv4_guard_count += 1
                else:
                    ipv4_middle_count += 1
            
            if has_ipv6:
                ipv6_relay_count += 1
                ipv6_total_bandwidth += relay_bandwidth
                ipv6_total_consensus_weight += relay_consensus_weight
                # Primary role assignment (Exit > Guard > Middle priority)
                if 'Exit' in relay_flags:
                    ipv6_exit_count += 1
                elif 'Guard' in relay_flags:
                    ipv6_guard_count += 1
                else:
                    ipv6_middle_count += 1
        
        unique_ipv4_count = len(unique_ipv4_addresses)
        unique_ipv6_count = len(unique_ipv6_addresses)
        
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
        
        # Calculate non-EU country breakdown for specialization column (NEW)
        non_eu_country_breakdown = {}
        for relay in operator_relays:
            country = relay.get('country', '').upper()
            if country and country.lower() not in EU_POLITICAL_REGION:
                non_eu_country_breakdown[country] = non_eu_country_breakdown.get(country, 0) + 1
        
        # Sort by relay count (descending) then by country name for consistent display
        sorted_non_eu_country_breakdown = sorted(non_eu_country_breakdown.items(), 
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
        
        # Guard Authority - reuse existing calculation from relays.py
        guard_consensus_weight = contact_data.get('guard_consensus_weight_fraction', 0.0)
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
        
        # === RELIABILITY CALCULATIONS (NEW) ===
        # Calculate reliability scores for both 6-month and 5-year periods
        uptime_data = getattr(relays_instance, 'uptime_data', None)
        
        # 6-month reliability score (primary metric)
        reliability_6m = _calculate_reliability_score(operator_relays, uptime_data, '6_months')
        
        # 5-year reliability score (legacy metric)
        reliability_5y = _calculate_reliability_score(operator_relays, uptime_data, '5_years')
        
        # Store operator data (mix of existing + new calculations)
        aroi_operators[operator_key] = {
            # === EXISTING CALCULATIONS (REUSED) ===
            'aroi_domain': aroi_domain,
            'contact_hash': contact_hash,
            'contact_info': contact_info,
            'total_relays': total_relays,
            'total_bandwidth': total_bandwidth,
            'exit_bandwidth': exit_bandwidth,
            'guard_bandwidth': guard_bandwidth,
            'middle_bandwidth': middle_bandwidth,
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
            'non_eu_country_breakdown': sorted_non_eu_country_breakdown,  # Non-EU country breakdown
            'diversity_score': diversity_score,
            'uptime_percentage': uptime_percentage,
            'exit_consensus_weight': exit_consensus_weight,
            'guard_consensus_weight': guard_consensus_weight,
            'veteran_score': veteran_score,
            'veteran_days': veteran_days,
            'veteran_relay_scaling_factor': veteran_relay_scaling_factor,
            'veteran_details': veteran_details,
            
            # === RELIABILITY METRICS (NEW) ===
            'reliability_6m_score': reliability_6m['score'],
            'reliability_6m_average': reliability_6m['average_uptime'],
            'reliability_6m_weight': reliability_6m['weight'],
            'reliability_6m_valid_relays': reliability_6m['valid_relays'],
            'reliability_6m_breakdown': reliability_6m['breakdown'],
            
            'reliability_5y_score': reliability_5y['score'],
            'reliability_5y_average': reliability_5y['average_uptime'],
            'reliability_5y_weight': reliability_5y['weight'],
            'reliability_5y_valid_relays': reliability_5y['valid_relays'],
            'reliability_5y_breakdown': reliability_5y['breakdown'],
            
            # === IPv4/IPv6 UNIQUE ADDRESS METRICS (NEW) ===
            'unique_ipv4_count': unique_ipv4_count,
            'unique_ipv6_count': unique_ipv6_count,
            'ipv4_relay_count': ipv4_relay_count,
            'ipv6_relay_count': ipv6_relay_count,
            'ipv4_total_bandwidth': ipv4_total_bandwidth,
            'ipv6_total_bandwidth': ipv6_total_bandwidth,
            'ipv4_total_consensus_weight': ipv4_total_consensus_weight,
            'ipv6_total_consensus_weight': ipv6_total_consensus_weight,
            'ipv4_guard_count': ipv4_guard_count,
            'ipv4_exit_count': ipv4_exit_count,
            'ipv4_middle_count': ipv4_middle_count,
            'ipv6_guard_count': ipv6_guard_count,
            'ipv6_exit_count': ipv6_exit_count,
            'ipv6_middle_count': ipv6_middle_count,
            
            # Keep minimal relay data for potential future use
            'relays': operator_relays
        }
    
    # Generate 14 core leaderboard categories (added Guard Authority + 2 new reliability categories)
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
    
    # 4. Guard Authority Champions (new calculation)
    leaderboards['guard_authority'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['guard_consensus_weight'],
        reverse=True
    )[:50]
    
    # 5. Exit Operators (use existing calculation)
    leaderboards['exit_operators'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['exit_count'],
        reverse=True
    )[:50]
    
    # 6. Guard Operators (use existing calculation)
    leaderboards['guard_operators'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['guard_count'],
        reverse=True
    )[:50]
    
    # 7. ⏰ Reliability Masters - 6-Month Average Uptime (NEW) - Only operators with > 25 relays AND > 0% uptime
    reliability_masters_filtered = {k: v for k, v in aroi_operators.items() if v['total_relays'] > 25 and v['reliability_6m_score'] > 0.0}
    leaderboards['reliability_masters'] = sorted(
        reliability_masters_filtered.items(),
        key=lambda x: x[1]['reliability_6m_score'],
        reverse=True
    )[:50]
    
    # 8. 👑 Legacy Titans - 5-Year Average Uptime (NEW) - Only operators with > 25 relays AND > 0% uptime
    legacy_titans_filtered = {k: v for k, v in aroi_operators.items() if v['total_relays'] > 25 and v['reliability_5y_score'] > 0.0}
    leaderboards['legacy_titans'] = sorted(
        legacy_titans_filtered.items(),
        key=lambda x: x[1]['reliability_5y_score'],
        reverse=True
    )[:50]
    
    # 9. Most Diverse Operators (new calculation)
    leaderboards['most_diverse'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['diversity_score'],
        reverse=True
    )[:50]
    
    # 10. Platform Diversity - Non-Linux Heroes (new calculation)
    leaderboards['platform_diversity'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['non_linux_count'],
        reverse=True
    )[:50]
    
    # 11. Geographic Champions - Non-EU Leaders (new calculation)
    leaderboards['non_eu_leaders'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['non_eu_count'],
        reverse=True
    )[:50]
    
    # 12. Frontier Builders - Rare Countries (new calculation)
    leaderboards['frontier_builders'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['rare_country_count'],
        reverse=True
    )[:50]
    
    # 13. Network Veterans - Earliest First Seen + Relay Scale (new calculation)
    leaderboards['network_veterans'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['veteran_score'],
        reverse=True
    )[:50]
    
    # 14. IPv4 Address Leaders - Unique IPv4 Addresses per Operator (new calculation)
    leaderboards['ipv4_leaders'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['unique_ipv4_count'],
        reverse=True
    )[:50]
    
    # 15. IPv6 Address Leaders - Unique IPv6 Addresses per Operator (new calculation)
    leaderboards['ipv6_leaders'] = sorted(
        aroi_operators.items(),
        key=lambda x: x[1]['unique_ipv6_count'],
        reverse=True
    )[:50]
    
    # Format data for template rendering with bandwidth units (reuse existing formatters)
    formatted_leaderboards = {}
    for category, data in leaderboards.items():
        formatted_data = []
        for rank, (operator_key, metrics) in enumerate(data, 1):
            # Use existing bandwidth formatting methods (top10 specific formatting)
            bandwidth_unit = relays_instance.bandwidth_formatter.determine_unit(metrics['total_bandwidth'])
            formatted_bandwidth = relays_instance.bandwidth_formatter.format_bandwidth_with_unit(
                metrics['total_bandwidth'], bandwidth_unit, decimal_places=1
            )
            
            # Format exit-specific bandwidth for exit categories (exit_authority, exit_operators)
            exit_bandwidth_unit = relays_instance.bandwidth_formatter.determine_unit(metrics['exit_bandwidth'])
            formatted_exit_bandwidth = relays_instance.bandwidth_formatter.format_bandwidth_with_unit(
                metrics['exit_bandwidth'], exit_bandwidth_unit, decimal_places=1
            )
            
            # Format guard-specific bandwidth for guard categories (guard_authority, guard_operators)
            guard_bandwidth_unit = relays_instance.bandwidth_formatter.determine_unit(metrics['guard_bandwidth'])
            formatted_guard_bandwidth = relays_instance.bandwidth_formatter.format_bandwidth_with_unit(
                metrics['guard_bandwidth'], guard_bandwidth_unit, decimal_places=1
            )
            
            # Calculate geographic achievement for non_eu_leaders category
            geographic_achievement = ""
            geographic_breakdown_details = ""
            geographic_breakdown_tooltip = ""
            if category == 'non_eu_leaders':
                geographic_achievement = calculate_geographic_achievement(metrics['countries'])
                # Use non-EU country breakdown for specialization column instead of all countries
                geographic_breakdown_details, geographic_breakdown_tooltip = _format_breakdown_details(
                    metrics['non_eu_country_breakdown'], 52
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
                    metrics['rare_country_breakdown'], 44,
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
                for relay in metrics['relays']:
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
                
                # Create short format (max 32 chars): "Win: 5, Mac: 3, FreeBSD: 2"
                platform_parts = []
                for platform, count in sorted_platform_breakdown:
                    platform_parts.append(f"{platform}: {count}")
                
                platform_breakdown_full = ", ".join(platform_parts)
                if len(platform_breakdown_full) > 32:
                    platform_breakdown_details = platform_breakdown_full[:29] + "..."
                else:
                    platform_breakdown_details = platform_breakdown_full
                
                # Create full tooltip with platform details only (countries not relevant for platform diversity)
                platform_tooltip_parts = []
                for platform, count in sorted_platform_breakdown:
                    platform_tooltip_parts.append(f"{count} {platform} relays")
                platform_tooltip_text = ", ".join(platform_tooltip_parts)
                
                platform_breakdown_tooltip = f"Platform Distribution: {platform_tooltip_text}"
            
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

            # Format reliability details for reliability categories (REUSE veteran pattern)
            reliability_details_short = ""
            reliability_tooltip = ""
            reliability_score_raw = 0.0
            reliability_average = 0.0
            reliability_weight = 1.0
            
            if category in ['reliability_masters', 'legacy_titans']:
                # Determine which reliability data to use
                if category == 'reliability_masters':
                    reliability_score_raw = metrics['reliability_6m_score']
                    reliability_average = metrics['reliability_6m_average']
                    reliability_weight = metrics['reliability_6m_weight']
                    period_label = "6-month"
                else:  # legacy_titans
                    reliability_score_raw = metrics['reliability_5y_score']
                    reliability_average = metrics['reliability_5y_average']
                    reliability_weight = metrics['reliability_5y_weight']
                    period_label = "5-year"
                
                # Create tooltip without weighting information (simplified)
                reliability_tooltip = f"{period_label} reliability: {reliability_average:.1f}% average uptime ({metrics['total_relays']} relays)"
                
                # Create short version for table display (simplified, no weight)
                reliability_details_short = f"{reliability_average:.1f}% avg"
            
            # Format IPv4/IPv6 specific details for IP address categories (NEW)
            ipv4_achievement_title = ""
            ipv6_achievement_title = ""
            ip_address_details = ""
            ip_address_tooltip = ""
            
            if category == 'ipv4_leaders':
                # Add achievement titles for top 3 IPv4 leaders
                if rank == 1:
                    ipv4_achievement_title = "🥇 IPv4 Legend"
                elif rank == 2:
                    ipv4_achievement_title = "🥈 IPv4 Master"
                elif rank == 3:
                    ipv4_achievement_title = "🥉 IPv4 Champion"
                
                # Format IPv4 bandwidth with unit (reuse existing formatters)
                ipv4_bandwidth_unit = relays_instance.bandwidth_formatter.determine_unit(metrics['ipv4_total_bandwidth'])
                formatted_ipv4_bandwidth = relays_instance.bandwidth_formatter.format_bandwidth_with_unit(
                    metrics['ipv4_total_bandwidth'], ipv4_bandwidth_unit, decimal_places=1
                )
                
                ip_address_details = f"{metrics['unique_ipv4_count']} unique IPv4"
                ip_address_tooltip = f"IPv4 Infrastructure: {metrics['unique_ipv4_count']} unique addresses across {metrics['ipv4_relay_count']} relays with {formatted_ipv4_bandwidth} {ipv4_bandwidth_unit} bandwidth"
                
            elif category == 'ipv6_leaders':
                # Add achievement titles for top 3 IPv6 leaders
                if rank == 1:
                    ipv6_achievement_title = "🥇 IPv6 Legend"
                elif rank == 2:
                    ipv6_achievement_title = "🥈 IPv6 Master"
                elif rank == 3:
                    ipv6_achievement_title = "🥉 IPv6 Champion"
                
                # Format IPv6 bandwidth with unit (reuse existing formatters)
                ipv6_bandwidth_unit = relays_instance.bandwidth_formatter.determine_unit(metrics['ipv6_total_bandwidth'])
                formatted_ipv6_bandwidth = relays_instance.bandwidth_formatter.format_bandwidth_with_unit(
                    metrics['ipv6_total_bandwidth'], ipv6_bandwidth_unit, decimal_places=1
                )
                
                ip_address_details = f"{metrics['unique_ipv6_count']} unique IPv6"
                ip_address_tooltip = f"IPv6 Infrastructure: {metrics['unique_ipv6_count']} unique addresses across {metrics['ipv6_relay_count']} relays with {formatted_ipv6_bandwidth} {ipv6_bandwidth_unit} bandwidth"

            
            display_name = metrics['aroi_domain'] if metrics['aroi_domain'] and metrics['aroi_domain'] != 'none' else operator_key

            # Calculate percentages for guard and exit relay ratios
            guard_percentage = (metrics['guard_count'] / metrics['total_relays'] * 100) if metrics['total_relays'] > 0 else 0
            exit_percentage = (metrics['exit_count'] / metrics['total_relays'] * 100) if metrics['total_relays'] > 0 else 0
            
            # Calculate non-EU percentage for geographic champions
            non_eu_percentage = (metrics['non_eu_count'] / metrics['total_relays'] * 100) if metrics['total_relays'] > 0 else 0

            formatted_entry = {
                'rank': rank,
                'operator_key': operator_key,
                'display_name': display_name,
                'aroi_domain': metrics['aroi_domain'],
                'contact_hash': metrics['contact_hash'],
                'contact_info': metrics['contact_info'],
                'contact_info_escaped': safe_html_escape(metrics['contact_info']),
                'total_relays': metrics['total_relays'],
                'total_bandwidth': formatted_bandwidth,
                'bandwidth_unit': bandwidth_unit,
                'exit_bandwidth': formatted_exit_bandwidth,
                'exit_bandwidth_unit': exit_bandwidth_unit,
                'guard_bandwidth': formatted_guard_bandwidth,
                'guard_bandwidth_unit': guard_bandwidth_unit,
                'total_consensus_weight_pct': f"{metrics['total_consensus_weight'] * 100:.2f}%",
                'exit_consensus_weight_pct': f"{metrics['exit_consensus_weight'] * 100:.2f}%",
                'guard_consensus_weight_pct': f"{metrics['guard_consensus_weight'] * 100:.2f}%",
                'guard_count': metrics['guard_count'],
                'exit_count': metrics['exit_count'],
                'guard_percentage': f"{guard_percentage:.0f}%",
                'exit_percentage': f"{exit_percentage:.0f}%",
                'middle_count': metrics['middle_count'],
                'measured_count': metrics['measured_count'],
                'unique_as_count': metrics['unique_as_count'],
                # Frontier Builders should show only rare country count, not total country count
                'country_count': metrics['rare_country_count'] if category == 'frontier_builders' else metrics['country_count'],
                'countries': metrics['countries'][:5],  # Top 5 countries for display
                'platform_count': metrics['platform_count'],
                'platforms': metrics['platforms'][:3],  # Top 3 platforms for display
                'non_linux_count': metrics['non_linux_count'],
                'non_eu_count': metrics['non_eu_count'],
                'non_eu_count_with_percentage': f"{metrics['non_eu_count']} ({non_eu_percentage:.0f}%)",
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
                'geographic_breakdown_tooltip': geographic_breakdown_tooltip,  # Add geographic tooltip
                
                # === RELIABILITY FIELDS (REUSE existing pattern) ===
                'reliability_score': f"{reliability_score_raw:.1f}",
                'reliability_average': f"{reliability_average:.1f}%",
                'reliability_weight': f"{reliability_weight:.1f}x",
                'reliability_details_short': reliability_details_short,
                'reliability_tooltip': reliability_tooltip,
                
                # === IPv4/IPv6 ADDRESS FIELDS (NEW) ===
                'unique_ipv4_count': metrics['unique_ipv4_count'],
                'unique_ipv6_count': metrics['unique_ipv6_count'],
                'ipv4_relay_count': metrics['ipv4_relay_count'],
                'ipv6_relay_count': metrics['ipv6_relay_count'],
                'ipv4_total_bandwidth': metrics['ipv4_total_bandwidth'],
                'ipv6_total_bandwidth': metrics['ipv6_total_bandwidth'],
                'ipv4_total_consensus_weight_pct': f"{metrics['ipv4_total_consensus_weight'] * 100:.2f}%",
                'ipv6_total_consensus_weight_pct': f"{metrics['ipv6_total_consensus_weight'] * 100:.2f}%",
                'ipv4_guard_count': metrics['ipv4_guard_count'],
                'ipv4_exit_count': metrics['ipv4_exit_count'],
                'ipv4_middle_count': metrics['ipv4_middle_count'],
                'ipv6_guard_count': metrics['ipv6_guard_count'],
                'ipv6_exit_count': metrics['ipv6_exit_count'],
                'ipv6_middle_count': metrics['ipv6_middle_count'],
                'ipv4_achievement_title': ipv4_achievement_title,
                'ipv6_achievement_title': ipv6_achievement_title,
                'ip_address_details': ip_address_details,
                'ip_address_tooltip': ip_address_tooltip,
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
    summary_bandwidth_unit = relays_instance.bandwidth_formatter.determine_unit(total_bandwidth_all)
    summary_bandwidth_value = relays_instance.bandwidth_formatter.format_bandwidth_with_unit(
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
            'guard_authority': 'Guard Authority Champions',
            'exit_operators': 'Exit Operators',
            'guard_operators': 'Guard Operators', 
            'reliability_masters': '⏰ Reliability Masters (6-Month Uptime)',
            'legacy_titans': '👑 Legacy Titans (5-Year Uptime)',
            'most_diverse': 'Most Diverse Operators',
            'platform_diversity': 'Platform Diversity (Non-Linux Heroes)',
            'non_eu_leaders': 'Geographic Champions (Non-EU Leaders)',
            'frontier_builders': 'Frontier Builders (Rare Countries)',
            'network_veterans': 'Network Veterans',
            'ipv4_leaders': 'IPv4 Address Leaders',
            'ipv6_leaders': 'IPv6 Address Leaders'
        }
    }
    
    return {
        'leaderboards': formatted_leaderboards,
        'summary': summary_stats,
        'raw_operators': aroi_operators  # For potential future use
    }

 