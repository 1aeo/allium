"""
File: page_writer.py

HTML page rendering and file I/O for allium static site generation.
Contains Jinja2 environment setup, multiprocessing workers, and all
page writing functions.
Extracted from relays.py for better modularity.
"""

import functools
import multiprocessing as mp
import os
import time
from shutil import rmtree

from jinja2 import Environment, FileSystemLoader, FileSystemBytecodeCache

from .aroileaders import _safe_parse_ip_address
from .bandwidth_formatter import (
    BandwidthFormatter,
    determine_unit,
    get_divisor_for_unit,
    format_bandwidth_with_unit,
    determine_unit_filter,
    format_bandwidth_filter,
)
from .intelligence_engine import IntelligenceEngine
from .time_utils import format_time_ago

ABS_PATH = os.path.dirname(os.path.abspath(__file__))



# Template bytecode cache directory for improved rendering performance
TEMPLATE_CACHE_DIR = os.path.join(os.path.dirname(ABS_PATH), ".jinja2_cache")
os.makedirs(TEMPLATE_CACHE_DIR, exist_ok=True)

ENV = Environment(
    loader=FileSystemLoader(os.path.join(ABS_PATH, "../templates")),
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=True,  # Enable autoescape to prevent XSS vulnerabilities
    bytecode_cache=FileSystemBytecodeCache(TEMPLATE_CACHE_DIR),  # Cache compiled templates
    auto_reload=False,  # Disable for production performance
)

# Jinja2 filter functions now imported from bandwidth_formatter.py

# Add custom filters to the Jinja2 environment
ENV.filters['determine_unit'] = determine_unit_filter
ENV.filters['format_bandwidth_with_unit'] = format_bandwidth_with_unit
ENV.filters['format_bandwidth'] = format_bandwidth_filter
ENV.filters['format_time_ago'] = format_time_ago
ENV.filters['split'] = lambda s, sep='/': s.split(sep) if s else []

# Multiprocessing globals (initialized via fork for copy-on-write memory sharing)
_mp_relay_set = None
_mp_template = None
_mp_page_type = None
_mp_the_prefixed = None
_mp_validated_aroi_domains = None


def _init_mp_worker(relay_set, template, page_type=None, the_prefixed=None, validated_aroi_domains=None):
    """Initialize worker with shared data via fork"""
    global _mp_relay_set, _mp_template, _mp_page_type, _mp_the_prefixed, _mp_validated_aroi_domains
    _mp_relay_set = relay_set
    _mp_template = template
    _mp_page_type = page_type
    _mp_the_prefixed = the_prefixed if the_prefixed is not None else []
    _mp_validated_aroi_domains = validated_aroi_domains if validated_aroi_domains is not None else set()


def _render_page_mp(args):
    """Render single page in worker process.
    
    OPTIMIZED: Now receives only (html_path, value) and builds template args
    using forked memory. This avoids serializing large relay_subset data
    through IPC, reducing overhead from ~300KB/page to ~100 bytes/page.
    """
    html_path, value = args
    
    # Get page data from forked memory (no IPC serialization needed)
    page_data = _mp_relay_set.json["sorted"][_mp_page_type][value]
    
    # Build template args in worker (uses forked memory)
    template_args = _mp_relay_set._build_template_args(
        _mp_page_type, value, page_data, _mp_the_prefixed, _mp_validated_aroi_domains
    )
    
    # Render and write
    rendered = _mp_template.render(relays=_mp_relay_set, **template_args)
    with open(html_path, "w", encoding="utf8") as f:
        f.write(rendered)
    return True


# =============================================================================
# HELPER FUNCTIONS (DRY - used by multiple precomputation/rendering paths)
# =============================================================================

def _compute_network_position_safe(guard_count, middle_count, exit_count, total_relays):
    """Compute network position with fallback handling.
    
    DRY helper that wraps IntelligenceEngine._calculate_network_position() with
    consistent error handling. Used by precomputation workers, template builders,
    and misc page generation.
    
    Args:
        guard_count: Number of guard relays
        middle_count: Number of middle relays  
        exit_count: Number of exit relays
        total_relays: Total relay count
        
    Returns:
        dict: Network position with 'label' and 'formatted_string' keys
    """
    try:
        return IntelligenceEngine({})._calculate_network_position(
            guard_count, middle_count, exit_count, total_relays)
    except Exception:
        return {'label': 'Mixed', 'formatted_string': f'{total_relays} relays'}


# Precomputation worker globals (for contact page data parallelization)
_precompute_relay_set = None


def _init_precompute_worker(relay_set):
    """Initialize precompute worker with shared relay_set via fork"""
    global _precompute_relay_set
    _precompute_relay_set = relay_set


