"""
File: network_health.py

Network health dashboard metrics calculation and template string pre-formatting.
Extracted from relays.py for better modularity.
"""

from .ip_utils import safe_parse_ip_address as _safe_parse_ip_address
from .ip_utils import is_private_ip_address, determine_ipv6_support
from .time_utils import parse_onionoo_timestamp, create_time_thresholds
from .string_utils import format_percentage_from_fraction
from .consensus.consensus_evaluation import _port_in_rules


def _pct(numerator, denominator):
    """Safe percentage calculation: (numerator / denominator * 100) or 0.0 if denominator is 0."""
    return (numerator / denominator * 100) if denominator > 0 else 0.0


def _safe_mean(values):
    """Return statistics.mean(values) if non-empty, else 0.0."""
    import statistics as _stats
    return _stats.mean(values) if values else 0.0


def _safe_median(values):
    """Return statistics.median(values) if non-empty, else 0.0."""
    import statistics as _stats
    return _stats.median(values) if values else 0.0


def preformat_network_health_template_strings(health_metrics):
    """
    OPTIMIZATION: Pre-format all template strings to eliminate Jinja2 formatting overhead.
    
    Replaces dozens of template format operations like {{ "{:,}".format(...) }} and 
    {{ "%.1f%%"|format(...) }} with pre-computed Python strings. This provides 3-5x
    speedup since Jinja2 formatting goes through the template engine interpretation layer.
    
    Args:
        health_metrics (dict): Network health metrics dictionary to add formatted strings to
    """
    # Format all number values with comma separators (16+ format operations eliminated)
    integer_format_keys = [
        'relays_total', 'exit_count', 'guard_count', 'middle_count', 'authorities_count',
        'bad_exits_count', 'offline_relays', 'overloaded_relays',  # REMOVED: hibernating_relays
        # NEW: Additional flag counts
        'fast_count', 'stable_count', 'v2dir_count', 'hsdir_count', 'stabledesc_count', 'sybil_count',
        'new_relays_24h', 'new_relays_30d', 'new_relays_6m', 'new_relays_1y',
        'measured_relays', 'aroi_operators_count', 'relays_with_contact', 'relays_without_contact',
        'families_count', 'relays_with_family', 'relays_without_family', 'unique_contacts_count',
        'countries_count', 'unique_as_count', 'unique_platforms_count', 'platform_others',
        'recommended_version_count', 'not_recommended_count', 'experimental_count', 
        'obsolete_count', 'outdated_count', 'guard_exit_count', 'unrestricted_exits',
        'restricted_exits', 'web_traffic_exits', 'eu_relays_count', 'non_eu_relays_count',
        'rare_countries_relays', 'ipv4_only_relays', 'both_ipv4_ipv6_relays',
        # NEW: AROI domain-level metrics
        'unique_aroi_domains_count', 'validated_aroi_domains_count', 'invalid_aroi_domains_count',
        # NEW: IPv6 AROI operator metrics
        'ipv4_only_aroi_operators', 'both_ipv4_ipv6_aroi_operators',
        # NEW: Happy Family Key Migration metrics
        'hf_ready_relays', 'hf_ready_exit_relays', 'hf_ready_guard_relays',
        'hf_ready_authorities', 'hf_some_operators', 'hf_all_operators',
        'hf_not_ready_relays', 'hf_total_validated_operators',
        'hf_family_cert_count', 'hf_family_no_cert_count',
    ]
    
    for key in integer_format_keys:
        if key in health_metrics:
            health_metrics[f'{key}_formatted'] = f"{health_metrics[key]:,}"
    
    # Format all percentage values with 1 decimal place (12+ format operations eliminated)
    percentage_format_keys = [
        'exit_percentage', 'guard_percentage', 'middle_percentage', 'authorities_percentage',
        'bad_exits_percentage', 'offline_relays_percentage', 'overloaded_relays_percentage',
        # REMOVED: 'hibernating_relays_percentage',
        # NEW: Additional flag percentages
        'fast_percentage', 'stable_percentage', 'v2dir_percentage', 'hsdir_percentage',
        'stabledesc_percentage', 'sybil_percentage',
        'new_relays_24h_percentage', 'new_relays_30d_percentage',
        'new_relays_6m_percentage', 'new_relays_1y_percentage', 'measured_percentage',
        'relays_with_contact_percentage', 'relays_without_contact_percentage',
        'relays_with_family_percentage', 'relays_without_family_percentage',
        'recommended_version_percentage', 'not_recommended_percentage', 'experimental_percentage',
        'obsolete_percentage', 'outdated_percentage', 'eu_consensus_weight_percentage',
        'non_eu_consensus_weight_percentage', 'rare_countries_consensus_weight_percentage',
        'eu_relays_percentage', 'non_eu_relays_percentage', 'rare_countries_relays_percentage',
        'top_3_as_concentration', 'top_5_as_concentration', 'top_10_as_concentration',
        # REFACTORED: Generate percentage format keys using consistent pattern
        'overall_uptime',
        'ipv4_only_relays_percentage', 'both_ipv4_ipv6_relays_percentage',
        'ipv4_only_bandwidth_percentage', 'both_ipv4_ipv6_bandwidth_percentage',
        # NEW: IPv6 AROI operator percentages
        'ipv4_only_aroi_operators_percentage', 'both_ipv4_ipv6_aroi_operators_percentage',
        # NEW: AROI domain percentages
        'validated_aroi_domains_percentage', 'invalid_aroi_domains_percentage',
        # NEW: Happy Family Key Migration percentages
        'hf_ready_relays_percentage', 'hf_ready_bandwidth_percentage',
        'hf_ready_cw_percentage', 'hf_some_operators_percentage',
        'hf_all_operators_percentage', 'hf_not_ready_relays_percentage',
    ]
    
    # Add 1_month period formatting keys (used directly in templates) 
    roles = ['exit', 'guard', 'middle', 'authority', 'v2dir', 'hsdir']
    statistics = ['mean', 'median']
    for role in roles:
        for stat in statistics:
            percentage_format_keys.append(f'{role}_uptime_1_month_{stat}')
    
    for key in percentage_format_keys:
        if key in health_metrics:
            health_metrics[f'{key}_formatted'] = f"{health_metrics[key]:.1f}%"
    
    # Format uptime time series data (4+ format operations eliminated)
    # Using consistent naming pattern: {role}_uptime_{period}_mean
    uptime_series_keys = [
        ('exit_uptime_1_month_mean', 'exit_uptime_6_months_mean', 'exit_uptime_1_year_mean', 'exit_uptime_5_years_mean'),
        ('guard_uptime_1_month_mean', 'guard_uptime_6_months_mean', 'guard_uptime_1_year_mean', 'guard_uptime_5_years_mean'),
        ('middle_uptime_1_month_mean', 'middle_uptime_6_months_mean', 'middle_uptime_1_year_mean', 'middle_uptime_5_years_mean'),
        ('authority_uptime_1_month_mean', 'authority_uptime_6_months_mean', 'authority_uptime_1_year_mean', 'authority_uptime_5_years_mean')
    ]
    
    for keys in uptime_series_keys:
        role = keys[0].split('_')[0]  # extract 'exit', 'guard', or 'middle'
        formatted_values = []
        for key in keys:
            if key in health_metrics:
                formatted_values.append(f"{health_metrics[key]:.1f}%")
            else:
                formatted_values.append("0.0%")
        health_metrics[f'{role}_uptime_series_formatted'] = " | ".join(formatted_values)
    
    # Format Top 3 AS data (loop with format operations eliminated)
    if 'top_3_as' in health_metrics:
        for as_info in health_metrics['top_3_as']:
            as_info['consensus_weight_percentage_formatted'] = f"{as_info['consensus_weight_percentage']:.1f}%"
    
    # Format Top 3 Countries data
    if 'top_3_countries' in health_metrics:
        for country_info in health_metrics['top_3_countries']:
            country_info['consensus_weight_percentage_formatted'] = f"{country_info['consensus_weight_percentage']:.1f}%"
    
    # Format platform data (loop with format operations eliminated)  
    if 'platform_top3' in health_metrics:
        formatted_platform_data = []
        for platform_data in health_metrics['platform_top3']:
            if len(platform_data) >= 3:  # (platform, count, percentage)
                formatted_platform_data.append((
                    platform_data[0],  # platform name
                    f"{platform_data[1]:,}",  # formatted count
                    f"{platform_data[2]:.0f}%"  # formatted percentage
                ))
            else:
                formatted_platform_data.append(platform_data)
        health_metrics['platform_top3_formatted'] = formatted_platform_data
    
    # Format combined count + percentage strings (8+ format operations eliminated)
    combined_format_mappings = [
        ('exit_count', 'exit_percentage', 'exit_count_with_percentage'),
        ('guard_count', 'guard_percentage', 'guard_count_with_percentage'),
        ('middle_count', 'middle_percentage', 'middle_count_with_percentage'),
        ('authorities_count', 'authorities_percentage', 'authorities_count_with_percentage'),
        ('bad_exits_count', 'bad_exits_percentage', 'bad_exits_count_with_percentage'),
        # NEW: Additional flag count + percentage combinations
        ('fast_count', 'fast_percentage', 'fast_count_with_percentage'),
        ('stable_count', 'stable_percentage', 'stable_count_with_percentage'),
        ('v2dir_count', 'v2dir_percentage', 'v2dir_count_with_percentage'),
        ('hsdir_count', 'hsdir_percentage', 'hsdir_count_with_percentage'),
        ('stabledesc_count', 'stabledesc_percentage', 'stabledesc_count_with_percentage'),
        ('sybil_count', 'sybil_percentage', 'sybil_count_with_percentage'),
        ('offline_relays', 'offline_relays_percentage', 'offline_relays_with_percentage'),
        ('measured_relays', 'measured_percentage', 'measured_relays_with_percentage'),
        ('relays_with_contact', 'relays_with_contact_percentage', 'relays_with_contact_formatted')
    ]
    
    for count_key, pct_key, combined_key in combined_format_mappings:
        if count_key in health_metrics and pct_key in health_metrics:
            count_formatted = f"{health_metrics[count_key]:,}"
            pct_formatted = format_percentage_from_fraction(health_metrics[pct_key] / 100, 1, "0.0%")
            health_metrics[combined_key] = f"{count_formatted} ({pct_formatted})"

