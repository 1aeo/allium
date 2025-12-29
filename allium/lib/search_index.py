"""
File: allium/lib/search_index.py

Search index generator for Cloudflare Pages Function search.
Generates a compact JSON index of relays and families for server-side search.

Design principles:
- Compute-efficient: All processing done at build time
- Compact output: Short keys, minimal redundancy
- DRY: Reusable helper functions
"""

import json
import os
from typing import Any, Dict, List, Optional


# =============================================================================
# CONSTANTS
# =============================================================================

MIN_PREFIX_LENGTH = 3
PREFIX_STRIP_CHARS = '-_0123456789'
GENERIC_PREFIXES = frozenset({
    'relay', 'tor', 'exit', 'guard', 'node', 'server',
    'unnamed', 'default', 'test', 'my'
})


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def extract_ip_from_or_address(or_address: str) -> Optional[str]:
    """
    Extract IP address from OR address string.
    Handles IPv4 "1.2.3.4:9001" and IPv6 "[2001:db8::1]:9001".
    """
    if not or_address:
        return None

    if or_address.startswith('['):
        bracket_end = or_address.find(']')
        if bracket_end > 1:
            return or_address[1:bracket_end]
    else:
        colon_pos = or_address.rfind(':')
        if colon_pos > 0:
            return or_address[:colon_pos]
        return or_address

    return None


def extract_common_prefix(nicknames: List[str]) -> Optional[str]:
    """
    Find the longest common prefix among a list of nicknames.
    Used to detect operator naming patterns.
    """
    if not nicknames or len(nicknames) < 2:
        return None

    valid_names = [n for n in nicknames if n]
    if len(valid_names) < 2:
        return None

    sorted_names = sorted(valid_names, key=str.lower)
    first = sorted_names[0].lower()
    last = sorted_names[-1].lower()

    prefix_len = 0
    for i, char in enumerate(first):
        if i < len(last) and first[i] == last[i]:
            prefix_len += 1
        else:
            break

    if prefix_len < MIN_PREFIX_LENGTH:
        return None

    prefix = sorted_names[0][:prefix_len].rstrip(PREFIX_STRIP_CHARS)

    if len(prefix) < MIN_PREFIX_LENGTH:
        return None

    return prefix


def is_generic_prefix(prefix: str) -> bool:
    """Check if a prefix is generic/common."""
    return prefix.lower() in GENERIC_PREFIXES


def compact_relay_entry(relay: Dict[str, Any], family_id: Optional[str]) -> Dict[str, Any]:
    """Create a compact relay entry for the search index."""
    entry = {
        'f': relay['fingerprint'],
        'n': relay.get('nickname', ''),
    }

    aroi = relay.get('aroi_domain')
    if aroi and aroi != 'none':
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

    ips = []
    for addr in relay.get('or_addresses', []):
        ip = extract_ip_from_or_address(addr)
        if ip:
            ips.append(ip)
    if ips:
        entry['ip'] = ips

    if family_id:
        entry['fam'] = family_id

    return entry


def compact_family_entry(
    family_id: str,
    family_data: Dict[str, Any],
    relays: List[Dict[str, Any]],
    relay_indices: List[int]
) -> Dict[str, Any]:
    """Create a compact family entry for the search index."""
    members = [relays[idx] for idx in relay_indices]

    nicknames = [m.get('nickname', '') for m in members if m.get('nickname')]
    prefix = extract_common_prefix(nicknames)

    as_numbers = sorted(set(m.get('as') for m in members if m.get('as')))
    countries = sorted(set(m.get('country', '').lower() for m in members if m.get('country')))
    contact_hashes = sorted(set(m.get('contact_md5') for m in members if m.get('contact_md5')))

    entry = {
        'id': family_id,
        'sz': len(members),
        'nn': nicknames,
    }

    if prefix:
        entry['px'] = prefix
        entry['pxg'] = is_generic_prefix(prefix)

    aroi = family_data.get('aroi_domain')
    if aroi and aroi != 'none':
        entry['a'] = aroi

    if contact_hashes:
        entry['c'] = contact_hashes

    if as_numbers:
        entry['as'] = as_numbers

    if countries:
        entry['cc'] = countries

    first_seen = family_data.get('first_seen', '')
    if first_seen:
        entry['fs'] = first_seen.split(' ')[0]

    return entry


# =============================================================================
# MAIN GENERATOR
# =============================================================================

def generate_search_index(relays_data: Dict[str, Any], output_path: str) -> Dict[str, int]:
    """
    Generate a compact search index for the Cloudflare Pages Function.

    Args:
        relays_data: The RELAY_SET.json data structure from allium
        output_path: Path to write the search-index.json file

    Returns:
        Dictionary with statistics about the generated index
    """
    relays = relays_data.get('relays', [])
    sorted_data = relays_data.get('sorted', {})
    family_data = sorted_data.get('family', {})

    # Build family membership map
    family_membership: Dict[str, str] = {}
    for family_id, fdata in family_data.items():
        for idx in fdata.get('relays', []):
            relay_fp = relays[idx]['fingerprint']
            family_membership[relay_fp] = family_id

    index = {
        'meta': {
            'generated_at': relays_data.get('relays_published', ''),
            'relay_count': len(relays),
            'family_count': len(family_data),
            'version': '1.0'
        },
        'relays': [],
        'families': [],
        'lookups': {
            'as_names': {},
            'country_names': {},
            'platforms': set(),
            'flags': set()
        }
    }

    # Process relays
    for relay in relays:
        fp = relay['fingerprint']
        family_id = family_membership.get(fp)

        # Only include family_id if family has 2+ members
        if family_id and len(family_data.get(family_id, {}).get('relays', [])) < 2:
            family_id = None

        entry = compact_relay_entry(relay, family_id)
        index['relays'].append(entry)

        # Build lookup tables
        if relay.get('as') and relay.get('as_name'):
            index['lookups']['as_names'][relay['as']] = relay['as_name']

        if relay.get('country') and relay.get('country_name'):
            index['lookups']['country_names'][relay['country'].lower()] = relay['country_name']

        if relay.get('platform'):
            index['lookups']['platforms'].add(relay['platform'].lower())

        for flag in relay.get('flags', []):
            index['lookups']['flags'].add(flag.lower())

    # Process families (only those with 2+ members)
    for family_id, fdata in family_data.items():
        relay_indices = fdata.get('relays', [])
        if len(relay_indices) < 2:
            continue

        entry = compact_family_entry(family_id, fdata, relays, relay_indices)
        index['families'].append(entry)

    # Convert sets to sorted lists for JSON serialization
    index['lookups']['platforms'] = sorted(index['lookups']['platforms'])
    index['lookups']['flags'] = sorted(index['lookups']['flags'])

    # Write minified JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, separators=(',', ':'), ensure_ascii=False)

    file_size = os.path.getsize(output_path)

    return {
        'relay_count': len(index['relays']),
        'family_count': len(index['families']),
        'as_count': len(index['lookups']['as_names']),
        'country_count': len(index['lookups']['country_names']),
        'file_size_bytes': file_size,
        'file_size_kb': round(file_size / 1024, 1)
    }