def _precompute_contact_worker(args):
    """Precompute data for a single contact in worker process.
    
    Returns a flat dict of precomputed values to store directly on contact_data
    (Sonnet-style simple access) using parallel computation (Opus-style performance).
    """
    contact_hash, aroi_validation_timestamp, validated_aroi_domains = args
    
    try:
        contact_data = _precompute_relay_set.json["sorted"]["contact"][contact_hash]
        
        # Get member relays for this contact
        members = [_precompute_relay_set.json["relays"][idx] 
                   for idx in contact_data.get("relays", [])]
        if not members:
            return (contact_hash, None)
        
        # Determine bandwidth unit for this contact
        bandwidth_unit = _precompute_relay_set.bandwidth_formatter.determine_unit(
            contact_data.get("bandwidth", 0))
        
        # Pre-compute contact rankings
        contact_rankings = _precompute_relay_set._generate_contact_rankings(contact_hash)
        
        # Pre-compute operator reliability statistics
        operator_reliability = _precompute_relay_set._calculate_operator_reliability(
            contact_hash, members)
        
        # Pre-compute contact display data
        contact_display_data = _precompute_relay_set._compute_contact_display_data(
            contact_data, bandwidth_unit, operator_reliability, contact_hash, members)
        
        # Pre-compute AROI validation status
        if "aroi_validation_full" in contact_data:
            contact_validation_status = contact_data["aroi_validation_full"]
        else:
            contact_validation_status = _precompute_relay_set._get_contact_validation_status(members)
        
        # Check if this contact has a validated AROI domain
        aroi_domain = members[0].get("aroi_domain") if members else None
        is_validated_aroi = (aroi_domain and aroi_domain != "none" and 
                            aroi_domain in validated_aroi_domains)
        
        # Return flat dict for direct storage on contact_data (simpler access pattern)
        return (contact_hash, {
            "contact_rankings": contact_rankings,
            "operator_reliability": operator_reliability,
            "contact_display_data": contact_display_data,
            "contact_validation_status": contact_validation_status,
            "aroi_validation_timestamp": aroi_validation_timestamp,
            "is_validated_aroi": is_validated_aroi,
            "precomputed_bandwidth_unit": bandwidth_unit,
            "aroi_domain": aroi_domain,  # Store for vanity URL generation (avoids re-fetching members)
        })
    except Exception as e:
        # Return None on error, sequential fallback will handle it
        return (contact_hash, None)


def _precompute_family_worker(args):
    """Precompute data for a single family in worker process.
    
    Returns a flat dict of precomputed values to store directly on family_data.
    Mirrors _precompute_contact_worker pattern for consistency.
    """
    family_hash, = args
    
    try:
        family_data = _precompute_relay_set.json["sorted"]["family"][family_hash]
        
        # Get member relays for this family
        members = [_precompute_relay_set.json["relays"][idx] 
                   for idx in family_data.get("relays", [])]
        if not members:
            return (family_hash, None)
        
        # Pre-compute AROI validation status (use cached if available)
        contact_validation_status = (family_data.get("aroi_validation_full") or 
                                     _precompute_relay_set._get_contact_validation_status(members))
        
        # Pre-compute network position using DRY helper
        network_position = _compute_network_position_safe(
            family_data["guard_count"], family_data["middle_count"], 
            family_data["exit_count"], len(members))
        
        # Return flat dict for direct storage on family_data
        return (family_hash, {
            "contact_validation_status": contact_validation_status,
            "network_position": network_position,
        })
    except Exception as e:
        # Return None on error, sequential fallback will handle it
        return (family_hash, None)




def create_output_dir(relay_set):
    """
    Ensure relay_set.output_dir exists (required for write functions)
    """
    os.makedirs(relay_set.output_dir, exist_ok=True)

def write_misc(
    relay_set,
    template,
    path,
    page_ctx=None,
    sorted_by=None,
    reverse=True,
    is_index=False,
):
    """
    Render and write unsorted HTML listings to disk
    
    Optimizes misc-families pages by pre-computing complex family statistics in Python
    instead of expensive Jinja2 template loops with deduplication logic.

    Args:
        template:    jinja template name
        path:        path to generate HTML document
        path_prefix: path to prefix other docs/includes
        sorted_by:   key to sort by, used in family and networks pages
        reverse:     passed to sort() function in family and networks pages
        is_index:    whether document is main index listing, limits list to 500
    """
    template = ENV.get_template(template)
    # relay_subset passed directly to template for thread safety
    relay_subset = relay_set.json["relays"]
    
    # Handle page context and path prefix
    if page_ctx is None:
        page_ctx = {'path_prefix': '../'}  # default fallback
    
    # Add AROI validation status to contact data for misc-contacts templates
    # This runs before write_pages_by_key, so we calculate once and store for reuse
    if template.name == "misc-contacts.html":
        for contact_hash, contact_data in relay_set.json["sorted"].get("contact", {}).items():
            # Only calculate if not already stored
            if "aroi_validation_status" not in contact_data:
                relay_indices = contact_data.get("relays", [])
                members = [relay_set.json["relays"][idx] for idx in relay_indices]
                validation_status = relay_set._get_contact_validation_status(members)
                contact_data["aroi_validation_status"] = validation_status["validation_status"]
                # Store full validation status for operator pages to reuse
                contact_data["aroi_validation_full"] = validation_status
    
    # Pre-compute family statistics for misc-families templates
    template_vars = {
        "relays": relay_set,
        "relay_subset": relay_subset,  # Pass directly for thread safety
        "sorted_by": sorted_by,
        "reverse": reverse,
        "is_index": is_index,
        "page_ctx": page_ctx,
        "validated_aroi_domains": relay_set.validated_aroi_domains if hasattr(relay_set, 'validated_aroi_domains') else set(),
        "base_url": relay_set.base_url,
    }
    
    if template.name == "misc-families.html":
        family_stats = relay_set.json.get('family_statistics', {
            'centralization_percentage': '0.0',
            'largest_family_size': 0,
            'large_family_count': 0
        })
        template_vars.update(family_stats)
    elif template.name == "misc-authorities.html":
        # Reuse existing authority uptime data from consolidated processing
        authorities_data = get_directory_authorities_data(relay_set)
        # Set attributes as expected by template (template uses relays.X)
        relay_set.authorities_data = authorities_data['authorities_data']
        relay_set.authorities_summary = authorities_data['authorities_summary']
        relay_set.consensus_status = authorities_data.get('consensus_status')
        relay_set.latency_summary = authorities_data.get('latency_summary')
        relay_set.authority_alerts = authorities_data.get('authority_alerts')
        relay_set.collector_flag_thresholds = authorities_data.get('collector_flag_thresholds')
        relay_set.collector_fetched_at = authorities_data.get('collector_fetched_at')
        template_vars.update(authorities_data)
    
    template_render = template.render(**template_vars)
    output = os.path.join(relay_set.output_dir, path)
    os.makedirs(os.path.dirname(output), exist_ok=True)

    with open(output, "w", encoding="utf8") as html:
        html.write(template_render)

