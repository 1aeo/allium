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


def _categorize_relay_by_validation(relay: Dict, validation_map: Dict) -> str:
    """
    Categorize a relay by its validation status.
    
    Args:
        relay: Relay dictionary from Onionoo API
        validation_map: Map of fingerprint -> validation result
        
    Returns:
        Category string: 'validated', 'unvalidated', 'no_proof', or 'no_aroi'
    """
    fingerprint = relay.get('fingerprint')
    aroi_domain = relay.get('aroi_domain', 'none')
    contact = relay.get('contact', '')
    
    if fingerprint in validation_map:
        result = validation_map[fingerprint]
        if result.get('valid', False):
            return 'validated'
        error = result.get('error', '')
        if error == 'No contact information':
            return 'no_aroi'
        elif error == 'Missing AROI fields':
            return 'no_proof'
        else:
            return 'unvalidated'
    else:
        # Fallback to local analysis
        if aroi_domain and aroi_domain != 'none':
            return 'unvalidated'
        elif contact and contact.strip():
            return 'no_proof'
        else:
            return 'no_aroi'


def calculate_aroi_validation_metrics(relays: List[Dict], validation_data: Optional[Dict] = None) -> Dict:
    """
    Calculate AROI validation metrics for network health dashboard.
    
    Analyzes relay fingerprints against validation data to determine:
    - How many relays have valid AROI proofs (dns-rsa or uri-rsa)
    - How many relays have invalid/failed AROI validation
    - How many relays have no AROI information
    - Success rates by proof type (dns-rsa vs uri-rsa)
    
    Args:
        relays: List of relay dictionaries from Onionoo API
        validation_data: Optional validation data from aroivalidator.1aeo.com
        
    Returns:
        Dict containing validation metrics for health dashboard
    """
    # Initialize metrics with safe defaults
    metrics = {
        'aroi_validated_count': 0,
        'aroi_unvalidated_count': 0,
        'aroi_no_proof_count': 0,
        'relays_no_aroi': 0,
        'aroi_validated_percentage': 0.0,
        'aroi_unvalidated_percentage': 0.0,
        'aroi_no_proof_percentage': 0.0,
        'relays_no_aroi_percentage': 0.0,
        'aroi_validation_success_rate': 0.0,
        'dns_rsa_success_rate': 0.0,
        'uri_rsa_success_rate': 0.0,
        'dns_rsa_total': 0,
        'dns_rsa_valid': 0,
        'uri_rsa_total': 0,
        'uri_rsa_valid': 0,
        'validation_data_available': False,
        'validation_timestamp': 'Unknown'
    }
    
    if not relays:
        return metrics
    
    total_relays = len(relays)
    
    # If no validation data available, return early with basic counts
    if not validation_data or 'results' not in validation_data:
        # Count relays with/without AROI based on contact info
        for relay in relays:
            aroi_domain = relay.get('aroi_domain', 'none')
            contact = relay.get('contact', '')
            
            if aroi_domain and aroi_domain != 'none':
                # Has AROI domain but no validation data available
                metrics['aroi_unvalidated_count'] += 1
            elif contact and contact.strip():
                # Has contact but no AROI domain
                metrics['aroi_no_proof_count'] += 1
            else:
                # No contact information at all
                metrics['relays_no_aroi'] += 1
        
        # Calculate percentages using helper function
        metrics['aroi_unvalidated_percentage'] = _calc_percentage(metrics['aroi_unvalidated_count'], total_relays)
        metrics['aroi_no_proof_percentage'] = _calc_percentage(metrics['aroi_no_proof_count'], total_relays)
        metrics['relays_no_aroi_percentage'] = _calc_percentage(metrics['relays_no_aroi'], total_relays)
        
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
    
    # Process each relay and categorize by validation status
    for relay in relays:
        category = _categorize_relay_by_validation(relay, validation_map)
        
        if category == 'validated':
            metrics['aroi_validated_count'] += 1
        elif category == 'unvalidated':
            metrics['aroi_unvalidated_count'] += 1
        elif category == 'no_proof':
            metrics['aroi_no_proof_count'] += 1
        else:  # no_aroi
            metrics['relays_no_aroi'] += 1
    
    # Calculate percentages using helper function
    metrics['aroi_validated_percentage'] = _calc_percentage(metrics['aroi_validated_count'], total_relays)
    metrics['aroi_unvalidated_percentage'] = _calc_percentage(metrics['aroi_unvalidated_count'], total_relays)
    metrics['aroi_no_proof_percentage'] = _calc_percentage(metrics['aroi_no_proof_count'], total_relays)
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


def get_contact_validation_status(relays: List[Dict], validation_data: Optional[Dict] = None) -> Dict:
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
    
    # Build fingerprint -> validation result mapping FIRST
    # This way we check validation data directly, not just parsed aroi_domain
    validation_map = {}
    if validation_data and 'results' in validation_data:
        for val_result in validation_data.get('results', []):
            fingerprint = val_result.get('fingerprint')
            if fingerprint:
                validation_map[fingerprint] = val_result
        result['validation_available'] = True
    
    # Check if any relay has AROI based on validation data OR parsed domain
    aroi_domains = set()
    for relay in relays:
        fingerprint = relay.get('fingerprint')
        aroi_domain = relay.get('aroi_domain', 'none')
        
        # Check both validation data and parsed domain
        has_validation_result = fingerprint in validation_map
        has_parsed_domain = aroi_domain and aroi_domain != 'none'
        
        if has_validation_result or has_parsed_domain:
            result['has_aroi'] = True
            if has_parsed_domain:
                aroi_domains.add(aroi_domain)
    
    if not result['has_aroi']:
        return result
    
    # If no validation data available, mark as unvalidated
    if not validation_map:
        result['validation_status'] = 'unvalidated'
        result['validation_summary']['relays_with_aroi'] = len([r for r in relays if r.get('aroi_domain') and r.get('aroi_domain') != 'none'])
        result['unvalidated_relays'] = [{
            'fingerprint': r.get('fingerprint', ''),
            'nickname': r.get('nickname', 'Unnamed'),
            'aroi_domain': r.get('aroi_domain', 'none'),
            'error': 'Validation data not available'
        } for r in relays if r.get('aroi_domain') and r.get('aroi_domain') != 'none']
        return result
    
    # Process each relay
    for relay in relays:
        fingerprint = relay.get('fingerprint')
        aroi_domain = relay.get('aroi_domain', 'none')
        nickname = relay.get('nickname', 'Unnamed')
        
        # Skip relays with no validation result (they don't have AROI fields)
        if fingerprint not in validation_map:
            continue
        
        result['validation_summary']['relays_with_aroi'] += 1
        
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
            result['validation_summary']['unvalidated_count'] += 1
            result['unvalidated_relays'].append({
                'fingerprint': fingerprint,
                'nickname': nickname,
                'aroi_domain': aroi_domain if aroi_domain != 'none' else 'unknown',
                'error': val_result.get('error', 'Unknown error'),
                'proof_type': val_result.get('proof_type', 'unknown'),
            })
    
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
    
    # Check if all errors are just "Missing AROI fields" - if so, don't show detailed list
    # This avoids repetitive display when operator hasn't configured AROI at all
    if result['unvalidated_relays']:
        all_missing_aroi = all(
            relay.get('error', '').strip() == 'Missing AROI fields'
            for relay in result['unvalidated_relays']
        )
        if all_missing_aroi:
            result['show_detailed_errors'] = False
    
    return result