def _integrate_aroi_validation(health_metrics, relay_set, total_relays_count):
    """
    Integrate AROI validation metrics into health dashboard.
    
    Calculates relay-level and operator-level AROI validation statistics,
    IPv6 support among validated operators, and stores the validation map
    for reuse by contact pages.
    
    Extracted from calculate_network_health_metrics for readability.
    """
    try:
        from .aroi_validation import calculate_aroi_validation_metrics
        
        # Get pre-fetched validation data (attached by coordinator)
        validation_data = getattr(relay_set, 'aroi_validation_data', None)
        
        # Calculate validation metrics (relay AND operator level in single pass)
        validation_metrics = calculate_aroi_validation_metrics(
            relay_set.json.get('relays', []), 
            validation_data,
            calculate_operator_metrics=True
        )
        
        # Store validation_map for reuse by contact pages (avoids rebuilding 3,000+ times)
        relay_set.validation_map = validation_metrics.pop('_validation_map', {})
        
        # Add validation metrics to health_metrics
        health_metrics.update(validation_metrics)
        
        # Calculate total relays with AROI (validated + invalid)
        total_relays_with_aroi = (
            validation_metrics.get('aroi_validated_count', 0) + 
            validation_metrics.get('aroi_unvalidated_count', 0)
        )
        
        # Calculate percentages relative to AROI relays
        if total_relays_with_aroi > 0:
            aroi_validated_pct_of_aroi = (
                validation_metrics['aroi_validated_count'] / total_relays_with_aroi * 100
            )
            aroi_invalid_pct_of_aroi = (
                validation_metrics['aroi_unvalidated_count'] / total_relays_with_aroi * 100
            )
        else:
            aroi_validated_pct_of_aroi = 0.0
            aroi_invalid_pct_of_aroi = 0.0
        
        # Add derived metrics
        health_metrics['total_relays_with_aroi'] = total_relays_with_aroi
        health_metrics['total_relays_with_aroi_percentage'] = _pct(total_relays_with_aroi, total_relays_count)
        health_metrics['aroi_validated_percentage_of_aroi'] = aroi_validated_pct_of_aroi
        health_metrics['aroi_invalid_percentage_of_aroi'] = aroi_invalid_pct_of_aroi
        
        # Calculate relays without AROI
        relays_without_aroi = total_relays_count - total_relays_with_aroi
        health_metrics['relays_without_aroi'] = relays_without_aroi
        health_metrics['relays_without_aroi_percentage'] = _pct(relays_without_aroi, total_relays_count)
        
        # Extract validated domain set for IPv6 calculation
        validated_domain_set = validation_metrics.get('_validated_domain_set', set())
        validated_aroi_domains = validation_metrics.get('validated_aroi_domains_count', 0)
        unique_aroi_domains_count = validation_metrics.get('unique_aroi_domains_count', 0)
        
        # Store validated domain set for vanity URL generation later
        relay_set.validated_aroi_domains = validated_domain_set
        
        # Update aroi_operators_count to use accurate AROI domain count
        health_metrics['aroi_operators_count'] = unique_aroi_domains_count
        
        # Get IPv6 status dict from earlier calculation
        operator_ipv6_status = health_metrics.pop('_temp_operator_ipv6_status', {})
        
        # Count IPv6 support ONLY among validated operators (mutually exclusive)
        both_ipv4_ipv6_aroi_operators = sum(1 for domain in validated_domain_set 
                                        if domain in operator_ipv6_status and operator_ipv6_status[domain]['has_dual_stack'])
        ipv4_only_aroi_operators = sum(1 for domain in validated_domain_set
                                   if domain in operator_ipv6_status and not operator_ipv6_status[domain]['has_dual_stack'] and operator_ipv6_status[domain]['has_ipv4_only'])
        
        health_metrics['ipv4_only_aroi_operators'] = ipv4_only_aroi_operators
        health_metrics['both_ipv4_ipv6_aroi_operators'] = both_ipv4_ipv6_aroi_operators
        
        # Calculate IPv6 operator percentages based on validated operators count
        if validated_aroi_domains > 0:
            health_metrics['ipv4_only_aroi_operators_percentage'] = _pct(ipv4_only_aroi_operators, validated_aroi_domains)
            health_metrics['both_ipv4_ipv6_aroi_operators_percentage'] = _pct(both_ipv4_ipv6_aroi_operators, validated_aroi_domains)
        else:
            health_metrics['ipv4_only_aroi_operators_percentage'] = 0.0
            health_metrics['both_ipv4_ipv6_aroi_operators_percentage'] = 0.0
        
        # Calculate average relays per operator
        aroi_operators_count = health_metrics.get('aroi_operators_count', 0)
        if aroi_operators_count > 0:
            health_metrics['avg_relays_per_aroi_operator'] = round(
                total_relays_with_aroi / aroi_operators_count, 2
            )
        else:
            health_metrics['avg_relays_per_aroi_operator'] = 0.0
                
    except Exception as e:
        # Graceful fallback if validation data unavailable
        if relay_set.progress:
            print(f"⚠️  AROI Validation: Error loading data: {e}")
        health_metrics.update({
            'aroi_validated_count': 0,
            'aroi_unvalidated_count': 0,
            'aroi_no_proof_count': 0,
            'relays_no_aroi': 0,
            'relays_without_aroi': total_relays_count,
            'relays_without_aroi_percentage': 100.0 if total_relays_count > 0 else 0.0,
            'aroi_validated_percentage': 0.0,
            'aroi_unvalidated_percentage': 0.0,
            'aroi_no_proof_percentage': 0.0,
            'relays_no_aroi_percentage': 0.0,
            'aroi_validation_success_rate': 0.0,
            'dns_rsa_success_rate': 0.0,
            'uri_rsa_success_rate': 0.0,
            'validation_data_available': False,
            'total_relays_with_aroi': 0,
            'total_relays_with_aroi_percentage': 0.0,
            'aroi_validated_percentage_of_aroi': 0.0,
            'aroi_invalid_percentage_of_aroi': 0.0,
            'avg_relays_per_aroi_operator': 0.0,
            'unique_aroi_domains_count': 0,
            'validated_aroi_domains_count': 0,
            'invalid_aroi_domains_count': 0,
            'validated_aroi_domains_percentage': 0.0,
            'invalid_aroi_domains_percentage': 0.0,
            'relay_error_top5': [],
            'operator_error_top5': [],
            'dns_error_top5': [],
            'uri_error_top5': [],
            'no_aroi_reasons_top5': [],
            'top_operators_text': 'No data available',
            'ipv4_only_aroi_operators': 0,
            'both_ipv4_ipv6_aroi_operators': 0,
            'ipv4_only_aroi_operators_percentage': 0.0,
            'both_ipv4_ipv6_aroi_operators_percentage': 0.0
        })