def get_directory_authorities_data(relay_set):
    """
    Prepare directory authorities data for template rendering.
    Reuses existing authority uptime calculations and z-score infrastructure.
    """
    from datetime import datetime, timezone
    
    # Filter authorities from existing relay data (no new processing)
    authorities = [relay for relay in relay_set.json["relays"] if 'Authority' in relay.get('flags', [])]
    
    # Sort authorities alphabetically by nickname (A at top, Z at bottom)
    authorities = sorted(authorities, key=lambda x: x.get('nickname', '').lower())
    
    # Get collector data for votes/bw authorities
    collector_data = getattr(relay_set, 'collector_consensus_data', None)
    collector_fetched_at = None
    if collector_data:
        collector_fetched_at = collector_data.get('fetched_at', '')
        votes = collector_data.get('votes', {})
        bw_authorities = set(collector_data.get('bw_authorities', []))
        
        # OPTIMIZATION: Build lookup maps ONCE instead of nested loops for each authority
        # This reduces O(A*V) to O(A+V) where A=authorities, V=votes
        votes_by_nickname = {}  # nickname.lower() -> (vote_data, relay_count)
        votes_by_fingerprint = {}  # fingerprint.upper() -> (vote_data, relay_count)
        votes_by_prefix = {}  # fingerprint[:8].upper() -> (vote_data, relay_count)
        
        for vote_key, vote_data in votes.items():
            relay_count = len(vote_data.get('relays', {})) if isinstance(vote_data, dict) else 0
            vote_tuple = (vote_data, relay_count)
            
            vote_key_upper = vote_key.upper()
            vote_key_lower = vote_key.lower()
            
            # Store by all possible lookup keys
            votes_by_nickname[vote_key_lower] = vote_tuple
            if len(vote_key) == 40:  # Full fingerprint
                votes_by_fingerprint[vote_key_upper] = vote_tuple
                votes_by_prefix[vote_key_upper[:8]] = vote_tuple
            elif len(vote_key) == 8:  # Prefix only
                votes_by_prefix[vote_key_upper] = vote_tuple
        
        # Same optimization for bw_authorities
        bw_auth_nicknames = {a.lower() for a in bw_authorities}
        bw_auth_fingerprints = {a.upper() for a in bw_authorities if len(a) == 40}
        bw_auth_prefixes = {a.upper()[:8] for a in bw_authorities if len(a) >= 8}
        
        for authority in authorities:
            auth_nickname = authority.get('nickname', '').lower()
            auth_fingerprint = authority.get('fingerprint', '').upper()
            auth_fp_prefix = auth_fingerprint[:8] if auth_fingerprint else ''
            
            # Check if this authority voted - O(1) lookups
            voted = False
            relay_count = 0
            vote_tuple = (
                votes_by_fingerprint.get(auth_fingerprint) or
                votes_by_prefix.get(auth_fp_prefix) or
                votes_by_nickname.get(auth_nickname)
            )
            if vote_tuple:
                voted = True
                relay_count = vote_tuple[1]
            
            # Check if this authority is a bandwidth authority - O(1) lookups
            is_bw = (
                auth_fingerprint in bw_auth_fingerprints or
                auth_fp_prefix in bw_auth_prefixes or
                auth_nickname in bw_auth_nicknames
            )
            
            authority['collector_data'] = {
                'voted': voted,
                'is_bw_authority': is_bw,
                'relay_count': relay_count,
            }
    
    # Perform latency checks on authorities
    latency_ok_count = 0
    latency_slow_count = 0
    latency_down_count = 0
    authority_alerts = []
    
    try:
        from .consensus import AuthorityMonitor
        
        # Build authority endpoint data from VOTING authorities only (those that voted in collector)
        # This ensures latency counts match voting authority counts
        authority_endpoints = []
        for auth in authorities:
            # Only include voting authorities in latency check
            if not auth.get('collector_data', {}).get('voted', False):
                continue
                
            # Extract address from or_addresses (Onionoo format)
            or_addresses = auth.get('or_addresses', [])
            address = or_addresses[0].split(':')[0] if or_addresses else ''
            
            # Extract dir_port from dir_address if available, otherwise default to 80
            dir_address = auth.get('dir_address', '')
            dir_port = dir_address.split(':')[-1] if ':' in dir_address else '80'
            
            if auth.get('nickname') and address:
                authority_endpoints.append({
                    'nickname': auth.get('nickname'),
                    'address': address,
                    'dir_port': dir_port,
                })
        
        # Pass discovered authorities to monitor (falls back to hardcoded if empty)
        monitor = AuthorityMonitor(timeout=2, authorities=authority_endpoints)
        latency_status = monitor.check_all_authorities()
        
        # Attach latency data to each authority
        for authority in authorities:
            auth_nickname = authority.get('nickname', '').lower()
            # Find matching latency data
            for name, status in latency_status.items():
                if name.lower() == auth_nickname:
                    authority['latency_ms'] = status.get('latency_ms')
                    authority['latency_online'] = status.get('online', False)
                    authority['latency_error'] = status.get('error')
                    authority['latency_checked_at'] = status.get('checked_at')
                    
                    # Count for summary
                    if status.get('online'):
                        if status.get('latency_ms') and status['latency_ms'] > 500:
                            latency_slow_count += 1
                        else:
                            latency_ok_count += 1
                    else:
                        latency_down_count += 1
                        authority_alerts.append(f"{authority.get('nickname', 'Unknown')} is not responding (latency check failed)")
                    break
    except Exception as e:
        # Latency check failed - continue without it
        pass
    
    # Calculate first_seen relative time for each authority
    for authority in authorities:
        first_seen = authority.get('first_seen', '')
        if first_seen:
            authority['first_seen_timestamp'] = first_seen
            authority['first_seen_relative'] = format_time_ago(first_seen)
        else:
            authority['first_seen_timestamp'] = 'Unknown'
            authority['first_seen_relative'] = 'Unknown'
    
    # Reuse existing consolidated uptime results (already computed)
    authority_network_stats = {}
    above_average_uptime = []
    below_average_uptime = []
    problem_uptime = []
    
    if hasattr(relay_set, '_consolidated_uptime_results'):
        network_flag_stats = relay_set._consolidated_uptime_results.get('network_flag_statistics', {})
        authority_network_stats = network_flag_stats.get('Authority', {})
        
        for authority in authorities:
            uptime_1month = authority.get('uptime_percentages', {}).get('1_month', 0.0)
            period_stats = authority_network_stats.get('1_month', {})
            
            if period_stats and period_stats.get('std_dev', 0) > 0 and uptime_1month > 0:
                mean = period_stats['mean']
                std_dev = period_stats['std_dev']
                authority['uptime_zscore'] = (uptime_1month - mean) / std_dev
                
                # Categorize authorities by uptime performance (reuse z-score calculation)
                if authority['uptime_zscore'] > 0.3:
                    above_average_uptime.append(authority)
                elif authority['uptime_zscore'] <= -2.0:
                    problem_uptime.append(authority)
                    authority_alerts.append(f"{authority.get('nickname', 'Unknown')} has significantly below average uptime (Z-score: {authority['uptime_zscore']:.1f})")
                else:
                    below_average_uptime.append(authority)
                
                # Add outlier classification using existing thresholds
                if uptime_1month <= period_stats.get('two_sigma_low', 0):
                    authority['uptime_outlier_status'] = 'low_outlier'
                elif uptime_1month >= period_stats.get('two_sigma_high', float('inf')):
                    authority['uptime_outlier_status'] = 'high_outlier'
                else:
                    authority['uptime_outlier_status'] = 'normal'
            else:
                authority['uptime_zscore'] = None
                authority['uptime_outlier_status'] = 'insufficient_data'
    else:
        # No uptime data available - ensure all authorities have required attributes
        for authority in authorities:
            authority['uptime_zscore'] = None
            authority['uptime_outlier_status'] = 'insufficient_data'
    
    # Build consensus status
    voted_count = sum(1 for a in authorities if a.get('collector_data', {}).get('voted', False))
    consensus_status = {
        'freshness': 'fresh' if voted_count >= 5 else ('stale' if voted_count >= 3 else 'unknown'),
        'voted_count': voted_count,
        'fetched_at': collector_fetched_at,
    }
    
    # Build latency summary
    latency_summary = {
        'ok_count': latency_ok_count,
        'slow_count': latency_slow_count,
        'down_count': latency_down_count,
    }
    
    # Get flag thresholds from collector data
    collector_flag_thresholds = getattr(relay_set, 'collector_flag_thresholds', None)
    if collector_flag_thresholds is None and collector_data:
        collector_flag_thresholds = collector_data.get('flag_thresholds', {})
    
    # Use voting authority count from collector (actual voters) rather than Onionoo authority flag count
    # This is more accurate since some authorities (like Serge) may have Authority flag but don't vote
    voting_authority_count = len(collector_flag_thresholds) if collector_flag_thresholds else len(authorities)
    
    return {
        'authorities_data': authorities,
        'authorities_summary': {
            'total_authorities': voting_authority_count,
            'total_with_authority_flag': len(authorities),  # Keep for reference
            'above_average_uptime': above_average_uptime,
            'below_average_uptime': below_average_uptime,
            'problem_uptime': problem_uptime
        },
        'authority_network_stats': authority_network_stats,
        'uptime_metadata': (getattr(relay_set, 'uptime_data', {}) or {}).get('relays_published', 'Unknown'),
        'consensus_status': consensus_status,
        'latency_summary': latency_summary,
        'authority_alerts': authority_alerts if authority_alerts else None,
        'collector_flag_thresholds': collector_flag_thresholds,
        'collector_fetched_at': collector_fetched_at,
    }



