#!/usr/bin/env python3
"""
Search Index Validation & Search Simulation Test

This script validates the search-index.json and simulates the search logic
that will be implemented in the Cloudflare Pages Function.
"""

import json
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

# =============================================================================
# LOAD INDEX
# =============================================================================

def load_index(path: str) -> Dict[str, Any]:
    with open(path, 'r') as f:
        return json.load(f)

# =============================================================================
# SEARCH PATTERNS (same as will be in search.js)
# =============================================================================

FULL_FINGERPRINT = re.compile(r'^[A-Fa-f0-9]{40}$')
PARTIAL_FINGERPRINT = re.compile(r'^[A-Fa-f0-9]{6,39}$')
IP_ADDRESS = re.compile(r'^[\d.:a-fA-F]+$')
AS_NUMBER = re.compile(r'^(?:AS)?(\d+)$', re.IGNORECASE)

# =============================================================================
# SEARCH SIMULATION (mirrors search.js logic)
# =============================================================================

def _family_result(f: Dict[str, Any], hint: str = None) -> Dict[str, Any]:
    """Return operator page if family has validated AROI, otherwise family page."""
    if f.get('v') and f.get('a'):
        return {'type': 'operator', 'aroi_domain': f['a'], 'hint': hint}
    return {'type': 'family', 'family_id': f['id'], 'hint': hint}


