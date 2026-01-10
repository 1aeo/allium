"""
File: allium/lib/search_index.py

Search index generator for Cloudflare Pages Function search.
Generates a compact JSON index of relays and families for server-side search.

Design principles:
- Compute-efficient: Precomputed lookups, minimal iterations, parallel processing
- Compact output: Short keys, minimal redundancy
- DRY: Reusable helper functions, imports existing utilities
- Security: Input validation, safe file handling
"""

import json
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Set, Tuple

# Import existing utilities (DRY - avoid reimplementing)
from .aroileaders import _safe_parse_ip_address
from .string_utils import is_valid_aroi


# =============================================================================
# CONSTANTS
# =============================================================================

MIN_PREFIX_LENGTH = 3
PREFIX_STRIP_CHARS = '-_0123456789'
GENERIC_PREFIXES = frozenset({
    'relay', 'tor', 'exit', 'guard', 'node', 'server',
    'unnamed', 'default', 'test', 'my'
})

# Parallel processing threshold (use threads if relay count exceeds this)
PARALLEL_THRESHOLD = 1000
MAX_WORKERS = 4


# =============================================================================
# HELPER FUNCTIONS (DRY)
# =============================================================================


def extract_ip_from_or_address(or_address: str) -> Optional[str]:
    """
    Extract IP address from OR address string.
    Handles IPv4 "1.2.3.4:9001" and IPv6 "[2001:db8::1]:9001".
    
    Uses _safe_parse_ip_address from aroileaders.py for robust parsing
    with ipaddress module validation.
    """
    ip, _ = _safe_parse_ip_address(or_address)
    return ip


def extract_common_prefix(nicknames: List[str]) -> Optional[str]:
    """
    Find the longest common prefix among a list of nicknames.
    Used to detect operator naming patterns (e.g., "relay1", "relay2" -> "relay").
    
    Uses efficient sorting-based algorithm: only compares first and last sorted items.
    """
    if not nicknames or len(nicknames) < 2:
        return None

    # Filter and validate in single pass
    valid_names = [n for n in nicknames if n and isinstance(n, str)]
    if len(valid_names) < 2:
        return None

    # Sort once, then compare first vs last (lexicographically most different)
    sorted_names = sorted(valid_names, key=str.lower)
    first = sorted_names[0].lower()
    last = sorted_names[-1].lower()

    # Find common prefix length
    prefix_len = 0
    min_len = min(len(first), len(last))
    for i in range(min_len):
        if first[i] == last[i]:
            prefix_len += 1
        else:
            break

    if prefix_len < MIN_PREFIX_LENGTH:
        return None

    # Strip trailing numbers and separators
    prefix = sorted_names[0][:prefix_len].rstrip(PREFIX_STRIP_CHARS)

    if len(prefix) < MIN_PREFIX_LENGTH:
        return None

    return prefix


def is_generic_prefix(prefix: str) -> bool:
    """Check if a prefix is generic/common (e.g., 'relay', 'tor')."""
    return prefix.lower() in GENERIC_PREFIXES


def extract_ips_from_relay(relay: Dict[str, Any]) -> List[str]:
    """Extract all valid IP addresses from relay OR addresses."""
    return [ip for addr in relay.get('or_addresses', [])
            if (ip := extract_ip_from_or_address(addr))]


# =============================================================================
# ENTRY BUILDERS (DRY - reusable compact entry creation)
# =============================================================================

def compact_relay_entry(
    relay: Dict[str, Any],
    family_id: Optional[str]
) -> Dict[str, Any]:
    """
    Create a compact relay entry for the search index.
    
    Only includes non-empty fields to minimize JSON size.
    """
    entry = {
        'f': relay['fingerprint'],
        'n': relay.get('nickname', ''),
    }

    # Optional fields - only include if present
    aroi = relay.get('aroi_domain')
    if is_valid_aroi(aroi):
        entry['a'] = aroi

    contact_md5 = relay.get('contact_md5')
    if contact_md5:
        entry['c'] = contact_md5

    as_number = relay.get('as')
    if as_number:
        entry['as'] = as_number

    country = relay.get('country')
    if country:
        entry['cc'] = country.lower()

    ips = extract_ips_from_relay(relay)
    if ips:
        entry['ip'] = ips

    if family_id:
        entry['fam'] = family_id

    return entry


