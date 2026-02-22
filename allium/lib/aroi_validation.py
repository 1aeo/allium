"""
File: aroi_validation.py

AROI (Authenticated Relay Operator Identifier) Validation Module
Fetches and processes AROI validation data from aroivalidator.1aeo.com
Provides validation metrics for network health dashboard

Uses existing infrastructure from workers.py and file_io_utils.py
Functional approach for simplicity and maintainability
"""

import json
import re
from collections import defaultdict
from typing import Dict, Optional, List
from datetime import datetime


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


def _categorize_by_missing_fields(aroi_fields: Dict[str, bool], has_contact: bool) -> str:
    """
    Helper function to categorize relay based on which AROI fields are missing.
    Eliminates code duplication.
    
    Args:
        aroi_fields: Dict from _check_aroi_fields() with has_ciissversion, has_proof, has_url
        has_contact: Boolean indicating if relay has a contact field at all
        
    Returns:
        Category string based on missing fields
    """
    fields_present = sum([aroi_fields['has_ciissversion'], 
                         aroi_fields['has_proof'], 
                         aroi_fields['has_url']])
    
    # First check: No contact field at all
    if not has_contact:
        return 'no_contact'  # Empty/missing contact field
    
    # Has contact, now check AROI field presence
    if fields_present == 0:
        return 'no_aroi_info'  # Has contact but no AROI fields at all
    elif fields_present == 1:
        return 'missing_two_aroi'  # Has 1 AROI field, missing 2
    
    # Has exactly 2 fields (missing exactly 1) - be specific
    if not aroi_fields['has_proof']:
        return 'no_proof'
    elif not aroi_fields['has_url']:
        return 'no_domain'
    elif not aroi_fields['has_ciissversion']:
        return 'no_ciissversion'
    
    # Shouldn't reach here if logic is correct, but defensive
    return 'no_aroi'


def _deduplicate_fingerprint_not_found_error(error: str) -> str:
    """
    Deduplicate error messages that repeat "Fingerprint not found in URL" for multiple URLs.
    
    Example input:
        "Fingerprint not found in https://prsv.ch/.../rsa-fingerprint.txt; Fingerprint not found in https://www.prsv.ch/.../rsa-fingerprint.txt"
    
    Example output:
        "Fingerprint not found in https://prsv.ch/.../rsa-fingerprint.txt, https://www.prsv.ch/.../rsa-fingerprint.txt"
    """
    # Pattern to match "Fingerprint not found in URL" segments separated by semicolons
    pattern = r'Fingerprint not found in ([^;]+)'
    matches = re.findall(pattern, error)
    
    if len(matches) > 1:
        # Multiple "Fingerprint not found" messages - combine the URLs
        urls = [url.strip() for url in matches]
        return "Fingerprint not found in " + ", ".join(urls)
    
    # No deduplication needed
    return error


def _simplify_error_message(error: str) -> tuple:
    """
    Simplify a verbose error message into a short description with protocol prefix.
    
    Returns:
        Tuple of (simplified_message, proof_type) where proof_type is 'dns', 'uri', or 'other'
    """
    e = error.lower()
    
    # DNS-specific errors (check first as they're more specific)
    if 'nxdomain' in e or 'no such domain' in e:
        return ("DNS: Domain not found (NXDOMAIN)", 'dns')
    if 'servfail' in e:
        return ("DNS: Server failure (SERVFAIL)", 'dns')
    if 'txt record' in e or ('txt' in e and 'dns' in e):
        return ("DNS: TXT record not found", 'dns') if 'not found' in e or 'missing' in e else ("DNS: TXT record error", 'dns')
    if 'dns' in e and 'lookup' in e:
        return ("DNS: Lookup failed", 'dns')
    
    # SSL/TLS errors - check for SSLV3_ALERT_HANDSHAKE_FAILURE specifically
    if 'sslv3_alert_handshake_failure' in e or ('ssl' in e and 'handshake' in e and 'alert' in e):
        return ("URI: SSL/TLS v3 handshake failed", 'uri')
    if 'ssl' in e and ('handshake' in e or 'alert' in e):
        return ("URI: SSL/TLS handshake failed", 'uri')
    if 'certificate' in e:
        return ("URI: SSL certificate error", 'uri')
    
    # HTTP errors (check after DNS patterns)
    if '404' in error or ('not found' in e and 'dns' not in e and 'txt' not in e):
        return ("URI: Fingerprint file not found (404)", 'uri') if 'fingerprint' in e else ("URI: Proof file not found (404)", 'uri')
    if '403' in error or 'forbidden' in e:
        return ("URI: Access forbidden (403)", 'uri')
    if 'connection refused' in e or 'refused' in e:
        return ("URI: Connection refused", 'uri')
    if 'timeout' in e:
        return ("URI: Connection timeout", 'uri')
    if 'max retries exceeded' in e:
        return ("URI: Server unreachable", 'uri')
    if 'name or service not known' in e or 'nameresolutionerror' in e:
        return ("URI: Domain resolution failed", 'uri')
    
    # Fingerprint errors
    if 'fingerprint' in e:
        if 'mismatch' in e or 'does not match' in e:
            return ("DNS: Fingerprint mismatch", 'dns') if 'http' not in e and 'uri' not in e else ("URI: Fingerprint mismatch", 'uri')
        if 'not found' in e:
            return ("URI: Fingerprint not in proof", 'uri')
    
    # Generic HTTP errors
    if 'failed to fetch' in e or ('http' in e and 'dns' not in e) or 'https' in e:
        return ("URI: Connection error", 'uri')
    
    # Unknown - truncate if too long
    return (error[:47] + "...", 'other') if len(error) > 50 else (error, 'other')


