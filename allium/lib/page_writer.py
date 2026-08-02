"""
File: page_writer.py

HTML page rendering and file I/O for allium static site generation.
Contains Jinja2 environment setup, multiprocessing workers, and all
page writing functions.
Extracted from relays.py for better modularity.
"""

import logging
import multiprocessing as mp
import os
import time
from shutil import rmtree

from jinja2 import Environment, FileSystemLoader, FileSystemBytecodeCache

from .contact_sorting import (
    CONTACT_SORT_FILE_MAP,
    CONTACT_SORT_MODES,
    CONTACT_DEFAULT_SORT_MODE,
    adjust_vanity_paths as _adjust_vanity_paths,
    contact_sort_links as _contact_sort_links,
    build_contact_variant_args as _build_contact_variant_args,
    contact_has_ipv6 as _contact_has_ipv6,
    contact_relay_count as _contact_relay_count,
)
from .bandwidth_formatter import (
    format_bandwidth_with_unit,
    determine_unit_filter,
    format_bandwidth_filter,
    format_data_volume_with_unit,
)
from .aroi_validation import get_contact_validation_status
from .intelligence_engine import IntelligenceEngine
from .ip_utils import safe_parse_ip_address
from .operator_analysis import (
    calculate_operator_reliability,
    compute_contact_display_data,
    generate_contact_rankings,
)
from .stability_utils import compute_group_overload_summary
from .time_utils import format_time_ago, format_timestamp, format_timestamp_ago

ABS_PATH = os.path.dirname(os.path.abspath(__file__))

logger = logging.getLogger(__name__)


def _sanitize_path_component(value: str) -> str:
    """Sanitize a string for safe use as a filesystem path component.
    
    Guards against directory traversal, path injection, and OS-specific edge cases:
    - Strips Windows drive prefixes (e.g. "C:") and backslashes
    - Removes control characters and null bytes
    - Replaces characters outside a safe whitelist with underscores
    - Trims leading/trailing dots and underscores to avoid "." / ".." results
    - Returns "_" if the result is empty or still equals "." / ".."
    - Appends a short hash suffix when normalization changes the value, preventing
      distinct raw inputs (e.g. "A B", "A/B", "A_B") from colliding on disk
    - Truncates to 255 characters (common filesystem limit)
    """
    import hashlib
    import re
    raw_value = str(value)
    # Strip Windows drive letter prefix (e.g. "C:", "D:")
    if len(value) >= 2 and value[1] == ':' and value[0].isalpha():
        value = value[2:]
    # Remove backslashes, forward slashes, null bytes, and control characters
    value = value.replace('\\', '_').replace('/', '_').replace('\x00', '')
    value = re.sub(r'[\x00-\x1f\x7f]', '', value)
    # Remove traversal sequences
    value = value.replace('..', '')
    # Replace any character not in safe whitelist (letters, digits, hyphen, underscore, dot)
    value = re.sub(r'[^A-Za-z0-9_.\-]', '_', value)
    # Trim leading/trailing dots and underscores
    value = value.strip('._')
    # Keep room for deterministic suffix when normalization changes value
    value = value[:240]
    # Final safety: reject empty or traversal-like results
    if not value or value in ('.', '..'):
        value = '_'
    # Prevent collisions when different raw inputs normalize to the same component
    if value != raw_value:
        suffix = hashlib.sha1(raw_value.encode("utf-8")).hexdigest()[:10]
        value = f"{value}-{suffix}"
    return value[:255]



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
ENV.filters['format_data_volume'] = format_data_volume_with_unit
ENV.filters['format_time_ago'] = format_time_ago
ENV.filters['split'] = lambda s, sep='/': s.split(sep) if s else []

# Overload section filters for millisecond timestamps (Onionoo overload fields)
ENV.filters['format_timestamp'] = format_timestamp
ENV.filters['format_timestamp_ago'] = format_timestamp_ago

from datetime import datetime as _dt, timezone as _tz