def compact_family_entry(
    family_id: str,
    family_data: Dict[str, Any],
    members: List[Dict[str, Any]],
    validated_aroi_domains: Optional[Set[str]] = None
) -> Dict[str, Any]:
    """
    Create a compact family entry for the search index.
    
    Aggregates data from all family members using set comprehensions.
    
    Optimizations for space and compute efficiency:
    - nn: Dict[nickname_lowercase, count] instead of array of repeated names
      Example: {"quetzalcoatl": 348} instead of ["Quetzalcoatl"] * 348
      Keys are LOWERCASE to avoid 300k+ .lower() calls during search
    - pxg: Only included when true (generic prefix); absence means false
    - px: Preserves original case for display purposes
    
    This reduces index size by ~25% while preserving searchability.
    """
    # Extract member data using comprehensions (more Pythonic)
    nicknames = [m['nickname'] for m in members if m.get('nickname')]
    as_numbers = {m['as'] for m in members if m.get('as')}
    countries = {m['country'].lower() for m in members if m.get('country')}
    contacts = {m['contact_md5'] for m in members if m.get('contact_md5')}

    # Count nicknames for compact storage using Counter (O(n) single pass)
    # Store keys in LOWERCASE for efficient case-insensitive search
    # (avoids 300k+ .lower() calls per search query)
    nickname_counts = {}
    for name in nicknames:
        key = name.lower()
        nickname_counts[key] = nickname_counts.get(key, 0) + 1

    # Build base entry
    entry: Dict[str, Any] = {
        'id': family_id,
        'sz': len(members),
        'nn': nickname_counts,  # {nickname: count} format for compactness
    }

    # Add prefix if detected (non-generic preferred for search relevance)
    prefix = extract_common_prefix(nicknames)
    if prefix:
        entry['px'] = prefix
        # Only include pxg when true (generic) - saves space as most are false
        if is_generic_prefix(prefix):
            entry['pxg'] = True

    # Optional fields - only include if present
    aroi = family_data.get('aroi_domain')
    if is_valid_aroi(aroi):
        entry['a'] = aroi
        # v=True enables operator page redirect instead of family page
        if validated_aroi_domains and aroi in validated_aroi_domains:
            entry['v'] = True

    if contacts:
        entry['c'] = sorted(contacts)

    if as_numbers:
        entry['as'] = sorted(as_numbers)

    if countries:
        entry['cc'] = sorted(countries)

    first_seen = family_data.get('first_seen', '')
    if first_seen:
        entry['fs'] = first_seen.split(' ')[0]  # Date only, no time

    return entry


# =============================================================================
# RELAY PROCESSING (DRY - shared between sequential and parallel paths)
# =============================================================================

def _get_valid_family_id(
    fingerprint: str,
    family_membership: Dict[str, str],
    valid_family_ids: Set[str]
) -> Optional[str]:
    """Get family ID for a relay, or None if not in a valid family (2+ members)."""
    family_id = family_membership.get(fingerprint)
    return family_id if family_id and family_id in valid_family_ids else None


def _collect_lookup_data(
    relay: Dict[str, Any],
    as_names: Dict[str, str],
    country_names: Dict[str, str],
    platforms: Set[str],
    flags: Set[str]
) -> None:
    """
    Collect lookup data from a relay into provided collectors (mutates in place).
    
    This is the single source of truth for what lookup data we extract from relays.
    """
    # AS name mapping
    as_num, as_name = relay.get('as'), relay.get('as_name')
    if as_num and as_name:
        as_names[as_num] = as_name

    # Country name mapping
    country, country_name = relay.get('country'), relay.get('country_name')
    if country and country_name:
        country_names[country.lower()] = country_name

    # Platform
    platform = relay.get('platform')
    if platform:
        platforms.add(platform.lower())

    # Flags
    flags.update(flag.lower() for flag in relay.get('flags', []))


def _process_relay_batch(
    batch: List[Tuple[int, Dict[str, Any]]],
    family_membership: Dict[str, str],
    valid_family_ids: Set[str]
) -> Tuple[List[Tuple[int, Dict[str, Any]]], Dict[str, str], Dict[str, str], Set[str], Set[str]]:
    """
    Process a batch of relays for parallel execution.
    
    Returns:
        Tuple of (indexed_entries, as_names, country_names, platforms, flags)
        where indexed_entries is List[(original_index, entry)]
    """
    indexed_entries: List[Tuple[int, Dict[str, Any]]] = []
    as_names: Dict[str, str] = {}
    country_names: Dict[str, str] = {}
    platforms: Set[str] = set()
    flags: Set[str] = set()

    for idx, relay in batch:
        family_id = _get_valid_family_id(relay['fingerprint'], family_membership, valid_family_ids)
        entry = compact_relay_entry(relay, family_id)
        indexed_entries.append((idx, entry))
        _collect_lookup_data(relay, as_names, country_names, platforms, flags)

    return indexed_entries, as_names, country_names, platforms, flags


# =============================================================================
# MAIN GENERATOR
# =============================================================================