def get_detail_page_context(relay_set, category, value):
    """Generate page context with correct breadcrumb data for detail pages"""
    # Use centralized page context generation
    from .page_context import get_detail_page_context
    return get_detail_page_context(category, value)

def write_pages_by_key(relay_set, k):
    """Render and write sorted HTML relay listings to disk"""
    start_time = time.time()
    relay_set._log_progress(f"Starting {k} page generation...")
    
    template = ENV.get_template(k + ".html")
    output_path = os.path.join(relay_set.output_dir, k)

    the_prefixed = [
        "Dominican Republic", "Ivory Coast", "Marshall Islands",
        "Northern Marianas Islands", "Solomon Islands", "United Arab Emirates",
        "United Kingdom", "United States", "United States of America",
        "Vatican City", "Czech Republic", "Bahamas", "Gambia", "Netherlands",
        "Philippines", "Seychelles", "Sudan", "Ukraine",
    ]

    if os.path.exists(output_path):
        rmtree(output_path)
    os.makedirs(output_path)

    sorted_values = sorted(relay_set.json["sorted"][k].keys()) if k == "first_seen" else list(relay_set.json["sorted"][k].keys())
    
    # Use multiprocessing for large page sets on systems with fork()
    # Contact pages now use precomputed data so they can be parallelized too
    use_mp = (relay_set.mp_workers > 0 and len(sorted_values) >= 100 and 
              hasattr(mp, 'get_context'))
    
    if use_mp:
        write_pages_parallel(relay_set, k, sorted_values, template, output_path, the_prefixed, start_time)
        return
    
    page_count = render_time = io_time = 0
    
    for v in sorted_values:
        # Sanitize the value to prevent directory traversal attacks
        v = v.replace("..", "").replace("/", "_")
        i = relay_set.json["sorted"][k][v]
        members = []

        for m_relay in i["relays"]:
            members.append(relay_set.json["relays"][m_relay])
        if k == "flag":
            dir_path = os.path.join(output_path, v.lower())
        else:
            dir_path = os.path.join(output_path, v)

        os.makedirs(dir_path, exist_ok=True)
        # relay_subset passed directly to template for thread safety (no shared state)
        
        bandwidth_unit = relay_set.bandwidth_formatter.determine_unit(i["bandwidth"])
        # Format all bandwidth values using the same unit
        bandwidth = relay_set.bandwidth_formatter.format_bandwidth_with_unit(i["bandwidth"], bandwidth_unit)
        guard_bandwidth = relay_set.bandwidth_formatter.format_bandwidth_with_unit(i["guard_bandwidth"], bandwidth_unit)
        middle_bandwidth = relay_set.bandwidth_formatter.format_bandwidth_with_unit(i["middle_bandwidth"], bandwidth_unit)
        exit_bandwidth = relay_set.bandwidth_formatter.format_bandwidth_with_unit(i["exit_bandwidth"], bandwidth_unit)
        
        # Calculate network position using DRY helper
        network_position = _compute_network_position_safe(
            i["guard_count"], i["middle_count"], i["exit_count"], len(members))
        network_position_display = network_position.get('formatted_string', 'unknown')
        
        # Generate page context with correct breadcrumb data
        page_ctx = get_detail_page_context(relay_set, k, v)
        
        # Generate contact rankings for AROI leaderboards (only for contact pages)
        contact_rankings = []
        operator_reliability = None
        contact_display_data = None
        primary_country_data = None
        contact_validation_status = None
        aroi_validation_timestamp = None
        if k == "contact":
            contact_rankings = relay_set._generate_contact_rankings(v)
            # Calculate operator reliability statistics
            operator_reliability = relay_set._calculate_operator_reliability(v, members)
            # Pre-compute all contact-specific display data
            contact_display_data = relay_set._compute_contact_display_data(
                i, bandwidth_unit, operator_reliability, v, members
            )
            # Store contact_display_data in the contact structure for relay pages to access
            i['contact_display_data'] = contact_display_data
            # Get primary country data for this contact
            primary_country_data = i.get("primary_country_data")
        
        # Add family-specific data for family templates (used by detail_summary macro)
        family_aroi_domain = None
        family_contact = None
        family_contact_md5 = None
        if k == "family":
            family_aroi_domain = i.get("aroi_domain", "")
            family_contact = i.get("contact", "")
            family_contact_md5 = i.get("contact_md5", "")
        
        # AROI validation status for contact and family pages (DRY - shared logic)
        if k in ("contact", "family"):
            contact_validation_status = (i.get("aroi_validation_full") or 
                                         i.get("contact_validation_status") or 
                                         relay_set._get_contact_validation_status(members))
            aroi_validation_timestamp = relay_set._aroi_validation_timestamp
        
        # Check if this contact has a validated AROI domain for vanity URL display
        is_validated_aroi = False
        if k == "contact" and members and hasattr(relay_set, 'validated_aroi_domains'):
            aroi_domain = members[0].get("aroi_domain")
            is_validated_aroi = aroi_domain and aroi_domain != "none" and aroi_domain in relay_set.validated_aroi_domains
        
        # Time the template rendering
        render_start = time.time()
        rendered = template.render(
            relays=relay_set,
            relay_subset=members,  # Pass directly for thread safety
            bandwidth=bandwidth,
            bandwidth_unit=bandwidth_unit,
            guard_bandwidth=guard_bandwidth,
            middle_bandwidth=middle_bandwidth,
            exit_bandwidth=exit_bandwidth,
            consensus_weight_fraction=i["consensus_weight_fraction"],
            guard_consensus_weight_fraction=i["guard_consensus_weight_fraction"],
            middle_consensus_weight_fraction=i["middle_consensus_weight_fraction"],
            exit_consensus_weight_fraction=i["exit_consensus_weight_fraction"],
            exit_count=i["exit_count"],
            guard_count=i["guard_count"],
            middle_count=i["middle_count"],
            network_position=network_position,
            is_index=False,
            page_ctx=page_ctx,
            key=k,
            value=v,
            flag=v if k == "flag" else None,  # For flag.html template
            sp_countries=the_prefixed,
            contact_rankings=contact_rankings,  # AROI leaderboard rankings for this contact
            operator_reliability=operator_reliability,  # Operator reliability statistics for contact pages
            contact_display_data=contact_display_data,  # Pre-computed contact-specific display data
            primary_country_data=primary_country_data,  # Primary country data for contact pages
            contact_validation_status=contact_validation_status,  # AROI validation status for Phase 2
            aroi_validation_timestamp=aroi_validation_timestamp,  # AROI validation data timestamp
            # Family-specific data for detail_summary macro in family templates
            family_aroi_domain=family_aroi_domain,  # AROI domain for family pages
            family_contact=family_contact,  # Contact string for family pages
            family_contact_md5=family_contact_md5,  # Contact MD5 hash for family pages
            # Template optimizations - pre-computed values to avoid expensive Jinja2 operations for all page types
            consensus_weight_percentage=f"{i['consensus_weight_fraction'] * 100:.2f}%",
            guard_consensus_weight_percentage=f"{i['guard_consensus_weight_fraction'] * 100:.2f}%",
            middle_consensus_weight_percentage=f"{i['middle_consensus_weight_fraction'] * 100:.2f}%",
            exit_consensus_weight_percentage=f"{i['exit_consensus_weight_fraction'] * 100:.2f}%",
            guard_relay_text="guard relay" if i["guard_count"] == 1 else "guard relays",
            middle_relay_text="middle relay" if i["middle_count"] == 1 else "middle relays",
            exit_relay_text="exit relay" if i["exit_count"] == 1 else "exit relays",
            has_guard=i["guard_count"] > 0,
            has_middle=i["middle_count"] > 0,
            has_exit=i["exit_count"] > 0,
            has_typed_relays=i["guard_count"] > 0 or i["middle_count"] > 0 or i["exit_count"] > 0,
            # Unique AROI and contact data for AS detail pages
            unique_aroi_list=i.get("unique_aroi_list", []),
            unique_contact_list=i.get("unique_contact_list", []),
            unique_aroi_count=i.get("unique_aroi_count", 0),
            unique_contact_count=i.get("unique_contact_count", 0),
            unique_aroi_contact_html=i.get("unique_aroi_contact_html", ""),
            aroi_to_contact_map=i.get("aroi_to_contact_map", {}),
            # Validation status for vanity URL display
            is_validated_aroi=is_validated_aroi,
            # Pass validated domains set to all templates for vanity URL links
            validated_aroi_domains=relay_set.validated_aroi_domains if hasattr(relay_set, 'validated_aroi_domains') else set(),
            # Base URL for vanity URLs
            base_url=relay_set.base_url
        )
        render_time += time.time() - render_start

        # Time the file I/O
        io_start = time.time()
        html_path = os.path.join(dir_path, "index.html")
        with open(html_path, "w", encoding="utf8") as html:
            html.write(rendered)
        io_time += time.time() - io_start
        
        # Create vanity URL for validated AROI domains (copy and adjust paths)
        # Only create if base_url is configured - Place at root level (e.g., /domain/ instead of /contact/domain/)
        if relay_set.base_url and k == "contact" and members and hasattr(relay_set, 'validated_aroi_domains'):
            aroi_domain = members[0].get("aroi_domain")
            if aroi_domain and aroi_domain != "none" and aroi_domain in relay_set.validated_aroi_domains:
                # Lowercase domain for case-insensitive URLs
                safe_domain = aroi_domain.lower().replace("..", "").replace("/", "_")
                # Use parent directory (root level) instead of output_path (contact subdirectory)
                vanity_dir = os.path.join(os.path.dirname(output_path), safe_domain)
                try:
                    os.makedirs(vanity_dir, exist_ok=True)
                    # Read the HTML and adjust paths for different directory depth
                    # Contact pages are depth 2 (../../) but vanity URLs are depth 1 (../)
                    with open(html_path, 'r', encoding='utf8') as f:
                        html_content = f.read()
                    # Adjust path prefix from depth 2 to depth 1
                    adjusted_html = html_content.replace('href="../../', 'href="../').replace('src="../../', 'src="../')
                    # Write adjusted HTML to vanity URL directory
                    with open(os.path.join(vanity_dir, "index.html"), 'w', encoding='utf8') as f:
                        f.write(adjusted_html)
                except OSError:
                    pass  # Silent fail - don't break generation for vanity URL issues
        
        page_count += 1
        
        # Print progress for large page sets
        if page_count % 1000 == 0:
            relay_set._log_progress(f"Processed {page_count} {k} pages...")

    end_time = time.time()
    total_time = end_time - start_time
    
    # Log completion with progress increment for granular tracking
    relay_set.progress_logger.log(f"{k} page generation complete - Generated {page_count} pages in {total_time:.2f}s")
    if relay_set.progress:
        # Additional detailed stats (not in standard format, but supporting info)
        print(f"    🎨 Template render time: {render_time:.2f}s ({render_time/total_time*100:.1f}%)")
        print(f"    💾 File I/O time: {io_time:.2f}s ({io_time/total_time*100:.1f}%)")
        if page_count > 0:
            print(f"    ⚡ Average per page: {total_time/page_count*1000:.1f}ms")
        print("---")

