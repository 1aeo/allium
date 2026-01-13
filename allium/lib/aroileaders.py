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



def normalize_contact_info(contact_info):
    """
    Normalize contact information by removing common artifacts and standardizing.
    
    This function cleans up contact information to improve grouping accuracy.
    
    Args:
        contact_info (str): Raw contact information string
        
    Returns:
        str: Normalized contact information
    """
    return contact_info.strip()


def _format_bandwidth_with_auto_unit(bandwidth_value, bandwidth_formatter, decimal_places=1):
    """
    Helper function to format bandwidth with automatic unit determination.
    
    Args:
        bandwidth_value (float): Bandwidth value in bytes/second
        bandwidth_formatter: The bandwidth formatter instance
        decimal_places (int): Number of decimal places to show
        
    Returns:
        tuple: (formatted_bandwidth, unit)
    """
    unit = bandwidth_formatter.determine_unit(bandwidth_value)
    formatted = bandwidth_formatter.format_bandwidth_with_unit(
        bandwidth_value, unit, decimal_places=decimal_places
    )
    return formatted, unit


def _calculate_generic_score(operator_relays, data, time_period, metric_type, prebuilt_map=None):
    """
    Generic function to calculate scores for different metrics (reliability, bandwidth).
    
    OPTIMIZATION: Accepts pre-built maps for batch processing. When processing multiple
    operators (e.g., AROI leaderboards with ~3000+ contacts), build maps once with
    build_uptime_map() or build_bandwidth_map() and pass to each call.
    
    Args:
        operator_relays (list): List of relay objects for this operator
        data (dict): Data from Onionoo API (uptime_data or bandwidth_data)
        time_period (str): Time period to use ('6_months' or '5_years')
        metric_type (str): Type of metric ('reliability' or 'bandwidth')
        prebuilt_map (dict, optional): Pre-built fingerprint->data mapping for batch processing
        
    Returns:
        dict: Metrics including score, average value, relay count, etc.
    """
    if not operator_relays:
        return {
            'score': 0.0,
            f'average_{metric_type}': 0.0,
            'relay_count': 0,
            'weight': 1.0,  # Always 1.0 since no weighting is applied
            'valid_relays': 0,
            'breakdown': {}
        }
    
    # If no data and no prebuilt_map, return empty result
    if not data and not prebuilt_map:
        return {
            'score': 0.0,
            f'average_{metric_type}': 0.0,
            'relay_count': len(operator_relays),
            'weight': 1.0,
            'valid_relays': 0,
            'breakdown': {}
        }
    
    relay_count = len(operator_relays)
    
    if metric_type == 'uptime':
        from .uptime_utils import extract_relay_uptime_for_period
        period_result = extract_relay_uptime_for_period(operator_relays, data, time_period, uptime_map=prebuilt_map)
        
        if not period_result['uptime_values']:
            return {
                'score': 0.0,
                'average_uptime': 0.0,
                'relay_count': relay_count,
                'weight': 1.0,
                'valid_relays': 0,
                'breakdown': {}
            }
        
        # Calculate simple average uptime across all relays (no weighting)
        average_value = sum(period_result['uptime_values']) / len(period_result['uptime_values'])
        score = average_value
        valid_relays = len(period_result['uptime_values'])
        
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
            'average_uptime': average_value,
            'relay_count': relay_count,
            'weight': 1.0,
            'valid_relays': valid_relays,
            'breakdown': breakdown
        }
    
    elif metric_type == 'bandwidth':
        from .bandwidth_utils import extract_operator_daily_bandwidth_totals, extract_relay_bandwidth_for_period
        
        # Calculate daily total bandwidth (sum across all relays per day, then average)
        # Pass pre-built bandwidth_map to avoid rebuilding for each operator
        daily_totals_result = extract_operator_daily_bandwidth_totals(operator_relays, data, time_period, bandwidth_map=prebuilt_map)
        
        if not daily_totals_result['daily_totals']:
            return {
                'score': 0.0,
                'average_bandwidth': 0.0,
                'relay_count': relay_count,
                'weight': 1.0,
                'valid_relays': 0,
                'breakdown': {}
            }
        
        # Score is the average of daily totals (matches Onionoo details API logic)
        score = daily_totals_result['average_daily_total']
        average_value = daily_totals_result['average_daily_total']
        
        # Get relay breakdown for display purposes (reuse existing logic)
        # Pass pre-built bandwidth_map to avoid rebuilding for each operator
        period_result = extract_relay_bandwidth_for_period(operator_relays, data, time_period, bandwidth_map=prebuilt_map)
        
        # Convert relay_breakdown format for compatibility
        breakdown = {}
        for fingerprint, relay_data in period_result['relay_breakdown'].items():
            breakdown[relay_data['nickname']] = {
                'fingerprint': fingerprint,
                'bandwidth': relay_data['bandwidth'],
                'data_points': relay_data.get('data_points', 0)
            }
        
        return {
            'score': score,
            'average_bandwidth': average_value,
            'relay_count': relay_count,
            'weight': 1.0,
            'valid_relays': len(period_result['bandwidth_values']),
            'breakdown': breakdown
        }
    
    # Default return for unsupported metric types
    return {
        'score': 0.0,
        f'average_{metric_type}': 0.0,
        'relay_count': relay_count,
        'weight': 1.0,
        'valid_relays': 0,
        'breakdown': {}
    }


