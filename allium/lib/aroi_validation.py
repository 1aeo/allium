"""
File: aroi_validation.py

AROI (Authenticated Relay Operator Identifier) Validation Module
Fetches and processes AROI validation data from aroivalidator.1aeo.com
Provides validation metrics for network health dashboard

Uses existing infrastructure from workers.py and file_io_utils.py
Functional approach for simplicity and maintainability
"""

import json
import os
import time
import urllib.request
import urllib.error
from typing import Dict, Optional, List
from datetime import datetime

DEFAULT_AROI_VALIDATION_URL = "https://aroivalidator.1aeo.com/latest.json"
CACHE_FILE_NAME = "aroi_validation_cache.json"
CACHE_DURATION_HOURS = 1


def fetch_aroi_validation_data(cache_dir="./cache", 
                                 url=DEFAULT_AROI_VALIDATION_URL,
                                 force_refresh=False):
    """
    Fetch AROI validation data from API with file-based caching.
    
    Args:
        cache_dir: Directory to store cache file
        url: API endpoint URL
        force_refresh: Force fetch from API even if cache is valid
        
    Returns:
        Dict containing validation data or None if fetch failed
    """
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, CACHE_FILE_NAME)
    
    # Check cache first
    if not force_refresh and os.path.exists(cache_path):
        try:
            cache_age = time.time() - os.path.getmtime(cache_path)
            if cache_age < CACHE_DURATION_HOURS * 3600:
                with open(cache_path, 'r') as f:
                    cached_data = json.load(f)
                    if _validate_structure(cached_data):
                        return cached_data
        except (OSError, json.JSONDecodeError) as e:
            print(f"⚠️  Warning: Failed to read AROI validation cache: {e}")
    
    # Fetch from API using same pattern as workers.py
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Allium/1.0'})
        api_response = urllib.request.urlopen(req, timeout=30).read()
        data = json.loads(api_response.decode('utf-8'))
        
        if not _validate_structure(data):
            print("❌ Error: Invalid AROI validation data structure")
            return None
        
        # Cache the data
        with open(cache_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return data
        
    except urllib.error.URLError as e:
        print(f"⚠️  AROI Validation: Network error: {e}")
        return None
    except Exception as e:
        print(f"⚠️  AROI Validation: Unexpected error: {e}")
        return None


def _validate_structure(data):
    """Validate data structure has required fields."""
    if not isinstance(data, dict):
        return False
    required_keys = ['metadata', 'statistics', 'results']
    return all(key in data for key in required_keys)


def _calc_percentage(count: int, total: int) -> float:
    """Calculate percentage safely."""
    return (count / total * 100) if total > 0 else 0.0


def _check_aroi_fields(contact: str) -> Dict[str, bool]:
    """
    Check which AROI fields are present in contact string.
    
    Returns:
        Dict with keys: 'has_ciissversion', 'has_proof', 'has_url', 'complete'
    """
    import re
    
    if not contact:
        return {'has_ciissversion': False, 'has_proof': False, 'has_url': False, 'complete': False}
    
    has_ciissversion = bool(re.search(r'\bciissversion:2\b', contact, re.IGNORECASE))
    has_proof = bool(re.search(r'\bproof:(dns-rsa|uri-rsa)\b', contact, re.IGNORECASE))
    has_url = bool(re.search(r'\burl:(?:https?://)?([^,\s]+)', contact, re.IGNORECASE))
    
    return {
        'has_ciissversion': has_ciissversion,
        'has_proof': has_proof,
        'has_url': has_url,
        'complete': has_ciissversion and has_proof and has_url
    }


def _categorize_by_missing_fields(aroi_fields: Dict[str, bool]) -> str:
    """
    Helper function to categorize relay based on which AROI fields are missing.
    Eliminates code duplication.
    
    Args:
        aroi_fields: Dict from _check_aroi_fields() with has_ciissversion, has_proof, has_url
        
    Returns:
        Category string based on missing fields
    """
    fields_present = sum([aroi_fields['has_ciissversion'], 
                         aroi_fields['has_proof'], 
                         aroi_fields['has_url']])
    
    if fields_present <= 1:
        # Missing 2+ fields or no fields at all
        return 'no_aroi'
    
    # Has exactly 2 fields (missing exactly 1) - be specific
    if not aroi_fields['has_proof']:
        return 'no_proof'
    elif not aroi_fields['has_url']:
        return 'no_domain'
    elif not aroi_fields['has_ciissversion']:
        return 'no_ciissversion'
    
    # Shouldn't reach here if logic is correct, but defensive
    return 'no_aroi'


def _categorize_relay_by_validation(relay: Dict, validation_map: Dict) -> str:
    """
    Categorize a relay by its validation status.
    
    AROI Standard: A relay must have all 3 required fields for AROI validation:
    1. ciissversion:2
    2. proof:dns-rsa or proof:uri-rsa
    3. url:<domain>
    
    Args:
        relay: Relay dictionary from Onionoo API
        validation_map: Map of fingerprint -> validation result
        
    Returns:
        Category string:
        - 'validated': Has all 3 AROI fields and validation succeeded
        - 'unvalidated': Has all 3 AROI fields but validation failed (SSL, DNS, etc.)
        - 'no_proof': Has ciissversion + url but missing proof (exactly 1 field missing)
        - 'no_domain': Has ciissversion + proof but missing url (exactly 1 field missing)
        - 'no_ciissversion': Has proof + url but missing ciissversion (exactly 1 field missing)
        - 'no_aroi': Missing 2+ fields or no contact at all
    """
    fingerprint = relay.get('fingerprint')
    aroi_domain = relay.get('aroi_domain', 'none')
    contact = relay.get('contact', '')
    
    # Check if has complete AROI setup (all 3 fields)
    has_complete_aroi = aroi_domain and aroi_domain != 'none'
    
    if fingerprint in validation_map:
        result = validation_map[fingerprint]
        if result.get('valid', False):
            return 'validated'
        
        error = result.get('error', '')
        
        # If validation attempted but relay has complete AROI, it's a real validation failure
        if has_complete_aroi:
            return 'unvalidated'
        
        # Check which specific fields are missing
        if error in ('No contact information', 'Missing AROI fields'):
            aroi_fields = _check_aroi_fields(contact)
            if not aroi_fields['complete']:
                return _categorize_by_missing_fields(aroi_fields)
            return 'no_aroi'
        else:
            # Real validation error (not missing fields)
            return 'unvalidated'
    else:
        # Not in validation map - use local analysis
        if has_complete_aroi:
            return 'unvalidated'
        
        # Check which fields are present - use helper to avoid duplication
        aroi_fields = _check_aroi_fields(contact)
        return _categorize_by_missing_fields(aroi_fields)


def calculate_aroi_validation_metrics(relays: List[Dict], validation_data: Optional[Dict] = None, 
                                       calculate_operator_metrics: bool = True) -> Dict:
    """
    Calculate AROI validation metrics for network health dashboard.
    
    Analyzes relay fingerprints against validation data to determine:
    - RELAY-level: How many relays have valid AROI proofs (dns-rsa or uri-rsa)
    - OPERATOR-level: How many operators (domains) are validated/invalid (if enabled)
    - Success rates by proof type (dns-rsa vs uri-rsa)
    - Failure breakdown by proof type
    
    Args:
        relays: List of relay dictionaries from Onionoo API
        validation_data: Optional validation data from aroivalidator.1aeo.com
        calculate_operator_metrics: If True, also calculate operator-level metrics in same pass
        
    Returns:
        Dict containing validation metrics for health dashboard (relay + operator level)
    """
    # Initialize metrics with safe defaults
    metrics = {
        'aroi_validated_count': 0,
        'aroi_unvalidated_count': 0,
        'aroi_no_proof_count': 0,
        'aroi_no_domain_count': 0,
        'aroi_no_ciissversion_count': 0,
        'relays_no_aroi': 0,
        'aroi_validated_percentage': 0.0,
        'aroi_unvalidated_percentage': 0.0,
        'aroi_no_proof_percentage': 0.0,
        'aroi_no_domain_percentage': 0.0,
        'aroi_no_ciissversion_percentage': 0.0,
        'relays_no_aroi_percentage': 0.0,
        'aroi_validation_success_rate': 0.0,
        'dns_rsa_success_rate': 0.0,
        'uri_rsa_success_rate': 0.0,
        'dns_rsa_total': 0,
        'dns_rsa_valid': 0,
        'uri_rsa_total': 0,
        'uri_rsa_valid': 0,
        'validation_data_available': False,
        'validation_timestamp': 'Unknown',
        'top_3_aroi_countries': [],  # Default empty list for template
        'relay_error_top5': [],  # Top 5 relay error reasons
        'operator_error_top5': []  # Top 5 operator error reasons
    }
    
    if not relays:
        return metrics
    
    total_relays = len(relays)
    
    # If no validation data available, return early with basic counts
    if not validation_data or 'results' not in validation_data:
        # Count relays with/without AROI based on contact info
        unique_aroi_domains = set()  # Track for operator metrics
        
        for relay in relays:
            aroi_domain = relay.get('aroi_domain', 'none')
            contact = relay.get('contact', '')
            
            if aroi_domain and aroi_domain != 'none':
                # Has AROI domain (all 3 fields) but no validation data available
                metrics['aroi_unvalidated_count'] += 1
                if calculate_operator_metrics:
                    unique_aroi_domains.add(aroi_domain)
            else:
                # Missing some or all AROI fields - categorize specifically using helper
                aroi_fields = _check_aroi_fields(contact)
                category = _categorize_by_missing_fields(aroi_fields)
                if category == 'no_proof':
                    metrics['aroi_no_proof_count'] += 1
                elif category == 'no_domain':
                    metrics['aroi_no_domain_count'] += 1
                elif category == 'no_ciissversion':
                    metrics['aroi_no_ciissversion_count'] += 1
                else:  # no_aroi
                    metrics['relays_no_aroi'] += 1
        
        # Calculate percentages using helper function
        metrics['aroi_unvalidated_percentage'] = _calc_percentage(metrics['aroi_unvalidated_count'], total_relays)
        metrics['aroi_no_proof_percentage'] = _calc_percentage(metrics['aroi_no_proof_count'], total_relays)
        metrics['aroi_no_domain_percentage'] = _calc_percentage(metrics['aroi_no_domain_count'], total_relays)
        metrics['aroi_no_ciissversion_percentage'] = _calc_percentage(metrics['aroi_no_ciissversion_count'], total_relays)
        metrics['relays_no_aroi_percentage'] = _calc_percentage(metrics['relays_no_aroi'], total_relays)
        
        # Add operator-level metrics even without validation data
        if calculate_operator_metrics:
            metrics['unique_aroi_domains_count'] = len(unique_aroi_domains)
            metrics['validated_aroi_domains_count'] = 0  # Can't validate without data
            metrics['invalid_aroi_domains_count'] = len(unique_aroi_domains)  # All unknown
            metrics['validated_aroi_domains_percentage'] = 0.0
            metrics['invalid_aroi_domains_percentage'] = 100.0 if len(unique_aroi_domains) > 0 else 0.0
            metrics['top_operators_text'] = "Validation data not available"
            metrics['_validated_domain_set'] = set()  # Empty set for IPv6 calculation
        
        return metrics
    
    # Extract validation metadata
    metadata = validation_data.get('metadata', {})
    statistics = validation_data.get('statistics', {})
    
    metrics['validation_data_available'] = True
    metrics['validation_timestamp'] = metadata.get('timestamp', 'Unknown')
    
    # Extract proof type statistics from validation data
    proof_types = statistics.get('proof_types', {})
    
    # DNS-RSA statistics
    dns_rsa_stats = proof_types.get('dns_rsa', {})
    metrics['dns_rsa_total'] = dns_rsa_stats.get('total', 0)
    metrics['dns_rsa_valid'] = dns_rsa_stats.get('valid', 0)
    metrics['dns_rsa_success_rate'] = dns_rsa_stats.get('success_rate', 0.0)
    
    # URI-RSA statistics
    uri_rsa_stats = proof_types.get('uri_rsa', {})
    metrics['uri_rsa_total'] = uri_rsa_stats.get('total', 0)
    metrics['uri_rsa_valid'] = uri_rsa_stats.get('valid', 0)
    metrics['uri_rsa_success_rate'] = uri_rsa_stats.get('success_rate', 0.0)
    
    # Build fingerprint -> validation result mapping for O(1) lookup
    validation_map = {}
    for result in validation_data.get('results', []):
        fingerprint = result.get('fingerprint')
        if fingerprint:
            validation_map[fingerprint] = result
    
    # Initialize operator-level tracking (if requested)
    unique_aroi_domains = set()
    domain_has_valid_relay = {}
    domain_relays = {}
    domain_failure_reasons = {}
    domain_country = {}  # Track country for each validated domain
    
    # SINGLE PASS: Process each relay for BOTH relay-level AND operator-level metrics
    for relay in relays:
        category = _categorize_relay_by_validation(relay, validation_map)
        
        # Relay-level counting
        if category == 'validated':
            metrics['aroi_validated_count'] += 1
        elif category == 'unvalidated':
            metrics['aroi_unvalidated_count'] += 1
        elif category == 'no_proof':
            metrics['aroi_no_proof_count'] += 1
        elif category == 'no_domain':
            metrics['aroi_no_domain_count'] += 1
        elif category == 'no_ciissversion':
            metrics['aroi_no_ciissversion_count'] += 1
        else:  # no_aroi
            metrics['relays_no_aroi'] += 1
        
        # Operator-level tracking (in same loop for efficiency)
        if calculate_operator_metrics:
            aroi_domain = relay.get('aroi_domain', 'none')
            
            # Only track operators with all 3 required AROI fields (ciissversion:2, proof, url)
            # aroi_domain is only set if _simple_aroi_parsing found all 3 fields
            if aroi_domain and aroi_domain != 'none':
                unique_aroi_domains.add(aroi_domain)
                
                if aroi_domain not in domain_has_valid_relay:
                    domain_has_valid_relay[aroi_domain] = False
                    domain_relays[aroi_domain] = []
                    domain_failure_reasons[aroi_domain] = {}
                
                # Track country for this domain (use first relay's country)
                if aroi_domain not in domain_country:
                    country = relay.get('country', 'unknown')
                    if country and country != 'unknown':
                        domain_country[aroi_domain] = country.upper()
                
                fp = relay.get('fingerprint')
                domain_relays[aroi_domain].append(fp)
                
                # Check validation status
                if fp in validation_map:
                    result = validation_map[fp]
                    if result.get('valid', False):
                        domain_has_valid_relay[aroi_domain] = True
                    else:
                        error = result.get('error', 'Unknown error')
                        # Only track actual validation failures, not missing AROI fields
                        # (relays with "Missing AROI fields" shouldn't have aroi_domain set, but defensive check)
                        if error not in ('Missing AROI fields', 'No contact information'):
                            domain_failure_reasons[aroi_domain][error] = domain_failure_reasons[aroi_domain].get(error, 0) + 1
    
    # Calculate percentages using helper function
    metrics['aroi_validated_percentage'] = _calc_percentage(metrics['aroi_validated_count'], total_relays)
    metrics['aroi_unvalidated_percentage'] = _calc_percentage(metrics['aroi_unvalidated_count'], total_relays)
    metrics['aroi_no_proof_percentage'] = _calc_percentage(metrics['aroi_no_proof_count'], total_relays)
    metrics['aroi_no_domain_percentage'] = _calc_percentage(metrics['aroi_no_domain_count'], total_relays)
    metrics['aroi_no_ciissversion_percentage'] = _calc_percentage(metrics['aroi_no_ciissversion_count'], total_relays)
    metrics['relays_no_aroi_percentage'] = _calc_percentage(metrics['relays_no_aroi'], total_relays)
    
    # Calculate overall validation success rate
    # Success rate = valid relays / (valid + invalid with AROI attempts)
    total_aroi_attempts = metrics['dns_rsa_total'] + metrics['uri_rsa_total']
    total_aroi_valid = metrics['dns_rsa_valid'] + metrics['uri_rsa_valid']
    
    if total_aroi_attempts > 0:
        metrics['aroi_validation_success_rate'] = (total_aroi_valid / total_aroi_attempts * 100)
    else:
        # Use metadata success rate if available
        metrics['aroi_validation_success_rate'] = metadata.get('success_rate', 0.0)
    
    # Calculate operator-level metrics (if requested)
    if calculate_operator_metrics:
        # Count validated vs invalid domains
        validated_aroi_domains = sum(1 for has_valid in domain_has_valid_relay.values() if has_valid)
        invalid_aroi_domains = len(unique_aroi_domains) - validated_aroi_domains
        
        # Build error details from existing domain_failure_reasons (already populated in main loop)
        relay_errors = {}  # error -> relay count
        operator_errors = {}  # error -> operator count
        
        # Process failed operators to get both relay and operator error counts
        for domain, has_valid in domain_has_valid_relay.items():
            if not has_valid:
                for error, relay_count in domain_failure_reasons.get(domain, {}).items():
                    relay_errors[error] = relay_errors.get(error, 0) + relay_count
                    operator_errors[error] = operator_errors.get(error, 0) + 1
        
        # Store top 5 for tooltips
        metrics['relay_error_top5'] = sorted(relay_errors.items(), key=lambda x: x[1], reverse=True)[:5]
        metrics['operator_error_top5'] = sorted(operator_errors.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Calculate top operators by relay count
        domain_relay_counts = [(domain, len(fps)) for domain, fps in domain_relays.items()]
        domain_relay_counts.sort(key=lambda x: x[1], reverse=True)
        top_ops = [f"{domain} ({count:,} relays)" for domain, count in domain_relay_counts[:4]]
        top_operators_text = ", ".join(top_ops) if top_ops else "No data available"
        
        # Add operator metrics
        metrics['unique_aroi_domains_count'] = len(unique_aroi_domains)
        metrics['validated_aroi_domains_count'] = validated_aroi_domains
        metrics['invalid_aroi_domains_count'] = invalid_aroi_domains
        
        if len(unique_aroi_domains) > 0:
            metrics['validated_aroi_domains_percentage'] = (validated_aroi_domains / len(unique_aroi_domains) * 100)
            metrics['invalid_aroi_domains_percentage'] = (invalid_aroi_domains / len(unique_aroi_domains) * 100)
        else:
            metrics['validated_aroi_domains_percentage'] = 0.0
            metrics['invalid_aroi_domains_percentage'] = 0.0
        
        metrics['top_operators_text'] = top_operators_text
        
        # Build validated domain set once for both IPv6 and country calculations
        validated_domains = {d for d, valid in domain_has_valid_relay.items() if valid}
        metrics['_validated_domain_set'] = validated_domains
        
        # Calculate top 3 countries by validated AROI operator count
        country_counts = {}
        for domain in validated_domains:
            if domain in domain_country:
                country_counts[domain_country[domain]] = country_counts.get(domain_country[domain], 0) + 1
        
        # Sort and format top 3 for template
        metrics['top_3_aroi_countries'] = [
            {'rank': i, 'country_code': cc, 'count': cnt, 
             'percentage': (cnt / validated_aroi_domains * 100) if validated_aroi_domains > 0 else 0.0}
            for i, (cc, cnt) in enumerate(sorted(country_counts.items(), key=lambda x: x[1], reverse=True)[:3], 1)
        ]
    
    # Store validation_map for reuse by contact pages (avoids rebuilding 3,000+ times)
    metrics['_validation_map'] = validation_map
    
    return metrics


def _format_timestamp(timestamp_str):
    """Format ISO timestamp to human-readable format."""
    if not timestamp_str:
        return 'Unknown'
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M UTC')
    except (ValueError, AttributeError):
        return timestamp_str


def get_contact_validation_status(relays: List[Dict], validation_data: Optional[Dict] = None, validation_map: Optional[Dict] = None) -> Dict:
    """
    Get validation status for a specific contact's relays.
    
    Analyzes all relays belonging to a contact and returns:
    - Overall validation status (validated, partially_validated, unvalidated)
    - List of validated relays with proof details
    - List of unvalidated relays with error messages
    - Summary statistics
    
    Args:
        relays: List of relay dictionaries for this contact
        validation_data: Optional validation data from aroivalidator.1aeo.com
        validation_map: Optional pre-built fingerprint -> validation result map (avoids rebuilding)
        
    Returns:
        Dict containing contact-level validation information
    """
    result = {
        'has_aroi': False,
        'validation_status': 'no_aroi',  # no_aroi, validated, partially_validated, unvalidated
        'validated_relays': [],
        'unvalidated_relays': [],
        'validation_summary': {
            'total_relays': len(relays),
            'relays_with_aroi': 0,
            'validated_count': 0,
            'unvalidated_count': 0,
            'validation_rate': 0.0
        },
        'validation_available': False,
        'show_detailed_errors': True  # Show detailed error list (False if all errors are just "Missing AROI fields")
    }
    
    if not relays:
        return result
    
    # Use pre-built validation_map if provided (much faster - avoids rebuilding map 3,000+ times)
    if validation_map is None:
        # FALLBACK: Build fingerprint -> validation result mapping
        # This is used for testing or when validation_map not available
        validation_map = {}
        if validation_data and 'results' in validation_data:
            for val_result in validation_data.get('results', []):
                fingerprint = val_result.get('fingerprint')
                if fingerprint:
                    validation_map[fingerprint] = val_result
            result['validation_available'] = True
    else:
        # Using shared map
        result['validation_available'] = len(validation_map) > 0
    
    # OPTIMIZED: Single pass through relays - check AROI existence AND build validation lists
    all_missing_aroi_fields = True  # Track if all errors are "Missing AROI fields"
    
    for relay in relays:
        fingerprint = relay.get('fingerprint')
        aroi_domain = relay.get('aroi_domain', 'none')
        nickname = relay.get('nickname', 'Unnamed')
        
        # AROI Standard: A relay must have ciissversion:2, proof:dns-rsa/uri-rsa, and url:domain
        # Only consider relays with proper AROI setup (aroi_domain != 'none')
        # The validator checks ALL relays, including ones without AROI setup
        has_aroi_setup = aroi_domain and aroi_domain != 'none'
        
        if not has_aroi_setup:
            # Relay doesn't have all 3 required AROI fields, skip validation check
            continue
        
        # Relay has proper AROI setup (all 3 required fields present)
        result['has_aroi'] = True
        result['validation_summary']['relays_with_aroi'] += 1
        
        # Check validation status
        if fingerprint not in validation_map:
            # Has AROI domain but not in validation data (shouldn't happen normally)
            continue
        
        val_result = validation_map[fingerprint]
        
        if val_result.get('valid', False):
            # Relay is validated
            result['validation_summary']['validated_count'] += 1
            result['validated_relays'].append({
                'fingerprint': fingerprint,
                'nickname': nickname,
                'aroi_domain': aroi_domain if aroi_domain != 'none' else 'unknown',
                'proof_type': val_result.get('proof_type', 'unknown'),
                'proof_uri': val_result.get('proof_uri', ''),
            })
        else:
            # Relay has validation error
            error = val_result.get('error', 'Unknown error')
            result['validation_summary']['unvalidated_count'] += 1
            result['unvalidated_relays'].append({
                'fingerprint': fingerprint,
                'nickname': nickname,
                'aroi_domain': aroi_domain if aroi_domain != 'none' else 'unknown',
                'error': error,
                'proof_type': val_result.get('proof_type', 'unknown'),
            })
            # Track if any error is NOT "Missing AROI fields"
            if error.strip() != 'Missing AROI fields':
                all_missing_aroi_fields = False
    
    # Early exit if no AROI found
    if not result['has_aroi']:
        return result
    
    # Calculate validation rate
    if result['validation_summary']['relays_with_aroi'] > 0:
        result['validation_summary']['validation_rate'] = (
            result['validation_summary']['validated_count'] / 
            result['validation_summary']['relays_with_aroi'] * 100
        )
    
    # Determine overall status
    if result['validation_summary']['validated_count'] == result['validation_summary']['relays_with_aroi']:
        result['validation_status'] = 'validated'
    elif result['validation_summary']['validated_count'] > 0:
        result['validation_status'] = 'partially_validated'
    else:
        result['validation_status'] = 'unvalidated'
    
    # Set show_detailed_errors flag (already computed during loop)
    if result['unvalidated_relays'] and all_missing_aroi_fields:
        result['show_detailed_errors'] = False
    
    return result