def _format_unix_timestamp(ts):
    if ts is None or ts == '':
        return ''
    try:
        return _dt.fromtimestamp(float(ts), tz=_tz.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    except (ValueError, TypeError, OSError):
        return str(ts)

def _ordinal(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return str(n) if n is not None else ''
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"

ENV.filters['format_unix_timestamp'] = _format_unix_timestamp
ENV.filters['ordinal'] = _ordinal

# ============================================================================
# HELPER: Partition effective_family by family-cert status
# ============================================================================

def _partition_family_lists(relay, family_cert_fps, fp_to_family_key, family_key_to_fps):
    """Partition effective_family by family-cert status for relay-info template.

    Happy Families (family-cert) relationships are always mutual — no alleged/indirect
    possible. Only effective_family is partitioned; alleged/indirect stay as-is (MyFamily only).

    Uses the same verified-key data as _set_family_support_types() for consistency:
      - family_cert_fps = set of fingerprints with verified extracted Ed25519 key
      - fp_to_family_key = map from fingerprint to family signing key
      - family_key_to_fps = map from family key to list of member fingerprints

    Sets 2 underscore-prefixed keys on relay dict (follows _flags_html convention):
      _hf_effective  — all relays sharing same family-cert key
      _mf_effective  — effective family members WITHOUT verified family-cert
    """
    fp = relay.get('fingerprint', '').upper()
    effective = relay.get('effective_family') or []

    family_key = fp_to_family_key.get(fp)
    if family_key:
        relay['_hf_effective'] = family_key_to_fps.get(family_key, [])
    else:
        relay['_hf_effective'] = []

    relay['_mf_effective'] = [f for f in effective if f.upper() not in family_cert_fps]


def _get_family_support_counts(k, contact_display_data, i):
    """Extract family_support_counts from precomputed data for contact/family pages.

    DRY helper used by both sequential (write_pages_by_key) and parallel (build_template_args) paths.
    """
    if k == "contact" and contact_display_data:
        return contact_display_data.get("operator_intelligence", {}).get("family_support_counts", {})
    elif k == "family":
        return i.get("family_support_counts", {})
    return {}


def _get_exit_dns_health_summary(k, i, members):
    """Get exit DNS health summary — precomputed for contacts/families, on-the-fly for others.

    DRY helper used by both sequential (write_pages_by_key) and parallel (build_template_args) paths.
    OPTIMIZATION: Uses i["exit_count"] fast bail-out to skip groups with no exit relays.
    """
    from .exit_dns_health import get_operator_exit_dns_health_summary

    # For contact and family pages, use precomputed data
    if k in ("contact", "family"):
        return i.get("exit_dns_health_summary")

    # For all other page types, compute on-the-fly with exit_count bail-out
    return get_operator_exit_dns_health_summary(members, exit_count=i.get("exit_count", 0))


# Multiprocessing globals (initialized via fork for copy-on-write memory sharing)
_mp_relay_set = None
_mp_template = None
_mp_page_type = None
_mp_the_prefixed = None
_mp_validated_aroi_domains = None
_mp_output_root = None


def _init_mp_worker(relay_set, template, page_type=None, the_prefixed=None, validated_aroi_domains=None, output_root=None):
    """Initialize worker with shared data via fork"""
    global _mp_relay_set, _mp_template, _mp_page_type, _mp_the_prefixed, _mp_validated_aroi_domains, _mp_output_root
    _mp_relay_set = relay_set
    _mp_template = template
    _mp_page_type = page_type
    _mp_the_prefixed = the_prefixed if the_prefixed is not None else []
    _mp_validated_aroi_domains = validated_aroi_domains if validated_aroi_domains is not None else set()
    _mp_output_root = output_root


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
    template_args = build_template_args(
        _mp_relay_set, _mp_page_type, value, page_data, _mp_the_prefixed, _mp_validated_aroi_domains
    )
    
    # Render and write
    rendered = _mp_template.render(relays=_mp_relay_set, **template_args)
    with open(html_path, "w", encoding="utf8") as f:
        f.write(rendered)
    return True



# Contact sorting constants and helpers are in contact_sorting.py.
# Rendering orchestration functions below use them via imports at the top.


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


def _contact_validation_status(relay_set, members):
    """AROI validation status for a group's relays (Phase 2).

    DRY helper: passes the relay_set's raw validation data plus its
    pre-built validation_map so the map is not rebuilt for each of the
    3,000+ contact/family groups.
    """
    return get_contact_validation_status(
        members,
        getattr(relay_set, 'aroi_validation_data', None),
        getattr(relay_set, 'validation_map', None))


# Precomputation worker globals (for contact page data parallelization)
_precompute_relay_set = None


def _init_precompute_worker(relay_set):
    """Initialize precompute worker with shared relay_set via fork"""
    global _precompute_relay_set
    _precompute_relay_set = relay_set


def _compute_contact_predata(relay_set, contact_hash, aroi_validation_timestamp, validated_aroi_domains):
    """Core contact precomputation logic shared by sequential and parallel paths.
    
    DRY: Extracted from both _precompute_single_contact (relays.py) and
    _precompute_contact_worker (page_writer.py) which contained identical logic.
    
    Args:
        relay_set: The Relays object (self or forked global)
        contact_hash: The contact hash to precompute for
        aroi_validation_timestamp: Cached validation timestamp
        validated_aroi_domains: Set of validated AROI domains
        
    Returns:
        dict of precomputed values or None if no members
    """
    contact_data = relay_set.json["sorted"]["contact"][contact_hash]
    
    members = [relay_set.json["relays"][idx] for idx in contact_data.get("relays", [])]
    if not members:
        return None
    
    bandwidth_unit = relay_set.bandwidth_formatter.determine_unit(contact_data.get("bandwidth", 0))
    
    contact_rankings = generate_contact_rankings(contact_hash, relay_set)
    operator_reliability = calculate_operator_reliability(contact_hash, members, relay_set)
    contact_display_data = compute_contact_display_data(
        contact_data, bandwidth_unit, operator_reliability, contact_hash, members, relay_set)

    if "aroi_validation_full" in contact_data:
        contact_validation_status = contact_data["aroi_validation_full"]
    else:
        contact_validation_status = _contact_validation_status(relay_set, members)
    
    aroi_domain = members[0].get("aroi_domain") if members else None
    is_validated_aroi = (aroi_domain and aroi_domain != "none" and
                        aroi_domain in validated_aroi_domains)

    # Exit DNS health summary — uses exit_count bail-out, reads pre-attached relay fields
    from .exit_dns_health import get_operator_exit_dns_health_summary
    exit_dns_health_summary = get_operator_exit_dns_health_summary(
        members, exit_count=contact_data.get("exit_count", 0))

    return {
        "contact_rankings": contact_rankings,
        "operator_reliability": operator_reliability,
        "contact_display_data": contact_display_data,
        "contact_validation_status": contact_validation_status,
        "aroi_validation_timestamp": aroi_validation_timestamp,
        "is_validated_aroi": is_validated_aroi,
        "precomputed_bandwidth_unit": bandwidth_unit,
        "aroi_domain": aroi_domain,
        "exit_dns_health_summary": exit_dns_health_summary,
    }


def _precompute_contact_worker(args):
    """Precompute data for a single contact in worker process.
    
    Thin wrapper around _compute_contact_predata using forked global relay_set.
    """
    contact_hash, aroi_validation_timestamp, validated_aroi_domains = args
    
    try:
        result = _compute_contact_predata(
            _precompute_relay_set, contact_hash, aroi_validation_timestamp, validated_aroi_domains)
        return (contact_hash, result)
    except Exception:
        return (contact_hash, None)


def _compute_family_predata(relay_set, family_hash):
    """Core family precomputation logic shared by sequential and parallel paths.
    
    DRY: Extracted from both _precompute_single_family (relays.py) and
    _precompute_family_worker (page_writer.py) which contained identical logic.
    
    Args:
        relay_set: The Relays object (self or forked global)
        family_hash: The family hash to precompute for
        
    Returns:
        dict of precomputed values or None if no members
    """
    family_data = relay_set.json["sorted"]["family"][family_hash]
    
    members = [relay_set.json["relays"][idx] for idx in family_data.get("relays", [])]
    if not members:
        return None
    
    contact_validation_status = (family_data.get("aroi_validation_full") or
                                 _contact_validation_status(relay_set, members))
    
    network_position = _compute_network_position_safe(
        family_data["guard_count"], family_data["middle_count"],
        family_data["exit_count"], len(members))
    
    # Family support type counts + Exit DNS health counts
    # Piggyback DNS health counting on same loop (avoid second iteration)
    family_support_counts = {'both': 0, 'happy_families': 0, 'my_family': 0, 'none': 0}
    exit_dns_healthy = 0
    exit_dns_failing = 0
    exit_dns_untested = 0
    exit_dns_total = 0
    for relay in members:
        fst = relay.get('family_support_type', 'none')
        family_support_counts[fst] = family_support_counts.get(fst, 0) + 1
        edh = relay.get('exit_dns_health_status')
        if edh is not None:
            exit_dns_total += 1
            if edh == 'success':
                exit_dns_healthy += 1
            elif edh == 'fail':
                exit_dns_failing += 1
            else:
                exit_dns_untested += 1

    from .exit_dns_health import _build_dns_summary_dict
    exit_dns_health_summary = (
        _build_dns_summary_dict(exit_dns_total, exit_dns_healthy, exit_dns_failing, exit_dns_untested)
        if exit_dns_total > 0 else None
    )

    return {
        "contact_validation_status": contact_validation_status,
        "network_position": network_position,
        "family_support_counts": family_support_counts,
        "exit_dns_health_summary": exit_dns_health_summary,
    }


def _precompute_family_worker(args):
    """Precompute data for a single family in worker process.
    
    Thin wrapper around _compute_family_predata using forked global relay_set.
    """
    family_hash, = args
    
    try:
        result = _compute_family_predata(_precompute_relay_set, family_hash)
        return (family_hash, result)
    except Exception:
        return (family_hash, None)




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
                validation_status = _contact_validation_status(relay_set, members)
                contact_data["aroi_validation_status"] = validation_status["validation_status"]
                # Store full validation status for operator pages to reuse
                contact_data["aroi_validation_full"] = validation_status
                # B1.6: surface peer-issue counts + v3 tier on the listing
                # row so misc-contacts.html can render \U0001f6a8 / \u23f3 / \U0001f3c6
                # markers without re-loading the full validation_status.
                _summary = validation_status.get('validation_summary', {}) or {}
                contact_data['aroi_security_count'] = _summary.get('security_incident_count', 0)
                contact_data['aroi_pending_count'] = _summary.get('pending_onionoo_count', 0)
                contact_data['aroi_v3_tier'] = _summary.get('v3_tier', 'none')
                contact_data['aroi_is_v3_adopter'] = _summary.get('is_v3_adopter', False)
                contact_data['aroi_v3_pct'] = _summary.get('v3_pct_of_total', 0.0)
    
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

        # B5.2: precompute v3 tier per family so misc-families.html can
        # render a tier badge inline. Compute once here (vs. doing it
        # in the template loop) — ~6,300 families × 1 tier classifier
        # call beats inline Jinja arithmetic, and matches the
        # precompute pattern already used for misc-contacts.
        from .aroi_validation import classify_v3_tier
        all_relays_list = relay_set.json.get('relays', [])
        for fam_hash, fam_data in (relay_set.json.get('sorted', {})
                                                  .get('family', {}).items()):
            if 'aroi_v3_tier' in fam_data:
                continue  # already computed
            relay_idxs = fam_data.get('relays', [])
            total = len(relay_idxs)
            if total == 0:
                fam_data['aroi_v3_tier'] = 'none'
                fam_data['aroi_v3_pct'] = 0.0
                continue
            v3 = sum(1 for ix in relay_idxs
                     if ix < len(all_relays_list)
                     and all_relays_list[ix].get('aroi_version') == '3')
            fam_data['aroi_v3_tier'] = classify_v3_tier(v3, total)
            fam_data['aroi_v3_pct'] = (v3 / total * 100) if total else 0.0
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
        relay_set.consensus_method_info = authorities_data.get('consensus_method_info')
        template_vars.update(authorities_data)
    
    template_render = template.render(**template_vars)
    output = os.path.join(relay_set.output_dir, path)
    os.makedirs(os.path.dirname(output), exist_ok=True)

    with open(output, "w", encoding="utf8") as html:
        html.write(template_render)

def probe_authority_latency(relay_set):
    """TCP-probe voting directory authorities; returns the latency status map.

    Runs from the coordinator before page generation so rendering stays
    pure; get_directory_authorities_data consumes the attached result and
    only probes inline as a fallback (tests / direct calls).
    """
    from .consensus import AuthorityMonitor

    authorities = [r for r in relay_set.json.get("relays", [])
                   if 'Authority' in r.get('flags', [])]
    collector_data = getattr(relay_set, 'collector_consensus_data', None) or {}
    votes = collector_data.get('votes', {}) if isinstance(collector_data, dict) else {}
    vote_nicknames = {k.lower() for k in votes}
    vote_fingerprints = {k.upper() for k in votes if len(k) == 40}
    vote_prefixes = ({k.upper()[:8] for k in votes if len(k) == 40}
                     | {k.upper() for k in votes if len(k) == 8})

    # Build authority endpoint data from VOTING authorities only (those that
    # voted in collector) so latency counts match voting authority counts
    authority_endpoints = []
    for auth in authorities:
        auth_nickname = auth.get('nickname', '')
        auth_fp = auth.get('fingerprint', '').upper()
        voted = (auth_fp in vote_fingerprints
                 or (auth_fp and auth_fp[:8] in vote_prefixes)
                 or auth_nickname.lower() in vote_nicknames)
        if not voted:
            continue

        # Extract address from or_addresses (Onionoo format). Entries
        # can be bracketed IPv6 ('[2001:db8::1]:9001'); naive ':' splits
        # would yield garbage if an authority ever published IPv6 first.
        # Prefer the first IPv4 entry - the monitor probes over IPv4 -
        # falling back to a bracket-aware parse of the first entry.
        or_addresses = auth.get('or_addresses', [])
        address = ''
        for or_addr in or_addresses:
            parsed_ip, ip_version = safe_parse_ip_address(or_addr)
            if parsed_ip and ip_version == 4:
                address = parsed_ip
                break
        if not address and or_addresses:
            parsed_ip, _ipv = safe_parse_ip_address(or_addresses[0])
            address = parsed_ip or ''

        # Extract dir_port from dir_address if available, otherwise
        # default to 80 (rsplit stays correct for bracketed IPv6)
        dir_address = auth.get('dir_address', '')
        dir_port = dir_address.rsplit(':', 1)[-1] if ':' in dir_address else '80'

        if auth_nickname and address:
            authority_endpoints.append({
                'nickname': auth_nickname,
                'address': address,
                'dir_port': dir_port,
            })

    # Pass discovered authorities to monitor (falls back to hardcoded if empty)
    monitor = AuthorityMonitor(timeout=2, authorities=authority_endpoints)
    return monitor.check_all_authorities()


def get_directory_authorities_data(relay_set):
    """
    Prepare directory authorities data for template rendering.
    Reuses existing authority uptime calculations and z-score infrastructure.
    """
    
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
            
            # Get per-authority consensus methods from consensus_method_info
            auth_max_method = None
            if collector_data:
                cm_per_auth = collector_data.get('consensus_method_info', {}).get('per_authority', {})
                # Try matching by nickname (vote auth names are lowercase)
                auth_methods = cm_per_auth.get(auth_nickname)
                if auth_methods:
                    auth_max_method = max(auth_methods) if auth_methods else None
            
            authority['collector_data'] = {
                'voted': voted,
                'is_bw_authority': is_bw,
                'relay_count': relay_count,
                'max_consensus_method': auth_max_method,
            }
    
    # Perform latency checks on authorities
    latency_ok_count = 0
    latency_slow_count = 0
    latency_down_count = 0
    authority_alerts = []
    
    try:
        # Probing runs in the coordinator so page generation stays pure
        # rendering; probe inline only when nothing was attached
        # (tests / direct calls without the coordinator).
        latency_status = getattr(relay_set, 'authority_latency_status', None)
        if latency_status is None:
            latency_status = probe_authority_latency(relay_set)
        
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
    except Exception:
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
    
    # ------------------------------------------------------------------
    # Retain recently-removed authorities (as offline) for historical context.
    # A directory authority removed from the consensus eventually ages out of ALL
    # live data sources (Onionoo drops it ~1 week after its last consensus; CollecTor
    # 'recent/' keeps only ~3-4 days), so it would silently vanish from this page. We
    # merge in a SMALL hardcoded list of known-offline authorities, but ONLY those not
    # already present dynamically from Onionoo. If such an authority returns to
    # Onionoo, the live row wins (dedupe) and the page refreshes it automatically.
    #
    # Display-only: these entries are never counted as voters and never affect the
    # reachability/consensus denominators. Totals below use the DYNAMIC (pre-merge)
    # authority count so the hardcoded rows can't inflate any counts.
    # ------------------------------------------------------------------
    dynamic_authority_count = len(authorities)
    dynamic_fingerprints = {a.get('fingerprint', '').upper() for a in authorities}
    dynamic_nicknames = {a.get('nickname', '').lower() for a in authorities}
    try:
        from .consensus.collector_fetcher import get_known_offline_authorities
        known_offline = get_known_offline_authorities()
    except Exception as e:
        logger.warning(f"Failed to load known offline authorities ({e}), skipping offline-retention rows")
        known_offline = []
    for entry in known_offline:
        entry_fp = (entry.get('fingerprint') or '').upper()
        entry_nick = (entry.get('nickname') or '').lower()
        # Skip if already present dynamically (authority returned / never fully left)
        if (entry_fp and entry_fp in dynamic_fingerprints) or \
           (entry_nick and entry_nick in dynamic_nicknames):
            continue
        # Build a complete authority-shaped dict so the template renders safely.
        # Intentionally NO 'collector_data'/'latency_*' keys -> those columns render as
        # a muted "-" rather than an alarming red 0 / X.
        authorities.append({
            'nickname': entry.get('nickname', ''),
            'fingerprint': entry.get('fingerprint', ''),
            'running': False,
            'country': entry.get('country'),
            'country_name': entry.get('country_name'),
            'as': None,
            'as_name': None,
            'uptime_percentages': {},
            'uptime_zscore': None,
            'uptime_outlier_status': 'insufficient_data',
            'version': None,
            'recommended_version': None,
            'first_seen': None,
            'first_seen_relative': None,
            'first_seen_timestamp': None,
            'last_restarted': None,
            'is_known_offline': True,
            'offline_since': entry.get('offline_since'),
            'offline_note': entry.get('note', 'Removed from the directory authority list.'),
        })
    # Re-sort so any appended offline rows slot into alphabetical position
    authorities = sorted(authorities, key=lambda x: x.get('nickname', '').lower())

    # Offline summary is DYNAMIC: any authority currently not running - includes live
    # (stage 1/2) offline authorities AND hardcoded (stage 3) entries. Drives the
    # header sub-bullet, so it auto-updates for ANY future DA going offline.
    offline_names = sorted(a.get('nickname', '') for a in authorities if not a.get('running', False))
    offline_count = len(offline_names)

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
    # This is more accurate since some authorities (like Serge) may have Authority flag but don't vote.
    # When flag_thresholds is absent but votes were seen, the voting registry (updated from the vote
    # keys in enrich_with_api_data) still holds the real voter count, so prefer it over the Onionoo
    # Authority-flag count. Only with no vote data at all fall back to the DYNAMIC (pre-merge) Onionoo
    # count, so hardcoded offline rows never inflate the denominator.
    if collector_flag_thresholds:
        voting_authority_count = len(collector_flag_thresholds)
    else:
        from .consensus.collector_fetcher import get_authority_registry
        registry = get_authority_registry()
        voting_authority_count = (registry.get_voting_authority_count()
                                  if registry.has_dynamic_voting_authorities()
                                  else dynamic_authority_count)
    
    # Extract consensus method info from collector data (for Happy Family migration tracking)
    consensus_method_info = None
    if collector_data:
        consensus_method_info = collector_data.get('consensus_method_info')
    
    return {
        'authorities_data': authorities,
        'authorities_summary': {
            'total_authorities': voting_authority_count,
            'total_with_authority_flag': dynamic_authority_count,  # Live Onionoo count (excludes hardcoded offline rows)
            'above_average_uptime': above_average_uptime,
            'below_average_uptime': below_average_uptime,
            'problem_uptime': problem_uptime,
            'offline_count': offline_count,  # Dynamic: any authority not running (live + hardcoded)
            'offline_names': offline_names,
        },
        'authority_network_stats': authority_network_stats,
        'uptime_metadata': (getattr(relay_set, 'uptime_data', {}) or {}).get('relays_published', 'Unknown'),
        'consensus_status': consensus_status,
        'latency_summary': latency_summary,
        'authority_alerts': authority_alerts if authority_alerts else None,
        'collector_flag_thresholds': collector_flag_thresholds,
        'collector_fetched_at': collector_fetched_at,
        'consensus_method_info': consensus_method_info,
    }



def get_detail_page_context(relay_set, category, value):
    """Generate page context with correct breadcrumb data for detail pages"""
    # Use centralized page context generation
    from .page_context import get_detail_page_context
    display_value = None
    if category == "country":
        # Breadcrumb should show the country's display name, not the raw
        # ISO-code sorted key (country.html already derives the full name)
        group = relay_set.json.get("sorted", {}).get("country", {}).get(value, {})
        relay_idxs = group.get("relays", [])
        if relay_idxs:
            first_relay = relay_set.json["relays"][relay_idxs[0]]
            display_value = first_relay.get("country_name") or None
    return get_detail_page_context(category, value, display_value)


def _cleanup_vanity_sort_files(vanity_dir):
    """Remove all contact sort variant files from a vanity directory.

    Prevents stale pages when sort modes change (e.g. IPv6 relays removed)
    or an operator loses AROI validation between generations.
    """
    if not os.path.isdir(vanity_dir):
        return
    for filename in CONTACT_SORT_FILE_MAP.values():
        filepath = os.path.join(vanity_dir, filename)
        try:
            os.remove(filepath)
        except FileNotFoundError:
            pass
    try:
        os.rmdir(vanity_dir)
    except OSError:
        pass


def _render_contact_variants(template, relay_set, base_template_args, dir_path, contact_data, output_root):
    """Render all static sort variants for one contact page.

    Respects two gating rules:
    - Threshold: operators with ≤2 relays get only index.html (no sort links).
    - IPv6: by-ipv6.html is only emitted when IPv6 is visible in the contact.

    Vanity cleanup: removes stale vanity files when an operator loses
    validation or when sort modes change between generations.
    """
    files_written = 0

    aroi_domain = contact_data.get('aroi_domain')
    has_vanity_domain = aroi_domain and aroi_domain != 'none' and output_root
    vanity_dir = None

    if has_vanity_domain:
        safe_domain = _sanitize_path_component(aroi_domain.lower())
        potential_vanity_dir = os.path.join(output_root, safe_domain)

        if relay_set.base_url and base_template_args.get('is_validated_aroi'):
            _cleanup_vanity_sort_files(potential_vanity_dir)
            vanity_dir = potential_vanity_dir
            os.makedirs(vanity_dir, exist_ok=True)
        else:
            _cleanup_vanity_sort_files(potential_vanity_dir)

    # Determine which sort modes to generate
    relay_count = _contact_relay_count(base_template_args)
    has_ipv6 = _contact_has_ipv6(base_template_args)
    sort_enabled = relay_count >= 3

    if sort_enabled:
        modes_to_render = [m for m in CONTACT_SORT_MODES if m != 'ipv6' or has_ipv6]
    else:
        modes_to_render = [CONTACT_DEFAULT_SORT_MODE]

    for sort_mode in modes_to_render:
        filename = CONTACT_SORT_FILE_MAP[sort_mode]
        template_args = _build_contact_variant_args(
            base_template_args, sort_mode,
            contact_sort_enabled=sort_enabled,
            enabled_modes=modes_to_render,
        )
        template_args['contact_has_ipv6'] = has_ipv6
        rendered = template.render(relays=relay_set, **template_args)

        with open(os.path.join(dir_path, filename), "w", encoding="utf8") as html:
            html.write(rendered)
        files_written += 1

        if vanity_dir:
            adjusted_html = _adjust_vanity_paths(rendered)
            with open(os.path.join(vanity_dir, filename), "w", encoding="utf8") as vanity_html:
                vanity_html.write(adjusted_html)

    return files_written


def _render_contact_batch_mp(args):
    """Render all contact sort variants for one contact in a worker."""
    dir_path, value = args
    page_data = _mp_relay_set.json["sorted"]["contact"][value]
    base_template_args = build_template_args(
        _mp_relay_set, "contact", value, page_data, _mp_the_prefixed, _mp_validated_aroi_domains
    )
    return _render_contact_variants(
        _mp_template, _mp_relay_set, base_template_args, dir_path, page_data, _mp_output_root
    )


def _write_contact_pages_sequential(relay_set, sorted_values, template, output_path, the_prefixed, start_time):
    """Sequential contact generation that writes all contact sort variants."""
    validated_aroi_domains = getattr(relay_set, 'validated_aroi_domains', set())
    output_root = os.path.dirname(output_path)
    page_count = 0
    rendered_file_count = 0
    render_time = 0.0

    for v in sorted_values:
        contact_data = relay_set.json["sorted"]["contact"][v]
        v_safe = _sanitize_path_component(v)
        dir_path = os.path.join(output_path, v_safe)
        os.makedirs(dir_path, exist_ok=True)

        base_template_args = build_template_args(
            relay_set, "contact", v, contact_data, the_prefixed, validated_aroi_domains
        )

        render_start = time.time()
        rendered_file_count += _render_contact_variants(
            template, relay_set, base_template_args, dir_path, contact_data, output_root
        )
        render_time += time.time() - render_start
        page_count += 1

        if page_count % 500 == 0:
            relay_set.progress_logger.log_without_increment(f"Processed {page_count}/{len(sorted_values)} contact pages...")

    total_time = time.time() - start_time
    relay_set.progress_logger.log(
        f"contact page generation complete - Generated {page_count} contacts, {rendered_file_count} files in {total_time:.2f}s"
    )
    if relay_set.progress and rendered_file_count:
        print(f"    🎨 Contact variant render time: {render_time:.2f}s ({render_time/total_time*100:.1f}%)")
        print(f"    ⚡ Average per rendered file: {total_time/rendered_file_count*1000:.1f}ms")


def _write_contact_pages_parallel(relay_set, sorted_values, template, output_path, the_prefixed, start_time):
    """Parallel contact generation with one worker task per contact."""
    validated_aroi_domains = getattr(relay_set, 'validated_aroi_domains', set())
    page_args = []
    output_root = os.path.dirname(output_path)

    for v in sorted_values:
        v_safe = _sanitize_path_component(v)
        dir_path = os.path.join(output_path, v_safe)
        os.makedirs(dir_path, exist_ok=True)
        page_args.append((dir_path, v))

    pool = None
    try:
        ctx = mp.get_context('fork')
        pool = ctx.Pool(
            relay_set.mp_workers,
            _init_mp_worker,
            (relay_set, template, "contact", the_prefixed, validated_aroi_domains, output_root),
        )
        rendered_counts = pool.map(_render_contact_batch_mp, page_args)
        pool.close()
        pool.join()

        total_time = time.time() - start_time
        total_files = sum(rendered_counts)
        relay_set.progress_logger.log(
            f"contact page generation complete - Generated {len(page_args)} contacts, {total_files} files in {total_time:.2f}s"
        )
        if relay_set.progress and total_files:
            print(f"    🚀 Parallel: {relay_set.mp_workers} workers, {total_time/total_files*1000:.1f}ms/rendered file avg")
    except Exception as e:
        if pool is not None:
            try:
                pool.terminate()
                pool.join()
            except Exception:
                pass

        relay_set.progress_logger.log_without_increment(f"Contact multiprocessing failed ({e}), falling back to sequential...")
        relay_set.mp_workers = 0
        for retry in range(3):
            try:
                if os.path.exists(output_path):
                    rmtree(output_path)
                os.makedirs(output_path)
                break
            except OSError:
                if retry < 2:
                    time.sleep(0.1)

        _write_contact_pages_sequential(relay_set, sorted_values, template, output_path, the_prefixed, start_time)


def write_pages_by_key(relay_set, k):
    """Render and write sorted HTML relay listings to disk"""
    start_time = time.time()
    relay_set.progress_logger.log_without_increment(f"Starting {k} page generation...")
    
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
    use_mp = (relay_set.mp_workers > 0 and len(sorted_values) >= 100 and 
              hasattr(mp, 'get_context'))

    # Contact pages use dedicated variant-aware renderers (17 by-*.html + index default)
    if k == "contact":
        if use_mp:
            _write_contact_pages_parallel(relay_set, sorted_values, template, output_path, the_prefixed, start_time)
        else:
            _write_contact_pages_sequential(relay_set, sorted_values, template, output_path, the_prefixed, start_time)
        return
    
    if use_mp:
        write_pages_parallel(relay_set, k, sorted_values, template, output_path, the_prefixed, start_time)
        return
    
    page_count = render_time = io_time = 0
    
    for v in sorted_values:
        i = relay_set.json["sorted"][k][v]
        # Sanitize for filesystem paths only (raw v used for data lookup above)
        v_safe = _sanitize_path_component(v)
        dir_path = os.path.join(output_path, v_safe.lower() if k == "flag" else v_safe)
        os.makedirs(dir_path, exist_ok=True)

        # Shared arg construction with the parallel path (they cannot drift)
        render_start = time.time()
        template_args = build_template_args(
            relay_set, k, v, i, the_prefixed,
            relay_set.validated_aroi_domains if hasattr(relay_set, 'validated_aroi_domains') else set()
        )
        rendered = template.render(relays=relay_set, **template_args)
        render_time += time.time() - render_start

        # Time the file I/O
        io_start = time.time()
        html_path = os.path.join(dir_path, "index.html")
        with open(html_path, "w", encoding="utf8") as html:
            html.write(rendered)
        io_time += time.time() - io_start

        page_count += 1
        
        # Print progress for large page sets
        if page_count % 1000 == 0:
            relay_set.progress_logger.log_without_increment(f"Processed {page_count} {k} pages...")

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
            contact_validation_status = _contact_validation_status(relay_set, members)
        aroi_validation_timestamp = relay_set._aroi_validation_timestamp
    
    # Family support counts for summary bullet (DRY helper)
    family_support_counts = _get_family_support_counts(k, contact_display_data, i)
    # Exit DNS Health summary (DRY helper - precomputed for contacts/families, on-the-fly for others)
    exit_dns_health_summary = _get_exit_dns_health_summary(k, i, members)
    # Overload summary bullet (contact/family/as pages only; None hides bullet)
    overload_summary = (compute_group_overload_summary(members)
                        if k in ("contact", "family", "as") else None)

    display = i.get("display", {})
    
    return {
        'relay_subset': members,
        'total_data_formatted': display.get("total_data_formatted", "N/A"),
        'total_data_pct': display.get("total_data_pct", ""),
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
        'family_support_counts': family_support_counts,
        'exit_dns_health_summary': exit_dns_health_summary,
        'overload_summary': overload_summary,
        'sortable_scope': 'contact' if k == 'contact' else 'none',
        'contact_sort_mode': CONTACT_DEFAULT_SORT_MODE if k == 'contact' else None,
        'contact_sort_links': _contact_sort_links() if k == 'contact' else {},
        'contact_sort_enabled': (k == 'contact' and len(members) > 2),
        'contact_has_ipv6': True,  # Default; _render_contact_variants overrides per-contact
    }

def write_pages_parallel(relay_set, k, sorted_values, template, output_path, the_prefixed, start_time):
    """Parallel page generation using fork() for significant speedup on large page sets.
    
    OPTIMIZED: Now passes only (html_path, value) to workers instead of full template args.
    Workers build template args from forked memory, avoiding ~300KB/page IPC serialization.
    This dramatically improves performance for large page sets like families (105+ members avg).
    """
    validated_aroi_domains = getattr(relay_set, 'validated_aroi_domains', set())
    page_args = []

    # Contact pages never reach this function (routed to dedicated renderers
    # in write_pages_by_key), so no vanity-URL handling is needed here.
    for v in sorted_values:
        # Sanitize for filesystem paths only (raw v used for data lookup by workers)
        v_safe = _sanitize_path_component(v)
        dir_path = os.path.join(output_path, v_safe.lower() if k == "flag" else v_safe)
        os.makedirs(dir_path, exist_ok=True)
        html_path = os.path.join(dir_path, "index.html")
        # OPTIMIZED: Pass only (html_path, value) - workers build template args from forked memory
        # Raw v is passed so workers can look up data in relay_set.json["sorted"][k][v]
        page_args.append((html_path, v))
    
    pool = None
    try:
        ctx = mp.get_context('fork')
        # Initialize workers with page_type and shared data for building template args
        pool = ctx.Pool(relay_set.mp_workers, _init_mp_worker, 
                       (relay_set, template, k, the_prefixed, validated_aroi_domains))
        pool.map(_render_page_mp, page_args)
        pool.close()
        pool.join()

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
        
        relay_set.progress_logger.log_without_increment(f"Multiprocessing failed ({e}), falling back to sequential...")
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
    
    # Optimization: Cache frequently-accessed properties before 10K relay loop
    validated_aroi_domains = getattr(relay_set, 'validated_aroi_domains', set())
    aroi_validation_timestamp = relay_set._aroi_validation_timestamp
    base_url = relay_set.base_url
    # Pre-fetch family cert data for partitioned family display (O(1) per member)
    family_cert_fps = getattr(relay_set, '_family_cert_fps_cache', set())
    fp_to_family_key = getattr(relay_set, '_fp_to_family_key', {})
    family_key_to_fps = getattr(relay_set, '_family_key_to_fps', {})

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
        
        # Partition family lists by family-cert status for template display
        _partition_family_lists(relay, family_cert_fps, fp_to_family_key, family_key_to_fps)
        
        rendered = template.render(
            relay=relay, page_ctx=page_ctx, relays=relay_set, contact_display_data=contact_display_data,
            contact_validation_status=contact_validation_status,
            aroi_validation_timestamp=aroi_validation_timestamp,
            validated_aroi_domains=validated_aroi_domains,
            base_url=base_url
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