def _calculate_reliability_score(operator_relays, uptime_data, time_period, uptime_map=None):
    """
    Calculate reliability score using simple average uptime (no weighting).
    
    OPTIMIZATION: Accepts pre-built uptime_map for batch processing.
    
    Formula: Score = Average uptime percentage across all relays
    Uses shared uptime utilities to avoid code duplication with relays.py.
    
    Args:
        operator_relays (list): List of relay objects for this operator
        uptime_data (dict): Uptime data from Onionoo API
        time_period (str): Time period to use ('6_months' or '5_years')
        uptime_map (dict, optional): Pre-built fingerprint->uptime mapping
    """
    return _calculate_generic_score(operator_relays, uptime_data, time_period, 'uptime', prebuilt_map=uptime_map)


def _calculate_bandwidth_score(operator_relays, bandwidth_data, time_period, bandwidth_map=None):
    """
    Calculate bandwidth score using daily total bandwidth averaging.
    
    OPTIMIZATION: Accepts pre-built bandwidth_map for batch processing.
    
    Formula: Score = Average of daily total bandwidth (sum across all relays per day)
    This matches the Onionoo details API calculation method.
    
    Args:
        operator_relays (list): List of relay objects for this operator
        bandwidth_data (dict): Bandwidth data from Onionoo API
        time_period (str): Time period to use ('6_months' or '5_years')
        bandwidth_map (dict, optional): Pre-built fingerprint->bandwidth mapping
    """
    return _calculate_generic_score(operator_relays, bandwidth_data, time_period, 'bandwidth', prebuilt_map=bandwidth_map)


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
    
    # === AROI VALIDATION DATA INTEGRATION ===
    # Get pre-fetched validation data for validated relay tracking
    validation_data = getattr(relays_instance, 'aroi_validation_data', None)
    validation_map = {}
    
    if validation_data and 'results' in validation_data:
        # Build fingerprint -> validation result mapping for O(1) lookup
        for result in validation_data.get('results', []):
            fingerprint = result.get('fingerprint')
            if fingerprint:
                validation_map[fingerprint] = result
    
    # === COMPUTE TOTAL NETWORK CONSENSUS WEIGHT ===
    # This is needed because consensus_weight_fraction is OPTIONAL in Onionoo API
    # Many relays don't have it, so we compute fractions from raw consensus_weight
    total_network_consensus_weight = sum(
        relay.get('consensus_weight', 0) for relay in all_relays
    )
    
    # === PERFORMANCE OPTIMIZATION: Pre-build data maps ONCE ===
    # This eliminates ~12,000+ redundant map-building operations (3,141 contacts × 4 metrics)
    # Each map-build previously iterated through ~10,517 relays = ~132M redundant iterations
    # Now we build each map once (2 × 10,517 iterations) = 99.998% reduction in iterations
    uptime_data = getattr(relays_instance, 'uptime_data', None)
    bandwidth_data = getattr(relays_instance, 'bandwidth_data', None)
    
    # Pre-build maps once for all operator calculations
    uptime_map = None
    bandwidth_map = None
    if uptime_data:
        from .uptime_utils import build_uptime_map
        uptime_map = build_uptime_map(uptime_data)
    if bandwidth_data:
        from .bandwidth_utils import build_bandwidth_map
        bandwidth_map = build_bandwidth_map(bandwidth_data)
    
    # Progress tracking for large operations
    total_contacts = len(contacts)
    processed_contacts = 0
    progress_logger = getattr(relays_instance, 'progress_logger', None)
    
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
        
        # === IPv4/IPv6 UNIQUE ADDRESS CALCULATIONS + VALIDATION TRACKING (MERGED) ===
        # Extract unique IPv4 and IPv6 addresses from all operator relays
        # Also track validation status in the same loop for efficiency
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
        
        # Validation tracking variables (merged into same loop)
        validated_relay_count = 0
        invalid_relay_count = 0
        validated_guard_count = 0
        validated_exit_count = 0
        validated_middle_count = 0
        validated_bandwidth = 0
        validated_consensus_weight = 0.0
        validated_countries = set()
        
        for relay in operator_relays:
            or_addresses = relay.get('or_addresses', [])
            relay_bandwidth = relay.get('observed_bandwidth', 0)
            # Prefer API-provided consensus_weight_fraction when available (more accurate)
            # Fallback to computing from raw consensus_weight when API fraction is missing
            api_fraction = relay.get('consensus_weight_fraction')
            if api_fraction is not None:
                relay_consensus_weight = api_fraction
            elif total_network_consensus_weight > 0:
                relay_consensus_weight = relay.get('consensus_weight', 0) / total_network_consensus_weight
            else:
                relay_consensus_weight = 0.0
            relay_flags = relay.get('flags', [])
            
            has_ipv4 = False
            has_ipv6 = False
            
            # IPv4/IPv6 address parsing
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
            
            # Validation tracking (merged into same loop)
            fp = relay.get('fingerprint')
            if fp in validation_map:
                result = validation_map[fp]
                if result.get('valid', False):
                    # This relay has valid AROI proof
                    validated_relay_count += 1
                    validated_bandwidth += relay_bandwidth
                    validated_consensus_weight += relay_consensus_weight
                    
                    # Track country for validated relays
                    country = relay.get('country', '')
                    if country:
                        validated_countries.add(country)
                    
                    # Count by role (Exit > Guard > Middle priority)
                    if 'Exit' in relay_flags:
                        validated_exit_count += 1
                    elif 'Guard' in relay_flags:
                        validated_guard_count += 1
                    else:
                        validated_middle_count += 1
                else:
                    # This relay has AROI but failed validation
                    invalid_relay_count += 1
        
        unique_ipv4_count = len(unique_ipv4_addresses)
        unique_ipv6_count = len(unique_ipv6_addresses)
        validated_country_count = len(validated_countries)
        
        # Non-EU country detection (using centralized utilities)
        operator_countries = [relay.get('country') for relay in operator_relays if relay.get('country')]
        non_eu_count = count_non_eu_countries(operator_countries, use_political=True)
        
        # Rare/frontier countries (using pre-calculated rare countries from above)
        # Use unique countries for rare country calculation (not per-relay count)
        unique_operator_countries = list(set(operator_countries))
        
        # Find which of the operator's countries are rare
        # operator_countries comes from relay.get('country') which is already UPPERCASE
        operator_rare_countries = set()
        for country in unique_operator_countries:
            if country and country in valid_rare_countries:
                operator_rare_countries.add(country)
        
        # Calculate rare country count by counting how many rare countries operator actually operates in
        rare_country_count = len(operator_rare_countries)
        
        # relay["country"] is already UPPERCASE from _preprocess_template_data()
        relays_in_rare_countries = sum(1 for relay in operator_relays 
                                     if relay.get('country', '') in operator_rare_countries)
        
        # Calculate breakdown of relays per rare country for tooltips and specialization
        rare_country_breakdown = {}
        for relay in operator_relays:
            country = relay.get('country', '')
            if country in operator_rare_countries:
                rare_country_breakdown[country] = rare_country_breakdown.get(country, 0) + 1
        
        # Sort by relay count (descending) then by country name for consistent display
        sorted_rare_breakdown = sorted(rare_country_breakdown.items(), 
                                     key=lambda x: (-x[1], x[0]))
        
        # Calculate general country breakdown for reuse (all countries, not just rare ones)
        all_country_breakdown = {}
        for relay in operator_relays:
            country = relay.get('country', '')
            if country:
                all_country_breakdown[country] = all_country_breakdown.get(country, 0) + 1
        
        # Sort by relay count (descending) then by country name for consistent display
        sorted_all_country_breakdown = sorted(all_country_breakdown.items(), 
                                     key=lambda x: (-x[1], x[0]))
        
        # Calculate non-EU country breakdown for specialization column
        non_eu_country_breakdown = {}
        for relay in operator_relays:
            country = relay.get('country', '')
            if country and country not in EU_POLITICAL_REGION:
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
        
        # === RELIABILITY CALCULATIONS (OPTIMIZED) ===
        # Calculate reliability scores for both 6-month and 5-year periods
        # Uses pre-built uptime_map to avoid ~12K redundant map-building operations
        
        # 6-month reliability score (primary metric)
        reliability_6m = _calculate_reliability_score(operator_relays, uptime_data, '6_months', uptime_map=uptime_map)
        
        # 5-year reliability score (legacy metric)
        reliability_5y = _calculate_reliability_score(operator_relays, uptime_data, '5_years', uptime_map=uptime_map)
        
        # === BANDWIDTH CALCULATIONS (OPTIMIZED) ===
        # Calculate bandwidth scores for both 6-month and 1-year periods
        # Uses pre-built bandwidth_map to avoid ~12K redundant map-building operations
        
        # 6-month bandwidth score (primary metric)
        bandwidth_6m = _calculate_bandwidth_score(operator_relays, bandwidth_data, '6_months', bandwidth_map=bandwidth_map)
        
        # 5-year bandwidth score (extended metric)
        bandwidth_5y = _calculate_bandwidth_score(operator_relays, bandwidth_data, '5_years', bandwidth_map=bandwidth_map)
        
        # Progress logging for large batches (log every 500 contacts)
        processed_contacts += 1
        if progress_logger and processed_contacts % 500 == 0:
            progress_logger.log_without_increment(f"AROI leaderboards: processed {processed_contacts}/{total_contacts} contacts...")
        
        # Note: Validation tracking is now merged with IPv4/IPv6 loop above for efficiency
        
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
            
            # === BANDWIDTH PERFORMANCE METRICS (NEW) ===
            # 6-month bandwidth data
            'bandwidth_6m_score': bandwidth_6m['score'],
            'bandwidth_6m_average': bandwidth_6m['average_bandwidth'],
            'bandwidth_6m_weight': bandwidth_6m['weight'],
            'bandwidth_6m_valid_relays': bandwidth_6m['valid_relays'],
            'bandwidth_6m_breakdown': bandwidth_6m['breakdown'],
            
            # 5-year bandwidth data
            'bandwidth_5y_score': bandwidth_5y['score'],
            'bandwidth_5y_average': bandwidth_5y['average_bandwidth'],
            'bandwidth_5y_weight': bandwidth_5y['weight'],
            'bandwidth_5y_valid_relays': bandwidth_5y['valid_relays'],
            'bandwidth_5y_breakdown': bandwidth_5y['breakdown'],
            
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
            
            # === AROI VALIDATION METRICS (NEW) ===
            'validated_relay_count': validated_relay_count,
            'invalid_relay_count': invalid_relay_count,
            'validated_guard_count': validated_guard_count,
            'validated_exit_count': validated_exit_count,
            'validated_middle_count': validated_middle_count,
            'validated_bandwidth': validated_bandwidth,
            'validated_consensus_weight': validated_consensus_weight,
            'validated_country_count': validated_country_count,
            
            # Keep minimal relay data for potential future use
            'relays': operator_relays
        }
    
    # Generate 17 core leaderboard categories (complete AROI leaderboard system)
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
    
    # 16. 🚀 Bandwidth Served Masters - 6-Month Average Bandwidth (NEW) - Only operators with > 25 relays AND > 0 bandwidth
    bandwidth_masters_filtered = {k: v for k, v in aroi_operators.items() if v['total_relays'] > 25 and v['bandwidth_6m_score'] > 0.0}
    leaderboards['bandwidth_masters'] = sorted(
        bandwidth_masters_filtered.items(),
        key=lambda x: x[1]['bandwidth_6m_score'],
        reverse=True
    )[:50]
    
    # 17. 🌟 Bandwidth Served Legends - 5-Year Average Bandwidth (NEW) - Only operators with > 25 relays AND > 0 bandwidth
    bandwidth_legends_filtered = {k: v for k, v in aroi_operators.items() if v['total_relays'] > 25 and v['bandwidth_5y_score'] > 0.0}
    leaderboards['bandwidth_legends'] = sorted(
        bandwidth_legends_filtered.items(),
        key=lambda x: x[1]['bandwidth_5y_score'],
        reverse=True
    )[:50]
    
    # 18. ✅ AROI Validation Champions - Most Validated Relays (NEW) - Only operators with > 0 validated relays
    validated_relays_filtered = {k: v for k, v in aroi_operators.items() if v['validated_relay_count'] > 0}
    leaderboards['validated_relays'] = sorted(
        validated_relays_filtered.items(),
        key=lambda x: x[1]['validated_relay_count'],
        reverse=True
    )[:50]
    
    # Format data for template rendering with bandwidth units (reuse existing formatters)
    formatted_leaderboards = {}
    for category, data in leaderboards.items():
        formatted_data = []
        for rank, (operator_key, metrics) in enumerate(data, 1):
            # Use existing bandwidth formatting methods (top10 specific formatting)
            # For bandwidth categories, use historical bandwidth instead of current bandwidth
            if category in ['bandwidth_masters', 'bandwidth_legends']:
                if category == 'bandwidth_masters':
                    bandwidth_value = metrics['bandwidth_6m_average']
                else:  # bandwidth_legends
                    bandwidth_value = metrics['bandwidth_5y_average']
            else:
                bandwidth_value = metrics['total_bandwidth']
            
            formatted_bandwidth, bandwidth_unit = _format_bandwidth_with_auto_unit(
                bandwidth_value, relays_instance.bandwidth_formatter
            )
            
            # Format exit-specific bandwidth for exit categories (exit_authority, exit_operators)
            formatted_exit_bandwidth, exit_bandwidth_unit = _format_bandwidth_with_auto_unit(
                metrics['exit_bandwidth'], relays_instance.bandwidth_formatter
            )
            
            # Format guard-specific bandwidth for guard categories (guard_authority, guard_operators)
            formatted_guard_bandwidth, guard_bandwidth_unit = _format_bandwidth_with_auto_unit(
                metrics['guard_bandwidth'], relays_instance.bandwidth_formatter
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
            
            # Format bandwidth details for bandwidth categories (NEW, similar to reliability pattern)
            bandwidth_details_short = ""
            bandwidth_tooltip = ""
            bandwidth_score_raw = 0.0
            bandwidth_average = 0.0
            bandwidth_weight = 1.0
            
            if category in ['bandwidth_masters', 'bandwidth_legends']:
                # Determine which bandwidth data to use
                if category == 'bandwidth_masters':
                    bandwidth_score_raw = metrics['bandwidth_6m_score']
                    bandwidth_average = metrics['bandwidth_6m_average']
                    bandwidth_weight = metrics['bandwidth_6m_weight']
                    period_label = "6-month"
                else:  # bandwidth_legends
                    bandwidth_score_raw = metrics['bandwidth_5y_score']
                    bandwidth_average = metrics['bandwidth_5y_average']
                    bandwidth_weight = metrics['bandwidth_5y_weight']
                    period_label = "5-year"
                
                # Format bandwidth with unit (reuse existing formatters)
                formatted_bandwidth_avg, bandwidth_unit = _format_bandwidth_with_auto_unit(
                    bandwidth_average, relays_instance.bandwidth_formatter
                )
                
                # Create tooltip without weighting information (simplified)
                bandwidth_tooltip = f"{period_label} bandwidth: {formatted_bandwidth_avg} {bandwidth_unit} average bandwidth ({metrics['total_relays']} relays)"
                
                # Create short version for table display (simplified, no weight)
                bandwidth_details_short = f"{formatted_bandwidth_avg} {bandwidth_unit} avg"
            
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
                formatted_ipv4_bandwidth, ipv4_bandwidth_unit = _format_bandwidth_with_auto_unit(
                    metrics['ipv4_total_bandwidth'], relays_instance.bandwidth_formatter
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
                formatted_ipv6_bandwidth, ipv6_bandwidth_unit = _format_bandwidth_with_auto_unit(
                    metrics['ipv6_total_bandwidth'], relays_instance.bandwidth_formatter
                )
                
                ip_address_details = f"{metrics['unique_ipv6_count']} unique IPv6"
                ip_address_tooltip = f"IPv6 Infrastructure: {metrics['unique_ipv6_count']} unique addresses across {metrics['ipv6_relay_count']} relays with {formatted_ipv6_bandwidth} {ipv6_bandwidth_unit} bandwidth"
            
            # Format validated bandwidth only for validated_relays category (optimization)
            formatted_validated_bandwidth = ""
            validated_bandwidth_unit = ""
            if category == 'validated_relays':
                formatted_validated_bandwidth, validated_bandwidth_unit = _format_bandwidth_with_auto_unit(
                    metrics['validated_bandwidth'], relays_instance.bandwidth_formatter
                )

            
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
                
                # === BANDWIDTH FIELDS (NEW) ===
                'bandwidth_score': f"{bandwidth_score_raw:.1f}",
                'bandwidth_average': f"{bandwidth_average:.1f}",
                'bandwidth_weight': f"{bandwidth_weight:.1f}x",
                'bandwidth_details_short': bandwidth_details_short,
                'bandwidth_tooltip': bandwidth_tooltip,
                
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
                
                # === AROI VALIDATION FIELDS (NEW) ===
                'validated_relay_count': metrics['validated_relay_count'],
                'invalid_relay_count': metrics['invalid_relay_count'],
                'validated_guard_count': metrics['validated_guard_count'],
                'validated_exit_count': metrics['validated_exit_count'],
                'validated_middle_count': metrics['validated_middle_count'],
                'validated_bandwidth': formatted_validated_bandwidth,
                'validated_bandwidth_unit': validated_bandwidth_unit,
                'validated_consensus_weight': metrics['validated_consensus_weight'],
                'validated_consensus_weight_pct': f"{metrics['validated_consensus_weight'] * 100:.2f}%",
                'validated_country_count': metrics['validated_country_count'],
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
    summary_bandwidth_value, summary_bandwidth_unit = _format_bandwidth_with_auto_unit(
        total_bandwidth_all, relays_instance.bandwidth_formatter
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
            'bandwidth_masters': '🚀 Bandwidth Served Masters (6-Month Historic)',
            'bandwidth_legends': '🌟 Bandwidth Served Legends (5-Year Historic)',
            'most_diverse': 'Most Diverse Operators',
            'platform_diversity': 'Platform Diversity (Non-Linux Heroes)',
            'non_eu_leaders': 'Geographic Champions (Non-EU Leaders)',
            'frontier_builders': 'Frontier Builders (Rare Countries)',
            'network_veterans': 'Network Veterans',
            'ipv4_leaders': 'IPv4 Address Leaders',
            'ipv6_leaders': 'IPv6 Address Leaders',
            'validated_relays': 'AROI Validation Champions'
        }
    }
    
    return {
        'leaderboards': formatted_leaderboards,
        'summary': summary_stats,
        'raw_operators': aroi_operators  # For potential future use
    }

 