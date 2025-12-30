"""
File: allium/lib/search_index.py

Search index generator for Cloudflare Pages Function search.
Generates a compact JSON index of relays and families for server-side search.

Design principles:
- Compute-efficient: Precomputed lookups, minimal iterations, parallel processing
- Compact output: Short keys, minimal redundancy
- DRY: Reusable helper functions
- Security: Input validation, safe file handling
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Set, Tuple


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

def is_valid_aroi(aroi: Optional[str]) -> bool:
    """Check if AROI domain is valid (not None, empty, or 'none')."""
    return bool(aroi) and aroi != 'none'


def extract_ip_from_or_address(or_address: str) -> Optional[str]:
    """
    Extract IP address from OR address string.
    Handles IPv4 "1.2.3.4:9001" and IPv6 "[2001:db8::1]:9001".
    
    Security: Only processes string input, returns None for invalid formats.
    """
    if not or_address or not isinstance(or_address, str):
        return None

    if or_address.startswith('['):
        # IPv6 format: [2001:db8::1]:9001
        bracket_end = or_address.find(']')
        if bracket_end > 1:
            return or_address[1:bracket_end]
        return None
    else:
        # IPv4 format: 1.2.3.4:9001
        colon_pos = or_address.rfind(':')
        if colon_pos > 0:
            return or_address[:colon_pos]
        return or_address


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
    ips = []
    for addr in relay.get('or_addresses', []):
        ip = extract_ip_from_or_address(addr)
        if ip:
            ips.append(ip)
    return ips


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
    members: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Create a compact family entry for the search index.
    
    Aggregates data from all family members in a single pass where possible.
    """
    # Collect data in single iteration over members
    nicknames = []
    as_numbers_set: Set[str] = set()
    countries_set: Set[str] = set()
    contact_hashes_set: Set[str] = set()

    for member in members:
        nickname = member.get('nickname')
        if nickname:
            nicknames.append(nickname)
        
        as_num = member.get('as')
        if as_num:
            as_numbers_set.add(as_num)
        
        country = member.get('country')
        if country:
            countries_set.add(country.lower())
        
        contact_md5 = member.get('contact_md5')
        if contact_md5:
            contact_hashes_set.add(contact_md5)

    # Build entry
    entry = {
        'id': family_id,
        'sz': len(members),
        'nn': nicknames,
    }

    # Add prefix if detected
    prefix = extract_common_prefix(nicknames)
    if prefix:
        entry['px'] = prefix
        entry['pxg'] = is_generic_prefix(prefix)

    # Optional fields
    aroi = family_data.get('aroi_domain')
    if is_valid_aroi(aroi):
        entry['a'] = aroi

    if contact_hashes_set:
        entry['c'] = sorted(contact_hashes_set)

    if as_numbers_set:
        entry['as'] = sorted(as_numbers_set)

    if countries_set:
        entry['cc'] = sorted(countries_set)

    first_seen = family_data.get('first_seen', '')
    if first_seen:
        entry['fs'] = first_seen.split(' ')[0]

    return entry


# =============================================================================
# PARALLEL PROCESSING HELPERS
# =============================================================================

def _process_relay_batch(
    batch: List[Tuple[int, Dict[str, Any]]],
    family_membership: Dict[str, str],
    valid_family_ids: Set[str]
) -> Tuple[List[Dict[str, Any]], Dict[str, str], Dict[str, str], Set[str], Set[str]]:
    """
    Process a batch of relays in parallel.
    
    Returns:
        Tuple of (relay_entries, as_names, country_names, platforms, flags)
    """
    relay_entries = []
    as_names: Dict[str, str] = {}
    country_names: Dict[str, str] = {}
    platforms: Set[str] = set()
    flags: Set[str] = set()

    for idx, relay in batch:
        fp = relay['fingerprint']
        family_id = family_membership.get(fp)
        
        # Only include family_id if family is valid (2+ members)
        if family_id and family_id not in valid_family_ids:
            family_id = None

        entry = compact_relay_entry(relay, family_id)
        relay_entries.append((idx, entry))

        # Collect lookup data
        if relay.get('as') and relay.get('as_name'):
            as_names[relay['as']] = relay['as_name']

        if relay.get('country') and relay.get('country_name'):
            country_names[relay['country'].lower()] = relay['country_name']

        platform = relay.get('platform')
        if platform:
            platforms.add(platform.lower())

        for flag in relay.get('flags', []):
            flags.add(flag.lower())

    return relay_entries, as_names, country_names, platforms, flags


# =============================================================================
# MAIN GENERATOR
# =============================================================================

def generate_search_index(
    relays_data: Dict[str, Any],
    output_path: str,
    use_parallel: bool = True
) -> Dict[str, int]:
    """
    Generate a compact search index for the Cloudflare Pages Function.

    Args:
        relays_data: The RELAY_SET.json data structure from allium
        output_path: Path to write the search-index.json file
        use_parallel: Whether to use parallel processing for large datasets

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
        # Sequential processing for small datasets
        for relay in relays:
            fp = relay['fingerprint']
            family_id = family_membership.get(fp)
            
            # Only include family_id if family is valid (2+ members)
            if family_id and family_id not in valid_family_ids:
                family_id = None

            entry = compact_relay_entry(relay, family_id)
            relay_entries.append(entry)

            # Collect lookup data
            if relay.get('as') and relay.get('as_name'):
                as_names[relay['as']] = relay['as_name']

            if relay.get('country') and relay.get('country_name'):
                country_names[relay['country'].lower()] = relay['country_name']

            platform = relay.get('platform')
            if platform:
                platforms.add(platform.lower())

            for flag in relay.get('flags', []):
                flags.add(flag.lower())

    # ==========================================================================
    # PHASE 3: Process families (O(f) where f = valid families)
    # ==========================================================================
    
    family_entries: List[Dict[str, Any]] = []
    for family_id in valid_family_ids:
        fdata = family_data[family_id]
        relay_indices = fdata.get('relays', [])
        
        # Get member relays (with bounds checking)
        members = [relays[idx] for idx in relay_indices if idx < len(relays)]
        
        entry = compact_family_entry(family_id, fdata, members)
        family_entries.append(entry)

    # ==========================================================================
    # PHASE 4: Assemble and write index
    # ==========================================================================
    
    index = {
        'meta': {
            'generated_at': relays_data.get('relays_published', ''),
            'relay_count': len(relays),
            'family_count': len(valid_family_ids),
            'version': '1.0'
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