def build_template_args(relay_set, k, v, i, the_prefixed, validated_aroi_domains):
    """Build template arguments for all page types (used by both sequential and parallel paths)."""
    members = [relay_set.json["relays"][idx] for idx in i["relays"]]
    bw = relay_set.bandwidth_formatter
    bw_unit = bw.determine_unit(i["bandwidth"])
    
    # Use precomputed network_position if available, otherwise calculate using DRY helper
    network_position = i.get("network_position") or _compute_network_position_safe(
        i["guard_count"], i["middle_count"], i["exit_count"], len(members))
    
    # Default values for all page types
    contact_rankings = []
    operator_reliability = None
    contact_display_data = None
    contact_validation_status = None
    aroi_validation_timestamp = None
    is_validated_aroi = False
    primary_country_data = None
    
    # For contact pages, use precomputed data stored directly on contact_data
    if k == "contact":
        contact_rankings = i.get("contact_rankings", [])
        operator_reliability = i.get("operator_reliability")
        contact_display_data = i.get("contact_display_data")
        is_validated_aroi = i.get("is_validated_aroi", False)
        primary_country_data = i.get("primary_country_data")
    
    # AROI validation status for contact and family pages (DRY - shared logic)
    # Uses precomputed data if available (both contact and family pages precompute this)
    if k in ("contact", "family"):
        contact_validation_status = (i.get("aroi_validation_full") or 
                                     i.get("contact_validation_status"))
        # Only compute on-the-fly if no precomputed data exists (fallback)
        if contact_validation_status is None:
            contact_validation_status = relay_set._get_contact_validation_status(members)
        aroi_validation_timestamp = relay_set._aroi_validation_timestamp
    
    return {
        'relay_subset': members,
        'bandwidth': bw.format_bandwidth_with_unit(i["bandwidth"], bw_unit),
        'bandwidth_unit': bw_unit,
        'guard_bandwidth': bw.format_bandwidth_with_unit(i["guard_bandwidth"], bw_unit),
        'middle_bandwidth': bw.format_bandwidth_with_unit(i["middle_bandwidth"], bw_unit),
        'exit_bandwidth': bw.format_bandwidth_with_unit(i["exit_bandwidth"], bw_unit),
        'consensus_weight_fraction': i["consensus_weight_fraction"],
        'guard_consensus_weight_fraction': i["guard_consensus_weight_fraction"],
        'middle_consensus_weight_fraction': i["middle_consensus_weight_fraction"],
        'exit_consensus_weight_fraction': i["exit_consensus_weight_fraction"],
        'exit_count': i["exit_count"], 'guard_count': i["guard_count"], 'middle_count': i["middle_count"],
        'network_position': network_position,
        'is_index': False,
        'page_ctx': get_detail_page_context(relay_set, k, v),
        'key': k, 'value': v,
        'flag': v if k == "flag" else None,
        'sp_countries': the_prefixed,
        'contact_rankings': contact_rankings,
        'operator_reliability': operator_reliability,
        'contact_display_data': contact_display_data,
        'primary_country_data': primary_country_data,
        'contact_validation_status': contact_validation_status,
        'aroi_validation_timestamp': aroi_validation_timestamp,
        # Family-specific data (extracted once, not per-field)
        **({'family_aroi_domain': i.get("aroi_domain", ""),
            'family_contact': i.get("contact", ""),
            'family_contact_md5': i.get("contact_md5", "")} if k == "family" else 
           {'family_aroi_domain': None, 'family_contact': None, 'family_contact_md5': None}),
        'consensus_weight_percentage': f"{i['consensus_weight_fraction'] * 100:.2f}%",
        'guard_consensus_weight_percentage': f"{i['guard_consensus_weight_fraction'] * 100:.2f}%",
        'middle_consensus_weight_percentage': f"{i['middle_consensus_weight_fraction'] * 100:.2f}%",
        'exit_consensus_weight_percentage': f"{i['exit_consensus_weight_fraction'] * 100:.2f}%",
        'guard_relay_text': "guard relay" if i["guard_count"] == 1 else "guard relays",
        'middle_relay_text': "middle relay" if i["middle_count"] == 1 else "middle relays",
        'exit_relay_text': "exit relay" if i["exit_count"] == 1 else "exit relays",
        'has_guard': i["guard_count"] > 0, 'has_middle': i["middle_count"] > 0, 'has_exit': i["exit_count"] > 0,
        'has_typed_relays': i["guard_count"] > 0 or i["middle_count"] > 0 or i["exit_count"] > 0,
        'unique_aroi_list': i.get("unique_aroi_list", []),
        'unique_contact_list': i.get("unique_contact_list", []),
        'unique_aroi_count': i.get("unique_aroi_count", 0),
        'unique_contact_count': i.get("unique_contact_count", 0),
        'unique_aroi_contact_html': i.get("unique_aroi_contact_html", ""),
        'aroi_to_contact_map': i.get("aroi_to_contact_map", {}),
        'is_validated_aroi': is_validated_aroi,
        'validated_aroi_domains': validated_aroi_domains,
        'base_url': relay_set.base_url,
    }

