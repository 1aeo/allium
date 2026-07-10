"""
File: aroileaders.py

AROI (Authenticated Relay Operator Identifier) Leaderboard calculations
Processes operator rankings based on Onionoo API data grouped by contact information
Reuses existing contact calculations and only computes new metrics not already available
"""

# Import centralized IP parsing from ip_utils (canonical home)
from .ip_utils import safe_parse_ip_address as _safe_parse_ip_address
# B4.1: shared classifier so leaderboard tier matches contact-page pill tier.
from .aroi_validation import classify_v3_tier as _classify_v3_tier_local

# Import centralized country utilities
from .country_utils import (
    count_non_eu_countries, 
    calculate_diversity_score, 
    calculate_geographic_achievement,
    calculate_operator_as_diversity_score,
    EU_POLITICAL_REGION
)

# Import HTML escaping utility
from .html_escape_utils import safe_html_escape
from .string_utils import extract_contact_display_name, URL_FIELD_TOKEN_RE


# Shared url-token regex (string_utils is the single source of truth) for the
# Option A incomplete-AROI fallback. Matches the CIISS `url:` field token in a
# raw contact string. We intentionally accept any plausible domain (we are not
# validating CIISS conformance here — the caller already confirmed AROI parsing
# FAILED, we just want a recognisable display name).
_URL_FIELD_FALLBACK_RE = URL_FIELD_TOKEN_RE

# Maximum length of a derived display name returned by
# extract_contact_display_name() that we accept for the incomplete-AROI
# leaderboard row. Values longer than this are rejected so the row falls
# through to the truncation cascade (cascade 3) and the leaderboard cell
# stays compact / readable.
MAX_DERIVED_LENGTH = 60


def _incomplete_aroi_display_name(contact_info, contact_hash) -> str:
    """Build a friendly display name for an operator whose AROI parsing
    failed but whose ContactInfo still contains a recognisable identifier.

    Cascade:
      1. If contact contains `url:<domain>`, return
         "<domain> (incomplete AROI)" so the row is attributable to the
         operator's domain even when the relay forgot to declare
         ciissversion. Domain is normalised (drops https:// prefix and
         trailing path/query if present).
      2. Else fall back to extract_contact_display_name() (email/name/url
         derivation used by the contact-listing tooltip code).
      3. Else truncated raw contact string (legacy behaviour).
      4. Else contact_hash prefix (last-resort fallback).
    """
    if contact_info and contact_info.strip():
        clean_contact = contact_info.strip()
        url_match = _URL_FIELD_FALLBACK_RE.search(clean_contact)
        if url_match:
            domain = url_match.group(1)
            # Normalise: drop scheme if present, then trailing path/query.
            if '://' in domain:
                domain = domain.split('://', 1)[1]
            domain = domain.split('/', 1)[0].split('?', 1)[0]
            # Canonicalise to lowercase before the www-prefix check so
            # values like "WWW.Example.com" are normalised correctly.
            domain = domain.lower()
            if domain.startswith('www.'):
                domain = domain[4:]
            domain = domain.rstrip('.,;:')
            if domain:
                return f"{domain} (incomplete AROI)"

        # Cascade 2: email/name/url-derivation helper.
        derived = extract_contact_display_name(clean_contact, None)
        if derived and derived != 'none' and len(derived) <= MAX_DERIVED_LENGTH:
            return derived

        # Cascade 3: truncated raw contact (preserved legacy behaviour).
        if len(clean_contact) > 30:
            return clean_contact[:30] + '...'
        return clean_contact

    # Cascade 4: contact-hash prefix.
    return f"contact_{contact_hash[:8]}"


def _top_n(operators, metric, n=50, filter_fn=None, tiebreakers=None):
    """
    Return the top-n operators sorted by a metric key, optionally pre-filtered.
    
    Replaces 18 repeated sorted(..., key=lambda x: x[1][metric], reverse=True)[:n] blocks.
    
    Args:
        operators (dict): Operator key → metrics dict
        metric (str): Key in the metrics dict to sort by
        n (int): Number of top entries to return (default 50)
        filter_fn (callable, optional): If provided, only include operators where filter_fn(v) is True
        tiebreakers (list, optional): Ordered list of secondary metric keys used to
            break ties on the primary metric. All keys sort descending (higher is
            better), matching the primary metric's direction.
    
    Returns:
        list: Top-n (operator_key, metrics) tuples sorted by metric descending
    """
    source = operators if filter_fn is None else {k: v for k, v in operators.items() if filter_fn(v)}
    # Explicit tiebreakers (if any) break ties on the primary metric; remaining
    # ties break by relay count (bigger operator wins), then operator key purely
    # to pin byte-stable output across runs (dict insertion order previously
    # decided ties nondeterministically).
    extra_keys = list(tiebreakers or [])
    return sorted(source.items(),
                  key=lambda x: (-x[1][metric],
                                 *(-x[1].get(k, 0) for k in extra_keys),
                                 -x[1].get('total_relays', 0), x[0]))[:n]


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


def _make_score_result(score, average_value, relay_count, valid_relays, breakdown, metric_type):
    """
    DRY helper: Create standardized score result dictionary.
    
    Args:
        score (float): The calculated score value
        average_value (float): The average metric value
        relay_count (int): Total number of relays for this operator
        valid_relays (int): Number of relays with valid data
        breakdown (dict): Per-relay breakdown data
        metric_type (str): 'uptime' or 'bandwidth' (determines average_X key name)
        
    Returns:
        dict: Standardized score result with consistent structure
    """
    avg_key = 'average_uptime' if metric_type == 'uptime' else 'average_bandwidth'
    return {
        'score': score,
        avg_key: average_value,
        'relay_count': relay_count,
        'weight': 1.0,  # Always 1.0 since no weighting is applied
        'valid_relays': valid_relays,
        'breakdown': breakdown
    }