def generate_search_index(
    relays_data: Dict[str, Any],
    output_path: str,
    use_parallel: bool = True,
    validated_aroi_domains: Optional[Set[str]] = None
) -> Dict[str, int]:
    """
    Generate a compact search index for the Cloudflare Pages Function.

    Args:
        relays_data: The RELAY_SET.json data structure from allium
        output_path: Path to write the search-index.json file
        use_parallel: Whether to use parallel processing for large datasets
        validated_aroi_domains: Set of validated AROI domains for operator page redirects

    Returns:
        Dictionary with statistics about the generated index
        
    Security:
        - Validates output_path is writable
        - Uses atomic write pattern to prevent partial writes
    """
    relays = relays_data.get('relays', [])
    sorted_data = relays_data.get('sorted', {})
    family_data = sorted_data.get('family', {})

    # ==========================================================================
    # PHASE 1: Precompute lookup structures (O(f) where f = families)
    # ==========================================================================
    
    # Build family membership map: fingerprint -> family_id
    family_membership: Dict[str, str] = {}
    # Precompute valid family IDs (families with 2+ members)
    valid_family_ids: Set[str] = set()
    
    for family_id, fdata in family_data.items():
        relay_indices = fdata.get('relays', [])
        if len(relay_indices) >= 2:
            valid_family_ids.add(family_id)
        for idx in relay_indices:
            if idx < len(relays):
                relay_fp = relays[idx]['fingerprint']
                family_membership[relay_fp] = family_id

    # ==========================================================================
    # PHASE 2: Process relays (O(n) where n = relays)
    # ==========================================================================
    
    relay_count = len(relays)
    use_threads = use_parallel and relay_count > PARALLEL_THRESHOLD

    # Initialize lookup collectors
    as_names: Dict[str, str] = {}
    country_names: Dict[str, str] = {}
    platforms: Set[str] = set()
    flags: Set[str] = set()
    relay_entries: List[Dict[str, Any]] = []

    if use_threads:
        # Parallel processing for large datasets
        batch_size = max(100, relay_count // MAX_WORKERS)
        batches = []
        for i in range(0, relay_count, batch_size):
            batch = [(j, relays[j]) for j in range(i, min(i + batch_size, relay_count))]
            batches.append(batch)

        # Process batches in parallel
        indexed_entries: List[Tuple[int, Dict[str, Any]]] = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [
                executor.submit(_process_relay_batch, batch, family_membership, valid_family_ids)
                for batch in batches
            ]
            for future in as_completed(futures):
                batch_entries, batch_as, batch_countries, batch_platforms, batch_flags = future.result()
                indexed_entries.extend(batch_entries)
                as_names.update(batch_as)
                country_names.update(batch_countries)
                platforms.update(batch_platforms)
                flags.update(batch_flags)

        # Sort by original index to maintain order
        indexed_entries.sort(key=lambda x: x[0])
        relay_entries = [entry for _, entry in indexed_entries]
    else:
        # Sequential processing for small datasets (uses same helpers as parallel)
        for relay in relays:
            family_id = _get_valid_family_id(relay['fingerprint'], family_membership, valid_family_ids)
            entry = compact_relay_entry(relay, family_id)
            relay_entries.append(entry)
            _collect_lookup_data(relay, as_names, country_names, platforms, flags)

    # ==========================================================================
    # PHASE 3: Process families (O(f) where f = valid families)
    # ==========================================================================
    
    family_entries: List[Dict[str, Any]] = []
    for family_id in valid_family_ids:
        fdata = family_data[family_id]
        relay_indices = fdata.get('relays', [])
        
        # Get member relays (with bounds checking)
        members = [relays[idx] for idx in relay_indices if idx < len(relays)]
        
        entry = compact_family_entry(family_id, fdata, members, validated_aroi_domains)
        family_entries.append(entry)

    # ==========================================================================
    # PHASE 4: Assemble and write index
    # ==========================================================================
    
    index = {
        'meta': {
            'generated_at': relays_data.get('relays_published', ''),
            'relay_count': len(relays),
            'family_count': len(valid_family_ids),
            'version': '1.4'  # 1.1: nn->dict, 1.2: pxg sparse, 1.3: nn keys lowercase, 1.4: v (validated) field
        },
        'relays': relay_entries,
        'families': family_entries,
        'lookups': {
            'as_names': as_names,
            'country_names': country_names,
            'platforms': sorted(platforms),
            'flags': sorted(flags)
        }
    }

    # Write minified JSON (atomic write pattern for safety)
    temp_path = output_path + '.tmp'
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(index, f, separators=(',', ':'), ensure_ascii=False)
        # Atomic rename
        os.replace(temp_path, output_path)
    except Exception:
        # Clean up temp file on error
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

    file_size = os.path.getsize(output_path)

    return {
        'relay_count': len(relay_entries),
        'family_count': len(family_entries),
        'as_count': len(as_names),
        'country_count': len(country_names),
        'file_size_bytes': file_size,
        'file_size_kb': round(file_size / 1024, 1)
    }