def calculate_network_health_metrics(relay_set):
    """
    ULTRA-OPTIMIZED: Calculate network health metrics in single pass with maximum reuse.
    
    OPTIMIZATIONS APPLIED:
    1. Single loop through relays instead of 3 separate loops
    2. Reuse existing network_totals and sorted data 
    3. Pre-calculate all Jinja2 template values
    4. Consolidate uptime calculations for all periods
    5. Use existing data structures where possible
    """
    # Ensure prerequisites are available
    if 'network_totals' not in relay_set.json:
        relay_set._calculate_network_totals()
    if 'sorted' not in relay_set.json:
        relay_set._categorize()
    
    network_totals = relay_set.json['network_totals']
    sorted_data = relay_set.json['sorted']
    
    # REUSE EXISTING DATA - no recalculation needed
    total_relays_count = network_totals['total_relays']
    health_metrics = {
        'relays_total': total_relays_count,
        'guard_count': network_totals['guard_count'],
        'middle_count': network_totals['middle_count'], 
        'exit_count': network_totals['exit_count'],
        'measured_relays': network_totals['measured_relays'],
        'measured_percentage': network_totals['measured_percentage'],
        'countries_count': len(sorted_data.get('country', {})),
        'unique_as_count': len(sorted_data.get('as', {})),
        # Add percentages for relay counts
        'guard_percentage': _pct(network_totals['guard_count'], total_relays_count),
        'middle_percentage': _pct(network_totals['middle_count'], total_relays_count),
        'exit_percentage': _pct(network_totals['exit_count'], total_relays_count)
    }
    
    # OPTIMIZED: Reuse cached unique families count from _calculate_and_cache_family_statistics()
    # This eliminates duplicate deduplication loops for better performance
    health_metrics['families_count'] = relay_set.json.get('family_statistics', {}).get('unique_families_count', 0)
    
    # AROI operators - reuse existing calculation
    if hasattr(relay_set, 'json') and 'aroi_leaderboards' in relay_set.json:
        aroi_summary = relay_set.json['aroi_leaderboards'].get('summary', {})
        health_metrics['aroi_operators_count'] = aroi_summary.get('total_operators', 0)
    else:
        health_metrics['aroi_operators_count'] = len(sorted_data.get('contact', {}))
    
    # Import modules once
    import statistics
    import datetime
    from .country_utils import is_eu_political, is_frontier_country
    from .uptime_utils import find_relay_uptime_data, calculate_relay_uptime_average
    
    # Time calculations for new relay detection - use centralized function
    time_thresholds = create_time_thresholds()
    now = time_thresholds['now']
    day_ago = time_thresholds['day_ago']
    month_ago = time_thresholds['month_ago']
    year_ago = time_thresholds['year_ago']
    six_months_ago = time_thresholds['six_months_ago']
    
    # Get rare countries once
    valid_rare_countries = set()
    try:
        if 'country' in sorted_data:
            from .country_utils import get_rare_countries_weighted_with_existing_data
            all_rare_countries = get_rare_countries_weighted_with_existing_data(
                sorted_data['country'], network_totals['total_relays'])
            valid_rare_countries = {c.lower() for c in all_rare_countries if len(c) == 2 and c.isalpha()}
    except:
        pass
    
    # Initialize all counters and collectors for SINGLE LOOP
    authority_count = bad_exit_count = 0
    # NEW: Additional flag counts
    fast_count = stable_count = v2dir_count = hsdir_count = 0
    stabledesc_count = sybil_count = 0
    total_bandwidth = guard_bandwidth = exit_bandwidth = middle_bandwidth = 0
    # NEW: Additional flag-specific bandwidth collectors
    fast_bandwidth_values = []
    stable_bandwidth_values = []
    authority_bandwidth_values = []
    v2dir_bandwidth_values = []
    hsdir_bandwidth_values = []
    relays_with_family = relays_without_family = 0
    relays_with_contact = relays_without_contact = 0
    unique_contacts = set()
    eu_relays = non_eu_relays = rare_countries_relays = 0
    eu_consensus_weight = non_eu_consensus_weight = rare_countries_consensus_weight = 0
    offline_relays = overloaded_relays = 0  # REMOVED: hibernating_relays
    new_relays_24h = new_relays_30d = new_relays_1y = new_relays_6m = 0
    unique_platforms = set()
    platform_counts = {}
    recommended_version_count = not_recommended_count = 0
    experimental_count = obsolete_count = outdated_count = 0
    total_consensus_weight = total_advertised_bandwidth = 0
    observed_advertised_diff_sum = observed_advertised_count = 0
    observed_advertised_diff_values = []
    
    # NEW: Age calculations
    relay_ages_days = []
    
    # NEW: Exit policy analysis
    guard_exit_count = 0
    port_restricted_exits = 0
    port_unrestricted_exits = 0
    ip_unrestricted_exits = 0
    ip_restricted_exits = 0
    no_port_restrictions_and_no_ip_restrictions = 0  # NEW: Combined metric for both no port AND no IP restrictions
    web_traffic_exits = 0
    
    # Role-specific collectors - combined into single loop
    exit_cw_values = []
    guard_cw_values = []
    middle_cw_values = []
    exit_bw_values = []
    guard_bw_values = []
    middle_bw_values = []
    exit_cw_sum = exit_bw_sum = 0
    guard_cw_sum = guard_bw_sum = 0  
    middle_cw_sum = middle_bw_sum = 0
    
    # NEW: Geographic CW/BW ratio collectors
    eu_cw_bw_values = []
    non_eu_cw_bw_values = []
    
    # OPTIMIZATION: AS-specific CW/BW collectors (eliminates need for separate relay loop)
    as_cw_bw_data = {}  # as_number -> [cw_bw_ratios]
    
    # NEW: IPv6 support analysis - relay-level counters
    ipv4_only_relays = 0
    both_ipv4_ipv6_relays = 0
    
    # NEW: IPv6 support analysis - bandwidth-level counters
    ipv4_only_bandwidth = 0
    both_ipv4_ipv6_bandwidth = 0
    
    # NEW: IPv6 support analysis - country-level collections
    ipv4_only_countries = {}  # country -> count
    both_ipv4_ipv6_countries = {}  # country -> count
    
    # NEW: IPv6 support analysis - AS-level collections
    ipv4_only_as = {}  # as_number -> count
    both_ipv4_ipv6_as = {}  # as_number -> count
    
    # NEW: IPv6 support analysis - operator-level collections
    # Track what types of relays each operator has to determine their overall support
    operator_ipv6_status = {}  # domain -> {'has_ipv4_only': bool, 'has_dual_stack': bool}
    
    # NEW: Happy Family Key Migration tracking
    def _is_happy_family_ready(version_str):
        """Check if relay version supports Happy Families (>= 0.4.9.1).
        
        Per Proposal 321: family-cert was implemented in Tor 0.4.9.1-alpha
        (first alpha in the 0.4.9 series). The community setup guide at
        community.torproject.org/relay/setup/post-install/family-ids/
        specifies "Tor 0.4.9.2-alpha and later" for the keygen-family tool.
        We use 0.4.9.1 as the minimum since that's when the protocol support
        was added to the codebase.
        """
        if not version_str:
            return False
        try:
            clean = version_str.split('-')[0]
            parts = [int(p) for p in clean.split('.')]
            while len(parts) < 4:
                parts.append(0)
            return tuple(parts) >= (0, 4, 9, 1)
        except (ValueError, IndexError):
            return False
    
    family_key_ready_relays = 0
    family_key_ready_exit_relays = 0
    family_key_ready_guard_relays = 0
    family_key_ready_bandwidth = 0
    family_key_ready_cw = 0
    operator_relay_versions = {}  # aroi_domain -> {'total': N, 'ready': N}
    
    # Uptime data will be extracted from existing consolidated results after uptime API processing
    
    # SINGLE LOOP - calculate everything at once
    for relay in relay_set.json['relays']:
        # Basic relay categorization
        flags = relay.get('flags', [])
        is_guard = 'Guard' in flags
        is_exit = 'Exit' in flags
        is_authority = 'Authority' in flags
        is_bad_exit = 'BadExit' in flags
        # NEW: Additional flag checks
        is_fast = 'Fast' in flags
        is_stable = 'Stable' in flags
        is_v2dir = 'V2Dir' in flags
        is_hsdir = 'HSDir' in flags
        is_stabledesc = 'StaleDesc' in flags
        is_sybil = 'Sybil' in flags
        is_running = relay.get('running', True)
        # REMOVED: is_hibernating
        # Use pre-computed stability field (computed in _reprocess_bandwidth_data)
        is_overloaded = relay.get('stability_is_overloaded', False)
        
        # Counts
        if is_authority:
            authority_count += 1
        if is_bad_exit:
            bad_exit_count += 1
        # NEW: Additional flag counts
        if is_fast:
            fast_count += 1
        if is_stable:
            stable_count += 1
        if is_v2dir:
            v2dir_count += 1
        if is_hsdir:
            hsdir_count += 1
        if is_stabledesc:
            stabledesc_count += 1
        if is_sybil:
            sybil_count += 1
        if not is_running:
            offline_relays += 1
        if is_overloaded:
            overloaded_relays += 1
        # REMOVED: hibernating count
        
        # NEW: Guard+Exit flag combination
        if is_guard and is_exit:
            guard_exit_count += 1
        
        # NEW: Exit policy analysis
        if is_exit:
            # Basic exit policy analysis using proper port range parsing
            # Reuses _port_in_rules from consensus_evaluation (DRY) which correctly
            # handles Onionoo exit_policy_summary format: '80', '443', '1-65535', etc.
            exit_policy_summary = relay.get('exit_policy_summary', {})
            ipv4_summary = exit_policy_summary.get('accept', [])
            
            # Check for web traffic (ports 80 or 443)
            has_web_traffic_ports = (
                _port_in_rules(ipv4_summary, 80) or _port_in_rules(ipv4_summary, 443)
            )
            
            if has_web_traffic_ports:
                web_traffic_exits += 1
            
            # Check for unrestricted exits — Onionoo normalizes full-range to '1-65535'
            is_port_unrestricted = '1-65535' in ipv4_summary
            
            if is_port_unrestricted:
                port_unrestricted_exits += 1
            else:
                port_restricted_exits += 1
            
            # Check for IP address restrictions (excluding private/local IP ranges)
            # An exit relay has IP address restrictions only if it restricts public IP addresses
            # Restrictions on private/local IP ranges (192.168.x, 10.x, etc.) are not counted
            # as meaningful restrictions since they don't limit access to public internet resources
            has_ip_restrictions = False
            
            # Check full exit_policy for reject rules with public IP restrictions
            exit_policy = relay.get('exit_policy', [])
            for rule in exit_policy:
                if rule.startswith('reject ') and ':' in rule:
                    # Extract IP part from "reject IP:PORT" rule using safe parsing
                    rule_part = rule[7:]  # Remove "reject "
                    if ':' in rule_part:
                        # Use safe IP parsing to extract IP part
                        parsed_ip, _ = _safe_parse_ip_address(rule_part)
                        # If it's a valid IP and not a private IP, it's a public IP restriction
                        if parsed_ip and not is_private_ip_address(parsed_ip):
                            has_ip_restrictions = True
                            break
            
            if has_ip_restrictions:
                ip_restricted_exits += 1
            else:
                ip_unrestricted_exits += 1
            
            # NEW: Track exits with BOTH no port restrictions AND no IP restrictions
            if is_port_unrestricted and not has_ip_restrictions:
                no_port_restrictions_and_no_ip_restrictions += 1
        
        # NEW: Age calculation using first_seen - use centralized parsing
        first_seen_str = relay.get('first_seen', '')
        if first_seen_str:
            first_seen = parse_onionoo_timestamp(first_seen_str)
            if first_seen:
                # Convert to naive datetime for comparison (since time_thresholds use naive datetimes)
                first_seen_naive = first_seen.replace(tzinfo=None)
                age_days = (now - first_seen_naive).days
                if age_days >= 0:  # Sanity check
                    relay_ages_days.append(age_days)
                    
                    # Count new relays for existing metrics
                    if first_seen_naive >= day_ago:
                        new_relays_24h += 1
                    if first_seen_naive >= month_ago:
                        new_relays_30d += 1
                    if first_seen_naive >= year_ago:
                        new_relays_1y += 1
                    if first_seen_naive >= six_months_ago:
                        new_relays_6m += 1
        
        # Platform tracking
        platform = relay.get('platform', 'Unknown')
        unique_platforms.add(platform)
        platform_counts[platform] = platform_counts.get(platform, 0) + 1
        
        # Version tracking
        recommended = relay.get('recommended_version')
        version_status = relay.get('version_status', '').lower()
        
        if recommended is True:
            recommended_version_count += 1
        elif recommended is False:
            not_recommended_count += 1
        
        if version_status == 'experimental':
            experimental_count += 1
        elif version_status == 'obsolete':
            obsolete_count += 1
        elif version_status in ['unrecommended', 'old']:
            outdated_count += 1
        
        # Happy Family Key Migration tracking (version-based)
        relay_version = relay.get('version', '')
        is_family_ready = _is_happy_family_ready(relay_version)
        
        # Bandwidth calculations
        bandwidth = relay.get('observed_bandwidth', 0)
        consensus_weight = relay.get('consensus_weight', 0)
        total_bandwidth += bandwidth
        advertised_bandwidth = relay.get('advertised_bandwidth', 0)
        total_consensus_weight += consensus_weight
        total_advertised_bandwidth += advertised_bandwidth
        
        if bandwidth > 0 and advertised_bandwidth > 0:
            diff = abs(bandwidth - advertised_bandwidth)
            observed_advertised_diff_sum += diff
            observed_advertised_count += 1
            observed_advertised_diff_values.append(diff)
        
        # Happy Family: accumulate counts (is_family_ready set above with version check)
        if is_family_ready:
            family_key_ready_relays += 1
            family_key_ready_bandwidth += bandwidth
            family_key_ready_cw += consensus_weight
            if is_exit:
                family_key_ready_exit_relays += 1
            if is_guard:
                family_key_ready_guard_relays += 1
        
        # Role-specific bandwidth and consensus weight - combined calculation
        if is_exit:
            exit_bandwidth += bandwidth
            if consensus_weight > 0 and bandwidth > 0:
                exit_cw_sum += consensus_weight
                exit_bw_sum += bandwidth
                exit_cw_values.append(consensus_weight / bandwidth)
                exit_bw_values.append(bandwidth)
        elif is_guard:
            guard_bandwidth += bandwidth
            if consensus_weight > 0 and bandwidth > 0:
                guard_cw_sum += consensus_weight
                guard_bw_sum += bandwidth
                guard_cw_values.append(consensus_weight / bandwidth)
                guard_bw_values.append(bandwidth)
        else:
            middle_bandwidth += bandwidth
            if consensus_weight > 0 and bandwidth > 0:
                middle_cw_sum += consensus_weight
                middle_bw_sum += bandwidth
                middle_cw_values.append(consensus_weight / bandwidth)
                middle_bw_values.append(bandwidth)
        
        # NEW: Flag-specific bandwidth collection for additional metrics
        if bandwidth > 0:  # Only collect bandwidth for relays with actual bandwidth
            if is_fast:
                fast_bandwidth_values.append(bandwidth)
            if is_stable:
                stable_bandwidth_values.append(bandwidth)
            if is_authority:
                authority_bandwidth_values.append(bandwidth)
            if is_v2dir:
                v2dir_bandwidth_values.append(bandwidth)
            if is_hsdir:
                hsdir_bandwidth_values.append(bandwidth)
        
        # Family and contact info
        effective_family = relay.get('effective_family', [])
        if effective_family and len(effective_family) > 1:
            relays_with_family += 1
        else:
            relays_without_family += 1
        
        contact = relay.get('contact', '').strip()
        unique_contacts.add(contact)
        if contact:
            relays_with_contact += 1
        else:
            relays_without_contact += 1
        
        # Geographic data - relay["country"] already UPPERCASE from _preprocess_template_data()
        country = relay.get('country', '')
        if country and len(country) == 2:
            if is_eu_political(country):
                eu_relays += 1
                eu_consensus_weight += consensus_weight
                # NEW: Collect EU CW/BW ratios for mean/median calculation
                if consensus_weight > 0 and bandwidth > 0:
                    eu_cw_bw_values.append(consensus_weight / bandwidth * 1000000)
            else:
                non_eu_relays += 1
                non_eu_consensus_weight += consensus_weight
                # NEW: Collect Non-EU CW/BW ratios for mean/median calculation
                if consensus_weight > 0 and bandwidth > 0:
                    non_eu_cw_bw_values.append(consensus_weight / bandwidth * 1000000)
            
            if country.lower() in valid_rare_countries or (not valid_rare_countries and is_frontier_country(country)):
                rare_countries_relays += 1
                rare_countries_consensus_weight += consensus_weight
                
        # OPTIMIZATION: AS-specific CW/BW collection (eliminates separate loop)
        as_number = relay.get('as')
        if as_number and consensus_weight > 0 and bandwidth > 0:
            cw_bw_ratio = consensus_weight / bandwidth * 1000000
            if as_number not in as_cw_bw_data:
                as_cw_bw_data[as_number] = []
            as_cw_bw_data[as_number].append(cw_bw_ratio)
        
        # NEW: IPv6 support analysis - determine IP version support for this relay
        or_addresses = relay.get('or_addresses', [])
        ipv6_support = determine_ipv6_support(or_addresses)
        relay['ipv6_support'] = ipv6_support  # Store for template O(1) access
        
        # Count relay-level IPv6 support
        if ipv6_support == 'ipv4_only':
            ipv4_only_relays += 1
            ipv4_only_bandwidth += bandwidth
        elif ipv6_support == 'both':
            both_ipv4_ipv6_relays += 1
            both_ipv4_ipv6_bandwidth += bandwidth
        
        # Country-level IPv6 support tracking
        if country and len(country) == 2:
            if ipv6_support == 'ipv4_only':
                ipv4_only_countries[country] = ipv4_only_countries.get(country, 0) + 1
            elif ipv6_support == 'both':
                both_ipv4_ipv6_countries[country] = both_ipv4_ipv6_countries.get(country, 0) + 1
        
        # AS-level IPv6 support tracking
        if as_number:
            if ipv6_support == 'ipv4_only':
                ipv4_only_as[as_number] = ipv4_only_as.get(as_number, 0) + 1
            elif ipv6_support == 'both':
                both_ipv4_ipv6_as[as_number] = both_ipv4_ipv6_as.get(as_number, 0) + 1
        
        # Operator-level IPv6 support tracking (uses AROI domain for consistency with Option B)
        aroi_domain = relay.get('aroi_domain', 'none')
        if aroi_domain and aroi_domain != 'none':
            if aroi_domain not in operator_ipv6_status:
                operator_ipv6_status[aroi_domain] = {'has_ipv4_only': False, 'has_dual_stack': False}
            
            if ipv6_support == 'ipv4_only':
                operator_ipv6_status[aroi_domain]['has_ipv4_only'] = True
            elif ipv6_support == 'both':
                operator_ipv6_status[aroi_domain]['has_dual_stack'] = True
            
            # Happy Family: per-operator version readiness (reuses aroi_domain from above)
            if aroi_domain not in operator_relay_versions:
                operator_relay_versions[aroi_domain] = {'total': 0, 'ready': 0}
            operator_relay_versions[aroi_domain]['total'] += 1
            if is_family_ready:
                operator_relay_versions[aroi_domain]['ready'] += 1
        
        # Skip uptime calculation here - will use existing consolidated results
    
    # NEW: Calculate age statistics
        # Skip uptime calculation here - will use existing consolidated results
    
    # NEW: Calculate age statistics
    def _format_age(days):
        """Format age in days to 'Xy Zmo' format"""
        if days < 30:
            return f"{days}d"
        elif days < 365:
            months = days // 30
            remaining_days = days % 30
            if remaining_days == 0:
                return f"{months}mo"
            else:
                return f"{months}mo {remaining_days}d"
        else:
            years = days // 365
            remaining_days = days % 365
            months = remaining_days // 30
            if months == 0:
                return f"{years}y"
            else:
                return f"{years}y {months}mo"
    
    if relay_ages_days:
        mean_age_days = statistics.mean(relay_ages_days)
        median_age_days = statistics.median(relay_ages_days)
        health_metrics['network_mean_age_formatted'] = _format_age(int(mean_age_days))
        health_metrics['network_median_age_formatted'] = _format_age(int(median_age_days))
    else:
        health_metrics['network_mean_age_formatted'] = "Unknown"
        health_metrics['network_median_age_formatted'] = "Unknown"
    
    # NEW: Top 3 countries by consensus weight (reuse existing sorted data)
    # Country keys are already UPPERCASE
    countries_by_cw = []
    if 'country' in sorted_data:
        for country_code, country_data in sorted_data['country'].items():
            if len(country_code) == 2:  # Valid country code
                cw_fraction = country_data.get('consensus_weight_fraction', 0)
                if cw_fraction > 0:
                    countries_by_cw.append((country_code, cw_fraction))
    
    countries_by_cw.sort(key=lambda x: x[1], reverse=True)
    health_metrics['top_3_countries'] = []
    for i, (country_code, cw_fraction) in enumerate(countries_by_cw[:3]):
        health_metrics['top_3_countries'].append({
            'rank': i + 1,
            'country_code': country_code,
            'consensus_weight_percentage': cw_fraction * 100
        })
    
    # NEW: Top AS by consensus weight and concentration metrics
    as_by_cw = []
    if 'as' in sorted_data:
        for as_number, as_data in sorted_data['as'].items():
            cw_fraction = as_data.get('consensus_weight_fraction', 0)
            if cw_fraction > 0:
                as_name = as_data.get('as_name', f'AS{as_number}')
                as_by_cw.append((as_number, as_name, cw_fraction))
    
    as_by_cw.sort(key=lambda x: x[2], reverse=True)
    
    # Top 3 AS details
    health_metrics['top_3_as'] = []
    for i, (as_number, as_name, cw_fraction) in enumerate(as_by_cw[:3]):
        health_metrics['top_3_as'].append({
            'rank': i + 1,
            'as_number': as_number,
            'as_name': as_name,
            'as_name_truncated': as_name[:8] if as_name and len(as_name) > 8 else (as_name or f'AS{as_number}'),
            'consensus_weight_percentage': cw_fraction * 100
        })
    
    # AS concentration metrics
    if as_by_cw:
        top_3_cw = sum(x[2] for x in as_by_cw[:3])
        top_5_cw = sum(x[2] for x in as_by_cw[:5])
        top_10_cw = sum(x[2] for x in as_by_cw[:10])
        
        health_metrics['top_3_as_concentration'] = top_3_cw * 100
        health_metrics['top_5_as_concentration'] = top_5_cw * 100
        health_metrics['top_10_as_concentration'] = top_10_cw * 100
    else:
        health_metrics['top_3_as_concentration'] = 0.0
        health_metrics['top_5_as_concentration'] = 0.0
        health_metrics['top_10_as_concentration'] = 0.0
    
    # NEW: Calculate geographic CW/BW ratios (mean and median)
    health_metrics.update({
        'eu_cw_bw_mean': int(_safe_mean(eu_cw_bw_values)),
        'eu_cw_bw_median': int(_safe_median(eu_cw_bw_values)),
        'non_eu_cw_bw_mean': int(_safe_mean(non_eu_cw_bw_values)),
        'non_eu_cw_bw_median': int(_safe_median(non_eu_cw_bw_values))
    })
    
    # OPTIMIZATION: Extract Top AS CW/BW values from collected data (eliminates extra loop)
    # Extract data for top ASes using the as_cw_bw_data collected in the main relay loop above
    top_3_as_cw_bw_values = []
    top_5_as_cw_bw_values = []
    top_10_as_cw_bw_values = []
    
    if as_by_cw:
        # Get AS numbers for top ASes
        top_3_as_numbers = {x[0] for x in as_by_cw[:3]}
        top_5_as_numbers = {x[0] for x in as_by_cw[:5]}
        top_10_as_numbers = {x[0] for x in as_by_cw[:10]}
        
        # Extract CW/BW ratios from collected data
        for as_number, cw_bw_ratios in as_cw_bw_data.items():
            if as_number in top_3_as_numbers:
                top_3_as_cw_bw_values.extend(cw_bw_ratios)
            if as_number in top_5_as_numbers:
                top_5_as_cw_bw_values.extend(cw_bw_ratios)
            if as_number in top_10_as_numbers:
                top_10_as_cw_bw_values.extend(cw_bw_ratios)
    
    health_metrics.update({
        'top_3_as_cw_bw_mean': int(_safe_mean(top_3_as_cw_bw_values)),
        'top_3_as_cw_bw_median': int(_safe_median(top_3_as_cw_bw_values)),
        'top_5_as_cw_bw_mean': int(_safe_mean(top_5_as_cw_bw_values)),
        'top_5_as_cw_bw_median': int(_safe_median(top_5_as_cw_bw_values)),
        'top_10_as_cw_bw_mean': int(_safe_mean(top_10_as_cw_bw_values)),
        'top_10_as_cw_bw_median': int(_safe_median(top_10_as_cw_bw_values))
    })
    
    # NEW: Exit policy metrics (FIXED: use exit_count for percentage calculations)
    exit_count = network_totals['exit_count']
    health_metrics.update({
        'guard_exit_count': guard_exit_count,
        'unrestricted_exits': port_unrestricted_exits,
        'restricted_exits': port_restricted_exits,
        'web_traffic_exits': web_traffic_exits,
        'ip_unrestricted_exits': ip_unrestricted_exits,
        'ip_restricted_exits': ip_restricted_exits,
        'unrestricted_and_no_ip_restrictions': no_port_restrictions_and_no_ip_restrictions,  # NEW: Combined metric
        # FIXED: Port restriction percentages use exit_count (applies to exit relays)
        'unrestricted_exits_percentage': _pct(port_unrestricted_exits, exit_count),
        'restricted_exits_percentage': _pct(port_restricted_exits, exit_count),
        'web_traffic_exits_percentage': _pct(web_traffic_exits, exit_count),
        'guard_exit_percentage': _pct(guard_exit_count, total_relays_count),
        # FIXED: IP restriction percentages use exit_count (applies only to exit relays)
        'ip_unrestricted_exits_percentage': _pct(ip_unrestricted_exits, exit_count),
        'ip_restricted_exits_percentage': _pct(ip_restricted_exits, exit_count),
        'unrestricted_and_no_ip_restrictions_percentage': _pct(no_port_restrictions_and_no_ip_restrictions, exit_count)
    })
    
    # STORE CALCULATED METRICS
    health_metrics.update({
        'authorities_count': authority_count,
        'bad_exits_count': bad_exit_count,
        # NEW: Additional flag counts
        'fast_count': fast_count,
        'stable_count': stable_count,
        'v2dir_count': v2dir_count,
        'hsdir_count': hsdir_count,
        'stabledesc_count': stabledesc_count,
        'sybil_count': sybil_count,
        'offline_relays': offline_relays,
        'overloaded_relays': overloaded_relays,
        # REMOVED: 'hibernating_relays': hibernating_relays,
        'new_relays_24h': new_relays_24h,
        'new_relays_30d': new_relays_30d,
        'new_relays_1y': new_relays_1y,
        'new_relays_6m': new_relays_6m,
        'unique_platforms_count': len(unique_platforms),
        'unique_contacts_count': len(unique_contacts),
        'relays_with_family': relays_with_family,
        'relays_without_family': relays_without_family,
        'relays_with_contact': relays_with_contact,
        'relays_without_contact': relays_without_contact,
        'eu_relays_count': eu_relays,
        'non_eu_relays_count': non_eu_relays,
        'rare_countries_relays': rare_countries_relays,
        'eu_relays_percentage': _pct(eu_relays, total_relays_count),
        'non_eu_relays_percentage': _pct(non_eu_relays, total_relays_count),
        'rare_countries_relays_percentage': _pct(rare_countries_relays, total_relays_count),
        # Geographic consensus weight metrics
        'eu_consensus_weight': eu_consensus_weight,
        'non_eu_consensus_weight': non_eu_consensus_weight,
        'rare_countries_consensus_weight': rare_countries_consensus_weight,
        'eu_consensus_weight_percentage': _pct(eu_consensus_weight, total_consensus_weight),
        'non_eu_consensus_weight_percentage': _pct(non_eu_consensus_weight, total_consensus_weight),
        'rare_countries_consensus_weight_percentage': _pct(rare_countries_consensus_weight, total_consensus_weight),
        # Geographic analysis metrics from intelligence engine
        'geographic_diversity_top3': relay_set.json.get('smart_context', {}).get('concentration_patterns', {}).get('template_optimized', {}).get('countries_top_3_percentage', '0.0'),
        'geographic_diversity_significant_count': relay_set.json.get('smart_context', {}).get('concentration_patterns', {}).get('template_optimized', {}).get('countries_significant_count', 0),
        'geographic_diversity_five_eyes': relay_set.json.get('smart_context', {}).get('concentration_patterns', {}).get('template_optimized', {}).get('countries_five_eyes_percentage', '0.0'),
        'jurisdiction_five_eyes': relay_set.json.get('smart_context', {}).get('geographic_clustering', {}).get('template_optimized', {}).get('five_eyes_influence', '0.0'),
        'jurisdiction_fourteen_eyes': relay_set.json.get('smart_context', {}).get('geographic_clustering', {}).get('template_optimized', {}).get('fourteen_eyes_influence', '0.0'),
        'regional_concentration_level': relay_set.json.get('smart_context', {}).get('geographic_clustering', {}).get('template_optimized', {}).get('concentration_hhi_interpretation', 'UNKNOWN'),
        'regional_hhi': relay_set.json.get('smart_context', {}).get('geographic_clustering', {}).get('template_optimized', {}).get('regional_hhi', '0.000'),
        'regional_top_3_breakdown': relay_set.json.get('smart_context', {}).get('geographic_clustering', {}).get('template_optimized', {}).get('top_3_regions', 'Insufficient data'),
        # Add percentages for other relay counts
        'authorities_percentage': _pct(authority_count, total_relays_count),
        'bad_exits_percentage': _pct(bad_exit_count, total_relays_count),
        # Additional flag percentages
        'fast_percentage': _pct(fast_count, total_relays_count),
        'stable_percentage': _pct(stable_count, total_relays_count),
        'v2dir_percentage': _pct(v2dir_count, total_relays_count),
        'hsdir_percentage': _pct(hsdir_count, total_relays_count),
        'stabledesc_percentage': _pct(stabledesc_count, total_relays_count),
        'sybil_percentage': _pct(sybil_count, total_relays_count),
        'offline_relays_percentage': _pct(offline_relays, total_relays_count),
        'overloaded_relays_percentage': _pct(overloaded_relays, total_relays_count),
        'new_relays_24h_percentage': _pct(new_relays_24h, total_relays_count),
        'new_relays_30d_percentage': _pct(new_relays_30d, total_relays_count),
        'new_relays_1y_percentage': _pct(new_relays_1y, total_relays_count),
        'new_relays_6m_percentage': _pct(new_relays_6m, total_relays_count)
    })
    
    # NEW: IPv6 support metrics - relay-level statistics
    health_metrics.update({
        'ipv4_only_relays': ipv4_only_relays,
        'both_ipv4_ipv6_relays': both_ipv4_ipv6_relays,
        'ipv4_only_relays_percentage': _pct(ipv4_only_relays, total_relays_count),
        'both_ipv4_ipv6_relays_percentage': _pct(both_ipv4_ipv6_relays, total_relays_count)
    })
    
    # NEW: IPv6 support metrics - bandwidth-level statistics
    health_metrics.update({
        'ipv4_only_bandwidth': ipv4_only_bandwidth,
        'both_ipv4_ipv6_bandwidth': both_ipv4_ipv6_bandwidth,
        'ipv4_only_bandwidth_percentage': _pct(ipv4_only_bandwidth, total_bandwidth),
        'both_ipv4_ipv6_bandwidth_percentage': _pct(both_ipv4_ipv6_bandwidth, total_bandwidth)
    })
    
    # NEW: IPv6 support metrics - operator-level statistics (counts only, percentages calculated later)
    # Note: These counts will be recalculated after AROI validation to only include validated operators
    # Temporarily store the full operator_ipv6_status dict for later filtering
    health_metrics['_temp_operator_ipv6_status'] = operator_ipv6_status
    
    # NEW: IPv6 support metrics - top country analysis
    # Find top country for each IPv6 category
    top_ipv4_only_country = max(ipv4_only_countries.items(), key=lambda x: x[1]) if ipv4_only_countries else ('N/A', 0)
    top_both_country = max(both_ipv4_ipv6_countries.items(), key=lambda x: x[1]) if both_ipv4_ipv6_countries else ('N/A', 0)
    
    health_metrics.update({
        'top_ipv4_only_country': top_ipv4_only_country[0],
        'top_ipv4_only_country_count': top_ipv4_only_country[1],
        'top_ipv4_only_country_percentage': _pct(top_ipv4_only_country[1], total_relays_count),
        'top_both_ipv4_ipv6_country': top_both_country[0],
        'top_both_ipv4_ipv6_country_count': top_both_country[1],
        'top_both_ipv4_ipv6_country_percentage': _pct(top_both_country[1], total_relays_count)
    })
    
    # NEW: IPv6 support metrics - top AS analysis
    # Find top AS for each IPv6 category
    top_ipv4_only_as = max(ipv4_only_as.items(), key=lambda x: x[1]) if ipv4_only_as else (None, 0)
    top_both_as = max(both_ipv4_ipv6_as.items(), key=lambda x: x[1]) if both_ipv4_ipv6_as else (None, 0)
    
    # Get AS names from sorted data
    as_names = {}
    if 'as' in sorted_data:
        for as_number, as_data in sorted_data['as'].items():
            as_names[as_number] = as_data.get('as_name', f'AS{as_number}')
    
    health_metrics.update({
        'top_ipv4_only_as_number': top_ipv4_only_as[0],
        'top_ipv4_only_as_name': as_names.get(top_ipv4_only_as[0], 'Unknown') if top_ipv4_only_as[0] else 'N/A',
        'top_ipv4_only_as_count': top_ipv4_only_as[1],
        'top_ipv4_only_as_percentage': _pct(top_ipv4_only_as[1], total_relays_count),
        'top_both_ipv4_ipv6_as_number': top_both_as[0],
        'top_both_ipv4_ipv6_as_name': as_names.get(top_both_as[0], 'Unknown') if top_both_as[0] else 'N/A',
        'top_both_ipv4_ipv6_as_count': top_both_as[1],
        'top_both_ipv4_ipv6_as_percentage': _pct(top_both_as[1], total_relays_count)
    })
    
    # Platform metrics with percentages
    total_relays = health_metrics['relays_total']
    sorted_platforms = sorted(platform_counts.items(), key=lambda x: x[1], reverse=True)
    top_platforms = sorted_platforms[:3]
    others_count = sum(count for _, count in sorted_platforms[3:])
    
    top_platforms_with_pct = []
    for platform, count in top_platforms:
        percentage = _pct(count, total_relays)
        top_platforms_with_pct.append((platform, count, percentage))
    
    health_metrics['platform_top3'] = top_platforms_with_pct
    health_metrics['platform_others'] = others_count
    health_metrics['platform_others_percentage'] = _pct(others_count, total_relays)
    
    # Version compliance with percentages
    total_with_version_info = recommended_version_count + not_recommended_count
    health_metrics.update({
        'recommended_version_percentage': _pct(recommended_version_count, total_with_version_info),
        'recommended_version_count': recommended_version_count,
        'not_recommended_count': not_recommended_count,
        'experimental_count': experimental_count,
        'obsolete_count': obsolete_count,
        'outdated_count': outdated_count,
        'not_recommended_percentage': _pct(not_recommended_count, total_relays),
        'experimental_percentage': _pct(experimental_count, total_relays),
        'obsolete_percentage': _pct(obsolete_count, total_relays),
        'outdated_percentage': _pct(outdated_count, total_relays)
    })
    
    # Bandwidth utilization metrics - calculate mean and median for Obs to Adv Diff
    avg_obs_adv_diff_bytes = (
        (observed_advertised_diff_sum / observed_advertised_count) 
        if observed_advertised_count > 0 else 0
    )
    median_obs_adv_diff_bytes = (
        statistics.median(observed_advertised_diff_values)
        if observed_advertised_diff_values else 0
    )
    
    # BandwidthFormatter already handles bytes→bits conversion internally via its
    # divisors (e.g. Gbit/s divisor = 10^9/8), so we pass raw bytes values directly.
    # This matches how relays.py _preprocess_template_data() formats relay-level bandwidth.
    bw_fmt = relay_set.bandwidth_formatter
    
    obs_adv_unit = bw_fmt.determine_unit(avg_obs_adv_diff_bytes)
    avg_formatted = bw_fmt.format_bandwidth_with_unit(avg_obs_adv_diff_bytes, obs_adv_unit, decimal_places=0) + f" {obs_adv_unit}"
    median_formatted = bw_fmt.format_bandwidth_with_unit(median_obs_adv_diff_bytes, obs_adv_unit, decimal_places=0) + f" {obs_adv_unit}"
    health_metrics['avg_observed_advertised_diff_formatted'] = f"{avg_formatted} | {median_formatted}"
    
    health_metrics['consensus_weight_bandwidth_ratio'] = (
        (total_consensus_weight / total_bandwidth) 
        if total_bandwidth > 0 else 0.0
    )
    
    # Role-specific CW/BW ratios and bandwidth statistics
    health_metrics.update({
        'exit_cw_bw_overall': (exit_cw_sum / exit_bw_sum) if exit_bw_sum > 0 else 0.0,
        'guard_cw_bw_overall': (guard_cw_sum / guard_bw_sum) if guard_bw_sum > 0 else 0.0,
        'middle_cw_bw_overall': (middle_cw_sum / middle_bw_sum) if middle_bw_sum > 0 else 0.0,
        'exit_cw_bw_avg': _safe_mean(exit_cw_values),
        'guard_cw_bw_avg': _safe_mean(guard_cw_values),
        'middle_cw_bw_avg': _safe_mean(middle_cw_values),
        'exit_cw_bw_median': _safe_median(exit_cw_values),
        'guard_cw_bw_median': _safe_median(guard_cw_values),
        'middle_cw_bw_median': _safe_median(middle_cw_values),
        'exit_bw_mean': _safe_mean(exit_bw_values),
        'guard_bw_mean': _safe_mean(guard_bw_values),
        'middle_bw_mean': _safe_mean(middle_bw_values),
        'exit_bw_median': _safe_median(exit_bw_values),
        'guard_bw_median': _safe_median(guard_bw_values),
        'middle_bw_median': _safe_median(middle_bw_values),
        # Flag-specific bandwidth statistics
        'fast_bw_mean': _safe_mean(fast_bandwidth_values),
        'fast_bw_median': _safe_median(fast_bandwidth_values),
        'stable_bw_mean': _safe_mean(stable_bandwidth_values),
        'stable_bw_median': _safe_median(stable_bandwidth_values),
        'authority_bw_mean': _safe_mean(authority_bandwidth_values),
        'authority_bw_median': _safe_median(authority_bandwidth_values),
        'v2dir_bw_mean': _safe_mean(v2dir_bandwidth_values),
        'v2dir_bw_median': _safe_median(v2dir_bandwidth_values),
        'hsdir_bw_mean': _safe_mean(hsdir_bandwidth_values),
        'hsdir_bw_median': _safe_median(hsdir_bandwidth_values)
    })
    
    # PRE-CALCULATE BANDWIDTH MEAN/MEDIAN WITH PROPER UNITS - avoid showing 0 values
    # BandwidthFormatter expects bytes input and handles bits conversion internally
    def _fmt_bw(value, unit):
        """Helper: format bandwidth value (in bytes/s) with unit suffix."""
        return bw_fmt.format_bandwidth_with_unit(value, unit, decimal_places=0) + f" {unit}"
    
    # Determine appropriate unit for role-specific mean/median values
    base_unit = bw_fmt.determine_unit(total_bandwidth)
    test_values = [health_metrics[k] for k in 
                   ('exit_bw_mean', 'exit_bw_median', 'guard_bw_mean',
                    'guard_bw_median', 'middle_bw_mean', 'middle_bw_median')]
    
    # Check if any would format to 0 with the base unit; if so, use smaller unit
    use_smaller_unit = any(
        v > 0 and float(bw_fmt.format_bandwidth_with_unit(v, base_unit, decimal_places=0)) == 0
        for v in test_values
    )
    smaller_unit = 'Mbit/s' if relay_set.use_bits else 'MB/s'
    larger_unit = 'Gbit/s' if relay_set.use_bits else 'GB/s'
    unit = smaller_unit if (use_smaller_unit and base_unit == larger_unit) else base_unit
    
    # Format all role/flag-specific bandwidth mean/median in a single pass
    for role in ('exit', 'guard', 'middle', 'fast', 'stable', 'authority', 'v2dir', 'hsdir'):
        health_metrics[f'{role}_bw_mean_formatted'] = _fmt_bw(health_metrics[f'{role}_bw_mean'], unit)
        health_metrics[f'{role}_bw_median_formatted'] = _fmt_bw(health_metrics[f'{role}_bw_median'], unit)
    
    # Bandwidth formatting with proper units for totals
    total_unit = bw_fmt.determine_unit(total_bandwidth)
    for key, value in [('total_bandwidth', total_bandwidth), ('guard_bandwidth', guard_bandwidth),
                       ('exit_bandwidth', exit_bandwidth), ('middle_bandwidth', middle_bandwidth),
                       ('ipv4_only_bandwidth', ipv4_only_bandwidth), ('both_ipv4_ipv6_bandwidth', both_ipv4_ipv6_bandwidth)]:
        health_metrics[f'{key}_formatted'] = _fmt_bw(value, total_unit)
    
    # Happy Family: bandwidth formatting
    health_metrics['hf_ready_bandwidth_formatted'] = _fmt_bw(family_key_ready_bandwidth, total_unit)
    
    # Uptime metrics - reuse existing consolidated uptime calculations for efficiency
    if hasattr(relay_set, '_consolidated_uptime_results') and relay_set._consolidated_uptime_results:
        network_statistics = relay_set._consolidated_uptime_results.get('network_statistics', {})
        network_flag_statistics = relay_set._consolidated_uptime_results.get('network_flag_statistics', {})
        network_middle_statistics = relay_set._consolidated_uptime_results.get('network_middle_statistics', {})
        network_other_statistics = relay_set._consolidated_uptime_results.get('network_other_statistics', {})
        
        # Use 1-month network mean for overall uptime as requested
        if network_statistics.get('1_month', {}).get('mean') is not None:
            health_metrics['overall_uptime'] = network_statistics['1_month']['mean']
        elif hasattr(relay_set, 'network_uptime_percentiles') and relay_set.network_uptime_percentiles:
            health_metrics['overall_uptime'] = relay_set.network_uptime_percentiles['average']
        else:
            health_metrics['overall_uptime'] = 0.0
            
        # Store uptime percentiles if available
        if hasattr(relay_set, 'network_uptime_percentiles') and relay_set.network_uptime_percentiles:
            health_metrics['uptime_percentiles'] = relay_set.network_uptime_percentiles['percentiles']
        else:
            health_metrics['uptime_percentiles'] = None
        
        # Reuse all existing role-specific calculations from consolidated uptime processing
        # This follows DRY/DIY principle by using already computed statistics
        # Exit and Guard statistics come from flag-specific network statistics
        # Middle statistics come from consolidated middle relay calculations
        # Other statistics come from consolidated other relay calculations
        
        for period in ['1_month', '6_months', '1_year', '5_years']:
            # Exit relay statistics - reuse existing calculation
            if network_flag_statistics.get('Exit', {}).get(period, {}).get('mean') is not None:
                exit_mean = network_flag_statistics['Exit'][period]['mean']
                exit_median = network_flag_statistics['Exit'][period].get('median', exit_mean)
            else:
                exit_mean = 0.0
                exit_median = 0.0
        
            # Guard relay statistics - reuse existing calculation  
            if network_flag_statistics.get('Guard', {}).get(period, {}).get('mean') is not None:
                guard_mean = network_flag_statistics['Guard'][period]['mean']
                guard_median = network_flag_statistics['Guard'][period].get('median', guard_mean)
            else:
                guard_mean = 0.0
                guard_median = 0.0
            
            # Middle relay statistics - reuse existing consolidated calculation
            if network_middle_statistics.get(period, {}).get('mean') is not None:
                middle_mean = network_middle_statistics[period]['mean']
                middle_median = network_middle_statistics[period].get('median', middle_mean)
            else:
                middle_mean = 0.0
                middle_median = 0.0
            
            # Other relay statistics - reuse existing consolidated calculation
            if network_other_statistics.get(period, {}).get('mean') is not None:
                other_mean = network_other_statistics[period]['mean']
                other_median = network_other_statistics[period].get('median', other_mean)
            else:
                other_mean = 0.0
                other_median = 0.0
            
            # NEW: Additional flag-specific uptime calculations
            # Authority uptime statistics
            if network_flag_statistics.get('Authority', {}).get(period, {}).get('mean') is not None:
                authority_mean = network_flag_statistics['Authority'][period]['mean']
                authority_median = network_flag_statistics['Authority'][period].get('median', authority_mean)
            else:
                authority_mean = 0.0
                authority_median = 0.0
            
            # V2Dir uptime statistics
            if network_flag_statistics.get('V2Dir', {}).get(period, {}).get('mean') is not None:
                v2dir_mean = network_flag_statistics['V2Dir'][period]['mean']
                v2dir_median = network_flag_statistics['V2Dir'][period].get('median', v2dir_mean)
            else:
                v2dir_mean = 0.0
                v2dir_median = 0.0
            
            # HSDir uptime statistics
            if network_flag_statistics.get('HSDir', {}).get(period, {}).get('mean') is not None:
                hsdir_mean = network_flag_statistics['HSDir'][period]['mean']
                hsdir_median = network_flag_statistics['HSDir'][period].get('median', hsdir_mean)
            else:
                hsdir_mean = 0.0
                hsdir_median = 0.0
            
            # REFACTORED: Consistent naming pattern for all periods - {role}_uptime_{period}_{statistic}
            # Eliminates redundant variables and special cases for better maintainability
            role_data = [
                ('exit', exit_mean, exit_median),
                ('guard', guard_mean, guard_median),
                ('middle', middle_mean, middle_median),
                ('other', other_mean, other_median),
                ('authority', authority_mean, authority_median),
                ('v2dir', v2dir_mean, v2dir_median),
                ('hsdir', hsdir_mean, hsdir_median)
            ]
            
            for role, mean_val, median_val in role_data:
                health_metrics[f'{role}_uptime_{period}_mean'] = mean_val
                health_metrics[f'{role}_uptime_{period}_median'] = median_val
        
    else:
        # Initialize to 0 when no consolidated uptime results available
        health_metrics['overall_uptime'] = 0.0
        health_metrics['uptime_percentiles'] = None
        
        # REFACTORED: Consistent fallback initialization using unified pattern
        uptime_periods = ['1_month', '6_months', '1_year', '5_years']
        roles = ['exit', 'guard', 'middle', 'other', 'authority', 'v2dir', 'hsdir']
        statistics = ['mean', 'median']
        
        # Generate all uptime keys using consistent pattern: {role}_uptime_{period}_{statistic}
        uptime_keys = [f'{role}_uptime_{period}_{stat}' for role in roles for period in uptime_periods for stat in statistics]
        
        for key in uptime_keys:
            health_metrics[key] = 0.0
    
    # Percentage calculations for participation metrics
    health_metrics.update({
        'relays_with_family_percentage': _pct(relays_with_family, total_relays),
        'relays_without_family_percentage': _pct(relays_without_family, total_relays),
        'relays_with_contact_percentage': _pct(relays_with_contact, total_relays),
        'relays_without_contact_percentage': _pct(relays_without_contact, total_relays)
    })
    
    # Final calculations - reuse existing data
    countries_count = health_metrics['countries_count']
    as_count = health_metrics['unique_as_count']
    
    health_metrics.update({
        'avg_as_per_country': round(as_count / countries_count, 1) if countries_count > 0 else 0.0,
        'avg_aroi_per_as': round(health_metrics['aroi_operators_count'] / as_count, 1) if as_count > 0 else 0.0,
        'avg_families_per_as': round(health_metrics['families_count'] / as_count, 1) if as_count > 0 else 0.0
    })
    
    # Add CW/BW ratio metrics from intelligence engine (same as contact performance insights)
    if hasattr(relay_set, 'json') and 'smart_context' in relay_set.json:
        # Extract contact intelligence data which contains network-wide CW/BW ratios
        contact_intelligence = relay_set.json['smart_context'].get('contact_intelligence', {}).get('template_optimized', {})
        
        # Find any contact's data to get the network-wide ratios (all contacts have same network values)
        network_ratios = {}
        for contact_hash, contact_data in contact_intelligence.items():
            if isinstance(contact_data, dict):
                # Extract network-wide performance ratios
                if 'performance_network_overall_ratio' in contact_data:
                    network_ratios['overall_ratio_mean'] = contact_data['performance_network_overall_ratio']
                if 'performance_network_overall_median' in contact_data:
                    network_ratios['overall_ratio_median'] = contact_data['performance_network_overall_median']
                if 'performance_network_guard_ratio' in contact_data:
                    network_ratios['guard_ratio_mean'] = contact_data['performance_network_guard_ratio']
                if 'performance_network_guard_median' in contact_data:
                    network_ratios['guard_ratio_median'] = contact_data['performance_network_guard_median']
                if 'performance_network_exit_ratio' in contact_data:
                    network_ratios['exit_ratio_mean'] = contact_data['performance_network_exit_ratio']
                if 'performance_network_exit_median' in contact_data:
                    network_ratios['exit_ratio_median'] = contact_data['performance_network_exit_median']
                break  # Only need one contact since all have same network values
        
        # Add to health metrics with defaults if not found
        health_metrics.update({
            'cw_bw_ratio_overall_mean': network_ratios.get('overall_ratio_mean', '0'),
            'cw_bw_ratio_overall_median': network_ratios.get('overall_ratio_median', '0'),
            'cw_bw_ratio_guard_mean': network_ratios.get('guard_ratio_mean', '0'),
            'cw_bw_ratio_guard_median': network_ratios.get('guard_ratio_median', '0'),
            'cw_bw_ratio_exit_mean': network_ratios.get('exit_ratio_mean', '0'),
            'cw_bw_ratio_exit_median': network_ratios.get('exit_ratio_median', '0')
        })
    else:
        # Fallback when smart_context not available
        health_metrics.update({
            'cw_bw_ratio_overall_mean': '0',
            'cw_bw_ratio_overall_median': '0',
            'cw_bw_ratio_guard_mean': '0',
            'cw_bw_ratio_guard_median': '0',
            'cw_bw_ratio_exit_mean': '0',
            'cw_bw_ratio_exit_median': '0'
    })
    
    # === AROI VALIDATION METRICS ===
    _integrate_aroi_validation(health_metrics, relay_set, total_relays_count)
    
    # === HAPPY FAMILY KEY MIGRATION METRICS ===
    # DA readiness (small loop over ~10 authority relays)
    family_key_ready_authorities = sum(
        1 for r in relay_set.json['relays']
        if 'Authority' in r.get('flags', []) and _is_happy_family_ready(r.get('version', ''))
    )
    
    # Consensus method + family params from collector consensus data
    collector_data_hf = getattr(relay_set, 'collector_consensus_data', None)
    cm_info = {}
    if collector_data_hf and isinstance(collector_data_hf, dict):
        cm_info = collector_data_hf.get('consensus_method_info', {})
    
    # Family-cert from collector descriptors (separate worker, separate cache)
    # Fetches last 18 hourly files for full network coverage (~10k relays).
    # Per-file results cached so subsequent runs only download new files.
    collector_descs = getattr(relay_set, 'collector_descriptors_data', None)
    family_cert_count = 0
    family_no_cert_count = 0
    desc_seen_total = 0
    family_cert_fps = set()
    all_seen_fps = set()
    if collector_descs and isinstance(collector_descs, dict):
        family_cert_fps = set(collector_descs.get('family_cert_fingerprints', []))
        all_seen_fps = set(collector_descs.get('all_seen_fingerprints', []))
        desc_seen_total = len(all_seen_fps)
        # Count relays in our Onionoo dataset: with family-cert vs without (from descriptors only)
        for relay in relay_set.json['relays']:
            fp = relay.get('fingerprint', '').upper()
            if fp in family_cert_fps:
                family_cert_count += 1
            elif fp in all_seen_fps:
                family_no_cert_count += 1
    
    # Operator readiness from SERVER DESCRIPTORS (not version-based)
    # Uses family_cert_fps and all_seen_fps from descriptor data
    validated_domain_set_hf = getattr(relay_set, 'validated_aroi_domains', set())
    # Build per-operator descriptor counts: {domain: {'cert': N, 'seen': N}}
    operator_desc_counts = {}
    for relay in relay_set.json['relays']:
        aroi_dom = relay.get('aroi_domain', 'none')
        if not aroi_dom or aroi_dom == 'none':
            continue
        fp = relay.get('fingerprint', '').upper()
        if fp not in all_seen_fps:
            continue  # Not yet seen in descriptors, skip
        if aroi_dom not in operator_desc_counts:
            operator_desc_counts[aroi_dom] = {'cert': 0, 'seen': 0}
        operator_desc_counts[aroi_dom]['seen'] += 1
        if fp in family_cert_fps:
            operator_desc_counts[aroi_dom]['cert'] += 1
    
    # Count validated operators with ≥1 family-cert relay vs all relays having family-cert
    family_cert_some_operators = 0
    family_cert_all_operators = 0
    for domain, counts in operator_desc_counts.items():
        if domain in validated_domain_set_hf and counts['seen'] > 0:
            if counts['cert'] > 0:
                family_cert_some_operators += 1
            if counts['cert'] == counts['seen']:
                family_cert_all_operators += 1
    total_validated_operators = len(validated_domain_set_hf) if validated_domain_set_hf else 0
    
    # Consensus params: extract family-related params from votes (None = not voted on yet)
    family_params_votes = cm_info.get('family_params_votes', {})
    use_family_ids_votes = family_params_votes.get('use-family-ids', {})
    use_family_lists_votes = family_params_votes.get('use-family-lists', {})
    hf_use_family_ids = None
    hf_use_family_lists = None
    if use_family_ids_votes:
        vals = sorted(use_family_ids_votes.values())
        hf_use_family_ids = vals[len(vals) // 2]  # median per dir-spec
    if use_family_lists_votes:
        vals = sorted(use_family_lists_votes.values())
        hf_use_family_lists = vals[len(vals) // 2]
    
    # Voting authority count — dynamic from collector data, not hardcoded
    hf_total_voters = cm_info.get('total_voters', 0)
    
    # Consensus method voting threshold — replicates the formula from Tor's C source:
    # https://gitlab.torproject.org/tpo/core/tor/-/blob/main/src/feature/dirauth/dirvote.c
    #   int min = (smartlist_len(votes) * 2) / 3;
    #   get_frequent_members(acceptable_methods, all_methods, min);  // count > min
    # A method is accepted when strictly more than (n*2)/3 authorities support it.
    # With 9 voters: (9*2)/3 = 6, need >6, so threshold is 7.
    hf_method_threshold = (hf_total_voters * 2) // 3 + 1 if hf_total_voters > 0 else 0
    
    health_metrics.update({
        # Consensus method (from actual consensus document, never self-computed)
        'hf_consensus_method': cm_info.get('current_method'),
        # Max method available from any DA (from vote data)
        'hf_consensus_method_max': cm_info.get('max_method'),
        # How many DAs support the max method
        'hf_max_method_support': cm_info.get('max_method_support', 0),
        # Total voting authorities (dynamic from votes, not hardcoded)
        'hf_consensus_total_voters': hf_total_voters,
        # 2/3 supermajority threshold (dynamic from voter count, per Tor dirvote.c formula)
        'hf_method_threshold': hf_method_threshold,
        # DA readiness (v0.4.9.x+ from Onionoo version field)
        'hf_ready_authorities': family_key_ready_authorities,
        # Relay adoption (from Onionoo version)
        'hf_ready_relays': family_key_ready_relays,
        'hf_ready_relays_percentage': _pct(family_key_ready_relays, total_relays_count),
        'hf_not_ready_relays': total_relays_count - family_key_ready_relays,
        'hf_not_ready_relays_percentage': _pct(total_relays_count - family_key_ready_relays, total_relays_count),
        'hf_ready_exit_relays': family_key_ready_exit_relays,
        'hf_ready_guard_relays': family_key_ready_guard_relays,
        # Family-cert adoption from server descriptors (18-hour window, full coverage)
        'hf_family_cert_count': family_cert_count,
        'hf_family_no_cert_count': family_no_cert_count,
        'hf_family_cert_seen_total': desc_seen_total,
        # Coverage window from descriptor worker (dynamic, not hardcoded)
        'hf_descriptor_coverage_hours': collector_descs.get('coverage_hours', 20) if collector_descs else 0,
        # Bandwidth + CW
        'hf_ready_bandwidth': family_key_ready_bandwidth,
        'hf_ready_bandwidth_percentage': _pct(family_key_ready_bandwidth, total_bandwidth),
        'hf_ready_cw_percentage': _pct(family_key_ready_cw, total_consensus_weight),
        # Operator adoption from server descriptors (family-cert based, not version based)
        'hf_some_operators': family_cert_some_operators,
        'hf_all_operators': family_cert_all_operators,
        'hf_some_operators_percentage': _pct(family_cert_some_operators, total_validated_operators) if total_validated_operators > 0 else 0.0,
        'hf_all_operators_percentage': _pct(family_cert_all_operators, total_validated_operators) if total_validated_operators > 0 else 0.0,
        'hf_total_validated_operators': total_validated_operators,
        # Consensus params (None = not voted on yet, auto-populates when they appear)
        'hf_use_family_ids': hf_use_family_ids,
        'hf_use_family_lists': hf_use_family_lists,
    })
    
    # OPTIMIZATION: Pre-format all template strings to eliminate Jinja2 formatting overhead
    # Template formatting in Jinja2 is 3-5x slower than Python formatting
    preformat_network_health_template_strings(health_metrics)
    
    # Store the complete health metrics
    relay_set.json['network_health'] = health_metrics