def _make_empty_score_result(relay_count, metric_type):
    """
    DRY helper: Create empty score result when no valid data is available.
    
    Args:
        relay_count (int): Total number of relays for this operator
        metric_type (str): 'uptime' or 'bandwidth' (determines average_X key name)
        
    Returns:
        dict: Empty score result with zero values
    """
    return _make_score_result(0.0, 0.0, relay_count, 0, {}, metric_type)


def _convert_relay_breakdown(period_result, value_key='uptime'):
    """
    DRY helper: Convert relay_breakdown from fingerprint-keyed to nickname-keyed format.
    
    Args:
        period_result (dict): Result from extract_relay_X_for_period function
        value_key (str): Key name for the metric value ('uptime' or 'bandwidth')
        
    Returns:
        dict: Breakdown keyed by nickname instead of fingerprint
    """
    breakdown = {}
    for fingerprint, relay_data in period_result.get('relay_breakdown', {}).items():
        breakdown[relay_data.get('nickname', 'Unknown')] = {
            'fingerprint': fingerprint,
            value_key: relay_data.get(value_key, 0),
            'data_points': relay_data.get('data_points', 0)
        }
    return breakdown


def _calculate_generic_score(operator_relays, data, time_period, metric_type, prebuilt_map=None):
    """
    Generic function to calculate scores for different metrics (reliability, bandwidth).
    
    OPTIMIZATION: For uptime, prefers already-computed per-relay `uptime_percentages`
    that are attached by _reprocess_uptime_data(). This avoids re-scanning the raw
    uptime API payload for each operator (major performance gain).
    
    For bandwidth, uses pre-built bandwidth_map when available to avoid rebuilding
    the fingerprint->data mapping for each operator.
    
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
        return _make_empty_score_result(0, metric_type)
    
    relay_count = len(operator_relays)
    
    if metric_type == 'uptime':
        # PERFORMANCE: Prefer already-computed per-relay uptime_percentages when available.
        # These are populated by relays._reprocess_uptime_data() and avoid re-scanning
        # the raw uptime API payload (which is very expensive at leaderboard scale).
        first = operator_relays[0] if operator_relays else None
        if first and isinstance(first, dict) and first.get('uptime_percentages'):
            uptime_values = []
            breakdown = {}
            
            for relay in operator_relays:
                percentages = relay.get('uptime_percentages') or {}
                uptime_pct = percentages.get(time_period, 0.0) or 0.0
                data_points = (relay.get('_uptime_datapoints') or {}).get(time_period, 0)
                # Include relays that HAVE uptime data for the period, even at
                # 0% uptime (excluding them inflated operator averages); skip
                # only relays with insufficient data (<30 daily points, the
                # same validity threshold the percentage computation uses).
                if data_points >= 30:
                    uptime_values.append(uptime_pct)
                    breakdown[relay.get('nickname', 'Unknown')] = {
                        'fingerprint': relay.get('fingerprint', ''),
                        'uptime': uptime_pct,
                        'data_points': data_points
                    }
            
            if not uptime_values:
                return _make_empty_score_result(relay_count, 'uptime')
            
            average_value = sum(uptime_values) / len(uptime_values)
            return _make_score_result(average_value, average_value, relay_count, len(uptime_values), breakdown, 'uptime')
        
        # Fallback: If uptime_percentages not available, use raw API data with pre-built map
        if not data and not prebuilt_map:
            return _make_empty_score_result(relay_count, 'uptime')
        
        from .uptime_utils import extract_relay_uptime_for_period
        period_result = extract_relay_uptime_for_period(operator_relays, data, time_period, uptime_map=prebuilt_map)
        
        if not period_result['uptime_values']:
            return _make_empty_score_result(relay_count, 'uptime')
        
        average_value = sum(period_result['uptime_values']) / len(period_result['uptime_values'])
        breakdown = _convert_relay_breakdown(period_result, 'uptime')
        return _make_score_result(average_value, average_value, relay_count, len(period_result['uptime_values']), breakdown, 'uptime')
    
    elif metric_type == 'bandwidth':
        from .bandwidth_utils import extract_operator_daily_bandwidth_totals, extract_relay_bandwidth_for_period
        
        # Calculate daily total bandwidth (sum across all relays per day, then average)
        daily_totals_result = extract_operator_daily_bandwidth_totals(operator_relays, data, time_period, bandwidth_map=prebuilt_map)
        
        if not daily_totals_result['daily_totals']:
            return _make_empty_score_result(relay_count, 'bandwidth')
        
        average_value = daily_totals_result['average_daily_total']
        
        # Get relay breakdown for display purposes
        period_result = extract_relay_bandwidth_for_period(operator_relays, data, time_period, bandwidth_map=prebuilt_map)
        breakdown = _convert_relay_breakdown(period_result, 'bandwidth')
        
        return _make_score_result(average_value, average_value, relay_count, len(period_result['bandwidth_values']), breakdown, 'bandwidth')
    
    # Default return for unsupported metric types
    return _make_empty_score_result(relay_count, metric_type)


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
    
    details = [formatter_func(count, country) for country, count in breakdown_items]
    tooltip_text = ", ".join(details)

    # Create short version with truncation
    short_text = tooltip_text
    if len(short_text) > max_chars:
        # Find the last complete entry that fits
        chars_used = 0
        for i, detail in enumerate(details):
            if i > 0:
                chars_used += 2  # for ", "
            if chars_used + len(detail) <= max_chars - 3:  # leave 3 chars for "..."
                chars_used += len(detail)
            else:
                details = details[:i]
                break
        details_text = ", ".join(details) + "..."
    else:
        details_text = short_text
    
    return details_text, tooltip_text

def _calculate_aroi_leaderboards(relays_instance):
    """
    Calculate AROI operator leaderboards using current live relay data.
    
    Composed from 3 sub-functions for readability and extensibility:
    1. _collect_operator_metrics: Gather per-operator data from contacts
    2. _rank_operators: Sort operators into leaderboard categories
    3. _format_leaderboard_entries: Format entries for template rendering
    
    To add a new leaderboard category:
    - Add metric collection in _collect_operator_metrics (if new data needed)
    - Add one sorted() call in _rank_operators
    - Add formatting in _format_leaderboard_entries
    """
    if not relays_instance.json or 'sorted' not in relays_instance.json:
        return {}
    
    contacts = relays_instance.json.get('sorted', {}).get('contact', {})
    all_relays = relays_instance.json.get('relays', [])
    
    if not contacts or not all_relays:
        return {}
    
    # Step 1: Collect per-operator metrics from contact data
    aroi_operators = _collect_operator_metrics(relays_instance)
    if not aroi_operators:
        return {}
    
    # Step 2: Sort operators into leaderboard category rankings
    leaderboards = _rank_operators(aroi_operators)
    
    # Step 3: Format for template rendering and generate summary
    return _format_leaderboard_entries(leaderboards, aroi_operators, relays_instance)


def _collect_operator_metrics(relays_instance):
    """
    Collect per-operator metrics from contact-based aggregations.
    
    Iterates through all contacts, gathering existing metrics from categorization
    and computing new metrics (diversity, reliability, bandwidth scores, etc.)
    
    Returns:
        dict: operator_key -> metrics dict for all qualifying operators
    """
    contacts = relays_instance.json.get('sorted', {}).get('contact', {})
    all_relays = relays_instance.json.get('relays', [])

    # PERFORMANCE OPTIMIZATION: Pre-calculate rare countries once instead of per-operator
    # This eliminates O(n²) performance where rare countries were calculated 3,123 times
    # Now calculated once and reused, improving performance by ~95%
    country_data = relays_instance.json.get('sorted', {}).get('country', {})
    as_sorted_data = relays_instance.json.get('sorted', {}).get('as', {})
    from .country_utils import get_rare_countries_weighted_with_existing_data
    from .bandwidth_formatter import pick_best_period
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
            
        # Use AROI domain as key if available, otherwise build a
        # friendlier fallback display name from the raw contact info.
        if aroi_domain and aroi_domain != 'none':
            operator_key = aroi_domain
        else:
            # Option A (incomplete-AROI fallback): when an operator has a
            # parseable `url:<domain>` token in their contact string but
            # is missing one of the other AROI fields (typically
            # ciissversion), aroi_domain is None — but we can still
            # derive a recognisable display name from the url token and
            # tag it as "(incomplete AROI)" so the leaderboard row is
            # still attributable to the operator's domain instead of
            # rendering as a truncated raw blob like
            # 'email:tor[]foo.com url:https:...'.
            #
            # Falls back through two earlier layers when no url: token
            # is present:
            #   1. extract_contact_display_name() — same email/name/url
            #      derivation used elsewhere in the site
            #   2. raw contact-info string truncated to 30 chars
            #   3. contact_hash prefix as last resort
            operator_key = _incomplete_aroi_display_name(contact_info, contact_hash)
            # Collision guard: two different contact_hash groups can
            # resolve to the same fallback display name (e.g. two
            # operators both publishing url:example.com but with
            # different ContactInfo variants and no ciissversion). The
            # later iteration would otherwise overwrite the earlier
            # entry in aroi_operators, silently dropping the first
            # operator's metrics. Append a short contact_hash suffix on
            # collision so both rows are preserved. Proper cross-
            # contact_hash *merging* is a larger refactor (would need to
            # re-aggregate from raw relays) and is intentionally
            # deferred — preventing data loss is the priority here.
            if operator_key in aroi_operators:
                operator_key = f"{operator_key}#{contact_hash[:8]}"
        
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
        
        # === MERGED LOOP: IPv4/IPv6 + Validation + Countries + Platforms ===
        # All per-relay metric collection in a single pass over operator_relays
        countries = set()
        platforms = set()
        non_linux_count = 0
        non_linux_bandwidth = 0
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
        # B4.1: per-version split (used by leaderboard tier badge + new columns)
        validated_v2_relay_count = 0
        validated_v3_relay_count = 0
        v2_relay_count = 0  # ANY ciissversion:2 declaration (valid or not)
        v3_relay_count = 0  # ANY ciissversion:3 declaration
        td_sums = {'1_month': 0, '6_months': 0, '1_year': 0, '5_years': 0}
        
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
            
            # Collect geographic/platform diversity (merged from separate loops)
            relay_country = relay.get('country', '')
            if relay_country:
                countries.add(relay_country)
            relay_platform = relay.get('platform', '')
            if relay_platform:
                platforms.add(relay_platform)
                if not relay_platform.startswith('Linux'):
                    non_linux_count += 1
                    non_linux_bandwidth += relay_bandwidth
            
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
            # B4.1: tally per-version DECLARATIONS (any v2 or v3 contact)
            # so we can compute v3_pct_of_total even for operators
            # whose v3 relays haven't been validated yet.
            relay_aroi_version = relay.get('aroi_version')
            if relay_aroi_version == '2':
                v2_relay_count += 1
            elif relay_aroi_version == '3':
                v3_relay_count += 1

            if fp in validation_map:
                result = validation_map[fp]
                if result.get('valid', False):
                    # This relay has valid AROI proof
                    validated_relay_count += 1
                    validated_bandwidth += relay_bandwidth
                    validated_consensus_weight += relay_consensus_weight

                    # B4.1: per-version validated counts so the leaderboard
                    # can show "v2: N validated, v3: N validated".
                    val_version = result.get('ciissversion') or relay_aroi_version
                    if val_version == '2':
                        validated_v2_relay_count += 1
                    elif val_version == '3':
                        validated_v3_relay_count += 1

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
            
            relay_td = relay.get('total_data', {})
            for _p in ('1_month', '6_months', '1_year', '5_years'):
                td_sums[_p] += relay_td.get(_p, 0)
        
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
        
        # Bandwidth capacity for relays in rare countries only (matches diverse relay count)
        rare_country_bandwidth = sum(relay.get('observed_bandwidth', 0) for relay in operator_relays
                                     if relay.get('country', '') in operator_rare_countries)
        
        # Calculate all country breakdowns in a single pass over operator_relays
        rare_country_breakdown = {}
        all_country_breakdown = {}
        non_eu_country_breakdown = {}
        non_eu_bandwidth = 0
        for relay in operator_relays:
            country = relay.get('country', '')
            if country:
                all_country_breakdown[country] = all_country_breakdown.get(country, 0) + 1
                if country in operator_rare_countries:
                    rare_country_breakdown[country] = rare_country_breakdown.get(country, 0) + 1
                if country not in EU_POLITICAL_REGION:
                    non_eu_country_breakdown[country] = non_eu_country_breakdown.get(country, 0) + 1
                    non_eu_bandwidth += relay.get('observed_bandwidth', 0)
        
        # Sort all breakdowns by relay count (descending) then by country name
        _sort_key = lambda x: (-x[1], x[0])
        sorted_rare_breakdown = sorted(rare_country_breakdown.items(), key=_sort_key)
        sorted_all_country_breakdown = sorted(all_country_breakdown.items(), key=_sort_key)
        sorted_non_eu_country_breakdown = sorted(non_eu_country_breakdown.items(), key=_sort_key)
        
        # Distinct non-EU country count (geographic BREADTH metric for the
        # Jurisdiction Globetrotters leaderboard; non_eu_count above is the
        # per-relay VOLUME metric for Global Powerhouses)
        non_eu_country_count = len(non_eu_country_breakdown)
        

        

        
        # Diversity score (using centralized calculation with AS rarity)
        as_diversity_score = calculate_operator_as_diversity_score(
            operator_relays, as_sorted_data
        )
        diversity_score = calculate_diversity_score(
            countries=list(countries), 
            platforms=list(platforms), 
            unique_as_count=unique_as_count,
            as_diversity_score=as_diversity_score
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
            from datetime import datetime, timezone
            from .time_utils import parse_onionoo_timestamp
            # UTC-aware, matching every other timestamp consumer; naive
            # local time made veteran_days drift by up to a day on
            # non-UTC hosts, breaking cross-machine reproducibility.
            current_date = datetime.now(timezone.utc)
            
            # Find earliest first_seen date among all relays
            earliest_first_seen = None
            for relay in operator_relays:
                relay_first_seen = parse_onionoo_timestamp(relay.get('first_seen', ''))
                if relay_first_seen is not None and (
                        earliest_first_seen is None or relay_first_seen < earliest_first_seen):
                    earliest_first_seen = relay_first_seen
            
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
        
        # Total data transferred: pick best-available period from sums collected above
        operator_total_data, operator_total_data_period = pick_best_period(td_sums)
        
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
            # sorted() pins byte-stable output: set iteration order varies
            # with PYTHONHASHSEED, which made country/platform lists (and
            # every surface that joins them) differ run-to-run
            'countries': sorted(countries),
            'country_count': len(countries),
            'platforms': sorted(platforms),
            'platform_count': len(platforms),
            'non_linux_count': non_linux_count,
            'non_linux_bandwidth': non_linux_bandwidth,
            'non_eu_count': non_eu_count,
            'non_eu_bandwidth': non_eu_bandwidth,
            'non_eu_country_count': non_eu_country_count,
            'rare_country_count': rare_country_count,
            'relays_in_rare_countries': relays_in_rare_countries,
            'rare_country_bandwidth': rare_country_bandwidth,
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

            # === B4.1: v2/v3 migration metadata for tier badge + columns ===
            'validated_v2_relay_count': validated_v2_relay_count,
            'validated_v3_relay_count': validated_v3_relay_count,
            'v2_relay_count': v2_relay_count,
            'v3_relay_count': v3_relay_count,
            'v3_pct_of_total': (
                v3_relay_count / total_relays * 100 if total_relays > 0 else 0.0
            ),
            'v3_tier': _classify_v3_tier_local(v3_relay_count, total_relays),
            
            # === TOTAL DATA TRANSFERRED (NEW) ===
            'total_data_transferred': operator_total_data,
            'total_data_period': operator_total_data_period,
            
            # Keep minimal relay data for potential future use
            'relays': operator_relays
        }
    
    return aroi_operators


def _rank_operators(aroi_operators):
    """
    Sort operators into leaderboard category rankings.
    
    Each category is a sorted list of (operator_key, metrics) tuples, top 50.
    Uses _top_n() helper to eliminate 18 repeated sort-and-slice blocks.
    To add a new leaderboard: add one _top_n() call here.
    
    Returns:
        dict: category_name -> sorted list of (operator_key, metrics) tuples
    """
    # Filter lambdas for categories that require minimum thresholds
    _reliability_filter = lambda v: v['total_relays'] > 25 and v['reliability_6m_score'] > 0.0
    _legacy_filter = lambda v: v['total_relays'] > 25 and v['reliability_5y_score'] > 0.0
    _bw_masters_filter = lambda v: v['total_relays'] > 25 and v['bandwidth_6m_score'] > 0.0
    _bw_legends_filter = lambda v: v['total_relays'] > 25 and v['bandwidth_5y_score'] > 0.0
    _validated_filter = lambda v: v['validated_relay_count'] > 0
    # OS Polyglots: only operators running >= 2 distinct OSes (incl. Linux) qualify
    _polyglot_filter = lambda v: v['platform_count'] >= 2

    # DIVERSITY CLUSTER: each diversity dimension has two co-equal boards —
    # a VOLUME board (scale of non-dominant contribution: relay count) and a
    # BREADTH board (internal spread: distinct count) — so a 600-relay
    # single-OS operator and a 15-relay six-OS operator can each top the
    # board that reflects their kind of diversity. Neither is buried under
    # the other's metric.
    leaderboards = {
        'bandwidth':          _top_n(aroi_operators, 'total_bandwidth'),
        'consensus_weight':   _top_n(aroi_operators, 'total_consensus_weight'),
        'exit_authority':     _top_n(aroi_operators, 'exit_consensus_weight'),
        'guard_authority':    _top_n(aroi_operators, 'guard_consensus_weight'),
        'exit_operators':     _top_n(aroi_operators, 'exit_count'),
        'guard_operators':    _top_n(aroi_operators, 'guard_count'),
        'reliability_masters': _top_n(aroi_operators, 'reliability_6m_score', filter_fn=_reliability_filter),
        'legacy_titans':      _top_n(aroi_operators, 'reliability_5y_score', filter_fn=_legacy_filter),
        'most_diverse':       _top_n(aroi_operators, 'diversity_score'),
        # Platform diversity — Volume: most non-Linux relays contributed
        'platform_volume':    _top_n(aroi_operators, 'non_linux_count',
                                     tiebreakers=['platform_count', 'total_bandwidth']),
        # Platform diversity — Breadth: most distinct OSes (incl. Linux), >=2 to qualify
        'platform_breadth':   _top_n(aroi_operators, 'platform_count',
                                     filter_fn=_polyglot_filter,
                                     tiebreakers=['non_linux_count', 'total_bandwidth']),
        # Geographic diversity — Volume: most relays outside the EU
        'non_eu_volume':      _top_n(aroi_operators, 'non_eu_count',
                                     tiebreakers=['non_eu_country_count', 'total_bandwidth']),
        # Geographic diversity — Breadth: most distinct non-EU countries
        'non_eu_breadth':     _top_n(aroi_operators, 'non_eu_country_count',
                                     tiebreakers=['non_eu_count', 'total_bandwidth']),
        # Geographic diversity — Rare-country breadth
        'frontier_builders':  _top_n(aroi_operators, 'rare_country_count',
                                     tiebreakers=['relays_in_rare_countries', 'total_bandwidth']),
        'network_veterans':   _top_n(aroi_operators, 'veteran_score'),
        'ipv4_leaders':       _top_n(aroi_operators, 'unique_ipv4_count'),
        'ipv6_leaders':       _top_n(aroi_operators, 'unique_ipv6_count'),
        'bandwidth_masters':  _top_n(aroi_operators, 'bandwidth_6m_score', filter_fn=_bw_masters_filter),
        'bandwidth_legends':  _top_n(aroi_operators, 'bandwidth_5y_score', filter_fn=_bw_legends_filter),
        'validated_relays':   _top_n(aroi_operators, 'validated_relay_count', filter_fn=_validated_filter),
        'total_data_champions': _top_n(aroi_operators, 'total_data_transferred'),
    }

    return leaderboards


# ---------------------------------------------------------------------------
# Table-driven per-category formatting config for _format_leaderboard_entries.
# The VARYING parts of the former 19-category switchboard live in these tables;
# genuinely unique logic lives in the small _*_extras() helpers below.
# ---------------------------------------------------------------------------

# Categories whose primary bandwidth column shows a historical average
# instead of the current total bandwidth.
_PRIMARY_BANDWIDTH_KEYS = {
    'bandwidth_masters': 'bandwidth_6m_average',
    'bandwidth_legends': 'bandwidth_5y_average',
}

# Achievement titles for top 3 operators: category -> (entry field,
# metrics key that must be truthy (None = always), {rank: title}).
_ACHIEVEMENT_TITLES = {
    'frontier_builders': ('frontier_achievement_title', 'rare_country_breakdown',
                          {1: "🌟 Frontier Legend", 2: "⭐ Frontier Master", 3: "✨ Frontier Champion"}),
    'most_diverse': ('diversity_master_title', None,
                     {1: "🌍 Diversity Legend", 2: "🌟 Diversity Master", 3: "🌐 Diversity Champion"}),
    'ipv4_leaders': ('ipv4_achievement_title', None,
                     {1: "🥇 IPv4 Legend", 2: "🥈 IPv4 Master", 3: "🥉 IPv4 Champion"}),
    'ipv6_leaders': ('ipv6_achievement_title', None,
                     {1: "🥇 IPv6 Legend", 2: "🥈 IPv6 Master", 3: "🥉 IPv6 Champion"}),
}

# Historical score categories: category -> (metrics key prefix, period label).
_SCORE_CATEGORIES = {
    'reliability_masters': ('reliability_6m', '6-month'),
    'legacy_titans': ('reliability_5y', '5-year'),
    'bandwidth_masters': ('bandwidth_6m', '6-month'),
    'bandwidth_legends': ('bandwidth_5y', '5-year'),
}

# IP-address categories: category -> (metrics key prefix, display label).
_IP_CATEGORIES = {
    'ipv4_leaders': ('ipv4', 'IPv4'),
    'ipv6_leaders': ('ipv6', 'IPv6'),
}

# Consensus weight metrics rendered as '<key>_pct' entry fields ("{value * 100:.2f}%").
_PCT_KEYS = ('total_consensus_weight', 'exit_consensus_weight', 'guard_consensus_weight',
             'ipv4_total_consensus_weight', 'ipv6_total_consensus_weight', 'validated_consensus_weight')

# Metrics copied through to the formatted entry unchanged.
_PASSTHROUGH_KEYS = (
    'aroi_domain', 'contact_hash', 'contact_info', 'total_relays', 'guard_count', 'exit_count',
    'middle_count', 'measured_count', 'unique_as_count', 'platform_count', 'non_linux_count',
    'non_eu_count', 'non_eu_country_count', 'rare_country_count', 'relays_in_rare_countries', 'veteran_days',
    'veteran_relay_scaling_factor', 'unique_ipv4_count', 'unique_ipv6_count', 'ipv4_relay_count',
    'ipv6_relay_count', 'ipv4_total_bandwidth', 'ipv6_total_bandwidth', 'ipv4_guard_count',
    'ipv4_exit_count', 'ipv4_middle_count', 'ipv6_guard_count', 'ipv6_exit_count', 'ipv6_middle_count',
    'validated_relay_count', 'invalid_relay_count', 'validated_guard_count', 'validated_exit_count',
    'validated_middle_count', 'validated_consensus_weight', 'validated_country_count',
    'validated_v2_relay_count', 'validated_v3_relay_count', 'v2_relay_count', 'v3_relay_count',
    'v3_pct_of_total', 'v3_tier',
)

# Defaults for category-specific entry fields (non-applicable categories keep these).
_ENTRY_EXTRAS_DEFAULTS = dict.fromkeys((
    'geographic_achievement', 'geographic_breakdown_details', 'geographic_breakdown_tooltip',
    'rare_country_details', 'rare_country_tooltip', 'frontier_achievement_title',
    'platform_breakdown_details', 'platform_breakdown_tooltip',
    'diversity_master_title', 'diversity_breakdown_details', 'diversity_breakdown_tooltip',
    'veteran_details_short', 'veteran_tooltip', 'reliability_details_short', 'reliability_tooltip',
    'bandwidth_details_short', 'bandwidth_tooltip', 'ipv4_achievement_title', 'ipv6_achievement_title',
    'ip_address_details', 'ip_address_tooltip', 'validated_bandwidth', 'validated_bandwidth_unit',
), "")
# Score fields default to formatted zero/unity values (matching f"{0.0:.1f}" etc.).
_ENTRY_EXTRAS_DEFAULTS.update({
    'reliability_score': "0.0", 'reliability_average': "0.0%", 'reliability_weight': "1.0x",
    'bandwidth_score': "0.0", 'bandwidth_average': "0.0", 'bandwidth_weight': "1.0x",
})


def _truncate_with_ellipsis(text, max_chars):
    """Truncate to max_chars total, reserving 3 chars for the trailing "..."."""
    return text[:max_chars - 3] + "..." if len(text) > max_chars else text


def _geographic_extras(category, metrics, bandwidth_formatter):
    """non_eu_volume / non_eu_breadth: dynamic geographic achievement + non-EU
    country breakdown (used for the specialization column instead of all countries).

    Bugbot fix (PR #217): derive the achievement from the operator's NON-EU
    countries only — these boards rank non-EU presence, so an EU-heavy operator
    must not earn EU-derived titles here."""
    non_eu_countries = [country for country, _count in metrics['non_eu_country_breakdown']]
    details, tooltip = _format_breakdown_details(metrics['non_eu_country_breakdown'], 52)
    return {
        'geographic_achievement': calculate_geographic_achievement(non_eu_countries),
        'geographic_breakdown_details': details,
        'geographic_breakdown_tooltip': tooltip,
    }


def _frontier_extras(category, metrics, bandwidth_formatter):
    """frontier_builders: rare country breakdown with custom "relay/relays" formatter."""
    if not metrics['rare_country_breakdown']:
        return {}
    details, tooltip = _format_breakdown_details(
        metrics['rare_country_breakdown'], 44,
        lambda count, country: f"{count} relay{'s' if count != 1 else ''} in {country}"
    )
    return {'rare_country_details': details, 'rare_country_tooltip': tooltip}


def _platform_extras(category, metrics, bandwidth_formatter):
    """platform_volume / platform_breadth: platform breakdown for the
    specialization column. platform_volume (Non-Linux Powerhouses) shows
    non-Linux relays only; platform_breadth (OS Polyglots) counts ALL OSes
    incl. Linux, so its breakdown includes Linux too."""
    include_linux = (category == 'platform_breadth')
    platform_breakdown = {}
    for relay in metrics['relays']:
        platform = relay.get('platform', 'Unknown')
        if platform and (include_linux or not platform.lower().startswith('linux')):
            # Extract short platform name (before first space or version number)
            short_platform = platform.split()[0] if platform else 'Unknown'
            # Map common platform names to shorter versions
            for prefix, short_name in (('win', 'Win'), ('mac', 'Mac'), ('darwin', 'Mac'),
                                       ('freebsd', 'FreeBSD'), ('openbsd', 'OpenBSD'), ('netbsd', 'NetBSD')):
                if short_platform.lower().startswith(prefix):
                    short_platform = short_name
                    break
            platform_breakdown[short_platform] = platform_breakdown.get(short_platform, 0) + 1

    # Sort by relay count (descending) then by platform name
    sorted_platform_breakdown = sorted(platform_breakdown.items(),
                                       key=lambda x: (-x[1], x[0]))

    # Create short format (max 32 chars): "Win: 5, Mac: 3, FreeBSD: 2"
    platform_breakdown_full = ", ".join(f"{platform}: {count}" for platform, count in sorted_platform_breakdown)

    # Create full tooltip with platform details only (countries not relevant for platform diversity)
    platform_tooltip_text = ", ".join(f"{count} {platform} relays" for platform, count in sorted_platform_breakdown)
    return {
        'platform_breakdown_details': _truncate_with_ellipsis(platform_breakdown_full, 32),
        'platform_breakdown_tooltip': f"Platform Distribution: {platform_tooltip_text}",
    }


def _diversity_extras(category, metrics, bandwidth_formatter):
    """most_diverse: diversity calculation breakdown + score tooltip."""
    country_count = metrics['country_count']
    platform_count = metrics['platform_count']
    as_count = metrics['unique_as_count']

    # Create short format (max 20 chars): "5 Countries, 3 OS, 8 AS"
    diversity_breakdown_full = f"{country_count} Countries, {platform_count} OS, {as_count} AS"

    # Create full tooltip with calculation details
    return {
        'diversity_breakdown_details': _truncate_with_ellipsis(diversity_breakdown_full, 20),
        'diversity_breakdown_tooltip': f"Diversity Score: {country_count} countries x 3.0 + {as_count} AS (rarity-weighted) x 2.0 + {platform_count} platforms x 1.0 = {metrics['diversity_score']:.1f}",
    }


def _veteran_extras(category, metrics, bandwidth_formatter):
    """network_veterans: veteran tenure tooltip with 20-char short version."""
    veteran_tooltip = metrics['veteran_details']
    if not veteran_tooltip:
        return {}
    if len(veteran_tooltip) > 20:
        # Extract just the days and scaling factor for short display
        days_part = f"{metrics['veteran_days']} days * {metrics['veteran_relay_scaling_factor']}"
        if len(days_part) > 17:  # leave room for "..."
            veteran_details_short = f"{metrics['veteran_days']} days..."
        else:
            veteran_details_short = days_part + "..."
    else:
        veteran_details_short = veteran_tooltip
    return {'veteran_details_short': veteran_details_short, 'veteran_tooltip': veteran_tooltip}


def _score_extras(category, metrics, bandwidth_formatter):
    """reliability_masters / legacy_titans / bandwidth_masters / bandwidth_legends:
    period-matched score, average and simplified tooltip (no weighting info)."""
    prefix, period_label = _SCORE_CATEGORIES[category]
    score = metrics[prefix + '_score']
    average = metrics[prefix + '_average']
    weight = metrics[prefix + '_weight']
    if prefix.startswith('reliability'):
        return {
            'reliability_score': f"{score:.1f}",
            'reliability_average': f"{average:.1f}%",
            'reliability_weight': f"{weight:.1f}x",
            'reliability_details_short': f"{average:.1f}% avg",
            'reliability_tooltip': f"{period_label} reliability: {average:.1f}% average uptime ({metrics['total_relays']} relays)",
        }
    # Format bandwidth average with unit (reuse existing formatters)
    formatted_avg, unit = _format_bandwidth_with_auto_unit(average, bandwidth_formatter)
    return {
        'bandwidth_score': f"{score:.1f}",
        'bandwidth_average': f"{average:.1f}",
        'bandwidth_weight': f"{weight:.1f}x",
        'bandwidth_details_short': f"{formatted_avg} {unit} avg",
        'bandwidth_tooltip': f"{period_label} bandwidth: {formatted_avg} {unit} average bandwidth ({metrics['total_relays']} relays)",
    }


def _ip_extras(category, metrics, bandwidth_formatter):
    """ipv4_leaders / ipv6_leaders: unique-address details + infrastructure tooltip."""
    prefix, label = _IP_CATEGORIES[category]
    unique_count = metrics['unique_' + prefix + '_count']
    # Format IP-specific bandwidth with unit (reuse existing formatters)
    formatted_ip_bandwidth, ip_bandwidth_unit = _format_bandwidth_with_auto_unit(
        metrics[prefix + '_total_bandwidth'], bandwidth_formatter
    )
    return {
        'ip_address_details': f"{unique_count} unique {label}",
        'ip_address_tooltip': f"{label} Infrastructure: {unique_count} unique addresses across {metrics[prefix + '_relay_count']} relays with {formatted_ip_bandwidth} {ip_bandwidth_unit} bandwidth",
    }


def _validated_extras(category, metrics, bandwidth_formatter):
    """validated_relays: validated-only bandwidth (skipped for other categories)."""
    formatted, unit = _format_bandwidth_with_auto_unit(metrics['validated_bandwidth'], bandwidth_formatter)
    return {'validated_bandwidth': formatted, 'validated_bandwidth_unit': unit}


# Dispatch table: category -> extras handler (absent categories use defaults only).
_CATEGORY_EXTRAS = {
    'non_eu_volume': _geographic_extras,
    'non_eu_breadth': _geographic_extras,
    'frontier_builders': _frontier_extras,
    'platform_volume': _platform_extras,
    'platform_breadth': _platform_extras,
    'most_diverse': _diversity_extras,
    'network_veterans': _veteran_extras,
    'reliability_masters': _score_extras,
    'legacy_titans': _score_extras,
    'bandwidth_masters': _score_extras,
    'bandwidth_legends': _score_extras,
    'ipv4_leaders': _ip_extras,
    'ipv6_leaders': _ip_extras,
    'validated_relays': _validated_extras,
}


def _format_leaderboard_entries(leaderboards, aroi_operators, relays_instance):
    """
    Format leaderboard entries for Jinja2 template rendering.
    
    Converts raw operator metrics into display-ready strings with units,
    percentages, achievement badges, and tooltips.

    Per-category variations (achievement titles, score periods, IP labels,
    breakdown details/tooltips) are table-driven via the _CATEGORY_EXTRAS,
    _ACHIEVEMENT_TITLES and related config tables defined above.

    Returns:
        dict with 'leaderboards' (formatted), 'summary' (stats), 'raw_operators'
    """
    from .bandwidth_formatter import format_data_volume_with_unit, compute_total_data_pct

    # Get per-period network totals for period-matched percentage calculations
    _net_by_period = {}
    if hasattr(relays_instance, 'json') and relays_instance.json.get('network_health'):
        _net_by_period = relays_instance.json['network_health'].get('network_total_data_by_period', {})

    # Format data for template rendering with bandwidth units (reuse existing formatters)
    formatted_leaderboards = {}
    for category, data in leaderboards.items():
        formatted_data = []
        for rank, (operator_key, metrics) in enumerate(data, 1):
            # Use existing bandwidth formatting methods (top10 specific formatting)
            # For bandwidth categories, use historical bandwidth instead of current bandwidth
            bandwidth_value = metrics[_PRIMARY_BANDWIDTH_KEYS.get(category, 'total_bandwidth')]
            formatted_bandwidth, bandwidth_unit = _format_bandwidth_with_auto_unit(
                bandwidth_value, relays_instance.bandwidth_formatter
            )

            # Category-specific extras: defaults for non-applicable categories,
            # overridden by the table-driven handler for the current category
            extras = dict(_ENTRY_EXTRAS_DEFAULTS)
            handler = _CATEGORY_EXTRAS.get(category)
            if handler:
                extras.update(handler(category, metrics, relays_instance.bandwidth_formatter))

            # Add achievement titles for top 3 operators (table-driven)
            title_config = _ACHIEVEMENT_TITLES.get(category)
            if title_config and (title_config[1] is None or metrics[title_config[1]]):
                extras[title_config[0]] = title_config[2].get(rank, "")

            # Format total data transferred for all categories (reused in template)
            raw_total_data = metrics.get('total_data_transferred', 0)
            raw_total_data_period = metrics.get('total_data_period')
            formatted_total_data_transferred = format_data_volume_with_unit(raw_total_data)
            total_data_pct = compute_total_data_pct(raw_total_data, raw_total_data_period, _net_by_period) if raw_total_data_period else ""

            display_name = metrics['aroi_domain'] if metrics['aroi_domain'] and metrics['aroi_domain'] != 'none' else operator_key

            # Calculate percentages for guard, exit and non-EU relay ratios
            guard_percentage = (metrics['guard_count'] / metrics['total_relays'] * 100) if metrics['total_relays'] > 0 else 0
            exit_percentage = (metrics['exit_count'] / metrics['total_relays'] * 100) if metrics['total_relays'] > 0 else 0
            non_eu_percentage = (metrics['non_eu_count'] / metrics['total_relays'] * 100) if metrics['total_relays'] > 0 else 0

            # === VOLUME/BREADTH SUMMARY STRINGS (diversity cluster boards) ===
            # Every diversity board shows BOTH numbers (volume + breadth) so the
            # ranking is transparent: the board's primary metric leads, the
            # other appears in parentheses.
            _os_n = metrics['platform_count']
            _nl_n = metrics['non_linux_count']
            _neu_n = metrics['non_eu_count']
            _neuc_n = metrics['non_eu_country_count']
            _os_word = "OS" if _os_n == 1 else "OSes"
            _nl_word = "relay" if _nl_n == 1 else "relays"
            _neu_word = "relay" if _neu_n == 1 else "relays"
            _neuc_word = "country" if _neuc_n == 1 else "countries"

            # Assemble the entry: raw passthrough metrics, per-role bandwidth columns,
            # consensus weight percentages, computed display fields, then category extras
            formatted_entry = {key: metrics[key] for key in _PASSTHROUGH_KEYS}

            # Format role/diversity-specific bandwidth columns (exit, guard, non-Linux,
            # non-EU and rare-country bandwidth only count relays matching each criteria)
            for prefix in ('exit', 'guard', 'non_linux', 'non_eu', 'rare_country'):
                bw, unit = _format_bandwidth_with_auto_unit(
                    metrics[prefix + '_bandwidth'], relays_instance.bandwidth_formatter
                )
                formatted_entry[prefix + '_bandwidth'] = bw
                formatted_entry[prefix + '_bandwidth_unit'] = unit

            formatted_entry.update({key + '_pct': f"{metrics[key] * 100:.2f}%" for key in _PCT_KEYS})

            formatted_entry.update({
                'rank': rank,
                'operator_key': operator_key,
                'display_name': display_name,
                'contact_info_escaped': safe_html_escape(metrics['contact_info']),
                'total_bandwidth': formatted_bandwidth,
                'bandwidth_unit': bandwidth_unit,
                'guard_percentage': f"{guard_percentage:.0f}%",
                'exit_percentage': f"{exit_percentage:.0f}%",
                # Frontier Builders should show only rare country count, not total country count
                'country_count': metrics['rare_country_count'] if category == 'frontier_builders' else metrics['country_count'],
                'countries': metrics['countries'][:5],  # Top 5 countries for display
                'platforms': metrics['platforms'][:3],  # Top 3 platforms for display
                'non_eu_count_with_percentage': f"{metrics['non_eu_count']} ({non_eu_percentage:.0f}%)",
                # === VOLUME/BREADTH SUMMARIES (diversity cluster) ===
                'platform_volume_summary': f"{_nl_n} non-Linux {_nl_word} ({_os_n} {_os_word})",
                'platform_breadth_summary': f"{_os_n} {_os_word} ({_nl_n} non-Linux {_nl_word})",
                'non_eu_volume_summary': f"{_neu_n} {_neu_word} ({_neuc_n} {_neuc_word})",
                'non_eu_breadth_summary': f"{_neuc_n} {_neuc_word} ({_neu_n} {_neu_word})",
                'diversity_score': f"{metrics['diversity_score']:.1f}",
                'uptime_percentage': f"{metrics['uptime_percentage']:.1f}%",
                'veteran_score': f"{metrics['veteran_score']:.0f}",
                'first_seen_date': metrics['first_seen'].split(' ')[0] if metrics['first_seen'] else 'Unknown',
                'v3_relay_pct_str': f"{metrics['v3_pct_of_total']:.0f}%",
                'total_data_transferred': formatted_total_data_transferred,
                'total_data_pct': total_data_pct,
            })
            formatted_entry.update(extras)
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
            'most_diverse': 'Diversity All-Rounders (Overall)',
            'platform_volume': 'Non-Linux Powerhouses (Platform Volume)',
            'platform_breadth': 'OS Polyglots (Platform Breadth)',
            'non_eu_volume': 'Global Powerhouses (Non-EU Volume)',
            'non_eu_breadth': 'Jurisdiction Globetrotters (Non-EU Breadth)',
            'frontier_builders': 'Frontier Builders (Rare-Country Breadth)',
            'network_veterans': 'Network Veterans',
            'ipv4_leaders': 'IPv4 Address Leaders',
            'ipv6_leaders': 'IPv6 Address Leaders',
            'validated_relays': 'AROI Validation Champions',
            'total_data_champions': 'Total Data Transferred Champions (5-Year)',
        }
    }
    
    return {
        'leaderboards': formatted_leaderboards,
        'summary': summary_stats,
        'raw_operators': aroi_operators  # For potential future use
    }

 