def write_pages_parallel(relay_set, k, sorted_values, template, output_path, the_prefixed, start_time):
    """Parallel page generation using fork() for significant speedup on large page sets.
    
    OPTIMIZED: Now passes only (html_path, value) to workers instead of full template args.
    Workers build template args from forked memory, avoiding ~300KB/page IPC serialization.
    This dramatically improves performance for large page sets like families (105+ members avg).
    """
    validated_aroi_domains = getattr(relay_set, 'validated_aroi_domains', set())
    page_args = []
    vanity_url_tasks = []  # Collect vanity URL tasks for post-processing
    
    for v in sorted_values:
        v = v.replace("..", "").replace("/", "_")
        i = relay_set.json["sorted"][k][v]
        dir_path = os.path.join(output_path, v.lower() if k == "flag" else v)
        os.makedirs(dir_path, exist_ok=True)
        html_path = os.path.join(dir_path, "index.html")
        # OPTIMIZED: Pass only (html_path, value) - workers build template args from forked memory
        page_args.append((html_path, v))
        
        # Collect vanity URL tasks for contact pages (to be processed after parallel generation)
        # Uses precomputed aroi_domain to avoid re-fetching members
        if k == "contact" and relay_set.base_url and i.get("is_validated_aroi"):
            aroi_domain = i.get("aroi_domain")
            if aroi_domain and aroi_domain != "none":
                vanity_url_tasks.append((html_path, aroi_domain, output_path))
    
    pool = None
    try:
        ctx = mp.get_context('fork')
        # Initialize workers with page_type and shared data for building template args
        pool = ctx.Pool(relay_set.mp_workers, _init_mp_worker, 
                       (relay_set, template, k, the_prefixed, validated_aroi_domains))
        pool.map(_render_page_mp, page_args)
        pool.close()
        pool.join()
        
        # Post-process vanity URLs for contact pages (after parallel generation)
        if vanity_url_tasks:
            for html_path, aroi_domain, contact_output_path in vanity_url_tasks:
                try:
                    safe_domain = aroi_domain.lower().replace("..", "").replace("/", "_")
                    vanity_dir = os.path.join(os.path.dirname(contact_output_path), safe_domain)
                    os.makedirs(vanity_dir, exist_ok=True)
                    with open(html_path, 'r', encoding='utf8') as f:
                        html_content = f.read()
                    adjusted_html = html_content.replace('href="../../', 'href="../').replace('src="../../', 'src="../')
                    with open(os.path.join(vanity_dir, "index.html"), 'w', encoding='utf8') as f:
                        f.write(adjusted_html)
                except OSError:
                    pass  # Silent fail for vanity URL issues
        
        total_time = time.time() - start_time
        relay_set.progress_logger.log(f"{k} page generation complete - Generated {len(page_args)} pages in {total_time:.2f}s")
        if relay_set.progress:
            print(f"    🚀 Parallel: {relay_set.mp_workers} workers, {total_time/len(page_args)*1000:.1f}ms/page avg")
    except Exception as e:
        # Ensure pool is properly terminated before fallback
        if pool is not None:
            try:
                pool.terminate()
                pool.join()
            except Exception:
                pass  # Ignore cleanup errors
        
        relay_set._log_progress(f"Multiprocessing failed ({e}), falling back to sequential...")
        relay_set.mp_workers = 0
        
        # Clean up partial output before sequential fallback (with retry for lingering file handles)
        for retry in range(3):
            try:
                if os.path.exists(output_path):
                    rmtree(output_path)
                os.makedirs(output_path)
                break
            except OSError:
                if retry < 2:
                    time.sleep(0.1)  # Brief pause before retry
        
        write_pages_by_key(relay_set, k)