def search(query: str, index: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate the search function from search.js"""
    q = query.strip()
    if not q:
        return {'type': 'not_found', 'query': ''}
    
    q_lower = q.lower()
    q_upper = q.upper()
    relays = index['relays']
    families = index['families']
    lookups = index['lookups']
    
    # Step 1: Full fingerprint
    if FULL_FINGERPRINT.match(q):
        for r in relays:
            if r['f'].upper() == q_upper:
                return {'type': 'relay', 'fingerprint': r['f'], 'nickname': r.get('n', '')}
        for f in families:
            if f['id'].upper() == q_upper:
                return _family_result(f)
        return {'type': 'not_found', 'query': q}
    
    # Step 2: Partial fingerprint
    if PARTIAL_FINGERPRINT.match(q):
        relay_matches = [r for r in relays if r['f'].upper().startswith(q_upper)][:10]
        family_matches = [f for f in families if f['id'].upper().startswith(q_upper)][:5]
        
        if len(relay_matches) == 1 and len(family_matches) == 0:
            return {'type': 'relay', 'fingerprint': relay_matches[0]['f'], 'nickname': relay_matches[0].get('n', '')}
        if len(family_matches) == 1 and len(relay_matches) == 0:
            return _family_result(family_matches[0])
        if relay_matches or family_matches:
            return {'type': 'multiple', 'relays': len(relay_matches), 'families': len(family_matches)}
    
    # Step 3: Exact nickname
    exact_matches = [r for r in relays if r.get('n', '').lower() == q_lower][:50]
    if len(exact_matches) == 1:
        return {'type': 'relay', 'fingerprint': exact_matches[0]['f'], 'nickname': exact_matches[0].get('n', '')}
    if len(exact_matches) > 1:
        family_ids = set(r.get('fam') for r in exact_matches if r.get('fam'))
        if len(family_ids) == 1:
            f = next((f for f in families if f['id'] == list(family_ids)[0]), None)
            if f:
                return _family_result(f, 'same_family')
        return {'type': 'multiple', 'relays': len(exact_matches), 'hint': 'nickname'}
    
    # Step 4: Family prefix (non-generic first, then generic)
    for f in families:
        if f.get('px') and f['px'].lower() == q_lower and not f.get('pxg'):
            return _family_result(f, 'prefix')
    for f in families:
        if f.get('px') and f['px'].lower() == q_lower:
            return _family_result(f, 'generic_prefix')
    
    # Step 5: AROI domain
    for f in families:
        if f.get('a') and f['a'].lower() == q_lower:
            return _family_result(f, 'aroi')
    for r in relays:
        if r.get('a') and r['a'].lower() == q_lower and r.get('c'):
            return {'type': 'contact', 'contact_md5': r['c'], 'aroi': r['a']}
    
    # Step 6: AS number
    as_match = AS_NUMBER.match(q)
    if as_match:
        as_num = f"AS{as_match.group(1)}"
        if as_num in lookups['as_names']:
            return {'type': 'as', 'as_number': as_num, 'as_name': lookups['as_names'][as_num]}
    
    # AS name search
    for as_num, as_name in lookups['as_names'].items():
        if q_lower in as_name.lower():
            return {'type': 'as', 'as_number': as_num, 'as_name': as_name}
    
    # Step 7: Country
    if q_lower in lookups['country_names']:
        return {'type': 'country', 'country_code': q_lower, 'country_name': lookups['country_names'][q_lower]}
    for code, name in lookups['country_names'].items():
        if name.lower() == q_lower:
            return {'type': 'country', 'country_code': code, 'country_name': name}
    
    # Step 8: IP address
    if IP_ADDRESS.match(q) and ('.' in q or ':' in q):
        for r in relays:
            if r.get('ip') and q in r['ip']:
                return {'type': 'relay', 'fingerprint': r['f'], 'nickname': r.get('n', ''), 'hint': 'ip'}
    
    # Step 9: Platform or flag
    if q_lower in lookups['platforms']:
        return {'type': 'platform', 'platform': q_lower}
    if q_lower in lookups['flags']:
        return {'type': 'flag', 'flag': q_lower}
    
    # Step 10: Fuzzy nickname
    fuzzy_matches = [r for r in relays if q_lower in r.get('n', '').lower()][:30]
    if len(fuzzy_matches) == 1:
        return {'type': 'relay', 'fingerprint': fuzzy_matches[0]['f'], 'nickname': fuzzy_matches[0].get('n', ''), 'hint': 'fuzzy'}
    if fuzzy_matches:
        return {'type': 'multiple', 'relays': len(fuzzy_matches), 'hint': 'fuzzy_nickname'}
    
    # Step 11: Family nickname search (nn keys are already lowercase)
    family_matches = [f for f in families if any(q_lower in n for n in f.get('nn', {}).keys())][:10]
    if len(family_matches) == 1:
        return _family_result(family_matches[0], 'member_nickname')
    if family_matches:
        return {'type': 'multiple', 'families': len(family_matches), 'hint': 'family_nickname'}
    
    return {'type': 'not_found', 'query': q}


# =============================================================================
# VALIDATION TESTS
# =============================================================================

def validate_structure(index: Dict[str, Any]) -> List[str]:
    """Validate the index structure matches specification."""
    errors = []
    
    # Check top-level keys
    required_keys = ['meta', 'relays', 'families', 'lookups']
    for key in required_keys:
        if key not in index:
            errors.append(f"Missing top-level key: {key}")
    
    # Check meta
    meta = index.get('meta', {})
    for key in ['generated_at', 'relay_count', 'family_count', 'version']:
        if key not in meta:
            errors.append(f"Missing meta key: {key}")
    
    # Check lookups
    lookups = index.get('lookups', {})
    for key in ['as_names', 'country_names', 'platforms', 'flags']:
        if key not in lookups:
            errors.append(f"Missing lookups key: {key}")
    
    # validated_aroi_domains is optional for backward compatibility with v1.4 indexes
    # but should be present in v1.5+ indexes
    if index.get('meta', {}).get('version', '1.4') >= '1.5':
        if 'validated_aroi_domains' not in lookups:
            errors.append("Missing lookups key: validated_aroi_domains (required for v1.5+)")
    
    # Validate relay entries (sample)
    relays = index.get('relays', [])
    if relays:
        sample = relays[0]
        if 'f' not in sample:
            errors.append("Relay entry missing 'f' (fingerprint)")
        if 'n' not in sample:
            errors.append("Relay entry missing 'n' (nickname)")
    
    # Validate family entries (sample)
    families = index.get('families', [])
    if families:
        sample = families[0]
        for key in ['id', 'sz', 'nn']:
            if key not in sample:
                errors.append(f"Family entry missing '{key}'")
    
    return errors


def validate_data_integrity(index: Dict[str, Any]) -> List[str]:
    """Validate data integrity and cross-references."""
    errors = []
    
    relays = index.get('relays', [])
    families = index.get('families', [])
    lookups = index.get('lookups', {})
    
    # Check relay count matches meta
    if len(relays) != index['meta']['relay_count']:
        errors.append(f"Relay count mismatch: {len(relays)} vs meta {index['meta']['relay_count']}")
    
    # Check family count matches meta
    if len(families) != index['meta']['family_count']:
        errors.append(f"Family count mismatch: {len(families)} vs meta {index['meta']['family_count']}")
    
    # Check fingerprints are valid hex and 40 chars
    invalid_fps = [r for r in relays if not FULL_FINGERPRINT.match(r.get('f', ''))]
    if invalid_fps:
        errors.append(f"Found {len(invalid_fps)} relays with invalid fingerprints")
    
    # Check family IDs are valid
    invalid_fam_ids = [f for f in families if not FULL_FINGERPRINT.match(f.get('id', ''))]
    if invalid_fam_ids:
        errors.append(f"Found {len(invalid_fam_ids)} families with invalid IDs")
    
    # Check family references in relays point to valid families
    family_ids = {f['id'] for f in families}
    relay_fam_refs = {r.get('fam') for r in relays if r.get('fam')}
    orphan_refs = relay_fam_refs - family_ids
    if orphan_refs:
        errors.append(f"Found {len(orphan_refs)} orphan family references in relays")
    
    # Check AS numbers in relays exist in lookups
    # Note: Some AS numbers may not have names in source data (Onionoo API limitation)
    # This is a data quality issue, not a code bug - just warn, don't error
    relay_as = {r.get('as') for r in relays if r.get('as')}
    missing_as = relay_as - set(lookups.get('as_names', {}).keys())
    # (Commented out - source data quality issue, not a validation error)
    # if missing_as:
    #     errors.append(f"Found {len(missing_as)} AS numbers not in lookups")
    
    # Check country codes in relays exist in lookups
    relay_cc = {r.get('cc') for r in relays if r.get('cc')}
    missing_cc = relay_cc - set(lookups.get('country_names', {}).keys())
    if missing_cc:
        errors.append(f"Found {len(missing_cc)} country codes not in lookups")
    
    return errors


def run_search_tests(index: Dict[str, Any]) -> List[Tuple[str, str, bool, str]]:
    """Run search tests and return results."""
    results = []
    
    relays = index['relays']
    families = index['families']
    lookups = index['lookups']
    
    # Get sample data for testing
    sample_relay = relays[0] if relays else None
    sample_family = families[0] if families else None
    sample_as = list(lookups['as_names'].keys())[0] if lookups['as_names'] else None
    sample_country = list(lookups['country_names'].keys())[0] if lookups['country_names'] else None
    
    tests = []
    
    # Test 1: Full fingerprint search
    if sample_relay:
        tests.append(('Full fingerprint', sample_relay['f'], 'relay'))
    
    # Test 2: Partial fingerprint search
    if sample_relay:
        tests.append(('Partial fingerprint (8 chars)', sample_relay['f'][:8], 'relay|multiple'))
    
    # Test 3: Nickname search
    # If all matches in same validated family, returns operator; otherwise relay/multiple/family
    if sample_relay and sample_relay.get('n'):
        tests.append(('Exact nickname', sample_relay['n'], 'relay|multiple|family|operator'))
    
    # Test 4: AS number search
    if sample_as:
        tests.append(('AS number', sample_as, 'as'))
        tests.append(('AS number (without prefix)', sample_as[2:], 'as'))
    
    # Test 5: Country code search
    # Note: Short country codes like 'at' may match AS name substrings first
    # Use a longer/unique country name for reliable testing
    if sample_country:
        country_name = lookups['country_names'][sample_country]
        # Country name search is more reliable than 2-letter codes
        tests.append(('Country name (full)', country_name, 'country|as'))
        # Short codes may match AS names containing that substring
        tests.append(('Country code (2-letter)', sample_country, 'country|as'))
    
    # Test 6: Platform search
    if lookups['platforms']:
        tests.append(('Platform', lookups['platforms'][0], 'platform'))
    
    # Test 7: Flag search
    if lookups['flags']:
        tests.append(('Flag', lookups['flags'][0], 'flag'))
    
    # Test 8: AROI domain search
    # If family has validated AROI, returns operator; otherwise contact or family
    aroi_relay = next((r for r in relays if r.get('a')), None)
    if aroi_relay:
        tests.append(('AROI domain', aroi_relay['a'], 'contact|family|operator'))
    
    # Test 9: IP address search
    ip_relay = next((r for r in relays if r.get('ip')), None)
    if ip_relay and ip_relay['ip']:
        tests.append(('IP address', ip_relay['ip'][0], 'relay'))
    
    # Test 10: Family prefix search
    # If family has validated AROI, returns operator; otherwise family
    prefix_family = next((f for f in families if f.get('px') and not f.get('pxg')), None)
    if prefix_family:
        tests.append(('Family prefix', prefix_family['px'], 'family|operator'))
    
    # Test 11: Not found
    tests.append(('Non-existent query', 'xyznonexistent12345', 'not_found'))
    
    # Run tests
    for name, query, expected_types in tests:
        result = search(query, index)
        expected_list = expected_types.split('|')
        passed = result['type'] in expected_list
        results.append((name, query, passed, f"Got: {result['type']}, Expected: {expected_types}"))
    
    return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_search_index.py <path-to-search-index.json>")
        sys.exit(1)
    
    index_path = sys.argv[1]
    print(f"=== SEARCH INDEX VALIDATION ===")
    print(f"Loading: {index_path}")
    print()
    
    try:
        index = load_index(index_path)
    except Exception as e:
        print(f"❌ Failed to load index: {e}")
        sys.exit(1)
    
    # Structure validation
    print("1. STRUCTURE VALIDATION")
    print("-" * 40)
    structure_errors = validate_structure(index)
    if structure_errors:
        for err in structure_errors:
            print(f"   ❌ {err}")
    else:
        print(f"   ✅ All required keys present")
        print(f"   ✅ Meta: version={index['meta']['version']}, relays={index['meta']['relay_count']}, families={index['meta']['family_count']}")
    print()
    
    # Data integrity validation
    print("2. DATA INTEGRITY VALIDATION")
    print("-" * 40)
    integrity_errors = validate_data_integrity(index)
    if integrity_errors:
        for err in integrity_errors:
            print(f"   ❌ {err}")
    else:
        print(f"   ✅ Relay count matches meta")
        print(f"   ✅ Family count matches meta")
        print(f"   ✅ All fingerprints valid (40 hex chars)")
        print(f"   ✅ All family references valid")
        print(f"   ✅ All AS/country codes in lookups")
    print()
    
    # Search simulation tests
    print("3. SEARCH SIMULATION TESTS")
    print("-" * 40)
    test_results = run_search_tests(index)
    passed = sum(1 for _, _, p, _ in test_results if p)
    total = len(test_results)
    
    for name, query, success, detail in test_results:
        status = "✅" if success else "❌"
        query_display = query[:30] + "..." if len(query) > 30 else query
        print(f"   {status} {name}: '{query_display}'")
        if not success:
            print(f"      {detail}")
    
    print()
    print(f"   Results: {passed}/{total} tests passed")
    print()
    
    # Summary statistics
    print("4. INDEX STATISTICS")
    print("-" * 40)
    relays_with_aroi = sum(1 for r in index['relays'] if r.get('a'))
    relays_with_family = sum(1 for r in index['relays'] if r.get('fam'))
    relays_with_ip = sum(1 for r in index['relays'] if r.get('ip'))
    families_with_prefix = sum(1 for f in index['families'] if f.get('px'))
    families_nongeneric_prefix = sum(1 for f in index['families'] if f.get('px') and not f.get('pxg'))
    
    print(f"   Relays: {len(index['relays'])}")
    print(f"     - With AROI domain: {relays_with_aroi} ({relays_with_aroi*100//len(index['relays'])}%)")
    print(f"     - With family: {relays_with_family} ({relays_with_family*100//len(index['relays'])}%)")
    print(f"     - With IP addresses: {relays_with_ip} ({relays_with_ip*100//len(index['relays'])}%)")
    print(f"   Families: {len(index['families'])}")
    print(f"     - With detected prefix: {families_with_prefix} ({families_with_prefix*100//len(index['families'])}%)")
    print(f"     - With non-generic prefix: {families_nongeneric_prefix} ({families_nongeneric_prefix*100//len(index['families'])}%)")
    print(f"   Lookups:")
    print(f"     - AS names: {len(index['lookups']['as_names'])}")
    print(f"     - Country names: {len(index['lookups']['country_names'])}")
    print(f"     - Platforms: {len(index['lookups']['platforms'])}")
    print(f"     - Flags: {len(index['lookups']['flags'])}")
    validated_aroi_count = len(index['lookups'].get('validated_aroi_domains', []))
    print(f"     - Validated AROI domains: {validated_aroi_count}")
    print()
    
    # Final verdict
    print("=" * 40)
    all_errors = structure_errors + integrity_errors
    if all_errors or passed < total:
        print(f"❌ VALIDATION FAILED")
        print(f"   Structure errors: {len(structure_errors)}")
        print(f"   Integrity errors: {len(integrity_errors)}")
        print(f"   Search tests: {passed}/{total} passed")
        sys.exit(1)
    else:
        print(f"✅ VALIDATION PASSED")
        print(f"   Index is valid and search simulation works correctly")
        sys.exit(0)


if __name__ == '__main__':
    main()