def _simplify_and_categorize_errors(errors: Dict[str, int]) -> Dict[str, Dict[str, int]]:
    """
    Simplify error messages and categorize them by proof type.
    
    Args:
        errors: Dict mapping raw error message -> count
        
    Returns:
        Dict with keys 'all', 'dns', 'uri' mapping simplified error -> count
    """
    result = {'all': {}, 'dns': {}, 'uri': {}}
    
    for raw_error, count in errors.items():
        simplified, proof_type = _simplify_error_message(raw_error)
        
        # Add to 'all' category
        result['all'][simplified] = result['all'].get(simplified, 0) + count
        
        # Add to specific proof type category
        if proof_type in ('dns', 'uri'):
            result[proof_type][simplified] = result[proof_type].get(simplified, 0) + count
    
    return result


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
                has_contact = bool(contact and contact.strip())
                return _categorize_by_missing_fields(aroi_fields, has_contact)
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
        has_contact = bool(contact and contact.strip())
        return _categorize_by_missing_fields(aroi_fields, has_contact)


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
        'relays_no_contact': 0,
        'relays_no_aroi_info': 0,
        'relays_missing_two_aroi': 0,
        'aroi_validated_percentage': 0.0,
        'aroi_unvalidated_percentage': 0.0,
        'aroi_no_proof_percentage': 0.0,
        'aroi_no_domain_percentage': 0.0,
        'aroi_no_ciissversion_percentage': 0.0,
        'relays_no_contact_percentage': 0.0,
        'relays_no_aroi_info_percentage': 0.0,
        'relays_missing_two_aroi_percentage': 0.0,
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
        'relay_error_top5': [],  # Top 5 relay error reasons (simplified)
        'operator_error_top5': [],  # Top 5 operator error reasons (simplified)
        'dns_error_top5': [],  # Top 5 DNS-RSA specific errors
        'uri_error_top5': [],  # Top 5 URI-RSA specific errors
        'no_aroi_reasons_top5': []  # Top reasons relays have no AROI
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
                has_contact = bool(contact and contact.strip())
                category = _categorize_by_missing_fields(aroi_fields, has_contact)
                if category == 'no_proof':
                    metrics['aroi_no_proof_count'] += 1
                elif category == 'no_domain':
                    metrics['aroi_no_domain_count'] += 1
                elif category == 'no_ciissversion':
                    metrics['aroi_no_ciissversion_count'] += 1
                elif category == 'no_contact':
                    metrics['relays_no_contact'] += 1
                elif category == 'no_aroi_info':
                    metrics['relays_no_aroi_info'] += 1
                elif category == 'missing_two_aroi':
                    metrics['relays_missing_two_aroi'] += 1
        
        # Calculate percentages using helper function
        metrics['aroi_unvalidated_percentage'] = _calc_percentage(metrics['aroi_unvalidated_count'], total_relays)
        metrics['aroi_no_proof_percentage'] = _calc_percentage(metrics['aroi_no_proof_count'], total_relays)
        metrics['aroi_no_domain_percentage'] = _calc_percentage(metrics['aroi_no_domain_count'], total_relays)
        metrics['aroi_no_ciissversion_percentage'] = _calc_percentage(metrics['aroi_no_ciissversion_count'], total_relays)
        metrics['relays_no_contact_percentage'] = _calc_percentage(metrics['relays_no_contact'], total_relays)
        metrics['relays_no_aroi_info_percentage'] = _calc_percentage(metrics['relays_no_aroi_info'], total_relays)
        metrics['relays_missing_two_aroi_percentage'] = _calc_percentage(metrics['relays_missing_two_aroi'], total_relays)
        
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
    operator_error_domains = defaultdict(set)
    
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
        elif category == 'no_contact':
            metrics['relays_no_contact'] += 1
        elif category == 'no_aroi_info':
            metrics['relays_no_aroi_info'] += 1
        elif category == 'missing_two_aroi':
            metrics['relays_missing_two_aroi'] += 1
        
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
                # relay["country"] is already UPPERCASE from _preprocess_template_data()
                if aroi_domain not in domain_country:
                    country = relay.get('country', 'unknown')
                    if country and country != 'unknown':
                        domain_country[aroi_domain] = country
                
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
        metrics['relays_no_contact_percentage'] = _calc_percentage(metrics['relays_no_contact'], total_relays)
        metrics['relays_no_aroi_info_percentage'] = _calc_percentage(metrics['relays_no_aroi_info'], total_relays)
        metrics['relays_missing_two_aroi_percentage'] = _calc_percentage(metrics['relays_missing_two_aroi'], total_relays)
    
    # Build no_aroi_reasons_top5 from the category counts
    no_aroi_reasons = [
        ("No contact info", metrics['relays_no_contact']),
        ("No AROI info", metrics['relays_no_aroi_info']),
        ("Missing 2 AROI fields", metrics['relays_missing_two_aroi']),
        ("Missing proof field (has domain + ciissversion)", metrics['aroi_no_proof_count']),
        ("Missing domain/URL field (has proof + ciissversion)", metrics['aroi_no_domain_count']),
        ("Missing ciissversion (has proof + domain)", metrics['aroi_no_ciissversion_count']),
    ]
    # Filter out zero counts and sort by count descending
    metrics['no_aroi_reasons_top5'] = sorted(
        [(reason, count) for reason, count in no_aroi_reasons if count > 0],
        key=lambda x: x[1],
        reverse=True
    )[:5]
    
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
        
        # Process failed operators to get both relay and operator error counts
        for domain, has_valid in domain_has_valid_relay.items():
            if not has_valid:
                seen_simplified_errors = set()
                for error, relay_count in domain_failure_reasons.get(domain, {}).items():
                    relay_errors[error] = relay_errors.get(error, 0) + relay_count
                    simplified_error, _ = _simplify_error_message(error)
                    if simplified_error not in seen_simplified_errors:
                        operator_error_domains[simplified_error].add(domain)
                        seen_simplified_errors.add(simplified_error)
        
        # Simplify error messages and categorize by proof type
        simplified_relay_errors = _simplify_and_categorize_errors(relay_errors)
        
        # Store top 5 for general tooltips (simplified messages)
        metrics['relay_error_top5'] = sorted(simplified_relay_errors['all'].items(), key=lambda x: x[1], reverse=True)[:5]
        metrics['operator_error_top5'] = sorted(
            ((reason, len(domains)) for reason, domains in operator_error_domains.items()),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        # Store categorized top 5 for DNS-RSA and URI-RSA tooltips
        metrics['dns_error_top5'] = sorted(simplified_relay_errors['dns'].items(), key=lambda x: x[1], reverse=True)[:5]
        metrics['uri_error_top5'] = sorted(simplified_relay_errors['uri'].items(), key=lambda x: x[1], reverse=True)[:5]
        
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
    
    Categorizes relays into:
    - validated: All 3 AROI fields + validation passed
    - unauthorized: All 3 AROI fields + "fingerprint not found" error
    - misconfigured: All 3 AROI fields + DNS/SSL/timeout errors
    - incomplete_*: Missing 1-2 AROI fields (granular sub-categories)
    - not_configured_*: No AROI fields (granular sub-categories)
    
    Operator status cascade:
    - validated: At least 1 relay passes validation
    - unauthorized: 0 validated AND at least 1 unauthorized
    - misconfigured: 0 validated AND 0 unauthorized AND at least 1 misconfigured/incomplete
    - not_configured: All relays have no AROI info
    
    Args:
        relays: List of relay dictionaries for this contact
        validation_data: Optional validation data from aroivalidator.1aeo.com
        validation_map: Optional pre-built fingerprint -> validation result map (avoids rebuilding)
        
    Returns:
        Dict containing contact-level validation information
    """
    result = {
        'has_aroi': False,
        'validation_status': 'not_configured',  # validated | unauthorized | misconfigured | not_configured
        
        # Complete AROI relays (all 3 fields present)
        'validated_relays': [],
        'unauthorized_relays': [],    # "fingerprint not found" errors
        'misconfigured_relays': [],   # DNS/SSL/timeout errors
        
        # Incomplete AROI relays (1-2 fields) - combined for display
        'incomplete_relays': [],
        
        # No AROI relays (0 fields) - combined for display
        'not_configured_relays': [],
        
        # Fingerprint sets for O(1) lookups in templates
        'validated_fingerprints': set(),
        'unauthorized_fingerprints': set(),
        'misconfigured_fingerprints': set(),
        
        'validation_summary': {
            'total_relays': len(relays),
            'validated_count': 0,
            'unauthorized_count': 0,
            'misconfigured_count': 0,
            'incomplete_count': 0,        # Sum of all incomplete_* counts
            'not_configured_count': 0,    # Sum of all not_configured_* counts
            # Granular counts for troubleshooting tooltips
            'incomplete_no_proof_count': 0,
            'incomplete_no_domain_count': 0,
            'incomplete_no_ciissversion_count': 0,
            'incomplete_missing_two_count': 0,
            'not_configured_no_aroi_info_count': 0,
            'not_configured_no_contact_count': 0,
        },
        'validation_available': False,
        'show_detailed_errors': True
    }
    
    if not relays:
        return result
    
    # Use pre-built validation_map if provided (much faster - avoids rebuilding map 3,000+ times)
    if validation_map is None:
        # FALLBACK: Build fingerprint -> validation result mapping
        validation_map = {}
        if validation_data and 'results' in validation_data:
            for val_result in validation_data.get('results', []):
                fingerprint = val_result.get('fingerprint')
                if fingerprint:
                    validation_map[fingerprint] = val_result
            result['validation_available'] = True
    else:
        result['validation_available'] = len(validation_map) > 0
    
    # Single pass through relays - categorize each one
    for relay in relays:
        fingerprint = relay.get('fingerprint')
        aroi_domain = relay.get('aroi_domain', 'none')
        nickname = relay.get('nickname', 'Unnamed')
        contact = relay.get('contact', '')
        first_seen = relay.get('first_seen', 'Unknown')
        
        # Check if relay has complete AROI setup (all 3 required fields)
        has_complete_aroi = aroi_domain and aroi_domain != 'none'
        
        if has_complete_aroi:
            # Relay has all 3 AROI fields - check validation result
            result['has_aroi'] = True
            
            if fingerprint not in validation_map:
                # Has AROI but not in validation data - treat as misconfigured (unknown status)
                result['validation_summary']['misconfigured_count'] += 1
                result['misconfigured_relays'].append({
                    'fingerprint': fingerprint,
                    'nickname': nickname,
                    'aroi_domain': aroi_domain,
                    'error': 'Not yet processed by validator (relay may be new)',
                    'proof_type': 'unknown',
                    'first_seen': first_seen,
                    'relay': relay,  # Include full relay for table display
                })
                continue
            
            val_result = validation_map[fingerprint]
            
            if val_result.get('valid', False):
                # VALIDATED: Validation passed
                result['validation_summary']['validated_count'] += 1
                result['validated_relays'].append({
                    'fingerprint': fingerprint,
                    'nickname': nickname,
                    'aroi_domain': aroi_domain,
                    'proof_type': val_result.get('proof_type', 'unknown'),
                    'proof_uri': val_result.get('proof_uri', ''),
                    'first_seen': first_seen,
                    'relay': relay,
                })
            else:
                # Validation failed - categorize by error type
                error = val_result.get('error', 'Unknown error')
                error = _deduplicate_fingerprint_not_found_error(error)
                
                # Check if unauthorized error (fingerprint/record not found) -> unauthorized
                # These indicate the relay is NOT in the operator's proof file
                # NXDOMAIN stays as misconfigured (domain doesn't exist = config error, not unauthorized claim)
                # HTTP 404 stays as misconfigured (proof file doesn't exist = setup error)
                error_lower = error.lower()
                is_http_error = '404' in error_lower or 'http error' in error_lower
                is_unauthorized = (
                    not is_http_error and (
                        'fingerprint not found' in error_lower or
                        ('not found' in error_lower and ('dns' in error_lower or 'txt' in error_lower or 'record' in error_lower) and 'nxdomain' not in error_lower)
                    )
                )
                
                relay_info = {
                    'fingerprint': fingerprint,
                    'nickname': nickname,
                    'aroi_domain': aroi_domain,
                    'error': error,  # Show full error from API
                    'proof_type': val_result.get('proof_type', 'unknown'),
                    'first_seen': first_seen,
                    'relay': relay,
                }
                
                if is_unauthorized:
                    result['validation_summary']['unauthorized_count'] += 1
                    result['unauthorized_relays'].append(relay_info)
                else:
                    # SSL/timeout/connection/other errors -> misconfigured
                    result['validation_summary']['misconfigured_count'] += 1
                    result['misconfigured_relays'].append(relay_info)
        else:
            # Relay does NOT have complete AROI - categorize as incomplete or not_configured
            aroi_fields = _check_aroi_fields(contact)
            has_contact = bool(contact and contact.strip())
            category = _categorize_by_missing_fields(aroi_fields, has_contact)
            
            relay_info = {
                'fingerprint': fingerprint,
                'nickname': nickname,
                'aroi_domain': aroi_domain if aroi_domain != 'none' else None,
                'contact': contact,
                'first_seen': first_seen,
                'category': category,
                'relay': relay,
            }
            
            if category in ('no_contact',):
                # Not configured: no contact at all
                result['validation_summary']['not_configured_count'] += 1
                result['validation_summary']['not_configured_no_contact_count'] += 1
                relay_info['missing'] = 'No contact info'
                result['not_configured_relays'].append(relay_info)
            elif category == 'no_aroi_info':
                # Not configured: has contact but no AROI fields
                result['validation_summary']['not_configured_count'] += 1
                result['validation_summary']['not_configured_no_aroi_info_count'] += 1
                relay_info['missing'] = 'Has contact, no AROI fields'
                result['not_configured_relays'].append(relay_info)
            else:
                # Incomplete: has 1-2 AROI fields
                result['has_aroi'] = True  # Has some AROI info
                result['validation_summary']['incomplete_count'] += 1
                
                if category == 'no_proof':
                    result['validation_summary']['incomplete_no_proof_count'] += 1
                    relay_info['missing'] = 'Missing proof field (has domain + ciissversion)'
                elif category == 'no_domain':
                    result['validation_summary']['incomplete_no_domain_count'] += 1
                    relay_info['missing'] = 'Missing domain/URL field (has proof + ciissversion)'
                elif category == 'no_ciissversion':
                    result['validation_summary']['incomplete_no_ciissversion_count'] += 1
                    relay_info['missing'] = 'Missing ciissversion (has proof + domain)'
                elif category == 'missing_two_aroi':
                    result['validation_summary']['incomplete_missing_two_count'] += 1
                    # Identify which 2 fields are missing (only 1 is present)
                    missing_fields = []
                    if not aroi_fields['has_proof']:
                        missing_fields.append('proof')
                    if not aroi_fields['has_url']:
                        missing_fields.append('url/domain')
                    if not aroi_fields['has_ciissversion']:
                        missing_fields.append('ciissversion')
                    relay_info['missing'] = f"Missing {' and '.join(missing_fields)}"
                else:
                    relay_info['missing'] = 'Incomplete AROI configuration'
                
                result['incomplete_relays'].append(relay_info)
    
    # Determine operator status using cascade logic
    summary = result['validation_summary']
    if summary['validated_count'] > 0:
        result['validation_status'] = 'validated'
    elif summary['unauthorized_count'] > 0:
        result['validation_status'] = 'unauthorized'
    elif summary['misconfigured_count'] > 0:
        result['validation_status'] = 'misconfigured'
    elif summary['incomplete_count'] > 0:
        result['validation_status'] = 'incomplete'
    else:
        result['validation_status'] = 'not_configured'
    
    # Build fingerprint sets for O(1) lookups in templates
    result['validated_fingerprints'] = {r['fingerprint'] for r in result['validated_relays']}
    result['unauthorized_fingerprints'] = {r['fingerprint'] for r in result['unauthorized_relays']}
    result['misconfigured_fingerprints'] = {r['fingerprint'] for r in result['misconfigured_relays']}
    
    return result