def write_relay_info(relay_set):
    """
    Render and write per-relay HTML info documents to disk
    """
    relay_list = relay_set.json["relays"]
    template = ENV.get_template("relay-info.html")
    output_path = os.path.join(relay_set.output_dir, "relay")

    if os.path.exists(output_path):
        rmtree(output_path)
    os.makedirs(output_path)

    # Optimization: Move imports and setup outside the loop (10k+ iterations)
    from .page_context import StandardTemplateContexts
    standard_contexts = StandardTemplateContexts(relay_set)
    
    # Optimization: Pre-fetch collections for fast lookup
    # Safely get contact map - avoiding 3-level .get() in loop
    contact_map = relay_set.json.get("sorted", {}).get("contact", {})
    
    # Optimization: Cache validated domains set
    validated_aroi_domains = getattr(relay_set, 'validated_aroi_domains', set())

    for relay in relay_list:
        if not relay["fingerprint"].isalnum():
            continue
        
        # Optimization: Fast direct lookup for contact data
        contact_hash = relay.get('contact_md5')
        contact_display_data = {}
        contact_validation_status = None
        
        if contact_hash and contact_hash in contact_map:
            contact_data = contact_map[contact_hash]
            contact_display_data = contact_data.get('contact_display_data', {})
            contact_validation_status = contact_data.get('contact_validation_status')
        
        full_context = standard_contexts.get_relay_page_context(relay, contact_display_data)
        page_ctx = full_context
        
        rendered = template.render(
            relay=relay, page_ctx=page_ctx, relays=relay_set, contact_display_data=contact_display_data,
            contact_validation_status=contact_validation_status,
            validated_aroi_domains=validated_aroi_domains,
            base_url=relay_set.base_url
        )
        
        # Create directory structure: relay/FINGERPRINT/index.html (depth 2)
        relay_dir = os.path.join(output_path, relay["fingerprint"])
        os.makedirs(relay_dir, exist_ok=True)
        
        with open(
            os.path.join(relay_dir, "index.html"),
            "w",
            encoding="utf8",
        ) as html:
            html.write(rendered)


